#!/usr/bin/env python3
"""DAAF deployment smoke-testing suite — CLI entry point.

Verifies that a LIVE DAAF installation, configured exactly as the user set it up,
is functioning end-to-end. This is deployment/configuration verification — NOT
framework-adherence evaluation (that is DAAFBench) and NOT the R-package smoke
tests under scripts/smoke_tests/.

The suite runs IN SITU inside a real installation, auto-detects the active route
from the live environment, and runs route-appropriate probes across tiers:

  Tier 0  preflight, no LLM      route detection + env coherence + hooks/statusline/shim/invariants + R locale
  Tier 1  one live round-trip    one claude -p call + the plumbing evidence around it
  Tier 2  functional battery     six capability-structural probes (dispatch, coding, web, skill, isolation, nested-dispatch deny)
  Tier D  deterministic battery  bats / Pester / lint / hook tests (opt-in, zero API cost)

Reports land under scripts/deploy_smoke/reports/{YYYYMMDD_HHMMSS}_{route}/ with a
human report.md (per-probe verdict + quoted evidence), a machine report.json
(git SHA, route, family, redacted env fingerprint, per-probe results), and an
evidence/ dir (shim health, /tmp cache snapshots). Overall exit is nonzero on any
FAIL, matching the run_all_smoke_tests.sh contract.

Framework tooling: standalone-CLI-tool exception to the no-functions rule — this
uses normal engineering style with functions, matching benchmarks/harness/.

Usage:
  python3 scripts/deploy_smoke/run_deploy_smoke.py --tiers 0 --yes
  python3 scripts/deploy_smoke/run_deploy_smoke.py --route openrouter --profiles openrouter-claude,openrouter-gpt
  python3 scripts/deploy_smoke/run_deploy_smoke.py --tiers 0,1,2,D --include-r-smoke
"""

import argparse
import json
import os
import subprocess
import sys
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

from route_detection import (  # noqa: E402
    Verdict,
    ProbeResult,
    ROUTE_OPENROUTER,
    SHIM_ROUTES,
    build_route_info,
    env_fingerprint,
)
import smoke_probes  # noqa: E402


BASE_DIR = "/daaf"
REPORTS_ROOT = _THIS_DIR / "reports"
PROFILES_PATH = _THIS_DIR / "profiles.yaml"


# --- Helpers --------------------------------------------------------------

def git_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", BASE_DIR, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "<unknown>"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "<unknown>"


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
    """Parse --tiers like '0,1,2' or '0,1,2,D' into an ordered unique list."""
    valid = {"0", "1", "2", "D"}
    tiers = []
    for t in spec.split(","):
        t = t.strip().upper() if t.strip().upper() == "D" else t.strip()
        if t and t in valid and t not in tiers:
            tiers.append(t)
    return tiers


def verdict_counts(results: list) -> dict:
    counts = {Verdict.PASS: 0, Verdict.FAIL: 0, Verdict.SKIP: 0, Verdict.WARN: 0, Verdict.INFO: 0}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1
    return counts


# --- Report writers -------------------------------------------------------

