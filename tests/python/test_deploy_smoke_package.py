"""Provider-free tests for the deploy-smoke v2 report writer, packager and importer.

Covers run_deploy_smoke.write_reports (Diagnosis summary: identity block,
problems table FAIL-then-WARN, ANSI-free output, report.json v2 fields), the
crash path (a tier exception or an interrupt still writes the report and the
package), the required --route choice, and scripts/deploy_smoke/smoke_package.py:
pattern scrubbing with counts, exclusion of FIFOs / symlinks / credential-named
files, the post-scrub gate, Windows-safe names, and the importer's zip-slip,
symlink, unlisted-member and sha256 checks plus MATRIX.md.

Standard-library unittest + unittest.mock only; no network, no live model call.
Every fake secret is assembled at runtime, so this file holds no secret-shaped
literal. Fixtures live under DAAF_SMOKE_TEST_SCRATCH when set (the framework
session points it at its workspace scratch), else under scripts/scratch/ — never
/tmp — and are removed in tearDown, with an atexit backstop for the whole
per-run root (FIFOs and Windows-uncreatable names included).

Wired into Tier D through TD.0's discovery of test_deploy_smoke*.py.

Run directly:
  python3 -m unittest discover -s /daaf/tests/python -p 'test_deploy_smoke_package.py'
"""

