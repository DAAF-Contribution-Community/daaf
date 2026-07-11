# Session Notes: Framework Development — HuggingFace Mirror Parquet / R Compatibility

**Started:** 2026-07-11
**Workspace:** /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat
**Work Type:** Modify Existing

## Accomplishments

- Phase 1 scoping complete (3 parallel read-only explorations):
  - Prior notes located in `/daaf/research/2026-07-07_HS_Disadvantage_College_Outcomes/`
    (STATE.md Runtime Risks + execution logs of `scripts/stage5_fetch/05_fetch-saipe.R`
    and `04_fetch-edfacts-gradrates_a.R`)
  - Verbatim error: `cannot handle Array of type <utf8_view>` from
    `arrow::read_parquet(url)` — R 4.5.3, arrow 23.0.1.2 (full C++ build, all codecs)
  - Affected (confirmed): SAIPE districts; EDFacts grad rates 2015-2019.
    Not affected: MEPS (read OK from mirror). CCD directory failed differently
    (download truncation — OUT OF SCOPE, logged as follow-up)
  - Mirror: `brhkim/education_data_portal_mirror` (HuggingFace), parquet-only,
    priority-1 in `education-data-query/references/mirrors.yaml`; no upload
    tooling exists in-repo; file provenance undocumented
  - Working hypothesis (MEDIUM confidence, to be verified): failing files carry an
    embedded ARROW:schema hint declaring `utf8_view` (StringView) string columns —
    characteristic of Polars-written parquet. R arrow's C++ layer reads them, but
    the R-binding conversion to character vectors fails.

## Key Decisions

- User confirmed scope at Checkpoint 1 (2026-07-11): prefer an R read-pattern fix
  in the querying skill over re-uploading the mirror in a compatible format
- CCD directory truncation issue explicitly excluded from scope (separate failure mode)
- Fix strategy order: (1) verified read-pattern change in skills;
  (2) fallback: arrow upgrade via Dockerfile P3M snapshot bump;
  (3) last resort: mirror re-upload

## Integration Status

**Component:** `education-data-query` skill (SKILL.md + references/fetch-patterns.md),
`tidyverse` skill (references/io.md), LEARNINGS flush for
2026-07-07_HS_Disadvantage_College_Outcomes
**Checklist:** FRAMEWORK_INTEGRATION_CHECKLIST.md § modification subsection
**Completed:** 0 of TBD items
**Remaining:** repro verification, skill edits, learnings flush, 3-angle review

## In Progress

- Fix cycle 1 COMPLETE (2026-07-11): user approved gap fixes, declined SKILL.md
  trim (replication useful for less capable models). Orchestrator added caution
  NOTEs at all 4 gap sites (comment-only edits, git-diff-verified):
  edfacts variable-definitions.md:635, graduation-rates.md:420,
  SCRIPT_EXECUTION_REFERENCE.md:1668, ERROR_RECOVERY.md:407
- Re-review (2-angle): Consistency CLEAN (pointers resolve, error string
  byte-identical, framing correct per snippet role, no code lines altered).
  Completeness: 4/4 CLOSED, but broader re-sweep found ~24 PRE-EXISTING
  R plain-read-of-mirror-URL sites in 19 files across other source skills
  (fsa x9, nccs x9, pseo x5, scorecard x2, ipeds x2, eada, campus-safety,
  nhgis x3) + DATA_SOURCE_SKILL_TEMPLATE.md:361 — same risk class, unknown
  whether those datasets are view-typed (only SAIPE/EDFacts confirmed; MEPS
  is Polars-written but NOT view-typed, so per-file variation exists)
- Fix cycle 2 COMPLETE (2026-07-11): user approved full second pass.
  framework-engineer added caution NOTEs to 19 files (18 data-source skill
  files + DATA_SOURCE_SKILL_TEMPLATE.md): 114 insertions, 0 deletions,
  28 NOTEs (27 skill-doc byte-identical + 1 domain-generic template NOTE with
  carry-forward directive). Hedged wording used throughout ("may declare"/
  "can fail") since only SAIPE/EDFacts are confirmed view-typed.
