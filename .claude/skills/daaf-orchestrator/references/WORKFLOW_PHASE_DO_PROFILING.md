# Data Onboarding: Profiling Phase (Stages DI-3 through DI-6)

Loaded by the orchestrator when entering the profiling phase. Contains part details, invocation templates, conditional execution rules, multi-file profiling protocols, and verification checklists. The main mode reference file (`data-onboarding-mode.md`) contains the workflow overview, gate definitions, execution cycle, and PSU templates.

---

## Profiling Protocol

### Script Inventory

| # | Part | Script Name | Purpose | Conditional? | Script Path Pattern |
|---|-------|-------------|---------|--------------|---------------------|
| 01 | A | load-and-format (or inventory for HIERARCHICAL) | Format detection, encoding validation, canonical load pattern; HIERARCHICAL: un-suffixed `01_inventory` inventories all files first | No | `scripts/profile_structural/01_load-and-format.py` (`.R` for R) (HIERARCHICAL: `01_inventory.py`/`.R` + `01a_load-and-format.py`/`.R`, `01b_...`, etc.) |
| 02 | A | structural-profile | Row/column counts, memory, types, schema | No | `scripts/profile_structural/02_structural-profile.py` (`.R` for R) |
| 03 | A | column-profile | Per-column statistics, value distributions | No | `scripts/profile_structural/03_column-profile.py` (`.R` for R) |
| 04 | B | distribution-analysis | Distribution fitting, outlier detection, multimodality | No | `scripts/profile_statistical/04_distribution-analysis.py` (`.R` for R) |
| 05 | B | temporal-coverage | Time coverage gaps, record count trends, drift | Yes: time column | `scripts/profile_statistical/05_temporal-coverage.py` (`.R` for R) |
| 06 | B | entity-coverage | Entity/geographic coverage, ID format validation | Yes: entity/geo ID | `scripts/profile_statistical/06_entity-coverage.py` (`.R` for R) |
| 07 | C | key-integrity | Uniqueness testing, composite keys, functional dependencies | No | `scripts/profile_relational/07_key-integrity.py` (`.R` for R) |
| 07b | C | cross-level-linkage | Cross-file key cardinality, coverage, orphan detection, join simulation | Yes: HIERARCHICAL | `scripts/profile_relational/07b_cross-level-linkage.py` (`.R` for R) |
| 08 | C | correlation-dependency | Pearson/Spearman, Cramer's V, redundant column detection | Yes: >=3 numeric cols | `scripts/profile_relational/08_correlation-dependency.py` (`.R` for R) |
| 09 | C | quality-anomaly | Completeness, coded missing values, duplicates, anomaly catalog | No | `scripts/profile_relational/09_quality-anomaly.py` (`.R` for R) |
| 10 | D | semantic-interpretation | Column name/value pattern matching, data dictionary draft | No | `scripts/profile_interpretation/10_semantic-interpretation.py` (`.R` for R) |
| 11 | D | reconcile-docs | Documentation verification, discrepancy report | Yes: docs provided | `scripts/profile_interpretation/11_reconcile-docs.py` (`.R` for R) |

### Part Dependency Diagram

```
Part A: Structural Discovery            Part B: Statistical Deep Dive
  01 ──> 02 ──> 03                       04 (ALWAYS)
  (sequential — canonical load             05? (time column found)
   pattern established in 01)              06? (entity/geo ID found)
       │                                 (independent within part)
       │  Part A findings gate             │
       │  conditional decisions            │
       v                                   v
Part C: Relational Analysis             Part D: Interpretation & Reconciliation
  07 (ALWAYS, per-file if HIERARCHICAL)    10 ──> 11?
  07b? (HIERARCHICAL only — after all      (sequential — 11 verifies docs
        per-file 07 scripts complete)        if provided)
  08? (>=3 numeric cols)
  09 (ALWAYS, per-file if HIERARCHICAL)
  (independent within part, except
   07b depends on all 07 scripts)
```

### Conditional Execution Rules

Scripts 05, 06, 07b, 08, and 11 are conditional. The orchestrator decides at part boundaries based on Part A structural findings, file structure classification, and intake information.

```
Script 05 (Temporal Analysis):
    Part A found date/time/year columns?
        YES → Execute script 05
        NO  → Skip; document "no temporal columns detected" in STATE.md

Script 06 (Entity Coverage):
    Part A found entity/geographic ID columns (state, county, FIPS, zip, entity ID)?
        YES → Execute script 06
        NO  → Skip; document "no entity/geographic ID columns detected" in STATE.md

Script 07b (Cross-Level Linkage):
    File structure = HIERARCHICAL?
        YES → Execute script 07b (after all per-file 07 scripts complete)
        NO  → Skip; document "single-file or horizontal — cross-level analysis not applicable"

Script 08 (Correlation/Dependency):
    Part A found >= 3 numeric columns?
        YES → Execute script 08
        NO  → Skip; document "fewer than 3 numeric columns — correlation analysis not applicable" in STATE.md

Script 11 (Documentation Reconciliation):
    User provided documentation at intake?
        YES → Execute script 11
        NO  → Skip; document "no documentation provided for reconciliation" in STATE.md
```

Document all skip decisions in STATE.md with the reasoning, **and declare each skip in the affected checkpoint's `not_applicable` mapping with that same reason** — a skip only counts as a skip when it is declared. A *declared* skip records `[SKIPPED]` and does not affect gate passage: gates evaluate the checks that ran, plus the written reasons the rest were waived. An *undeclared* absence is not equivalent — the check records `[NOT VERIFIED]`, which forces at least `WARNING` on a `QAP{N} RESULT` line and `FAILED` on a `CPP{N} VALIDATION` verdict (see § QAP Outcome Vocabulary below and `agent_reference/VALIDATION_CHECKPOINTS.md`). Silently omitting a conditional script therefore does not leave the gate clean; it leaves it unverified.

## Column Batching Strategy

For datasets with more than 100 columns, profiling scripts that inspect individual columns (02, 03, 04, 10) must be batched to avoid context overflow in subagent invocations.

- **Batch size:** ~50 columns per invocation
- **Batching method:** Partition the column list into groups of ~50; dispatch one subagent invocation per batch
- **Priority columns first:** If the user specified priority columns at intake, include them in the first batch
- **Merge outputs:** After all batches complete, merge per-batch outputs into a single consolidated result before proceeding to the next part
- **STATE.md tracking:** Record batch boundaries and completion status for each batch

> **Wave barrier discipline (async dispatch).** Column batching is this mode's parallel-dispatch surface: multiple data-ingest invocations for the same profiling script may run concurrently. Subagents dispatched via the Agent tool run in the background by default and return via completion notifications that may arrive one at a time. Treat mid-wave notifications as **status-only**: do not merge per-batch outputs, advance to the next part, or update STATE.md conclusions until EVERY batch invocation in the wave has returned. The merge happens once, over the complete set of batch returns — never incrementally per return. An early return under context pressure, or a failed batch, still counts as that batch's completion — handle re-dispatch as part of the whole-wave merge, not as an immediate mid-wave reaction. The sequential Part A → B → C → D dispatches are governed by the same principle at their gates (see below): each part's completion notification must arrive and its preliminary notes must be persisted before the next part is dispatched.

