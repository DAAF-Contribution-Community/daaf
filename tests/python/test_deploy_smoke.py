"""Provider-free regression tests for the DAAF deployment smoke harness.

Standard-library unittest + unittest.mock ONLY — no third-party test deps, no
network, no live provider calls. Every fixture lives under scripts/scratch/
(NEVER /tmp) and is removed in tearDown.

This module is wired into Tier D as TD.0 (run BEFORE the broader batteries) so an
official Tier D run first validates its own harness: environment sanitization,
Tier D failure-evidence capture, Pester/battery output routing, per-run Tier 2
sandbox cleanup, and the stricter T2.2 freshness/success semantics.

Run directly:
  python3 -m unittest discover -s /daaf/tests/python -p 'test_deploy_smoke.py'
"""

import os
import subprocess
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock

# --- Import path guard: mirror run_deploy_smoke.py so route_detection /
# smoke_probes / run_deploy_smoke and the benchmarks harness all import
# regardless of the caller's CWD. ---
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]                       # tests/python/ -> tests/ -> /daaf
_SMOKE_DIR = _REPO_ROOT / "scripts" / "deploy_smoke"
for _p in (str(_REPO_ROOT), str(_SMOKE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import route_detection  # noqa: E402
import smoke_probes  # noqa: E402
import run_deploy_smoke  # noqa: E402
from route_detection import Verdict  # noqa: E402

_SCRATCH = _REPO_ROOT / "scripts" / "scratch"


def _scratch_dir(prefix):
    """Create and return a fresh, uniquely named scratch directory (inside the
    project, per the /tmp prohibition)."""
    d = _SCRATCH / f"{prefix}_{uuid.uuid4().hex[:10]}"
    d.mkdir(parents=True, exist_ok=False)
    return d


class TierDEnvSanitizationTests(unittest.TestCase):
    def test_removes_exactly_the_two_contaminants_and_preserves_the_rest(self):
        with mock.patch.dict(os.environ, {
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000",
            "DAAF_BRANCH": "daaf_dev_r2",
            "PATH": os.environ.get("PATH", "/usr/bin"),
            "SMOKE_UNRELATED": "keepme",
        }, clear=False):
            env, removed = smoke_probes.tier_d_sanitized_env()
        self.assertNotIn("CLAUDE_CODE_MAX_CONTEXT_TOKENS", env)
        self.assertNotIn("DAAF_BRANCH", env)
        self.assertEqual(sorted(removed), ["CLAUDE_CODE_MAX_CONTEXT_TOKENS", "DAAF_BRANCH"])
        self.assertEqual(env.get("SMOKE_UNRELATED"), "keepme")
        self.assertIn("PATH", env)  # toolchain reachability preserved

    def test_does_not_mutate_os_environ(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000"}, clear=False):
            smoke_probes.tier_d_sanitized_env()
            # The real process env is untouched; the helper copies first.
            self.assertEqual(os.environ.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS"), "1050000")

    def test_reports_no_contaminants_when_absent(self):
        clean = {k: v for k, v in os.environ.items()
                 if k not in ("CLAUDE_CODE_MAX_CONTEXT_TOKENS", "DAAF_BRANCH")}
        with mock.patch.dict(os.environ, clean, clear=True):
            env, removed = smoke_probes.tier_d_sanitized_env()
        self.assertEqual(removed, [])


class BatteryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ev = _scratch_dir("td_evidence")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.ev, ignore_errors=True)

    def test_pass_evidence_is_concise_final_eight_lines(self):
        # 30 numbered lines, exit 0 -> only the final 8 are retained, no artifact.
        script = "import sys\n" + "".join(f"print({i})\n" for i in range(30))
        r = smoke_probes._run_battery_cmd(
            "TDX.pass", "concise pass", ["python3", "-c", script], timeout=30,
            evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.PASS)
        out = r.evidence[0].output
        self.assertLessEqual(len(out.splitlines()), 8)
        self.assertIn("29", out)         # final line kept
        self.assertNotIn("0\n", out + "\n")  # early lines dropped from concise view
        # No failure artifact on PASS.
        self.assertFalse((self.ev / "TDX.pass.log").exists())

    def test_fail_evidence_keeps_head_and_tail_and_writes_full_artifact(self):
        # Distinctive early + late markers around a long middle, then exit 1.
        lines = ["print('EARLY_FAILURE_MARKER')"]
        lines += [f"print('mid-{i}')" for i in range(80)]
        lines += ["print('FINAL_SUMMARY_MARKER')", "import sys; sys.exit(1)"]
        script = "\n".join(lines) + "\n"
        r = smoke_probes._run_battery_cmd(
            "TDX.fail", "long fail", ["python3", "-c", script], timeout=30,
            evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.FAIL)
        excerpt = r.evidence[0].output
        self.assertIn("EARLY_FAILURE_MARKER", excerpt)     # early failure name visible
        self.assertIn("FINAL_SUMMARY_MARKER", excerpt)     # final summary visible
        self.assertIn("omitted", excerpt)                  # middle elided with count
        # Complete scrubbed output persisted and referenced.
        artifact = self.ev / "TDX.fail.log"
        self.assertTrue(artifact.exists())
        full = artifact.read_text()
        self.assertIn("EARLY_FAILURE_MARKER", full)
        self.assertIn("mid-40", full)                      # the elided middle is in the full log
        self.assertIn("FINAL_SUMMARY_MARKER", full)
        self.assertTrue(any(str(artifact) in (e.note or "") for e in r.evidence))

    def test_timeout_preserves_flushed_output_when_available(self):
        # Flush a marker, then block past the timeout -> partial output captured.
        script = ("import sys, time\n"
                  "sys.stdout.write('PRE_TIMEOUT_MARKER\\n'); sys.stdout.flush()\n"
                  "time.sleep(30)\n")
        r = smoke_probes._run_battery_cmd(
            "TDX.timeout", "timeout probe", ["python3", "-u", "-c", script], timeout=2,
            evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("timed out", r.detail)
        artifact = self.ev / "TDX.timeout.log"
        self.assertTrue(artifact.exists())
        self.assertIn("PRE_TIMEOUT_MARKER", artifact.read_text())

    def test_secret_values_are_scrubbed_from_evidence(self):
        # The threat channel is CAPTURED OUTPUT: a battery echoing an env secret.
        # (Tier D commands are fixed invocations with no secrets in argv.) The
        # child reads the secret from the env and prints it, so it appears in
        # stdout and must be scrubbed from both the excerpt and the full artifact.
        secret = "supersecretvalue123456"
        script = ("import os, sys\n"
                  "sys.stdout.write('leak=' + os.environ['SMOKE_TEST_API_KEY'] + '\\n')\n"
                  "sys.exit(1)\n")
        with mock.patch.dict(os.environ, {"SMOKE_TEST_API_KEY": secret}, clear=False):
            r = smoke_probes._run_battery_cmd(
                "TDX.scrub", "scrub", ["python3", "-c", script], timeout=30,
                evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertNotIn(secret, r.evidence[0].output)
        self.assertNotIn(secret, (self.ev / "TDX.scrub.log").read_text())

    def test_cwd_routes_output_into_the_evidence_directory(self):
        # Mirrors how TD.2 sets cwd=evidence_dir so Pester's testResults.xml lands
        # in the report instead of the repo root.
        target = self.ev / "wrote_in_cwd.txt"
        script = "open('wrote_in_cwd.txt', 'w').write('x')\nprint('ok')\n"
        r = smoke_probes._run_battery_cmd(
            "TDX.cwd", "cwd routing", ["python3", "-c", script], timeout=30,
            cwd=str(self.ev), evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.PASS)
        self.assertTrue(target.exists())


class T22FreshnessTests(unittest.TestCase):
    """The pure T2.2 evaluator: fresh banner + '# Exit code: 0' + this run's
    nonce after the banner is the ONLY PASS shape."""

    NONCE = "daaf-exec-abc123def456"

    def _log(self, exit_code, tail_body):
        return (
            f"import x\nprint('{self.NONCE}')\n"          # source line (nonce present by construction)
            "\n\n# =====\n# EXECUTION LOG\n# =====\n#\n"
            "# Executed: 2026-07-17\n"
            f"# Exit code: {exit_code}\n#\n"
            "# --- STDOUT ---\n"
            f"{tail_body}\n"
        )

    def test_fresh_success_with_nonce_after_banner_passes(self):
        body = self._log(0, f"# {self.NONCE}")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.PASS)
        self.assertTrue(all(facts.values()))

    def test_missing_script_fails(self):
        verdict, _ = smoke_probes._evaluate_t22(False, None, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)

    def test_no_banner_source_only_nonce_fails(self):
        # Script written (nonce in source) but never executed: no banner.
        body = f"import x\nprint('{self.NONCE}')\n"
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["banner"])

    def test_stale_banner_with_different_nonce_fails(self):
        # A leftover banner from a prior run carries a DIFFERENT run's nonce.
        body = self._log(0, "# daaf-exec-STALERUNyyyy")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["nonce_after_banner"])

    def test_banner_and_nonce_but_nonzero_exit_fails(self):
        body = self._log(1, f"# {self.NONCE}")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["exit_success"])

    def test_exit_code_100_does_not_match_success(self):
        # Anchored regex: '# Exit code: 100' must NOT satisfy the exit-0 check.
        body = self._log(100, f"# {self.NONCE}")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["exit_success"])


