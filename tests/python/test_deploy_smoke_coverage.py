"""Provider-free tests for the deploy-smoke coverage changes (design items
D1-D5, then the review fixes H1-H5):

  * D1  T0.0 "Image flavor" (developer / standard / partial; WARN only for
        DAAF_DEV=1 without the tools) and the T0.15 / T0.22 INFO downgrade on a
        standard image; no hint text still says the suite needs DAAF_DEV=1.
  * D2  the preflight gate before paid tiers: gate subset with and without
        Tier 0 selected, T0.ABORT naming the blocking probes, the
        --allow-preflight-fail escape hatch, fail-closed on a gate crash.
  * D3  T0.24 settings invariants: each invariant's FAIL / WARN / PASS.
  * D4  T2.8: the shared write-and-execute judge on an R fixture, T2.2's text
        unchanged, and Tier 2's eighth call under the anthropic-api budget.
  * D5  TD.9: start / poll / stop of a stdlib http.server stub, a no-answer
        stub, an early exit, a SKIP for an absent binary, token scrubbing,
        child env redirection and the static launcher check.
  * H1  SIGTERM / SIGHUP unwind like Ctrl+C: a runner process holding a TD.9
        service is signalled mid-poll; the service is stopped, the report is
        written with RUN.CRASH, the exit code is 128 + the signal number. The
        same runner on a pseudo-terminal whose terminal end is closed (a real
        hang-up, after which console writes fail with EIO) still reaches the
        package step and exits 129.
  * H2  the gate per --profiles overlay (T0.3 / T0.16 / T0.17 on each child
        env): one profile blocked while its sibling runs, the override, the
        overlay's own model family, fail-closed on a crash.
  * H3  T0.0's WARN names only the Tier D batteries a missing tool gates, and
        says that without shellcheck TD.1 skips its shellcheck lint tests.
  * H4  TD.9: credential-named variables withheld from the services, the
        launcher wording when a binary was not tested, the SIGKILL rung.
  * H5  --timeout help names the TD.1 and TD.7 floors.
  Also T0.24 with CLAUDE_CODE_TMPDIR a symlink into /tmp.

Standard-library unittest + unittest.mock only, so it runs in the bare CI unit
job as well: no network beyond 127.0.0.1, no model call, no binary
other than this interpreter and bash (guarded with skipUnless). Fixtures live
under scripts/scratch/ (never /tmp) and are removed by addCleanup.

Wired into Tier D through TD.0's discovery of test_deploy_smoke*.py.

Run (file-first, via a captured runner script):
  python3 -m unittest discover -s /daaf/tests/python -p 'test_deploy_smoke_coverage.py'
"""

import io
import json
import os
import select
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import types
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

try:  # POSIX only: the closed-terminal (pty hang-up) test skips without it
    import pty
except ImportError:  # pragma: no cover — Windows
    pty = None

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "scripts" / "deploy_smoke")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import route_detection as rd  # noqa: E402
import smoke_probes as sp  # noqa: E402
import run_deploy_smoke as runner  # noqa: E402
from route_detection import ProbeResult, Verdict  # noqa: E402

_SCRATCH = _REPO_ROOT / "scripts" / "scratch"


def _scratch(test, prefix):
    d = _SCRATCH / f"{prefix}_{uuid.uuid4().hex[:10]}"
    d.mkdir(parents=True)
    test.addCleanup(shutil.rmtree, d, True)
    return d


def _pr(probe_id, verdict, tier="0", name="stub", detail=""):
    r = ProbeResult(probe_id=probe_id, name=name, tier=tier)
    r.verdict = verdict
    r.detail = detail or f"{probe_id} detail"
    return r


def _which_from(present):
    return lambda tool: f"/usr/bin/{tool}" if tool in present else None


ALL_DEV = set(rd.FLAVOR_TOOLS)


# --- D1: image flavor ---------------------------------------------------------------------------

