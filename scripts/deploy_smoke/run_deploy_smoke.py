#!/usr/bin/env python3
"""DAAF deployment smoke-testing suite — CLI entry point.

Verifies that a LIVE DAAF installation, configured exactly as the user set it up,
is functioning end-to-end. This is deployment/configuration verification — NOT
framework-adherence evaluation (that is DAAFBench) and NOT the R-package smoke
tests under scripts/smoke_tests/.

The suite runs IN SITU inside a real installation. The operator states the
install route with --route (a required choice of the five route IDs); Tier 0
proves the container's identity by FAILing T0.1 when detection disagrees.
Route-appropriate probes then run across tiers:

  Tier 0  preflight, no LLM      image flavor (INFO) + route detection + env coherence + hooks/statusline/
                                 shim/invariants + R locale + local-settings shadowing + claude.ai synced
                                 surface (INFO) + versions/identity + settings invariants
  Tier N  network, no LLM        route endpoint reachability, web_fetch, scholar_search, education-data mirror
  Tier D  deterministic battery  bats / Pester / lint / hook tests + local browser services (zero API cost;
                                 --tier-d-all adds route-scoped suites on other routes)
  Tier 1  one live round-trip    one claude -p call + the plumbing evidence around it
  Tier 2  functional battery     capability-structural probes (dispatch, coding in Python and R, web,
                                 skill, isolation, nested-dispatch prevention, guardrails)
  Tier A  Auto mode (opt-in)     one claude -p --permission-mode auto call
  Tier 3  golden path (opt-in)   mode-confirmation gate + Pre-K answer with a curated-skill retrieval
                                 (by the orchestrator or its Data Lookup specialist)

The suite runs on any DAAF image (T0.0 reports whether it is the developer
image, which adds the bats and Pester batteries). Before any paid tier (1, 2,
A, 3) a preflight gate applies: T0.1, T0.3, T0.16 and T0.17 must not FAIL,
reusing Tier 0's results or running them as a "gate subset" when Tier 0 is not
selected; a FAIL records T0.ABORT and skips the paid tiers unless
--allow-preflight-fail is given. Then each profile's T0.14 is re-checked on
its own environment; a named --profiles overlay also re-runs T0.1, T0.3,
T0.16 and T0.17 there (the profile gate), and a FAIL skips that profile only.

Tiers N, A and 3 are provided by smoke_probes' run_tier_n / run_tier_a /
run_tier_3 (smoke v2 contract); a checkout without them records a SKIP saying
so rather than failing the run. On shim routes, when any live tier ran, a
Post-run shim-log scan over this run's window follows the live tiers and
carries the shim-log verdict (report section "Post-run").

Reports land under scripts/deploy_smoke/reports/{YYYYMMDD_HHMMSS}_{stated route}/ with a
human report.md that opens with a Diagnosis summary (identity block, a problems
table FAIL-then-WARN with likely cause, evidence path inside the package and
where to fix, then a passed count by tier) followed by full per-probe detail
(ANSI-free); a machine report.json (schema_version 2: started_utc, versions{},
per-probe duration_s / session_ids / cost_usd / hint); and an evidence/ dir
(shim_health.json, env_fingerprint.json, tier_d/ full failure logs and Pester
testResults.xml, t07_statusline_cache/ and t16_statusline_cache/).

SIGTERM and SIGHUP unwind like Ctrl+C: every cleanup runs (TD.9 stops its
services), the run is recorded as RUN.CRASH, and the exit code is 128 + the
signal number (143, 129; 130 after Ctrl+C). When the terminal itself was
closed, the rest of the console output goes to os.devnull, so the report and
package are still written.

Every run, including one whose tier block crashed, then builds a portable
diagnostic package (smoke_package.py) under scripts/deploy_smoke/packages/ and
prints the commands that copy it to the main container. There,
`--import PKG [PKG ...]` runs no probes: it verifies and extracts packages into
scripts/deploy_smoke/inbox/<package>/ and writes inbox/MATRIX.md when two or
more are present. Overall exit is nonzero on any FAIL, matching the
run_all_smoke_tests.sh contract.

Framework tooling: standalone-CLI-tool exception to the no-functions rule — this
uses normal engineering style with functions, matching benchmarks/harness/.

Usage:
  python3 scripts/deploy_smoke/run_deploy_smoke.py --route anthropic-subscription --tiers 0 --yes
  python3 scripts/deploy_smoke/run_deploy_smoke.py --route openrouter --profiles openrouter-claude,openrouter-gpt
  python3 scripts/deploy_smoke/run_deploy_smoke.py --route chatgpt-subscription --tiers 0,D,N,1,2,A,3
  python3 scripts/deploy_smoke/run_deploy_smoke.py --import scripts/deploy_smoke/inbox/<pkg>.zip [more.zip ...]
"""

