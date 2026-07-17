"""Deterministic regression tests for the G1R Phase-B harness fixes.

Covers, with no backend/model call:
  B1 — repetition-safe workspaces (guarded per-run sandbox wipe + unconditional
       workspace containment instruction).
  B2 — child-model purity as a non-scoring validity gate (invalid runs excluded
       from score rollups, retained, disclosed).
  B3 — shared manifest provenance stamping across all four phase runners.

All scratch lives under benchmarks/ (no /tmp writes).
"""

import hashlib
import json
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from benchmarks.harness import artifacts
from benchmarks.harness.artifacts import (
    CONDITION_ID,
    EMPTY_DIFF_SHA256,
    GOLDEN_GENERATION_ID,
    SCHEMA_VERSION,
    claude_code_version,
    git_worktree_state,
    golden_checksums,
    is_scorable,
    manifest_provenance,
    run_validity,
    validity_coverage,
)
from benchmarks.harness.models import ModelConfig, PricingConfig
from benchmarks.scripts import (
    run_dispatch_compliance,
    run_mode_classification,
    run_post_confirmation,
    run_skill_routing,
)


TEST_SCRATCH = Path("/daaf/benchmarks/.test_scratch_g1r")
SANDBOX_ROOT = Path(run_dispatch_compliance.SANDBOX_ROOT)
REAL_GOLDEN = "benchmarks/golden/dispatch_compliance/ad_hoc_initialized.jsonl"


def legacy_model():
    return ModelConfig(
        id="claude-sonnet-4-6",
        name="Sonnet 4.6",
        provider="anthropic",
        pricing=PricingConfig(input=3.0, output=15.0, cached_input=0.3),
    )


# --- B1: repetition-safe workspaces ---


class WorkspaceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.run_sandbox = SANDBOX_ROOT / "run_g1r-b1-test"
        shutil.rmtree(self.run_sandbox, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.run_sandbox, ignore_errors=True)

    def test_prepare_run_sandbox_wipes_prior_run_artifacts(self):
        # Seed a stale artifact from a "prior run".
        self.run_sandbox.mkdir(parents=True, exist_ok=True)
        stale = self.run_sandbox / "leftover_from_prior_run.txt"
        stale.write_text("stale")
        self.assertTrue(stale.exists())

        returned = run_dispatch_compliance.prepare_run_sandbox(str(self.run_sandbox))

        self.assertEqual(self.run_sandbox, returned)
        self.assertTrue(self.run_sandbox.is_dir())
        self.assertFalse(stale.exists())
        # A repeated wipe on the fresh sandbox is idempotent.
        run_dispatch_compliance.prepare_run_sandbox(str(self.run_sandbox))
        self.assertEqual([], list(self.run_sandbox.iterdir()))

    def test_prepare_run_sandbox_refuses_paths_outside_sandbox_root(self):
        # A legitimate /daaf/research project directory must never be wiped.
        for unsafe in (
            "/daaf/research/2026-07-16_AdHoc_MonteCarlo_Simulation",
            "/daaf",
            "/daaf/benchmarks",
            "/daaf/benchmarks/_sandboxes_evil",  # prefix-adjacent, not under root
        ):
            with self.subTest(path=unsafe):
                with self.assertRaises(ValueError):
                    run_dispatch_compliance.prepare_run_sandbox(unsafe)

    def test_prepare_fixtures_adds_containment_for_a_no_fixture_case(self):
        # dc-01 style: prompt has no test_fixtures/ path, yet must still get a
        # workspace and the containment instruction (the pre-fix gap).
        case = SimpleNamespace(
            id="dc-01",
            prompt="Please dispatch a research-executor to run a Monte Carlo sim.",
        )
        run_dispatch_compliance.prepare_run_sandbox(str(self.run_sandbox))
        result = run_dispatch_compliance.prepare_fixtures(case, str(self.run_sandbox))

        self.assertNotEqual(case.prompt, result.prompt)
        self.assertIn(str(self.run_sandbox), result.prompt)
        self.assertIn("must live under", result.prompt)
        self.assertIn("do not create", result.prompt)
        workspace = self.run_sandbox / "workspace"
        self.assertTrue(workspace.is_dir())
        self.assertTrue((workspace / "scripts" / "run_with_capture.sh").exists())


