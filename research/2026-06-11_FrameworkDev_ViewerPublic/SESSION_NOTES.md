# Session Notes: Framework Development — Public Benchmarks Viewer

**Started:** 2026-06-11
**Workspace:** /daaf/research/2026-06-11_FrameworkDev_ViewerPublic
**Work Type:** Modify Existing (multi-file: generator + template + docs; public-consumption evolution of the benchmarks results viewer)

## Accomplishments

- Phase 1 scoping complete: 3 parallel read-only explorations persisted to
  `preliminary_notes/`:
  - `2026-06-11_scoping_prose-inventory.md` — full prose surface map (~40
    surfaces, ~30 jargon terms), slots for new content, About-layer gaps
  - `2026-06-11_scoping_takeaway-claims-verification.md` — all 8 proposed
    takeaway claims adjudicated against viewer_2026-06-11d.html embedded JSON
    (verified 17-model leaderboard table, cost ratios, caveats, JSON paths)
  - `2026-06-11_scoping_architecture-hosting.md` — new-section recipe,
    web-hosting gap list, file://-vs-http retest list, integration/doc-sync
    landscape, publishing-workflow observations

## Key Decisions (user-confirmed scope inputs, this session)

- Venue: project website (daaf.openaugments.org) + links from README/Substack/
  social media
- Transcripts stay embedded (no stripping)
- Evolution of the existing single viewer — no separate public variant
- Full audience inversion: prose must be legible to readers unfamiliar with
  DAAF; per-phase failure-mode intuitions (P1 query routing, P2 protocol/
  reference-loading discipline, P3a delegation quality, P3b subagent conduct,
  P4 judicious domain-knowledge grounding) + Perfect-vs-Critical as
  first-class concepts
- Key-takeaways editorial section desired; hybrid pattern (dated qualitative
  narrative + generation-time injected numbers) — **user confirmed at
  Checkpoint 1 (2026-06-11)**
- Checkpoint 1 decisions (all user-confirmed): reworded claims accepted,
  EXCEPT DeepSeek Flash keeps the user's "meaningfully worse than GLM"
  framing anchored on the critical-only composite gap (0.720 vs 0.787) with
  composite near-tie disclosed; no light theme; mobile/accessibility trivial
  fixes only; stable filename + compression + deployment handled in user's
  separate website deploy infrastructure (out of scope); main README
  unchanged for now
- Newcomer framing sources (user-directed): mirror main README framing and
  daaf.openaugments.org language (verbatim extraction available at
  research/2026-06-10_FrameworkDev_UserDoc02Sync/preliminary_notes/
  2026-06-10_website_verbatim_extraction.md + companion full-page text);
  user_reference/02_understanding_daaf.md for jargon language at discretion
- Data corrections needed to user's draft claims (from verification):
  Sonnet 4.6 is #2 overall ahead of Opus 4.8; GLM 5.1 ≈ 1/7 Opus cost (not
  1/10); DS Flash ≈ GLM on composite (gap 0.0055; "appreciably worse" only
  on critical-only composite 0.787 vs 0.720); DS Flash ~1/12 GLM ~1/81 Opus;
  Gemma unreliability has two distinct bases (viewer timed_out 45.8%/13.7%
  vs README forensic silent-stall 18.5%/9.3%) — cite bases explicitly

## Design (approved at design review, 2026-06-11)

- TOC order: Hero → Key Takeaways (NEW) → About (restructured) → existing
  sections. New section uses 4-point registration (scaffold, TOC,
  SECTION_IDS, content-visibility CSS)
- Hero/About framing: GENERALIST — "How well do different AI models handle
  the complexities of rigorous research workflows?" User explicitly REJECTED
  the Mind/Body/Instructions device (overcomplicates)
- Key Takeaways: dated "Editorial takeaways — June 2026 corpus" +
  disclaimer; six takeaways (Fable dominance; Opus evolution + 4.7
  regression; Sonnet 4.6 budget pick #2 overall; GLM 5.1 leads open-weight
  ~1/7 Opus cost; DS Flash extreme-value outlier framed on critical-only gap
  0.720 vs 0.787 with composite near-tie disclosed, ~1/12 GLM ~1/100 Opus;
  small/local not there + Gemma 31B 45.8% timed-out); numbers span-injected
  via precompute (incl. NEW per-model timed-out rates in build_precomputed)
- Audience inversion: two-register PD_EXPLAINERS; always-visible "Two bars"
  Perfect-vs-Critical block + echo-site sweep; plain-language criterion
  label map (snake_case stays in forensic surfaces); About glossary
  collapsible (~10 terms); outbound links (site + repo); forensic sections
  get one-line orientation only
