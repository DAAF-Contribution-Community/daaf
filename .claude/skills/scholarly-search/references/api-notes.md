# API notes behind `scholar_search` — dated measurement log

Measured behavior the tool's design depends on, newest first. Each entry is
dated and says how it was observed. When a backend starts behaving
differently, re-measure through the CLI (so the probe itself leaves a
MANIFEST row), then update this log, the per-backend reference, and the
constant or comment in the adapter it points to. Truth hierarchy: live
measurement > vendor docs > this skill.

Evidence locations:
- 2026-10-02 (S1 port): `research/2026-10-02_FrameworkDev_ScholarlySearch/smoke_s1/`
  (MANIFEST.jsonl + raw `.json` per call, `DAAF_FETCH_CONTEXT=FrameworkDev_S1_smoke`);
  vendor docs in `…/web_fetches/apis/`.
- 2026-09-27 (the user's original tool, imported): the user's project
  `content_strategy/2026-09-27_academic_search_tooling/` (not in this
  repository); copied notes are in `…/scholarly-search/references/api-notes.md`
  of the S1 workspace.
- 2026-10-02 (verify calibration): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_calibration`; 8 `find` rows +
  107 `verify` rows), scripts `…/scripts/01_extract_calibration_candidates.py`,
  `02_run_verify_calibration.py`, `calibrate_verify_cutoffs.py` (execution logs
  appended); labeled set `tests/python/fixtures/scholar_search/verify_calibration_set.json`.
- 2026-10-03 (verify R1–R4): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_r1r4/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_r1r4`; 106 `verify` rows), scripts
  `…/scripts/03_add_claimed_year_to_fixture.py`, `04_run_verify_r1r4.py`,
  `calibrate_verify_r1r4.py` (execution logs appended); derived tables
  `calibration_verify_r1r4/derived/r1r4_items.parquet` and `r1r4_title_path.parquet`.
- 2026-10-03 (verify cycle 2): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle2/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle2`; 110 `verify` rows),
  scripts `…/scripts/06_run_verify_cycle2.py`, `calibrate_verify_cycle2.py`
  and its revision `calibrate_verify_cycle2_a.py` (the first labeled every
  numeral difference a guard firing; use `_a`); derived tables
  `calibration_verify_cycle2/derived/cycle2_items.parquet` and `cycle2_title_path.parquet`.
- 2026-10-03 (verify cycle 3): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle3/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle3`; 106 `verify` rows), scripts
  `…/scripts/08_run_verify_cycle3.py`, `calibrate_verify_cycle3.py`; probe
  `…/scratch/probe_cycle3_meaning_marks.py` (execution logs appended); derived tables
  `calibration_verify_cycle3/derived/cycle3_items.parquet` and `cycle3_title_path.parquet`.
- 2026-10-05 (verify cycle 4): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle4/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle4`; 106 `verify` rows), scripts
  `…/scripts/10_run_verify_cycle4.py`, `calibrate_verify_cycle4.py`,
  `11_check_contact_email_leak_cycle4.py` (execution logs appended); derived tables
  `calibration_verify_cycle4/derived/cycle4_items.parquet`, `cycle4_title_path.parquet`
  and `cycle4_cross_pairs_new_rule_passes.parquet`. Despite its name, that
  last table holds **all 197** cross-pair passes, every one labeled `v3`
  (none came from a cycle-4 fold or acronym); its `rule` column is the
  script's v3 / v4-fold / v4-acronym split.
- 2026-10-06 (verify cycle 5): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle5/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle5`; 106 live `verify` rows), scripts
  `…/scripts/12_run_verify_cycle5.py`, `calibrate_verify_cycle5.py`,
  `13_check_contact_email_leak_cycle5.py` (execution logs appended); derived tables
  `calibration_verify_cycle5/derived/cycle5_items.parquet`, `cycle5_title_path.parquet`,
  `cycle5_cross_pair_passes.parquet` (all passes, each with the `name_part` /
  fold that produced it), `cycle5_acronym_probes.parquet` and
  `cycle5_gate_matrix.parquet`; the gate matrix's MOCKED-HTTP artifacts (no
  network) are in `calibration_verify_cycle5/gate_matrix_mocked/`.
- 2026-10-06 (verify cycle 6, user decision D-16): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle6/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle6`; 106 live `verify` rows), scripts
  `…/scripts/14_run_verify_cycle6.py`, `calibrate_verify_cycle6.py`,
  `15_check_contact_email_leak_cycle6.py`, probe `…/scratch/c6_probe_author_rules.py`
  (execution logs appended); derived tables `calibration_verify_cycle6/derived/cycle6_items.parquet`,
  `cycle6_title_path.parquet`, `cycle6_cross_pair_passes.parquet`, `cycle6_acronym_probes.parquet`
  and `cycle6_gate_matrix.parquet` (540 cells); MOCKED-HTTP gate-matrix artifacts in
  `calibration_verify_cycle6/gate_matrix_mocked/`.
- 2026-10-06 (verify cycle 7, fix round K): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle7/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle7`; 106 live `verify` rows), scripts
  `…/scripts/16_run_verify_cycle7.py`, `calibrate_verify_cycle7.py`,
  `17_check_contact_email_leak_cycle7.py`, probes `…/scratch/c7_probe_rules.py` and
  `c7_probe_record_author_shapes.py` (execution logs appended); derived tables
  `calibration_verify_cycle7/derived/cycle7_items.parquet`, `cycle7_title_path.parquet`,
  `cycle7_cross_pair_passes.parquet` and `cycle7_gate_matrix.parquet` (828 cells);
  MOCKED-HTTP gate-matrix artifacts in `calibration_verify_cycle7/gate_matrix_mocked/`.
- 2026-10-06 (verify cycle 8, fix round L, user decision D-17): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle8/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle8`; 106 live `verify` rows), scripts
  `…/scripts/19_run_verify_cycle8.py`, `calibrate_verify_cycle8.py`,
  `20_check_contact_email_leak_cycle8.py` (execution logs appended); derived tables
  `calibration_verify_cycle8/derived/cycle8_items.parquet`, `cycle8_title_path.parquet`,
  `cycle8_cross_pair_passes.parquet` and `cycle8_gate_matrix.parquet` (996 cells);
  MOCKED-HTTP gate-matrix artifacts in `calibration_verify_cycle8/gate_matrix_mocked/`.
- 2026-10-06 (verify cycle 8b, transliteration add-on): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle8b/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle8b`; 106 live `verify` rows), scripts
  `…/scripts/21_run_verify_cycle8b.py`, `calibrate_verify_cycle8b.py`,
  `22_check_contact_email_leak_cycle8b.py`, probes `…/scratch/probe_nonfolding_letters.py`
  (orchestrator) and `probe_translit_8b.py` (execution logs appended); derived tables
  `calibration_verify_cycle8b/derived/cycle8b_items.parquet`, `cycle8b_title_path.parquet`,
  `cycle8b_cross_pair_passes.parquet` and `cycle8b_gate_matrix.parquet` (1,122 cells);
  MOCKED-HTTP gate-matrix artifacts in `calibration_verify_cycle8b/gate_matrix_mocked/`.
- 2026-10-06 (verify cycle 9, the final S1 patch): `research/2026-10-02_FrameworkDev_ScholarlySearch/calibration_verify_cycle9/`
  (`DAAF_FETCH_CONTEXT=FrameworkDev_S1_verify_cycle9`; 106 live `verify` rows), scripts
  `…/scripts/23_run_verify_cycle9.py`, `calibrate_verify_cycle9.py`,
  `24_check_contact_email_leak_cycle9.py`, design probe `…/scratch/probe_translit_v2_design.py`,
  and the review-8 reviewer's scripts re-run unchanged as `…/review_scratch/c8_r01_pure_probes_a.py`
  and `c8_r02_gate_matrix_a.py` (mocked output in `review_scratch/c8_quality/gm_out_a/`; execution
  logs appended); derived tables `calibration_verify_cycle9/derived/cycle9_items.parquet`,
  `cycle9_title_path.parquet`, `cycle9_cross_pair_passes.parquet` and `cycle9_mutations.parquet`.
- 2026-10-11 (S2, Scite adapter, tool 1.2.0): `research/2026-10-02_FrameworkDev_ScholarlySearch/smoke_s2/scite/`
  (`DAAF_FETCH_CONTEXT="FrameworkDev S2 Scite live trial"`; 6 MANIFEST rows, Scite raw
  responses under `restricted/`); vendor docs in `…/web_fetches/s2_research/`.
- 2026-10-11 (S2, Elicit adapter, tool 1.3.0 → 1.3.1): `research/2026-10-02_FrameworkDev_ScholarlySearch/smoke_s2/elicit/`
  (`DAAF_FETCH_CONTEXT="FrameworkDev S2 Elicit live trial"`, then "… (re-attach after crash)" and
  "… (step 5: usage after report)"; 6 MANIFEST rows, raw responses under `restricted/`); read-only
  state check `…/scripts/25_check_elicit_crash_recovery_state.py` (execution log appended).

## How far to trust the `verify` gate (standing summary, rules `2026-10-06f`)

*Moved here unchanged from SKILL.md § Verify before citing on 2026-10-11 (S2 wiring, to keep the
skill body near 500 lines); it summarizes the dated calibration entries below and is not itself a
new measurement.*

The cutoffs and rules (rules version
`2026-10-06f`, constants in `scripts/scholar_backends/_common.py`, every
value stamped in each MANIFEST row's `verify_cutoffs`) were calibrated
**in-sample** on 84 labeled items, part of them written by the calibrating
model; numbers and confusion tables are in the dated entries below. An
independent held-out validation is scheduled before Literature Review mode
depends on `verify`. What the calibration implies for use:
- CONFIDENT means "the titles are at least 95% alike character by
  character, with the same numbers, and every given author / year check
  passed". It does not mean the same title. With `--year`, no labeled
  wrong or fabricated title reached it (0 of 40; the identical-title
  Cochrane update needs the year check to fail). Zero passes in this
  sample bounds the true rate only loosely (about 7.7% at most, 95%
  confidence, for titles like these).
- Small edits that change the meaning still pass, because one changed
  word is a small share of a long title's characters. Measured: one
  word swapped ("Reading" → "Math") reaches CONFIDENT at about 90
  characters / 14 words (0.951); an inserted "No " scored 0.992; in
  Chinese or Japanese, a one-character swap or negation is CONFIDENT
  from about 20 characters (小学 → 中学 0.963; 有 → 无 0.955). Marks that
  carry meaning are dropped before scoring: `<` vs `>`, "-10%" vs "10%",
  Vietnamese tone marks, "año" vs "ano". So read the matched title
  (shown in the digest) once against the citation before citing: the
  score cannot tell a typo from a changed claim, and a fabricated title
  is often a one-word edit of a real one.
- Expect WEAK for most genuine citations that drop or add a subtitle,
  carry a report-number suffix, cite a renamed working paper, or garble a
  word.
- On `title:"…"`, a WEAK is "not verified", not "real but garbled": a
  fabricated title often lands on the real paper it imitated.

## Measured behavior: Elicit usage lag + S2 review fixes (2026-10-12)

- **Usage accounting lags.** `elicit-usage` read `percentUsed` **0** at
  2026-10-11T18:34:53Z, 18:35:06Z and 18:55:41Z (around a 1-result search
  and one 10/5 report; rows 1, 3, 6 below), then **3** at
  2026-10-12T15:44:52Z (orchestrator run, `hasUsageRemaining True`, same
  billing period, `extraUsage` null). So the two calls together drew about
  3% of the monthly allowance, charged hours later. Inference limits: no
  other use of the account is assumed (not verifiable), and the split
  between the search and the report is unknown. A usage bracket read right
  after a call can show nothing yet.
- **Tool 1.4.0 (fix round S-D, mocked tests only, no live paid call).** The
  quality review's probes (`review_scratch/s2q_r01_spend_probes.py`, log
  lines A1–A6, B, C, E) showed accepted-but-odd creates (non-JSON, no or
  non-UUID sessionId, 201, empty, oversize) left no uncertain marker, a
  same-origin 307 loop re-POSTed the create 6 times with an empty
  `requests` list, a process killed during the create left no row, and an
  undocumented status ("queued") ended polling with exit 11. Now: uncertain
  unless a refusal/429/4xx proves nothing started; 201 accepted; a
  `creating` checkpoint row before the POST; no 307/308 re-send on a
  non-idempotent POST and every refused redirect logged; non-terminal
  statuses polled to the cap (exit 13); 2 consecutive poll network/timeout
  errors tolerated; the duplicate guard ignores punctuation; `elicit-search`
  is sent once (it may draw quota). openapi.json declares only 202 for the
  create (research script 26, 2026-10-12). Details: `elicit.md`.
- **Tool 1.5.0 (fix round S-E, 2026-10-12, mocked tests only, no live or
  paid call).** Review cycle 2's probes (`review_scratch/s2q_r01_spend_probes_a.py`
  cases N1 and N5, `s2q_r07_redirect_busy_c2.py`) showed that a 301/302/303
  on the create POST was followed as a GET, and a 404/401/403/400 or 429 on
  that GET was read as "not started", so a re-run created a second paid
  report; the 429 was also logged as the POST's status with no redirect
  chain. And an uncertain create blocked its question for good, with only
  `--new-session` (which skips the whole guard) as a way out. Now: a
  non-idempotent POST follows **no** redirect (every 3xx refused, exit 4,
  `uncertain`, logged with `method: "POST"`, its real status and the chain;
  a session UUID in the `Location` becomes `elicit_recovery_session_id`); a
  4xx/429 proves "not started" only as the direct answer to the POST; a
  followed chain (idempotent requests only) records each hop's status and
  `final_method`; the close path: `elicit-resume <id> DEST --for-question
  "<q>"` (or a re-attach to the create's recovery sessionId) records
  `elicit_resolved_creates`, and `elicit-report --confirm-spend
  --new-session` records `elicit_superseded_creates`; unfinished sessions
  with a known sessionId keep blocking. `find --backends elicit,elicit`
  sends one Elicit search (names are de-duplicated). Intended trade: the
  cycle-1 probe F case (a 303 to a completed report) is now an uncertain
  create with a recovery ID, not a followed redirect. Unit suite: 245 tests,
  OK (6 expected failures), session scripts 28_b and 28_c. Details: `elicit.md` §
  "Closing an uncertain create".
- **Tool 1.5.1 (fix round S-F, 2026-10-12, user-authorized 4th round; mocked
  tests only, no live or paid call).** Review cycle 3's close-path probe
  (`review_scratch/s2q_r08_close_path_c3.py`) found three ways to close an
  uncertain create without evidence that its report exists: S3, `elicit-resume
  SID --for-question Q` on a session the MANIFEST tied to another question
  closed Q's create while SID kept counting for the other question (a plain Q
  re-run then created again: `exit=13 creates=1`); S5, a `--new-session` whose
  create never started (direct 402, or no key) still superseded the old
  create (`exit=13 creates=1`); S11, a status read of `unknown` closed it
  (`exit=13 creates=1`). Now: that `--for-question` is refused (exit 2, no
  request, `elicit_for_question_conflict`); a supersession counts only with
  the call's own outcome `uncertain`/`accepted` or an orphaned checkpoint
  (`elicit_supersession_effective` in the row); a status of `unknown` (or
  none) closes nothing (`elicit_close_skipped`). Re-run of the reviewer's
  probes as revision copies (`s2q_r08_close_path_c3_a.py`,
  `s2q_r01_spend_probes_c.py`): S3, S5 (both) and S11 now `exit=2 creates=0`
  on the plain re-run; every other case unchanged. Also: the S1 fixtures
  `s2_search.json`, `s2_snippets.json` and `eric_search.json` are now
  synthetic (live S1 shapes, invented values; user decision 2026-10-12;
  session scripts 32_a, 33_b: shapes identical, no old or live content value
  left). Unit suite: 248 tests, OK (6 expected failures), session script
  31_a.

