"""Executor module: runs a single benchmark test case via Claude Code CLI.

Wraps `claude -p` invocation with model selection, turn limits, and output
capture. Designed to run INSIDE the DAAF container so all hooks fire and
the full framework is exercised.
"""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from benchmarks.harness.models import RunConfig, RunResult
from benchmarks.harness.checkpoint_manager import prepare_sandbox, cleanup_sandbox


# Timeout per cost tier (seconds)
TIMEOUT_BY_TIER = {
    "low": 120,      # 2 minutes for simple classification
    "medium": 300,   # 5 minutes for multi-turn protocol tests
    "high": 600,     # 10 minutes for code generation tests
}

# Grace window between SIGTERM and SIGKILL for timed-out runs (seconds).
# Claude Code's main-session transcript writes are async/buffered; a hard
# SIGKILL races the writer and can truncate the transcript tail (lost Agent
# tool_use records — see README § 11 item 9). SIGTERM first gives the CLI a
# chance to flush before the hard kill lands.
KILL_GRACE_SECONDS = 15


def execute_run(config: RunConfig) -> RunResult:
    """Execute a single benchmark run via claude -p.

    Launches Claude Code in headless mode with the test case prompt,
    captures the JSON output, and returns a RunResult.
    """
    test_case = config.test_case
    model = config.model

    # Handle golden checkpoint setup
    checkpoint_session_id = None
    if test_case.golden_checkpoint:
        golden_path = Path("/daaf") / test_case.golden_checkpoint
        sandbox_path = Path(config.sandbox_dir)
        checkpoint_session_id = prepare_sandbox(
            golden_path, sandbox_path,
            project_path=test_case.golden_project_path,
            wipe_sandbox=config.wipe_sandbox,
        )

    # Pre-assign session ID for cold starts so we can always locate the
    # transcript, even after timeout. Golden checkpoint runs already have
    # a known session_id from prepare_sandbox; cold starts need one too.
    cold_start_session_id = None
    if not checkpoint_session_id:
        cold_start_session_id = str(uuid.uuid4())

    # Build the CLI command
    cmd = [
        "claude",
        "-p", test_case.prompt,
        "--model", model.id,
        "--output-format", "json",
        "--max-turns", str(test_case.turn_limit),
        "--permission-mode", config.permission_mode,
    ]

    if config.disallowed_tools:
        cmd.append("--disallowed-tools")
        cmd.extend(config.disallowed_tools)

    if checkpoint_session_id:
        cmd.extend(["--resume", checkpoint_session_id])

    if cold_start_session_id:
        cmd.extend(["--session-id", cold_start_session_id])

    if model.effort_level:
        cmd.extend(["--effort", model.effort_level])

    # Build environment with any model-specific overrides.
    # Explicitly set CLAUDE_CODE_EFFORT_LEVEL to match --effort flag so it
    # overrides the settings.json env value (which defaults to "high").
    env = os.environ.copy()
    # Activates the benchmark-scoped git-blocking hook (block-git-writes.sh)
    # for this run and all subagent sessions it spawns; inert in normal sessions.
    env["DAAF_BENCHMARK_RUN"] = "1"
    if model.effort_level:
        env["CLAUDE_CODE_EFFORT_LEVEL"] = model.effort_level
    env.update(model.env_overrides)

    timeout = config.timeout_override or TIMEOUT_BY_TIER.get(test_case.cost_tier, 300)

    result = RunResult(
        test_case_id=test_case.id,
        model_id=model.id,
        model_name=model.name,
        run_index=config.run_index,
    )

    start_time = time.time()

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=config.working_dir,
            env=env,
        )

        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Graceful shutdown ladder: SIGTERM -> grace window -> SIGKILL.
            stdout, stderr = _graceful_kill(proc)
            timed_out = True

        result.duration_seconds = time.time() - start_time

        if timed_out:
            # Try parsing partial stdout captured through the kill sequence
            # (everything the CLI emitted before SIGTERM plus anything it
            # flushed during the grace window).
            if stdout:
                _parse_json_output(stdout, result)

            # Set the timeout error AFTER parsing: _parse_json_output writes
            # a parse-failure message into result.error on broken partial
            # JSON, and downstream timed_out detection keys on this exact
            # string ("Timed out" substring — see runner result dicts).
            result.error = f"Timed out after {timeout}s"

            # Use the known session_id — either from golden checkpoint or
            # pre-assigned via --session-id for cold starts.
            if not result.session_id:
                result.session_id = checkpoint_session_id or cold_start_session_id or ""
            return result

        result.exit_code = proc.returncode

        if proc.returncode != 0 and not stdout.strip():
            result.error = f"CLI exited with code {proc.returncode}: {stderr[:500]}"
            return result

        _parse_json_output(stdout, result)
        _extract_tool_failures(result)

        # Capture stderr for diagnostics (but don't treat as error)
        if stderr.strip():
            stderr_summary = stderr.strip()[:500]
            if result.error:
                result.error += f"\nstderr: {stderr_summary}"

    except Exception as e:
        # Defensive cleanup: subprocess.run() reaped the child internally;
        # with Popen we must not leak a live CLI process on unexpected errors.
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.communicate()
        result.duration_seconds = time.time() - start_time
        result.error = f"Execution error: {type(e).__name__}: {e}"
        if not result.session_id:
            result.session_id = checkpoint_session_id or cold_start_session_id or ""

    # NOTE: cleanup_sandbox is NOT called here. The runner is responsible
    # for calling cleanup_sandbox() AFTER scoring and archiving the
    # transcript. This ensures timed-out runs still produce scorable data.

    return result