# --- B2: purity validity gate ---


class PurityValidityGateTests(unittest.TestCase):
    def test_run_validity_marks_only_failed_purity_invalid(self):
        self.assertEqual(
            {"status": "invalid", "reason": "child_model_purity_failed"},
            run_validity({"child_model_purity": {"purity_status": "failed"}}),
        )
        for status in ("verified", "unverifiable"):
            self.assertEqual(
                {"status": "valid", "reason": None},
                run_validity({"child_model_purity": {"purity_status": status}}),
            )
        # Absent purity evidence is treated as valid (non-dispatching runs).
        self.assertEqual({"status": "valid", "reason": None}, run_validity({}))

    def test_validity_coverage_and_is_scorable(self):
        records = [
            {"validity": {"status": "valid"}},
            {"validity": {"status": "invalid"}},
            {},  # missing validity -> valid
        ]
        self.assertEqual({"valid": 2, "invalid": 1}, validity_coverage(records))
        self.assertTrue(is_scorable(records[0]))
        self.assertFalse(is_scorable(records[1]))
        self.assertTrue(is_scorable(records[2]))

    def test_dispatch_archive_excludes_invalid_runs_but_retains_and_discloses(self):
        model = legacy_model()
        case = SimpleNamespace(
            id="dc-01", subcategory="research_executor",
            golden_checkpoint=REAL_GOLDEN, expected={},
        )

        def make(rep, purity_status, crit_passed, validity_status):
            record = run_dispatch_compliance._error_result(case, model, rep, "boom")
            record["criteria"] = [
                {
                    "name": "agent_dispatched",
                    "passed": crit_passed,
                    "tier": "tier1",
                    "detail": "",
                }
            ]
            record["child_model_purity"] = {"purity_status": purity_status}
            record["validity"] = {
                "status": validity_status,
                "reason": (
                    "child_model_purity_failed"
                    if validity_status == "invalid"
                    else None
                ),
            }
            record["error"] = None
            return record

        records = [
            make(0, "verified", True, "valid"),     # valid, passing
            make(1, "unverifiable", False, "valid"), # valid, failing
            make(2, "failed", True, "invalid"),      # invalid, passing (excluded)
        ]
        args = SimpleNamespace(
            reps=3, sequential=True, delay=0, timeout=300,
            test_id="dc-01", models=model.name,
        )
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        TEST_SCRATCH.mkdir(parents=True)
        try:
            with patch.object(run_dispatch_compliance, "BASE_DIR", TEST_SCRATCH), \
                    patch.object(run_dispatch_compliance, "get_git_sha", return_value="sha"), \
                    patch.object(
                        run_dispatch_compliance, "manifest_provenance",
                        return_value={"golden_generation_id": "G1"},
                    ):
                output_dir = run_dispatch_compliance.archive_results(
                    records, [model], [case], args, 1.0
                )

            summary = json.loads((output_dir / "summary.json").read_text())
            # Invalid run excluded from score rollups: all_criteria total == 2.
            all_crit = summary["by_model"][model.name]["criteria"]["all_criteria"]
            self.assertEqual(2, all_crit["total"])
            self.assertEqual(1, all_crit["passed"])
            # Disclosure retained over ALL runs.
            self.assertEqual(
                {"valid": 2, "invalid": 1}, summary["validity_coverage"]
            )
            self.assertEqual(
                {"verified": 1, "failed": 1, "unverifiable": 1},
                summary["purity_coverage"],
            )
            # All three runs retained on disk (nothing deleted).
            run_dirs = sorted((output_dir / "runs").glob("*/result.json"))
            self.assertEqual(3, len(run_dirs))
        finally:
            shutil.rmtree(TEST_SCRATCH, ignore_errors=True)


# --- B3: manifest provenance stamping ---


