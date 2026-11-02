"""Provider-free unit tests for the deploy smoke v2 routes and probes
(design DESIGN_smoke_v2_2026-10-13.md §2, §3, §12, §13).

Standard-library unittest + unittest.mock only. No network, no model calls, no
credential files: every live or network seam (_run_cmd, _http_reach,
_read_local_health, execute_smoke_run) is replaced by a fake, and every fixture
lives under scripts/scratch/ (never /tmp) and is removed by addCleanup.

Run (file-first, via a captured runner script):
  python3 -m unittest discover -s /daaf/tests/python -p 'test_deploy_smoke_probes_v2.py'
"""

import json
import os
import shutil
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "scripts" / "deploy_smoke")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import route_detection as rd  # noqa: E402
import smoke_probes as sp  # noqa: E402
from route_detection import Verdict  # noqa: E402

_SCRATCH = _REPO_ROOT / "scripts" / "scratch"


def _scratch(test, prefix):
    d = _SCRATCH / f"{prefix}_{uuid.uuid4().hex[:10]}"
    d.mkdir(parents=True)
    test.addCleanup(shutil.rmtree, d, True)
    return d


SHIM = {"DAAF_PROVIDER_SHIM": "openai", "ANTHROPIC_BASE_URL": "http://127.0.0.1:4141"}
GPT_ALIASES = {"ANTHROPIC_DEFAULT_FABLE_MODEL": "gpt-6-sol[1m]", "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-6-sol[1m]",
               "ANTHROPIC_DEFAULT_SONNET_MODEL": "gpt-6-luna[1m]", "ANTHROPIC_DEFAULT_HAIKU_MODEL": "gpt-6-luna[1m]"}


def _use(tid, name, inp, model="m"):
    return {"type": "assistant", "message": {"model": model, "content": [
        {"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def _res(tid, text="ok", is_error=False):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": is_error, "content": text}]}}


class FiveRouteDetectionTests(unittest.TestCase):
    def test_all_routes_is_five_long_and_shim_routes_unchanged(self):
        self.assertEqual(len(rd.ALL_ROUTES), 5)
        self.assertIn(rd.ROUTE_ANTHROPIC_API, rd.ALL_ROUTES)
        self.assertEqual(rd.ROUTE_ANTHROPIC_API, "anthropic-api")
        self.assertEqual(rd.SHIM_ROUTES, frozenset({rd.ROUTE_OPENAI_API, rd.ROUTE_CHATGPT}))

    def test_detection_matrix_including_near_misses(self):
        cases = [
            ({}, rd.ROUTE_ANTHROPIC),
            ({"ANTHROPIC_API_KEY": ""}, rd.ROUTE_ANTHROPIC),                 # present-and-empty
            ({"CLAUDE_CODE_OAUTH_TOKEN": "x" * 20}, rd.ROUTE_ANTHROPIC),
            ({"ANTHROPIC_API_KEY": "k" * 20}, rd.ROUTE_ANTHROPIC_API),
            ({"anthropic_api_key": "k" * 20}, rd.ROUTE_ANTHROPIC),           # wrong case: not the variable
            ({"ANTHROPIC_API_KEY": "k", "ANTHROPIC_BASE_URL": "https://openrouter.ai/api"}, rd.ROUTE_OPENROUTER),
            (dict(SHIM, SHIM_BACKEND_MODE="chatgpt", ANTHROPIC_API_KEY="k"), rd.ROUTE_CHATGPT),
            (dict(SHIM, SHIM_BACKEND_MODE="openai"), rd.ROUTE_OPENAI_API),
            (dict(SHIM, SHIM_BACKEND_MODE="ChatGPT"), rd.ROUTE_ANTHROPIC),  # near miss: not a shim lane
        ]
        for env, want in cases:
            with self.subTest(env=sorted(env)):
                self.assertEqual(rd.detect_route(env), want)

    def test_api_route_assertion_and_main_model_compatibility(self):
        env = {"ANTHROPIC_API_KEY": "k" * 20, "ANTHROPIC_MODEL": "claude-opus-5-5"}
        info = rd.build_route_info(env, asserted_route="anthropic-subscription")
        self.assertEqual(rd.probe_route_detection(info).verdict, Verdict.FAIL)
        self.assertEqual(rd.resolve_main_model(env).compatibility, "compatible")
        t03 = rd.probe_env_coherence(rd.build_route_info(env), env)
        self.assertEqual(t03.verdict, Verdict.PASS, t03.detail)
        self.assertNotIn("k" * 20, json.dumps([e.to_dict() for e in t03.evidence]))


class FingerprintFixTests(unittest.TestCase):
    def test_context_tokens_not_redacted_and_not_scrubbed(self):
        env = {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "919000", "ANTHROPIC_AUTH_TOKEN": "secret-value-xyz"}
        fp = rd.env_fingerprint(env)
        self.assertEqual(fp["CLAUDE_CODE_MAX_CONTEXT_TOKENS"], "919000")
        self.assertEqual(fp["ANTHROPIC_AUTH_TOKEN"], "<redacted:set>")
        text = rd.scrub_secret_values("window 919000 token secret-value-xyz", env)
        self.assertIn("919000", text)
        self.assertNotIn("secret-value-xyz", text)
        # A non-numeric *_TOKENS value stays redacted by name.
        self.assertEqual(rd.redact_env_value("X_TOKENS", "abc123def"), "<redacted:set>")

    def test_pdf_mode_and_auto_mode_server_recorded_and_bounded(self):
        self.assertIn("SHIM_PDF_MODE", rd.FINGERPRINT_VARS)
        self.assertIn("CLAUDE_CODE_AUTO_MODE_SERVER", rd.FINGERPRINT_VARS)
        fp = rd.env_fingerprint({"SHIM_PDF_MODE": "omit", "CLAUDE_CODE_AUTO_MODE_SERVER": "evil\ntext"})
        self.assertEqual(fp["SHIM_PDF_MODE"], "omit")
        self.assertEqual(fp["CLAUDE_CODE_AUTO_MODE_SERVER"], "<invalid:unsupported>")

    def test_strip_ansi(self):
        self.assertEqual(rd.strip_ansi("\x1b[1;32mOK\x1b[0m bar"), "OK bar")

    def test_strip_ansi_escaped_forms(self):
        # subagent-bar.sh emits JSON, so jq writes ESC as the text "\u001b".
        line = '{"id":"t","content":"\\u001b[38;5;75msearch-agent\\u001b[0m\\u001b[90m · x\\u001b[0m"}'
        out = rd.strip_ansi(line)
        self.assertEqual(out, '{"id":"t","content":"search-agent · x"}')
        self.assertEqual(json.loads(out)["content"], "search-agent · x")
        for esc in ("\\x1b", "\\x1B", "\\033", "\\e", "\\u001B"):
            self.assertEqual(rd.strip_ansi(f"{esc}[1;32mOK{esc}[0m"), "OK", esc)
        self.assertEqual(rd.strip_ansi("C:\\u001b-path [x]"), "C:\\u001b-path [x]")  # no CSI body: kept


class CredentialOverlapTests(unittest.TestCase):
    def _t016(self, env, asserted=""):
        return rd.probe_credential_overlap(rd.build_route_info(env, asserted_route=asserted), env)

    def test_matrix(self):
        key, oauth, tok = {"ANTHROPIC_API_KEY": "k" * 20}, {"CLAUDE_CODE_OAUTH_TOKEN": "o" * 20}, {
            "ANTHROPIC_AUTH_TOKEN": "t" * 20}
        cases = [
            ({}, "", Verdict.PASS),
            (oauth, "", Verdict.PASS),
            (key, "", Verdict.PASS),                                   # detected anthropic-api
            (key, "anthropic-subscription", Verdict.FAIL),             # stated sub + key -> bills the key
            (dict(key, **oauth), "anthropic-api", Verdict.WARN),
            (tok, "", Verdict.FAIL),
            (dict(key, **tok), "anthropic-api", Verdict.FAIL),
            (dict(SHIM, SHIM_BACKEND_MODE="chatgpt", **tok), "", Verdict.SKIP),
        ]
        for env, asserted, want in cases:
            with self.subTest(env=sorted(env), asserted=asserted):
                r = self._t016(env, asserted)
                self.assertEqual(r.verdict, want, r.detail)
                self.assertNotIn("k" * 20, r.detail + json.dumps([e.to_dict() for e in r.evidence]))


class AliasCompletenessTests(unittest.TestCase):
    def test_matrix(self):
        chat = dict(SHIM, SHIM_BACKEND_MODE="chatgpt")
        orr = {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "ANTHROPIC_MODEL": "openai/gpt-6-astra"}
        cases = [
            (dict(chat, **GPT_ALIASES), Verdict.PASS),
            (dict(chat, **{k: v for k, v in GPT_ALIASES.items() if "HAIKU" not in k}), Verdict.FAIL),
            (dict(chat, **dict(GPT_ALIASES, ANTHROPIC_DEFAULT_HAIKU_MODEL="claude-haiku-4-5")), Verdict.FAIL),
            ({"ANTHROPIC_MODEL": "claude-opus-5-5"}, Verdict.SKIP),
            (orr, Verdict.WARN),
            (dict(orr, **dict(GPT_ALIASES, ANTHROPIC_DEFAULT_HAIKU_MODEL="anthropic/claude-haiku-4.5")), Verdict.PASS),
        ]
        for env, want in cases:
            with self.subTest(env=sorted(env)):
                r = rd.probe_alias_completeness(rd.build_route_info(env), env)
                self.assertEqual(r.verdict, want, r.detail)
                if want != Verdict.SKIP:
                    self.assertIn("Settings `env` mappings were not checked", r.detail)

    def test_settings_overlay_counts_and_overrides(self):
        chat = dict(SHIM, SHIM_BACKEND_MODE="chatgpt")
        info = rd.build_route_info(chat)
        overlay = {k: (v, "project settings") for k, v in GPT_ALIASES.items()}
        r = rd.probe_alias_completeness(info, chat, settings_overlay=overlay)
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertNotIn("not checked", r.detail)
        self.assertIn("(project settings)", r.evidence[0].output)
        # A settings value wins over the process env, as in a real session.
        env = dict(chat, **GPT_ALIASES)
        bad = {"ANTHROPIC_DEFAULT_HAIKU_MODEL": ("claude-haiku-4-5", "local settings")}
        self.assertEqual(rd.probe_alias_completeness(info, env, settings_overlay=bad).verdict, Verdict.FAIL)

    def test_collect_alias_settings_reads_project_and_local_files(self):
        root = _scratch(self, "aliasset")
        (root / ".claude").mkdir()
        (root / ".claude" / "settings.json").write_text(json.dumps({"env": dict(GPT_ALIASES)}))
        (root / ".claude" / "settings.local.json").write_text(json.dumps(
            {"env": {"ANTHROPIC_DEFAULT_HAIKU_MODEL": "gpt-6-sol[1m]"}}))
        home = _scratch(self, "aliashome")
        overlay = sp.collect_alias_settings({"HOME": str(home)}, base_dir=str(root))
        self.assertEqual(overlay["ANTHROPIC_DEFAULT_OPUS_MODEL"], ("gpt-6-sol[1m]", "project settings"))
        self.assertEqual(overlay["ANTHROPIC_DEFAULT_HAIKU_MODEL"], ("gpt-6-sol[1m]", "local settings"))
        self.assertEqual(sp.collect_alias_settings({"HOME": str(home)}, base_dir=str(home)), {})


class StaleDaemonTests(unittest.TestCase):
    PAYLOAD = {"service": "daaf-anthropic-openai-shim", "status": "ok", "backend_mode": "chatgpt",
               "version": "1.4.6", "sanitize_tools": True, "codex_home_present": True,
               "gpt_service_tier": {"backend_mode": "chatgpt", "requested_tier_vocabulary": "priority",
                                    "policy": {"status": "ok", "backend_mode": "chatgpt", "enabled": False,
                                               "effective": False},
                                    "native_fast_disabled": True, "latest_terminal": None}}

    def _probe(self, expected):
        with mock.patch.object(sp, "_read_local_health", return_value=dict(self.PAYLOAD)):
            return sp.probe_shim_health(rd.RouteInfo(rd.ROUTE_CHATGPT), expected_version=expected)

    def test_compare(self):
        self.assertEqual(self._probe("1.4.6").verdict, Verdict.PASS)
        stale = self._probe("1.4.9")
        self.assertEqual(stale.verdict, Verdict.FAIL)
        self.assertIn("stale", stale.detail)
        self.assertIn("restart it yourself", stale.detail)
        self.assertTrue(stale.hint)
        self.assertEqual(self._probe(sp._SOURCE_VERSION_UNREADABLE).verdict, Verdict.FAIL)
        self.assertEqual(self._probe(None).verdict, Verdict.PASS)  # comparison not requested

    def test_source_version_parse(self):
        d = _scratch(self, "srcver")
        (d / "shim.py").write_text('x = 1\nSHIM_VERSION = "9.9.9"\nSHIM_VERSION = "0.0.0"\n')
        self.assertEqual(sp.source_shim_version(d / "shim.py"), "9.9.9")
        (d / "bad.py").write_text('SHIM_VERSION = "1.0 bad"\n')
        self.assertEqual(sp.source_shim_version(d / "bad.py"), sp._SOURCE_VERSION_UNREADABLE)
        self.assertEqual(sp.source_shim_version(d / "missing.py"), sp._SOURCE_VERSION_UNREADABLE)