import atexit
import base64
import io
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import unittest
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SMOKE_DIR = _REPO_ROOT / "scripts" / "deploy_smoke"
for _p in (str(_REPO_ROOT), str(_SMOKE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import route_detection  # noqa: E402
import smoke_probes  # noqa: E402
import smoke_package  # noqa: E402
import run_deploy_smoke  # noqa: E402
from route_detection import ProbeResult, Verdict  # noqa: E402

_SCRATCH_BASE = Path(os.environ.get("DAAF_SMOKE_TEST_SCRATCH") or (_REPO_ROOT / "scripts" / "scratch"))
_RUN_ROOT = _SCRATCH_BASE / f"smoke_pkg_tests_{uuid.uuid4().hex[:10]}"


def _cleanup_run_root():
    # Trap-style backstop: removes FIFOs, odd names and every fixture even when
    # a test died before its own tearDown ran.
    shutil.rmtree(_RUN_ROOT, ignore_errors=True)


atexit.register(_cleanup_run_root)

# C-M2 guard: every package these tests build goes under the per-test scratch
# root; the real scripts/deploy_smoke/packages/ must gain nothing.
_PACKAGES_BEFORE = None


def _packages_listing():
    root = Path(smoke_package.PACKAGES_ROOT)
    return set(os.listdir(root)) if root.is_dir() else set()


def setUpModule():
    global _PACKAGES_BEFORE
    _PACKAGES_BEFORE = _packages_listing()


def tearDownModule():
    added = sorted(_packages_listing() - (_PACKAGES_BEFORE or set()))
    if added:
        raise AssertionError(f"tests left new entries in {smoke_package.PACKAGES_ROOT}: {added}")

UTC = timezone.utc
T_START = datetime(2026, 10, 13, 20, 30, 0, tzinfo=UTC)
T_END = T_START + timedelta(minutes=3)
SID_A = "0123abcd-1111-4222-8333-444455556666"
ESC = "\x1b"


# --- Runtime-assembled fake secrets (no secret-shaped literal in this file) ---

def fake_sk():
    return "sk" + "-" + "proj" + "-" + "Q" * 6 + "7" * 6 + "z" * 8


def fake_jwt():
    def b64(raw):
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return ".".join((b64('{"alg":"HS256","typ":"JWT"}'), b64('{"sub":"smoke-test-subject"}'),
                     b64("not-a-real-signature-bytes")))


def fake_email():
    return "smoke.tester" + "@" + "example" + ".org"


def fake_bearer_token():
    return "tok" + "X" * 10 + "9" * 6


def fake_password():
    return "hun" + "ter" + "2" * 10


def fake_env_value():
    return "envsecret" + "-" + "v" * 12


def codex_header_line():
    return "x-codex-" + "turn-state" + ": " + "opaque" + "Z" * 20


def fake_balance():
    return "4" * 3 + "." + "5" * 2


def quota_snapshot_line(stamp="2026-10-13 20:30:10,000"):
    # The shim's 2xx quota_snapshot shape (anthropic_openai_shim.py
    # _QUOTA_SNAPSHOT_HEADER_FIELDS), with synthetic values.
    cred = "cred" + "its_"
    return (f"{stamp} INFO req_id=r1 phase=upstream event=quota_snapshot elapsed_ms=12 plan_type=plus "
            f"active_limit=codex primary_used_pct=7 primary_window_min=300 primary_reset_s=100 "
            f"secondary_used_pct=1 secondary_window_min=10080 secondary_reset_s=200 "
            f"{cred}has=True {cred}balance={fake_balance()} {cred}unlimited=False")


def fake_bare_token():
    return "abcdEFGH" + "1234567890" + "tokenvalue"


def fake_pem():
    kind = "RSA " + "PRIVATE" + " KEY"
    return f"-----BEGIN {kind}-----\n" + "MIIB" + "A" * 60 + "\n" + "Q" * 40 + "=\n" + f"-----END {kind}-----"


class _ScratchCase(unittest.TestCase):
    def setUp(self):
        self.root = _RUN_ROOT / f"{type(self).__name__}_{uuid.uuid4().hex[:8]}"
        self.root.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # A minimal fake deployment root: no logs unless a test adds them.
    def fake_base(self):
        base = self.root / "base"
        (base / ".claude" / "logs" / "sessions").mkdir(parents=True, exist_ok=True)
        (base / ".claude" / "settings.json").write_text(json.dumps(
            {"env": {"ANTHROPIC_DEFAULT_MODEL": "opus", "EXAMPLE_API_KEY": "should-not-appear-1234"},
             "hooks": {"PreToolUse": [{}]}, "permissions": {"allow": ["x"], "deny": []}}))
        return base

    def make_report(self, name="report", results=None, route="anthropic-subscription", detected=None,
                    versions=None):
        report_dir = self.root / name
        info = route_detection.build_route_info({}, asserted_route=route)
        if detected:
            info.detected_route = detected
        results = results if results is not None else [_pr("T0.5", "CLI", "0", Verdict.PASS)]
        with mock.patch.object(run_deploy_smoke, "git_sha", return_value="96381ca" + "0" * 33):
            run_deploy_smoke.write_reports(
                report_dir, info, route_detection.env_fingerprint({}), results, ["0", "1", "2"],
                [("", {})], None, started_utc=T_START, ended_utc=T_END,
                versions=versions or _versions(), stated_route=route)
        return report_dir, results

    def build(self, report_dir, results, route="anthropic-subscription", env=None, **kw):
        kw.setdefault("out_dir", self.root / "packages")
        kw.setdefault("user_settings_path", self.root / "no_user_settings.json")
        base_dir = kw.pop("base_dir", None) or self.fake_base()
        return smoke_package.build_package(
            report_dir, route, T_START, T_END, _versions(), results, base_dir,
            detected_route=route, overall="PASS", summary={"PASS": 1}, env=env or {}, **kw)


def _pr(probe_id, name, tier, verdict, detail="", hint=None, evidence=()):
    r = ProbeResult(probe_id=probe_id, name=name, tier=tier)
    r.verdict = verdict
    r.detail = detail or f"{probe_id} detail"
    for cmd, out in evidence:
        r.add_evidence(cmd, output=out)
    if hint is not None:
        r.hint = hint
    return r


def _versions():
    return {"daaf_branch": "daaf_dev", "daaf_sha": "96381ca" + "0" * 33,
            "daaf_describe": "v3.0.1-83-g96381ca-dirty", "daaf_dirty_files": 3,
            "daaf_dirty_scope": run_deploy_smoke.DIRTY_SCOPE,
            "claude_code": "2.1.281 (Claude Code)", "codex": None, "shim": None, "python": "3.12.3"}


def _zip_names(path):
    with zipfile.ZipFile(path) as zf:
        return set(zf.namelist())


def _zip_manifest(path):
    with zipfile.ZipFile(path) as zf:
        return json.loads(zf.read("MANIFEST.json"))


# --- Report writer -------------------------------------------------------------------

class ReportWriterTests(_ScratchCase):
    def _results(self):
        return [
            _pr("T0.5", "Claude CLI available", "0", Verdict.PASS),
            _pr("T0.3", "Env coherence", "0", Verdict.FAIL, detail="ANTHROPIC_AUTH_TOKEN set on an Anthropic route"),
            _pr("T0.7", "Statuslines render", "0", Verdict.WARN,
                detail=f"bar output {ESC}[32mgreen{ESC}[0m text",
                evidence=[("bash context-bar.sh", f"{ESC}[1;31m[ctx]{ESC}[0m 12%")]),
            _pr("T1.1", "Live round-trip response", "1", Verdict.FAIL, detail="no completion token",
                hint="The provider returned an error. Where to fix: environment_settings.txt credentials",
                evidence=[("claude -p (session 0123abcd)", "error text")]),
            _pr("T2.3", "Web retrieval", "2", Verdict.WARN, detail="web_fetch fallback used",
                hint="WebSearch did not run through the real tool"),
            _pr("T0.13", "Synced surface", "0", Verdict.INFO),
        ]

    def test_diagnosis_summary_orders_fail_then_warn_with_identity(self):
        report_dir, _ = self.make_report(results=self._results())
        md = (report_dir / "report.md").read_text()
        self.assertLess(md.index("## Diagnosis summary"), md.index("## Environment Fingerprint"))
        self.assertLess(md.index("## Environment Fingerprint"), md.index("## Tier 0"))
        identity = md[md.index("### Identity"):md.index("### Problems")]
        for needle in ("stated `anthropic-subscription`", "2.1.281 (Claude Code)", "daaf_dev",
                       "v3.0.1-83-g96381ca-dirty", "2026-10-13T20:30:00Z", "Paid calls / cost", "Model mapping"):
            self.assertIn(needle, identity)
        problems = md[md.index("### Problems"):md.index("**Passed:**")]
        rows = [ln for ln in problems.splitlines() if ln.startswith("| T")]
        self.assertEqual([r.split("|")[2].strip() for r in rows], ["FAIL", "FAIL", "WARN", "WARN"])
        self.assertTrue(rows[0].startswith("| T0.3"))
        self.assertTrue(rows[1].startswith("| T1.1"))
        self.assertIn("transcripts/0123abcd/", rows[1])
        self.assertIn("environment_settings.txt credentials", rows[1].split("|")[-2])
        self.assertIn("The provider returned an error.", rows[1])
        self.assertIn("Tier 0: 1 of 4 (1 INFO)", md)

    def test_report_is_ansi_free(self):
        report_dir, _ = self.make_report(results=self._results())
        self.assertNotIn(ESC, (report_dir / "report.md").read_text())
        raw_json = (report_dir / "report.json").read_text()
        self.assertNotIn(ESC, json.loads(raw_json)["results"][2]["detail"])
        self.assertNotIn("\\u001b", raw_json)

    def test_report_json_v2_fields(self):
        report_dir, _ = self.make_report(results=self._results())
        data = json.loads((report_dir / "report.json").read_text())
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["started_utc"], "2026-10-13T20:30:00Z")
        self.assertEqual(data["versions"]["claude_code"], "2.1.281 (Claude Code)")
        for r in data["results"]:
            for key in ("duration_s", "session_ids", "cost_usd", "hint"):
                self.assertIn(key, r)
        by_id = {r["probe_id"]: r for r in data["results"]}
        self.assertEqual(by_id["T1.1"]["session_ids"], ["0123abcd"])
        self.assertEqual(by_id["T2.3"]["hint"], "WebSearch did not run through the real tool")

    def test_no_problems_message(self):
        report_dir, _ = self.make_report(results=[_pr("T0.5", "CLI", "0", Verdict.PASS)])
        self.assertIn("No FAIL or WARN results.", (report_dir / "report.md").read_text())


# --- Scrubbing ---------------------------------------------------------------------------

class ReportStripAnsiTests(unittest.TestCase):
    def test_report_writer_strips_raw_and_escaped_ansi(self):
        # The report writer must remove the escaped text forms jq writes for a
        # statusline that emits JSON, not only raw ESC bytes (review fix cycle 1).
        raw = "\x1b[38;5;71mA\x1b[0m"
        escaped = "\\u001b[38;5;1mB\\x1b[0mC\\033[1mD\\e[0mE"
        self.assertEqual(run_deploy_smoke.strip_ansi(raw), "A")
        self.assertEqual(run_deploy_smoke.strip_ansi(escaped), "BCDE")


class ScrubTests(unittest.TestCase):
    def test_each_pattern_removed_and_counted(self):
        env = {"FAKE_SERVICE_TOKEN": fake_env_value()}
        text = "\n".join([
            f"contact {fake_email()} for access",
            f"jwt {fake_jwt()} end",
            f"key {fake_sk()} end",
            f"Authorization: Bearer {fake_bearer_token()}",
            f"MY_SERVICE_PASSWORD={fake_password()}",
            codex_header_line(),
            f"env leak {fake_env_value()} here",
        ])
        out, counts = smoke_package.scrub_text(text, env)
        for secret in (fake_email(), fake_jwt(), fake_sk(), fake_bearer_token(), fake_password(),
                       "x-codex-turn-state", fake_env_value()):
            self.assertNotIn(secret, out)
        for key in ("email", "jwt", "sk_key", "bearer", "secret_assignment", "dropped_lines", "env_value"):
            self.assertGreaterEqual(counts[key], 1, key)
        self.assertEqual(smoke_package.detect_secret_shapes(out, env), {})

    def test_diagnostic_values_survive(self):
        text = ('{"session_id": "0123abcd-1111-4222-8333-444455556666", "input_tokens": 1234}\n'
                "Session started: 2026-10-13 19:54:46 | Session: dbae30f2\n"
                "test_x (test_deploy_smoke.ParseTiersTests.test_x) ... ok\n"
                '"ANTHROPIC_API_KEY": "<redacted:set>"\n')
        out, counts = smoke_package.scrub_text(text, {})
        self.assertEqual(out, text)
        self.assertEqual(sum(counts.values()), 0)

    def test_json_escaped_assignment_is_redacted(self):
        line = '{"content": "{\\"api_key\\": \\"' + fake_password() + '\\"}"}'
        out, counts = smoke_package.scrub_text(line, {})
        self.assertNotIn(fake_password(), out)
        self.assertEqual(counts["secret_assignment"], 1)

    def _assert_scrubbed(self, text, secret, count_key):
        """The secret is gone, the count moved, the gate sees the raw text and
        is clean on the scrubbed one."""
        self.assertTrue(smoke_package.detect_secret_shapes(text, {}), f"gate missed raw {count_key}")
        out, counts = smoke_package.scrub_text(text, {})
        self.assertNotIn(secret, out)
        self.assertGreaterEqual(counts[count_key], 1, count_key)
        self.assertEqual(smoke_package.detect_secret_shapes(out, {}), {}, out)
        return out

    # Q-M1: the shim's quota snapshot carries account credit fields.
    def test_quota_snapshot_credits_stripped_rest_kept(self):
        line = quota_snapshot_line()
        out = self._assert_scrubbed(line, fake_balance(), "credits")
        for key in ("has", "balance", "unlimited"):
            self.assertIn(f"credits_{key}=[REDACTED]", out)
        self.assertIn("primary_used_pct=7", out)
        self.assertIn("plan_type=plus", out)
        self.assertIn("event=quota_snapshot", out)

    def test_credits_in_json_shape_stripped(self):
        text = '{"' + "credits" + '_balance": "' + fake_balance() + '", "plan_type": "plus"}'
        out = self._assert_scrubbed(text, fake_balance(), "credits")
        self.assertIn('"plan_type": "plus"', out)

    # S1 repros, one per gap.
    def test_scheme_less_authorization_header(self):
        text = "Author" + "ization: " + fake_bare_token()
        out = self._assert_scrubbed(text, fake_bare_token(), "secret_header")
        self.assertIn("[REDACTED:authorization]", out)

    def test_json_escaped_basic_authorization(self):
        cred = base64.b64encode(("user:" + fake_password()).encode()).decode()
        text = '{"line": "{\\"Authorization\\": \\"Basic ' + cred + '\\"}"}'
        out = self._assert_scrubbed(text, cred, "bearer")
        json.loads(out)  # the escaping around the marker is intact

    def test_json_escaped_x_api_key(self):
        text = '{"line": "{\\"x-api-key\\": \\"' + fake_bare_token() + '\\"}"}'
        out = self._assert_scrubbed(text, fake_bare_token(), "secret_header")
        json.loads(out)

    def test_url_query_secret_key_and_api_version_kept(self):
        url = "https://x.example/a?api-version=2024-10-01&access" + "_token=" + fake_bare_token()
        out = self._assert_scrubbed(url, fake_bare_token(), "url_param")
        self.assertIn("api-version=2024-10-01", out)
        self.assertIn("access_token=[REDACTED:url-param]", out)

    def test_url_userinfo_with_undotted_host(self):
        url = "http://u:" + fake_password() + "@localhost:4141/v1"
        out = self._assert_scrubbed(url, fake_password(), "userinfo")
        self.assertIn("@localhost:4141/v1", out)

    def test_pem_private_key_block(self):
        text = "before\n" + fake_pem() + "\nafter"
        out = self._assert_scrubbed(text, "MIIB" + "A" * 60, "private_key")
        self.assertIn("before", out)
        self.assertIn("after", out)
        self.assertNotIn("PRIVATE KEY", out)
        # JSON-escaped and cut off before END (a truncated transcript line).
        cut = json.dumps({"c": fake_pem()[:90]})
        self._assert_scrubbed(cut, "MIIB" + "A" * 30, "private_key")

    # S2: the gate never trips on the scrubber's own markers.
    def test_gate_ignores_redaction_markers(self):
        for text in ("x-api-key: [REDACTED:header]", 'x-api-key: "[REDACTED:header]"',
                     "Authorization: Bearer [REDACTED:bearer]", "Authorization: [REDACTED:authorization]",
                     "cookie=[REDACTED: value of SESSION_COOKIE]", "credits_balance=[REDACTED]",
                     "https://x.example/a?token=[REDACTED:url-param]", "http://u:[REDACTED:userinfo]@localhost",
                     "MY_SERVICE_PASSWORD=[REDACTED:assignment]", '"ANTHROPIC_API_KEY": "<redacted:set>"',
                     "[REDACTED:private-key]"):
            self.assertEqual(smoke_package.detect_secret_shapes(text, {}), {}, text)

    def test_scrub_is_idempotent_on_its_own_output(self):
        text = "\n".join([quota_snapshot_line(), "Author" + "ization: " + fake_bare_token(),
                          "x-api-key: " + fake_bare_token(), fake_pem()])
        once, _ = smoke_package.scrub_text(text, {})
        twice, counts = smoke_package.scrub_text(once, {})
        self.assertEqual(once, twice)
        self.assertEqual(sum(counts.values()), 0)

    # Fix cycle 2, item 4: diagnostic names and bracketed model ids survive.
    def test_diagnostic_names_and_model_ids_survive(self):
        text = "\n".join([
            '{"session_model": "gpt-6.1-sol[1m]#high", "auth_mode": "chatgpt_lane_x"}',
            "2026-10-13 10:00:01,000 INFO req_id=r1 phase=upstream event=request_shape "
            "keys=include,input,model",
            "2026-10-13 10:00:01,000 INFO req_id=r1 phase=upstream event=request_shape "
            "keys=instructions,input,model,parallel_tool_calls text_keys=verbosity reasoning_keys=effort,summary",
            '{"prompt_cache_key": "0123abcd-1111-4222-8333-444455556666", "cache_key": "daaf_search_error_body"}',
            "session_model=gpt-6.1-sol[1m]#high",
        ])
        out, counts = smoke_package.scrub_text(text, {})
        self.assertEqual(out, text)
        self.assertEqual(sum(counts.values()), 0)
        self.assertEqual(smoke_package.detect_secret_shapes(text, {}), {})

    def test_bracketed_secret_value_is_redacted_whole(self):
        # The value pattern no longer stops at "]", so nothing of a bracketed
        # secret value is left after the marker.
        tail = "efgh" + "ijkl" + "mnop"
        text = '{"api_token": "abcd[1m]' + tail + '"}'
        out = self._assert_scrubbed(text, tail, "secret_assignment")
        self.assertEqual(out, '{"api_token": "[REDACTED:assignment]"}')
        json.loads(out)

    def test_unverified_names_stay_redacted(self):
        # auth_status and key_source have no known writer: not on the list.
        for name in ("auth_status", "key_source"):
            out, _ = smoke_package.scrub_text(f"{name}={fake_password()}", {})
            self.assertNotIn(fake_password(), out, name)

    # Fix cycle 2, item 6: every cookie value, short first pair included.
    def test_cookie_values_all_redacted(self):
        sid = "Zx9a8b7c" + "6d5e4f3g2h1"
        out = self._assert_scrubbed("Cookie: a=1; sid=" + sid, sid, "secret_header")
        self.assertEqual(out, "Cookie: a=[REDACTED:cookie]; sid=[REDACTED:cookie]")
        out = self._assert_scrubbed("Set-Cookie: sid=" + sid + "; Path=/; HttpOnly", sid, "secret_header")
        self.assertIn("HttpOnly", out)
        self.assertNotIn("Path=/", out)
        escaped = '{"line": "{\\"cookie\\": \\"a=1; sid=' + sid + '\\"}"}'
        json.loads(self._assert_scrubbed(escaped, sid, "secret_header"))
        once, _ = smoke_package.scrub_text("cookie: a=1; b=" + sid, {})
        self.assertEqual(smoke_package.scrub_text(once, {})[0], once)  # idempotent

    def test_codex_header_value_redacted_in_place_without_drops(self):
        # Generated files are scrubbed with drop_markers=(): the line stays, the
        # value goes, and the generated-mode gate passes a bare mention.
        line = "detail: " + codex_header_line() + " seen; hint: a Codex turn-state header -> shim >= 1.4.9"
        out, counts = smoke_package.scrub_text(line, {}, ())
        self.assertIn("x-codex-turn-state: [REDACTED:header] seen", out)
        self.assertNotIn("opaque", out)
        self.assertEqual(counts["dropped_lines"], 0)
        self.assertEqual(smoke_package.detect_secret_shapes(out, {}, generated=True), {})
        self.assertTrue(smoke_package.detect_secret_shapes(line, {}, generated=True))
        # A copied log keeps the strict rule: any marker at all fails the gate.
        self.assertTrue(smoke_package.detect_secret_shapes(out, {}))


# --- Packager ------------------------------------------------------------------------------

class PackagerTests(_ScratchCase):
    def test_transcript_email_and_codex_header_removed_and_counted(self):
        base = self.fake_base()
        projects = self.root / "projects"
        (projects / SID_A / "subagents").mkdir(parents=True)
        (projects / f"{SID_A}.jsonl").write_text("\n".join([
            json.dumps({"type": "user", "message": {"content": f"my email is {fake_email()}"}}),
            json.dumps({"type": "tool_result", "content": codex_header_line()}),
            json.dumps({"type": "assistant", "session_id": SID_A, "message": {"content": "done"}}),
        ]) + "\n")
        (projects / SID_A / "subagents" / "agent-abc123.jsonl").write_text(
            json.dumps({"content": f"key {fake_sk()}"}) + "\n")
        audit = base / ".claude" / "logs" / "audit.jsonl"
        audit.write_text(json.dumps({"session_id": SID_A, "tool": "Bash", "target": "echo hi"}) + "\n"
                         + json.dumps({"session_id": "ffffffff-0000", "tool": "Bash", "target": "other"}) + "\n")
        r = _pr("T1.1", "Live round-trip", "1", Verdict.PASS)
        r.session_ids = [SID_A]
        report_dir, _ = self.make_report(results=[r])
        built = self.build(report_dir, [r], base_dir=base, projects_dir=projects,
                           sessions_dir=base / ".claude" / "logs" / "sessions")
        zp = built["zip_path"]
        names = _zip_names(zp)
        self.assertIn("transcripts/0123abcd/main.jsonl", names)
        self.assertIn("transcripts/0123abcd/subagents/agent-abc123.jsonl", names)
        with zipfile.ZipFile(zp) as zf:
            main = zf.read("transcripts/0123abcd/main.jsonl").decode()
            sub = zf.read("transcripts/0123abcd/subagents/agent-abc123.jsonl").decode()
            audit_rows = zf.read("logs/audit.jsonl").decode().strip().splitlines()
        self.assertNotIn(fake_email(), main)
        self.assertNotIn("x-codex-turn-state", main)
        self.assertIn("done", main)
        self.assertNotIn(fake_sk(), sub)
        self.assertEqual(len(audit_rows), 1)
        manifest = built["manifest"]
        entry = {f["path"]: f for f in manifest["files"]}["transcripts/0123abcd/main.jsonl"]
        self.assertEqual(entry["scrub_counts"]["email"], 1)
        self.assertEqual(entry["scrub_counts"]["dropped_lines"], 1)
        self.assertGreaterEqual(manifest["scrub_totals"]["sk_key"], 1)

    def test_session_ids_from_evidence_and_archived_transcript(self):
        base = self.fake_base()
        sessions = base / ".claude" / "logs" / "sessions"
        (sessions / "2026-10-13_20-30-01_0123abcd_orchestrator.jsonl").write_text('{"x": 1}\n')
        r = _pr("T2.1", "Dispatch", "2", Verdict.PASS, evidence=[("claude -p (session 0123abcd)", "ok")])
        report_dir, _ = self.make_report(results=[r])
        built = self.build(report_dir, [r], base_dir=base, projects_dir=self.root / "none")
        self.assertIn("transcripts/0123abcd/main.jsonl", _zip_names(built["zip_path"]))
        self.assertEqual(built["manifest"]["session_ids"], ["0123abcd"])

    def test_settings_projection_redacts_secret_named_values(self):
        report_dir, results = self.make_report()
        built = self.build(report_dir, results)
        with zipfile.ZipFile(built["zip_path"]) as zf:
            proj = json.loads(zf.read("config/settings_projection.json"))
        env = proj[0]["env"]
        self.assertEqual(env["EXAMPLE_API_KEY"], "<redacted:set>")
        self.assertEqual(env["ANTHROPIC_DEFAULT_MODEL"], "opus")
        self.assertEqual(proj[0]["hook_events"], {"PreToolUse": 1})

    def test_shim_log_window_and_header_lines_dropped(self):
        base = self.fake_base()
        logs = base / "scripts" / "provider_shim" / "logs"
        logs.mkdir(parents=True)
        local = T_START.astimezone().replace(tzinfo=None)

        def ts(delta):
            return (local + timedelta(seconds=delta)).strftime("%Y-%m-%d %H:%M:%S") + ",000"
        (logs / "shim.log").write_text("\n".join([
            f"{ts(-7200)} INFO req_id=- phase=process shim v1.4.8 starting port=4141",
            f"{ts(-3600)} INFO req_id=a phase=x before the run window",
            f"{ts(-60)} INFO req_id=- phase=process shim v1.4.9 starting port=4141",
            f"{ts(10)} INFO req_id=b phase=x inside the run",
            f"{ts(20)} INFO req_id=c phase=x {codex_header_line()}",
            f"{ts(30)} INFO req_id=d phase=x response | headers: secretish",
            # The main backend-error record: its header dump holds a Codex
            # header, yet the record before the dump must survive (fix cycle 2).
            f"{ts(40)} ERROR req_id=f phase=upstream backend 400 (attempt 1/3) backend_code=bad_req "
            f"anthropic_type=invalid_request_error | headers: {{'{codex_header_line().split(': ')[0]}': "
            f"'{codex_header_line().split(': ')[1]}'}}",
            f"{ts(9999)} INFO req_id=e phase=x after the run",
        ]) + "\n")
        (logs / "quota_state.json").write_text(json.dumps({"plan_type": "pro", "credits_balance": "12.5"}))
        report_dir, results = self.make_report(route="chatgpt-subscription")
        built = self.build(report_dir, results, route="chatgpt-subscription", base_dir=base)
        with zipfile.ZipFile(built["zip_path"]) as zf:
            shim = zf.read("logs/shim.log").decode()
            quota = json.loads(zf.read("logs/quota_state.projection.json"))
        self.assertIn("inside the run", shim)
        self.assertNotIn("before the run window", shim)
        self.assertNotIn("after the run", shim)
        self.assertNotIn("x-codex-turn-state", shim)
        self.assertNotIn("secretish", shim)
        self.assertNotIn("opaque", shim)
        # Cut, not dropped: the prefix of each header-dump line is kept.
        self.assertIn("req_id=d phase=x response | headers: [REMOVED]\n", shim)
        self.assertIn("backend 400 (attempt 1/3) backend_code=bad_req anthropic_type=invalid_request_error "
                      "| headers: [REMOVED]\n", shim)
        self.assertEqual(quota, {"plan_type": "pro"})
        entry = {f["path"]: f for f in built["manifest"]["files"]}["logs/shim.log"]
        self.assertEqual(entry["scrub_counts"]["dropped_lines"], 1)
        self.assertEqual(entry["scrub_counts"]["truncated_lines"], 2)
        self.assertEqual(built["manifest"]["gates"]["post_scrub_secret_scan"], "clean")

    def test_truncate_marker_lines_keeps_prefix_and_line_endings(self):
        text = "a | headers: {x}\r\nb plain\nc | HEADERS: y"
        out, n = smoke_package.truncate_marker_lines(text, smoke_package.SHIM_TRUNCATE_MARKERS)
        self.assertEqual(out, "a | headers: [REMOVED]\r\nb plain\nc | headers: [REMOVED]")
        self.assertEqual(n, 2)


class ExclusionTests(_ScratchCase):
    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs os.mkfifo")
    def test_fifo_symlink_and_credential_files_excluded(self):
        report_dir, results = self.make_report()
        ev = report_dir / "evidence"
        fifo = ev / "stream.fifo"
        os.mkfifo(fifo)
        self.addCleanup(lambda: fifo.exists() and fifo.unlink())
        link = ev / "link.log"
        os.symlink(ev / "env_fingerprint.json", link)
        self.addCleanup(lambda: link.is_symlink() and link.unlink())
        for name in ("credentials.json", "auth.json", ".env", "server.pem", "deploy.key"):
            (ev / name).write_text("credential material")
        (ev / "secrets").mkdir()
        (ev / "secrets" / "inner.txt").write_text("credential material")
        (ev / "ok.log").write_text("fine")
        # An accidental open() of the FIFO would block forever; fail instead.
        old = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("FIFO opened")))
        signal.alarm(60)
        try:
            built = self.build(report_dir, results)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        names = _zip_names(built["zip_path"])
        self.assertIn("evidence/ok.log", names)
        for bad in ("stream.fifo", "link.log", "credentials.json", "auth.json", ".env", "server.pem",
                    "deploy.key", "inner.txt"):
            self.assertFalse(any(n.endswith(bad) for n in names), bad)
        reasons = {Path(e["source"]).name: e["reason"] for e in built["manifest"]["excluded"]}
        self.assertEqual(reasons["stream.fifo"], "not a regular file (fifo)")
        self.assertEqual(reasons["link.log"], "not a regular file (symlink)")
        self.assertIn("credential", reasons["credentials.json"])
        self.assertIn("never read", reasons[".env"])
        self.assertIn("secrets", reasons)

    def test_credential_name_rules(self):
        for name in (".env", ".env.local", "x.pem", "credentials.json", ".credentials.json", "auth.json",
                     ".claude.json", ".claude.json.tmp1", "reasoning_cache.json", "my_secret.txt"):
            self.assertIsNotNone(smoke_package.credential_name_reason(name), name)
        for name in ("report.md", "TD.1.log", "shim_health.json", "keyring_notes.md"):
            self.assertIsNone(smoke_package.credential_name_reason(name), name)

    def test_any_dot_env_prefix_is_excluded(self):
        # The docs say "any basename starting with .env" (fix cycle 2).
        for name in (".env", ".envrc", ".env-prod", ".env_local", ".ENV.backup", ".environment"):
            self.assertEqual(smoke_package.credential_name_reason(name), "credential file (.env)", name)
        self.assertIsNone(smoke_package.credential_name_reason("notes.env.md"))


