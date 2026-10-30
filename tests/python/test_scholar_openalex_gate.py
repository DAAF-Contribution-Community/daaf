"""Network-free tests for the OpenAlex per-second gate (scholar_search tool 1.6.0).

User decision 2026-10-30: the OpenAlex main lane is gated container-wide by
key tier, and a search with more than 5 upper-case AND/OR/NOT operators also
books an `openalex-boolean` lane. These tests cover interval selection
(keyed / keyless), operator counting, lane routing in the adapter, the
core's one-step multi-lane booking in Http (reserve_lanes(); Phase 4 review
fix: every lane's spacing must hold for send times), and registry
validation of the new lanes.

Standard-library unittest + unittest.mock only; no network (every HTTP call
goes to a fake client). Kept in its own module; CI discovers both
(`test_*.py`). This module
defines its own TestCases and imports none from test_scholar_search.py (an
imported TestCase class would be collected and run twice). Gate state and
CLI destinations live under scripts/scratch/ (never /tmp) and are removed in
tearDown.

Run directly:
  python3 -m unittest discover -s /daaf/tests/python -p 'test_scholar_openalex_gate.py'
"""

import importlib
import io
import json
import os
import shutil
import sys
import time
import types
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
import scholar_backends as registry  # noqa: E402
from scholar_backends import openalex  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "scholar_search"
FAKE_KEY = "oa-test-GATE-0123456789abcdef"   # fake key value; never a real credential
# Documented per-second limits (help.openalex.org/api/authentication, fetched
# 2026-10-28): keyless, free key / prepaid. Every gate interval must stay under them.
DOC_LIMITS = {True: {"openalex": 30, "openalex-boolean": 5, "openalex-semantic": 1},
              False: {"openalex": 10, "openalex-boolean": 1, "openalex-semantic": 1}}
REAL_INTERVALS = {"openalex": 0.04, "openalex-semantic": 1.1, "openalex-boolean": 0.22}


class FakeResp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self.content = json.dumps(body if body is not None else {}).encode()
        self.headers = httpx.Headers(headers or {})


class FakeClient:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": dict(params or {})})
        return self.handler(url, params or {}, headers or {})


class LaneRecorder:
    """Stands in for Http in adapter calls: records the lane each request books."""

    def __init__(self, body):
        self.body = body
        self.calls = []

    def get(self, backend, url, params=None, headers=None, lane=None, **kw):
        self.calls.append({"backend": backend, "url": url, "params": dict(params or {}), "lane": lane})
        return self.body


def works_body():
    return json.loads((FIX / "openalex_semantic_search.json").read_text(encoding="utf-8"))


def work_body():
    return json.loads((FIX / "openalex_work.json").read_text(encoding="utf-8"))


def ops(n, word="AND"):
    # A query with exactly n upper-case operators between n + 1 terms.
    return f" {word} ".join(f"term{i}" for i in range(n + 1))


class GateScratch(unittest.TestCase):
    """Per-test gate directory under scripts/scratch/, sleep mocked."""

    def setUp(self):
        self.root = _SCRIPTS / "scratch" / f"scholar_gate_test_{uuid.uuid4().hex[:10]}"
        self.dest = self.root / "lit_search"
        self.root.mkdir(parents=True)
        self._env = mock.patch.dict(os.environ, {"SCHOLAR_SEARCH_STATE_DIR": str(self.root / "gate"),
                                                 "OPENALEX_API_KEY": FAKE_KEY,
                                                 "DAAF_FETCH_CONTEXT": "unit-test"})
        self._env.start()
        os.environ.pop("SCHOLARLY_CONTACT_EMAIL", None)
        self._sleep = mock.patch.object(scholar_search.time, "sleep", lambda s: None)
        self._sleep.start()

    def tearDown(self):
        self._sleep.stop()
        self._env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def gate_files(self):
        gate = self.root / "gate"
        return sorted(p.stem for p in gate.glob("*.gate")) if gate.exists() else []

    def marker(self, lane):
        return float((self.root / "gate" / f"{lane}.gate").read_text())


