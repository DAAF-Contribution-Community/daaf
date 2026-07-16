"""Smoke probe implementations for the DAAF deployment smoke-testing suite.

Holds the trimmed `claude -p` executor (a copy-and-cut of
benchmarks/harness/executor.py:execute_run that drops the golden-checkpoint
coupling) plus every tier's probe implementations:

  * Tier 0 (no-LLM system checks not already in route_detection): CLI liveness,
    hook registration across all .claude/hooks/*.sh, statusline rendering,
    shim /health, chatgpt auth.json, workspace invariants.
  * Tier 1: one live claude -p round-trip and the evidence checks around it.
  * Tier 2: the six-probe capability-structural battery (T2.1-T2.6).
  * Tier D: the deterministic battery (bats, Pester, lint, safety-hook tests,
    single-command tests, optional R/Python skill smoke).

Reuse boundary (per the Phase 1 harness-reusability findings): we IMPORT the
JSON-output parsers from benchmarks.harness.executor (zero benchmark coupling)
and the RunResult dataclass from benchmarks.harness.models, but COPY the
execution wrapper so we shed the checkpoint_manager dependency and the
checkpoint branch. The graceful-kill ladder is imported to keep a single source
of truth for the SIGTERM -> grace -> SIGKILL subprocess hygiene.

Framework tooling: normal engineering style with functions, matching
benchmarks/harness/ — NOT the sequential no-functions research-script style.
"""

import json
import os
import re
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from route_detection import (
    Verdict,
    ProbeResult,
    RouteInfo,
    ROUTE_CHATGPT,
    ROUTE_OPENAI_API,
    SHIM_ROUTES,
    scrub_secret_values,
)

# Imported from the benchmark harness — these have zero benchmark coupling and
# keep the smoke runner's output parsing byte-identical to the benchmark's.
from benchmarks.harness.models import RunResult
from benchmarks.harness.executor import (
    _parse_json_output,
    _extract_tool_failures,
    _graceful_kill,
    KILL_GRACE_SECONDS,
)


BASE_DIR = "/daaf"
SHIM_HEALTH_URL = "http://127.0.0.1:4141/health"
_GLM52_STATIC_ID = re.compile(r"z-ai/glm-5\.2(?:-[0-9]{8})?")


def _is_wide_context_model(model_id: str) -> bool:
    """Classify models whose headless context cache may represent a wide window.

    Keep GLM matching narrower than the existing GPT and ``[1m]`` checks: only
    the exact canonical id and a terminal eight-digit snapshot qualify. Air and
    arbitrary future suffixes deliberately fall through.
    """
    model_id = model_id or ""
    return (
        "[1m]" in model_id
        or "gpt-5" in model_id.lower()
        or _GLM52_STATIC_ID.fullmatch(model_id) is not None
    )


# The deliberate DAAF_BENCHMARK_RUN=1 overload: its SOLE behavioral consumer is
# benchmarks/harness/hooks/block-git-writes.sh:33, which gives every probe
# subprocess (and its subagents) git-write blocking — desirable for a suite that
# dispatches coding agents into a live repo. No DAAF hook/statusline/settings
# reads this flag. Renaming to a shared DAAF_SMOKETEST_RUN gate is future cleanup
# tracked in the design notes; the overload is safe today.
PROBE_GATE_ENV = {"DAAF_BENCHMARK_RUN": "1"}


# --- Trimmed executor -----------------------------------------------------

def execute_smoke_run(
    prompt: str,
    max_turns: int,
    timeout: int,
    working_dir: str = BASE_DIR,
    model_id: str = "",
    extra_env: dict = None,
    session_id: str = "",
):
    """Run a single cold-start `claude -p` round-trip and return (RunResult, meta).

    A trimmed copy of benchmarks/harness/executor.py:execute_run:
      * NO golden-checkpoint / --resume branch (every smoke probe is a cold start).
      * Pre-assigns a --session-id UUID so the transcript is locatable even after
        a timeout (the load-bearing cold-start pattern).
      * Builds env = os.environ + extra_env (profile overlay) + PROBE_GATE_ENV,
        with the gate applied LAST so a profile overlay cannot override it.
      * SIGTERM -> grace -> SIGKILL kill ladder via the imported _graceful_kill.
      * Parses output via the imported _parse_json_output / _extract_tool_failures.

    model_id: when empty (the in-situ default), --model is omitted so Claude Code
    resolves the model exactly as a normal session would (from settings.json /
    ANTHROPIC_MODEL / the profile overlay) — this tests the AS-CONFIGURED model.

    Returns (RunResult, meta) where meta carries {session_id, timed_out, cmd}.
    """
    sid = session_id or str(uuid.uuid4())

    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--permission-mode", "bypassPermissions",
        "--session-id", sid,
    ]
    if model_id:
        cmd.extend(["--model", model_id])

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    # Apply the probe gate LAST so a profile overlay cannot override
    # DAAF_BENCHMARK_RUN — the git-write block must hold for every probe
    # subprocess and its subagents regardless of the overlay's contents.
    env.update(PROBE_GATE_ENV)

    result = RunResult(
        test_case_id="smoke",
        model_id=model_id or env.get("ANTHROPIC_MODEL", "as-configured"),
        model_name="smoke",
        run_index=0,
    )
    meta = {"session_id": sid, "timed_out": False, "cmd": " ".join(cmd[:6]) + " ..."}

    start = time.time()
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir,
            env=env,
        )
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            stdout, stderr = _graceful_kill(proc)
            timed_out = True

        result.duration_seconds = time.time() - start

        if timed_out:
            if stdout:
                _parse_json_output(stdout, result)
            result.error = f"Timed out after {timeout}s"
            if not result.session_id:
                result.session_id = sid
            meta["timed_out"] = True
            return result, meta

        result.exit_code = proc.returncode
        if proc.returncode != 0 and not stdout.strip():
            result.error = f"CLI exited with code {proc.returncode}: {stderr[:500]}"
            if not result.session_id:
                result.session_id = sid
            return result, meta

        _parse_json_output(stdout, result)
        _extract_tool_failures(result)
        if not result.session_id:
            result.session_id = sid
        if stderr.strip():
            # Scrub secret env values from raw stderr before it can reach evidence.
            meta["stderr"] = scrub_secret_values(stderr.strip()[:500])

    except Exception as e:  # defensive: never leak a live CLI process
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.communicate()
        result.duration_seconds = time.time() - start
        result.error = f"Execution error: {type(e).__name__}: {e}"
        if not result.session_id:
            result.session_id = sid

    return result, meta