## Multi-File Profiling

When intake includes multiple data files, the profiling protocol adapts based on the file structure classification from DI-1.

#### File Structure: HORIZONTAL (Same Schema, Multiple Files)

For same-schema files (e.g., one file per year, one per state):

1. **Script 01** loads a sample from each file and verifies schema compatibility: column names, types, and order
2. **If schemas match** (default path): Concatenate all files into a single DataFrame with a `_source_file` tracking column. Profile the combined dataset through Parts A-D as if it were a single file. The concatenation approach is the default but the user is asked to confirm at DI-1.
3. **If schemas diverge:** Flag specific differences (added/removed columns, type changes across files) as a WARNING. Profile the union of columns. Note per-file column availability in the execution log.
4. **Temporal scripts (05)** become especially valuable for horizontal files — they reveal coverage gaps and overlap across the file set
5. **The skill documents:** multi-file structure (year range, file naming pattern, schema drift if any) so future fetches know to retrieve multiple files

**Script naming:** Standard (no suffix) since the combined dataset is profiled as one unit. The concatenation happens in script 01.

### Schema Drift Handling (HORIZONTAL)

For files with partially overlapping schemas (e.g., same columns mostly, but some year-specific additions):

- **If schemas overlap >=80%** (most columns shared): Concatenate the shared columns with a `_source_file` tracking column. Document per-file unique columns as supplementary fields in the execution log. The skill should note which columns are available only in specific file segments.
- **If schemas overlap 50-80%**: Flag as WARNING. Concatenate shared columns, document divergent columns per-file. Consider whether the non-shared columns represent meaningful structural changes (e.g., methodology revisions) vs. simple additions.
- **If schemas overlap <50%**: Reclassify as HIERARCHICAL — the files represent fundamentally different data structures, not segments of the same structure.

Schema overlap is calculated as: `(columns in intersection) / (columns in union) x 100%`.

#### File Structure: HIERARCHICAL (Different Schemas, Linked by Keys)

For files at different aggregation levels (e.g., schools, districts, states):

1. **Script 01_inventory.py** (un-suffixed prologue) runs first: inventories all files, produces a **schema map table** (file -> entity type -> row count -> column count -> suspected join key), designates **primary** (most granular or largest) vs **auxiliary** files, and validates that all files are accessible and non-empty. This script is the cross-file orchestration step; it does NOT do per-file profiling.
2. **Per-file scripts are suffixed:** `01a_load-and-format.py` (file 1), `01b_load-and-format.py` (file 2), etc. Scripts 02 and 03 are similarly suffixed. Each file gets its own canonical load pattern established in its `01{x}` script.
3. **Part B scripts are suffixed per file** where applicable: `04a_distribution-analysis.py`, `04b_distribution-analysis.py`, etc. Conditional scripts (05, 06) run per-file based on per-file characteristics.
4. **Part C runs per-file AND cross-file:**
   - Scripts 07, 09 run per-file (suffixed) for within-file key integrity and quality
   - **Script 07b: cross-level-linkage.py** (new, conditional on HIERARCHICAL) runs once across all files to test cross-file relationships: key cardinality, coverage completeness, orphan detection, temporal alignment, and join loss simulation
   - Script 08 runs per-file if applicable (suffixed)
5. **Part D runs per-file AND produces cross-file output:**
   - Script 10 runs per-file (suffixed) for per-file semantic interpretations
   - Script 10 also produces a cross-file schema map showing the join topology
   - Script 11 (if docs provided) runs once across all files
6. **Skill authoring subagent** synthesizes per-file and cross-file findings from all scripts. For UNIFIED skill structure: one SKILL.md with a Multi-File Structure section. For PER-ENTITY: one SKILL.md per entity type with cross-references.

**Script naming convention for HIERARCHICAL** (shown with `.py`; use `.R` when execution language is R):
```
scripts/profile_structural/
  01_inventory.py              (cross-file: schema map, file inventory)
  01a_load-and-format.py      (file 1: schools)
  01b_load-and-format.py      (file 2: districts)
  02a_structural-profile.py
  02b_structural-profile.py
  03a_column-profile.py
  03b_column-profile.py
scripts/profile_statistical/
  04a_distribution-analysis.py
  04b_distribution-analysis.py
  05a_temporal-coverage.py     (if applicable per file)
  06a_entity-coverage.py       (if applicable per file)
scripts/profile_relational/
  07a_key-integrity.py         (per-file)
  07b_cross-level-linkage.py   (cross-file, runs once)
  08a_correlation-dependency.py (if applicable per file)
  09a_quality-anomaly.py       (per-file)
scripts/profile_interpretation/
  10a_semantic-interpretation.py (per-file + cross-file schema map)
  10b_semantic-interpretation.py
  11_reconcile-docs.py          (once, if docs provided)
```

**STATE.md tracking for multi-file:** The Profiling Progress table gains per-file rows using the suffix convention. The orchestrator tracks completion per-file and gates on all files within a part completing before proceeding to QA.

#### Conditional Script: 07b Cross-Level Linkage

**07b_cross-level-linkage.py** (CONDITIONAL — only if file structure = HIERARCHICAL):

Runs once during Part C, after per-file script 07 completes for all files. Tests:

1. **Key cardinality:** Count unique key values in each file; classify each link as 1:1, 1:M, or M:M
2. **Coverage completeness:** What % of child-level keys exist in the parent-level file?
3. **Orphan detection:** List child records with no parent match (counts + sample key values)
4. **Temporal alignment:** If both files have time columns, compare coverage periods and identify gaps
5. **Join loss simulation:** Perform inner join on declared keys; report row survival rate
6. **Join duplication check:** Does joining create unexpected row multiplication?

**Print requirements (execution log — no size limit):**
- MUST print the complete cross-file relationship table
- MUST print orphan counts and sample orphan key values (top 10 per link)
- MUST print join simulation results for every declared key pair
- MUST print temporal alignment matrix if applicable

**Conditional execution rule:**
```
Script 07b (Cross-Level Linkage):
    File structure = HIERARCHICAL?
        YES → Execute script 07b after all per-file 07 scripts complete
        NO  → Skip; document "single-file or horizontal — cross-level analysis not applicable"
```

---

## Part Details

### Part A -- Structural Discovery

Scripts 01-03 establish foundational understanding. Always fully executed.

**01_load-and-format:** Detect file format (CSV/TSV/Parquet/Excel/JSON), validate encoding (BOM, line endings, delimiter inference), analyze character set, establish canonical load call — `pl.read_*` (Python/Polars) or `arrow::read_parquet()` / `readr::read_csv()` (R) — with exact parameters reused by all subsequent scripts. Outputs: detected format/encoding, canonical load statement, CPP1 results.