# --- Interval selection ------------------------------------------------------
class IntervalSelectionTests(unittest.TestCase):
    def test_keyed_and_keyless_maps(self):
        self.assertEqual(openalex.rate_limit(True),
                         {"openalex": 0.04, "openalex-semantic": 1.1, "openalex-boolean": 0.22})
        self.assertEqual(openalex.rate_limit(False),
                         {"openalex": 0.11, "openalex-semantic": 1.1, "openalex-boolean": 1.1})

    def test_every_interval_stays_under_the_documented_limit(self):
        for keyed in (True, False):
            for lane, interval in openalex.rate_limit(keyed).items():
                with self.subTest(keyed=keyed, lane=lane):
                    self.assertLess(1.0 / interval, DOC_LIMITS[keyed][lane])

    def test_note_names_the_tier(self):
        self.assertIn("(keyed)", openalex.rate_limit_note(True))
        self.assertIn("every request 0.04 s", openalex.rate_limit_note(True))
        self.assertIn("(keyless)", openalex.rate_limit_note(False))
        self.assertIn("boolean-heavy 1.1 s", openalex.rate_limit_note(False))

    def test_module_load_reads_the_tier_from_the_key(self):
        # RATE_LIMIT is fixed when the adapter loads; reload under each env and
        # restore the original module state afterwards.
        try:
            for keyed, env in ((True, {"OPENALEX_API_KEY": FAKE_KEY}), (False, {"OPENALEX_API_KEY": "  "})):
                with self.subTest(keyed=keyed), mock.patch.dict(os.environ, env):
                    importlib.reload(openalex)
                    self.assertEqual(openalex.RATE_LIMIT, openalex.rate_limit(keyed))
                    self.assertEqual(registry.validate_registry(registry.ADAPTERS), [])
                    gates = registry.gate_intervals()
                    for lane, interval in openalex.rate_limit(keyed).items():
                        self.assertEqual(gates[lane], interval)
        finally:
            importlib.reload(openalex)

    def test_main_lane_is_gated_in_the_core(self):
        # The core's import-time GATE_INTERVALS holds every OpenAlex lane (the
        # main lane was None, i.e. ungated, before 1.6.0).
        for lane in ("openalex", "openalex-semantic", "openalex-boolean"):
            self.assertIn(lane, scholar_search.GATE_INTERVALS)
            self.assertEqual(scholar_search.GATE_INTERVALS[lane], openalex.RATE_LIMIT[lane])


# --- Operator counting -------------------------------------------------------
class OperatorCountTests(unittest.TestCase):
    def test_five_vs_six_operators(self):
        five = {"filter": f"title_and_abstract.search:{ops(5)}"}
        six = {"filter": f"title_and_abstract.search:{ops(6)}"}
        self.assertEqual(openalex.boolean_operator_count(five), 5)
        self.assertEqual(openalex.boolean_operator_count(six), 6)
        self.assertEqual(openalex.lanes_for(five), ("openalex",))
        self.assertEqual(openalex.lanes_for(six), ("openalex-boolean", "openalex"))

    def test_lowercase_words_are_not_operators(self):
        text = "reading and math or science not tested and more and more or less"
        self.assertEqual(openalex.boolean_operator_count({"search": text}), 0)
        self.assertEqual(openalex.boolean_operator_count({"search": "Reading And Math Or Not"}), 0)

    def test_only_whole_words_count(self):
        text = "ORDER ANDROID NOTE ORCID ANDORRA NOTABLE OR"
        self.assertEqual(openalex.boolean_operator_count({"search": text}), 1)
        self.assertEqual(openalex.boolean_operator_count({"search": "(a OR b) AND (c OR d) NOT e AND f"}), 5)

    def test_quoted_phrases_are_counted(self):
        # DAAF's conservative rule: a quoted upper-case operator still counts.
        text = '"war AND peace" OR "crime AND punishment" OR "pride AND prejudice"'
        self.assertEqual(openalex.boolean_operator_count({"search": text}), 5)
        self.assertEqual(openalex.lanes_for({"search": text + ' OR "x AND y"'}),
                         ("openalex-boolean", "openalex"))

    def test_which_params_are_counted(self):
        params = {"search": ops(2), "search.semantic": ops(1, "OR"),
                  "filter": f"title.search:{ops(2)},type:!dataset,publication_year:>2014,"
                            f"abstract.search.no_stem:{ops(1, 'NOT')}",
                  "sort": "relevance_score:desc OR AND NOT", "select": "id,doi"}
        # search 2 + search.semantic 1 + title.search 2 + abstract.search.no_stem 1; sort/select ignored
        self.assertEqual(openalex.boolean_operator_count(params), 6)
        self.assertEqual(openalex.boolean_operator_count({"filter": "type:!dataset,cites:W1"}), 0)
        self.assertEqual(openalex.boolean_operator_count({"per_page": 25, "filter": None}), 0)
        self.assertEqual(openalex.boolean_operator_count(None), 0)

    def test_sum_across_params_crosses_the_limit(self):
        params = {"search": ops(3), "filter": f"title_and_abstract.search:{ops(3)}"}
        self.assertEqual(openalex.lanes_for(params), ("openalex-boolean", "openalex"))

    def test_comma_inside_a_search_filter_cannot_hide_operators(self):
        # Searching docs (fetched 2026-10-30): "A comma in a search filter's text is
        # part of the text". 1 OR before the comma + 5 after = 6, so the boolean lane.
        value = f"title.search:alpha OR beta, {ops(5, 'OR')}"
        self.assertEqual(openalex.boolean_operator_count({"filter": value}), 6)
        self.assertEqual(openalex.lanes_for({"filter": value}), ("openalex-boolean", "openalex"))
        rec = LaneRecorder(works_body())
        openalex.search(rec, "", "filter", 5, extra_filter=value)
        self.assertEqual(rec.calls[-1]["lane"], ("openalex-boolean", "openalex"))
        # Without a .search clause the filter is not free text: nothing counted.
        self.assertEqual(openalex.boolean_operator_count({"filter": "type:!dataset,cites:W1 OR AND"}), 0)