class GateTests(_ScratchCase):
    def test_non_utf8_file_is_scrubbed_and_bytes_round_trip(self):
        # S1: a non-UTF-8 file used to bypass the scrubber (and was withheld by
        # the gate); it is now scrubbed, and its undecodable bytes survive.
        report_dir, results = self.make_report()
        blob = report_dir / "evidence" / "blob.bin"
        blob.write_bytes(b"\xff\xfe\x00binary " + fake_sk().encode() + b" \xff tail")
        built = self.build(report_dir, results)
        with zipfile.ZipFile(built["zip_path"]) as zf:
            data = zf.read("evidence/blob.bin")
        self.assertNotIn(fake_sk().encode(), data)
        self.assertEqual(data, b"\xff\xfe\x00binary [REDACTED:sk-key] \xff tail")
        entry = {f["path"]: f for f in built["manifest"]["files"]}["evidence/blob.bin"]
        self.assertEqual(entry["scrub_counts"]["sk_key"], 1)
        self.assertEqual(built["manifest"]["gates"]["post_scrub_secret_scan"], "clean")

    def test_gate_withholds_unscrubbed_file_in_build(self):
        report_dir, results = self.make_report()
        with mock.patch.object(smoke_package, "scrub_text", side_effect=lambda t, e, d: (t, smoke_package._empty_counts())):
            (report_dir / "evidence" / "leak.log").write_text("leak " + fake_sk())
            built = self.build(report_dir, results)
        self.assertNotIn("evidence/leak.log", _zip_names(built["zip_path"]))
        withheld = {w["path"]: w["reason"] for w in built["manifest"]["withheld"]}
        self.assertTrue(withheld["evidence/leak.log"].startswith("withheld: secret-shaped content"))
        self.assertIn("sk_key", withheld["evidence/leak.log"])
        self.assertTrue(any("leak.log" in w for w in built["warnings"]))
        self.assertIn("file(s) withheld", built["manifest"]["gates"]["post_scrub_secret_scan"])

    def test_gate_catches_each_new_shape_unscrubbed(self):
        stage = self.root / "stage"
        stage.mkdir()
        st = smoke_package._Stager(stage, {})
        raw = {"credits.log": quota_snapshot_line(), "pem.txt": fake_pem(),
               "auth.txt": "Author" + "ization: " + fake_bare_token(),
               "url.txt": "https://x.example/?access" + "_token=" + fake_bare_token(),
               "userinfo.txt": "http://u:" + fake_password() + "@localhost:4141",
               "assign.txt": "MY_SERVICE_PASSWORD=" + fake_password()}
        for name, text in raw.items():
            st.add_bytes(name, text.encode(), "test", scrub=False)
        self.assertEqual(sorted(smoke_package.post_scrub_gate(st)), sorted(raw))

    def test_gate_direct_on_staged_file(self):
        stage = self.root / "stage"
        stage.mkdir()
        st = smoke_package._Stager(stage, {})
        st.add_bytes("a.txt", b"clean text", "test")
        st.add_bytes("b.txt", f"leak {fake_jwt()}".encode(), "test", scrub=False)
        self.assertEqual(smoke_package.post_scrub_gate(st), ["b.txt"])
        self.assertFalse((stage / "b.txt").exists())
        self.assertTrue((stage / "a.txt").exists())


