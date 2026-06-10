# Benchmark Results Viewer — Redesign Plan

**Date:** 2026-06-10
**Target:** `benchmarks/scripts/generate_results_viewer.py` (and its output, `viewer.html`)
**Status:** APPROVED at Checkpoint 1 (2026-06-10) — decisions recorded in § 11
**Status (final, 2026-06-10):** COMPLETE — v2 shipped (`generate_results_viewer_v2.py`
v2.3.0 + `scripts/viewer_template.html`, committed through `8f61fc1`; v1 generator
retained as archival code, the old `viewer.html` artifact deleted). This document is
the design record plus the accepted residuals (§ 12); it describes no in-progress work.

---

## 1. Goal and Design Principles

Transform the viewer from an analyst's dashboard into a **standalone, self-explanatory
document** that serves two audiences in one file:

- **The casual reader** who opens `viewer.html` cold: within 30 seconds they should
  know what was tested, how, who performed best, and what the caveats are — without
  clicking anything.
- **The analyst** who needs criterion-level heatmaps, per-rep consistency, cost
  detail, and full transcript drill-down — available below the fold and behind
  progressive disclosure, never gating the summary.

Design principles (grounded in the UX research, § 3.2):

1. **Overview first, zoom and filter, details on demand** (Shneiderman). The document
   reads top-to-bottom in inverted-pyramid order; nothing important hides in a tab.
