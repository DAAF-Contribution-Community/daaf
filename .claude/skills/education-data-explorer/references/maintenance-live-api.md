# Maintenance: Live-API Catalog Surfaces & Regeneration Mechanics

> **MAINTENANCE SESSIONS ONLY — never load for analysis-time discovery.** Analysis uses the pinned mirror exclusively; the live API is current-Portal and drifts from the pinned vintage by construction. Nothing in this file is a routing fact for a research question — the routing files (`{schools,districts,colleges}-datasets.md`) and the generated `variable-dictionary-*.md` files are the only discovery surfaces. This file exists so a maintainer regenerating the mirror/dictionaries at a new vintage knows where the machine-readable ground truth lives, how the live API differs from the bulk mirror, and how to probe the API without hanging.

The Education Data Portal serves two things that diverge: a **live REST API** (current-Portal, moves quarterly) and **bulk downloads** (the source of the pinned HuggingFace parquet mirror). DAAF analysis reads the mirror. The live API is useful only at maintenance time — to re-derive the endpoint→file bridge and the variable dictionaries at a new Portal vintage, and to spot-check coded values. Because the API is always current and the mirror is frozen at vintage 0.26.1, the two are *expected* to disagree; the divergence classes below are structural, not bugs.

## The two machine-readable surfaces

Both are the correct regeneration source of truth — they are authoritative for the *current* Portal at the moment you pull them. Snapshot them (with the pull date) before deriving anything.

### `https://educationdata.urban.org/api/v1/api-endpoints/`

The endpoint catalog: one row per data route, with `endpoint_id`, `endpoint_url`, `section` (schools / school-districts / college-university), `source`, `topic`, `subtopic`, and **`years_available`** (the advertised coverage list). As of the 2026-08-07 audit this held **129 routes**, every one of which returned HTTP 200 at a mid-range year (the catalog is healthy and complete — no dead catalog routes). `years_available` is the advertised boundary; the 2026-08-07 boundary-year sweep confirmed 256/258 first/last-year probes returned non-zero counts, so the advertised boundaries are trustworthy modulo two flaky CRDC `retention` subgroup probes.

### `https://educationdata.urban.org/api/v1/api-endpoint-varlist/`

