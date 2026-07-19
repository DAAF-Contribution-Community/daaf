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
import shlex
import shutil
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


# Derive the repo root from this module's own location rather than hardcoding
# "/daaf": this file lives at {repo}/scripts/deploy_smoke/smoke_probes.py, so
# parents[2] is the repo root. In-container this resolves to "/daaf" exactly
# (preserving live-deployment behavior), while on a CI checkout it resolves to the
# runner's checkout path (e.g. /home/runner/work/daaf/daaf). Kept a str — it is
# interpolated into f-strings, wrapped in Path(...), and passed as cwd= throughout.
BASE_DIR = str(Path(__file__).resolve().parents[2])
SHIM_HEALTH_URL = "http://127.0.0.1:4141/health"
EXPECTED_SHIM_SERVICE = "daaf-anthropic-openai-shim"
_SAFE_SHIM_VERSION_RE = re.compile(r"[A-Za-z0-9._+-]{1,64}")
_GLM52_STATIC_ID = re.compile(r"z-ai/glm-5\.2(?:-[0-9]{8})?")


def _project_slug(base_dir: str) -> str:
    """Encode a working-directory path the way Claude Code names its
    ~/.claude/projects/<slug> transcript directory, derived from BASE_DIR rather
    than hardcoding "-daaf" (which is only correct when the deployment root is
    /daaf).

    Ground truth (in-container, 2026-07-17): `ls ~/.claude/projects/` shows a
    single entry `-daaf` for the working directory `/daaf`. Claude Code forms
    that slug by replacing path separators (and other non-alphanumeric
    punctuation) with `-`, so `/daaf` -> `-daaf`; under the same rule a CI
    checkout like `/home/runner/work/daaf/daaf` -> `-home-runner-work-daaf-daaf`.

    ASSUMES: every character outside [A-Za-z0-9] maps to a single `-`. This
    reproduces the in-container mapping (`/daaf` -> `-daaf`) and was verified
    equivalent to Claude Code's documented projects-dir encoding (separators and
    all non-ASCII-alphanumeric characters become `-`, uppercase preserved, no
    collapsing of consecutive separators; claude-code issue #19972, checked
    2026-07-17) across adversarial cases including `.`, `_`, spaces, consecutive
    separators, and non-ASCII — so exotic-punctuation handling is settled, not
    open. Invariant: _project_slug('/daaf') == '-daaf' (live-deployment behavior
    preserved)."""
    return re.sub(r"[^A-Za-z0-9]", "-", base_dir)


# Live projects-dir slug for this deployment root (see _project_slug). Computed
# once from BASE_DIR so find_transcript / find_subagent_transcripts agree.
_PROJECT_SLUG = _project_slug(BASE_DIR)


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


# Env vars a fully-configured LIVE install legitimately exports but that
# CONTAMINATE the deterministic Tier D batteries by steering default-window /
# default-branch fixtures onto the live session's values:
#   * CLAUDE_CODE_MAX_CONTEXT_TOKENS — the context-reporter/statusline bats
#     fixtures assume the payload window; a live 1050000 override flips default
#     tests.
#   * DAAF_BRANCH — the updater Pester fixtures model the default-branch flow; a
#     live daaf_dev_r2 export silently steers them onto another branch.
# Tier D removes ONLY these two as defense-in-depth ATOP each battery's own
# fixture isolation (bats setup() `unset`, Pester BeforeEach `Remove-Item`). It
# is NOT `env -i`: PATH, HOME, route credentials, and the developer toolchain
# are all preserved so the batteries can still find their interpreters.
TIER_D_CONTAMINANTS = ("CLAUDE_CODE_MAX_CONTEXT_TOKENS", "DAAF_BRANCH")