class NameTests(_ScratchCase):
    def test_package_name_is_windows_safe(self):
        name = smoke_package.package_name(T_START, "anthropic-api", "96381ca" + "0" * 33)
        self.assertEqual(name, "daaf-smoke_20261013T203000Z_anthropic-api_96381ca.zip")
        self.assertRegex(name, smoke_package.PACKAGE_NAME_RE)
        self.assertIsNone(smoke_package.windows_name_problem(name))
        self.assertNotIn(":", name)
        self.assertEqual(smoke_package.package_name(T_START, "Bad Route:", "<unknown>"),
                         "daaf-smoke_20261013T203000Z_unknown-route_nosha.zip")

    def test_windows_name_rules(self):
        for bad in ("a:b", "trail.", "trail ", "CON", "nul.txt", "x\x01y", "q?"):
            self.assertIsNotNone(smoke_package.windows_name_problem(bad), repr(bad))
        self.assertIsNone(smoke_package.windows_name_problem("report.md"))

    def test_bad_evidence_name_is_withheld(self):
        report_dir, results = self.make_report()
        odd = report_dir / "evidence" / "bad:name.log"
        odd.write_text("fine content")
        self.addCleanup(lambda: odd.exists() and odd.unlink())
        built = self.build(report_dir, results)
        withheld = {w["path"]: w["reason"] for w in built["manifest"]["withheld"]}
        self.assertIn("Windows-incompatible name", withheld["evidence/bad:name.log"])
        self.assertNotIn("evidence/bad:name.log", _zip_names(built["zip_path"]))

    @unittest.skipUnless(smoke_package.INVARIANTS_SCRIPT.is_file() and shutil.which("bash"),
                         "needs bash and check_workspace_invariants.sh")
    def test_package_passes_names_only_invariants(self):
        report_dir, results = self.make_report()
        built = self.build(report_dir, results)
        self.assertTrue(built["manifest"]["gates"]["names_only_invariants"].startswith("OK"))
        dest = smoke_package.import_package(built["zip_path"], self.root / "inbox")
        proc = subprocess.run(["bash", str(smoke_package.INVARIANTS_SCRIPT), "--names-only"],
                              capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, DAAF_INVARIANT_ROOT=str(dest)))
        self.assertEqual(proc.returncode, 0, proc.stderr)


