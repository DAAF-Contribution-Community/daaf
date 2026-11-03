# STATE.md Template (Literature Review Mode)

This template defines the session state file, the researcher's "saved progress", for a Literature
Review project. The orchestrator copies it to `STATE.md` in the project folder, keeps it current
at every checkpoint and dispatch, and reads it first when a session resumes. It is written for the
orchestrator. The researcher reads parts of it too, so the "Where we are" table, Open Review
Items and the restart prompt use plain words (`agent_reference/DOCUMENTATION_STANDARDS.md`
§ S3); the decision records quote the researcher's words verbatim beside the tool values they
were recorded as (paper keys, decision values, MANIFEST rows), which are agent-facing. Stage and
checkpoint codes are defined in
`.claude/skills/daaf-orchestrator/references/literature-review-mode.md`; the files and statuses
named here are defined in `agent_reference/LIT_REVIEW_OUTPUT_CONTRACT.md`.

**What a record in this file is worth.** Every value that a tool writes elsewhere (a MANIFEST row,
a card_check, an audit record, a ledger row) is copied here as a pointer for recovery, never as
the authority. When this file and a tool record disagree, the tool record wins and this file is
corrected (§ Integration with Session Recovery > Stale state).

---

## Template

Copy this template to `STATE.md` in the project folder at intake, once the level and question are
set and the folder exists (before the Scope Check). Delete the sections marked for a level the
review is not using.