# --- Lane routing in the adapter ---------------------------------------------
class LaneRoutingTests(unittest.TestCase):
    def test_lane_order_main_last(self):
        self.assertEqual(openalex.lanes_for({}), ("openalex",))
        self.assertEqual(openalex.lanes_for({}, "openalex-semantic"), ("openalex-semantic", "openalex"))
        self.assertEqual(openalex.lanes_for({"search.semantic": ops(6)}, "openalex-semantic"),
                         ("openalex-semantic", "openalex-boolean", "openalex"))

    def test_search_modes_book_the_right_lanes(self):
        cases = [("keyword", ops(5), ("openalex",)),
                 ("keyword", ops(6), ("openalex-boolean", "openalex")),
                 ("keyword", ops(6).lower(), ("openalex",)),
                 ("broad", ops(6, "OR"), ("openalex-boolean", "openalex")),
                 ("semantic", "a plain question about tutoring", ("openalex-semantic", "openalex")),
                 ("filter", "", ("openalex",))]
        for mode, query, want in cases:
            with self.subTest(mode=mode, query=query):
                rec = LaneRecorder(works_body())
                openalex.search(rec, query, mode, 5)
                self.assertEqual(rec.calls[-1]["lane"], want)

    def test_boolean_heavy_raw_filter_is_counted(self):
        # `openalex --filter` passes raw filter text; the lane is chosen from the final params.
        rec = LaneRecorder(works_body())
        openalex.search(rec, "", "filter", 5, extra_filter=f"fulltext.search:{ops(6)}")
        self.assertEqual(rec.calls[-1]["lane"], ("openalex-boolean", "openalex"))

    def test_title_lookup_and_single_work_lanes(self):
        rec = LaneRecorder({"results": []})
        openalex.title_candidates(rec, "Reading AND Writing")
        self.assertEqual(rec.calls[-1]["lane"], ("openalex",))
        rec = LaneRecorder(work_body())
        openalex.get_work(rec, "10.1093/qje/qjv036")
        # Single lookups pass no lane: the core books the backend's own lane, "openalex".
        self.assertIsNone(rec.calls[-1]["lane"])


