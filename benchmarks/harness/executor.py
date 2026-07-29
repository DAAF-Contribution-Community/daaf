"""Executor module: runs a single benchmark test case via Claude Code CLI.

Wraps `claude -p` invocation with model selection, turn limits, and output
capture. Designed to run INSIDE the DAAF container so all hooks fire and
the full framework is exercised.
"""

import json
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.harness.models import RunConfig, RunResult
from benchmarks.harness.route_provenance import (
    CHATGPT_PROVIDER,
    build_chatgpt_child_env,
    revalidate_route,
)
from benchmarks.harness.checkpoint_manager import prepare_sandbox, cleanup_sandbox
from benchmarks.harness.cost_estimator import compute_accounting
from benchmarks.scorers.deterministic.checkpoint_adherence import (
    find_benchmark_transcript,
)
from benchmarks.scorers.deterministic.subagent_behavior import (
    find_subagent_transcripts,
)
from benchmarks.scorers.deterministic.error_classification import (
    classify_tool_failure_class,
)


# Uniform fallback timeout (seconds). Only fires if a caller passes
# timeout_override=None explicitly; the phase runners always pass their
# argparse default, so this is off the normal path. Set to match the runners'
# uniform 900s logistical cap (2026-07-21 walltime redesign, replacing the
# former per-cost-tier dict of 120/300/600).
DEFAULT_TIMEOUT_S = 900

# Grace window between SIGTERM and SIGKILL for timed-out runs (seconds).
# Observed timeout archives sometimes lack terminal parent-side evidence. As a
# precaution, SIGTERM first gives the CLI an orderly shutdown interval before
# escalation. This does not establish Claude Code's write internals or prove
# that SIGKILL caused any particular missing transcript tail (README § 11).
KILL_GRACE_SECONDS = 15