**02_structural-profile.py:** Extract row/column counts, estimated memory footprint (MB), column data types and order, first/last 5 rows for visual inspection, schema summary table. Outputs: shape, memory, type distribution, schema.

**03_column-profile.py:** Per-column stats: nulls, uniques, uniqueness ratio. Numerics: min/max/mean/median/std, percentiles (p5/p25/p50/p75/p95), skewness, kurtosis. Strings: min/max length, empty count, pattern detection (emails/phones/dates/IDs). Categoricals (<50 unique): top 20 value counts. Outputs: complete per-column profile, potential identifier flags (>95% unique).

#### CPP1: Post-Load Validation

Embedded in script 01, in its `# --- Validate ---` section.

> **The code lives in one place.** Copy the CPP1 block (Python and R) verbatim from
> `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints > CPP1: Post-Load Validation.
> That section is canonical; this file supplies only the config stanza and the
> part-specific guidance. Do not paraphrase the block and do not re-derive it from
> memory — the checkpoint's whole value is that its outcome tokens and count line are
> identical across every onboarding project.

**Config stanza — assign these in script 01's `# --- Config ---` region before the block:**
```python
df = None                # set to the loaded frame; stays None if the load produced nothing
not_applicable = {}      # e.g. {"encoding": "parquet input — encoding was fixed at write time"}
```
```r
df <- NULL
not_applicable <- list()
```

**What CPP1 reports:** one outcome line each for shape, overall null rate, entirely-null
columns, row volume, and encoding damage (U+FFFD scan), then the count line and
`CPP1 VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED`. Entirely-null columns and a
sub-100-row frame are `[WARNING]` (the checkpoint still passes, with warnings); an empty
frame, a >=50% null rate, or replacement characters are `[FAIL]`.

#### QAP1: Post-Structural QA

> **The checklist lives in one place.** The QAP1 default checks — each with its
> `not_applicable` key, its BLOCKER condition, and the per-check statement of what is
> *not applicable* versus *not verifiable* — are canonical in
> `agent_reference/QA_CHECKPOINTS.md` § Profiling QA Checkpoints (QAP1-QAP4) > QAP1: Post-Structural (Part A).
> Read them there and use those keys verbatim; do not paraphrase them here or re-derive
> them from memory.

QAP1 asks whether Part A's structural claims survive independent re-testing: the file loads to the same shape under an alternative parameterization, sample rows match the raw file, text is undamaged, type inference is stable, and every column in the schema appears in the column profile.

**QA Script Path:** `scripts/cr/profile_structural_cr1.py`

### Part B -- Statistical Deep Dive

Scripts 04-06 analyze distributions, temporal patterns, and entity coverage. Independent within part. Scripts 05 and 06 are conditional.

**04_distribution-analysis.py (ALWAYS):** Distribution fitting per numeric column, multimodality detection (histogram gap analysis), outlier ID via IQR (1.5x/3x) and z-score (|z|>3), skewness/kurtosis interpretation, heavy-tail flagging. Outputs: distribution classifications, outlier counts/percentages, multimodality flags.

**05_temporal-coverage.py (CONDITIONAL: time column):** Year/period coverage gaps, record count trends over time, value drift across periods, panel completeness (entity-time matrix), structural break detection. Outputs: coverage listing, trend analysis, completeness matrix, break flags.

**06_entity-coverage.py (CONDITIONAL: entity/geo ID):** Coverage completeness vs known universe, identifier format validation (FIPS padding, ISO codes), geographic anomaly catalog, entity appearance frequency distribution. Outputs: completeness ratio, format validation results, anomaly catalog.

#### CPP2: Post-Statistical Validation

Embedded in the last executed script of Part B, in its `# --- Validate ---` section.

> **The code lives in one place.** Copy the CPP2 block (Python and R) verbatim from
> `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints > CPP2: Post-Statistical Validation.

**Config stanza — assign these before the block:**
```python
df = None                    # the frame profiled in Part B
numeric_columns = []         # numeric column names identified in Part A
temporal_expected = None     # True/False from the orchestrator's Part A determination
time_columns_found = None    # True/False set by script 05; None if script 05 did not run
not_applicable = {}          # e.g. {"temporal_detection": "script 05 skipped — no date/time/year columns in Part A"}
```
```r
df <- NULL
numeric_columns <- character(0)
temporal_expected <- NULL
time_columns_found <- NULL
not_applicable <- list()
```

**What CPP2 reports:** one outcome line per numeric column for mean-within-[min,max] and
for percentile monotonicity, plus one line for the temporal determination, then the count
line and verdict. An **empty `numeric_columns`** is `[NOT VERIFIED]` (⇒ `FAILED`), not a
silent pass — if the dataset genuinely has no numeric columns, declare
`not_applicable["numeric_summaries"]` and `not_applicable["percentile_monotonicity"]` with
that reason. An all-null column is `[NOT VERIFIED]` for that column rather than a crash.

#### QAP2: Post-Statistical QA

> **The checklist lives in one place.** The QAP2 default checks — each with its
> `not_applicable` key, its BLOCKER condition, and the per-check statement of what is
> *not applicable* versus *not verifiable* — are canonical in
> `agent_reference/QA_CHECKPOINTS.md` § Profiling QA Checkpoints (QAP1-QAP4) > QAP2: Post-Statistical (Part B).
> Read them there and use those keys verbatim.

QAP2 asks whether Part B's statistical characterization holds up: recomputed summary statistics match the profiled ones, distribution labels survive the appropriate test, outlier fences are defensible, and the temporal and entity-coverage findings are complete. Scripts 05 and 06 are conditional, so the orchestrator must tell the reviewer which of them ran and why — a conditional script whose skip was decided and recorded becomes a declared `[SKIPPED]`, while an unstated absence is `[NOT VERIFIED]`.

**QA Script Path:** `scripts/cr/profile_statistical_cr1.py`

### Part C -- Relational Analysis

Scripts 07-09 examine inter-column relationships. Independent within part. Script 08 is conditional.

**07_key-integrity.py (ALWAYS):** Single-column uniqueness for all columns, composite key combinatorial testing (pairs/triples), functional dependency detection, near-duplicate keys (edit distance for strings), multi-file referential integrity. Outputs: uniqueness results, composite key candidates, dependency map, recommended primary key.

**08_correlation-dependency.py (CONDITIONAL: >=3 numeric):** Pearson/Spearman correlation matrices, Cramer's V for categoricals, high-correlation flagging (|r|>0.8), redundant column detection (|r|>0.95), conditional distributions across categorical groups. Outputs: correlation matrices, redundancy candidates, conditional summaries.

**09_quality-anomaly.py (ALWAYS):** Completeness summary, coded missing value scan (negatives: -1,-2,-3,-9,-99,-999; strings: "NA","N/A","Missing","","Unknown","."; high sentinels: 999,9999), exact/near duplicate rows, cross-column consistency rules, anomaly catalog with BLOCKER/WARNING/INFO severity. Outputs: completeness table, sentinel scan results, duplicate counts, anomaly catalog.

#### CPP3: Post-Relational Validation

Embedded in script 09 (the last executed script of Part C), in its `# --- Validate ---` section.

