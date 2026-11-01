"""Network-free tests for retried-attempt recording in scholar_search (tool 1.6.2).

User decision 2026-11-01: a request that was retried records every retried
attempt in its request-log entry as `retried_attempts` (raw log and the
MANIFEST row's `requests`): the attempt number, the HTTP status that caused
the retry, the server's Retry-After header as sent (secrets and the contact
email redacted, then cut to 100 characters), the delay applied, where that
delay came from (`retry-after` or `backoff`) and how it was applied (`lane`
or `sleep`). A busy gate on a retry has no request entry, so its
`rate_gate_skips` entry carries the list. Retry BEHAVIOR is unchanged: these
tests also pin the call counts, sleeps and gate pushes the retry loop makes,
so a recording change that altered them would fail here.

Standard-library unittest + unittest.mock only; no network (every HTTP call
goes to a fake client). Kept in its own module; CI discovers it
(`test_*.py`) and so does the scholarly-search test command
(`-p "test_scholar*.py"`). This module defines its own TestCases and imports
none from the other scholar suites (an imported TestCase class would be
collected and run twice). Gate state and CLI destinations live under
scripts/scratch/ (never /tmp) and are removed in tearDown.

Run directly:
  python3 -m unittest discover -s /daaf/tests/python -p 'test_scholar_retry_log.py'
"""

import io
import json
import os
import shutil
import sys
import time
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

# httpx is scholar_search's only third-party dependency; skip, as
# test_scholar_search.py does, on a host without it.
try:
    import httpx
except ModuleNotFoundError:
    raise unittest.SkipTest("httpx not available on this host")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import scholar_search  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "scholar_search"
FAKE_KEY = "sk-test-RETRYLOG-0123456789abcdef"   # fake key value; must never appear in output
FAKE_CONTACT = "retry.tester@example.org"        # fake contact email; scrubbed from every artifact
URL = "https://api.example/read"


def fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeResp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self.content = json.dumps(body if body is not None else {}).encode()
        self.headers = httpx.Headers(headers or {})


class FakeClient:
    """Answers each GET/POST with the next item of `answers` (an exception is raised)."""

    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def _next(self):
        out = next(self.answers)
        if isinstance(out, Exception):
            raise out
        return out

    def get(self, url, params=None, headers=None):
        self.calls.append({"method": "GET", "url": url})
        return self._next()

    def post(self, url, params=None, headers=None, json=None):
        self.calls.append({"method": "POST", "url": url})
        return self._next()


class Scratch(unittest.TestCase):
    """Per-test scratch dir under scripts/scratch/; sleep recorded, not slept; no gated lanes by default."""

    def setUp(self):
        self.root = _SCRIPTS / "scratch" / f"scholar_retrylog_test_{uuid.uuid4().hex[:10]}"
        self.dest = self.root / "lit_search"
        self.root.mkdir(parents=True)
        self._env = mock.patch.dict(os.environ, {"SCHOLAR_SEARCH_STATE_DIR": str(self.root / "gate"),
                                                 "OPENALEX_API_KEY": FAKE_KEY,
                                                 "SCHOLARLY_CONTACT_EMAIL": FAKE_CONTACT,
                                                 "DAAF_FETCH_CONTEXT": "unit-test"})
        self._env.start()
        os.environ.pop("OPENALEX_RATE_TIER", None)   # patch.dict restores it
        self.slept = []
        self._sleep = mock.patch.object(scholar_search.time, "sleep", side_effect=self.slept.append)
        self._sleep.start()
        self._gate = mock.patch.object(scholar_search, "GATE_INTERVALS", {})
        self._gate.start()

    def tearDown(self):
        self._gate.stop()
        self._sleep.stop()
        self._env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def http(self, answers):
        fake = FakeClient(answers)
        return scholar_search.Http(5, client=fake), fake


def rec(attempt, status, delay, source, applied, retry_after=None):
    # The expected record for one retried attempt.
    out = {"attempt": attempt, "http_status": status}
    if retry_after is not None:
        out["retry_after"] = retry_after
    out.update(delay_s=delay, delay_source=source, applied_as=applied)
    return out