```markdown
# Saved Progress: [Review title] (Literature Review)

**Last Updated:** [YYYY-MM-DD HH:MM]
**Session Count:** [N]

---

## Current Position (where we are)

| Field | Value |
|-------|-------|
| **Review** | [Full title, e.g., "What tutoring programs do for reading in primary school"] |
| **Depth** | [Quick scan / Standard review / Formal systematic review] |
| **Now doing** | [The activity in plain words, e.g., "reading the key papers (4 of 7 done)"] |
| **Round** | [0 (scoping searches) / N / "one pass" for a quick scan] |
| **Status** | [In progress / Waiting for your reply / Blocked / Complete] |
| **Waiting for** | [What the researcher is asked to do, in plain words, or "Nothing"] |

**Agent fields** (codes from `literature-review-mode.md`):

| Field | Value |
|-------|-------|
| **Stage** | [LR-0 … LR-8, LR-3b, LR-5a, LR-7Q, LR-8Q] |
| **Open checkpoint** | [CP-1 / CP-K / CP-S / CP-A / CP-R / CP-G / CP-F / none] |
| **Level (machine value)** | [quick / standard / formal] |

---

## Project

| Field | Value |
|-------|-------|
| **Question (the researcher's words)** | > [verbatim] |
| **Review type** | [systematic / scoping / state-of-the-art / integrative / realist / umbrella / related work] |
| **Project folder** | `research/YYYY-MM-DD_LitReview_{Topic}/` |
| **Created** | [YYYY-MM-DD] |
| **Papers the researcher already knows (seeds)** | [list with identifiers, or "None"] |
| **Materials the researcher pointed to** | [paths in the project: `web_fetches/…`, `papers/…`, `output/preliminary_notes/{date}_{slug}_materials-digest.md`, or "None"] |

---

## Session Metadata

> Captured at project setup for AI use disclosure (`agent_reference/AI_DISCLOSURE_REFERENCE.md`).

| Field | Value |
|-------|-------|
| **DAAF Version (at setup)** | [short commit hash from `git rev-parse --short HEAD` at setup; never refreshed] |
| **Session Model ID** | [the runtime model ID of the orchestrator at session start] |
| **Subagent Model Tiers** | [resolved IDs per tier, plus any per-dispatch overrides, e.g., opus for formal-level screening] |
| **Session Date(s)** | [dates] |
| **Session Transcript(s)** | `logs/`, collected at completion via `collect_session_logs.sh` |

---

## Scope Check

> The review plan is the mode's hard Scope Check (CP-1). Session recovery reads the status line:
> anything but `confirmed YYYY-MM-DD` means the plan is shown again before any full search.

- **Scope Check status:** [awaiting confirmation | confirmed YYYY-MM-DD]
- **Plan in force:** `Protocol_v[N].md` (sha256 [first 12 hex])
- **Approved in the researcher's words:** > [verbatim reply]

| Plan version | Date | What changed | Researcher's words |
|--------------|------|--------------|--------------------|
| `Protocol_v1.md` | [date] | [first plan] | > [verbatim] |
| `Protocol_v2.md` | [date] | [e.g., "added a sub-question on attendance"] | > [verbatim] |

---

## Route Record (reading setup)

> The setup line comes from `lit_verify route`, run at intake at every level, never typed. Each paper-reader dispatch copies the
> `ROUTE:` line verbatim; no line means no picture reading.

| Field | Value |
|-------|-------|
| **ROUTE line (verbatim)** | `ROUTE: [name]` |
| **Route MANIFEST row** | `papers/MANIFEST.jsonl` line [n], sha256 [first 12 hex], timestamp [ISO] |
| **Pictures of pages** | [Available on this setup / Text only on this setup] |
| **PDF page-image preference** | [auto / all-pages / off, from CLAUDE.md § User Preferences] |
| **Image cap per reader** | [8 on a 200k window / 30 on a 1M window] |

---

## Round Table

> One row per round. Counts come from `lit_corpus counts` (`output/counts_v{N}.json`), never from
> memory. Round 0 is the scoping searches (`lit_search/round0/`, recorded in
> `output/preliminary_notes/{date}_scoping_round0.md`; never ingested).

| Round | Plan version | Searched (calls / records) | Screened | Kept | Read in full | Cited | Counts file | Check-in decision (1 another round / 2 change the plan / 3 final, researcher's words) |
|-------|--------------|----------------------------|----------|------|--------------|-------|-------------|---------------------------------------------------------------------------------------|
| 0 | — | [n / n] (scoping) | — | — | — | — | — | — |
| 1 | `Protocol_v1.md` | [n / n] | [n] | [n] | [n] | [n] | `output/counts_v[N].json` | [1 / 2 / 3] > [verbatim] |

---

## Key-Paper and Full-Text Decisions

> Standard level: the key-paper list (CP-K). Formal level: every full-text decision and each
> settled second-screener disagreement (CP-S), recorded with `screen record` pass `researcher`.
> Quick scan: delete this section.

| Round | Paper key | Citekey | Decision | Reason | Researcher's words | Recorded (`screen record` row) |
|-------|-----------|---------|----------|--------|--------------------|--------------------------------|
| [R] | [key] | [citekey] | [read in full / not read / include / exclude] | [one line] | > [verbatim] | [MANIFEST timestamp or "not recorded yet"] |

---

## Reader Table

> One row per paper-reader dispatch (one paper per dispatch; long papers in page-range chunks).
> Record the dispatch's agent ID from the dispatch result the moment it returns: the audit needs
> it, and for a chunked paper it takes every chunk row's ID (one `--agent-id` each). Recovery reads this table (§ Integration with Session Recovery). The dispatch names a model
> tier (the Agent tool takes tier aliases, not model IDs); the model ID the reader actually ran on
> is the one the audit record names, copied from it.

| Paper key | Pages / chunk | Dispatch agent ID | Model tier (dispatch) | Model ID (recorded) | Card | Card check verdict | Card revisions | Audit record | Audit outcome | Settlement | Status |
|-----------|---------------|-------------------|-----------------------|---------------------|------|--------------------|----------------|--------------|---------------|------------|--------|
| [key] | [1-N / a-b (chunk k of m)] | [agent ID] | [opus] | [model ID from the audit record, or "none recorded"] | `papers/[key]/evidence_card[S].md` or "none yet" | [PASS / PARTIAL / NEEDS_REVIEW / FAIL / —] | [0-2] | `papers/[key]/vision_audit[S].json` or "none" or "not needed (no picture readings)" | [confirmed / confirmed_with_checks / person_must_check / mismatch / chain_unconfirmed / —] | [`audit_settlement[S]_[n].json` or "pending: [k] items" or "—"] | [dispatched / card written / audited / settled / done] |

**Chunk notes:** [for a chunked paper: `papers/[key]/chunk_notes_p[a]-[b].md` per finished chunk]

---

## Adjudication and Glance Batches

### Glance Records

> Until an adjudicator passes its evaluation, every reference's second check is the researcher's
> glance at the list to check before a final deliverable (one list, one reply per deliverable),
> shown at the reference check (CP-G; at a quick scan, at the final review). A request to check a
> left-out reference again is `check_again`, distinct from `defer` (the researcher's own later
> look): it is never a `record-human` call, and its new list is the next row.

| Glance sheet | Rows file | For deliverable | Shown | Researcher's words | Decision | `record-human` row |
|--------------|-----------|-----------------|-------|--------------------|----------|--------------------|
| `output/reference_glance_v[N].md` | `output/reference_glance_v[N]_rows.txt` | `output/[file]` | [YYYY-MM-DD HH:MM or "not yet"] | > [verbatim, or "awaiting reply"] | [same_work / different_work / defer / override_mismatch, per row group; check_again (searcher re-dispatch [agent ID], KEYS [keys]) for references asked to be checked again] | [data/MANIFEST.jsonl timestamp, "not recorded", or "none (check_again)"] |

### Adjudicator Batches

> Only after an adjudicator identity is on an evaluated list. Pack runs from a captured script;
> a packed batch that was not ingested is re-dispatched with the same bundle, never re-packed.
> One that will not be ingested (never dispatched, no completed pack log, or refused by
> `ingest`) is released with `adjudications release` and a reason, and its rows are packed in a
> new batch (the next row).

| Batch | Pack script | Bundle sha256 | Prompt sha256 | Model tier (dispatch) | Model ID (packed) | Dispatch agent ID | Return saved | Ingest |
|-------|-------------|---------------|---------------|-----------------------|-------------------|-------------------|--------------|--------|
| [b01] | `scripts/lr_adjudication/[NN]_pack_batch_[b01].py` | [first 12 hex] | [first 12 hex] | [opus] | [the `--model-id` given to pack] | [agent ID or "not dispatched"] | `data/adjudication_raw/[b01].jsonl` or "no" | [not ingested / ingested (MANIFEST timestamp) / refused: exit [n], reason / released (MANIFEST timestamp): reason] |

### Reading Items for a Person

> Audit items a person compares with the page. `lit_verify settle PAPER_DIR --audit
> vision_audit{S}.json --list` prints them in plain words and writes their ids to
> `settle_items{S}.txt`; the researcher's one reply is recorded with `settle … --items FILE
> --decision matches|does_not_match --user-words "…"`, one call per decision, each writing
> `audit_settlement{S}_{n}.json` beside the audit and a `papers/MANIFEST.jsonl` row of kind
> `lit_verify_settle`. Item ids are copied from `settle_items{S}.txt`, never typed. The
> researcher sees only the reasons, under the paper each belongs to (its short reference and PDF
> path), numbered across the check-in; record each number with its
> item id before presenting, so the reply's numbers lead back to the ids.

| Paper key | Audit record | Item ids | Number shown (check-in) | Shown | Researcher's words | Decisions (`matches` / `does_not_match`) | Settlement record |
|-----------|--------------|----------|-------------------------|-------|--------------------|------------------------------------------|-------------------|
| [key] | `vision_audit[S].json` | [ids] | [e.g. "1, 2 (round 2 check-in)"] | [date or "not yet"] | > [verbatim] | [per item] | `audit_settlement[S]_[n].json` or "pending" |

---

## Spend Ledger

> OpenAlex cost is summed from the `openalex_cost_usd` field of the project's `lit_search/`
> MANIFEST rows. A paid call (Elicit, a licensed Scite key, `elicit-resume --confirm-spend`) runs
> only with the researcher's approval for that call, quoted below.

| Item | Value |
|------|-------|
| **OpenAlex spend to date** | $[x.xxx] (as of [timestamp]) |
| **OpenAlex budget line in the plan** | $[x] |
| **SPEND APPROVED (from the confirmed plan)** | [none / the named paid calls, with the researcher's words] |

| Date | Paid call | Approval (researcher's words) | Cost recorded |
|------|-----------|-------------------------------|---------------|
| [date] | [command and backend] | > [verbatim] | [from the call's MANIFEST row] |

---

## Formal Level Only

> Delete for quick scan and standard review.

**Appraisal log:** `output/appraisal_log_v[N].md` (written by the orchestrator after each checklist
review, CP-A)

| Round | Item | Where it is recorded | Researcher's words |
|-------|------|----------------------|--------------------|
| [R] | [checklist judgments for paper [key] (CP-A)] | [`output/appraisal_log_v[N].md`; a changed weight via `notes record`, row timestamp] | > [verbatim] |
| [R] | [certainty ratings for findings (collected at CP-R)] | [`findings` with `certainty_scheme` `researcher_grade`, row timestamp] | > [verbatim] |

---

## Deliverables

| File | Kind | Report check | Verdict | Open items |
|------|------|--------------|---------|------------|
| `output/[quick_scan_v1 / synthesis_round1_v1 / lit_review_final_v1].md` | [synthesis / final] | `output/[stem].report_check[_n].json` | [PASS / NEEDS_REVIEW / FAIL] | [n review, n fail] |

**Claim spot check (final checks):** `output/claim_spot_check_v[N].md` or "not yet"
**Review manifest:** `output/LIT_REVIEW_MANIFEST.json` → [latest manifest path], contract
[version]

---

## Open Review Items

> Anything a person must still look at, in plain words, with where it came from. Cleared items stay
> with how they were cleared.

| # | Item (plain words) | Source | Status |
|---|--------------------|--------|--------|
| 1 | [e.g., "Compare the number 88 with PDF page 2 of Allen 2020"] | [audit / report check / glance / reader return] | [open / cleared: how] |

---

## Key Decisions Made

| Decision | Choice | Researcher's words or rationale | Stage |
|----------|--------|---------------------------------|-------|
| [Topic] | [What was decided] | > [verbatim, or the reason] | [LR-n / CP-x] |

---

## Blockers

| Blocker | Stage | Impact | Resolution |
|---------|-------|--------|------------|
| [None or description] | [LR-n] | [effect] | [what is needed] |

---

## Pending Learning Signals

*Buffer for learning signals from subagents. Flushed to LEARNINGS.md at each check-in and at the
final review.*

| Stage | Category | Signal | Source Agent |
|-------|----------|--------|--------------|
| [LR-n] | [Access/Data/Method/Perf/Process] | [One-line insight] | [literature-searcher / paper-reader / literature-synthesizer] |

**Last Flushed:** [timestamp or "Not yet flushed"]

---

## Next Actions

1. **Immediate:** [next step]
2. **After That:** [following step]
3. **Waiting for the researcher:** [decision or reply needed, or "Nothing"]

---

## Session History

| Session | Date | What was done | Notes |
|---------|------|---------------|-------|
| 1 | [date] | [e.g., "plan agreed; round 1 searched and screened"] | [summary] |

---

## Session Continuity

### Last Action Completed

| Field | Value |
|-------|-------|
| **Stage** | [LR-n] |
| **Action** | [dispatch, command or checkpoint] |
| **Timestamp** | [ISO 8601] |
| **Files written** | [list] |

### Context Snapshot

**Orchestrator Utilization:** [actual value from the context-reporter hook]

**Key points (max 5 bullets):**
- [point]

### User Restart Prompt

**To pick up where we left off, run `/clear` to start a fresh session, then paste this into the chat:**

> Resume my literature review "[Review title]". Saved progress: `[exact STATE.md path]`. We were [the activity in plain words, e.g., "reading the key papers; 4 of 7 are done"]. Next: [the next step in plain words, e.g., "read the remaining 3 papers, then show you what this round found"].

**Orchestrator:** keep this prompt in plain words (no stage or checkpoint codes, no agent or status
names). Update it at the HIGH and CRITICAL context levels, before a planned break, and when the
researcher stops. Use concrete values, never brackets.

### Resumption Instructions (Agent Reference)

1. Read this file in full; then read `LEARNINGS.md`.
2. Read `.claude/skills/daaf-orchestrator/references/literature-review-mode.md`.
3. Apply the recovery rules in § Integration with Session Recovery of
   `agent_reference/STATE_TEMPLATE_LITREVIEW.md`, in their order, before any new dispatch.
4. Re-tier any dispatch plan to the current session's model (`session-recovery.md` § Step 5b).
5. Show the researcher where the review stands, in plain words, and confirm before continuing.
```