> **The code lives in one place.** Copy the CPP3 block (Python and R) verbatim from
> `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints > CPP3: Post-Relational Validation,
> **including the re-computation NOTE** that precedes it.

> **Re-computation NOTE.** Each profiling script runs as its own process; there is no
> shared in-memory state. `uniqueness_results` (script 07) and `correlation_matrix`
> (script 08) must be recomputed or loaded inside script 09 before the block runs.

**Config stanza — assign these before the block:**
```python
df = None                    # the frame profiled in Part C
anomaly_catalog = None       # list of anomaly records from script 09
correlation_matrix = None    # square matrix recomputed/loaded here; None if script 08 skipped
key_candidates = []          # key columns nominated by script 07
uniqueness_results = {}      # {column: reported_n_unique} recomputed/loaded here
not_applicable = {}          # e.g. {"correlation_symmetry": "script 08 skipped — fewer than 3 numeric columns"}
```
```r
df <- NULL
anomaly_catalog <- NULL
correlation_matrix <- NULL
key_candidates <- character(0)
uniqueness_results <- list()
not_applicable <- list()
```

**What CPP3 reports:** one line for the anomaly catalog, one for correlation symmetry, and
one per key candidate for uniqueness agreement, then the count line and verdict. When
script 08 was skipped, a bare `correlation_matrix = None` is `[NOT VERIFIED]` (⇒ `FAILED`) —
carry the orchestrator's documented skip reason into
`not_applicable["correlation_symmetry"]` so it becomes a counted `[SKIPPED]`. An all-NA
correlation matrix is `[NOT VERIFIED]`, never a vacuous symmetry pass.

#### QAP3: Post-Relational QA

> **The checklist lives in one place.** The QAP3 default checks — each with its
> `not_applicable` key, its BLOCKER condition, and the per-check statement of what is
> *not applicable* versus *not verifiable* — are canonical in
> `agent_reference/QA_CHECKPOINTS.md` § Profiling QA Checkpoints (QAP1-QAP4) > QAP3: Post-Relational (Part C).
> Read them there and use those keys verbatim.

QAP3 asks whether Part C's relationship claims are real: nominated keys are unique when tested independently, claimed functional dependencies have no counter-examples, the anomaly catalog is complete, cross-column consistency rules cover what the schema allows, and the sentinel scan reached every numeric column. For HIERARCHICAL sources it also covers script 07b's cross-file linkage results (cardinality, coverage, orphans, join simulation); for SINGLE or HORIZONTAL sources that check is declared not applicable with the recorded reason.

**QA Script Path:** `scripts/cr/profile_relational_cr1.py`

### Part D -- Interpretation & Reconciliation

Scripts 10-11 produce interpretations and reconciliation. Sequential: 10 before 11 (if applicable).

**10_semantic-interpretation.py (ALWAYS):** Column name pattern matching (FIPS->geo, _id->identifier, _pct->percentage, _dt->temporal, _cd->categorical), value patterns (binary 0/1, year-like 1900-2100, percentage-like 0-100 or 0-1), domain heuristics, derived metric feasibility, join key candidates, data dictionary draft. ALL marked `[PRELIMINARY]`. **Domain decomposition:** Group columns into analytical domains and assess which warrant dedicated reference files in the skill. **Exclusion observations:** Note any apparent population boundaries based on entity coverage and column scope. Outputs: role assignments, pattern classifications, draft data dictionary, domain decomposition, exclusion observations.

**11_reconcile-docs.py (CONDITIONAL: docs provided):** Column existence/order/type verification against documentation, value enumeration verification, scope verification (time range, coverage, entity count), cross-document consistency, discrepancy report with BLOCKER/WARNING/INFO severity. **Exclusion extraction:** Extract all exclusion statements from documentation ("does not include," "excludes," "limited to," "only covers"). Outputs: verification results per documented claim, discrepancy catalog, exclusions identified.

#### CPP4: Post-Interpretation Validation

Embedded in the last executed Part D script (script 11 if docs provided, otherwise script 10), in its `# --- Validate ---` section.

> **The code lives in one place.** Copy the CPP4 block (Python and R) verbatim from
> `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints > CPP4: Post-Interpretation Validation.

**CPP4 checks the structured draft, not printed text.** Script 10 must build
`data_dictionary_draft` as an enumerable set of records — one per interpreted column,
each with a `column` name and an `interpretation` string (Python: a list of dicts;
R: a data.frame with `column` and `interpretation` character columns). This is the same
draft data dictionary Part D already owes; CPP4 simply requires it as an object rather
than as console output, because "zero records" is detectable while "zero regex matches
against printed text" silently passed.

**Config stanza — assign these before the block:**
```python
data_dictionary_draft = None   # list of {"column": str, "interpretation": str} from script 10
documentation_provided = None  # True/False from intake
reconciliation_ran = None      # True/False set by script 11; None if script 11 did not run
not_applicable = {}
```
```r
data_dictionary_draft <- NULL   # data.frame(column = character(), interpretation = character())
documentation_provided <- NULL
reconciliation_ran <- NULL
not_applicable <- list()
```

**What CPP4 reports:** one line per interpretation record (every non-empty line of the
record's text must carry `[PRELIMINARY]` or `[NO INTERPRETATION]` — a hedge on the first
line does not cover the rest) plus one line for documentation reconciliation, then the
count line and verdict. `documentation_provided = False` is a `[PASS]` with evidence, not
a skip; a missing or empty draft is `[NOT VERIFIED]` (⇒ `FAILED`).

#### QAP4: Post-Interpretation QA

> **The checklist lives in one place.** The QAP4 default checks — each with its
> `not_applicable` key, its BLOCKER condition, and the per-check statement of what is
> *not applicable* versus *not verifiable* — are canonical in
> `agent_reference/QA_CHECKPOINTS.md` § Profiling QA Checkpoints (QAP1-QAP4) > QAP4: Post-Interpretation (Part D).
> Read them there and use those keys verbatim.

QAP4 asks whether Part D's semantic claims are honestly hedged and completely reconciled: every interpretation line carries a `[PRELIMINARY]` (or `[NO INTERPRETATION]`) marker, every documented claim was checked against the data when documentation existed, every discrepancy shows its actual-versus-documented values, and every column with identifiable meaning has an entry. Script 11 runs only when documentation was provided, so the documentation-bound checks are declared not applicable with that reason rather than passing silently.

**QA Script Path:** `scripts/cr/profile_interpretation_cr1.py`

#### QAP Outcome Vocabulary (all four parts)

QAP reviews use the review-severity family. The canonical wording — the six tokens, the
count line, the derived verdict, the applicability declarations, and the escalation rule —
is `agent_reference/QA_CHECKPOINTS.md` § QAP Severity Classification, § QAP Applicability
Declarations, and § QAP Count Line and Verdict. What follows is an orientation summary; where
it and QA_CHECKPOINTS.md differ, QA_CHECKPOINTS.md governs.

- Per-check lines start with `[PASS]`, `[WARNING]`, `[BLOCKER]`, `[NOT VERIFIED]`, `[SKIPPED]`, or `[INFO]`, carrying the observed numbers, followed by a count line and `QAP{N} RESULT: PASSED | WARNING | BLOCKER`.
- `BLOCKER` if any blocker; else `WARNING` if any warning **or any NOT VERIFIED**; else `PASSED`. Zero checks run ⇒ `WARNING`.
- **`[NOT VERIFIED]` forces at least `WARNING`** — a review check that could not run has not reviewed anything, so it cannot be absorbed into a clean pass. Each checkpoint's canonical table states, per check, which absences are expected and should instead be declared not applicable with the orchestrator's documented reason (making them counted `[SKIPPED]`).
- Escalation: if the profiling part *promised* the input a check needs (e.g. Part C reported a correlation matrix but the QA script cannot find it), the reviewer escalates that NOT VERIFIED to `BLOCKER` under the "validation inadequate" criterion and says so.

---

## Invocation Templates

Invocation templates for all profiling, QA, and revision subagent calls. The orchestrator substitutes context-specific values before dispatching.

### Part A: Structural Discovery

**Purpose:** Execute scripts 01-03  |  **Stage:** DI-3, Part A  |  **Subagent:** data-ingest  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Part A: Structural Discovery (scripts 01-03)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. Execute ONLY Part A work (scripts 01-03).
Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the file-first protocol.
Read `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints > CPP1 and copy
that block verbatim into script 01's `# --- Validate ---` section; assign its config stanza in
`# --- Config ---`. It is the only maintained copy — do not write CPP code from memory.