def _graceful_kill(proc: subprocess.Popen) -> tuple[str, str]:
    """Terminate a timed-out CLI process via a graceful shutdown ladder.

    SIGTERM -> wait up to KILL_GRACE_SECONDS -> SIGKILL. The grace window
    lets Claude Code flush its async/buffered main-session transcript writes
    before dying (README § 11 item 9 — a hard SIGKILL truncates the
    transcript tail, losing records like the Agent tool_use block).

    Uses communicate() rather than wait() for the grace wait: the CLI may
    keep writing to stdout/stderr while flushing, and wait() with full pipes
    deadlocks. communicate() keeps draining the pipes, and per the subprocess
    docs a retried communicate() after TimeoutExpired loses no output.

    Returns (stdout, stderr) accumulated across the entire process lifetime,
    including anything emitted during the grace window.
    """
    proc.terminate()  # SIGTERM — request shutdown, allow transcript flush
    try:
        stdout, stderr = proc.communicate(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()  # SIGKILL — grace window expired, hard stop
        stdout, stderr = proc.communicate()
    return stdout or "", stderr or ""


def _parse_json_output(stdout_raw: str, result: RunResult) -> None:
    """Parse claude -p JSON output into a RunResult.

    claude -p --output-format json returns a JSON array of messages:
      [{type: "system", subtype: "init", ...},
       {type: "assistant", message: {content: [...]}},
       ...,
       {type: "result", subtype: "success", session_id, result, total_cost_usd, ...}]
    """
    stdout = stdout_raw.strip()
    if not stdout:
        return

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        result.error = f"Failed to parse JSON output: {e}"
        result.response_text = stdout[:2000]
        return

    if isinstance(output, list):
        result.raw_json = {"messages": output}

        result_msg = None
        for msg in reversed(output):
            if isinstance(msg, dict) and msg.get("type") == "result":
                result_msg = msg
                break

        if result_msg:
            result.session_id = result_msg.get("session_id", "")
            result.response_text = result_msg.get("result", "")
            result.total_cost_usd = result_msg.get("total_cost_usd", 0.0)
            result.total_turns = result_msg.get("num_turns", 0)
            duration_ms = result_msg.get("duration_ms", 0)
            if duration_ms:
                result.duration_seconds = duration_ms / 1000.0
            _extract_token_usage(result_msg, result)

        if not result.response_text:
            for msg in reversed(output):
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") == "assistant":
                    content = msg.get("message", {}).get("content", [])
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            result.response_text = block.get("text", "")
                            break
                    if result.response_text:
                        break

    elif isinstance(output, dict):
        result.raw_json = output
        result.session_id = output.get("session_id", "")
        result.response_text = output.get("result", "")
        result.total_cost_usd = output.get("total_cost_usd", 0.0)
        result.total_turns = output.get("num_turns", 0)
        _extract_token_usage(output, result)


def _extract_token_usage(msg: dict, result: "RunResult") -> None:
    """Extract token usage from a CLI result message.

    The CLI returns usage in two places:
      - msg["usage"]: main session only (excludes subagent token consumption)
      - msg["modelUsage"]: per-model breakdown that aggregates across main
        session AND all subagent sessions

    We prefer "modelUsage" because it captures the true total cost including
    subagents dispatched via the Agent tool. Falls back to "usage" when
    modelUsage is absent (e.g., older CLI versions).
    """
    model_usage = msg.get("modelUsage")
    if isinstance(model_usage, dict):
        for model_key, mu in model_usage.items():
            if isinstance(mu, dict):
                result.input_tokens += mu.get("inputTokens", 0)
                result.output_tokens += mu.get("outputTokens", 0)
                result.cache_read_tokens += mu.get("cacheReadInputTokens", 0)
                result.cache_creation_tokens += mu.get("cacheCreationInputTokens", 0)
        return

    usage = msg.get("usage")
    if isinstance(usage, dict):
        result.input_tokens = usage.get("input_tokens", 0)
        result.output_tokens = usage.get("output_tokens", 0)
        result.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
        result.cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)


