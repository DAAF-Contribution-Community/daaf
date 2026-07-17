"""Deterministic schema-v1/v2 DAAFBench viewer-template rendering tests.

Every fixture, generated HTML file, and extracted JavaScript check file lives
beneath ``benchmarks/.test_scratch``. The suite exercises the template's actual
JavaScript render functions with Node.js; it does not make network or model
calls and does not require a browser package.
"""

import io
import json
import re
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from benchmarks.scripts import generate_results_viewer_v2 as viewer


TEST_SCRATCH = Path("/daaf/benchmarks/.test_scratch")
TEMPLATE_PATH = Path("/daaf/benchmarks/scripts/viewer_template.html")
SECRET_SENTINELS = (
    "VIEWER_RAW_HEALTH_SECRET",
    "VIEWER_RAW_EXECUTOR_SECRET",
    "VIEWER_RAW_ENVIRONMENT_SECRET",
    "VIEWER_PROBE_SECRET",
)


class _StructureProbe(HTMLParser):
    """Count document-boundary tags using only standard-library parsing."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.starts = []
        self.ends = []

    def handle_starttag(self, tag, attrs):
        self.starts.append(tag)

    def handle_endtag(self, tag):
        self.ends.append(tag)


class ViewerSchemaRenderingTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        TEST_SCRATCH.mkdir(parents=True)
        self.results_dir = TEST_SCRATCH / "combined_results"
        self.results_dir.mkdir()
        self._write_legacy_set(self.results_dir, "20260101_010101")
        self._write_subscription_set(self.results_dir, "20260715_120000")
        self._write_probe_container(self.results_dir)
        self.data_bundle, self.precomputed = self._load_payload(self.results_dir)
        self.generated_html = viewer.generate_html(self.data_bundle, self.precomputed)

    def tearDown(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        self.assertFalse(TEST_SCRATCH.exists())

    def _write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_legacy_set(self, results_dir, timestamp):
        root = results_dir / timestamp
        self._write_json(root / "manifest.json", {
            "daaf_git_sha": "a" * 40,
            "config": {"reps": 1, "parallel": False},
            "models": [{
                "id": "claude-sonnet-4-6",
                "name": "Legacy Model",
                "provider": "anthropic",
            }],
        })
        self._write_json(root / "summary.json", {
            "total_runs": 1,
            "errored_runs": 0,
            "total_cost_usd": 0,
            "wall_time_s": 2,
            "by_model": {
                "Legacy Model": {
                    "avg_cost_usd": 0,
                    "criteria": {
                        "orchestrator_skill_loaded": {
                            "passed": 1, "total": 1, "rate": 1.0,
                        },
                        "all_criteria": {"passed": 1, "total": 1, "rate": 1.0},
                    },
                },
            },
        })
        self._write_json(root / "runs" / "legacy_0" / "result.json", {
            "case_id": "mc-legacy",
            "model": "Legacy Model",
            "model_id": "claude-sonnet-4-6",
            "provider": "anthropic",
            "rep": 0,
            "session_id": "legacy-session",
            "turns": 1,
            "computed_cost_usd": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "duration_s": 0,
            "timed_out": False,
            "criteria": {"orchestrator_skill_loaded": {"passed": True}},
        })

    def _write_subscription_set(self, results_dir, timestamp):
        root = results_dir / timestamp
        self._write_json(root / "manifest.json", {
            "schema_version": 2,
            "daaf_git_sha": "b" * 40,
            "raw_environment": {"token": SECRET_SENTINELS[2]},
            "config": {"reps": 1, "parallel": False},
            "models": [{
                "key": "gpt-56-luna-chatgpt",
                "id": "gpt-5.6-luna",
                "name": "Luna Subscription",
                "display_name": "Luna Subscription",
                "provider": "chatgpt-subscription",
                "effort_level": "high",
                "context_window_tokens": 370_000,
                "billing": {"actual_billing_treatment": "not_separately_billed"},
            }],
        })
        self._write_json(root / "summary.json", {
            "schema_version": 2,
            "total_runs": 1,
            "errored_runs": 0,
            "total_cost_usd": None,
            "wall_time_s": 3,
            "accounting_coverage": {
                "exact": 0,
                "scenario_only": 1,
                "unavailable": 0,
                "legacy_numeric": 0,
            },
            "purity_coverage": {
                "verified": 1,
                "failed": 0,
                "unverifiable": 0,
            },
            "subagent_behavior": {"criterion_names": ["subagent_writes_script"]},
            "by_model": {
                "Luna Subscription": {
                    "avg_cost_usd": None,
                    "accounting_coverage": {
                        "exact": 0,
                        "scenario_only": 1,
                        "unavailable": 0,
                        "legacy_numeric": 0,
                    },
                    "purity_coverage": {
                        "verified": 1,
                        "failed": 0,
                        "unverifiable": 0,
                    },
                    "criteria": {
                        "agent_dispatched": {"passed": 1, "total": 1, "rate": 1.0},
                        "all_criteria": {"passed": 1, "total": 1, "rate": 1.0},
                    },
                },
            },
        })
        self._write_json(root / "runs" / "subscription_0" / "result.json", {
            "schema_version": 2,
            "case_id": "dc-subscription",
            "model": "Luna Subscription",
            "model_id": "gpt-5.6-luna",
            "provider": "chatgpt-subscription",
            "rep": 0,
            "session_id": "subscription-session",
            "turns": 1,
            "computed_cost_usd": None,
            "duration_s": 0,
            "timed_out": False,
            "criteria": {"agent_dispatched": {"passed": True}},
            "subagent_criteria": {"subagent_writes_script": {"passed": True}},
            "provenance": {
                "route_type": "chatgpt_subscription_shim",
                "provider": "chatgpt-subscription",
                "endpoint_origin": "http://127.0.0.1:4141",
                "backend_mode": "chatgpt",
                "backend": "https://chatgpt.com/backend-api/codex",
                "shim_version": "1.2.5",
                "sanitizer_enabled": True,
                "sanitizer_condition": "deployed_default",
                "auth_store_readable": True,
                "reasoning_effort": "high",
                "text_verbosity": "high",
                "captured_at": "2026-07-15T12:00:00+00:00",
                "raw_health_payload": {"secret": SECRET_SENTINELS[0]},
            },
            "model_identity": {
                "benchmark_key": "gpt-56-luna-chatgpt",
                "requested_model_id": "gpt-5.6-luna",
                "claude_cli_model_usage_ids": ["gpt-5.6-luna"],
                "backend_confirmed_model_id": None,
                "executor_raw_json": {"secret": SECRET_SENTINELS[1]},
            },
            "usage_observed": {
                "input_tokens": 123,
                "input_semantics": "shim_reported_total_input_cache_breakdown_unavailable",
                "input_includes_cache_tokens": True,
                "output_tokens": 0,
                "output_includes_reasoning": True,
                "cache_read_tokens": None,
                "cache_write_tokens": None,
                "reasoning_tokens": None,
                "max_request_input_tokens": 0,
                "pricing_context_tier": None,
                "source": "claude_cli.modelUsage",
                "completeness": "partial",
                "incompleteness_reasons": [
                    "cache_read_tokens_unavailable",
                    "reasoning_tokens_unavailable",
                ],
            },
            "actual_billing": {
                "access_type": "chatgpt_subscription",
                "charge_status": "not_separately_billed",
                "actual_marginal_charge_usd": None,
            },
            "api_equivalent": {
                "cost_usd": None,
                "calculation_status": "scenario_only",
                "short_context_uncached_scenario_usd": 0,
                "long_context_uncached_scenario_usd": 0.0009,
                "scenario_assumptions": ["all input treated as uncached"],
                "incompleteness_reasons": ["request_tier_unavailable"],
                "price_source_url": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
                "price_schedule_accessed_at": "2026-07-15",
                "currency": "USD",
                "context_threshold_input_tokens": 272_000,
                "context_tier": None,
                "not_invoiced": True,
            },
            "subscription_capacity": {
                "before": None,
                "after": None,
                "delta_observed": 0,
                "credits_calculated": 0,
                "credit_usd_value": None,
            },
            "child_model_purity": {
                "requested_child_model_id": "gpt-5.6-luna",
                "observed_child_model_ids_raw": ["gpt-5.6-luna"],
                "comparison_child_model_ids": ["gpt-5.6-luna"],
                "normalization_applied": False,
                "comparison_rule": "exact_string_equality_no_alias_normalization",
                "purity_status": "verified",
                "evidence_source": "child_transcript_assistant_message.model",
                "evidence_boundary": "CLI-observed; not backend-confirmed",
                "child_transcript_count": 1,
                "readable_child_transcript_count": 1,
                "incompleteness_reason": None,
            },
            "raw_json": {"secret": SECRET_SENTINELS[1]},
        })

    def _write_probe_container(self, results_dir):
        self._write_json(results_dir / "probes" / "probe-a" / "probe.json", {
            "artifact_type": "daafbench_model_route_probe",
            "schema_version": 2,
            "secret": SECRET_SENTINELS[3],
        })

    def _load_payload(self, results_dir):
        with redirect_stderr(io.StringIO()):
            result_sets = viewer.load_result_sets(str(results_dir))
            runs, anth_tokens = viewer.load_runs(str(results_dir), result_sets, cases={})
        data_bundle = viewer.build_data_bundle(
            result_sets,
            cases={},
            runs=runs,
            transcripts={},
            subagent_transcripts={},
            model_pricing={},
            inline_transcripts=True,
        )
        precomputed = viewer.build_precomputed(
            result_sets,
            cases={},
            runs=runs,
            generation_params={"fixture": True},
            model_pricing={},
            anth_token_totals=anth_tokens,
            reconciliation=None,
        )
        return data_bundle, precomputed

    def _inline_scripts(self, html):
        return re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, flags=re.DOTALL)

    def _node_render_payload(self):
        scripts = self._inline_scripts(self.generated_html)
        data_script = next(script for script in scripts if "const DATA =" in script)
        main_script = next(
            script for script in scripts
            if "function renderRunDetail" in script and "function init()" in script
        )
        self.assertEqual(1, main_script.count("\ninit();\n"))
        main_script = main_script.replace(
            "\ninit();\n",
            "\nglobalThis.__DAAF_RENDER__={renderRunDetail:renderRunDetail," \
            "renderProvenance:renderProvenance," \
            "costOmissionNoteHtml:costOmissionNoteHtml};\n",
        )
        node_source = r'''
function escapeHtml(value){
  return String(value).replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/\"/g,"&quot;").replace(/'/g,"&#39;");
}
var document={
  createElement:function(){
    var node={_text:""};
    Object.defineProperty(node,"textContent",{
      set:function(value){node._text=value===null||value===undefined?"":String(value);}
    });
    Object.defineProperty(node,"innerHTML",{get:function(){return escapeHtml(node._text);}});
    return node;
  },
  getElementById:function(){return {textContent:"",innerHTML:"",classList:{add:function(){},remove:function(){},toggle:function(){}},addEventListener:function(){}};},
  querySelectorAll:function(){return [];},
  querySelector:function(){return null;},
  body:{classList:{add:function(){},remove:function(){}}},
  createDocumentFragment:function(){return {appendChild:function(){}};}
};
var location={protocol:"file:",hash:""};
var history={replaceState:function(){}};
var window={requestIdleCallback:null,IntersectionObserver:null,addEventListener:function(){},requestAnimationFrame:function(fn){fn();},scrollTo:function(){}};
''' + data_script + "\n" + main_script + r'''
var legacy=DATA.runs.filter(function(run){return run.legacy_schema;})[0];
var subscription=DATA.runs.filter(function(run){return run.provider==="chatgpt-subscription";})[0];
var exact=JSON.parse(JSON.stringify(subscription));
exact.api_equivalent.cost_usd=0.012345;
exact.api_equivalent.short_context_uncached_scenario_usd=null;
exact.api_equivalent.long_context_uncached_scenario_usd=null;
exact.api_equivalent.calculation_status="exact";
var actualZero=JSON.parse(JSON.stringify(subscription));
actualZero.actual_billing.actual_marginal_charge_usd=0;
var purity={};
["verified","failed","unverifiable"].forEach(function(state){
  var variant=JSON.parse(JSON.stringify(subscription));
  variant.child_model_purity.purity_status=state;
  if(state==="unverifiable") variant.child_model_purity.incompleteness_reason="child_transcript_unreadable";
  purity[state]=__DAAF_RENDER__.renderRunDetail(variant);
});
var provenanceContainer={innerHTML:""};
__DAAF_RENDER__.renderProvenance(provenanceContainer);
process.stdout.write(JSON.stringify({
  legacy:__DAAF_RENDER__.renderRunDetail(legacy),
  subscription:__DAAF_RENDER__.renderRunDetail(subscription),
  exact:__DAAF_RENDER__.renderRunDetail(exact),
  actualZero:__DAAF_RENDER__.renderRunDetail(actualZero),
  purity:purity,
  omission:__DAAF_RENDER__.costOmissionNoteHtml(),
  provenance:provenanceContainer.innerHTML
}));
'''
        runner_path = TEST_SCRATCH / "render_template.js"
        runner_path.write_text(node_source, encoding="utf-8")
        completed = subprocess.run(
            ["node", str(runner_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(completed.stdout)

    def _run_full_single_file_generation(self, schema):
        root = TEST_SCRATCH / f"full_schema_v{schema}"
        results_dir = root / "results"
        datasets_dir = root / "datasets"
        results_dir.mkdir(parents=True)
        datasets_dir.mkdir()
        if schema == 1:
            self._write_legacy_set(results_dir, "20260101_010101")
        else:
            self._write_subscription_set(results_dir, "20260715_120000")
            self._write_probe_container(results_dir)
        output_path = root / f"schema_v{schema}_viewer.html"
        argv = [str(Path(viewer.__file__)), "--single-file", str(output_path)]
        with patch.object(sys, "argv", argv), \
                patch.object(
                    viewer,
                    "resolve_paths",
                    return_value=(
                        str(root), str(results_dir), str(datasets_dir), str(output_path)
                    ),
                ), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            viewer.main()
        self.assertTrue(output_path.is_file())
        return output_path, output_path.read_text(encoding="utf-8")

    def test_schema_v1_detail_renders_without_schema_v2_sections(self):
        rendered = self._node_render_payload()["legacy"]
        self.assertIn("mc-legacy", rendered)
        self.assertIn("Duration: 0.0s", rendered)
        self.assertNotIn("Route and deployment condition", rendered)
        self.assertNotIn("Actual billing", rendered)
        self.assertNotIn("Phase-3 child-model purity", rendered)

    def test_subscription_detail_contains_all_schema_v2_evidence_labels(self):
        rendered = self._node_render_payload()["subscription"]
        for label in (
            "Route and deployment condition",
            "chatgpt-subscription",
            "chatgpt_subscription_shim",
            "Tool sanitizer",
            "Enabled",
            "deployed_default",
            "Auth store",
            "Readable",
            "Model identity evidence",
            "gpt-56-luna-chatgpt",
            "Backend-confirmed ID",
            "backend confirmation is unavailable",
            "Private-backend alias caveat",
            "Usage and telemetry completeness",
            "claude_cli.modelUsage",
            "Incompleteness reasons",
            "Non-additive reasoning",
            "Actual billing",
            "API-equivalent accounting",
            "Subscription capacity",
            "Phase-3 child-model purity",
        ):
            self.assertIn(label, rendered)

    def test_explicit_zero_and_null_have_distinct_rendering(self):
        rendered = self._node_render_payload()["subscription"]
        self.assertIn("0 tokens", rendered)
        self.assertIn("Observed delta", rendered)
        self.assertIn("Calculated credits", rendered)
        self.assertIn("$0.00 USD", rendered)
        self.assertIn("Cache read", rendered)
        self.assertIn("Not observed", rendered)
        self.assertIn("Calculated credits do not imply a USD value", rendered)

        actual_start = rendered.index("Actual billing")
        api_start = rendered.index("API-equivalent accounting")
        actual_ledger = rendered[actual_start:api_start]
        self.assertIn("Unavailable — no marginal USD charge was reported", actual_ledger)
        self.assertNotIn("$0.00", actual_ledger)
        self.assertNotIn("free", actual_ledger.lower())

        actual_zero = self._node_render_payload()["actualZero"]
        zero_start = actual_zero.index("Actual billing")
        zero_end = actual_zero.index("API-equivalent accounting")
        self.assertIn("$0.00 USD", actual_zero[zero_start:zero_end])

    def test_exact_and_scenario_only_api_equivalent_paths_are_distinct(self):
        rendered = self._node_render_payload()
        scenario = rendered["subscription"]
        exact = rendered["exact"]
        self.assertIn("scenario only", scenario)
        self.assertIn("Short-context scenario", scenario)
        self.assertIn("$0.00 USD", scenario)
        self.assertIn("$0.000900 USD", scenario)
        self.assertIn("Exact equivalent", scenario)
        self.assertIn("Unavailable", scenario)

        self.assertIn("$0.0123 USD", exact)
        self.assertIn("Calculation status", exact)
        self.assertIn("exact", exact)
        exact_start = exact.index("API-equivalent accounting")
        exact_ledger = exact[exact_start:]
        self.assertNotIn("Short-context scenario", exact_ledger)
        self.assertNotIn("Long-context scenario", exact_ledger)

    def test_not_invoiced_copy_and_purity_states_include_icons_and_text(self):
        rendered = self._node_render_payload()
        self.assertIn("not_invoiced", rendered["subscription"])
        self.assertIn("Not invoiced", rendered["subscription"])
        expected = {
            "verified": ("✓", "Verified"),
            "failed": ("✕", "Failed"),
            "unverifiable": ("?", "Unverifiable"),
        }
        for state, (icon, label) in expected.items():
            detail = rendered["purity"][state]
            self.assertIn(icon, detail)
            self.assertIn(label, detail)
            self.assertIn("CLI child-transcript observed, not backend-confirmed", detail)
            self.assertIn("exact_string_equality_no_alias_normalization", detail)
            self.assertIn("Not applied — exact comparison", detail)
            self.assertIn("Raw observed IDs", detail)
        self.assertIn("child transcript unreadable", rendered["purity"]["unverifiable"])

    def test_cost_omission_note_retains_behavioral_scores(self):
        rendered = self._node_render_payload()
        omission = rendered["omission"]
        self.assertIn("Luna Subscription", omission)
        self.assertIn("remains in behavioral score views", omission)
        self.assertIn("omitted from billing-grade cost charts", omission)
        self.assertIn("not invoiced", omission)
        self.assertIn("Behavioral scores retained", rendered["provenance"])
        self.assertIn("Excluded from billing-grade cost views", rendered["provenance"])

    def test_provenance_surfaces_schema_routes_and_summary_coverage(self):
        provenance = self._node_render_payload()["provenance"]
        self.assertIn("v1", provenance)
        self.assertIn("legacy schema v1", provenance)
        self.assertIn("default absent version", provenance)
        self.assertIn("v2", provenance)
        self.assertIn("schema v2", provenance)
        self.assertIn("chatgpt-subscription", provenance)
        self.assertIn("chatgpt_subscription_shim", provenance)
        self.assertIn("scenario only: 1", provenance)
        self.assertIn("verified: 1", provenance)
        self.assertIn("failed: 0", provenance)
        self.assertIn("Archived total", provenance)

    def test_probe_and_secret_sentinels_never_enter_generated_html(self):
        timestamps = [entry["timestamp"] for entry in self.data_bundle["result_sets"]]
        self.assertEqual(["20260101_010101", "20260715_120000"], timestamps)
        self.assertNotIn("probes", timestamps)
        for sentinel in SECRET_SENTINELS:
            self.assertNotIn(sentinel, self.generated_html)
        for forbidden_key in (
            "raw_health_payload",
            "executor_raw_json",
            "raw_environment",
            "raw_json",
        ):
            self.assertNotIn(forbidden_key, self.generated_html)

    def test_inline_javascript_passes_node_syntax_check(self):
        scripts = self._inline_scripts(self.generated_html)
        self.assertGreaterEqual(len(scripts), 3)
        js_path = TEST_SCRATCH / "generated_inline_scripts.js"
        js_path.write_text("\n\n".join(scripts), encoding="utf-8")
        completed = subprocess.run(
            ["node", "--check", str(js_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_new_evidence_styles_reuse_existing_theme_tokens(self):
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        start = template.index("/* Schema-v2 run evidence:")
        end = template.index("/* Transcript */", start)
        evidence_css = template[start:end]
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}", evidence_css))
        for token in (
            "var(--surface-0)",
            "var(--surface-1)",
            "var(--border-1)",
            "var(--text-1)",
            "var(--text-2)",
            "var(--text-3)",
            "var(--c-pass)",
            "var(--c-fail-light)",
            "var(--c-partial)",
        ):
            self.assertIn(token, evidence_css)

    def test_full_schema_v1_and_v2_single_file_generation_and_structure(self):
        for schema in (1, 2):
            with self.subTest(schema=schema):
                output_path, html = self._run_full_single_file_generation(schema)
                self.assertGreater(output_path.stat().st_size, 10_000)
                self.assertTrue(html.startswith("<!DOCTYPE html>"))
                self.assertNotIn("__DATA_JSON__", html)
                self.assertNotIn("__PRECOMPUTED_JSON__", html)
                self.assertIn(f'"schema_version":{schema}', html)
                parser = _StructureProbe()
                parser.feed(html)
                parser.close()
                self.assertEqual(1, parser.starts.count("html"))
                self.assertEqual(1, parser.ends.count("html"))
                self.assertEqual(1, parser.starts.count("body"))
                self.assertEqual(1, parser.ends.count("body"))
                for sentinel in SECRET_SENTINELS:
                    self.assertNotIn(sentinel, html)


if __name__ == "__main__":
    unittest.main()