---

## Usage Guidelines

### When to Create

At intake, once the researcher has chosen the depth and stated the question and the project folder
exists: before the scoping searches and the Scope Check, so a session that stops at the plan can
be resumed. Fill Current Position (stage LR-0), Project, Session Metadata and the Route Record (run
`lit_verify route` first), and set Scope Check status to `awaiting confirmation`. The mode file's
§ State, Recovery and LEARNINGS.md > STATE.md update gates lists the fields each event updates; the
table below follows it.

### What This Template Leaves Out

No inter-rater agreement statistic, no escalation-tier fields and no PRISMA flow fields. The
second-screener disagreements live in the screening table (`lit_corpus screen record` lists them)
and the per-round flow counts in `output/counts_v{N}.json`.

### When to Update

| Event | Update |
|-------|--------|
| The review plan is shown | Current Position; Scope Check status `awaiting confirmation`; Status "Waiting for your reply" |
| The researcher approves the plan, or a changed plan | Scope Check status `confirmed YYYY-MM-DD` with the plan path; the plan version row with their words; Spend Ledger (SPEND APPROVED) |
| A searcher dispatch returns | Round Table (counts from `counts`); Spend Ledger; Open Review Items (retractions, missing seeds) |
| The key-paper list or full-text decisions are agreed | Key-Paper and Full-Text Decisions, with the researcher's words |
| A paper-reader is dispatched | A Reader Table row with the agent ID, before anything else |
| A reader returns | Card, card check verdict, revisions |
| `lit_verify audit` runs | Audit record and outcome; Model ID (recorded) from the audit record's observed model; Reading Items for a Person for each listed item |
| A settlement is recorded | Settlement column; the item's row |
| A checklist review is answered (formal) | Formal Level Only: the appraisal log path and the researcher's words |
| A glance sheet is shown, and when the reply is recorded | Glance Records |
| An adjudicator batch is packed, dispatched, saved, ingested or released | Adjudicator Batches, at each step |
| A paid call is approved or run | Spend Ledger |
| A synthesizer returns and `lit_verify report` runs | Round Table (read, cited); Deliverables; Open Review Items |
| A round check-in is answered | Round Table check-in decision; formal ratings, verbatim |
| The final review is approved | Deliverables (final paths); Current Position "Complete" |
| At ELEVATED context or higher, and before any break | Current Position, Next Actions, Session Continuity and the restart prompt |