2. **Every chart states its finding, not its axes.** Chart titles and callout
   annotations carry the conclusion ("`prompt_has_context_section` is the weakest
   criterion across all models"), computed from the data at render time.
3. **Prose adjacency.** Every section opens with 1–3 sentences of "how to read this"
   (the Epoch AI pattern). A collapsible methodology primer sits near the top.
4. **Honest uncertainty.** Visible denominators everywhere (`21/24`, not just `88%`);
   tier bands instead of false-precision #1–#17 rankings; uneven rep counts flagged.
5. **Accessible encoding.** Colorblind-safe status palette with glyph redundancy
   (✓ / ✗ / partial glyph), ≥3:1 contrast on the dark surface, never color alone.
6. **Self-contained forever.** Single file, zero external dependencies, works from
   `file://` in Chrome and Firefox. All current escaping safeguards retained.

---

## 2. Current State Assessment

What exists (generator v1.0.0, 2,238 lines, single Python f-string template):

| Component | Verdict |
|-----------|---------|
| Data pipeline (load → normalize tiers → condense transcripts → embed JSON) | **Sound.** Keep; extend. |
| Tier normalization (P1 from `hard_requirements`, P2/3 from explicit `tier`) | Keep as-is. |
| Transcript condensation + HTML5 tokenizer escaping + `file://` hash handling | Keep as-is (hard-won fixes). |
| 5-tab IA (Overview / Models / Cases / Costs / Logs) | **Replace.** Tabs hide content from casual readers (Baymard/NN/g evidence). |
| Scorecard row (one card per model) | **Replace.** Sprawls at 17 models. |
| Phase Summary table (17 models × 3 sub-columns = 51 columns) | **Replace.** Unreadable. |
| Grouped bar chart (3 bars × 17 models × 4 groups ≈ 200 bars) | **Replace.** Grouped bars fail at this cardinality. |
| Cases view (rep × criterion × model checkmark matrix per case) | **Restructure.** Valuable data, overwhelming presentation. |
| Costs view (pricing table + scatter) | **Keep core, improve** (frontier annotation, log-x option). |
| Logs view (run list + detail with criteria, transcripts, subagent transcripts) | **Keep largely as-is** — strongest existing view; relocate as final section. |
| Red/green status colors, color-only checkmarks | **Replace** with accessible palette + glyphs. |
| No explanatory content anywhere | **Add** README-style layer (§ 4.2). |
| Global filter bar driving all views | **Replace** with per-section controls (§ 4.9). |

Known doc/code mismatch to fix while here: README § 8 says default output is
`benchmarks/viewer.html`, but `resolve_paths()` auto-generates dated
`viewer_YYYY-MM-DD{a}.html` names when `--output` is absent.

---

## 3. Grounding Findings

### 3.1 Data realities (from results inventory, 2026-06-10)

Scale: **1,728 on-disk runs** across 42 result sets — P1: 750 runs / 15 cases / 4
criteria; P2: 450 / 9 / 1–2; P3: 528 / 12 / 10 dispatch + 5–6 subagent criteria
(16 distinct subagent criterion names; applicability varies by case subcategory).
17 models, max 3 reps per (phase, model, case) cell.

Constraints the redesign must honor:

1. **Run-level data is ground truth.** `summary.json` run counts disagree with
   on-disk run dirs in 9 of 42 sets (67 phantom runs). All viewer aggregates must
   come from loaded `result.json` files; summary totals used only for provenance.
2. **Timeouts are graded.** Every on-disk `error` string is a timeout
   (`"Timed out after {120|180|300}s"`); such runs have zeroed turns/cost/tokens but
   **fully graded criteria** (e.g., a timed-out run with 10/10 passes). The current
   `runStatus()` maps these to "errored," which both hides valid grades and pollutes
   cost/duration averages. New taxonomy: grade status (perfect / partial / failed /
   ungraded) **orthogonal to** a `timed_out` flag (field exists in all result.json;
   stop string-matching `error`).
3. **Uneven denominators.** 84 of 204 P3 cells have 2 reps, not 3; Fable 5 and the
   Anthropic flagships have fewer P3 runs. Every rate display needs its n.
4. **Unused fields worth surfacing:** `timed_out`, `expected_mode` (P1),
   `subcategory` (P2/3), criterion `detail` strings (consistently human-useful —
   e.g., `"Found Agent(research-executor)."`), `tool_failures[].content`,
   `manifest.daaf_git_sha` + `manifest.config` (reps/parallelism/timeout per set),
   `summary.by_case` (free case-difficulty data).
5. **`reasoning_cost_multiplier` is not in any result.json** — the generator's
   default-1.0 fallback is currently dead weight; keep the badge logic but read it
   defensively.
6. Criteria shape inconsistency across phases is already normalized — preserve that
   code path untouched.

### 3.2 UX research (web survey, 2026-06-10)

- **Tabs are the root IA problem** — users reliably miss non-default tabs; long
  scrolling page + sticky scrollspy TOC is the evidence-backed pattern.
- **Leaderboard conventions:** rank-ordered (never alphabetical in performance
  views), tier bands over strict ranks when reps are few (LMArena CI critique),
  composite score up front with per-axis winners named, methodology one click away
  (Artificial Analysis), chart + adjacent prose unit (Epoch AI).
- **Chart types:** rank-ordered horizontal bars for 17-model comparison; discrete
  (not continuous-ramp) heatmap for model × criterion; annotated scatter with
  efficiency frontier for cost-vs-performance; k-of-n agreement heatmap for rep
  consistency. Grouped bars at 17-model cardinality are explicitly an anti-pattern.
- **Color:** Wong-palette derivatives on dark — pass = light teal/blue-green, fail =
  vermillion/orange, partial = yellow, all separated in lightness as well as hue;
  glyph redundancy mandatory; ≥3:1 non-text contrast (WCAG 1.4.11).

---

## 4. Target Information Architecture

Single scrolling document. Fixed left rail: slim TOC with scrollspy highlighting
(IntersectionObserver), anchor deep-links per section, "back to top" affordance.
Hash state preserved for deep links (existing `file://`-safe mechanism).

Sections in order:

### 4.1 Hero / Headline Verdict
Title, generation timestamp, and a computed verdict block (2–3 sentences + stat
chips): N models, N runs, N phases, total spend; top tier members; the single most
notable finding (weakest universal criterion). All numbers computed from loaded
runs at render time — never hand-written.

### 4.2 About This Benchmark (the README-style layer)
One visible intro paragraph: *what this is* (behavioral conformance to DAAF
orchestrator protocols — does the model follow the framework, not is it smart) and
*what it is not* (answer quality, analytical capability). Then collapsible
`<details>` subsections (native HTML, zero-JS):

- **The three phases** — plain-language table: what each phase starts from and tests
  (cold-start classification; post-confirmation loading; dispatch compliance + the
  3b subagent-behavior sub-scoring).
- **How scoring works** — criteria, hard vs. soft tiers, and the Perfect vs.
  Hard/Soft rate distinction with the worked example from README § 6 (4 runs each
  failing one soft criterion → 67% Perfect, 100% Hard, 96% Soft).
- **How runs were executed** — real DAAF container, `claude -p` CLI, hooks live,
  reps, golden checkpoints in two sentences.
- **Reading caveats** — timeouts still graded; uneven rep counts; OpenRouter token
  counts approximate; deterministic scorers have known false negatives
  (`prompt_has_context_section`); encrypted Fable thinking blocks.

Content adapted from `benchmarks/README.md` §§ 1, 2, 5–7, 11 into plain language;
static prose in the template with dynamically inserted counts where cheap.

### 4.3 Leaderboard (replaces scorecards + 51-column table)
One **rank-ordered horizontal table-chart**, one row per model:
tier band (A/B/C grouping rendered as background bands with gap-based breaks),
model + provider chip, **composite bar** (mean of per-phase Perfect rates, equal
weight, with components shown), per-phase mini-cells (P1 / P2 / P3a / P3b Perfect
rate with n), dispatch reliability (P3 `agent_dispatched` rate), consistency
(k-of-n reps all-pass, the pass^k idea), avg cost/run. Sort control (composite |
any phase | cost | consistency); default composite. Each per-phase cell deep-links
to that model's rows in the phase deep-dive. Models with incomplete phase coverage
get a visible "partial data" marker rather than silent exclusion.

Composite definition is a judgment call — see Open Question 1.

### 4.4 Cost vs. Performance
Scatter (x = avg computed cost/run on log scale, y = composite Perfect rate), all
17 points labeled, efficiency frontier polyline annotated ("best value" region),
timeout-zeroed runs excluded from cost averages with a footnote. Adjacent prose
notes the OpenRouter approximation caveat.

### 4.5 Phase Deep-Dives (one subsection per phase, replaces Models tab)
Per phase: a 2-sentence explainer, then a **discrete model × criterion heatmap** —
rows = models sorted by phase score, columns = criteria grouped hard-then-soft with
tier markers, cells = pass rate rendered as discrete steps (0, 1–49, 50–89, 90–99,
100%) with the exact k/n in tooltip and click-through to matching runs in the Run
Explorer. A computed callout names the weakest criterion and the per-phase winner.
Phase 3 renders dispatch (3a) and subagent (3b) heatmaps side by side; 3b cells
show "—" where a criterion doesn't apply to a case subcategory (varying
denominators made explicit).