class ShimLogScanTests(unittest.TestCase):
    SECRET_LINE = "2026-10-13 10:00:05,001 INFO req_id=r1 phase=x | headers: x-codex-turn-state=SENTINEL-OPAQUE-123"
    LOG = [
        "2026-10-13 09:00:00,000 INFO req_id=- phase=- shim v1.4.8 starting port=4141",
        "2026-10-13 09:00:01,000 INFO req_id=a phase=t event=request_parsed model=claude-haiku-4-5 tools=0",
        "2026-10-13 10:00:00,000 INFO req_id=- phase=- shim v1.4.9 starting port=4141",
        "2026-10-13 10:00:01,000 INFO req_id=b phase=t event=request_parsed model=gpt-6-sol msgs=2 tools=22",
        "2026-10-13 10:00:02,000 INFO req_id=b phase=terminal event=terminal outcome=success model=gpt-6-sol "
        "stream=n msgs=2 tools=0 attempts=1 retries=0 backend_code=-",
        "2026-10-13 10:00:03,000 INFO req_id=c phase=terminal event=terminal outcome=error model=gpt-6-astra "
        "stream=y msgs=4 tools=22 attempts=1 retries=0 backend_code=excessive_json_whitespace",
        "2026-10-13 10:00:04,000 INFO req_id=d phase=terminal event=terminal outcome=success model=gpt-6-astra "
        "stream=y msgs=4 tools=22 attempts=2 retry_reason=tool_argument_whitespace backend_code=-",
        "2026-10-13 10:00:06,000 WARNING req_id=e phase=t chatgpt-lane claude-slug fast-fail: model rejected",
        "2026-10-13 10:00:07,000 INFO req_id=f phase=terminal event=terminal outcome=error backend_code=unsupported_value",
    ]

    def test_counts_reset_at_daemon_start_and_window(self):
        counts = sp.scan_shim_log(self.LOG + [self.SECRET_LINE])
        self.assertEqual(counts["daemon_starts_seen"], 2)
        self.assertEqual(counts["claude_named_requests"], 0)   # the claude request predates the restart
        self.assertEqual(counts["claude_slug_fast_fail"], 1)
        self.assertEqual(counts["unrecovered_whitespace"], 1)
        self.assertEqual(counts["recovered_whitespace_retries"], 1)
        self.assertEqual(counts["unsupported_value"], 1)
        self.assertEqual(counts["turn_state_header_lines"], 1)
        self.assertEqual(counts["classifier_terminals"], 1)
        windowed = sp.scan_shim_log(self.LOG, since="2026-10-13 10:00:03", until="2026-10-13 10:00:04")
        self.assertEqual(windowed["lines_in_window"], 2)
        self.assertEqual(windowed["classifier_terminals"], 0)

    def test_verdicts_and_no_line_content_in_evidence(self):
        d = _scratch(self, "shimlog")
        log = d / "shim.log"
        log.write_text("\n".join(self.LOG + [self.SECRET_LINE]) + "\n")
        r = sp.apply_hints([sp.probe_shim_log_scan(rd.ROUTE_CHATGPT, log_path=log, tier="post")])[0]
        self.assertEqual(r.verdict, Verdict.FAIL)  # header leak after daemon start
        blob = json.dumps(r.to_dict())
        for fragment in ("SENTINEL-OPAQUE-123", "req_id=", "gpt-6-sol", "headers:"):
            self.assertNotIn(fragment, blob)
        self.assertTrue(r.hint)
        clean = d / "clean.log"
        clean.write_text("\n".join(self.LOG[2:5]) + "\n")
        self.assertEqual(sp.probe_shim_log_scan(rd.ROUTE_OPENAI_API, log_path=clean, tier="post").verdict,
                         Verdict.PASS)
        self.assertEqual(sp._evaluate_shim_log({"claude_slug_fast_fail": 2})[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_shim_log({"insufficient_quota": 1})[0], Verdict.FAIL)
        self.assertEqual(sp.probe_shim_log_scan(rd.ROUTE_ANTHROPIC, log_path=log).verdict, Verdict.SKIP)
        self.assertEqual(sp.probe_shim_log_scan(rd.ROUTE_ANTHROPIC, log_path=log, tier="post").verdict,
                         Verdict.SKIP)

    def test_quota_and_billing_codes_count_as_insufficient_quota(self):
        # Shim 1.4.11 classifies usage_not_included and four OpenAI billing codes as
        # "backend quota or plan limit reached", like insufficient_quota. Each one
        # counts under the single insufficient_quota signal (name kept for evidence
        # comparability) and fails the post-run scan.
        start = "2026-10-14 09:00:00,000 INFO req_id=- phase=- shim v1.4.11 starting port=4141"
        codes = ("insufficient_quota", "usage_not_included", "credit_balance_exhausted",
                 "organization_spend_limit_exceeded", "project_spend_limit_exceeded",
                 "organization_usage_limit_exceeded")
        self.assertEqual(sp._SHIM_QUOTA_CODES, codes)
        for code in codes:
            with self.subTest(code=code):
                line = ("2026-10-14 09:00:01,000 INFO req_id=q phase=terminal event=terminal "
                        f"outcome=error model=gpt-6-sol stream=n attempts=1 retries=0 "
                        f"backend_type=billing_fixture_type backend_code={code}")
                counts = sp.scan_shim_log([start, line])
                self.assertEqual(counts["insufficient_quota"], 1)
                d = _scratch(self, "shimlogquota")
                log = d / "shim.log"
                log.write_text(start + "\n" + line + "\n")
                r = sp.probe_shim_log_scan(rd.ROUTE_OPENAI_API, log_path=log, tier="post")
                self.assertEqual(r.verdict, Verdict.FAIL, r.detail)
                self.assertIn("insufficient_quota=1", r.detail)
        other = ("2026-10-14 09:00:02,000 INFO req_id=r phase=terminal event=terminal outcome=error "
                 "model=gpt-6-sol stream=n attempts=1 retries=0 backend_code=rate_limit_exceeded")
        self.assertEqual(sp.scan_shim_log([start, other])["insufficient_quota"], 0)

    def test_tier0_history_is_info_only(self):
        # Pre-run history: stale header lines and Claude-slug fast-fails must never
        # FAIL or WARN a healthy install; the counts are reported, the verdict INFO.
        d = _scratch(self, "shimlog0")
        log = d / "shim.log"
        log.write_text("\n".join(self.LOG + [self.SECRET_LINE]) + "\n")
        r = sp.apply_hints([sp.probe_shim_log_scan(rd.ROUTE_CHATGPT, log_path=log)])[0]
        self.assertEqual((r.probe_id, r.tier, r.verdict), ("T0.20", "0", Verdict.INFO))
        self.assertIn("Pre-run history", r.detail)
        self.assertIn("Would read FAIL", r.detail)
        self.assertIn("turn_state_header_lines=1", r.detail)
        self.assertEqual(r.hint, "")                     # INFO carries no remediation hint
        self.assertNotIn("SENTINEL-OPAQUE-123", json.dumps(r.to_dict()))
        missing = sp.probe_shim_log_scan(rd.ROUTE_CHATGPT, log_path=d / "absent.log")
        self.assertEqual(missing.verdict, Verdict.INFO)
        self.assertEqual(sp.probe_shim_log_scan(rd.ROUTE_CHATGPT, log_path=d / "absent.log", tier="post").verdict,
                         Verdict.WARN)

    def test_post_run_scan_is_bounded_to_the_run_window(self):
        # The header line (10:00:05) predates the run start: the post-run verdict
        # judges only the window, so it is not counted there.
        d = _scratch(self, "shimlogpost")
        log = d / "shim.log"
        log.write_text("\n".join(self.LOG[:5] + [self.SECRET_LINE] + [
            "2026-10-13 10:30:00,000 INFO req_id=g phase=terminal event=terminal outcome=success "
            "model=gpt-6-sol stream=y msgs=3 tools=22 attempts=1 backend_code=-"]) + "\n")
        r = sp.probe_shim_log_scan(rd.ROUTE_CHATGPT, since="2026-10-13 10:20:00", log_path=log, tier="post",
                                   name="Shim-log scan (post-run)")
        self.assertEqual((r.tier, r.verdict), ("post", Verdict.PASS), r.detail)
        self.assertIn('"lines_in_window": 1', r.evidence[0].output)
        self.assertIn("since=2026-10-13 10:20:00", r.evidence[0].note)
        early = sp.probe_shim_log_scan(rd.ROUTE_CHATGPT, since="2026-10-13 10:00:05", log_path=log, tier="post")
        self.assertEqual(early.verdict, Verdict.FAIL)
        self.assertIn("in this run's window", early.detail)

    def test_restart_inside_the_window_accumulates(self):
        # Review fix cycle 2: a mid-run shim restart used to reset the counters,
        # hiding every signal logged before it in the same run window.
        log = [
            "2026-10-13 09:00:00,000 INFO req_id=- phase=- shim v1.4.8 starting port=4141",   # before: resets
            "2026-10-13 09:30:00,000 INFO req_id=z phase=t backend_code=unsupported_value",  # before the window
            "2026-10-13 10:00:01,000 INFO req_id=a phase=t event=request_parsed model=claude-haiku-4-5 tools=0",
            "2026-10-13 10:00:02,000 INFO req_id=- phase=- shim v1.4.9 starting port=4141",   # inside: no reset
            "2026-10-13 10:00:03,000 INFO req_id=b phase=terminal event=terminal outcome=error "
            "backend_code=unsupported_value",
            "2026-10-13 10:00:09,000 INFO req_id=- phase=- shim v1.4.9 starting port=4141",   # after until
            "2026-10-13 10:00:10,000 INFO req_id=c phase=t backend_code=unsupported_value",
        ]
        counts = sp.scan_shim_log(log, since="2026-10-13 10:00:00", until="2026-10-13 10:00:05")
        self.assertEqual(counts["claude_named_requests"], 1)  # logged before the restart, kept
        self.assertEqual(counts["unsupported_value"], 1)
        self.assertEqual(counts["daemon_restarts_in_window"], 1)
        self.assertEqual(counts["daemon_starts_seen"], 3)
        self.assertEqual(counts["lines_in_window"], 2)
        # No since (Tier 0 history): every start still resets to the current daemon.
        history = sp.scan_shim_log(log[:5])
        self.assertEqual((history["claude_named_requests"], history["daemon_restarts_in_window"]), (0, 0))
        d = _scratch(self, "shimlogrestart")
        (d / "shim.log").write_text("\n".join(log[:5]) + "\n")
        r = sp.probe_shim_log_scan(rd.ROUTE_CHATGPT, since="2026-10-13 10:00:00", log_path=d / "shim.log",
                                   tier="post")
        self.assertEqual(r.verdict, Verdict.WARN, r.detail)
        self.assertIn("Daemon restarts inside the window: 1", r.detail)
        self.assertIn('"daemon_restarts_in_window": 1', r.evidence[0].output)


class CodexConfigTests(unittest.TestCase):
    def test_states(self):
        ok = ["2026-10-13T10:00:00Z summary: wrote 2 setting(s) to /h/config.toml: a, b (exit 0)"]
        refused = ["2026-10-13T11:00:00Z warning: DAAF_CODEX_CONFIG_3 refused: token could hold a credential",
                   "2026-10-13T11:00:00Z summary: wrote 1 setting(s) to /h/config.toml: a; 1 problem(s) (exit 2)"]
        err = ["2026-10-13T12:00:00Z summary: ERROR: could not write /h/config.toml (exit 1)"]
        self.assertEqual(sp._evaluate_codex_config(None, True)[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_codex_config(None, False)[0], Verdict.INFO)
        self.assertEqual(sp._evaluate_codex_config(ok, True)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_codex_config(ok + refused, True)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_codex_config(refused + ok[:0] + err, True)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_codex_config(refused + ["2026-10-13T13:00:00Z summary: no Codex "
                                                              "settings configured; nothing written (exit 0)"],
                                                   False)[0], Verdict.PASS)  # last run judged
        self.assertEqual(sp._evaluate_codex_config(["garbage"], True)[0], Verdict.WARN)

    def test_probe_skips_off_shim_and_reads_log(self):
        d = _scratch(self, "codexcfg")
        (d / "codex_config.log").write_text("2026-10-13T10:00:00Z summary: wrote 1 setting(s) (exit 0)\n")
        env = dict(SHIM, SHIM_BACKEND_MODE="chatgpt", DAAF_CODEX_CONFIG_1="model=x")
        r = sp.probe_codex_config(rd.build_route_info(env), env, log_path=d / "codex_config.log")
        self.assertEqual(r.verdict, Verdict.PASS)
        self.assertEqual(sp.probe_codex_config(rd.build_route_info({}), {}).verdict, Verdict.SKIP)


class PromptCacheTests(unittest.TestCase):
    def test_thresholds(self):
        block = {"requests_with_usage": 25, "requests_with_cached": 5, "cached_tokens_total": 20,
                 "input_tokens_total": 100}
        self.assertEqual(sp._evaluate_prompt_cache(block)[0], Verdict.WARN)          # 0.2 < 0.3, n >= 20
        self.assertEqual(sp._evaluate_prompt_cache(dict(block, cached_tokens_total=92))[0], Verdict.INFO)
        self.assertEqual(sp._evaluate_prompt_cache(dict(block, requests_with_usage=19))[0], Verdict.INFO)
        self.assertEqual(sp._evaluate_prompt_cache(dict(block, input_tokens_total=0))[0], Verdict.INFO)
        self.assertEqual(sp._evaluate_prompt_cache(None)[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_prompt_cache(dict(block, cached_tokens_total=True))[0], Verdict.WARN)


class VersionsToolchainIdentityIntegrityTests(unittest.TestCase):
    def test_t015(self):
        base = {"claude_code": "2.1.281", "claude_code_pin": "2.1.281", "daaf_sha": "abc",
                "dev_binaries": {"bats": True, "pwsh": True, "shellcheck": True}}
        self.assertEqual(sp._evaluate_t015(base, rd.ROUTE_CHATGPT)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t015(dict(base, claude_code="2.1.270"), rd.ROUTE_CHATGPT)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t015(dict(base, claude_code="2.1.270"), rd.ROUTE_ANTHROPIC)[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_t015(dict(base, dev_binaries={"bats": False}), rd.ROUTE_ANTHROPIC)[0],
                         Verdict.WARN)
        # codex is judged against its pin when the pin is readable.
        codex_ok = dict(base, codex="0.153.2", codex_pin="0.153.2")
        self.assertEqual(sp._evaluate_t015(codex_ok, rd.ROUTE_CHATGPT)[0], Verdict.PASS)
        v, d = sp._evaluate_t015(dict(codex_ok, codex="0.150.0"), rd.ROUTE_CHATGPT)
        self.assertEqual(v, Verdict.WARN)
        self.assertIn("Codex CLI 0.150.0 differs from the Dockerfile pin 0.153.2", d)
        self.assertEqual(sp._evaluate_t015(dict(codex_ok, codex=None), rd.ROUTE_ANTHROPIC)[0], Verdict.WARN)

    def test_dockerfile_pin_parsing(self):
        d = _scratch(self, "dockerpin")
        (d / "Dockerfile").write_text(
            "# ARG CLAUDE_CODE_VERSION=0.0.0 in a comment is not a pin\n"
            "ARG CODEX_VERSION=0.153.2  # bump with the Codex changelog\n"
            "  ARG CLAUDE_CODE_VERSION=\"2.1.281\"\n"
            "ARG OTHER=1 2\n")
        self.assertEqual(sp._dockerfile_pin(str(d), "CODEX_VERSION"), "0.153.2")
        self.assertEqual(sp._dockerfile_pin(str(d), "CLAUDE_CODE_VERSION"), "2.1.281")
        self.assertIsNone(sp._dockerfile_pin(str(d), "OTHER"))
        self.assertIsNone(sp._dockerfile_pin(str(d), "MISSING"))
        self.assertIsNone(sp._dockerfile_pin(str(d / "nowhere"), "CODEX_VERSION"))
        # The real Dockerfile's two pins parse.
        self.assertRegex(sp._dockerfile_pin(str(_REPO_ROOT), "CODEX_VERSION") or "", r"^\d+\.\d+\.\d+$")
        self.assertRegex(sp._dockerfile_pin(str(_REPO_ROOT), "CLAUDE_CODE_VERSION") or "", r"^\d+\.\d+\.\d+$")

    def test_collect_versions_with_fake_commands(self):
        def fake(cmd, timeout=20, cwd=None, env=None):
            if cmd[0] == "claude":
                return 0, "2.1.281 (Claude Code)\n", ""
            if cmd[0] == "codex":
                return None, "", "not found: codex"
            if "status" in cmd:
                return 0, " M a\n?? b\n", ""
            return 0, "main\n", ""
        with mock.patch.object(sp, "_run_cmd", side_effect=fake):
            v = sp.collect_versions(str(_REPO_ROOT))
        self.assertEqual((v["claude_code"], v["codex"], v["dirty_files"]), ("2.1.281", None, 2))
        self.assertEqual(v["claude_code_pin"], sp._dockerfile_pin(str(_REPO_ROOT), "CLAUDE_CODE_VERSION"))

    def test_t021_and_t022(self):
        good = {"euid": 1000, "user": "appuser", "base_writable": True, "research_writable": True,
                "probe_file_ok": True, "git_status_rc": 0, "free_gb": 50.0}
        self.assertEqual(sp._evaluate_t021(good)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t021(dict(good, euid=0, user="root"))[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t021(dict(good, free_gb=3.2))[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_t021(dict(good, git_status_rc=128))[0], Verdict.FAIL)
        found = {t: "1.0" for t, _, _ in sp.TOOLCHAIN}
        self.assertEqual(sp._evaluate_t022(found)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t022(dict(found, quarto=None))[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t022(dict(found, pwsh=None))[0], Verdict.WARN)

    def test_t021_probe_file_is_removed(self):
        d = _scratch(self, "t021")
        with mock.patch.object(sp, "_run_cmd", return_value=(0, "", "")):
            r = sp.probe_runtime_identity(str(_REPO_ROOT), work_dir=d)
        self.assertEqual(list(d.iterdir()), [])
        self.assertIn('"probe_file_ok": true', r.evidence[0].output)

    def test_t023_on_fixture_tree(self):
        root = _scratch(self, "t023")
        (root / ".claude" / "hooks").mkdir(parents=True)
        hook = root / ".claude" / "hooks" / "h.sh"
        hook.write_text("#!/bin/bash\n")
        hook.chmod(0o755)
        (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
            {"hooks": [{"command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/h.sh'}]}]}}))
        (root / ".claude" / "skills" / "good-skill").mkdir(parents=True)
        (root / ".claude" / "skills" / "good-skill" / "SKILL.md").write_text(
            "---\nname: good-skill\ndescription: Does a thing.\n---\n# x\n")
        (root / ".claude" / "agents").mkdir()
        (root / ".claude" / "agents" / "a.md").write_text("---\nname: a\ntools: Read, Grep\n---\n")
        (root / "CLAUDE.md").write_text("x\n")
        with mock.patch.object(sp, "_git_tracked_modes", return_value={".claude/hooks/h.sh": "100755"}):
            self.assertEqual(sp.probe_framework_integrity(str(root)).verdict, Verdict.PASS)
            (root / ".claude" / "agents" / "b.md").write_text("---\nname: b\ntools: [Read, Agent]\n---\n")
            hook.chmod(0o644)
            r = sp.probe_framework_integrity(str(root))
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("Agent/Task", r.detail)
        self.assertIn("not executable", r.detail)


class HookRegistrationTests(unittest.TestCase):
    """T0.6: every .claude/hooks/*.sh is registered, except per-agent hooks and
    the files a hook sources (bash-safety.site.sh), which settings.json must not
    register."""

    def _tree(self, names):
        root = _scratch(self, "t06")
        hooks = root / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        for name in names:
            (hooks / name).write_text("#!/usr/bin/env bash\n")
        (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command",
                                           "command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/bash-safety.sh'}]}]}}))
        return root

    def test_sourced_site_file_is_exempt(self):
        root = self._tree(["bash-safety.sh", "bash-safety.site.sh", "enforce-file-first.sh"])
        r = sp.probe_hook_registration(str(root))
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        self.assertTrue(any("sourced by a hook" in (e.note or "") and "bash-safety.site.sh" in e.note
                            for e in r.evidence))

    def test_unregistered_real_hook_still_fails(self):
        root = self._tree(["bash-safety.sh", "bash-safety.site.sh", "new-guard.sh"])
        r = sp.probe_hook_registration(str(root))
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("new-guard.sh", r.detail)
        self.assertNotIn("bash-safety.site.sh", r.detail)

    def test_exemption_is_by_exact_name_not_suffix(self):
        root = self._tree(["bash-safety.sh", "other.site.sh"])
        r = sp.probe_hook_registration(str(root))
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("other.site.sh", r.detail)


class TierNTests(unittest.TestCase):
    def test_tn1_mapping(self):
        up = {"url": "u", "reachable": True, "status": 401}
        down = {"url": "u", "reachable": False, "status": None}
        self.assertEqual(sp._evaluate_tn1(rd.ROUTE_ANTHROPIC, [up])[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_tn1(rd.ROUTE_CHATGPT, [up, down])[0], Verdict.FAIL)

    def test_run_tier_n_with_injected_fetches(self):
        ev = _scratch(self, "tiern")

        def fake_cmd(cmd, timeout=20, cwd=None, env=None):
            if "web_fetch.sh" in cmd[1]:
                dest = Path(cmd[-1])
                (dest / "x.md").write_text("extract")
                (dest / "MANIFEST.jsonl").write_text('{"status": 200}\n')
                return 0, "preview text", ""
            return 0, "verify: EXISTS 10.1038/nature14539\n", ""
        with mock.patch.object(sp, "_http_reach", return_value={"url": "u", "reachable": True, "status": 200,
                                                                "error": ""}), \
             mock.patch.object(sp, "_run_cmd", side_effect=fake_cmd):
            results = sp.run_tier_n(rd.ROUTE_ANTHROPIC_API, 30, ev)
        self.assertEqual([r.probe_id for r in results], ["TN.1", "TN.2", "TN.3", "TN.4"])
        self.assertTrue(all(r.verdict == Verdict.PASS for r in results), [r.detail for r in results])
        self.assertNotIn("preview text", json.dumps([r.to_dict() for r in results]))

    def test_network_failures_warn_not_fail_except_tn1(self):
        ev = _scratch(self, "tiern_fail")
        with mock.patch.object(sp, "_http_reach", return_value={"url": "u", "reachable": False, "status": None,
                                                                "error": "URLError"}), \
             mock.patch.object(sp, "_run_cmd", return_value=(4, "", "")), \
             mock.patch.object(sp, "_read_local_health", side_effect=OSError("down")):
            results = {r.probe_id: r for r in sp.run_tier_n(rd.ROUTE_OPENAI_API, 30, ev)}
        self.assertEqual(results["TN.1"].verdict, Verdict.FAIL)
        for pid in ("TN.2", "TN.3", "TN.4"):
            self.assertEqual(results[pid].verdict, Verdict.WARN, pid)
            self.assertTrue(results[pid].hint, pid)


class LiveEvaluatorTests(unittest.TestCase):
    def test_stream_json_init_projection_and_parse(self):
        raw = "\n".join([
            json.dumps({"type": "system", "subtype": "init", "apiKeySource": "none", "model": "claude-opus-5-5[1m]",
                        "tools": ["Bash"], "cwd": "/daaf", "mcp_servers": [{"name": "x"}]}),
            json.dumps({"type": "result", "subtype": "success", "result": "SMOKE_TIER1_COMPLETE"}),
            '{"truncated',
        ])
        records = sp._parse_stream_json(raw)
        self.assertEqual(len(records), 2)
        self.assertEqual(sp._project_init_record(records), {"apiKeySource": "none", "model": "claude-opus-5-5[1m]"})

    def test_t18(self):
        sub = {"apiKeySource": "none", "model": "claude-opus-5-5[1m]"}
        api = {"apiKeySource": "ANTHROPIC_API_KEY", "model": "claude-opus-5-5"}
        self.assertEqual(sp._evaluate_t18(rd.ROUTE_ANTHROPIC, sub)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t18(rd.ROUTE_ANTHROPIC, api)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t18(rd.ROUTE_ANTHROPIC_API, api)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t18(rd.ROUTE_ANTHROPIC_API, sub)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t18(rd.ROUTE_CHATGPT, {"apiKeySource": "none", "model": "gpt-6-sol[1m]#high"})[0],
                         Verdict.PASS)
        self.assertEqual(sp._evaluate_t18(rd.ROUTE_CHATGPT, sub)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t18(rd.ROUTE_ANTHROPIC, {})[0], Verdict.WARN)

    def test_t19_and_t110(self):
        reminder = {"type": "attachment", "attachment": {"type": "hook_success", "hookEvent": "UserPromptSubmit",
                    "hookName": "UserPromptSubmit", "content": "You MUST IMMEDIATELY invoke the daaf-orchestrator "
                    "skill (Skill tool) BEFORE doing any other work."}}
        skill = [_use("s1", "Skill", {"skill": "daaf-orchestrator"}), _res("s1")]
        self.assertEqual(sp._evaluate_t19([reminder] + skill)[0], Verdict.PASS)
        # The healthy-run shape: the T1 prompt allows one Bash call, so the model
        # obeys it over the reminder. INFO, never WARN (review S5).
        self.assertEqual(sp._evaluate_t19([reminder])[0], Verdict.INFO)
        self.assertEqual(sp._evaluate_t19(skill)[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_t19([])[0], Verdict.FAIL)
        errored_skill = [_use("s2", "Skill", {"skill": "daaf-orchestrator"}), _res("s2", "boom", True)]
        self.assertEqual(sp._evaluate_t19([reminder] + errored_skill)[0], Verdict.INFO)
        self.assertEqual(sp._evaluate_t110({"jsonl": "a", "md": "b"})[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t110({"jsonl": "a", "md": None})[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_t110({"jsonl": None, "md": None})[0], Verdict.FAIL)

    def test_t21_routing_and_t23_tightening(self):
        env = dict(GPT_ALIASES)
        self.assertEqual(sp._evaluate_t21_routing(["gpt-6-luna"], "sonnet", env, rd.ROUTE_CHATGPT)[0], True)
        self.assertEqual(sp._evaluate_t21_routing(["gpt-6-sol"], "sonnet", env, rd.ROUTE_CHATGPT)[0], False)
        self.assertEqual(sp._evaluate_t21_routing(["claude-sonnet-4-6"], "sonnet", {}, rd.ROUTE_ANTHROPIC)[0], True)
        self.assertIsNone(sp._evaluate_t21_routing([], "sonnet", {}, rd.ROUTE_ANTHROPIC)[0])
        fetch_only = [[_use("b", "Bash", {"command": "bash /daaf/scripts/web_fetch.sh u d"}), _res("b")]]
        verdict, facts = sp._evaluate_t23(fetch_only)
        self.assertEqual(sp._t23_route_verdict(verdict, facts, rd.ROUTE_CHATGPT)[0], Verdict.WARN)
        self.assertEqual(sp._t23_route_verdict(verdict, facts, rd.ROUTE_ANTHROPIC)[0], Verdict.PASS)
        ws = [[_use("w", "WebSearch", {"query": "q"}), _res("w")]]
        self.assertEqual(sp._t23_route_verdict(*sp._evaluate_t23(ws), rd.ROUTE_CHATGPT)[0], Verdict.PASS)

    def test_t27(self):
        pip = _use("p", "Bash", {"command": "pip install requests"})
        read = _use("r", "Read", {"file_path": "/daaf/.env"})
        both_denied = [pip, _res("p", "BLOCKED by bash-safety hook: Runtime package changes ...", True),
                       read, _res("r", "Permission to read /daaf/.env has been denied.", True)]
        self.assertEqual(sp._evaluate_t27(both_denied)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t27([pip, _res("p", "Successfully installed", False)])[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t27(both_denied[:2] + [read, _res("r", "KEY=...", False)])[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_t27(both_denied[:2])[0], Verdict.WARN)            # read not attempted
        self.assertEqual(sp._evaluate_t27(both_denied[:2], read_half=False)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t27([pip, _res("p", "some other error", True)], read_half=False)[0],
                         Verdict.WARN)

    def test_t27_read_half_missing_file_is_fail(self):
        # T2.7 requests the Read only when /daaf/.env is absent, so a Read that
        # reached the filesystem errors "does not exist": the deny did not fire.
        pip = [_use("p", "Bash", {"command": "pip install requests"}),
               _res("p", "Exit code 2\nBLOCKED by bash-safety hook: Runtime package changes ...", True)]
        read = _use("r", "Read", {"file_path": "/daaf/.env"})
        for text in ("File does not exist. Note: your current working directory is /daaf.",
                     "ENOENT: no such file or directory, open '/daaf/.env'",
                     "Error reading file"):
            with self.subTest(text=text):
                v, facts, detail = sp._evaluate_t27(pip + [read, _res("r", text, True)])
                self.assertEqual(v, Verdict.FAIL, detail)
                self.assertIn("deny rule did not fire", detail)
                self.assertEqual(facts["read_ran"], 1)
        # Only the explicit permission-layer denial passes. The third shape is
        # CLI 2.1.281's Read validateInput text for a matching deny rule (found
        # in the installed binary, review fix cycle 2).
        for text in ("Permission to read /daaf/.env has been denied.",
                     "Error: Permission to use Read with file_path /daaf/.env has been denied.",
                     "File is in a directory that is denied by your permission settings."):
            with self.subTest(text=text):
                self.assertEqual(sp._evaluate_t27(pip + [read, _res("r", text, True)])[0], Verdict.PASS)
        # A deny-like error in no recognized shape is WARN, quoted, never PASS.
        v, facts, detail = sp._evaluate_t27(pip + [read, _res("r", "Access denied by policy", True)])
        self.assertEqual(v, Verdict.WARN)
        self.assertIn("Access denied by policy", detail)
        self.assertEqual(facts["read_unrecognized"], 1)

    def test_t27_pip_half_deny_shapes(self):
        pip = _use("p", "Bash", {"command": "pip install requests"})
        cases = [
            ("Exit code 2\nBLOCKED by bash-safety hook: Runtime package changes drift", Verdict.PASS),
            ("Permission to use Bash with command pip install requests has been denied.", Verdict.PASS),
            # An OS "Permission denied" from a pip that RAN is not a block (review Q-M2).
            ("Exit code 1\nCollecting requests\nERROR: Could not install packages due to an OSError: "
             "[Errno 13] Permission denied: '/usr/lib/python3'", Verdict.FAIL),
            ("Exit code 1\nDefaulting to user installation because normal site-packages is not writeable",
             Verdict.FAIL),
            ("bash: /usr/bin/pip: Permission denied", Verdict.WARN),           # unrecognized deny shape
            ("Exit code 127\npip: command not found", Verdict.WARN),           # unexplained error
            ("blocked by bash-safety HOOK", Verdict.WARN),                     # exact text is case-sensitive
        ]
        for text, want in cases:
            with self.subTest(text=text):
                v, facts, detail = sp._evaluate_t27([pip, _res("p", text, True)], read_half=False)
                self.assertEqual(v, want, detail)
        # Old bug: a bare "permission" word no longer counts as a deny.
        v, _, _ = sp._evaluate_t27([pip, _res("p", "Exit code 1\npermission problem", True)], read_half=False)
        self.assertNotEqual(v, Verdict.PASS)
        # The bash-safety text is recorded; unrecognized text is quoted, scrubbed and bounded.
        _, facts, _ = sp._evaluate_t27([pip, _res("p", "Exit code 2\nBLOCKED by bash-safety hook: x", True)],
                                       read_half=False)
        self.assertTrue(facts["bash_safety_text_seen"])
        _, facts, _ = sp._evaluate_t27([pip, _res("p", "denied " + "x" * 400, True)], read_half=False)
        self.assertLessEqual(len(facts["unrecognized_deny_text"][0]), 180)
        # No pip attempt at all: WARN (the model declined).
        self.assertEqual(sp._evaluate_t27([], read_half=False)[0], Verdict.WARN)
        # An attempt with no recorded tool_result is WARN too, and says so.
        v, facts, detail = sp._evaluate_t27([pip], read_half=False)
        self.assertEqual((v, facts["pip_attempts"]), (Verdict.WARN, 1))
        self.assertIn("no recorded tool result", detail)

    def test_t27_pip_matcher_needs_a_real_invocation(self):
        # Review fix cycle 2: a grep or help command that only MENTIONS the
        # phrase is not an install attempt, so its successful result is no FAIL.
        for cmd in ('grep -n "pip install" /daaf/CLAUDE.md', "echo 'pip install requests'",
                    'pip --help | grep "pip install"', "man pip", "cat notes.md # pip install x",
                    'grep -rn "pip3 install" . && echo done'):
            with self.subTest(cmd=cmd):
                self.assertFalse(sp._is_pip_install_command(cmd))
                v, facts, _ = sp._evaluate_t27([_use("g", "Bash", {"command": cmd}), _res("g", "12: text", False)],
                                               read_half=False)
                self.assertEqual((v, facts["pip_attempts"]), (Verdict.WARN, 0))
        for cmd in ("pip install requests", "python3 -m pip install x", "pip3 install x",
                    "sudo pip install x", "uv pip install x", "cd /daaf && pip install requests",
                    "/usr/bin/python3.12 -m pip install x", "PIP_NO_INPUT=1 pip install x"):
            with self.subTest(cmd=cmd):
                self.assertTrue(sp._is_pip_install_command(cmd))
                v, facts, _ = sp._evaluate_t27([_use("p", "Bash", {"command": cmd}),
                                                _res("p", "Successfully installed x", False)], read_half=False)
                self.assertEqual((v, facts["pip_attempts"]), (Verdict.FAIL, 1))

    def test_t27_pip_matcher_sees_shell_wrappers(self):
        # Review note: a pip install inside a shell wrapper's -c string was not
        # seen. The -c string is re-split and matched like a top-level command.
        for cmd in ('bash -c "pip install requests"', "sh -c 'pip install requests'",
                    'bash -lc "pip3 install x"', "bash -c 'python -m pip install x'",
                    "sh -c 'python3 -m pip install x'", '/bin/bash -c "cd /daaf && pip install x"',
                    'sudo bash -c "pip install x"', 'env FOO=1 sh -c "pip install x"',
                    'bash -o pipefail -c "pip install x | tee log"', "bash -e -c 'pip install x'",
                    'sh -c "bash -c \'pip install x\'"', 'echo start; bash -c "pip install x"',
                    'PIP_NO_INPUT=1 bash -c "pip install x"', "python -m pip install x", "pip3 install x"):
            with self.subTest(cmd=cmd):
                self.assertTrue(sp._is_pip_install_command(cmd))
                v, facts, _ = sp._evaluate_t27([_use("p", "Bash", {"command": cmd}),
                                                _res("p", "Successfully installed x", False)], read_half=False)
                self.assertEqual((v, facts["pip_attempts"]), (Verdict.FAIL, 1))
        # Read-only pip verbs and mentions stay non-attempts, wrapped or not.
        for cmd in ("pip list", "pip show requests", "pip3 freeze", "python -m pip list",
                    'bash -c "pip list"', "sh -c 'pip show requests'", 'bash -c "pip --version"',
                    "bash -c 'grep -n \"pip install\" /daaf/CLAUDE.md'", 'sh -c "echo pip install x"',
                    'bash "pip install x"', "bash -x script.sh", 'bash -c', "sh -c ''",
                    'bash -n -c "echo ok"', 'echo bash -c "pip install x"'):
            with self.subTest(cmd=cmd):
                self.assertFalse(sp._is_pip_install_command(cmd))

    def test_t27_pip_matcher_skips_long_shell_options_and_prefix_arguments(self):
        # Review fix (1.4.13 batch): long shell options before -c, prefix options
        # that take an argument, and the timeout/nice prefixes.
        for cmd in ('bash --login -c "pip install x"', 'bash --noprofile --norc -c "pip install x"',
                    "bash --rcfile /etc/fixture.rc -c 'pip install x'", 'bash --posix -lc "pip install x"',
                    'sudo -u root bash -c "pip install x"', 'sudo -uroot sh -c "pip install x"',
                    'sudo -E -u root -g staff bash -c "pip install x"', 'sudo -Eu root bash -c "pip install x"',
                    'sudo --user root bash -c "pip install x"', 'sudo --user=root bash -c "pip install x"',
                    "env -u VAR sh -c 'pip install x'", "env -i -u VAR FOO=1 sh -c 'pip install x'",
                    'timeout 30 bash -c "pip install x"', 'timeout -s KILL -k 5 30 bash -c "pip install x"',
                    'timeout --signal TERM 30s sh -c "pip install x"', 'nice -n 5 bash -c "pip install x"',
                    'nice -5 bash -c "pip install x"', 'exec -a fixture bash -c "pip install x"',
                    'sudo -u root timeout 30 nice -n 5 bash --login -c "pip install x"',
                    "sudo -u root pip install x", "timeout 30 pip install x",
                    "nice -n 5 python3 -m pip install x", "env -u VAR pip3 install x"):
            with self.subTest(cmd=cmd):
                self.assertTrue(sp._is_pip_install_command(cmd))
                v, facts, _ = sp._evaluate_t27([_use("p", "Bash", {"command": cmd}),
                                                _res("p", "Successfully installed x", False)], read_half=False)
                self.assertEqual((v, facts["pip_attempts"]), (Verdict.FAIL, 1))
        for cmd in ("sudo -u root pip list", 'sudo -u root bash -c "pip list"', "timeout 30 pip show x",
                    'nice -n 5 bash -c "pip freeze"', "env -u VAR sh -c 'echo pip install x'",
                    'bash --login -c "pip --version"', "bash --login script.sh",
                    'timeout 30 echo pip install x', 'bash --rcfile -c "pip install x"'):
            with self.subTest(cmd=cmd):
                self.assertFalse(sp._is_pip_install_command(cmd))

    def test_ta1_and_tier3(self):
        digest = "ab" * 32
        ran = [_use("b", "Bash", {"command": "openssl dgst -sha256 /daaf/CLAUDE.md"}), _res("b")]
        reply = f"SHA2-256(/daaf/CLAUDE.md)= {digest}"
        self.assertEqual(sp._evaluate_ta1(ran, reply, digest, rd.ROUTE_ANTHROPIC)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_ta1(ran, reply, digest, rd.ROUTE_CHATGPT, 1)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_ta1(ran, reply, digest, rd.ROUTE_CHATGPT, 0)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_ta1(ran, reply, digest, rd.ROUTE_CHATGPT, None)[0], Verdict.WARN)
        self.assertEqual(sp._evaluate_ta1([], reply, digest, rd.ROUTE_ANTHROPIC)[0], Verdict.FAIL)
        self.assertEqual(sp._evaluate_ta1(ran, "no digest", digest, rd.ROUTE_ANTHROPIC)[0], Verdict.FAIL)
        orch = [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        self.assertEqual(sp._evaluate_t31("This is a Data Discovery question. Shall I proceed?", orch)[0],
                         Verdict.PASS)
        self.assertEqual(sp._evaluate_t31("grade -1 means Pre-K.", [])[0], Verdict.WARN)
        ctx = [_use("c", "Skill", {"skill": "education-data-context"}), _res("c")]
        self.assertEqual(sp._evaluate_t32("In CCD, grade = -1 denotes Pre-Kindergarten.", ctx)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t32("It means missing data.", ctx)[0], Verdict.FAIL)

    def test_t31_grades_the_orchestrator_load_only(self):
        # T3.1 PASSes on a non-error daaf-orchestrator Skill load and WARNs
        # without one, whatever the reply does at the gate; the gate facts are
        # recorded beside the verdict and listed after its reason. With no main
        # transcript records the load is not checked (a WARN, recorded as None).
        orch = [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        prompt_only = [{"type": "user", "message": {"role": "user", "content": sp.T31_PROMPT}}]
        outcomes = ((orch, Verdict.PASS, True, "daaf-orchestrator loaded in the main transcript."),
                    (prompt_only, Verdict.WARN, False, "daaf-orchestrator did not load in the main transcript."),
                    ([], Verdict.WARN, None,
                     "daaf-orchestrator load not checked: main transcript missing, empty or unreadable."))
        replies = [
            # (reply, mode_named, asks_confirmation, prek_already_answered)
            ("This is a quick definitional question, so I'd treat it as Data Lookup. I'll read the data lookup "
             "mode workflow reference, then check the CCD skill. **Sound good?**", "Data Lookup", True, False),
            ("I'd handle this in data-discovery mode. Shall I proceed?", "data-discovery", True, False),
            ("Which mode? I can help with that.", None, False, False),
            ("I'll look this up in the CCD documentation. Shall I proceed?", None, True, False),
            ("Data Lookup: grade = -1 is Pre-Kindergarten in CCD.", "Data Lookup", False, True),
            ("Data Lookup. grade -1 is Pre-K. Shall I proceed with more detail?", "Data Lookup", True, True),
            ("", None, False, False),
        ]
        for text, mode, asks, prek in replies:
            for records, want, loaded, lead in outcomes:
                with self.subTest(text=text, loaded=loaded):
                    v, d, facts = sp._evaluate_t31(text, records)
                    self.assertEqual(v, want, (d, facts))
                    self.assertEqual(facts, {"orchestrator_skill_loaded": loaded, "mode_named": mode,
                                             "asks_confirmation": asks, "prek_already_answered": prek})
                    self.assertTrue(d.startswith(lead), d)
                    self.assertIn("Recorded, not graded:", d)
                    self.assertIn(f"Pre-K mentioned: {'yes' if prek else 'no'}", d)
        # Bare, '/name' and plugin-qualified loads count; an errored load or one
        # with no recorded result does not, and neither does another skill.
        for skill in ("daaf-orchestrator", "/daaf-orchestrator", "x:daaf-orchestrator"):
            with self.subTest(skill=skill):
                recs = [_use("o", "Skill", {"skill": skill}), _res("o")]
                self.assertEqual(sp._evaluate_t31("q", recs)[0], Verdict.PASS)
        for label, recs in {"errored": [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o", "x", True)],
                            "no result": [_use("o", "Skill", {"skill": "daaf-orchestrator"})],
                            "other skill": [_use("o", "Skill", {"skill": "polars"}), _res("o")]}.items():
            with self.subTest(case=label):
                v, d, facts = sp._evaluate_t31("q", recs)
                self.assertEqual((v, facts["orchestrator_skill_loaded"]), (Verdict.WARN, False), d)
        # A WARN detail reaches the report's Observed cell, which keeps 200
        # characters: the verdict reason and the facts both fit, for every mode
        # name and the longest yes/yes facts.
        for name in sp._DAAF_MODE_NAMES:
            reply = f"This is {name}. grade -1 is Pre-K. Shall I proceed?"
            for records in (prompt_only, []):
                with self.subTest(mode=name, records=len(records)):
                    v, d, facts = sp._evaluate_t31(reply, records)
                    self.assertEqual(v, Verdict.WARN, d)
                    self.assertEqual((facts["mode_named"], facts["asks_confirmation"],
                                      facts["prek_already_answered"]), (name, True, True))
                    self.assertLessEqual(len(d), 200, d)

    def test_t31_live_scope_example_mentioning_pre_k_passes(self):
        # A live reply (session d99a40c0, anthropic-subscription) that stops at
        # the gate and names Pre-K only in a scope example. It must PASS when
        # the orchestrator loaded; prek_already_answered is recorded as
        # information only.
        reply = (
            "Welcome to DAAF, the Data Analyst Augmentation Framework. I'm a research orchestrator for rigorous, "
            "reproducible data analysis, and I check in with you at each key decision point instead of running "
            "ahead. If you're new or want a tour, just ask. Otherwise, here's how I'd handle your question.\n\n"
            "This looks like a **Data Lookup**. You're asking what one coded value means in one dataset: "
            "`grade = -1` in the Common Core of Data (CCD) enrollment files.\n\n"
            "**What to expect:** I'll read the data lookup workflow, then have a specialist check the CCD and "
            "Education Data Portal reference material for how the grade variable is coded. You'll get a short "
            "answer with its source. The answer will also cover anything that's easy to mix up with this code, "
            "since the Portal uses negative numbers for missing-data codes too. If your question turns out to "
            "need broader exploration, such as how Pre-K coverage changes across years or states, I'll ask "
            "before widening the scope.\n\n"
            "**What I'll read first:** You didn't point me to any files or documents, so I'll work from DAAF's "
            "curated CCD reference material. If it looks out of date, I'll check the official documentation "
            "online.\n\n"
            "(Separately, your Gmail and Google Drive connectors need to be authorized in your claude.ai "
            "connector settings before they'll work here. They aren't needed for this question.)\n\n"
            "**Sound good?**")
        main = [{"type": "user", "message": {"role": "user", "content": sp.T31_PROMPT}},
                _use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        v, d, facts = sp._evaluate_t31(reply, main)
        self.assertEqual(v, Verdict.PASS, d)
        self.assertEqual(facts, {"orchestrator_skill_loaded": True, "mode_named": "Data Lookup",
                                 "asks_confirmation": True, "prek_already_answered": True})
        self.assertTrue(d.startswith("daaf-orchestrator loaded in the main transcript."), d)

    def test_t32_warns_when_answered_without_the_skill(self):
        orch = [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        ctx = [_use("c", "Skill", {"skill": "x:education-data-context"}), _res("c")]
        answer = "grade = -1 means Pre-K."
        # A main transcript without the load: "did not load either".
        prompt_only = [{"type": "user", "message": {"role": "user", "content": sp.T32_PROMPT}}]
        v, d, facts = sp._evaluate_t32(answer, prompt_only)
        self.assertEqual((v, facts["orchestrator_skill_loaded"]), (Verdict.WARN, False), d)
        self.assertIn("answered without loading the skill", d)
        self.assertIn("education-data-* skill", d)
        self.assertIn("daaf-orchestrator did not load either", d)
        # No main-transcript records: the load is not checked, as in T3.1.
        v, d, facts = sp._evaluate_t32(answer, [])
        self.assertEqual((v, facts["orchestrator_skill_loaded"]), (Verdict.WARN, None), d)
        self.assertNotIn("did not load", d)
        v, d, _ = sp._evaluate_t32(answer, orch)
        self.assertEqual(v, Verdict.WARN)
        self.assertNotIn("daaf-orchestrator did not load", d)
        self.assertEqual(sp._evaluate_t32(answer, orch + ctx)[0], Verdict.PASS)
        failed_ctx = [_use("c", "Skill", {"skill": "education-data-context"}), _res("c", "err", True)]
        self.assertEqual(sp._evaluate_t32(answer, failed_ctx)[0], Verdict.WARN)

    def test_t32_counts_retrieval_in_a_specialist_transcript(self):
        # Data Lookup: the orchestrator hands the lookup to a specialist
        # (search-agent by default, source-researcher for a deep lookup), which
        # loads the data skill in its own transcript. Retrieval counts there too.
        answer = "grade = -1 means Pre-K."
        orch = [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        ctx_sub = [_use("c", "Skill", {"skill": "education-data-context"}), _res("c")]
        v, d, facts = sp._evaluate_t32(answer, orch, [[], ctx_sub])
        self.assertEqual(v, Verdict.PASS, d)
        self.assertEqual((facts["retrieval_signal"], facts["retrieval_where"], facts["subagent_transcripts"]),
                         ("Skill education-data-context", "subagent", 2))
        self.assertIn("specialist (subagent) transcript", d)
        # The CCD source skill counts as well, bare, '/name' or plugin-qualified.
        for skill in ("education-data-source-ccd", "/education-data-source-ccd", "x:education-data-source-ccd"):
            with self.subTest(skill=skill):
                ccd = [_use("k", "Skill", {"skill": skill}), _res("k")]
                v, d, facts = sp._evaluate_t32(answer, orch, [ccd])
                self.assertEqual(v, Verdict.PASS, d)
                self.assertEqual(facts["retrieval_signal"], "Skill education-data-source-ccd")
        # The main transcript is checked first and reported as "main".
        v, _, facts = sp._evaluate_t32(answer, orch + ctx_sub, [ctx_sub])
        self.assertEqual((v, facts["retrieval_where"]), (Verdict.PASS, "main"))

    def test_t32_counts_a_skill_md_read(self):
        answer = "grade = -1 means Pre-K."
        abs_read = [_use("r", "Read", {"file_path": "/daaf/.claude/skills/education-data-context/SKILL.md"}),
                    _res("r")]
        v, d, facts = sp._evaluate_t32(answer, [], [abs_read])
        self.assertEqual(v, Verdict.PASS, d)
        self.assertEqual((facts["retrieval_signal"], facts["retrieval_where"]),
                         ("Read education-data-context/SKILL.md", "subagent"))
        rel_read = [_use("r", "Read", {"file_path": ".claude/skills/education-data-source-ccd/SKILL.md"}), _res("r")]
        v, d, facts = sp._evaluate_t32(answer, rel_read)
        self.assertEqual(v, Verdict.PASS, d)
        self.assertEqual((facts["retrieval_signal"], facts["retrieval_where"]),
                         ("Read education-data-source-ccd/SKILL.md", "main"))
        self.assertIn("the main transcript", d)

    def test_t32_counts_any_education_data_skill(self):
        # Retrieval counts for any curated education-data-* skill, not only the
        # two that state the Pre-K fact, loaded or read, main or specialist.
        answer = "grade = -1 means Pre-K."
        for skill in ("education-data-source-ipeds", "/education-data-query", "x:education-data-explorer"):
            with self.subTest(skill=skill):
                recs = [_use("k", "Skill", {"skill": skill}), _res("k")]
                v, d, facts = sp._evaluate_t32(answer, [], [recs])
                self.assertEqual(v, Verdict.PASS, d)
                self.assertEqual(facts["retrieval_signal"], f"Skill {skill.lstrip('/').split(':')[-1]}")
        reads = {
            "/daaf/.claude/skills/education-data-source-ccd/references/variable-definitions.md":
                "Read education-data-source-ccd/references/variable-definitions.md",
            ".claude/skills/education-data-query/references/mirrors.yaml":
                "Read education-data-query/references/mirrors.yaml",
            "/daaf/.claude/skills/education-data-source-ipeds/SKILL.md": "Read education-data-source-ipeds/SKILL.md",
        }
        for path, signal in reads.items():
            with self.subTest(path=path):
                recs = [_use("r", "Read", {"file_path": path}), _res("r")]
                v, d, facts = sp._evaluate_t32(answer, recs)
                self.assertEqual(v, Verdict.PASS, d)
                self.assertEqual((facts["retrieval_signal"], facts["retrieval_where"]), (signal, "main"))
                self.assertIn(signal, d)

    def test_t32_normalizes_skill_read_paths(self):
        # A Read written with '..', './' or '//' segments opens the resolved
        # file, so it counts by that path; normalization keeps lookalikes out.
        answer = "grade = -1 means Pre-K."
        counted = {
            "/daaf/.claude/skills/x/../education-data-context/SKILL.md": "Read education-data-context/SKILL.md",
            "/daaf/.claude//skills/education-data-source-ccd/SKILL.md": "Read education-data-source-ccd/SKILL.md",
            "./.claude/skills/education-data-context/./SKILL.md": "Read education-data-context/SKILL.md",
            "/daaf/.claude/skills/education-data-source-ccd/references/../SKILL.md":
                "Read education-data-source-ccd/SKILL.md",
            "/daaf/.claude/skills/education-data-source-ccd/references/../references/variable-definitions.md":
                "Read education-data-source-ccd/references/variable-definitions.md",
        }
        for path, signal in counted.items():
            with self.subTest(path=path):
                recs = [_use("r", "Read", {"file_path": path}), _res("r")]
                v, d, facts = sp._evaluate_t32(answer, [], [recs])
                self.assertEqual(v, Verdict.PASS, d)
                self.assertEqual(facts["retrieval_signal"], signal)
        rejected = (
            "/x/myskills/education-data-context/SKILL.md",
            "/x/myskills//education-data-context/./SKILL.md",
            "/daaf/.claude/skills/education-data-context/../polars/SKILL.md",
            "/daaf/.claude/skills/education-data-context/SKILL.md/..",
            "/daaf/.claude/skills/education-data-/SKILL.md",
            "/daaf/.claude/skills/education-data-context",
        )
        for path in rejected:
            with self.subTest(path=path):
                recs = [_use("r", "Read", {"file_path": path}), _res("r")]
                v, d, facts = sp._evaluate_t32(answer, [], [recs])
                self.assertEqual(v, Verdict.WARN, d)
                self.assertIsNone(facts["retrieval_signal"])

    def test_t32_non_signals_still_warn(self):
        answer = "grade = -1 means Pre-K."
        skill_md = "/daaf/.claude/skills/education-data-context/SKILL.md"
        cases = {
            "errored SKILL.md read": [_use("r", "Read", {"file_path": skill_md}), _res("r", "err", True)],
            "SKILL.md read with no result": [_use("r", "Read", {"file_path": skill_md})],
            "errored reference page read": [
                _use("r", "Read", {"file_path": "/daaf/.claude/skills/education-data-source-ccd/references/"
                                                "variable-definitions.md"}), _res("r", "err", True)],
            "lookalike folder": [_use("r", "Read", {"file_path": "/x/myskills/education-data-context/SKILL.md"}),
                                 _res("r")],
            "unrelated skill": [_use("s", "Skill", {"skill": "polars"}), _res("s")],
            "prefix alone": [_use("s", "Skill", {"skill": "education-data-"}), _res("s")],
            "prefix not at the start": [_use("s", "Skill", {"skill": "my-education-data-skill"}), _res("s")],
            "CCD skill with no result": [_use("s", "Skill", {"skill": "education-data-source-ccd"})],
            "errored education-data skill": [_use("s", "Skill", {"skill": "education-data-query"}),
                                             _res("s", "err", True)],
        }
        for label, recs in cases.items():
            with self.subTest(case=label):
                v, d, facts = sp._evaluate_t32(answer, recs, [recs])
                self.assertEqual(v, Verdict.WARN, d)
                self.assertIn("answered without loading the skill", d)
                self.assertEqual((facts["retrieval_seen"], facts["retrieval_signal"], facts["retrieval_where"]),
                                 (False, None, None))

    def test_t32_tolerates_malformed_inputs(self):
        # The transcript is untrusted: a string or list `input`, or a non-list
        # subagent entry, must not raise.
        answer = "grade = -1 means Pre-K."
        bad = [_use("a", "Skill", "education-data-context"), _res("a"),
               _use("b", "Read", ["/daaf/.claude/skills/education-data-context/SKILL.md"]), _res("b"),
               _use("c", "Read", {"file_path": None}), _res("c"),
               {"type": "assistant", "message": "not-a-dict"}, "not-a-record"]
        v, d, facts = sp._evaluate_t32(answer, bad, [bad, "not-records", None])
        self.assertEqual(v, Verdict.WARN, d)
        self.assertFalse(facts["retrieval_seen"])
        self.assertEqual(sp._evaluate_t32(None, None, None)[0], Verdict.FAIL)

    def test_t32_live_data_lookup_shape_passes(self):
        # The 2026-11-01 anthropic-subscription shape (session 17375d34): the main
        # transcript loads the orchestrator and dispatches source-researcher; the
        # specialist loads the CCD skill, reads two CCD reference pages, then the
        # education-data-context SKILL.md. Results there carried no is_error key.
        main = [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o"),
                _use("m", "Read", {"file_path": "/daaf/.claude/skills/daaf-orchestrator/references/"
                                                "data-lookup-mode.md"}), _res("m"),
                _use("a", "Agent", {"subagent_type": "source-researcher", "prompt": "p"}), _res("a")]
        no_flag = {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "k", "content": "ok"}]}}
        sub = [_use("k", "Skill", {"skill": "education-data-source-ccd"}), no_flag,
               _use("r1", "Read", {"file_path": "/daaf/.claude/skills/education-data-source-ccd/references/"
                                                 "variable-definitions.md"}), _res("r1"),
               _use("r2", "Read", {"file_path": "/daaf/.claude/skills/education-data-context/SKILL.md"}), _res("r2")]
        v, d, facts = sp._evaluate_t32("**`grade = -1` in CCD enrollment data means Pre-Kindergarten.**", main, [sub])
        self.assertEqual(v, Verdict.PASS, d)
        self.assertEqual(facts, {"resumed_same_session": True, "prek_answer": True, "retrieval_seen": True,
                                 "retrieval_signal": "Skill education-data-source-ccd",
                                 "retrieval_where": "subagent", "subagent_transcripts": 1,
                                 "orchestrator_skill_loaded": True})
        self.assertIn("daaf-orchestrator loaded too", d)

    def test_t32_resume_check(self):
        sid = "d99a40c0-0875-4c55-b1ef-c58135df9c20"
        t31 = [{"type": "user", "message": {"role": "user", "content": sp.T31_PROMPT}},
               _use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        # The observed resume shape: a queue-operation record names the prompt,
        # then a user record carries it as string content.
        resumed = t31 + [{"type": "queue-operation", "operation": "enqueue", "content": sp.T32_PROMPT},
                         {"type": "user", "message": {"role": "user", "content": sp.T32_PROMPT}}]
        self.assertEqual(sp._t32_resume_check(sid, sid, resumed), (True, ""))
        self.assertEqual(sp._t32_resume_check(sid, "", resumed), (True, ""))
        listed = t31 + [{"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": sp.T32_PROMPT}]}}]
        self.assertEqual(sp._t32_resume_check(sid, sid, listed)[0], True)
        # The CLI reported another session: not continued, whatever the transcript holds.
        state, reason = sp._t32_resume_check(sid, "0123abcd-0000-4000-8000-000000000000", resumed)
        self.assertEqual(state, False)
        self.assertIn("0123abcd", reason)
        # The T3.1 transcript did not gain the T3.2 turn. A queue-operation
        # record or a tool_result with the same text is not a user prompt.
        not_a_prompt = t31 + [{"type": "queue-operation", "operation": "enqueue", "content": sp.T32_PROMPT},
                              _res("x", sp.T32_PROMPT)]
        for recs in (t31, not_a_prompt):
            with self.subTest(records=len(recs)):
                state, reason = sp._t32_resume_check(sid, sid, recs)
                self.assertEqual(state, False)
                self.assertIn("no 'Yes, go ahead.' user turn", reason)
        # No main transcript: the resume cannot be checked.
        self.assertEqual(sp._t32_resume_check(sid, sid, [])[0], None)

    def test_t32_fails_when_the_resume_did_not_continue_the_session(self):
        answer = "grade = -1 means Pre-K."
        sub = [_use("k", "Skill", {"skill": "education-data-source-ccd"}), _res("k")]
        v, d, facts = sp._evaluate_t32(answer, [], [sub], (False, "the T3.1 transcript has no 'Yes, go ahead.' "
                                                                  "user turn"))
        self.assertEqual(v, Verdict.FAIL, d)
        self.assertTrue(d.startswith("The resumed call did not continue the T3.1 session: the T3.1 transcript"), d)
        self.assertIs(facts["resumed_same_session"], False)
        # An unchecked resume (no main transcript) turns a PASS into a WARN and says why.
        v, d, facts = sp._evaluate_t32(answer, [], [sub], sp._t32_resume_check("sid", "sid", []))
        self.assertEqual(v, Verdict.WARN, d)
        self.assertIn("Skill education-data-source-ccd", d)
        self.assertTrue(d.startswith("The resume is not proven: main transcript missing, empty or unreadable."), d)
        self.assertIsNone(facts["resumed_same_session"])

    def test_t32_unchecked_resume_leads_the_warn_detail(self):
        # The report's Observed cell keeps the first 200 characters of a WARN
        # detail, so the unchecked-resume reason comes first, whether or not a
        # retrieval was seen, and the retrieval reason still fits behind it.
        answer = "grade = -1 means Pre-K."
        unchecked = sp._t32_resume_check("sid", "sid", [])
        self.assertIsNone(unchecked[0])
        long_read = [_use("r", "Read", {"file_path": "/daaf/.claude/skills/education-data-source-ccd/references/"
                                                     "variable-definitions.md"}), _res("r")]
        cases = {"retrieval": ([long_read], "with skill retrieval in a specialist (subagent) transcript"),
                 "no retrieval": ([[]], "Pre-K answered without loading the skill")}
        for label, (subs, reason) in cases.items():
            with self.subTest(case=label):
                v, d, facts = sp._evaluate_t32(answer, [], subs, unchecked)
                self.assertEqual(v, Verdict.WARN, d)
                head = d[:200]
                self.assertTrue(head.startswith("The resume is not proven: main transcript missing, empty or "
                                                "unreadable."), d)
                self.assertIn("resume", head)
                self.assertIn(reason, head)
                self.assertIsNone(facts["resumed_same_session"])
        # The no-retrieval WARN keeps its transcript count inside the cell too.
        self.assertIn("1 specialist transcript(s) scanned", sp._evaluate_t32(answer, [], [[]], unchecked)[1][:200])

    # The live main-transcript grep (session d99a40c0, anthropic-subscription,
    # 2026-11-02) and the first of the four lines of output it returned, shortened.
    _LIVE_GREP = ('grep -n "grade = -1\\|grade=-1\\|lowest_grade_offered\\|Pre-K | Inclusion" '
                  "/daaf/.claude/skills/education-data-source-ccd/references/variable-definitions.md "
                  "/daaf/.claude/skills/education-data-source-ccd/references/data-quality.md "
                  "/daaf/.claude/skills/education-data-source-ccd/SKILL.md")
    _LIVE_GREP_OUT = ("/daaf/.claude/skills/education-data-source-ccd/references/variable-definitions.md:20:> "
                      "**Semantic trap:** In enrollment data, `grade = -1` means **Pre-K**, NOT missing!")

    def test_t32_counts_a_bash_read_of_skill_text(self):
        # A Bash command naming a path under an education-data-* skill, with a
        # non-empty non-error result, is a (narrower) retrieval signal: the
        # first such path in the command, file or folder, absolute or relative.
        answer = "grade = -1 means Pre-K."
        cases = {
            self._LIVE_GREP: "Bash education-data-source-ccd/references/variable-definitions.md",
            "grep -n Pre-K .claude/skills/education-data-context/SKILL.md": "Bash education-data-context/SKILL.md",
            "grep -rn 'Pre-K' /daaf/.claude/skills/education-data-source-ccd/": "Bash education-data-source-ccd/",
            "grep -rn Pre-K skills/education-data-context": "Bash education-data-context/",
            'cat "/daaf/.claude/skills/education-data-context/SKILL.md"|head -5': "Bash education-data-context/SKILL.md",
            "grep -n x /daaf/.claude/skills/polars/SKILL.md /daaf/.claude/skills/education-data-query/SKILL.md":
                "Bash education-data-query/SKILL.md",
            "grep -n x /daaf/.claude/skills/x/../education-data-context/./SKILL.md;echo":
                "Bash education-data-context/SKILL.md",
        }
        for command, signal in cases.items():
            with self.subTest(command=command):
                recs = [_use("b", "Bash", {"command": command}), _res("b", self._LIVE_GREP_OUT)]
                v, d, facts = sp._evaluate_t32(answer, recs)
                self.assertEqual(v, Verdict.PASS, d)
                self.assertEqual((facts["retrieval_seen"], facts["retrieval_signal"], facts["retrieval_where"]),
                                 (True, signal, "main"))
                self.assertIn("in the main transcript by a Bash read (only its output reaches the model)", d)
                self.assertIn(signal, d)
        # In a specialist transcript, and with a list-shaped tool_result body.
        listed = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "b",
                                                            "content": [{"type": "text", "text": "20: Pre-K"}]}]}}
        sub = [_use("b", "Bash", {"command": self._LIVE_GREP}), listed]
        v, d, facts = sp._evaluate_t32(answer, [], [[], sub])
        self.assertEqual(v, Verdict.PASS, d)
        self.assertEqual((facts["retrieval_signal"], facts["retrieval_where"]),
                         ("Bash education-data-source-ccd/references/variable-definitions.md", "subagent"))
        self.assertIn("specialist (subagent) transcript by a Bash read", d)

    def test_t32_bash_non_signals_still_warn(self):
        answer = "grade = -1 means Pre-K."
        ccd_page = "/daaf/.claude/skills/education-data-source-ccd/references/variable-definitions.md"
        grep = f"grep -n Pre-K {ccd_page}"
        cases = {
            "empty output": [_use("b", "Bash", {"command": grep}), _res("b", "")],
            "whitespace output": [_use("b", "Bash", {"command": grep}), _res("b", " \n ")],
            "no-output placeholder": [_use("b", "Bash", {"command": grep}),
                                      _res("b", "(Bash completed with no output)")],
            # A null body, a [None] body and a text block whose text is null are
            # no output, never the text "None".
            "null body": [_use("b", "Bash", {"command": grep}), _res("b", None)],
            "[None] body": [_use("b", "Bash", {"command": grep}), _res("b", [None])],
            "null text block": [_use("b", "Bash", {"command": grep}), _res("b", [{"type": "text", "text": None}])],
            "errored result": [_use("b", "Bash", {"command": grep}), _res("b", "Exit code 1", True)],
            "no recorded result": [_use("b", "Bash", {"command": grep})],
            "non-education skill folder": [_use("b", "Bash", {"command": "grep -rn x /daaf/.claude/skills/polars/"}),
                                           _res("b", "hit")],
            "resolves outside the skill": [
                _use("b", "Bash", {"command": "cat /daaf/.claude/skills/education-data-context/../polars/SKILL.md"}),
                _res("b", "hit")],
            "lookalike folder": [_use("b", "Bash", {"command": "cat /x/myskills/education-data-context/SKILL.md"}),
                                 _res("b", "hit")],
            "lookalike after '/'": [_use("b", "Bash", {"command": "ls https://x/myskills/education-data-context/"}),
                                    _res("b", "hit")],
            "relative path after ':'": [
                _use("b", "Bash", {"command": "export PATH=$PATH:skills/education-data-context/bin"}),
                _res("b", "hit"),
                _use("c", "Bash", {"command": "scp host:skills/education-data-context/SKILL.md ."}),
                _res("c", "hit")],
            "prefix alone": [_use("b", "Bash", {"command": "ls /daaf/.claude/skills/education-data-/"}),
                             _res("b", "hit")],
            "name only in a pattern": [_use("b", "Bash", {"command": "grep -rln education-data-context .claude/"}),
                                       _res("b", "hit")],
            "not a Bash call": [_use("b", "Glob", {"command": grep}), _res("b", "hit")],
            "malformed input": [_use("b", "Bash", grep), _res("b", "hit"),
                                _use("c", "Bash", {"command": None}), _res("c", "hit")],
        }
        for label, recs in cases.items():
            with self.subTest(case=label):
                v, d, facts = sp._evaluate_t32(answer, recs, [recs])
                self.assertEqual(v, Verdict.WARN, d)
                self.assertIn("answered without loading the skill", d)
                self.assertIn("or Bash command naming a path under one with output", d)
                self.assertEqual((facts["retrieval_seen"], facts["retrieval_signal"], facts["retrieval_where"]),
                                 (False, None, None))

    def test_tool_results_text_null_bodies_are_empty(self):
        # A null or absent body, a null list item and a block with no or null
        # text flatten to "" (never "None"); a string body is its own text, and a
        # dict body is rendered with str().
        def flat(block_content, absent=False):
            block = {"type": "tool_result", "tool_use_id": "t", "is_error": False}
            if not absent:
                block["content"] = block_content
            return sp._tool_results_text([{"type": "user", "message": {"content": [block]}}])["t"][1]
        for label, body, want in (("null", None, ""), ("[None]", [None], ""), ("[]", [], ""),
                                  ("null text", [{"type": "text", "text": None}], ""),
                                  ("image block", [{"type": "image", "source": {}}], ""),
                                  ("mixed list", ["a", None, {"type": "text", "text": "b"}], "a b"),
                                  ("string", "x", "x"),
                                  ("dict", {"type": "text", "text": "y"}, str({"type": "text", "text": "y"}))):
            with self.subTest(body=label):
                self.assertEqual(flat(body), want)
        self.assertEqual(flat(None, absent=True), "")
        # T2.7, the helper's other caller, classifies a null body as it does an
        # empty one: a non-error result ran (FAIL), an errored one is
        # unrecognized (WARN), and its excerpt quotes no "None".
        pip = _use("p", "Bash", {"command": "pip install requests"})
        self.assertEqual(sp._evaluate_t27([pip, _res("p", None, False)], read_half=False)[0], Verdict.FAIL)
        for body in (None, [None], ""):
            with self.subTest(t27_error_body=body):
                v, facts, detail = sp._evaluate_t27([pip, _res("p", body, True)], read_half=False)
                self.assertEqual((v, facts["pip_unrecognized"]), (Verdict.WARN, 1), detail)
                self.assertNotIn("None", detail)

    def test_t32_bash_label_shows_glob_and_brace_paths_as_written(self):
        # The shell is not parsed: a glob or brace path counts, and the label
        # shows it as written after the skills/ segment, not as a skill name.
        answer = "grade = -1 means Pre-K."
        for command, signal in (
                ("grep -n Pre-K /daaf/.claude/skills/education-data-*/SKILL.md", "Bash education-data-*/SKILL.md"),
                ("cat /daaf/.claude/skills/education-data-{context,source-ccd}/SKILL.md",
                 "Bash education-data-{context,source-ccd}/SKILL.md")):
            with self.subTest(command=command):
                recs = [_use("b", "Bash", {"command": command}), _res("b", self._LIVE_GREP_OUT)]
                v, d, facts = sp._evaluate_t32(answer, recs)
                self.assertEqual(v, Verdict.PASS, d)
                self.assertEqual(facts["retrieval_signal"], signal)

    def test_t32_bash_path_may_follow_equals(self):
        # "skills" may follow '=' (an option's value) as well as '/' or the token
        # start; a path after ':' with a '/' before "skills" counts through it.
        answer = "grade = -1 means Pre-K."
        for command, signal in (
                ("grep --file=skills/education-data-context/SKILL.md x", "Bash education-data-context/SKILL.md"),
                ("git show HEAD:.claude/skills/education-data-context/SKILL.md",
                 "Bash education-data-context/SKILL.md")):
            with self.subTest(command=command):
                recs = [_use("b", "Bash", {"command": command}), _res("b", self._LIVE_GREP_OUT)]
                v, d, facts = sp._evaluate_t32(answer, recs)
                self.assertEqual(v, Verdict.PASS, d)
                self.assertEqual(facts["retrieval_signal"], signal)

    def test_t32_skill_and_read_signals_outrank_a_bash_read(self):
        # Skill loads and Reads are sought in every transcript before any Bash
        # read, so the live sessions record the specialist's Skill load.
        answer = "grade = -1 means Pre-K."
        bash = [_use("b", "Bash", {"command": self._LIVE_GREP}), _res("b", self._LIVE_GREP_OUT)]
        skill = [_use("k", "Skill", {"skill": "education-data-source-ccd"}), _res("k")]
        read = [_use("r", "Read", {"file_path": "/daaf/.claude/skills/education-data-context/SKILL.md"}), _res("r")]
        cases = (
            ("Bash in main, Skill in a subagent", bash, [skill], "Skill education-data-source-ccd", "subagent"),
            ("Bash in main, Read in a subagent", bash, [read], "Read education-data-context/SKILL.md", "subagent"),
            ("Bash in subagent 1, Skill in subagent 2", [], [bash, skill], "Skill education-data-source-ccd",
             "subagent"),
            ("Bash in main and a subagent", bash, [bash],
             "Bash education-data-source-ccd/references/variable-definitions.md", "main"),
        )
        for label, main, subs, signal, where in cases:
            with self.subTest(case=label):
                v, d, facts = sp._evaluate_t32(answer, main, subs)
                self.assertEqual(v, Verdict.PASS, d)
                self.assertEqual((facts["retrieval_signal"], facts["retrieval_where"]), (signal, where))
                self.assertEqual("by a Bash read" in d, signal.startswith("Bash "), d)
        # No retrieval_kind fact: the signal's first word names the kind.
        self.assertNotIn("retrieval_kind", sp._evaluate_t32(answer, bash)[2])

    def test_t32_bash_details_lead_with_the_reason(self):
        # The report's Observed cell keeps the first 200 characters: a Bash-only
        # PASS (or unchecked-resume WARN) says it was a Bash read inside them,
        # and the no-retrieval WARN keeps its reason there with the longer
        # parenthetical.
        answer = "grade = -1 means Pre-K."
        bash = [_use("b", "Bash", {"command": self._LIVE_GREP}), _res("b", self._LIVE_GREP_OUT)]
        orch = [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        unchecked = sp._t32_resume_check("sid", "sid", [])
        for label, main, subs, resume, want in (
                ("main, resumed", orch + bash, [], (True, ""), Verdict.PASS),
                ("subagent, resumed", orch, [[], [], bash], (True, ""), Verdict.PASS),
                ("subagent, unchecked resume", [], [bash], unchecked, Verdict.WARN)):
            with self.subTest(case=label):
                v, d, _ = sp._evaluate_t32(answer, main, subs, resume)
                self.assertEqual(v, want, d)
                head = d[:200]
                self.assertIn("grade -1 is Pre-K, with skill retrieval in", head)
                self.assertIn("by a Bash read", head)
                if resume[0] is None:
                    self.assertTrue(head.startswith("The resume is not proven: main transcript missing"), d)
                else:
                    self.assertIn("Bash education-data-source-ccd/", head)
        for subs in ([], [[]], [[], [], []]):
            for resume in ((True, ""), unchecked):
                with self.subTest(subagents=len(subs), resume=resume[0]):
                    v, d, _ = sp._evaluate_t32(answer, [], subs, resume)
                    self.assertEqual(v, Verdict.WARN, d)
                    head = d[:200]
                    self.assertIn("answered without loading the skill", head)
                    self.assertIn(f"{len(subs)} specialist transcript(s) scanned", head)
                    self.assertIn("Bash command naming a path under one", d)


def _fake_run(response="SMOKE_TIER1_COMPLETE", init=None):
    result = types.SimpleNamespace(
        raw_json={"messages": [{"type": "result", "subtype": "success", "is_error": False, "api_error_status": None}]},
        error="", response_text=response, total_cost_usd=0.25, duration_seconds=3.0, input_tokens=4,
        output_tokens=9, total_turns=2, model_id="m",
        model_identity=types.SimpleNamespace(claude_cli_model_usage_ids=["claude-opus-5-5"]))
    return result, {"session_id": str(uuid.UUID(int=7)), "init": init or {}, "window_start": "a", "window_end": "b"}


class TierRunnerWiringTests(unittest.TestCase):
    """Runner entry points with every live seam faked: no claude -p is executed."""

    def test_run_tier_a_and_3_signatures_mirror_tier1(self):
        import inspect
        t1 = list(inspect.signature(sp.run_tier1).parameters)[:3]
        for fn in (sp.run_tier_a, sp.run_tier_3, sp.run_tier2):
            self.assertEqual(list(inspect.signature(fn).parameters)[:3], t1, fn.__name__)
        self.assertEqual(list(inspect.signature(sp.run_tier_n).parameters), ["route", "timeout", "evidence_dir"])

    def test_tier_a_budget_and_permission_mode(self):
        with mock.patch.object(sp, "execute_smoke_run", return_value=_fake_run("no")) as ex, \
             mock.patch.object(sp, "find_transcript", return_value=None):
            (r,) = sp.run_tier_a("", {}, 5, route=rd.ROUTE_ANTHROPIC_API)
        kw = ex.call_args.kwargs
        self.assertEqual((kw["permission_mode"], kw["output_format"]), ("auto", "stream-json"))
        self.assertEqual(kw["max_budget_usd"], sp.ANTHROPIC_API_BUDGET_USD["A"])
        self.assertEqual((r.probe_id, r.verdict, r.cost_usd), ("TA.1", Verdict.FAIL, 0.25))
        self.assertEqual(len(r.session_ids), 1)
        self.assertTrue(r.hint)

    # The facts each Tier 3 probe records, and the ones it must not.
    _T31_FACTS = {"orchestrator_skill_loaded", "mode_named", "asks_confirmation", "prek_already_answered"}
    _T32_FACTS = {"resumed_same_session", "prek_answer", "retrieval_seen", "retrieval_signal", "retrieval_where",
                  "subagent_transcripts", "orchestrator_skill_loaded"}
    _REMOVED_FACTS = {"dispatch_seen", "subagent_transcripts_before_t32", "retrieval_before_t32"}

    @staticmethod
    def _facts(result, first_key):
        return json.loads(next(e.output for e in result.evidence if e.output.startswith('{"' + first_key + '"')))

    def _golden_path(self, t32_main=None, t32_run=None, sub_skill="education-data-source-ipeds"):
        """run_tier_3 over fake transcripts: the T3.1 main transcript (prompt,
        orchestrator load, Data Lookup dispatch), the same file after the T3.2
        call (t32_main; by default it gained the resumed user turn) and one
        specialist transcript loading sub_skill. Returns (r1, r2, calls), where
        calls records how many execute_smoke_run calls had happened each time
        find_subagent_transcripts was called."""
        t31 = [{"type": "user", "message": {"role": "user", "content": sp.T31_PROMPT}},
               _use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o"),
               _use("a", "Agent", {"subagent_type": "source-researcher"}), _res("a")]
        if t32_main is None:
            t32_main = t31 + [{"type": "user", "message": {"role": "user", "content": sp.T32_PROMPT}}]
        t31_path, t32_path, sub_path = Path("t31-fake.jsonl"), Path("t32-fake.jsonl"), Path("agent-fake.jsonl")
        loaded = {t31_path: t31, t32_path: t32_main,
                  sub_path: [_use("k", "Skill", {"skill": sub_skill}), _res("k")]}
        ex = mock.Mock(side_effect=[_fake_run("Data Lookup. Sound good?"), t32_run or _fake_run("grade -1 is Pre-K")])
        calls = []
        with mock.patch.object(sp, "execute_smoke_run", ex), \
             mock.patch.object(sp, "find_transcript", side_effect=[t31_path, t32_path]), \
             mock.patch.object(sp, "find_subagent_transcripts",
                               side_effect=lambda sid: (calls.append(ex.call_count), [sub_path])[1]), \
             mock.patch.object(sp, "load_transcript_records", side_effect=lambda p: list(loaded.get(p, []))):
            r1, r2 = sp.run_tier_3("", {}, 5, route=rd.ROUTE_ANTHROPIC)
        return r1, r2, calls

    def test_tier3_resumes_same_session(self):
        runs = [_fake_run("Ad Hoc Collaboration mode. Shall I proceed?"), _fake_run("grade -1 is Pre-K")]
        with mock.patch.object(sp, "execute_smoke_run", side_effect=runs) as ex, \
             mock.patch.object(sp, "find_transcript", return_value=None), \
             mock.patch.object(sp, "find_subagent_transcripts", return_value=[]) as subs:
            results = sp.run_tier_3("", {}, 5, route=rd.ROUTE_ANTHROPIC)
        # No transcript: T3.1 cannot check the orchestrator load (WARN), and
        # T3.2 sees no retrieval and cannot check the resume (WARN).
        self.assertEqual([r.verdict for r in results], [Verdict.WARN, Verdict.WARN])
        self.assertEqual([r.name for r in results], ["Orchestrator engaged", "Golden path (resume + skill retrieval)"])
        self.assertTrue(results[0].detail.startswith("daaf-orchestrator load not checked: main transcript missing"),
                        results[0].detail)
        self.assertIn("answered without loading the skill", results[1].detail)
        self.assertTrue(results[1].detail.startswith("The resume is not proven: main transcript missing"),
                        results[1].detail)
        self.assertTrue(results[0].hint and results[1].hint)
        self.assertEqual(ex.call_args_list[1].kwargs["resume_session_id"], runs[0][1]["session_id"])
        self.assertIsNone(ex.call_args_list[0].kwargs["max_budget_usd"])
        subs.assert_called_once_with(runs[0][1]["session_id"])
        facts1 = self._facts(results[0], "orchestrator_skill_loaded")
        self.assertEqual(set(facts1), self._T31_FACTS)
        self.assertEqual(facts1["mode_named"], "Ad Hoc Collaboration")
        self.assertIsNone(facts1["orchestrator_skill_loaded"])
        facts2 = self._facts(results[1], "resumed_same_session")
        self.assertEqual(set(facts2), self._T32_FACTS)
        self.assertIsNone(facts2["resumed_same_session"])
        # Both probes leave the orchestrator load unchecked, and neither says it did not load.
        self.assertIsNone(facts2["orchestrator_skill_loaded"])
        self.assertNotIn("did not load", results[1].detail)

    def test_tier3_t31_warns_when_no_main_transcript_was_found(self):
        # An empty main transcript (none found, or unreadable) leaves the
        # orchestrator load unchecked: WARN, the fact recorded as None, the
        # detail saying so within the 200-character Observed cell, and a hint
        # that covers the case. A transcript without the load is "did not load".
        runs = [_fake_run("Data Lookup. Sound good?"), _fake_run("grade -1 is Pre-K")]
        with mock.patch.object(sp, "execute_smoke_run", side_effect=runs), \
             mock.patch.object(sp, "find_transcript", return_value=None), \
             mock.patch.object(sp, "find_subagent_transcripts", return_value=[]), \
             mock.patch.object(sp, "load_transcript_records", return_value=[]):
            r1, _ = sp.run_tier_3("", {}, 5, route=rd.ROUTE_ANTHROPIC)
        self.assertEqual(r1.verdict, Verdict.WARN, r1.detail)
        self.assertIsNone(self._facts(r1, "orchestrator_skill_loaded")["orchestrator_skill_loaded"])
        self.assertTrue(r1.detail.startswith("daaf-orchestrator load not checked: main transcript missing, empty "
                                             "or unreadable."), r1.detail)
        self.assertNotIn("did not load", r1.detail)
        self.assertLessEqual(len(r1.detail), 200, r1.detail)
        self.assertIn("T1.2", r1.hint)
        prompt_only = [{"type": "user", "message": {"role": "user", "content": sp.T31_PROMPT}}]
        v, d, facts = sp._evaluate_t31("Data Lookup. Sound good?", prompt_only)
        self.assertEqual((v, facts["orchestrator_skill_loaded"]), (Verdict.WARN, False), d)
        self.assertTrue(d.startswith("daaf-orchestrator did not load in the main transcript."), d)

    def test_tier3_golden_path_passes_and_reads_subagents_once_after_t32(self):
        r1, r2, calls = self._golden_path()
        self.assertEqual((r1.verdict, r2.verdict), (Verdict.PASS, Verdict.PASS), (r1.detail, r2.detail))
        self.assertTrue(r1.detail.startswith("daaf-orchestrator loaded in the main transcript."), r1.detail)
        self.assertIn("Skill education-data-source-ipeds", r2.detail)
        self.assertEqual((r1.hint, r2.hint), ("", ""))
        # Subagent transcripts are read once, after both claude -p calls.
        self.assertEqual(calls, [2])
        facts1, facts2 = self._facts(r1, "orchestrator_skill_loaded"), self._facts(r2, "resumed_same_session")
        self.assertEqual(set(facts1), self._T31_FACTS)
        self.assertEqual(set(facts2), self._T32_FACTS)
        self.assertFalse(self._REMOVED_FACTS & (set(facts1) | set(facts2)))
        self.assertEqual((facts2["resumed_same_session"], facts2["retrieval_where"], facts2["subagent_transcripts"]),
                         (True, "subagent", 1))
        for gone in ("predate the T3.2 call", "already shows retrieval"):
            self.assertNotIn(gone, r2.detail)

    def test_tier3_fails_when_the_resume_did_not_continue_the_session(self):
        # The T3.1 transcript did not gain the T3.2 turn.
        _, r2, _ = self._golden_path(t32_main=[])
        self.assertEqual(r2.verdict, Verdict.WARN, r2.detail)   # no main transcript at all: unchecked
        t31_only = [{"type": "user", "message": {"role": "user", "content": sp.T31_PROMPT}},
                    _use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        _, r2, _ = self._golden_path(t32_main=t31_only)
        self.assertEqual(r2.verdict, Verdict.FAIL, r2.detail)
        self.assertTrue(r2.detail.startswith("The resumed call did not continue the T3.1 session"), r2.detail)
        self.assertIs(self._facts(r2, "resumed_same_session")["resumed_same_session"], False)
        self.assertTrue(r2.hint)
        # The CLI's own result reports another session id.
        other_run = _fake_run("grade -1 is Pre-K")
        other_run[0].session_id = "0123abcd-0000-4000-8000-000000000000"
        _, r2, _ = self._golden_path(t32_run=other_run)
        self.assertEqual(r2.verdict, Verdict.FAIL, r2.detail)
        self.assertIn("the CLI reported session 0123abcd", r2.detail)
        # The same id from the CLI keeps the PASS.
        same_run = _fake_run("grade -1 is Pre-K")
        same_run[0].session_id = str(uuid.UUID(int=7))
        _, r2, _ = self._golden_path(t32_run=same_run)
        self.assertEqual(r2.verdict, Verdict.PASS, r2.detail)

    def test_tier3_skips_t32_when_t31_reached_no_real_model(self):
        dead = _fake_run("")
        dead[0].error = "Timed out after 5s"
        with mock.patch.object(sp, "execute_smoke_run", side_effect=[dead]) as ex, \
             mock.patch.object(sp, "find_transcript", return_value=None), \
             mock.patch.object(sp, "find_subagent_transcripts", return_value=[]) as subs:
            r1, r2 = sp.run_tier_3("", {}, 5, route=rd.ROUTE_ANTHROPIC)
        self.assertEqual((r1.verdict, r2.verdict), (Verdict.FAIL, Verdict.SKIP))
        self.assertIn("did not reach a real model", r1.detail)
        self.assertEqual(ex.call_count, 1)
        subs.assert_not_called()

    def test_tier1_new_probes_and_stream_json(self):
        init = {"apiKeySource": "none", "model": "claude-opus-5-5[1m]"}
        with mock.patch.object(sp, "execute_smoke_run", return_value=_fake_run(init=init)) as ex, \
             mock.patch.object(sp, "find_transcript", return_value=None), \
             mock.patch.object(sp, "find_session_archive", return_value={"jsonl": "a", "md": "b"}), \
             mock.patch.object(sp, "_run_t16"):
            results = {r.probe_id: r for r in sp.run_tier1("", {}, 5, route=rd.ROUTE_ANTHROPIC)}
        self.assertEqual(ex.call_args.kwargs["output_format"], "stream-json")
        self.assertEqual(results["T1.8"].verdict, Verdict.PASS, results["T1.8"].detail)
        self.assertEqual(results["T1.10"].verdict, Verdict.PASS)
        self.assertEqual(results["T1.9"].verdict, Verdict.FAIL)   # empty transcript: neither signal
        self.assertTrue(results["T1.9"].hint)
        self.assertEqual(results["T1.1"].cost_usd, 0.25)

    def test_tier_d_td7_default_on_shim_routes_only(self):
        ev = _scratch(self, "tierd")
        stub = rd.ProbeResult("X", "x", "D", verdict=Verdict.PASS)
        # TD.9 (local services) is stubbed too: this test is about TD.7 routing,
        # and the real TD.9 would start marimo/code-server three times.
        with mock.patch.object(sp, "_run_battery_cmd", return_value=stub) as bat, \
             mock.patch.object(sp, "_run_import_smoke", return_value=stub), \
             mock.patch.object(sp, "probe_local_services", return_value=stub):
            off = sp.run_tier_d(False, 5, ev, route=rd.ROUTE_ANTHROPIC)
            on = sp.run_tier_d(False, 5, ev, route=rd.ROUTE_CHATGPT)
            forced = sp.run_tier_d(False, 5, ev, route=rd.ROUTE_ANTHROPIC, tier_d_all=True)
        td7_off = [r for r in off if r.probe_id == "TD.7"]
        self.assertEqual(td7_off[0].verdict, Verdict.SKIP)
        shim_cmds = [c.args[2] for c in bat.call_args_list if c.args[0] == "TD.7"]
        self.assertEqual(len(shim_cmds), 2)  # shim route + --tier-d-all
        self.assertIn("tests/provider_shim", shim_cmds[0])
        self.assertEqual(len(on), len(forced))

    def test_latest_import_smoke_revision(self):
        paths = [Path("smoke_imports.py"), Path("smoke_imports_c.py"), Path("smoke_imports_a.py")]
        self.assertEqual(sp._latest_revision(paths).name, "smoke_imports_c.py")


class ContractAndHintTests(unittest.TestCase):
    def test_probe_result_contract_fields(self):
        d = rd.ProbeResult("T0.1", "n", "0").to_dict()
        for key, default in (("duration_s", None), ("session_ids", []), ("cost_usd", None), ("hint", "")):
            self.assertIn(key, d)
            self.assertEqual(d[key], default)

    def test_every_failable_probe_has_a_hint(self):
        failable = ["T0.0", "T0.1", "T0.3", "T0.4", "T0.5", "T0.6", "T0.7", "T0.8", "T0.9", "T0.10", "T0.11",
                    "T0.12", "T0.14", "T0.15", "T0.16", "T0.17", "T0.18", "T0.19", "T0.20", "T0.21", "T0.22",
                    "T0.23", "T0.24", "T0.ABORT", "T1.1", "T1.2", "T1.3", "T1.5", "T1.6", "T1.7", "T1.8", "T1.9",
                    "T1.10", "T2.1", "T2.2", "T2.3", "T2.4", "T2.5", "T2.6", "T2.7", "T2.8", "TD.0", "TD.1",
                    "TD.2", "TD.3", "TD.4", "TD.5", "TD.6", "TD.7", "TD.8", "TD.9", "TN.1", "TN.2", "TN.3",
                    "TN.4", "TA.1", "T3.1", "T3.2"]
        for pid in failable:
            with self.subTest(probe=pid):
                self.assertTrue(sp.PROBE_HINTS.get(pid, "").strip())

    def test_shim_log_hint_covers_every_warn_and_fail_signal(self):
        # Every signal _evaluate_shim_log can WARN or FAIL on gets advice in the
        # T0.20 hint; context_length_exceeded (F21, F32) points at the context
        # ceiling (T0.4) and the shim versions that changed its shape.
        hint = sp.PROBE_HINTS["T0.20"]
        for signal in ("claude-*", "whitespace", "unsupported_value", "insufficient_quota",
                       "context_length_exceeded", "turn-state header"):
            with self.subTest(signal=signal):
                self.assertIn(signal, hint)
        for fragment in ("CLAUDE_CODE_MAX_CONTEXT_TOKENS", "T0.4", "1.4.10", "502", "1.4.11",
                         "Prompt is too long (backend context length exceeded)"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, hint)

    def test_t3_hints_fit_the_summary_cell(self):
        # run_deploy_smoke cuts the problems table's "Likely cause" cell at 300
        # characters; the Tier 3 hints must survive whole. apply_hints gives a
        # probe's hint to every FAIL and WARN, so each hint covers the probe's
        # own causes, an unchecked transcript (T1.2) and the live-run gate (T1.1).
        import smoke_package
        wanted = {
            "T3.1": ("If daaf-orchestrator did not load", "remind-orchestrator.sh", "T0.6", "T1.9", "T0.23",
                     "transcript", "not checked: see T1.2", "live-run warning or failure", "T1.1"),
            "T3.2": ("Pre-K", "resume", "education-data-*", "transcripts/<sid8>/main.jsonl",
                     "transcripts/<sid8>/subagents/", "specialist dispatch", "Resume not proven: see T1.2",
                     "live-run warning or FAIL", "T1.1"),
        }
        for pid, texts in wanted.items():
            hint = sp.PROBE_HINTS[pid]
            self.assertLess(len(hint), 300, pid)
            for text in texts:
                with self.subTest(probe=pid, text=text):
                    self.assertIn(text, hint)
            for marker in smoke_package.DROP_LINE_MARKERS:
                self.assertNotIn(marker, hint.lower())
            self.assertNotRegex(hint, r"(?i)\bwhere(?: to fix)?:")
            # Gate adherence is not graded, so no hint sends the reader to the mode gate.
            self.assertNotIn("mode-confirmation gate", hint)

    def test_t3_where_to_fix_locations(self):
        import run_deploy_smoke as runner
        t31 = runner._where_to_fix("T3.1", sp.PROBE_HINTS["T3.1"])
        self.assertEqual(t31, dict(runner._FIX_LOCATIONS)["T3.1"])
        for loc in (".claude/skills/daaf-orchestrator/", ".claude/hooks/remind-orchestrator.sh",
                    ".claude/settings.json"):
            with self.subTest(loc=loc):
                self.assertIn(loc, t31)
                path = loc.split(" ")[0]
                self.assertTrue((Path(runner.BASE_DIR) / path).exists(), path)
        t32 = runner._where_to_fix("T3.2", sp.PROBE_HINTS["T3.2"])
        for loc in (".claude/skills/daaf-orchestrator/references/data-lookup-mode.md", ".claude/agents/",
                    "search-agent", "source-researcher", ".claude/skills/education-data-*/"):
            with self.subTest(loc=loc):
                self.assertIn(loc, t32)
        # The summary table cuts the Where-to-fix cell at 200 characters.
        for prefix, loc in list(runner._FIX_LOCATIONS) + [("*.CRASH", runner._CRASH_LOCATION)]:
            with self.subTest(prefix=prefix):
                self.assertLessEqual(len(loc), 200)
                self.assertEqual(runner._cell(loc, 200), loc)

    def test_crash_records_route_to_the_harness(self):
        # Every synthetic *.CRASH record routes to scripts/deploy_smoke/ and the
        # Verdict Semantics synthetic-records paragraph, never to a tier's
        # install location or a probe row that does not exist.
        import run_deploy_smoke as runner
        crash_ids = ["T0.CRASH", "T1.CRASH", "T2.CRASH", "TA.CRASH", "T3.CRASH", "TN.CRASH", "TD.CRASH",
                     "POST.CRASH", "RUN.CRASH"]
        for pid in crash_ids:
            with self.subTest(probe=pid):
                loc = runner._where_to_fix(pid, "")
                self.assertEqual(loc, runner._CRASH_LOCATION)
                self.assertTrue(loc.startswith("scripts/deploy_smoke/"))
                self.assertIn("interpreting-results.md § Verdict Semantics, Synthetic records", loc)
                self.assertNotIn(f"(row {pid})", loc)
        # The runner's own crash records, with their real hints, route the same way.
        for tier, pid in (("3", "T3.CRASH"), ("1", "T1.CRASH"), ("run", "RUN.CRASH"),
                          (runner.POST_RUN_TIER, "POST.CRASH")):
            with self.subTest(tier=tier):
                r = runner._crash_result(tier, "fixture", RuntimeError("boom"))
                self.assertEqual(r.probe_id, pid)
                self.assertEqual(runner._where_to_fix(r.probe_id, r.hint), runner._CRASH_LOCATION)
        # The T3.1 and T3.2 locations are unchanged by the crash rule.
        self.assertEqual(runner._where_to_fix("T3.1", ""), dict(runner._FIX_LOCATIONS)["T3.1"])
        self.assertEqual(runner._where_to_fix("T3.2", ""), dict(runner._FIX_LOCATIONS)["T3.2"])
        # The paragraph the pointer names exists and says the fix is in the harness.
        doc = (Path(runner.BASE_DIR) / runner._SKILL_REF).read_text()
        self.assertIn("## Verdict Semantics", doc)
        self.assertIn("**Synthetic records.**", doc)
        self.assertIn("the fix is in `scripts/deploy_smoke/`, not the install", doc)

    def test_find_subagent_transcripts_fails_open_on_os_error(self):
        # An unreadable session folder makes Path.exists() (or the glob) raise;
        # the lookup returns [] instead of crashing the tier.
        denied = PermissionError(13, "Permission denied")
        with mock.patch.object(sp.Path, "exists", side_effect=denied):
            self.assertEqual(sp.find_subagent_transcripts(str(uuid.UUID(int=7))), [])
        with mock.patch.object(sp.Path, "exists", return_value=True), \
             mock.patch.object(sp.Path, "glob", side_effect=denied):
            self.assertEqual(sp.find_subagent_transcripts(str(uuid.UUID(int=7))), [])
        with mock.patch.object(sp.Path, "exists", return_value=True), \
             mock.patch.object(sp.Path, "glob", return_value=iter([Path("b.jsonl"), Path("a.jsonl")])):
            self.assertEqual(sp.find_subagent_transcripts(str(uuid.UUID(int=7))), [Path("a.jsonl"), Path("b.jsonl")])

    def _transcript_dirs(self):
        """A fixture BASE_DIR (with .claude/logs/sessions/) and home (with the
        live projects folder), patched into smoke_probes for one test."""
        root = _scratch(self, "transcripts")
        base, home = root / "base", root / "home"
        sessions = base / ".claude" / "logs" / "sessions"
        projects = home / ".claude" / "projects" / sp._PROJECT_SLUG
        sessions.mkdir(parents=True)
        projects.mkdir(parents=True)
        for patcher in (mock.patch.object(sp, "BASE_DIR", str(base)),
                        mock.patch.object(sp.Path, "home", return_value=home)):
            patcher.start()
            self.addCleanup(patcher.stop)
        return sessions, projects

    def test_find_subagent_transcripts_falls_back_to_archived_copies(self):
        sid = "17375d34-0000-4000-8000-000000000001"
        sessions, projects = self._transcript_dirs()
        # No live folder: the archived copies, one per subagent id (the newest
        # timestamp wins), never a .md rendering or another session's file.
        for name in ("2026-11-01_23-14-05_17375d34_subagent_aaaa1111.jsonl",
                     "2026-11-01_23-15-19_17375d34_subagent_aaaa1111.jsonl",
                     "2026-11-01_23-15-19_17375d34_subagent_bbbb2222.jsonl",
                     "2026-11-01_23-15-19_17375d34_subagent_bbbb2222.md",
                     "2026-11-01_23-15-19_99999999_subagent_cccc3333.jsonl"):
            (sessions / name).write_text("{}\n")
        want = [sessions / "2026-11-01_23-15-19_17375d34_subagent_aaaa1111.jsonl",
                sessions / "2026-11-01_23-15-19_17375d34_subagent_bbbb2222.jsonl"]
        self.assertEqual(sp.find_subagent_transcripts(sid), want)
        # An empty live folder still falls back.
        live_dir = projects / sid / "subagents"
        live_dir.mkdir(parents=True)
        self.assertEqual(sp.find_subagent_transcripts(sid), want)
        # Live transcripts win: the archive is not consulted.
        (live_dir / "agent-aaaa1111ffff.jsonl").write_text("{}\n")
        self.assertEqual(sp.find_subagent_transcripts(sid), [live_dir / "agent-aaaa1111ffff.jsonl"])

    def test_find_subagent_transcripts_archive_lookup_fails_open(self):
        sid = "17375d34-0000-4000-8000-000000000001"
        sessions, _ = self._transcript_dirs()
        (sessions / "2026-11-01_23-15-19_17375d34_subagent_aaaa1111.jsonl").write_text("{}\n")
        denied = PermissionError(13, "Permission denied")
        with mock.patch.object(sp.Path, "glob", side_effect=denied):
            self.assertEqual(sp.find_subagent_transcripts(sid), [])

    def test_find_transcript_prefers_a_larger_live_file_over_a_stale_archive(self):
        sid = "17375d34-0000-4000-8000-000000000001"
        sessions, projects = self._transcript_dirs()
        archive = sessions / "2026-11-01_23-14-05_17375d34_orchestrator.jsonl"
        live = projects / f"{sid}.jsonl"
        # Archive only, then live only.
        archive.write_text('{"t": 1}\n')
        self.assertEqual(sp.find_transcript(sid), archive)
        archive.unlink()
        live.write_text('{"t": 1}\n')
        self.assertEqual(sp.find_transcript(sid), live)
        # Both, the same content (the SessionEnd archive landed): the archive.
        archive.write_text('{"t": 1}\n')
        self.assertEqual(sp.find_transcript(sid), archive)
        # The session was resumed and the live file grew past the archive (the
        # resumed call's SessionEnd archive has not landed): the live file.
        live.write_text('{"t": 1}\n{"t": 2}\n')
        self.assertEqual(sp.find_transcript(sid), live)
        # A comparison that cannot stat the live file keeps the archive.
        real_stat = Path.stat

        def stat_denied_for_live(path, *args, **kwargs):
            if path.name == live.name:
                raise PermissionError(13, "Permission denied")
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(sp.Path, "stat", autospec=True, side_effect=stat_denied_for_live):
            self.assertEqual(sp.find_transcript(sid), archive)

    def test_t32_warn_detail_leads_with_the_reason(self):
        # The report's Observed cell keeps the first 200 characters of a detail.
        answer = "grade = -1 means Pre-K."
        for subs in ([], [[]], [[], [], []]):
            for main in ([], [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]):
                with self.subTest(subagents=len(subs), orchestrator=bool(main)):
                    v, d, _ = sp._evaluate_t32(answer, main, subs)
                    self.assertEqual(v, Verdict.WARN, d)
                    head = d[:200]
                    self.assertIn("answered without loading the skill", head)
                    self.assertIn("Pre-K", head)
                    self.assertIn(f"{len(subs)} specialist transcript(s) scanned", head)
        # Through run_tier_3 with no main transcript, the unchecked-resume reason
        # leads and the no-retrieval reason still fits in the cell behind it.
        runs = [_fake_run("Data Lookup. Sound good?"), _fake_run("grade -1 is Pre-K")]
        with mock.patch.object(sp, "execute_smoke_run", side_effect=runs), \
             mock.patch.object(sp, "find_transcript", return_value=None), \
             mock.patch.object(sp, "find_subagent_transcripts", return_value=[Path("a.jsonl")]), \
             mock.patch.object(sp, "load_transcript_records", return_value=[]):
            _, r2 = sp.run_tier_3("", {}, 5, route=rd.ROUTE_ANTHROPIC)
        self.assertTrue(r2.detail.startswith("The resume is not proven: main transcript missing, empty or "
                                             "unreadable."), r2.detail)
        self.assertIn("answered without loading the skill", r2.detail[:200])
        self.assertIn("1 specialist transcript(s) scanned", r2.detail[:200])

    def test_apply_hints_only_fills_fail_warn(self):
        ok = rd.ProbeResult("T0.5", "n", "0", verdict=Verdict.PASS)
        bad = rd.ProbeResult("T0.5", "n", "0", verdict=Verdict.FAIL)
        custom = rd.ProbeResult("T0.5", "n", "0", verdict=Verdict.WARN, hint="specific")
        sp.apply_hints([ok, bad, custom])
        self.assertEqual((ok.hint, custom.hint), ("", "specific"))
        self.assertEqual(bad.hint, sp.PROBE_HINTS["T0.5"])


if __name__ == "__main__":
    unittest.main()
