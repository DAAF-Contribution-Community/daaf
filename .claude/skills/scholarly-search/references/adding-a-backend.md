# Adding a scholarly source (backend onboarding workflow)

How a user adds a new scholarly API, tool or website as a search source — for
example PubMed/Europe PMC, CORE, SSRN/RePEc, IEEE, or an institutional
discovery API — without touching the core of `scholar_search`. This is a
sub-flow of Framework Development mode (work type "New Scholarly Search
Backend"), triggered by requests such as "add a new scholarly source", "add
PubMed as a backend", or "can the lit search use CORE?". Design source:
Literature Review spec v0.2 §5.5. The registration points are itemized in
`agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` § 8 (SB1–SB17, and
SBM1–SBM7 for changes to an existing backend); this file is the procedure.

## Why adapters

The core (`scripts/scholar_search.py`) owns everything that protects the audit
trail: argparse, the destination and secret guards, artifacts, the MANIFEST,
fusion, version merging, rendering and the shared rate gate. A backend is a
module in `scripts/scholar_backends/` that only builds requests (through the
core's `Http` object), maps native responses to the common record schema,
and parses cost headers. **An adapter never writes files and never handles
provenance**, so a new backend cannot weaken the record. The built-in
backends (openalex, semantic_scholar, eric, crossref, unpaywall, scite,
elicit) are themselves adapters.

## First decision: API or website?

| The source has… | Route |
|-----------------|-------|
| A documented HTTP API (JSON/XML) | Adapter (this workflow) |
| Only a website search page | **Not an adapter.** Retrieve result pages with `web_fetch.sh` under the `web-retrieval` skill, and record the saved search-URL pattern in the review protocol. This keeps scraping out of the scholarly tool, respects site terms, and still leaves provenance. |
| A Python SDK only | Prefer its REST API; DAAF installs no packages at runtime (a Dockerfile change is the user's call) |

## Steps

1. **Intake (orchestrator ↔ user).** What the source covers and why (which
   coverage gap it closes); access model (keyless, free key, paid; per-call
   cost); terms on storage and redistribution; rate limits. Decide the
   license class now: `open`, `cc-by-nc`, or `restricted` (anything that bars
   storing or sharing → `restricted`, which routes artifacts to
   `lit_search/restricted/`).
2. **Docs research.** A search-agent fetches the API docs **and** the terms
   with `web_fetch.sh` into the Framework Development workspace, so every
   claim in the new reference file traces to a stored page.
3. **Scaffold from `_BACKEND_TEMPLATE.md`:**
   - `scripts/scholar_backends/<name>.py` (adapter),
   - `.claude/skills/scholarly-search/references/<name>.md` (reference: Auth ·
     Endpoints used · Cost/limits · Measured behavior with dates ·
     Storage/ToS · Exit mapping · Minimal smoke test),
   - fixtures + test cases in `tests/python/test_scholar_search.py`.
   Register the module in `scripts/scholar_backends/__init__.py` (add it to
   the `ADAPTERS` tuple; `BACKENDS` is built from it). The registry validates
   every adapter **at import**: a contract violation — a missing attribute, an
   unknown capability or license class, `search` without `FIND_LEGS`, or a
   `NAME`, `KEY_ENV`, rate lane or `FIND_LEGS` name already used by another
   adapter — stops every `scholar_search` command with exit 1 and names each
   problem on stderr, before any request or artifact. If the backend declares
   `search`, it becomes selectable with `find --backends` and its `NAME` and
   `FIND_LEGS` become `find --skip` choices automatically; `retraction` joins
   `retractions` automatically (and becomes a `retractions --skip` choice; a
   `restricted` backend's `retraction_check` must return facts only, status
   and notice DOIs/dates, because the `retractions` digest stays in the open
   folder while its raw response goes to `restricted/`); `oa_locate` needs a leg added to `cmd_oa` in
   the core (the only capability whose fallback order is a core decision).
   If the adapter's records key their native ID under something other than
   `NAME` in the `ids` map, declare `ID_KEY` so rendered ID lines get its
   label.
4. **Live smoke** with the cheapest possible call, through the CLI, into a
   scratch project, with `DAAF_FETCH_CONTEXT` set. Capture the real response
   as the test fixture (trim it; add `_fixture_source`). Fixtures must be
   live-wire evidence, not doc-derived shapes — doc-only fixtures gave false
   coverage in the provider-shim precedent (FRAMEWORK_INTEGRATION_CHECKLIST
   item P8). If a live call is impossible, label the fixture DOC-DERIVED and
   log it as an open issue. **Exception, `restricted` sources:** their terms
   bar sharing content and the repository is published, so the committed
   fixture is **synthetic**: the live response's exact shape (keys, types,
   nesting, status vocabularies) with invented values, and a
   `_fixture_source` reading "SYNTHETIC; shape from live response <MANIFEST
   row, date>; values invented". The live response itself stays in the
   smoke run's `restricted/` folder (Scite and Elicit, 2026-10-12).
5. **Register:**
   - keyed source → a commented `#<NAME>_API_KEY=` line with a get-key URL
     and cost note in `scripts/host/environment_settings_example.txt` §[5],
     then run `bats /daaf/tests/bash/environment_settings_example.bats`;
   - a row in the API-key table of
     `user_reference/01_installation_and_quickstart.md`;
   - a row in this skill's Backends table and decision tree (SKILL.md), plus
     the licensing matrix (`licensing.md`) and a dated entry in
     `api-notes.md`.
6. **Review** with the standard Framework Development review pass; run the
   unit tests and quote the result.

## What an adapter may raise

Adapters signal failure with exactly one type, `BackendError(backend, kind,
message, http_status=None)` from `scholar_backends/_common.py`. Most kinds
come from the core's `Http` object — `Http.get()` and, since tool 1.2.0,
`Http.post()`, the adapter's only network paths; an adapter raises its own
only for conditions it detects in a successful response or before a request.

**POST (tool 1.2.0).** `http.post(NAME, url, json_body=None, params=None,
headers=None, lane=None, ok_statuses=(200,), idempotent=False,
max_attempts=None, max_wait=GATE_DEFAULT_MAX_WAIT, penalize_429=None)`
returns `(http_status, parsed)` (`parsed` is any JSON value, or None for an
empty body), so an adapter can tell `202 Accepted` from `200`. `lane`
overrides the rate lane (default: the backend name); `max_attempts` applies
only to an idempotent POST; `max_wait` caps the rate-gate queue wait. It
applies get()'s guards, with the secret guard covering the body too, logs the
method and scrubbed body, and refuses a cross-origin POST redirect. **A
POST makes exactly one attempt** unless the call is declared
`idempotent=True` (a free read sent as POST, e.g. Scite's batch tallies), which
restores get()'s 429/5xx retry loop; never declare a create idempotent: a
timeout or 5xx does not prove no work started. A call that may draw quota
stays non-idempotent too (Elicit search, tool 1.4.0). **A non-idempotent
POST follows no redirect** (tool 1.5.0; 1.4.0 refused only 307/308): a
307/308 would re-send it, and a 301/302/303 would turn it into a GET whose
answer says nothing about whether the POST started the work. Every 3xx fails
`network`, logged with `method: "POST"`, the real status and the redirect
chain, as does any refused redirect and a chain longer than 5 hops, so the
row's `requests` are never empty after a request left. A redirect an
idempotent request follows is logged with each hop's status and the final
request's method (`redirect_statuses`, `final_method`), so a status that
answered a redirected GET is never read as the POST's. **429 as a timed block:** an
adapter whose 429 means "blocked for N seconds" declares `RETRY_POLICY =
{"penalize_429_s": N}` (validated at import), or a caller passes
`penalize_429=N`: the 429 is not retried, the lane is paused N s for every
process, and the call fails `busy` (exit 12). Without it, GETs keep the
default backoff.

**Paid or asynchronous work (tool 1.3.x, Elicit).** A source that starts
paid work and is polled (a report, a review job) needs **core** support, not
just an adapter. The adapter supplies only the request builders (create once
with `idempotent=False`, poll, resume) and the error-shape reader. The core
owns the rest, in `scholar_search.py` § ELICIT, which is the pattern to copy:
- a spend flag refused before any request (exit 2, MANIFEST row);
- a **`creating` checkpoint row** written BEFORE the create is sent (tool
  1.4.0), so a process killed during the create still leaves a trace;
- an **uncertain-by-default create** (tool 1.4.0): the outcome is
  "uncertain" unless the answer proves nothing started (a refusal before
  sending, or a 429 or another 4xx that is the **direct** answer to the POST:
  one request, no redirect, tool 1.5.0); an accepted answer without a valid
  job ID, a 5xx, a timeout, any refused 3xx, an oversize or non-JSON body are
  all uncertain;
- a **checkpoint row** written through `ctx["checkpoint"]` before the first
  poll, so the job ID survives a killed process;
- a poll loop driven by the module-level `poll_clock`/`poll_sleep` (testable
  without real sleeps), with a minimum interval plus jitter and a wall-clock
  cap, that keeps polling any non-terminal status (including undocumented
  ones) and rides out up to 2 consecutive network/timeout errors;
- exit 13 ("accepted, not finished") with a re-attach command;
- a re-attach subcommand that never creates;
- a **duplicate guard** that reads DEST_DIR's MANIFEST and refuses a second
  create while the same request has unfinished work (an orphaned checkpoint,
  exit 13, a poll failure, an uncertain create, or an orphaned `creating`
  row), with a documented **close path** for uncertain creates that does not
  bypass the guard (tool 1.5.0: a re-attach that names the question or the
  recovery ID records `elicit_resolved_creates`; an explicit, spend-confirmed
  new create records `elicit_superseded_creates`; `elicit.md` § "Closing an
  uncertain create").

The S2 live trial needed all of it: the host crashed mid-poll, and the
checkpoint plus `elicit-resume` recovered the paid report without a second
create (`elicit.md` § Crash recovery). Do not generalize this machinery until
a second async backend exists; reuse Elicit's shape when one does.

| `kind` | Raised by | Exit when the command fails | Inside `find` / `oa` / `retractions` |
|--------|-----------|-----------------------------|--------------------------------------|
| `not-configured` | `require_configured()` (core) or the adapter, when a required key/contact is missing | 10 | The leg is recorded as failed/skipped; other backends continue |
| `refused` | `Http.get()` / `Http.post()` secret guard (a secret value in the URL/params, or a POST body) | 2 | **Aborts the whole command** — never caught per leg |
| `network` | `Http.get()` / `Http.post()` (connection error, invalid URL, > 5 redirects, a cross-origin POST redirect, any 3xx on a non-idempotent POST) | 4 | Leg recorded as failed |
| `timeout` | `Http.get()` / `Http.post()` | 6 | Leg recorded as failed |
| `oversize` | `Http.get()` / `Http.post()` (body > 25 MB) | 7 | Leg recorded as failed |
| `api` | `Http.get()` / `Http.post()` (a status outside the success set after retries, non-JSON body); the adapter, for a malformed 200 (e.g. Crossref "no message object") | 11 | Leg recorded as failed |
| `not-found` | `Http.get()` / `Http.post()` on HTTP 404; the adapter, for an empty match (e.g. OpenAlex title lookup with no candidates) | 11 (for `work`/`verify` a recorded NOT FOUND result) | `retractions` and the Unpaywall `oa` leg record "not found" (an answer); a `find` leg and the other `oa` legs record it as failed |
| `busy` | `Http.get()` / `Http.post()` when the shared rate-gate queue exceeds the command's max wait, or on a 429 under a `RETRY_POLICY` / `penalize_429` (lane paused) | 12 | Leg recorded as failed |

An unknown `kind` maps to 11. **Any other exception** (a `KeyError` in a
mapper, a parse error) is a bug: the core's catch-all still writes the raw
request log and a MANIFEST row, exits 11 with `internal error: <TypeName>`,
and does not echo the exception text (it may quote upstream content). It
is not isolated per leg, so one mapper bug fails a whole `find`. Map
defensively (`.get()` with defaults) rather than raising. Adapters never
catch `refused`.

## Acceptance checklist

- [ ] The registry imports cleanly (any contract violation exits 1 at import),
      and `registry.validate_adapter(<module>)` returns `[]` (a test asserts
      this for every registered backend; negative cases are tested too)
- [ ] `NAME`, `KEY_ENV` (if any), every `RATE_LIMIT` lane and every
      `FIND_LEGS` name are unique across adapters
- [ ] If `search` is declared: `FIND_LEGS` names every leg `find_legs()`
      returns, and `find --help` lists them under `--skip`
- [ ] Keys only in headers; `backends` shows the key by NAME only
- [ ] `RATE_LIMIT` lanes set from the documented limit (with margin)
- [ ] Mapper test passes against a live-wire fixture (for a `restricted`
      source, the synthetic fixture with the live shape and invented values;
      Step 4)
- [ ] `license_class` set; restricted sources write to `restricted/`
- [ ] Exit mapping documented (which statuses mean bad key, quota, not found;
      see "What an adapter may raise" above)
- [ ] Attribution line (`ATTRIBUTION`) set from the vendor's terms
- [ ] Reference file, SKILL.md tables, licensing matrix, api-notes, env
      template and user_reference updated