# --- Transcript / cache lookup helpers ------------------------------------

def find_transcript(session_id: str):
    """Locate a session transcript, archived-or-live, mirroring
    benchmarks/scorers/deterministic/checkpoint_adherence.py:find_benchmark_transcript.
    Archived (clean exit) is checked first, then the live projects file (survives
    timeouts / no archive-hook fire)."""
    sessions_dir = Path(BASE_DIR) / ".claude" / "logs" / "sessions"
    projects_dir = Path.home() / ".claude" / "projects" / "-daaf"
    if sessions_dir.exists():
        short = session_id[:8]
        for p in sessions_dir.glob(f"*_{short}_orchestrator.jsonl"):
            return p
    live = projects_dir / f"{session_id}.jsonl"
    if live.exists():
        return live
    return None


def find_subagent_transcripts(session_id: str):
    """Return subagent transcript paths for a session, if any.

    Subagent transcripts live beside the main transcript under
    <projects>/-daaf/<session_id>/subagents/agent-<id>.jsonl (per subagent-bar.sh's
    sidecar contract) — best-effort, fail-open to an empty list."""
    projects_dir = Path.home() / ".claude" / "projects" / "-daaf"
    sub_dir = projects_dir / session_id / "subagents"
    if sub_dir.exists():
        return sorted(sub_dir.glob("agent-*.jsonl"))
    return []