**CONTEXT:**
- Profiling part: A
- Data file: {data_file_path} (primary file if multi-file)
- File format: {file_format}
- File size: {file_size}
- Target skill name: {skill_name}
- Domain context: {domain_context}
- Intended use: {intended_use}
- Data pull date: {data_pull_date}
- Project script dir: {project_script_dir}
- Priority columns: {priority_columns_or_none}
- Documentation files: {doc_file_paths_or_none}
- Documentation website URL: {doc_url_or_none}
- Prior part findings: (none — this is Part A)
- Conditional script decisions: (determined by Part A output)
- Access method: {local_file_or_api}
- File structure: {SINGLE_or_HORIZONTAL_or_HIERARCHICAL}
- Multi-file paths: {list_of_all_file_paths_or_none} (if HORIZONTAL or HIERARCHICAL)
- Schema map: {file_to_entity_mapping_and_keys_or_none} (if HIERARCHICAL — from DI-1)
- Acquisition script path: {path_or_none} (if API-acquired — for provenance)

**TASK:**
[If SINGLE or HORIZONTAL:]
1. Write and execute 01_load-and-format.py — canonical load pattern, embed CPP1
   [If HORIZONTAL: concatenate files with _source_file tracking column]
2. Write and execute 02_structural-profile.py — shape, types, memory, schema
3. Write and execute 03_column-profile.py — per-column stats, value distributions
[If HIERARCHICAL:]
1. Write and execute 01_inventory.py — inventory all files, produce schema map, designate primary/auxiliary
2. For each file (suffix a, b, ...): write and execute 01{x}_load-and-format.py — per-file load/format
3. For each file: write and execute 02{x}_structural-profile.py
4. For each file: write and execute 03{x}_column-profile.py
Scripts go to: scripts/profile_structural/
Execute: bash {BASE_DIR}/scripts/run_with_capture.sh {project_script_dir}/profile_structural/{script}.py (or {script}.R for R)

**OUTPUT FORMAT:**
Return findings using the Data Ingest Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation (Part A):**
- CPP1 status and structural findings (rows, columns, memory, types)
- Potential identifiers (>95% unique) and categoricals (<50 unique)
- Coded value indicators (negative values or sentinels)
- Conditional Script Decisions for Parts B-D (Script 05, 06, 08, 11 — EXECUTE/SKIP with reason) """,
    subagent_type: "data-ingest"
})
```

#### Preliminary Notes Persistence: Part A

After the Part A data-ingest agent returns, the orchestrator persists the full return to disk:

| Agent Return | Write To |
|-------------|----------|
| data-ingest (Part A) | `{project_dir}/output/preliminary_notes/{date}_partA_structural-discovery.md` |

**Gate condition:** Part A preliminary notes must exist on disk before dispatching Part B data-ingest agent. The orchestrator confirms the file was written in Subagent Return Processing step 1 (see orchestrator SKILL.md).

### Part B: Statistical Deep Dive

**Purpose:** Execute scripts 04-06  |  **Stage:** DI-4, Part B  |  **Subagent:** data-ingest  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Part B: Statistical Deep Dive (scripts 04-06)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. Execute ONLY Part B work (scripts 04-06).
Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the file-first protocol.
Read `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints > CPP2 and copy
that block verbatim into the last executed Part B script; assign its config stanza in `# --- Config ---`.
It is the only maintained copy — do not write CPP code from memory.

**CONTEXT:**
- Profiling part: B
- Data file: {data_file_path} (primary file if multi-file)
- File format: {file_format}
- Canonical load pattern: {canonical_load_from_part_a}
- Prior part findings (orientation summary): {part_a_summary_brief}
- Prior part full preliminary notes:
  Read: {project_dir}/output/preliminary_notes/{date}_partA_structural-discovery.md
- Conditional script decisions: Script 05 [{EXECUTE/SKIP}], Script 06 [{EXECUTE/SKIP}]
- Target skill name: {skill_name}
- Domain context: {domain_context}
- Intended use: {intended_use}
- Data pull date: {data_pull_date}
- Project script dir: {project_script_dir}
- Priority columns: {priority_columns_or_none}
- File structure: {SINGLE_or_HORIZONTAL_or_HIERARCHICAL}
- Multi-file paths: {list_of_all_file_paths_or_none}
- Schema map: {file_to_entity_mapping_and_keys_or_none}

**TASK:**
[If SINGLE or HORIZONTAL:]
1. Write and execute 04_distribution-analysis.py — distributions, outliers, multimodality
2. If EXECUTE: 05_temporal-coverage.py — time gaps, trends, drift
3. If EXECUTE: 06_entity-coverage.py — coverage, ID validation
[If HIERARCHICAL — per-file with conditional scripts evaluated per file:]
1. For each file: write and execute 04{x}_distribution-analysis.py
2. For each file where applicable: 05{x}_temporal-coverage.py, 06{x}_entity-coverage.py
4. Embed CPP2 in last executed script
Scripts go to: scripts/profile_statistical/
Execute: bash {BASE_DIR}/scripts/run_with_capture.sh {project_script_dir}/profile_statistical/{script}.py (or {script}.R for R)

**OUTPUT FORMAT:**
Return findings using the Data Ingest Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation (Part B):**
- CPP2 status, distribution summaries, outlier findings
- Temporal coverage: [executed/skipped — key findings]
- Entity coverage: [executed/skipped — key findings] """,
    subagent_type: "data-ingest"
})
```

#### Preliminary Notes Persistence: Part B

After the Part B data-ingest agent returns, the orchestrator persists the full return:

| Agent Return | Write To |
|-------------|----------|
| data-ingest (Part B) | `{project_dir}/output/preliminary_notes/{date}_partB_statistical-deep-dive.md` |

**Gate condition:** Part B preliminary notes must exist on disk before dispatching Part C.

### Part C: Relational Analysis

**Purpose:** Execute scripts 07-09  |  **Stage:** DI-5, Part C  |  **Subagent:** data-ingest  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Part C: Relational Analysis (scripts 07-09, optionally 07b)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. Execute ONLY Part C work (scripts 07-09, + 07b if HIERARCHICAL).
Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the file-first protocol.
Read `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints > CPP3 and copy
that block — including its re-computation NOTE — verbatim into script 09; assign its config stanza in
`# --- Config ---`. It is the only maintained copy — do not write CPP code from memory.