class ImageFlavorTests(unittest.TestCase):
    def test_detect_flavor(self):
        self.assertEqual(rd.detect_image_flavor(_which_from(ALL_DEV))[0], rd.FLAVOR_DEVELOPER)
        self.assertEqual(rd.detect_image_flavor(_which_from(set()))[0], rd.FLAVOR_STANDARD)
        flavor, present = rd.detect_image_flavor(_which_from({"bats", "gh"}))
        self.assertEqual(flavor, rd.FLAVOR_PARTIAL)
        self.assertEqual(present, {"bats": True, "pwsh": False, "shellcheck": False, "gh": True})
        self.assertEqual(rd.FLAVOR_TOOLS, ("bats", "pwsh", "shellcheck", "gh"))

    def test_t00_verdicts_never_fail(self):
        cases = (
            ({}, set(), Verdict.INFO, "standard image"),
            ({}, ALL_DEV, Verdict.INFO, "developer image"),
            ({}, {"bats"}, Verdict.INFO, "partial"),
            ({"DAAF_DEV": "1"}, ALL_DEV, Verdict.INFO, "developer image"),
            ({"DAAF_DEV": "0"}, set(), Verdict.INFO, "standard image"),
            ({"DAAF_DEV": "1"}, set(), Verdict.WARN, "without a rebuild"),
            ({"DAAF_DEV": "1"}, {"bats", "pwsh", "shellcheck"}, Verdict.WARN, "gh"),
        )
        for env, present, want, fragment in cases:
            with self.subTest(env=env, present=sorted(present)):
                r = rd.probe_image_flavor(env, which=_which_from(present))
                self.assertEqual((r.probe_id, r.name, r.tier), ("T0.0", "Image flavor", "0"))
                self.assertEqual(r.verdict, want, r.detail)
                self.assertIn(fragment, r.detail)
                self.assertNotEqual(r.verdict, Verdict.FAIL)
                self.assertIn("DAAF_DEV", " ".join(e.command for e in r.evidence))

    def test_t00_warn_names_only_the_affected_batteries(self):
        # Review fix H3: bats gates TD.1, pwsh gates TD.2. shellcheck and gh SKIP
        # no battery, but TD.1's bats suite skips its shellcheck lint tests
        # without shellcheck (re-review W2), and the detail says so.
        sc_note = "shellcheck: TD.1 still runs but skips its shellcheck lint tests"
        cases = (
            (ALL_DEV - {"gh"}, [], ["TD.1 (", "TD.2"], "No Tier D battery will SKIP (gh: no Tier D battery uses it)."),
            (ALL_DEV - {"shellcheck"}, [], ["TD.1 (", "TD.2", "uses shellcheck"],
             f"No Tier D battery will SKIP ({sc_note})."),
            (ALL_DEV - {"shellcheck", "gh"}, [], ["TD.2", "uses shellcheck"],
             f"No Tier D battery will SKIP ({sc_note}; gh: no Tier D battery uses it)."),
            (ALL_DEV - {"bats"}, ["TD.1 (bats)"], ["TD.2"], "so Tier D will SKIP TD.1 (bats)."),
            (ALL_DEV - {"pwsh", "gh"}, ["TD.2 (Pester)", "(gh: no Tier D battery uses it.)"], ["TD.1"], ""),
            (ALL_DEV - {"pwsh", "shellcheck"}, ["TD.2 (Pester)", f"({sc_note}.)"], ["TD.1 ("], ""),
            (set(), ["TD.1 (bats) and TD.2 (Pester)",
                     "(shellcheck: only TD.1's lint tests use it; gh: no Tier D battery uses it.)"], [sc_note], ""),
        )
        for present, named, absent, fragment in cases:
            with self.subTest(present=sorted(present)):
                r = rd.probe_image_flavor({"DAAF_DEV": "1"}, which=_which_from(present))
                self.assertEqual(r.verdict, Verdict.WARN)
                self.assertIn("without a rebuild", r.detail)
                for text in named + ([fragment] if fragment else []):
                    self.assertIn(text, r.detail)
                for text in absent:
                    self.assertNotIn(text, r.detail)
        self.assertEqual(rd.FLAVOR_TIER_D_BATTERIES, {"bats": "TD.1 (bats)", "pwsh": "TD.2 (Pester)"})
        self.assertEqual(set(rd.FLAVOR_TIER_D_PARTIAL), {"shellcheck", "gh"})
        self.assertEqual(set(rd.FLAVOR_TIER_D_BATTERIES) | set(rd.FLAVOR_TIER_D_PARTIAL), set(rd.FLAVOR_TOOLS))

    def test_td1_bats_suite_really_uses_shellcheck_and_no_battery_uses_gh(self):
        # Re-review W2: pins the facts the T0.0 wording rests on. TD.1 runs
        # tests/bash; some of its tests call shellcheck and skip without it.
        # TD.3-TD.5 never call shellcheck, and no Tier D battery calls gh.
        bats_dir = _REPO_ROOT / "tests" / "bash"
        calls = [p.name for p in sorted(bats_dir.glob("*.bats"))
                 if "run shellcheck" in p.read_text(encoding="utf-8", errors="replace")]
        self.assertTrue(calls, "no TD.1 bats test calls shellcheck; update FLAVOR_TIER_D_PARTIAL")
        for name in calls:
            self.assertIn('skip "shellcheck not installed', (bats_dir / name).read_text(encoding="utf-8"), name)
        others = [_REPO_ROOT / "tests" / "lint" / "check-daaf-conventions.sh",
                  _REPO_ROOT / "scripts" / "test_safety_hooks.sh",
                  _REPO_ROOT / "scripts" / "test_enforce_single_command.sh"]
        for path in [p for p in others if p.is_file()]:
            with self.subTest(battery=path.name):
                text = path.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn("command -v shellcheck", text)
                self.assertNotIn("run shellcheck", text)
        battery_files = list(bats_dir.glob("*.bats")) + [p for p in others if p.is_file()]
        for path in battery_files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in ("command -v gh", "run gh "):
                self.assertNotIn(needle, text, path.name)

    def test_warn_carries_a_hint_and_alias_kept(self):
        r = sp.apply_hints([rd.probe_image_flavor({"DAAF_DEV": "1"}, which=_which_from(set()))])[0]
        self.assertIn("rebuild", r.hint)
        self.assertIs(rd.probe_daaf_dev, rd.probe_image_flavor)
        detected = (rd.FLAVOR_STANDARD, {t: False for t in rd.FLAVOR_TOOLS})
        self.assertEqual(rd.probe_image_flavor({}, detected=detected).verdict, Verdict.INFO)

    def test_no_text_still_requires_daaf_dev(self):
        texts = list(sp.PROBE_HINTS.values()) + [loc for _, loc in runner._FIX_LOCATIONS]
        for text in texts:
            with self.subTest(text=text[:60]):
                self.assertNotIn("DAAF_DEV=1 dev image", text)
                self.assertNotIn("requires DAAF_DEV=1", text)
                self.assertNotIn("Run inside the DAAF_DEV=1", text)
        self.assertIn("--allow-preflight-fail", sp.PROBE_HINTS["T0.ABORT"])

    def test_t015_info_on_standard_image_only(self):
        base = {"claude_code": "2.1.281", "claude_code_pin": "2.1.281", "daaf_sha": "abc",
                "dev_binaries": {"bats": False, "pwsh": False, "shellcheck": False}}
        v, d = sp._evaluate_t015(base, rd.ROUTE_ANTHROPIC, rd.FLAVOR_STANDARD)
        self.assertEqual(v, Verdict.INFO)
        self.assertIn("as expected on a standard image", d)
        for flavor in (rd.FLAVOR_PARTIAL, rd.FLAVOR_DEVELOPER, None):
            with self.subTest(flavor=flavor):
                self.assertEqual(sp._evaluate_t015(base, rd.ROUTE_ANTHROPIC, flavor)[0], Verdict.WARN)
        # Another warning keeps the WARN on a standard image; a shim-floor FAIL stays FAIL.
        v, d = sp._evaluate_t015(dict(base, claude_code="2.1.280"), rd.ROUTE_ANTHROPIC, rd.FLAVOR_STANDARD)
        self.assertEqual(v, Verdict.WARN)
        self.assertIn("differs from the Dockerfile pin", d)
        self.assertEqual(sp._evaluate_t015(dict(base, claude_code="2.1.270"), rd.ROUTE_CHATGPT,
                                           rd.FLAVOR_STANDARD)[0], Verdict.FAIL)
        full = dict(base, dev_binaries={"bats": True, "pwsh": True, "shellcheck": True})
        self.assertEqual(sp._evaluate_t015(full, rd.ROUTE_ANTHROPIC, rd.FLAVOR_STANDARD)[0], Verdict.PASS)

    def test_t022_info_on_standard_image_only(self):
        found = {t: "1.0" for t, _, _ in sp.TOOLCHAIN}
        dev_gone = dict(found, bats=None, pwsh=None, shellcheck=None)
        v, d = sp._evaluate_t022(dev_gone, rd.FLAVOR_STANDARD)
        self.assertEqual(v, Verdict.INFO)
        self.assertIn("standard image", d)
        for flavor in (rd.FLAVOR_PARTIAL, rd.FLAVOR_DEVELOPER, None):
            with self.subTest(flavor=flavor):
                self.assertEqual(sp._evaluate_t022(dev_gone, flavor)[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_t022(dict(dev_gone, quarto=None), rd.FLAVOR_STANDARD)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t022(found, rd.FLAVOR_STANDARD)[0], Verdict.PASS)

    def test_run_tier0_hands_t00_flavor_to_t015_t022_and_runs_t024(self):
        stub = _pr("stub", Verdict.SKIP)
        names = ("probe_cli_available", "probe_hook_registration", "probe_statuslines", "probe_shim_health",
                 "probe_auth_json", "probe_workspace_invariants", "probe_r_locale",
                 "probe_local_settings_shadowing", "probe_synced_surface", "probe_codex_config",
                 "probe_prompt_cache", "probe_shim_log_scan", "probe_runtime_identity",
                 "probe_framework_integrity")
        detected = (rd.FLAVOR_STANDARD, {t: False for t in rd.FLAVOR_TOOLS})
        with mock.patch.multiple(sp, **{n: mock.MagicMock(return_value=stub) for n in names}), \
             mock.patch.object(sp, "probe_versions", return_value=stub) as versions, \
             mock.patch.object(sp, "probe_toolchain", return_value=stub) as toolchain, \
             mock.patch.object(sp, "probe_settings_invariants", return_value=_pr("T0.24", Verdict.PASS)) as t024, \
             mock.patch.object(rd, "detect_image_flavor", return_value=detected):
            results = sp.run_tier0(rd.build_route_info({}), {"DAAF_DEV": "1"}, base_dir="/not-used")
        self.assertEqual(results[0].probe_id, "T0.0")
        self.assertEqual(results[0].verdict, Verdict.WARN)  # DAAF_DEV=1 on a standard image
        self.assertEqual(versions.call_args.kwargs["image_flavor"], rd.FLAVOR_STANDARD)
        self.assertEqual(toolchain.call_args.kwargs["image_flavor"], rd.FLAVOR_STANDARD)
        t024.assert_called_once()
        self.assertEqual(results[-1].probe_id, "T0.24")


# --- D2: preflight gate -------------------------------------------------------------------------

class PreflightGateTests(unittest.TestCase):
    """main() end to end with every tier entry point mocked; the gate probes
    themselves run for real against a synthetic environment (pure env + a
    settings read of a scratch base dir)."""

    COHERENT = {"ANTHROPIC_MODEL": "claude-opus-4-8"}               # anthropic-subscription
    KEY_SET = {"ANTHROPIC_MODEL": "claude-opus-4-8", "ANTHROPIC_API_KEY": "k" * 24}

    def setUp(self):
        self.root = _scratch(self, "gate")
        (self.root / "base" / ".claude").mkdir(parents=True)
        (self.root / "user").mkdir()

    def _run(self, env, tiers, extra_args=(), route="anthropic-subscription", profiles=None, **patches):
        report = self.root / f"report_{uuid.uuid4().hex[:6]}"
        argv = ["--route", route, "--tiers", tiers, "--yes", "--no-package",
                "--report-dir", str(report)] + list(extra_args)
        mocks = {}
        defaults = {
            "run_tier0": mock.Mock(return_value=[]),
            "run_tier1": mock.Mock(return_value=[]),
            "run_tier2": mock.Mock(return_value=[]),
            "run_tier_n": mock.Mock(return_value=[]),
            "probe_main_model_coherence": mock.Mock(
                side_effect=lambda e, b, **kw: _pr("T0.14", Verdict.PASS, tier=kw.get("tier", "1"))),
        }
        defaults.update(patches)
        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, dict(env, CLAUDE_CONFIG_DIR=str(self.root / "user")),
                                                clear=True))
            stack.enter_context(mock.patch.object(runner, "BASE_DIR", str(self.root / "base")))
            stack.enter_context(mock.patch.object(runner, "collect_versions", return_value={}))
            stack.enter_context(mock.patch.object(runner, "git_sha", return_value="0" * 40))
            if profiles is not None:
                stack.enter_context(mock.patch.object(runner, "load_profiles", return_value=profiles))
            stack.enter_context(mock.patch("sys.stdout", io.StringIO()))
            err = stack.enter_context(mock.patch("sys.stderr", io.StringIO()))
            for name, value in defaults.items():
                mocks[name] = stack.enter_context(mock.patch.object(sp, name, value, create=True))
            rc = runner.main(argv)
            stderr = err.getvalue()
        data = json.loads((report / "report.json").read_text())
        md = (report / "report.md").read_text()
        return rc, data, md, mocks, stderr

    def test_gate_subset_runs_without_tier_zero(self):
        rc, data, md, mocks, _ = self._run(self.COHERENT, "1")
        self.assertEqual(rc, 0)
        gate = [r for r in data["results"] if r["tier"] == "0"]
        self.assertEqual([r["probe_id"] for r in gate], ["T0.1", "T0.3", "T0.16", "T0.17"])
        self.assertTrue(all(r["name"].endswith("(gate subset)") for r in gate))
        mocks["run_tier0"].assert_not_called()
        mocks["run_tier1"].assert_called_once()
        pf = data["preflight_gate"]
        self.assertEqual((pf["applied"], pf["blocking"], pf["reused_from_tier0"]), (True, [], []))
        self.assertEqual(pf["gate_subset_run"], ["T0.1", "T0.3", "T0.16", "T0.17"])
        self.assertFalse(data["allow_preflight_fail"])
        self.assertIn("## Tier 0 (gate subset)", md)
        self.assertLess(md.index("## Tier 0 (gate subset)"), md.index("## Tier 1"))
        self.assertIn("| Preflight gate | passed: T0.1, T0.3, T0.16, T0.17", md)

    def test_gate_reuses_tier_zero_results(self):
        t0 = [_pr(pid, Verdict.PASS) for pid in ("T0.0", "T0.1", "T0.3", "T0.16", "T0.17")]
        gate = mock.Mock(return_value=[])
        rc, data, md, mocks, _ = self._run(self.COHERENT, "0,1", run_tier0=mock.Mock(return_value=t0),
                                           run_preflight_gate=gate)
        self.assertEqual(rc, 0)
        gate.assert_not_called()  # no double run
        self.assertEqual(data["preflight_gate"]["reused_from_tier0"], ["T0.1", "T0.3", "T0.16", "T0.17"])
        self.assertEqual([r["probe_id"] for r in data["results"]].count("T0.1"), 1)
        self.assertNotIn("(gate subset)", md)

    def test_gate_runs_only_what_tier_zero_lacks(self):
        t0 = [_pr("T0.1", Verdict.PASS), _pr("T0.3", Verdict.PASS)]
        gate = mock.Mock(return_value=[_pr("T0.16", Verdict.PASS), _pr("T0.17", Verdict.SKIP)])
        rc, data, _, _, _ = self._run(self.COHERENT, "0,1", run_tier0=mock.Mock(return_value=t0),
                                      run_preflight_gate=gate)
        self.assertEqual(rc, 0)
        self.assertEqual(gate.call_args.kwargs["probe_ids"], ("T0.16", "T0.17"))
        self.assertEqual(data["preflight_gate"]["gate_subset_run"], ["T0.16", "T0.17"])

    def test_abort_names_each_blocking_probe_and_free_tiers_still_run(self):
        # anthropic-subscription stated, but a Console key is set: T0.1 (route
        # mismatch: detection says anthropic-api) and T0.16 (credential overlap) FAIL.
        rc, data, md, mocks, stderr = self._run(self.KEY_SET, "1,2,N")
        self.assertEqual(rc, 1)
        mocks["run_tier1"].assert_not_called()
        mocks["run_tier2"].assert_not_called()
        mocks["probe_main_model_coherence"].assert_not_called()
        mocks["run_tier_n"].assert_called_once()
        abort = [r for r in data["results"] if r["probe_id"] == "T0.ABORT"]
        self.assertEqual(len(abort), 1)
        self.assertEqual(abort[0]["verdict"], "FAIL")
        self.assertIn("T0.1, T0.16", abort[0]["detail"])
        self.assertIn("--allow-preflight-fail", abort[0]["hint"])
        self.assertEqual(data["preflight_gate"]["blocking"], ["T0.1", "T0.16"])
        self.assertTrue(data["preflight_gate"]["paid_tiers_skipped"])
        self.assertIn("**BLOCKED** by T0.1, T0.16", md)
        self.assertIn("ABORT: preflight gate FAILed (T0.1, T0.16)", stderr)

    def test_abort_on_a_failing_reused_tier_zero_probe(self):
        t0 = [_pr("T0.1", Verdict.PASS), _pr("T0.3", Verdict.FAIL), _pr("T0.16", Verdict.PASS),
              _pr("T0.17", Verdict.SKIP)]
        rc, data, _, mocks, _ = self._run(self.COHERENT, "0,1", run_tier0=mock.Mock(return_value=t0))
        self.assertEqual(rc, 1)
        mocks["run_tier1"].assert_not_called()
        abort = [r for r in data["results"] if r["probe_id"] == "T0.ABORT"]
        self.assertIn("FAILed: T0.3.", abort[0]["detail"])

    def test_escape_hatch_runs_paid_tiers_and_is_recorded(self):
        rc, data, md, mocks, stderr = self._run(self.KEY_SET, "1", extra_args=["--allow-preflight-fail"])
        mocks["run_tier1"].assert_called_once()
        self.assertNotIn("T0.ABORT", [r["probe_id"] for r in data["results"]])
        self.assertTrue(data["allow_preflight_fail"])
        pf = data["preflight_gate"]
        self.assertTrue(pf["overridden"])
        self.assertFalse(pf["paid_tiers_skipped"])
        self.assertIn("--allow-preflight-fail", md.split("### Problems")[0])
        self.assertIn("**FAILED** (T0.1, T0.16)", md)
        self.assertIn("running the paid tiers anyway", stderr)
        self.assertEqual(rc, 1)  # the gate FAILs still fail the run

    def test_gate_crash_fails_closed(self):
        rc, data, _, mocks, _ = self._run(self.COHERENT, "1",
                                          run_preflight_gate=mock.Mock(side_effect=RuntimeError("boom")))
        self.assertEqual(rc, 1)
        mocks["run_tier1"].assert_not_called()
        abort = [r for r in data["results"] if r["probe_id"] == "T0.ABORT"]
        self.assertIn("T0.CRASH", abort[0]["detail"])

    def test_no_live_tier_no_gate(self):
        gate = mock.Mock(return_value=[])
        rc, data, md, _, _ = self._run(self.KEY_SET, "N", run_preflight_gate=gate)
        gate.assert_not_called()
        self.assertEqual(rc, 0)
        self.assertFalse(data["preflight_gate"]["applied"])
        self.assertIn("| Preflight gate | not applied (no paid tier selected).", md)

    def test_flag_in_help_and_call_counts(self):
        help_text = runner.build_parser().format_help()
        self.assertIn("--allow-preflight-fail", help_text)
        self.assertEqual(runner.LIVE_CALLS_PER_PROFILE, {"1": 1, "2": 8, "A": 1, "3": 2})
        self.assertEqual(sum(runner.LIVE_CALLS_PER_PROFILE.values()), 12)
        worst = sum(n * sp.ANTHROPIC_API_BUDGET_USD[t] for t, n in runner.LIVE_CALLS_PER_PROFILE.items())
        self.assertAlmostEqual(worst, 50.0)
        self.assertEqual(runner.GATE_PROBE_IDS, sp.GATE_PROBE_IDS)
        self.assertEqual(sp.GATE_PROBE_IDS, ("T0.1", "T0.3", "T0.16", "T0.17"))

    def test_run_preflight_gate_marks_the_subset(self):
        info = rd.build_route_info({}, asserted_route=rd.ROUTE_ANTHROPIC)
        out = sp.run_preflight_gate(info, {}, str(self.root / "base"), probe_ids=("T0.16", "T0.1"))
        self.assertEqual([r.probe_id for r in out], ["T0.1", "T0.16"])  # gate order, not argument order
        self.assertTrue(all(r.name.endswith(" (gate subset)") and r.tier == "0" for r in out))

    # --- Review fix H2: the gate per --profiles overlay ---

    # The ambient install is a clean subscription; the "keyed" overlay adds a
    # Console key, so on that profile's child env T0.16 FAILs (every paid call
    # would bill the key) and T0.1 FAILs (the key moves detection to
    # anthropic-api), while "clean" stays coherent.
    PROFILES = [("keyed", {"ANTHROPIC_API_KEY": "k" * 24}), ("clean", {"ANTHROPIC_MODEL": "claude-sonnet-4-6"})]

    def test_profile_gate_blocks_only_its_profile(self):
        rc, data, md, mocks, stderr = self._run(self.COHERENT, "1", profiles=self.PROFILES)
        self.assertEqual(rc, 1)
        # The sibling runs; the keyed profile's paid tiers do not.
        self.assertEqual([c.args[0] for c in mocks["run_tier1"].call_args_list], ["clean"])
        # Both profiles still get their T0.14 re-check.
        self.assertEqual(mocks["probe_main_model_coherence"].call_count, 2)
        gated = [r for r in data["results"]
                 if r["name"].endswith("(profile gate)") and r["probe_id"] != "T0.ABORT"]
        self.assertEqual(sorted({(r["probe_id"], r["profile"]) for r in gated}),
                         sorted((pid, p) for pid in ("T0.1", "T0.3", "T0.16", "T0.17") for p in ("keyed", "clean")))
        self.assertTrue(all(r["tier"] == "1" for r in gated))  # filed with the T0.14 re-check
        verdicts = {(r["probe_id"], r["profile"]): r["verdict"] for r in gated}
        self.assertEqual(verdicts[("T0.16", "keyed")], "FAIL")
        self.assertEqual(verdicts[("T0.16", "clean")], "PASS")
        self.assertEqual((verdicts[("T0.1", "keyed")], verdicts[("T0.1", "clean")]), ("FAIL", "PASS"))
        keyed_hint = [r["hint"] for r in gated if (r["probe_id"], r["profile"]) == ("T0.16", "keyed")][0]
        self.assertIn("profiles.yaml", keyed_hint)
        aborts = [r for r in data["results"] if r["probe_id"] == "T0.ABORT"]
        self.assertEqual(len(aborts), 1)
        self.assertEqual((aborts[0]["profile"], aborts[0]["name"]), ("keyed", "Paid tiers skipped (profile gate)"))
        self.assertIn("T0.16", aborts[0]["detail"])
        pf = data["preflight_gate"]
        self.assertEqual(pf["blocking"], [])  # the ambient gate passed
        self.assertEqual(pf["per_profile"]["keyed"],
                         {"probes": ["T0.1", "T0.3", "T0.16", "T0.17"], "blocking": ["T0.1", "T0.16"],
                          "overridden": False,
                          "t014_verdict": "PASS", "paid_tiers_skipped": True})
        self.assertEqual(pf["per_profile"]["clean"]["blocking"], [])
        self.assertFalse(pf["per_profile"]["clean"]["paid_tiers_skipped"])
        self.assertIn("Per profile (T0.1, T0.3, T0.16, T0.17 re-checked on each overlay): keyed **BLOCKED** by "
                      "T0.1, T0.16; clean passed.", md)
        self.assertIn("ABORT: profile gate FAILed for keyed (T0.1, T0.16)", stderr)

    def test_profile_gate_override(self):
        rc, data, md, mocks, stderr = self._run(self.COHERENT, "1", extra_args=["--allow-preflight-fail"],
                                                profiles=self.PROFILES)
        self.assertEqual([c.args[0] for c in mocks["run_tier1"].call_args_list], ["keyed", "clean"])
        self.assertNotIn("T0.ABORT", [r["probe_id"] for r in data["results"]])
        keyed = data["preflight_gate"]["per_profile"]["keyed"]
        self.assertEqual((keyed["blocking"], keyed["overridden"], keyed["paid_tiers_skipped"]),
                         (["T0.1", "T0.16"], True, False))
        self.assertIn("keyed **FAILED** (T0.1, T0.16), ran anyway", md)
        self.assertIn("running its paid tiers anyway", stderr)
        self.assertEqual(rc, 1)  # the profile gate FAIL still fails the run

    def test_no_profile_gate_without_named_profiles_or_after_an_ambient_block(self):
        rc, data, _, mocks, _ = self._run(self.COHERENT, "1")
        self.assertEqual(rc, 0)
        self.assertEqual(data["preflight_gate"]["per_profile"], {})
        self.assertFalse(any(r["name"].endswith("(profile gate)") for r in data["results"]))
        rc, data, md, mocks, _ = self._run(self.KEY_SET, "1", profiles=self.PROFILES)
        mocks["run_tier1"].assert_not_called()
        self.assertEqual(data["preflight_gate"]["per_profile"], {})
        self.assertFalse(any(r["name"].endswith("(profile gate)") for r in data["results"]))
        self.assertNotIn("Per profile", md)

    def test_profile_gate_judges_the_overlay_model_family(self):
        # A Claude-family OpenRouter install: the ambient T0.17 SKIPs. A non-Claude
        # overlay with no tier aliases must be judged as non-Claude (WARN), which
        # needs the route info rebuilt from the profile's child env.
        env = {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "ANTHROPIC_AUTH_TOKEN": "o" * 24,
               "ANTHROPIC_API_KEY": "", "ANTHROPIC_MODEL": "anthropic/claude-opus-4-8"}
        rc, data, _, mocks, _ = self._run(env, "1", route="openrouter",
                                          profiles=[("gpt", {"ANTHROPIC_MODEL": "openai/gpt-6-astra"})])
        ambient = [r for r in data["results"] if r["probe_id"] == "T0.17" and not r["profile"]]
        self.assertEqual(ambient[0]["verdict"], "SKIP", ambient[0]["detail"])
        overlay = [r for r in data["results"] if r["probe_id"] == "T0.17" and r["profile"] == "gpt"]
        self.assertEqual(overlay[0]["verdict"], "WARN", overlay[0]["detail"])
        mocks["run_tier1"].assert_called_once()  # a WARN never blocks
        self.assertEqual(rc, 0)

    def test_profile_gate_t01_fails_when_the_overlay_moves_route_detection(self):
        # The ambient env detects anthropic-subscription, as stated. The "moved"
        # overlay points ANTHROPIC_BASE_URL at OpenRouter, so detection on its
        # child env no longer matches --route: T0.1 FAILs for that profile only.
        moved = ("moved", {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api"})
        rc, data, _, mocks, stderr = self._run(self.COHERENT, "1", profiles=[moved, self.PROFILES[1]])
        self.assertEqual(rc, 1)
        self.assertEqual([c.args[0] for c in mocks["run_tier1"].call_args_list], ["clean"])
        t01 = {r["profile"]: r for r in data["results"] if r["probe_id"] == "T0.1"}
        self.assertEqual(t01["moved"]["verdict"], "FAIL", t01["moved"]["detail"])
        self.assertTrue(t01["moved"]["name"].endswith("(profile gate)"))
        self.assertIn("openrouter", t01["moved"]["detail"])
        self.assertEqual(t01["clean"]["verdict"], "PASS")
        self.assertIn("T0.1", data["preflight_gate"]["per_profile"]["moved"]["blocking"])
        self.assertTrue(data["preflight_gate"]["per_profile"]["moved"]["paid_tiers_skipped"])
        self.assertIn("ABORT: profile gate FAILed for moved (T0.1", stderr)

    def test_profile_gate_crash_fails_closed(self):
        calls = []

        def gate(info, env, base, probe_ids=(), name_suffix=""):
            calls.append(name_suffix)
            if name_suffix.strip() == "(profile gate)":
                raise RuntimeError("boom")
            return [_pr(pid, Verdict.PASS) for pid in probe_ids]
        rc, data, _, mocks, _ = self._run(self.COHERENT, "1", profiles=self.PROFILES[1:],
                                          run_preflight_gate=mock.Mock(side_effect=gate))
        self.assertEqual(rc, 1)
        mocks["run_tier1"].assert_not_called()
        self.assertEqual(data["preflight_gate"]["per_profile"]["clean"]["blocking"], ["T0.CRASH"])


# --- D3: T0.24 settings invariants --------------------------------------------------------------

class SettingsInvariantsTests(unittest.TestCase):
    GOOD_ENV = {"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"}

    def setUp(self):
        self.base = _scratch(self, "t024")
        (self.base / ".claude" / "scripts").mkdir(parents=True)
        self.user = self.base / "user"
        self.user.mkdir()
        for name in ("context-bar.sh", "subagent-bar.sh"):
            p = self.base / ".claude" / "scripts" / name
            p.write_text("#!/usr/bin/env bash\necho ok\n")
            p.chmod(0o755)
        self.tmproot = self.base / "cc-tmp"
        self.tmproot.mkdir()
        self.settings = {
            "statusLine": {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/scripts/context-bar.sh"},
            "subagentStatusLine": {"type": "command",
                                   "command": "$CLAUDE_PROJECT_DIR/.claude/scripts/subagent-bar.sh"},
            "env": dict(self.GOOD_ENV),
        }

    def _probe(self, env_extra=None, settings=None, local=None, tmpdir="default"):
        (self.base / ".claude" / "settings.json").write_text(json.dumps(settings or self.settings))
        if local is not None:
            (self.base / ".claude" / "settings.local.json").write_text(local)
        env = {"CLAUDE_CONFIG_DIR": str(self.user)}
        if tmpdir == "default":
            env["CLAUDE_CODE_TMPDIR"] = str(self.tmproot)
        elif tmpdir is not None:
            env["CLAUDE_CODE_TMPDIR"] = tmpdir
        env.update(env_extra or {})
        return sp.probe_settings_invariants(env, str(self.base))

    def test_shipped_shape_passes(self):
        r = self._probe()
        self.assertEqual((r.probe_id, r.name, r.tier), ("T0.24", "Settings invariants", "0"))
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertIn("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1 (project settings)", r.evidence[0].output)

    def test_shipped_settings_json_carries_the_invariants(self):
        facts = sp.collect_settings_invariants({"CLAUDE_CONFIG_DIR": str(self.user)}, str(_REPO_ROOT))
        self.assertEqual(facts["env"]["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"]["value"], "1")
        self.assertEqual(facts["env"]["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"]["value"], "1")
        for key in sp.STATUSLINE_KEYS:
            self.assertTrue(facts["statusline"][key]["executable"], facts["statusline"][key])

    def test_spawn_depth_fail_names_the_layer(self):
        r = self._probe(local=json.dumps({"env": {"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "2"}}))
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=2 (local settings)", r.detail)
        (self.base / ".claude" / "settings.local.json").unlink()
        unset = dict(self.settings, env={"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"})
        r = self._probe(settings=unset)
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=<unset>", r.detail)

    def test_settings_layer_overrides_process_env(self):
        r = self._probe(env_extra={"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "5"})
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        no_env = dict(self.settings, env={})
        r = self._probe(settings=no_env, env_extra=self.GOOD_ENV)
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertIn("(process env)", r.evidence[0].output)

    def test_background_tasks_is_warn(self):
        r = self._probe(settings=dict(self.settings, env={"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1",
                                                          "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "0"}))
        self.assertEqual(r.verdict, Verdict.WARN, r.detail)
        self.assertIn("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=0", r.detail)
        self.assertTrue(sp.apply_hints([r])[0].hint)

    def test_tmpdir_rules(self):
        self.assertEqual(self._probe(tmpdir=None).verdict, Verdict.FAIL)
        r = self._probe(tmpdir="/tmp/claude-1000")  # judged by path only; nothing is written there
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("under /tmp", r.detail)
        self.assertEqual(self._probe(tmpdir="relative/dir").verdict, Verdict.FAIL)
        # Absent but creatable under a writable parent: Claude Code creates it.
        r = self._probe(tmpdir=str(self.base / "not-yet" / "cc-tmp"))
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        # A settings-file value is ignored (Claude Code 2.1.251+), only reported.
        in_settings = dict(self.settings, env=dict(self.GOOD_ENV, CLAUDE_CODE_TMPDIR=str(self.tmproot)))
        r = self._probe(settings=in_settings, tmpdir=None)
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn('"also_in_settings_ignored": ["project settings"]', r.evidence[1].output)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root bypasses the write bit")
    def test_tmpdir_not_writable(self):
        locked = self.base / "locked"
        locked.mkdir()
        locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(locked.chmod, 0o755)
        r = self._probe(tmpdir=str(locked))
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("is not writable", r.detail)

    def test_statusline_rules(self):
        (self.base / ".claude" / "scripts" / "subagent-bar.sh").chmod(0o644)
        r = self._probe()
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("subagentStatusLine (project settings) script is not executable", r.detail)
        (self.base / ".claude" / "scripts" / "context-bar.sh").unlink()
        self.assertIn("statusLine (project settings) script does not exist", self._probe().detail)
        missing = {k: v for k, v in self.settings.items() if k != "statusLine"}
        self.assertIn("statusLine is not registered", self._probe(settings=missing).detail)
        wrong = dict(self.settings, statusLine={"type": "static", "text": "x"})
        self.assertIn("is not a command statusline", self._probe(settings=wrong).detail)

    def test_malformed_local_layer_is_warn(self):
        r = self._probe(local="{broken")
        self.assertEqual(r.verdict, Verdict.WARN, r.detail)
        self.assertIn("local settings is malformed", r.detail)

    @unittest.skipUnless(hasattr(os, "symlink") and os.path.realpath("/tmp") == "/tmp",
                         "needs symlinks and a /tmp that is not itself a link")
    def test_tmpdir_symlink_into_tmp_fails(self):
        # Review fix (I6 test gap): CLAUDE_CODE_TMPDIR names a project path that
        # is a symlink into /tmp. The links live in this test's scratch dir and
        # are removed by cleanup; only the link TARGET strings name /tmp, and
        # nothing is created there (one target is /tmp itself, one does not exist).
        never = f"/tmp/daaf-t024-{uuid.uuid4().hex}/never-created"
        dangling = self.base / "cc-link-dangling"
        to_tmp = self.base / "cc-link-tmp"
        os.symlink(never, dangling)
        self.addCleanup(lambda: dangling.unlink() if os.path.lexists(dangling) else None)
        os.symlink("/tmp", to_tmp)
        self.addCleanup(lambda: to_tmp.unlink() if os.path.lexists(to_tmp) else None)
        for value in (str(dangling), str(to_tmp), str(to_tmp / "claude-1000")):
            with self.subTest(value=value):
                self.assertFalse(value.startswith("/tmp"))  # the literal path is not under /tmp
                self.assertTrue(sp._is_under_tmp(value))
                r = self._probe(tmpdir=value)
                self.assertEqual(r.verdict, Verdict.FAIL, r.detail)
                self.assertIn("is under /tmp", r.detail)
        self.assertFalse(os.path.lexists(never))
        self.assertFalse(os.path.lexists(os.path.dirname(never)))


# --- D4: T2.8 R write + execute -----------------------------------------------------------------

NONCE_R = "daaf-exec-r-0123456789ab"
RULE = "# " + "=" * 77


def _r_log(nonce_line=f"# {NONCE_R}", exit_code=0, capture="COMPLETE", source_extra=""):
    """The run_with_capture.sh log shape for an R script (Command: Rscript ...)."""
    return (f'cat("{NONCE_R}\\n")\n{source_extra}\n\n{RULE}\n# EXECUTION LOG\n{RULE}\n#\n'
            "# Executed: 2026-11-01 16:00:00\n"
            "# Command: Rscript /daaf/scripts/deploy_smoke/_sandbox/run_x/t28_probe.R\n"
            "# Duration: 0s\n"
            f"# Exit code: {exit_code}\n# Capture: {capture}\n#\n# --- STDOUT ---\n{nonce_line}\n#\n"
            "# --- STDERR ---\n# (captured in STDOUT above via 2>&1)\n#\n" + RULE + "\n")


def _cli_result(response="ok"):
    msg = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 2, "result": response,
           "api_error_status": None}
    return types.SimpleNamespace(
        raw_json={"messages": [msg]}, error="", response_text=response,
        model_identity=types.SimpleNamespace(claude_cli_model_usage_ids=["claude-opus-5-5[1m]"]),
        input_tokens=4, output_tokens=10, total_turns=2, total_cost_usd=0.01, model_id="claude-opus-5-5[1m]")


class RCodingProbeTests(unittest.TestCase):
    def test_evaluator_on_r_fixture(self):
        verdict, facts = sp._evaluate_t22(True, _r_log(), NONCE_R)
        self.assertEqual(verdict, Verdict.PASS, facts)
        for body, why in ((_r_log(exit_code=1), "exit"), (_r_log(capture="INCOMPLETE (tee exit 1)"), "capture"),
                          (_r_log(nonce_line="# (no output)"), "nonce only in source"),
                          (f'cat("{NONCE_R}\\n")\n', "never run")):
            with self.subTest(why=why):
                self.assertEqual(sp._evaluate_t22(True, body, NONCE_R)[0], Verdict.FAIL)
        forged = f"# =\n# EXECUTION LOG\n# =\n# Exit code: 0\n# Capture: COMPLETE\n# {NONCE_R}\n"
        self.assertEqual(sp._evaluate_t22(True, f'cat("{NONCE_R}\\n")\n' + forged, NONCE_R)[0], Verdict.FAIL)

    def _judge(self, probe_id, body):
        d = _scratch(self, "t28")
        script = d / ("t28_probe.R" if probe_id == "T2.8" else "t22_probe.py")
        if body is not None:
            script.write_text(body)
        r = ProbeResult(probe_id=probe_id, name="x", tier="2")
        with mock.patch.object(sp, "find_transcript", return_value=None), \
             mock.patch.object(sp, "load_transcript_records", return_value=[]):
            sp._judge_exec_probe(r, script, NONCE_R, _cli_result(), {"session_id": "sid-t28-0000"})
        return r

    def test_shared_judge_on_r_script(self):
        r = self._judge("T2.8", _r_log())
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertEqual(r.session_ids, ["sid-t28-0000"])
        self.assertTrue(r.detail.startswith("research-executor wrote the script and executed it via "
                                            "run_with_capture:"))
        r = self._judge("T2.8", None)
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertTrue(r.detail.startswith("T2.8 freshness/success check failed — required ALL of:"))

    def test_t22_text_unchanged(self):
        r = self._judge("T2.2", None)
        self.assertTrue(r.detail.startswith("T2.2 freshness/success check failed — required ALL of: script "
                                            "created, exactly ONE three-line execution-log banner frame"))
        self.assertEqual([e.command.split(" ")[0] for e in r.evidence[:3]], ["claude", "test", "evaluate"])

    def test_tier2_runs_t28_under_the_budget_cap(self):
        sandbox = _scratch(self, "t2_budget")
        calls = []

        def fake_exec(**kw):
            calls.append(kw)
            return _cli_result(), {"session_id": f"sid-{len(calls):04d}"}
        with mock.patch.object(sp, "_sandbox_dir", return_value=sandbox), \
             mock.patch.object(sp, "execute_smoke_run", side_effect=fake_exec), \
             mock.patch.object(sp, "find_transcript", return_value=None), \
             mock.patch.object(sp, "find_subagent_transcripts", return_value=[]):
            results = sp.run_tier2("", {}, timeout=5, route=rd.ROUTE_ANTHROPIC_API)
        self.assertEqual(len(calls), 8)
        self.assertEqual({c.get("max_budget_usd") for c in calls}, {5.0})
        self.assertEqual(results[-1].probe_id, "T2.8")
        self.assertEqual(results[-1].name, "R coding agent write + execute")
        prompt = calls[-1]["prompt"]
        self.assertIn("t28_probe.R", prompt)
        self.assertIn("cat(", prompt)
        self.assertIn("run_with_capture.sh", prompt)
        self.assertEqual(results[-1].verdict, Verdict.FAIL)  # no script was written by the fake


# --- D5: TD.9 local browser services ------------------------------------------------------------

def _stub_service(argv_tail, name="stub-http", short="st", secrets=()):
    return {"name": name, "binary": sys.executable, "short": short,
            "prepare": lambda work, port: list(secrets),
            "argv": lambda binary, port, work: [binary] + [a.format(port=port, work=work) for a in argv_tail]}


HTTP_STUB = ["-m", "http.server", "--bind", "127.0.0.1", "{port}", "--directory", "{work}"]


class LocalServicesTests(unittest.TestCase):
    def setUp(self):
        self.ev = _scratch(self, "td9") / "td9"

    def _stop_facts(self, r):
        for e in r.evidence:
            if e.command.startswith("process-group stop"):
                return json.loads(e.output)
        return None

    def test_http_stub_starts_answers_and_stops(self):
        r = sp.probe_local_services(self.ev, services=[_stub_service(HTTP_STUB)], launchers=())
        self.assertEqual((r.probe_id, r.tier), ("TD.9", "D"))
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertIn("stub-http: HTTP 200", r.detail)
        facts = self._stop_facts(r)
        self.assertEqual(facts["still_running"], 0)
        self.assertIn("SIGTERM", facts["signals"])
        # Only the scrubbed log remains; the work dir (HOME, XDG, TMPDIR) is gone.
        self.assertEqual(sorted(p.name for p in self.ev.iterdir()), ["stub-http.log"])
        port = int(r.evidence[0].output.split("port=")[1].split()[0])
        with socket.socket() as s:
            s.settimeout(1)
            self.assertNotEqual(s.connect_ex(("127.0.0.1", port)), 0)

    def test_no_answer_fails_with_output_and_is_killed(self):
        hang = ["-c", "import time; print('stub-start', flush=True); time.sleep(120)"]
        r = sp.probe_local_services(self.ev, services=[_stub_service(hang, name="hang")], launchers=(),
                                    timeout=2)
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("hang: no HTTP answer within 2s", r.detail)
        self.assertIn("stub-start", "\n".join(e.output for e in r.evidence))
        self.assertEqual(self._stop_facts(r)["still_running"], 0)
        self.assertTrue(sp.apply_hints([r])[0].hint)

    def test_early_exit_fails(self):
        boom = ["-c", "import sys; print('boom', flush=True); sys.exit(3)"]
        r = sp.probe_local_services(self.ev, services=[_stub_service(boom, name="boom")], launchers=())
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("boom: exited with code 3 before answering HTTP", r.detail)
        self.assertNotIn("retried once", "\n".join(e.note for e in r.evidence))  # no address-in-use: no retry

    # Quality review I4: the stub counts its starts in a file outside the work
    # dir (which is removed between attempts); it reports the address in use
    # on the first `fail_first` starts, then serves HTTP.
    ADDR_STUB = ("import sys, pathlib, http.server\n"
                 "c = pathlib.Path(sys.argv[2]); n = int(c.read_text()) if c.exists() else 0\n"
                 "c.write_text(str(n + 1))\n"
                 "if n < int(sys.argv[3]):\n"
                 "    print('Error: listen EADDRINUSE: address already in use 127.0.0.1:' + sys.argv[1], flush=True)\n"
                 "    sys.exit(1)\n"
                 "http.server.HTTPServer(('127.0.0.1', int(sys.argv[1])), "
                 "http.server.SimpleHTTPRequestHandler).serve_forever()\n")

    def test_address_in_use_is_retried_once_on_a_fresh_port(self):
        counter = self.ev.parent / "starts_once"
        r = sp.probe_local_services(self.ev, launchers=(), services=[
            _stub_service(["-c", self.ADDR_STUB, "{port}", str(counter), "1"], name="race")])
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertEqual(counter.read_text(), "2")
        retry = [e for e in r.evidence if "retried once on a fresh port" in e.note]
        self.assertEqual(len(retry), 1)
        self.assertIn("address already in use", retry[0].output)
        self.assertEqual(self._stop_facts(r)["still_running"], 0)
        self.assertEqual(sorted(p.name for p in self.ev.iterdir()), ["race.log"])

    def test_address_in_use_twice_fails_after_one_retry(self):
        counter = self.ev.parent / "starts_twice"
        r = sp.probe_local_services(self.ev, launchers=(), services=[
            _stub_service(["-c", self.ADDR_STUB, "{port}", str(counter), "9"], name="race")])
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("race: exited with code 1 before answering HTTP", r.detail)
        self.assertEqual(counter.read_text(), "2")

    def test_absent_binary_is_skip_and_mixed_is_pass(self):
        absent = {"name": "ghost", "binary": "daaf-td9-no-such-binary", "short": "gh",
                  "prepare": lambda w, p: [], "argv": lambda b, p, w: [b]}
        r = sp.probe_local_services(self.ev, services=[absent], launchers=())
        self.assertEqual(r.verdict, Verdict.SKIP)
        self.assertIn("ghost: SKIP (binary absent)", r.detail)
        r = sp.probe_local_services(self.ev, services=[absent, _stub_service(HTTP_STUB)], launchers=())
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertIn("ghost: SKIP (binary absent)", r.detail)

    def test_token_is_scrubbed_from_log_and_evidence(self):
        token = "td9" + "T" * 20 + "9" * 10
        say = ["-c", f"import time; print('token={token}', flush=True); time.sleep(120)"]
        r = sp.probe_local_services(self.ev, services=[_stub_service(say, name="tok", secrets=[token])],
                                    launchers=(), timeout=2)
        text = "\n".join(e.output for e in r.evidence) + (self.ev / "tok.log").read_text()
        self.assertNotIn(token, text)
        self.assertIn("<redacted:td9-token>", text)

    def test_child_env_is_redirected_under_the_work_dir(self):
        work = self.ev / "w"
        work.mkdir(parents=True)
        env = sp._td9_child_env({"HOME": "/home/real", "PASSWORD": "x", "PATH": "/usr/bin"}, work, 4242)
        for var in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME",
                    "XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP"):
            with self.subTest(var=var):
                self.assertTrue(env[var].startswith(str(work)), env[var])
                self.assertFalse(env[var].startswith("/tmp"))
        self.assertEqual((env["PORT"], env["PATH"]), ("4242", "/usr/bin"))
        self.assertNotIn("PASSWORD", env)
        self.assertEqual(stat.S_IMODE((work / "x" / "r").stat().st_mode), 0o700)

    def test_child_env_withholds_credential_names(self):
        # Review fix H4(b): neither service needs a credential; code-server runs
        # --auth none with a terminal that could read one.
        work = self.ev / "w"
        work.mkdir(parents=True)
        base = {"PATH": "/usr/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": "/home/real",
                "ANTHROPIC_API_KEY": "a" * 20, "OPENROUTER_TOKEN": "b" * 20, "CLIENT_SECRET": "c" * 20,
                "CLAUDE_CODE_OAUTH_TOKEN": "d" * 20, "DB_PASSWORD": "e" * 20, "SESSION_COOKIE": "f" * 20,
                "AWS_CREDENTIALS": "g" * 20, "PASSWORD": "h" * 20, "HASHED_PASSWORD": "i" * 20}
        secret_names = [k for k in base if k not in ("PATH", "LANG", "LC_ALL", "HOME")]
        env = sp._td9_child_env(base, work, 4242)
        for name in secret_names:
            with self.subTest(name=name):
                self.assertNotIn(name, env)
        self.assertEqual((env["PATH"], env["LANG"], env["LC_ALL"], env["PORT"]), ("/usr/bin", "C.UTF-8", "C.UTF-8", "4242"))
        self.assertTrue(env["HOME"].startswith(str(work)))
        # Without the packager's vocabulary the redaction test still strips the
        # KEY/TOKEN/SECRET/AUTH names, and PASSWORD is dropped by name.
        with mock.patch.dict(sys.modules, {"smoke_package": None}):
            env = sp._td9_child_env(base, work, 4242)
        for name in ("ANTHROPIC_API_KEY", "OPENROUTER_TOKEN", "CLIENT_SECRET", "CLAUDE_CODE_OAUTH_TOKEN",
                     "PASSWORD", "HASHED_PASSWORD"):
            with self.subTest(fallback=name):
                self.assertNotIn(name, env)

    def test_credentials_do_not_reach_the_service(self):
        probe = ("import os, sys, http.server; "
                 "print('seen=%s' % ('DAAF_TD9_TEST_API_KEY' in os.environ), flush=True); "
                 "http.server.HTTPServer(('127.0.0.1', int(sys.argv[1])), "
                 "http.server.SimpleHTTPRequestHandler).serve_forever()")
        env = {"PATH": os.environ.get("PATH", "/usr/bin"), "DAAF_TD9_TEST_API_KEY": "z" * 24}
        r = sp.probe_local_services(self.ev, env=env, services=[_stub_service(["-c", probe, "{port}"], name="env")],
                                    launchers=())
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        text = "\n".join(e.output for e in r.evidence)
        self.assertIn("seen=False", text)
        self.assertNotIn("seen=True", text)
        self.assertIn("1 credential-named env var(s) withheld", "\n".join(e.note for e in r.evidence))

    @unittest.skipUnless(shutil.which("bash"), "needs bash for bash -n")
    def test_launcher_wording_says_what_was_tested(self):
        # Review fix H4(a): "invoke the tested binaries" only when every service ran.
        base = self.ev.parent / "base_wording"
        (base / "scripts").mkdir(parents=True)
        (base / "scripts" / "good.sh").write_text('#!/usr/bin/env bash\nexec marimo edit "$D" --headless\n')
        launchers = (("marimo", "scripts/good.sh", sp.TD9_LAUNCHERS[0][2]),)
        absent = {"name": "ghost", "binary": "daaf-td9-no-such-binary", "short": "gh",
                  "prepare": lambda w, p: [], "argv": lambda b, p, w: [b]}
        r = sp.probe_local_services(self.ev, services=[absent], base_dir=str(base), launchers=launchers)
        self.assertEqual(r.verdict, Verdict.SKIP)
        self.assertIn("still call their binaries (no binary was present to test)", r.detail)
        self.assertNotIn("tested binaries", r.detail)
        r = sp.probe_local_services(self.ev, services=[absent, _stub_service(HTTP_STUB)], base_dir=str(base),
                                    launchers=launchers)
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertIn("(tested here: stub-http; absent, not tested: ghost)", r.detail)
        self.assertNotIn("tested binaries", r.detail)
        r = sp.probe_local_services(self.ev, services=[_stub_service(HTTP_STUB)], base_dir=str(base),
                                    launchers=launchers)
        self.assertIn("launchers pass bash -n and invoke the tested binaries", r.detail)

    def test_sigterm_ignoring_service_is_killed(self):
        # The SIGKILL rung of the stop ladder: the stub ignores SIGTERM before it
        # binds, so an HTTP answer proves the handler is in place.
        ignore = ("import signal, sys, http.server; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                  "http.server.HTTPServer(('127.0.0.1', int(sys.argv[1])), "
                  "http.server.SimpleHTTPRequestHandler).serve_forever()")
        with mock.patch.object(sp, "TD9_STOP_GRACE", 1):
            r = sp.probe_local_services(self.ev, services=[_stub_service(["-c", ignore, "{port}"], name="stubborn")],
                                        launchers=())
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        facts = self._stop_facts(r)
        self.assertEqual(facts["signals"], ["SIGTERM", "SIGKILL"])
        self.assertEqual(facts["still_running"], 0)
        self.assertEqual(facts["exit_code"], -9)

    def test_default_service_argv_is_loopback_and_offline(self):
        work = Path("/w")
        specs = {s["name"]: s for s in sp._td9_default_services()}
        mo = specs["marimo"]["argv"]("marimo", 4000, work)
        for flag in ("--host", "127.0.0.1", "--headless", "--skip-update-check", "--no-sandbox",
                     "--token-password-file"):
            self.assertIn(flag, mo)
        cs = specs["code-server"]["argv"]("code-server", 4001, work)
        for flag in ("127.0.0.1:4001", "--auth", "none", "--disable-telemetry", "--disable-update-check",
                     "--user-data-dir", "--extensions-dir", "--config"):
            self.assertIn(flag, cs)
        self.assertFalse(any(a.startswith("/tmp") for a in mo + cs))

    @unittest.skipUnless(shutil.which("bash"), "needs bash for bash -n")
    def test_static_launcher_check(self):
        base = self.ev.parent / "base"
        (base / "scripts").mkdir(parents=True)
        (base / "scripts" / "good.sh").write_text('#!/usr/bin/env bash\nexec marimo edit "$D" --headless\n')
        (base / "scripts" / "broken.sh").write_text("#!/usr/bin/env bash\nif then fi (\n")
        (base / "scripts" / "other.sh").write_text("#!/usr/bin/env bash\nexec jupyter lab\n")
        pattern = sp.TD9_LAUNCHERS[0][2]
        ok, _ = sp._td9_static_launchers(str(base), _which_from({"marimo"}),
                                         (("marimo", "scripts/good.sh", pattern),))
        self.assertEqual(ok, [])
        bad, _ = sp._td9_static_launchers(str(base), _which_from(set()),
                                          (("marimo", "scripts/broken.sh", pattern),
                                           ("marimo", "scripts/other.sh", pattern),
                                           ("marimo", "scripts/missing.sh", pattern)))
        self.assertTrue(any("bash -n scripts/broken.sh failed" in p for p in bad), bad)
        self.assertIn("scripts/other.sh no longer invokes `marimo`", bad)
        self.assertIn("scripts/missing.sh missing", bad)
        # The shipped launchers pass the same static check.
        shipped, _ = sp._td9_static_launchers(str(_REPO_ROOT), shutil.which)
        self.assertEqual(shipped, [])
        r = sp.probe_local_services(self.ev, services=[], base_dir=str(base),
                                    launchers=(("marimo", "scripts/other.sh", pattern),))
        self.assertEqual(r.verdict, Verdict.FAIL)

    def test_run_tier_d_always_runs_td9_last(self):
        ev = self.ev.parent / "tier_d"
        stub = _pr("X", Verdict.PASS, tier="D")
        with mock.patch.object(sp, "_run_battery_cmd", return_value=stub), \
             mock.patch.object(sp, "_run_import_smoke", return_value=stub), \
             mock.patch.object(sp, "probe_local_services", return_value=_pr("TD.9", Verdict.SKIP, tier="D")) as td9:
            out = sp.run_tier_d(False, 5, ev, route=rd.ROUTE_ANTHROPIC)
        self.assertEqual(out[-1].probe_id, "TD.9")
        self.assertEqual(td9.call_args.args[0], ev / "td9")

    def test_td1_timeout_has_a_floor(self):
        # The bats battery outgrew the 600 s Tier D default: TD.1 always gets at
        # least TD1_MIN_TIMEOUT_S, and a larger --timeout still wins. TD.7 keeps
        # its own 900 s floor; the other batteries take the timeout as given.
        self.assertEqual(sp.TD1_MIN_TIMEOUT_S, 1800)
        ev = self.ev.parent / "tier_d_floor"
        stub = _pr("X", Verdict.PASS, tier="D")
        for given, td1_expected, td7_expected in ((600, 1800, 900), (5, 1800, 900), (2400, 2400, 2400)):
            with self.subTest(timeout=given), \
                 mock.patch.object(sp, "_run_battery_cmd", return_value=stub) as bat, \
                 mock.patch.object(sp, "_run_import_smoke", return_value=stub), \
                 mock.patch.object(sp, "probe_local_services", return_value=stub):
                sp.run_tier_d(False, given, ev, route=rd.ROUTE_CHATGPT)
                timeouts = {c.args[0]: c.args[3] for c in bat.call_args_list}
                self.assertEqual(timeouts["TD.1"], td1_expected)
                self.assertEqual(timeouts["TD.7"], td7_expected)
                self.assertEqual(timeouts["TD.3"], given)

    def test_td1_hint_tells_a_timeout_from_a_failing_test(self):
        ev = self.ev.parent / "tier_d_hint"
        stub = _pr("X", Verdict.PASS, tier="D")
        for detail, expect, reject in (
                ("bats tests/bash timed out after 1800s.", "A timeout, not a failing test", "for the failing bats"),
                ("bats tests/bash exited 1.", "for the failing bats test", "A timeout")):
            def battery(pid, name, *args, **kwargs):
                if pid == "TD.1":
                    return _pr("TD.1", Verdict.FAIL, tier="D", detail=detail)
                return _pr(pid, Verdict.PASS, tier="D")
            with self.subTest(detail=detail), \
                 mock.patch.object(sp, "_run_battery_cmd", side_effect=battery), \
                 mock.patch.object(sp, "_run_import_smoke", return_value=stub), \
                 mock.patch.object(sp, "probe_local_services", return_value=stub):
                td1 = [r for r in sp.run_tier_d(False, 600, ev) if r.probe_id == "TD.1"][0]
                self.assertIn(expect, td1.hint)
                self.assertNotIn(reject, td1.hint)
                if expect.startswith("A timeout"):
                    self.assertIn(f"above the {sp.TD1_MIN_TIMEOUT_S} s floor", td1.hint)
                    self.assertIn("bats tests/bash/", td1.hint)

    def test_timeout_help_names_the_floors(self):
        # Review fix H5: --help states the TD.1 and TD.7 floors the code applies.
        help_text = " ".join(runner.build_parser().format_help().split())
        self.assertIn(f"TD.1 always gets at least {sp.TD1_MIN_TIMEOUT_S}", help_text)
        self.assertIn(f"TD.7 at least {sp.TD7_MIN_TIMEOUT_S}", help_text)
        self.assertEqual(sp.TD7_MIN_TIMEOUT_S, 900)


# --- Review fix H1: SIGTERM / SIGHUP unwind like Ctrl+C ---------------------------------------

def _process_alive(pid):
    """True while pid runs (a zombie counts as gone); Linux /proc."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[-1].split()[0]
    except (OSError, IndexError):
        return False
    return state != "Z"


class TerminationSignalTests(unittest.TestCase):
    def test_guard_raises_once_then_defers(self):
        err = runner.TerminationSignal(signal.SIGTERM)
        self.assertIsInstance(err, SystemExit)
        self.assertEqual((err.code, err.signame, str(err)), (143, "SIGTERM", "received SIGTERM"))
        if hasattr(signal, "SIGHUP"):
            self.assertEqual(runner.TerminationSignal(signal.SIGHUP).code, 129)
        guard = runner._TerminationGuard()
        with self.assertRaises(runner.TerminationSignal):
            guard._handle(signal.SIGTERM, None)
        self.assertIsNone(guard._handle(signal.SIGTERM, None))  # the second one never raises
        self.assertEqual(guard.deferred, signal.SIGTERM)
        guard = runner._TerminationGuard()
        guard.finishing()
        self.assertIsNone(guard._handle(signal.SIGTERM, None))  # the report is being written
        self.assertEqual(guard.deferred, signal.SIGTERM)

    def _main(self, tier_n):
        report = _scratch(self, "term") / "report"
        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))
            stack.enter_context(mock.patch.object(runner, "collect_versions", return_value={}))
            stack.enter_context(mock.patch.object(runner, "git_sha", return_value="0" * 40))
            stack.enter_context(mock.patch("sys.stdout", io.StringIO()))
            err = stack.enter_context(mock.patch("sys.stderr", io.StringIO()))
            stack.enter_context(mock.patch.object(sp, "run_tier_n", tier_n))
            rc = runner.main(["--route", "anthropic-subscription", "--tiers", "N", "--yes", "--no-package",
                              "--report-dir", str(report)])
        return rc, json.loads((report / "report.json").read_text()), err.getvalue()

    def test_a_termination_signal_writes_the_report_and_exits_143(self):
        before = {s: signal.getsignal(s) for s in runner.TERMINATION_SIGNALS}
        rc, data, stderr = self._main(mock.Mock(side_effect=runner.TerminationSignal(signal.SIGTERM)))
        self.assertEqual(rc, 143)
        crash = [r for r in data["results"] if r["probe_id"] == "RUN.CRASH"]
        self.assertEqual(len(crash), 1)
        self.assertIn("received SIGTERM", crash[0]["detail"])
        self.assertIn("Not a deployment verdict", crash[0]["hint"])
        self.assertIn("interrupted by SIGTERM", stderr)
        # main() restores whatever handlers were installed before it ran.
        self.assertEqual({s: signal.getsignal(s) for s in runner.TERMINATION_SIGNALS}, before)

    def test_ctrl_c_is_unchanged(self):
        rc, data, _ = self._main(mock.Mock(side_effect=KeyboardInterrupt()))
        self.assertEqual(rc, 130)
        crash = [r for r in data["results"] if r["probe_id"] == "RUN.CRASH"][0]
        self.assertIn("KeyboardInterrupt", crash["detail"])
        self.assertIn("A harness exception", crash["hint"])

    @unittest.skipUnless(sys.platform.startswith("linux") and Path("/proc").is_dir() and hasattr(signal, "SIGHUP"),
                         "needs Linux /proc and SIGHUP")
    def test_signal_stops_td9_services_and_writes_the_report(self):
        # The reviewer's repro, end to end: a runner process holds a TD.9 service
        # (start_new_session=True) mid-poll and receives SIGTERM or SIGHUP. Its
        # TD.9 cleanup must run (no orphan), and the report must be written.
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=sig.name):
                d = _scratch(self, "term_e2e")
                pidfile, report = d / "service.pid", d / "report"
                child = d / "runner_child.py"
                service = (f"import os, time; open({str(pidfile)!r}, 'w').write(str(os.getpid())); "
                           "time.sleep(300)")
                child.write_text(
                    "import sys\n"
                    f"sys.path[:0] = [{str(_REPO_ROOT)!r}, {str(_REPO_ROOT / 'scripts' / 'deploy_smoke')!r}]\n"
                    "import run_deploy_smoke as runner\n"
                    "import smoke_probes as sp\n"
                    f"SERVICE = {service!r}\n"
                    "stub = {'name': 'stub', 'binary': sys.executable, 'short': 'st',\n"
                    "        'prepare': lambda work, port: [],\n"
                    "        'argv': lambda binary, port, work: [binary, '-c', SERVICE]}\n"
                    "sp.run_tier_d = lambda *a, **k: [sp.probe_local_services(k['evidence_dir'] / 'td9',\n"
                    "                                 services=[stub], launchers=(), timeout=120)]\n"
                    "runner.collect_versions = lambda base=None: {}\n"
                    "runner.git_sha = lambda: '0' * 40\n"
                    "sys.exit(runner.main(['--route', 'anthropic-subscription', '--tiers', 'D', '--yes',\n"
                    f"                       '--no-package', '--report-dir', {str(report)!r}]))\n")
                env = {k: v for k, v in os.environ.items()
                       if k not in ("DAAF_PROVIDER_SHIM", "SHIM_BACKEND_MODE", "ANTHROPIC_BASE_URL")}
                proc = subprocess.Popen([sys.executable, "-B", str(child)], stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, env=env)
                service_pid = None

                def _cleanup(proc=proc, pidfile=pidfile):
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=10)
                    if pidfile.is_file() and pidfile.read_text().strip():
                        pid = int(pidfile.read_text())
                        if _process_alive(pid):
                            os.kill(pid, signal.SIGKILL)
                self.addCleanup(_cleanup)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline and proc.poll() is None:
                    if pidfile.is_file() and pidfile.read_text().strip():
                        service_pid = int(pidfile.read_text())
                        break
                    time.sleep(0.1)
                self.assertIsNotNone(service_pid, "the TD.9 stub service never started")
                self.assertTrue(_process_alive(service_pid))
                proc.send_signal(sig)
                out, _ = proc.communicate(timeout=60)
                text = out.decode("utf-8", "replace")
                self.assertEqual(proc.returncode, 128 + sig, text)
                self.assertFalse(_process_alive(service_pid), "TD.9's service outlived the runner")
                data = json.loads((report / "report.json").read_text())
                crash = [r for r in data["results"] if r["probe_id"] == "RUN.CRASH"]
                self.assertEqual(len(crash), 1, text)
                self.assertIn(f"received {sig.name}", crash[0]["detail"])
                self.assertIn(f"interrupted by {sig.name}", text)
                td9 = report / "evidence" / "tier_d" / "td9"
                self.assertFalse((td9 / "st").exists(), "the TD.9 work dir was not removed")
                self.assertTrue((td9 / "stub.log").is_file())

    def test_sighup_detaches_only_terminal_descriptors(self):
        # Re-review W1: a real SIGHUP points the descriptors that were terminals
        # at install() at os.devnull, once; SIGTERM never does, and neither does
        # a SIGHUP when output goes to a pipe or file (no terminal descriptors).
        if not hasattr(signal, "SIGHUP"):
            self.skipTest("no SIGHUP on this platform")
        with mock.patch.object(runner, "_detach_console") as detach:
            guard = runner._TerminationGuard()
            guard.console_ttys = (1, 2)
            with self.assertRaises(runner.TerminationSignal):
                guard._handle(signal.SIGTERM, None)
            detach.assert_not_called()
            guard._handle(signal.SIGHUP, None)  # deferred: the first signal already raised
            detach.assert_called_once_with((1, 2))
            guard._handle(signal.SIGHUP, None)
            detach.assert_called_once()
            guard = runner._TerminationGuard()  # console_ttys () until install(): nothing to detach
            with self.assertRaises(runner.TerminationSignal):
                guard._handle(signal.SIGHUP, None)
            self.assertEqual(detach.call_count, 1)

    def test_unwind_console_drops_oserror_and_propagates_the_rest(self):
        # Re-review W1: during the unwind a console write that raises OSError
        # (EIO from a hung-up terminal) detaches that descriptor and is dropped;
        # any other exception still propagates.
        class _Dead:
            def __init__(self, exc):
                self.exc = exc

            def write(self, text):
                raise self.exc

            def flush(self):
                raise self.exc

            def fileno(self):
                return 7

        with mock.patch.object(runner, "_detach_console") as detach:
            dead = runner._UnwindConsole(_Dead(OSError(5, "Input/output error")))
            self.assertEqual(dead.write("abc"), 3)
            dead.flush()
            self.assertEqual(detach.call_args_list, [mock.call((7,)), mock.call((7,))])
            with self.assertRaises(ValueError):
                runner._UnwindConsole(_Dead(ValueError("not a console error"))).write("x")
        live = io.StringIO()
        wrapped = runner._UnwindConsole(live)
        print("kept", file=wrapped)
        self.assertEqual(live.getvalue(), "kept\n")
        self.assertIs(wrapped.getvalue.__self__, live)  # other attributes come from the stream
        out, err = sys.stdout, sys.stderr
        saved = runner._protect_console()
        try:
            self.assertIsInstance(sys.stdout, runner._UnwindConsole)
            self.assertIsInstance(sys.stderr, runner._UnwindConsole)
        finally:
            runner._restore_console(saved)
        self.assertEqual((sys.stdout, sys.stderr), (out, err))

    @unittest.skipUnless(sys.platform.startswith("linux") and Path("/proc").is_dir()
                         and hasattr(signal, "SIGHUP") and pty is not None,
                         "needs Linux /proc, SIGHUP and the pty module")
    def test_closed_terminal_still_packages_and_exits_129(self):
        # Re-review W1, end to end: the runner holds a TD.9 stub service on a
        # pseudo-terminal, and the test closes the terminal end (the pty
        # master). The kernel sends SIGHUP, and from then on every write to the
        # terminal fails with EIO, which used to stop the unwind at its first
        # print: no package, no exit 129. Now the service is stopped, the report
        # carries RUN.CRASH, the package step runs and the exit code is 129.
        d = _scratch(self, "hangup_pty")
        pidfile, report, marker = d / "service.pid", d / "report", d / "package.marker"
        child = d / "runner_child.py"
        service = (f"import os, time; open({str(pidfile)!r}, 'w').write(str(os.getpid())); "
                   "time.sleep(300)")
        child.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path[:0] = [{str(_REPO_ROOT)!r}, {str(_REPO_ROOT / 'scripts' / 'deploy_smoke')!r}]\n"
            "import run_deploy_smoke as runner\n"
            "import smoke_probes as sp\n"
            f"SERVICE = {service!r}\n"
            "stub = {'name': 'stub', 'binary': sys.executable, 'short': 'st',\n"
            "        'prepare': lambda work, port: [],\n"
            "        'argv': lambda binary, port, work: [binary, '-c', SERVICE]}\n"
            "sp.run_tier_d = lambda *a, **k: [sp.probe_local_services(k['evidence_dir'] / 'td9',\n"
            "                                 services=[stub], launchers=(), timeout=120)]\n"
            "runner.collect_versions = lambda base=None: {}\n"
            "runner.git_sha = lambda: '0' * 40\n"
            "def fake_package(*a, **k):\n"
            f"    Path({str(marker)!r}).write_text('package step reached')\n"
            f"    return {{'warnings': ['a warning printed to the dead terminal'], 'zip_path': Path({str(marker)!r})}}\n"
            "runner.smoke_package.build_package = fake_package\n"
            "sys.exit(runner.main(['--route', 'anthropic-subscription', '--tiers', 'D', '--yes',\n"
            f"                       '--report-dir', {str(report)!r}]))\n")
        env = {k: v for k, v in os.environ.items()
               if k not in ("DAAF_PROVIDER_SHIM", "SHIM_BACKEND_MODE", "ANTHROPIC_BASE_URL")}
        pid, master = pty.fork()
        if pid == 0:  # the child: session leader, stdin/stdout/stderr on the pty
            try:
                os.execve(sys.executable, [sys.executable, "-B", str(child)], env)
            finally:
                os._exit(127)
        state = {"master": master, "status": None}

        def _cleanup():
            if state["master"] is not None:
                os.close(state["master"])
                state["master"] = None
            if state["status"] is None:
                try:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                except (ProcessLookupError, ChildProcessError):
                    pass
            if pidfile.is_file() and pidfile.read_text().strip():
                spid = int(pidfile.read_text())
                if _process_alive(spid):
                    os.kill(spid, signal.SIGKILL)
        self.addCleanup(_cleanup)

        # Drain the terminal (a full pty would block the child) until the service runs.
        service_pid = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    os.read(master, 65536)
                except OSError:
                    pass
            if pidfile.is_file() and pidfile.read_text().strip():
                service_pid = int(pidfile.read_text())
                break
        self.assertIsNotNone(service_pid, "the TD.9 stub service never started")
        self.assertTrue(_process_alive(service_pid))

        os.close(master)  # the hang-up
        state["master"] = None
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            wpid, status = os.waitpid(pid, os.WNOHANG)
            if wpid:
                state["status"] = status
                break
            time.sleep(0.05)
        self.assertIsNotNone(state["status"], "the runner did not exit within 60 s of the hang-up")
        self.assertEqual(os.waitstatus_to_exitcode(state["status"]), 129)
        self.assertFalse(_process_alive(service_pid), "TD.9's service outlived the runner")
        data = json.loads((report / "report.json").read_text())
        crash = [r for r in data["results"] if r["probe_id"] == "RUN.CRASH"]
        self.assertEqual(len(crash), 1)
        self.assertIn("received SIGHUP", crash[0]["detail"])
        self.assertTrue(marker.is_file(), "the package step was not reached after the hang-up")
        self.assertFalse((report / "evidence" / "tier_d" / "td9" / "st").exists(),
                         "the TD.9 work dir was not removed")


if __name__ == "__main__":
    unittest.main()