def read_transcript_lines(path: Path):
    """Yield parsed JSONL records from a transcript, skipping unparseable lines."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def snapshot_tmp_caches(session_id: str) -> dict:
    """Read the /tmp coordination caches for a session (READ ONLY — /tmp writes
    are blocked; reads of DAAF caches are the sanctioned pattern)."""
    snap = {}
    for name, path in {
        "model": f"/tmp/claude-model-{session_id}",
        "ctx_window": f"/tmp/claude-ctx-window-{session_id}",
        "or_models": f"/tmp/claude-or-models-{session_id}",
    }.items():
        p = Path(path)
        if p.exists():
            try:
                snap[name] = {"path": path, "value": p.read_text().strip()[:200]}
            except OSError:
                snap[name] = {"path": path, "value": "<unreadable>"}
        else:
            snap[name] = {"path": path, "value": None}
    return snap


# --- Tier 0 system probes (no LLM) ----------------------------------------

def probe_cli_available() -> ProbeResult:
    r = ProbeResult(probe_id="T0.5", name="claude CLI available", tier="0")
    try:
        proc = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=15)
        out = (proc.stdout or proc.stderr).strip()
        r.add_evidence("claude --version", output=out)
        if proc.returncode == 0:
            r.verdict = Verdict.PASS
            r.detail = f"claude CLI responsive: {out}"
        else:
            r.verdict = Verdict.FAIL
            r.detail = f"claude --version exited {proc.returncode}."
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        r.verdict = Verdict.FAIL
        r.detail = f"claude CLI unavailable: {type(e).__name__}"
        r.add_evidence("claude --version", note=str(e))
    return r


def probe_hook_registration(base_dir: str = BASE_DIR) -> ProbeResult:
    """Verify every hook script in .claude/hooks/ is registered in settings.json.

    Extends benchmarks/harness/executor.py:check_hooks_active (which checked only
    6 named hooks by substring) to ALL .sh files in .claude/hooks/, cross-checking
    each against the registered command strings in settings.json."""
    r = ProbeResult(probe_id="T0.6", name="Hook registration (all hooks)", tier="0")
    hooks_dir = Path(base_dir) / ".claude" / "hooks"
    settings_path = Path(base_dir) / ".claude" / "settings.json"

    hook_scripts = sorted(p.name for p in hooks_dir.glob("*.sh")) if hooks_dir.exists() else []
    r.add_evidence(f"ls {hooks_dir}/*.sh", output=f"{len(hook_scripts)} hook scripts: " + ", ".join(hook_scripts))

    if not settings_path.exists():
        r.verdict = Verdict.FAIL
        r.detail = f"{settings_path} not found."
        return r

    try:
        settings_text = settings_path.read_text()
        settings = json.loads(settings_text)
    except (OSError, json.JSONDecodeError) as e:
        r.verdict = Verdict.FAIL
        r.detail = f"settings.json unreadable/invalid: {e}"
        return r

    # Collect every registered command string across all event chains.
    registered_cmds = []
    for event_matchers in settings.get("hooks", {}).values():
        if not isinstance(event_matchers, list):
            continue
        for group in event_matchers:
            for hd in group.get("hooks", []) if isinstance(group, dict) else []:
                if isinstance(hd, dict):
                    registered_cmds.append(hd.get("command", ""))
    blob = " ".join(registered_cmds)

    # A hook counts as registered if its filename appears in some command string.
    # Note: some hooks legitimately live outside settings.json (per-agent
    # frontmatter, e.g. enforce-file-first.sh) — those are reported as INFO, not FAIL.
    per_agent_only = {"enforce-file-first.sh"}
    missing = [h for h in hook_scripts if h not in blob and h not in per_agent_only]
    per_agent = [h for h in hook_scripts if h in per_agent_only and h not in blob]

    r.add_evidence(
        "parse .claude/settings.json hook chains",
        output=f"{len(registered_cmds)} command entries; project-registered hooks matched",
    )
    if per_agent:
        r.add_evidence("", note=f"per-agent-frontmatter hooks (not in settings.json, expected): {', '.join(per_agent)}")

    if missing:
        r.verdict = Verdict.FAIL
        r.detail = f"Hook scripts present but NOT registered in settings.json: {', '.join(missing)}"
    else:
        r.verdict = Verdict.PASS
        r.detail = f"All {len(hook_scripts)} hook scripts accounted for (project-registered or per-agent)."
    return r


def _synthetic_context_bar_payload() -> str:
    """A minimal but schema-valid statusLine payload (see context-bar.sh IFS/jq block)."""
    return json.dumps({
        "model": {"display_name": "Smoke Model", "id": "claude-smoke-1"},
        "cwd": BASE_DIR,
        "transcript_path": "",
        "context_window": {"context_window_size": 200000},
        "session_id": "smoke-synthetic",
        "effort": {"level": "high"},
        "rate_limits": {},
    })


def _synthetic_subagent_bar_payload() -> str:
    """A minimal but schema-valid subagentStatusLine payload (see subagent-bar.sh
    INPUT CONTRACT)."""
    return json.dumps({
        "session_id": "smoke-synthetic",
        "transcript_path": "/nonexistent/transcript.jsonl",
        "cwd": BASE_DIR,
        "columns": 120,
        "tasks": [{
            "id": "smoke-task-1",
            "type": "local_agent",
            "status": "running",
            "description": "smoke synthetic task",
            "label": "smoke",
            "startTime": int(time.time() * 1000),
            "tokenCount": 1234,
            "tokenSamples": [1234],
            "cwd": BASE_DIR,
        }],
    })


def probe_statuslines(base_dir: str = BASE_DIR) -> ProbeResult:
    """Verify both statusline scripts execute cleanly against a synthetic payload
    (exit 0, non-empty output). These are fail-open scripts, so a crash still
    exits 0 — we additionally require non-empty rendered output as the real signal."""
    r = ProbeResult(probe_id="T0.7", name="Statusline rendering (synthetic)", tier="0")
    scripts = {
        "context-bar.sh": (Path(base_dir) / ".claude" / "scripts" / "context-bar.sh", _synthetic_context_bar_payload()),
        "subagent-bar.sh": (Path(base_dir) / ".claude" / "scripts" / "subagent-bar.sh", _synthetic_subagent_bar_payload()),
    }
    failures = []
    for name, (path, payload) in scripts.items():
        if not path.exists():
            failures.append(f"{name} missing")
            r.add_evidence(f"test -f {path}", output="missing")
            continue
        try:
            proc = subprocess.run(["bash", str(path)], input=payload, capture_output=True, text=True, timeout=20)
            out = (proc.stdout or "").strip()
            r.add_evidence(f"echo <synthetic> | bash {name}", output=(out[:300] or "<empty>"))
            if proc.returncode != 0:
                failures.append(f"{name} exited {proc.returncode}")
            elif not out:
                failures.append(f"{name} produced no output")
        except subprocess.TimeoutExpired:
            failures.append(f"{name} timed out")
            r.add_evidence(f"bash {name}", note="timed out")

    if failures:
        r.verdict = Verdict.FAIL
        r.detail = "; ".join(failures)
    else:
        r.verdict = Verdict.PASS
        r.detail = "Both statusline scripts render non-empty output against a synthetic payload."
    return r


def probe_shim_health(route_info: RouteInfo) -> ProbeResult:
    """GET the shim /health endpoint (shim routes only) and verify backend_mode
    matches the detected route; report sanitize_tools, codex_home_present, version."""
    r = ProbeResult(probe_id="T0.8", name="Provider shim /health", tier="0")
    if route_info.detected_route not in SHIM_ROUTES:
        r.verdict = Verdict.SKIP
        r.detail = f"Not a shim route ({route_info.detected_route}); shim /health N/A."
        r.add_evidence("", note="shim /health only applies to openai-api / chatgpt-subscription routes")
        return r

    try:
        with urlopen(SHIM_HEALTH_URL, timeout=10) as resp:
            body = resp.read().decode("utf-8", "replace")
        health = json.loads(body)
        # Scrub any secret env value that the /health JSON might echo verbatim
        # before it enters evidence (defense-in-depth; the placeholder keeps the
        # blob parseable for the evidence/ snapshot).
        r.add_evidence(f"GET {SHIM_HEALTH_URL}",
                       output=scrub_secret_values(json.dumps(health, indent=2)[:1500]))
    except (URLError, socket.timeout, json.JSONDecodeError, OSError) as e:
        r.verdict = Verdict.FAIL
        r.detail = f"shim /health unreachable/invalid: {type(e).__name__}: {e}"
        r.add_evidence(f"GET {SHIM_HEALTH_URL}", note=str(e))
        return r

    expected_mode = "chatgpt" if route_info.detected_route == ROUTE_CHATGPT else "openai"
    actual_mode = health.get("backend_mode")
    problems = []
    if actual_mode != expected_mode:
        problems.append(f"backend_mode='{actual_mode}' but route expects '{expected_mode}'")
    if route_info.detected_route == ROUTE_CHATGPT and not health.get("codex_home_present"):
        problems.append("codex_home_present=false (auth.json missing/unreadable) for chatgpt route")

    r.add_evidence("", note=(
        f"backend_mode={actual_mode} sanitize_tools={health.get('sanitize_tools')} "
        f"codex_home_present={health.get('codex_home_present')} version={health.get('version')}"
    ))
    if problems:
        r.verdict = Verdict.FAIL
        r.detail = "; ".join(problems)
    else:
        r.verdict = Verdict.PASS
        r.detail = f"shim healthy: backend_mode={actual_mode}, version={health.get('version')}."
    return r


def probe_auth_json(route_info: RouteInfo, env) -> ProbeResult:
    """chatgpt route only: confirm $CODEX_HOME/auth.json exists and is readable
    (presence/readability only — never read or emit its contents)."""
    r = ProbeResult(probe_id="T0.9", name="ChatGPT auth.json readable", tier="0")
    if route_info.detected_route != ROUTE_CHATGPT:
        r.verdict = Verdict.SKIP
        r.detail = f"Not the chatgpt-subscription route ({route_info.detected_route}); auth.json N/A."
        return r
    codex_home = env.get("CODEX_HOME")
    if not codex_home:
        r.verdict = Verdict.FAIL
        r.detail = "CODEX_HOME unset — cannot locate auth.json for the chatgpt route."
        r.add_evidence("env: CODEX_HOME", output="<unset>")
        return r
    auth_path = Path(codex_home) / "auth.json"
    readable = auth_path.exists() and os.access(auth_path, os.R_OK)
    r.add_evidence(f"os.access({auth_path}, R_OK)", output=str(readable), note="presence/readability only; contents never read")
    if readable:
        r.verdict = Verdict.PASS
        r.detail = "auth.json present and readable (contents not inspected)."
    else:
        r.verdict = Verdict.FAIL
        r.detail = f"auth.json missing or unreadable at {auth_path} — run 'codex login --device-auth'."
    return r


def probe_workspace_invariants(base_dir: str = BASE_DIR) -> ProbeResult:
    """Run check_workspace_invariants.sh -q (no unauthorized symlinks / repo-root
    leak artifacts on the live filesystem)."""
    r = ProbeResult(probe_id="T0.10", name="Workspace invariants", tier="0")
    script = Path(base_dir) / "scripts" / "check_workspace_invariants.sh"
    try:
        proc = subprocess.run(["bash", str(script), "-q"], capture_output=True, text=True, timeout=60)
        out = (proc.stdout + proc.stderr).strip()
        r.add_evidence(f"bash {script} -q", output=out or "<no output = clean>")
        if proc.returncode == 0:
            r.verdict = Verdict.PASS
            r.detail = "Workspace invariants satisfied."
        else:
            r.verdict = Verdict.FAIL
            r.detail = f"Workspace invariant violation (exit {proc.returncode})."
    except subprocess.TimeoutExpired:
        r.verdict = Verdict.FAIL
        r.detail = "check_workspace_invariants.sh timed out."
    return r


def run_tier0(route_info: RouteInfo, env, base_dir: str = BASE_DIR):
    """Assemble the full Tier 0 preflight (route_detection probes + system probes).
    route_detection contributes T0.0-T0.4; this adds T0.5-T0.10."""
    from route_detection import (
        probe_daaf_dev,
        probe_route_detection,
        probe_model_family,
        probe_env_coherence,
        probe_context_window_coherence,
    )
    results = [
        probe_daaf_dev(env),
        probe_route_detection(route_info),
        probe_model_family(route_info, env),
        probe_env_coherence(route_info, env),
        probe_context_window_coherence(route_info, env),
        probe_cli_available(),
        probe_hook_registration(base_dir),
        probe_statuslines(base_dir),
        probe_shim_health(route_info),
        probe_auth_json(route_info, env),
        probe_workspace_invariants(base_dir),
    ]
    return results


# --- Tier 1: one live round-trip ------------------------------------------

TIER1_PROMPT = (
    "You are a deployment smoke test. Do exactly two things in order:\n"
    "1. Make exactly ONE Bash tool call that runs: echo daaf-smoke-ok\n"
    "2. Then reply with exactly this text and nothing else: SMOKE_TIER1_COMPLETE\n"
    "Do not use any other tools. Do not dispatch subagents."
)


def run_tier1(profile_name: str, extra_env: dict, timeout: int) -> list:
    """One live claude -p round-trip plus the evidence checks around it.

    Checks (each a capability-structural ProbeResult): response returned;
    transcript located (archived-or-live); audit.jsonl entries exist for the
    session; context-reporter injection visible; /tmp caches populated (with
    headless 200k results interpreted against the narrow static model map);
    statuslines render against the REAL session; token/cost fields parse from the
    JSON result.
    """
    results = []
    result, meta = execute_smoke_run(
        prompt=TIER1_PROMPT, max_turns=6, timeout=timeout, extra_env=extra_env,
    )
    sid = meta["session_id"]

    # T1.1 — response returned
    r1 = ProbeResult(probe_id="T1.1", name="Live round-trip response", tier="1", profile=profile_name)
    # result.error can carry up to 500 chars of raw CLI stderr — scrub any secret
    # env value out of it before it enters evidence.
    r1.add_evidence(f"claude -p (session {sid[:8]})", output=(result.response_text or "")[:300],
                    note=f"error={scrub_secret_values(result.error or '')}")
    if result.error and "Timed out" in (result.error or ""):
        r1.verdict = Verdict.FAIL
        r1.detail = f"Round-trip timed out after {timeout}s."
    elif result.response_text:
        r1.verdict = Verdict.PASS
        r1.detail = "Live round-trip returned a response."
    else:
        r1.verdict = Verdict.FAIL
        r1.detail = f"No response text; error={result.error}"
    results.append(r1)

    # T1.2 — transcript located
    r2 = ProbeResult(probe_id="T1.2", name="Transcript located", tier="1", profile=profile_name)
    transcript = find_transcript(sid)
    r2.add_evidence(f"find_transcript({sid[:8]}...)", output=str(transcript) if transcript else "<not found>")
    if transcript:
        r2.verdict = Verdict.PASS
        r2.detail = f"Transcript found: {transcript}"
    else:
        r2.verdict = Verdict.FAIL
        r2.detail = "Session transcript not found in archived or live locations."
    results.append(r2)

    # T1.3 — audit.jsonl entries exist for the session
    r3 = ProbeResult(probe_id="T1.3", name="Audit-log hook fired", tier="1", profile=profile_name)
    audit_path = Path(BASE_DIR) / ".claude" / "logs" / "audit.jsonl"
    audit_count = 0
    if audit_path.exists():
        for entry in read_transcript_lines(audit_path):
            if entry.get("session_id") == sid:
                audit_count += 1
    r3.add_evidence(f"grep session_id={sid[:8]} audit.jsonl", output=f"{audit_count} entries")
    if audit_count > 0:
        r3.verdict = Verdict.PASS
        r3.detail = f"audit-log hook wrote {audit_count} entries for the session."
    else:
        r3.verdict = Verdict.FAIL
        r3.detail = "No audit.jsonl entries for the session (audit-log hook may not have fired)."
    results.append(r3)

    # T1.4 — context-reporter injection visible in transcript.
    # context-reporter.sh injects at most once per INJECT_INTERVAL=60s. A
    # cold-start headless probe completes in seconds — well under that cadence —
    # so an absent injection is EXPECTED, not an install defect. The hook still
    # fires and falls back to a 200k window when the ctx-window cache is
    # unresolved, so silence here is cadence-driven, never a window-resolution
    # failure. Verdict is INFO (not WARN) when absent so it does not read as a
    # possible defect.
    r4 = ProbeResult(probe_id="T1.4", name="Context-reporter injection", tier="1", profile=profile_name)
    injection_seen = False
    if transcript:
        for rec in read_transcript_lines(transcript):
            blob = json.dumps(rec)
            if "Context utilization" in blob or "context-reporter" in blob:
                injection_seen = True
                break
    r4.add_evidence(
        "scan transcript for 'Context utilization'", output=str(injection_seen),
        note="context-reporter injects at most once per 60s (INJECT_INTERVAL)",
    )
    if injection_seen:
        r4.verdict = Verdict.PASS
        r4.detail = "context-reporter injection visible in transcript (hook fired within the run)."
    else:
        r4.verdict = Verdict.INFO
        r4.detail = (
            "No context-reporter injection this run — EXPECTED for a short headless probe. "
            "context-reporter injects at most once per 60s (INJECT_INTERVAL), and a cold-start probe "
            "finishes in seconds. The hook still fires and falls back to a 200k window when the cache is "
            "unresolved, so absence is cadence-driven, not a defect."
        )
    results.append(r4)

    # T1.5 — /tmp coordination caches (bounded-retry read; headless-mode-aware).
    #
    # Writers (verified): context-bar.sh is the sole writer of the per-session
    # ctx-window cache; context-reporter.sh cache_model() writes the model cache.
    # Both fire during a headless run but ASYNC relative to CLI exit, so an earlier
    # single-shot read raced the writes. Poll with a bounded ~5s backoff and quote
    # BOTH the first and final read.
    #
    # A headless statusline payload may omit its real context-window size, so
    # context-bar.sh begins from 200000. Its static map corrects supported GPT ids
    # and exact z-ai/glm-5.2 or terminal -YYYYMMDD snapshots; Air and arbitrary
    # future GLM suffixes do not inherit that constant. Dynamic OpenRouter metadata
    # remains authoritative, including a resolved value of exactly 200000. Native
    # Claude [1m] ids still depend on the supplied statusline window. Therefore the
    # primary signal is whether both caches are POPULATED AT ALL; a populated cache
    # is PASS, while a genuinely absent cache after retries is WARN. Physical GLM
    # capacity does not alter its conservative context-quality threshold family.
    r5 = ProbeResult(probe_id="T1.5", name="/tmp coordination caches", tier="1", profile=profile_name)
    first_snap = snapshot_tmp_caches(sid)
    final_snap = first_snap
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if (final_snap.get("ctx_window") or {}).get("value") and (final_snap.get("model") or {}).get("value"):
            break
        time.sleep(0.5)
        final_snap = snapshot_tmp_caches(sid)
    r5.add_evidence(f"read /tmp/claude-{{model,ctx-window}}-{sid[:8]} (t=0, pre-backoff)", output=json.dumps(first_snap))
    r5.add_evidence(f"read /tmp/claude-{{model,ctx-window}}-{sid[:8]} (after <=5s backoff)", output=json.dumps(final_snap))
    window_val = (final_snap.get("ctx_window") or {}).get("value")
    model_val = (final_snap.get("model") or {}).get("value")
    missing = []
    if not model_val:
        missing.append("model cache absent after retries (writer: context-reporter.sh cache_model)")
    if not window_val:
        missing.append("ctx-window cache absent after retries (writer: statusline context-bar.sh)")
    if missing:
        r5.verdict = Verdict.WARN
        r5.detail = (
            "; ".join(missing)
            + " — an absent cache after the bounded retry can indicate the writer did not run for this "
            "headless session."
        )
    else:
        r5.verdict = Verdict.PASS
        is_wide = _is_wide_context_model(result.model_id)
        note = ""
        if is_wide and str(window_val).strip() == "200000":
            note = (
                " Window value 200000 can be valid headless statusline behavior for a wide-window model: "
                "context-bar.sh statically maps supported GPT ids plus exact/date-snapshot GLM-5.2, while "
                "native Claude [1m] ids depend on the payload and authoritative dynamic OpenRouter metadata "
                "may itself resolve to exactly 200000. Air and arbitrary GLM suffixes are intentionally not "
                "classified as the exact GLM model. Cache population, not this one numeric value, is the probe."
            )
        r5.detail = f"/tmp caches populated (model={model_val}, window={window_val})." + note
    results.append(r5)

    # T1.6 — statuslines render against the REAL session
    r6 = ProbeResult(probe_id="T1.6", name="Statusline against real session", tier="1", profile=profile_name)
    if transcript:
        payload = json.dumps({
            "model": {"display_name": result.model_id, "id": result.model_id},
            "cwd": BASE_DIR,
            "transcript_path": str(transcript),
            "context_window": {"context_window_size": 200000},
            "session_id": sid,
            "effort": {"level": "high"},
            "rate_limits": {},
        })
        try:
            proc = subprocess.run(
                ["bash", str(Path(BASE_DIR) / ".claude" / "scripts" / "context-bar.sh")],
                input=payload, capture_output=True, text=True, timeout=20,
            )
            out = (proc.stdout or "").strip()
            r6.add_evidence("context-bar.sh <real-session payload>", output=out[:300] or "<empty>")
            r6.verdict = Verdict.PASS if (proc.returncode == 0 and out) else Verdict.WARN
            r6.detail = "context-bar renders against the real session." if r6.verdict == Verdict.PASS else "context-bar produced no output for the real session."
        except subprocess.TimeoutExpired:
            r6.verdict = Verdict.WARN
            r6.detail = "context-bar timed out on the real session."
    else:
        r6.verdict = Verdict.SKIP
        r6.detail = "No transcript to render against."
    results.append(r6)

    # T1.7 — token / cost fields parse from the JSON result
    r7 = ProbeResult(probe_id="T1.7", name="Token/cost parsing", tier="1", profile=profile_name)
    r7.add_evidence(
        "parse claude -p JSON result",
        output=(f"input_tokens={result.input_tokens} output_tokens={result.output_tokens} "
                f"total_cost_usd={result.total_cost_usd} turns={result.total_turns}"),
    )
    if result.total_turns > 0 or result.input_tokens > 0:
        r7.verdict = Verdict.PASS
        r7.detail = "Token/turn/cost fields parsed from the JSON result."
    else:
        r7.verdict = Verdict.WARN
        r7.detail = "Token/cost fields are zero (parse may have missed the result message)."
    results.append(r7)

    return results


# --- Tier 2: six-probe capability-structural battery -----------------------

def _sandbox_dir() -> Path:
    return Path(BASE_DIR) / "scripts" / "deploy_smoke" / "_sandbox"


def _tool_uses_in_transcript(transcript: Path):
    """Yield (tool_name, block) for every tool_use across a transcript (main +
    any subagent transcripts are handled by the caller)."""
    for rec in read_transcript_lines(transcript):
        if rec.get("type") != "assistant":
            continue
        for block in rec.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield block.get("name", ""), block


def run_tier2(profile_name: str, extra_env: dict, timeout: int) -> list:
    """The six-probe functional battery. Each probe is a SEPARATE cold-start
    claude -p run. All checks are capability-structural (did the machinery work),
    deliberately tolerant of stylistic/protocol variation — adherence quality is
    DAAFBench's job, not this suite's."""
    results = []
    sandbox = _sandbox_dir()
    sandbox.mkdir(parents=True, exist_ok=True)

    # T2.1 — dispatch/search: dispatch search-agent to read a marker fixture and echo its token.
    marker_token = f"SMOKE-MARKER-{uuid.uuid4().hex[:8]}"
    fixture = sandbox / "t21_marker.txt"
    fixture.write_text(f"The smoke marker token is: {marker_token}\n")
    p21 = (
        f"You are a deployment smoke test. Dispatch a 'search-agent' subagent via the "
        f"Agent tool and instruct it to read the file {fixture} and report the marker "
        f"token it contains. Then reply with the token you received."
    )
    res21, meta21 = execute_smoke_run(prompt=p21, max_turns=12, timeout=timeout, extra_env=extra_env)
    r21 = ProbeResult(probe_id="T2.1", name="Subagent dispatch + search", tier="2", profile=profile_name)
    tr21 = find_transcript(meta21["session_id"])
    subs21 = find_subagent_transcripts(meta21["session_id"])
    dispatched = False
    if tr21:
        for name, _ in _tool_uses_in_transcript(tr21):
            if name in ("Agent", "Task"):
                dispatched = True
                break
    marker_returned = marker_token in (res21.response_text or "")
    r21.add_evidence(f"claude -p (session {meta21['session_id'][:8]})", output=(res21.response_text or "")[:200])
    r21.add_evidence("scan transcript for Agent/Task tool_use", output=f"dispatched={dispatched}")
    r21.add_evidence("check marker round-trip in response", output=f"marker_returned={marker_returned}")
    r21.add_evidence("find subagent transcripts (supporting evidence)", output=f"{len(subs21)} found")
    r21.add_evidence("", note=(
        f"model purity: cache /tmp/claude-subagent-model-{meta21['session_id'][:8]}-* vs remap intent; "
        f"ceiling-hook posture route-correct for family expectation"), is_inference=True)
    # PASS requires the marker to round-trip: dispatch alone (a subagent transcript
    # existing) proves the Agent tool fired but NOT that the search result flowed
    # back through the orchestrator. A dispatch with no round-trip is a distinct
    # WARN (dispatch machinery works, result relay did not), not a silent PASS.
    if dispatched and marker_returned:
        r21.verdict = Verdict.PASS
        r21.detail = "search-agent dispatched and the marker token round-tripped back to the orchestrator."
    elif dispatched and subs21:
        r21.verdict = Verdict.WARN
        r21.detail = ("search-agent dispatched (subagent transcript present) but the marker token did "
                      "not round-trip to the orchestrator response — dispatch worked, result relay did not.")
    else:
        r21.verdict = Verdict.FAIL
        r21.detail = "No subagent dispatch and/or marker token not returned."
    results.append(r21)

    # T2.2 — coding agent: research-executor writes + runs a tiny script via run_with_capture.
    p22 = (
        "You are a deployment smoke test. Dispatch a 'research-executor' subagent via the "
        f"Agent tool. Instruct it to write a tiny Python script to "
        f"{sandbox}/t22_probe.py that prints 'daaf-exec-ok', then execute it with "
        f"bash {BASE_DIR}/scripts/run_with_capture.sh {sandbox}/t22_probe.py. "
        "Report whether the run succeeded."
    )
    res22, meta22 = execute_smoke_run(prompt=p22, max_turns=12, timeout=timeout, extra_env=extra_env)
    r22 = ProbeResult(probe_id="T2.2", name="Coding agent write + execute", tier="2", profile=profile_name)
    probe_script = sandbox / "t22_probe.py"
    script_created = probe_script.exists()
    log_appended = False
    exec_output_seen = False
    if script_created:
        try:
            body = probe_script.read_text()
            # The appended "# EXECUTION LOG" banner (written by run_with_capture.sh)
            # is the proof the script actually RAN. A bare "daaf-exec-ok" match is
            # NOT proof: the agent writes print('daaf-exec-ok') per the prompt, so
            # the token is present in the script SOURCE even if it was never
            # executed. Require the banner; then, to prove the token came from
            # CAPTURED OUTPUT and not the source line, require it to appear AFTER
            # the banner.
            banner_idx = body.find("# EXECUTION LOG")
            log_appended = banner_idx != -1
            exec_output_seen = log_appended and ("daaf-exec-ok" in body[banner_idx:])
        except OSError:
            pass
    r22.add_evidence(f"claude -p (session {meta22['session_id'][:8]})", output=(res22.response_text or "")[:200])
    r22.add_evidence(f"test -f {probe_script}", output=str(script_created))
    r22.add_evidence("check for '# EXECUTION LOG' banner + token after banner",
                     output=f"banner_appended={log_appended} token_in_captured_output={exec_output_seen}")
    if script_created and log_appended:
        r22.verdict = Verdict.PASS
        r22.detail = (
            "research-executor wrote a script and executed it via run_with_capture "
            "(# EXECUTION LOG banner appended"
            + ("; 'daaf-exec-ok' present in captured output)." if exec_output_seen
               else ", though the token was not found in captured output).")
        )
    else:
        r22.verdict = Verdict.FAIL
        r22.detail = "Script not created or no '# EXECUTION LOG' banner appended (not executed via run_with_capture)."
    results.append(r22)

    # T2.3 — web access: search-agent performs one minimal WebSearch.
    p23 = (
        "You are a deployment smoke test. Dispatch a 'search-agent' subagent via the "
        "Agent tool and instruct it to perform exactly one WebSearch for a simple fact "
        "(e.g. the capital of France) and report the fact. Then relay the fact."
    )
    res23, meta23 = execute_smoke_run(prompt=p23, max_turns=12, timeout=timeout, extra_env=extra_env)
    r23 = ProbeResult(probe_id="T2.3", name="Web access (WebSearch)", tier="2", profile=profile_name)
    web_ok = False
    scanned = [find_transcript(meta23["session_id"])] + find_subagent_transcripts(meta23["session_id"])
    for tr in scanned:
        if not tr:
            continue
        for name, _ in _tool_uses_in_transcript(tr):
            if name in ("WebSearch", "WebFetch"):
                web_ok = True
                break
        if web_ok:
            break
    r23.add_evidence(f"claude -p (session {meta23['session_id'][:8]})", output=(res23.response_text or "")[:200])
    r23.add_evidence("scan transcripts for WebSearch/WebFetch tool_use", output=f"web_tool_used={web_ok}")
    if web_ok:
        r23.verdict = Verdict.PASS
        r23.detail = "A WebSearch/WebFetch tool_use occurred in the subagent transcript."
    else:
        r23.verdict = Verdict.FAIL
        r23.detail = "No successful WebSearch/WebFetch tool_use observed."
    results.append(r23)

    # T2.4 — skill loading: load the polars skill and confirm one fact.
    p24 = (
        "You are a deployment smoke test. Load the 'polars' skill via the Skill tool, "
        "then confirm one fact from it (e.g. that polars is DAAF's default DataFrame "
        "library). Reply with the fact."
    )
    res24, meta24 = execute_smoke_run(prompt=p24, max_turns=8, timeout=timeout, extra_env=extra_env)
    r24 = ProbeResult(probe_id="T2.4", name="Skill loading", tier="2", profile=profile_name)
    skill_used = False
    tr24 = find_transcript(meta24["session_id"])
    if tr24:
        for name, block in _tool_uses_in_transcript(tr24):
            if name == "Skill":
                skill_used = True
                break
    r24.add_evidence(f"claude -p (session {meta24['session_id'][:8]})", output=(res24.response_text or "")[:200])
    r24.add_evidence("scan transcript for Skill tool_use", output=f"skill_loaded={skill_used}")
    if skill_used:
        r24.verdict = Verdict.PASS
        r24.detail = "Skill tool_use present (a Skill call fired; progressive disclosure engaged)."
    else:
        r24.verdict = Verdict.FAIL
        r24.detail = "No Skill tool_use observed."
    results.append(r24)

    # T2.5 — isolation-strip (SKIP-tolerant): a dispatch that includes isolation:"worktree".
    p25 = (
        "You are a deployment smoke test verifying a safety hook. Dispatch a 'search-agent' "
        "subagent via the Agent tool with the parameter isolation set to \"worktree\", "
        "instructing it to simply reply 'isolation-probe-ok'. It is expected that the "
        "isolation parameter is stripped by a hook before the dispatch runs."
    )
    res25, meta25 = execute_smoke_run(prompt=p25, max_turns=10, timeout=timeout, extra_env=extra_env)
    r25 = ProbeResult(probe_id="T2.5", name="Isolation-strip hook", tier="2", profile=profile_name)
    tr25 = find_transcript(meta25["session_id"])
    isolation_requested = False
    strip_evidence = False
    if tr25:
        for rec in read_transcript_lines(tr25):
            blob = json.dumps(rec)
            if '"isolation"' in blob:
                isolation_requested = True
            if "block-remote-isolation" in blob or "updatedInput" in blob:
                strip_evidence = True
    r25.add_evidence(f"claude -p (session {meta25['session_id'][:8]})", output=(res25.response_text or "")[:200])
    r25.add_evidence("scan transcript for isolation param + strip evidence",
                     output=f"isolation_requested={isolation_requested} strip_evidence={strip_evidence}")
    if not isolation_requested:
        r25.verdict = Verdict.SKIP
        r25.detail = "Model omitted/refused the isolation parameter; nothing to strip (SKIP, not FAIL)."
    elif strip_evidence:
        r25.verdict = Verdict.PASS
        r25.detail = "block-remote-isolation.sh stripped the isolation parameter (hook evidence in transcript)."
    else:
        r25.verdict = Verdict.WARN
        r25.detail = "isolation requested but no explicit strip evidence found; dispatch did not hang."
    results.append(r25)

    # T2.6 — nested-dispatch deny (SKIP-tolerant): dispatch a general-purpose
    # subagent and instruct IT to attempt exactly one nested Agent dispatch,
    # which block-nested-dispatch.sh must deny (subagents may not dispatch
    # their own subagents — all dispatch authority belongs to the orchestrator).
    p26 = (
        "You are a deployment smoke test verifying a safety hook. Dispatch a "
        "'general-purpose' subagent via the Agent tool. Instruct that subagent to: "
        "(1) report whether an Agent or Task tool is present in its own toolset; "
        "(2) attempt EXACTLY ONE nested dispatch via the Agent tool with "
        "subagent_type \"general-purpose\" and prompt \"Reply with the single word "
        "OK and do nothing else.\", making no more than 2 attempts total; and "
        "(3) quote the VERBATIM outcome of that nested dispatch attempt (the exact "
        "denial text or result) in its final report. Relay the subagent's full "
        "report back to me verbatim."
    )
    res26, meta26 = execute_smoke_run(prompt=p26, max_turns=12, timeout=timeout, extra_env=extra_env)
    r26 = ProbeResult(probe_id="T2.6", name="Nested-dispatch deny hook", tier="2", profile=profile_name)
    tr26 = find_transcript(meta26["session_id"])
    subs26 = find_subagent_transcripts(meta26["session_id"])

    # nested_attempted: did the OUTER (dispatched) subagent itself try to call
    # Agent/Task — i.e. is there anything here for block-nested-dispatch.sh to
    # deny at all? Scanned from the outer subagent's own transcript, mirroring
    # how T2.5 scans for the isolation parameter before judging the strip.
    nested_attempted = False
    for tr in subs26:
        for name, _ in _tool_uses_in_transcript(tr):
            if name in ("Agent", "Task"):
                nested_attempted = True
                break
        if nested_attempted:
            break

    # denial_seen: the hook's permissionDecisionReason text ("...nested
    # subagents...") surfaced somewhere in the record — main transcript, the
    # outer subagent's transcript, or the relayed final response.
    denial_seen = False
    for tr in ([tr26] if tr26 else []) + subs26:
        for rec in read_transcript_lines(tr):
            if "nested subagents" in json.dumps(rec).lower():
                denial_seen = True
                break
        if denial_seen:
            break
    if not denial_seen and "nested subagents" in (res26.response_text or "").lower():
        denial_seen = True

    # nested_ran: a nested dispatch that actually EXECUTED would spawn its own
    # subagent transcript sidecar beyond the one outer dispatch this probe's
    # top-level prompt itself requests — more than one subagent transcript is
    # therefore the load-bearing signal that the deny path did NOT fire, and is
    # stronger evidence than a keyword scan alone (a model could paraphrase or
    # omit the denial text even though the hook correctly blocked the call).
    nested_ran = len(subs26) > 1

    r26.add_evidence(f"claude -p (session {meta26['session_id'][:8]})", output=(res26.response_text or "")[:300])
    r26.add_evidence("scan outer subagent transcript for an attempted Agent/Task tool_use",
                     output=f"nested_attempted={nested_attempted}")
    r26.add_evidence("scan transcripts + relayed response for 'nested subagents' denial text",
                     output=f"denial_seen={denial_seen}")
    r26.add_evidence("count subagent transcripts (>1 implies a nested dispatch actually spawned/ran)",
                     output=f"subagent_transcripts={len(subs26)} nested_ran={nested_ran}")
    if not nested_attempted:
        r26.verdict = Verdict.SKIP
        r26.detail = ("The dispatched subagent did not attempt a nested Agent/Task dispatch as instructed; "
                      "nothing for block-nested-dispatch.sh to deny (SKIP, not FAIL).")
    elif nested_ran:
        r26.verdict = Verdict.FAIL
        r26.detail = (
            f"A nested dispatch appears to have actually RUN ({len(subs26)} subagent transcripts found, "
            "more than the one outer dispatch this probe requests) — block-nested-dispatch.sh did not deny "
            "it. Most likely the hook is unregistered/misregistered in settings.json (it must sit first in "
            "both the Task and Agent matcher chains) or the harness stopped sending the agent_id/agent_type "
            "caller-identifying fields the hook keys on. Cross-check with tests/bash/block_nested_dispatch.bats."
        )
    elif denial_seen:
        r26.verdict = Verdict.PASS
        r26.detail = ("block-nested-dispatch.sh denied the nested dispatch attempt (denial text mentioning "
                      "'nested subagents' observed; no second-level subagent transcript was spawned).")
    else:
        r26.verdict = Verdict.WARN
        r26.detail = ("A nested dispatch was attempted and no second-level subagent transcript spawned "
                      "(consistent with a deny), but no explicit 'nested subagents' denial text was found in "
                      "the transcripts or relayed response — the deny path likely fired but the evidence is "
                      "inconclusive.")
    results.append(r26)

    return results


# --- Tier D: deterministic battery (opt-in, zero API cost) -----------------

def _run_battery_cmd(probe_id: str, name: str, cmd: list, timeout: int, cwd: str = BASE_DIR) -> ProbeResult:
    r = ProbeResult(probe_id=probe_id, name=name, tier="D")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-8:]
        r.add_evidence(" ".join(cmd), output="\n".join(tail))
        if proc.returncode == 0:
            r.verdict = Verdict.PASS
            r.detail = f"{name} passed."
        else:
            r.verdict = Verdict.FAIL
            r.detail = f"{name} exited {proc.returncode}."
    except FileNotFoundError as e:
        r.verdict = Verdict.SKIP
        r.detail = f"{name} tool unavailable: {e}"
        r.add_evidence(" ".join(cmd), note=str(e))
    except subprocess.TimeoutExpired:
        r.verdict = Verdict.FAIL
        r.detail = f"{name} timed out after {timeout}s."
    return r


def run_tier_d(include_skill_smoke: bool, timeout: int) -> list:
    """The deterministic battery: bats, Pester, lint, safety-hook tests,
    single-command tests, and (opt-in) the R/Python skill smoke suite via the
    CI log-stripped staging pattern. Zero API cost."""
    results = []
    results.append(_run_battery_cmd("TD.1", "bats tests/bash", ["bats", f"{BASE_DIR}/tests/bash/"], timeout))
    results.append(_run_battery_cmd(
        "TD.2", "Pester tests/powershell",
        ["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path {BASE_DIR}/tests/powershell -CI"], timeout))
    results.append(_run_battery_cmd("TD.3", "daaf-conventions lint", ["bash", f"{BASE_DIR}/tests/lint/check-daaf-conventions.sh"], timeout))
    results.append(_run_battery_cmd("TD.4", "safety-hook tests", ["bash", f"{BASE_DIR}/scripts/test_safety_hooks.sh"], timeout))
    results.append(_run_battery_cmd("TD.5", "single-command hook tests", ["bash", f"{BASE_DIR}/scripts/test_enforce_single_command.sh"], timeout))

    if include_skill_smoke:
        results.append(_run_skill_smoke(timeout))
    else:
        skip = ProbeResult(probe_id="TD.6", name="R/Python skill smoke suite", tier="D")
        skip.verdict = Verdict.SKIP
        skip.detail = "Skill smoke suite not requested (pass --include-r-smoke to enable; it is slow)."
        results.append(skip)
    return results


def _run_skill_smoke(timeout: int) -> ProbeResult:
    """Stage log-stripped copies of the R/Python skill smokes into
    scripts/scratch/smoke_live/ (NEVER /tmp) and run the existing runner against
    them via SMOKE_DIR — replicating ci-integration.yml Job 5's approach."""
    r = ProbeResult(probe_id="TD.6", name="R/Python skill smoke suite", tier="D")
    src = Path(BASE_DIR) / "scripts" / "smoke_tests"
    dst = Path(BASE_DIR) / "scripts" / "scratch" / "smoke_live"
    try:
        if dst.exists():
            for f in dst.glob("*"):
                if f.is_file():
                    f.unlink()
        dst.mkdir(parents=True, exist_ok=True)
        # Copy + log-strip each smoke script (delete from the first EXECUTION LOG
        # banner to EOF), mirroring the CI staging step.
        for smoke in list(src.glob("smoke_*.R")) + list(src.glob("smoke_*.py")):
            text = smoke.read_text()
            lines = text.splitlines()
            cut = None
            for i, line in enumerate(lines):
                if line.startswith("# EXECUTION LOG"):
                    cut = i - 1 if i > 0 else i  # drop the ==== rule line above too
                    break
            staged = "\n".join(lines[:cut]) if cut is not None else text
            (dst / smoke.name).write_text(staged)

        env = os.environ.copy()
        env["SMOKE_DIR"] = str(dst)
        proc = subprocess.run(
            ["bash", str(src / "run_all_smoke_tests.sh")],
            capture_output=True, text=True, timeout=timeout, cwd=BASE_DIR, env=env,
        )
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-12:]
        r.add_evidence(f"SMOKE_DIR={dst} bash run_all_smoke_tests.sh", output="\n".join(tail))
        if proc.returncode == 0:
            r.verdict = Verdict.PASS
            r.detail = "R/Python skill smoke suite passed (log-stripped live run)."
        else:
            r.verdict = Verdict.FAIL
            r.detail = f"Skill smoke suite reported failures (exit {proc.returncode})."
    except subprocess.TimeoutExpired:
        r.verdict = Verdict.FAIL
        r.detail = f"Skill smoke suite timed out after {timeout}s."
    except OSError as e:
        r.verdict = Verdict.FAIL
        r.detail = f"Skill smoke staging failed: {e}"
    return r
