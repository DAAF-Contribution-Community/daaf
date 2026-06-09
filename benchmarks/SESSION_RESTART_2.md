# Benchmark System Session Restart (Sessions 2 + 3)

**Date:** 2026-06-09
**Mode:** Framework Development
**Workspace:** /daaf/benchmarks
**Previous Session:** SESSION_RESTART.md (read it first for full context)

---

## What Was Accomplished (Session 2)

### Viewer Code Changes (ALL WORKING)

Four changes to `scripts/generate_results_viewer.py`:

1. **Overflow scroll (CSS):** Added `overflow-x:auto` to `.card` class. Fixes horizontal overflow on Overview phase summary, Models heatmap, and Cases tables.

2. **Costs table — Perfect Rate + sortable headers:** Added `perfectByModel` computation, `costTh()` local function with sort arrows, `costRows` data array with `costRows.sort()`, and `window.sortCosts` event handler. State extended with `costSortCol`/`costSortDir`.

3. **Cases view — complete restructure:** Replaced `renderCases`. Now groups by eval phase (Phase 1, Phase 2, Phase 3a, Phase 3b) instead of subcategory. Natural numeric sort on case IDs. Each case shows all (rep, criterion) detail rows by default — no expand/collapse. Models as columns, criteria as rows. Every cell is clickable via `jumpToRun()`.

4. **Chrome file:// fix:** `updateHash()` detects `file://` protocol and uses `location.hash` directly instead of `history.replaceState`.

---

## What Was Accomplished (Session 3)

### Bug Fix: Subagent transcript content broke browser rendering (RESOLVED)

See detailed root cause analysis below.

### Bug Fix: Phase 3b filter did not update Model Scorecards

Scorecard computation used `r.criteria` directly, ignoring the phase filter. Fixed to use `getRunCriteria(r, activeGroup)` and `groupAllPassed(r, activeGroup)` when a phase filter is active.

### Bug Fix: Cases tab Phase 3b showed too many X's

When a criterion didn't exist in a run's criteria dict (e.g., subagent criteria for a run not evaluated on them), `critData` was `undefined`, causing `passed` to be falsy and rendering an X. Fixed to show `—` (dash) when `critData` is undefined.

### Bug Fix: jumpToRun didn't navigate to specific transcript

`render()` unconditionally reset `state.selectedRunIdx = -1`, clobbering the index that `jumpToRun()` had just set. Removed the reset from `render()` — the nav click handler already resets it when switching tabs.

### Bug Fix: Costs table and scatter plot metrics disagreed

Two issues: (1) Costs table "Perfect Rate" used `allCriteriaPassed(r)` which always checked dispatch criteria regardless of phase filter. Fixed to use `groupAllPassed(r, activeGroup)` when filtered. (2) Scatter plot computed a per-criterion pass rate (passed criteria / total criteria) while the table showed per-run perfect rate. Fixed scatter to use the same `perfectByModel` rates as the table.

### Enhancement: Grouped bar chart redesigned

- Bars now use model colors (was: three indigo shades repeating)
- Perfect = solid fill, Hard = diagonal hatching, Soft = translucent fill
- More spacing between model clusters
- 45-degree rotated model name labels beneath each cluster (replaces color legend)
- Tier texture legend in top-right corner

### Enhancement: Scatter plot improved

- Larger chart (780x460, was 560x340)
- Smaller dots (radius 5, was 8)
- Major and minor gridlines
- Rich hover tooltips showing pass rate, input/output/cache-read costs per 1M tokens

### Cleanup

- Deleted 34 debug viewer files (a-d, f-w, all viewer_test_*.html)
- Remaining: `viewer_2026-06-09e.html` (session 1 reference), `viewer_2026-06-09g.html` (latest)

---

## RESOLVED BUG: Subagent Transcript Content Broke Browser Rendering

### Root Cause (Session 3)

**HTML5 parser state machine triggers in embedded transcript content.** Subagent transcripts contained `<!--` (69 occurrences), `<script` (24 occurrences), and `<!` (77 occurrences) as literal text within JSON string values embedded in a `<script>` block. The HTML5 tokenizer interprets these sequences as state transitions — `<!--` enters "script data escaped" state, `<script` triggers "double-escaped" state — creating chaotic parser behavior that prevented the browser from determining where the `<script>` block ends.

The previous fix (`data_json.replace("</", r"<\/")`) only caught end-tag patterns. `<!--` and `<script` are NOT end tags but still trigger parser state changes.

**Key evidence:** The working file (200-char truncation) had 0 `<script` patterns; the failing file had 24. All 24 appeared past character 200 in transcript strings.

### Fix Applied