class Tier2SandboxCleanupTests(unittest.TestCase):
    """run_tier2 end-to-end with the live executor mocked out: no provider call,
    but the real per-run UUID sandbox creation + guaranteed cleanup path runs."""

    def setUp(self):
        self.sandbox = _scratch_dir("t2_sandbox")
        # A pre-existing sibling that must SURVIVE (proves cleanup is scoped to the
        # run-owned dir only, never a recursive wipe of _sandbox/).
        self.sibling = self.sandbox / "historical_sibling.txt"
        self.sibling.write_text("keep me\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_cleanup_removes_only_the_run_dir_and_spares_siblings(self):
        fake_meta = {"session_id": "test-sid-00000000"}
        fake_res = types.SimpleNamespace(response_text="", model_id="")

        with mock.patch.object(smoke_probes, "_sandbox_dir", return_value=self.sandbox), \
             mock.patch.object(smoke_probes, "execute_smoke_run",
                               return_value=(fake_res, fake_meta)), \
             mock.patch.object(smoke_probes, "find_transcript", return_value=None), \
             mock.patch.object(smoke_probes, "find_subagent_transcripts", return_value=[]):
            results = smoke_probes.run_tier2("", {}, timeout=5)

        # Six probes still produced (structure intact), no exception.
        self.assertEqual(len(results), 6)
        # The sibling survived; no stray run_ directory remains.
        self.assertTrue(self.sibling.exists())
        leftover = [p for p in self.sandbox.glob("run_*") if p.is_dir()]
        self.assertEqual(leftover, [], f"run dir not cleaned: {leftover}")


class ParseTiersTests(unittest.TestCase):
    def test_valid_spec_orders_and_dedupes(self):
        self.assertEqual(run_deploy_smoke.parse_tiers("0,1,2,D"), ["0", "1", "2", "D"])
        self.assertEqual(run_deploy_smoke.parse_tiers("d"), ["D"])
        self.assertEqual(run_deploy_smoke.parse_tiers("0,0,1"), ["0", "1"])

    def test_empty_spec_yields_empty_list(self):
        self.assertEqual(run_deploy_smoke.parse_tiers(""), [])
        self.assertEqual(run_deploy_smoke.parse_tiers(",, ,"), [])

    def test_invalid_token_is_a_hard_error_naming_token_and_valid_set(self):
        with self.assertRaises(ValueError) as ctx:
            run_deploy_smoke.parse_tiers("0,X")
        msg = str(ctx.exception)
        self.assertIn("X", msg)
        for tok in ("0", "1", "2", "D"):
            self.assertIn(tok, msg)

    def test_invalid_token_not_silently_dropped_when_valid_present(self):
        with self.assertRaises(ValueError):
            run_deploy_smoke.parse_tiers("D,3")


class LintScopingTests(unittest.TestCase):
    """The PowerShell preamble lint must ignore research/worktree/scratch residue
    while still failing a noncompliant scripts/host/*.ps1 (including untracked)."""

    LINT = _REPO_ROOT / "tests" / "lint" / "check-daaf-conventions.sh"

    def setUp(self):
        self.repo = _scratch_dir("lint_fakerepo")
        # Ignored residue: noncompliant PS everywhere the recursive scan used to
        # reach. None of these may produce a lint failure after the scoping fix.
        for rel in ("research/proj/scratch/a.ps1",
                    ".claude/worktrees/wt1/scripts/host/b.ps1",
                    "scripts/scratch/probe/c.ps1"):
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("Write-Output 'no error action preference here'\n")
        # A CLAUDE.md so the freshness check (section 7) has a real path to grep;
        # without any freshness target present, GNU `grep -r` with an empty path
        # list falls back to scanning the process CWD — an artifact of running the
        # lint against a minimal synthetic root, not the scoping under test.
        (self.repo / "CLAUDE.md").write_text("# fake\nno bad freshness key here\n")
        # A compliant host script (DAAF_NESTED + progress + EAP) so the ONLY
        # possible failure isolates the preamble rule.
        host = self.repo / "scripts" / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "good.ps1").write_text(
            "# host script [1/1] DAAF_NESTED\n"
            "$ErrorActionPreference = 'Stop'\n"
            "Write-Output 'ok'\n")
        self.bad = host / "bad.ps1"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo, ignore_errors=True)

    def _run_lint(self):
        return subprocess.run(["bash", str(self.LINT), str(self.repo)],
                              capture_output=True, text=True, timeout=60)

    def test_ignored_residue_does_not_fail_lint(self):
        proc = self._run_lint()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for token in ("research/proj", ".claude/worktrees", "scripts/scratch/probe"):
            self.assertNotIn(token, proc.stdout)

    def test_noncompliant_host_ps1_still_fails(self):
        # Untracked host script missing $ErrorActionPreference (but DAAF_NESTED +
        # progress present so only the preamble rule fires).
        self.bad.write_text(
            "# host script [1/1] DAAF_NESTED\n"
            "Write-Output 'missing error action preference'\n")
        proc = self._run_lint()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("scripts/host/bad.ps1", proc.stdout)
        self.assertIn("ErrorActionPreference", proc.stdout)


if __name__ == "__main__":
    unittest.main()