def _extract_tool_content(content) -> str:
    """Extract text from a tool_result content field.

    Content can be a plain string or a list of content blocks:
      [{"type": "text", "text": "..."}, ...]
    """
    if isinstance(content, str):
        return content[:500]
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)[:500]
    return str(content)[:500]


def _extract_tool_failures(result: RunResult) -> None:
    """Extract tool call failures from parsed JSON output.

    Scans the messages array for tool_result blocks with is_error=True,
    cross-references with tool_use blocks to get the tool name.
    """
    messages = result.raw_json.get("messages", [])
    if not messages:
        return

    # Build tool_use_id -> tool_name map from assistant messages
    tool_names = {}
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("type") != "assistant":
            continue
        for block in msg.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_names[block.get("id", "")] = block.get("name", "unknown")

    # Find failed tool_results in user messages
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("type") != "user":
            continue
        for block in msg.get("message", {}).get("content", []):
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            if not block.get("is_error", False):
                continue

            tool_use_id = block.get("tool_use_id", "")
            result.tool_failures.append({
                "tool_use_id": tool_use_id,
                "tool_name": tool_names.get(tool_use_id, "unknown"),
                "content": _extract_tool_content(block.get("content", "")),
            })




def check_cli_available() -> bool:
    """Verify that the claude CLI is available and responsive."""
    try:
        proc = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_hooks_active(working_dir: str = "/daaf") -> dict[str, bool]:
    """Check which DAAF hooks are likely active by examining settings.json.

    DAAF settings.json uses a nested structure:
    {event: [{matcher, hooks: [{command, ...}]}]}
    """
    settings_path = Path(working_dir) / ".claude" / "settings.json"
    hooks_found = {
        "audit_log": False,
        "bash_safety": False,
        "enforce_file_first": False,
        "context_reporter": False,
        "archive_session": False,
        "output_scanner": False,
    }

    if not settings_path.exists():
        return hooks_found

    # Map hook script names to our key names
    hook_name_map = {
        "audit-log": "audit_log",
        "bash-safety": "bash_safety",
        "enforce-file-first": "enforce_file_first",
        "context-reporter": "context_reporter",
        "archive-session": "archive_session",
        "output-scanner": "output_scanner",
    }

    try:
        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        for event_matchers in hooks.values():
            if not isinstance(event_matchers, list):
                continue
            for matcher_group in event_matchers:
                inner_hooks = matcher_group.get("hooks", [])
                if not isinstance(inner_hooks, list):
                    continue
                for hook_def in inner_hooks:
                    cmd = hook_def.get("command", "") if isinstance(hook_def, dict) else ""
                    for script_name, key in hook_name_map.items():
                        if script_name in cmd:
                            hooks_found[key] = True
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return hooks_found
