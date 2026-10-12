# Elicit

Elicit's API v2 adds two things no other backend has. **Paper search** returns
screening fields: study-design tags (RCT, meta-analysis, systematic review,
review, longitudinal), the journal's SJR quartile, and a best full-text link.
**Paid research reports** are asynchronous, AI-generated syntheses over up to
1,000 searched and 80 extracted papers. Both are **restricted**, and Elicit is
**never part of default `find` fusion** (user decision, Checkpoint 1,
2026-10-11). Systematic reviews and agent sessions are deferred to v1.1. Adapter:
`scripts/scholar_backends/elicit.py`; the poll loop, checkpoints and every
artifact live in the core (`scripts/scholar_search.py` § ELICIT). Docs: the
v2 reference https://docs.elicit.com/ and the OpenAPI spec
https://docs.elicit.com/openapi.json (the only source for the report bounds),
fetched 2026-10-11 into `web_fetches/s2_research/` of the S1 workspace
`research/2026-10-02_FrameworkDev_ScholarlySearch/`, with the research digest
in `preliminary_notes/07_research_s2_elicit_scite.md`. API Terms: "Last
updated: July 15, 2026".

## Auth

`ELICIT_API_KEY` is **required** by every `elicit-*` command. Without it the
command exits 10 and sends no request. It is sent as `Authorization: Bearer
elk_live_…`. "API access requires a Pro plan or above." Keys are generated
at https://elicit.com/developer (changelog: "generate a key at
elicit.com/developer"). `backends` shows the key by name only. There is no
keyless mode.

**Personal data.** "You are expressly prohibited from submitting Personal Data
to the API under any circumstances. Personal Data includes names, …" (Terms
§2), and "Elicit does not screen for Personal Data". Keep people's names out
of every query and question; an author name is personal data too. The tool
cannot detect it. It prints the reminder in `elicit-search` /
`elicit-report` help and stdout.

## Endpoints used

| Use | Request | Command |
|-----|---------|---------|
| Usage against the plan (free; starts no work) | `GET /api/v2/usage` | `elicit-usage DEST` |
| Paper search (synchronous, no pagination) | `POST /api/v2/search/papers` `{query, maxResults, searchMode, corpus, filters?}` | `elicit-search "<q>" DEST [--max-results 10] [--mode semantic\|keyword] [--corpus elicit\|pubmed] [--years 2015-2025] [--type-tags RCT,Meta-Analysis]` |
| Create a report (**paid**, exactly once) | `POST /api/v2/sessions/reports` `{researchQuestion, maxSearchPapers, maxExtractPapers, isPublic: false}` → **202** (the only success openapi.json declares; 201 is accepted too) | `elicit-report "<question>" DEST --confirm-spend --max-search-papers N --max-extract-papers M` |
| Poll a report | `GET /api/v2/sessions/reports/{id}` | inside `elicit-report` / `elicit-resume` |
| Final report with its body | `GET /api/v2/sessions/reports/{id}?include=reportBody` | same, once `completed` |
| Resume a quota-paused session (**restarts paid work**) | `POST /api/v2/sessions/{id}/resume` | `elicit-resume <id> DEST --confirm-spend` |
| Opt-in search leg | the search call above, with the question and `--years` | `find "<q>" DEST --backends …,elicit` (the whole `find` becomes restricted) |

