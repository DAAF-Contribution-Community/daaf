"""Executor module: runs a single benchmark test case via Claude Code CLI.

Wraps `claude -p` invocation with model selection, turn limits, and output
capture. Designed to run INSIDE the DAAF container so all hooks fire and
the full framework is exercised.
"""

import json
import subprocess
import time
from pathlib import Path

from benchmarks.harness.models import RunConfig, RunResult


# Timeout per cost tier (seconds)
TIMEOUT_BY_TIER = {
    "low": 120,      # 2 minutes for simple classification
    "medium": 300,   # 5 minutes for multi-turn protocol tests
    "high": 600,     # 10 minutes for code generation tests
}


def execute_run(config: RunConfig) -> RunResult:
    """Execute a single benchmark run via claude -p.

    Launches Claude Code in headless mode with the test case prompt,
    captures the JSON output, and returns a RunResult.
    """
    test_case = config.test_case
    model = config.model

    # Build the CLI command
    cmd = [
        "claude",
        "-p", test_case.prompt,
        "--model", model.id,
        "--output-format", "json",
        "--max-turns", str(test_case.turn_limit),
        "--permission-mode", config.permission_mode,
    ]

    # Build environment with any model-specific overrides
    import os
    env = os.environ.copy()
    env.update(model.env_overrides)

    timeout = TIMEOUT_BY_TIER.get(test_case.cost_tier, 300)

    result = RunResult(
        test_case_id=test_case.id,
        model_id=model.id,
        model_name=model.name,
        run_index=config.run_index,
    )

    start_time = time.time()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=config.working_dir,
            env=env,
        )

        result.exit_code = proc.returncode
        result.duration_seconds = time.time() - start_time

        if proc.returncode != 0 and not proc.stdout.strip():
            result.error = f"CLI exited with code {proc.returncode}: {proc.stderr[:500]}"
            return result

        # Parse JSON output.
        # claude -p --output-format json returns a JSON array of messages:
        #   [{type: "system", subtype: "init", ...},
        #    {type: "assistant", message: {content: [...]}},
        #    ...,
        #    {type: "result", subtype: "success", session_id, result, total_cost_usd, ...}]
        stdout = proc.stdout.strip()
        if stdout:
            try:
                output = json.loads(stdout)

                # Handle list-of-messages format
                if isinstance(output, list):
                    result.raw_json = {"messages": output}

                    # Find the result message (last item with type=result)
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

                    # Also extract the last assistant text as response if
                    # result.response_text is empty
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
                    # Fallback: single dict format (future-proofing)
                    result.raw_json = output
                    result.session_id = output.get("session_id", "")
                    result.response_text = output.get("result", "")
                    result.total_cost_usd = output.get("total_cost_usd", 0.0)
                    result.total_turns = output.get("num_turns", 0)

            except json.JSONDecodeError as e:
                result.error = f"Failed to parse JSON output: {e}"
                result.response_text = stdout[:2000]

        # Capture stderr for diagnostics (but don't treat as error)
        if proc.stderr.strip():
            stderr_summary = proc.stderr.strip()[:500]
            if result.error:
                result.error += f"\nstderr: {stderr_summary}"

    except subprocess.TimeoutExpired:
        result.duration_seconds = time.time() - start_time
        result.error = f"Timed out after {timeout}s"

    except Exception as e:
        result.duration_seconds = time.time() - start_time
        result.error = f"Execution error: {type(e).__name__}: {e}"

    return result


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