One-line change in `generate_html()`:
```python
data_json = data_json.replace("<", "\\u003c")
```
Replaces ALL `<` with `\u003c` in the JSON data section. The HTML parser sees only safe ASCII (`\`, `u`, `0`, `0`, `3`, `c`), while the JS engine interprets `\u003c` as `<` when parsing string values. Subsumes the old `</` → `<\/` replacement.

Also reverted `ensure_ascii=True` back to `False` (it was never the fix; `<` is ASCII so `ensure_ascii` doesn't touch it). Kept C1 control character stripping as hygiene.

### Current Code State

The generator at `scripts/generate_results_viewer.py` currently has:
- `ensure_ascii=False` in `json.dumps` (correct — UTF-8 is fine, saves ~300KB)
- `data_json.replace("<", "\\u003c")` for HTML5 parser safety (replaces old `</` → `<\/`)
- `_strip_nonprintable()` function in `_truncate_content` and tool output/args paths
- C1 control character strip (U+007F-U+009F) as hygiene
- `isFileProto` detection for Chrome file:// compatibility
- Subagent transcript messages at full length (cap was reverted)

**To produce a working viewer right now:** Either cap subagent transcript strings to 200 chars (the workaround in viewer_2026-06-09u.html), or exclude subagent transcripts entirely.

---

## Architecture Decisions (New This Session)

### 32. Card overflow-x for wide tables
Added `overflow-x:auto` to `.card` CSS — simplest fix covering all three affected views since all tables are wrapped in `.card` divs.

### 33. Costs table sortable with costTh pattern
Local `costTh()` function inside `renderCosts` renders `<th>` with onclick + sort arrows. State tracks `costSortCol`/`costSortDir` separately from the general sort state. Model rows built as `costRows` array, sorted before rendering.

### 34. Cases view phase-grouped with click-to-jump
Complete renderCases rewrite. Uses existing `getEvalGroups()`, `runInGroup()`, `getRunCriteria()` infrastructure. Natural numeric sort via inline `caseSort()`. Every ✓/✗ cell calls existing `jumpToRun()`. Rep labels use `rowspan` for visual grouping.

### 35. file:// protocol detection for hash state
`var isFileProto=(location.protocol==="file:");` — skip `history.replaceState` entirely on file:// URLs, use `location.hash` assignment directly.

### 36. HTML5 script tokenizer requires escaping all `<` in embedded data
Phase 3 subagent transcripts contain `<!--` (69 occurrences) and `<script` (24 occurrences) as literal text. These trigger HTML5 parser state transitions ("script data escaped" and "double-escaped" states) that cause the browser to lose track of where the `<script>` block ends. Fix: `data_json.replace("<", "\\u003c")` — escapes all `<` to `\u003c` which the HTML parser ignores but the JS engine interprets correctly. Subsumes the old `</` → `<\/` replacement.

### 37. Scorecard and table metrics must be phase-aware
When a phase filter is active, all rate computations (scorecards, costs table, scatter plot) must use `getRunCriteria(run, group)` and `groupAllPassed(run, group)` instead of raw `r.criteria` / `allCriteriaPassed(r)`. The eval group determines whether to read `run.criteria` (dispatch) or `run.subagent_criteria` (subagent).

### 38. Perfect vs Hard/Soft rate semantics
Perfect = per-run (did ALL criteria pass for this run?). Hard/Soft = per-criterion (across all runs, what fraction of hard/soft criteria passed?). These are intentionally different metrics and can diverge significantly — e.g., 67% Perfect with 100% Hard and 96% Soft when 4 runs each fail one soft criterion.

### 39. Cases table: undefined criteria → dash, not X
When a criterion doesn't exist in a run's criteria dict, render `—` not `✗`. This happens for subagent criteria on runs that weren't evaluated, or dispatch criteria that some result sets don't include.

---

## Result Sets on Disk

(Same as SESSION_RESTART.md plus new Phase 3 sets)

| Result Set | Phase | Models | Notes |
|-----------|-------|--------|-------|
| `20260609_003629` | Phase 3 | GLM, Kimi, Qwen, Gemma 31B/26B | 58% errored |
| `20260609_004353` | Phase 3 | DS Pro/Flash, Gemini Pro, Nemotron, Flash Lite | 30% errored |
| `20260609_005021` | Phase 3 | Haiku, Opus 4.5, Sonnet | 14% errored |
| `20260609_005920` | Phase 3 | GLM, Kimi, Qwen, Gemma 31B/26B | 55% errored |
| `20260609_010631` | Phase 3 | DS Pro/Flash, Gemini Pro, Nemotron, Flash Lite | 42% errored |

Ghost result sets (20260608_231509, 20260608_232158) still present.

Additional Phase 3 result sets from Session 3:

| Result Set | Phase | Models | Notes |
|-----------|-------|--------|-------|
| `20260609_011346` | Phase 3 | GLM, Kimi, Qwen, Gemma 31B/26B | 47% errored |
| `20260609_012055` | Phase 3 | DS Pro/Flash, Gemini Pro, Nemotron, Flash Lite | 42% errored |

---

### Viewer Files on Disk

- `viewer.html` — default/main viewer
- `viewer_2026-06-08*.html` (a-f) — session 1 versions
- `viewer_2026-06-09e.html` — last working version from session 1
- `viewer_2026-06-09g.html` — latest version (session 3, all fixes + enhancements)

---

## Restart Prompt

> Launch framework development mode. We're continuing work on the DAAF benchmark system at `/daaf/benchmarks`. Read `/daaf/benchmarks/SESSION_RESTART_2.md` for the session 2+3 state, and `/daaf/benchmarks/SESSION_RESTART.md` for the original session state. The HTML results viewer (`scripts/generate_results_viewer.py`) is fully functional with all bugs resolved: subagent transcript rendering (HTML5 `<` escaping), phase-aware scorecards/metrics, Cases dash-vs-X, jumpToRun navigation, and aligned scatter plot metrics. Visual improvements: model-colored bars with texture differentiation, 45-degree model labels, larger scatter plot with gridlines and hover tooltips. Phase 1+2+3 results across 16 models. The priority for this session is [STATE YOUR PRIORITY].