# --- Core: multi-lane booking in Http ----------------------------------------
class HttpMultiLaneTests(GateScratch):
    def http(self, handler=None):
        return scholar_search.Http(timeout=5, client=FakeClient(handler or (lambda u, p, h: FakeResp(200, {"ok": 1}))))

    def set_marker(self, lane, value):
        gate = self.root / "gate"
        gate.mkdir(parents=True, exist_ok=True)
        (gate / f"{lane}.gate").write_text(f"{value:.3f}")

    def test_tuple_books_every_gated_lane_in_one_step(self):
        # Two gated lanes: one reserve_lanes() booking, no per-lane RateGate.reserve().
        with mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)), \
                mock.patch.object(scholar_search.RateGate, "reserve", side_effect=AssertionError("per-lane")), \
                mock.patch.object(scholar_search, "reserve_lanes", wraps=scholar_search.reserve_lanes) as spy:
            t0 = time.time()
            self.http().get("openalex", "https://api.openalex.org/works", {}, {},
                            lane=("openalex-boolean", "openalex"))
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(self.gate_files(), ["openalex", "openalex-boolean"])
        self.assertGreaterEqual(self.marker("openalex"), t0 + 0.04 - 0.01)
        self.assertGreaterEqual(self.marker("openalex-boolean"), t0 + 0.22 - 0.01)

    def test_sub_lane_marker_follows_the_actual_departure(self):
        # Phase 4 review W1: with a 1.0 s main-lane backlog the request leaves at
        # t0 + 1.0, so the boolean lane's next slot must sit one boolean interval
        # after that. Sequential booking (boolean first, then main) left it at t0 + 0.22.
        with mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)):
            t0 = time.time()
            self.set_marker("openalex", t0 + 1.0)
            self.http().get("openalex", "https://api.openalex.org/works", {}, {},
                            lane=("openalex-boolean", "openalex"))
        self.assertGreaterEqual(self.marker("openalex-boolean"), t0 + 1.0 + 0.22 - 0.01)
        self.assertGreaterEqual(self.marker("openalex"), t0 + 1.0 + 0.04 - 0.01)

    def test_sub_lane_send_spacing_holds_under_a_main_lane_backlog(self):
        # Fake clock (the consistency review's probe, as a test): every request
        # arrives at T, books in turn, sleeps (advancing the clock) and is sent;
        # the stub client stamps the send time. 28 plain lookups make a 1.12 s
        # main-lane backlog; 3 semantic and 9 boolean-heavy searches follow.
        clock = {"now": 1000.0}

        def fake_sleep(s):
            clock["now"] += s
        sends = []
        http_for = lambda role: scholar_search.Http(timeout=5, client=FakeClient(
            lambda u, p, h: (sends.append((role, clock["now"])), FakeResp(200, {"ok": 1}))[1]))
        roles = [("lookup", None)] * 28 + [("semantic", ("openalex-semantic", "openalex"))] * 3 \
            + [("boolean", ("openalex-boolean", "openalex"))] * 9
        with mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)), \
                mock.patch.object(scholar_search.time, "time", lambda: clock["now"]), \
                mock.patch.object(scholar_search.time, "sleep", fake_sleep):
            for role, lane in roles:
                clock["now"] = 1000.0   # every "process" arrives at the same instant
                http_for(role).get("openalex", "https://api.openalex.org/works", {}, {}, lane=lane)

        def min_gap(times):
            times = sorted(times)
            return min(b - a for a, b in zip(times, times[1:]))
        self.assertEqual(len(sends), 40)
        self.assertGreaterEqual(min_gap([t for _, t in sends]), 0.04 - 0.002, "main lane")
        self.assertGreaterEqual(min_gap([t for r, t in sends if r == "semantic"]), 1.1 - 0.002, "semantic lane")
        self.assertGreaterEqual(min_gap([t for r, t in sends if r == "boolean"]), 0.22 - 0.002, "boolean lane")

    def test_single_name_and_default_lane_unchanged(self):
        with mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)), \
                mock.patch.object(scholar_search, "reserve_lanes", side_effect=AssertionError("multi-lane path")):
            self.http().get("openalex", "https://api.openalex.org/works/W1", {}, {})
            self.http().get("openalex", "https://api.openalex.org/works", {}, {}, lane=("openalex",))
        self.assertEqual(self.gate_files(), ["openalex"])

    def test_ungated_lanes_in_a_tuple_are_skipped(self):
        with mock.patch.object(scholar_search, "GATE_INTERVALS", {"openalex": 0.04}):
            self.http().get("openalex", "https://api.openalex.org/works", {}, {},
                            lane=("not-a-gated-lane", "openalex"))
        self.assertEqual(self.gate_files(), ["openalex"])

    def test_a_lane_named_twice_is_booked_once(self):
        with mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)):
            t0 = time.time()
            self.http().get("openalex", "https://api.openalex.org/works", {}, {}, lane=("openalex", "openalex"))
        self.assertEqual(self.gate_files(), ["openalex"])
        # One booking leaves the marker at about t0 + 0.04; two would leave t0 + 0.08.
        self.assertLess(self.marker("openalex"), t0 + 0.07, "booked once, not twice")

    def test_busy_lane_is_named_and_nothing_is_booked(self):
        # Either lane can be the busy one (gate files are locked in sorted path
        # order, and "openalex-boolean.gate" sorts before "openalex.gate").
        for busy_lane, idle_lane in (("openalex", "openalex-boolean"), ("openalex-boolean", "openalex")):
            with self.subTest(busy_lane=busy_lane), \
                    mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)):
                http = self.http()
                t0 = time.time()
                self.set_marker(busy_lane, t0 + 500)
                self.set_marker(idle_lane, t0 - 5)
                with self.assertRaises(scholar_search.BackendError) as ctx:
                    http.get("openalex", "https://api.openalex.org/works", {}, {},
                             lane=("openalex-boolean", "openalex"))
                self.assertEqual(ctx.exception.kind, "busy")
                self.assertEqual([s["lane"] for s in http.gate_skips], [busy_lane])
                self.assertAlmostEqual(self.marker(busy_lane), t0 + 500, places=2)
                self.assertAlmostEqual(self.marker(idle_lane), t0 - 5, places=2, msg="no marker written")
                self.assertEqual(http.gate_wait_s, 0.0)
                self.assertEqual(http.client.calls, [], "a busy gate sends nothing")

    def test_max_wait_caps_the_one_slot(self):
        for max_wait, busy in ((20, False), (10, True)):
            with self.subTest(max_wait=max_wait), \
                    mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)):
                http = self.http()
                self.set_marker("openalex", time.time() + 15)
                self.set_marker("openalex-boolean", 0)
                try:
                    http.get("openalex", "https://api.openalex.org/works", {}, {},
                             lane=("openalex-boolean", "openalex"), max_wait=max_wait)
                    got_busy = False
                except scholar_search.BackendError as exc:
                    got_busy = exc.kind == "busy"
                self.assertEqual(got_busy, busy)

    def test_successful_request_records_the_actual_sleep(self):
        # Mutant M13: the gate wait of a successful attempt must reach gate_wait_s
        # and the request log, and it must be the sleep actually taken.
        slept = []
        for lane in (("openalex-boolean", "openalex"), None):
            with self.subTest(lane=lane), \
                    mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)), \
                    mock.patch.object(scholar_search.time, "sleep", lambda s: slept.append(s)):
                slept.clear()
                http = self.http()
                self.set_marker("openalex", time.time() + 0.3)
                http.get("openalex", "https://api.openalex.org/works", {}, {}, lane=lane)
                self.assertEqual(len(slept), 1, "one sleep per booking")
                self.assertGreater(slept[0], 0.2)
                self.assertAlmostEqual(http.gate_wait_s, slept[0], places=6)
                self.assertEqual(http.log[-1]["wait_s"], round(slept[0], 2))

    def test_429_under_retry_policy_pauses_every_lane(self):
        # Mutant M5: a 429 under a declared block (penalize_429) pushes EVERY lane.
        http = self.http(lambda u, p, h: FakeResp(429, {"error": "blocked"}))
        with mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)):
            t0 = time.time()
            with self.assertRaises(scholar_search.BackendError) as ctx:
                http.get("openalex", "https://api.openalex.org/works", {}, {},
                         lane=("openalex-boolean", "openalex"), penalize_429=60)
        self.assertEqual(ctx.exception.kind, "busy")
        self.assertEqual(len(http.client.calls), 1, "not retried inside the block")
        self.assertGreaterEqual(self.marker("openalex"), t0 + 60 - 0.01)
        self.assertGreaterEqual(self.marker("openalex-boolean"), t0 + 60 - 0.01)

    def test_429_backoff_pushes_every_lane_back(self):
        answers = iter([FakeResp(429, {"error": "slow down"}, {"retry-after": "9"}), FakeResp(200, {"ok": 1})])
        with mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)):
            t0 = time.time()
            self.http(lambda u, p, h: next(answers)).get("openalex", "https://api.openalex.org/works", {}, {},
                                                         lane=("openalex-boolean", "openalex"))
        # penalize(9) then the retry's own booking (sleep mocked): both markers sit >= 9 s out.
        self.assertGreaterEqual(self.marker("openalex"), t0 + 9 - 0.01)
        self.assertGreaterEqual(self.marker("openalex-boolean"), t0 + 9 - 0.01)