# --- Runner: crash path, required route, tiers ----------------------------------------------------

class RunnerTests(_ScratchCase):
    def _main(self, argv, **patches):
        pk = self.root / "packages"
        stack = [
            mock.patch.object(run_deploy_smoke, "PACKAGES_ROOT", pk),
            mock.patch.object(run_deploy_smoke, "INBOX_ROOT", self.root / "inbox"),
            mock.patch.object(run_deploy_smoke, "BASE_DIR", str(self.fake_base())),
            mock.patch.object(run_deploy_smoke, "collect_versions", return_value=_versions()),
            mock.patch("sys.stdout", io.StringIO()),
            mock.patch("sys.stderr", io.StringIO()),
        ]
        stack += [mock.patch.object(smoke_probes, k, v, create=True) for k, v in patches.items()]
        for p in stack:
            p.start()
        try:
            return run_deploy_smoke.main(argv), pk
        finally:
            for p in reversed(stack):
                p.stop()

    def _argv(self, tiers="0"):
        return ["--route", "anthropic-subscription", "--tiers", tiers, "--yes",
                "--report-dir", str(self.root / "report")]

    def test_tier_exception_still_reports_and_packages(self):
        rc, pk = self._main(self._argv(), run_tier0=mock.Mock(side_effect=RuntimeError("boom")))
        self.assertEqual(rc, 1)
        data = json.loads((self.root / "report" / "report.json").read_text())
        crash = [r for r in data["results"] if r["probe_id"] == "T0.CRASH"]
        self.assertEqual(crash[0]["verdict"], "FAIL")
        self.assertIn("RuntimeError: boom", crash[0]["detail"])
        zips = list(pk.glob("daaf-smoke_*_anthropic-subscription_*.zip"))
        self.assertEqual(len(zips), 1)
        self.assertTrue({"report.md", "report.json", "README_FOR_MAIN_SESSION.md", "MANIFEST.json"}
                        <= _zip_names(zips[0]))

    def test_interrupt_in_tier_block_still_reports_and_packages(self):
        rc, pk = self._main(self._argv(), run_tier0=mock.Mock(side_effect=KeyboardInterrupt()))
        self.assertEqual(rc, 130)
        data = json.loads((self.root / "report" / "report.json").read_text())
        self.assertIn("RUN.CRASH", [r["probe_id"] for r in data["results"]])
        self.assertEqual(len(list(pk.glob("*.zip"))), 1)

    def test_missing_v2_tier_entry_point_is_a_skip(self):
        rc, _ = self._main(self._argv("N"), run_tier_n=None)
        data = json.loads((self.root / "report" / "report.json").read_text())
        skip = [r for r in data["results"] if r["probe_id"] == "TN.UNAVAILABLE"]
        self.assertEqual(skip[0]["verdict"], "SKIP")
        self.assertEqual(rc, 0)

    def test_v2_tier_entry_point_bound_by_parameter_name(self):
        seen = {}

        def fake_tier_n(route, timeout, evidence_dir):
            seen.update(route=route, timeout=timeout, evidence_dir=evidence_dir)
            return [_pr("TN.1", "Endpoint", "N", Verdict.PASS)]
        self._main(self._argv("N"), run_tier_n=fake_tier_n)
        self.assertEqual(seen["route"], "anthropic-subscription")
        self.assertEqual(seen["evidence_dir"], self.root / "report" / "evidence" / "tier_n")

    def test_route_is_a_required_choice(self):
        with mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as missing:
                run_deploy_smoke.main(["--tiers", "0", "--yes"])
            with self.assertRaises(SystemExit) as typo:
                run_deploy_smoke.main(["--route", "anthropic-subscriptoin", "--tiers", "0", "--yes"])
        self.assertEqual(missing.exception.code, 2)
        self.assertEqual(typo.exception.code, 2)
        self.assertEqual(len(run_deploy_smoke.ROUTE_CHOICES), 5)
        self.assertIn("anthropic-api", run_deploy_smoke.ROUTE_CHOICES)

    def test_parse_tiers_accepts_v2_tokens(self):
        self.assertEqual(run_deploy_smoke.parse_tiers("0,d,n,1,2,a,3"), ["0", "D", "N", "1", "2", "A", "3"])
        with self.assertRaises(ValueError):
            run_deploy_smoke.parse_tiers("0,X")


# --- Importer + MATRIX ------------------------------------------------------------------------------

def _write_zip(path, members, manifest_files=None):
    """members: {name: bytes or (bytes, external_attr)}; the MANIFEST lists
    manifest_files (default: every member, with correct hashes)."""
    import hashlib
    if manifest_files is None:
        manifest_files = [{"path": n, "sha256": hashlib.sha256(v if isinstance(v, bytes) else v[0]).hexdigest(),
                           "bytes": len(v if isinstance(v, bytes) else v[0])} for n, v in members.items()]
    with zipfile.ZipFile(path, "w") as zf:
        for name, value in members.items():
            data, attr = (value, None) if isinstance(value, bytes) else value
            info = zipfile.ZipInfo(name)
            if attr is not None:
                info.external_attr = attr
            zf.writestr(info, data)
        zf.writestr("MANIFEST.json", json.dumps({"kind": smoke_package.PACKAGE_KIND, "files": manifest_files}))