- Head metadata: title, meta description, OG/Twitter WITHOUT og:image
  (deferred to deploy infra), inline SVG favicon, noscript notice
- Deferred/out of scope: og:image, print stylesheet, light theme, touch/
  aria audit, responsive rework, deploy/rename/compression, main README
- Generator 2.5.0 → 2.6.0; dev-guide + README §§ 8/12 sync in dispatch 2

## Integration Status

**Component:** benchmarks viewer (generator v2.6.0 + template) + docs
**Checklist:** FRAMEWORK_INTEGRATION_CHECKLIST.md has no benchmarks section;
explicit doc-sync list applies instead (benchmarks/README.md §§ 8/12,
generator dev-guide + version bump; main README explicitly out of scope)
**Completed:** Phase 3 implementation dispatches 1+2 (generator COMPLETE:
v2.6.0, timeout_by_model precompute, dev-guide "Public-prose registries"
section; template COMPLETE: all 15 spec items — noscript, head metadata
incl. OG sans og:image, hero rewrite, #takeaways section w/ 29 kt-* spans +
fillTakeaways(), CRIT_LABELS 45-entry map + critLabel(), About restructure
w/ two-bars block + 10-term glossary + failure-mode phases table,
PD_EXPLAINERS two-register, jargon sweeps, costs-lead fix, renumbering).
Sanity: regenerated /tmp/viewer_public_sanity.html (13.87 MB), 30/30 checks
pass; figures match verification notes. Dispatch 1 partial report + spec at
preliminary_notes/2026-06-11_dispatch1_partial-report-and-template-spec.md
**Remaining:** doc-sync dispatch (benchmarks README §§ 8/12 + official dated
regeneration) → Phase 4 3-angle review → Checkpoint 2 + user visual check

## In Progress

- Doc-sync dispatch COMPLETE (2026-06-11 ~03:10 UTC): benchmarks README § 8
  (section list, token-notation fix, "Public-audience evolution" design-record
  addendum items a-g + 2 accepted residuals) and § 12 (RESOLVED bullet,
  viewer pointer → viewer_2026-06-11e.html, fast-follows + og:image);
  official regeneration `/daaf/benchmarks/viewer_2026-06-11e.html` (v2.6.0,
  13.87 MB, 50 sets / 2,283 runs); 34/34 verification checks incl. simulated
  render (every kt-span write target has data — no em-dash defaults survive)