import argparse
import inspect
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# --- sys.path guard: make `benchmarks...` and the sibling modules importable
# regardless of the caller's CWD (robustness per the reuse recommendation). ---
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[1]  # scripts/deploy_smoke/ -> scripts/ -> /daaf
for _p in (str(_REPO_ROOT), str(_THIS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402

import route_detection  # noqa: E402
from route_detection import (  # noqa: E402
    Verdict,
    ProbeResult,
    ROUTE_OPENROUTER,
    SHIM_ROUTES,
    build_route_info,
    env_fingerprint,
    scrub_secret_values,
)
import smoke_probes  # noqa: E402
import smoke_package  # noqa: E402


# Single source of truth: reuse smoke_probes' BASE_DIR (derived from that module's
# own location, not hardcoded "/daaf") so this CLI and the probes it drives agree
# on the deployment root on every checkout (in-container /daaf, CI runner path,
# etc.). smoke_probes does not import this module, so there is no import cycle.
BASE_DIR = smoke_probes.BASE_DIR
REPORTS_ROOT = _THIS_DIR / "reports"
PACKAGES_ROOT = smoke_package.PACKAGES_ROOT
INBOX_ROOT = smoke_package.INBOX_ROOT
PROFILES_PATH = _THIS_DIR / "profiles.yaml"

# report.json schema: 1 = pre-v2 (no version field); 2 = smoke v2 (2026-10-13):
# schema_version, started_utc, ended_utc, stated_route, versions{}, and per-probe
# duration_s / session_ids / cost_usd / hint.
REPORT_SCHEMA_VERSION = 2

# The five install routes, in the order the skill presents them. Dispatch-1's
# ROUTE_ANTHROPIC_API may not exist on an older route_detection, hence getattr.
ROUTE_ANTHROPIC_API = getattr(route_detection, "ROUTE_ANTHROPIC_API", "anthropic-api")
ROUTE_CHOICES = (
    route_detection.ROUTE_ANTHROPIC,
    ROUTE_ANTHROPIC_API,
    route_detection.ROUTE_CHATGPT,
    route_detection.ROUTE_OPENAI_API,
    ROUTE_OPENROUTER,
)

VALID_TIERS = ("0", "1", "2", "D", "N", "A", "3")
LIVE_TIERS = ("1", "2", "A", "3")
# Approximate claude -p calls per profile (design §12.4): Tier 2 is six probes
# plus T2.7 guardrails plus T2.8, the R twin of T2.2 (coverage design D4,
# 2026-11-01).
LIVE_CALLS_PER_PROFILE = {"1": 1, "2": 8, "A": 1, "3": 2}
# The preflight gate applied before any live tier (coverage design D2): kept in
# step with smoke_probes.GATE_PROBE_IDS, which is preferred when present.
GATE_PROBE_IDS = tuple(getattr(smoke_probes, "GATE_PROBE_IDS", ("T0.1", "T0.3", "T0.16", "T0.17")))
# The gate probes re-run per named --profiles overlay, on that profile's child
# environment, next to its T0.14 re-check (review fix H2).
PROFILE_GATE_PROBE_IDS = tuple(getattr(smoke_probes, "PROFILE_GATE_PROBE_IDS", ("T0.1", "T0.3", "T0.16", "T0.17")))
PROFILE_GATE_SUFFIX = getattr(smoke_probes, "PROFILE_GATE_SUFFIX", " (profile gate)")
# Timeout floors applied inside Tier D whatever --timeout says (a larger value wins).
TD1_MIN_TIMEOUT_S = getattr(smoke_probes, "TD1_MIN_TIMEOUT_S", 1800)
TD7_MIN_TIMEOUT_S = getattr(smoke_probes, "TD7_MIN_TIMEOUT_S", 900)

# SIGTERM (`timeout`, `kill`, a CI cancellation) and SIGHUP (a closed terminal)
# would otherwise end the process without running any `finally`: TD.9's
# start_new_session services would outlive the run, and no report or package
# would be written. main() turns them into TerminationSignal, a SystemExit, so
# they unwind exactly like Ctrl+C (KeyboardInterrupt), which is left as it is.
TERMINATION_SIGNALS = tuple(getattr(signal, n) for n in ("SIGTERM", "SIGHUP") if hasattr(signal, n))
# After a terminal hang-up, every write to that terminal raises OSError (EIO).
# A console print in the unwind would then stop it before the package step and
# turn exit 129 into a crash. So a real SIGHUP points the descriptors that were
# terminals at os.devnull (_detach_console), and during the unwind sys.stdout
# and sys.stderr are wrapped (_UnwindConsole) so that any console write raising
# OSError detaches that descriptor and drops the text instead of raising.
_SIGHUP = getattr(signal, "SIGHUP", None)


def _terminal_fds() -> tuple:
    """The descriptors among stdout (1) and stderr (2) that are terminals."""
    fds = []
    for fd in (1, 2):
        try:
            if os.isatty(fd):
                fds.append(fd)
        except OSError:
            pass
    return tuple(fds)


def _detach_console(fds) -> None:
    """Point each descriptor in fds at os.devnull with dup2, so later output on
    it is discarded instead of failing. sys.stdout and sys.stderr keep their
    objects and now write to os.devnull. Never raises."""
    fds = tuple(fds)
    if not fds:
        return
    try:
        null = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        return
    try:
        for fd in fds:
            try:
                os.dup2(null, fd)
            except OSError:
                pass
    finally:
        if null not in fds:
            os.close(null)


class _UnwindConsole:
    """sys.stdout or sys.stderr while the report and package are written. A
    write or flush that raises OSError (EIO after a terminal hang-up, EPIPE from
    a closed pipe) detaches the stream's descriptor (_detach_console) and drops
    that text, so the unwind goes on to the package step and the exit code. Any
    other exception propagates; every other attribute is the wrapped stream's."""

    def __init__(self, inner):
        self._inner = inner

    def _detach(self):
        try:
            fd = self._inner.fileno()
        except (OSError, ValueError, AttributeError):  # e.g. io.StringIO has no descriptor
            return
        _detach_console((fd,))

    def write(self, text):
        try:
            return self._inner.write(text)
        except OSError:
            self._detach()
            return len(text)

    def flush(self):
        try:
            self._inner.flush()
        except OSError:
            self._detach()

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _protect_console():
    """Wrap sys.stdout and sys.stderr in _UnwindConsole; returns the originals
    for _restore_console. A None stream (no console at all) stays None."""
    saved = (sys.stdout, sys.stderr)
    if sys.stdout is not None and not isinstance(sys.stdout, _UnwindConsole):
        sys.stdout = _UnwindConsole(sys.stdout)
    if sys.stderr is not None and not isinstance(sys.stderr, _UnwindConsole):
        sys.stderr = _UnwindConsole(sys.stderr)
    return saved


def _restore_console(saved) -> None:
    if saved is not None:
        sys.stdout, sys.stderr = saved


class TerminationSignal(SystemExit):
    """SIGTERM or SIGHUP as an exception. A SystemExit, so `except Exception`
    in a probe never swallows it; its exit code is 128 + the signal number (143
    for SIGTERM, 129 for SIGHUP), the shell's convention for a signal death."""

    def __init__(self, signum):
        self.signum = signum
        try:
            self.signame = signal.Signals(signum).name
        except ValueError:
            self.signame = f"signal {signum}"
        super().__init__(128 + signum)

    def __str__(self):
        return f"received {self.signame}"


class _TerminationGuard:
    """Installs the SIGTERM/SIGHUP handlers for one run and restores the
    previous ones afterwards (main() may run in-process, e.g. under the
    self-tests). Only the first signal raises: a later one, or any signal once
    the report is being written (finishing()), is recorded and acted on after
    the report and package exist, so a second SIGTERM cannot cut TD.9's stop
    ladder or the report short. The handler never prints: a print from inside a
    signal handler can collide with a print it interrupted. A SIGHUP, which
    normally means the terminal is gone, first points the descriptors that were
    terminals at install() at os.devnull, so the unwind's console output cannot
    fail; output to a pipe or file is left as it is."""

    def __init__(self):
        self.previous = {}
        self.raised = False
        self.finishing_now = False
        self.deferred = None
        self.console_ttys = ()

    def install(self):
        self.console_ttys = _terminal_fds()
        for sig in TERMINATION_SIGNALS:
            try:
                self.previous[sig] = signal.signal(sig, self._handle)
            except (ValueError, OSError):  # not the main thread, or not supported here
                pass
        return self

    def _handle(self, signum, frame):  # noqa: ARG002 — signal handler signature
        if signum == _SIGHUP and self.console_ttys:
            _detach_console(self.console_ttys)
            self.console_ttys = ()
        if self.raised or self.finishing_now:
            if self.deferred is None:
                self.deferred = signum
            return
        self.raised = True
        raise TerminationSignal(signum)

    def finishing(self):
        self.finishing_now = True

    def restore(self):
        for sig, prev in self.previous.items():
            try:
                signal.signal(sig, prev if prev is not None else signal.SIG_DFL)
            except (ValueError, OSError):
                pass
        self.previous = {}

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# --- Helpers --------------------------------------------------------------

def git_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", BASE_DIR, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "<unknown>"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "<unknown>"


def _run_quiet(cmd, timeout=15, cwd=None):
    """First line of a short command's stdout, or "<unavailable>" on any error."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "<unavailable>"
    if proc.returncode != 0:
        return "<unavailable>"
    out = strip_ansi(proc.stdout).strip().splitlines()
    return out[0][:160] if out else ""


DIRTY_SCOPE = "tracked and untracked (git status --porcelain)"


def collect_versions(base_dir=None) -> dict:
    """Per-run identity for the report and package: DAAF branch / SHA /
    describe-dirty / dirty file count, Claude Code and Codex CLI versions,
    Python. smoke_probes.collect_versions (the T0.15 source) is used when this
    checkout has it, so the identity block's dirty count and T0.15's agree:
    both count tracked AND untracked files (git status --porcelain; the scope
    is recorded as daaf_dirty_scope). The fallback below runs the same command.
    The shim version is filled in later from T0.8's /health evidence."""
    base = str(base_dir or BASE_DIR)
    probe_versions = None
    fn = getattr(smoke_probes, "collect_versions", None)
    if callable(fn):
        try:
            probe_versions = fn(base)
        except Exception as exc:  # noqa: BLE001 — identity must never crash a run; fall back below
            print(f"WARN: smoke_probes.collect_versions failed ({type(exc).__name__}); "
                  "using the runner's own version probe.", file=sys.stderr)
    if isinstance(probe_versions, dict):
        return {
            "daaf_branch": probe_versions.get("daaf_branch") or "<unavailable>",
            "daaf_sha": probe_versions.get("daaf_sha") or "<unavailable>",
            "daaf_describe": probe_versions.get("daaf_describe") or "<unavailable>",
            "daaf_dirty_files": probe_versions.get("dirty_files"),
            "daaf_dirty_scope": DIRTY_SCOPE,
            "claude_code": probe_versions.get("claude_code") or "<unavailable>",
            "claude_code_pin": probe_versions.get("claude_code_pin"),
            "codex": probe_versions.get("codex"),
            "shim": None,
            "shim_source": probe_versions.get("shim_source"),
            "python": platform.python_version(),
            "source": "smoke_probes.collect_versions",
        }
    versions = {
        "daaf_branch": _run_quiet(["git", "-C", base, "rev-parse", "--abbrev-ref", "HEAD"]),
        "daaf_sha": _run_quiet(["git", "-C", base, "rev-parse", "HEAD"]),
        "daaf_describe": _run_quiet(["git", "-C", base, "describe", "--always", "--dirty"]),
        "daaf_dirty_files": None,
        "daaf_dirty_scope": DIRTY_SCOPE,
        "claude_code": _run_quiet(["claude", "--version"]),
        "codex": _run_quiet(["codex", "--version"], timeout=10) if shutil.which("codex") else None,
        "shim": None,
        "python": platform.python_version(),
        "source": "run_deploy_smoke.collect_versions (fallback)",
    }
    try:
        proc = subprocess.run(["git", "-C", base, "status", "--porcelain"],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            versions["daaf_dirty_files"] = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return versions


def strip_ansi(text):
    """Remove ANSI escape sequences and stray control characters (keeps \\n, \\t).

    The escaped text forms (\\u001b[…, \\x1b[, \\033[, \\e[ — what jq writes when
    a statusline emits JSON) are removed by route_detection.strip_ansi first, so
    every evidence block in the report gets the same treatment as T0.7/T1.6."""
    if not isinstance(text, str) or not text:
        return text
    shared = getattr(route_detection, "strip_ansi", None)
    if callable(shared):
        text = shared(text)
    return _CTRL_RE.sub("", _ANSI_RE.sub("", text))


def _strip_ansi_deep(obj):
    if isinstance(obj, str):
        return strip_ansi(obj)
    if isinstance(obj, list):
        return [_strip_ansi_deep(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_ansi_deep(v) for k, v in obj.items()}
    return obj


def load_profiles(names: list) -> list:
    """Load named env-overlay profiles from profiles.yaml.

    Returns a list of (name, env_overlay_dict). If no --profiles given, returns a
    single unnamed default ("", {}) meaning: run once with the ambient env only.
    """
    if not names:
        return [("", {})]
    if not PROFILES_PATH.exists():
        print(f"ERROR: --profiles requested but {PROFILES_PATH} not found.", file=sys.stderr)
        sys.exit(2)
    with open(PROFILES_PATH) as f:
        data = yaml.safe_load(f) or {}
    defined = data.get("profiles", {}) or {}
    out = []
    for name in names:
        name = name.strip()
        if name not in defined:
            print(f"ERROR: profile '{name}' not defined in {PROFILES_PATH}. "
                  f"Available: {', '.join(defined.keys())}", file=sys.stderr)
            sys.exit(2)
        overlay = (defined[name] or {}).get("env", {}) or {}
        # Coerce all overlay values to str (env vars are strings).
        overlay = {k: str(v) for k, v in overlay.items()}
        out.append((name, overlay))
    return out


def parse_tiers(spec: str) -> list:
    """Parse --tiers like '0,1,2' or '0,D,N,1,2,A,3' into an ordered unique list.

    Invalid tokens are a HARD ERROR (ValueError naming the offending token and
    the valid set), never silently dropped: a typo like '--tiers D,X' must not
    quietly run only Tier D and let the operator believe X also ran. Letter
    tiers are case-insensitive. Empty tokens (from stray commas or an empty
    spec) are ignored; a spec with no valid tier yields an empty list, which the
    caller reports separately."""
    valid = set(VALID_TIERS)
    tiers = []
    for raw in spec.split(","):
        t = raw.strip()
        if not t:
            continue
        norm = t.upper()
        if norm not in valid:
            raise ValueError(
                f"invalid tier token '{t}' in --tiers; valid tokens are "
                f"{', '.join(VALID_TIERS)}"
            )
        if norm not in tiers:
            tiers.append(norm)
    return tiers


def verdict_counts(results: list) -> dict:
    counts = {Verdict.PASS: 0, Verdict.FAIL: 0, Verdict.SKIP: 0, Verdict.WARN: 0, Verdict.INFO: 0}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1
    return counts


def _result_dict(r) -> dict:
    d = r.to_dict()
    # Probes that name their session only in evidence text (pre-v2 shapes)
    # still get session_ids, so the package can find their transcripts.
    if not d.get("session_ids"):
        d["session_ids"] = list(smoke_package.session_ids_for_result(r))
    d["hint"] = d.get("hint") or ""
    return _strip_ansi_deep(d)


def _crash_result(tier: str, label: str, exc: BaseException) -> ProbeResult:
    """Synthetic FAIL recording an exception that escaped a tier (or the whole
    tier block), so the report and package still say what happened."""
    probe_id = ("RUN.CRASH" if tier in ("", "run") else "POST.CRASH" if tier == POST_RUN_TIER
                else f"T{tier}.CRASH")
    r = ProbeResult(probe_id=probe_id, name=f"{label} crashed", tier=tier or "run")
    r.verdict = Verdict.FAIL
    r.detail = f"{label} raised {type(exc).__name__}: {scrub_secret_values(str(exc))[:300]}"
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    r.add_evidence("traceback (last 40 lines, secret env values scrubbed)",
                   output="\n".join(scrub_secret_values(tb).splitlines()[-40:]))
    r.hint = ("A harness exception, not a deployment verdict: the traceback names the failing "
              "line in scripts/deploy_smoke/. Fix the harness, then re-run the tier.")
    # An interrupt is not a harness defect either: Ctrl+C gets the same
    # re-run advice as SIGTERM/SIGHUP, never "Fix the harness".
    if isinstance(exc, TerminationSignal):
        r.hint = (f"Not a deployment verdict: the run received {exc.signame} (a closed terminal, `timeout`, "
                  "`kill` or a CI cancellation) and stopped; probes that had started were cleaned up. "
                  "Re-run the tiers that did not finish.")
    elif isinstance(exc, KeyboardInterrupt):
        r.hint = ("Not a deployment verdict: the run received SIGINT (Ctrl+C) and stopped; probes that had "
                  "started were cleaned up. Re-run the tiers that did not finish.")
    return r


def _unavailable_result(tier: str, fn_name: str, why: str) -> ProbeResult:
    probe_id = "POST.UNAVAILABLE" if tier == POST_RUN_TIER else f"T{tier}.UNAVAILABLE"
    r = ProbeResult(probe_id=probe_id, name=f"Tier {tier} not available", tier=tier)
    r.verdict = Verdict.SKIP
    r.detail = f"Tier {tier} was not run: smoke_probes.{fn_name} {why}."
    r.add_evidence(f"getattr(smoke_probes, {fn_name!r})", output=why)
    return r


def _guarded_tier(tier: str, label: str, fn, *args, **kwargs) -> list:
    """Run one tier entry point; an ordinary exception becomes a synthetic FAIL
    and the run continues with the next tier. KeyboardInterrupt / SystemExit
    propagate to main()'s try/finally, which still writes report and package."""
    try:
        return list(fn(*args, **kwargs) or [])
    except Exception as exc:  # noqa: BLE001 — recorded as a FAIL, never swallowed
        print(f"ERROR: Tier {tier} raised {type(exc).__name__}; recorded as {tier}.CRASH FAIL.",
              file=sys.stderr)
        return [_crash_result(tier, label, exc)]


def _call_tier_entry(tier: str, fn_name: str, *args, **kwargs) -> list:
    """Call a smoke-v2 tier entry point (run_tier_n / run_tier_a / run_tier_3).
    A checkout without it records a SKIP instead of failing the run."""
    fn = getattr(smoke_probes, fn_name, None)
    if fn is None or not callable(fn):
        return [_unavailable_result(tier, fn_name, "is not available in this checkout")]
    return _guarded_tier(tier, f"smoke_probes.{fn_name}", fn, *args, **kwargs)


def _optional_kwargs(fn, **candidates) -> dict:
    """The subset of candidate keyword arguments `fn` names in its signature
    (all of them when it takes **kwargs). Used for the post-run shim-log scan,
    whose keyword set may still change; the tier entry points are called
    directly."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {}
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return dict(candidates)
    return {k: v for k, v in candidates.items() if k in params}


POST_RUN_TIER = "post"
POST_RUN_SECTION = "Post-run"


def _post_run_shim_scan(route: str, started_utc) -> list:
    """S3: after the live tiers, scan shim.log from the run start (container
    local time, the shim's asctime format) so the shim-log verdict covers this
    run only. Tier 0's scan of the history before the run is INFO; this one
    carries the verdict. A checkout without the scan function records a SKIP."""
    fn = getattr(smoke_probes, "probe_shim_log_scan", None)
    if not callable(fn):
        return [_unavailable_result(POST_RUN_TIER, "probe_shim_log_scan", "is not available in this checkout")]
    since = started_utc.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    kwargs = _optional_kwargs(fn, since=since, tier=POST_RUN_TIER,
                              name="Shim-log scan (post-run window)")
    out = _guarded_tier(POST_RUN_TIER, "smoke_probes.probe_shim_log_scan", lambda: [fn(route, **kwargs)])
    for r in out:
        r.tier = POST_RUN_TIER  # whatever the signature accepted, report it in the Post-run section
    hints = getattr(smoke_probes, "apply_hints", None)
    return hints(out) if callable(hints) else out


def _apply_preflight_gate(route_info, env, tier0_results):
    """Coverage design D2. Returns (gate, ran, blocking, reused, missing):
    gate     — every gate result judged (reused Tier 0 results + newly run ones);
    ran      — the gate-subset results run now (to add to the report);
    blocking — the FAILing gate results (a crashed gate run is a T0.CRASH FAIL
               and blocks too: fail closed);
    reused / missing — the gate probe IDs taken from Tier 0 / run as the subset.
    The subset runs through _guarded_tier, so an exception (including a checkout
    without smoke_probes.run_preflight_gate) becomes a FAIL, never a pass."""
    reused_results = [r for r in (tier0_results or []) if r.probe_id in GATE_PROBE_IDS]
    seen = {r.probe_id for r in reused_results}
    reused = [pid for pid in GATE_PROBE_IDS if pid in seen]
    missing = [pid for pid in GATE_PROBE_IDS if pid not in seen]
    ran = []
    if missing:
        ran = _guarded_tier("0", "smoke_probes.run_preflight_gate",
                            lambda: smoke_probes.run_preflight_gate(route_info, env, BASE_DIR,
                                                                    probe_ids=tuple(missing)))
    gate = reused_results + ran
    blocking = [r for r in gate if r.verdict in Verdict.FAILING]
    return gate, ran, blocking, reused, missing


def _preflight_abort_result(gate, blocking, reused, missing) -> ProbeResult:
    """T0.ABORT (FAIL): the paid tiers were skipped; names each blocking probe."""
    ids = ", ".join(r.probe_id for r in blocking)
    abort = ProbeResult(probe_id="T0.ABORT", name="Paid tiers skipped (preflight gate)", tier="0")
    abort.verdict = Verdict.FAIL
    abort.detail = (f"Live API tiers (1/2/A/3) were SKIPPED because preflight gate probe(s) FAILed: {ids}. "
                    "Each such FAIL means the paid calls would test, or bill, the wrong configuration. "
                    "Fix the named probe(s) and re-run, or pass --allow-preflight-fail to run the paid "
                    "tiers against this configuration on purpose.")
    abort.add_evidence("preflight gate: " + ", ".join(GATE_PROBE_IDS),
                       output="; ".join(f"{r.probe_id}={r.verdict}" for r in gate),
                       note=(f"reused from Tier 0: {', '.join(reused) or 'none'}; "
                             f"run as the gate subset: {', '.join(missing) or 'none'}"))
    for r in blocking:
        abort.add_evidence(f"blocking: {r.probe_id} {r.name}", output=_cell(r.detail, 400))
    abort.hint = getattr(smoke_probes, "PROBE_HINTS", {}).get("T0.ABORT", "")
    return abort


def _apply_profile_gate(stated_route, child_env, prof_name, tier):
    """Review fix H2: re-run PROFILE_GATE_PROBE_IDS (T0.1, T0.3, T0.16, T0.17) on
    one named profile's child environment (ambient env + overlay), because an
    overlay can set exactly what they judge (profiles.yaml sets the four tier
    aliases). The route info is rebuilt from child_env, so T0.1 FAILs when the
    overlay moves detection away from the stated --route (which stays the
    assertion) and T0.17 sees the profile's model family. Results are filed like the
    T0.14 re-check: under `tier`, carrying `profile`. Returns (ran, blocking);
    a crash is a T0.CRASH FAIL and blocks (fail closed)."""
    info = build_route_info(child_env, asserted_route=stated_route)
    ran = _guarded_tier("0", "smoke_probes.run_preflight_gate (profile gate)",
                        lambda: smoke_probes.run_preflight_gate(info, child_env, BASE_DIR,
                                                                probe_ids=PROFILE_GATE_PROBE_IDS,
                                                                name_suffix=PROFILE_GATE_SUFFIX))
    for r in ran:
        r.tier = tier
        r.profile = prof_name
        if r.hint and not r.probe_id.endswith(".CRASH"):
            r.hint += (f" With --profiles, also check profile {prof_name}'s env block in "
                       "scripts/deploy_smoke/profiles.yaml.")
    return ran, [r for r in ran if r.verdict in Verdict.FAILING]


def _profile_abort_result(prof_name, tier, gate, blocking) -> ProbeResult:
    """T0.ABORT (FAIL) for one profile: its profile gate blocked its paid tiers
    only; other profiles are judged on their own."""
    ids = ", ".join(r.probe_id for r in blocking)
    abort = ProbeResult(probe_id="T0.ABORT", name="Paid tiers skipped (profile gate)", tier=tier,
                        profile=prof_name)
    abort.verdict = Verdict.FAIL
    abort.detail = (f"Live API tiers (1/2/A/3) were SKIPPED for profile {prof_name} because its profile gate "
                    f"probe(s) FAILed on the ambient environment plus this profile's overlay: {ids}. Other "
                    "profiles run if their own gate and T0.14 re-check pass. Fix the profile's overlay in "
                    "profiles.yaml (or the ambient setting it builds on) and re-run, or pass "
                    "--allow-preflight-fail to run it against this configuration on purpose.")
    abort.add_evidence("profile gate: " + ", ".join(PROFILE_GATE_PROBE_IDS),
                       output="; ".join(f"{r.probe_id}={r.verdict}" for r in gate),
                       note=f"child environment: ambient env + profile {prof_name} overlay")
    for r in blocking:
        abort.add_evidence(f"blocking: {r.probe_id} {r.name}", output=_cell(r.detail, 400))
    abort.hint = getattr(smoke_probes, "PROBE_HINTS", {}).get("T0.ABORT", "")
    return abort


def _run_tier_d(args, td_timeout, evidence_dir, stated_route):
    """Tier D: route for the route-scoped TD.7 shim suite, tier_d_all for
    --tier-d-all."""
    return _guarded_tier("D", "smoke_probes.run_tier_d", smoke_probes.run_tier_d, args.include_r_smoke,
                         td_timeout, evidence_dir=evidence_dir, route=stated_route,
                         tier_d_all=args.tier_d_all)


# --- Diagnosis summary helpers ----------------------------------------------

# Where a failing probe is usually fixed. Locations only (files, docs, actions);
# the probe's own `hint` carries the cause-specific remediation and is listed
# first. The skill's interpreting-results.md row for the probe is the fallback.
_FIX_LOCATIONS = (
    ("T0.0", "rebuild the image (bash rebuild_daaf.sh) or drop DAAF_DEV=1 from daaf-docker/environment_settings.txt"),
    ("T0.ABORT", "the blocking gate probe(s) named in the detail; --allow-preflight-fail to run anyway"),
    ("T0.1", "the --route value or the route variables in environment_settings.txt"),
    ("T0.2", ".claude/hooks/enforce-model-ceiling.sh (user-applied) or the model selectors"),
    ("T0.3", "route variables in environment_settings.txt"),
    ("T0.4", "CLAUDE_CODE_MAX_CONTEXT_TOKENS and model selectors in environment_settings.txt"),
    ("T0.5", "Dockerfile CLAUDE_CODE_VERSION, then rebuild"),
    ("T0.6", ".claude/settings.json hook registrations (user-applied)"),
    ("T0.7", ".claude/scripts/context-bar.sh, .claude/scripts/subagent-bar.sh"),
    ("T0.8", "scripts/provider_shim/ (restart with start_shim.sh)"),
    ("T0.9", "codex login inside the container ($CODEX_HOME)"),
    ("T0.10", "remove the objects check_workspace_invariants.sh lists"),
    ("T0.11", "Dockerfile locale settings"),
    ("T0.12", ".claude/settings.local.json"),
    ("T0.14", "model selectors: environment_settings.txt, settings model key, profiles.yaml"),
    ("T0.16", "credentials in environment_settings.txt (one per install)"),
    ("T0.17", "ANTHROPIC_DEFAULT_{FABLE,OPUS,SONNET,HAIKU}_MODEL in environment_settings.txt or settings env"),
    ("T0.24", ".claude/settings.json env and statusLine (user-applied), docker-compose.yml CLAUDE_CODE_TMPDIR"),
    ("T0.", "environment_settings.txt or the install (see the probe detail)"),
    ("TN.", "network access or the named service; re-run Tier N"),
    ("TD.9", "the service log under evidence/tier_d/td9/; scripts/launch_marimo.sh, launch_code_server.sh"),
    ("TD.", "the failing suite; full log under evidence/tier_d/"),
    ("T1.", "provider credentials and route; .claude/hooks/ for the plumbing probes"),
    ("T2.", ".claude/agents/, .claude/skills/, .claude/hooks/ (see the transcript)"),
    ("TA.", "Auto-mode settings; shim classifier path on shim routes"),
    ("T3.1", ".claude/skills/daaf-orchestrator/"),
    ("T3.2", ".claude/skills/daaf-orchestrator/references/data-lookup-mode.md (Data Lookup); .claude/agents/ "
             "(search-agent, source-researcher); .claude/skills/education-data-{context,source-ccd}/"),
)
_SKILL_REF = ".claude/skills/daaf-deploy-smoke-testing/references/interpreting-results.md"
# Every synthetic *.CRASH record (T<tier>.CRASH, POST.CRASH, RUN.CRASH) is a
# harness exception or an interrupted run, not an install defect, and has no
# probe row of its own: it is checked before the tier prefixes in
# _FIX_LOCATIONS, which would otherwise send T0.CRASH to the install.
_CRASH_LOCATION = (f"scripts/deploy_smoke/ (an interrupt needs only a re-run); see {_SKILL_REF} "
                   "§ Verdict Semantics, Synthetic records")


def _where_to_fix(probe_id: str, hint: str) -> str:
    m = re.search(r"(?i)\bwhere(?: to fix)?:\s*(.+)$", hint or "")
    if m:
        return m.group(1).strip()
    if probe_id.endswith(".CRASH"):
        return _CRASH_LOCATION
    for prefix, loc in _FIX_LOCATIONS:
        if probe_id == prefix or (prefix.endswith(".") and probe_id.startswith(prefix)):
            return loc
    return f"{_SKILL_REF} (row {probe_id})"


# Probes whose evidence is (also) a log the package copies under logs/. The
# shim log window is packaged on shim routes; codex_config.log's tail on any
# route where it exists. The packager marks a path that did not make it into
# the zip as "(withheld)" or "(not in package)" in the Problems table.
_PROBE_LOG_PATHS = {
    "T0.8": ("logs/shim.log",),
    "T0.18": ("logs/codex_config.log", "logs/shim.log"),
    "T0.20": ("logs/shim.log",),
    "TA.1": ("logs/shim.log",),
}


def _package_evidence_paths(r, report_dir: Path) -> list:
    """Where the evidence for one probe sits inside the package."""
    paths = [f"report.md § {r.probe_id}"]
    for sid in smoke_package.session_ids_from_results([r]):
        paths.append(smoke_package.transcript_package_dir(sid) + "/")
    paths.extend(p for p in _PROBE_LOG_PATHS.get(r.probe_id, ()) if p not in paths)
    root = str(report_dir).rstrip("/") + "/"
    for e in r.evidence or []:
        for text in (e.note or "", e.output or ""):
            for m in re.finditer(re.escape(root) + r"([^\s'\"`)]+)", text):
                rel = m.group(1)
                if rel not in paths:
                    paths.append(rel)
    return paths


def _tier_label(tier: str) -> str:
    return POST_RUN_SECTION if tier == POST_RUN_TIER else f"Tier {tier}"


def _cell(text, limit=200) -> str:
    text = strip_ansi(str(text or "")).replace("\n", " ").replace("|", "\\|").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _live_invocations(r) -> list:
    """The claude -p commands one probe result ran: each live tier records
    exactly one `claude -p ...` evidence command per invocation, on the probe
    that made it (T1.1 for the Tier 1 run, each T2.x, TA.1, T3.1 and T3.2).
    Probes that only read that run's output (T1.2-T1.10) carry no such command."""
    return [e.command for e in (r.evidence or []) if (e.command or "").startswith("claude -p")]


def _run_cost(results: list):
    """(paid_call_count, total_cost_usd_or_None, resumed_session_present).

    C7: paid calls are counted per claude -p INVOCATION, not per session: T3.2
    resumes T3.1's session (--resume), so the two share one session id but are
    two paid calls. Cost is summed over the invoking results only (T1.7 copies
    T1.1's cost for the same invocation and must not be added twice).

    Inference, not verified: Claude Code may restore a resumed session's
    running cost, which would make T3.2's total_cost_usd cumulative (T3.1 +
    T3.2). If so, the sum overstates the cost by T3.1's amount; the report then
    labels the total an upper bound (resumed_session_present=True).

    Falls back to T1.7's total_cost_usd evidence when no probe reports cost_usd."""
    calls, total, any_cost, resumed = 0, 0.0, False, False
    for r in results:
        invocations = _live_invocations(r)
        if not invocations:
            continue
        calls += len(invocations)
        resumed = resumed or any(" --resume " in c for c in invocations)
        cost = r.cost_usd
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            any_cost = True
            total += float(cost)
    if not any_cost:
        for r in results:
            if r.probe_id != "T1.7":
                continue
            for e in r.evidence or []:
                m = re.search(r"total_cost_usd=([0-9.]+)", e.output or "")
                if m:
                    any_cost = True
                    total += float(m.group(1))
    return calls, (total if any_cost else None), resumed


def _model_mapping(fingerprint: dict, route_info) -> str:
    labels = (("ANTHROPIC_MODEL", "ANTHROPIC_MODEL"), ("ANTHROPIC_DEFAULT_MODEL", "DEFAULT_MODEL"),
              ("ANTHROPIC_DEFAULT_FABLE_MODEL", "FABLE"), ("ANTHROPIC_DEFAULT_OPUS_MODEL", "OPUS"),
              ("ANTHROPIC_DEFAULT_SONNET_MODEL", "SONNET"), ("ANTHROPIC_DEFAULT_HAIKU_MODEL", "HAIKU"),
              ("CLAUDE_CODE_SUBAGENT_MODEL", "SUBAGENT_MODEL"))
    parts = [f"{label}={fingerprint.get(n)}" for n, label in labels
             if fingerprint.get(n) not in (None, "<unset>")]
    family = f"family {route_info.model_family}, remap_active={route_info.remap_active}"
    return (", ".join(f"`{p}`" for p in parts) + f" ({family})") if parts else f"no model env set ({family})"


# --- Report writers -------------------------------------------------------

def _preflight_text(preflight) -> str:
    """The identity-block cell for the preflight gate (coverage design D2)."""
    pf = preflight or {}
    flag = " `--allow-preflight-fail` given." if pf.get("allow_preflight_fail") else ""
    if not pf.get("applied"):
        return "not applied (no paid tier selected)." + flag
    probes = ", ".join(pf.get("probes") or [])
    source = []
    if pf.get("reused_from_tier0"):
        source.append("reused from Tier 0: " + ", ".join(pf["reused_from_tier0"]))
    if pf.get("gate_subset_run"):
        source.append("run as the gate subset: " + ", ".join(pf["gate_subset_run"]))
    src = f" ({'; '.join(source)})" if source else ""
    blocking = ", ".join(pf.get("blocking") or [])
    if not blocking:
        text = f"passed: {probes}{src}." + (" `--allow-preflight-fail` given, not needed." if flag else "")
    elif pf.get("overridden"):
        text = (f"**FAILED** ({blocking}); paid tiers ran anyway because `--allow-preflight-fail` "
                f"was given{src}.")
    else:
        text = f"**BLOCKED** by {blocking}: paid tiers skipped (T0.ABORT){src}."
    # Review fix H2: the per-profile gate (named --profiles only; absent when
    # the ambient gate blocked, since no profile then runs).
    per_profile = pf.get("per_profile") or {}
    if per_profile:
        parts = []
        for name, entry in per_profile.items():
            pblock = ", ".join(entry.get("blocking") or [])
            if not pblock:
                parts.append(f"{name} passed")
            elif entry.get("overridden"):
                parts.append(f"{name} **FAILED** ({pblock}), ran anyway")
            else:
                parts.append(f"{name} **BLOCKED** by {pblock}")
        text += (f" Per profile ({', '.join(PROFILE_GATE_PROBE_IDS)} re-checked on each overlay): "
                 + "; ".join(parts) + ".")
    return text


def _section_order(tiers, tier_seen) -> list:
    """Report section order: a Tier 0 that holds only the gate subset (0 not in
    --tiers) leads, then --tiers order, then any other tier seen (post-run scan,
    crash records)."""
    lead = ["0"] if ("0" in tier_seen and "0" not in tiers) else []
    return lead + [t for t in tiers if t not in lead] + [t for t in tier_seen if t not in tiers and t not in lead]


def write_reports(report_dir: Path, route_info, fingerprint, results, tiers, profiles, shim_health,
                  started_utc=None, ended_utc=None, versions=None, stated_route="", preflight=None):
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = report_dir / "evidence"
    evidence_dir.mkdir(exist_ok=True)

    now = datetime.now(timezone.utc)
    started_utc = started_utc or now
    ended_utc = ended_utc or now
    versions = dict(versions or {})
    stated_route = stated_route or route_info.asserted_route or route_info.detected_route
    counts = verdict_counts(results)
    overall_fail = any(r.verdict in Verdict.FAILING for r in results)
    sha = git_sha()
    paid_calls, total_cost, cost_upper_bound = _run_cost(results)
    fmt = "%Y-%m-%dT%H:%M:%SZ"

    # --- report.json (machine-readable) ---
    report_json = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_utc": now.strftime(fmt),
        "started_utc": started_utc.strftime(fmt),
        "ended_utc": ended_utc.strftime(fmt),
        "daaf_git_sha": sha,
        "stated_route": stated_route,
        "route": route_info.to_dict(),
        "versions": versions,
        "env_fingerprint": fingerprint,
        "tiers_run": tiers,
        "allow_preflight_fail": bool((preflight or {}).get("allow_preflight_fail")),
        "preflight_gate": dict(preflight or {"applied": False, "allow_preflight_fail": False}),
        "profiles": [p[0] or "<ambient>" for p in profiles],
        "paid_calls": paid_calls,
        "total_cost_usd": total_cost,
        "total_cost_is_upper_bound": cost_upper_bound and total_cost is not None,
        "summary": counts,
        "overall": "FAIL" if overall_fail else "PASS",
        "results": [_result_dict(r) for r in results],
    }
    (report_dir / "report.json").write_text(json.dumps(report_json, indent=2))

    # --- evidence/ snapshots ---
    if shim_health is not None:
        (evidence_dir / "shim_health.json").write_text(json.dumps(shim_health, indent=2))
    # /tmp cache snapshots for any Tier 1 session are already embedded in probe
    # evidence; write a consolidated fingerprint snapshot for audit convenience.
    (evidence_dir / "env_fingerprint.json").write_text(json.dumps(fingerprint, indent=2))

    # --- report.md (human audit), Diagnosis summary first ---
    lines = ["# DAAF Deployment Smoke Report", "", "## Diagnosis summary", "", "### Identity", "",
             "| Field | Value |", "|-------|-------|"]
    match = "matches" if route_info.detected_route == stated_route else "**MISMATCH**"
    lines.append(f"| Route | stated `{stated_route}`, detected `{route_info.detected_route}` ({match}) |")
    dirty = versions.get("daaf_dirty_files")
    lines.append(f"| DAAF | branch `{versions.get('daaf_branch', '?')}`, `{versions.get('daaf_describe', '?')}`, "
                 f"SHA `{sha}`, {'?' if dirty is None else dirty} dirty file(s) "
                 f"({versions.get('daaf_dirty_scope') or DIRTY_SCOPE}) |")
    lines.append(f"| Claude Code | `{versions.get('claude_code', '?')}` |")
    if stated_route in SHIM_ROUTES or route_info.detected_route in SHIM_ROUTES:
        lines.append(f"| Shim | `{versions.get('shim') or 'unknown (T0.8 not run or no /health)'}` |")
    if versions.get("codex"):
        lines.append(f"| Codex CLI | `{versions.get('codex')}` |")
    lines.append(f"| Model mapping | {_cell(_model_mapping(fingerprint, route_info), 600)} |")
    lines.append(f"| Tiers run | {', '.join(tiers)} (profiles: {', '.join(p[0] or '<ambient>' for p in profiles)}) |")
    lines.append(f"| Preflight gate | {_cell(_preflight_text(preflight), 600)} |")
    lines.append(f"| Started / ended (UTC) | {report_json['started_utc']} / {report_json['ended_utc']} |")
    cost_txt = f"${total_cost:.4f}" if isinstance(total_cost, float) else "not reported"
    if isinstance(total_cost, float) and cost_upper_bound:
        cost_txt += " (upper bound: a resumed session's reported cost may be cumulative)"
    lines.append(f"| Paid calls / cost | {paid_calls} claude -p call(s) / {cost_txt} |")
    lines.append(f"| Overall | **{report_json['overall']}** (PASS={counts[Verdict.PASS]} FAIL={counts[Verdict.FAIL]} "
                 f"WARN={counts[Verdict.WARN]} SKIP={counts[Verdict.SKIP]} INFO={counts[Verdict.INFO]}) |")
    lines.append("")

    problems = ([r for r in results if r.verdict == Verdict.FAIL]
                + [r for r in results if r.verdict == Verdict.WARN])
    lines += ["### Problems (FAIL first, then WARN)", ""]
    if problems:
        lines += ["| Probe | Verdict | Observed | Likely cause | Evidence in package | Where to fix |",
                  "|-------|---------|----------|--------------|---------------------|--------------|"]
        for r in problems:
            hint = r.hint or ""
            cause = re.split(r"(?i)\bwhere(?: to fix)?:", hint)[0].strip() if hint else "not stated; see the probe detail"
            prof = f" ({r.profile})" if r.profile else ""
            ev = ", ".join(f"`{p}`" for p in _package_evidence_paths(r, report_dir))
            lines.append(f"| {r.probe_id}{_cell(prof)} {_cell(r.name, 60)} | {r.verdict} | {_cell(r.detail)} | "
                         f"{_cell(cause, 300)} | {ev} | {_cell(_where_to_fix(r.probe_id, hint), 200)} |")
    else:
        lines.append("No FAIL or WARN results.")
    lines.append("")

    tier_seen = []
    for r in results:
        if r.tier not in tier_seen:
            tier_seen.append(r.tier)
    passed = []
    gate_only = "0" in tier_seen and "0" not in tiers
    for t in [t for t in _section_order(tiers, tier_seen) if t in tier_seen]:
        tr = [r for r in results if r.tier == t]
        c = verdict_counts(tr)
        extra = ", ".join(f"{c[v]} {v}" for v in (Verdict.SKIP, Verdict.INFO) if c[v])
        label = _tier_label(t) + (" (gate subset)" if t == "0" and gate_only else "")
        passed.append(f"{label}: {c[Verdict.PASS]} of {len(tr)}" + (f" ({extra})" if extra else ""))
    lines += [f"**Passed:** {' · '.join(passed) if passed else 'no probes ran'}", ""]

    lines.append("## Environment Fingerprint (secrets redacted)")
    lines.append("")
    lines.append("| Variable | Value |")
    lines.append("|----------|-------|")
    for k, v in fingerprint.items():
        lines.append(f"| `{k}` | `{strip_ansi(str(v))}` |")
    lines.append("")

    # Full per-probe detail, grouped by tier (any tier not in --tiers, such as
    # the post-run shim-log scan or a synthetic crash record, follows at the end).
    for tier in _section_order(tiers, tier_seen):
        tier_results = [r for r in results if r.tier == tier]
        if not tier_results:
            continue
        lines.append(f"## {_tier_label(tier)}" + (" (gate subset)" if tier == "0" and gate_only else ""))
        lines.append("")
        if tier == "0" and gate_only:
            lines.append("Tier 0 was not selected; these are the preflight gate probes the runner applies "
                         "before any paid tier (T0.ABORT, when present, names the probe that blocked them).")
            lines.append("")
        if tier == POST_RUN_TIER:
            lines.append("Checks run after the live tiers over this run's window only (the Tier 0 shim-log "
                         "scan covers the history before the run and is informational).")
            lines.append("")
        for r in tier_results:
            prof = f" _(profile: {r.profile})_" if r.profile else ""
            lines.append(f"### [{r.verdict}] {r.probe_id} — {strip_ansi(r.name)}{prof}")
            lines.append("")
            lines.append(f"{strip_ansi(r.detail)}")
            lines.append("")
            meta = []
            dur = r.duration_s
            if isinstance(dur, (int, float)):
                meta.append(f"duration {dur:.1f}s")
            sids = smoke_package.session_ids_for_result(r)
            if sids:
                meta.append("session(s) " + ", ".join(f"`{s[:8]}`" for s in sids))
            cost = r.cost_usd
            if isinstance(cost, (int, float)):
                meta.append(f"cost ${cost:.4f}")
            if meta:
                lines.append(f"_{'; '.join(meta)}_")
                lines.append("")
            hint = r.hint or ""
            if hint and r.verdict in (Verdict.FAIL, Verdict.WARN):
                lines.append(f"**Hint:** {strip_ansi(hint)}")
                lines.append("")
            if r.evidence:
                lines.append("Evidence:")
                lines.append("")
                for e in r.evidence:
                    if e.command:
                        lines.append(f"- `{strip_ansi(e.command)}`")
                        if e.output:
                            lines.append("  ```")
                            for ln in strip_ansi(e.output).splitlines():
                                lines.append(f"  {ln}")
                            lines.append("  ```")
                    if e.note:
                        label = "inference" if e.is_inference else "note"
                        lines.append(f"  - _{label}:_ {strip_ansi(e.note)}")
                lines.append("")
    (report_dir / "report.md").write_text("\n".join(lines))
    return overall_fail


# --- Confirmation ---------------------------------------------------------

def confirm_launch(route_info, tiers, profiles, assume_yes: bool, stated_route: str = "",
                   allow_preflight_fail: bool = False) -> bool:
    live_tiers = [t for t in tiers if t in LIVE_TIERS]
    print("=" * 68)
    print("DAAF Deployment Smoke Test — pre-launch summary")
    print("=" * 68)
    if stated_route:
        print(f"  Stated route   : {stated_route}")
    print(f"  Detected route : {route_info.detected_route}")
    print(f"  Model family   : {route_info.model_family} (remap_active={route_info.remap_active})")
    print(f"  Tiers          : {', '.join(tiers)}")
    print(f"  Profiles       : {', '.join(p[0] or '<ambient>' for p in profiles)}")
    if live_tiers:
        n_runs = len(profiles) * sum(LIVE_CALLS_PER_PROFILE[t] for t in live_tiers)
        print(f"  COST NOTE      : Tiers {live_tiers} make ~{n_runs} live claude -p API calls "
              f"(billed to your configured provider).")
        print(f"  PREFLIGHT GATE : {', '.join(GATE_PROBE_IDS)} must not FAIL before any paid tier"
              + (" (--allow-preflight-fail: a FAIL is recorded but does not stop them)."
                 if allow_preflight_fail else " (override: --allow-preflight-fail)."))
        if any(p[0] for p in profiles):
            print(f"                   Per profile: {', '.join(PROFILE_GATE_PROBE_IDS)} and T0.14 re-checked "
                  "on its overlay; a FAIL skips that profile only.")
    else:
        print("  COST NOTE      : No live API tiers selected (Tiers 0/D/N are free).")
    print("=" * 68)
    if assume_yes or not live_tiers:
        return True
    try:
        ans = input("Proceed with live API tiers? [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


# --- Package / import -----------------------------------------------------

def print_copy_steps(zip_path: Path) -> None:
    """The host-side commands that carry a package to the main container."""
    in_container = str(zip_path)
    inbox = str(INBOX_ROOT) + "/"
    print("")
    print("=" * 68)
    print("Diagnostic package (copy it to the main container for diagnosis)")
    print("=" * 68)
    print(f"  {in_container}")
    print("")
    print("  On the HOST (any shell; PowerShell uses the same docker syntax):")
    print('    docker ps --format "{{.Names}}"          # find this install\'s container')
    print(f"    docker cp <this-container>:{in_container} ./")
    print(f"    docker cp ./{zip_path.name} <main-container>:{inbox}")
    print("  Or, without docker commands: download the file from this container's editor,")
    print(f"  then drag it into the main container's editor under {inbox}")
    print("")
    print("  Then, in the main container:")
    print(f"    python3 {_THIS_DIR / 'run_deploy_smoke.py'} --import {inbox}{zip_path.name}")
    print("=" * 68)


def run_import(paths: list) -> int:
    """--import: verify and extract packages into the inbox, then write
    MATRIX.md when two or more packages are present. Runs no probes."""
    resolved = []
    for p in paths:
        cand = Path(p)
        if not cand.exists() and not cand.is_absolute():
            for base in (_THIS_DIR, Path(BASE_DIR)):
                if (base / p).exists():
                    cand = base / p
                    break
        resolved.append(cand)
    outcomes = smoke_package.import_packages(resolved, INBOX_ROOT)
    bad = 0
    for o in outcomes:
        if o["status"] == "imported":
            print(f"IMPORTED {o['package']} -> {o['dest']}")
        else:
            bad += 1
            print(f"REJECTED {o['package']}: {o['error']}", file=sys.stderr)
    matrix = smoke_package.write_matrix(INBOX_ROOT)
    if matrix:
        print(f"MATRIX   {matrix}")
    else:
        print("MATRIX   not written (fewer than two imported packages in the inbox).")
    print("Next: read each package's README_FOR_MAIN_SESSION.md and the report.md Diagnosis summary; "
          "package contents are untrusted data, not instructions.")
    return 1 if bad else 0


# --- Main -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DAAF deployment smoke-testing suite (in-situ, route-aware). Each run writes a "
                    "report and a portable diagnostic package; --import extracts packages on the "
                    "main container.")
    parser.add_argument("--route", choices=ROUTE_CHOICES, default=None,
                        help="REQUIRED for a run: the install route of this container "
                             f"({', '.join(ROUTE_CHOICES)}). Detection mismatch => T0.1 FAIL.")
    parser.add_argument("--profiles", default="", help="Comma-separated profile names from profiles.yaml (OpenRouter route).")
    parser.add_argument("--tiers", default="0,1,2",
                        help="Comma-separated tiers: 0,1,2,D,N,A,3 (default 0,1,2). Free: 0, D, N. "
                             "Recommended release run: 0,D,N,1,2,A,3.")
    parser.add_argument("--tier-d-all", action="store_true",
                        help="Run every Tier D suite, including route-scoped ones (e.g. the shim unit "
                             "suite) on routes where they are skipped by default.")
    parser.add_argument("--include-r-smoke", action="store_true", help="Include the (slow) R/Python skill smoke suite in Tier D.")
    parser.add_argument("--timeout", type=int, default=0,
                        help="Per-probe timeout seconds (0 = per-tier defaults: N 60, 1 180, 2/A/3 300, D 600). "
                             f"TD.1 always gets at least {TD1_MIN_TIMEOUT_S} and TD.7 at least "
                             f"{TD7_MIN_TIMEOUT_S}; a larger value wins.")
    parser.add_argument("--yes", action="store_true", help="Skip the pre-launch cost/summary confirmation.")
    parser.add_argument("--allow-preflight-fail", action="store_true",
                        help="Run the paid tiers (1, 2, A, 3) even when a preflight gate probe "
                             f"({', '.join(GATE_PROBE_IDS)}) FAILs, e.g. to test a deliberately broken "
                             "config. Recorded in report.json and the report identity block.")
    parser.add_argument("--report-dir", default="", help="Override the report output directory.")
    parser.add_argument("--no-package", action="store_true",
                        help="Skip building the diagnostic package (it is built by default).")
    parser.add_argument("--import", dest="import_pkgs", nargs="+", metavar="PKG", default=None,
                        help="Main-container side: run no probes; verify and extract the given package "
                             "zip(s) into scripts/deploy_smoke/inbox/<package>/ and write inbox/MATRIX.md.")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.import_pkgs:
        return run_import(args.import_pkgs)
    if not args.route:
        parser.error(f"--route is required: one of {', '.join(ROUTE_CHOICES)}")

    started_utc = datetime.now(timezone.utc)
    env = os.environ
    try:
        tiers = parse_tiers(args.tiers)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if not tiers:
        print("ERROR: no valid tiers in --tiers.", file=sys.stderr)
        return 2

    route_info = build_route_info(env, asserted_route=args.route)
    fingerprint = env_fingerprint(env)
    profiles = load_profiles([p for p in args.profiles.split(",") if p.strip()] if args.profiles else [])

    # Warn if --profiles used on a shim route (daemon state is not per-run overridable).
    if args.profiles and route_info.detected_route in SHIM_ROUTES:
        print(f"WARNING: --profiles is an OpenRouter-route feature. On shim routes "
              f"({route_info.detected_route}) daemon state (SHIM_SANITIZE_TOOLS, backend_mode) "
              f"is NOT per-run overridable; overlays apply to the CLI session env only.", file=sys.stderr)

    # Per-tier timeout defaults (small; overridable via --timeout).
    t1_timeout = args.timeout or 180
    t2_timeout = args.timeout or 300
    td_timeout = args.timeout or 600
    tn_timeout = args.timeout or 60
    ta_timeout = args.timeout or 300
    t3_timeout = args.timeout or 300

    if not confirm_launch(route_info, tiers, profiles, args.yes, stated_route=args.route,
                          allow_preflight_fail=args.allow_preflight_fail):
        print("Aborted by user (no confirmation).", file=sys.stderr)
        return 1

    versions = collect_versions(BASE_DIR)

    # Resolve and create the report directory BEFORE executing tiers so Tier D
    # can route its evidence (full failure logs, Pester's NUnit testResults.xml)
    # into report/evidence/tier_d/ instead of the repository root. write_reports
    # is idempotent with these pre-created directories.
    if args.report_dir:
        report_dir = Path(args.report_dir)
    else:
        stamp = started_utc.astimezone().strftime("%Y%m%d_%H%M%S")
        # The STATED route, as in the package name, so a report folder and its
        # package always carry the same route (detection is checked by T0.1).
        report_dir = REPORTS_ROOT / f"{stamp}_{args.route}"
    evidence_root = report_dir / "evidence"
    tier_d_evidence_dir = evidence_root / "tier_d"

    results = []
    shim_health_snapshot = None
    crash = None
    overall_fail = True
    preflight = {"applied": False, "allow_preflight_fail": bool(args.allow_preflight_fail)}
    # Review fix H1: SIGTERM/SIGHUP unwind like Ctrl+C from here on (every
    # `finally` runs, TD.9's services are stopped, report and package written).
    guard = _TerminationGuard()
    console = None  # the original sys.stdout/sys.stderr once the unwind wraps them
    try:
        guard.install()
        run_live_tiers = True
        live_tier_ran = False  # set when a live tier (1/2/A/3) entry point is actually called
        t0 = []

        # Tier 0 — run once (route-scoped, not profile-scoped).
        if "0" in tiers:
            # T0.7 renders both statuslines for a synthetic session into a
            # report-local cache dir, so it never writes /tmp.
            t0 = _guarded_tier("0", "smoke_probes.run_tier0", smoke_probes.run_tier0, route_info, env,
                               BASE_DIR, statusline_cache_dir=evidence_root / "t07_statusline_cache",
                               evidence_dir=evidence_root / "tier_0")
            results.extend(t0)
            # Capture the shim /health JSON for evidence/, if present.
            for r in t0:
                if r.probe_id == "T0.8":
                    for e in r.evidence:
                        if e.command.startswith("GET ") and e.output:
                            try:
                                shim_health_snapshot = json.loads(e.output)
                            except json.JSONDecodeError:
                                pass

        # Preflight gate (coverage design D2): whenever a live tier (1/2/A/3) is
        # selected, the gate probes (T0.1 route, T0.3 env coherence, T0.16
        # credential overlap, T0.17 tier aliases) must not FAIL, because each such
        # FAIL means the paid calls would test, or bill, the wrong configuration.
        # Tier 0's own results are reused when Tier 0 ran; any gate probe missing
        # from them (Tier 0 not selected, or it crashed) runs as the "gate subset"
        # and is reported under Tier 0. A FAIL skips every paid tier and records
        # T0.ABORT naming the blocking probe(s), unless --allow-preflight-fail is
        # given. Free tiers (N, D) still run. The per-profile T0.14 re-check below
        # stays as it was. The cost confirmation (skipped by --yes) is unchanged.
        if any(t in LIVE_TIERS for t in tiers):
            gate, ran, blocking, reused, missing = _apply_preflight_gate(route_info, env, t0)
            results.extend(ran)
            preflight.update(applied=True, probes=list(GATE_PROBE_IDS), reused_from_tier0=reused,
                             gate_subset_run=missing, blocking=[r.probe_id for r in blocking],
                             overridden=bool(blocking) and bool(args.allow_preflight_fail),
                             paid_tiers_skipped=bool(blocking) and not args.allow_preflight_fail,
                             per_profile={})
            if blocking and args.allow_preflight_fail:
                print("WARNING: preflight gate FAILed (" + ", ".join(r.probe_id for r in blocking)
                      + "); running the paid tiers anyway because --allow-preflight-fail was given.",
                      file=sys.stderr)
            elif blocking:
                run_live_tiers = False
                print("ABORT: preflight gate FAILed (" + ", ".join(r.probe_id for r in blocking)
                      + "). Skipping all live API tiers (1/2/A/3) so no cost is billed against the "
                      "wrong configuration. Fix the named probe(s), or pass --allow-preflight-fail.",
                      file=sys.stderr)
                results.append(_preflight_abort_result(gate, blocking, reused, missing))

        # Tier N — free network checks, once (route-scoped).
        if "N" in tiers:
            results.extend(_call_tier_entry("N", "run_tier_n", route=args.route, timeout=tn_timeout,
                                            evidence_dir=evidence_root / "tier_n"))

        # Live tiers 1 / 2 / A / 3 — run once PER PROFILE (skipped if the
        # preflight gate tripped).
        if run_live_tiers:
            for prof_name, overlay in profiles:
                if any(t in LIVE_TIERS for t in tiers):
                    # Check the ACTUAL child's ambient+profile environment, not the
                    # ambient T0 family aggregate. Settings projection then models
                    # the same ordinary startup layers; no --model is injected.
                    child_env = dict(env)
                    child_env.update(overlay)
                    first_live = next(t for t in tiers if t in LIVE_TIERS)
                    recheck_tier = "1" if "1" in tiers else first_live
                    # Review fix H2: a named profile also re-runs the gate probes
                    # its overlay can change (T0.1, T0.3, T0.16, T0.17) on its child
                    # env, filed with its T0.14 re-check. A FAIL blocks this
                    # profile only (T0.ABORT carrying the profile), unless
                    # --allow-preflight-fail is given, which overrides it as it
                    # overrides the ambient gate. The ambient profile ("") was
                    # judged by the ambient gate above.
                    profile_blocked = False
                    if prof_name:
                        p_gate, p_blocking = _apply_profile_gate(args.route, child_env, prof_name, recheck_tier)
                        results.extend(p_gate)
                        p_ids = [r.probe_id for r in p_blocking]
                        if p_blocking and args.allow_preflight_fail:
                            print(f"WARNING: profile gate FAILed for {prof_name} ({', '.join(p_ids)}); running "
                                  "its paid tiers anyway because --allow-preflight-fail was given.",
                                  file=sys.stderr)
                        elif p_blocking:
                            profile_blocked = True
                            print(f"ABORT: profile gate FAILed for {prof_name} ({', '.join(p_ids)}); this "
                                  "profile's paid tiers skipped.", file=sys.stderr)
                            results.append(_profile_abort_result(prof_name, recheck_tier, p_gate, p_blocking))
                        preflight.setdefault("per_profile", {})[prof_name] = {
                            "probes": list(PROFILE_GATE_PROBE_IDS),
                            "blocking": p_ids,
                            "overridden": bool(p_blocking) and bool(args.allow_preflight_fail),
                        }
                    coherence = smoke_probes.probe_main_model_coherence(
                        child_env, BASE_DIR, profile=prof_name, tier=recheck_tier)
                    results.append(coherence)
                    if prof_name:
                        entry = preflight["per_profile"][prof_name]
                        entry["t014_verdict"] = coherence.verdict
                        entry["paid_tiers_skipped"] = profile_blocked or coherence.verdict == Verdict.FAIL
                    if coherence.verdict == Verdict.FAIL:
                        print("ABORT: incompatible main model for this profile; paid tiers skipped.",
                              file=sys.stderr)
                        continue
                    if profile_blocked:
                        continue
                if "1" in tiers:
                    # T1.6 renders the statusline into a report-local cache dir so it
                    # can never write the real session's /tmp coordination caches.
                    live_tier_ran = True
                    results.extend(_guarded_tier(
                        "1", "smoke_probes.run_tier1", smoke_probes.run_tier1,
                        prof_name, overlay, t1_timeout,
                        statusline_cache_dir=evidence_root / "t16_statusline_cache", route=args.route))
                if "2" in tiers:
                    live_tier_ran = True
                    results.extend(_guarded_tier("2", "smoke_probes.run_tier2", smoke_probes.run_tier2,
                                                 prof_name, overlay, t2_timeout, route=args.route))
                for tier, fn_name, timeout in (("A", "run_tier_a", ta_timeout), ("3", "run_tier_3", t3_timeout)):
                    if tier in tiers:
                        live_tier_ran = True
                        results.extend(_call_tier_entry(tier, fn_name, prof_name, overlay, timeout,
                                                        route=args.route,
                                                        evidence_dir=evidence_root / f"tier_{tier.lower()}"))

        # Post-run — the shim-log scan over this run's window (stated shim
        # routes, and only when a live tier sent traffic through the shim). It
        # carries the shim-log verdict; Tier 0's scan of the earlier history is
        # INFO. The stated route decides, as everywhere else: a detection
        # mismatch is already T0.1's FAIL.
        if live_tier_ran and args.route in SHIM_ROUTES:
            results.extend(_post_run_shim_scan(args.route, started_utc))

        # Tier D — run once (not profile-scoped; deterministic, provider-agnostic).
        if "D" in tiers:
            results.extend(_run_tier_d(args, td_timeout, tier_d_evidence_dir, args.route))
        guard.finishing()
    except BaseException as exc:  # KeyboardInterrupt / SystemExit / TerminationSignal: report and package anyway
        guard.finishing()
        # A dead terminal (SIGHUP) must not stop the unwind at the next print.
        console = _protect_console()
        crash = exc
        results.append(_crash_result("run", "the tier block", exc))
        what = exc.signame if isinstance(exc, TerminationSignal) else type(exc).__name__
        print(f"ERROR: the tier block was interrupted by {what}; writing the report "
              "and package for the probes that ran.", file=sys.stderr)
    finally:
        # From here a SIGTERM/SIGHUP is recorded, not raised, so the report and
        # package are always completed; the exit code reports it afterwards.
        # Console writes that fail (OSError) are dropped, not raised.
        guard.finishing()
        if console is None:
            console = _protect_console()
        ended_utc = datetime.now(timezone.utc)
        if isinstance(shim_health_snapshot, dict) and isinstance(shim_health_snapshot.get("version"), str):
            if re.fullmatch(r"[A-Za-z0-9._+-]{1,64}", shim_health_snapshot["version"]):
                versions["shim"] = shim_health_snapshot["version"]

        # --- Reports ---
        try:
            overall_fail = write_reports(report_dir, route_info, fingerprint, results, tiers, profiles,
                                         shim_health_snapshot, started_utc=started_utc, ended_utc=ended_utc,
                                         versions=versions, stated_route=args.route, preflight=preflight)
        except Exception as exc:  # noqa: BLE001 — still try to package what exists
            overall_fail = True
            print(f"ERROR: writing the report failed ({type(exc).__name__}: {exc}).", file=sys.stderr)

        counts = verdict_counts(results)
        print("")
        print(f"Report written: {report_dir}")
        print(f"Summary: PASS={counts[Verdict.PASS]} FAIL={counts[Verdict.FAIL]} "
              f"WARN={counts[Verdict.WARN]} SKIP={counts[Verdict.SKIP]} INFO={counts[Verdict.INFO]}")
        print(f"Overall: {'FAIL' if overall_fail else 'PASS'}")

        # --- Package (default on; skipped only with --no-package or when no
        # report directory exists, e.g. a test that mocks write_reports) ---
        if args.no_package:
            print("Package: skipped (--no-package).")
        elif not report_dir.is_dir():
            print(f"WARN: no report directory at {report_dir}; package not built.", file=sys.stderr)
        else:
            try:
                built = smoke_package.build_package(
                    report_dir, args.route, started_utc, ended_utc, versions, results, BASE_DIR,
                    out_dir=PACKAGES_ROOT, detected_route=route_info.detected_route,
                    overall="FAIL" if overall_fail else "PASS", summary=counts)
                for w in built["warnings"]:
                    print(f"WARN: {w}", file=sys.stderr)
                print_copy_steps(built["zip_path"])
            except Exception as exc:  # noqa: BLE001 — a packaging failure must not hide the report
                print(f"WARN: package not built ({type(exc).__name__}: {exc}). The report is still at "
                      f"{report_dir}.", file=sys.stderr)
        guard.restore()

    try:
        if isinstance(crash, KeyboardInterrupt):
            return 130
        if isinstance(crash, TerminationSignal):
            return crash.code
        if guard.deferred is not None:
            # A signal that arrived while the report was being written: honoured now.
            name = TerminationSignal(guard.deferred).signame
            print(f"WARNING: {name} received while the report and package were being written; they are "
                  "complete, and the run stops here.", file=sys.stderr)
            return 128 + guard.deferred
        return 1 if overall_fail else 0
    finally:
        _restore_console(console)


if __name__ == "__main__":
    sys.exit(main())