class ManifestProvenanceTests(unittest.TestCase):
    def test_git_worktree_state_dirty_clean_and_failure(self):
        with patch.object(
            artifacts, "_git_output_bytes",
            side_effect=[b" M benchmarks/x\n", b"diff-bytes"],
        ):
            dirty, diff_sha = git_worktree_state("/daaf")
        self.assertTrue(dirty)
        self.assertEqual(hashlib.sha256(b"diff-bytes").hexdigest(), diff_sha)

        with patch.object(artifacts, "_git_output_bytes", side_effect=[b"", b""]):
            dirty, diff_sha = git_worktree_state("/daaf")
        self.assertFalse(dirty)
        self.assertEqual(EMPTY_DIFF_SHA256, diff_sha)

        with patch.object(artifacts, "_git_output_bytes", side_effect=[None, None]):
            self.assertEqual((None, None), git_worktree_state("/daaf"))

    def test_golden_checksums_hash_real_golden_and_skip_falsy(self):
        checksums = golden_checksums([REAL_GOLDEN, None, ""])
        expected = hashlib.sha256(Path("/daaf", REAL_GOLDEN).read_bytes()).hexdigest()
        self.assertEqual({REAL_GOLDEN: expected}, checksums)
        self.assertEqual({}, golden_checksums([None, ""]))

    def test_claude_code_version_failsoft_returns_none(self):
        with patch.object(
            artifacts.subprocess, "run", side_effect=FileNotFoundError()
        ):
            self.assertIsNone(claude_code_version())

    def test_manifest_provenance_reuses_run_record_route_provenance(self):
        route = {"route_type": "chatgpt_subscription_shim", "sanitizer_enabled": True}
        records = [{"provenance": None}, {"provenance": route}, {"provenance": {}}]
        with patch.object(artifacts, "git_worktree_state", return_value=(True, "d")), \
                patch.object(artifacts, "claude_code_version", return_value="1.2.3"):
            block = manifest_provenance(
                golden_checkpoints=[REAL_GOLDEN], run_records=records
            )
        self.assertTrue(block["git_dirty"])
        self.assertEqual("d", block["worktree_diff_sha256"])
        self.assertEqual(GOLDEN_GENERATION_ID, block["golden_generation_id"])
        self.assertEqual(CONDITION_ID, block["condition_id"])
        self.assertEqual("1.2.3", block["claude_code_version"])
        self.assertEqual(route, block["route_provenance"])
        self.assertIn(REAL_GOLDEN, block["golden_checksums"])

    def test_all_four_runner_manifests_carry_provenance_fields(self):
        model = legacy_model()
        stub = {
            "git_dirty": False,
            "worktree_diff_sha256": EMPTY_DIFF_SHA256,
            "golden_generation_id": GOLDEN_GENERATION_ID,
            "golden_checksums": {},
            "condition_id": CONDITION_ID,
            "claude_code_version": "stub-1.0",
            "route_provenance": None,
        }
        runners = {
            run_mode_classification: SimpleNamespace(
                id="mc-01", subcategory="x",
                expected={"mode": "data_lookup"}, golden_checkpoint=None,
            ),
            run_post_confirmation: SimpleNamespace(
                id="pc-01", subcategory="x",
                expected={}, golden_checkpoint=REAL_GOLDEN,
            ),
            run_dispatch_compliance: SimpleNamespace(
                id="dc-01", subcategory="x",
                expected={}, golden_checkpoint=REAL_GOLDEN,
            ),
            run_skill_routing: SimpleNamespace(
                id="sr-01", subcategory="x",
                expected={}, golden_checkpoint=REAL_GOLDEN,
            ),
        }
        args = SimpleNamespace(
            reps=1, sequential=True, delay=0, timeout=300,
            test_id=None, models=None,
        )
        for module, case in runners.items():
            with self.subTest(module=module.__name__):
                shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
                TEST_SCRATCH.mkdir(parents=True)
                try:
                    record = module._error_result(case, model, 0, "boom")
                    with patch.object(module, "BASE_DIR", TEST_SCRATCH), \
                            patch.object(module, "get_git_sha", return_value="sha"), \
                            patch.object(
                                module, "manifest_provenance", return_value=stub
                            ):
                        output_dir = module.archive_results(
                            [record], [model], [case], args, 1.0
                        )
                    manifest = json.loads((output_dir / "manifest.json").read_text())
                    self.assertEqual(SCHEMA_VERSION, manifest["schema_version"])
                    self.assertEqual("sha", manifest["daaf_git_sha"])
                    for key in stub:
                        self.assertIn(key, manifest)
                    self.assertEqual(CONDITION_ID, manifest["condition_id"])
                finally:
                    shutil.rmtree(TEST_SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
