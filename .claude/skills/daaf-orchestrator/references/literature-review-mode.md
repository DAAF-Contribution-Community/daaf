# Literature Review Mode

Literature Review mode answers "what does the published research say about this question?" at one of three levels the researcher picks: a quick scan of abstracts, a standard review that reads the key papers in full, or a formal systematic review the researcher leads. It produces a versioned deliverable (a memo or a synthesis) in which every search is recorded, every reference is looked up in a database and checked by the researcher, every quote and number is checked on its page, and no sentence sounds surer than the evidence, inside a research project folder holding the full search, screening, reading and checking record.

## User Orientation

The mode confirmation already gave the user this preview, so do not repeat it after confirmation. Present these points only when the user signals they are new to DAAF or asks for more detail.

- You choose how deep the review goes: a quick scan (titles and abstracts, a short memo of pointers), a standard review (the key papers read in full, a note on each, how sure we can be about each conclusion) or a formal systematic review (you lead; DAAF drafts checklist answers with the passages behind them, you make every judgment)
- Before any full search, a scope check: the question, where DAAF will search, what counts as in or out, and the expected reading and cost; the plan is saved and every change becomes a new version of it. When the AI model that checks references, or the one that reads the papers, has not been tested by DAAF for that job, the scope check says so and asks what you would like it to do
- Standard and formal reviews run in rounds: one cycle of searching, choosing papers and reading them, then a check-in where you choose another round, a change of plan, or the final write-up
- Check-ins: quick scan, two (the plan; the memo with its references). Standard review: the plan, then per round the list of papers to read in full and the round check-in, then a reference check and the final review. Formal review: the plan, then per round your full-text decisions (in place of the key-paper list), a checklist review and the round check-in, then the reference check and the final review
- What is checked at every level: every search is saved with its exact wording; every reference is looked up in a database, and you check each one once before the final version (your reference check); every quote and number is found on the page it came from; results from different studies are never averaged into one number
- You receive: the memo or the final review (each round's write-up and the final review also come as a web page to read in the browser), a checked reference list, a list of gaps, and a project folder with the whole record
- This mode is experimental: it works end to end and every reference and quote is still checked, but it has had limited real-world testing. Review its output more closely, and tell us what goes wrong.

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md` § Literature Review Mode.

---

## Scope Check

- **Tier:** Hard (blocking): a review commits real reading, usage and the researcher's time, so the plan is agreed before any full search.
- **Where:** CP-1, the review plan (§ Checkpoint Templates > CP-1), which embeds the standard block; a quick scan uses the short form of the same template.
- **Read first:** every material the user pointed to, after mode confirmation and LR-0, before CP-1 (`SKILL.md` § Scope Check > Read First), plus the scoping searches (LR-1, standard and formal levels), whose record grounds the volume and seed lines of the plan.
- **No staging, the folder exists:** LR-0 creates the project folder once the level and question are known, before CP-1, so fetches, PDF ingests and the materials digest go straight into it. A declined plan leaves a small folder in `research/`, as in Data Onboarding.
- **Mode-specific carve-out:** a material that is itself a paper the review may include (a PDF the user wants reviewed, a reading list's entries) is not ingested at scoping: it becomes a seed and enters the corpus in round 1 through the searcher (`add-record`, then `pdf_ingest` into `papers/`), so each paper has one key and one ingest. Only background materials (a proposal, a draft, a syllabus) go through the scoping digest, into `materials/`.
- **Rule and standard block:** `SKILL.md` § Scope Check.
- **On resume:** STATE.md's `Scope Check status` reads `awaiting confirmation` or `confirmed YYYY-MM-DD` with the `Protocol_v{N}.md` path; re-present CP-1 only when it reads `awaiting confirmation` or is absent (`session-recovery.md` § Step 5c).

---

## Levels at a Glance

| | Quick scan (`quick`) | Standard review (`standard`, default) | Formal review (`formal`) |
|---|---|---|---|
| What is read | Titles and abstracts | The key papers in full | Every included paper in full |
| Rounds | One pass | Until the researcher chooses the final write-up | Same |
| Researcher check-ins | CP-1 (short form), CP-F | CP-1; per round CP-K and CP-R; CP-G; CP-F | CP-1; per round CP-S, CP-A and CP-R; CP-G; CP-F |
| Second screener | None (the memo says so) | Optional (agent or person), with a resolution pass | Required: a person on every full text (CP-S); an AI second screener is a declared protocol deviation |
| Weight per paper | None | Drafted by the reader; the synthesizer may settle it | Drafted by the reader; the researcher confirms or changes it at CP-A |
| Certainty | "certainty not rated: abstracts only" if any cross-paper statement | Stated by the synthesizer with a reason (`stated`) | The researcher's rating at CP-R (`researcher_grade`) |
| Final checks | `report --kind final`, the reference glance | The same, the reading audits settled, the data-verifier spot-check | The same |

Method detail lives in the `literature-review` skill (`quick-scan.md`, `standard-review.md`, `formal-review.md`, `screening.md`); agents preload what they need.

---

## Literature Review Workflow

The standard level; § Stage Tables gives the quick and formal differences.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LR-0 INTAKE AND PROJECT SETUP (orchestrator)                                │
│   level menu (shown as written) → question, seeds, materials               │
│   create folder → STATE.md, LEARNINGS.md → lit_verify route → read first   │
├─────────────────────────────────────────────────────────────────────────────┤
│ LR-1 SCOPING SEARCHES, round 0 (literature-searcher; not ingested)          │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓
            ★ CP-1 Scope Check: the review plan → Protocol_v1.md
                          ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ ROUND R (repeat)                                                            │
│   LR-2/3 search, corpus, title-and-abstract screen (literature-searcher)    │
│      [optional second-screener pass, then resolution pass]                  │
│   ★ CP-K key papers                                                         │
│   LR-4 acquire and check: verify, retractions, oa, fetch, ingest            │
│   LR-5 read: one paper-reader per paper, waves of ≤ 5 → lit_verify card     │
│   LR-5a reading audit: lit_verify audit per card (orchestrator)             │
│      → settle --list for items a person compares                           │
│   LR-6 round synthesis (literature-synthesizer, KIND draft)                 │
│      → lit_verify report (orchestrator) → lit_corpus manifest --round R     │
│   ★ CP-R round check-in: (1) another round (2) change the plan (3) final   │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓ (3)
┌─────────────────────────────────────────────────────────────────────────────┐
│ FINAL                                                                       │
│   reference checker: pack → citation-adjudicator → ingest (every review)    │
│   glance-sheet (+ open settle --list items) → ★ CP-G reference check        │
│   record-human / lit_verify settle with the user's words → export-bib       │
│   LR-7 final synthesis (literature-synthesizer, KIND final)                 │
│   LR-8 lit_verify report --kind final → data-verifier spot-check            │
│   lit_corpus manifest, HTML copy → ★ CP-F final review → logs, LEARNINGS    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage Tables

Stage and checkpoint codes are agent-facing. The second column is what the user hears (§ Plain-Language Vocabulary). Every command runs as its own Bash call; agent commands are listed for orientation, and the agent files hold their syntax.

### Quick scan

| Stage | User-facing activity | Who | Commands | Gate / checkpoint | Saved |
|---|---|---|---|---|---|
| LR-0 Intake | setting up the review | orchestrator | `lit_verify route --reader-model`; the checker's identity check; `mkdir`; STATE and LEARNINGS from templates | level, question, seeds collected | `STATE.md`, `LEARNINGS.md`, materials digest if any |
| ★ CP-1 (short form) | the scope check | orchestrator → user | after: `untested-checker` when the user lets an untested checker confirm references | **Hard**: question, phrasings, sources, in/out rules, spend line, the reference-checker choice | `Protocol_v1.md` (short), STATE `Scope Check status`, the checker choice |
| LR-2 Search | searching | literature-searcher | `find` × 2-3 phrasings, optional one hop; `lit_corpus ingest --round 1`; `dedup decide` | at least one database answered; seed recall reported | `lit_search/round1/`, `data/corpus_v*`, `search_log_v*` |
| LR-3 Screen | the first pass on titles and abstracts | literature-searcher | `screen sheet`, `screen record` (`ta`) | every record has a decision | `screening_v*` |
| LR-4' Check references | checking the references | literature-searcher | `verify`, `retractions` per includable paper; `attach verify`, `attach retractions` | every includable paper has an attached check | corpus `citation_status` |
| LR-7Q Memo | writing up | literature-synthesizer (KIND draft) | `claims abstract`, `export-bib`, `counts`; writes `output/quick_scan_v{N}.md`. Orchestrator: `lit_verify report --level quick` | 0 FAIL | memo, `*.report_check.json` |
| ★ CP-F | the memo and its references | orchestrator → user | the reference checker (§ The Citation Second Check > The checker flow), then `glance-sheet`, before; `record-human` (user's words), `export-bib` after; a reference to check again: the searcher's check-only pass, `export-bib`, a new list | the user's reply recorded; the approval counts only once LR-8Q passes on the memo the user saw | ledger, `reference_glance_v*` |
| LR-8Q Final check | the final check | orchestrator | `lit_verify report --kind final --level quick` on the same memo; `lit_corpus manifest --round 1` | 0 FAIL on the memo the user approved. A FAIL, or a reply that changed a cited reference, means a KIND final version: check it, then show it at CP-F again before delivery (§ Checkpoint Templates, "After the reply (quick scan)") | `output/manifests/LIT_REVIEW_MANIFEST_v{N}.json` |

### Standard review

| Stage | User-facing activity | Who | Commands | Gate / checkpoint | Saved |
|---|---|---|---|---|---|
| LR-0 Intake | setting up the review | orchestrator | as quick scan | level, question, seeds | as quick scan |
| LR-1 Scoping (round 0) | the first searches | literature-searcher | `find` × 2-3 phrasings; no ingest | at least one database answered; seed recall | `lit_search/round0/`, `output/preliminary_notes/{date}_scoping_round0.md` |
| ★ CP-1 | the scope check | orchestrator → user | after: `untested-checker` and `lit_verify vision-override` when the user chooses them | **Hard**: the plan with reads and cost lines (§ Plan and Cost Lines), the reference-checker and page-picture choices | `Protocol_v1.md`, STATE |
| LR-2/3 Search and screen | searching; choosing papers | literature-searcher | `find`, `cites`/`refs --s2-context`, `similar` per the protocol; `ingest --round R`; `screen` (`ta`); key-paper candidates | decisions complete | `lit_search/round{R}/`, tables |
| LR-3b Second screen (optional) | a second look at the choices | literature-searcher (opus), then a resolution pass | `screen sheet`, `screen record` (`second`, then `resolution`) | disagreements listed; borderline cases to CP-K | `screening_v*` |
| ★ CP-K | the key-paper list | orchestrator → user | — | the researcher agrees the list | STATE key-paper list with the user's words |
| LR-4 Acquire and check | getting the papers; checking the references | literature-searcher | `verify`, `retractions`, `attach`; `oa` → `web_fetch.sh` → `pdf_ingest` | each key paper ingested or "not retrieved" | `web_fetches/`, `papers/{key}/` |
| LR-5 Read | reading the key papers | paper-reader × n, waves of ≤ 5 | `lit_verify card` (≤ 2 revisions) | PASS, PARTIAL or NEEDS_REVIEW | `evidence_card{S}.md`, `card_check{S}.json` |
| LR-5a Reading audit | checking who read the pages | orchestrator | `lit_verify audit` per latest card; `lit_verify settle --list` on items a person compares | exit 0, or items listed for CP-R | `vision_audit{S}.json`, `settle_items{S}.txt` |
| LR-6 Round synthesis | writing up the round | literature-synthesizer (KIND draft) | `claims build`, `edges ingest`, `notes`, `findings`, `gaps`, `export-bib`, `counts`. Orchestrator: `lit_verify report --level standard`; `lit_corpus manifest --round R` | 0 FAIL | `output/synthesis_round{R}_v{N}.md`, `output/follow_up_plan_round{R}.md` |
| ★ CP-R | the round check-in | orchestrator → user | `quarto pandoc` HTML copy of the round synthesis before (§ HTML Copies for Reading); `lit_verify settle` on the user's page comparisons | (1) another round (2) change the plan (3) final | STATE decision; `audit_settlement{S}_{n}.json`; `synthesis_round{R}_v{N}.html` |
| ★ CP-G | the reference check | orchestrator → user | the reference checker (§ The Citation Second Check > The checker flow), then `glance-sheet --deliverable`, before; `record-human`, `lit_verify settle` (comparisons still open), `export-bib` after; a reference to check again: the searcher's check-only pass, `export-bib`, a new list | every reference the final needs is citable at final; every audit the final needs confirmed or settled | ledger, `reference_glance_v*`, `audit_settlement{S}_{n}.json` |
| LR-7 Final synthesis | writing the final review | literature-synthesizer (KIND final) | as LR-6 | — | `output/lit_review_final_v{N}.md` |
| LR-8 Verification | the final checks | orchestrator; data-verifier | `report --kind final`; claim-sample script; spot-check dispatch | 0 FAIL; sampled claims confirmed | `output/claim_spot_check_v{N}.md` |
| ★ CP-F | the final review | orchestrator → user | `quarto pandoc` HTML copy (§ HTML Copies for Reading); `lit_corpus manifest`; `collect_session_logs.sh` | approval; handoff offers | final manifest; `lit_review_final_v{N}.html` |

### Formal review

The standard flow with these changes (`formal-review.md`):

| Change | Where |
|---|---|
| CP-1 carries the 11-item protocol (`formal-review.md` § The protocol), versioned; the researcher approves it | CP-1 |
| Title-and-abstract screening by the searcher on opus; dual screening of the records the protocol names | LR-2/3 |
| **CP-S Full-text decisions** replaces CP-K: the searcher's primary `ft` pass is shown; the researcher decides every full-text inclusion and settles disagreements; recorded with `screen record`, pass `researcher`, their words in the rationale | after LR-4 |
| LR-5 reads every included paper; the reader drafts `appraisal` claims from the routed `guide-*.md` and a weight | LR-5 |
| **CP-A Checklist review** after each round's reads: the researcher confirms or changes each answer, gives each domain and overall judgment, and confirms or changes each weight | after LR-5a |
| The round synthesis drafts GRADE notes "for your rating"; the researcher's ratings are collected verbatim at CP-R and passed as RESEARCHER RATINGS; findings use `certainty_scheme: researcher_grade` | LR-6, CP-R, LR-7 |

**Second check before final, every level.** A reference whose rule check reads CONFIDENT is held as `pending_adjudication` and cannot be cited in a final deliverable until a second check confirms it. The citation-adjudicator runs in every review, before the reference glance; it confirms references by itself only when its identity is evaluated or the researcher accepted it (`untested-checker`), and only those it judges `SAME_WORK`. Every other reference is confirmed by the researcher's reference glance, with an untested checker's verdict shown beside it as a hint (§ The Citation Second Check).

---

## LR-0: Intake and Project Setup

1. **Level menu.** Read `{BASE_DIR}/.claude/skills/literature-review/SKILL.md` § The level menu and show it to the user as written (a targeted read of that section; the orchestrator does not load the skill). Default: standard review.
2. **Intake questions** (`literature-review/references/review-types-and-levels.md` § Questions to ask, by level): the question; papers the user expects to find (seeds); materials; for standard and formal, the review type (default from the intent menu). A level change later is a new protocol version.
3. **Create the project** `{BASE_DIR}/research/{YYYY-MM-DD}_LitReview_{Short_Topic}/`, one `mkdir -p` per call: the project root, `output/preliminary_notes/`, `lit_inputs/`, `scripts/`, `user_pdfs/` (`cp` does not create it, and the user may be told to add a PDF there at any check-in). Other folders are created by the tools on first use.
4. **STATE.md** from `{BASE_DIR}/agent_reference/STATE_TEMPLATE_LITREVIEW.md`: Project (title, level, review type, question, folder), `Scope Check status: awaiting confirmation`, Current Position LR-0.
5. **LEARNINGS.md** skeleton (§ LEARNINGS.md).
6. **Route record:** `bash {BASE_DIR}/scripts/lit_verify.sh route {PROJECT_DIR} --reader-model {ID}`, where {ID} is the exact model ID the paper-reader dispatch resolves to. Copy its first two lines (`ROUTE: <name>`, `VISION: <value>`) verbatim into STATE's Route record. Never type either. If it prints a `WARNING for the researcher` line, that text goes into CP-1's page-pictures paragraph as it stands. Run it at every level; `lit_verify audit` counts only a route row recorded no later than the card check.
6a. **Reference-checker status:** run the identity check (§ The Citation Second Check > Tested or untested) for the model the `opus` tier resolves to, and record in STATE's AI Reference Check section whether that checker is tested or not yet tested; CP-1's checker paragraph says which.
7. **Read first** (`SKILL.md` § Scope Check > Read First): background materials in full, or through one `search-agent` digest dispatch (§ Dispatch Templates > Materials digest) writing into `{PROJECT_DIR}/materials/` and `{PROJECT_DIR}/output/preliminary_notes/{date}_{slug}_materials-digest.md`. A PDF outside `/daaf` is copied first, one `cp` per call, into `{PROJECT_DIR}/user_pdfs/` (`pdf_ingest` refuses sources outside `/daaf`). A paper the user wants reviewed is copied the same way and listed as a seed; it is not ingested at scoping (§ Scope Check carve-out).
8. **Standard and formal:** dispatch LR-1 scoping. **Quick:** go straight to CP-1 (short form).

---

## Plan and Cost Lines

Shown at CP-1 and in each follow-up plan. Token figures are inference from the reading cost per page; label them as estimates.

| Line | Estimate |
|---|---|
| Searches | phrasings × databases, plus citation-following hops; OpenAlex within its free daily budget (the amounts: `scholarly-search` `references/openalex.md` § Cost and limits), each round reporting how much of it was used |
| Screening | records per round from the scoping volume; the share likely to pass the first look |
| Deep reads | n papers × (pages × 0.8-1k text tokens + cited flagged pages × ~4k image tokens), shown as a dispatch count, waves of ≤ 5, and a token range of the user's plan usage |
| Reference check (the researcher's look over the list) | one list per final deliverable; about 1 minute per 10 references for the researcher |
| Paid searches | none unless the user approves named calls (CP-1 decision; recorded as SPEND APPROVED) |
| AI reference check (every review) | ~1.5-2.5k tokens per reference row; up to 30 rows per dispatch; every CONFIDENT plus every WEAK row, once per row |

A paper's page count and its `pages_needing_vision` come from its ingest manifest (the searcher's LR-4 return), so the deep-read line is refined at CP-K.

---

## Rounds and the Check-In

A round is one cycle of searching, screening, reading and round synthesis, then CP-R. The follow-up plan (`output/follow_up_plan_round{R}.md`) lists three options, and CP-R presents them:

| Option | What happens |
|---|---|
| (1) Another round | Dispatch LR-2/3 with `ROUND: R+1`, the same protocol version, and the follow-up plan's searches and citation-following steps; the round-1 corpus, screening and cards carry over |
| (2) Change the plan | The orchestrator writes `Protocol_v{N+1}.md` with the user's changes (phrasings, sources, criteria, level, stopping rule), records the decision in STATE, and the next round runs that version. A level change follows `review-types-and-levels.md` § Changing level or re-steering |
| (3) Write the final review | CP-G, then LR-7, LR-8 and CP-F |

When the protocol's stopping rule is met, the follow-up plan recommends (3); the user decides. Seed recall and saturation (`gaps-and-saturation.md`) are reported at every CP-R. The round's manifest (`lit_corpus manifest --round R --protocol Protocol_v{N}.md`) is written before CP-R.

---

## The Citation Second Check

The citation-adjudicator (the AI reference check) is dispatched in every review, before each reference glance, whatever model the `opus` tier resolves to. What its verdicts do depends on whether its identity is tested and on the researcher's choice (`literature-review/references/lit-corpus.md` § Citation second check):

| Checker | Its `SAME_WORK` | Its `DIFFERENT_WORK` / `UNCERTAIN` |
|---|---|---|
| Tested: the in-force entry of `ADJUDICATOR_EVALUATED_LISTS` holds its whole identity | confirms: `model_confirmed` (CONFIDENT), `model_adjudicated` (WEAK at or above the title floor, not `org_unchecked`) | `DIFFERENT_WORK` rejects (`rejected`); `UNCERTAIN` goes to the glance |
| Not yet tested, and the researcher accepted it for that model ID (`untested-checker`, in force at ingest) | confirms: `model_confirmed_untested`, labelled "confirmed by an untested AI check (your choice)" (CONFIDENT, or WEAK under the same floor rules) | hints on the glance; the researcher decides |
| Not yet tested (the default) | a hint on the glance | a hint on the glance |

A hint changes no status: the reference reaches the researcher's glance with the checker's verdict and its one-line reason beside it, and the sheet lists the references it calls a different work, then those it could not judge, first. Only a reference the checker confirmed skips the reply; the sheet still lists it, labelled.

### Tested or untested: the identity check

Run it at LR-0, and again whenever the model the `opus` tier resolves to changes (§ Checkpoint Templates > When the model or setup changes). A checker is tested only when the in-force entry of `ADJUDICATOR_EVALUATED_LISTS` holds a 4-tuple `(model_id, template_sha256, rubric_version, agent_file_sha256)` equal to the identity about to be dispatched (`literature-review/references/lit-corpus.md` § Citation second check > Evaluated identities):

1. `grep -n -A6 "^ADJUDICATOR_EVALUATED_LISTS" {BASE_DIR}/scripts/lit_corpus.py` and `grep -n "^ADJUDICATOR_LIST_VERSION" {BASE_DIR}/scripts/lit_corpus.py`. An empty tuple for the in-force version (the shipped `adjudicator-list-none`) means every checker is not yet tested.
2. Only when the entry is non-empty: a captured script `scripts/lr_adjudication/{NN}_identity_check.py` prints the template body's sha256 (extracted per `scholarly-search/references/citation-adjudication.md` § The extraction contract), the rubric version from its start marker and the sha256 of `.claude/agents/citation-adjudicator.md`; the checker is tested only on an exact match with the model ID the `opus` tier resolves to in this session (STATE's Subagent Model Tiers row), because the Agent tool's `model` parameter takes a tier alias, not a model ID. The same script prints today's sha256 of `CLAUDE.md` beside the one the evaluation ran under (`ADJUDICATOR_EVALUATED_CLAUDE_MD` for the in-force list version, imported from `lit_corpus`), and, when they differ, a plain line `WARNING: CLAUDE.md has changed since the adjudicator's evaluation; consider a small re-check`. The checker stays tested on that difference: CLAUDE.md is general guidance outside the adjudicator's read-only task and changes often, so it is recorded with the identity but never part of it; the warning is for a person to weigh a small re-check, recorded in STATE.

`ingest` decides how each batch counts from the identity it packed, not from this check; the check tells the orchestrator what to say at CP-1. The researcher's choice for an untested checker is recorded after CP-1 (§ Checkpoint Templates > Recording the choices).

### The reference glance (every review)

Every final deliverable's references reach the researcher, at every level, as one list and one reply. The checker flow (below) runs first, so the list carries its confirmations and hints.

1. **Sheet:** `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications glance-sheet {PROJECT_DIR} --deliverable {deliverable path} [--keys K1,...]`. `--deliverable` names the draft the final will rest on; `--keys` names, by paper key, papers the final will cite beyond it. The extra keys are added to the draft's references, so one sheet and one reply cover both. They include every held reference (the round synthesizers' "Held for the reference glance") that the captured rows script of step 4 shows as undecided, CONFIDENT or WEAK, with `reply_can_decide` True: on the sheet it gets a number and a normal reply (CP-G "Building the list" sorts the other held references). It writes `output/reference_glance_v{N}.md` and `output/reference_glance_v{N}_rows.txt`.
2. **Show it** at CP-G (quick scan: CP-F): inline the table when it has 30 rows or fewer, else give the path and inline only the rows that need attention (partly matches, does not match, retracted, and those the AI reference check thinks may be a different work or could not judge) and the rows the sheet says are left out of the reference list. Copy the sheet's sentences about the references it will leave out, word for word (they name each by number and say how to ask for one to be checked). When a title on record starts with "Does not match:" or "Not compared:", copy the sheet's note about that label (all of its sentences), word for word, above the table: it says what that record is and, for "Does not match:", that a reference kept anyway is cited from that record. When the sheet carries the note that DAAF's AI reference check has not been tested with the model it ran on, copy that note (both of its sentences when it has two), word for word, above the table as well.
3. **Rows files** from the reply. Copy lines verbatim from `reference_glance_v{N}_rows.txt` into one file per decision, `{PROJECT_DIR}/lit_inputs/glance_v{N}_{decision}_{seq}.txt` (for "all look right": the whole rows file can be passed as is). Never type a row hash.
4. **Record**, one Bash call per decision, with the user's words copied verbatim from their message (never a paraphrase, never a subagent's text):

   ```
   bash {BASE_DIR}/scripts/lit_corpus.sh adjudications record-human {PROJECT_DIR} --rows {rows file} --decision same_work --user-words "{the user's words}" --rationale "The researcher compared each title as cited with the title on record in reference_glance_v{N}.md"
   ```

   `--rationale` is required for every decision except `defer`, `different_work` included. `different_work` for a reference the user says is a different work (→ `rejected`); `defer` (no rationale) for "I'll check later" (stays uncitable at final). A row whose check reads "does not match the record" (MISMATCH) takes only `override_mismatch` or `defer`. Overrides: a reference whose check reads "does not match the record" that the user keeps is `--decision override_mismatch` with **its own rows file** and a `--rationale` stating the user's reason; the deliverable labels it "accepted by the researcher despite the automatic reference check". MISMATCH rows are not in the glance rows file: take their hashes from a captured script `scripts/lr_adjudication/{NN}_rows_{label}.py` (the same script sorts the held references at step 1 and CP-G). It prints `paper_key`, `citekey`, `verify_verdict`, `verify_row_sha256` and `citation_status` from the latest `data/corpus_v{N}.parquet`, and two columns computed with functions it imports from `lit_corpus` (from `{BASE_DIR}/scripts`): `reply_can_decide(verify_verdict, row_verdict)` and `left_out`, which is `glance_left_out(corpus_row, row_verdict)`, the sheet's own rule (`not reply_can_decide(row.get("verify_verdict"), row_verdict) and read_status(row.get("citation_status")) not in CITABLE_FINAL + ("rejected",)`). `row_verdict` is the `verdict` of the row, in any `lit_search/**/MANIFEST.jsonl` (searched recursively, as `search_rows` does), whose sha256 is the paper's `verify_row_sha256`: each line is hashed as `manifest_rows` splits the file (`f.read().split(b"\n")`), so the trailing `\n` is not hashed and a `\r` before it is. No such row (or no verify row): `row_verdict` is None, so `reply_can_decide` is False. Only a MISMATCH row whose `reply_can_decide` is True takes `override_mismatch`; the decision command refuses any other. A reference the list says is left out cannot be recorded (`record-human` refuses it, exit 11): it stays out of the reference list unless the researcher asks for it to be checked again.

   **Check again** (its own decision, distinct from "I'll check later", which is `defer`): when the researcher asks for a left-out reference to be checked again ("check 7 again", or "check 7" for one never checked), record the reply's other decisions first, from this list's rows files, then dispatch the literature-searcher's check-only pass for those references (§ Dispatch Templates > literature-searcher: LR-4 acquire and check, with `TASK: LR-4' check only`, `ROUND:` the current round, `KEYS:` their paper keys and `CORRECTED CITATIONS:` any title or DOI the researcher gave, quoted). The searcher runs `verify` again and attaches the new rows. Then run `export-bib` and the rows script again, the checker flow (its `pack` selects the new rows that read CONFIDENT or WEAK, which the checker has not judged), then `glance-sheet` again with the same flags, adding to `--keys` every held reference the rows script now shows as undecided, CONFIDENT or WEAK, with `reply_can_decide` True (CP-G "Building the list"), so a held reference the new check made confirmable gets a number; held references are re-sorted from the same output. Show the new list (`reference_glance_v{N+1}.md`) at the same checkpoint. `record-human` is never called for this request. A new check promises no match: a reference it still cannot confirm stays left out, and the new list says so. When the searcher reports a corrected DOI it did not attach, tell the user in plain words that the DOI they gave belongs to a different record from the one the review holds, so the reference stays left out; adding the paper under that DOI is a new search, which runs only with their approval, through the round's usual searching and choosing of papers.
5. **Export:** `bash {BASE_DIR}/scripts/lit_corpus.sh export-bib {PROJECT_DIR}`, so the reference list carries the statuses `report` reads.
6. **STATE:** the glance version, the rows files, each `record-human` call and its decision, and each check-again request (decision `check_again`, with the searcher dispatch and the keys), in the Adjudication and glance batches table.

`record-human` sits behind the Ask-First rule `Bash(*lit_corpus*record-human*)` in `.claude/settings.json`, so the user approves the call that shows their own words; run it as its own Bash call and never inside a script. The same holds for `lit_verify settle` with `--decision`, behind `Bash(*lit_verify*settle*--d*)` (§ Readings From Pictures of Pages: the Audit and the Person's Comparison, step 4), and for the two choices recorded after CP-1, `lit_corpus adjudications untested-checker` behind `Bash(*lit_corpus*untested-checker*)` and `lit_verify vision-override` behind `Bash(*lit_verify*vision-override*)` (§ Checkpoint Templates > Recording the choices). `run_with_capture.sh` refuses a script that calls `record-human`, `settle --decision`, `untested-checker` or `vision-override` (exit 3, `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` § Researcher-Decision Command Scan).

### The checker flow (every review, before the glance sheet)

Run it before the glance sheet of every final deliverable (CP-G; quick scan: CP-F), on the references whose check reads CONFIDENT or WEAK and whose status is undecided (`pending_adjudication` or `unverified`). `pack` selects them itself and skips those the checker has already judged, unless a judgment now would count for more: a checker now on the evaluated list, or one the researcher has since accepted (`literature-review/references/lit-corpus.md` § Citation second check > `pack`, "Already judged"). So another untested model, or a framework update that changes the checker's files, does not judge the hinted references again. A reference the researcher asks to have checked again gets a new check, and that new row runs through this flow before the new sheet. Dispatches count toward the 5 in flight (§ Subagent Invocation > Dispatch rules).

1. **Pack** through a captured script, `{PROJECT_DIR}/scripts/lr_adjudication/{NN}_pack_batch_{batch_id}.py` (batch ids `b01`, `b02`, …): a flat script that runs `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications pack {PROJECT_DIR} --batch {batch_id} --model-id {exact model ID} --max-rows 30` with `subprocess.run`, its stdout reaching the script's stdout unchanged, and asserts exit 0. `pack` takes at most 30 references per batch; the next batch's `pack` skips the ones already held or judged and takes the rest, so a batch of fewer than 30 rows means none is left. A `pack` that finds nothing to select exits 11 ("no reference to pack", each paper's reason in its MANIFEST row): no batch is needed, and the failed script stays as the record, unrevised. When the researcher asks the checker to look again at a reference whose check did not change, pack it by name with `--keys {K1,...} --rejudge` (`--rejudge` needs `--keys`; it lifts only the already-judged skip). `--model-id` is the exact model ID the `opus` tier resolves to in this session (STATE's Subagent Model Tiers row), in the form `ingest` compares: a trailing `[1m]` dropped and a dotted Claude ID hyphenated (`claude-opus-5.5` becomes `claude-opus-5-5`); a provider prefix such as `anthropic/` is kept, so `ingest` then needs the transcript to record that same prefix, and the ID matches only an evaluated-list entry that names it with the prefix. `pack` refuses any other form (exit 1, nothing packed) and names the form to pass; put that form in a revision of the script. Execute it with `bash {BASE_DIR}/scripts/run_with_capture.sh {that path}`; the hashes land in its immutable log, which `ingest` reads.
2. **Dispatch** (§ Dispatch Templates > citation-adjudicator): the prompt is the content of `data/adjudication_bundles/{batch_id}_prompt.txt`, verbatim, nothing added; `model: "opus"`, the tier alias whose resolved ID pack recorded (the Agent tool takes tier aliases, not model IDs). One bundle per dispatch. `ingest` checks which model ran, as evidence, not proof: it reads the adjudicator's own Claude Code transcript (found from the agent ID) and requires at least one model there, every one the packed model ID; for a tested identity a failure refuses the batch, for an untested one it keeps the batch as hints only (step 4). Never dispatch when the `opus` tier resolves to a model other than the one packed.
3. **Persist** only the lines inside the return's `jsonl` fence to `{PROJECT_DIR}/data/adjudication_raw/{batch_id}.jsonl`. The return is the agent's report wherever it arrives: in the Agent tool result, or in a separate hand-back message from the checker that the result points to; the checker delivers it with SubagentHandback, the one tool besides Read that `adjudicator-read-scope.sh` lets it call, and `ingest` accepts that tool's records in the audit log. NOT_JUDGED: persist nothing; re-dispatch the same prompt. If the return quotes an `adjudicator-read-scope.sh` refusal of the bundle path, do not re-dispatch: the same prompt carries the same path, which the hook refuses (a project outside `research/`, or a symlink on the path); report it to the user.
4. **Ingest:** `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications ingest {PROJECT_DIR} --batch {batch_id} --agent-id {agent ID from the dispatch result}`, soon after the return (Claude Code deletes transcripts after `cleanupPeriodDays`, 30 days by default; without the transcript `ingest` exits 10). Its first output line says whether the identity is on the evaluated list and, for an untested one, whether the researcher's acceptance applies ("its same-work verdicts confirm references (labelled)") or the verdicts are "hints only". Exit 11 naming the transcript's model (a tested identity): the batch ran on another model and none of its judgments count; release it (below) and pack its rows in a new batch, with `--model-id` the model the `opus` tier resolves to then (step 1). Exit 0 with a `WARNING` that the transcript records another model (an untested identity): the batch is kept as hints only, and no acceptance applies to it; record it in STATE and treat it as a model change (§ Checkpoint Templates > When the model or setup changes).
5. **Glance** the rows still undecided (every hint; `UNCERTAIN`; below the title floor; `org_unchecked`) as above; a user reversing a model's `DIFFERENT_WORK` is `same_work` with a rationale (→ `human_overridden`, "accepted by you" in messages to the user). A reference the checker confirmed needs no reply; if the user says one is a different work, record `different_work` with its row hash from the rows script, as for a MISMATCH row.

Never re-pack a packed batch that is not yet ingested (re-dispatch that bundle). When a batch will not be ingested (never dispatched, a captured pack script that failed, or a batch `ingest` refused), release it, one Bash call: `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications release {PROJECT_DIR} --batch {batch_id} --reason "{why, in a sentence}"`. Its rows can then be packed in a new batch (a new batch id); the released bundle stays on disk and is never ingested. An ingested batch is never released. `release` decides no reference, so it needs no permission prompt; record it in STATE's Adjudication and glance batches. Never edit `.claude/agents/citation-adjudicator.md` between pack and ingest: the batch would count as unevaluated.

---

## Readings From Pictures of Pages: the Audit and the Person's Comparison

1. **Audit** each reader's latest card, once, after the reader returns, in the session that dispatched the reader: `bash {BASE_DIR}/scripts/lit_verify.sh audit {PROJECT_DIR}/papers/{key} --card {card file name} --agent-id {agent ID} --project {PROJECT_DIR}`, with one `--agent-id` per reader dispatch that worked on the card, each copied from that dispatch's result (a chunked paper: one per chunk). Only the context-reporter hook's own record of a reader's model, kept for the current session, confirms the model. `--transcript {path}` (a reader's `agent-{ID}.jsonl`, located by a `find` probe) is read only when the hook has no record for that ID, and it never confirms the model: a model it shows that differs from the card's gives `mismatch`, and a matching one still sends every reading from a picture of a page to a person's page comparison (`person_must_check`). The record is exclusive-create: a second audit needs a new card version.
2. **Outcome** (exit 0: `confirmed`, `confirmed_with_checks`, `confirmed_untested_reader`; exit 11: `person_must_check`, `mismatch`, `chain_unconfirmed`). Record it in STATE's Reader table. `confirmed_with_checks`: show the reason text of its `SHOULD LOOK:` lines (never the tag) at CP-R as numbers worth a look, under the paper each belongs to; nothing to record. Outcome `confirmed_untested_reader` (exit 0): the user chose to accept an untested reader's readings. Nothing to compare; the report labels the paper's citations (`VISION_READ_BY_UNTESTED_MODEL`) and the final deliverable's methods or AI-use note must say so. Under the user's choice "check", an untested reader's picture readings come back as `person_must_check` and follow step 3.
3. **List what a person compares** (`person_must_check`, `mismatch`): `bash {BASE_DIR}/scripts/lit_verify.sh settle {PROJECT_DIR}/papers/{key} --audit vision_audit{S}.json --list`. It prints one plain reason per reading and writes `settle_items{S}.txt`, the item ids the reasons belong to. At CP-R (or CP-G when still open) show the user the reason texts under the paper each belongs to (its short reference and PDF path), numbered across the check-in (§ Checkpoint Templates > Building and recording the page comparisons); never an item id, the `(optional)` prefix or the `next (for the agent)` line.
4. **Record the reply**, one call per decision, the user's words verbatim: `bash {BASE_DIR}/scripts/lit_verify.sh settle {PROJECT_DIR}/papers/{key} --audit vision_audit{S}.json --items {items file} --decision matches|does_not_match --user-words "{the user's words}" [--rationale "{reason}"]`. The items file holds item ids, one per line, as `--list` wrote them: pass `settle_items{S}.txt` itself when the reply covers every item, else write `{PROJECT_DIR}/lit_inputs/settle_{key}{S}_{decision}_{seq}.txt` with the ids the reply covers, copied verbatim. The number the user replied with leads to its id through the mapping recorded in STATE's Reading Items for a Person when the comparisons were numbered (each number, its paper and the item id, copied from `--list`'s output and `settle_items{S}.txt`). `does_not_match` needs `--rationale` (which number, what the page prints). It writes `audit_settlement{S}_{n}.json` in PAPER_DIR and a MANIFEST row. Exit 0 recorded; 11 refused, nothing written (empty words, a missing rationale, an id twice or not this audit's); 9 the card or audit changed since the audit (a new card version and audit are needed); 8 an unreadable items file.
5. **`does_not_match`:** dispatch the reader again for that paper (§ Dispatch Templates > paper-reader, with the correction line): a new card version that reads those numbers from the page text or drops them; then `card`, a new audit and, if needed, a new comparison.
6. **`chain_unconfirmed`** is never settled by a comparison. It matters only when the card takes readings from pictures of pages: then the searcher fetches the paper again (`web_fetch.sh` into `web_fetches/`) or the user places their PDF in `user_pdfs/`, and it is ingested again and read again. A card that reads text only needs no re-fetch, because the final check gates only cards with picture readings; record the outcome in STATE and go on.

A final deliverable cannot cite a paper whose card has readings from pictures of pages unless its audit confirmed them or every listed item is settled by a person's record (`literature-review/references/lit-verify-report.md` § What is checked > Readings from pictures of pages). An audit confirms only when every reader's model came from the hook's own record; the final check counts any other confirming audit as not confirmed (`model_not_confirmed`, which no comparison settles; the report's reason gives the fix). Readings accepted under the user's choice "accept" stay citable only while that choice (level, model and setup) is in force: once it is withdrawn or changed, `settle --list` lists them as required comparisons, and the final check reports them as not confirmed (`override_withdrawn`) until each is settled or the same choice is recorded again.

---

## Subagent Invocation

| Agent | `subagent_type` | Model | Stages |
|---|---|---|---|
| literature-searcher | `literature-searcher` | `sonnet`; `opus` for formal screening and every second-screener or resolution pass | LR-1, LR-2/3, LR-3b, LR-4, LR-4' |
| paper-reader | `paper-reader` | `opus` (on GPT routes the sonnet tier reads PDFs as text only) | LR-5 |
| literature-synthesizer | `literature-synthesizer` | `opus` | LR-6, LR-7, LR-7Q |
| citation-adjudicator | `citation-adjudicator` | `opus` (the tier whose resolved model ID `pack --model-id` recorded) | before every reference check (CP-G; quick scan: CP-F) |
| data-verifier | `data-verifier` | `opus` (never downgraded) | LR-8 |
| search-agent | `search-agent` | `sonnet` | LR-0 materials digest |

**Dispatch rules.**
- **One literature-searcher at a time.** `scholar_search` calls share one rate gate; two searchers in flight throttle each other.
- **Readers in waves of at most 5**, one paper per dispatch (`SKILL.md` § Subagent Coordination > "Parallel Dispatch Guideline"; more only with the user's explicit approval, recorded in STATE).
- **The orchestrator runs every gate it does not author:** `lit_verify route`, `report`, `audit`, `settle`, `vision-override`, `adjudications pack`/`ingest`/`release`/`record-human`/`glance-sheet`/`untested-checker`, `lit_corpus manifest`. The synthesizer never runs `report` on its own deliverable.
- **Agent IDs:** record every dispatch's agent ID in STATE (reader table, one row per chunk; adjudication batches): `audit` needs every reader dispatch's ID for a card, and `ingest` needs the adjudicator's.
- **User preference "PDF page-image cross-checking"** (CLAUDE.md § User Preferences): copy its value into every paper-reader dispatch and the data-verifier dispatch. Under `all-pages` the searcher ingests with `--render all`; otherwise `--render flagged` (renders exist for a later validated reader or a person even under `off`).
- **Window and image cap:** DAAF's rule: `WINDOW: 1M`, `IMAGE CAP: 30` only when the session's own model ID carries `[1m]` and STATE's Subagent Model Tiers row shows the `opus` tier resolving to that same model; otherwise `WINDOW: 200k`, `IMAGE CAP: 8`. The cap of 30 is an estimate, not a measured limit.
- **Language directives** do not apply: no agent in this mode writes analysis code for the user's data.
- **Subagent return processing** follows `SKILL.md` § Subagent Coordination > "Subagent Return Processing". Persist the searcher's and synthesizer's full returns to `output/preliminary_notes/{date}_{stage}_r{R}_{agent}.md`; a reader's card and `card_check` are its record (persist only an INCOMPLETE or BLOCKED return).

> **Wave barrier discipline (async dispatch).** The barrier applies however subagent results arrive. Treat mid-wave notifications as status-only: do not run the round synthesis, present CP-A or CP-R, or decide on re-dispatches until EVERY reader in the wave has returned and its card is audited. Synthesize once, over the complete wave: an early return (a chunk handoff, context pressure) or a failed reader still counts as that member's completion, handled in the whole-wave review. See the master statement in `SKILL.md` § Subagent Coordination > "Wave Barrier Discipline (Async Dispatch)."

### Reader dispatch cycle (per paper)

```
STEP 0  ls papers/{key}/ → INGEST manifest path; next free card name; prior chunk notes
STEP 1  size it: pages and cited flagged pages from the ingest manifest
        > ~60 pages, or more cited flagged pages than the image cap → page-range chunks