Base URL `https://elicit.com/api/v2`. The default `--timeout` is 60 s for
search/usage and 90 s for report commands ("creation can take tens of
seconds").

**Search details.** `searchMode` is `semantic` (natural language, the default)
or `keyword` (Lucene syntax on the Elicit corpus, PubMed syntax on
`--corpus pubmed`). "Filters and searchMode: "keyword" are mutually
exclusive … Mixing them returns a 400." The CLI refuses `--mode keyword` with
`--years`/`--type-tags` as a usage error (exit 1, no request). `--type-tags`
accepts Review, Meta-Analysis, Systematic Review, RCT and Longitudinal, matched
without regard to case. `maxResults` defaults to 10, and the Pro plan caps a
request at 300 (above it, 400). Mapped fields: `elicitId`, `title`, `authors`,
`year`, `abstract`, `doi`, `pmid`, `venue`, `citedByCount`, `urls`,
`studyTypeTags`, `journalQuartile`, `fullTextUrl`. Response-level `warnings`
are recorded in the row (`elicit_warnings`). A `null` abstract means Elicit
cannot redistribute the publisher's abstract (docs). The digest labels it
"withheld", and the row counts it (`elicit_abstracts_withheld`), so "no
abstract" is never read as "the paper has none". `fullTextUrl` has no license
attached, so it is shown as "Elicit's full-text link (license unknown)" and
never becomes an OA location. Run `oa` for a legal copy.

**Report details.** Bounds from openapi.json: `maxSearchPapers` 1–1000
(Elicit's default 50) and `maxExtractPapers` 1–80 (default 10). The CLI
requires both flags explicitly, so a paid call never runs on a default
nobody chose. Out-of-range values are a usage error with no request.
`researchQuestion` is 1–2000 characters, and the CLI caps any query at 1000.
`isPublic: false` is always sent. Statuses are `processing`,
`pausedForInsufficientQuota`, `completed`, `failed` and `unknown`. Those last
four end the loop ("Stop normal polling on completed, failed, or unknown"; a
pause "does not automatically resume"). Since tool 1.4.0 **any other status**
(`processing`, or one the docs do not list, such as `queued`) keeps the loop
polling until the cap, then exits 13 with the re-attach command, so an
unexpected status never closes a live session.

**Search is sent once.** `elicit-search` makes one attempt (no retry on a
5xx or a timeout, and since tool 1.5.0 no redirect of any kind is followed).
`find --backends` names are de-duplicated (1.5.0), so `--backends
elicit,elicit` sends one search, not two. A search starts no session, but it may
draw quota: the docs declare 402 for it, and usage moved 0 → 3% after one
1-result search plus one small report, with lagged accounting (§ Cost and
limits). A retried search could be charged twice.

## How `elicit-report` runs (the order is the safety)

1. **Guards first, no request, in this order:** bounds, keyword + filters,
   unknown type tag → exit 1 (usage, no row). Invalid DEST_DIR → exit 2 (no
   row); a secret value in the question → exit 2 with a row. No
   `--confirm-spend` → exit 2 with a row (the spend guard). **Unfinished or
   uncertain work for the same question in this DEST_DIR** → exit 2 with a
   row and the `elicit-resume` command (the duplicate guard, below;
   `--new-session` overrides and records what it supersedes; see "Closing an
   uncertain create"). Only then: missing `ELICIT_API_KEY` → exit 10.
   So a call without the key but also without `--confirm-spend` exits 2, not 10.
2. **`creating` checkpoint (tool 1.4.0):** before the create is sent, a
   MANIFEST row with `phase: "creating"`, the question, the parameters,
   `exit_code: null` and `elicit_create_outcome: "uncertain"` is written
   (plus `restricted/<base>_creating.json`, an empty request log). If the
   process is killed during the create, this row is the only trace.
3. **Create exactly once** (`Http.post`, `idempotent=False`): never retried,
   and **no redirect is followed** (tool 1.5.0; 1.4.0 refused only 307/308).
   A 307/308 would re-send the create, and a 301/302/303 would turn it into
   a GET whose answer (a 404, 401 or 429) says nothing about whether the POST
   started the work. Every 3xx is refused as a network error (exit 4), and the
   row's `requests` entry records `method: "POST"`, the real 3xx status and
   the `redirect_chain`. If the `Location` names a session
   (`/sessions/reports/<uuid>`, `/sessions/<uuid>` or `/review/<uuid>`), that
   UUID is recorded as `elicit_recovery_session_id` and the `elicit-resume`
   command is printed. Intended trade: a 303 pointing at a finished report is
   now an uncertain create with a recovery ID (re-attach to read it), not a
   followed redirect. "A timeout does not prove that work was not started",
   so since 1.4.0 the outcome is **uncertain unless the answer proves nothing
   started**: only a refusal before sending (including a full rate-gate
   queue), or a 429 (busy) or another HTTP 4xx that is the **direct** answer
   to the POST (one request, no redirect: 400, 401, 402, 403, 404, 408, 409…),
   count as `elicit_create_outcome: "not started"`. A 408 or 409 also counts,
   by HTTP semantics (the server did not accept the request); openapi.json
   declares neither for this endpoint, so that reading is an inference.
   Everything else is `"uncertain"`: a timeout, a network error or refused
   redirect, a 5xx, an oversize or non-JSON answer, and an accepted answer
   (202/201) without a valid UUID `sessionId`. A 2xx outside 202/201 that
   still names a valid `sessionId`, and an error body's `error.sessionId`, are
   recorded as `elicit_recovery_session_id` with their re-attach command. An
   uncertain create says the report MAY exist, and the duplicate guard refuses
   the same question in this DEST_DIR until the row is **closed** (see
   "Closing an uncertain create").
4. **Persist before polling:** the 202/201 body's `sessionId` goes into a
   **checkpoint MANIFEST row** (`phase: "created"`, `exit_code: null`,
   `elicit_create_outcome: "accepted"`), plus
   `restricted/<base>_created.json` (the raw log so far). Only then are the
   sessionId and the re-attach command printed to stdout.
5. **Poll** every ≥ 30 s plus up to 5 s of jitter (`--poll-interval`, 30–300).
   Each poll books a slot on the shared `elicit` lane, so concurrent agents
   behind one IP stay under 100/min together. The wall-clock cap is
   `--max-wait-min` (default 20, 0–120, counted from the command's start).
   Up to **2 consecutive network/timeout errors** on a poll are ridden out
   within the cap (each in the raw log, in `elicit_statuses_seen` and counted
   in `elicit_poll_errors`); the third exits 4/6 with the re-attach command.
6. **Finish:** `completed` → fetch `?include=reportBody` and save the body
   verbatim as `restricted/<base>_report.md`. The raw `.json` holds the full
   response. Record the export links' presence and expiry (`elicit_exports`;
   the links themselves stay in `restricted/`). `failed` / `unknown` → exit 11,
   a recorded result. Paused, still processing, or any undocumented status at
   the cap → **exit 13** with the re-attach command. The final row has
   `phase: "final"`.

Any other poll failure (5xx after 3 attempts, 429, a third network error in
a row) re-raises with the sessionId and the re-attach command. The final row
carries the sessionId on failure too.

## Crash recovery (orphaned checkpoint)

**What happened (2026-10-11, the S2 live trial).** `elicit-report` created
the trial session at 18:35:12Z and wrote the `created` checkpoint row.
The host then crashed while the process was polling (the last booking on the
`elicit` gate was 18:37:49Z, inferred from the gate file's mtime), and no final
row was ever written. The checkpoint row was the only record, as designed.
The statuses seen by the lost polls were not recoverable, because they were
held in memory until the final row. Re-attaching 20 minutes later found the
report `completed`.

**Procedure.**
1. **Never run `elicit-report` again for that question.** Since tool 1.3.1
   the CLI refuses it anyway: when DEST_DIR's MANIFEST holds an
   **unfinished** session for the same question, it exits 2 with no request.
   Questions are compared ignoring case, spacing and (since 1.4.0)
   punctuation, so "…achievement?" equals "…achievement" and "K-12" equals
   "K 12". The unfinished cases are an orphaned checkpoint, an exit-13 row, a
   poll failure, an `uncertain` create, or (since 1.4.0) a `creating` row
   with no final row and no sessionId from its own call. The row lists
   `elicit_open_sessions` / `elicit_uncertain_creates`, and the note gives
   the re-attach command and the close path. Pass `--new-session` (it still
   needs `--confirm-spend`) only after checking the session and deciding a
   second paid report is wanted. **Limits:** the guard
   is a crash guard, not a spend cap. A reworded question ("on the
   achievement") is a different question, and it reads only this DEST_DIR's
   MANIFEST, so the same question asked into another DEST_DIR is not seen.
2. **Find the sessionId** in the checkpoint row (`elicit_session_id`,
   `resume_command`): `grep '"phase": "created"' DEST/MANIFEST.jsonl`.
3. **Re-attach:** `bash /daaf/scripts/scholar_search.sh elicit-resume
   <sessionId> DEST` (set `DAAF_FETCH_CONTEXT`). This makes one status read,
   then polls if still processing, then fetches the body once completed. With
   no `--confirm-spend` it can send **no POST at all**. The final row records
   `elicit_session_history` (the earlier rows for this sessionId) and
   `elicit_orphaned_checkpoints` (the checkpoint with no final row from its own
   call), and stdout says "re-attached an orphaned checkpoint". The checkpoint
   row stays as the historical record: never edit the MANIFEST.
4. **If paused** (`pausedForInsufficientQuota`, exit 13): run `elicit-usage`
   and get the user's decision. Only then run `elicit-resume … --confirm-spend`,
   because resuming restarts paid work.
5. **If the create itself timed out or got an odd answer** (no sessionId
   ever arrived): look for the report in the Elicit web app and re-attach by
   its ID with `--for-question` (next section). **If the process died during
   the create** (a `creating` row with no final row): same, since no sessionId
   is known. `elicit-resume` lists such rows (`elicit_orphaned_creates`: time,
   question, artifact) so they can be matched against the web app, and prints
   "orphaned create (no sessionId known)".

### Closing an uncertain create (tool 1.5.0; tightened in 1.5.1)

Before 1.5.0 an uncertain create (or an orphaned `creating` row) blocked its
question in that DEST_DIR for good, and only `--new-session`, which skips the
whole guard, got past it. Two documented ways now close such a row without
bypassing the guard; neither edits the MANIFEST (a later row names the
closed row's `raw_artifact`, unique per call):

- **The report exists** (found in the Elicit web app or `GET /sessions`):
  `bash /daaf/scripts/scholar_search.sh elicit-resume <sessionId> DEST
  --for-question "<the question>"`. After a successful status read (the
  session exists and is this key's), the row closes every open uncertain
  create for that question (same words, case and punctuation ignored) and
  lists them in `elicit_resolved_creates` (timestamp, raw artifact, question,
  `matched_by`). The API does not return a report's question, so
  `--for-question` is your statement that this session is that report; the
  session then counts as created for that question. A create whose
  `elicit_recovery_session_id` is this session is closed by a plain
  `elicit-resume <that ID>`, no flag needed (`matched_by: "recovery
  sessionId"`). A failed status read (404, 401, a network error) closes
  nothing. **Since 1.5.1:** a status read of `unknown` ("Elicit does not
  track this report") or with no status closes nothing either, and
  `--for-question` then ties nothing (the row says why in
  `elicit_close_skipped`; stdout prints "nothing closed"). And a session
  this DEST_DIR's MANIFEST already ties to **another** question (it was
  created here for it, an earlier re-attach named it with `--for-question`,
  or it is that question's recovery sessionId) cannot be claimed for this
  one: `--for-question` naming a different question is refused (exit 2, no
  request, a row with `elicit_for_question_conflict` naming both questions),
  because one session is one report for one question. So whenever a
  re-attach does close a create by `--for-question`, the session really
  counts for that question from then on.
- **No report exists** (you checked and decided to pay again):
  `elicit-report … --confirm-spend --new-session`. Its rows record the open
  uncertain creates it overrides in `elicit_superseded_creates`, and stdout
  prints "--new-session superseded N", so later plain runs are not blocked by
  them. `--new-session` without `--confirm-spend` is still refused (exit 2).
  **Since 1.5.1** the supersession takes effect only if this call's own
  create may have started a report (final row `elicit_create_outcome`
  `uncertain` or `accepted`, or a checkpoint row whose call left no final
  row because the process died during the create). A `--new-session` whose
  create started nothing (refused before sending, no key, a busy lane, or a
  402/4xx/429 as the direct answer) supersedes nothing: the row records
  `elicit_supersession_effective: false`, stdout prints "--new-session
  started no report, so it superseded nothing", and the old uncertain create
  keeps blocking.

**What stays blocking:** a session with a known sessionId that has not
finished (an orphaned `created` checkpoint, exit 13, a poll failure,
including a session re-attached with `--for-question` that is still
processing). Neither path closes it: re-attach until it reaches `completed`,
`failed` or `unknown`. `--new-session` creates past it but lists it in
`elicit_open_sessions`, and it keeps blocking plain runs.

A checkpoint is paired with its final row by artifact base
(`<base>_created.json` ↔ `<base>.json`, unique per call), not by timestamp,
because two calls can start in the same second. A session counts as
**closed** once a final row reached `completed`, `failed` or `unknown`. A
torn last MANIFEST line (a crash mid-append) is skipped.

## Cost and limits

**Cost is undocumented per call.** Usage draws on the plan's pool. `GET
/usage` returns `hasUsageRemaining`, `percentUsed`, `periodStart`,
`periodEnd` and `extraUsage{limitUsdCents, spentUsdCents}|null`. Bracket any
paid call with `elicit-usage` before and after, but **the accounting lags**:
on 2026-10-11 `percentUsed` read 0 before and after a 1-result search and a
10/5 report (last read 18:55:41Z, after the re-attach), and it read **3** at
2026-10-12T15:44:52Z. So those two calls together drew about 3% of the
monthly allowance (assuming no other use of the account, which cannot be
verified; the per-call split is unknown), and a bracket read right after a
call can show nothing yet. Re-read the next day before concluding. Pricing
pages list Pro at $39 ("5x usage") or $49 ("Standard usage"), both "billed
annually" (A/B variants, an inference).

**Rate limit.** "All endpoints share a burst limit of 100 requests per minute
per IP address, including polling requests. Exceeding it returns 429 and
blocks that IP for 5 minutes." The gate spaces Elicit calls 0.75 s apart (80/min) on one
lane, `elicit`, shared by every process. A 429 is **never retried**
(`RETRY_POLICY = {"penalize_429_s": 300}`): the lane is paused 300 s for
every process and the call fails `busy` (exit 12). The edge 429 body is flat
(`{"error": "Rate limit exceeded", "message": …}`), not the usual `{"error":
{code, message}}` envelope; the adapter reads both shapes. No Elicit response
carried rate-limit headers (2026-10-11: `rate_headers: null` on all 7).

**Quota.** "402 insufficient_quota when starting work". Search is
quota-gated too (`/search/papers` declares 402). A running report can pause
as `pausedForInsufficientQuota`, which never resumes by itself.

## Measured behavior

Full table: `api-notes.md` § "Measured behavior: Elicit (2026-10-11)".
Evidence: `research/2026-10-02_FrameworkDev_ScholarlySearch/smoke_s2/elicit/`
(MANIFEST rows 1–6, raw responses under `restricted/`).
- **Usage** (2026-10-11, rows 1, 3, 6): 200, `percentUsed` integer **0**
  each time (before the search, after it, and after the report);
  `hasUsageRemaining: true`; period 2026-10-09T11:00Z → 2026-11-09T11:00Z;
  `extraUsage: null`. **Lag:** the same counter read **3** at
  2026-10-12T15:44:52Z (orchestrator `elicit-usage` run), so the calls were
  charged after a delay (see Cost and limits).
- **Search** (row 2, `--max-results 1`): 200 with 1 paper carrying every
  documented field (`studyTypeTags`, `journalQuartile`, `fullTextUrl`,
  `pmid` null), `warnings: []`, no usage fields.
- **Create** (row 4): **202** in 0.4 s, `{type, sessionId, status:
  "processing", url: "https://elicit.com/review/{id}", isPublic: false,
  links.self}`; no `executionStage` in the 202.
- **Completed report** (row 5, re-attach): the plain read already returns
  `result.{title, summary}`, the five export URLs and `exportsStatus:
  "ready"`; `?include=reportBody` adds `result.reportBody` (28,663 bytes of
  markdown) and `result.abstract`. **No paper counts** in the JSON. The
  body's included-studies table lists **5 studies** (= `maxExtractPapers`
  5), each marked as full text retrieved. Nothing shows how many of the 10
  searched papers were screened out.
- **Report body format**: 106 inline evidence-anchor tokens
  `{<64-hex>_<n>}`, one hex prefix per report, plus bracketed author-year
  citations (`[Surname et al., YYYY]`) and no reference-list section.
  References come through the `bibUrl`/`risUrl` exports. The v2 docs describe
  resolving inline tokens only for agent-session messages, so no resolver for
  report anchors is documented (inference). Treat the anchors as opaque, and
  `verify` every cited study yourself.
- **Export links**: presigned S3 URLs on two buckets
  (`elicit-report-pdfs-prod` for pdf/docx, `elicit-public-api-exports-prod`
  for txt/bib/ris), `X-Amz-Expires=604800` (7 days) and `X-Amz-Date` = the
  moment of the fetch. Every fetch mints fresh links, so `elicit-resume` on a
  completed session refreshes them. They carry a temporary credential
  (`X-Amz-Security-Token`): treat them as secrets. They stay in `restricted/`
  and never reach the MANIFEST (checked: 0 occurrences).
- **Not yet seen live**: 402, 409 (usage or resume), 429, `failed`,
  `unknown`, a pause. These paths are covered by mocked unit tests only.

### Vendor-sample pitfalls (github.com/elicit/api-examples, commit `89e24c1b`, MIT)

- The sample skill says on 429 "wait 60 seconds before retrying". That is
  **wrong** for this API: a 429 blocks the IP for 5 minutes, and retrying
  inside the block wastes calls. The tool pauses 300 s and never retries.
- The installer is advertised as `curl -sL …/install.sh | bash`. DAAF
  forbids piping downloads to a shell, and installs nothing at runtime.
  **Never install it.**
- `python/3_create_report.py` polls `while True: time.sleep(30)` with no
  timeout and no error handling, and loops forever on `unknown`. The CLI
  sample prints the sessionId only with `--no-wait`, so a poll error loses
  it. Neither persists the ID before polling or warns that a create is not
  idempotent. Adopt their human-confirmation guidance ("Do not create
  reports speculatively"), not their mechanics.

## Storage and ToS

`LICENSE_CLASS = "restricted"` (spec D-4; user decision 2026-10-11): every
`elicit-*` artifact is in `lit_search/restricted/`, and the MANIFEST row in
`lit_search/` records counts, statuses, the sessionId and the export links'
presence and expiry. It never records content or a link. Quoted from
https://elicit.com/operations/api-terms ("Last updated: July 15, 2026",
fetched 2026-10-11):
- **§2** "You are expressly prohibited from submitting Personal Data to the
  API under any circumstances. Personal Data includes names, email
  addresses, …"
- **§3.2(b)** you will not "use the API, its outputs, or any data obtained
  through the API to train, fine-tune, evaluate, or improve any machine
  learning model or AI system"; **§3.2(c)** nor "systematically query the
  API to download, replicate, or reconstruct the Elicit paper corpus or any
  substantial portion of it"; **§3.2(j)** nor "exceed or circumvent rate
  limits".
- **§3.3** for "an AI agent or automated pipeline": "implement safeguards to
  prevent runaway loops or excessive API calls". The spend flag, the duplicate
  guard, the never-retried create and the poll cap are those safeguards.
- **§3.4** "You are responsible for complying with all applicable laws and
  regulations governing AI-generated content disclosure, labeling, and
  transparency … including any requirements to disclose that content was
  generated using artificial intelligence." Every report digest opens with an
  **AI-generated content** banner. Carry that disclosure into any
  deliverable that uses a report or summary.
- **§3.5** "You may store and reuse API Outputs, including search results,
  reports, and SLR outputs, for your permitted purposes under this Agreement.
  You may not aggregate search results to build or contribute to a
  standalone search index, database, or corpus." So never merge Elicit
  results into a reusable corpus, and use `find --backends …,elicit` per
  question, not for bulk harvesting.
- **§4.2** "The API may produce different API Outputs for identical inputs.
  Elicit does not guarantee consistency or reproducibility." The archived raw
  response is the only record, and re-running gives a different report.
- **§12.3** "Upon termination: … (c) you will delete any cached API Outputs
  within 30 days." This is why the class is restricted: if API access ends,
  every `restricted/` Elicit artifact must be deleted within 30 days.

`ATTRIBUTION` (printed by `backends`) carries the AI-generation disclosure,
the non-determinism, the personal-data rule and the restricted storage.
- **Test fixtures** `tests/python/fixtures/scholar_search/elicit_*.json` are
  **synthetic** (tool 1.4.0, 2026-10-12; user decision: the repository will
  be published). They keep the exact shapes of the trial's responses (usage,
  one search result, the 202 body, the completed report: keys, types,
  nesting, status vocabulary, the `{<64-hex>_<n>}` anchor form) with invented
  values: a fake sessionId, invented titles, authors, abstract, summary and
  report text, DOIs under `10.5555/`, and non-resolving `example.invalid`
  export URLs with no signature or token. Each `_fixture_source` names the
  MANIFEST row its shape came from. No Elicit output is in the repository.
- **Audited scripts** never call any `elicit-*` command (nor `find --backends
  …,elicit`): their stdout carries Elicit output (paper titles, report
  titles, statuses), a script's stdout is appended to the script file by
  `run_with_capture.sh`, and a report is a paid call that needs the user's
  approval for that call (see SKILL.md, "Who may run this").

## Exit mapping

| Situation | Result |
|-----------|--------|
| `ELICIT_API_KEY` missing (any `elicit-*`) | exit 10, no request |
| `elicit-report` without `--confirm-spend` | exit 2, MANIFEST row, no request (checked before the key, so it wins over exit 10) |
| `elicit-report` with unfinished or uncertain work for the same question in DEST_DIR | exit 2, row with `elicit_open_sessions` / `elicit_uncertain_creates`, no request; `--new-session` (with `--confirm-spend`) overrides and records `elicit_superseded_creates` (effective only if its own create may have started, 1.5.1); `elicit-resume <id> DEST --for-question "<q>"` closes uncertain creates (`elicit_resolved_creates`) unless the status read is `unknown` (`elicit_close_skipped`, 1.5.1) |
| `elicit-resume --for-question "<q>"` on a session DEST_DIR's MANIFEST ties to another question | exit 2, row with `elicit_for_question_conflict`, no request (1.5.1) |
| `elicit-resume --for-question` empty after removing punctuation, or over 1,000 characters | exit 1 (usage), no row |
| Bad bounds, keyword + filters, unknown type tag, non-UUID sessionId | exit 1 (usage), no row |
| 400 / 401 / 403 | exit 11, with Elicit's meaning in the note (invalid request / bad key / plan); on create, as the direct answer, `not started` |
| 402 `insufficient_quota` | exit 11, "insufficient quota" (`elicit_error_code`); on create, as the direct answer, the work did not start |
| 408 / 409 on create (not declared in openapi.json) | exit 11; counted `not started` like any direct 4xx (HTTP semantics; an inference for this API) |
| 404 on a report read | exit 11 (not found, or another user's session) |
| 409 on `/usage` | exit 0: "usage reporting not available" is the answer |
| 409 on resume | "not paused": status re-read, polling continues |
| 429 (flat body) | exit 12; lane paused 300 s for every process; never retried; on create `elicit_create_outcome: not started` |
| 5xx on search | exit 11 after **one** attempt (a search may draw quota) |
| 5xx on a poll | up to 3 attempts, then exit 11 with the re-attach command |
| Network / timeout on a poll | 2 in a row tolerated within the cap; the third → exit 4 / 6 with the re-attach command |
| Timeout / network / 5xx on create | exit 6 / 4 / 11, sent once, "MAY have been created", `elicit_create_outcome: uncertain` |
| Any 3xx (301/302/303/307/308) on create | exit 4 (not followed; `requests` entry with `method: "POST"`, the real status and `redirect_chain`), `uncertain`; a session UUID in `Location` → `elicit_recovery_session_id` and the `elicit-resume` command |
| Create answered 202/201 without a valid `sessionId`, non-JSON, empty, or oversize | exit 11 (oversize 7), `uncertain`; a 2xx outside 202/201 naming a valid `sessionId` → that ID as `elicit_recovery_session_id` |
| Process killed during the create | only the `creating` row; the next same-question call is refused (exit 2) |
| Report `failed` / `unknown` | exit 11, a recorded result (digest + row) |
| Report paused, or still processing (or an undocumented status such as `queued`) at `--max-wait-min` | exit 13, re-attach command in stdout, stderr and the row |
| Report `completed` | exit 0, body saved as `restricted/<base>_report.md` |

## Minimal smoke test

Free calls first: `elicit-usage` (and a plain `elicit-resume`, a status
read) draw nothing. Every other Elicit call is a **paid call**, meaning one
that can draw on the plan's usage: `elicit-search` (and `find --backends
…elicit…`, whose Elicit leg is a search), `elicit-report`, and
`elicit-resume --confirm-spend` (it restarts paused paid work). In a
framework-development smoke test, run a paid call only when the dispatch
carries the user's approval for that named call (`framework-engineer.md`
§ Never Do; checklist SB7). Bracket the one search with usage reads:

    bash /daaf/scripts/scholar_search.sh elicit-usage {PROJECT_DIR}/lit_search
    bash /daaf/scripts/scholar_search.sh elicit-search "high-dosage tutoring effects on student achievement" {PROJECT_DIR}/lit_search --max-results 1
    bash /daaf/scripts/scholar_search.sh elicit-usage {PROJECT_DIR}/lit_search

A report is paid: run it only with the user's explicit approval, at the
smallest bounds that answer the question (the trial used 10/5), and keep the
printed `elicit-resume` command.