class ImporterTests(_ScratchCase):
    def test_zip_slip_member_rejected(self):
        inbox = self.root / "inbox"
        zp = self.root / "daaf-smoke_20261013T203000Z_openrouter_96381ca.zip"
        _write_zip(zp, {"../evil.txt": b"escaped"})
        with self.assertRaises(smoke_package.ImportRejected) as ctx:
            smoke_package.import_package(zp, inbox)
        self.assertIn("escapes", str(ctx.exception))
        self.assertFalse((self.root / "evil.txt").exists())
        self.assertEqual([p.name for p in inbox.iterdir()], [])

    def test_absolute_and_symlink_members_rejected(self):
        for members in ({"/abs.txt": b"x"},
                        {"link": (b"/etc/passwd", (stat.S_IFLNK | 0o777) << 16)}):
            zp = self.root / "daaf-smoke_20261013T203000Z_openrouter_96381ca.zip"
            _write_zip(zp, members)
            with self.assertRaises(smoke_package.ImportRejected):
                smoke_package.import_package(zp, self.root / "inbox")
            zp.unlink()

    def test_hash_mismatch_rejected(self):
        report_dir, results = self.make_report()
        built = self.build(report_dir, results)
        good = built["zip_path"]
        tampered = self.root / good.name
        with zipfile.ZipFile(good) as src, zipfile.ZipFile(tampered, "w") as dst:
            for info in src.infolist():
                data = src.read(info)
                if info.filename == "report.md":
                    data = data + b"\ntampered\n"
                dst.writestr(info, data)
        inbox = self.root / "inbox"
        with self.assertRaises(smoke_package.ImportRejected) as ctx:
            smoke_package.import_package(tampered, inbox)
        self.assertIn("sha256 mismatch", str(ctx.exception))
        self.assertFalse((inbox / good.name[:-4]).exists())
        self.assertFalse(any(p.name.startswith(".import_") for p in inbox.iterdir()))

    def test_unlisted_member_rejected(self):
        zp = self.root / "daaf-smoke_20261013T203000Z_openrouter_96381ca.zip"
        _write_zip(zp, {"report.md": b"x", "extra.txt": b"y"}, manifest_files=[])
        with self.assertRaises(smoke_package.ImportRejected) as ctx:
            smoke_package.import_package(zp, self.root / "inbox")
        self.assertIn("not listed", str(ctx.exception))

    def test_good_package_imports_and_verifies(self):
        report_dir, results = self.make_report()
        built = self.build(report_dir, results)
        dest = smoke_package.import_package(built["zip_path"], self.root / "inbox")
        self.assertTrue((dest / "README_FOR_MAIN_SESSION.md").is_file())
        self.assertTrue((dest / "report.md").is_file())
        self.assertEqual(dest.name, built["zip_path"].name[:-4])

    def test_matrix_with_two_packages(self):
        sub = [_pr("T0.3", "Env coherence", "0", Verdict.PASS), _pr("T0.10", "Invariants", "0", Verdict.FAIL)]
        gpt = [_pr("T0.3", "Env coherence", "0", Verdict.FAIL), _pr("T0.10", "Invariants", "0", Verdict.FAIL),
               _pr("T0.8", "Shim health", "0", Verdict.WARN)]
        r1, _ = self.make_report("rep_sub", sub, route="anthropic-subscription")
        r2, _ = self.make_report("rep_gpt", gpt, route="chatgpt-subscription")
        z1 = self.build(r1, sub)["zip_path"]
        z2 = self.build(r2, gpt, route="chatgpt-subscription")["zip_path"]
        inbox = self.root / "inbox"
        outcomes = smoke_package.import_packages([z1, z2], inbox)
        self.assertEqual([o["status"] for o in outcomes], ["imported", "imported"])
        matrix = smoke_package.write_matrix(inbox)
        text = matrix.read_text()
        self.assertIn("| | anthropic-subscription | chatgpt-subscription |", text)
        rows = {ln.split("|")[1].strip().split(" ")[0]: ln for ln in text.splitlines()
                if ln.startswith("| T")}
        self.assertIn("FAIL on: chatgpt-subscription", rows["T0.3"])
        self.assertIn("common FAIL", rows["T0.10"])
        self.assertIn("| - |", rows["T0.8"])
        self.assertIn("2.1.281 (Claude Code)", text)

    def test_matrix_splits_pre_run_and_post_run_shim_scan(self):
        # The Tier-0 pre-run history and the post-run scan share probe_id T0.20;
        # report.json tells them apart by tier ("post"). Each gets its own row,
        # so no cell reads "INFO/WARN".
        gpt = [_pr("T0.20", "Shim-log scan", "0", Verdict.INFO),
               _pr("T0.20", "Shim-log scan (post-run window)", "post", Verdict.WARN)]
        api = [_pr("T0.20", "Shim-log scan", "0", Verdict.INFO),
               _pr("T0.20", "Shim-log scan (post-run window)", "post", Verdict.PASS)]
        r1, _ = self.make_report("rep_gpt", gpt, route="chatgpt-subscription")
        r2, _ = self.make_report("rep_api", api, route="openai-api")
        inbox = self.root / "inbox"
        smoke_package.import_packages([self.build(r1, gpt, route="chatgpt-subscription")["zip_path"],
                                       self.build(r2, api, route="openai-api")["zip_path"]], inbox)
        text = smoke_package.write_matrix(inbox).read_text()
        rows = [ln for ln in text.splitlines() if ln.startswith("| T0.20")]
        self.assertEqual(len(rows), 2, rows)
        pre, post = rows  # pre-run sorts first
        self.assertTrue(pre.startswith("| T0.20 Shim-log scan |"), pre)
        self.assertTrue(post.startswith("| T0.20 (post-run) Shim-log scan (post-run window) |"), post)
        for row in rows:
            cells = [c.strip() for c in row.split("|")[2:4]]
            self.assertTrue(all("/" not in c for c in cells), row)
        self.assertEqual([c.strip() for c in pre.split("|")[2:5]], ["INFO", "INFO", ""])
        self.assertEqual([c.strip() for c in post.split("|")[2:5]], ["WARN", "PASS", "WARN on: chatgpt-subscription"])

    def test_matrix_same_route_columns_are_distinguishable(self):
        report_dir, results = self.make_report()
        inbox = self.root / "inbox"
        z1 = self.build(report_dir, results)["zip_path"]
        z2 = self.build(report_dir, results)["zip_path"]  # same second -> "_2" suffix
        smoke_package.import_packages([z1, z2], inbox)
        header = [ln for ln in smoke_package.write_matrix(inbox).read_text().splitlines()
                  if ln.startswith("| | ")][0]
        labels = [c.strip() for c in header.split("|")[2:-1]]
        self.assertEqual(len(set(labels)), 2, labels)
        self.assertTrue(all(lab.startswith("anthropic-subscription (20261013T203000Z_96381ca") for lab in labels))

    def test_matrix_needs_two_packages(self):
        report_dir, results = self.make_report()
        inbox = self.root / "inbox"
        smoke_package.import_package(self.build(report_dir, results)["zip_path"], inbox)
        self.assertIsNone(smoke_package.write_matrix(inbox))

    def test_corrupt_deflate_member_is_rejected_and_others_import(self):
        # S4: a damaged deflate stream raised zlib.error out of the importer and
        # aborted the whole batch. It is now one rejection among imports.
        report_dir, results = self.make_report()
        good = self.build(report_dir, results)["zip_path"]
        bad = self.build(report_dir, results)["zip_path"]
        with zipfile.ZipFile(bad) as zf:
            info = zf.getinfo("report.md")
        raw = bytearray(bad.read_bytes())
        name_len = int.from_bytes(raw[info.header_offset + 26:info.header_offset + 28], "little")
        extra_len = int.from_bytes(raw[info.header_offset + 28:info.header_offset + 30], "little")
        data_start = info.header_offset + 30 + name_len + extra_len
        raw[data_start] = 0xFF  # BTYPE=11: a reserved deflate block type -> zlib.error
        bad.write_bytes(bytes(raw))
        inbox = self.root / "inbox"
        with self.assertRaises(smoke_package.ImportRejected) as ctx:
            smoke_package.import_package(bad, inbox)
        self.assertIn("error", str(ctx.exception).lower())
        self.assertFalse((inbox / bad.name[:-4]).exists())
        outcomes = smoke_package.import_packages([bad, good], inbox)
        self.assertEqual([o["status"] for o in outcomes], ["rejected", "imported"])
        self.assertTrue((inbox / good.name[:-4] / "report.md").is_file())


# --- Package contents after the gates (S7), log reads and caps ---------------------------------