### 4.6 Cases and Consistency (restructured Cases tab)
Two layers:
1. **Agreement heatmap:** case × model grid, cell = reps-perfect out of reps-run
   (4-step discrete scale 0/3→3/3), revealing flaky cases and flaky models at a
   glance. Case rows carry subcategory chips; `summary.by_case`-style difficulty
   (cross-model pass rate) shown as a row margin.
2. **Case browser:** collapsible per-case panels — full prompt (they're short),
   expected behavior from case metadata (`expected.*`, hard/soft requirement
   lists), and the current per-rep checkmark matrix scoped to one case at a time
   (where it works fine).

### 4.7 Costs Detail
Current pricing table (kept, with sort) + per-model observed spend: avg/total
cost, token composition (input/output/cache-read shares), reasoning-multiplier
badge when present. Timeout-zeroed runs excluded from averages, count disclosed.

### 4.8 Run Explorer (relocated Logs tab)
Largely unchanged mechanics (list + detail panel) with upgrades: status dots use
the new taxonomy (grade + timeout flag as a distinct marker); criterion `detail`
strings shown by default (they're good diagnostics); `tool_failures[].content`
rendered in detail view; section-local filters (phase, model, case, status,
search) replacing the global filter bar. Every deep-link target from §§ 4.3–4.6
lands here with filters pre-applied.

### 4.9 Provenance Footer
Per-result-set table from `manifest.json` (never previously read): timestamp, DAAF
git SHA, run config (reps, parallel/sequential, delays, timeout), runs on disk vs.
summary count (discrepancies shown, not hidden), generator version. Plus an AI
disclosure line (document generated by DAAF tooling).

**Global filter bar: removed.** Document sections own their controls; global
filters made sense for a dashboard, not a narrative document. Hash deep-links keep
cross-section navigation working.

---

## 5. Visual Design System

- **Theme:** keep dark (it's the established identity; transcripts read well on it).
  Slightly larger base type for prose sections; clear typographic hierarchy
  (prose 14px, data 12px, captions 11px).
- **Status palette (replaces red/green):**
  - Pass: teal-green `#34d399` family (light enough for dark bg)
  - Fail: vermillion `#fb7185`/`#f87171` family — paired with lightness separation
  - Partial: yellow `#fbbf24`
  - Ungraded/no-data: neutral slate `#64748b`
  - Timeout marker: distinct outline/clock glyph, not a color of its own
  - All status conveyed as color + glyph (✓ ✗ ◐ —) + tooltip text; greyscale-tested.
- **Rate scale (heatmaps):** 5 discrete steps on a single hue ramp with lightness
  spread, not a continuous red→green ramp.
- **Model identity colors:** keep per-model hues for the scatter and leaderboard
  accents, but expand the palette to 17 distinguishable values and stop relying on
  hue alone for identification (always label points/rows).
- **Charts:** inline SVG, no libraries (unchanged constraint). Each chart gets:
  finding-as-title, axis captions, and a legend.

---

## 6. Data Layer Changes (generator Python)

1. Read `manifest.json` per result set → provenance table + git SHA grouping.
2. Carry through new fields: `timed_out`, `expected_mode`, `subcategory`,
   `tool_call_count`, criterion `detail` (already loaded, now surfaced), full
   `tool_failures`.
3. New derived metrics computed in Python and embedded (keeping JS lean):
   per-model per-phase aggregates (perfect/hard/soft with n), composite score,
   consistency (k-of-n cells), per-case difficulty, weakest-criterion callouts,
   efficiency frontier points. JS still computes section-local filtered views from
   the runs array, but headline numbers come precomputed so prose and charts can't
   drift apart.
4. Status taxonomy: `grade` (perfect/partial/failed/ungraded) computed per run +
   `timed_out` flag; drop string-matching on `error`.
5. Cost/duration averages computed excluding zeroed timeout runs; excluded counts
   recorded for footnotes.
6. Default-output mismatch resolved as a documentation fix: the dated
   auto-incrementing filenames are intentional and retained; README § 8 will be
   corrected to describe them (decision 4).

Unchanged: transcript condensation, tier enrichment, rep renumbering, JSON
escaping, `--results`/`--output` CLI.

## 7. Implementation Architecture

**New script, not a rewrite-in-place (user decision, archival).** The existing
`generate_results_viewer.py` is preserved untouched as the v1 historical artifact.
Work proceeds in a copy: `benchmarks/scripts/generate_results_viewer_v2.py`, which
becomes the maintained generator going forward.

**Extract the template.** Move HTML/CSS/JS out of the Python f-string into
`benchmarks/scripts/viewer_template.html` with two placeholders
(`/*__DATA_JSON__*/`, `/*__PRECOMPUTED_JSON__*/` — plus small ones for generated
prose snippets). The generator becomes data-prep + placeholder substitution.

Why: the f-string forces `{{ }}` escaping throughout 1,400 lines of CSS/JS (a
constant source of subtle bugs), prevents editor syntax support, and makes
review diffs noisy. A sibling template file keeps the output single-file and
self-contained while making both halves maintainable. The generator stays the
single entry point; no build step.

JS remains vanilla, IIFE-wrapped, ES5-compatible style as now. CSS organized by
section with the design tokens (§ 5) as custom properties.

## 8. Work Packages and Sequencing

| WP | Scope | Depends on |
|----|-------|-----------|
| WP1 | Copy v1 → `generate_results_viewer_v2.py`; template extraction (mechanical port, equivalent-output sanity check vs v1) | — |
| WP2 | Data layer: manifest loading, new fields, derived-metrics block, status taxonomy | WP1 |
| WP3 | Document IA: TOC rail + scrollspy, section skeleton, hero verdict, About content, provenance footer; remove global filter bar | WP1 (WP2 for verdict numbers) |
| WP4 | Leaderboard + cost/performance scatter (with frontier) | WP2, WP3 |
| WP5 | Phase deep-dive heatmaps (incl. 3a/3b) + callouts | WP2, WP3 |
| WP6 | Cases & consistency (agreement heatmap + case browser) | WP2, WP3 |
| WP7 | Run Explorer upgrades + section-local filters + deep-link wiring from all sections | WP3–WP6 |
| WP8 | Design-system polish pass (palette, glyphs, contrast audit), regeneration of `viewer.html`, cross-browser `file://` checks, README § 8 update | all |

Each WP ends with a regeneration against a small fixed `--results` subset and a
full-corpus generation (file-size + console-error check). WPs 4–6 are
parallelizable in principle; sequential execution recommended for review sanity.

## 9. Verification Plan

- **Structural:** regenerate on (a) 2-set subset, (b) all 42 sets; assert no Python
  errors, valid JSON embed, file size reported; grep output for unescaped `<` in
  the data block.
- **Behavioral:** headless checks where possible (e.g., `python3 -c` DOM-less lint,
  node-free); since the container has no browser, **final visual verification is a
  user step** — I'll provide a short checklist (TOC scrollspy, deep-links from
  leaderboard → run explorer, `<details>` toggles, tooltips, Chrome `file://` hash
  behavior).
- **Numbers audit:** spot-check leaderboard figures against README § 10 snapshot
  values (allowing for rep-count differences), and on-disk recounts via jq.
- **Accessibility:** programmatic contrast-ratio check of the palette tokens;
  greyscale screenshot review (user step).

## 10. Out of Scope (this effort)

- Statistical aggregation (Beta-Binomial credible intervals) — Design Backlog item;
  the leaderboard's tier-band presentation is designed so intervals can slot in
  later without IA change.
- New scorers, rescoring, or new benchmark runs (separate priorities #2–#3).
- Light theme / print stylesheet (could be a fast follow if wanted).
- Live-server features (search indexing, URL routing beyond hash).

## 11. Resolved Decisions (Checkpoint 1, 2026-06-10)

1. **Composite score:** unweighted mean of per-phase Perfect rates (P1, P2, P3a,
   P3b as four equal components), always shown with its components.
2. **Tier bands:** derived mechanically from gaps in composite score (reproducible
   rule, documented in code).
3. **Default result-set scope:** all result sets embedded by default; size
   expectation documented.
4. **Default output filename:** dated auto-incrementing names (`viewer_YYYY-MM-DD{a}.html`)
   are intentional and retained; README § 8 updated to match the code.
5. **About layer:** plain-language, DAAF-aware tone, ~600–900 words across the
   collapsibles — approved.
6. **Archival approach (user-added):** do not rewrite `generate_results_viewer.py`
   in place — copy to `generate_results_viewer_v2.py` and evolve the copy; v1 and
   existing `viewer.html` remain untouched as historical artifacts. (Superseding
   note: `viewer.html` itself was later deleted at Checkpoint 2 housekeeping, user
   decision; the v1 *script* remains archival.)

## 12. Accepted Residuals (ported from session notes, 2026-06-10)

Recorded at Checkpoint 2 (Session 3) as design imperfections reviewed and
**accepted as-is** — no fix planned. They originated in the review-fix handoff
document (`REVIEW_FIX_HANDOFF.md`, deleted at Checkpoint 2 housekeeping) and were
preserved in the working-session log; ported here verbatim-in-substance when that
log was retired (2026-06-10).

1. **`konStep` "most" label at 2 reps.** The discrete k-of-n agreement scale
   (`konStep`, used by the case × model agreement heatmaps, § 4.6) labels 1-of-2
   reps as "most" — a labeling quirk at the smallest denominators, where 1/2
   falls into the "most reps agree" band. Exact k/n remains visible in the cell
   data, so no information is lost.
2. **Fixed "#" rank column on the leaderboard.** The leaderboard keeps a fixed
   "#" rank column, despite the design principle (§ 1, item 4) of preferring tier
   bands over false-precision #1–#17 rankings. Adjacent prose disclaims the
   precision of the strict ordering.
3. **P3b denominator subtlety.** Phase 3b (subagent-behavior) criterion
   applicability varies by case subcategory (§ 3.1), so P3b heatmap cells carry
   varying denominators. Policy accepted as-is; the cell tooltip showing the
   exact k/n mitigates misreading.
4. **`print_summary` echoes summary.json totals.** The generator's console
   `print_summary` output echoes `summary.json` totals without the
   disk-vs-summary discrepancy caveat that the rendered provenance section
   carries (run-level `result.json` data is ground truth; summary counts
   disagree with on-disk runs in some sets — § 3.1, constraint 1).
5. **Provenance git SHA is per-set display only.** The DAAF git SHA from each
   `manifest.json` is displayed per result set in the provenance footer; there
   is no cross-set SHA grouping or comparison.