**CONTEXT:**
- Profiling part: C
- Data file: {data_file_path} (primary file if multi-file)
- File format: {file_format}
- Canonical load pattern: {canonical_load_from_part_a}
- Prior part findings (orientation summary): {accumulated_brief_summary}
- Prior part full preliminary notes:
  Read: {project_dir}/output/preliminary_notes/{date}_partA_structural-discovery.md
  Read: {project_dir}/output/preliminary_notes/{date}_partB_statistical-deep-dive.md
- Conditional script decisions: Script 07b [{EXECUTE/SKIP}], Script 08 [{EXECUTE/SKIP}]
- Target skill name: {skill_name}
- Domain context: {domain_context}
- Intended use: {intended_use}
- Data pull date: {data_pull_date}
- Project script dir: {project_script_dir}
- Priority columns: {priority_columns_or_none}
- File structure: {SINGLE_or_HORIZONTAL_or_HIERARCHICAL}
- Multi-file paths: {list_of_all_file_paths_or_none}
- Schema map: {file_to_entity_mapping_and_keys_or_none}

**TASK:**
[If SINGLE or HORIZONTAL:]
1. Write and execute 07_key-integrity.py — uniqueness, composite keys, dependencies
2. If EXECUTE: 08_correlation-dependency.py — correlations, redundancy
3. Write and execute 09_quality-anomaly.py — completeness, coded values, anomaly catalog
[If HIERARCHICAL:]
1. For each file: write and execute 07{x}_key-integrity.py — per-file key analysis
2. Write and execute 07b_cross-level-linkage.py — cross-file key cardinality, coverage, orphans, join simulation, key type comparison
3. If EXECUTE per file: 08{x}_correlation-dependency.py
4. For each file: write and execute 09{x}_quality-anomaly.py
5. Embed CPP3 in last executed script
Scripts go to: scripts/profile_relational/
Execute: bash {BASE_DIR}/scripts/run_with_capture.sh {project_script_dir}/profile_relational/{script}.py (or {script}.R for R)