## Measured behavior: Elicit (2026-10-11)

**How.** Live calls through the real CLI into `smoke_s2/elicit/`, using the
user-approved budget of exactly **one** paid report. Rows 1–4 used tool
1.3.0. The host crashed while row 4's process was polling, so rows 5–6 used
1.3.1 (built after the crash) and **re-attached** to the same session; no
second report was created. The fixtures
`tests/python/fixtures/scholar_search/elicit_*.json` keep the shapes of these
rows with invented values: synthetic since tool 1.4.0 (2026-10-12), no
Elicit output in the repository (see `elicit.md` § Storage).

| Row | Time (UTC) | Command | Request | Observed |
|-----|------------|---------|---------|----------|
| 1 | 18:34:53 | `elicit-usage` | `GET /usage` | 200 `{hasUsageRemaining: true, percentUsed: 0, periodStart 2026-10-09T11:00:00.000Z, periodEnd 2026-11-09T11:00:00.000Z, extraUsage: null}` |
| 2 | 18:34:58 | `elicit-search "high-dosage tutoring effects on student achievement" --max-results 1` | `POST /search/papers` `{query, maxResults 1, searchMode semantic, corpus elicit}` | 200; 1 paper carrying every documented field (`studyTypeTags`, `journalQuartile`, `fullTextUrl`, `pmid` null, a non-null abstract); `warnings: []`; no usage fields (the record itself is withheld from this published file: Elicit API Terms; raw response in `restricted/`) |
| 3 | 18:35:06 | `elicit-usage` | `GET /usage` | 200, identical to row 1 (`percentUsed 0`) |
| 4 | 18:35:12 | `elicit-report "What are the effects of high-dosage tutoring on K-12 student achievement?" --confirm-spend --max-search-papers 10 --max-extract-papers 5 --max-wait-min 9` | `POST /sessions/reports` (`isPublic: false`), one attempt | **202** in 0.4 s, the trial session's `sessionId`, `status processing`; `created` checkpoint row written before polling (`exit_code: null`). **No final row**: the host crashed mid-poll (last `elicit` gate booking 18:37:49, from the gate file's mtime; the in-memory poll statuses were lost) |
| 5 | 18:55:32 | `elicit-resume <the trial session> DEST --max-wait-min 8` (no `--confirm-spend`) | `GET /sessions/reports/{id}`, then `?include=reportBody`; **no POST** | Already `completed` / `executionStage done` (1.3 s, 0 polls). The plain read carries `result.{title, summary}`, 5 export URLs, `exportsStatus ready`; the body read adds `reportBody` (28,663 bytes) and `abstract`. Row names the orphaned row-4 checkpoint (`elicit_orphaned_checkpoints`) and its history |
| 6 | 18:55:41 | `elicit-usage` | `GET /usage` | 200, identical to row 1 (`percentUsed 0`) |