class PackageContentTests(_ScratchCase):
    def test_readme_is_generated_after_gates_and_lists_withheld_and_not_found(self):
        r = _pr("T1.1", "Live round-trip", "1", Verdict.FAIL, detail="no completion token",
                evidence=[("claude -p (session 0123abcd)", "error text")])
        report_dir, _ = self.make_report(results=[r])
        (report_dir / "evidence" / "leak.log").write_text("leak")
        real_scrub = smoke_package.scrub_text

        def scrub_but_leave_leak(text, env, drop):
            out = real_scrub(text, env, drop)
            return (out[0] + " " + fake_sk(), out[1]) if text == "leak" else out
        with mock.patch.object(smoke_package, "scrub_text", side_effect=scrub_but_leave_leak):
            built = self.build(report_dir, [r])
        with zipfile.ZipFile(built["zip_path"]) as zf:
            readme = zf.read("README_FOR_MAIN_SESSION.md").decode()
            md = zf.read("report.md").decode()
        self.assertIn("## Not in this package", readme)
        self.assertIn("`evidence/leak.log`: withheld: secret-shaped content (sk_key)", readme)
        self.assertIn("transcript for session 0123abcd", readme)  # not found (no transcript on disk)
        self.assertNotIn(fake_sk(), readme)
        problems = md[md.index("### Problems"):md.index("**Passed:**")]
        self.assertIn("`transcripts/0123abcd/` (not in package)", problems)
        readme_entry = {f["path"]: f for f in built["manifest"]["files"]}["README_FOR_MAIN_SESSION.md"]
        self.assertEqual(readme_entry["source"], "generated (after the gates)")
        smoke_package.import_package(built["zip_path"], self.root / "inbox")  # hashes still verify

    def test_problem_evidence_path_marked_withheld(self):
        md = "\n".join([
            "### Problems (FAIL first, then WARN)", "",
            "| Probe | Verdict | Observed | Likely cause | Evidence in package | Where to fix |",
            "|-------|---------|----------|--------------|---------------------|--------------|",
            "| T0.20 Shim-log scan | FAIL | x \\| y | cause | `report.md § T0.20`, `logs/shim.log` | here |",
            "| T0.18 Codex | WARN | `logs/shim.log` in detail | cause | `logs/codex_config.log` | here |",
            "", "**Passed:** Tier 0: 1 of 3", "", "| T9.9 | after | `logs/shim.log` | x | `logs/shim.log` | y |"])
        out, n = smoke_package.annotate_problem_evidence(md, {"logs/codex_config.log"}, {"logs/shim.log"})
        self.assertEqual(n, 1)
        self.assertIn("`report.md § T0.20`, `logs/shim.log` (withheld) | here |", out)
        self.assertIn("| `logs/shim.log` in detail |", out)  # the Observed cell is untouched
        self.assertIn("| `logs/codex_config.log` | here |", out)
        self.assertTrue(out.endswith("| T9.9 | after | `logs/shim.log` | x | `logs/shim.log` | y |"))

    def test_shim_log_credits_stripped_in_package(self):
        # Q-M1 end to end: the quota_snapshot line keeps its rate-window numbers.
        base = self.fake_base()
        logs = base / "scripts" / "provider_shim" / "logs"
        logs.mkdir(parents=True)
        local = T_START.astimezone().replace(tzinfo=None)
        stamp = (local + timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S") + ",000"
        (logs / "shim.log").write_text(quota_snapshot_line(stamp) + "\n")
        report_dir, results = self.make_report(route="chatgpt-subscription")
        built = self.build(report_dir, results, route="chatgpt-subscription", base_dir=base)
        with zipfile.ZipFile(built["zip_path"]) as zf:
            shim = zf.read("logs/shim.log").decode()
        self.assertNotIn(fake_balance(), shim)
        self.assertIn("credits_balance=[REDACTED]", shim)
        self.assertIn("primary_used_pct=7", shim)
        entry = {f["path"]: f for f in built["manifest"]["files"]}["logs/shim.log"]
        self.assertEqual(entry["scrub_counts"]["credits"], 3)
        self.assertEqual(built["manifest"]["gates"]["post_scrub_secret_scan"], "clean")

    def test_large_log_read_from_end_and_truncation_recorded(self):
        base = self.fake_base()
        activity = base / ".claude" / "logs" / "activity.log"
        local = T_START.astimezone().replace(tzinfo=None)
        old = (local - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        inside = (local + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
        activity.write_text("".join(f"{old} old line {i}\n" for i in range(2000)) + f"{inside} in the run\n")
        report_dir, results = self.make_report()
        with mock.patch.object(smoke_package, "MAX_SOURCE_FILE_BYTES", 4096):
            built = self.build(report_dir, results, base_dir=base)
        with zipfile.ZipFile(built["zip_path"]) as zf:
            tail = zf.read("logs/activity.tail.log").decode()
            readme = zf.read("README_FOR_MAIN_SESSION.md").decode()
        self.assertIn("in the run", tail)
        trunc = built["manifest"]["truncated_reads"]
        self.assertEqual(len(trunc), 1)
        self.assertTrue(trunc[0]["source"].endswith("activity.log"))
        self.assertLessEqual(trunc[0]["bytes_read"], 4096)
        self.assertGreater(trunc[0]["bytes_total"], 4096)
        self.assertIn("Read from the end only", readme)

    def test_read_tail_text_drops_partial_first_line(self):
        p = self.root / "x.log"
        p.write_text("aaaa\nbbbb\ncccc\n")
        text, total, read, truncated = smoke_package.read_tail_text(p, max_bytes=8)
        self.assertEqual((text, total, truncated), ("cccc\n", 15, True))
        self.assertEqual(smoke_package.read_tail_text(p)[0], "aaaa\nbbbb\ncccc\n")

    def test_package_size_cap_excludes_and_warns(self):
        report_dir, results = self.make_report()
        (report_dir / "evidence" / "big.log").write_text("z" * 5000)
        with mock.patch.object(smoke_package, "MAX_PACKAGE_TOTAL_BYTES", 6000):
            built = self.build(report_dir, results)
        self.assertNotIn("evidence/big.log", _zip_names(built["zip_path"]))
        self.assertTrue(built["manifest"]["size"]["cap_reached"])
        self.assertTrue(any("size cap" in w for w in built["warnings"]))
        self.assertTrue(any("size cap" in e["reason"] for e in built["manifest"]["excluded"]))

    def test_audit_jsonl_symlink_is_not_read(self):
        base = self.fake_base()
        target = self.root / "elsewhere.jsonl"
        target.write_text(json.dumps({"session_id": SID_A, "tool": "Bash"}) + "\n")
        audit = base / ".claude" / "logs" / "audit.jsonl"
        os.symlink(target, audit)
        self.addCleanup(lambda: audit.is_symlink() and audit.unlink())
        r = _pr("T1.1", "Live round-trip", "1", Verdict.PASS)
        r.session_ids = [SID_A]
        report_dir, _ = self.make_report(results=[r])
        built = self.build(report_dir, [r], base_dir=base, projects_dir=self.root / "none")
        self.assertNotIn("logs/audit.jsonl", _zip_names(built["zip_path"]))
        reasons = {e["source"]: e["reason"] for e in built["manifest"]["excluded"]}
        self.assertEqual(reasons[str(audit)], "not a regular file; not read")


# --- Review fix cycle 2: generated files, README fallback, MANIFEST ------------------------------

class GeneratedFileTests(_ScratchCase):
    def _build_direct(self, report_dir, results, versions):
        return smoke_package.build_package(
            report_dir, "anthropic-subscription", T_START, T_END, versions, results, self.fake_base(),
            out_dir=self.root / "packages", detected_route="anthropic-subscription", overall="PASS",
            summary={"PASS": 1}, env={}, user_settings_path=self.root / "no_user_settings.json")

    def test_t020_warn_row_survives_in_both_reports(self):
        # Item 1 (MUST-FIX): a WARN T0.20 with its remediation hint, packaged.
        # The cycle-1 hint named the Codex turn-state header, so the whole-line
        # drop erased the row from report.md and broke report.json.
        warn = smoke_probes.apply_hints([_pr("T0.20", "Shim-log scan (post-run)", "post", Verdict.WARN,
                                             detail="Shim log shows claude_named_requests=2 in this run's window.")])[0]
        self.assertEqual(warn.hint, smoke_probes.PROBE_HINTS["T0.20"])
        # Half (b) on its own: a hint that still NAMES the header, and a detail
        # carrying a header with a value. Neither may cost a row.
        old = _pr("T0.19", "Prompt-cache health", "0", Verdict.WARN, detail="low reuse",
                  hint="x-codex-" + "turn-state -> shim >= 1.4.9 and rotate the log")
        leak = _pr("T0.18", "Codex config", "0", Verdict.FAIL, detail="saw " + codex_header_line())
        results = [warn, old, leak]
        report_dir, _ = self.make_report(results=results, route="chatgpt-subscription")
        built = self.build(report_dir, results, route="chatgpt-subscription")
        with zipfile.ZipFile(built["zip_path"]) as zf:
            md = zf.read("report.md").decode()
            raw_json = zf.read("report.json").decode()
        data = json.loads(raw_json)  # report.json still parses
        problems = md[md.index("### Problems"):md.index("**Passed:**")]
        for pid in ("T0.20", "T0.19", "T0.18"):
            self.assertTrue(any(ln.startswith(f"| {pid} ") for ln in problems.splitlines()), pid)
        self.assertIn(smoke_probes.PROBE_HINTS["T0.20"].split(":")[0], problems)
        by_id = {r["probe_id"]: r for r in data["results"]}
        self.assertEqual((by_id["T0.20"]["verdict"], by_id["T0.20"]["hint"]),
                         ("WARN", smoke_probes.PROBE_HINTS["T0.20"]))
        self.assertTrue(by_id["T0.19"]["hint"].startswith("x-codex-turn-state -> shim"))
        self.assertIn("[REDACTED:header]", by_id["T0.18"]["detail"])
        self.assertNotIn("opaque", md + raw_json)
        files = {f["path"]: f for f in built["manifest"]["files"]}
        for rel in ("report.md", "report.json"):
            self.assertNotIn("dropped_lines", files[rel]["scrub_counts"], rel)
        self.assertEqual(built["manifest"]["withheld"], [])
        # write_matrix reads report.json: the package is a column, not skipped.
        other, other_results = self.make_report("rep_sub", [_pr("T0.20", "Shim-log scan", "0", Verdict.INFO)])
        inbox = self.root / "inbox"
        smoke_package.import_packages([built["zip_path"], self.build(other, other_results)["zip_path"]], inbox)
        rows = [ln for ln in smoke_package.write_matrix(inbox).read_text().splitlines() if ln.startswith("| T0.20")]
        self.assertTrue(any("WARN" in ln for ln in rows), rows)

    def test_no_hint_names_a_dropped_or_cut_marker(self):
        for pid, hint in smoke_probes.PROBE_HINTS.items():
            for marker in smoke_package.DROP_LINE_MARKERS + smoke_package.SHIM_TRUNCATE_MARKERS:
                self.assertNotIn(marker, hint.lower(), pid)

    def test_generated_json_broken_by_scrubbing_is_withheld(self):
        stage = self.root / "stage"
        stage.mkdir()
        st = smoke_package._Stager(stage, {})
        st.add_text("report.json", '{"cred' + 'its_balance": ' + fake_balance() + "}", "test")
        self.assertNotIn("report.json", st.files)
        reasons = {w["path"]: w["reason"] for w in st.withheld}
        self.assertIn("generated JSON no longer parses after scrubbing", reasons["report.json"])
        # Changed by scrubbing but still valid: kept.
        st.add_text("config/settings_projection.json", json.dumps({"note": "mail " + fake_email()}), "test")
        self.assertIn("config/settings_projection.json", st.files)
        json.loads((stage / "config" / "settings_projection.json").read_text())

    def test_readme_fallback_goes_through_scrub_and_gate(self):
        report_dir, results = self.make_report()
        real_scrub, real_readme = smoke_package.scrub_text, smoke_package._readme_text

        def scrub(text, env, drop):  # the full README's leak reaches the gate unscrubbed
            return (text, smoke_package._empty_counts()) if "full leak" in text else real_scrub(text, env, drop)

        def readme(meta, *args, **kw):  # positional args = the full form; none = the static fallback
            return real_readme(meta, *args, **kw) + (
                "\nfull leak " + fake_sk() if args else "\nstatic contact " + fake_email())
        with mock.patch.object(smoke_package, "scrub_text", side_effect=scrub), \
                mock.patch.object(smoke_package, "_readme_text", side_effect=readme):
            built = self.build(report_dir, results)
        with zipfile.ZipFile(built["zip_path"]) as zf:
            text = zf.read("README_FOR_MAIN_SESSION.md").decode()
        self.assertIn("static contact [REDACTED:email]", text)  # the fallback was scrubbed
        self.assertNotIn(fake_sk(), text)
        self.assertNotIn(fake_email(), text)
        entry = {f["path"]: f for f in built["manifest"]["files"]}["README_FOR_MAIN_SESSION.md"]
        self.assertEqual(entry["scrub_counts"], {"email": 1})
        self.assertNotIn("README_FOR_MAIN_SESSION.md", [w["path"] for w in built["manifest"]["withheld"]])

    def test_readme_withheld_when_fallback_also_fails_the_gate(self):
        report_dir, results = self.make_report()
        real_scrub, real_readme = smoke_package.scrub_text, smoke_package._readme_text

        def scrub(text, env, drop):
            return (text, smoke_package._empty_counts()) if "leak" in text else real_scrub(text, env, drop)
        with mock.patch.object(smoke_package, "scrub_text", side_effect=scrub), \
                mock.patch.object(smoke_package, "_readme_text",
                                  side_effect=lambda meta, *a, **k: real_readme(meta, *a, **k) + " leak " + fake_sk()):
            built = self.build(report_dir, results)
        self.assertNotIn("README_FOR_MAIN_SESSION.md", _zip_names(built["zip_path"]))
        reasons = {w["path"]: w["reason"] for w in built["manifest"]["withheld"]}
        self.assertIn("full and static forms (sk_key)", reasons["README_FOR_MAIN_SESSION.md"])
        self.assertTrue(any("README" in w for w in built["warnings"]))
        smoke_package.import_package(built["zip_path"], self.root / "inbox")  # still verifies

    def test_manifest_is_scrubbed_and_still_verifies(self):
        report_dir, results = self.make_report()
        versions = dict(_versions(), claude_code="2.1.281 (Claude Code) " + fake_email())
        built = self._build_direct(report_dir, results, versions)
        with zipfile.ZipFile(built["zip_path"]) as zf:
            raw = zf.read("MANIFEST.json").decode()
        self.assertNotIn(fake_email(), raw)
        manifest = json.loads(raw)
        self.assertEqual(manifest["versions"]["claude_code"], "2.1.281 (Claude Code) [REDACTED:email]")
        self.assertEqual(manifest["manifest_self_scrub_counts"], {"email": 1})
        self.assertEqual(manifest, built["manifest"])
        self.assertEqual(manifest["secret_vocab_source"], smoke_package.SECRET_VOCAB_SOURCE)  # not redacted
        dest = smoke_package.import_package(built["zip_path"], self.root / "inbox")  # every hash verifies
        self.assertTrue((dest / "report.json").is_file())

    def test_manifest_failing_the_gate_writes_no_package(self):
        report_dir, results = self.make_report()
        versions = dict(_versions(), claude_code="x " + fake_sk())
        with mock.patch.object(smoke_package, "scrub_text",
                               side_effect=lambda t, e, d: (t, smoke_package._empty_counts())):
            with self.assertRaises(smoke_package.PackageError) as ctx:
                self._build_direct(report_dir, results, versions)
        self.assertIn("MANIFEST.json still holds secret-shaped content (sk_key)", str(ctx.exception))
        self.assertEqual(sorted(p.name for p in (self.root / "packages").iterdir()), [])


# --- Runner: post-run shim-log scan (S3), cost (C7), identity and naming ------------------------

class RunnerV2Tests(_ScratchCase):
    def _main(self, argv, **patches):
        stack = [
            mock.patch.object(run_deploy_smoke, "PACKAGES_ROOT", self.root / "packages"),
            mock.patch.object(run_deploy_smoke, "INBOX_ROOT", self.root / "inbox"),
            mock.patch.object(run_deploy_smoke, "REPORTS_ROOT", self.root / "reports"),
            mock.patch.object(run_deploy_smoke, "BASE_DIR", str(self.fake_base())),
            mock.patch.object(run_deploy_smoke, "collect_versions", return_value=_versions()),
            mock.patch("sys.stdout", io.StringIO()),
            mock.patch("sys.stderr", io.StringIO()),
        ]
        stack += [mock.patch.object(smoke_probes, k, v, create=True) for k, v in patches.items()]
        for p in stack:
            p.start()
        try:
            return run_deploy_smoke.main(argv)
        finally:
            for p in reversed(stack):
                p.stop()

    def _coherent(self, env, base, **kw):
        r = _pr("T0.14", "Main model coherence", kw.get("tier", "1"), Verdict.PASS)
        r.profile = kw.get("profile", "")
        return r

    def _scan(self, calls, verdict=Verdict.FAIL):
        def scan(route, since=None, until=None, log_path=None, probe_id="T0.20", tier="0", name="Shim-log scan"):
            calls.append({"route": route, "since": since, "tier": tier})
            r = _pr(probe_id, name, tier, verdict, detail="Shim log shows insufficient_quota=1.")
            return r
        return scan

    def _report(self):
        return (self.root / "report" / "report.md").read_text(), \
            json.loads((self.root / "report" / "report.json").read_text())

    def test_post_run_scan_on_shim_route_after_a_live_tier(self):
        calls = []
        t1 = _pr("T1.1", "Live round-trip", "1", Verdict.PASS, evidence=[("claude -p (session 0123abcd)", "ok")])
        rc = self._main(["--route", "chatgpt-subscription", "--tiers", "1", "--yes", "--no-package",
                         "--report-dir", str(self.root / "report")],
                        probe_main_model_coherence=self._coherent, run_tier1=mock.Mock(return_value=[t1]),
                        probe_shim_log_scan=self._scan(calls))
        self.assertEqual(rc, 1)  # the post-run FAIL carries the verdict
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["route"], "chatgpt-subscription")
        self.assertEqual(calls[0]["tier"], "post")
        self.assertRegex(calls[0]["since"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        md, data = self._report()
        self.assertIn("## Post-run", md)
        self.assertLess(md.index("## Tier 1"), md.index("## Post-run"))
        self.assertIn("Post-run: 0 of 1", md)
        post = [r for r in data["results"] if r["tier"] == "post"]
        self.assertEqual(post[0]["verdict"], "FAIL")
        problems = md[md.index("### Problems"):md.index("**Passed:**")]
        self.assertIn("`logs/shim.log`", problems)

    def test_no_post_run_scan_without_live_tier_or_off_shim(self):
        calls = []
        self._main(["--route", "chatgpt-subscription", "--tiers", "0", "--yes", "--no-package",
                    "--report-dir", str(self.root / "report")],
                   run_tier0=mock.Mock(return_value=[]), probe_shim_log_scan=self._scan(calls))
        t1 = _pr("T1.1", "Live round-trip", "1", Verdict.PASS)
        self._main(["--route", "anthropic-subscription", "--tiers", "1", "--yes", "--no-package",
                    "--report-dir", str(self.root / "report2")],
                   probe_main_model_coherence=self._coherent, run_tier1=mock.Mock(return_value=[t1]),
                   probe_shim_log_scan=self._scan(calls))
        self.assertEqual(calls, [])

    def test_post_run_scan_binds_by_name(self):
        seen = {}

        def narrow_scan(route, since=None):
            seen.update(route=route, since=since)
            return _pr("T0.20", "Shim-log scan", "0", Verdict.PASS)
        t1 = _pr("T1.1", "Live round-trip", "1", Verdict.PASS)
        self._main(["--route", "openai-api", "--tiers", "1", "--yes", "--no-package",
                    "--report-dir", str(self.root / "report")],
                   probe_main_model_coherence=self._coherent, run_tier1=mock.Mock(return_value=[t1]),
                   probe_shim_log_scan=narrow_scan)
        self.assertEqual(seen["route"], "openai-api")
        _, data = self._report()
        self.assertEqual([r["tier"] for r in data["results"] if r["probe_id"] == "T0.20"], ["post"])

    def test_tier3_resume_counts_two_calls_and_sums_cost(self):
        r31 = _pr("T3.1", "Gate", "3", Verdict.PASS, evidence=[("claude -p 'q' (session 0123abcd)", "")])
        r31.session_ids, r31.cost_usd = [SID_A], 0.25
        r32 = _pr("T3.2", "Golden", "3", Verdict.PASS, evidence=[("claude -p --resume 0123abcd 'Yes'", "")])
        r32.session_ids, r32.cost_usd = [SID_A], 0.5
        r11 = _pr("T1.1", "Round-trip", "1", Verdict.PASS, evidence=[("claude -p (session 99999999)", "")])
        r11.cost_usd = 0.1
        r17 = _pr("T1.7", "Usage", "1", Verdict.PASS, evidence=[("usage", "total_cost_usd=0.1")])
        r17.cost_usd = 0.1  # same invocation as T1.1: not a second call, not added twice
        calls, total, upper = run_deploy_smoke._run_cost([r11, r17, r31, r32])
        self.assertEqual(calls, 3)
        self.assertAlmostEqual(total, 0.85)
        self.assertTrue(upper)
        report_dir, _ = self.make_report(results=[r11, r17, r31, r32])
        md = (report_dir / "report.md").read_text()
        self.assertIn("| Paid calls / cost | 3 claude -p call(s) / $0.8500 (upper bound", md)
        self.assertTrue(json.loads((report_dir / "report.json").read_text())["total_cost_is_upper_bound"])

    def test_report_folder_and_package_use_the_stated_route(self):
        self._main(["--route", "anthropic-api", "--tiers", "0", "--yes"],
                   run_tier0=mock.Mock(return_value=[_pr("T0.5", "CLI", "0", Verdict.PASS)]))
        folders = [p.name for p in (self.root / "reports").iterdir()]
        self.assertEqual(len(folders), 1)
        self.assertTrue(folders[0].endswith("_anthropic-api"), folders)
        zips = list((self.root / "packages").glob("*.zip"))
        self.assertEqual(len(zips), 1)
        self.assertIn("_anthropic-api_", zips[0].name)

    def test_identity_uses_probe_versions_dirty_count(self):
        probe = {"daaf_branch": "b", "daaf_sha": "a" * 40, "daaf_describe": "v1-dirty", "dirty_files": 5,
                 "claude_code": "2.1.281", "codex": None, "shim_source": "1.4.9"}
        with mock.patch.object(smoke_probes, "collect_versions", return_value=probe, create=True):
            v = run_deploy_smoke.collect_versions("/not-used")
        self.assertEqual((v["daaf_dirty_files"], v["source"]), (5, "smoke_probes.collect_versions"))
        self.assertIn("untracked", v["daaf_dirty_scope"])
        report_dir, _ = self.make_report(versions=dict(_versions(), daaf_dirty_files=5))
        identity = (report_dir / "report.md").read_text().split("### Problems")[0]
        self.assertIn("5 dirty file(s) (tracked and untracked", identity)

    def test_evidence_paths_name_the_packaged_logs(self):
        for probe_id, expected in (("T0.18", ["logs/codex_config.log", "logs/shim.log"]),
                                   ("T0.8", ["logs/shim.log"]), ("TA.1", ["logs/shim.log"])):
            paths = run_deploy_smoke._package_evidence_paths(_pr(probe_id, "x", "0", Verdict.FAIL), self.root)
            for p in expected:
                self.assertIn(p, paths, probe_id)


if __name__ == "__main__":
    unittest.main()