# --- End to end through the CLI ----------------------------------------------
class CliGateTests(GateScratch):
    def run_cli(self, argv):
        fake = FakeClient(lambda u, p, h: FakeResp(200, works_body(), {"x-ratelimit-cost-usd": "0.001"}))
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(scholar_search.httpx, "Client", return_value=fake), \
                mock.patch.object(scholar_search, "GATE_INTERVALS", dict(REAL_INTERVALS)), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                code = scholar_search.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, fake

    def test_keyword_search_with_six_operators_books_the_boolean_lane(self):
        code, fake = self.run_cli(["openalex", ops(6, "OR"), str(self.dest), "--mode", "keyword"])
        self.assertEqual(code, 0)
        self.assertEqual(self.gate_files(), ["openalex", "openalex-boolean"])
        self.assertIn("title_and_abstract.search:", fake.calls[0]["params"]["filter"])

    def test_keyword_search_with_five_operators_books_only_the_main_lane(self):
        code, _ = self.run_cli(["openalex", ops(5, "OR"), str(self.dest), "--mode", "keyword"])
        self.assertEqual(code, 0)
        self.assertEqual(self.gate_files(), ["openalex"])

    def test_semantic_search_books_semantic_and_main(self):
        code, _ = self.run_cli(["openalex", "how does tutoring affect reading", str(self.dest),
                                "--mode", "semantic"])
        self.assertEqual(code, 0)
        self.assertEqual(self.gate_files(), ["openalex", "openalex-semantic"])

    def test_tool_version_bumped(self):
        self.assertEqual(scholar_search.TOOL_VERSION, "1.6.0-daaf")