- **Usage deltas.** Search (rows 1 → 3): `percentUsed` 0 → 0. Report (rows 3
  → 6, a window spanning the crash; only this session ran on the key, an
  inference since other clients of the key cannot be seen): 0 → 0. Both
  calls are below the integer resolution of `percentUsed` on this plan, so
  the per-call cost stays **unmeasured**. A meaningful reading needs many
  calls or an account with `extraUsage` enabled (`spentUsdCents`).
  **Superseded 2026-10-12:** the 0 → 0 readings were lagged accounting, not
  sub-resolution cost; the same counter read 3 the next day, so the two calls
  together drew about 3% of the allowance (entry "Elicit usage lag + S2
  review fixes (2026-10-12)" above). The per-call split is still unknown.
- **Statuses seen:** 200 (usage, search, report reads) and 202 (create).
  Not seen: 402, 409, 429, a pause, `failed`, `unknown` (mocked tests only).
  `rate_headers: null` on all 7 Elicit responses (no rate-limit headers).
- **Report paper counts:** the JSON has no count fields. The body's
  included-studies table lists **5** studies (= `maxExtractPapers` 5), all
  "Full text retrieved? Yes" (the study list itself is report content and
  stays in `restricted/`). How many of the 10 searched papers were excluded
  is not reported. Completion time is
  bounded at ≤ 20 min 20 s after creation (18:35:12 → 18:55:32); the exact
  time is unknown.
- **Body format:** 106 inline anchors `{<64-hex>_<n>}` (one prefix, `n` from
  0 to 142 with gaps), bracketed author-year citations, and no reference
  list (references only via `bibUrl`/`risUrl`).
- **Export links:** presigned S3 (`X-Amz-Expires=604800`, `X-Amz-Date` = the
  fetch moment, a `X-Amz-Security-Token` credential), on two buckets.
  `links_expire_by` 2026-10-18T18:55:33Z in row 5. `grep -c X-Amz` on the
  MANIFEST = 0.
- **Crash-recovery lesson → tool 1.3.1.** The checkpoint did its job (the
  sessionId survived the crash). But nothing linked the checkpoint to a later
  re-attach, and nothing stopped a second paid create for the same question.
  1.3.1 adds both: `elicit-resume` records `elicit_session_history` /
  `elicit_orphaned_checkpoints`, and `elicit-report` refuses (exit 2, no
  request) when DEST_DIR's MANIFEST shows unfinished work for the same
  question, unless `--new-session`. The read-only check (script 25) confirms
  that the live session is now closed and that its checkpoint is recorded as
  orphaned.

## Measured behavior: Scite (2026-10-11)

**How.** Six live calls through the real CLI (tool 1.2.0) into
`smoke_s2/scite/`, MANIFEST rows 1–6 in order; the fixtures
`tests/python/fixtures/scholar_search/scite_*.json` keep their shapes with
invented values (synthetic since tool 1.4.0, 2026-10-12). Scite-derived
evidence stays private in `restricted/`; no Scite content is in the
repository (see `scite.md` § Storage).

| Row | Command | Request | Observed |
|-----|---------|---------|----------|
| 1 | `scite-tally 10.1093/qje/qjv036` | keyless `GET /tallies/{doi}` | 200; all six documented fields present (`supporting, contradicting, mentioning, unclassified, total, citingPublications`, integers); here total < citingPublications: the two counts measure different things (values withheld from this published file: Scite Terms §8(b); the raw response is in `restricted/`) |
| 2 | `retractions` Wakefield 1998 + `10.1093/qje/qjv036` | keyless `GET /papers/{doi}` ×2 (plus OpenAlex, Crossref) | Wakefield: `retracted: true`, a non-empty `editorialNotices` list; QJE: `retracted: false`, `editorialNotices: []`. **No `tally` key** in either keyless `/papers` response (the schema lists it); notices carry `status, date, noticeDoi, doi` and **no `urls`**. Combined: RETRACTED (all three sources) / NONE (all three) |
| 3 | `scite-tally 10.9999/daaf-nonexistent-doi-2026` | keyless `GET /tallies/{doi}` | 404 `{"detail": "Tally not found"}` → exit 11, recorded NOT FOUND |
| 4 | `scite-tally` 2 DOIs | keyless `POST /tallies`, body `{"dois": [...]}` (the guide's form) | **400** `{"message": "Invalid request."}` (a gateway-style body, not Scite's `{"detail": …}`) |
| 5 | same 2 DOIs | keyless `POST /tallies`, body = **bare JSON array** | 200 `{"tallies": {"<doi>": {tally}, …}}`; the adapter now sends the bare array |
| 6 | `scite-search "tutoring" --limit 1 --ack-scite-license` | keyed `GET /api_partner/search?term=&limit=` | 200; top level `aggregations, count (an integer), countIsApproximate (false), hits, restrictedCites (false), suggestedTerm`; the hit has `tally`, `citations` (3, every one `snippetHidden: true`, `snippet: ""`), `fulltextExcerpts`, `editorialNotices`; `title` wraps matches in `<strong class="highlight">` (the mapper strips tags) |

- **Rate limits.** Keyless (rows 1–5): `RateLimit-Limit: 60`,
  `X-RateLimit-Limit-Minute: 60`; `RateLimit-Remaining` fell 59 → 58 → 57 →
  56 → 55 across `/tallies`, `/papers` and the batch POST, so one keyless
  bucket covers all three. Keyed Search (row 6): `RateLimit-Limit: 13` with
  `X-RateLimit-Limit-Second: 13` and `X-RateLimit-Limit-Minute: 60`. The gate
  stays at 1.1 s on one lane, `scite`.
- **Editorial-notice status vocabulary** (Wakefield, the docs enumerate
  none): `Retracted` (1), `Has correction` (1), `Has erratum` (1), `Has
  expression of concern` (1), `Comment` (26). Mapped by stem to the
  retraction vocabulary: retracted / corrected / corrected / expression of
  concern / **updated** (tools 1.2.0–1.3.1; since 1.4.0 `Comment` maps to
  **commented**, ranked with `none`: `scite.md` § Retraction status values);
  the native string is kept as `native_status` and shown in the digest.
  Under 1.2.0–1.3.1 a Scite-only UPDATED was therefore usually just
  published comments.
- **Caching.** `cache-control: s-maxage=1800` (measured 2026-10-11 by the
  pre-authoring research with curl, headers only): tallies can be up to 30
  minutes stale; the `scite-tally` digest says so.

## Measured behavior: verify cycle 9 / final S1 patch (2026-10-06)

**Why.** Review cycle 8, the last review round, found one literal BLOCKER
under the D-17 closing rule and one FIX-NOW item (reviewer logs
`review_scratch/c8_r01_pure_probes.py`, `c8_r02_gate_matrix.py`,
`c8_r03_mutants_and_fix_sketch.py`). The user approved fixing both with
the reviewer's tested sketches, verified by re-running the reviewer's own
scripts, with no further review round (Checkpoint 2g).
- **B-1:** the N-2 check compared only the *second* given position.
  "John Q. R. Smith" on "John Q. S. Smith" graded CONFIDENT on all six
  routes (`c8_r02` log).
- **F-1:** `translit-v1` still deleted 216 Latin code points (`c8_r01`
  log). "Aliyev" on "İlham Əliyev" and "Habib" on "Joe Ħabib" were false
  MISMATCHes (exit 11). "Liyev" on "Əliyev" passed, which is a deleted-letter
  collision.

**Change (rules `2026-10-06f`, author rule `contiguous-surname-v10`,
`VERIFY_TRANSLIT` `translit-v2`; organization rule and numeral guard
unchanged).**
- **F1.** When both names carry two or more given words or initials, every
  aligned position after the first must agree: equal, or one is the
  other's initial. `zip` stops at the shorter side, so "J. Q. Smith" on
  "John Quincy Adams Smith", "Smith JAB" on "John A. Smith", "C. K.
  Jackson" on "C. Kirabo Jackson" and "M. A. Kraft" on "Matthew A. Kraft"
  still pass. A mismatch is *ambiguous* with `name_part` `surname; given
  name differs`, and the reason names the position. Code:
  `person_step_aside`.
- **F2, option (a): a principled mapping, not a hand list.** The table
  (`LATIN_TRANSLITERATION`, applied after NFKD in `name_tokens`,
  `norm_title` and `org_initials`) is now built from three parts. Later
  parts win:
  1. **name-derived:** every letter in the reviewer's code-point blocks
     (U+00C0–U+024F, U+0250–U+02AF, U+1E00–U+1EFF) that the ASCII fold
     deletes and whose Unicode name is `LATIN SMALL|CAPITAL LETTER <X>
     WITH …` maps to `<X>`. Examples: ħ→h, ŧ→t, ɓ→b, ɗ→d, ƙ→k, ƴ→y, ƒ→f,
     ǥ→g, ɨ→i, ʂ→s. A letter not of that shape whose case partner is
     maps the same way: Ɖ "AFRICAN D", partner of ɖ "D WITH TAIL"; ɵ
     "BARRED O", partner of Ɵ; Ɋ, partner of ɋ. Function:
     `name_derived_transliteration`. Unicode names are immutable, and the
     blocks are fixed in `TRANSLIT_NAME_RANGES`, so the table does not
     drift with a newer Python. The design probe found 85 of the 216 to be
     `… WITH …` letters (`probe_translit_v2_design.py` log);
  2. the `translit-v1` letters, unchanged (ø→o, æ→ae, đ→d, þ→th, …);
  3. the reviewer's letters whose name carries no base letter: ə→a,
     ɛ→e, ɔ→o, ʒ→z, both cases. Ǯ/ǯ (ezh with caron) follow, because NFKD
     yields Ʒ.
- **Why (a) rather than (b).** The rule is simple and reviewable (one
  regex on an immutable name), and it can only turn a deletion into the
  base letter. That is the same thing NFKD already does for decomposable
  marks (ç→c). It cannot create a new collision of the deleted-letter kind.
- **Left deleted (118, counted, documented).** These letters have no
  principled single-letter reading: IPA-only letters (ɐ ɑ ɒ ɘ ɜ ɡ ɣ ɤ ɥ ɯ
  ɹ ʃ ʊ ʌ ʍ ʎ …), small capitals (ɢ ɪ ɴ ʀ ʁ ʏ ʙ ʛ ʜ ʟ), clicks and glottal
  stops (ǀ ǁ ǂ ǃ ʘ ʔ ʕ ʖ Ɂ ɂ ʡ ʢ), tone letters (Ƅ ƅ Ƨ ƨ Ƽ ƽ), historic
  letters (ƿ Ƿ Ȝ ȝ Ƕ ƕ Ȣ ȣ Ỻ ỻ Ỽ ỽ ẜ ẝ ẟ), digraphs (ȸ ȹ ʣ ʤ ʥ ʦ ʧ ʨ ʩ ʪ ʫ),
  and Ǝ/ǝ, Ɣ, Ɩ, Ɯ, Ʃ, Ʊ, Ʌ, Ʉ/ʉ, ƛ, ƍ, Ƹ ƹ ƺ, ƻ, ƾ, ȷ, ɟ, ʄ. The full list
  is in the `c8_r01_pure_probes_a.py` log :113. Of these, Ǝ/ǝ (Pan-Nigerian
  orthographies) and Ɣ/ɣ (Ewe and other West African orthographies) are
  the most likely to appear in an author name. They are left out because
  their romanization is not settled (ǝ as a or e; ɣ as g, gh or x). This is
  a candidate for the held-out validation, not a guess made now.
- **No new alternatives.** `TRANSLIT_ALTERNATIVES` is unchanged. A
  second romanization of ə ("Memmedov" for "Məmmədov") still fails. This is
  stated as a cost below.
- **Doc fix (review-8 FIX-NOW).** "Soerensen" on "Sørensen" is *ambiguous*
  through the cycle-5 dropped-umlaut fold, not the transliteration
  step-aside. The `--help` text, the SKILL.md and the code comments now
  give "Djordjevic" as the transliteration example.
- **CONFIDENT digest (review-8 FIX-NOW).** The CONFIDENT line of the
  digest now carries the hand-off's interim caveat in one sentence: until
  the adjudicator ships, treat CONFIDENT as WEAK when the cited author is
  an organization named by less than its full listed name, "&" company
  names included. The word CONFIDENT still appears only on a CONFIDENT
  verdict. The W-B tests pass, and 0 live runs had a stray CONFIDENT.

**Measured.**
- **The reviewer's scripts, re-run unchanged against `-06f`**
  (`create_script_revision.sh` copies; r02's only edit is its output
  folder, so that its `rmtree` cannot delete the reviewer's c8 artifacts):
  - `c8_r02_gate_matrix_a.py` (100 mocked runs, 6 routes). The list
    `non-genuine CONFIDENT` is `[("hyphen half 'Paul Sartre'",
    'design')]` (log :175). That cell is P-1, a design matter deferred to
    pre-S5. B-1 "N-2 gap: 3rd given differs" is WEAK on all six routes
    (log :155). The collision "Liyev" is MISMATCH (:158). "Aliyev" and
    "Habib" are CONFIDENT (:159, :160). `genuine MISMATCH: []` (:176).
    EXISTS, NOT FOUND and fabricated titles never reach CONFIDENT (the
    script's own assertion passed).
  - `c8_r01_pure_probes_a.py`. Still-deleted letters: **216 → 118**
    (log :113). `genuine-labeled probes that FAIL: []` (:193). `wrong-labeled
    probes that PASS: [('RAND Corp.', ['R. Corp'])]` (:191). That probe is
    unchanged from cycle 8: "RAND" is compatible with the initial "R." under
    rule 1, which is the "J. Smith" = "John Smith" design. The
    design-labeled passes are unchanged. Among them is P-1, "Paul Sartre"
    on "Jean-Paul Sartre".
- **Live labeled runs** (`calibrate_verify_cycle9.py` log): no verdict,
  author status, numeral check or exit note changed on the 106 runs
  (log :336–:367).
  - DOI path, match 9/35/0 and mismatch 0/20/20 (C/W/M), the same as
    cycle 8b. Genuine-as-MISMATCH is 0, and mismatch-as-CONFIDENT with
    `--year` is 0 (log :318). On the title alone it is X40 (:319).
  - `title:` path: match 3/7/1/0 and mismatch 0/5/1/5 (C/W/M/NF).
  - No labeled cited author holds a translit-v2 letter or carries three or
    more given words (log :369–:370). The live set therefore does not
    exercise either change; the reviewer's scripts and the unit tests do.
  - OpenAlex spend: $0.0270.
- **Cross-pairing:** 197 passes over 6,972 pairs, with none gained and
  none lost (log :373, :375). One live record name holds a translit-v2
  letter: "Saša Đurić", whose đ was already in v1 (:376).
- **Mutations** (in-process, production files untouched; log :378–:387).
  The baseline is 183 tests with 0 failures. Every mutant fails tests:
  - F1 reverted to the cycle-8 second-position check: 7 failures and 1
    error;
  - F2 reverted to the `translit-v1` table: 47 failures;
  - F2 with the name-derived letters only (no schwa, open e, open o or
    ezh): 22 failures;
  - F2 with the explicit letters only: 30 failures.
- **Unit tests:** `VerifyCycle9Tests` (8 tests, with negatives). Ran 183
  tests, OK, with 6 expected failures.

**Costs, stated.**
- A citation that carries a later given name or initial *different* from
  the record's is now WEAK. Example: "John Q. R. Smith" on "John Q. S.
  Smith", where the R/S slot may be a typo.
- A second romanization of a v2 letter still fails ("Memmedov" vs
  "Məmmədov", "Hhabib"). Under v1 the same citation also failed.
- `norm_title` fusion keys change for titles that hold a v2 letter. Before,
  such a letter was deleted. *Inference:* this is rare in titles.

**Re-verify advice.** Re-verify the following CONFIDENT rows graded under
`2026-10-06e` or earlier:
- rows whose cited author carries **three or more** given words or
  initials (B-1);
- rows whose cited or listed name holds a **newly mapped letter**
  (ə ɛ ɔ ʒ, or any "letter with stroke, hook, bar, curl, tail or loop"
  outside the v1 table, such as ħ ŧ ɓ ɗ ƙ ƴ ƒ).

Re-run MISMATCH rows of that second kind as well: they were false blocks
("Aliyev" on "Əliyev").

## Measured behavior: verify cycle 8 (2026-10-06)

**This is the final rule-layer round (user decision D-17).** D-17 makes the
citation adjudicator's second check on **every** CONFIDENT mandatory. The
rule layer's remaining false passes therefore become documented residuals
that the model reviews, not blockers for another heuristic round. Once the
adjudicator ships, CONFIDENT will mean "rule-passed, then model-confirmed".

**Question.** Review cycle 7 found three defects in rules `2026-10-06c`
(reviewer logs `review_scratch/c7_quality_r01_*`, `c7_quality_r02_*`,
`c7_quality_r03_*`):
- **N-1 (false block):** "RAND Corp." on "RAND Corporation" and "Brookings
  Inst." on "Brookings Institution" were MISMATCH on all six routes. A
  final period was read as reference-list punctuation.
- **N-2 (false pass):** "J.-M. Sartre" on "Jean-Paul Sartre" and "John Q.
  Smith" on "John A. Smith" were CONFIDENT. Rule 1 compared only the first
  given word.
- **N-3 (false pass):** "Health Canada" on a record listing just "Canada",
  and "Jane Smith" on "Smith", were CONFIDENT. Rule 1 was skipped when the
  record had no given name.
- **INFO:** a hyphenated given name ("Jean-Paul Sartre" on "J.-P. Sartre")
  was stepped aside by rule 2 as an organization shape.

**Change (rules `2026-10-06d`, author rule `contiguous-surname-v8`; org
rule `org-conservative-v2` unchanged).** All four are step-asides built
from the reviewer's tested sketch (`c7_quality_r03`), with no word lists.
- **N-1.** A cited name of two or more words whose last word is two or
  more letters plus "." is *ambiguous* (`organization: not an exact name
  match`) when that stem is a proper prefix of a word in a listed name.
  The listed name supplies the expansion. "Fakeman.", "Jane Fakeman." and
  "J. Fakeman." still fail. Code: `cited_final_abbreviation`.
- **N-2.** When both names carry two or more given words or initials, the
  second must agree too (equal, or one is the other's initial). Otherwise
  the result is `surname; given name differs`. Still passing: "C. K.
  Jackson", "Smith JA", "M. A. Kraft", "Kirabo Jackson" on "C. Kirabo
  Jackson", and "John Smith" on "John A. Smith".
- **N-3.** Cited given words with no listed given name to compare against
  give `surname; given name differs`.
- **INFO, hyphenated given names.** A hyphen-joined given name counts as
  one word for rule 2, so "Jean-Paul Sartre" on "J.-P. Sartre" passes
  (`name_part` `surname`). It is also one *name*: a listing that shows only
  part of it steps aside ("Jean-Paul Smith" or "J.-P. Smith" on "Jean
  Smith"). Without that guard, the rule-2 change alone would have made
  "Jean-Paul Smith" on "Jean Smith" a new CONFIDENT. Code:
  `cited_given_hyphenated`.

**Measured** (`calibrate_verify_cycle8.py` log).
- **Live labeled runs:** no verdict, author status, numeral check or exit
  note changed on the 106 runs (log :799 to :831). DOI path: match 9/35/0,
  mismatch 0/20/20, the same as cycle 7. Genuine-as-MISMATCH is 0 and
  mismatch-as-CONFIDENT (with `--year`) is 0 (log :781). No genuine item
  lost CONFIDENT (log :831). The live author statuses are rebuilt offline
  from the digests' author lists (log :762).
- **Cross-pairing:** 197 passes over 6,972 pairs, none gained and none
  lost (log :835, :837).
- **Gate matrix:** 996 mocked cells on six routes: cycle 7's flag sets plus
  28 new ones (log :839). The new ones cover N-1, N-1 negatives, N-2, N-3,
  hyphenated names, controls and residuals. Results (assertion log :896):
  - the N-1 cells are WEAK with exit 0 (log :893);
  - the N-1 negatives are MISMATCH (log :894);
  - every N-2 / N-3 / hyphen cell is WEAK with `surname; given name
    differs` (log :895);
  - none of the 432 organization-related or name-incompatible cells reaches
    CONFIDENT: 394 WEAK, 30 MISMATCH, 8 NOT FOUND (log :890);
  - the six residual cells are CONFIDENT on every route, as pinned (log
    :891);
  - the full CONFIDENT list is at log :889.
- **Mutations:** each reverted cycle-8 change fails tests (log :899 to
  :902):
  - N-1: 1 failure;
  - N-2: 21;
  - N-3: 9;
  - hyphen rule: 1.

  The cycle-7 mutants still fail: H1 66, prefix 25, L1 2, "&" 3, MUT-2 2
  (log :903 to :907).

**Costs, stated.** Each step-aside moves a pass to WEAK (none to MISMATCH):
- a cited given name against a surname-only listing ("Jane Smith" or "J.
  Smith" on "Smith");
- a cited middle initial that differs from the listed one ("John Q." vs
  "John A.");
- a hyphenated given name listed only in part ("J.-P. Smith" on "Jean
  Smith").

**Documented D-16 residuals (accepted; pinned in
`VerifyCycle8Tests.test_documented_d16_residuals_*`).** Each is shaped
exactly like a genuine person citation, so no word-list-free rule separates
it. Each still grades CONFIDENT on every route, and the mandatory
adjudicator CONFIDENT check (D-17) reviews it:
- **A bare or partial organization name that is the record's last
  word(s):** "Canada" on Statistics Canada; "Research" and "Policy
  Research" on Mathematica Policy Research. This is the shape of "Smith"
  on "John Smith".
- **First and last word with the middle dropped:** "Mathematica Research"
  on Mathematica Policy Research; "Public Associates" on Public Policy
  Associates. This is the shape of "John Smith" on "John A. Smith".
- **The "&" co-author split:** "Johnson & Johnson" on "Mary Johnson" (also
  "Ernst & Young" on "Jane Ernst"). The "&" ends the first cited author, so
  only "Johnson" is checked. This is the shape of "Smith & Jones".

**Not changed.** A hyphenated given name in a cited name that matched no
listed author still counts as three words in `cited_org_shape`, so
"Jean-Paul Fakeman" is *ambiguous* rather than a fail (inference from the
code; not run). This is a WEAK, not a pass, so it was left alone.

### Add-on 8b: transliteration (2026-10-06)

**Reported by the Manuscript Preparation session**, then confirmed by the
orchestrator's probe (`scratch/probe_nonfolding_letters.py`, log).

**Question.** The ASCII fold deleted Latin letters that have no Unicode
decomposition. "Sørensen" became `srensen`, "Łukasz" `ukasz`, "Ærø" `r`,
"Đorđević" `orevic`, "Þórsson" `orsson`. A native spelling on both sides
passed. An ASCII-transliterated citation was falsely blocked: "Sorensen",
"Djordjevic" and "Aeroe" failed (MISMATCH, exit 11), and "Lukasz Nowak"
was *ambiguous*. Deleting letters also allowed collisions: "Srensen" would
have passed on "Anne Sørensen".

**Change (rules `2026-10-06e`, author rule `contiguous-surname-v9`,
`VERIFY_TRANSLIT` `translit-v1`, stamped in `verify_cutoffs.translit`).**
- **Table.** `LATIN_TRANSLITERATION` is applied after NFKD, on both
  sides, in every fold that deletes: `name_tokens` (all folds),
  `norm_title` (fusion keys) and `org_initials`. It maps ø→o, ł→l, æ→ae,
  œ→oe, đ/ð→d, þ→th, ı→i, ŋ→ng, ĸ→k, ß→ss. `norm_title` and
  `org_initials` used to delete ß as well. A character table is
  normalization, not a word list (D-16). `verify_title_norm` is unchanged
  because it never deleted these letters: it keeps every script (probe
  `probe_translit_8b.py`: "ærø" stays "ærø").
- **Step-aside.** When the surname matches no one, it is retried with each
  table letter, on either side, replaced by an alternative spelling
  (`TRANSLIT_ALTERNATIVES`: ø o/oe, æ ae/a/e, œ oe/o/e, đ d/dj, ð d/dh/th,
  þ th/t, ŋ ng/n, ĸ k/q). A hit is *ambiguous* (`name_part` `surname;
  alternative transliteration`, fold `translit-alt`), never a pass. Code:
  `translit_alternative_hit`.
- **Narrowing, stated.** The dispatch asked for *ambiguous* whenever a
  name holds a table letter and the comparison fails. This would also
  have stepped aside "Nielsen" on "Anne Sørensen", which the dispatch
  requires to stay a fail. So the step-aside fires only when an
  alternative spelling actually matches.
- "Soerensen" on "Sørensen" was already *ambiguous* through the cycle-5
  dropped-umlaut fold (r + oe + two letters). It stays *ambiguous*, with
  `name_part` `surname`.

**Measured** (`calibrate_verify_cycle8b.py` log).
- **Live labeled runs:** no verdict, author status, numeral check or exit
  note changed on the 106 runs (log :875 to :908). DOI path: match
  9/35/0, mismatch 0/20/20, the same as cycle 8. Genuine-as-MISMATCH is 0
  and mismatch-as-CONFIDENT (with `--year`) is 0 (log :858). No cited
  author in the labeled set holds a table letter (log :911), so the live
  set does not exercise the change. The gate matrix does.
- **Cross-pairing:** 197 passes over 6,972 pairs, none gained and none
  lost (log :914, :916). Two live record names hold a table letter:
  "Saša Đurić" and "Gilbert Ramı́rez", whose dotless ı carries a combining
  accent (log :917).
- **Gate matrix:** 1,122 mocked cells on six routes: cycle 8's flag sets
  and assertions, plus 21 new ones (log :919). Every cycle-8 assertion
  still holds (log :969). Results:
  - native and ASCII spellings ("Sorensen", "Dordevic", "Aero", "Lukasz
    Nowak", "Thorsson") are CONFIDENT (log :970);
  - alternative transliterations ("Soerensen", "Djordjevic", "Aeroe",
    "Torsson") are WEAK with exit 0 on every route (log :971);
  - a different surname ("Nielsen", "Petrovic") and the old deleted-letter
    collisions ("Srensen", "Orevic", "Rr") are MISMATCH (log :972);
  - the bare "R" is *not checked*: no surname can be read (log :973).
- **Mutations** (log :977, :978). Reverting the table fails 36 tests, and
  reverting the step-aside fails 13. The cycle-7 and cycle-8 mutants still
  fail.

**Not changed.** Other Latin letters without a decomposition (for
example ħ, ŧ, ƒ) are still deleted by the ASCII fold. This is inference
from the code; they were not probed. They are outside `translit-v1`.
*(Superseded 2026-10-06: review cycle 8 probed this and counted 216 such
letters; cycle 9, `translit-v2`, maps 98 of them. See the cycle-9 entry
above.)*

## Measured behavior: verify cycle 7 (2026-10-06)

**Question.** Review cycle 6 found two classification holes in rules
`2026-10-06b` (reviewer logs `review_scratch/c6_r01_*`, `c6_r02_*`):
- **H1:** an organization whose name holds no organization word was read as
  a person and passed on its last word. "Health Canada" on Statistics
  Canada, "New America" on Teach For America and "Westat Policy Research"
  on Mathematica Policy Research graded CONFIDENT on all six routes;
- **M1:** the U.S. prefix was set aside on both sides, so "U.S.
  Department of Education" on a bare "Department of Education" record
  graded CONFIDENT;
- also M2 (a test gap: a mutant passing partial names survived), L1 ("Am.
  Psychiatric Assn." was a false MISMATCH) and L2 ("&" vs "and").

Under D-16 each fix had to be a **step-aside**, not a new word list.

**Change (rules `2026-10-06c`, author rule `contiguous-surname-v7`, org
rule `org-conservative-v2`).**
- **Rule 1, given names.** When the cited name gives a given name or
  initial, the first one must be one of the matched author's given names
  or their initial (either direction). Words both names share just before
  the surname count as surname, so these pass:
  - "García Márquez" on "Gabriel García Márquez";
  - "Kirabo Jackson" on "C. Kirabo Jackson";
  - "Dela Cruz" on "Juan de la Cruz" (joined particles, which the
    reviewer's sketch broke).

  Otherwise the match is *ambiguous*, with `name_part` = `surname; given
  name differs`.
- **Rule 2.** A cited name of three or more words (particles not counted)
  with no initial passes only when it reproduces the listed name whole.
- **Rule 3.** The same holds for a listed name of three or more words with
  no initial and a connective word ("of", "and", "for", "the", "on",
  "in"), as in "Teach For America". The rule does not try to recognize
  given names. A connective is the only organization signal it reads,
  because "Andre Joshua Nickow" (four genuine labeled items) is also three
  words with no initial.
- **M1.** The national prefix ("U.S.", "US", "USA", "United States (of
  America)") is set aside only when the listed name has it and the cited
  name does not, and only when two or more content words remain.
- **L1.** An abbreviated or organization-shaped cited name that matches no
  one is *ambiguous* (`organization: not an exact name match`), never a
  fail. That covers a non-final word ending in ".", a connective, or rule
  2's shape.
- **L2.** "&" is read as "and". Centre/Center and
  Organisation/Organization stay unmatched for the adjudicator (*not
  checked*, pinned in `test_l2_ampersand_and_spelling_variants`).

**Measured** (`calibrate_verify_cycle7.py` log).
- **Live labeled runs:** no verdict, author status, numeral check or exit
  note changed on the 106 runs (log :720 to :726). DOI path: match 9/35/0,
  mismatch 0/20/20. Genuine-as-MISMATCH is 0; mismatch-as-CONFIDENT (with
  `--year`) is 0 (log :670). No genuine item lost CONFIDENT. Every cited
  author in the set is a bare surname, so rule 1 never fires on it.
- **Cross-pairing:** 197 passes over 6,972 pairs, none gained and none
  lost (log :726).
- **Gate matrix:** 828 mocked cells on six routes: cycle 6's 91 flag sets
  plus 48 new ones (H1, M1, L1, L2, given names). CONFIDENT appears only
  on the cells allowed it, and none of the 372 organization-related or
  name-incompatible cells reaches it: 334 WEAK, 30 MISMATCH, 8 NOT FOUND
  (log :799, assertion :802). The H1 and M1 cells are WEAK (log :737,
  :743, :748, :753), and both L1 cells are WEAK with exit 0 (log :801).
- **Mutations:** each reverted change fails tests (log :805 to :809):
  - H1: 32 failures;
  - asymmetric prefix: 25;
  - L1: 3;
  - "&" fold: 3;
  - MUT-2: 2. Before this cycle it survived.

**Costs, stated.**
- **Given names:** "Jane Smith" on "John Smith", "J. Smith" on "Mary
  Smith" and "Bill Clinton" on "William J. Clinton" are WEAK. A nickname
  or another person is a question for the adjudicator. A different given
  name is *ambiguous*, not a fail: no labeled negative needs the fail
  (mismatch-as-CONFIDENT stays 0 without it), and MISMATCH is a hard
  block.
- **Three-word names:** "Andre Joshua Nickow" cited whole on "A. J.
  Nickow" is WEAK (rule 2), and "Teach America" on "Teach For America" is
  WEAK (rule 3).
- **Prefix:** "U.S. Department of Education" on a bare "Department of
  Education" record is WEAK.

**Residual (documented, not closed).** A bare last word of a two-word
organization name, or everything but the first word of a longer one with
no connective, is shaped exactly like "Smith" on "John Smith" or "García
Márquez" on "Gabriel García Márquez". So these still pass, CONFIDENT on
all six routes (log :800):
- "Canada" on Statistics Canada;
- "Policy Research" and "Research" on Mathematica Policy Research.

They are pinned in `test_h1_rules_2_and_3_organization_shaped_names`. A
rule layer without word lists cannot separate them; the adjudicator, or a
reader of the matched author, can.

**Also seen.** "Environment and Climate Change Canada" cited on a
Statistics Canada record is MISMATCH: " and " splits co-authors, so
"Environment" is read as a surname. It is a wrong organization, so this
is not a false block of a genuine citation. Cited on its own record, the
same name reads as a given-name match: *ambiguous* (inference from the
rule; not run).

## Measured behavior: verify cycle 6 (2026-10-06)

**Question.** Review cycle 5 found organization-author holes for the third
cycle running, each found by adversarial review after the previous patch:
- **N1:** the reverse form "APA (American Psychological Association)"
  graded CONFIDENT on an American Psychiatric Association record, on all six
  routes;
- **N2:** organizations without an organization word were read as persons
  on their last word ("World Bank" on an Asian Development Bank record →
  CONFIDENT);
- **N4:** a contained name passed ("Department of Education" on "Ohio
  Department of Education");
- **N3:** the dropped-umlaut fold also caught Xue / Xu and similar pairs;
- **N5:** "APA, American Psychiatric Association" was a false MISMATCH.

The user asked why brittle string checks were doing semantic work and
decided on a new architecture (**D-16**, 2026-10-06):
- the `verify` rule layer owns *identity* (the record exists, exact or
  near-exact title, numbers, year, surname, retraction) and is either
  certain or steps aside to WEAK;
- a forthcoming model **citation adjudicator** (built with the S5 agents)
  resolves the WEAK band (semantic equivalence);
- a human resolves what the adjudicator marks uncertain.

**Heuristic patching of semantic matching stops with this cycle.** Later
semantic gaps go to the adjudicator's design and evaluation, not to new
string rules. This round makes organization matching conservative, not
clever. Rules are `2026-10-06b`: author rule `contiguous-surname-v6`,
organization rule `org-conservative-v1` (new MANIFEST key
`verify_cutoffs.org_rule`), `numerals-v4` unchanged; the tool is still
`1.1.0-daaf`. Does it close N1–N5 without new MISMATCHes on genuine
citations, and what does it cost?

**What changed** (constants and comments in `scholar_backends/_common.py`):
- **Rule 1, organizations.** An organization author passes only when the
  cited full name equals a listed author's **whole** name, compared with
  `org_key`: case, punctuation and accents normalized, a leading "The" and
  a leading "U.S." / "United States" dropped on both sides, hyphens either
  kept or deleted. Five written forms are read the same way: "Full (ACR)",
  "Full [ACR]", "ACR (Full)", "ACR, Full" and "Full, ACR". In each, the full
  name is compared and the acronym only corroborates it
  (`acronym_corroborates`, informational). Every weaker relation is
  *ambiguous*, with `name_part` = `organization: not an exact name match`
  and a reason starting `organization: not an exact name match
  (adjudicate):`, never *pass*. The weaker relations are:
  - a bare acronym, or any acronym, equal to a listed organization's
    initials;
  - an acronym or parenthetical equal to a listed name;
  - one name contained in the other;
  - one name's content words a subset of the other's.
- **Rule 1, decision on unrelated organizations.** An organization with
  none of those relations stays *not checked*, as since cycle 3; it does
  not *fail*. Reasons: the existing negatives pin *not checked*
  (`test_id_author_edge_cases`: "Institute of Education Sciences (IES)" vs
  NCES, "National Academy of Sciences" vs IES); a cited organization may
  be a sponsor or publisher the record does not list (X02); and a *fail*
  would add MISMATCH risk on genuine citations, against D-16.
- **Rule 1, person reading inside an organization.** A cited name read as a
  person ("Bank", "Association (APA)") that is found only **inside** a
  listed organization's name is the same *ambiguous* outcome. A listed
  person with that surname is preferred to the organization. A listed name
  reads as an organization (`is_org_name`) when it holds an `ORG_WORDS`
  word and either has two or more words before its first comma or carries
  the word after the comma ("ACT, Inc.").
- **Dead code.** The cycle-4 acronym *pass* path now returns *ambiguous*,
  and the cycle-5 "organization acronym only" outcome is folded into
  `ORG_NOT_EXACT`. With `--first-author`, a bare acronym matching a later
  author still *fails* (unchanged). `org_initials` and `cited_acronyms`
  remain in use, to find relations.
- **N2.** `ORG_WORDS` gains bank, union(s), clearinghouse(s),
  parliament(s), forum(s), court(s), reserve(s) and nations. "banks" is
  left out on purpose: Banks is a common surname ("James A. Banks"). A
  single lead word stays a person: "Bank" vs "John Smith" is *fail*, and
  "Union, J." vs "Union, Jane" is *pass*.
- **N3.** The dropped-umlaut fold now needs a consonant, then ae/oe/ue,
  then **two** more letters (`(?<=[b-df-hj-np-tv-z])([aou])e(?=[a-z]{2})`).
  The reviewer's sketch allowed one letter after, which still folded Goel
  into Gol. Xue/Xu, Yue/Yu, Hue/Hu, Doe/Do, Bauer/Baur, Goel/Gol, Lue/Lu
  and Rao/Raoe *fail*; Mueller/Muller, Schroeder/Schroder and
  Koehler/Kohler stay *ambiguous*.
- **N5.** "APA, American Psychiatric Association" now *passes* on the
  Psychiatric record (CONFIDENT on all six routes), and the Psychological
  variant is *ambiguous*. "[APA]" behaves exactly like "(APA)".
- **Help and docs.** The `--author` help and SKILL.md state the exact-name
  rule and its reason, and the WEAK workflow treats organization WEAKs as
  expected.

**Test changes, stated** (151 tests, 6 expected failures):
- `VerifyCycle4Tests.test_3`: the OECD, NBER, IES and NCES acronyms moved
  *pass* → *ambiguous*.
- `test_10`: "Board" and "Board, Jane" vs "Jane Board" moved *pass* →
  *ambiguous*. This is the cost of reading "Jane Board" as an
  organization.
- `VerifyCycle5Tests`: the bare-APA limit and the six M2 acronyms (plus
  WWC, now readable) moved *pass* → *ambiguous*, and "IES" moved *pass* →
  *ambiguous*. The CLI positive control "APA" moved CONFIDENT → WEAK.
  `name_part` "organization acronym only" became `ORG_NOT_EXACT`.
- The `verify_cutoffs` dict gains `org_rule`.
- New `VerifyCycle6Tests` (10 methods) covers rule 1 (exact positives, 25
  non-exact negatives, unrelated *not checked*, a person found inside an
  organization, and a 4-route CLI gate), N2, N3, N5 and the help text.

**Method.** Script 14 made the same 106 live calls with the same flags as
cycle 5, and asserted that each new MANIFEST row's `query` is the call's
identifier. `calibrate_verify_cycle6.py`:
- rebuilds every DOI-path verdict, similarity and author status offline
  (0 differences);
- compares them with the cycle-5 live runs;
- re-runs the cross-pairing probe and the 25 acronym probes, plus 15
  collision probes;
- runs a mocked-HTTP CLI gate matrix of **540 cells**: 6 routes × 91 flag
  sets over 15 records. The records are person, DSM-5 organization,
  two-author (person + NBER), no-organization-word (Asian Development
  Bank), N2 union / clearinghouse / parliament, N4 NRC Canada / Ohio, the
  U.S. prefix, CDC, OECD full and bare, and N3 Xu / Muller;
- runs a **mutation check**: the unit suite in-process with each change
  reverted.

OpenAlex spend: $0.0270 (106 rows).

**Results:**
- **Gate matrix.** CONFIDENT appears on exactly the 33 flag sets allowed it
  (198 cells). Nine are genuine person cells. The other 24 are
  organization cells, every one an exact whole-name form: "Full", "The
  Full", "Full (ACR)", "Full [ACR]", "ACR, Full", "Full, ACR", "ACR (Full)",
  "U.S." prefix variants, the hyphen-joined OECD name, and bare "OECD" on a
  record listing "OECD". No other organization cell reaches CONFIDENT: 204
  are WEAK, 24 MISMATCH (fabricated title, or `--first-author` on a later
  author) and 6 NOT FOUND. That includes every N1, N2, N4 and
  non-exact-N5 cell and every bare acronym. There is no stray CONFIDENT
  text.
- **Labeled set, live.** DOI path (C / W / M): match 9 / 35 / 0, mismatch
  0 / 20 / 20, the same as cycle 5. Genuine-as-MISMATCH **0 → 0**.
  Mismatch-as-CONFIDENT **0 → 0** with `--year`; 1 (X40) without it.
  `title:` path: 3 / 7 / 1 / 0 and 0 / 5 / 1 / 5, unchanged.
- **No verdict, author status, numeral check or exit note changed.** The
  set's only organization authors are "Open Science Collaboration", as the
  cited author of X02 and as the listed author of X04 and X31. Those
  matches are either exact or not on the record, so rule 1 does not move
  them. The rules are covered by unit tests and the gate matrix.
- **Cross-pairing.** 6,972 pairs; 197 passes (195 `surname`, 2
  `organization`), the same 197 pairs as cycle 5: 0 new, 0 lost.
- **Acronyms (25 common ones, one record each).**
  - Cycle 5: 19 pass, 5 not checked, 1 ambiguous.
  - Cycle 6: **2 pass, 19 ambiguous, 4 not checked (CDC, UN, UNICEF,
    NAEP), 0 fail.**
  - The 2 passes are "OECD" and "MDRC" on records that list exactly
    "OECD" / "MDRC", which is identity, not an acronym reading.
  - WWC moved *not checked* → *ambiguous*, because "clearinghouse" is now
    an organization word.
  - This is the accepted cost: an acronym-cited organization is WEAK
    until adjudicated.
- **Collision probes.** None pass. Cycle 5 still let the bare "APA"
  (Psychiatric) and "AERA" (Africa) pass; both are now *ambiguous*. The
  N1 reverse forms are *ambiguous*. "Smith (APA)", "Smith (US)" and
  "Smith (NBER)" *fail*. The two-letter cases are *not checked*.
- **Mutation check** (151-test suite; baseline OK). Each reverted change
  failed tests:
  - rule 1 reverted (every non-exact relation passes): 80 failures;
  - no listed name reads as an organization: 12;
  - N2 words removed: 7;
  - the cycle-5 umlaut fold restored: 10;
  - the comma form not read: 11 failures + 1 error.

**Costs, stated.**
- Every organization cited by acronym is WEAK, as is ACT vs "ACT, Inc.",
  RAND vs "RAND Corporation", and "Department of Education" vs a
  state's department. The adjudicator, or until then a human, decides
  these.
- A person whose two-word name holds an organization word ("Jane Board",
  "Steffen Bank"), cited by surname only, is WEAK, not CONFIDENT.
- "Department of Education" passes on "U.S. Department of Education",
  because the user-specified U.S.-prefix normalization treats them as one
  name.
- Organization names that differ only in spelling ("Organization" vs
  "Organisation") get no exact match, so they are at best *not checked*
  (WEAK). This followed from the rule's construction; review cycle 6
  then observed it (`review_scratch/c6_r01_pure_probes.py` log: *not
  checked*), and cycle 7 pins it in a test (below).

**Limits.** In-sample n = 84, with three organization-author items.
Organization matching is now deliberately conservative rather than
complete; its residual WEAK band is the adjudicator's evaluation set,
together with the reviewers' adversarial cases. The deferred items are
unchanged and still pinned as expected failures: the word- or
character-swap guard, meaning-bearing marks, and the independent held-out
validation.

## Measured behavior: verify cycle 5 (2026-10-06)

**Question.** Review cycle 4 found a regression its own fix round had
introduced (M1): a parenthetical acronym overrode a wrong cited name.
`--author "American Psychological Association (APA)"` and `--author "Smith
(APA)"` graded CONFIDENT on an "American Psychiatric Association" record on
all six CLI routes (reviewer log `review_scratch/c4_r02_cli_gate_matrix.py`,
24 CONFIDENT cells in that matrix). It also found two-letter acronym
collisions that passed (L2), ten common acronyms hard-blocked as MISMATCH
(M2), and three smaller gaps (L1, L3). A user-authorized fifth round
(rules `2026-10-06a`, author rule `contiguous-surname-v5`, `numerals-v4`;
tool still `1.1.0-daaf`) changed the rules. Is M1 closed at the CLI, and
what moved on the labeled set?

**What changed** (constants and comments in `scholar_backends/_common.py`):
- **M1.** An acronym is read only when the **whole** cited name is that
  acronym ("OECD", "OECD (2019)"). A parenthetical is never read as the
  cited author's acronym. A cited organization passes only on its full
  name. When the full name is not on the record but its parenthetical
  equals a record organization's initials or name, the result is
  *ambiguous* (`name_part` "organization acronym only"). Otherwise it is
  *not checked*. A parenthetical acronym beside a full name that matched
  only corroborates it: `acronym_corroborates` true / false, informational.
  "Smith (APA)" is now the person Smith: *fail*, so MISMATCH on an APA record.
- **L2.** Acronym matching needs 3–8 letters.
- **M2.** An all-caps 2–8 letter cited name that matched nothing is *not
  checked* (caps WEAK), never *fail*. A person surname that matches nobody
  still fails. `ORG_WORDS` gains plurals (centers, institutes, academies,
  departments, offices, bureaus, councils, …). A leading "U.S." / "United
  States" is read both with and without it for initials ("U.S. Bureau of
  Labor Statistics" → BLS; "U.S. Department of Agriculture" → USDA and DA).
  **Test change, stated:** `VerifyCycle4Tests.test_3`'s negatives "NBER" vs
  "National Center for Education Statistics", "OECD" vs "Oscar Ellis Carl
  Davis" and "OECD" vs "World Bank" moved from *fail* to *not checked*
  (WEAK, never pass or CONFIDENT). The cycle-3 test "Institute of Education
  Sciences (IES)" vs a record listing "IES" moved from *pass* to
  *ambiguous* (M1).
- **L1.** A separate "Mac"/"Mc" that leaves no match is retried without it
  ("Mac Hulbert" vs "M. Hulbert"). The result is *ambiguous* (`name_part`
  "surname without Mc/Mac"), because "Mac" may be a given name.
- **L3, dropped umlaut.** A surname that matches only with ae/oe/ue read as
  a/o/u on both sides ("Mueller" vs "H. Muller", fold `deumlaut`) is
  *ambiguous*: Mueller and Muller are also two distinct names. "Mueller" vs
  "Müller" still passes. *(Cycle 6, N3: the fold now needs a consonant
  before and two letters after, so Xue / Xu and similar pairs fail again.)*
- **L3, part words.** Year and Cohort join them (`numerals-v4`; Wave and
  Round were already there). "Year One" vs "Year Two" in the reviewer's
  probe title (0.979, CONFIDENT under numerals-v3) is now WEAK.
- **L3, contact scrub.** It also matches "[dot]" / "(dot)", the plain words
  " at " / " dot ", and a reference escaped any number of times
  ("&amp;amp;#64;"). It only matches text that reconstructs the configured
  address, so prose is untouched. This is unit-tested with a fake address.

**Method.** Script 12 ran the same 106 live calls with the same flags as
cycle 4. It also asserts each new MANIFEST row's `query` equals the call's
identifier. `calibrate_verify_cycle5.py`:
- rebuilds every DOI-path verdict, similarity and author status offline (0
  differences);
- compares them with the cycle-4 live runs;
- re-runs the cross-pairing probe;
- evaluates 25 acronym probes;
- re-runs the reviewer's CLI gate matrix with mocked HTTP. That matrix is
  192 cells: 6 routes × a person record, the DSM-5 organization record,
  three M1 collision records and a CDC record, with every M1 and L2 cell.

OpenAlex spend: $0.0270 (106 rows).

**Results:**
- **Gate matrix (mocked, offline).** CONFIDENT appears only on the 11
  genuine full-flag cells, × 6 routes = 66. All M1 cells are WEAK (wrong
  full name with an acronym → *ambiguous*) or MISMATCH ("Smith (APA)", "Smith
  (US)" → *fail*) on all six routes. The two-letter "AP" and "US" cells are
  WEAK. No stray CONFIDENT text. EXISTS never appears on a genuine cell.
- **Labeled set, live.** DOI path (C / W / M): match 9 / 35 / 0, mismatch
  0 / 20 / 20, the same as cycle 4. Genuine-as-MISMATCH **0 → 0**.
  Mismatch-as-CONFIDENT **0 → 0** with `--year`; 1 (X40) without it.
  `title:` path: 3 / 7 / 1 / 0 and 0 / 5 / 1 / 5, unchanged.
- **No verdict, author status, numeral check or exit note changed.** The
  set's only organization author is X02 ("Open Science Collaboration"), so
  these fixes are covered by unit tests and the gate matrix, not by the set.
- **Cross-pairing.** 6,972 pairs, 197 passes: 195 `surname`, 2
  `organization`, none from an acronym, a fold, an Mc/Mac retry or the
  dropped umlaut. These are the same 197 pairs as cycle 4: 0 new, 0 lost.
- **Acronyms (25 common ones, one record each).** Cycle 4: 14 pass, 1
  ambiguous, 10 fail. Cycle 5: **19 pass, 5 not checked (CDC, UN, UNICEF,
  WWC, NAEP), 1 ambiguous (RAND), 0 fail.**
- **Collision probes.**
  - *ambiguous:* "American Psychological Association (APA)", "Institute of
    Education Sciences (IES)" and "National Bureau of Economic Research
    (NBER)", each against the other organization;
  - *fail:* "Smith (APA)", "Smith (US)", "Smith (NBER)";
  - *not checked:* "UN" vs "University of Nebraska" / "Nevada", "JB", "LI",
    "WU".
  - Still *pass*: the bare 3+ letter acronyms "APA" (American Psychiatric
    Association) and "AERA" (Association for Education Research in
    Africa). That is the documented limit of reading bare acronyms; the
    title check still applies. *(Cycle 6, D-16: both are now *ambiguous*;
    no bare acronym passes on an organization's full name.)*

**Costs, stated.**
- An all-caps person surname that matches nobody ("LI" against unrelated
  authors) is now *not checked* (WEAK) rather than MISMATCH.
- A spaced "Mc Donald" against a "John Donald" record is *ambiguous*, not
  *fail*.
- A wrong acronym cited for a person-authored record ("NBER") is WEAK, not
  MISMATCH.

**Limits.** In-sample n = 84. The deferred items are unchanged and still
pinned as expected failures: the word- or character-swap guard,
meaning-bearing marks, and the independent held-out validation.

## Measured behavior: verify cycle 4 (2026-10-05)

**Question.** A user-authorized fourth fix round changed the author rule,
the numeral guard, the `title:` tie-break and some wording (rules version
`2026-10-05a`; tool still `1.1.0-daaf`). On the same 84 labeled items and
22 `title:` runs, with the same flags as cycle 3, what moved, and do the
new author rules let wrong authors pass?

**What changed** (constants in `scholar_backends/_common.py`):
- **Author rule `contiguous-surname-v4`.** Each of these was a fail
  (MISMATCH on a genuine citation) in cycle-3 reviewer probes:
  - "Smith 2019" (year without parentheses) and "Smith Ed." / "Eds.":
    all-digit tokens and a trailing editor mark are dropped. Now *pass*.
  - "Al-Hassan" / "Alhassan", "El-Sayed" / "Elsayed": compared with hyphens
    deleted on both sides. Now *pass*.
  - "Mueller" / "Müller": ä/ö/ü spelled ae/oe/ue on both sides; "ß" is now
    "ss" in every comparison (the ASCII fold used to delete it). Now *pass*.
  - "McDonald" / "Mc Donald": "Mc"/"Mac" join the next token like a
    particle. Now *pass*.
  - "von Hippel" / "Paul T. Hippel", "de Souza" / "Maria Souza": a cited
    particle the record drops is *ambiguous* (caps WEAK), not a pass,
    because the bare surname may be another person. "St" is never dropped.
  - "OECD" / "Organisation for Economic Co-operation and Development": an
    all-caps 2–8 letter cited name (or parenthetical) equal to the initials
    of a record name that contains an organization word (of / and / for /
    the / on / in skipped; a hyphenated word read whole and split). Now
    *pass*. *(Review cycle 4 found that reading the parenthetical let a wrong
    full name pass, M1, a regression of this round; cycle 5 reads bare 3–8
    letter acronyms only.)*
  - A cited author with fewer than two words before its first comma is
    read as a person even when a word is an organization word ("Board",
    "Board, Jane"). Before, it was *not checked* even against an
    all-Latin record. A person fallback for multi-word organization names
    was tried and dropped: it let "National Academy of Sciences" pass on
    "Institute of Education Sciences". "Jane Board" against "Board, Jane"
    stays *not checked*.
  - Unchanged and still fail: "Steenbergen-Hu" vs "Xueyan Hu";
    "de la Cruz" vs "Maria Cruz Lopez"; "Al-Hassan" vs "Ahmed Hassan Omar";
    "Mueller" vs a record spelled "Muller" (no umlaut on either side).
    *(Cycle 5: Mueller vs Muller became ambiguous; cycle 6 keeps that and
    restricts the fold to consonant + ae/oe/ue + two letters.)*
  - The mixed-script rule is unchanged: *not checked* when **any** record
    author name has no Latin-script letters and the cited surname matched
    no one. The `reason` text now says exactly that.
- **Numeral guard `numerals-v3`.** Part words are now Part, Volume, Vol,
  Book, Chapter, Study, Phase, Wave, Title, Section, Stage, Round,
  Experiment, Grade and Level. Spelled-out one–twenty and first–twentieth
  count after a part word, with only spaces between ("Part Two" = 2). A
  segment-closing "I" after an auxiliary verb (am, was, can, do, should …)
  is the pronoun, so "Who Am I:" vs "Who Am I?" is CONFIDENT, not WEAK;
  "Teachers I:" still counts. Reviewer probes that were CONFIDENT and are
  now WEAK: "Phase I"/"Phase V", "Wave I"/"Wave V", "Title I"/"Title V",
  "Part One"/"Part Two". "Grade 3" vs "Grade three" moved WEAK → CONFIDENT.
  Still not covered: spelled-out numbers away from a part word, and digits
  glued to CJK text ("2018年").
- **`title:` tie-break.** Same-titled candidates now rank by author pass,
  then year, then citations. An author failure is MISMATCH and a year gap
  only WEAK, so author goes first. Reviewer repro: `--author Lee --year 2002`,
  Lee's record 2005, a more-cited Hanushek record 2002. Cycle 3 picked
  Hanushek (MISMATCH, exit 11); cycle 4 picks Lee (WEAK: the year differs).
- **ID-path MISMATCH wording.** This now branches like the `title:` path.
  A title that passed with an author that failed reads "the title matches
  but the cited author is not on this record". The MANIFEST `note` reads
  "the cited author is not on the record the title matched", on both paths.
  With no title checked, the digest asks for a re-run with `--title`. A
  title failure keeps "resolves to a different work".
- **Contact scrub.** It now also matches `@`, `&#43;` / `&#x2B;`,
  double-escaped `&amp;#64;`, and `[at]` / `(at)` with optional spaces.
  This is unit-tested with a fake address.

**Method.** Script 10 ran every item with `verify <DOI> --title --author
--year`, and the 22 `title:` items with `--author --year`, the same flags as
cycle 3. `calibrate_verify_cycle4.py`:
- joins each run to its own MANIFEST row;
- rebuilds all 84 DOI-path verdicts, similarities **and author statuses**
  offline from the production functions and the digest's author list (0
  differences);
- compares them with the cycle-3 live runs.
OpenAlex spend: $0.0270 (106 rows).

**Results, live:**
- DOI path (C / W / M): match 9 / 35 / 0 and mismatch 0 / 20 / 20, the same
  as cycle 3. Offline: title only, mismatch 1 / 30 / 9 (X40); title + year,
  0 / 31 / 9.
- Genuine-as-MISMATCH **0 → 0**. Mismatch-as-CONFIDENT **0 → 0** with
  `--year`; 1 (X40) without it.
- **No verdict, author status, numeral check, `title:` candidate or exit
  note changed** on either path. No labeled item uses a form the new rules
  touch, so the fixes are covered by unit tests, not by this set.
- `title:` path (genuine / fabricated, C / W / M / NF): 3 / 7 / 1 / 0 and
  0 / 5 / 1 / 5, the same as cycle 3.
- W-B: 0 of 106 runs printed CONFIDENT under a non-CONFIDENT verdict.

**False-pass risk of the new author rules (offline cross-pairing).** Every
item's cited author was checked against every *other* item's record author
list: 6,972 pairs. There were 197 passes, all from the v3 rules. Many pairs
share a record, because mismatch items reuse the match items' DOIs. **0
passes came from a cycle-4 fold or acronym.** Only 2 record authors in the
set are organizations with readable initials, so the acronym rule's risk
is barely sampled. The residual risk is a cited acronym that equals another
organization's initials. Review cycle 4 then **observed** it in a reviewer
probe: "UN" vs "University of Nevada" passed. Cycle 5 closed two-letter
acronyms (L2), so that pair is now *not checked*. The title check still
applies to any acronym pass.

**Limits.** In-sample n = 84, the same as cycle 3; the deferred items
(word- or character-level swap guard, meaning-bearing marks, held-out
validation) are unchanged and still pinned as expected failures.

## Measured behavior: verify cycle 3 (2026-10-03)

**Question.** Review-fix cycle 3 changed the numeral guard, the author rule
and some output wording (rules version `2026-10-03c`; tool still
`1.1.0-daaf`). On the same 84 labeled items and 22 `title:` runs, with the
same flags as cycle 2, what moved?

**What changed** (constants in `scholar_backends/_common.py`):
- **Numeral guard `numerals-v2` (W-A).** Ordinals and decades count by their
  number ("21st" = 21, "3rd" = 3, "1980s" = 1980). Decimal digits of any
  script count ("٢٠١٨" = 2018). I / V / X count directly after Part,
  Volume, Vol, Book, Chapter or Study anywhere in a title, as well as at
  the end of a segment. Before, "21st" vs "20th", "3rd" vs "4th", "1980s"
  vs "1990s", Arabic-Indic 2018 vs 2019 and a mid-title "Part I" vs "Part
  V" all graded CONFIDENT (reviewer probes, 0.962–0.987). They are now WEAK.
  Not covered: spelled-out numbers, and digits glued to unspaced CJK text
  ("2018年").
- **The word CONFIDENT (W-B).** `openalex.get_work`'s title-lookup note,
  which `verify` and `work` embed, now reads "close title match" or "not a
  close title match — check it manually". Before, a `title:` MISMATCH or
  WEAK printed "(CONFIDENT MATCH)" in stdout and in the digest.
- **Author rule `contiguous-surname-v3` (W-C, I-D).** Four outcomes that
  used to be fail (MISMATCH on a genuine citation) change:
  - nothing matched and a record name has no Latin-script letters ("王 伟",
    "Иван Петров"): *not checked*;
  - a cited organization (a word such as Institute, Collaboration or
    Organization) is compared by its whole name or a parenthetical
    acronym, never by its last word. When it is not on the record, it is
    *not checked*;
  - particles may be spaced or joined ("de la Cruz" = "Dela Cruz");
  - the same names in another order ("Di Wu" vs "Wu Di") give *ambiguous*.
  In addition, "Xiaoming LI" no longer loses "LI" as Vancouver initials when
  "Li" is the record's surname, and a parenthetical ("Smith (2019)") is
  dropped before the surname is read.
- **Wording and ranking.** A `title:` MISMATCH whose title check passed and
  whose author failed now says "the title matches but the cited author is
  not on this record" (I-B). On `title:`, among equal title scores, a
  candidate that passes `--author` now ranks after the year check and
  before citation count (I-C). The contact-email scrub also matches `&#64;`,
  `&#x40;` and `&commat;` (I-E). A `title:` NOT FOUND names, on stdout, any
  backend that did not answer (I-F).

**Method.** Script 08 ran every item with `verify <DOI> --title --author
--year` and the 22 `title:` items with `--author --year`, the same flags
as cycle 2. The 4 EXISTS probes were not repeated; the EXISTS routes are
unit-tested. The analysis (`calibrate_verify_cycle3.py`):
- joins each run to its own MANIFEST row;
- rebuilds all 84 DOI-path verdicts and similarities offline from the
  production functions (0 differences);
- compares them with the cycle-2 live runs.
OpenAlex spend: $0.0270 (106 rows).

**DOI path, live** (C / W / M):

| Scope | Grading | match | mismatch |
|---|---|---|---|
| all 84 | cycle 2 (live) | 9 / 35 / 0 | 0 / 20 / 20 |
| all 84 | cycle 3 (live) | 9 / 35 / 0 | 0 / 20 / 20 |
| 83 title-separable | cycle 3, title only (offline) | 9 / 35 / 0 | 0 / 30 / 9 |
| all 84 | cycle 3, title only (offline) | 9 / 35 / 0 | **1** / 30 / 9 |
| all 84 | cycle 3, title + year (offline) | 9 / 35 / 0 | 0 / 31 / 9 |

- Genuine-as-MISMATCH **0 → 0**; mismatch-as-CONFIDENT **0 → 0** with
  `--year`. Without the year the count is 1 (X40, the Cochrane update), so
  "0 of 40" depends on the year check.
- **No verdict changed** on either path.
- **Author status changed on 1 item: X02** ("Open Science Collaboration",
  a mismatch), from fail to *not checked*, under the organization rule.
  Its title (0.192) still makes it MISMATCH. This is the rule's cost: when
  a cited organization is not on the record, the author check no longer
  flags the citation, and the title check must.
- **Numeral check changed on 1 item: M29** (genuine). The record's "2nd"
  now counts, so the numbers differ. The score is 0.758, so this is
  informational only and the verdict stays WEAK. The guard still fires
  only on M37 among the 84 items.
- **W-B, live:** 0 of 106 runs printed CONFIDENT on stdout or in the digest
  under a non-CONFIDENT verdict.
- `retracted` appears on 101 of 106 rows: every row where a record
  resolved. The 5 without it are the NOT FOUND runs.

**`title:` path, live** (genuine / fabricated, C / W / M / NF): cycle 2
3 / 7 / 1 / 0 and 0 / 5 / 1 / 5; cycle 3 the same. No candidate choice
changed: the author tie-break decided nothing in this set (inference: no
run's `verified_by` or similarity moved). It is covered by a unit test
(an identical-title "Lee (2002)" vs a more-cited "Hanushek").

**Measured extent of the deferred minimal-edit limit (W-D; the
reviewer's probes, pinned in `test_wd_measured_extent_of_the_known_limits`):**
- One word swapped ("Reading" → "Math"): 0.944 (WEAK) at 12 words / 82
  characters, then **0.951 CONFIDENT at 14 words / 93 characters**, rising
  to 0.976 at 28 words.
- An inserted "No " before a 28-word title: **0.992**.
- Chinese: one character swapped (小学 → 中学, 27 characters) **0.963**; a
  negation (有 → 无) **0.955**. Japanese: one kanji swapped **0.957**. A
  19-character Chinese swap stays below the cutoff (0.944).
- Each is pinned as an expected failure, so a future content-token guard
  flips it.

**Meaning-bearing marks (I-A): documented, not changed.** Probe
`probe_cycle3_meaning_marks.py` kept Unicode Sm symbols, a leading minus
and a percent sign in the verify normalization. `<` vs `>` then scores
0.980 (was 1.000) and "-10%" vs "10%" 0.979 (was 1.000): both still
CONFIDENT. So the change alone would not fix the verdict. It needs the
deferred content-token guard. Vietnamese tone marks and año / ano sit on
Latin letters, which the normalization folds by design (genuine citations
rely on it). The variant moved 0 of the 84 labeled scores.

**Limits (unchanged).** In-sample n = 84, the same as cycle 2. The fixture
has no ordinal, decade, non-Latin-author or organization-not-on-record
genuine item, so W-A and W-C are covered by unit tests, not by the labeled
set.

## Measured behavior: verify cycle 2 (2026-10-03)

**Question.** The review-fix cycle changed how `verify` normalizes and
grades (rules version `2026-10-03b`, tool `1.1.0-daaf`). On the same 84
labeled items, run through the live CLI, what moved?

**What changed** (constants in `scholar_backends/_common.py`; all stamped in
every verify row's `verify_cutoffs`, failure rows included):
- **EXISTS (user decision D1).** An ID with no `--title` grades EXISTS
  (exit 0, stderr hint), never CONFIDENT; `--author` alone can still give
  MISMATCH. CONFIDENT requires a passing title check.
- **Verify normalization `nfkc-casefold-v1` (B1/B2).** `verify_title_norm`:
  NFKC, casefold, Latin diacritics folded, punctuation/symbols to spaces,
  any script kept, **no truncation**; difflib with `autojunk=False`. Either
  title under `VERIFY_MIN_TITLE_LETTERS = 3` letters is WEAK at best; a
  punctuation-only cited title is a usage error. `norm_title` (160-char ASCII
  fold) stays the merge/fusion key. Before: two different CJK or Cyrillic
  titles scored 1.00 (both folded to ""), and titles differing only after
  character 160 scored 1.00.
- **Numeral guard `numerals-v1` (D2).** Standalone digits, Roman II–XX, and
  I/V/X closing a title segment must match (as values) for CONFIDENT;
  otherwise WEAK. The single-letter rule keeps the pronoun ("What I
  Learned"), "Brown v. Board", "X-ray" and an index glitch ("Intergenerational
  I ncome") out. Rows record `numeral_check` whenever the numbers differ
  (informational); it changes the verdict only at a CONFIDENT-level score.
- **Author rule `contiguous-surname-v2` (W3).** Strips "et al." / "and
  others" / co-author tails, Jr/Sr/II–IV and Vancouver initials ("Smith
  JA"). New outcomes: *unchecked* (no surname read, or no record authors) and
  *ambiguous* (the match is a given or middle name, e.g. "Kirabo"); both cap
  at WEAK, never MISMATCH. Before: "Smith et al." read as surname "al",
  "Fryer Jr." as "jr", "Smith JA" as "ja", and an author-less record gave
  MISMATCH.
- **`title:` path (B3).** `--author` / `--first-author` apply to the chosen
  candidate (a failure is MISMATCH); `--title` is refused.
- Rows also carry `retracted` / `retracted_by` (W5) and, when a backend
  failed, `unanswered_backends` (I4).

**Method.** Script 06 ran every item `verify <DOI> --title --author --year`,
the 22 `title:` items with `--author --year`, and 4 EXISTS probes. The
analysis (`calibrate_verify_cycle2_a.py`) joins each run to its own MANIFEST
row, rebuilds all 84 DOI-path verdicts and similarities offline from the
production functions (0 differences), and compares with the R1–R4 live runs.
OpenAlex spend: $0.0270 (110 rows).

**DOI path, live** (C / W / M):

| Scope | Grading | match | mismatch |
|---|---|---|---|
| all 84 | R1–R4 (2026-10-03 live) | 12 / 32 / 0 | 0 / 19 / 21 |
| all 84 | cycle 2 (live) | 9 / 35 / 0 | 0 / 20 / 20 |
| 83 title-separable | cycle 2, title only (offline) | 9 / 35 / 0 | 0 / 30 / 9 |
| all 84 | cycle 2, title + year (offline) | 9 / 35 / 0 | 0 / 31 / 9 |

- Genuine-as-MISMATCH **0 → 0**; mismatch-as-CONFIDENT **0 → 0** with
  `--year`. The Cochrane-update item X40 needs the year check: title only,
  1 of 40.
- Four verdicts moved, all toward WEAK. M30 and M32 (genuine truncated
  citations) lost CONFIDENT because the 160-char truncation had hidden the
  record's subtitle (1.000 → 0.902, 0.987 → 0.945). M37 (genuine) lost it to
  the numeral guard (cited without the record's part number "I", 0.982).
  X21 (same-author other paper) moved MISMATCH → WEAK: untruncated it
  scores 0.479 (was 0.444), above the 0.45 MISMATCH cutoff; it stays
  uncitable.
- **Long titles** (9 records over 160 normalized characters; old → new
  full-title score): M22 1.000 → 1.000, M26 1.000 → 1.000, M27 0.994 →
  0.994, M28 0.944 → 0.733, M29 0.926 → 0.758, M30 1.000 → 0.902, M31 0.815
  → 0.746, M32 0.987 → 0.945, X21 0.444 → 0.479.
- **D2 guard:** numbers differ on 8 genuine items (M07, M08, M09, M10 report
  numbers; M14, M15 "II"; M21 "2"; M37 "I") and 10 mismatches. It fired
  (demoted a CONFIDENT-level score) on **1 genuine item, M37**, and on no
  mismatch, since no mismatch reached 0.95. M37 is a strict false flag: the
  subtitle identifies part I, but the citation omits the part number; the
  rule was kept as decided, not loosened.
- **Author check:** no outcome changed on the 84 items (genuine 44 pass;
  mismatches 17 fail, 23 pass). The fixture has no "et al.", suffix or
  initials forms, so W3 is covered by unit tests only.

**`title:` path, live** (genuine / fabricated, C / W / M / NF):
R1–R4: 4 / 7 / 0 / 0 and 0 / 6 / 0 / 5. Cycle 2: 3 / 7 / **1** / 0 and
0 / 5 / **1** / 5.
- M37: CONFIDENT → WEAK (numeral guard).
- **M41 (genuine) → MISMATCH**, forced by B3. "Deep Residual Learning for
  Image Classification" resolves to a different paper (0.803), which lacks
  "He". The candidate *is* a different work; the citation is a garbled real
  title. The digest says so and points to `find`.
- X34 (fabricated) → MISMATCH (B3, same mechanism).

**EXISTS probes, live:** M01 and X01 by DOI only → EXISTS (exit 0, stderr
hint). X01's DOI belongs to a mismatched citation, so EXISTS vets nothing.
M01 with `--author` → EXISTS. X13 with `--author Steenbergen-Hu` → MISMATCH
(exit 11).

**Not fixed (known limit, deferred by decision D2):** a one-word swap
still clears 0.95, and not only in long titles. Measured: 165-char shared
prefix, "Boston" vs "Tulsa" = 0.975 untruncated
(`scratch/probe_cycle2_scorer_design.py`); "Reading" vs "Math" in a
136-char title = 0.965 (orchestrator adjudication, pre-cycle-2 scorer;
inference: unchanged, as that title is ASCII and under 160 characters).
A unit test records the first as an expected failure, to flip when a
content-token guard lands after the held-out validation. Cycle 3 measured
how far the limit reaches (see the cycle 3 entry above). It starts at
about 14 words / 90 characters (0.951). An inserted "No " scores 0.992.
In Chinese or Japanese, a one-character swap or negation is CONFIDENT
from about 20 characters.

**Limits.** In-sample: n = 84 (22 on `title:`), the mismatches and garbles
partly model-authored, with the same agent family writing the rules and the
labels. Zero mismatch-as-CONFIDENT in 39 title-separable mismatches bounds
the true rate at about 7.7% (rule of three, 3/39, 95% upper bound), for
titles distributed like these only. Independent held-out validation (≥ 50
mismatches, minimal edits, sequels, long and non-Latin titles, reference-list
author forms, real LLM bibliographies) is scheduled before Literature Review
mode depends on `verify`.

## Measured behavior: verify R1–R4 (2026-10-03)

**Question.** The user approved the four report-only recommendations of the
2026-10-02 calibration (below). Implemented, do they deliver the measured
gains on the same labeled items, through the live CLI?

**What changed** (constants in `scholar_backends/_common.py` § VERIFY_CUTOFFS;
every `verify` MANIFEST row now carries them in `verify_cutoffs`, plus
`title_similarity_subtitle_aware`, `author_check`, `year_check` and, for a
below-floor NOT FOUND, `nearest_candidate`):
- **R1, scorer `hybrid-v1`.** CONFIDENT is still decided by the difflib
  full-title score (≥ 0.95). MISMATCH (`--title` on an ID) is decided by the
  subtitle-aware score: max(full, main title before the first colon on BOTH
  sides), the 2026-10-02 `alt_subtitle` definition (< 0.45). Rows from
  before 2026-10-03 have no `scorer` key.
- **R2, `VERIFY_TITLE_SEARCH_FLOOR = 0.70`.** On `verify title:"…"`, a best
  candidate below 0.70 is NOT FOUND (exit 11), and the digest lists it under
  "Nearest works by title (not matches)". The score is the full-title score of
  the best OpenAlex, then Crossref, candidate, the one the 2026-10-02 floor
  sweep used.
- **R3, author rule `contiguous-surname-v1`.** The cited surname (forms:
  "Surname", "Surname, First", "First Surname", "F. Surname", particle-led
  "van der Klaauw", hyphenated) must appear as a contiguous token sequence
  inside ONE listed author's name. Normalization: NFC, apostrophes deleted,
  other punctuation (hyphens included) a token break, NFKD ASCII fold.
  `--first-author` restricts the match to the first author.
- **R4, `--year`, `VERIFY_YEAR_TOLERANCE = 1`.** A gap over ±1 turns
  CONFIDENT into WEAK, never MISMATCH. On `title:"…"`, the year also breaks
  exact similarity ties between candidates (before citation count).

**Method.** Script 03 added `claimed_year` and `record_year` to all 84 fixture
items from the OpenAlex sourcing records. The claimed year is the year of the
work the claimed title comes from (version pairs, other papers, X40's 2013
original review); otherwise the record's own year, which is also what
fabricated items get, the worst case for the year check. Script 04 ran every item
through the CLI (`verify <DOI> --title --author --year`; the 22 `title:` items
with `--year`). The analysis joins each run to its own MANIFEST row and
digest and checks four things:
- all 84 full-title similarities equal the 2026-10-02 live values;
- the subtitle-aware scores equal the 2026-10-02 `alt_subtitle` values;
- record years equal the fixture's;
- every live verdict is rebuilt offline from the row's own measurements.
The 0 differences on each check are in the script log. "Before" is the
production grading of 2026-10-02 (0.95 / 0.45, full-title score,
last-token-anywhere author rule, no year), reconstructed by
`calibrate_verify_cutoffs.py`. OpenAlex spend: $0.0270 (106 rows; DOI
lookups free, title searches and NOT FOUND semantic searches $0.001 each).

**Confusion tables, DOI path** (rows = truth, C / W / M; same items):

| Scope | Grading | match | mismatch |
|---|---|---|---|
| 83 title-separable | before: title only | 12 / 29 / **3** | 0 / 28 / 11 |
| 83 title-separable | before: title + author | 12 / 29 / **3** | 0 / 18 / 21 |
| 83 title-separable | after R1: title only | 12 / 32 / **0** | 0 / 29 / 10 |
| 83 title-separable | after R1+R3+R4 (live) | 12 / 32 / **0** | 0 / 18 / 21 |
| all 84 | before: title + author | 12 / 29 / 3 | **1** / 18 / 21 |
| all 84 | after R1+R3+R4 (live) | 12 / 32 / 0 | **0** / 19 / 21 |

- **Genuine-as-MISMATCH: 3 → 0** (M04 "Look Closer to See Better", M18
  "False-Positive Psychology", M21 "Pervasive Attention: 2"; all now WEAK).
- **Mismatch-as-CONFIDENT: 0 → 0** on the 83 title-separable items; **1 → 0**
  on all 84, because X40 (the 2013 Cochrane review cited with its 2021
  update's DOI, title similarity 1.00) now grades **WEAK** with
  `--year 2013` ("year differs (cited 2013, record 2021)").
- **Cost of R1:** one mismatch moved MISMATCH → WEAK on the title-only grade
  (X25, a same-author other paper, full 0.414, subtitle-aware 0.481). With
  the author check, R3 caught X13 instead, so mismatches graded MISMATCH stay
  at 21 of 39, a different 21. Both stay uncitable.
- The year check changed no genuine verdict. The 6 genuine items whose
  cited year differs (all real version pairs, gaps 2–4 years) were already
  WEAK on the title.

**Author check (R3), before → after** (same record author lists; replaying the
old rule on them reproduces every 2026-10-02 `author_found`):
- False flags on the 44 genuine items: **0 → 0**.
- False passes, i.e. the check passed on a different person's partial name
  (the matched author's name does not end with the whole cited surname):
  **1 → 0**. The one was X13: "Steenbergen-Hu" had matched "Xueyan Hu".
- Mismatches whose surname was not found: 16 → 17 of 40.
- 23 mismatch items still pass the author check, all on the right person:
  - 21 same-author papers and fabrications carry the DOI's real first author;
  - X40's Dobbins is author 3 of the update;
  - "Fu" (X16) is a real co-author (author 2) of the other paper.
  The author check cannot catch these; the title and year checks do.
- `--first-author`, derived offline from `author_check.position` (not run
  live): 0 genuine items would be flagged (every genuine citation named the
  first author), and 2 more mismatches would read MISMATCH (X16, and X40
  where Dobbins is author 3 of the update).

**Year tolerance (R4).** Measured |cited − record| on genuine items: 0 for 38,
2 for 1, 3 for 4, 4 for 1. All the non-zero gaps are working-paper vs
journal pairs. Sweeping the tolerance from 0 to 5:
- No genuine item with a CONFIDENT title grade is downgraded at any
  tolerance in that range.
- X40 (gap 8) is caught at every tolerance in that range.
- Genuine items carrying a year flag (all already WEAK on the title):
  0 → 6, ±1 → 6, ±2 → 5, ±3 → 1, ±4 → 0.

So the data do not separate ±1 from the alternatives, and ±1 was kept as
decided. Supporting observation: one DOI (10.1086/705882) is 2019 in OpenAlex
and 2020 in Crossref (M34's `title:` run). That is an online-first vs issue
gap of exactly one year, which a tolerance of 0 would flag.

**`title:` path (R2 + R4)**, 11 genuine / 11 fabricated, C / W / M / NF:
- Before (0.95, no floor): genuine 4 / 7 / 0 / 0; fabricated 0 / 11 / 0 / 0.
- After: genuine 4 / 7 / 0 / 0; fabricated 0 / 6 / 0 / **5**.
- **5 of 11 fabricated → NOT FOUND, 0 of 11 genuine** (X28, X30, X31, X32,
  X33; best similarity 0.507–0.627). Margin from the floor to the lowest
  genuine title: 0.059 (M06, 0.759). Best similarities equal the 2026-10-02
  values for all 22 runs.
- The 6 fabricated titles still WEAK scored 0.728–0.882 and include the
  real paper they imitate (Fryer w23792, Chetty Teachers I, Ritter 2009,
  Angrist w5888).
- `--year` flagged 4 of those 6 (cited year ≠ candidate's) and the genuine
  M41, which resolved to a different paper ("Deep Residual Learning for Image
  Classification" → a 2020 paper). None changed grade, since all were WEAK.
- The year tie-break never decided a candidate in this set (inference: no
  live run's similarity or verdict depended on it; it is covered by a unit
  test).

**Limits (unchanged).** n = 84 (22 on the `title:` path) is small; the 0.70
floor's 0.059 margin rests on 11 genuine titles. Same-author papers and
fabrications that borrow the real first author (21 of 40 mismatches here)
pass every author check, `--first-author` included, by design.

## Measured behavior: verify cutoff calibration (2026-10-02)

**Question.** Which `title_similarity` cutoffs should grade `verify`, given the
user's priority order: (1) a wrong or fabricated citation must not pass as
CONFIDENT; (2) keep false flags on genuine citations acceptable?

**Method.** Eight `find` calls (tutoring, teacher value-added, minimum wage,
neighborhood effects, school physical-activity trials, replication in
psychology, class size / school spending, attention / residual networks)
returned 373 OpenAlex works. From them, 84 labeled triples (DOI, claimed
title, claimed author) were authored. Every DOI, record title and
"real" claimed title traces to a sourcing record (`02_run…` asserts this
before any call). Each item ran through the live CLI: `verify <DOI> DEST
--title … --author …`, and 22 of them also ran as `verify title:"…"`. The
analysis joins the labels to each run's own MANIFEST row and digest. It
reproduces every live verdict at 0.90 / 0.60 and every `title_similarity`
offline from the fixture (0 differences), then re-grades the set at other
cutoffs. Scorer: difflib `SequenceMatcher` on `norm_title` (160-char
truncation); 9 record titles exceed 160 characters.

**Set composition.** Match (44): dropped_subtitle 6, report_suffix 5,
case_punct_diacritic 6 and truncated 6 (all `mechanical`);
real_version_pair 10 (`real-version-pair`: NBER vs journal renames, a
record indexed without its subtitle, index glitches such as "I ncome" and
"Pervasive Attention: 2"); llm_garbled 11 (`model-authored`). Mismatch (40):
different_real_paper 6, same_topic_near_title 11 and
same_author_other_paper 10 (`real-other-paper`); fabricated 12
(`model-authored`; 11 carry the DOI's real first author); plus 1
identical_title_other_work (a 2013 Cochrane review cited with its 2021
update's DOI). The last item is reported separately: no title metric can
separate it.

**Distributions** (`title_similarity`, DOI path; min / q25 / median / q75 / max, n):

| Class / subtype | min | q25 | median | q75 | max | n |
|---|---|---|---|---|---|---|
| match (all) | 0.338 | 0.784 | 0.883 | 0.982 | 1.0 | 44 |
| mismatch (all) | 0.192 | 0.444 | 0.665 | 0.792 | 1.0 | 40 |
| match dropped_subtitle | 0.373 | 0.588 | 0.726 | 0.759 | 0.784 | 6 |
| match report_suffix | 0.766 | 0.852 | 0.857 | 0.881 | 0.896 | 5 |
| match llm_garbled | 0.8 | 0.857 | 0.881 | 0.982 | 0.987 | 11 |
| match real_version_pair | 0.338 | 0.5 | 0.904 | 0.914 | 0.991 | 10 |
| match truncated | 0.753 | 0.815 | 0.935 | 0.987 | 1.0 | 6 |
| match case_punct_diacritic | 0.994 | 0.996 | 0.998 | 1.0 | 1.0 | 6 |
| mismatch different_real_paper | 0.192 | 0.231 | 0.285 | 0.317 | 0.343 | 6 |
| mismatch fabricated | 0.476 | 0.627 | 0.7215 | 0.809 | 0.857 | 12 |
| mismatch same_author_other_paper | 0.231 | 0.326 | 0.487 | 0.713 | 0.901 | 10 |
| mismatch same_topic_near_title | 0.592 | 0.682 | 0.755 | 0.827 | 0.917 | 11 |
| mismatch identical_title_other_work | 1.0 | | | | 1.0 | 1 |

The highest-scoring mismatches were near-identical templated titles:
"The Effects of the Minimum Wage on Employment and Wages" against "The effect
of the minimum wage on employment and hours" (0.917, different authors), and
Steenbergen-Hu's college-students vs K–12 ITS meta-analyses (0.901, same
author).

**Confusion tables** (83 title-separable items; rows = truth, columns = verdict):

| Cutoffs | Grading | match C / W / M | mismatch C / W / M |
|---|---|---|---|
| old 0.90 / 0.60 | title only | 20 / 18 / 6 | **2** / 21 / 16 |
| old 0.90 / 0.60 | title + author (live verdicts) | 20 / 18 / 6 | **1** / 13 / 25 |
| **new 0.95 / 0.45** | title only | 12 / 29 / 3 | **0** / 28 / 11 |
| **new 0.95 / 0.45** | title + author | 12 / 29 / 3 | **0** / 18 / 21 |

The identical-title item grades CONFIDENT under both (similarity 1.00, author found).

**CONFIDENT sweep** (mismatches CONFIDENT title-only / with author; matches CONFIDENT of 44):
0.85: 3 / 2 / 29 · 0.88: 2 / 1 / 24 · 0.90: 2 / 1 / 20 · 0.91: 1 / 0 / 16 ·
0.92: 0 / 0 / 15 · 0.93–0.94: 0 / 0 / 13 · 0.95–0.98: 0 / 0 / 12 ·
0.99: 0 / 0 / 8 · 1.00: 0 / 0 / 4.

**Chosen: `VERIFY_CONFIDENT_MIN = 0.95`.** It is the smallest round cutoff
with zero mismatch passes and a margin above the highest mismatch. The
nearest mismatch (0.917) sits **0.033** below it; with `--author`, the nearest
mismatch that passes the author check (0.901) sits 0.049 below. The sweep
grades the set identically at 0.95, 0.96, 0.97 and 0.98, so 0.95 costs no
recall against them. Against 0.93 it gives up one truncated title (0.944) for
2.5× the margin. Honest margin: 0 passes in 39 title-separable
mismatches bounds the true pass rate at about 7.7% (rule of three, 3/39,
95% upper bound), for this distribution of titles only; the calibration is
in-sample. Same-template titles that differ in one content word are the
risk. Genuine citations flagged WEAK or MISMATCH: 73% of this stress set,
by construction mostly hard variants. The 12 genuine items graded
CONFIDENT all scored ≥ 0.982; the cosmetic variants (case, punctuation,
diacritics, spelling) scored ≥ 0.994.

**MISMATCH sweep** (title only; matches graded MISMATCH / mismatches graded MISMATCH):
0.30: 0 / 5 · 0.35: 1 / 9 · 0.40: 3 / 9 · 0.45: 3 / 11 · 0.50: 3 / 12 ·
0.55: 4 / 13 · 0.60: 6 / 16 · 0.70: 6 / 22.

**Chosen: `VERIFY_MISMATCH_BELOW = 0.45`.** It halves the genuine citations
hard-flagged as MISMATCH (6 → 3 of 44). All six were subtitle asymmetries:
a claimed title that drops the record's subtitle, or a record indexed
without the cited one. The 5 mismatches it moves from MISMATCH to WEAK stay
uncitable. 0.45 sits 0.05 below a genuine pair at exactly 0.500
("Minimum Wages and Employment" vs its 84-character working-paper title),
so 0.50 was rejected as borderline. The 3 genuine items still below 0.45
(0.338, 0.373, 0.385) are short main titles of long records. Only a
different scorer fixes them (below).

**`--author` contribution.** The claimed surname was not found for 16 of 39
mismatches: all 6 different_real_paper, 9 of 11 same_topic_near_title and 1
of 12 fabricated (11 fabricated items borrowed the real author). At the old
cutoffs it caught 1 title-only CONFIDENT pass and moved 8 WEAK to MISMATCH.
At the new cutoffs it catches no CONFIDENT pass, because none remain, and
moves 10 WEAK to MISMATCH. It raised no false flags on the 44 genuine items
("Llargues" matched "Llargués"). It cannot catch a same-author mix-up. Its
surname-anywhere semantics also passed two different papers: "Fu" is a real
co-author of the other paper, and "Steenbergen-Hu" passed because its last
token "hu" matched a co-author "Xueyan Hu".

**Alternative scorers (offline, report-only; production scorer unchanged).**

| Scorer | AUC | max mismatch | matches above it | matches CONFIDENT at max + 0.03 | match / mismatch below 0.45 |
|---|---|---|---|---|---|
| production (difflib full title) | 0.836 | 0.917 | 15 | 12 (at 0.947) | 3 / 11 |
| subtitle-aware: max(full, main-before-colon) | 0.925 | **1.0** | 0 | — | **0** / 10 |
| token-set Jaccard (content words) | 0.881 | 0.8 | 16 | 14 (at 0.83) | 5 / 24 |

The subtitle-aware score rescues every subtitle asymmetry: genuine minimum
0.857, no genuine item below 0.45. It must never decide CONFIDENT, though. A
fabrication that keeps the real main title and invents a subtitle scores
1.00 ("Online Tutoring by College Volunteers: Evidence from a Statewide
Randomized Trial in Texas"; "Not Too Late: Mentoring Programs and …"), and
sequels score 0.986–0.992 ("…Teachers I" vs "…Teachers II"). Token-set
Jaccard separates slightly better than difflib at the top but hard-flags 5
genuine items.

**`title:` path** (11 genuine, 11 fabricated; never MISMATCH by design).
- Fabricated: 11 of 11 came back WEAK via Crossref, none CONFIDENT and none
  NOT FOUND, with best similarity 0.507–0.882. At least four landed on the
  real paper they imitated (Fryer w23792, Angrist w5888, Ritter 2009, Chetty
  Teachers I; per-run DOIs in the script log).
- Genuine: CONFIDENT on the right paper 6 of 11 at 0.90 and 4 of 11 at 0.95.
  "Deep Residual Learning for Image Classification" resolved to a different
  paper (WEAK, 0.803).
- NOT FOUND floor sweep (fabricated / genuine sent to NOT FOUND): 0.60: 3 / 0
  · 0.65: 5 / 0 · 0.70: 5 / 0 · 0.75: 6 / 0 (genuine minimum 0.759) · 0.80:
  7 / 2.

**`TITLE_MATCH_MIN` (0.90, version-sibling matching): unchanged, but note.**
The same-author pair at 0.901 would pass it. That cutoff gates fulltext's
other-version lookup (also filtered to `title.search` hits with cached text)
and the ERIC `oa` leg (an exact-phrase search), where candidates are
pre-filtered, so it was left as is. Revisit if a wrong sibling is ever
observed.

**Report-only recommendations (user decisions; items 1–4 approved and
implemented 2026-10-03, see "Measured behavior: verify R1–R4" above).**
1. A `title:` floor: best similarity below **0.70** reads NOT FOUND instead of
   WEAK. On this set that converts 5 of 11 fabricated titles and 0 of 11
   genuine ones, a 0.059 margin to the lowest genuine match (n = 22, small).
2. Hybrid scorer: keep difflib on the full title for CONFIDENT. Decide
   MISMATCH on the subtitle-aware score (< 0.45). On this set that would give
   0 genuine items hard-flagged instead of 3, at 10 vs 11 mismatches flagged.
3. `--author`: match the full normalized surname (all its tokens, e.g.
   "steenbergen hu") as a contiguous sequence in one author's name, not its
   last token anywhere. Optionally add `--first-author` for a strict check.
4. A `--year` cross-check: the only signal that separates
   identical-title versions (the Cochrane update case).
5. Re-run the calibration (`02_run…` + `calibrate_verify_cutoffs.py`) after any
   scorer or `norm_title` change. The regression test
   `VerifyCalibrationTests` pins the confusion table.

## 2026-10-02 (later) — Unpaywall, live via the CLI

First live Unpaywall calls, after the user set `SCHOLARLY_CONTACT_EMAIL`.
Probe: `oa 10.1371/journal.pmed.0020124 10.1093/qje/qjv036
10.48550/arXiv.2205.01833 --all-legs`
(`DAAF_FETCH_CONTEXT=FrameworkDev_S1_unpaywall_live`; `smoke_s1/`
MANIFEST.jsonl line 15, timestamp 2026-10-02T19:08:51Z). OpenAlex spend $0
(single lookups).

| # | Question | Finding |
|---|---|---|
| 1 | Is Unpaywall's answer the same as OpenAlex's (docs: same database since late 2025)? | Yes for the gold PLOS paper: both best locations are the publisher landing page with no PDF link; the PDF is a repository location in both. |
| 2 | Closed paper: 404 or an answer? | HTTP 200, `is_oa: false`, `oa_status: closed`, `best_oa_location: null`, `oa_locations: []`. |
| 3 | DataCite DOI (docs: 404) | HTTP 404 with an HTML body, not JSON. The `oa` digest now reads "not found (HTTP 404: DOI unknown to Unpaywall …)" instead of "failed". |
| 4 | Does the response echo the email? | No. The raw artifact held `[SCHOLARLY_CONTACT_EMAIL]` only in the three request params; zero occurrences of the address (raw, URL-encoded) in the raw, digest or MANIFEST. |
| 5 | Doc-derived fixture vs live shape | `z_authors` use `raw_author_name` (no `given`/`family`); extra fields (`first_oa_location`, `data_standard: 2`, `is_paratext`, …); location `evidence`/`updated` = `"deprecated"`; no rate-limit headers. Fixture replaced. Details in `unpaywall.md`. |

Still not measured: Crossref polite pool (no Crossref call was needed in this
probe); Unpaywall's daily limit.

## 2026-10-02 — S1 re-measurement (DAAF port, live via the CLI)

Spend for the whole smoke run: about $0.006 of the OpenAlex $1/day budget
(remaining $0.9939 after the last call).

| # | Question (doc vs. earlier measurement) | Probe | Finding |
|---|---|---|---|
| 1 | Does semantic search accept "most filters" (docs) or reject most (2026-09-27)? | `openalex … --mode semantic --filter has_content.grobid_xml:true` then `--filter is_oa:true` | `has_content.grobid_xml` → HTTP 400 "not supported with semantic search" with the supported list (matches 2026-09-27); `is_oa:true` → 200. Docs' "most filters work" is too generous. A rejected request cost $0 (`x-ratelimit-cost-usd: 0`). |
| 2 | Does semantic search return a relevance score (docs: yes; 2026-09-27: no)? | `--with-score` (adds `relevance_score` to `select`) | Yes: 0.9018 / 0.8999 / 0.8933 for the top 3. The earlier "no score" came from a select list without the field. |
| 3 | Usage header names: docs `X-RateLimit-{Limit,Remaining,Credits-Used,Reset}` vs measured `x-ratelimit-{cost,remaining,limit}-usd`? | headers logged per request (`rate_headers` in raw JSON) | **Both families are sent**: `x-ratelimit-cost-usd 0.001`, `-credits-used 10`, `-limit 10000`, `-limit-usd 1`, `-remaining 9959`, `-remaining-usd 0.9959`, `-reset 40054`, `-onetime-remaining 0`, `-prepaid-remaining-usd 0`. 10 credits = $0.001. `meta.cost_usd` is also present. The adapter parses both families. |
| 4 | Does the new `corpus=` parameter (Aug 2026) work? | `openalex '"high-dosage tutoring"' --corpus core` vs `--corpus all` | Accepted. `meta.count` 47 (core) vs 70 (all). Default (no param) not separately measured. |
| 5 | Does S2 `/paper/search/bulk` accept boolean syntax? | `s2-bulk '"high-dosage tutoring" + (achievement \| outcomes) -college' --limit 3` | HTTP 200 after one 429 retry; total 16, continuation token present, top 3 on-topic. Operator-by-operator interpretation not isolated (no contrasting query). Docs: results are "without search relevance". |
| 6 | Title lookup cost | `verify 'title:"Not Too Late…"'` | `filter=title.search:` billed $0.001 (search price), not the $0.0001 list price. DOI lookups free. |
| 7 | Crossref retraction signals | `retractions '10.1016/S0140-6736(97)11096-0' 10.1093/qje/qjv036` | Lancet/Wakefield: `updated-by` and `filter=updates:` both list the 2010 retraction and 2004 correction with `source: retraction-watch`; OpenAlex `is_retracted: true`. QJE: none at either source. |
| 8 | OA location for a gold-OA paper | `oa 10.1371/journal.pmed.0020124 10.48550/arXiv.2205.01833` | PLOS: PDF via OpenAlex, license cc-by, version reported `submittedVersion` (OpenAlex's own value). arXiv DOI: PDF via OpenAlex (`arxiv.org/pdf/2205.01833`). Two closed papers (QJE, an AER DOI): no OA copy at OpenAlex or ERIC. |
| 9 | Fused `find` end-to-end | tutoring question + `--keywords` | All four legs answered (25/25/20/25 records), 10 papers after fusion; S2 needed no retries. Cost $0.002. |

Not measured in this run: Unpaywall (no `SCHOLARLY_CONTACT_EMAIL` yet;
measured later the same day, entry above); Crossref polite pool; OpenAlex
keyless behavior (a key is configured here).

## 2026-09-27 — the user's original measurements (imported)

### OpenAlex
- **Auth:** keys mandatory since 2026-02-13 per the deprecations page; the old
  `mailto` polite pool is ignored. `Authorization: Bearer` works on both
  `api.` and `content.` hosts.
- **Pricing:** free key $1/day; ID lookup free, filter list $0.0001,
  search/semantic $0.001, content download $0.01.
- **`search=`** matches title, abstract and full text and blends in
  citations (Chetty's value-added paper ranked 4th for "school finance reform
  student outcomes"); `title_and_abstract.search` + `sort=relevance_score:desc`
  stayed on topic. Quotes and `AND`/`OR`/parentheses work inside it; terms are
  effectively ANDed (a long sentence returned 6 odd hits).
- **Commas** inside filter values split the filter; `?`/`*` break stemmed
  `.search` filters (HTTP 400).
- **Semantic search:** ≤ 50 results, 1 req/s (429 "Semantic search is limited
  to 1 request per second"). Supported filters per the 400 text: author.id,
  authorships.author.id, authorships.institutions.id/lineage, funders.id,
  has_abstract, has_fulltext, institution(s).id, is_oa, is_retracted,
  language, open_access.is_oa, primary_location.license,
  primary_location.source.id, publication_year, type.
- **Open year ranges** need `publication_year:>2014`.
- **Type negation** `type:!dataset,type:!paratext` works in both modes;
  ICPSR "Code for: …" deposits otherwise took 4 of the top 6 `similar` slots.
- **Full text:** `content.openalex.org/works/{W}.grobid-xml`; availability
  `has_content.grobid_xml`; Fryer's NYC tutoring paper came back as 7,539
  words.
- **Versions:** NBER and journal versions are separate works (3–4 records).
- **Abstract coverage:** ~75% in Education (subfield 3304), 2015–2025.
- **`group_by=has_abstract`** returned a false 0.
- **`find` dissertations:** 9 of the top 20 for a teacher-coaching question
  were theses → excluded by default.

### Semantic Scholar
- `x-api-key`; invalid key → 403, valid → 200/429.
- "1 request per second, cumulative across all endpoints" (Ai2 key email +
  tutorial). Shared gate: five concurrent calls sent 11 requests in 15 s, all
  succeeded.
- Throttling: ~30% of rapid first attempts refused (backoff recovered 10/10);
  later 5 of 6 searches 5 s apart refused; `/paper/search` with `abstract` at
  limit ≥ 10 refused every time → `SEARCH_FIELDS` without abstracts,
  `SEARCH_MAX = 20`, `FIND_ATTEMPTS = 3`, `DEDICATED_ATTEMPTS = 8`.
- `/paper/search` is plain relevance text; quotes/operators zeroed a query.
- `DOI:10.1093/qje/qjv036` → 404; title match found only a 2015 seminar
  version.
- Snippet schema and OA-only coverage as in `semantic-scholar.md`.
- Recommendations returned unrelated 2026 papers for an AER tutoring paper →
  `similar` uses OpenAlex.

### ERIC
- `https://api.ies.ed.gov/eric/`, no key, `format=json`.
- Solr default OR: "school finance reform" 171,348 hits vs 183 AND-joined.
- `peerreviewed:T`, `e_fulltextauth:1`, `publicationdateyear:[2018 TO *]`.
- No DOI and no citation count; PDFs at `files.eric.ed.gov/fulltext/{ED…}.pdf`.

### Not a backend
The user's original toolkit also wrapped Firecrawl web search; DAAF defers it
(decision D-3, no `FIRECRAWL_API_KEY`). Grey literature uses WebSearch +
`web_fetch.sh` instead.