# --- Http: what is recorded --------------------------------------------------
class RetriedAttemptsRecordTests(Scratch):
    def test_no_retry_leaves_the_entry_shape_unchanged(self):
        http, fake = self.http([FakeResp(200, {"ok": 1})])
        http.get("openalex", URL)
        self.assertEqual(len(fake.calls), 1)
        self.assertNotIn("retried_attempts", http.log[-1])
        self.assertNotIn("retried_attempts", scholar_search.summarize_requests(http.log)[-1])
        self.assertEqual(http.gate_skips, [])

    def test_retry_after_is_recorded_and_used(self):
        http, fake = self.http([FakeResp(429, {}, {"retry-after": "2"}), FakeResp(200, {"ok": 1})])
        self.assertEqual(http.get("openalex", URL), {"ok": 1})
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(self.slept, [2.0])
        entry = http.log[-1]
        self.assertEqual((entry["http_status"], entry["attempts"], entry["retries"]), (200, 2, 1))
        self.assertEqual(entry["retried_attempts"], [rec(1, 429, 2.0, "retry-after", "sleep", "2")])
        self.assertEqual(entry["wait_s"], 2.0)

    def test_backoff_without_a_header_has_no_retry_after_key(self):
        with mock.patch.object(scholar_search.random, "uniform", return_value=1.0):
            http, fake = self.http([FakeResp(503), FakeResp(502), FakeResp(200, {"ok": 1})])
            http.get("openalex", URL)
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(self.slept, [2.0, 4.0])   # min(2**attempt, cap) * 1.0
        self.assertEqual(http.log[-1]["retried_attempts"],
                         [rec(1, 503, 2.0, "backoff", "sleep"), rec(2, 502, 4.0, "backoff", "sleep")])
        self.assertEqual(len(http.log[-1]["retried_attempts"]), http.log[-1]["retries"])

    def test_a_date_retry_after_is_recorded_as_sent_but_not_used(self):
        date = "Wed, 21 Oct 2026 07:28:00 GMT"
        with mock.patch.object(scholar_search.random, "uniform", return_value=1.0):
            http, _ = self.http([FakeResp(503, {}, {"retry-after": date}), FakeResp(200, {"ok": 1})])
            http.get("openalex", URL)
        self.assertEqual(self.slept, [2.0])
        self.assertEqual(http.log[-1]["retried_attempts"], [rec(1, 503, 2.0, "backoff", "sleep", date)])

    def test_huge_retry_after_is_capped_in_the_wait_and_cut_in_the_record(self):
        http, _ = self.http([FakeResp(429, {}, {"retry-after": "9" * 500}), FakeResp(200, {"ok": 1})])
        http.get("openalex", URL)
        self.assertEqual(self.slept, [scholar_search.BACKOFF_CAP])
        got = http.log[-1]["retried_attempts"][0]
        self.assertEqual(got["retry_after"], "9" * 100)
        self.assertEqual((got["delay_s"], got["delay_source"]), (scholar_search.BACKOFF_CAP, "retry-after"))

    def test_gated_lane_records_applied_as_lane_and_pushes_the_gate(self):
        with mock.patch.object(scholar_search, "GATE_INTERVALS", {"openalex": 0.04}):
            t0 = time.time()
            http, fake = self.http([FakeResp(429, {}, {"retry-after": "3"}), FakeResp(200, {"ok": 1})])
            http.get("openalex", URL)
            marker = float(Path(scholar_search.RateGate("openalex", 0.04).path).read_text())
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(http.log[-1]["retried_attempts"], [rec(1, 429, 3.0, "retry-after", "lane", "3")])
        # Behavior pin: the delay pushed the shared schedule instead of a plain
        # sleep, so the only sleep is the retry's own booking waiting for that
        # slot (the first booking found the lane free and did not sleep).
        # (The gate file stores the marker to 3 decimals, rounded, so the
        # booking may sleep a fraction of a millisecond past 3 s.)
        self.assertEqual(len(self.slept), 1)
        self.assertGreater(self.slept[0], 2.5)
        self.assertLess(self.slept[0], 3.01)
        self.assertGreaterEqual(marker, t0 + 3 - 0.01)

    def test_retries_exhausted_records_every_retried_attempt(self):
        with mock.patch.object(scholar_search.random, "uniform", return_value=1.0):
            http, fake = self.http([FakeResp(503)] * scholar_search.MAX_ATTEMPTS)
            with self.assertRaises(scholar_search.BackendError) as ctx:
                http.get("openalex", URL)
        self.assertEqual((ctx.exception.kind, ctx.exception.http_status), ("api", 503))
        self.assertEqual(len(fake.calls), scholar_search.MAX_ATTEMPTS)
        entry = http.log[-1]
        self.assertEqual((entry["http_status"], entry["attempts"]), (503, scholar_search.MAX_ATTEMPTS))
        self.assertEqual([r["attempt"] for r in entry["retried_attempts"]],
                         list(range(1, scholar_search.MAX_ATTEMPTS)))
        self.assertEqual(self.slept, [min(2 ** n, scholar_search.BACKOFF_CAP)
                                      for n in range(1, scholar_search.MAX_ATTEMPTS)])

    def test_timeout_after_a_retry_is_not_retried_and_keeps_the_record(self):
        with mock.patch.object(scholar_search.random, "uniform", return_value=1.0):
            http, fake = self.http([FakeResp(503), httpx.ReadTimeout("slow"), FakeResp(200, {"ok": 1})])
            with self.assertRaises(scholar_search.BackendError) as ctx:
                http.get("openalex", URL)
        self.assertEqual(ctx.exception.kind, "timeout")
        self.assertEqual(len(fake.calls), 2, "a timeout ends the request (never retried)")
        entry = http.log[-1]
        self.assertEqual((entry["http_status"], entry["error"], entry["attempts"]), (None, "ReadTimeout", 2))
        self.assertEqual(entry["retried_attempts"], [rec(1, 503, 2.0, "backoff", "sleep")])

    def test_penalized_429_after_a_retry_keeps_the_record(self):
        with mock.patch.object(scholar_search.random, "uniform", return_value=1.0):
            http, fake = self.http([FakeResp(503), FakeResp(429, {"error": "blocked"})])
            with self.assertRaises(scholar_search.BackendError) as ctx:
                http.get("openalex", URL, penalize_429=60)
        self.assertEqual((ctx.exception.kind, ctx.exception.http_status), ("busy", 429))
        self.assertEqual(len(fake.calls), 2)
        entry = http.log[-1]
        self.assertEqual((entry["http_status"], entry["penalized_s"]), (429, 60.0))
        self.assertEqual(entry["retried_attempts"], [rec(1, 503, 2.0, "backoff", "sleep")])

    def test_busy_gate_after_a_retry_puts_the_record_on_the_skip(self):
        # A Retry-After longer than max_wait: the retry's booking finds the
        # queue too long, so no request entry is logged; the skip carries it.
        with mock.patch.object(scholar_search, "GATE_INTERVALS", {"openalex": 0.04}):
            http, fake = self.http([FakeResp(429, {}, {"retry-after": "30"}), FakeResp(200, {"ok": 1})])
            with self.assertRaises(scholar_search.BackendError) as ctx:
                http.get("openalex", URL, max_wait=5)
        self.assertEqual(ctx.exception.kind, "busy")
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(http.log, [], "unchanged: a busy gate logs no request entry")
        self.assertEqual(http.gate_skips[-1]["lane"], "openalex")
        self.assertEqual(http.gate_skips[-1]["retried_attempts"], [rec(1, 429, 30.0, "retry-after", "lane", "30")])

    def test_busy_gate_without_a_retry_has_no_record(self):
        with mock.patch.object(scholar_search, "GATE_INTERVALS", {"openalex": 0.04}), \
                mock.patch.object(scholar_search.RateGate, "reserve", side_effect=scholar_search.GateBusy(300)):
            http, fake = self.http([FakeResp(200, {"ok": 1})])
            with self.assertRaises(scholar_search.BackendError):
                http.get("openalex", URL)
        self.assertEqual(len(fake.calls), 0)
        self.assertNotIn("retried_attempts", http.gate_skips[-1])

    def test_non_idempotent_post_is_never_retried_and_has_no_record(self):
        http, fake = self.http([FakeResp(503), FakeResp(200, {"ok": 1})])
        with self.assertRaises(scholar_search.BackendError) as ctx:
            http.post("scite", URL, {"q": 1}, max_attempts=6)   # ignored: not idempotent
        self.assertEqual((ctx.exception.kind, len(fake.calls)), ("api", 1))
        self.assertNotIn("retried_attempts", http.log[-1])
        self.assertEqual(self.slept, [])

    def test_idempotent_post_records_like_a_get(self):
        with mock.patch.object(scholar_search.random, "uniform", return_value=1.0):
            http, fake = self.http([FakeResp(503), FakeResp(429, {}, {"retry-after": "1"}), FakeResp(200, {"t": 1})])
            self.assertEqual(http.post("scite", URL, ["10.1/x"], idempotent=True), (200, {"t": 1}))
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(http.log[-1]["method"], "POST")
        self.assertEqual(http.log[-1]["retried_attempts"],
                         [rec(1, 503, 2.0, "backoff", "sleep"), rec(2, 429, 1.0, "retry-after", "sleep", "1")])

    def test_summarize_requests_keeps_a_non_empty_list_only(self):
        base = {"backend": "openalex", "endpoint": URL, "params": {}, "http_status": 200, "attempts": 1,
                "retries": 0, "wait_s": 0.0, "cost": None}
        r = [rec(1, 429, 1.0, "retry-after", "sleep", "1")]
        got = scholar_search.summarize_requests([dict(base), dict(base, retried_attempts=[]),
                                                 dict(base, retried_attempts=r)])
        self.assertNotIn("retried_attempts", got[0])
        self.assertNotIn("retried_attempts", got[1])
        self.assertEqual(got[2]["retried_attempts"], r)

    def test_tool_version_is_at_least_1_6_2(self):
        core = scholar_search.TOOL_VERSION.split("-")[0]
        self.assertGreaterEqual(tuple(int(x) for x in core.split(".")), (1, 6, 2))