# --- Registry validation -----------------------------------------------------
class RegistryLaneTests(unittest.TestCase):
    def test_registry_valid_under_both_tiers(self):
        for keyed in (True, False):
            with self.subTest(keyed=keyed), mock.patch.object(openalex, "RATE_LIMIT", openalex.rate_limit(keyed)):
                self.assertEqual(registry.validate_registry(registry.ADAPTERS), [])
                self.assertEqual(registry.validate_adapter(openalex), [])

    def test_boolean_lane_is_owned_by_openalex(self):
        fake = types.SimpleNamespace(
            NAME="fakesrc", LABEL="Fake", KEY_ENV=None, REQUIRED_KEY=False, LICENSE_CLASS="open",
            RATE_LIMIT={"openalex-boolean": 1.0}, RATE_LIMIT_NOTE="n", CAPABILITIES=frozenset({"lookup"}),
            DEFAULT_IN_FIND=False, COST_NOTE="free", ATTRIBUTION="a", key_present=lambda: True,
            auth_headers=lambda: {}, degraded_note=lambda: None, parse_cost=lambda h: None,
            to_record=lambda x: x)
        problems = registry.validate_registry(list(registry.ADAPTERS) + [fake])
        self.assertTrue(any("rate lane(s) ['openalex-boolean'] already used by 'openalex'" in p for p in problems),
                        problems)

    def test_every_lane_the_adapter_books_is_declared(self):
        declared = set(openalex.RATE_LIMIT)
        booked = {openalex.MAIN_LANE, openalex.SEMANTIC_LANE, openalex.BOOLEAN_LANE}
        self.assertEqual(booked, declared)
        self.assertTrue(all(isinstance(v, float) and v > 0 for v in openalex.RATE_LIMIT.values()),
                        "no OpenAlex lane is ungated (None) any more")


if __name__ == "__main__":
    unittest.main()