STEP 2  dispatch paper-reader (whole paper, or chunk 1 of m); record agent ID in STATE
STEP 3  WAIT for the whole wave
STEP 4  CHUNK_HANDOFF → dispatch the remaining range with PRIOR CHUNK NOTES (STATE: chunk k of m)
        CARD_CHECKED → lit_verify audit on the latest card (once; an --agent-id per chunk) → STATE reader table
        audit exit 11 → settle --list → items to CP-R
        INCOMPLETE (FAIL after 2 revisions) → no findings from this card; re-dispatch on opus or ask the user
        BLOCKED → resolve (re-ingest by the searcher, a missing field, a scan without validated vision)
STEP 5  UPDATE STATE (reader table, open review items, files)
```

---

## Dispatch Templates

Fields follow each agent file's Invocation section; extra lines are named in the agent's Inputs table or marked as mode additions. All paths absolute. Never name a Markdown file whose basename starts with `report`, `summary`, `findings` or `analysis` (CLAUDE.md § Subagent File Output).

### literature-searcher: LR-1 scoping (round 0)

```
Agent(subagent_type: "literature-searcher", model: "sonnet", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   LEVEL: {standard|formal}   ROUND: 0
TASK: LR-1 scoping
PROTOCOL: none (LR-1 feeds the first protocol). Phrasings: {2-3}; keyword query: {query}; sub-questions: {list}   SEEDS: {list or none}
KEYS: none
DEST: lit_search/round0/   web_fetches/   papers/
SPEND APPROVED: none
USER-REFERENCED MATERIALS: {seed PDFs in user_pdfs/, relative to PROJECT_DIR | none} (listed only: not added or ingested in round 0)
WRITE INPUTS TO: lit_inputs/
RETURN: counts, seed recall, reference statuses, not-retrieved list, spend used, issues; the scoping record at output/preliminary_notes/{date}_scoping_round0.md
""")
```

### literature-searcher: LR-2/3 search and screen (round R)

```
Agent(subagent_type: "literature-searcher", model: "{sonnet | opus at the formal level}", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   LEVEL: {quick|standard|formal}   ROUND: {R}
TASK: LR-2/3 search and screen
PROTOCOL: {PROJECT_DIR}/Protocol_v{N}.md   SEEDS: {list or none}
KEYS: none (screen every paper this round added)
DEST: lit_search/round{R}/   web_fetches/   papers/
SPEND APPROVED: {none | the named paid calls the user approved}
USER-REFERENCED MATERIALS: {seed PDFs in user_pdfs/ to add with add-record and ingest | none}
WRITE INPUTS TO: lit_inputs/
KEY-PAPER CANDIDATES: {standard: up to {k}, one line of reason each | quick and formal: none}
FOLLOW-UP STEPS: {round ≥ 2: the searches and citation-following steps of output/follow_up_plan_round{R-1}.md | none}
RETURN: counts, seed recall, reference statuses, not-retrieved list, spend used, issues
""")
```

Round 1: the whole-MANIFEST `ingest` also takes in the round-0 scoping calls; the return says so, and STATE's round table notes it.

### literature-searcher: LR-4 acquire and check (LR-4' at the quick level, and for a re-check from the reference check at any level)

```
Agent(subagent_type: "literature-searcher", model: "sonnet", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   LEVEL: {quick|standard|formal}   ROUND: {R; a re-check from the reference check: the current round}
TASK: {LR-4 acquire and check | LR-4' check only}
PROTOCOL: {PROJECT_DIR}/Protocol_v{N}.md   SEEDS: {list or none}
KEYS: {standard: the approved key papers | formal: every paper included or maybe at ta | quick: every includable paper | a re-check from the reference check (LR-4' at any level): the references the researcher asked to have checked again}
DEST: lit_search/round{R}/   web_fetches/   papers/
SPEND APPROVED: {none | named calls}
USER-REFERENCED MATERIALS: {user PDFs for these keys | none}
WRITE INPUTS TO: lit_inputs/
CORRECTED CITATIONS: {a re-check from the reference check: per key, the title or DOI the researcher gave, quoted from their reply | none}
INGEST RENDER: {flagged | all (the user's PDF page-image preference is all-pages)}   (passed as pdf_ingest --render)
FULL-TEXT DECISIONS: {formal: yes, primary ft pass for every retrieved paper | no}
RETURN: counts, seed recall, reference statuses, not-retrieved list, spend used, issues; per paper: pages, pages_needing_vision, lanes_unavailable
""")
```

### literature-searcher: second-screener pass and resolution pass

```
Agent(subagent_type: "literature-searcher", model: "opus", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   LEVEL: {standard|formal}   ROUND: {R}
TASK: {second-screener pass (stage {ta|ft}) | resolution pass (stage {ta|ft})}
PROTOCOL: {PROJECT_DIR}/Protocol_v{N}.md   SEEDS: none
KEYS: {the paper keys to screen}
DEST: lit_search/round{R}/   web_fetches/   papers/
SPEND APPROVED: none
USER-REFERENCED MATERIALS: none
WRITE INPUTS TO: lit_inputs/
RESOLUTION CASES: {resolution pass only: per key, both decisions and both rationales, quoted from the screen record output | none}
RETURN: counts, disagreement count from screen record, issues; borderline cases for the researcher
""")
```

A second-screener prompt carries the criteria and KEYS only: never the first screener's decisions, rationales or counts (RESOLUTION CASES is `none`). A second screener records its pass once: `screen record` prints the disagreement count after it records, and a second `screen record` of the same pass after seeing that count is never allowed (re-dispatch a fresh second screener instead, if a pass must be redone). Borderline cases from a resolution pass go to CP-K (standard) or CP-S (formal).

### paper-reader: whole paper, or chunk k of m

```
Agent(subagent_type: "paper-reader", model: "opus", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   PAPER_KEY: {key}   LEVEL: {standard|formal}
INGEST: {PROJECT_DIR}/papers/{key}/ingest_manifest{S}.json   PAGES: {1-N | a-b (chunk k of m)}
PRIOR CHUNK NOTES: {absolute paths of chunk_notes_p{a}-{b}.md from earlier chunks | none}
QUESTION: {review question, verbatim from the protocol}
KEY REFERENCES TO TRACE: {paper keys or external:<doi or W-id> | none}
RECORD: {citekey, title, authors, year, venue, DOI or OpenAlex id, as printed by the searcher's index script | none}
ROUTE: {the line copied verbatim from STATE's Route record | omit the line when none was recorded}
VISION: {the line copied verbatim from STATE's Route record | omit the line when none was recorded}
WINDOW: {200k|1M}   IMAGE CAP: {8|30}
PDF page-image cross-checking (user preference): {auto|all-pages|off}
GUIDE (formal only): {BASE_DIR}/.claude/skills/literature-review/references/guide-{design}.md
WRITE CARD TO: {PROJECT_DIR}/papers/{key}/evidence_card{S}.md   then run lit_verify card (at most 2 revisions)
RETURN: verdict, grade, items for a person, images opened, model ID self-report
""")
```

- **WRITE CARD TO** names a free card file: `evidence_card.md` for a first reading, else the next letter after the highest existing card (`ls` first). The card suffix is independent of the ingest suffix; `card_check{S}.json` and `vision_audit{S}.json` follow the card's.
- **KEY REFERENCES TO TRACE:** the approved key papers this paper may cite, and seeds, as paper keys; a reference outside the corpus as `external:<doi>` or `external:<W-id>`.
- **GUIDE:** routed by the design of the result the review uses (`formal-review.md` § Routing a study to a guide); one guide per dispatch.
- **Correction dispatch** (after a `lit_verify settle --decision does_not_match` record, or a `mismatch` audit the user wants re-read): add, before RETURN, the line `CORRECTION: the researcher compared {items} with the page and found they do not match; read these numbers from the page text or leave them out, text only` (named in paper-reader's Inputs), and a free WRITE CARD TO.
- At the standard and formal levels the reader drafts `study_weight`; at the formal level the researcher confirms or changes it at CP-A. "NI" or "not reported" checklist answers go in the card's Appraisal prose, not in claims.

### literature-synthesizer: quick-scan memo

```
Agent(subagent_type: "literature-synthesizer", model: "opus", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   LEVEL: quick   ROUND: 1
DELIVERABLE: quick_scan   KIND: {draft | final (only when the final check failed on the memo the user saw, e.g. a reference the reply left out)}   VERSION: {N}
PROTOCOL: {PROJECT_DIR}/Protocol_v{N}.md
QUESTION: {verbatim}
KEY PAPERS (approved): none
READER TABLE: none
RESEARCHER RATINGS: none
RESEARCHER DECISIONS: {verbatim | none}
PRIOR DELIVERABLE: {path | none}   REVISE FROM: {*.report_check.json path | none}
WRITE TO: output/   WRITE INPUTS TO: lit_inputs/   SCRIPTS: scripts/lr_synthesis/
RETURN: deliverable path, findings and gaps recorded, references by status, held references, items for the researcher
""")
```

### literature-synthesizer: round synthesis

```
Agent(subagent_type: "literature-synthesizer", model: "opus", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   LEVEL: {standard|formal}   ROUND: {R}
DELIVERABLE: round_synthesis   KIND: draft   VERSION: {N}
PROTOCOL: {PROJECT_DIR}/Protocol_v{N}.md
QUESTION: {verbatim}
KEY PAPERS (approved): {standard: paper keys, with the researcher's approval line quoted | formal: the full-text inclusions, with the CP-S record}
READER TABLE: {per paper: card path, page-check verdict, reading-audit outcome, settle record}
RESEARCHER RATINGS: {formal: finding: the researcher's words, verbatim, from an earlier CP-R | none}
RESEARCHER DECISIONS: {verbatim; formal: each weight the researcher confirmed or changed at CP-A, to record with notes record, decided_by {role: researcher, researcher_instruction: <their words>, recorded_by: literature-synthesizer, model_id} | none}
PRIOR DELIVERABLE: {path | none}   REVISE FROM: {*.report_check.json path | none}
WRITE TO: output/   WRITE INPUTS TO: lit_inputs/   SCRIPTS: scripts/lr_synthesis/
RETURN: deliverable path, findings and gaps recorded, references by status, held references, items for the researcher
""")
```

### literature-synthesizer: final synthesis

```
Agent(subagent_type: "literature-synthesizer", model: "opus", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   LEVEL: {standard|formal}   ROUND: {last R}
DELIVERABLE: final_synthesis   KIND: final   VERSION: {N}
PROTOCOL: {PROJECT_DIR}/Protocol_v{N}.md
QUESTION: {verbatim}
KEY PAPERS (approved): {as for the round synthesis}
READER TABLE: {as for the round synthesis, with every settle record}
RESEARCHER RATINGS: {formal: every finding's rating, verbatim, from CP-R | none}
RESEARCHER DECISIONS: {verbatim, including any retracted paper kept and every reference accepted by the researcher | none}
PRIOR DELIVERABLE: {the last round synthesis | the earlier final version}   REVISE FROM: {*.report_check.json path | none}
WRITE TO: output/   WRITE INPUTS TO: lit_inputs/   SCRIPTS: scripts/lr_synthesis/
RETURN: deliverable path, findings and gaps recorded, references by status, held references, items for the researcher
""")
```

**Revision loop.** After `lit_verify report` exits 11 (FAIL), re-dispatch with the next VERSION and `REVISE FROM` the result file (`CARD_RECHECK_DIFFERS` items, which the synthesizer cannot fix, are handled first: § Error Handling; the loop then covers the FAIL items that remain); at most 2 revisions per deliverable, then present the open items to the user and ask how to proceed. **`AWAITING_GLANCE`:** run the glance (or the audit, or `settle`) for the listed papers, record the reply, export, and re-dispatch with the same VERSION. Finding, claim and edge ids appear only in markers and in the Methods section's "Technical appendix"; the markers show as text in a plain Markdown preview, so the user reads a synthesis through its HTML copy (§ HTML Copies for Reading).

### citation-adjudicator (every review, before the reference check)

```
Agent(subagent_type: "citation-adjudicator", model: "opus",
      prompt: <the content of {PROJECT_DIR}/data/adjudication_bundles/{batch_id}_prompt.txt, verbatim>)
```

No `BASE_DIR` line and no other text: anything added makes the dispatched prompt differ from the hashed one. `model` is the tier alias; `pack --model-id` recorded the exact model ID it resolves to (§ The Citation Second Check > The checker flow, steps 1-2). The prompt is the same whether the checker is tested or not: what its verdicts do is decided at `ingest`, never in the prompt.

### data-verifier: LR-8 claim spot-check

Before the dispatch, the orchestrator writes and runs a captured script, `{PROJECT_DIR}/scripts/lr_verification/{NN}_claim_sample_v{N}.py`: it reads the latest `data/claims_v{N}.parquet` and the final deliverable's `.lr-finding` and `.lr-claim` markers, and prints a deterministic sample (seeded by the deliverable's sha256) of up to 20 marked claims: at least one per cited paper read in full, every claim with source `vision` or `both` up to 8, the rest by the seeded order; per claim: `claim_id`, `paper_key`, `page`, `quote`, `numbers_json`, `source`, `card_file`, and the reading copy path `papers/{key}/pages{S}/p{NNN}.txt`.

```
Agent(subagent_type: "data-verifier", model: "opus", prompt: """
**MODE: Literature Review — LR-8 claim spot-check (override)**
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
PROJECT_DIR: {abs}   LEVEL: {standard|formal}
DELIVERABLE: {PROJECT_DIR}/output/lit_review_final_v{N}.md
REPORT CHECK: {PROJECT_DIR}/output/lit_review_final_v{N}.report_check{_k}.json (verdict {PASS|NEEDS_REVIEW})
QUESTION: {verbatim}
CLAIM SAMPLE: {PROJECT_DIR}/scripts/lr_verification/{NN}_claim_sample_v{N}.py (the sample is in its appended execution log)
READER TABLE: {per paper: card path, verdict, audit outcome, settle record}
REFERENCE CHECK RECORD: {PROJECT_DIR}/output/reference_glance_v{M}.md (read-only context)
ROUTE: {verbatim from STATE's Route record | omit when none}
PDF page-image cross-checking (user preference): {auto|all-pages|off}
RETURN: one row per sampled claim: CONFIRMED | DISPUTED | NOT DIRECTLY VERIFIED, with the page text that settles it; for a disputed claim, the findings that rest on it; counts; confidence; Learning Signal
""")
```

The data-verifier reads the page reading copies and opens a render only when its own model ID and the ROUTE line are on the vision-validated list. It writes nothing: persist its full return to `{PROJECT_DIR}/output/claim_spot_check_v{N}.md` with the provenance header (`SKILL.md` § Subagent Return Processing). A DISPUTED claim goes to CP-F with the findings it carries; the user decides whether the synthesizer revises.

### search-agent: LR-0 materials digest

```
Agent(subagent_type: "search-agent", model: "sonnet", prompt: """
BASE_DIR: /daaf
All relative paths in referenced files resolve from BASE_DIR.
TASK: Read the user's background materials for a literature review's scope check and write one digest record.
MATERIALS: {absolute paths and URLs}
PDFs: load pdf-reading; ingest each with bash /daaf/scripts/pdf_ingest.sh {pdf} {PROJECT_DIR}/materials/papers/ --paper-key user_{the first 8 hex characters of the PDF's sha256}
WEB PAGES: bash /daaf/scripts/web_fetch.sh URL {PROJECT_DIR}/web_fetches/
WRITE YOUR RECORD TO: {PROJECT_DIR}/output/preliminary_notes/{date}_{slug}_materials-digest.md (cite artifacts by paths relative to PROJECT_DIR, materials by title or URL)
FOCUS: what each material says about the question, its scope, sources, criteria and named papers
RETURN: a summary of the digest; the papers the materials name (as seed candidates); issues
""")
```

---

## HTML Copies for Reading

Pandoc (run through Quarto) hides the markers and turns the citations into a formatted reference list; a plain Markdown preview, such as the browser editor's, shows the markers as text in braces. So before a synthesis reaches the user, the orchestrator renders an HTML copy of the version that passed its report check, one Bash call, absolute paths:

```
quarto pandoc {PROJECT_DIR}/output/{deliverable}_v{N}.md --citeproc --bibliography {PROJECT_DIR}/output/references_v{M}.bib -s -o {PROJECT_DIR}/output/{deliverable}_v{N}.html
```

- `{M}` is the reference list the report check read (the newest `references_v{M}.bib` at that run). `-s` writes a whole web page with its character set declared, so accented names and symbols display correctly.
- Render each round synthesis before CP-R and the final synthesis before CP-F. The quick-scan memo carries no markers and needs no HTML copy.
- The `.md` stays the checked source: the report check, the data-verifier and the review manifest read it, never the `.html`. A revision is a new `.md` version and a new HTML copy.
- Name the `.html` to the user as the file to read and the `.md` as the checked source. Every round and final synthesis opens with the fixed line in `literature-synthesizer.md` § Deliverable Shapes, which points a reader of the `.md` to the HTML copy.
- A non-zero exit, or a warning printed about a citation: give the user the `.md`, say that the tags in braces link statements to their evidence, and note the problem in LEARNINGS.md.

---

## Orchestrator Commands

One command per Bash call; absolute paths. The orchestrator runs these itself (agents run their own CLIs).

| When | Command | Notes |
|---|---|---|
| LR-0 | `bash {BASE_DIR}/scripts/lit_verify.sh route {PROJECT_DIR} --reader-model {ID}` | Copy the `ROUTE:` and `VISION:` lines to STATE, verbatim |
| After CP-1, when the user lets an untested checker confirm references | `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications untested-checker {PROJECT_DIR} --model-id {ID} --user-words "{verbatim}" --rationale "{reason}"` (withdraw: `--revoke` in place of `--rationale`) | Its own Bash call, never from a script; behind `Bash(*lit_corpus*untested-checker*)`; `{ID}` in the form `pack` takes (§ Checkpoint Templates > Recording the choices) |
| After CP-1, when the user picks page-picture choice 2 or 3 | `bash {BASE_DIR}/scripts/lit_verify.sh vision-override {PROJECT_DIR} --level check\|accept --model-id {ID} --user-words "{verbatim}" --rationale "{reason}"` (withdraw: `--level withdraw --user-words "{verbatim}"`) | Its own Bash call, never from a script; behind `Bash(*lit_verify*vision-override*)`; then `route --reader-model` again |
| Before CP-G / CP-F, after the dispatch | `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications ingest {PROJECT_DIR} --batch {batch_id} --agent-id {ID}` | Soon after the return; `pack` runs from a captured script (§ The Citation Second Check > The checker flow) |
| A batch that will not be ingested | `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications release {PROJECT_DIR} --batch {batch_id} --reason "{why}"` | Then pack its rows in a new batch |
| After each reader | `bash {BASE_DIR}/scripts/lit_verify.sh audit {PROJECT_DIR}/papers/{key} --card {card} --agent-id {ID} [--agent-id {ID} ...] --project {PROJECT_DIR} [--transcript {path} ...]` | Once per card version, in the session that dispatched the readers; one `--agent-id` per reader dispatch (per chunk); a transcript never confirms the model; exit 0 or 11 are results |
| After an audit exit 11 | `bash {BASE_DIR}/scripts/lit_verify.sh settle {PROJECT_DIR}/papers/{key} --audit vision_audit{S}.json --list` | Plain reasons for CP-R or CP-G |
| On the user's comparison reply | `bash {BASE_DIR}/scripts/lit_verify.sh settle {PROJECT_DIR}/papers/{key} --audit vision_audit{S}.json --items {file} --decision matches\|does_not_match --user-words "{verbatim}" [--rationale "{reason}"]` | Item ids from `--list`; rationale required for `does_not_match`; never for `chain_unconfirmed` |
| After each synthesizer return | `bash {BASE_DIR}/scripts/lit_verify.sh report {PROJECT_DIR} {deliverable} --level {quick\|standard\|formal}` | Drafts use the default kind, `synthesis` (the synthesizer's KIND `draft`) |
| Before CP-R / CP-F, on a synthesis that passed its check | `quarto pandoc {PROJECT_DIR}/output/{deliverable}_v{N}.md --citeproc --bibliography {PROJECT_DIR}/output/references_v{M}.bib -s -o {PROJECT_DIR}/output/{deliverable}_v{N}.html` | The HTML copy the user reads (§ HTML Copies for Reading) |
| Final deliverable | `bash {BASE_DIR}/scripts/lit_verify.sh report {PROJECT_DIR} {deliverable} --kind final --level {level}` | Re-checks the cards; needs each paper's stored source file |
| Before CP-G / CP-F | `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications glance-sheet {PROJECT_DIR} --deliverable {path} [--keys K1,...]` | Writes the sheet and its rows file; the extra keys are added to the draft's references |
| On the glance reply | `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications record-human {PROJECT_DIR} --rows {file} --decision same_work\|different_work\|defer\|override_mismatch --user-words "{verbatim}" --rationale "{reason}"` | One call per decision; `--rationale` with every decision except `defer` |
| After record-human | `bash {BASE_DIR}/scripts/lit_corpus.sh export-bib {PROJECT_DIR}` | The list `report` reads |
| Formal CP-S reply | `bash {BASE_DIR}/scripts/lit_corpus.sh screen record {PROJECT_DIR} {PROJECT_DIR}/lit_inputs/r{R}_screen_ft_researcher_{seq}.jsonl` | Lines `{paper_key, stage: "ft", pass: "researcher", decision, reason_code (exclude), rationale: "<the researcher's words>", screener: {"role": "researcher"}}` |
| End of each round; final | `bash {BASE_DIR}/scripts/lit_corpus.sh manifest {PROJECT_DIR} --round {R} --protocol {PROJECT_DIR}/Protocol_v{N}.md` | Writes the versioned manifest and the pointer |
| CP-F | `bash {BASE_DIR}/scripts/collect_session_logs.sh {PROJECT_DIR}` | Before the delivery message |

Keys and row hashes in any input the orchestrator writes come from tool output or a captured script's log, never from memory.

---

## Checkpoint Templates

These are user-facing: plain language, no stage or checkpoint codes, no status or verdict codes, no agent or tool names (§ Plain-Language Vocabulary). Record each checkpoint in STATE's Current Position as awaiting a reply when presenting it, and the reply (quoted) when it arrives.

### CP-1: the review plan (Scope Check)

```
**Literature review: the plan (scope check)**

**What I read:** [each material, one line on what in it shapes the plan; the first searches: what they turned up] (or "Nothing beyond your request — the estimates below are preliminary")
**Proposed scope:**
- Question: [one sentence]
- How deep: [quick scan / standard review / formal systematic review]; kind of review: [e.g. state of the art, scoping, systematic]
- Searching: [2–3 wordings of the question]; keywords: [query]; databases: [names]; years: [range]; following citations forward and back: [yes, from the key papers / no]
- What counts as in or out: [each rule on one line]
- Papers you expect to see: [each: found by the first searches / not found yet]
- How much there is: [about n papers per sub-question; roughly k% show a free full text]
- When to stop: [the stopping rule]
**What changed from your original request:** [differences the materials or first searches introduced, or "Nothing — your request and the materials agree"]

[the reference-checker paragraph, one of:]
[tested:] **Checking references with AI.** Before your reference check, an AI model DAAF has tested for this ([model]) compares each reference with its database record. References it judges to be the same work are confirmed and labelled "confirmed by DAAF's second check (an AI judgment)"; the rest come to you.
[not yet tested:] **Checking references with AI.** Before your reference check, an AI model ([model]) compares each reference with its database record. DAAF has not tested this model on that judgment, so by default its view is shown beside each reference on your list as a hint, and you decide every reference. You can choose: (1) hints only (the default); or (2) let it confirm the references it judges to be the same work, each labelled "confirmed by an untested AI check (your choice)", while the references it thinks may be a different work, or is not sure about, still come to you. Which do you prefer? You can change this later; if you withdraw choice 2, references it already confirmed keep their label, and you can still mark any of them as a different paper on your list.

[the page-pictures paragraph, one of (standard and formal only):]
[`VISION: validated`:] **Reading pictures of PDF pages.** The AI model that will read the papers has been tested by DAAF on reading tables from pictures of PDF pages on this setup, so it will check numbers in tables against pictures of the pages. Numbers on scanned pages are listed for you to check.
[otherwise:] **Reading pictures of PDF pages.** [the WARNING text from `lit_verify route`, verbatim] Which do you prefer? You can change this later. If you later withdraw choice 3, the numbers it accepted are listed for you to compare before the final report.

**Expected reading and cost (estimates):**
- Searching: [n] searches per round on free databases, within OpenAlex's free daily allowance; each round reports how much of it was used
- Reading in full: about [n] papers per round, up to 5 at a time; roughly [a–b] tokens of your plan's usage per round
- The AI reference check: about [n] references, roughly [a–b] tokens of your plan's usage, once before the final version
- Your reference check: before the final version, you check each reference once, its title as cited against the title on record (about a minute per 10 references; references the AI check confirmed are listed but need no reply)
- Paid searches: none unless you approve them
**Decisions for you:**
- [each independent decision on its own line, with its default: e.g. "Include working papers? (default: yes)", "Paid searches with Elicit? (default: no)", "A second look at which papers are kept? (default: no)"]
**Saved as:** `Protocol_v1.md` in the project folder; any later change becomes a new version.
**Does this plan look right? Shall I start the searches?**
```

**Quick scan, short form:** keep What I read, the question, the wordings and databases, in-or-out rules, papers you expect, "What changed", the reference-checker paragraph, the AI reference check and reference-check lines and "Decisions for you"; drop the rounds, reading, page-pictures and stopping lines (a quick scan reads abstracts only); close with **"Shall I run the scan?"**

**Formal:** "Proposed scope" lists the eleven protocol items (`formal-review.md` § The protocol) in plain words, including who the second person deciding on full texts is.

**On confirmation:** write `Protocol_v1.md` from the confirmed scope (the decisions and the user's adjustments included), set `Scope Check status: confirmed YYYY-MM-DD` with its path, record SPEND APPROVED, record the two choices (below), and dispatch the first round.

**Recording the choices.** Each choice the user makes in the two paragraphs is recorded with their reply copied verbatim (never a paraphrase), as its own Bash call, never from a script; each command sits behind its own Ask-First rule, so the user approves the call that shows their words. A reply that gives no choice is the default, which records nothing.
- **Reference checker, choice 2** (not yet tested): `bash {BASE_DIR}/scripts/lit_corpus.sh adjudications untested-checker {PROJECT_DIR} --model-id {ID} --user-words "{the user's reply, verbatim}" --rationale "{the user's reason in a sentence, or: chosen at the review plan after the warning}"`, where `{ID}` is the model the `opus` tier resolves to, in the form `pack` takes (§ The Citation Second Check > The checker flow, step 1). It needs no corpus, so it runs before the first round. It covers that model ID in this project, from the next `ingest` on; a batch already ingested keeps its statuses. Choice 1 records nothing. To withdraw: `… untested-checker {PROJECT_DIR} --model-id {ID} --user-words "{verbatim}" --revoke` (later batches are hints again; references already confirmed keep their label). Exit 11 refuses, nothing written, with a MANIFEST refusal row (no words; no rationale; an acceptance already in force; nothing to withdraw; an acceptance of a model ID that is on the evaluated list in force, where nothing in force changes and nothing is to be done, because that model's judgments already count; a withdrawal of an earlier acceptance is still allowed); exit 1, an `{ID}` in another form (the message names the form to pass). An acceptance row counts only as the step writes it: `tool_version` and `timestamp`, non-empty `parameters.user_words` whose sha256 is `user_words_sha256`, `human_decider` `researcher`, `human_binding` `permission_prompt`, `parameters.model_id` equal to the row's and `parameters.revoke` false, a rationale, and no acceptance already in force. When the latest row for a model ID is a withdrawal or does not hold up, no acceptance is in force (`agent_reference/LIT_REVIEW_OUTPUT_CONTRACT.md` § The Second-Check Ledger).
- **Page pictures, choice 2 (`--level check`) or 3 (`--level accept`):** `bash {BASE_DIR}/scripts/lit_verify.sh vision-override {PROJECT_DIR} --level check|accept --model-id {ID} --user-words "{the user's reply, verbatim}" --rationale "{the user's reason in a sentence, or: chosen at the review plan after the warning}"`, where `{ID}` is the reader's model ID given to `route --reader-model`. Then re-run `lit_verify route {PROJECT_DIR} --reader-model {ID}` and copy the new `VISION:` line to STATE. Choice 1 records nothing. To withdraw: `… vision-override {PROJECT_DIR} --level withdraw --user-words "{verbatim}"`. A choice counts only as `vision-override` wrote it: its record (`papers/vision_override_{n}.json`) must hash to its MANIFEST row, carry `schema_version` `lit-verify-vision-override-v1`, `kind` `lit_verify_vision_override`, `human_decider` `researcher`, the researcher's words (whose sha256 is the row's `user_words_sha256`) and, for `check` or `accept`, a rationale, and repeat the row's level, model, route and time; the row must carry `tool_version` and the level in its `parameters`. When the latest choice record or row does not hold up, there is no choice at all (the reader reads text only), never the choice before it (`pdf-reading/references/vision-validation.md` § The researcher's choice for an untested reader).
- Record each in STATE (the AI Reference Check section; the Route Record), with the user's words and the MANIFEST row.

**When the model or setup changes.** At a session start (STATE's Subagent Model Tiers row is resolved again) and before each reader wave and each checker pack, compare the `opus` tier's model and `lit_verify route`'s route with the ones the choices named. If the reader's model or the route changed: re-run `route --reader-model` and copy its new `VISION:` line; an earlier page-picture choice no longer applies (the line reads `text-only` unless the new model and route are on the list). If the checker's model changed: run the identity check again; an acceptance covers only the model ID it names, so the new model's batches are hints. Either way, show the user the matching CP-1 paragraph again, as a short check-in before the next dispatch, and record a new choice if they want one.

### CP-K: the key-paper list (standard)

```
**Literature review, round [R]: which papers to read in full**

**Bottom line:** the searches found [n] papers; [m] passed the first look at titles and abstracts; I propose reading [k] in full.

**Papers I propose to read in full:**
| # | Paper | Why read it in full | Pages | Free full text? |
|---|-------|---------------------|-------|-----------------|

**Kept, but not read in full** ([n]): the write-up may mention them, marked "per abstract", but draws no conclusions from them. [list, or the path to the screening sheet]
**Papers you named:** [each: found and kept / found but left out, because … / not found by these searches]
**For your attention:** [retracted papers; papers without a free full text (DAAF does not use paywalled copies; you can add a PDF you have to the project's `user_pdfs/` folder); cases where the second look disagreed with the first]
**Reading cost:** about [a–b] tokens of your plan's usage for these [k] papers.

**Decisions for you:**
- Is this the right list? Add, drop or swap any paper (default: the list above)

**Shall I read these [k] papers?**
```

### CP-S: full-text decisions (formal)

```
**Formal review, round [R]: your full-text decisions**

I retrieved [n] of the [m] papers that passed the first look; [k] could not be retrieved (listed below, not excluded). For each retrieved paper, the search specialist's draft decision on the full text and the passage it rests on:

| # | Paper | Draft decision (full text) | Reason | Passage it rests on (page) |
|---|-------|----------------------------|--------|----------------------------|

**Where the two screenings disagree:** [paper, both decisions, both reasons]
**Not retrieved:** [paper, what was tried]

**Please give your decision for each paper: include, or exclude with a reason. I record your words as you write them.**
```

### CP-A: checklist review (formal)

```
**Formal review, round [R]: checklist review**

For each paper read this round: the checklist used, the result it judges, and my draft answer to each question with the passage behind it. Questions marked "(look closely)" are the kind AI drafts get wrong most often.

### [Paper]
- Checklist: [e.g. RoB 2, for randomized trials]; result judged: [outcome, analysis]
| Question | Draft answer | Passage (page) |
|----------|--------------|----------------|
- Answers that rest on what the paper does not report: [question, draft answer, why]
- Draft weight: [substantial / moderate / limited], because [the limitations behind it, with pages]

**Your judgments:** for each paper, please confirm or change each answer, give each domain judgment and the overall judgment, and confirm or change the weight. I record your words as you write them.
```

### CP-R: the round check-in

```
**Literature review, round [R] check-in**

**Bottom line:** [what is now known, in one or two sentences, at its stated certainty]

**What this round added:**
| Round | Searches run | New papers kept | Read in full | New themes | New conclusions | New gaps |
|-------|--------------|-----------------|--------------|------------|-----------------|----------|

**What the evidence shows so far:** [each conclusion in its calibrated wording, with "how sure: [level] — [what that level means]"]
**Papers you named:** [found / kept / left out]
**For a person to check:**
**Page comparisons** (please reply for each number, e.g. "all match" or "1 and 3 match, 2 does not: the page says 83"):
[the paper's short reference, e.g. Smith (2020), "Tutoring and reading outcomes"]; PDF: [path to the PDF]
1. [the first reason, as listed: "The AI reader took the number … from a picture of PDF page …. Please compare … with PDF page …."]
2. […]
[the next paper's short reference]; PDF: [path to the PDF]
3. […]
- [items the page check listed for a person, in plain words]
- [numbers worth a look, read from charts the paper's text does not confirm, under the paper each belongs to (its short reference; PDF: [path to the PDF])]
- [[n] references match the database record and are not yet confirmed; you check them at your reference check before the final version]
[Formal:] **Your certainty ratings:** for each conclusion, my draft notes on what holds the evidence up or down, and a proposed rating. Please give your rating, in your own words.

**Your options:**
1. Another round: [searches and citation-following to run, expected yield, papers to read in full, reading cost]
2. Change the plan: [what the results suggest changing]; the plan becomes a new version
3. Write the final review: [what stopping now would leave open]
**Recommendation:** [one option and why]
**Files:** this round's write-up to read [path to the .html] (the checked source, the same text with tags in braces that link each statement to its evidence: [path to the .md]); the follow-up plan [path]; the list of gaps [path]

**Which would you like?**
```

**Building and recording the page comparisons.** The page comparisons are the required readings `lit_verify settle --list` printed for each audit with exit 11 (§ Readings From Pictures of Pages, step 3). Group them by paper, under one plain line per paper: its short reference (first author, year and title, from the RECORD line of the paper's reader dispatch) and the path of its PDF (`source.path` in the ingest manifest the card's `card_check{S}.json` names as `ingest.manifest`), so the user knows which file to open. Under that line show the plain reason text of each comparison, numbered 1, 2, 3 … across the whole check-in, the numbering continuing from one paper to the next; never an item id, the `(optional)` prefix or the `next (for the agent)` line. Before presenting, record in STATE's Reading Items for a Person each number with its paper and item id, copied from `--list`'s output and `settle_items{S}.txt`. Split the reply by decision and paper, then record each part with `lit_verify settle --items … --decision matches|does_not_match --user-words "…"`, the user's whole reply as the words (step 4); record the round decision in STATE. Comparisons the user leaves open stay in Reading Items for a Person and are shown again at CP-G, numbered afresh.

### CP-G: the reference check (standard and formal, before the final write-up)

```
**Before the final write-up: your reference check**

DAAF's automatic reference check looked up every reference in a database. That check can be fooled by a one-word change in a title, so you look over each reference once, comparing the title as cited with the title on record, before it goes into the final version. [when the AI reference check confirmed some: [k] references were confirmed by the AI reference check and are listed with that label; they need no reply.]

**The list to check:** `[path to the list to check]`, [n] references, numbered: for each, the title as cited and the title on record, the authors, the year, where it was published, and where it stands.
[when a title on record starts with "Does not match:" or "Not compared:": the list's note about that label, all of its sentences, word for word]
[when the AI reference check is not yet tested: the list's note about its hints, word for word]
[the table, when it has 30 rows or fewer; else the rows that need attention and the rows the list says are left out]

**Needs your attention:** [references the list shows as only partly matching, or not matching, the record; retracted papers]
[**Left out because the record does not match:** [each such reference the write-up wanted to cite that your reply can keep]; to keep one, say so and give your reason]
[**Not matched to any database record:** [the list's sentences about the references it will leave out, word for word; they name each by number and say how to ask for one to be checked] [each other reference the write-up wanted to cite that could not be matched to any database record, by its short reference: "it will be left out unless an automatic check matches it; to keep it, ask for it to be checked again" (for one never checked: "ask for it to be checked")]]
[**Page comparisons still open** (please reply for each number, as at the round check-in):
[the paper's short reference]; PDF: [path to the PDF]
1. [the reason, as listed: "The AI reader took the number … from a picture of PDF page …. Please compare … with PDF page …."]]

**How to reply:** one reply covers the whole list, for example "all look right", or "all except 4 and 9: 4 is a different paper, 9 I'll check later". A reference you say is a different paper, or want to check later, is left out of the final version. To keep a reference whose record does not match, say so and give your reason; it stays in, labelled as accepted by you. To have a reference the list could not match to any database record checked again, say so, for example "check 7 again" (with the correct title or DOI if you have it): I run the automatic check on it again and show you a new list. That is different from "I'll check later", which leaves a reference for your own look and out of the final version. I record your reply in your own words.

**Do the references look right?**
```

**Building the list.** The numbered rows are the glance sheet's (§ The Citation Second Check > The reference glance, steps 1-2). The round synthesizers' held references (each return's "Held for the reference glance") are named rather than dropped silently, sorted as the sheet sorts its own rows, by the captured rows script of § The Citation Second Check, step 4. "Decided" means a `citation_status` that `read_status` reads as citable at final (`CITABLE_FINAL`) or `rejected`.
- Undecided, CONFIDENT or WEAK, `reply_can_decide` True: it is on the list itself, added with `--keys` when the sheet was built (step 1), so it has a number and the reply decides it.
- Undecided MISMATCH with `reply_can_decide` True: the "Left out because the record does not match" line (a reply can keep it with `override_mismatch`).
- `left_out` True: the "Not matched to any database record" line, where the user can ask for it to be checked again, or checked when its `verify_row_sha256` is empty (never checked).
- Decided: on neither line. A `rejected` one is simply not cited.

**The AI reference check on the list.** References the checker confirmed are on the list, labelled ("confirmed by DAAF's second check (an AI judgment)" or "confirmed by an untested AI check (your choice)"), and need no reply. Where the checker is not yet tested, its view sits beside each other reference as a hint, and the sheet's note about it is copied above the table (§ The Citation Second Check > The reference glance, step 2).

**Recording the reply.** The reference part goes through `record-human` (§ The Citation Second Check, step 4), then `export-bib`. A request to check a reference again goes through the searcher's check-only pass, `export-bib` and a new list shown at this checkpoint (step 4, "Check again"), never through `record-human`. The open page comparisons go through `lit_verify settle`, as at CP-R. A final dispatch waits until every reference the final needs is citable at final and every audit it needs is confirmed or settled; anything left open goes to the user as what the final will leave out.

### CP-F: final review (standard and formal)

```
**Literature review complete: the final review**

**Bottom line:** [the main conclusions, each at its stated certainty]

**What you can rely on:**
- [when the final check listed nothing for a person:] Every quote and number in the review was found on the page it came from [when it listed quotes or numbers for a person: Every other quote and number was found on the page it came from; the [n] listed under What to check need a person's look] [when it listed only wording for a person: Every quote and number in the review was found on the page it came from; [n] points of wording are listed under What to check]
- Every reference was looked up in a database by the automatic reference check, then confirmed: [n] by you[; [m] by DAAF's second check (an AI judgment)][; [u] by an AI check DAAF has not tested, at your choice, which the review says beside each][; [k] accepted by you despite a mismatch, which the review says beside each]
- [when an untested reader's page-picture readings were accepted at your choice: Some numbers in [n] papers were read from pictures of PDF pages by an AI model DAAF has not tested for this, at your choice, and were not compared with the page; the review says so in its methods]
- An independent re-read of [k] sampled quotes and numbers: [n] confirmed, [n] disputed [details]
**What to check:** [open items: disputed claims and the conclusions they carry; anything a person should check]

**Deliverables:**
- The final review, to read in your browser: [path to the .html] (the checked source, the same text with tags in braces that link each statement to its evidence: [path to the .md])
- The reference list: [path to the .bib]
- The list of gaps: [path]
- The search record: [path] (a machine-readable list of every search and file in the review)
**Files to browse:** the project folder [path]; session logs in `logs/`; to browse the session timeline, run `bash /daaf/scripts/generate_log_viewer.sh [project path]` in the Docker terminal.

**What could come next:** [if a gap is answerable with data: "see what data exists for it" or "run a full analysis of it"]
**AI disclosure:** [what was AI-drafted (searching, screening, reading notes, drafts), what code checked (references, quotes, numbers, wording), and what you decided]

**Is this final review acceptable?**
```

### CP-F: the memo and its references (quick scan)

```
**Quick scan ready: the memo and its references**

**Bottom line:** [what the abstracts report, in one or two sentences; abstracts only]
**The memo:** [path] — what studies report, where to start reading, gaps that seem open
**Your reference check:** DAAF's automatic reference check looked up every reference in a database. That check can be fooled by a one-word change in a title, so please look over the list to check once, comparing each title as cited with the title on record: [path to the list to check], [n] references, numbered, each with the title as cited and on record and where it stands. [when the AI reference check confirmed some: [k] references were confirmed by the AI reference check and are listed with that label; they need no reply.] [when a title on record starts with "Does not match:" or "Not compared:": the list's note about that label, all of its sentences, word for word] [when the AI reference check is not yet tested: the list's note about its hints, word for word] [the table when it has 30 rows or fewer; else the rows that need attention and the rows the list says are left out]
**Needs your attention:** [as at the reference check]
[**Left out because the record does not match:** as at the reference check]
[**Not matched to any database record:** as at the reference check]
**How to reply:** one reply covers the list, for example "all look right", or "all except 4 and 9: 4 is a different paper, 9 I'll check later". A reference you say is a different paper, or want to check later, is left out of the final memo. To keep a reference whose record does not match, say so and give your reason; it stays in, labelled as accepted by you. To have a reference the list could not match to any database record checked again, say so, for example "check 7 again" (with the correct title or DOI if you have it): I run the automatic check on it again and show you a new list. That is different from "I'll check later", which leaves a reference for your own look and out of the final memo. I record your reply in your own words.

**Does the memo serve your purpose, and do the references look right?**
```

**After the reply (quick scan).** Record it (`record-human`, then `export-bib`; a request to check a reference again goes through the searcher's check-only pass, `export-bib` and a new list shown at this checkpoint, § The Citation Second Check, step 4, "Check again", and LR-8Q then waits for the reply to that new list), then run `lit_verify report --kind final --level quick` on the memo the user saw (LR-8Q), before treating the reply as approval. A pass with the reply removing no cited reference: the approval stands; close with a short briefing that the final check passed, naming the memo and the reference list. Otherwise (a FAIL, which a removed or deferred cited reference causes): dispatch the synthesizer for a KIND final version with `REVISE FROM` the result file, check it, and show the new memo at this checkpoint again; approval of the earlier memo does not carry over.

---

## Plain-Language Vocabulary

User-facing words for this mode's internal terms. `SKILL.md` § Plain-Language Rule holds one row per code family and points here.

| Internal term | User-facing language |
|---|---|
| LR-0 … LR-8, LR-7Q, LR-8Q | describe the activity: "setting up", "searching", "choosing papers", "getting the papers", "reading the key papers", "writing up", "the final checks" |
| CP-1 / CP-K / CP-S / CP-A / CP-R / CP-G / CP-F | "scope check" / "key-paper list" / "full-text decisions" / "checklist review" / "round check-in" / "reference check" (defined once where the user meets it: "you compare each title as cited with the title on record") / "final review" |
| round | "round (one cycle of searching, choosing and reading, then a check-in)" |
| review_level `quick` / `standard` / `formal` | "quick scan" / "standard review" / "formal systematic review" |
| protocol, `Protocol_v{N}.md` | "the plan" (named by its file when the user meets it) |
| evidence card | "reading notes for one paper" |
| `lit_verify card`, card_check, PASS / PARTIAL / FAIL | "the page check": "every quote and number found on its page" / "checked, with items listed for you" / "the notes did not pass the page check and were redone" |
| FULL_TEXT_VERIFIED / FULL_TEXT_PARTIAL / ABSTRACT_ONLY / METADATA_ONLY | "read in full and checked" / "read in full; some items could not be checked (listed)" / "abstract only" / "record only, not read" |
| NEEDS_REVIEW, review item | "a person should check this" |
| anchor quote | never shown; if needed, "a quote that pins the page" |
| vision, vision-validated, vision audit, transcript-confirmed | "numbers read from a picture of the page"; "a model tested on reading tables from page images"; "a check that the tested model did the reading"; "confirmed" |
| `lit_verify settle`, matches / does_not_match | "your page comparison": "matches" / "does not match" |
| `settle --list` item ids, the `MUST CHECK:` / `SHOULD LOOK:` tags of `audit` output, `settle --list`'s `(optional)` prefix and its `next (for the agent)` line | never shown; only the reason texts, under the paper each belongs to, numbered across the check-in |
| `chain_unconfirmed` | "DAAF could not confirm where this PDF came from; it will be fetched again (or you can add your copy)" |
| route; the `ROUTE:` and `VISION:` lines | never shown; if vision is off: "on this setup DAAF reads the text of PDFs only" |
| `override-check` / `override-accept` / untested reader | "you compare each number read from a picture" / "you accepted its picture readings without comparing them" / "a model DAAF has not tested on reading page pictures" |
| `confirmed_untested_reader`, `VISION_READ_BY_UNTESTED_MODEL` | "read from pictures of PDF pages by an AI model DAAF has not tested for this, at your choice" (in deliverables: "at the researcher's choice") |
| lane B, lane names, `rows` file | never shown |
| `scholar_search verify`, the rule check, its match | "the automatic reference check" |
| verify verdicts CONFIDENT / WEAK / MISMATCH / NOT FOUND / EXISTS | "matches the database record" / "partly matches; a person decides" (on the glance sheet: "partly matches; please decide") / "does not match the record" / "no record found" / "the identifier exists, but its title was not compared" |
| `pending_adjudication` | "matches the record; not yet confirmed" (the glance sheet's words) |
| `model_confirmed` / `model_adjudicated` | "confirmed by DAAF's second check (an AI judgment)" / "partly matches; confirmed by DAAF's second check (an AI judgment)" (the glance sheet's words) |
| `model_confirmed_untested` | "confirmed by an untested AI check (your choice)" (the glance sheet's words); in deliverables, which the researcher may share: "confirmed by an AI check DAAF has not tested, at the researcher's choice" |
| hint (an untested checker's verdict on an undecided reference) | the glance sheet's words: "DAAF's AI reference check, not yet tested with this model, says: the same work" / "a different work" / "not sure", with its one-line reason; a batch whose transcript recorded another model, or none, reads "DAAF's AI reference check, which may not have run on the AI model planned for it, says: …" |
| tested / untested checker; `untested-checker` (accept / revoke) | "an AI model DAAF has tested for this" / "an AI model DAAF has not tested on that judgment"; "you let it confirm the references it judges to be the same work" / "you withdrew that choice" |
| `human_confirmed` / `human_overridden` / `rejected`, in messages to the user | "you confirmed it" / "accepted by you" / "you marked it as a different work" (on the glance sheet: "accepted by you despite the automatic reference check" / "judged to be a different work; it will not be cited") |
| the same, in deliverables (which the researcher may share) | "confirmed by the researcher" / "accepted by the researcher despite the automatic reference check" / not cited |
| a reference no reply can decide (`unverified` with no verdict a reply can decide: the glance sheet's left-out rows) | "could not be confirmed against a database record, so it will be left out of the reference list unless an automatic check matches it" (the glance sheet's words; its cell ends "left out of the reference list unless an automatic check matches it"); "not checked yet" for a reference with no attached check |
| `check_again` (the searcher's check-only pass for a left-out reference) | "check it again" ("check it" for one never checked): "I run the automatic check on it again and show you a new list" |
| SAME_WORK / DIFFERENT_WORK / UNCERTAIN | "the same work" / "a different work" / "not sure" |
| reference glance, glance sheet | "your reference check"; the sheet is "the list to check" ("the reference list" is the `.bib` deliverable) |
| citation-adjudicator, paper-reader, literature-searcher, literature-synthesizer, data-verifier | "DAAF's second check (an AI judgment)" or "the AI reference check", "the AI reader", "the search specialist", "the writer", "an independent reviewer" (or omit) |
| claim ids, finding ids, edge ids, `.lr-*` markers | never in user-facing prose; ids only in a technical appendix. The markers show as tags in braces in the `.md`, so the user reads the HTML copy, where they are hidden |
| HTML copy (`{deliverable}_v{N}.html`) / the `.md` deliverable | "the review to read in your browser" / "the checked source" |
| weight `substantial` / `moderate` / `limited`; certainty high … very low | keep the words; certainty with one line on what it means |
| screening `ta` / `ft`; snowballing | "first pass on titles and abstracts" / "full-text check"; "following citations forward and back" |
| gap register; saturation | "list of gaps"; "whether new rounds still turn up new things" |
| MANIFEST | "the search record" |

---

## Output Format

| Level | Primary deliverable | Supporting artifacts |
|---|---|---|
| Quick scan | `output/quick_scan_v{N}.md` (a KIND final version only when the final check failed on the memo the user saw) | `references_v{N}.bib`, `reference_glance_v{N}.md`, `gap_register_v{N}.md` if gaps were recorded, the counts, the review manifest |
| Standard | `output/lit_review_final_v{N}.md`, with its HTML copy `lit_review_final_v{N}.html` for reading | Round syntheses (each with its HTML copy) and follow-up plans, `references_v{N}.bib` (and `.ris` if asked), `gap_register_v{N}.md`, `reference_glance_v{N}.md`, `claim_spot_check_v{N}.md`, the review manifest |
| Formal | `output/lit_review_final_v{N}.md` | As standard, plus every `Protocol_v{N}.md`, the screening log, `appraisal_log_v{N}.md`, the certainty notes |

**What a consumer may rely on.** `{BASE_DIR}/agent_reference/LIT_REVIEW_OUTPUT_CONTRACT.md` is the review's interface: the tables and their schema ids, the citation statuses citable in a draft and in a final, the second-check ledger, the audit and settlement records, the files a consumer outside the review may read (starting from the manifest pointer `output/LIT_REVIEW_MANIFEST.json`), the in-prose markers, and the contract version. Any mode that takes up a finished review reads it through that file. The data-verifier spot-check relies on the same statuses and claims table and, as part of the review's own final checks, also reads the page reading copies of the claims it samples.

**Formal appraisal log.** `lit_corpus` has no field for a checklist's domain and overall judgments, and a checked card is never edited, so the orchestrator writes `output/appraisal_log_v{N}.md` after each CP-A: per paper, the guide, the result judged, each answer confirmed or changed, each domain and overall judgment, with the researcher's words quoted and the date. A weight the researcher confirms or changes goes to the synthesizer as RESEARCHER DECISIONS and is recorded with `lit_corpus notes record` (`decided_by.role: researcher`, their words in `researcher_instruction`), which a later `claims build` never replaces.

**Handoff.** On escalation to Full Pipeline or Data Discovery, write `output/LitReview_Handoff_v{N}.md`: the question, the final deliverable's path, the gaps marked answerable with data (from `gap_register_v{N}.md`), the reference list path and the manifest pointer `output/LIT_REVIEW_MANIFEST.json`. The receiving mode reads the review only through the files in `LIT_REVIEW_OUTPUT_CONTRACT.md` § Files Consumers May Read; a fact it needs that is not a page-checked claim is a request for another round.

**Before CP-F:** run the Scratch Graduation Check (`{BASE_DIR}/agent_reference/SCRIPT_EXECUTION_REFERENCE.md` § Scratch Graduation Check), `lit_corpus manifest`, and `collect_session_logs.sh`; consolidate LEARNINGS.md. The deliverable's Methods section carries the AI disclosure; `agent_reference/AI_DISCLOSURE_REFERENCE.md` has the mode's guidance.

**Turn-end briefing.** Checkpoints are this mode's heavyweight instances of the Turn-End Briefing; every other substantive turn that returns control (a round paused for an error, a reader wave reported between checkpoints) closes with a briefing that leads with the bottom line and references files by path (`SKILL.md` § User-Facing Communication Standards > "Turn-End Briefing").

---

## Project Layout

```
research/YYYY-MM-DD_LitReview_{Short_Topic}/
├── STATE.md  LEARNINGS.md  Protocol_v1.md …
├── lit_search/round{R}/      scholar_search raw logs, digests, records files, MANIFEST.jsonl
├── web_fetches/              OA PDFs and grey literature (web_fetch.sh), MANIFEST.jsonl
├── user_pdfs/                PDFs the user supplied (copied in)
├── materials/papers/         ingests of background materials (scoping digest only)
├── papers/{paper_key}/       ingest, evidence_card{S}.md, card_check{S}.json, vision_audit{S}.json,
│                             settle_items{S}.txt, audit_settlement{S}_{n}.json,
│                             chunk_notes_p{a}-{b}.md; papers/MANIFEST.jsonl,
│                             papers/vision_override_{n}.json (page-picture choices)
├── lit_inputs/               JSONL inputs and rows files (never rewritten after a tool read them)
├── data/                     versioned tables, MANIFEST.jsonl, adjudication_bundles/, adjudication_raw/
├── scripts/lr_search/  lr_synthesis/  lr_adjudication/  lr_verification/  scratch/
├── logs/                     session transcripts (collected at CP-F)
└── output/                   preliminary_notes/, screening/, counts, memos and syntheses (with
                              their .html copies), follow-up plans, reference_glance_v{N}.md, references_v{N}.bib, gap_register_v{N}.md,
                              appraisal_log_v{N}.md, claim_spot_check_v{N}.md, manifests/,
                              LIT_REVIEW_MANIFEST.json
```

Captured scripts in `scripts/lr_*/` are numbered `{NN}` per folder, in order of creation, and follow CLAUDE.md § Code Style (flat, IAT comments); a failed one is revised with `create_script_revision.sh`.

---

## State, Recovery and LEARNINGS.md

### STATE.md update gates

STATE.md follows `{BASE_DIR}/agent_reference/STATE_TEMPLATE_LITREVIEW.md`.

| Event | Fields |
|---|---|
| LR-0 | Project; Scope Check status `awaiting confirmation`; Route record (the `ROUTE:` and `VISION:` lines and their MANIFEST row); AI Reference Check (the checker's model ID and whether it is tested); Current Position |
| CP-1 presented / confirmed | Current Position; Scope Check status `confirmed YYYY-MM-DD` with the `Protocol_v{N}.md` path; Spend ledger (SPEND APPROVED); the user's page-picture choice (level, words, `vision_override_{n}.json`) if any, and the new `VISION:` line; the user's checker choice (words, the `untested-checker` MANIFEST row) if any |
| A model or setup change (§ Checkpoint Templates > When the model or setup changes) | Route record or AI Reference Check: the new lines and status, the warning shown again, and any new choice with the user's words |
| Searcher returns | Round table (searched, screened, kept; round-1 note on the scoping calls); Spend ledger (OpenAlex spend, paid calls with their approval line); Open review items (retractions, missing seeds) |
| CP-K / CP-S reply | Key-paper or full-text decisions, with the user's words |
| Each reader dispatch and return | Reader table: paper key, chunk k of m and pages, dispatch agent ID, model tier dispatched, card path, `card_check` verdict, audit outcome with the model ID it recorded, settle record |
| CP-A reply | Appraisal log path; weights for the next synthesizer dispatch |
| Synthesizer returns; report run | Round table (read, cited); deliverable path and report verdict |
| CP-R reply | Round decision (1, 2 or 3, quoted); formal ratings, verbatim |
| Checker flow, glance and settle | Adjudication and glance batches: every review, each batch's pack script, bundle hash, dispatch agent ID, ingest status (counted as tested, accepted or hints; any model-check WARNING), release and its reason; glance version, rows files, each `record-human` and `settle` call, and each page comparison's number, paper and item id when numbered for a check-in |
| Context ELEVATED or higher | Restart prompt |
| CP-F | Final paths; Current Position complete |

### Session recovery

| Record | On resume |
|---|---|
| `Scope Check status` | `awaiting confirmation` → re-present CP-1 (re-read materials and the scoping record); `confirmed YYYY-MM-DD` → resume from Current Position |
| Reader table: a dispatch with no card | Re-dispatch the paper (or its remaining chunk) with a free WRITE CARD TO |
| Reader table: a card with no audit record | Audit it before anything else, with every recorded agent ID for the card (one per chunk). In a new session the hook's record of the earlier session's readers no longer counts, so the audit cannot confirm the model: pass `--transcript` when a `find` probe locates `agent-{ID}.jsonl` (it can still show a differing model, `mismatch`); either way the card's readings from pictures of pages go to the user's page comparison (`person_must_check`) |
| An audit with open settle items | Re-run `settle --list` only if `settle_items{S}.txt` is missing; present the items at the next check-in |
| Glance shown, no reply recorded | Re-present the same `reference_glance_v{N}.md` |
| Adjudication batch packed, not ingested | Re-dispatch the same bundle and prompt (same hashes); never re-pack. When it cannot be ingested (no completed pack log, or `ingest` refused it), release it with a reason and pack its rows in a new batch |
| Reader model or route changed since the page-picture choice | Re-run `route --reader-model` and copy its `VISION:` line; an earlier choice no longer applies (`text-only` unless the new model and route are on the list); show the CP-1 warning again and record a new choice if the user wants one |
| Checker model changed since the checker choice, or the identity check now gives another result | Run the identity check again; an acceptance covers only the model ID it names, so the new model's batches are hints; show the CP-1 checker paragraph again and record a new choice if the user wants one |
| Synthesizer dispatched, no deliverable | Re-dispatch with the same VERSION; recorded findings and gaps stand |

### LEARNINGS.md

Mandatory. Create the skeleton at LR-0; append at each CP-R and consolidate at CP-F (search backends, rate gates and gate behaviour are reusable knowledge).

```markdown
# LEARNINGS: {review title}

## Search and Access Notes
<!-- backends that failed or throttled; phrasings that missed seeds; OA retrieval quirks -->

## Tool and Gate Behaviour
<!-- lit_corpus refusals, lit_verify card/report/audit/settle outcomes worth knowing -->

## Reading Notes
<!-- PDF layouts, scans, tables, chunking, image-cap behaviour -->

## Method Notes
<!-- screening criteria that proved undecidable; synthesis or certainty issues -->

## Pending Learning Signals
<!-- one line per subagent Learning Signal, with the stage -->

## System Update Action Plan
<!-- at CP-F: generalizable improvements to skills, agents or tools, P1/P2/P3; or "No generalizable framework updates identified during this review." -->
```

---

## Error Handling

| Signal | Action |
|---|---|
| A searcher return with a retraction flag | Raise it at the next checkpoint; the researcher decides (`attach decision include_retracted` is theirs) |
| `scholar_search` exit 12 twice, or a backend failing all round | Report it at CP-R with the backends that answered; offer a re-run |
| A key paper not retrieved | List it at CP-K or CP-S; the user may add a PDF to `user_pdfs/` |
| `lit_corpus` exit 9 (integrity) | STOP: a table or input changed after it was recorded; tell the user; no further writes |
| Reader BLOCKED (missing ingest, scan without validated vision) | Re-dispatch the searcher to ingest, or tell the user the pages cannot be covered |
| Reader INCOMPLETE (FAIL after two revisions) | The paper supplies no findings; offer a re-read or leave it as context |
| `audit` exit 9 (card changed after its check, or audited before) | Do not re-audit; a new card version is needed |
| `report` exit 11 | Revision loop (≤ 2), then the user. When the FAIL items include `CARD_RECHECK_DIFFERS`, handle those first (the `report --kind final` row below; the same paper's `CLAIM_ROW_MISMATCH` items usually clear with them), run the final check again, then the revision loop for the FAIL items that remain |
| Quick scan: `report --kind final` fails after the user's reply | A KIND final memo with `REVISE FROM`, checked, then shown at CP-F again; the earlier approval does not carry over |
| `quarto pandoc` fails or warns about a citation | Give the user the `.md` with the one-line note on the tags in braces; record the problem in LEARNINGS.md |
| `report --kind final` exit 11 with `CARD_RECHECK_DIFFERS` (a card's re-check differs from its record, e.g. the paper's stored source file is missing or changed) | Do not run the revision loop: the synthesizer cannot restore a file. The item names the paper and what differs, not the cause: open the ingest manifest the paper's `card_check{S}.json` names (its `ingest.manifest`) and check that the file at `source.path` exists and hashes to that manifest's `source.sha256`. **Missing or changed:** put the original file back at that path, unchanged, and run the final check again; do not run `lit_verify card` again (a new card run leaves the paper's current claims bound to an older check, which fails until the claims are rebuilt, and any new check, even with the same result, leaves the audit of readings from pictures of pages behind: the audit names the card_check's sha256, and each check records its own time). **Cannot be restored:** the searcher ingests the paper again (a new fetch, or the user's PDF in `user_pdfs/`), the reader writes a new card version on that ingest (§ Dispatch Templates > paper-reader), then `card`, the audit when the card reads pictures of pages, and a KIND final synthesizer re-dispatch, whose `claims build` rebuilds the claims. **Intact, and the card still differs** (the gate now gives another result): run `lit_verify card` on the latest card again, then the KIND final re-dispatch; a card with readings from pictures of pages gets a new card version instead, then `card` and its audit (an audit is never repeated on one card version). Then the final check; never skip it |
| `report` exit 10 | A missing corpus table, exported reference list, pinned table version or dependency (rapidfuzz for `--kind final`): supply the missing input (`export-bib` for the list; a missing dependency means the image needs a rebuild: tell the user) and run the check again |
| `record-human` or `settle` exit 11 | Read the refusal; fix the rows or items file; never reword the user's words. A reference the list says is left out is never recorded: it is checked again only when the researcher asks (§ The Citation Second Check, step 4, "Check again") |
| `ingest` refuses a batch | Persist nothing more; keep the batch's rows on the glance. A batch that will not be ingested (another model ran under a tested identity, its transcript is gone, a stray read, no completed pack log: `ingest` exit 10 or 11): `adjudications release` with the reason, then pack its rows in a new batch (§ The Citation Second Check > The checker flow) |
| `ingest` exit 0 with a model-check `WARNING` (an untested identity whose transcript records another model) | The batch is kept as hints only, and no acceptance applies to it; record it in STATE and follow § Checkpoint Templates > When the model or setup changes |
| An adjudicator dispatch ends without delivering a report (its hand-back was refused) | Persist nothing; release the batch with that reason; tell the user the reference checker could not return its answer, and show the glance without its hints |
| `untested-checker` or `vision-override` exit 11 | Refused, nothing written (no words; no rationale for an acceptance or a check or accept choice; an acceptance already in force; nothing to withdraw; for `vision-override`, a model already tested on this setup, or `--user-words` or `--rationale` longer than 4000 characters). Read the refusal and fix the call; never reword the user's words. Over 4000 characters: quote the reply that covers the decision. `untested-checker` also refuses an acceptance of a model ID that is on the evaluated list in force (a MANIFEST refusal row, nothing in force changes): "{model} is already on DAAF's evaluated list for the reference checker ({list version}), so no acceptance is needed; no acceptance recorded". Nothing to do: that model's judgments already count. A withdrawal of an earlier acceptance is still allowed |

For a signal not in this table, or a tool exit the table does not name, follow `agent_reference/ERROR_RECOVERY.md` § Literature Review Mode Error Recovery.

---

## Context Management

Context thresholds follow CLAUDE.md § Context & Session Health. The atomic units are a reader wave (dispatch, return, audit, STATE update) and a synthesizer dispatch with its report run. Natural restart points: after CP-K, after each CP-R, and after CP-G. At ELEVATED, update STATE's restart prompt; at HIGH, finish the current unit, update STATE and stop at the next checkpoint.

---

## Boundaries

These boundaries supplement the universal safety boundaries in `CLAUDE.md`. `agent_reference/BOUNDARIES.md` § Mode-Specific Boundaries carries the mode's entry.

**Always Do:**
1. Show the level menu as written, and create the project folder before the scope check
2. Run `lit_verify route --reader-model {ID}` and copy its `ROUTE:` line verbatim into every reader and data-verifier dispatch, and its `VISION:` line into every reader dispatch
3. Audit every reader's latest card, once, in the session that dispatched its readers, with each reader dispatch's agent ID (one per chunk), before its claims are used in a deliverable
4. Run `lit_verify report` on every deliverable, and `--kind final` on the version the researcher receives, before the researcher's approval counts
5. Run the reference checker, then show the reference glance list, before every final deliverable, and record the reply with the user's words verbatim
6. Give the researcher each round and final synthesis as its HTML copy, with the `.md` named as the checked source
7. Record every researcher decision (key papers, full-text decisions, checklist judgments, weights, ratings, reference replies, page comparisons, the reference-checker and page-picture choices) in the user's own words
8. Keep at most 5 readers in flight and one searcher at a time
9. Update STATE.md after every dispatch return and every checkpoint reply
10. Warn the user at the review plan when the reference checker or the paper reader runs on a model DAAF has not tested for that job, and again whenever that model or the setup changes

**Ask First Before:**
1. Any paid call (Elicit, licensed Scite): the user names it, and it goes into SPEND APPROVED
2. Changing the protocol, the level or the stopping rule (a new protocol version)
3. Reading in full a paper outside the approved key-paper list (standard)
4. More than 5 readers in flight
5. Keeping a retracted paper, or a reference whose record does not match
6. Letting an untested reference checker confirm references, or an untested reader read page pictures: only on the user's own choice, recorded with their words (`untested-checker`, `vision-override`, each behind its Ask-First rule)

**Never Do:**
1. Add anything to the citation-adjudicator's prompt, or count an untested checker's verdict as a decision without the researcher's recorded acceptance
2. Type a route, a row hash, a paper key or a claim id; paraphrase or compose a user's words for `record-human`, `settle`, `untested-checker`, `vision-override`, `screen record` or `researcher_grade`
3. Cite a reference waiting for its check, or a paper with an unconfirmed reading audit, in a final deliverable
4. Average, pool or vote-count results across studies, or let wording outrun certainty
5. Edit a checked card, a recorded input or an execution log; re-pack an un-ingested batch; edit `citation-adjudicator.md` between pack and ingest
6. Settle a `chain_unconfirmed` audit by a comparison
7. Let the synthesizer run `lit_verify report` on its own deliverable
8. Show internal codes, agent names, status codes or `settle` item ids to the user
9. Let a second screener record its pass a second time after seeing the disagreement count
10. Record a checker or page-picture choice the user did not give, type a `VISION:` line, or run `untested-checker` or `vision-override` from a script

---

## Orchestrator Skill Loading

None. The agents preload their skills (`scholarly-search`, `literature-review`, `pdf-reading`). The orchestrator reads by path only the sections it shows or follows: `literature-review/SKILL.md` § The level menu (LR-0) and, in `literature-review/references/`, `review-types-and-levels.md` § Questions to ask, by level, `formal-review.md` § The protocol (formal CP-1), and `lit-corpus.md` § Citation second check when a glance or settle refusal needs explaining. Two agent-reference files are read by path as well: `agent_reference/STATE_TEMPLATE_LITREVIEW.md` at LR-0 and on resume, and `agent_reference/LIT_REVIEW_OUTPUT_CONTRACT.md` when a handoff, the data-verifier spot-check or a consumer's question needs the review's output interface (statuses, files, markers, contract version).

---

## Mode Confirmation Template

Process-only (`SKILL.md` § Mode Confirmation Gate): no counts, sources or years. The text for `SKILL.md` § Confirmation Templates by Mode:

> [Why this is a **Literature Review**]. [Your goal in one line]. I'll read the literature review workflow, set up a project folder, and ask how deep you'd like to go: a quick scan of abstracts, a standard review where I read the key papers in full (recommended for most questions), or a formal systematic review that you lead. Then I'll come back with a scope check: the question as I understand it, where I'll search, what counts as in or out, and the expected reading and cost, before any full search starts. Along the way you'll check each reference once before the final version and approve the final write-up; in a standard or formal review you'll also agree which papers get read in full and see what each round found. Every reference is looked up in a database, every quote and number is checked against its page, and results from different studies are never averaged into one number. This mode is experimental: it works end to end and every reference and quote is still checked, but it has had limited real-world testing. Review its output more closely, and tell us what goes wrong. [If materials: I'll read [X] first.] **Shall I proceed?**

---

## Escalation Triggers

All escalations require explicit user confirmation.

| From | To | Trigger | Handoff |
|---|---|---|---|
| Data Discovery | Literature Review | "What's known about …", prior work before choosing data | conversation |
| Literature Review | Data Discovery | A gap is answerable with data and the user wants to see what data exists | `output/LitReview_Handoff_v{N}.md` |
| Literature Review | Full Pipeline | A data-answerable gap the user wants analysed | `output/LitReview_Handoff_v{N}.md` |
| Full Pipeline (Phase 1) | Literature Review | The user wants the literature reviewed before planning | Phase 1 notes |
| Full Pipeline (complete) | Literature Review | A surprising finding needs grounding | report path and findings |
| Ad Hoc Collaboration | Literature Review | The user wants a recorded review with checked citations | conversation |
| Literature Review | Ad Hoc Collaboration | The user wants to discuss rather than run rounds | STATE.md |
| Literature Review | Framework Development | LEARNINGS.md's System Update Action Plan has items (a backend quirk, a gate behaviour) | LEARNINGS.md |
| User Support | Literature Review | The user wants to do a review, not learn about one | conversation |

Propose an escalation as: "Based on [what was found], would you like me to [the other mode's activity]?" On confirmation, write the handoff file and load the other mode's reference. When another mode proposes switching into Literature Review, the proposal includes the experimental notice of § Mode Confirmation Template, both of its sentences word for word (from "it works end to end" to "tell us what goes wrong."), led by "This mode is experimental:" (or "Literature Review mode is experimental:" when it comes before the mode is named), because that proposal stands in for this mode's confirmation.