def write_reports(report_dir: Path, route_info, fingerprint, results, tiers, profiles, shim_health):
    report_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = report_dir / "evidence"
    evidence_dir.mkdir(exist_ok=True)

    counts = verdict_counts(results)
    overall_fail = any(r.verdict in Verdict.FAILING for r in results)

    # --- report.json (machine-readable) ---
    report_json = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "daaf_git_sha": git_sha(),
        "route": route_info.to_dict(),
        "env_fingerprint": fingerprint,
        "tiers_run": tiers,
        "profiles": [p[0] or "<ambient>" for p in profiles],
        "summary": counts,
        "overall": "FAIL" if overall_fail else "PASS",
        "results": [r.to_dict() for r in results],
    }
    (report_dir / "report.json").write_text(json.dumps(report_json, indent=2))

    # --- evidence/ snapshots ---
    if shim_health is not None:
        (evidence_dir / "shim_health.json").write_text(json.dumps(shim_health, indent=2))
    # /tmp cache snapshots for any Tier 1 session are already embedded in probe
    # evidence; write a consolidated fingerprint snapshot for audit convenience.
    (evidence_dir / "env_fingerprint.json").write_text(json.dumps(fingerprint, indent=2))

    # --- report.md (human audit) ---
    lines = []
    lines.append(f"# DAAF Deployment Smoke Report")
    lines.append("")
    lines.append(f"- **Generated:** {report_json['generated_utc']}")
    lines.append(f"- **DAAF git SHA:** `{report_json['daaf_git_sha']}`")
    lines.append(f"- **Detected route:** `{route_info.detected_route}`"
                 + (f" (asserted `{route_info.asserted_route}`, match={route_info.route_match})"
                    if route_info.asserted_route else ""))
    lines.append(f"- **Model family:** `{route_info.model_family}` (remap_active={route_info.remap_active})")
    lines.append(f"- **Tiers run:** {', '.join(tiers)}")
    lines.append(f"- **Profiles:** {', '.join(p[0] or '<ambient>' for p in profiles)}")
    lines.append(f"- **Overall:** **{report_json['overall']}** "
                 f"(PASS={counts[Verdict.PASS]} FAIL={counts[Verdict.FAIL]} "
                 f"WARN={counts[Verdict.WARN]} SKIP={counts[Verdict.SKIP]} INFO={counts[Verdict.INFO]})")
    lines.append("")
    lines.append("## Environment Fingerprint (secrets redacted)")
    lines.append("")
    lines.append("| Variable | Value |")
    lines.append("|----------|-------|")
    for k, v in fingerprint.items():
        lines.append(f"| `{k}` | `{v}` |")
    lines.append("")

    # Group results by tier for readability.
    for tier in tiers:
        tier_results = [r for r in results if r.tier == tier]
        if not tier_results:
            continue
        lines.append(f"## Tier {tier}")
        lines.append("")
        for r in tier_results:
            badge = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP", "INFO": "INFO"}[r.verdict]
            prof = f" _(profile: {r.profile})_" if r.profile else ""
            lines.append(f"### [{badge}] {r.probe_id} — {r.name}{prof}")
            lines.append("")
            lines.append(f"{r.detail}")
            lines.append("")
            if r.evidence:
                lines.append("Evidence:")
                lines.append("")
                for e in r.evidence:
                    if e.command:
                        lines.append(f"- `{e.command}`")
                        if e.output:
                            lines.append("  ```")
                            for ln in e.output.splitlines():
                                lines.append(f"  {ln}")
                            lines.append("  ```")
                    if e.note:
                        label = "inference" if e.is_inference else "note"
                        lines.append(f"  - _{label}:_ {e.note}")
                lines.append("")
    (report_dir / "report.md").write_text("\n".join(lines))
    return overall_fail


# --- Confirmation ---------------------------------------------------------

