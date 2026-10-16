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
        self.assertEqual(sp._evaluate_t31("This is a Data Discovery question. Shall I proceed?")[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t31("grade -1 means Pre-K.")[0], Verdict.FAIL)
        ctx = [_use("c", "Skill", {"skill": "education-data-context"}), _res("c")]
        self.assertEqual(sp._evaluate_t32("In CCD, grade = -1 denotes Pre-Kindergarten.", ctx)[0], Verdict.PASS)
        self.assertEqual(sp._evaluate_t32("It means missing data.", ctx)[0], Verdict.FAIL)

    def test_t31_requires_named_mode_and_confirmation_question(self):
        cases = [
            # The confirmation templates (daaf-orchestrator SKILL.md).
            ("This is a quick definitional question, so I'd treat it as Data Lookup. I'll read the data lookup "
             "mode workflow reference, then check the CCD skill. **Sound good?**", Verdict.PASS),
            ("Classification: Ad Hoc Collaboration. Would you like me to proceed this way?", Verdict.PASS),
            ("I'd handle this in data-discovery mode. Shall I proceed?", Verdict.PASS),
            # Too loose before the fix: the bare word "mode" plus any "?".
            ("Which mode? I can help with that.", Verdict.FAIL),
            ("I can switch mode if needed. What year?", Verdict.FAIL),
            ("Do you mean the CCD? Let me know.", Verdict.FAIL),
            # A confirmation question but no DAAF mode named.
            ("I'll look this up in the CCD documentation. Shall I proceed?", Verdict.WARN),
            # The gate was skipped: the question is already answered.
            ("Data Lookup: grade = -1 is Pre-Kindergarten in CCD.", Verdict.FAIL),
            ("Data Lookup. grade -1 is Pre-K. Shall I proceed with more detail?", Verdict.WARN),
        ]
        for text, want in cases:
            with self.subTest(text=text):
                v, d, facts = sp._evaluate_t31(text)
                self.assertEqual(v, want, (d, facts))

    def test_t32_warns_when_answered_without_the_skill(self):
        orch = [_use("o", "Skill", {"skill": "daaf-orchestrator"}), _res("o")]
        ctx = [_use("c", "Skill", {"skill": "x:education-data-context"}), _res("c")]
        answer = "grade = -1 means Pre-K."
        v, d, facts = sp._evaluate_t32(answer, [])
        self.assertEqual(v, Verdict.WARN)
        self.assertIn("answered without loading the skill", d)
        self.assertIn("education-data-context or daaf-orchestrator", d)
        v, d, _ = sp._evaluate_t32(answer, orch)
        self.assertEqual(v, Verdict.WARN)
        self.assertNotIn("or daaf-orchestrator", d)
        self.assertEqual(sp._evaluate_t32(answer, orch + ctx)[0], Verdict.PASS)
        failed_ctx = [_use("c", "Skill", {"skill": "education-data-context"}), _res("c", "err", True)]
        self.assertEqual(sp._evaluate_t32(answer, failed_ctx)[0], Verdict.WARN)


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

    def test_tier3_resumes_same_session(self):
        runs = [_fake_run("Ad Hoc Collaboration mode. Shall I proceed?"), _fake_run("grade -1 is Pre-K")]
        with mock.patch.object(sp, "execute_smoke_run", side_effect=runs) as ex, \
             mock.patch.object(sp, "find_transcript", return_value=None):
            results = sp.run_tier_3("", {}, 5, route=rd.ROUTE_ANTHROPIC)
        # No transcript, so no education-data-context load is visible: T3.2 WARNs.
        self.assertEqual([r.verdict for r in results], [Verdict.PASS, Verdict.WARN])
        self.assertIn("answered without loading the skill", results[1].detail)
        self.assertEqual(ex.call_args_list[1].kwargs["resume_session_id"], runs[0][1]["session_id"])
        self.assertIsNone(ex.call_args_list[0].kwargs["max_budget_usd"])

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
        with mock.patch.object(sp, "_run_battery_cmd", return_value=stub) as bat, \
             mock.patch.object(sp, "_run_import_smoke", return_value=stub):
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
                    "T0.23", "T0.ABORT", "T1.1", "T1.2", "T1.3", "T1.5", "T1.6", "T1.7", "T1.8", "T1.9", "T1.10",
                    "T2.1", "T2.2", "T2.3", "T2.4", "T2.5", "T2.6", "T2.7", "TD.0", "TD.1", "TD.2", "TD.3",
                    "TD.4", "TD.5", "TD.6", "TD.7", "TD.8", "TN.1", "TN.2", "TN.3", "TN.4", "TA.1", "T3.1", "T3.2"]
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

    def test_apply_hints_only_fills_fail_warn(self):
        ok = rd.ProbeResult("T0.5", "n", "0", verdict=Verdict.PASS)
        bad = rd.ProbeResult("T0.5", "n", "0", verdict=Verdict.FAIL)
        custom = rd.ProbeResult("T0.5", "n", "0", verdict=Verdict.WARN, hint="specific")
        sp.apply_hints([ok, bad, custom])
        self.assertEqual((ok.hint, custom.hint), ("", "specific"))
        self.assertEqual(bad.hint, sp.PROBE_HINTS["T0.5"])


if __name__ == "__main__":
    unittest.main()
