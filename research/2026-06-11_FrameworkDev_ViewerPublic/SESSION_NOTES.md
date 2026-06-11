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

## Open Questions

- None pending — all design decisions resolved at Checkpoint 1 + design
  review (og:image deferred; print stylesheet deferred; takeaways list
  locked at six with user framing adjustments)

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework
Development mode. DAAF contributed to: scoping exploration (prose inventory,
data verification of takeaway claims, architecture/hosting audit) and scope
synthesis. The researcher directs all design decisions and approves all
changes at checkpoints.