**OUTPUT FORMAT:**
Return findings using the Data Ingest Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation (Part C):**
- CPP3 status, recommended key, dependencies, high correlations
- Coded missing values found, anomaly catalog counts
- Cross-level linkage findings (if HIERARCHICAL) """,
    subagent_type: "data-ingest"
})
```

#### Preliminary Notes Persistence: Part C

After the Part C data-ingest agent returns, the orchestrator persists the full return:

| Agent Return | Write To |
|-------------|----------|
| data-ingest (Part C) | `{project_dir}/output/preliminary_notes/{date}_partC_relational-analysis.md` |

**Gate condition:** Part C preliminary notes must exist on disk before dispatching Part D.

### Part D: Interpretation & Reconciliation

**Purpose:** Execute scripts 10-11  |  **Stage:** DI-6, Part D  |  **Subagent:** data-ingest  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Part D: Interpretation & Reconciliation (scripts 10-11)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. Execute ONLY Part D work (scripts 10-11).
Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the file-first protocol.
Read `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints > CPP4 and copy
that block verbatim into the last executed Part D script; assign its config stanza in `# --- Config ---`.
Script 10 must build `data_dictionary_draft` as structured records (one per interpreted column, each
with `column` and `interpretation`) — CPP4 checks that object, not printed text.

**CONTEXT:**
- Profiling part: D
- Data file: {data_file_path} (primary file if multi-file)
- File format: {file_format}
- Canonical load pattern: {canonical_load_from_part_a}
- Prior part findings (orientation summary): {accumulated_brief_summary}
- Prior part full preliminary notes:
  Read: {project_dir}/output/preliminary_notes/{date}_partA_structural-discovery.md
  Read: {project_dir}/output/preliminary_notes/{date}_partB_statistical-deep-dive.md
  Read: {project_dir}/output/preliminary_notes/{date}_partC_relational-analysis.md
- Documentation files: {doc_file_paths_or_none}
- Conditional script decisions: Script 11 [{EXECUTE/SKIP}]
- Target skill name: {skill_name}
- Domain context: {domain_context}
- Intended use: {intended_use}
- Data pull date: {data_pull_date}
- Project script dir: {project_script_dir}
- Documentation website URL: {doc_url_or_none}
- Priority columns: {priority_columns_or_none}
- Access method: {local_file_or_api}
- File structure: {SINGLE_or_HORIZONTAL_or_HIERARCHICAL}
- Multi-file paths: {list_of_all_file_paths_or_none}
- Schema map: {file_to_entity_mapping_and_keys_or_none}
- Acquisition script path: {path_or_none} (if API-acquired — reference for provenance)

**TASK:**
[If SINGLE or HORIZONTAL:]
1. Write and execute 10_semantic-interpretation.py — ALL outputs marked [PRELIMINARY]
2. If EXECUTE: 11_reconcile-docs.py — verify docs against data
3. Embed CPP4 in the last executed script (script 11 if docs provided, otherwise script 10)
[If HIERARCHICAL:]
1. For each file: write and execute 10{x}_semantic-interpretation.py — per-file interpretations, ALL marked [PRELIMINARY]
2. In the last suffixed 10{x} script, also produce a cross-file schema map showing join topology
3. If EXECUTE: 11_reconcile-docs.py (once, cross-file) — verify docs against all files
4. Embed CPP4 in the last executed script
Scripts go to: scripts/profile_interpretation/
Execute: bash {BASE_DIR}/scripts/run_with_capture.sh {project_script_dir}/profile_interpretation/{script}.py (or {script}.R for R)

**ADDITIONAL PART D REQUIREMENTS:**

**Structured interpretation records (in script 10):** Build `data_dictionary_draft` as an
enumerable object — Python: a list of `{"column": ..., "interpretation": ...}` dicts; R: a
data.frame with `column` and `interpretation` character columns — one record per interpreted
column, every claim line carrying `[PRELIMINARY]` (or `[NO INTERPRETATION]`). Print it as well,
but CPP4 validates the object: zero records is a reportable absence, whereas zero regex matches
against printed text used to pass silently.

**Domain Decomposition (in script 10):** After semantic classification, group columns into
analytical domains (e.g., "outcome variables," "geographic identifiers," "temporal indicators,"
"covariates/controls," "survey design variables"). For each domain cluster with 5+ columns
OR with distinct methodology/limitations, note whether it warrants a dedicated reference file
in the skill. Include this domain decomposition in your return under "Domain Decomposition."

**Exclusion Extraction (in script 11, if docs provided):** When reading documentation, extract
all exclusion statements — phrases like "does not include," "excludes," "limited to," "only
covers," "not available for." Report these in a structured "Exclusions Identified" section in
your return, with source citation for each exclusion. Even without documentation, note any
apparent population boundaries observed during profiling (e.g., "data appears limited to
public institutions only" based on entity coverage in Part B).

**OUTPUT FORMAT:**
Return findings using the Data Ingest Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation (Part D):**
- CPP4 status, interpretation count, documentation reconciliation
- Full Preliminary Interpretations table (ALL columns — critical for PSU-DI2 user review)
- Domain Decomposition table
- Exclusions Identified table """,
    subagent_type: "data-ingest"
})
```

#### Preliminary Notes Persistence: Part D

After the Part D data-ingest agent returns, the orchestrator persists the full return:

| Agent Return | Write To |
|-------------|----------|
| data-ingest (Part D) | `{project_dir}/output/preliminary_notes/{date}_partD_interpretation-reconciliation.md` |

**Gate condition:** Part D preliminary notes must exist on disk before presenting PSU-DI2 to the user and before dispatching DI-7 (skill authoring). All four profiling preliminary notes (Parts A-D) must be on disk before DI-7 can proceed. In addition, the Pre-Authoring Research Offer (presented after PSU-DI2) must be resolved before DI-7 is dispatched: if the user accepted it, the research return must be persisted to preliminary notes first (see `WORKFLOW_PHASE_DO_AUTHORING.md` § Pre-Authoring Research (Optional)); if skipped, DI-7 proceeds directly.

### QA Invocation Template

Invoked after each profiling part completes. Orchestrator substitutes part-specific values.

```python
Agent({
    description: "QA Review: Part {A/B/C/D} — {Part Name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/code-reviewer.md`. This is a Data Onboarding QA review (not Full Pipeline) — there is no Plan.md. Use the context below for methodology alignment instead.

**SCRIPTS TO REVIEW:**
{list_of_script_paths_in_part}

**CPP RESULT:** {cpp_checkpoint_status_and_output}

**DATA ONBOARDING CONTEXT:**
Task name: QAP{N} review of {part_name} profiling scripts
Domain context: {domain_context}
Research question / Intended use: {intended_use}
Data file: {data_file_path}
File format: {file_format}
Data characteristics: {row_count} rows, {col_count} columns, {file_size}
Prior QA findings: {prior_qap_summary_or_none}
IAT compliance: Required per agent_reference/INLINE_AUDIT_TRAIL.md

**Note:** In Data Onboarding mode, profiling scripts produce embedded output (appended to script files via run_with_capture.sh), not separate data files. QA scripts should verify the appended execution log, not look for separate output files.

**QAP FOCUS AREAS (Part {A/B/C/D}):**
Read `agent_reference/QA_CHECKPOINTS.md` § Profiling QA Checkpoints (QAP1-QAP4) > QAP{N} for the
default checks, their `not_applicable` keys, and the per-check not-applicable versus
not-verifiable conditions. That table is canonical — use its keys verbatim.
Conditional-script outcomes for this part: {which_of_05_06_07b_08_11_ran_and_why}

**TASK:**
1. Review all executed scripts in Part {X} for correctness and completeness
2. Verify CPP{N} results are legitimate (not bypassed or incomplete)
3. Create QA scripts at: scripts/cr/profile_{part_dir}_cr1.py (+ cr2..cr5 as warranted)
4. Execute QA scripts and synthesize findings
5. Return QA report with severity classification

**OUTPUT FORMAT (3500-word hard cap):**
### QA Review: Part {X}
**Status:** [COMPLETED | ISSUES_FOUND]   <- agent status: did the review itself run to completion
**Severity:** [BLOCKER | WARNING | INFO | None]
**QAP{N} RESULT:** [PASSED | WARNING | BLOCKER]   <- the checkpoint verdict, transcribed from the QA script's `QAP{N} RESULT:` line
**Checks:** {passed} passed, {warnings} warnings, {blockers} blockers, {not_verified} not verified, {skipped} skipped, {info} info
**Scripts Reviewed / QA Scripts Created**
**Checks Performed:** [table]
**Issues Found:** BLOCKER / WARNING / INFO lists
**NOT VERIFIED escalation decisions:** one line per NOT VERIFIED check — the check key, the input that was missing, and whether it stays WARNING or is escalated to BLOCKER (with the reason)
**Recommendation:** [PROCEED | REVISION_REQUIRED | ESCALATE]

The `QAP{N} RESULT:` line and its `Checks:` count line are transcribed verbatim from the QA script's execution log, never asserted independently; the orchestrator copies both into STATE.md (`agent_reference/STATE_TEMPLATE_ONBOARDING.md` § Secondary Validation (QAP1-QAP4)). `Status` and `QAP{N} RESULT` are different fields: the first says whether the reviewer finished its job, the second is the checkpoint verdict.""",
    subagent_type: "code-reviewer"
})
```

### Revision Invocation Template

When a code-reviewer QAP review returns a BLOCKER, the orchestrator re-invokes the data-ingest agent to create a revised script. Use this template:

**Agent:** `subagent_type: "data-ingest"`

```
**BASE_DIR:** {BASE_DIR}

Read your agent protocol at `.claude/agents/data-ingest.md`.

**TASK:** Revise a failing profiling script based on QA BLOCKER findings.

**CONTEXT:**
- Profiling part: {A/B/C/D}
- Data file: {data_file_path}
- File format: {file_format}
- Target skill name: {skill_name}
- Project script dir: {project_script_dir}
- Canonical load pattern: {canonical_load_from_part_a}

**FAILING SCRIPT:**
- Script path: {failing_script_path}
- Script version: {original or _a/_b suffix}

**QA BLOCKER DETAILS:**
{code_reviewer_blocker_findings}

**REVISION INSTRUCTIONS:**
1. Read the failing script and its appended execution log
2. Read the code-reviewer's QA script and its findings
3. Create a NEW versioned script with suffix _a (or _b if _a exists): `{failing_script_name_without_ext}_a.py` (or `_a.R` for R)
4. Fix ONLY the issues identified in the BLOCKER findings
5. Preserve all IAT documentation from the original script
6. Execute via run_with_capture.sh
7. Verify the fix resolves the identified issues