# --- End to end: raw log, MANIFEST row, redaction ----------------------------
class RetriedAttemptsCliTests(Scratch):
    def run_cli(self, argv, answers):
        fake = FakeClient(answers)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(scholar_search.httpx, "Client", return_value=fake), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                code = scholar_search.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue(), fake

    def rows(self):
        p = self.dest / "MANIFEST.jsonl"
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []

    def raw_text(self, row):
        return (self.dest / row["raw_artifact"]).read_text(encoding="utf-8")

    def test_row_and_raw_log_carry_the_record(self):
        code, *_ = self.run_cli(["work", "10.1093/qje/qjv036", str(self.dest)],
                                [FakeResp(429, {}, {"retry-after": "1"}), FakeResp(200, fixture("openalex_work.json"))])
        self.assertEqual(code, 0)
        row = self.rows()[-1]
        self.assertEqual(row["retries"], 1)
        want = [rec(1, 429, 1.0, "retry-after", "sleep", "1")]
        self.assertEqual(row["requests"][-1]["retried_attempts"], want)
        raw = json.loads(self.raw_text(row))
        self.assertEqual(raw["requests"][-1]["retried_attempts"], want)

    def test_row_without_a_retry_keeps_its_shape(self):
        code, *_ = self.run_cli(["work", "10.1093/qje/qjv036", str(self.dest)],
                                [FakeResp(200, fixture("openalex_work.json"))])
        self.assertEqual(code, 0)
        row = self.rows()[-1]
        self.assertNotIn("retried_attempts", row["requests"][-1])
        self.assertNotIn("retried_attempts", json.loads(self.raw_text(row))["requests"][-1])

    def test_secret_and_contact_in_retry_after_never_reach_disk(self):
        # A hostile Retry-After echoing the key (placed so a plain 100-char cut
        # would leave a fragment) and the contact email.
        for label, value in (("key at the cut", "x" * 90 + FAKE_KEY), ("key whole", FAKE_KEY),
                             ("contact", f"ask {FAKE_CONTACT}")):
            with self.subTest(label):
                shutil.rmtree(self.dest, ignore_errors=True)
                code, out, err, _ = self.run_cli(["work", "10.1093/qje/qjv036", str(self.dest)],
                                                 [FakeResp(503, {}, {"retry-after": value}),
                                                  FakeResp(200, fixture("openalex_work.json"))])
                self.assertEqual(code, 0)
                row = self.rows()[-1]
                texts = [(self.dest / "MANIFEST.jsonl").read_text(encoding="utf-8"), self.raw_text(row), out, err]
                for text in texts:
                    self.assertNotIn(FAKE_KEY[:10], text)
                    self.assertNotIn(FAKE_CONTACT, text)
                got = row["requests"][-1]["retried_attempts"][0]["retry_after"]
                self.assertLessEqual(len(got), 100)
                if label != "contact":
                    self.assertIn("[REDACTED", got)


if __name__ == "__main__":
    unittest.main()