---

## Integration with Session Recovery

`session-recovery.md` routes a Literature Review project here. A project is a Literature Review
when its folder name holds `_LitReview_` and its STATE.md has a Reader Table and a Scope Check
status line. The mode file's § State, Recovery and LEARNINGS.md > Session recovery holds the same
rules in short form.

**Recovery rules, applied in this order** (each names what the resumed session reads and what it
does):

| # | What STATE.md and the folder show | Action |
|---|-----------------------------------|--------|
| 1 | Scope Check status is `awaiting confirmation`, or the line is missing | Show the review plan again (CP-1), from the latest `Protocol_v{N}.md` and the round-0 scoping notes; do not start a full search |
| 2 | Scope Check status is `confirmed YYYY-MM-DD` | Resume from Current Position; do not show the plan again |
| 3 | A Reader Table row has a dispatch agent ID but no card on disk | Dispatch that paper (or its remaining chunk) again, with a card path not yet used. A chunked paper resumes at the first chunk whose `chunk_notes_*` file is missing |
| 4 | A card exists but its row has no audit record | Run `lit_verify audit` on it before anything else, with the agent ID from every row of that card (one per chunk). In a new session the hook's record of the earlier session's readers no longer counts, so the audit cannot confirm the model: pass `--transcript` when a `find` probe locates a reader's `agent-{ID}.jsonl` (it can still show a differing model, `mismatch`); either way the audit lists every picture reading for a person (`person_must_check`) |
| 5 | A card's latest card_check is FAIL | The reader revises up to twice inside its own dispatch, so a FAIL on record is a returned failure: handle it as the mode file says for a failed card, never by editing the card |
| 6 | An audit (`person_must_check` or `mismatch`) lists items for a person and no settlement covers them | Re-run `lit_verify settle … --list` only if `settle_items{S}.txt` is missing; present the items at the next check-in, then record the researcher's one reply with `settle … --items`. A `chain_unconfirmed` audit cannot be settled: follow the mode file (a fetched or user-supplied copy of the PDF) |
| 7 | An adjudicator batch is packed but not ingested | Dispatch the same bundle again with the same prompt file (same hashes), then ingest; never pack it again. A saved return not yet ingested: ingest it |
| 8 | A glance sheet was shown and no reply is recorded | Show the same `reference_glance_v{N}.md` again (CP-G; at a quick scan, the final review), then record the reply with `record-human` in the researcher's own words |
| 9 | A deliverable has no report check, or its newest check is FAIL | Run `lit_verify report`; on FAIL, re-dispatch the synthesizer with the failure items |
| 10 | A round check-in has no decision | Show the round check-in again (CP-R) |

**Stale state.** If a tool record is newer than this file (a card, audit, settlement or report
check on disk that no row names; a MANIFEST row after **Last Updated**), the earlier session
stopped before saving. Rebuild the rows from `papers/MANIFEST.jsonl`, `data/MANIFEST.jsonl` and
the files on disk, tag each rebuilt row `[reconstructed]`, and tell the researcher.

**Words are never reconstructed.** A researcher's reply that is not in this file or in a tool
record (the `record-human` or `settle` MANIFEST row) was never recorded: ask again rather than
infer it.

See `{BASE_DIR}/.claude/skills/daaf-orchestrator/references/session-recovery.md` for the complete
recovery procedure.