def _finalize_result(result: RunResult, model, start_time: float) -> None:
    """Stamp caller timing and attach the provider-appropriate accounting ledgers."""
    result.end_time_utc = datetime.now(timezone.utc).isoformat()
    result.wall_clock_seconds = time.time() - start_time
    if model.provider == CHATGPT_PROVIDER:
        accounting = compute_accounting(model, result)
        result.actual_billing = accounting["actual_billing"]
        result.api_equivalent = accounting["api_equivalent"]
        result.subscription_capacity = accounting["subscription_capacity"]


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
    # Model configuration, not an unrelated parent shell, owns the flatten
    # selector. Scrub ambient leakage first; an explicit per-model override below
    # is intentionally re-applied by env.update().
    env.pop("CLAUDE_CODE_SUBAGENT_MODEL", None)
    # Activates the benchmark-scoped git-blocking hook (block-git-writes.sh)
    # for this run and all subagent sessions it spawns; inert in normal sessions.
    env["DAAF_BENCHMARK_RUN"] = "1"
    if model.effort_level:
        env["CLAUDE_CODE_EFFORT_LEVEL"] = model.effort_level
    env.update(model.env_overrides)
    if model.context_window_tokens is not None:
        env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(model.context_window_tokens)

    # Since 2026-07-21 the phase runners set a uniform --timeout default (900s
    # logistical cap; formerly 120/180/300/300 per-phase), so timeout_override
    # is always truthy on the default path and the uniform fallback below only
    # fires if a caller passes timeout_override=None explicitly.
    timeout = config.timeout_override or DEFAULT_TIMEOUT_S

    result = RunResult(
        test_case_id=test_case.id,
        model_id=model.id,
        model_name=model.name,
        run_index=config.run_index,
    )
    result.model_identity.benchmark_key = (
        model.key or model.name.lower().replace(" ", "-").replace(".", "")
    )
    result.model_identity.requested_model_id = model.id
    if model.provider == CHATGPT_PROVIDER:
        result.total_cost_usd = None
        result.actual_billing.access_type = "chatgpt_subscription"
        result.actual_billing.charge_status = (
            model.actual_billing_treatment or "not_separately_billed"
        )
        result.actual_billing.actual_marginal_charge_usd = None

    start_time = time.time()
    result.start_time_utc = datetime.now(timezone.utc).isoformat()

    proc = None
    try:
        # Per-run route validation is intentionally the final operation before
        # launch. Resolve the local child overlay again so a long-lived process
        # cannot retain a stale registry-time port, then check ambient
        # deployment coherence and live daemon state. Any mismatch raises
        # before subprocess.Popen can execute claude -p.
        if model.provider == CHATGPT_PROVIDER:
            env.update(build_chatgpt_child_env(os.environ))
        result.route_provenance = revalidate_route(model, environ=os.environ)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=config.working_dir,
            env=env,
        )

        # The session id is knowable pre-launch (golden checkpoint resume or the
        # pre-assigned cold-start uuid), so the watchdog can locate the live
        # parent/subagent transcripts while the run is still in flight.
        watchdog_session_id = checkpoint_session_id or cold_start_session_id or ""

        timed_out = False
        # Watchdog engages only when a caller opts in (stall detection and/or an
        # early-stop callback). With neither, the path below is byte-identical to
        # the pre-watchdog harness: a single blocking communicate() with the
        # SIGTERM->grace->SIGKILL ladder on timeout.
        watchdog_active = (
            config.stall_detection or config.early_stop_check is not None
        )
        if not watchdog_active:
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Graceful shutdown ladder: SIGTERM -> grace window -> SIGKILL.
                stdout, stderr = _graceful_kill(proc)
                timed_out = True
        else:
            stdout, stderr, reason, stall_diag = _watchdog_wait(
                proc, config, watchdog_session_id, start_time, timeout
            )
            if reason == "timeout":
                timed_out = True
            elif reason == "early_stop":
                result.early_stopped = True
                # Comparable "time-to-demonstrated-compliance" duration: launch ->
                # first early-stop-check pass of the confirmed episode, excluding
                # the confirmation poll and kill tail (README § 8). May be None if
                # the executor cannot attribute it (defensive).
                result.score_complete_seconds = stall_diag.get(
                    "score_complete_seconds"
                )
            elif reason == "stalled":
                result.stalled = True
                result.stall_diagnostics = stall_diag

        result.duration_seconds = time.time() - start_time

        # Early-stop and stall are terminal, non-timeout outcomes. Scoring is
        # done downstream from the live/archived transcript (not from stdout), so
        # the known session id is all the runner needs. An early stop is
        # score-neutral by construction (all monotone-pass criteria already
        # settled), so we deliberately do NOT set result.error for it; a stall is
        # a run-health failure and carries a distinct, non-"Timed out" message.
        if result.early_stopped or result.stalled:
            if not result.session_id:
                result.session_id = watchdog_session_id
            if result.stalled:
                result.error = (
                    f"Stalled: transcript inactive beyond "
                    f"{config.stall_threshold_seconds}s across "
                    f"{config.stall_consecutive_reads} consecutive watchdog polls"
                )
            _finalize_result(result, model, start_time)
            return result

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
            _finalize_result(result, model, start_time)
            return result

        result.exit_code = proc.returncode

        if proc.returncode != 0 and not stdout.strip():
            result.error = f"CLI exited with code {proc.returncode}: {stderr[:500]}"
            _finalize_result(result, model, start_time)
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

    _finalize_result(result, model, start_time)
    return result