def confirm_launch(route_info, tiers, profiles, assume_yes: bool) -> bool:
    live_tiers = [t for t in tiers if t in ("1", "2")]
    print("=" * 68)
    print("DAAF Deployment Smoke Test — pre-launch summary")
    print("=" * 68)
    print(f"  Detected route : {route_info.detected_route}")
    print(f"  Model family   : {route_info.model_family} (remap_active={route_info.remap_active})")
    print(f"  Tiers          : {', '.join(tiers)}")
    print(f"  Profiles       : {', '.join(p[0] or '<ambient>' for p in profiles)}")
    if live_tiers:
        n_runs = len(profiles) * (1 if "1" in tiers else 0) + len(profiles) * (6 if "2" in tiers else 0)
        print(f"  COST NOTE      : Tiers {live_tiers} make ~{n_runs} live claude -p API calls "
              f"(billed to your configured provider).")
    else:
        print("  COST NOTE      : No live API tiers selected (Tier 0/D are free).")
    print("=" * 68)
    if assume_yes or not live_tiers:
        return True
    try:
        ans = input("Proceed with live API tiers? [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


# --- Main -----------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="DAAF deployment smoke-testing suite (in-situ, route-aware).")
    parser.add_argument("--route", default="", help="Assert the expected route; detection mismatch => FAIL.")
    parser.add_argument("--profiles", default="", help="Comma-separated profile names from profiles.yaml (OpenRouter route).")
    parser.add_argument("--tiers", default="0,1,2", help="Comma-separated tiers to run (default 0,1,2; add D for the deterministic battery).")
    parser.add_argument("--include-r-smoke", action="store_true", help="Include the (slow) R/Python skill smoke suite in Tier D.")
    parser.add_argument("--timeout", type=int, default=0, help="Per-probe timeout seconds (0 = per-tier defaults).")
    parser.add_argument("--yes", action="store_true", help="Skip the pre-launch cost/summary confirmation.")
    parser.add_argument("--report-dir", default="", help="Override the report output directory.")
    args = parser.parse_args()

    env = os.environ
    tiers = parse_tiers(args.tiers)
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

    if not confirm_launch(route_info, tiers, profiles, args.yes):
        print("Aborted by user (no confirmation).", file=sys.stderr)
        return 1

    results = []
    shim_health_snapshot = None
    run_live_tiers = True

    # Tier 0 — run once (route-scoped, not profile-scoped).
    if "0" in tiers:
        t0 = smoke_probes.run_tier0(route_info, env, BASE_DIR)
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

        # Fail-fast gate: if T0.0 (DAAF_DEV) FAILed, do NOT proceed to any paid
        # live tier. The suite assumes the DAAF_DEV=1 dev image; running Tier 1/2
        # against a non-dev image would burn API cost on a config the suite cannot
        # validate. The report is still written and the run still exits nonzero
        # (T0.0's FAIL already flips the overall verdict). Tier D (free,
        # deterministic) still runs and self-SKIPs any missing dev tooling.
        daaf_dev_failed = any(r.probe_id == "T0.0" and r.verdict == Verdict.FAIL for r in t0)
        live_selected = any(t in ("1", "2") for t in tiers)
        if daaf_dev_failed and live_selected:
            run_live_tiers = False
            print("ABORT: T0.0 (DAAF_DEV) FAILed — the deployment smoke suite assumes the "
                  "DAAF_DEV=1 dev image. Skipping all live API tiers (1/2) so no cost is "
                  "billed against an unvalidatable config. Fix DAAF_DEV=1 and re-run.",
                  file=sys.stderr)
            abort = ProbeResult(probe_id="T0.ABORT", name="Live tiers aborted (DAAF_DEV FAIL)", tier="0")
            abort.verdict = Verdict.FAIL
            abort.detail = (
                "Live API tiers (1/2) were SKIPPED because T0.0 (DAAF_DEV) FAILed. The suite "
                "assumes the DAAF_DEV=1 dev image; running paid tiers against a non-dev image "
                "would burn cost on a config it cannot validate. Fix DAAF_DEV=1 and re-run."
            )
            abort.add_evidence("", note="fail-fast gate: DAAF_DEV must be 1 before any live tier",
                               is_inference=False)
            results.append(abort)

    # Tier 1 / Tier 2 — run once PER PROFILE (skipped if the DAAF_DEV gate tripped).
    if run_live_tiers:
        for prof_name, overlay in profiles:
            if "1" in tiers:
                results.extend(smoke_probes.run_tier1(prof_name, overlay, t1_timeout))
            if "2" in tiers:
                results.extend(smoke_probes.run_tier2(prof_name, overlay, t2_timeout))

    # Tier D — run once (not profile-scoped; deterministic, provider-agnostic).
    if "D" in tiers:
        results.extend(smoke_probes.run_tier_d(args.include_r_smoke, td_timeout))

    # --- Reports ---
    if args.report_dir:
        report_dir = Path(args.report_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = REPORTS_ROOT / f"{stamp}_{route_info.detected_route}"

    overall_fail = write_reports(report_dir, route_info, fingerprint, results, tiers, profiles, shim_health_snapshot)

    counts = verdict_counts(results)
    print("")
    print(f"Report written: {report_dir}")
    print(f"Summary: PASS={counts[Verdict.PASS]} FAIL={counts[Verdict.FAIL]} "
          f"WARN={counts[Verdict.WARN]} SKIP={counts[Verdict.SKIP]} INFO={counts[Verdict.INFO]}")
    print(f"Overall: {'FAIL' if overall_fail else 'PASS'}")
    return 1 if overall_fail else 0


if __name__ == "__main__":
    sys.exit(main())