**CONSTRAINTS:**
- Do NOT modify the original script (it is an immutable audit artifact with its execution log)
- Do NOT change the script's scope or add new functionality
- Maximum 2 revision attempts per script (_a, _b) before escalating to user
```

**Expected Output:** Same as standard part output, but focused on the revised script's status.

---

## Operational References

### Script-to-Skill-Template Mapping

| Script | Feeds SKILL.md Section(s) |
|--------|---------------------------|
| 01 load-and-format | Data Access (Example Fetch, load parameters) |
| 02 structural-profile | Summary, "What is [Source]?" |
| 03 column-profile | Quick Reference (Key Identifiers), Reference File Structure |
| 04 distribution-analysis | Quick Reference (distribution notes), Common Pitfalls |
| 05 temporal-coverage | "What is" (years, frequency), Common Pitfalls |
| 06 entity-coverage | "What is" (coverage scope), Decision Trees, Common Pitfalls |
| 07 key-integrity | Quick Reference (Key Identifiers), Data Access (join keys) |
| 08 correlation-dependency | Common Pitfalls (redundant columns), Decision Trees |
| 09 quality-anomaly | Value Encodings Warning, Quick Reference (Missing Data Codes), Common Pitfalls |
| 10 semantic-interpretation | Decision Trees, coded value tables |
| 11 reconcile-docs | Reference File Structure, data-quality.md |

### Profiling Script Template

**Python:**
```python
#!/usr/bin/env python3
"""
Script: {NN}_{name}.py
Part: {A/B/C/D} — {Part Name}
Project: {project_name}
Created: {YYYY-MM-DD}

Purpose: {brief description}
"""
import polars as pl

# --- Config ---
# INTENT: Central configuration for file paths and parameters
DATA_FILE = "{absolute_path_to_data_file}"
# ASSUMES: Canonical load pattern established by script 01

# --- Load ---
# INTENT: Load data using canonical pattern from script 01
# REASONING: Reuse exact load parameters to ensure consistency across scripts
df = pl.read_{format}(DATA_FILE, {canonical_params})
print(f"Loaded: {df.shape[0]} rows, {df.shape[1]} columns")

# --- Profile ---
# INTENT: {part-specific profiling purpose}
{profiling_logic}

# --- Validate ---
# INTENT: {CPP checkpoint if this is the last script in part}
{validation_code_if_applicable}

# --- Summary ---
# INTENT: Structured output for orchestrator consumption
print("=" * 60)
print(f"PART {part} PROFILING COMPLETE: {script_name}")
print("=" * 60)
{structured_summary_output}

# === EXECUTION LOG ===
# (Appended by run_with_capture.sh — do not edit below this line)
```

**R:**
```r
#!/usr/bin/env Rscript
# Script: {NN}_{name}.R
# Part: {A/B/C/D} — {Part Name}
# Project: {project_name}
# Created: {YYYY-MM-DD}
#
# Purpose: {brief description}

# --- Config ---
library(dplyr)
library(arrow)

# INTENT: Central configuration for file paths and parameters
DATA_FILE <- "{absolute_path_to_data_file}"
# ASSUMES: Canonical load pattern established by script 01

# --- Load ---
# INTENT: Load data using canonical pattern from script 01
# REASONING: Reuse exact load parameters to ensure consistency across scripts
df <- arrow::read_parquet(DATA_FILE)  # or readr::read_csv() per canonical pattern
cat(sprintf("Loaded: %d rows, %d columns\n", nrow(df), ncol(df)))

# --- Profile ---
# INTENT: {part-specific profiling purpose}
{profiling_logic}

# --- Validate ---
# INTENT: {CPP checkpoint if this is the last script in part}
{validation_code_if_applicable}

# --- Summary ---
# INTENT: Structured output for orchestrator consumption
cat(strrep("=", 60), "\n")
cat(sprintf("PART %s PROFILING COMPLETE: %s\n", part, script_name))
cat(strrep("=", 60), "\n")
{structured_summary_output}

# === EXECUTION LOG ===
# (Appended by run_with_capture.sh — do not edit below this line)
```

**Conventions:** Python: Polars only (never pandas). R: dplyr + arrow (tidyverse ecosystem). IAT comments (INTENT:, REASONING:, ASSUMES:) on every non-trivial operation. Section separators: Config, Load, Profile, Validate, Summary. No function definitions. Canonical load pattern from script 01 reused verbatim.

---

## Verification Checklists

#### Part A (Structural Discovery)

- [ ] Script 01 established canonical load pattern (format, encoding, params documented)
- [ ] CPP1 count line printed; verdict `PASSED` or `PASSED WITH WARNINGS`; 0 not verified (row count, column count, and null rate all carry their numbers on the check lines)
- [ ] Script 02 produced row/column counts, memory footprint, and complete type listing
- [ ] Script 03 produced per-column stats for every column (none missing)
- [ ] Conditional script decisions documented with Part A evidence
- [ ] All scripts saved to `scripts/profile_structural/` with execution logs
- [ ] QAP1 completed (code-reviewer invoked, QA script in `scripts/cr/`)

#### Part B (Statistical Deep Dive)

- [ ] Script 04 produced distribution classification for all numeric columns
- [ ] Script 05 executed or skipped with documented rationale
- [ ] Script 06 executed or skipped with documented rationale
- [ ] CPP2 count line printed; verdict `PASSED` or `PASSED WITH WARNINGS`; 0 not verified (mean-within-[min,max] and percentile monotonicity reported per numeric column; an empty `numeric_columns` is a NOT VERIFIED failure, not a pass)
- [ ] Outlier counts and thresholds documented per column
- [ ] All scripts saved to `scripts/profile_statistical/` with execution logs
- [ ] QAP2 completed

#### Part C (Relational Analysis)

- [ ] Script 07 tested single-column uniqueness for all columns
- [ ] Script 08 executed or skipped with documented rationale
- [ ] Script 09 produced anomaly catalog with severity classifications
- [ ] CPP3 count line printed; verdict `PASSED` or `PASSED WITH WARNINGS`; 0 not verified (correlation symmetry, per-key uniqueness agreement, non-empty catalog — a skipped script 08 declared in `not_applicable` with its reason, not left as a bare `None`)
- [ ] Coded missing value scan covered all standard sentinels
- [ ] Recommended primary key documented with uniqueness ratio
- [ ] All scripts saved to `scripts/profile_relational/` with execution logs
- [ ] QAP3 completed

#### Part D (Interpretation & Reconciliation)

- [ ] Script 10 marked ALL interpretations with `[PRELIMINARY]`
- [ ] Script 10 produced domain decomposition (columns grouped into analytical domains with reference file recommendations)
- [ ] Script 10 noted apparent population boundaries / exclusion observations
- [ ] Script 11 executed or skipped with documented rationale
- [ ] Script 11 extracted exclusion statements from documentation (if docs provided)
- [ ] Script 10 produced `data_dictionary_draft` as structured records (one per interpreted column), not printed text only
- [ ] CPP4 count line printed; verdict `PASSED` or `PASSED WITH WARNINGS`; 0 not verified (every claim line of every record hedged; reconciliation confirmed if docs provided)
- [ ] All scripts saved to `scripts/profile_interpretation/` with execution logs
- [ ] QAP4 completed