- Phase 4 three-angle review COMPLETE (user directed continuation past HIGH
  threshold; all three reviewers returned proceed YES):
  - Consistency: clean across all 7 check areas (versions, section lists,
    echo sites, README-vs-code claims, cross-refs, no Mind/Body, kt-span
    wiring 29=29). INFO: pre-existing dev-guide line anchors in the
    phase-addition section drifted ~250-450 lines (self-disclaimed; cheap
    fast-follow).
  - Quality: all 45 CRIT_LABELS traced to scorer code — none wrong, 38
    exact; 3 MINOR rewordings suggested (required_skills_engaged ~L1284
    "loads or at least names the required skills"; subagent_searches ~L1272
    "uses search/exploration tools"; routing_order ~L1286 "follows the
    skills' prescribed routing order"). SUGGESTION: orienting line atop
    Takeaways for pre-glossary terms. Framing fidelity, honesty,
    legibility, prose: clean.
  - Completeness: design fully traced; MINOR doc gap (touch/aria +
    main-README deferrals only in SESSION_NOTES, not README § 12);
    REPLACE-WITH-FINAL-URL properly marked; artifact data verified.
  - **CROSS-SESSION SEQUENCING FLAG:** a concurrent Benchmark Bugfixes
    session rescored 83 runs at ~03:13 UTC — AFTER viewer_2026-06-11e.html
    was generated (03:06). The artifact embeds pre-rescue scores. Its git
    files (scorers/deterministic/dispatch_compliance.py,
    subagent_behavior.py, run_dispatch_compliance.py, untracked
    rescore_dispatch_timeout_rescue.py) + interleaved README edits share
    the tree; commit hygiene needs care. Post-rescue regeneration
    (viewer_2026-06-11f+) + kt-figure/qualitative-claim delta check needed
    before deploy (README:1110-1113 already records the regen need).
- Checkpoint 2 round 1: user approved 5 minor fixes (3 CRIT_LABELS rewords,
  takeaways orienting line, README deferral note) — applied by orchestrator;
  regenerated viewer_2026-06-11f.html on post-rescue corpus
- Delta check (search-agent, vs post-rescue data): T1/T3/T5/T6 HOLD;
  T2 needed 1-sentence reword (4.7 no longer drops a tier — tier structure
  collapsed 5→4, T2 now 9 models incl. DS Pro 0.7259 > GLM 0.7085 > DS Flash
  0.7030 + Gemini Pro); T4 BROKEN (DS Pro now leads open-weight). User
  approved reframed T4 ("Open-weight models are credible — and now crowd
  the frontier tier", DS-Pro-led) + T2 sentence swap
- Final engineer dispatch COMPLETE: T2/T4 rewritten, fillTakeaways rewired
  (29→31 spans: +kt-t4-dspro/-glm/-dsblend/-dsto), README § 8 count + 
  re-adjudication record + § 12 pointer → **viewer_2026-06-11g.html**
  (13.92 MB, 50 sets / 2,283 runs — two throwaway validation sets were
  deleted by user after _11f, so corpus differs from _11f's 52 sets; all
  takeaway figures verified identical). All verification PASS; nothing
  committed
- **PENDING USER APPROVAL: DS Pro timeout honesty clause** — orchestrator
  added to T4: "DS Pro carries the corpus's second-highest timeout rate
  (26.8% of runs), so its scores come with a reliability asterisk" (echoed
  in README § 8/§ 12). User has not yet explicitly approved — approve or
  remove at wrap-up
- NEXT: user visual check of viewer_2026-06-11g.html; superseded-viewer
  housekeeping (_11a–_11f; user deletes); commit when user directs (CARE:
  working tree shares README.md edits + scorer files with the concurrent
  Benchmark Bugfixes session — stage deliberately)
- Context CRITICAL (~250k) — session wrap after final checkpoint; any new
  work in a fresh session (this file is the resume point)

**Session closure (2026-06-11 ~13:00 UTC):** All code/doc work from this
session was committed by the concurrent Benchmark Bugfixes session in
commit 5402185 ("fix(benchmarks): timeout dispatch recovery..." — its
message explicitly notes it includes this session's generator/template/
README § 8 edits). That session also bumped the generator to v2.7.0
(transcript keying by {result_set}/{run_dir}) and changed the corpus
again after viewer_2026-06-11g.html: the 4 transcript-less Fable pc runs
(120s-ceiling artifacts) were replaced at 300s in set 20260611_124829
(4/4 pass). This workspace folder committed separately by this session.

**Restart prompt (paste into a fresh session after /clear):** "Launch
Framework Development mode. Resume from
/daaf/research/2026-06-11_FrameworkDev_ViewerPublic/SESSION_NOTES.md —
read it fully; the public-audience evolution of the benchmarks viewer is
implemented, reviewed (3-angle, all YES), and committed (commit 5402185,
which also carried a concurrent session's v2.7.0 transcript-keying fix
and corpus changes). Goal this session: TEXT AND LAYOUT FINE-TUNING of
the viewer per user direction. Before any tuning: (1) regenerate a fresh
artifact via python3 benchmarks/scripts/generate_results_viewer_v2.py
(corpus changed after viewer_2026-06-11g.html: Fable pc-03/pc-07 runs
replaced and now passing, new set 20260611_124829, generator v2.7.0) and
(2) run a takeaway delta check against the new PRECOMPUTED — Fable
margin/consistency and tier structure may have shifted; the six takeaway
qualitative claims were last adjudicated against the _11g corpus (see In
Progress section for the T2/T4 rewrite history). (3) Resolve the still-
PENDING user decision: the DS Pro timeout honesty clause in Takeaway 4
('second-highest timeout rate, 26.8% of runs... reliability asterisk')
was orchestrator-added and never explicitly approved — ask keep/remove/
reword. Then collect the user's fine-tuning directions and iterate.
Conventions: benchmarks/README.md § 12 is source of truth; regen only
via the generator (never edit artifacts); python3 (not rg) for results/
and viewer_*.html; superseded viewers _11a–_11g are user-deletion
housekeeping; at deploy: og:url REPLACE-WITH-FINAL-URL placeholder,
og:image, and the http(s) hash-navigation retest (README § 8)."
- Deploy-time reminders for user: replace og:url REPLACE-WITH-FINAL-URL
  placeholder; og:image; http(s) retest (explicit-nav hash writes, scrollspy
  replaceState, content-visibility anchor rendering)

## Session 2 (2026-06-11, post-commit): Cost Estimation Work

**New scope (user-directed, precedes text/layout fine-tuning):** improve cost
guidance — listed blended $/Mtok is misleading without token-appetite context.

- Phase A reconciliation COMPLETE (framework-engineer): OpenRouter billing CSV
  (`benchmarks/openrouter_activity_2026-06-11.csv`) attributed to corpus runs
  via transcript time windows (UTC confirmed; ±120s; 86-98% of $ attributed,
  9/10 models; Nemotron 68%). Full findings:
  `preliminary_notes/2026-06-11_phaseA_openrouter-cost-reconciliation.md`.
  Artifacts: `benchmarks/scripts/reconcile_openrouter_costs.py` +
  `benchmarks/derived/openrouter_reconciliation_2026-06-11.json` (uncommitted)
- Key findings: token hunger only 0.67-1.26x vs Opus 4.8 (NOT the main
  distortion); models.yaml listed rates WRONG for Gemma 26B (~2.1x), DS Flash
  (~1.34x), Gemma 31B (~1.26x) vs billing; harness cost formula ignores
  cache_creation → Anthropic logged costs ~3x understated; Fable concealed
  thinking IS in the usage meter (not hidden from billing); OpenRouter
  caching effectively never materialized (parallel requests)
- **DECIDED (user, 2026-06-11):** new headline cost metric = estimated cost
  per benchmark battery (47 probes = 141 runs/3 reps, assumption to verify):
  list prices × each model's observed token mix, UNCACHED basis; Anthropic
  shown uncached-only for direct comparability (validated within ~3% of
  actual billing for 7/10 OpenRouter models). Published $/Mtok stays as
  secondary detail. Headline figures: Fable $174/battery, Opus 4.8 $75,
  Sonnet 4.6 $31, GLM $18 (≈1/4 Opus, not 1/7), DS Flash $1.80 (≈1/10 GLM,
  ~1/40 Opus, pre rate-fix). Caching disclosure sentence required (real
  Anthropic usage caches; ~$32/battery for Opus 4.8 under full convention)
- Takeaway cost ratios (T3 "1/7", T5 "1/12 GLM ~1/100 Opus") CONTRADICTED by
  observed billing — rework on new basis pending alongside corpus delta check
- Viewers _11h/_11i discovered (concurrent bugfix session regens); even _11i
  predates Fable replacement set → fresh regen still needed
- Phase C COMPLETE (two framework-engineer dispatches + one search-agent
  adjudication; full returns in preliminary_notes/):
  - `2026-06-11_phaseC_battery-metric-implementation.md`: models.yaml rate
    fixes (Gemma 26B ×2.12, DS Flash ×1.34, Gemma 31B ×1.26); harness
    cache_creation billing fix (future runs only); generator v2.8.0
    cost.battery block + staleness guard; template battery surfaces;
    README §§ 7/8/12. battery_size = 51 distinct probes (NOT 47 — uneven
    reps: Anthropic dc cases ran 2 reps; 141 = 15×3+9×3+12×2+15×3)
  - `2026-06-11_takeaway-readjudication-11j-battery.md`: vs viewer_2026-
    06-11j.html (53 sets/2,493 runs; tier structure back to 5 tiers,
    Sonnet 0.829 + Opus 4.8 0.796 alone in T2): T1 HOLD, T2/T3/T4/T5/T6
    REWORD; kt-foot "single repetition on P4" claim found false (45 P4
    runs/model now)
  - **USER DECISION:** display battery cost as rough relative MULTIPLIER
    vs Opus 4.8 (=1.0×), never dollars (false precision); "cached cheaper"
    caveat dropped; NEW drift caveat (repricing + provider caching
    mechanics × model behaviors affect relative figures)
  - **USER DECISION (T4/DS Pro clause RESOLVED):** open-weight case
    reframed control-not-price; timeout reliability asterisk (26.8%) kept
  - `2026-06-11_final-application_multiplier-takeaways.md`: all rewrites
    applied (29 kt-spans, was 31); generator v2.8.1; official artifact
    **viewer_2026-06-11k.html** (24.68 MB, 53 sets / 2,493 runs); all
    verification checks PASS
- Artifact size note: ~25 MB (was ~14 MB) — jump came from the concurrent
  session's transcript-keying corpus changes (_11h→_11i), not this work;
  flag for deploy compression
- NOTHING COMMITTED. Working tree: models.yaml, harness/models.py,
  harness/cost_estimator.py, generator, template, benchmarks/README.md,
  NEW scripts/reconcile_openrouter_costs.py + derived/openrouter_
  reconciliation_2026-06-11.json, this workspace. CAUTION: raw
  `benchmarks/openrouter_activity_2026-06-11.csv` contains a user hash —
  user decision whether to commit raw CSV (derived JSON is the committable
  artifact). Superseded viewers _11a–_11j = user-deletion housekeeping
- PENDING NEXT SESSION: (1) Phase 4 three-angle review of this session's
  changes (consistency/quality/completeness; files above) — NOT yet run;
  (2) user visual check of _11k (battery table multipliers, scatter
  battery toggle, takeaways, kt-foot); (3) commit when user directs;
  (4) THEN the original goal: text/layout fine-tuning per user direction

**Restart prompt (Session 3 — paste into a fresh session after /clear):**
"Launch Framework Development mode. Resume from
/daaf/research/2026-06-11_FrameworkDev_ViewerPublic/SESSION_NOTES.md —
read it fully. Session 2 added the battery-cost work: OpenRouter billing
reconciliation (scripts/reconcile_openrouter_costs.py + derived JSON),
models.yaml rate fixes, harness cache-write fix, generator v2.8.1
battery-MULTIPLIER cost display (vs Opus 4.8, never dollars), takeaways
re-adjudicated + rewritten (29 kt-spans), official artifact
viewer_2026-06-11k.html. Conventions: benchmarks/
README.md § 12 is source of truth; regen only via the generator; python3
(not rg) for results/ and viewer_*.html; at deploy: og:url placeholder,
og:image, http(s) hash-navigation retest, and ~25 MB artifact compression.

This session: 

## Session 3 (2026-06-12): Website Integration — Tone, Cost Centralization, Multi-File + Styling

**Scope (user-directed, confirmed at session start):** (1) percolate the user's
e099982 frontmatter voice + website framing through all viewer prose; (2) make
the battery cost multiplier the headline cost figure everywhere (leaderboard,
scatter default, cost table) and remove blended $/Mtok entirely (input/output
rates stay secondary); (3) multi-file architecture (fully committed — lazy-load
transcripts) + adopt daaf-product topbar and site styling (daaf-anatomy as
deep-dive analogue; bundle to live in the daaf-product site folder; user's
deploy script handles relative links). Session-wide context override: 300k
critical for orchestrator and all subagents. User has visually approved _11k.
Session 2's deferred 3-angle review folds into this session's Phase 4.

**Phase 1 scoping COMPLETE** — 3 parallel search-agents, full returns persisted:
- `preliminary_notes/2026-06-12_scoping_voice-percolation.md` — voice guide
  (colon-first, decoder pattern, honest hedging, website phrases); 35-surface
  percolation map; 12-item user-edit cleanup list incl. TWO RUNTIME CRASHES
  introduced by e099982 (renderHero L1492 hero-models; fillAboutCounts
  L1674-5 ab-models/ab-runs — both spans deleted, el() null → TypeError →
  hero chips/verdict and About counts never render); kt-t4-dsflash unfilled;
  12 orphaned setters; T2 garbled sentence with figure-less claim
- `preliminary_notes/2026-06-12_scoping_cost-surfaces.md` — 31 cost surfaces
  (G1-G8, T1-T21, R1-R5); blend31 lives ONLY in generator+template (no
  harness/config/golden exposure); data-flow map; multiplier range
  0.019×-2.327× (log axis already in place); 12-item removal risk list;
  generator → v2.9.0
- `preliminary_notes/2026-06-12_scoping_architecture-styling.md` — size
  anatomy (transcripts 84.6% of 25 MB; ~3.9 MB initial payload after split);
  per-result_set shards (53 files, median 275 KB) via the single
  renderRunDetail seam (T:3078/3117); site is DARK-themed, token-adjacent
  (indigo #6366f1 shared); token swap + fonts (Space Grotesk/DM Sans/
  JetBrains Mono) + topbar/footer, NOT full restyle; teal-vs-status-green
  collision caution; split-first sequencing; scrollspy/contrast/
  content-visibility fragility list

**Checkpoint 1 PASSED (2026-06-12).** User decisions: --single-file flag KEEP;
shards per-result-set (orchestrator's call); teal-as-chrome/indigo-in-content
accent split confirmed; T2 minimal repair + critical-only spans approved;
hero counts re-injected as spans; hero chips hoisted above prose WITH content
redesign (intuitive-without-context challenge — orchestrator latitude).
**NEW SCOPE STRAND:** this page is "DAAFBench: Orchestration" (part A); a
future separate DAAFBench will test analytic competency (adversarial
examples, known-good code, deterministically verifiable outputs). Make the
separate-and-complementary relationship clear in naming, hero/frontmatter,
and About (lands in Wave 3).

**Wave 0 COMPLETE (framework-engineer):** both e099982 crashes fixed
(hero-models/hero-runs re-injected + renderHero fills; dead ab-models/ab-runs
writes removed); kt-t4-dsflash filled; 11 orphaned setters pruned;
kt-t6-*→kt-t5-* renumbered; T2 repaired w/ kt-t2-o45h/o46h/o47h/o48h spans
from composite_hard (claim VERIFIED TRUE: 4.7 dip 8.5pts critical-only vs
4.9pts composite); typos/entities fixed; #caveats id added (kt-foot links
#about); .kt-badge/.kt-disclaimer CSS removed; generator dev-guide span
contract 29→23 (no version bump); README §8/§12 synced. Bidirectional span
check 32↔32 zero orphans; sanity /tmp/viewer_wave0_sanity.html 30+ checks
pass. Residual: two stale "1,700+" internal JS comments (later wave).

**Wave 1 COMPLETE (framework-engineer):** generator v3.0.0 — default output
now bundle dir `benchmarks/daafbench_YYYY-MM-DD[suffix]/` (index.html 3.72 MB
+ data/tx_{result_set}.json × 53, 20.97 MB, largest 1.14 MB); DATA swaps
transcripts/subagent_transcripts for transcripts_index (mutually exclusive
keys mark the mode); --single-file [PATH] emits pre-3.0 monolith
(viewer_YYYY-MM-DD*.html naming); template renderRunDetail two-stage w/
feature-detect, memoized shard cache, stale-click token, visible error
fallback (file:// → http.server hint), deep-links unchanged; noscript prose
fixed; .gitignore daafbench_*/; README §8 bundle-first rewrite + retest list
3→4 + design addendum, §12 dated entry. 24/24 structural checks PASS incl.
exact shard-vs-monolith key-set equality both namespaces; PRECOMPUTED
byte-identical across modes. Sanity: /tmp/daafbench_wave1_sanity/ +
/tmp/viewer_wave1_sanity.html. Browser check of fetch paths = http(s)
retest at deploy (4 items). viewer_2026-06-11k.html stays official until
Wave 5 regen.

**Wave 2 COMPLETE (framework-engineer):** generator v3.1.0 — blend31 removed
from cost.models[] + frontiers (battery/input/output, battery first); sanity
report prints battery frontier; template leaderboard cost column → battery
multiplier (new shared batteryMult() helper; header "Battery cost (× Opus
4.8)"; fmtMult + na-idiom + ⚠ stale tooltip — no current model stale);
scatter default costForm "battery", COST_FORMS[0] battery, blend31 entry
deleted; CvP lead rewritten multiplier-first (functional; voice polish in
W3); About caveat flipped multiplier-first; README §8 addendum (input-token-
dominance rationale) + §12 entry. Verified: zero blend31 in generated output;
17/17 multiplier ladder (Fable 2.3× → Gemma 31B 0.02×); frontier 6 models.

**Wave 3 COMPLETE (framework-engineer):** suite naming "DAAFBench:
Orchestration" (title/og/meta/TOC/About h2); TWO sanctioned voice-anchor
edits, both flagged for user review at Checkpoint 2: (1) hero ¶3 insertion
naming the suite + companion analytic-competency suite (adversarial
examples/known-good code/deterministic outputs, complementary halves);
(2) takeaway-1 "at a Perfect average score of" clarifier. Full rewrites:
leaderboard lead, PD_EXPLAINERS ×5 (P4 uses site "fuzzy general knowledge"
vocabulary), CvP voice polish. Moderate passes: two-bars, phases table,
scoring, PD/Cases/Costs leads, lbTierRuleText, hero verdict decoder. NEW
#next-steps closing CTA (anatomy model; openaugments.org +
daaf.openaugments.org/anatomy links verified from subset; Open Augments
attribution); glossary lab-manager gloss; hero chips HOISTED above prose +
content redesign (17 AI MODELS TESTED / 2,493 ARCHIVED TEST RUNS / 51
DISTINCT TEST SCENARIOS / 100% OF SCORES TRACE TO A REAL RUN); stale JS
comments fixed; dev-guide anchors + recipes synced; README §8 (a)-(g)
addendum + §12. Voice-anchor diff: only the 2 sanctioned deltas; span
contract 23 intact; 24/24 simulated fills non-null. No version bump.

**Wave 4 COMPLETE (framework-engineer):** template-only restyle — site tokens
(#0a0f1c surfaces, white-alpha borders, --accent-teal/mint, --nav-height,
radii scale), site font loading mirrored (Space Grotesk/DM Sans/JetBrains
Mono, swap, offline fallback documented); 3px gradient strip + sticky 88px
nav.site-nav (class-scoped to avoid toc-rail collision; anatomy relative
href model ../daaf-product/…; Learn dropdown carries active "Choosing Your
Model (DAAFBench)" entry; nav JS ported as zero-global IIFE); anatomy
site-footer after #next-steps; idioms: summary-badge chips, gradient
callouts (verdict/pd-callout), teal eyebrows ×9, 999px pills, indigo mono
chips (deliberately not teal beside pass/fail), gradient-text h1; JS hex
sweep complete (SVG gridlines → white-alpha; inline styles → vars; status
ramp/MODEL_COLORS/ambers untouched); geometry nav-height-aware (scroll-
padding, toc-rail top, scrollspy NAV_SPY_OFFSET ≈121px); WCAG re-audit all
PASS alphas unchanged (rs-3 4.71 vs 4.5 floor; recorded in WP8 comment);
contain-intrinsic-size kept (line-height stays 1.5 by design); index.html
3.75 MB (+0.03). Deliberate skips: phase-cascade coloring, two-bars indigo
bar, print stylesheet. README §8 addendum + §12 (deploy visual check now
incl. dropdowns/hamburger/chips/footer/fonts).

**Wave 5 COMPLETE:** official bundle daafbench_2026-06-12/ generated
(v3.1.0); then 3-angle review (3 parallel search-agents), ALL PROCEED YES,
zero blockers; covers Session 2's deferred review (Session-2 cost triangle
verified clean: models.yaml ↔ recon JSON ↔ README §7 agree; cache_creation
fix consistent). Findings: 3 consistency WARNINGs (README §12 pointer,
"six claims"→five, §8 section list missing next-steps), quality findings
1-7 mechanical + 8-10 user-voice/judgment, completeness 2 WARNINGs (pointer
+ two-bars skip record) + INFO ledger. Claim audit vs live artifact: ALL
TRUE (chips, T1-T5 figures, site quotes verbatim; "100% trace" defensible).

**Post-review fix pass (cycle 1) COMPLETE (framework-engineer):** T2
sentence re-fixed ("The 4.7 dip is even more pronounced… across the four
Opus releases"); leaderboard lead names (P1, P2, P3a, P3b, P4); entity
sweep L894-1220 (21 apostrophes → &rsquo;); "chews" dedupe (Costs lead →
"burns far more tokens getting there"); cost-foot "billing-export token
mixes"; two-bars "right down to the protocol details"; generator v3.1.1
__HERO_MODELS__/__HERO_RUNS__ build-time substitution (noscript counts now
live; substitution order enumerated in dev-guide); anchors re-derived;
README §8 five-claims amendment + next-steps in section list + two-bars
skip record; §12 Viewer current → **daafbench_2026-06-12a/** (_11k = last
monolith-only official). Regen verified: 17/2,493 substituted, zero
unsubstituted tokens, 23-span bidirectional clean, 53 shards.

**RESERVED for user at Checkpoint 2 (untouched, user voice/judgment):**
(1) hero ¶3 insertion approval (DAAFBench: Orchestration + companion
suite); (2) takeaway-1 "a Perfect average score of" clarifier approval;
(3) T4 claim-line tangle ("highly capable as a win for self-hosting
opportunities… meaningful and crucial") + "same cost bracket as Sonnet"
stretch (GLM 0.235× vs Sonnet 0.415×); (4) T5 "often not actually doing
any work at all" forensic-basis citation; (5) optional kt-foot editorial-
boundary clause (user removed kt-disclaimer deliberately); (6) footer
ASCII "LGPL-3.0 --" (verbatim site mirror — confirm intentional).

**Deferred-item ledger (deploy/housekeeping):** og:url placeholder;
og:image; http(s) 4-item retest (hash writes, scrollspy replaceState,
content-visibility anchors, transcript fetch + &run= deep link); visual
check (topbar dropdowns hover+mobile, hamburger, hero chip badges, footer,
font loading/fallback); ~21 MB shard compression; deploy-script
relative-link compatibility w/ data/ fetches (unconfirmed assumption);
superseded viewers _09e–_11k + daafbench_2026-06-12/ (pre-fix bundle) =
user-deletion housekeeping; raw openrouter_activity CSVs (user hash —
commit decision); future: print stylesheet, light theme, touch/aria,
main README link.

**Checkpoint 2 round 1 (2026-06-12):** user approved both sanctioned edits;
T4 self-hosting fix applied ("highly capable — a real win for self-hosting —
but with a crucial decline in consistency"; "same cost bracket" kept); T5
"— per transcript forensics —" added; no kt-foot editorial clause; footer
ASCII confirmed fine. Single-file viewer_2026-06-12a.html generated.

**Fine-tuning round COMPLETE (framework-engineer, 11 user items):**
(1) #hero-verdict + renderHero verdict prose removed; (2) TOC "Verdict"→
"Intro"; (3) T1 "genuinely"→"simply" (de-dupe vs T2); (4) leaderboard
"Timed out" column (PRECOMPUTED.timeout_by_model, worst-first defDir −1,
not on rs-* ramp, tooltip + lb-foot clause); (5) CvP chart responsive
(viewBox + width:100%, no resize listener needed); (6) native <title>
tooltips removed from CvP points; (7) TOC first-click fix: first explicit
nav → ensureAllRendered() + body.nav-rendered un-skips content-visibility
+ double-rAF scroll (stays on http(s) retest list); (8) #next-steps section
removed (links live on in hero/About); (9) Costs Detail section REMOVED —
condensed battery disclosures now unconditional in CvP footnotes
(batteryDisclosureHtml: uncached/bases/⚠/drift/never-dollars), list-price
table relocated as <details class="cp-pricing"> under the chart, all
#costs refs re-pointed; (10) intro restructure: hero = h1+date+chips+¶1;
takeaways; NEW #cvp-preview (same svgCostFrontier path, H=330, no toggles,
renders on load); About opens with hero ¶¶2-4 moved VERBATIM, Wave-3
About-intro ¶1 trimmed to one non-duplicative sentence (companion-suite
framing stated once, in user's ¶3); (11) kt-foot removed, content merged
into About Key Caveats ("Denominators are small and uneven" + drift/
kt-foot-bat). Span contract still 23 (22 in #takeaways + kt-foot-bat in
About). Sections 11→9. No generator version bump (comments only). README
§8 fine-tuning addendum + §12. Artifact viewer_2026-06-12b.html.

**Website-deploy compat notes (from user's website assistant, applied):**
canonical tag added (https://daaf.openaugments.org/bench/; og:url
placeholder frozen for deploy.sh substitution, comment added); nav Learn
entry shortened to "Choosing Your Model" (on-page DAAFBench branding
kept); confirmed: bundle deploys as root-level sibling dir (../daaf-
product/ links anatomy-style — no edits needed), data/ is flat tx_*.json
only (verified 0 strays), Learn self-link stays index.html. og:image:
recommend deploy-time injection (pending user confirm). Review artifact
regenerated: **viewer_2026-06-12c.html** (24.71 MB; _12a/_12b superseded).

**og:image RESOLVED:** deploy-time injection confirmed (deploy.sh injects
sitewide daaf_ogimage.png after og:url, asserts exactly one tag). Nothing
needed framework-side. Website's on-disk bundle copy has the old long nav
label — resolves at next copy-over.

**Fine-tuning round 2 COMPLETE (framework-engineer):** (1) hero prose →
single "TLDR:" paragraph (user's first sentence verbatim w/ both links +
user-supplied DAAFBench: Orchestration sentence verbatim); "DAAF layers
together…" sentence moved verbatim to About as its opening paragraph
(About order: layers → orchestration explainer → "But a framework…" w/
hero spans → "But these results…" → mechanical-scoring sentence →
open-source ¶); #cvp-preview moved between hero and #takeaways (init-
render + exclusion verified); (2) leaderboard + CvP footnotes wrapped in
collapsed <details class="foot-details"><summary>Details</summary> at
regular 13.5px --text-2 size (authored in renderLeaderboard/renderCostPerf
innerHTML; prov-foot + cp-pricing-internal footnotes deliberately
unchanged; cp-pricing stays sibling expander). Dev-guide page-top-order
notes synced; README §8 round-2 paragraph + §12 bullet. 11/11 artifact
checks PASS; 23-span contract clean; sections 9. Artifact:
**viewer_2026-06-12d.html** (supersedes _12a-_12c).

**Session close (2026-06-12):** user approved _12d + made final manual
prose touches directly; official bundle **daafbench_2026-06-12b/**
generated (3.75 MB index + 53 shards; span wiring verified clean post-
user-edits, 31 spans zero orphans, zero unsubstituted tokens); README §12
Viewer current → _12b (user-approved for deploy; _12a marked superseded
before deploy). All session work committed (template, generator, README,
.gitignore, this workspace incl. website subset reference). Deploy ledger
stands (og:url/og:image owned by deploy.sh; http(s) 4-item retest; shard
compression; superseded single-file viewers _09e–_12d = user-deletion
housekeeping). Next session: post-deploy retest findings or DAAFBench
part B (analytic-competency suite) scoping.

## Open Questions

- None pending — all design decisions resolved at Checkpoint 1 + design
  review (og:image deferred; print stylesheet deferred; takeaways list
  locked at six with user framing adjustments)

## AI Disclosure

Sessions 1-3 used DAAF (Data Analyst Augmentation Framework) in Framework
Development mode. DAAF contributed to: scoping exploration (prose
inventories, data verification of takeaway claims, architecture/hosting/
styling audits, cost-surface audits); OpenRouter billing reconciliation
analysis; implementation of the viewer template/generator across the
public-audience evolution, battery-cost metric, bundle architecture, tone
percolation, and site-cohesion styling; three-angle reviews (consistency/
quality/completeness) with claim-truthfulness verification against
generated artifacts; and documentation sync. The researcher directed all
design decisions, authored the voice-anchor prose (hero, Key Takeaways),
and approves all changes at checkpoints.