- Re-review cycle 2 (2-angle): Consistency PASS all six checks (insertions-only
  via git numstat, hedged wording verified by empty assertive-variant grep,
  28 NOTE == 28 error-string counts reconcile, pointers resolve, placement
  spot-checked at 8 sites incl. multi-read fences, template carry-forward
  framing confirmed). Completeness: ZERO GAPS remaining framework-wide —
  every R-context external-mirror read has the view-safe pattern or a caution;
  utf8_view signature discoverable in 27 files; CLAUDE.md/user_reference clean
  (one benign local-path FAQ mention, correctly uncautioned).
  Template phrase-count of 2 explained: 1 NOTE + its carry-forward directive
  quoting the term.
- Awaiting final user approval at Checkpoint 2. All changes uncommitted on
  branch daaf_dev_R2 (commits are user-initiated per harness rule).

## Phase 3 Step 2 + Verification (COMPLETE)

- Skill edits applied by framework specialist (6 files): education-data-query
  SKILL.md + fetch-patterns.md (both R branches) + mirrors.yaml + and
  datasets-reference.md; tidyverse io.md; LEARNINGS/STATE flush for
  2026-07-07_HS_Disadvantage_College_Outcomes (3 signals, accounting 5=5)
- Engineer reordered conditional to large_string_view-first (defensive vs
  substring collision); orchestrator closed the untested-variant gap with
  scripts/scratch/08_verify-prescribed-pattern.R — exit 0: unit check all 4
  branches, SAIPE reads correctly (368,967 x 10), MEPS exact no-op
- Orchestrator direct fix: io.md Write Parquet note "below" -> "above"

## Phase 4 Review Findings (2026-07-11)

- Consistency (opus): no blockers; pattern byte-identical at all 4 code sites;
  all cross-refs resolve; YAML parses; flush accounting reconciles (2+3=5).
  Trivial nit: SKILL.md:188 "View-safe" capitalization (no action)
- Quality (opus): no blockers; code verified against execution logs.
  SUGGESTION: trim SKILL.md:187-212 full pattern to shape + pointer
  (skill-authoring anti-duplication; 4 copies risk future drift)
- Completeness (sonnet): 4 propagation gaps still teaching plain
  arrow::read_parquet(url) for external mirror URLs:
  1. education-data-source-edfacts/references/variable-definitions.md:636,644
  2. education-data-source-edfacts/references/graduation-rates.md:420
  3. agent_reference/SCRIPT_EXECUTION_REFERENCE.md:1668 (R mirror-loop template)
  4. agent_reference/ERROR_RECOVERY.md:407 (mirror-fallback template)
  EDFacts gaps read CONFIRMED-affected files. Error-string discoverability HIGH
  (verbatim signature in io.md/fetch-patterns.md); learning signals all flushed

## Repro Findings (Phase 3 step 1 — COMPLETE, hypothesis CONFIRMED w/ refinement)

- No ARROW:schema metadata hint: `string_view` is declared in the parquet-native
  logical schema (`created_by='Polars'` on both failing and working files; the
  working MEPS file simply has zero view-typed columns)
- Failure isolated to R-binding Table→data.frame conversion; C++ Table read succeeds
- Verified fix: `read_parquet(as_data_frame = FALSE)` → rebuild schema mapping
  `string_view`→`utf8`, `large_string_view`→`large_utf8`, `binary_view`→`binary`
  (pass-through otherwise) → `tbl$cast(schema)` → `as.data.frame()`
- Proven: repro on local + URL; fix works on failing file + URL; no-op on MEPS;
  values/rows/cols match polars read exactly
- Gotchas: `open_dataset() |> collect()` does NOT work (same error);
  R arrow `Schema$field(i)` is 0-indexed
- Diagnostic scripts: `scripts/scratch/01`–`06` (03 failed, retained; 03_a corrected)

## Open Questions

- (none blocking)

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework
Development mode. DAAF contributed to: prior-note discovery, R parquet stack
diagnosis, empirical fix verification, skill reference updates, and cross-file
consistency review. The researcher directed all framework design decisions and
approved all changes.