def tier_d_sanitized_env():
    """Return (env, removed): a copy of os.environ with only the known Tier D
    contaminants removed, plus the list of names actually removed.

    Pure with respect to os.environ — it copies first and never mutates the
    process environment."""
    env = os.environ.copy()
    removed = []
    for name in TIER_D_CONTAMINANTS:
        if name in env:
            env.pop(name, None)
            removed.append(name)
    return env, removed


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
    projects_dir = Path.home() / ".claude" / "projects" / _PROJECT_SLUG
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
    <projects>/<slug>/<session_id>/subagents/agent-<id>.jsonl (per subagent-bar.sh's
    sidecar contract, where <slug> is the BASE_DIR-derived _PROJECT_SLUG, e.g.
    "-daaf" for /daaf) — best-effort, fail-open to an empty list."""
    projects_dir = Path.home() / ".claude" / "projects" / _PROJECT_SLUG
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
    """GET the shim /health endpoint (shim routes only) and fail closed on its
    provenance schema before reporting bounded configuration evidence."""
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
        if not isinstance(health, dict):
            raise ValueError("shim /health JSON must be an object")
    except (URLError, socket.timeout, json.JSONDecodeError, OSError, ValueError) as e:
        r.verdict = Verdict.FAIL
        r.detail = f"shim /health unreachable/invalid: {type(e).__name__}: {str(e)[:200]}"
        r.add_evidence(f"GET {SHIM_HEALTH_URL}", note=str(e)[:200])
        return r

    version = health.get("version")
    version_is_safe = (
        isinstance(version, str)
        and _SAFE_SHIM_VERSION_RE.fullmatch(version) is not None
    )
    version_marker = version if version_is_safe else "<invalid>"

    codex_home_present = health.get("codex_home_present")
    codex_home_marker = (
        codex_home_present if isinstance(codex_home_present, bool) else "<invalid>"
    )

    # Preserve the response shape for audit evidence, but never reflect an unsafe
    # version or non-boolean auth-presence value. The local markers are bounded and
    # contain no endpoint-controlled text; secret-value scrubbing remains a second
    # defense before the snapshot enters the report.
    health_evidence = dict(health)
    if not version_is_safe:
        health_evidence["version"] = version_marker
    if "codex_home_present" in health and not isinstance(codex_home_present, bool):
        health_evidence["codex_home_present"] = codex_home_marker
    r.add_evidence(
        f"GET {SHIM_HEALTH_URL}",
        output=scrub_secret_values(json.dumps(health_evidence, indent=2)[:1500]),
    )

    expected_mode = "chatgpt" if route_info.detected_route == ROUTE_CHATGPT else "openai"
    actual_mode = health.get("backend_mode")
    problems = []
    if health.get("service") != EXPECTED_SHIM_SERVICE:
        problems.append(f"service must equal '{EXPECTED_SHIM_SERVICE}'")
    if health.get("status") != "ok":
        problems.append("status must equal 'ok'")
    if actual_mode != expected_mode:
        problems.append(f"backend_mode='{actual_mode}' but route expects '{expected_mode}'")
    if not version_is_safe:
        problems.append("version must match [A-Za-z0-9._+-]{1,64}")
    if route_info.detected_route == ROUTE_CHATGPT and codex_home_present is not True:
        problems.append(
            "codex_home_present must be boolean true "
            "(auth.json missing/unreadable) for chatgpt route"
        )

    r.add_evidence("", note=(
        f"backend_mode={actual_mode} sanitize_tools={health.get('sanitize_tools')} "
        f"codex_home_present={codex_home_marker} version={version_marker}"
    ))
    if problems:
        r.verdict = Verdict.FAIL
        r.detail = "; ".join(problems)
    else:
        r.verdict = Verdict.PASS
        r.detail = f"shim healthy: backend_mode={actual_mode}, version={version_marker}."
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


def probe_r_locale() -> ProbeResult:
    """Verify R starts under a UTF-8 locale (image ENV LANG/LC_ALL=C.UTF-8).

    Route-independent image property. Without it, R silently corrupts UTF-8:
    yaml::read_yaml() returns NULL with only a warning, and non-ASCII string
    literals are escape-mangled at parse time (unfixable by runtime
    Sys.setlocale). Python is immune via PEP 538 coercion; R has no equivalent,
    so the image env is the only complete fix. See interpreting-results.md T0.11.

    PEP 538 trap: this harness IS Python, and on a stale image (LANG/LC_ALL
    unset) the interpreter's startup coercion exports LC_CTYPE=C.UTF-8 into
    os.environ, which subprocesses inherit — an Rscript child would see a UTF-8
    LC_CTYPE and PASS even though bash-spawned R sessions get POSIX. When
    neither LANG nor LC_ALL is set, strip that coercion artifact from the child
    env so the probe reflects the true image environment."""
    r = ProbeResult(probe_id="T0.11", name="R UTF-8 locale", tier="0")
    cmd = ["Rscript", "-e", 'quit(status = !isTRUE(l10n_info()[["UTF-8"]]))']
    child_env = dict(os.environ)
    if not child_env.get("LANG") and not child_env.get("LC_ALL"):
        child_env.pop("LC_CTYPE", None)
        r.add_evidence(
            "env sanitization",
            note="LANG/LC_ALL unset: dropped inherited LC_CTYPE (PEP 538 coercion artifact) from child env",
        )
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=child_env)
        out = (proc.stdout + proc.stderr).strip()
        r.add_evidence(" ".join(cmd), output=out or f"<no output; exit {proc.returncode}>")
        if proc.returncode == 0:
            r.verdict = Verdict.PASS
            r.detail = "R starts under a UTF-8 locale (l10n_info()[['UTF-8']] is TRUE)."
        else:
            r.verdict = Verdict.FAIL
            r.detail = (
                "R is NOT in a UTF-8 locale — LANG/LC_ALL are unset in this image "
                "(stale or pre-v3.0.0 build) and R will silently corrupt UTF-8. "
                "Confirm the ENV LANG=C.UTF-8 / ENV LC_ALL=C.UTF-8 block near the "
                "top of the Dockerfile and rebuild (bash rebuild_daaf.sh from daaf-docker)."
            )
    except FileNotFoundError:
        r.verdict = Verdict.SKIP
        r.detail = "Rscript not on PATH — R locale check skipped."
        r.add_evidence(" ".join(cmd), note="FileNotFoundError: Rscript not found")
    except subprocess.TimeoutExpired:
        r.verdict = Verdict.FAIL
        r.detail = "Rscript locale check timed out."
    return r


def run_tier0(route_info: RouteInfo, env, base_dir: str = BASE_DIR):
    """Assemble the full Tier 0 preflight (route_detection probes + system probes).
    route_detection contributes T0.0-T0.4; this adds T0.5-T0.11."""
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
        probe_r_locale(),
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


# The exit-code record run_with_capture.sh appends after its execution-log
# banner: a full line "# Exit code: N". Anchored so "0" cannot match inside a
# larger number (e.g. 100).
_EXEC_EXIT0_RE = re.compile(r"^#\s*Exit code:\s*0\s*$", re.MULTILINE)


def _evaluate_t22(script_created: bool, body, nonce: str):
    """Pure evaluator for T2.2 — did the coding agent actually WRITE and
    SUCCESSFULLY EXECUTE its probe script via run_with_capture?

    Given whether this run's script exists, its full text (source plus any
    appended execution log), and this run's unique nonce, PASS requires ALL of:
      * the script exists;
      * run_with_capture's "# EXECUTION LOG" banner is present (proof it ran);
      * the captured "# Exit code: 0" record appears AFTER the banner (success);
      * this run's nonce appears AFTER the banner — proving it came from CAPTURED
        OUTPUT, not merely the source print line (the token is in the source by
        construction, so a source-only match is not proof of execution).
    Anything short of all four is FAIL — never PASS-with-note. A stale banner
    from a prior run carries a different nonce; a script written but never run
    has no banner; a nonzero recorded exit fails the success check.

    Returns (verdict, facts) where facts holds the load-bearing booleans."""
    facts = {"script_created": bool(script_created), "banner": False,
             "exit_success": False, "nonce_after_banner": False}
    if script_created and body:
        idx = body.find("# EXECUTION LOG")
        if idx != -1:
            facts["banner"] = True
            after = body[idx:]
            facts["exit_success"] = _EXEC_EXIT0_RE.search(after) is not None
            facts["nonce_after_banner"] = bool(nonce) and nonce in after
    verdict = Verdict.PASS if all(facts.values()) else Verdict.FAIL
    return verdict, facts


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
    # Per-run, UUID-owned run directory: T2.1/T2.2 fixtures live ONLY here, so a
    # fresh run can never be satisfied by a prior run's residue. A run dir left
    # by a hard process kill carries a stale UUID that no future run mints, so it
    # is inert. Cleanup in the finally below removes ONLY this exact directory.
    run_id = uuid.uuid4().hex
    run_dir = sandbox / f"run_{run_id}"
    run_dir.mkdir(parents=False, exist_ok=False)
    try:
        return _run_tier2_body(profile_name, extra_env, timeout, run_dir, results)
    finally:
        # Guaranteed cleanup of ONLY this run's owned directory — never
        # recursively clear _sandbox/ or touch a sibling. The guard re-checks
        # that the target is exactly sandbox/run_<run_id> before removal.
        try:
            if (run_dir.name == f"run_{run_id}" and run_dir.parent == sandbox
                    and run_dir.is_dir() and not run_dir.is_symlink()):
                shutil.rmtree(run_dir, ignore_errors=True)
        except OSError:
            pass


def _run_tier2_body(profile_name: str, extra_env: dict, timeout: int, sandbox: Path, results: list) -> list:
    """The six Tier 2 probes, operating inside the caller's per-run UUID sandbox.
    `sandbox` here is the run-owned directory (not the shared _sandbox/ root)."""
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

    # T2.2 — coding agent: research-executor writes + runs a tiny script via
    # run_with_capture. A run-specific nonce ties the CAPTURED OUTPUT to THIS run:
    # the token is present in the source by construction, so PASS additionally
    # requires the nonce to appear after the execution-log banner.
    exec_nonce = f"daaf-exec-{uuid.uuid4().hex[:12]}"
    probe_script = sandbox / "t22_probe.py"
    p22 = (
        "You are a deployment smoke test. Dispatch a 'research-executor' subagent via the "
        f"Agent tool. Instruct it to write a tiny Python script to "
        f"{probe_script} whose only action is to print exactly '{exec_nonce}', then "
        f"execute it with bash {BASE_DIR}/scripts/run_with_capture.sh {probe_script}. "
        "Report whether the run succeeded."
    )
    res22, meta22 = execute_smoke_run(prompt=p22, max_turns=12, timeout=timeout, extra_env=extra_env)
    r22 = ProbeResult(probe_id="T2.2", name="Coding agent write + execute", tier="2", profile=profile_name)
    script_created = probe_script.exists()
    body = None
    if script_created:
        try:
            body = probe_script.read_text()
        except OSError:
            body = None
    verdict22, facts22 = _evaluate_t22(script_created, body, exec_nonce)
    r22.add_evidence(f"claude -p (session {meta22['session_id'][:8]})", output=(res22.response_text or "")[:200])
    r22.add_evidence(f"test -f {probe_script}", output=str(script_created))
    r22.add_evidence("evaluate freshness: banner + '# Exit code: 0' + run nonce after banner",
                     output=(f"banner={facts22['banner']} exit_success={facts22['exit_success']} "
                             f"nonce_after_banner={facts22['nonce_after_banner']}"))
    r22.verdict = verdict22
    if verdict22 == Verdict.PASS:
        r22.detail = ("research-executor wrote the script and executed it via run_with_capture: "
                      "'# EXECUTION LOG' banner present, '# Exit code: 0' recorded, and this run's "
                      "nonce appears in the captured output after the banner.")
    else:
        r22.detail = ("T2.2 freshness/success check failed — required ALL of: script created, "
                      "execution-log banner, recorded '# Exit code: 0', and this run's nonce in "
                      f"captured output after the banner. Observed: {facts22}.")
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

def _bounded_excerpt(text: str, head: int = 20, tail: int = 20) -> str:
    """Head-and-tail excerpt with an explicit omission count, so both the early
    failure names and the final summary of a long battery log stay visible in the
    concise report while the middle is elided."""
    lines = text.splitlines()
    if len(lines) <= head + tail:
        return "\n".join(lines)
    omitted = len(lines) - head - tail
    return "\n".join(lines[:head] + [f"...[{omitted} lines omitted; full log in evidence/tier_d]..."] + lines[-tail:])


def _persist_tier_d_artifact(evidence_dir, probe_id: str, cmd_str: str,
                             scrubbed_output: str, status: str):
    """Write the COMPLETE scrubbed output for a failed/timed-out Tier D probe to
    evidence_dir/<probe_id>.log and return its path (str), or None on any I/O
    problem or when no evidence dir was provided. Best-effort; never raises."""
    if not evidence_dir:
        return None
    try:
        d = Path(evidence_dir)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{probe_id}.log"
        header = (
            f"# probe: {probe_id}\n"
            f"# command: {cmd_str}\n"
            f"# status: {status}\n"
            f"# NOTE: secret env values scrubbed via scrub_secret_values()\n\n"
        )
        path.write_text(header + (scrubbed_output or "<no captured output>") + "\n")
        return str(path)
    except OSError:
        return None


def _run_battery_cmd(probe_id: str, name: str, cmd: list, timeout: int,
                     cwd: str = BASE_DIR, env: dict = None, evidence_dir=None) -> ProbeResult:
    """Run one deterministic battery command and translate its result into a
    ProbeResult with a two-level evidence policy:
      * PASS — retain only the concise final eight lines.
      * FAIL/timeout — quote a bounded head-and-tail excerpt (early failure names
        AND final summary both visible) and persist the COMPLETE scrubbed output
        under evidence_dir/<probe_id>.log, referenced from the probe evidence.
    All captured output is scrubbed with scrub_secret_values before it is quoted
    or persisted; the command is rendered with shlex.join for an auditable, un-
    ambiguous representation."""
    r = ProbeResult(probe_id=probe_id, name=name, tier="D")
    cmd_str = shlex.join(cmd)
    # A missing WORKING DIRECTORY is a broken harness, not a missing tool. Without
    # this pre-check, subprocess.run(cwd=<nonexistent>) raises FileNotFoundError,
    # which the `except FileNotFoundError` handler below would swallow as SKIP
    # ("tool unavailable"). That is fail-open in an evidence harness: a misdetected
    # BASE_DIR (or an evidence dir that failed to materialize) would silently SKIP
    # the entire Tier D battery, and false negatives accrue false authority. Fail
    # loudly instead, and keep the FileNotFoundError handler for a genuinely missing
    # executable — the overwhelmingly common way it fires past this guard. (Strictly,
    # this is a check-then-run/TOCTOU pre-check: if cwd is removed in the narrow window
    # between the is_dir() check and subprocess.run, FileNotFoundError still lands in
    # the SKIP branch below. That race is accepted for contributor tooling.)
    if cwd is not None and not Path(cwd).is_dir():
        r.verdict = Verdict.FAIL
        r.detail = f"{name} could not run: working directory does not exist: {cwd}"
        r.add_evidence(cmd_str, note=f"working directory missing/unavailable: {cwd}")
        return r
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
        combined = scrub_secret_values((proc.stdout + proc.stderr).strip())
        if proc.returncode == 0:
            tail = combined.splitlines()[-8:]
            r.add_evidence(cmd_str, output="\n".join(tail))
            r.verdict = Verdict.PASS
            r.detail = f"{name} passed."
        else:
            r.add_evidence(cmd_str, output=_bounded_excerpt(combined))
            artifact = _persist_tier_d_artifact(evidence_dir, probe_id, cmd_str, combined,
                                                f"exit {proc.returncode}")
            if artifact:
                r.add_evidence("", note=f"complete scrubbed output: {artifact}")
            r.verdict = Verdict.FAIL
            r.detail = f"{name} exited {proc.returncode}."
    except FileNotFoundError as e:
        r.verdict = Verdict.SKIP
        r.detail = f"{name} tool unavailable: {e}"
        r.add_evidence(cmd_str, note=str(e))
    except subprocess.TimeoutExpired as e:
        # subprocess.run populates .output/.stderr on timeout when capturing, so
        # preserve whatever was emitted before the kill rather than discarding it.
        partial = ""
        for stream in (e.output, e.stderr):
            if not stream:
                continue
            partial += stream if isinstance(stream, str) else stream.decode("utf-8", "replace")
        partial = scrub_secret_values(partial.strip())
        r.add_evidence(cmd_str, output=(_bounded_excerpt(partial) if partial
                                        else "<no output captured before timeout>"))
        artifact = _persist_tier_d_artifact(evidence_dir, probe_id, cmd_str, partial,
                                            f"timeout after {timeout}s")
        if artifact:
            r.add_evidence("", note=f"complete scrubbed output (partial, pre-timeout): {artifact}")
        r.verdict = Verdict.FAIL
        r.detail = f"{name} timed out after {timeout}s."
    return r


def _run_tier_d_unit_tests(timeout: int, env: dict, evidence_dir) -> ProbeResult:
    """TD.0 — run this suite's own provider-free unittest module BEFORE the
    broader batteries, so an official Tier D run first validates its own harness
    (env sanitization, evidence capture, Tier 2 cleanup, T2.2 freshness)."""
    return _run_battery_cmd(
        "TD.0", "deploy-smoke harness unit tests",
        ["python3", "-m", "unittest", "discover", "-s", f"{BASE_DIR}/tests/python",
         "-p", "test_deploy_smoke.py", "-v"],
        timeout, env=env, evidence_dir=evidence_dir)


def run_tier_d(include_skill_smoke: bool, timeout: int, evidence_dir) -> list:
    """The deterministic battery: the harness self-test (TD.0), bats, Pester,
    lint, safety-hook tests, single-command tests, and (opt-in) the R/Python
    skill smoke suite via the CI log-stripped staging pattern. Zero API cost.

    All batteries run under a Tier-D-sanitized subprocess env (the two known
    live-config contaminants removed; PATH/HOME/credentials/toolchain intact),
    and every failure/timeout persists its complete scrubbed output under
    evidence_dir. Pester runs with its working directory set to evidence_dir so
    its NUnit testResults.xml lands in the report instead of the repo root."""
    results = []
    env, removed = tier_d_sanitized_env()
    # evidence_dir is required: without it, Pester's testResults.xml would fall
    # back to the repository root and the missing-XML contract check would be
    # silently skipped (artifact-ownership regression).
    tier_d_evidence = Path(evidence_dir)
    tier_d_evidence.mkdir(parents=True, exist_ok=True)

    # TD.0 — harness self-test first.
    td0 = _run_tier_d_unit_tests(timeout, env, tier_d_evidence)
    # Non-secret sanitization note (defense-in-depth record), attached to TD.0
    # since the sanitized env governs the whole tier.
    td0.add_evidence(
        "",
        note=(f"Tier D subprocess env sanitized: removed {list(removed)} "
              f"(defense-in-depth atop bats/Pester fixture isolation); "
              f"PATH/HOME/credentials/toolchain preserved."
              if removed else
              "Tier D subprocess env sanitized: no known contaminants "
              "(CLAUDE_CODE_MAX_CONTEXT_TOKENS, DAAF_BRANCH) were present."),
        is_inference=False)
    results.append(td0)

    results.append(_run_battery_cmd("TD.1", "bats tests/bash", ["bats", f"{BASE_DIR}/tests/bash/"],
                                    timeout, env=env, evidence_dir=tier_d_evidence))

    # TD.2 — Pester. Run WITH the working directory set to the Tier D evidence dir
    # so Invoke-Pester -CI writes its NUnit testResults.xml there rather than at
    # the repository root (/daaf/testResults.xml).
    td2_cwd = str(tier_d_evidence)
    td2 = _run_battery_cmd(
        "TD.2", "Pester tests/powershell",
        ["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path {BASE_DIR}/tests/powershell -CI"],
        timeout, cwd=td2_cwd, env=env, evidence_dir=tier_d_evidence)
    # A zero Pester exit with a MISSING report-local XML is a TD.2 failure: the
    # artifact-ownership contract requires the XML to land in the report evidence.
    if td2.verdict == Verdict.PASS:
        xml_path = tier_d_evidence / "testResults.xml"
        if xml_path.exists():
            td2.add_evidence(f"test -f {xml_path}", output=str(xml_path))
        else:
            td2.verdict = Verdict.FAIL
            td2.detail = ("Pester exited 0 but its NUnit testResults.xml is missing from the report "
                          "evidence dir — artifact-routing failure (TD.2).")
            td2.add_evidence(f"test -f {xml_path}", output="missing")
    results.append(td2)

    results.append(_run_battery_cmd("TD.3", "daaf-conventions lint", ["bash", f"{BASE_DIR}/tests/lint/check-daaf-conventions.sh"],
                                    timeout, env=env, evidence_dir=tier_d_evidence))
    results.append(_run_battery_cmd("TD.4", "safety-hook tests", ["bash", f"{BASE_DIR}/scripts/test_safety_hooks.sh"],
                                    timeout, env=env, evidence_dir=tier_d_evidence))
    results.append(_run_battery_cmd("TD.5", "single-command hook tests", ["bash", f"{BASE_DIR}/scripts/test_enforce_single_command.sh"],
                                    timeout, env=env, evidence_dir=tier_d_evidence))

    if include_skill_smoke:
        results.append(_run_skill_smoke(timeout, env=env, evidence_dir=tier_d_evidence))
    else:
        skip = ProbeResult(probe_id="TD.6", name="R/Python skill smoke suite", tier="D")
        skip.verdict = Verdict.SKIP
        skip.detail = "Skill smoke suite not requested (pass --include-r-smoke to enable; it is slow)."
        results.append(skip)
    return results


def _run_skill_smoke(timeout: int, env: dict = None, evidence_dir=None) -> ProbeResult:
    """Stage log-stripped copies of the R/Python skill smokes into
    scripts/scratch/smoke_live/ (NEVER /tmp) and run the existing runner against
    them via SMOKE_DIR — replicating ci-integration.yml Job 5's approach.

    Runs under the Tier-D-sanitized env (defense-in-depth) and applies the same
    failure-artifact policy as the other batteries: scrubbed output, a bounded
    head-and-tail excerpt on failure, and complete output persisted under
    evidence_dir."""
    r = ProbeResult(probe_id="TD.6", name="R/Python skill smoke suite", tier="D")
    src = Path(BASE_DIR) / "scripts" / "smoke_tests"
    dst = Path(BASE_DIR) / "scripts" / "scratch" / "smoke_live"
    cmd_str = f"SMOKE_DIR={dst} bash {src / 'run_all_smoke_tests.sh'}"
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

        run_env = dict(env) if env is not None else os.environ.copy()
        run_env["SMOKE_DIR"] = str(dst)
        proc = subprocess.run(
            ["bash", str(src / "run_all_smoke_tests.sh")],
            capture_output=True, text=True, timeout=timeout, cwd=BASE_DIR, env=run_env,
        )
        combined = scrub_secret_values((proc.stdout + proc.stderr).strip())
        if proc.returncode == 0:
            tail = combined.splitlines()[-12:]
            r.add_evidence(cmd_str, output="\n".join(tail))
            r.verdict = Verdict.PASS
            r.detail = "R/Python skill smoke suite passed (log-stripped live run)."
        else:
            r.add_evidence(cmd_str, output=_bounded_excerpt(combined))
            artifact = _persist_tier_d_artifact(evidence_dir, "TD.6", cmd_str, combined,
                                                f"exit {proc.returncode}")
            if artifact:
                r.add_evidence("", note=f"complete scrubbed output: {artifact}")
            r.verdict = Verdict.FAIL
            r.detail = f"Skill smoke suite reported failures (exit {proc.returncode})."
    except subprocess.TimeoutExpired as e:
        partial = ""
        for stream in (e.output, e.stderr):
            if not stream:
                continue
            partial += stream if isinstance(stream, str) else stream.decode("utf-8", "replace")
        partial = scrub_secret_values(partial.strip())
        r.add_evidence(cmd_str, output=(_bounded_excerpt(partial) if partial
                                        else "<no output captured before timeout>"))
        artifact = _persist_tier_d_artifact(evidence_dir, "TD.6", cmd_str, partial,
                                            f"timeout after {timeout}s")
        if artifact:
            r.add_evidence("", note=f"complete scrubbed output (partial, pre-timeout): {artifact}")
        r.verdict = Verdict.FAIL
        r.detail = f"Skill smoke suite timed out after {timeout}s."
    except OSError as e:
        r.verdict = Verdict.FAIL
        r.detail = f"Skill smoke staging failed: {e}"
    return r