def _graceful_kill(proc: subprocess.Popen) -> tuple[str, str]:
    """Terminate a timed-out CLI process via a graceful shutdown ladder.

    SIGTERM -> wait up to KILL_GRACE_SECONDS -> SIGKILL. Observed timeout
    archives sometimes lack terminal parent-side evidence, so the grace window
    is a precaution that permits orderly CLI shutdown before escalation. It
    does not establish the CLI's transcript-write internals or attribute any
    particular missing tail to SIGKILL (README § 11).

    Uses communicate() rather than wait() for the grace wait: the CLI may
    keep writing to stdout/stderr during shutdown, and wait() with full pipes
    deadlocks. communicate() keeps draining the pipes, and per the subprocess
    docs a retried communicate() after TimeoutExpired loses no output.

    Returns (stdout, stderr) accumulated across the entire process lifetime,
    including anything emitted during the grace window.
    """
    proc.terminate()  # SIGTERM — request orderly shutdown before escalation
    try:
        stdout, stderr = proc.communicate(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()  # SIGKILL — grace window expired, hard stop
        stdout, stderr = proc.communicate()
    return stdout or "", stderr or ""


def _transcript_recency(session_id, find_parent, find_subs):
    """Aggregate the most-recent activity time across parent AND subagent
    transcripts for a live run.

    Returns (latest_mtime_or_None, parent_exists_bool, lookup_errors_int).
    Staleness must aggregate max-recency across BOTH the parent and every
    subagent transcript: a parent-only monitor false-alarms while the parent
    blocks on long subagent work (validated in the K3 rerun campaign). File mtime
    is used as the activity signal because the CLI appends records as it works, so
    mtime advances with real progress; it is read defensively (a transcript may
    not exist yet, or may vanish between the find and the stat).

    A lookup FUNCTION raising (find_parent/find_subs) is distinct from a
    transcript legitimately not existing yet: the former is a monitoring
    regression that would silently masquerade as a model stall (no mtime -> looks
    like dead air). Such exceptions are counted in ``lookup_errors`` and printed
    as WARNINGs (parallel to the early-stop path's warning style) so the caller
    can surface them in stall_diagnostics rather than misattributing them. The
    stall DECISION logic is intentionally unchanged: a lookup error still yields
    no mtime for this poll, exactly as a genuinely absent transcript does.
    """
    mtimes = []
    parent_exists = False
    lookup_errors = 0
    try:
        parent = find_parent(session_id)
    except Exception as e:
        parent = None
        lookup_errors += 1
        print(
            f"WARNING: transcript parent lookup raised {type(e).__name__}: {e}; "
            f"treating as no parent activity this poll (not a model stall)."
        )
    if parent is not None:
        parent_exists = True
        try:
            mtimes.append(Path(parent).stat().st_mtime)
        except OSError:
            pass
    try:
        subs = find_subs(session_id)
    except Exception as e:
        subs = []
        lookup_errors += 1
        print(
            f"WARNING: transcript subagent lookup raised {type(e).__name__}: {e}; "
            f"treating as no subagent activity this poll (not a model stall)."
        )
    for sub in subs or []:
        try:
            mtimes.append(Path(sub).stat().st_mtime)
        except OSError:
            pass
    latest = max(mtimes) if mtimes else None
    return latest, parent_exists, lookup_errors


def _graceful_kill_threaded(proc, reader_threads):
    """SIGTERM -> grace -> SIGKILL for the watchdog path, then join the pipe
    reader threads so all buffered stdout/stderr is collected.

    The watchdog drains stdout/stderr via background reader threads (a naive wait
    loop would deadlock once ``claude -p --output-format json`` fills the pipe
    buffer, because that format emits its JSON only at exit). Those threads own
    the pipe file objects, so this kill path must NOT call proc.communicate()
    (which would race the readers); it waits on the process and then joins the
    readers, which return when the pipes close on process death.
    """
    proc.terminate()  # SIGTERM
    try:
        proc.wait(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()  # SIGKILL — grace window expired
        try:
            proc.wait(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass
    for t in reader_threads:
        t.join(timeout=KILL_GRACE_SECONDS)


def _watchdog_wait(
    proc,
    config,
    session_id,
    start_time,
    timeout,
    find_parent=find_benchmark_transcript,
    find_subs=find_subagent_transcripts,
    now_fn=time.time,
):
    """Poll a running ``claude -p`` process, draining stdout/stderr on background
    reader threads, and terminate early on score-complete or stall.

    Returns ``(stdout, stderr, reason, diagnostics)`` where ``reason`` is one of:
      - ``None``  — the process exited on its own before any watchdog action.
      - ``"timeout"``    — the 900s wall-clock backstop fired (unchanged policy).
      - ``"early_stop"`` — ``early_stop_check`` returned True on two consecutive
                           polls (an initial hit plus one confirmation poll that
                           protects the subagent-transcript flush race).
      - ``"stalled"``    — ``stall_consecutive_reads`` consecutive stalled
                           readings (>``stall_threshold_seconds`` staleness, or
                           no transcript at all past
                           ``stall_first_activity_seconds``).

    The lookup functions and clock are injectable so the decision logic can be
    unit-tested against a synthetic subprocess (e.g. ``sleep``) and transcript
    files with controlled mtimes, without launching the CLI.
    """
    stdout_box = []
    stderr_box = []

    def _drain(pipe, box):
        try:
            box.append(pipe.read())
        except Exception:
            box.append("")

    reader_threads = [
        threading.Thread(target=_drain, args=(proc.stdout, stdout_box), daemon=True),
        threading.Thread(target=_drain, args=(proc.stderr, stderr_box), daemon=True),
    ]
    for t in reader_threads:
        t.start()

    poll = config.watchdog_poll_seconds or 60
    deadline = start_time + timeout
    early_stop_pending = False  # True after an initial hit, awaiting confirmation
    # Elapsed wall time (launch -> the poll at which early_stop_check first
    # returned True for the episode that ultimately confirms). This is a
    # "time-to-demonstrated-compliance" measure: it deliberately EXCLUDES the
    # confirmation poll and the SIGTERM/SIGKILL tail, so the viewer can use it as
    # a comparable duration contribution for completed_early runs (README § 8).
    # Reset alongside early_stop_pending on an intermittent False so it always
    # reflects the first hit of the winning episode.
    score_complete_at = None
    stall_reads = 0
    lookup_errors_total = 0
    poll_history = []
    reason = None

    while True:
        try:
            proc.wait(timeout=poll)
            reason = None  # exited on its own
            break
        except subprocess.TimeoutExpired:
            pass

        now = now_fn()

        # Wall-clock backstop is unchanged: the 900s cap still governs.
        if now >= deadline:
            reason = "timeout"
            break

        # --- Score-complete early stop (with confirmation poll) ---
        if config.early_stop_check is not None:
            try:
                done = bool(config.early_stop_check(session_id))
            except Exception as e:
                # Never kill on a scorer crash — treat as "not done" but log it.
                done = False
                print(
                    f"WARNING: early_stop_check raised {type(e).__name__}: {e}; "
                    f"not early-stopping this poll."
                )
            if done:
                if early_stop_pending:
                    reason = "early_stop"
                    break
                # First hit: require one more confirming poll before killing.
                # This also gives the subagent-transcript flush a poll-width
                # grace so the dispatch-recovery fallback has records on disk.
                early_stop_pending = True
                score_complete_at = now - start_time
            else:
                early_stop_pending = False
                score_complete_at = None

        # --- Stall detection ---
        if config.stall_detection:
            latest, parent_exists, lookup_errors = _transcript_recency(
                session_id, find_parent, find_subs
            )
            lookup_errors_total += lookup_errors
            elapsed = now - start_time
            if latest is None:
                # No parent OR subagent transcript activity exists at all yet.
                staleness = elapsed
                is_stalled_read = elapsed > config.stall_first_activity_seconds
            else:
                staleness = now - latest
                is_stalled_read = staleness > config.stall_threshold_seconds
            poll_history.append(round(staleness, 1))
            if is_stalled_read:
                stall_reads += 1
                if stall_reads >= config.stall_consecutive_reads:
                    reason = "stalled"
                    break
            else:
                stall_reads = 0

    if reason is not None:
        _graceful_kill_threaded(proc, reader_threads)
    else:
        for t in reader_threads:
            t.join()

    stdout = stdout_box[0] if stdout_box else ""
    stderr = stderr_box[0] if stderr_box else ""
    # The reader threads own the pipe file objects and have now joined (either via
    # _graceful_kill_threaded or the plain join above), so no reader can race a
    # close here. Explicitly close the pipes to release the fds promptly rather
    # than leaning on GC/finalizer timing.
    for pipe in (proc.stdout, proc.stderr):
        try:
            if pipe is not None:
                pipe.close()
        except Exception:
            pass
    diagnostics = {
        "reason": reason,
        "stall_reads": stall_reads,
        "staleness_poll_history": poll_history,
        "stall_threshold_seconds": config.stall_threshold_seconds,
        "stall_consecutive_reads": config.stall_consecutive_reads,
        # Count of transcript-lookup-function exceptions across all polls. >0
        # signals a monitoring regression (not a model stall) worth investigating.
        "lookup_errors": lookup_errors_total,
        # Time-to-demonstrated-compliance for an early stop (None otherwise).
        "score_complete_seconds": score_complete_at,
    }
    return stdout or "", stderr or "", reason, diagnostics


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
            if result.actual_billing.access_type != "chatgpt_subscription":
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
        if result.actual_billing.access_type != "chatgpt_subscription":
            result.total_cost_usd = output.get("total_cost_usd", 0.0)
        result.total_turns = output.get("num_turns", 0)
        _extract_token_usage(output, result)


def _first_optional_int(data: dict, *keys: str):
    """Return the first recognized non-boolean integer, preserving missing as None."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _sum_optional(values: list) -> int | None:
    observed = [value for value in values if value is not None]
    return sum(observed) if observed else None


def _extract_token_usage(msg: dict, result: "RunResult") -> None:
    """Extract safely observable CLI usage without overstating its semantics.

    ``modelUsage`` aggregates the main session and subagents and is preferred to
    the main-session-only ``usage`` fallback. Model keys are CLI-observed
    identity evidence, not backend confirmation. Missing token categories stay
    null; they are never silently converted to zero.
    """
    model_usage = msg.get("modelUsage")
    if isinstance(model_usage, dict):
        recognized = {}
        input_values = []
        output_values = []
        cache_read_values = []
        cache_write_values = []
        reasoning_values = []

        for model_key, raw_usage in model_usage.items():
            if not isinstance(model_key, str) or not isinstance(raw_usage, dict):
                continue
            values = {
                "input_tokens": _first_optional_int(
                    raw_usage, "inputTokens", "input_tokens"
                ),
                "output_tokens": _first_optional_int(
                    raw_usage, "outputTokens", "output_tokens"
                ),
                "cache_read_tokens": _first_optional_int(
                    raw_usage, "cacheReadInputTokens", "cache_read_input_tokens",
                    "cachedInputTokens", "cached_input_tokens",
                ),
                "cache_write_tokens": _first_optional_int(
                    raw_usage, "cacheCreationInputTokens",
                    "cache_creation_input_tokens", "cacheWriteInputTokens",
                    "cache_write_tokens",
                ),
                "reasoning_tokens": _first_optional_int(
                    raw_usage, "reasoningTokens", "reasoning_tokens"
                ),
            }
            recognized[model_key] = values
            input_values.append(values["input_tokens"])
            output_values.append(values["output_tokens"])
            cache_read_values.append(values["cache_read_tokens"])
            cache_write_values.append(values["cache_write_tokens"])
            reasoning_values.append(values["reasoning_tokens"])

        result.model_identity.claude_cli_model_usage_ids = list(recognized)
        observed = result.usage_observed
        observed.cli_model_usage = recognized
        observed.input_tokens = _sum_optional(input_values)
        observed.output_tokens = _sum_optional(output_values)
        observed.reasoning_tokens = _sum_optional(reasoning_values)
        observed.source = "claude_cli.modelUsage"
        result.input_tokens = observed.input_tokens
        result.output_tokens = observed.output_tokens

        if result.actual_billing.access_type == "chatgpt_subscription":
            # The deployed shim currently forwards total input/output but does
            # not expose reliable cache or reasoning breakdowns. Preserve any
            # CLI fields above as observations while keeping accounting fields
            # unavailable instead of treating synthesized zeros as evidence.
            observed.input_semantics = "shim_reported_total_input_cache_breakdown_unavailable"
            observed.input_includes_cache_tokens = True
            observed.output_includes_reasoning = True
            observed.cache_read_tokens = None
            observed.cache_write_tokens = None
            observed.reasoning_tokens = None
            observed.completeness = (
                "partial"
                if observed.input_tokens is not None or observed.output_tokens is not None
                else "unavailable"
            )
            observed.incompleteness_reasons = [
                "cache_read_tokens_not_reliably_exposed_by_deployed_shim",
                "cache_write_tokens_not_reliably_exposed_by_deployed_shim",
                "reasoning_tokens_not_exposed_by_deployed_shim",
                "per_request_context_tier_not_exposed_by_claude_cli",
            ]
            result.cache_read_tokens = None
            result.cache_creation_tokens = None
        else:
            observed.input_semantics = "claude_cli_uncached_input_additive_cache_fields"
            observed.output_includes_reasoning = None
            observed.cache_read_tokens = _sum_optional(cache_read_values)
            observed.cache_write_tokens = _sum_optional(cache_write_values)
            required = (
                observed.input_tokens,
                observed.output_tokens,
                observed.cache_read_tokens,
                observed.cache_write_tokens,
            )
            observed.completeness = "complete" if all(v is not None for v in required) else "partial"
            observed.incompleteness_reasons = [
                name for name, value in {
                    "input_tokens": observed.input_tokens,
                    "output_tokens": observed.output_tokens,
                    "cache_read_tokens": observed.cache_read_tokens,
                    "cache_write_tokens": observed.cache_write_tokens,
                }.items() if value is None
            ]
            result.cache_read_tokens = observed.cache_read_tokens
            result.cache_creation_tokens = observed.cache_write_tokens
        return

    usage = msg.get("usage")
    if isinstance(usage, dict):
        observed = result.usage_observed
        observed.input_tokens = _first_optional_int(usage, "input_tokens", "inputTokens")
        observed.output_tokens = _first_optional_int(usage, "output_tokens", "outputTokens")
        observed.source = "claude_cli.usage"
        result.input_tokens = observed.input_tokens
        result.output_tokens = observed.output_tokens

        if result.actual_billing.access_type == "chatgpt_subscription":
            observed.input_semantics = "shim_reported_total_input_cache_breakdown_unavailable"
            observed.input_includes_cache_tokens = True
            observed.output_includes_reasoning = True
            observed.completeness = (
                "partial"
                if observed.input_tokens is not None or observed.output_tokens is not None
                else "unavailable"
            )
            observed.incompleteness_reasons = [
                "modelUsage_unavailable_main_session_only",
                "cache_read_tokens_not_reliably_exposed_by_deployed_shim",
                "cache_write_tokens_not_reliably_exposed_by_deployed_shim",
                "reasoning_tokens_not_exposed_by_deployed_shim",
                "per_request_context_tier_not_exposed_by_claude_cli",
            ]
        else:
            observed.input_semantics = "claude_cli_uncached_input_additive_cache_fields"
            observed.cache_read_tokens = _first_optional_int(
                usage, "cache_read_input_tokens", "cacheReadInputTokens"
            )
            observed.cache_write_tokens = _first_optional_int(
                usage, "cache_creation_input_tokens", "cacheCreationInputTokens"
            )
            result.cache_read_tokens = observed.cache_read_tokens
            result.cache_creation_tokens = observed.cache_write_tokens
            observed.completeness = "partial"
            observed.incompleteness_reasons = ["modelUsage_unavailable_main_session_only"]


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
            content = _extract_tool_content(block.get("content", ""))
            # C4 (additive): tag each failure with a finer operational cause.
            # The configured child model id is the run's routing selector, which
            # the lane-refusal branch compares against the rejected id named in
            # the error string. It is reachable here on the result identity, so
            # no invasive plumbing is needed.
            configured_child_model_id = getattr(
                result.model_identity, "requested_model_id", None
            )
            result.tool_failures.append({
                "tool_use_id": tool_use_id,
                "tool_name": tool_names.get(tool_use_id, "unknown"),
                "content": content,
                "tool_failure_class": classify_tool_failure_class(
                    content, configured_child_model_id
                ),
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