The variable metadata surface: **2,994 rows** (as of 2026-08-07), one row per (endpoint, variable), carrying `variable`, `label`, `is_filter`, `format`, `data_type`, `string_length`, `description`, and **`values`** (the Portal's authoritative coded-value string). Filter to one endpoint with `?endpoint_id=N` (e.g. `?endpoint_id=1` → the 96 rows of IPEDS directory). It **joins to `api-endpoints/` on `endpoint_id`**. All 129 catalog endpoints have varlist rows, and all 2,994 rows carry a `values` string — this is the fastest ground-truth refresh mechanism for variable names, filter flags, and coded values.

> **Format-tied caveat (load-bearing).** The `values` string is a **global per-`format` definition, not a per-source populated subset.** It defines the Portal's *global* code universe for a variable's format but cannot tell you which codes a specific source actually populates (e.g., CCD vs CRDC vs IPEDS `race`, or which sources emit `sex=9`). Per-source populated-subset claims require live-data GETs, not the metadata string alone. This is exactly why `variable-codes.md` carries curated per-source rows that the metadata surface cannot supply.

## The four API-vs-bulk divergence classes

When the live API and the bulk-derived mirror disagree, the disagreement falls into one of four classes. Examples below are evidence-true (probed 2026-08-07 / 2026-08-08); do not generalize past them.

### 1. Grain / packaging

The live API disaggregates by URL path segment; the mirror packs the same disaggregation into **columns**. One mirror file corresponds to *many* API disaggregation routes. In the API, `.../fall-enrollment/{year}/{level_of_study}/race/sex/` is a distinct route per dimension combination; in the mirror, `ipeds/colleges_ipeds_fall-enrollment-race_{year}` is one file whose `race`, `sex`, `level_of_study`, etc. are columns and each combination is a row. So an API **path segment maps to a mirror dimension column**. The regeneration bridge must collapse the many-routes-per-file relationship, not assume 1:1.

### 2. Coverage

The two serving surfaces (live API, bulk-download manifest) can list **different year sets or different objects**, and both can differ from what the mirror build actually produced. Real example: `ipeds/colleges_ipeds_completions-2digcip_2023` and `ipeds/colleges_ipeds_completions-6digcip_2023` exist as parquet files in the v2 mirror build but were **absent from the 2026-07-21 api-downloads manifest snapshot** (present-but-unbridged shards). Treat a mirror file with no matching bridge entry as real-but-unbridged rather than dropping it.

> **Correction — do NOT use the finance coverage example.** Older session notes cited "`ipeds/finance` API 1979-2017 vs mirror reaching 2021" as a coverage-divergence example. A 2026-08-08 probe of the pinned mirror parquet proved the finance content is exactly **1979, 1983-2017** — matching the API — so there is *no* post-2017 mirror overhang. That example is refuted; the completions-2023 shards above are the correct coverage-class illustration.

### 3. Representation

The same value can be encoded differently across surfaces. The live API **integer-rounds** some derived columns that the bulk/mirror files keep at full precision: CCD `teachers_fte` reads `28.0` from the live API vs `28.98` in the bulk/mirror file (observed 2026-08-07, mirror-maintenance fidelity battery; bulk CSV confirmed 28.98 — see /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_urban-fidelity/). Missing-value encoding also differs (null vs a coded sentinel like `-1`/`-2`/`-3`). A regeneration that cross-checks a mirror column against a live probe must expect rounding and missing-encoding drift, not treat it as a data error.

### 4. Vintage

The mirror is **pinned at Portal 0.26.1** (revision `0ad00ce0e232c96b0642459e4e7326607a8d26aa`); the live API is always current. On 2026-08-07 the API already served **2024** data for several sources — years that do not exist in the pinned mirror. This is the baseline reason analysis never reads the API: the pinned vintage is reproducible, the API is a moving target. Any "the API has newer data" observation is this class and is expected.

## Operational lessons for maintenance probing

Learned from the 2026-08-07 route/variable audits and the 2026-08-08 closure probes:

- **Use SIGALRM wall-clock timeouts, not socket timeouts.** A 20s socket timeout hangs indefinitely on a slow-**trickle** response (bytes arriving inside each read window keep the per-read timeout from ever firing) — two independent runs stalled at the identical endpoint. A hard `signal.SIGALRM` **wall-clock deadline (~25s) per request** bounds total request time regardless of socket activity and lets a sweep complete.
- **Pace at ~1 request/second, sequential, with retry + backoff.** The Portal is polite-pacing-friendly but not abuse-tolerant; the audits used ~1 req/sec and completed cleanly.
- **Use resumable checkpoints that exclude non-definitive verdicts.** Persist per-route results as you go so a re-run resumes, but do **not** checkpoint timeout/connection-error rows as final — leave them `pending` so a resume re-probes them rather than baking in a false negative.
- **Check for orphan probe processes before re-running a shared-file script.** A stalled prior run can hold a handle on the output parquet; confirm no leftover probe process is alive before relaunching a script that writes the same file.

## Regeneration procedure pointer

At the next mirror vintage, the endpoint→file bridge and the variable dictionaries are rebuilt from the two surfaces above by two file-first scripts:

- `/daaf/scripts/mirror_maintenance/53_endpoint-file-bridge.py` — rebuilds the endpoint→file bridge (collapsing the grain/packaging many-routes-per-file relationship from § class 1).
- `/daaf/scripts/mirror_maintenance/54_generate-variable-dictionaries.py` — regenerates the 14 `variable-dictionary-{source}.md` files from `api-endpoint-varlist/`.

After both run against the new vintage, the routing files (`{schools,districts,colleges}-datasets.md`) are **re-verified against the new bridge** — year ranges, grain, and key-variable names are checked against the regenerated dictionaries, and any coverage-class (§ class 2) unbridged shards are reconciled.

## Known open item

**EDFacts assessments `race` codes are metadata-declared, not live-confirmed.** The set `{1-9, 20, 99}` for EDFacts assessment race comes from the Portal `values` metadata string only — live confirmation is still open. The 2026-08-07 audit's candidate GETs missed the populated slice (wrong `grade_edfacts` guesses returned count 0), and 2026-08-08 closure probes hit **systematic HTTP 500** (an Urban Portal outage, not a code error). A 2026-08-09 re-probe (`56_race-edfacts-reprobe.py`) again returned systematic HTTP 500 on all three attempted slices, so the outage now persists across two sessions; the next re-probe is recommended on a longer cadence. When the Portal recovers, re-run the `55_race-edfacts-closure-probe_a.py` logic in **≤2 requests** (correct `grade_edfacts` value, one populated year) to confirm the populated race subset, then fold the result into `variable-codes.md` (which currently flags this set as metadata-declared).
