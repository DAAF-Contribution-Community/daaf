#!/usr/bin/env python3
"""
Generate the HTML viewer for DAAF benchmark results (v2 generator line).

Reads benchmark result sets from benchmarks/results/, loads case definitions
and per-set manifests, condenses transcripts, computes derived metrics
(per-model per-phase aggregates, composite scores and tier bands under both
the Perfect and Critical-only metrics, consistency, per-case difficulty,
callouts, published-pricing formulations with per-basis/per-metric
efficiency frontiers, estimated battery costs from observed token mixes
(see the "Battery-cost metric" dev guide above PHASE_MAP), estimated
battery durations from observed per-run latencies, provenance), and
produces the viewer artifact. Timed-out runs are excluded at load (they
carry no gradeable signal — see the load_runs chokepoint), so every metric
and the embedded run payload reflect completed runs only.

Two output modes (v3.0.0 — see the "Bundle architecture" dev guide above
PHASE_MAP):

  Bundle (DEFAULT) — a multi-file directory, benchmarks/
  daafbench_YYYY-MM-DD[suffix]/, containing index.html (the full report
  with all run-level data + precomputed metrics inline, ~4 MB on the
  2026-06 corpus). By default it ALSO writes data/tx_{result_set}.json
  transcript shards fetched on demand by the Run Explorer (lazy-loaded, so
  index.html stays small). This is the official artifact for website
  hosting. Bundles REQUIRE http(s) serving — fetch() of sibling files is
  CORS-blocked on file:// (the viewer shows a fallback message with a
  `python3 -m http.server` hint).

  Single-file (--single-file) — a self-contained monolith named
  viewer_YYYY-MM-DD{letter}.html that works opened directly from disk
  (file://); kept for offline auditing. As of v3.4.0 the DEFAULT single-file
  artifact is transcript-LITE (scores/runs/aggregates only) so it stays
  small; pass --transcripts to restore the full inline-transcript monolith
  (~25 MB on the 2026-06 corpus).

Transcript-inclusion control (v3.4.0 — see the "Transcript-inclusion
control" dev guide above PHASE_MAP): --transcripts / --no-transcripts are a
mutually exclusive pair that overrides the per-mode default in either
direction. Mode defaults: bundle INCLUDES transcripts (lazy shards),
single-file EXCLUDES them. A transcript-less build carries neither
DATA.transcripts nor DATA.transcripts_index and the Run Explorer shows a
"transcripts not included in this build" notice (no broken fetch, no empty
pane).

The HTML/CSS/JS lives in the sibling template file viewer_template.html;
this script is data preparation + placeholder substitution. v1
The v1 generator has been retired.

Usage:
    python3 benchmarks/scripts/generate_results_viewer_v2.py [--results TIMESTAMP...] [--exclude-results TIMESTAMP...] [--output PATH] [--single-file [PATH]] [--transcripts | --no-transcripts]

Examples:
    # Generate the bundle for all result sets (benchmarks/daafbench_YYYY-MM-DD[suffix]/)
    # — includes lazy transcript shards by default
    python3 benchmarks/scripts/generate_results_viewer_v2.py

    # Bundle with NO transcript shards (index.html only, smallest official build)
    python3 benchmarks/scripts/generate_results_viewer_v2.py --no-transcripts

    # Generate for specific result sets, bundle at an explicit directory
    python3 benchmarks/scripts/generate_results_viewer_v2.py --results 20260608_181352 20260608_181751 --output /tmp/daafbench_view/

    # Transcript-lite single-file monolith for offline auditing (DEFAULT single-file)
    python3 benchmarks/scripts/generate_results_viewer_v2.py --single-file

    # Full inline-transcript single-file monolith (pre-3.4 behavior)
    python3 benchmarks/scripts/generate_results_viewer_v2.py --single-file --transcripts

    # Single-file monolith at an explicit path
    python3 benchmarks/scripts/generate_results_viewer_v2.py --single-file /tmp/my_viewer.html

Changelog:
    v3.7.3 (2026-08-03):
      - Key Takeaways T4 reworked (viewer_template.html) to run on the
        all-perfect Consistency `rate` — the same metric as the leaderboard's
        Consistency column — instead of the v3.7.0 rate_agree agreement
        variant, per user decision (supersedes the 2026-07-29 T4 hand-edit
        anchor; prose ratified by the user in this pass). Headline narrowed
        to "reliability" (dropping "predictability", which was the agreement
        framing); mechanism sentence now names the leaderboard tie-in; spans
        renamed kt-t4-{topagree,budgetagree} -> kt-t4-{topcons,budgetcons}
        (28-span contract count unchanged). Schema untouched: rate_agree /
        cells_all_agree remain in PRECOMPUTED.consistency (schema-additive
        contract) but no longer have a display consumer.
    v3.7.2 (2026-07-29):
      - User intensive-pass hand edits over the five Key Takeaways items
        (viewer_template.html), typed directly by the user — the strongest
        ratification tier, superseding the v3.7.1 anchors for those passages
        (anchor comments restamped accordingly; hero bottom-line + About
        intro anchors untouched). Prose-only: no schema, PRECOMPUTED, kt-*
        span inventory, or JS change; the 28-span contract and every
        fillTakeaways setter are intact. Highlights: T1 "top tier is
        increasingly crowded" headline + "no monopoly on frontier compute"
        closer; T2 "model creators" headline + Gemma home-computer aside;
        T3 "in terms of cost" headline; T4 mechanism sentence reworded
        ("every test here runs three times" / "scores equally well");
        T5 "next crossover" closing sentence removed.
      - Corpus (not viewer-code) changes shipped alongside this version:
        3 ledger-adjudicated-unusable Sol runs quarantined
        (_quarantine_2026-07-29_solunusable), the Opus 4.5 spend-limit dc-08
        run quarantined (_quarantine_2026-07-29_opus45spendlimit), the 11
        Opus 4.5 dated-snapshot purity false negatives re-adjudicated to
        verified/valid (wire_id "claude-opus-4-5-20251101" declared in
        models.yaml; summaries rebuilt via the sanctioned rescore path, which
        also resolves 20260726_171652's phase-"unknown" classification), and
        a 1-rep Opus 4.5 dc-08 top-up.
    v3.7.1 (2026-07-29):
      - Prose-only voice pass over the Key Takeaways / hero narrative
        (viewer_template.html), applying the user's 2026-07-29 edit slate. No
        schema, PRECOMPUTED, kt-* span inventory, or JS change — the 28-span
        contract and every fillTakeaways setter are untouched; only prose around
        the injected spans was reworded:
        - Hero bottom-line paragraph rewritten (top-performer framing; "economical
          choices"; slash-joined self-host clause).
        - T1 headline -> "Fable 5 still leads, but the top tier now spans three
          providers"; body "dominates it outright" -> "simply dominates it" plus a
          sample-noise/cost-gap parenthetical.
        - T2 frontier definition recast with a "(basically: ...)" gloss; closer
          ends at the budget-point clause + a small-denominator caveat pointer,
          dropping "not on brand loyalty".
        - T3 closer -> "All to say: it's worth figuring out...".
        - T4 headline -> "What budget models actually give up: reliability and
          predictability"; first sentence contraction+colon; "merely" -> "just".
          Mechanism sentence and "wobble" phrasing preserved verbatim.
        - T5 headline -> "Open-weight models are no longer the compromise option";
          closer rewritten to the provider-flexibility / "next crossover" line
          (optional sun-setting sentence deliberately omitted).
        - Cost-vs-Performance lead: frontier sentence ends at "...hundredfold in
          cost", dropping the Takeaway-2-duplicating clause.
        - Mechanical: GPT-5.6 cost caveat "api-equivalent" -> "API-equivalent";
          trailing whitespace removed in the cvp-preview lead.
        All voice-passed passages flagged with anchor comments as user-ratified
        2026-07-29; the two prior voice anchors (hero TLDR, About intro paragraphs)
        remain byte-identical.
    v3.7.0 (2026-07-29):
      - Key Takeaways narrative overhaul (viewer_template.html) + one
        schema-additive PRECOMPUTED field:
        - Rewrote the five Key Takeaways items for the July 2026 corpus (the
          top tier now spans three providers — Fable 5, Opus 5, GPT-5.6 Sol,
          and the open-weights Kimi K3), retitled the section "Key Takeaways
          (July 2026)", and reworked the hero bottom-line paragraph, the
          Cost-vs-Performance section lead (six-point / four-provider battery
          frontier), the cost-estimate caveat (GPT rate verification), and the
          Phase 3a dispatch explainer (GPT alias-dispatch temptation). The two
          voice anchors (hero TLDR, the four About intro paragraphs) are
          untouched.
        - fillTakeaways() kt-* span inventory rebuilt to match the new prose;
          every numeric figure is live-injected from PRECOMPUTED so future
          regenerations track the data (frontier scores/costs, diminishing-
          returns ratios, per-model agreement rates).
        - PRECOMPUTED.consistency gains two schema-additive fields per model:
          cells_all_agree and rate_agree — the share of repeated (phase, case)
          cells where every rep lands on the identical grade (an agreement /
          predictability measure decoupled from score level, distinct from the
          existing all-perfect `rate`). Powers the Key Takeaways reliability
          claim. No existing field renamed or removed.
        - Removed the "Relative Duration" leaderboard column (header, cells,
          sort hooks, its footnote sentence, and the lb-th-duration CSS). The
          PRECOMPUTED.duration pipeline and the Cost-vs-Performance duration
          scatter axis are unchanged; only the leaderboard column is gone.
    v3.6.1 (2026-07-29):
      - Load-time behavior change: the no-signal exclusion chokepoint now also
        drops legacy instant-exit stub runs. For legacy-schema records
        (schema_version < 2, so status predates the field and is null) it
        additionally excludes a run when top-level output_tokens is null AND
        error is null — the instant-exit signature (status null, not timed out,
        no error, null output, 0/N criteria) surfaced by the 2026-07-29
        instant-exit corpus audit (7 stubs, since quarantined on disk). Mirrors
        the corpus parity scan's legacy screen. Errored legacy null-output runs
        are unaffected (kept, as before). New-taxonomy (schema-v2) records are
        unchanged — their tokens live nested under usage_observed and the audit
        found zero stub divergences there. Each excluded stub emits a stderr
        NOTE and is folded into the No-signal excluded count.
    v3.6.0 (2026-07-29):
      - Display-layer cleanup pass (viewer_template.html + this generator's
        version constant only; no payload keys, model-name keys, or persisted
        fields renamed — model display names remain the cross-payload join
        keys, so every rename below is applied at RENDER time):
        - Removed the rendered Provenance section (section markup, TOC link,
          renderProvenance renderer, sectionRenderers/SECTION_IDS entries, and
          the content-visibility selectors that named #provenance). The
          PRECOMPUTED.provenance data pipeline is intact (still built and
          embedded); only the rendered section is gone. The generated-timestamp
          still shows in the hero and DAAF/Open Augments attribution remains in
          the site footer.
        - GPT model display names strip the "(ChatGPT Subscription)" suffix at
          render time via the displayModelName() JS helper; payload "model"
          keys are unchanged.
        - Leaderboard provider badge renders "chatgpt-subscription" as
          "chatgpt" (badge text only).
        - Removed the per-cell "api-equiv" leaderboard badge; the api-equivalent
          basis disclosure moved to Methods/battery-cost prose. The payload
          `basis` field is retained.
        - Cost-vs-performance scatter legend: "Anthropic API" -> "Anthropic";
          added a "ChatGPT" legend entry for the chatgpt-lane GPT points. Same
          legend on the #cvp-preview intro plot.
        - Composite-score bar hollow-circle component markers: stroke width
          +1px.
    v3.5.0 (2026-07-29):
      - Fix 2 — GPT ChatGPT-subscription (provider chatgpt-subscription)
        battery estimates on an api-equivalent counterfactual basis. These
        models were excluded three ways (load_model_pricing skip,
        _cost_compatibility force-omit, anthropic-only token gate); now priced
        from models.yaml api_equivalent_pricing.short_context list rates,
        aggregated into the live-token battery block (None cache fields -> 0,
        uncached basis), and tagged basis="api-equivalent" so the leaderboard
        marks them "api-equiv" (vs Anthropic "corpus-live"). The run/set-level
        billing_grade_cost_eligible flag is intentionally NOT flipped, so the
        run-detail not-invoiced disclosures stay accurate — only the explicitly
        counterfactual battery estimate includes them.
      - Fix 3 — degenerate leaderboard-column suppression in build_eval_groups
        (and the lockstep template buildEvalGroups): skip phase "unknown", skip
        result sets with zero loaded runs, and fold a subagent-less
        dispatch_compliance set into the 3a dispatch group rather than emitting
        a bare `dispatch_compliance` column. Column-derivation-scoped — runs
        still count in the all-runs aggregates.
      - Fix 4 — tier-banding share cap: the range-quartile fallback now also
        fires when the gap rule's largest tier holds > TIER_MAX_TIER_SHARE
        (50%) of ranked models, even with >= 3 tiers. tier_rule records the
        fallback_trigger.
      - Fix 5 — composite-bar component markers rendered as small hollow white
        circles instead of vertical tick marks (viewer_template.html CSS only;
        renderer positioning unchanged).
      - Fix 1 (OpenRouter reconciliation glob) NOT applied — reported
        BLOCKED-on-schema: the current derived/*_openrouter_reconciliation.parquet
        artifacts carry billed-vs-computed DOLLAR reconciliation columns keyed
        by base_slug, with NO per-run prompt/completion token mix, so they
        cannot feed the uncached-basis battery consumer (which needs
        openrouter_models[name].billed_tokens.{prompt,completion} + n_covered_runs
        from the reconcile_openrouter_costs.py JSON). load_reconciliation left
        unchanged (legacy .json glob retained).
    v3.4.0 (2026-07-29):
      - Transcript-inclusion control (--transcripts / --no-transcripts) with
        per-mode defaults: bundle includes (lazy shards), single-file now
        defaults to a transcript-lite monolith. Transcript-less builds emit a
        DATA payload with neither transcripts nor transcripts_index; the Run
        Explorer feature-detects this and shows a "not included" notice.
      - Explicit non-phase discovery skip: results-root children named in
        RESERVED_RESULT_CONTAINERS (probes, removed_runs) OR prefixed with `_`
        (the `_quarantine*` convention) are skipped up front rather than
        relying on the implicit "no summary.json" filter. A QUARANTINE_NOTE.md
        at a kept set's root is inert (discovery keys only off summary.json).
      - Extended the load-time no-signal exclusion chokepoint to drop
        new-taxonomy status=="stalled"/"timed_out" runs alongside the legacy
        timed_out flag.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import yaml


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate DAAF benchmark results HTML viewer"
    )
    parser.add_argument(
        "--results",
        nargs="*",
        default=None,
        help="Timestamps of result sets to include (default: all in results/)",
    )
    parser.add_argument(
        "--exclude-results",
        nargs="*",
        default=None,
        help="Timestamps of result sets to skip at load time (complement to "
             "--results; applied after inclusion filtering). Exclusions are "
             "recorded in the embedded generation_params for provenance.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path. Bundle mode (default): a DIRECTORY for the "
             "multi-file bundle (default: auto-named dated dir in "
             "benchmarks/, e.g. daafbench_YYYY-MM-DD, with a letter suffix "
             "auto-incrementing to avoid overwriting earlier same-day "
             "outputs). Single-file mode (--single-file): an HTML FILE path "
             "(default: auto-named viewer_YYYY-MM-DDa.html in benchmarks/, "
             "same auto-increment convention).",
    )
    parser.add_argument(
        "--single-file",
        nargs="?",
        const=True,
        default=None,
        metavar="PATH",
        help="Emit the self-contained single-file monolith instead of the "
             "multi-file bundle — the offline/file:// audit path. By DEFAULT "
             "this is now a transcript-lite monolith (scores/runs/aggregates "
             "only); pass --transcripts to restore the full inline-transcript "
             "monolith (the pre-3.4 behavior, ~25 MB). Optional PATH names the "
             "output HTML file (equivalent to --output in this mode; PATH given "
             "here wins if both are supplied).",
    )
    # Transcript-inclusion control (v3.4.0). Tri-state: the flag pair is
    # optional and mutually exclusive; when neither is given the mode default
    # applies (bundle: INCLUDED via lazy shards; single-file: EXCLUDED). Either
    # default is overridable in either direction.
    tx_group = parser.add_mutually_exclusive_group()
    tx_group.add_argument(
        "--transcripts",
        dest="transcripts",
        action="store_true",
        default=None,
        help="Force transcripts INTO the build, overriding the mode default. "
             "In bundle mode this is already the default (writes data/"
             "tx_*.json shards); in single-file mode it restores the full "
             "inline-transcript monolith.",
    )
    tx_group.add_argument(
        "--no-transcripts",
        dest="transcripts",
        action="store_false",
        default=None,
        help="Force transcripts OUT of the build, overriding the mode default. "
             "In bundle mode this writes index.html only (no shards); in "
             "single-file mode it is already the default. Transcript-less "
             "builds carry neither DATA.transcripts nor DATA.transcripts_index, "
             "and the Run Explorer shows a 'transcripts not included' notice.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_paths(args):
    """Return (base_dir, results_dir, datasets_dir, output_path).

    output_path semantics depend on the output mode:
      - Bundle mode (default): output_path is a DIRECTORY. Auto-naming is
        benchmarks/daafbench_YYYY-MM-DD/ (generation date), with a letter
        suffix appended (daafbench_YYYY-MM-DDa, b, ...) whenever the
        candidate already exists — preserving the no-overwrite versioning
        convention the dated viewer_*.html files established.
      - Single-file mode (--single-file): output_path is an HTML FILE.
        Auto-naming keeps the historical viewer_YYYY-MM-DD{letter}.html
        convention (letter starts at 'a' and increments past existing
        same-day files). An optional PATH on --single-file names the file
        directly and wins over --output if both are given.
    Explicit paths (either flag) are used as-is — auto-increment applies
    only to auto-generated names, matching pre-3.0 behavior.
    """
    # The script lives at benchmarks/scripts/generate_results_viewer_v2.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)  # benchmarks/
    results_dir = os.path.join(base_dir, "results")
    datasets_dir = os.path.join(base_dir, "datasets")

    single_file = args.single_file is not None
    explicit = None
    if single_file and isinstance(args.single_file, str):
        explicit = args.single_file
        if args.output:
            print("NOTE: both --single-file PATH and --output were given; "
                  "using the --single-file PATH", file=sys.stderr)
    elif args.output:
        explicit = args.output

    if explicit:
        output_path = explicit
    elif single_file:
        # Auto-generate dated filename with incrementing letter suffix
        date_str = datetime.now().strftime("%Y-%m-%d")
        suffix = 'a'
        while os.path.exists(os.path.join(base_dir, f"viewer_{date_str}{suffix}.html")):
            suffix = chr(ord(suffix) + 1)
        output_path = os.path.join(base_dir, f"viewer_{date_str}{suffix}.html")
    else:
        # Auto-generate dated bundle directory; bare name first, then
        # letter suffixes (a, b, ...) if earlier same-day bundles exist
        date_str = datetime.now().strftime("%Y-%m-%d")
        candidate = os.path.join(base_dir, f"daafbench_{date_str}")
        if os.path.exists(candidate):
            suffix = 'a'
            while os.path.exists(f"{candidate}{suffix}"):
                suffix = chr(ord(suffix) + 1)
            candidate = f"{candidate}{suffix}"
        output_path = candidate

    return base_dir, results_dir, datasets_dir, output_path


# ---------------------------------------------------------------------------
# Phase detection
#
# Adding a new benchmark phase (developer guide):
#   1. Marker: add ONE criterion name unique to the new phase to PHASE_MAP,
#      mapped to (phase_id, label). Markers are matched by exact name against
#      the set of criterion names found in a result set's summary.json (see
#      detect_phase); pick a criterion that appears in every run of the new
#      phase and in no other phase.
#   2. Ordering + label: add the phase_id to PHASE_ORDER (result-set /
#      provenance sort) and to EVAL_GROUP_ORDER (eval-group display order).
#      The label set here flows automatically to the eval group, deep-dive
#      heatmap, per-group callouts, run explorer, and provenance.
#   3. Composite membership: DECIDE whether the new phase joins COMPOSITE_GIDS
#      (defined next to EVAL_GROUP_ORDER). The composite currently has five
#      approved components (P1, P2, P3a, P3b, P4 — user decision 2026-06-10,
#      superseding the original four-component pin; design record: README § 8);
#      adding a component changes leaderboard/tier semantics and requires explicit
#      user approval plus updates to the About-layer scoring prose in
#      viewer_template.html and README.md §§ 6/8. By default a new phase
#      stays OUT of the composite until that approval happens.
#   4. Template prose + JS registries: the About layer's "The benchmark
#      phases" collapsible in viewer_template.html enumerates phases in
#      hand-written prose — add an entry for the new phase. ALSO register the
#      phase in the template's JS lookup maps: GROUP_SHORT (~L2018, short
#      labels), PD_EXPLAINERS (~L3165, deep-dive explainer prose), the
#      eval-group `order` array inside buildEvalGroups() (~L1995) so the new
#      group sorts canonically instead of falling to the unordered tail, AND
#      the About-table case-count wiring: a `phaseSpan` entry (~L2478)
#      mapping the phase_id to an `ab-pX-cases` span id, plus the matching
#      table row in the "The benchmark phases" collapsible (~L1405).
#      (Anchors refreshed 2026-06-13, round-3 post-review fix pass — they
#      had drifted ~+320-425 across the round-3 waves.)
#      Omitting these caused the missing Phase 4 (skill_routing) explainer.
#      (Template edits, not handled in this script; line anchors drift as
#      the template evolves — grep for the identifier names.) Cost vs.
#      Performance bases are built dynamically from the eval groups — no
#      registration needed there. (The Costs Detail section and its phase
#      scope were removed 2026-06-12, user fine-tuning round.)
#   5. Dataset dir: name datasets/<phase_id>/ to match the phase_id so
#      load_cases() attaches case definitions (it falls back to the dirname).
#   6. Regenerate and spot-check the new eval group's k/n in the sanity
#      report and the deep-dive heatmap before publishing.
#   Eval-group derivation note (degenerate-column suppression, v3.5.0 Fix 3):
#   build_eval_groups() (and the lockstep template buildEvalGroups()) emit a
#   column group per distinct rs["phase"], but suppress three degenerate cases
#   so aborted/partial/mid-write sets do not spawn junk columns: (a) phase
#   "unknown" (detect_phase fallback) is skipped; (b) a set with zero loaded
#   runs is skipped; (c) a dispatch_compliance set lacking subagent criterion
#   names is FOLDED into the 3a dispatch group instead of emitting a bare
#   `dispatch_compliance` column. Suppression is column-derivation-scoped: the
#   runs themselves still count in the all-runs aggregates (consistency,
#   per_case, cost, duration). A genuinely new phase whose marker is wired per
#   step 1 will NOT be classified "unknown", so it is unaffected.
#
# Public-prose registries in the template (maintenance guide, added v2.6.0
# with the public-audience evolution of the viewer):
#   - CRIT_LABELS (viewer_template.html JS, next to KNOWN_SCORER_CAVEATS):
#     maps snake_case criterion ids to plain-language labels used in headline
#     prose (deep-dive callouts and the global finding; the hero verdict and
#     the leaderboard Dispatch column that also consumed these were removed
#     in the 2026-06-12 fine-tuning rounds). Forensic surfaces (run explorer, rotated
#     heatmap column headers) keep raw names; heatmap header tooltips append
#     the label. When a new criterion enters the corpus, add a label entry —
#     unlabeled criteria fall back to the snake_case name with underscores
#     replaced by spaces (critLabel()).
#   - Key Takeaways (#takeaways section in the template): DATED hand-written
#     editorial prose whose figures are injected into kt-* spans by
#     fillTakeaways() at init from PRECOMPUTED (composite, consistency, and
#     cost.battery, with relative ratios/multipliers only since v2.8.1). The
#     July-2026 overhaul (v3.7.0) rewrote all five items; fillTakeaways no
#     longer reads composite_hard or per_model_phase. Since v3.7.3 T4 reads
#     the all-perfect consistency `rate` (the leaderboard Consistency metric);
#     the v3.7.0 rate_agree agreement field stays in the payload but has no
#     display consumer.
#     Span contract:
#     28 kt-* spans — 27 in the #takeaways section + kt-foot-bat, which
#     since the 2026-06-12 user fine-tuning round lives in the About Key
#     Caveats cost caveat (the kt-foot paragraph itself was removed; its
#     content was folded into the About caveats). The 27 #takeaways spans
#     (v3.7.0): T1 kt-t1-{fable,opus5,opus5cost,sol,kimi} (5); T2 the six
#     frontier points kt-fr-{gemma,dsflash,luna,sonnet5,sol,fable}-{s,c}
#     (12); T3 kt-t3-{lunapct,lunacost,solpct,solcost,lastmult} (5); T4
#     kt-t4-{topcons,budgetcons} (2, renamed from -{topagree,budgetagree}
#     in v3.7.3 with the switch to the all-perfect rate); T5
#     kt-t5-{glm,glmcost,kimi} (3).
#     History: 22 (21 + kt-foot-bat) from 2026-06-12 through v3.6.x, 29 before
#     the 2026-06-12 e099982 repair pass, 31 originally. Every kt-* span must
#     have a fillTakeaways() setter and every setter a live span; verify
#     both directions when editing either side. Injected numbers track the data
#     automatically; the qualitative claims do NOT — when the corpus changes
#     materially, rewrite the prose and update the date, which lives in the
#     takeaways h2 ("Key Takeaways (Month YYYY)" — the standalone date badge
#     was removed with the kt-disclaimer). Spans default
#     to an em dash, and a model absent from the corpus leaves its spans
#     dashed rather than erroring. Two analogous live-count spans
#     (hero-models, hero-runs) sit in the moved intro paragraphs at the TOP
#     OF #about (hero paragraphs 2-4 moved there verbatim in the 2026-06-12
#     user fine-tuning round; round 2 added the "layers together" remainder
#     of the former hero ¶1 above them): since v3.1.1 their static text is
#     build-time
#     substituted in generate_html() (__HERO_MODELS__ / __HERO_RUNS__
#     tokens), so the no-JS fallback always matches the embedded corpus,
#     and the renderHero() refill from PRECOMPUTED.totals is a
#     belt-and-braces no-op re-writing the same values (previously the
#     static text shipped the prior generation's figures).
#   - Adding a new top-level prose section (the #takeaways recipe): section
#     scaffold in <main>, TOC link in nav#toc-rail, id in SECTION_IDS, and a
#     deliberate decision on the content-visibility CSS rule (above-the-fold
#     static sections stay out — see the CSS comment at the top of the
#     template); register in sectionRenderers only if JS-rendered.
#     (#next-steps, the static closing CTA added 2026-06-12, followed this
#     recipe — and was removed the same day in the user fine-tuning round,
#     exercising the recipe in reverse; its CTA links live on in the hero
#     and About. The #cvp-preview block deliberately does NOT follow the
#     recipe: no TOC link, no SECTION_IDS entry — it sits between the hero
#     and #takeaways (moved above the takeaways in the 2026-06-12
#     fine-tuning round 2; it scrollspy-reads as part of #hero) and renders
#     at init via renderCostPerfPreview().)
#   - Suite naming + hero orientation (2026-06-12 tone percolation; intro
#     restructured later the same day, user fine-tuning round): the page
#     presents this suite as "DAAFBench: Orchestration" — title/og/twitter
#     meta and the moved intro paragraphs at the top of #about carry it,
#     alongside the planned analytic-competency companion suite framing.
#     (The TOC rail title carried it too until fine-tuning round 3 Wave B,
#     when the title became the Learn-page-idiom "On this page" — the
#     suite name now leads the hero h1/eyebrow and the head metadata.)
#     Keep that naming consistent when editing
#     prose. Page-top order is now (fine-tuning rounds 2 + 3B, 2026-06-12):
#     hero (eyebrow "Choosing Your Model" + anatomy-scale h1 + mono
#     breadcrumb date + stat chips + ONE user "TLDR:" paragraph — the first
#     sentence of the user's former hero ¶1, links intact, plus a
#     user-supplied DAAFBench framing sentence; TOC label "Intro"; the
#     computed verdict callout was REMOVED) -> #cvp-preview (compact
#     cost-performance scatter, battery basis, rendered at init) ->
#     #takeaways -> #about, which opens with the "layers together"
#     remainder of the user's former hero ¶1 as its own paragraph, then the
#     user's hero paragraphs 2-4 — all moved VERBATIM (voice anchors —
#     never reword; two recorded exceptions, both user-approved: the
#     Wave B "is a testing suite" typo fix in the TLDR, and the Wave C
#     inputs/outputs framing sentence INSERTED into About ¶3 — an
#     addition with zero changes to pre-existing words. Wave C <b>
#     emphasis wrapping inside the anchors is presentation-only and
#     user-confirmed; the per-anchor comments in the template carry the
#     details). Chip content must stay
#     intuitively meaningful to a zero-context reader (counts and concrete
#     facts, never metric jargon — see renderHero).
#   - Substitution order in generate_html() is load-bearing: the small
#     controlled placeholders (__GENERATED_DISPLAY__, __HERO_MODELS__,
#     __HERO_RUNS__) are filled first, then __PRECOMPUTED_JSON__, with
#     __DATA_JSON__ last, so transcript content can never be treated as
#     a placeholder.
#
# Battery-cost metric (added v2.8.0, dev guide):
#   - New data dependency: benchmarks/derived/openrouter_reconciliation_*.json
#     (latest by filename), produced by scripts/reconcile_openrouter_costs.py
#     from an OpenRouter billing export. It supplies each OpenRouter model's
#     BILLED token mix (prompt/completion per covered run) — the harness's own
#     token counts are Anthropic-tokenizer approximations, not the billing
#     meter, and must not be used for OpenRouter dollar figures. If the file
#     is absent the generator warns and omits OpenRouter battery costs
#     (Anthropic battery costs still compute — fail soft, never fail build).
#   - Metric definition (uncached basis, user-approved 2026-06-11):
#     est_cost_per_run = (input_side x price_input + output_side x
#     price_output) / 1e6 at current models.yaml list rates with NO cache
#     discounts, using each model's own observed per-run token mix.
#     Anthropic input_side = input + cache_read + cache_creation tokens, all
#     at full input rate (uncached counterfactual), aggregated LIVE from
#     corpus result.json in load_runs(); OpenRouter input_side/output_side =
#     billed prompt/completion tokens per covered run from the reconciliation
#     JSON (reasoning tokens are included in completion). battery cost =
#     est_cost_per_run x battery_size, where battery_size = number of
#     distinct case_ids across the loaded corpus (51 on the 2026-06-11
#     corpus: 15 mc + 9 pc + 12 dc + 15 sr — NOT runs/reps, which are uneven
#     across providers).
#   - Cost bases (basis tag on each cost.battery.models entry):
#       * "corpus-live"          — Anthropic, live token mix from result.json
#                                  priced at models.yaml list rates.
#       * "billing-snapshot-DATE" — OpenRouter, billed token mix from the
#                                  reconciliation JSON.
#       * "api-equivalent"       — chatgpt-subscription GPT-5.6 lane (v3.5.0,
#                                  Fix 2). These are NEVER invoiced per token
#                                  (flat subscription), so they carry no
#                                  `pricing:` block; they are priced from
#                                  models.yaml api_equivalent_pricing.
#                                  short_context as an explicit COUNTERFACTUAL
#                                  — the same uncached full-input basis, using
#                                  their live token mix (cache fields absent ->
#                                  0). load_model_pricing tags them
#                                  pricing_basis="api-equivalent"; they clear
#                                  the cost-loop omission via that tag WITHOUT
#                                  flipping billing_grade_cost_eligible (their
#                                  not-invoiced run-detail disclosures stay
#                                  truthful). The leaderboard marks the cost
#                                  cell "api-equiv".
#   - Staleness guard: the reconciliation JSON is a dated billing snapshot.
#     At generation time each OpenRouter model's current corpus run count is
#     compared against the JSON's recorded n_runs; mismatches print a console
#     WARNING (and set stale=true on the embedded entry) but never fail the
#     build. When OpenRouter runs are added to the corpus, re-run
#     reconcile_openrouter_costs.py with a fresh billing export.
#   - Embedding: PRECOMPUTED.cost.battery (per-model est_cost_per_run,
#     est_battery_cost, tokens_per_run, token/cost multipliers vs the
#     reference model, basis tag, staleness fields). "battery" is also a
#     price formulation on cost.models entries + cost.frontiers, so the Cost
#     vs. Performance scatter can use the relative battery cost as its x-axis
#     (template: COST_FORMS registry; the Costs Detail battery table was
#     removed 2026-06-12 — the canonical definition + disclosures now render
#     as the CvP battery-disclosure footnote, batteryDisclosureHtml(), and
#     the published list-price table survives as a collapsible under the
#     same chart, pricingDetailsHtml()). Timeout data is NOT computed: as of
#     v3.3.0 the viewer is timeout-blind — timed-out runs are excluded at load
#     and never presented (no per-model timeout share, no leaderboard column).
#   - Headline promotion (v3.1.0, user decision): the battery multiplier is
#     THE headline cost figure page-wide — the leaderboard cost column, the
#     Cost vs. Performance default axis, the Costs Detail headline table
#     (section since removed, 2026-06-12), and
#     the Key Takeaways cost claims all run on it. Raw input/output $/Mtok
#     list rates remain as secondary detail only (scatter toggles + the Costs
#     Detail published-price table). The blended 3:1 form (blend31, the
#     Artificial Analysis convention) was retired in the same change — the
#     corpus's benchmark cost is dominated by input tokens, so a 3:1 in/out
#     blend misled. Schema note: blend31 no longer exists on cost.models
#     entries or in cost.frontiers; battery is ordered first in both.
#   - Presentation (v2.8.1, user decision): all user-facing battery surfaces
#     (Costs Detail table, the Cost vs. Performance battery axis, the Key
#     Takeaways cost claims) display RELATIVE multipliers vs the reference
#     model (Opus 4.8 = 1.0x), never dollar amounts — exact dollars would
#     imply false precision. The embedded PRECOMPUTED values stay in dollars
#     (est_cost_per_run, est_battery_cost); the template normalizes at render
#     time (fmtMult, renderCostPerf batScale, renderCostsDetail multiplier
#     column, fillTakeaways battery ratios). The console battery table below
#     keeps dollars — it is a maintainer sanity surface, not user-facing.
#
# Bundle architecture (added v3.0.0, dev guide):
#   - The OFFICIAL artifact is a multi-file bundle directory
#     (daafbench_YYYY-MM-DD[suffix]/, auto-incrementing — resolve_paths):
#       index.html              shell + inline DATA (sans transcripts) +
#                               PRECOMPUTED (~4 MB on the 2026-06 corpus)
#       data/tx_{result_set}.json   one transcript shard per result set:
#                               {"transcripts":{...},
#                                "subagent_transcripts":{...}} holding only
#                               that set's entries
#     Rationale: transcripts + subagent_transcripts were 84.6% of the 25 MB
#     monolith and are read ONLY by the template's renderRunDetail; sharding
#     per result set matches the composite "{result_set}/{run_dir}" lookup
#     key (the shard name falls out of the key prefix), gives good fetch
#     sizes (median ~275 KB / max ~1.2 MB per set), and sets are append-only
#     archival units so shards are stable across regenerations. DATA.runs
#     (~3.5 MB) stays inline — every viewer section computes from it.
#   - Shard keys are UNCHANGED — full "{result_set}/{run_dir}" composite
#     form — so the template's lookup code is byte-identical in both modes
#     (no key surgery on either side; see load_transcripts docstring).
#   - In bundle mode DATA drops "transcripts"/"subagent_transcripts" and
#     instead carries "transcripts_index": {result_set: {file: "data/
#     tx_{set}.json", n_main, n_subagent}}. The template feature-detects the
#     artifact shape on DATA.transcripts presence (inline -> synchronous
#     render exactly as pre-3.0; absent -> placeholder + fetch with a
#     memoized shard cache, a stale-click token, and a visible failure
#     fallback). The two keys are mutually exclusive by design so an
#     artifact's mode is unambiguous.
#   - file:// support is DROPPED for bundles (user decision 2026-06-12):
#     fetch() of sibling files is CORS-blocked on file:// origins, so the
#     Run Explorer renders a fallback message with a `python3 -m http.server`
#     hint instead of a transcript. --single-file emits the pre-3.0 monolith
#     (full inline transcripts, viewer_YYYY-MM-DD{letter}.html naming) as
#     the offline/file:// audit path; data prep is fully shared, the modes
#     diverge only at bundle assembly/serialization/write time.
#   - Shard serialization reuses escape_embedded_json: shards are fetched
#     and JSON.parse'd, never seen by the HTML tokenizer, so the \\u003c
#     escaping is not strictly required there — but it is a valid JSON
#     escape, and one serializer everywhere keeps the C1-control-character
#     hygiene without a second code path.
#   - How to regenerate: `python3 benchmarks/scripts/
#     generate_results_viewer_v2.py` writes a fresh bundle dir; add
#     `--single-file` for the monolith. Spot-check the printed bundle
#     report: index.html should sit in the low-single-digit-MB band
#     (~4 MB), shard count should equal the number of loaded result sets
#     (53 on the 2026-06 corpus), and total shard bytes ≈ the old monolith
#     minus index.html (~21 MB). A ballooning index.html means transcript
#     data leaked back inline.
#
# Transcript-inclusion control (added v3.4.0, dev guide):
#   - Three DATA shapes now exist, along a single "does this build carry
#     transcripts, and how" axis (build_data_bundle):
#       (a) inline   — DATA.transcripts + DATA.subagent_transcripts embedded
#                      in full (full single-file monolith).
#       (b) lazy     — DATA.transcripts_index only; per-set shards on disk
#                      (bundle default).
#       (c) none     — NEITHER key present (transcript-lite build).
#     The three are mutually exclusive and the client feature-detects in this
#     exact priority: DATA.transcripts -> inline render; else
#     DATA.transcripts_index -> placeholder + lazy shard fetch; else -> a
#     static "Transcripts not included in this build" notice (renderRunDetail
#     in viewer_template.html). Shape (c) makes NO fetch attempt — there is no
#     index to fetch from — so a transcript-less build cannot 404 or hang.
#   - Per-mode defaults + overrides (parse_args, main):
#       bundle      default INCLUDE (lazy shards)   | --no-transcripts -> none
#       single-file default EXCLUDE (none, v3.4.0)  | --transcripts    -> inline
#     --transcripts / --no-transcripts are a mutually exclusive pair; absent
#     both, the mode default applies. Rationale: the bundle is the official
#     hosted artifact where lazy transcripts cost nothing until a run is
#     opened, so it keeps them; the single-file monolith is the offline/
#     file:// convenience artifact where inlining every transcript is what
#     bloated it to ~25 MB, so it now ships transcript-lite unless explicitly
#     asked for the full monolith. Either default is overridable in either
#     direction in either mode.
#   - When transcripts are excluded, main() SKIPS load_transcripts() entirely
#     (the dominant load-time cost), passes empty dicts, and — in bundle mode —
#     writes no data/ shards. generation_params records transcripts_included
#     for provenance.
#
# Timeout-blindness + duration metric (added v3.3.0, dev guide):
#   - Timeout-blindness (user decision): timed-out runs carry NO gradeable
#     signal, so they are removed entirely — from the data, every metric, and
#     all presentation. The exclusion is a SINGLE chokepoint in load_runs():
#     the harness's explicit timed_out flag is read as a filter key and
#     matching runs are dropped before any run record enters the embedded DATA
#     payload or any precomputed aggregate. Consequences by design:
#       * per_model_phase / composite / consistency / per_case / cost /
#         duration / counts see completed runs only; the existing
#         `if not gruns/cruns` guards naturally skip cells that go empty after
#         exclusion (a set x model pair whose every run timed out simply drops
#         that component and renders via the existing em-dash / rs-na /
#         composite `partial` idioms — no ZeroDivisionError, no new guard).
#       * The disk_run_count census (load_result_sets) stays RAW so the
#         provenance run_count_discrepancy audit still compares on-disk dirs
#         vs summary totals unchanged.
#       * PRECOMPUTED no longer carries timeout_by_model or totals.n_timed_out
#         (their consumers — the leaderboard Timed-out column, the About
#         "Timeouts are still graded" caveat, the Key Takeaways timeout figure
#         — were all removed from the template). The per-load excluded count is
#         a console-only maintainer diagnostic (print_summary), not embedded.
#   - Duration multiplier: a real-world LATENCY proxy mirroring the cost
#     machinery by direct analogy (PRECOMPUTED.duration, shaped like
#     cost.battery): per model, est_duration_per_run = mean duration_s over
#     completed runs; est_battery_duration = per-run x battery_size (the same
#     distinct-case count the cost block uses); duration_multiplier_vs_ref vs
#     BATTERY_REFERENCE_MODEL (Opus 4.8). Built from SUMMED per-run duration_s,
#     which is parallelization-INVARIANT (independent of config.parallel) —
#     never summary.json wall_time_s, a batch clock that depends on run mode.
#     Duration needs no pricing, so it covers ALL models including OpenRouter
#     and the cost-omitted subscription lane (not gated on provider). The
#     template exposes it as a "Relative Duration" leaderboard column and a
#     duration axis on the Cost vs. Performance scatter with its own Pareto
#     frontier (durScale clone of batScale; PRECOMPUTED.duration.frontiers is a
#     SEPARATE block, not a cost.frontiers form, because it covers models the
#     cost block omits). Caveat (folded into the CvP methodology footnote):
#     duration folds in provider routing/congestion — mitigated but not
#     eliminated by multi-rep averaging.
# ---------------------------------------------------------------------------

PHASE_MAP = {
    "orchestrator_skill_loaded": ("mode_classification", "Phase 1 \u2014 Mode Classification"),
    "read_data_onboarding_mode": ("post_confirmation", "Phase 2 \u2014 Post-Confirmation"),
    "agent_dispatched": ("dispatch_compliance", "Phase 3 \u2014 Dispatch Compliance"),
    "required_skills_loaded": ("skill_routing", "Phase 4 \u2014 Skill Routing"),
}


def detect_phase(summary):
    """Detect benchmark phase from criterion names in summary.json."""
    # Collect all criterion names from by_model
    criterion_names = set()
    for model_data in summary.get("by_model", {}).values():
        criterion_names.update(model_data.get("criteria", {}).keys())

    # Remove synthetic "all_criteria" before matching
    criterion_names.discard("all_criteria")

    for marker, (phase_id, phase_label) in PHASE_MAP.items():
        if marker in criterion_names:
            return phase_id, phase_label

    # Fallback: Phase 2 criteria all start with "read_" or "skill_"
    if any(c.startswith("read_") or c.startswith("skill_") for c in criterion_names):
        return "post_confirmation", "Phase 2 \u2014 Post-Confirmation"

    return "unknown", "Unknown Phase"


# ---------------------------------------------------------------------------
# Criteria normalization
# ---------------------------------------------------------------------------

def normalize_criteria(criteria_raw):
    """Normalize criteria from array format to dict keyed by name.

    Phase 1 result.json stores criteria as a dict (already correct).
    Phase 2 and Phase 3 result.json store criteria as an array of objects.
    """
    if isinstance(criteria_raw, dict):
        return criteria_raw
    if isinstance(criteria_raw, list):
        result = {}
        for entry in criteria_raw:
            name = entry.get("name", "unknown")
            result[name] = entry
        return result
    return {}


# ---------------------------------------------------------------------------
# Result set loading
# ---------------------------------------------------------------------------

# Non-phase results-root children that discovery must skip EXPLICITLY rather
# than relying on the implicit "lacks a summary.json" filter below. Two forms
# are excluded (behaviorally equivalent to the corpus-scan idiom used across
# the campaign workspace for the operative `_quarantine*` convention; the exact
# predicates here are `startswith("_")` + the reserved names below):
#   1. Named containers in RESERVED_RESULT_CONTAINERS (exact match):
#        - ``results/probes``      — bounded route-probe CLI output; carries
#          probe.json files, not the manifest.json/summary.json/runs contract.
#        - ``results/removed_runs`` — a holding area for run dirs pulled out of
#          otherwise-kept sets; not a phase result set itself.
#   2. Any child whose name STARTS WITH ``_`` — the operative quarantine
#      convention is ``_quarantine*`` (e.g. ``_quarantine_2026-07-29``), and the
#      leading underscore also covers any other maintainer scratch/staging dir
#      parked at the results root. Underscore-prefixed dirs sort ahead of the
#      ``YYYYMMDD_*`` timestamps and are never valid result-set timestamps, so
#      the prefix test cannot suppress a real set.
# NB: a KEPT result set may contain a ``QUARANTINE_NOTE.md`` at its root (added
# 2026-07-29 to the 8 sets whose individual run dirs were relocated to
# ``removed_runs``). This does NOT affect discovery: a set is recognized solely
# by its ``summary.json`` (and enriched from ``manifest.json``/``runs/``); a
# stray ``.md`` at the set root is simply never consulted. The note is inert.
RESERVED_RESULT_CONTAINERS = frozenset({"probes", "removed_runs"})

PROVENANCE_FIELDS = (
    "route_type", "provider", "endpoint_origin", "backend_mode", "backend",
    "shim_version", "sanitizer_enabled", "sanitizer_condition",
    "auth_store_readable", "reasoning_effort", "text_verbosity", "captured_at",
)
MODEL_IDENTITY_FIELDS = (
    "benchmark_key", "requested_model_id", "claude_cli_model_usage_ids",
    "backend_confirmed_model_id",
)
USAGE_FIELDS = (
    "input_tokens", "input_semantics", "input_includes_cache_tokens",
    "output_tokens", "output_includes_reasoning", "cache_read_tokens",
    "cache_write_tokens", "reasoning_tokens", "max_request_input_tokens",
    "pricing_context_tier", "source", "completeness",
    "incompleteness_reasons",
)
ACTUAL_BILLING_FIELDS = (
    "access_type", "charge_status", "actual_marginal_charge_usd",
)
API_EQUIVALENT_FIELDS = (
    "cost_usd", "calculation_status", "short_context_uncached_scenario_usd",
    "long_context_uncached_scenario_usd", "scenario_assumptions",
    "incompleteness_reasons", "price_source_url",
    "price_schedule_accessed_at", "currency",
    "context_threshold_input_tokens", "context_tier", "not_invoiced",
)
SUBSCRIPTION_CAPACITY_FIELDS = (
    "before", "after", "delta_observed", "credits_calculated",
    "credit_usd_value",
)
CHILD_PURITY_FIELDS = (
    "requested_child_model_id", "observed_child_model_ids_raw",
    "comparison_child_model_ids", "normalization_applied", "comparison_rule",
    "purity_status", "evidence_source", "evidence_boundary",
    "child_transcript_count", "readable_child_transcript_count",
    "incompleteness_reason",
    # Added with the wire_id / non-model-marker purity fix. Archived result.json
    # files are never rewritten, so these read as None for every pre-fix run —
    # _safe_known_mapping already fills missing keys with None and the JS
    # renderer reads named fields, so older payloads render exactly as before.
    "comparison_target_child_model_id", "wire_id_declared",
    "observed_non_model_markers", "non_model_marker_rule",
)


def _read_json_object(path, label):
    """Read one JSON object, reporting malformed/non-object artifacts clearly."""
    try:
        with open(path, "r", encoding="utf-8") as source:
            payload = json.load(source)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: Could not read {label} at {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(payload, dict):
        print(f"WARNING: {label} at {path} is not a JSON object, skipping",
              file=sys.stderr)
        return None
    return payload


def _schema_value(payload):
    """Return a positive integer schema version or None for absent/invalid data."""
    if not isinstance(payload, dict) or "schema_version" not in payload:
        return None
    value = payload.get("schema_version")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def detect_schema_version(manifest=None, summary=None, run=None):
    """Detect schema with manifest > summary > run precedence; absence means v1."""
    for payload in (manifest, summary, run):
        version = _schema_value(payload)
        if version is not None:
            return version
    return 1


def _schema_version_source(manifest=None, summary=None, run=None):
    """Name the source selected by ``detect_schema_version``."""
    for source, payload in (("manifest", manifest), ("summary", summary), ("run", run)):
        if _schema_value(payload) is not None:
            return source
    return "default_absent_version"


def _first_run_payload(result_set_dir):
    """Return the first readable run object for schema fallback detection."""
    runs_dir = os.path.join(result_set_dir, "runs")
    if not os.path.isdir(runs_dir):
        return None
    for run_dirname in sorted(os.listdir(runs_dir)):
        result_path = os.path.join(runs_dir, run_dirname, "result.json")
        if not os.path.isfile(result_path):
            continue
        payload = _read_json_object(result_path, "result.json")
        if payload is not None:
            return payload
    return None


def _optional_rounded_number(value, digits):
    """Round an observed number while preserving explicit zero and missing null."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value, digits)


def _string_list(value):
    """Keep only strings from a known list-valued schema field."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _safe_known_mapping(raw, fields):
    """Copy a fixed scalar/list field set; unknown/raw extras never cross."""
    if not isinstance(raw, dict):
        return None
    safe = {field: raw.get(field) for field in fields}
    for field in (
        "claude_cli_model_usage_ids", "incompleteness_reasons",
        "scenario_assumptions", "observed_child_model_ids_raw",
        "comparison_child_model_ids", "observed_non_model_markers",
    ):
        if field in safe and safe[field] is not None:
            safe[field] = _string_list(safe[field])
    return safe


def _safe_manifest_models(manifest):
    """Return only known, non-secret model registry metadata from a manifest."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("models"), list):
        return []
    safe_models = []
    for entry in manifest["models"]:
        if not isinstance(entry, dict):
            continue
        billing = entry.get("billing") if isinstance(entry.get("billing"), dict) else {}
        safe_models.append({
            "key": entry.get("key"),
            "id": entry.get("id"),
            # Additive: None for archived manifests written before wire_id.
            "wire_id": entry.get("wire_id"),
            "name": entry.get("name"),
            "display_name": entry.get("display_name"),
            "provider": entry.get("provider"),
            "effort_level": entry.get("effort_level"),
            "context_window_tokens": entry.get("context_window_tokens"),
            "actual_billing_treatment": billing.get("actual_billing_treatment"),
        })
    return safe_models


def _safe_count_mapping(raw, known_keys):
    """Copy fixed summary count keys without admitting arbitrary nested extras."""
    if not isinstance(raw, dict):
        return None
    return {key: raw.get(key) for key in known_keys}


def _safe_model_accounting(by_model):
    """Project nullable per-model accounting summaries through a fixed schema."""
    safe = {}
    if not isinstance(by_model, dict):
        return safe
    for model, model_data in by_model.items():
        if not isinstance(model, str) or not isinstance(model_data, dict):
            continue
        safe[model] = {
            "avg_cost_usd": _optional_rounded_number(
                model_data.get("avg_cost_usd"), 12
            ),
            "accounting_coverage": _safe_count_mapping(
                model_data.get("accounting_coverage"),
                ("exact", "scenario_only", "unavailable", "legacy_numeric"),
            ),
            "purity_coverage": _safe_count_mapping(
                model_data.get("purity_coverage"),
                ("verified", "failed", "unverifiable"),
            ),
        }
    return safe


def _cost_compatibility(providers):
    """Classify whether legacy billing-grade cost surfaces are compatible."""
    provider_set = {provider for provider in providers if isinstance(provider, str) and provider}
    if "chatgpt-subscription" in provider_set:
        return False, "subscription_access_api_equivalent_is_counterfactual_not_invoiced"
    return True, None


def load_result_sets(results_dir, filter_timestamps=None, exclude_timestamps=None):
    """Discover normal phase result sets, excluding separately shaped containers."""
    result_sets = []

    if not os.path.isdir(results_dir):
        print(f"ERROR: Results directory not found: {results_dir}", file=sys.stderr)
        return result_sets

    discovered_dirs = sorted([
        d for d in os.listdir(results_dir)
        if os.path.isdir(os.path.join(results_dir, d)) and not d.startswith(".")
    ])
    # Explicit non-phase skip (see RESERVED_RESULT_CONTAINERS comment): named
    # reserved containers OR any underscore-prefixed dir (the `_quarantine*`
    # convention plus other maintainer scratch/staging). Both are excluded up
    # front rather than left to the implicit "no summary.json" filter, so a
    # quarantine container that happens to acquire a summary-shaped file can
    # never leak into the corpus.
    skipped_present = [
        d for d in discovered_dirs
        if d in RESERVED_RESULT_CONTAINERS or d.startswith("_")
    ]
    for dirname in skipped_present:
        kind = ("reserved container" if dirname in RESERVED_RESULT_CONTAINERS
                else "quarantine/underscore container")
        print(f"NOTE: Ignoring non-phase results {kind}: {dirname}",
              file=sys.stderr)
    all_timestamps = [
        d for d in discovered_dirs
        if d not in RESERVED_RESULT_CONTAINERS and not d.startswith("_")
    ]

    if filter_timestamps:
        timestamps = [t for t in all_timestamps if t in filter_timestamps]
        missing = sorted(set(filter_timestamps) - set(timestamps))
        if missing:
            print(f"WARNING: Result sets not found or not phase result sets: {missing}",
                  file=sys.stderr)
    else:
        timestamps = all_timestamps

    # Exclusion filter (--exclude-results): applied after inclusion so the
    # two flags compose predictably. Useful for dropping known-contaminated
    # sets without enumerating every other set via --results.
    if exclude_timestamps:
        exclude_set = set(exclude_timestamps)
        not_on_disk = sorted(exclude_set - set(all_timestamps))
        if not_on_disk:
            print(f"WARNING: --exclude-results sets not found: {not_on_disk}",
                  file=sys.stderr)
        excluded_here = [t for t in timestamps if t in exclude_set]
        if excluded_here:
            print(f"Excluding result sets: {', '.join(excluded_here)}")
        timestamps = [t for t in timestamps if t not in exclude_set]

    for ts in timestamps:
        ts_dir = os.path.join(results_dir, ts)
        summary_path = os.path.join(ts_dir, "summary.json")
        if not os.path.isfile(summary_path):
            print(f"WARNING: No summary.json in {ts_dir}, skipping", file=sys.stderr)
            continue
        summary = _read_json_object(summary_path, "summary.json")
        if summary is None:
            continue

        phase_id, phase_label = detect_phase(summary)

        # Load manifest.json (run provenance: git SHA + run configuration).
        # Older/partial result sets may lack it; run/summary loading remains valid.
        manifest = None
        daaf_git_sha = None
        manifest_config = None
        manifest_path = os.path.join(ts_dir, "manifest.json")
        if os.path.isfile(manifest_path):
            manifest = _read_json_object(manifest_path, "manifest.json")
            if manifest is not None:
                sha = manifest.get("daaf_git_sha")
                daaf_git_sha = sha[:12] if isinstance(sha, str) and sha else None
                cfg = manifest.get("config", {})
                if isinstance(cfg, dict):
                    manifest_config = {
                        "reps": cfg.get("reps"),
                        "parallel": cfg.get("parallel"),
                        "launch_delay_s": cfg.get("launch_delay_s"),
                        "timeout_override": cfg.get("timeout_override"),
                        "test_ids": cfg.get("test_ids"),
                        "model_keys": cfg.get("model_keys"),
                    }
        else:
            print(f"WARNING: No manifest.json in {ts_dir}", file=sys.stderr)

        # Count run directories actually on disk (those with a result.json).
        disk_run_count = 0
        runs_dir = os.path.join(ts_dir, "runs")
        if os.path.isdir(runs_dir):
            for run_dirname in os.listdir(runs_dir):
                if os.path.isfile(os.path.join(runs_dir, run_dirname, "result.json")):
                    disk_run_count += 1

        first_run = _first_run_payload(ts_dir)
        schema_version = detect_schema_version(manifest, summary, first_run)
        schema_source = _schema_version_source(manifest, summary, first_run)
        manifest_models = _safe_manifest_models(manifest)
        providers = sorted({
            entry["provider"] for entry in manifest_models
            if isinstance(entry.get("provider"), str) and entry["provider"]
        })
        billing_eligible, billing_reason = _cost_compatibility(providers)

        by_model = summary.get("by_model", {})
        if not isinstance(by_model, dict):
            by_model = {}
        models = sorted(by_model.keys())

        criterion_names = set()
        for model_data in by_model.values():
            if not isinstance(model_data, dict):
                continue
            criteria = model_data.get("criteria", {})
            if not isinstance(criteria, dict):
                continue
            for cname in criteria:
                if cname != "all_criteria":
                    criterion_names.add(cname)
        criterion_names = sorted(criterion_names)

        subagent_criterion_names = []
        subagent_behavior = summary.get("subagent_behavior")
        if isinstance(subagent_behavior, dict):
            names = subagent_behavior.get("criterion_names", [])
            if isinstance(names, list):
                subagent_criterion_names = [name for name in names if isinstance(name, str)]

        result_set = {
            "timestamp": ts,
            "phase": phase_id,
            "phase_label": phase_label,
            "schema_version": schema_version,
            "schema_version_source": schema_source,
            "schema_classification": (
                "schema_v2" if schema_version >= 2 else "legacy_schema_v1"
            ),
            "legacy_schema": schema_version < 2,
            "total_runs": summary.get("total_runs", 0),
            "errored_runs": summary.get("errored_runs", 0),
            "total_cost_usd": _optional_rounded_number(
                summary.get("total_cost_usd"), 3
            ),
            "wall_time_s": _optional_rounded_number(summary.get("wall_time_s"), 1),
            "accounting_coverage": _safe_count_mapping(
                summary.get("accounting_coverage"),
                ("exact", "scenario_only", "unavailable", "legacy_numeric"),
            ),
            "purity_coverage": _safe_count_mapping(
                summary.get("purity_coverage"),
                ("verified", "failed", "unverifiable"),
            ),
            "models": models,
            "model_metadata": manifest_models,
            "model_accounting": _safe_model_accounting(by_model),
            "providers": providers,
            "billing_grade_cost_eligible": billing_eligible,
            "billing_grade_cost_exclusion_reason": billing_reason,
            "criterion_names": criterion_names,
            "subagent_criterion_names": subagent_criterion_names,
            # Provenance (manifest + on-disk ground truth)
            "daaf_git_sha": daaf_git_sha,
            "config": manifest_config,
            "disk_run_count": disk_run_count,
            "summary_total_runs": summary.get("total_runs", 0),
            # Partial-pass disclosure (progressive-archiving redesign, 2026-07).
            # A summary is `partial` while a pass is mid-flight or was killed
            # before completing; runs_expected/runs_completed make the shortfall
            # legible. Fields absent on pre-redesign archives default to complete.
            "partial": bool(summary.get("partial", False)),
            "runs_expected": summary.get("runs_expected"),
            "runs_completed": summary.get(
                "runs_completed", summary.get("total_runs", 0)
            ),
            # Aggregate hook-block vs tool-failure diagnostic counters (additive;
            # None on archives predating the field).
            "error_counts": summary.get("error_counts"),
        }
        result_sets.append(result_set)

    return result_sets


# ---------------------------------------------------------------------------
# Case definitions loading
# ---------------------------------------------------------------------------

def load_cases(datasets_dir):
    """Load case definitions from all datasets/*/cases.jsonl files."""
    cases = {}

    if not os.path.isdir(datasets_dir):
        print(f"WARNING: Datasets directory not found: {datasets_dir}", file=sys.stderr)
        return cases

    for dirname in sorted(os.listdir(datasets_dir)):
        cases_path = os.path.join(datasets_dir, dirname, "cases.jsonl")
        if not os.path.isfile(cases_path):
            continue

        # Dataset directory names ARE the phase IDs (see developer guide
        # step 5 above) — no mapping table needed.
        phase = dirname

        with open(cases_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                case = json.loads(line)
                case_id = case.get("id", "unknown")
                case["phase"] = phase
                cases[case_id] = case

    return cases


# ---------------------------------------------------------------------------
# Run loading
# ---------------------------------------------------------------------------

def _classify_tier(crit_name, crit_entry, case):
    """Classify a criterion as 'hard' or 'soft'.

    - If the criterion entry already has a 'tier' field (Phase 2/3), map it:
        tier1 -> hard, tier2 -> soft, info -> None (skip)
    - Otherwise (Phase 1), look up the case's hard_requirements list.
        Present in hard_requirements -> hard, otherwise -> soft.
        If no hard_requirements list exists, default to hard.
    """
    raw_tier = crit_entry.get("tier") if isinstance(crit_entry, dict) else None
    if raw_tier is not None:
        tier_map = {"tier1": "hard", "tier2": "soft", "info": None}
        return tier_map.get(raw_tier, "hard")

    # No explicit tier — use the case's hard_requirements list
    if case is None:
        return "hard"
    hard_reqs = case.get("hard_requirements", None)
    if hard_reqs is None:
        return "hard"
    return "hard" if crit_name in hard_reqs else "soft"


def _enrich_criteria_with_tiers(criteria, case):
    """Add a 'tier' field to each criterion entry in-place."""
    for crit_name, entry in criteria.items():
        if not isinstance(entry, dict):
            entry = {"passed": bool(entry)}
            criteria[crit_name] = entry
        tier = _classify_tier(crit_name, entry, case)
        if tier is None:
            # 'info' tier — keep but mark as info so JS can ignore
            entry["tier"] = "info"
        else:
            entry["tier"] = tier


def compute_grade(criteria):
    """Compute the grade status of a criteria dict.

    Status taxonomy (orthogonal to the timed_out flag — timed-out runs are
    often fully graded and must never be treated as ungraded):
      perfect  — all criteria passed
      partial  — some, but not all, criteria passed
      failed   — no criteria passed
      ungraded — no criteria present

    All criterion entries are counted (matching the Perfect-rate semantics of
    the v1 viewer's allCriteriaPassed/runStatus); no info-tier criteria exist
    in the current corpus.
    """
    if not criteria:
        return "ungraded"
    total = len(criteria)
    passed = sum(
        1 for entry in criteria.values()
        if isinstance(entry, dict) and entry.get("passed")
    )
    if passed == total:
        return "perfect"
    if passed == 0:
        return "failed"
    return "partial"


def load_runs(results_dir, result_sets, cases):
    """Load all result.json files for each result set.

    Timed-out runs (the harness's explicit timed_out flag) are excluded at a
    single chokepoint as each result.json is read: they carry no gradeable
    signal, so they never enter the returned runs list, the embedded DATA
    payload, or any precomputed aggregate. The on-disk disk_run_count census
    (load_result_sets) is a separate earlier pass and stays raw for the
    provenance discrepancy audit.

    Returns (runs, anth_token_totals, n_timed_out_excluded).
    anth_token_totals aggregates raw
    token counts per Anthropic-provider model — {model: {n, input, output,
    cache_read, cache_creation}} — for the battery-cost metric (see the
    "Battery-cost metric" dev guide above PHASE_MAP). Aggregated here, in
    the same pass that reads every result.json, so per-run token counts
    still are NOT embedded in the data bundle (see the comment on the run
    dict below); only per-model means reach the viewer. Anthropic counts
    come from the provider's own usage meter, so they are billing-grade;
    OpenRouter counts are Anthropic-tokenizer approximations and are
    deliberately NOT aggregated here — OpenRouter battery costs come from
    the billing reconciliation JSON instead.
    """
    runs = []
    anth_token_totals = {}
    n_timed_out_excluded = 0

    for rs in result_sets:
        ts = rs["timestamp"]
        runs_dir = os.path.join(results_dir, ts, "runs")

        if not os.path.isdir(runs_dir):
            print(f"WARNING: No runs directory in {ts}", file=sys.stderr)
            continue

        for run_dirname in sorted(os.listdir(runs_dir)):
            result_path = os.path.join(runs_dir, run_dirname, "result.json")
            if not os.path.isfile(result_path):
                continue

            result = _read_json_object(result_path, "result.json")
            if result is None:
                continue

            case_id = result.get("case_id", "")
            case = cases.get(case_id)

            # Normalize criteria
            criteria = normalize_criteria(result.get("criteria", {}))
            _enrich_criteria_with_tiers(criteria, case)

            # Normalize subagent_criteria (Phase 3 only)
            subagent_criteria = None
            if "subagent_criteria" in result and result["subagent_criteria"]:
                subagent_criteria = normalize_criteria(result["subagent_criteria"])
                # Subagent criteria default to soft unless explicit tier
                for sc_name, sc_entry in subagent_criteria.items():
                    if not isinstance(sc_entry, dict):
                        sc_entry = {"passed": bool(sc_entry)}
                        subagent_criteria[sc_name] = sc_entry
                    raw_tier = sc_entry.get("tier")
                    if raw_tier:
                        tier_map = {"tier1": "hard", "tier2": "soft", "info": "info"}
                        sc_entry["tier"] = tier_map.get(raw_tier, "soft")
                    else:
                        sc_entry["tier"] = "soft"

            provider = result.get("provider")
            if not isinstance(provider, str) or not provider:
                provider = next((
                    entry.get("provider") for entry in rs.get("model_metadata", [])
                    if entry.get("name") == result.get("model")
                    or entry.get("id") == result.get("model_id")
                ), None)
            schema_version = rs.get("schema_version", 1)
            billing_eligible, billing_reason = _cost_compatibility([provider])

            usage_observed = _safe_known_mapping(
                result.get("usage_observed"), USAGE_FIELDS
            )
            # cli_model_usage is intentionally not passed through. It is a
            # variable-key executor structure; the fixed nullable category totals
            # above and allowlisted model-identity IDs are the viewer contract.
            model_identity = _safe_known_mapping(
                result.get("model_identity"), MODEL_IDENTITY_FIELDS
            )
            provenance = _safe_known_mapping(
                result.get("provenance"), PROVENANCE_FIELDS
            )
            actual_billing = _safe_known_mapping(
                result.get("actual_billing"), ACTUAL_BILLING_FIELDS
            )
            api_equivalent = _safe_known_mapping(
                result.get("api_equivalent"), API_EQUIVALENT_FIELDS
            )
            subscription_capacity = _safe_known_mapping(
                result.get("subscription_capacity"), SUBSCRIPTION_CAPACITY_FIELDS
            )
            child_model_purity = _safe_known_mapping(
                result.get("child_model_purity"), CHILD_PURITY_FIELDS
            )

            run = {
                "result_set": ts,
                "schema_version": schema_version,
                "schema_classification": (
                    "schema_v2" if schema_version >= 2 else "legacy_schema_v1"
                ),
                "legacy_schema": schema_version < 2,
                "case_id": case_id,
                "model": result.get("model", ""),
                "model_id": result.get("model_id"),
                "provider": provider,
                "route_type": provenance.get("route_type") if provenance else None,
                "rep": result.get("rep", 0),
                "session_id": result.get("session_id", ""),
                "turns": result.get("turns", 0),
                # Legacy computed cost stays available only as archived evidence.
                # It is never populated from API-equivalent exact/scenario values.
                "computed_cost_usd": _optional_rounded_number(
                    result.get("computed_cost_usd"), 12
                ),
                "billing_grade_cost_eligible": billing_eligible,
                "billing_grade_cost_exclusion_reason": billing_reason,
                "duration_s": _optional_rounded_number(result.get("duration_s"), 3),
                # Time-to-demonstrated-compliance for early-stopped runs (launch
                # -> first score-complete pass, excluding the confirmation/kill
                # tail). Substituted for duration_s in duration/latency aggregates
                # when a completed_early run carries it; None (excluded) otherwise.
                # None on archives predating the field.
                "score_complete_seconds": _optional_rounded_number(
                    result.get("score_complete_seconds"), 3
                ),
                "error": result.get("error", None),
                # Run lifecycle status. Dispatch B (executor-side watchdog) will
                # emit "completed_early" for early-stopped runs; these substitute
                # score_complete_seconds into duration/latency aggregates when
                # present (else are excluded, as their wall time is truncated and
                # not comparable) while their scores count normally. None on
                # archives predating the field.
                "status": result.get("status"),
                # Additive hook-block vs tool-failure diagnostic counters
                # (None on archives predating the error_counts field).
                "error_counts": result.get("error_counts"),
                # Phase 1 only (None elsewhere)
                "expected_mode": result.get("expected_mode"),
                # Phase 2/3 only (None elsewhere)
                "subcategory": result.get("subcategory"),
                # Phase 2/3 only (None on Phase 1 result.json)
                "tool_call_count": result.get("tool_call_count"),
                # Grade status computed from main criteria (see compute_grade)
                "grade": compute_grade(criteria),
                "criteria": criteria,
                "subagent_criteria": subagent_criteria,
                "provenance": provenance,
                "model_identity": model_identity,
                "usage_observed": usage_observed,
                "actual_billing": actual_billing,
                "api_equivalent": api_equivalent,
                "subscription_capacity": subscription_capacity,
                "child_model_purity": child_model_purity,
                # Carried through in full, including each entry's `content`
                # string — surfaced in the run detail view
                "tool_failures": result.get("tool_failures", []),
                "run_dir": run_dirname,
            }
            # --- No-gradeable-signal exclusion chokepoint (v3.3.0; status
            #     taxonomy extended v3.4.0) ---
            # Runs that carry no gradeable signal are dropped HERE — before any
            # run record enters the embedded DATA payload or ANY precomputed
            # aggregate (per_model_phase, composite, consistency, per_case,
            # cost/duration, counts). Two exclusion keys, both watchdog/harness
            # facts (never a string-match on `error`):
            #   1. `timed_out` — the harness's explicit legacy timeout flag.
            #   2. `status` in the run-lifecycle taxonomy (README § 3, post
            #      2026-07-28): "stalled" (watchdog-killed hang — wall time is a
            #      kill artifact, scores are truncated/absent) and "timed_out"
            #      (the new-taxonomy spelling of the same terminal timeout).
            #      Both are excluded exactly like a legacy timed-out run; without
            #      this a `status="stalled"`/`"timed_out"` record whose legacy
            #      `timed_out` flag is unset (newer archives) would slip past
            #      leg 1 and pollute the metrics. "completed" and
            #      "completed_early" are normal completions and are KEPT
            #      (completed_early is score-neutral — README § 3); None status
            #      (archives predating the field) is also kept and governed by
            #      leg 1 alone.
            # These keys are read ONLY as filter keys; the exclusion count is a
            # console-only maintainer diagnostic. The disk census that feeds the
            # provenance run_count_discrepancy check (load_result_sets ->
            # disk_run_count) runs in a separate earlier pass and is left RAW, so
            # the discrepancy audit still sees every on-disk run. Because runs
            # are filtered here, the downstream `if not gruns/cruns` guards
            # naturally skip cells that are empty after exclusion — no extra
            # empty-cell guard is needed.
            run_status = result.get("status")
            if bool(result.get("timed_out", False)) or run_status in ("stalled", "timed_out"):
                n_timed_out_excluded += 1
                continue
            # --- Legacy instant-exit stub exclusion (v3.6.1; 2026-07-29
            #     instant-exit corpus audit) ---
            # A legacy-schema record (schema_version < 2, so status predates the
            # field and is null) with BOTH top-level output_tokens null AND error
            # null is an instant-exit stub: it exited in ~2s having produced no
            # model output and locked 0/N criteria, yet its unset legacy
            # timed_out flag lets it slip past leg 1 above and pollute rep counts
            # and score averages. This mirrors the corpus parity scan's legacy
            # screen (research 2026-07-18 StaticAudit,
            # scratch/11_corpus-parity-scan_a.py L62-65), narrowed to the pure
            # stub signature. Three deliberate narrowings:
            #   - The `legacy_schema` gate scopes this to schema-v1 records,
            #     whose token counts live in TOP-LEVEL flat fields. Schema-v2
            #     records carry tokens nested under usage_observed (top-level
            #     output_tokens is legitimately null for them, e.g. the
            #     chatgpt-subscription lane), so they must NOT be screened here —
            #     the audit found zero stub divergences in new-taxonomy records.
            #   - The `error` clause keeps an errored legacy null-output run
            #     (a real failure signal), unchanged from prior behavior.
            #   - `status is None` is faithful to the "legacy record" definition
            #     and is implied by legacy_schema, but stated for clarity.
            # A per-run stderr NOTE keeps exclusions visible.
            if (
                run["legacy_schema"]
                and run_status is None
                and result.get("output_tokens") is None
                and not result.get("error")
            ):
                n_timed_out_excluded += 1
                print(
                    f"NOTE: excluding legacy instant-exit stub "
                    f"({run['model']} / {case_id} / rep {result.get('rep', 0)} / "
                    f"{ts}/{run_dirname}): status null, not timed out, no error, "
                    f"output_tokens null. See 2026-07-29 instant-exit audit.",
                    file=sys.stderr,
                )
                continue
            runs.append(run)

            # Battery-cost token aggregation (Anthropic provider only; see
            # docstring). Timed-out runs never reach this point (excluded at the
            # chokepoint above, v3.3.0; the metric already excluded them since
            # v3.1.2). Schema-v1 keeps its historical flat-field zero fallback
            # byte-for-byte so published battery calculations do not change. For
            # schema-v2, missing categories make the run ineligible for this
            # billing-grade token mix; explicit source zero remains valid
            # evidence.
            # Providers whose per-run token mix feeds the battery-cost block.
            # "anthropic" mixes are priced corpus-live at list rates; the
            # "chatgpt-subscription" GPT-5.6 lane (v3.5.0, Fix 2) is priced on
            # the api-equivalent counterfactual basis (load_model_pricing). The
            # subscription lane carries no cache accounting, so its result.json
            # records input_tokens/output_tokens with cache fields None —
            # coerced to 0 below so the run stays eligible under the same
            # uncached (full input rate) basis used everywhere.
            if run["provider"] in ("anthropic", "chatgpt-subscription"):
                if run["legacy_schema"]:
                    token_values = {
                        "input": result.get("input_tokens", 0) or 0,
                        "output": result.get("output_tokens", 0) or 0,
                        "cache_read": result.get("cache_read_tokens", 0) or 0,
                        "cache_creation": result.get("cache_creation_tokens", 0) or 0,
                    }
                else:
                    token_values = {
                        "input": result.get("input_tokens"),
                        "output": result.get("output_tokens"),
                        "cache_read": result.get("cache_read_tokens"),
                        "cache_creation": result.get("cache_creation_tokens"),
                    }
                if run["provider"] == "chatgpt-subscription":
                    # None-tolerant cache fields: the subscription lane reports
                    # no cache read/creation, so treat missing as explicit 0.
                    for _cache_field in ("cache_read", "cache_creation"):
                        if token_values[_cache_field] is None:
                            token_values[_cache_field] = 0
                if all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in token_values.values()
                ):
                    agg = anth_token_totals.setdefault(run["model"], {
                        "n": 0, "input": 0, "output": 0,
                        "cache_read": 0, "cache_creation": 0,
                    })
                    agg["n"] += 1
                    for field, value in token_values.items():
                        agg[field] += value

    # Manifest metadata is preferred, but run data can feature-detect providers
    # in older/partial sets. This mutates only the in-memory viewer projection.
    runs_by_set = {}
    for run in runs:
        runs_by_set.setdefault(run["result_set"], []).append(run)
    for rs in result_sets:
        providers = set(rs.get("providers", []))
        providers.update(
            run["provider"] for run in runs_by_set.get(rs["timestamp"], [])
            if isinstance(run.get("provider"), str) and run["provider"]
        )
        rs["providers"] = sorted(providers)
        eligible, reason = _cost_compatibility(providers)
        rs["billing_grade_cost_eligible"] = eligible
        rs["billing_grade_cost_exclusion_reason"] = reason

    return runs, anth_token_totals, n_timed_out_excluded


# ---------------------------------------------------------------------------
# Transcript condensation
# ---------------------------------------------------------------------------

def _strip_nonprintable(text):
    """Remove non-printable characters that break HTML/JS embedding.

    Transcript content can contain raw binary data (e.g., corrupted tool output)
    with control characters (U+007F-U+009F, U+0000-U+0008, etc.) that json.dumps
    does not escape. These literal bytes in <script> blocks break browser parsing.
    """
    return "".join(ch for ch in text if ch >= " " or ch in "\n\r\t")


def _truncate_content(text, max_chars=2000):
    """Truncate content to max_chars, adding a truncation marker if needed."""
    text = _strip_nonprintable(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, {len(text):,} chars total]"


def _is_system_injected(text):
    """Detect system-injected content (skill loads, system reminders).

    These appear as user text blocks but are actually framework content
    injected by the harness. They are huge (40KB+) and not diagnostic.
    """
    prefixes = (
        "Base directory for this skill:",
        "<system-reminder>",
        "Contents of /",
    )
    for prefix in prefixes:
        if text.strip().startswith(prefix):
            return True
    return False


def condense_transcript(jsonl_path):
    """Parse a transcript.jsonl and extract a condensed conversation view.

    Returns a list of message dicts with roles:
      user, assistant, tool_call, tool_result

    Content is truncated to keep condensed transcripts under ~10KB each:
      - User/assistant text: max 2000 chars
      - System-injected content (skills, reminders): max 200 chars
      - Tool call args: max 200 chars
      - Tool result output: max 500 chars
    """
    messages = []

    if not os.path.isfile(jsonl_path):
        return messages

    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type", "")

            # Skip non-conversation entries
            if entry_type in ("queue-operation", "attachment", "last-prompt",
                              "deferred_tools_delta", "skill_listing"):
                continue

            if entry_type == "user":
                msg = entry.get("message", {})
                content = msg.get("content", "")

                if isinstance(content, str):
                    # Simple text user message
                    text = content.strip()
                    if text:
                        if _is_system_injected(text):
                            messages.append({
                                "role": "system",
                                "content": _truncate_content(text, 200),
                            })
                        else:
                            messages.append({
                                "role": "user",
                                "content": _truncate_content(text),
                            })
                elif isinstance(content, list):
                    # Content blocks — may contain tool_result blocks
                    for block in content:
                        block_type = block.get("type", "")
                        if block_type == "tool_result":
                            tool_use_id = block.get("tool_use_id", "")
                            block_content = block.get("content", "")
                            # Determine status from is_error field or content
                            is_error = block.get("is_error", False)
                            status = "error" if is_error else "success"
                            output = _strip_nonprintable(str(block_content)[:500]) if block_content else ""
                            # Try to find the tool name from a previous tool_call
                            tool_name = _find_tool_name(messages, tool_use_id)
                            messages.append({
                                "role": "tool_result",
                                "tool": tool_name or tool_use_id[:20],
                                "status": status,
                                "output": output,
                            })
                        elif block_type == "text":
                            text = block.get("text", "").strip()
                            if text:
                                if _is_system_injected(text):
                                    messages.append({
                                        "role": "system",
                                        "content": _truncate_content(text, 200),
                                    })
                                else:
                                    messages.append({
                                        "role": "user",
                                        "content": _truncate_content(text),
                                    })

            elif entry_type == "assistant":
                msg = entry.get("message", {})
                content = msg.get("content", [])

                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        block_type = block.get("type", "")
                        if block_type == "text":
                            text_parts.append(block.get("text", ""))
                        elif block_type == "tool_use":
                            # Emit any accumulated text first
                            if text_parts:
                                combined = "\n".join(text_parts).strip()
                                if combined:
                                    messages.append({
                                        "role": "assistant",
                                        "content": _truncate_content(combined),
                                    })
                                text_parts = []
                            # Emit tool call
                            tool_name = block.get("name", "unknown")
                            tool_id = block.get("id", "")
                            tool_input = block.get("input", {})
                            args_str = json.dumps(tool_input) if tool_input else ""
                            messages.append({
                                "role": "tool_call",
                                "tool": tool_name,
                                "tool_id": tool_id,
                                "args": _strip_nonprintable(args_str[:200]),
                            })
                        # Skip thinking, redacted_thinking blocks

                    # Emit remaining text
                    if text_parts:
                        combined = "\n".join(text_parts).strip()
                        if combined:
                            messages.append({
                                "role": "assistant",
                                "content": _truncate_content(combined),
                            })

                elif isinstance(content, str):
                    text = content.strip()
                    if text:
                        messages.append({
                            "role": "assistant",
                            "content": _truncate_content(text),
                        })

    return messages


def _find_tool_name(messages, tool_use_id):
    """Look backwards through messages for a tool_call with matching tool_id."""
    if not tool_use_id:
        return None
    for msg in reversed(messages):
        if msg.get("role") == "tool_call" and msg.get("tool_id") == tool_use_id:
            return msg.get("tool")
    return None


def load_transcripts(results_dir, runs):
    """Condense transcripts for all runs.

    Returns:
        transcripts: dict keyed by "{result_set}/{run_dir}" -> condensed message list
        subagent_transcripts: dict keyed by "{result_set}/{run_dir}" -> dict of
            agent_id -> messages

    Keying (v2.7.0 fix): both dicts are namespaced by result set because run
    directory names (e.g. "dc-08_Gemma_4_26B_0") are only unique WITHIN a
    result set. Bare run_dir keys silently overwrote main transcripts across
    sets (last-loaded set won) and displayed another set's subagent transcript
    on same-named runs (482 colliding names / 1,339 transcript-bearing run
    instances on the 2026-06-11 52-set corpus; the composite keying recovered
    857 main transcripts that bare keys had been dropping). The template's
    lookups in renderRunDetail()
    mirror this composite key exactly (DATA.transcripts[r.result_set+"/"+
    r.run_dir]); the two sides must stay in lockstep. Bundle artifacts
    (v3.0.0) ship these dicts split into per-result-set shards with the SAME
    full composite keys, so the template lookup is identical in both modes —
    see the "Bundle architecture" dev guide above PHASE_MAP.
    """
    transcripts = {}
    subagent_transcripts = {}

    for run in runs:
        ts = run["result_set"]
        run_dir = run["run_dir"]
        run_path = os.path.join(results_dir, ts, "runs", run_dir)
        # Composite key: run_dir alone collides across result sets (see
        # docstring) — must match the template's lookup key construction
        key = f"{ts}/{run_dir}"

        # Main transcript
        transcript_path = os.path.join(run_path, "transcript.jsonl")
        condensed = condense_transcript(transcript_path)
        if condensed:
            transcripts[key] = condensed

        # Subagent transcripts (Phase 3)
        # Cap string values at 200 chars — subagent transcripts can contain
        # corrupted binary data (e.g., garbled tool output from failed runs)
        # that breaks HTML/JS embedding regardless of escaping
        subagent_dir = os.path.join(run_path, "subagents")
        if os.path.isdir(subagent_dir):
            agent_transcripts = {}
            for fname in sorted(os.listdir(subagent_dir)):
                if fname.endswith(".jsonl"):
                    agent_id = fname.replace(".jsonl", "")
                    agent_path = os.path.join(subagent_dir, fname)
                    agent_condensed = condense_transcript(agent_path)
                    if agent_condensed:
                        agent_transcripts[agent_id] = agent_condensed

            if agent_transcripts:
                subagent_transcripts[key] = agent_transcripts

    return transcripts, subagent_transcripts


# ---------------------------------------------------------------------------
# Model pricing loading
# ---------------------------------------------------------------------------

def load_model_pricing(base_dir):
    """Load per-token pricing from config/models.yaml.

    Returns a dict keyed by model name (matching run.model) with per-million
    token rates for input, output, and cached_input.
    """
    config_path = os.path.join(base_dir, "config", "models.yaml")
    if not os.path.isfile(config_path):
        print(f"WARNING: models.yaml not found at {config_path}", file=sys.stderr)
        return {}

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    pricing = {}
    for entry in config.get("models", []):
        name = entry.get("name")
        if not name:
            continue
        provider = entry.get("provider", "anthropic")
        if provider == "chatgpt-subscription":
            # API-equivalent counterfactual pricing (v3.5.0, Fix 2). These
            # GPT-5.6 models are accessed under a flat ChatGPT subscription and
            # are NEVER invoiced per token, so no `pricing:` block exists.
            # Price them at the published api_equivalent_pricing.short_context
            # list rates as an explicit counterfactual — mirroring how the
            # Anthropic subscription models are already priced at list rates.
            # These entries carry pricing_basis="api-equivalent" so the battery
            # block tags them a distinct basis and the leaderboard marks them
            # api-equiv (vs the Anthropic corpus-live basis). NB: the schedule
            # lives at entry["api_equivalent_pricing"]["short_context"], NOT
            # under a `billing:` wrapper.
            aep = entry.get("api_equivalent_pricing", {})
            sc = aep.get("short_context", {}) if isinstance(aep, dict) else {}
            if not isinstance(sc, dict):
                continue
            input_rate = sc.get("input")
            output_rate = sc.get("output")
            cached_rate = sc.get("cached_input")
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in (input_rate, output_rate)
            ):
                continue
            pricing[name] = {
                "input_per_million": round(input_rate, 4),
                "output_per_million": round(output_rate, 4),
                "cached_input_per_million": (
                    round(cached_rate, 4)
                    if isinstance(cached_rate, (int, float))
                    and not isinstance(cached_rate, bool)
                    else None
                ),
                "pricing_basis": "api-equivalent",
            }
            continue
        p = entry.get("pricing", {})
        if not isinstance(p, dict):
            continue
        input_rate = p.get("input")
        output_rate = p.get("output")
        cached_rate = p.get("cached_input")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in (input_rate, output_rate)
        ):
            continue
        pricing[name] = {
            "input_per_million": round(input_rate, 4),
            "output_per_million": round(output_rate, 4),
            "cached_input_per_million": (
                round(cached_rate, 4)
                if isinstance(cached_rate, (int, float))
                and not isinstance(cached_rate, bool)
                else None
            ),
            "pricing_basis": "list",
        }

    # Retired models with archived corpus history: their entries are commented
    # out of `models:` (the retirement convention), which would silently drop
    # pricing for their historical runs. The registry preserves those rates in
    # the top-level `retired_model_pricing:` section — same schema, same list
    # basis. Active entries win on any name collision.
    for entry in config.get("retired_model_pricing", []):
        name = entry.get("name")
        if not name or name in pricing:
            continue
        p = entry.get("pricing", {})
        if not isinstance(p, dict):
            continue
        input_rate = p.get("input")
        output_rate = p.get("output")
        cached_rate = p.get("cached_input")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in (input_rate, output_rate)
        ):
            continue
        pricing[name] = {
            "input_per_million": round(input_rate, 4),
            "output_per_million": round(output_rate, 4),
            "cached_input_per_million": (
                round(cached_rate, 4)
                if isinstance(cached_rate, (int, float))
                and not isinstance(cached_rate, bool)
                else None
            ),
            "pricing_basis": "list",
        }
    return pricing


# ---------------------------------------------------------------------------
# OpenRouter billing reconciliation loading (battery-cost metric)
# ---------------------------------------------------------------------------

def load_reconciliation(base_dir):
    """Load the latest OpenRouter billing reconciliation JSON, if present.

    Discovers benchmarks/derived/openrouter_reconciliation_*.json and takes
    the latest by filename (dated names sort chronologically). Supplies the
    BILLED per-run token mix for OpenRouter models — see the "Battery-cost
    metric" dev guide above PHASE_MAP. Fail-soft by design: a missing or
    unreadable file prints a WARNING and returns None, and the generator
    then omits OpenRouter battery costs rather than failing the build.

    Returns the parsed dict with two derived fields attached:
    "_snapshot_date" (parsed from the filename) and "_path".
    """
    import glob as _glob
    pattern = os.path.join(base_dir, "derived", "openrouter_reconciliation_*.json")
    candidates = sorted(_glob.glob(pattern))
    if not candidates:
        print("WARNING: no derived/openrouter_reconciliation_*.json found; "
              "OpenRouter battery costs will be omitted (produce one from the "
              "v2 classified billing parquet — precedent: the campaign "
              "workspace's scripts/scratch/22_billing-tokenmix-json.py; the "
              "legacy scripts/reconcile_openrouter_costs.py emitter is stale "
              "for post-2026-07-27 data)",
              file=sys.stderr)
        return None
    path = candidates[-1]
    try:
        with open(path, "r") as f:
            recon = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: could not read reconciliation JSON {path}: {exc}; "
              "OpenRouter battery costs will be omitted", file=sys.stderr)
        return None
    fname = os.path.basename(path)
    recon["_snapshot_date"] = (
        fname.replace("openrouter_reconciliation_", "").replace(".json", ""))
    recon["_path"] = path
    print(f"Reconciliation snapshot: {path} "
          f"(billing snapshot dated {recon['_snapshot_date']})")
    return recon


# ---------------------------------------------------------------------------
# Data bundle assembly
# ---------------------------------------------------------------------------

PHASE_ORDER = {"mode_classification": 1, "post_confirmation": 2,
               "dispatch_compliance": 3, "skill_routing": 4}


def shard_filename(result_set_ts):
    """Canonical shard filename for a result set (used by index + writer)."""
    return f"tx_{result_set_ts}.json"


def build_transcripts_index(result_sets, transcripts, subagent_transcripts):
    """Build the bundle-mode transcripts_index embedded in DATA.

    {result_set: {file: "data/tx_{set}.json", n_main, n_subagent}} — the
    template fetches index entries' relative `file` paths on demand (plain
    relative URLs; the website deploy step handles any production
    rewriting). n_main counts main-transcript run keys, n_subagent counts
    run keys carrying subagent transcripts. Result sets with no transcripts
    at all get no index entry and no shard file — the template renders no
    transcript block for their runs, matching single-file behavior.
    """
    main_counts = {}
    for key in transcripts:
        ts = key.split("/", 1)[0]
        main_counts[ts] = main_counts.get(ts, 0) + 1
    sub_counts = {}
    for key in subagent_transcripts:
        ts = key.split("/", 1)[0]
        sub_counts[ts] = sub_counts.get(ts, 0) + 1

    index = {}
    for rs in result_sets:
        ts = rs["timestamp"]
        n_main = main_counts.get(ts, 0)
        n_sub = sub_counts.get(ts, 0)
        if n_main == 0 and n_sub == 0:
            continue
        index[ts] = {
            "file": "data/" + shard_filename(ts),
            "n_main": n_main,
            "n_subagent": n_sub,
        }
    return index


def build_data_bundle(result_sets, cases, runs, transcripts, subagent_transcripts,
                      model_pricing=None, inline_transcripts=True,
                      include_transcripts=True):
    """Assemble the DATA bundle for embedding in HTML.

    Three artifact shapes, selected by (include_transcripts, inline_transcripts)
    (v3.0.0 introduced the first two; v3.4.0 added the transcript-less shape —
    see "Bundle architecture" and "Transcript-inclusion control" dev guides
    above PHASE_MAP):
      include_transcripts=True, inline_transcripts=True (full single-file
        monolith): transcripts and subagent_transcripts embedded in full — the
        pre-3.0 shape (single-file only under --transcripts as of v3.4.0).
      include_transcripts=True, inline_transcripts=False (bundle index.html):
        both transcript dicts are DROPPED from DATA and replaced by
        transcripts_index pointing at the per-result-set shard files written
        next to index.html. The v3.0.0 bundle default.
      include_transcripts=False (transcript-less, either mode): DATA carries
        NEITHER transcripts/subagent_transcripts NOR transcripts_index. This is
        the v3.4.0 single-file default (transcript-lite offline monolith) and
        the bundle behavior under --no-transcripts. The client feature-detects
        the absence of both keys and shows a "transcripts not included in this
        build" notice instead of attempting any shard fetch.
    The transcripts/subagent_transcripts and transcripts_index keys are
    mutually exclusive BY DESIGN: the template feature-detects the artifact
    shape on DATA.transcripts / DATA.transcripts_index presence, so the three
    shapes (inline / lazy-index / neither) are each unambiguous.
    """
    # Sort result_sets by phase order so they always appear Phase 1, 2, 3, 4
    sorted_result_sets = sorted(
        result_sets, key=lambda rs: PHASE_ORDER.get(rs["phase"], 99)
    )
    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": "3.7.3",
        "embedded_schema_contract_version": 2,
        "result_sets": sorted_result_sets,
        "cases": cases,
        "runs": runs,
        "model_pricing": model_pricing or {},
    }
    if not include_transcripts:
        # Transcript-less shape: emit neither key. The client's three-way
        # feature detect (DATA.transcripts -> inline; DATA.transcripts_index ->
        # lazy; neither -> "not included" notice) covers this.
        pass
    elif inline_transcripts:
        bundle["transcripts"] = transcripts
        bundle["subagent_transcripts"] = subagent_transcripts
    else:
        bundle["transcripts_index"] = build_transcripts_index(
            sorted_result_sets, transcripts, subagent_transcripts)
    return bundle


# ---------------------------------------------------------------------------
# Precomputed metrics
#
# All aggregates below are derived from loaded run-level data (run dirs are
# ground truth; summary.json totals are used only for provenance disclosure).
# Headline numbers are computed here in Python and embedded as PRECOMPUTED so
# that prose, charts, and tables in the viewer cannot drift apart; the JS
# still computes section-local filtered views from the runs array.
# ---------------------------------------------------------------------------

# Canonical eval-group order: P1, P2, P3a (dispatch), P3b (subagent), P4
EVAL_GROUP_ORDER = [
    "mode_classification",
    "post_confirmation",
    "dispatch_compliance_dispatch",
    "dispatch_compliance_subagent",
    "skill_routing",
]

# Composite scoring is PINNED to the five approved components (P1, P2, P3a,
# P3b, P4 — unweighted mean of Perfect rates). The original four-component
# pin (design record: README § 8, decision 1) was superseded by user decision
# 2026-06-10 adding skill_routing (P4); see README §§ 8/12.
# Future phases get their own labeled eval group, per_model_phase cells, and
# per-group callouts, but never enter the composite, tiers, or the global
# weakest-criterion callout unless they are deliberately added here (see
# "Adding a new benchmark phase" above PHASE_MAP — joining the composite
# changes leaderboard semantics and requires prose updates in
# viewer_template.html and README.md §§ 6/8). Models lacking runs for a
# component score the mean over their available components and carry a
# partial_data flag (disclosed in the leaderboard and hero verdict) —
# mirroring the cost-perf omitted-model disclosure pattern.
COMPOSITE_GIDS = [
    "mode_classification",
    "post_confirmation",
    "dispatch_compliance_dispatch",
    "dispatch_compliance_subagent",
    "skill_routing",
]

# Tier banding rule (mechanical and reproducible by design — see
# design record: README § 8, decision 2). Two deterministic stages:
#
#   Primary (gap rule): walking the composite ranking in descending order, a
#   new tier starts wherever the gap to the previous model's composite is
#   >= TIER_GAP_THRESHOLD (5 percentage points).
#
#   Fallback (range quartiles): on a corpus of >= TIER_FALLBACK_MIN_MODELS
#   models, the gap rule is overridden by equal-width range-quartile banding
#   when EITHER degeneracy appears:
#     (a) it yields fewer than TIER_MIN_TIERS tiers — the near-continuum case,
#         where the largest observed composite gap is ~6.8 points at the
#         original 8-point threshold; OR
#     (b) its largest tier holds more than TIER_MAX_TIER_SHARE of the ranked
#         models (v3.5.0, Fix 4 — the "share cap"). Post-rescore score
#         compression can leave >= 3 tiers while dumping the vast majority into
#         one band (observed T1=25/T2=2/T3=2, largest interior gap 0.0428 <
#         threshold), which is just as uninformative as a single band. The
#         share cap catches that even though the tier-count test (a) passes.
#   Both trigger the same range-quartile rebanding: models are banded by which
#   quarter of the composite range [min, max] their score falls in (equal-width
#   bands; empty bands are skipped so tier labels stay contiguous T1, T2, ...).
#
# The applied method is recorded in PRECOMPUTED["tier_rule"] so the viewer's
# leaderboard prose can disclose which rule produced the bands on this corpus.
TIER_GAP_THRESHOLD = 0.05
TIER_MIN_TIERS = 3
TIER_FALLBACK_MIN_MODELS = 12
TIER_MAX_TIER_SHARE = 0.5  # Fix 4: gap rule is overridden if its largest tier
                           # exceeds this share of ranked models (share cap).


def build_eval_groups(result_sets, active_timestamps=None):
    """Build eval groups, mirroring the viewer JS buildEvalGroups() split.

    Phase 1 and Phase 2 are single groups. Phase 3 result sets that carry
    subagent criterion names contribute their runs to BOTH a dispatch group
    (3a — scored on run['criteria']) and a subagent group (3b — scored on
    run['subagent_criteria']). The eval-group semantics here must stay in
    lockstep with the template JS so precomputed and JS-derived numbers agree.

    Degenerate-column suppression (v3.5.0, Fix 3): a result set contributes a
    leaderboard column group only if it clears three gates. These skips are
    COLUMN-DERIVATION-SCOPED — the underlying runs still count in the all-runs
    aggregates (consistency, per_case, cost, duration), which iterate DATA.runs
    directly rather than through eval groups:
      1. phase != "unknown" — detect_phase() falls back to "unknown" on
         empty/aborted/mid-write summary.json sets whose criteria match no
         known phase marker; such a set must not spawn an "Unknown Phase"
         column.
      2. the set has >= 1 completed (loaded) run — `active_timestamps` is the
         set of result_set timestamps present in the loaded runs (post
         load-time no-signal exclusion). A set with zero loaded runs produces
         only an empty column. When active_timestamps is None the gate is
         disabled (back-compat).
      3. a dispatch_compliance set lacking subagent criterion names is FOLDED
         into the dispatch group (3a) rather than emitting a bare, second
         `dispatch_compliance` column — its main criteria are scored exactly
         like any other 3a set.
    """
    gmap = {}
    for rs in result_sets:
        # Gate 1: skip the Unknown-Phase fallback bucket.
        if rs["phase"] == "unknown":
            continue
        # Gate 2: skip sets with no loaded/completed runs (empty column).
        if active_timestamps is not None and rs["timestamp"] not in active_timestamps:
            continue
        if rs["phase"] == "dispatch_compliance" and rs.get("subagent_criterion_names"):
            gid = "dispatch_compliance_dispatch"
            if gid not in gmap:
                gmap[gid] = {
                    "id": gid, "phase": rs["phase"],
                    "label": "Phase 3a \u2014 Dispatch Compliance",
                    "timestamps": [], "is_subagent": False,
                    "criterion_names": list(rs["criterion_names"]),
                }
            gmap[gid]["timestamps"].append(rs["timestamp"])
            gid = "dispatch_compliance_subagent"
            if gid not in gmap:
                gmap[gid] = {
                    "id": gid, "phase": rs["phase"],
                    "label": "Phase 3b \u2014 Subagent Behavior",
                    "timestamps": [], "is_subagent": True,
                    "criterion_names": list(rs["subagent_criterion_names"]),
                }
            gmap[gid]["timestamps"].append(rs["timestamp"])
        elif rs["phase"] == "dispatch_compliance":
            # Gate 3: subagent-less dc set — fold into the 3a dispatch group
            # instead of emitting a bare `dispatch_compliance` column.
            gid = "dispatch_compliance_dispatch"
            if gid not in gmap:
                gmap[gid] = {
                    "id": gid, "phase": rs["phase"],
                    "label": "Phase 3a — Dispatch Compliance",
                    "timestamps": [], "is_subagent": False,
                    "criterion_names": list(rs["criterion_names"]),
                }
            gmap[gid]["timestamps"].append(rs["timestamp"])
        else:
            gid = rs["phase"]
            if gid not in gmap:
                gmap[gid] = {
                    "id": gid, "phase": rs["phase"],
                    "label": rs["phase_label"],
                    "timestamps": [], "is_subagent": False,
                    "criterion_names": list(rs["criterion_names"]),
                }
            gmap[gid]["timestamps"].append(rs["timestamp"])

    ordered = [gmap[gid] for gid in EVAL_GROUP_ORDER if gid in gmap]
    ordered += [g for gid, g in gmap.items() if gid not in EVAL_GROUP_ORDER]
    return ordered


def run_group_criteria(run, group):
    """Return the criteria dict a run is scored on within an eval group."""
    if group["is_subagent"]:
        return run.get("subagent_criteria") or {}
    return run.get("criteria") or {}


def build_precomputed(result_sets, cases, runs, generation_params,
                      model_pricing=None, anth_token_totals=None,
                      reconciliation=None):
    """Compute the derived-metrics bundle embedded as PRECOMPUTED."""
    # active_timestamps drives Fix 3 Gate 2: only result sets with >= 1 loaded
    # (completed, post-exclusion) run may spawn a leaderboard column.
    active_timestamps = {r["result_set"] for r in runs}
    groups = build_eval_groups(result_sets, active_timestamps)
    group_ts = {g["id"]: set(g["timestamps"]) for g in groups}
    models = sorted({r["model"] for r in runs})
    phase_lookup = {rs["timestamp"]: rs["phase"] for rs in result_sets}

    def rnd(x, digits=4):
        return None if x is None else round(x, digits)

    # --- per_model_phase: model x eval group aggregates ---
    per_model_phase = {}
    for model in models:
        per_model_phase[model] = {}
        for g in groups:
            gid = g["id"]
            gruns = [r for r in runs
                     if r["model"] == model and r["result_set"] in group_ts[gid]]
            if not gruns:
                continue
            n_runs = len(gruns)
            n_graded = 0
            perfect_count = 0
            hard_pass_count = 0
            hard_passed = hard_total = soft_passed = soft_total = 0
            dispatch_passed = dispatch_total = 0
            for r in gruns:
                crit = run_group_criteria(r, g)
                if crit:
                    n_graded += 1
                # Perfect requires at least one criterion present and all
                # passed — mirrors the JS groupAllPassed(): runs with no
                # criteria in this group count toward n_runs but can never
                # be perfect (matters for 3b, where some Phase 3 runs have
                # no subagent criteria)
                if compute_grade(crit) == "perfect":
                    perfect_count += 1
                # Hard-pass (leaderboard "Critical-only" metric) mirrors Perfect
                # but over hard-tier criteria only: at least one criterion
                # present AND every hard-tier criterion passed. A graded run
                # whose group has no hard-tier criteria passes vacuously, so
                # the hard-pass set always contains the perfect set
                # (hard_rate >= perfect_rate by construction).
                hard_run_ok = bool(crit)
                for name, entry in crit.items():
                    if not isinstance(entry, dict):
                        continue
                    tier = entry.get("tier")
                    if tier == "hard":
                        hard_total += 1
                        if entry.get("passed"):
                            hard_passed += 1
                        else:
                            hard_run_ok = False
                    elif tier == "soft":
                        soft_total += 1
                        if entry.get("passed"):
                            soft_passed += 1
                    if gid == "dispatch_compliance_dispatch" and name == "agent_dispatched":
                        dispatch_total += 1
                        if entry.get("passed"):
                            dispatch_passed += 1
                if hard_run_ok:
                    hard_pass_count += 1
            cell = {
                "n_runs": n_runs,
                "n_graded": n_graded,
                "perfect_count": perfect_count,
                "perfect_rate": rnd(perfect_count / n_runs),
                "hard_pass_count": hard_pass_count,
                "hard_rate": rnd(hard_pass_count / n_runs),
                "hard_passed": hard_passed,
                "hard_total": hard_total,
                "soft_passed": soft_passed,
                "soft_total": soft_total,
            }
            if gid == "dispatch_compliance_dispatch":
                cell["dispatch_passed"] = dispatch_passed
                cell["dispatch_total"] = dispatch_total
                cell["dispatch_rate"] = rnd(
                    dispatch_passed / dispatch_total) if dispatch_total else None
            per_model_phase[model][gid] = cell

    # --- composite: unweighted mean of available per-group perfect rates ---
    # P1, P2, P3a, P3b, P4 are five equal components (user decision
    # 2026-06-10, superseding resolved decision 1's four-component pin) —
    # pinned via COMPOSITE_GIDS so non-composite eval groups never enter
    # scores, components, or partial-data flags.
    # Models missing a component get the mean over available components and a
    # partial_data flag, relative to the composite components present in this
    # corpus (components_missing likewise refers only to composite gids).
    corpus_components = [gid for gid in COMPOSITE_GIDS
                         if any(g["id"] == gid for g in groups)]

    def build_composite_from(rate_field):
        # Single code path shared by the Perfect metric
        # (rate_field="perfect_rate") and the Critical-only metric
        # (rate_field="hard_rate") so the composite construction cannot
        # drift between the two leaderboard metrics. Output shape is
        # identical for both.
        out = {}
        for model in models:
            comps = {}
            n_total = 0
            for gid in corpus_components:
                cell = per_model_phase.get(model, {}).get(gid)
                if cell is None:
                    continue
                comps[gid] = cell[rate_field]
                n_total += cell["n_runs"]
            if not comps:
                continue
            score = sum(comps.values()) / len(comps)
            out[model] = {
                "score": rnd(score),
                "components": comps,
                "components_present": list(comps.keys()),
                "components_missing": [gid for gid in corpus_components
                                       if gid not in comps],
                "n_total": n_total,
                "partial_data": len(comps) < len(corpus_components),
            }
        return out

    composite = build_composite_from("perfect_rate")
    composite_hard = build_composite_from("hard_rate")

    # --- tiers: mechanical banding on composite (gap rule + quartile fallback) ---
    # Factored into one helper so the IDENTICAL rule produces both the
    # Perfect-metric tiers and the Critical-only-metric tiers — the banding
    # logic cannot drift between the two leaderboard metrics.
    def compute_tiers_for(composite_dict):
        # Stage 1 (gap rule): sort by composite descending; start a new tier
        # where the gap to the previous model's composite is >=
        # TIER_GAP_THRESHOLD. Annotates entry["tier"] in place.
        ranked = sorted(composite_dict.items(),
                        key=lambda kv: (-kv[1]["score"], kv[0]))
        tiers = []
        prev_score = None
        for model, entry in ranked:
            if prev_score is None or (prev_score - entry["score"]) >= TIER_GAP_THRESHOLD:
                tiers.append({"label": "T" + str(len(tiers) + 1), "models": []})
            tiers[-1]["models"].append(model)
            entry["tier"] = tiers[-1]["label"]
            prev_score = entry["score"]
        tier_rule = {"method": "gap", "gap_threshold": TIER_GAP_THRESHOLD}
        # Stage 2 (fallback): on a large corpus (>= TIER_FALLBACK_MIN_MODELS)
        # the gap rule is overridden by range-quartile banding when it
        # degenerates in either of two ways — too few tiers (near-continuum),
        # or a single tier dominating the field (v3.5.0, Fix 4 share cap:
        # largest tier > TIER_MAX_TIER_SHARE of ranked models, even with >= 3
        # tiers). Both cases band by which quarter of the composite range
        # [min, max] each score falls in. Walking the descending ranking, band
        # indices are non-decreasing, so a band change starts a new tier; empty
        # bands are skipped and labels stay contiguous.
        largest_tier_share = (
            max((len(t["models"]) for t in tiers), default=0) / len(ranked)
            if ranked else 0
        )
        share_cap_exceeded = largest_tier_share > TIER_MAX_TIER_SHARE
        too_few_tiers = len(tiers) < TIER_MIN_TIERS
        if len(ranked) >= TIER_FALLBACK_MIN_MODELS and (
            too_few_tiers or share_cap_exceeded
        ):
            hi = ranked[0][1]["score"]
            lo = ranked[-1][1]["score"]
            span = hi - lo
            if span > 0:
                tiers = []
                prev_band = None
                for model, entry in ranked:
                    # band 0 = top quarter of the range ... band 3 = bottom
                    band = min(3, int((hi - entry["score"]) / span * 4))
                    if prev_band is None or band != prev_band:
                        tiers.append({"label": "T" + str(len(tiers) + 1),
                                      "models": []})
                        prev_band = band
                    tiers[-1]["models"].append(model)
                    entry["tier"] = tiers[-1]["label"]
                tier_rule = {
                    "method": "range_quartiles",
                    "gap_threshold": TIER_GAP_THRESHOLD,
                    # Which degeneracy forced the fallback (Fix 4 disclosure).
                    "fallback_trigger": (
                        "min_tiers" if too_few_tiers else "share_cap"
                    ),
                    "max_tier_share": TIER_MAX_TIER_SHARE,
                }
        return tiers, tier_rule

    tiers, tier_rule = compute_tiers_for(composite)
    tiers_hard, tier_rule_hard = compute_tiers_for(composite_hard)

    # --- consistency: pass^k over (phase, case) cells with >= 2 reps ---
    # A cell is all-perfect when every rep of that (model, phase, case) has
    # grade == "perfect" (main-criteria grade; raw phase, matching the rep
    # renumbering key in main()).
    # Deliberately spans ALL loaded runs, including non-composite phases —
    # consistency is an all-runs reliability measure, not pinned to COMPOSITE_GIDS.
    consistency = {}
    for model in models:
        cells = {}
        for r in runs:
            if r["model"] != model:
                continue
            key = (phase_lookup.get(r["result_set"], ""), r["case_id"])
            cells.setdefault(key, []).append(r["grade"])
        multi = {k: v for k, v in cells.items() if len(v) >= 2}
        all_perfect = sum(
            1 for grades in multi.values()
            if all(gr == "perfect" for gr in grades)
        )
        # Agreement/predictability (v3.7.0): a cell "agrees" when every rep
        # lands on the IDENTICAL grade (all perfect, OR all partial, OR all
        # failed, OR all ungraded) — i.e., the model produces the same verdict
        # on repeat attempts. Distinct from cells_all_perfect: that measures
        # capability (all reps clean), whereas agreement measures reliability
        # decoupled from score level (a model that fails identically every time
        # is predictable, if not good). Display-orphaned since v3.7.3: the
        # Key Takeaways T4 reliability claim now runs on the all-perfect
        # `rate` (matching the leaderboard Consistency column); rate_agree
        # stays in the payload under the schema-additive contract.
        all_agree = sum(
            1 for grades in multi.values()
            if len(set(grades)) == 1
        )
        consistency[model] = {
            "cells_total": len(multi),
            "cells_all_perfect": all_perfect,
            "rate": rnd(all_perfect / len(multi)) if multi else None,
            "cells_all_agree": all_agree,
            "rate_agree": rnd(all_agree / len(multi)) if multi else None,
        }

    # --- per_case: cross-model difficulty ---
    per_case = {}
    case_runs = {}
    for r in runs:
        case_runs.setdefault(r["case_id"], []).append(r)
    for case_id, cruns in sorted(case_runs.items()):
        case = cases.get(case_id, {})
        subcategory = case.get("subcategory")
        if subcategory is None:
            # Fall back to the field carried on Phase 2/3 result.json
            subcategory = next(
                (r["subcategory"] for r in cruns if r.get("subcategory")), None)
        perfect_count = sum(1 for r in cruns if r["grade"] == "perfect")
        per_case[case_id] = {
            "phase": phase_lookup.get(cruns[0]["result_set"], ""),
            "subcategory": subcategory,
            "n_runs": len(cruns),
            "n_models": len({r["model"] for r in cruns}),
            "perfect_count": perfect_count,
            "perfect_rate": rnd(perfect_count / len(cruns)),
        }

    # --- callouts: weakest criterion + top model per eval group ---
    callouts = {"groups": {}, "global_weakest": None}
    global_weakest = None
    for g in groups:
        gid = g["id"]
        gruns = [r for r in runs if r["result_set"] in group_ts[gid]]
        crit_agg = {}
        for r in gruns:
            for name, entry in run_group_criteria(r, g).items():
                if not isinstance(entry, dict):
                    continue
                agg = crit_agg.setdefault(name, {"passed": 0, "total": 0})
                agg["total"] += 1
                if entry.get("passed"):
                    agg["passed"] += 1
        weakest = None
        for name, agg in crit_agg.items():
            rate = agg["passed"] / agg["total"]
            # Deterministic tie-breaks: lowest rate, then largest n, then name
            key = (rate, -agg["total"], name)
            if weakest is None or key < weakest[0]:
                weakest = (key, {
                    "name": name,
                    "passed": agg["passed"],
                    "total": agg["total"],
                    "rate": rnd(rate),
                })
        top_model = None
        for model in models:
            cell = per_model_phase.get(model, {}).get(gid)
            if cell is None:
                continue
            key = (-cell["perfect_rate"], -cell["n_runs"], model)
            if top_model is None or key < top_model[0]:
                top_model = (key, {
                    "model": model,
                    "perfect_rate": cell["perfect_rate"],
                    "n_runs": cell["n_runs"],
                })
        callouts["groups"][gid] = {
            "label": g["label"],
            "weakest_criterion": weakest[1] if weakest else None,
            "top_model": top_model[1] if top_model else None,
        }
        # global_weakest (hero verdict + #phases finding) is restricted to
        # composite groups so a single experimental phase cannot hijack the
        # document's headline finding; callouts["groups"] above still covers
        # every eval group, including non-composite ones.
        if weakest is not None and gid in COMPOSITE_GIDS:
            if global_weakest is None or weakest[0] < global_weakest[0]:
                global_weakest = (weakest[0],
                                  dict(weakest[1], group=gid, group_label=g["label"]))
    if global_weakest is not None:
        callouts["global_weakest"] = global_weakest[1]

    # --- cost: price formulations (NO observed spend) ---
    # Observed token-derived spend was removed entirely: OpenRouter token
    # accounting does not align with the harness's usage logging (the
    # Anthropic-compatible endpoint reports Anthropic-tokenizer counts, not
    # each model's own billing meter), so computed dollar figures were
    # unreliable. The HEADLINE cost figure page-wide is "battery" — the
    # estimated cost to run the full benchmark battery once (filled by the
    # battery block below; displayed as a multiplier vs the reference model).
    # Two secondary per-Mtok forms are precomputed per model from
    # config/models.yaml list rates:
    #   input   -- input $/Mtok
    #   output  -- output $/Mtok
    # The blended 3:1 form (blend31, Artificial Analysis convention) was
    # retired in v3.1.0: benchmark cost is dominated by input tokens, so a
    # 3:1 in/out blend misled.
    pricing = model_pricing or {}
    cost = {"models": [], "frontiers": {}, "omitted_models": []}
    price_by_model = {}
    for model in models:
        model_runs = [run for run in runs if run["model"] == model]
        providers = sorted({
            run["provider"] for run in model_runs
            if isinstance(run.get("provider"), str) and run["provider"]
        })
        incompatible = [
            run for run in model_runs
            if run.get("billing_grade_cost_eligible") is False
        ]
        if incompatible:
            # A model flagged not-billing-grade (e.g. chatgpt-subscription:
            # subscription access, never invoiced per token). v3.5.0 (Fix 2):
            # if an api-equivalent counterfactual price schedule exists for the
            # model, price it on that explicit basis instead of omitting it —
            # the battery figure is already a counterfactual (uncached list
            # rates) for every provider, so an api-equivalent GPT estimate is
            # directly comparable. We deliberately do NOT flip the run/set-level
            # billing_grade_cost_eligible flag: these models remain correctly
            # disclosed as not-invoiced in the run-detail ledger, and only the
            # counterfactual battery estimate includes them (tagged api-equiv).
            # Models with no api-equivalent schedule are omitted exactly as
            # before.
            p_api = pricing.get(model)
            has_api_equiv = (
                isinstance(p_api, dict)
                and p_api.get("pricing_basis") == "api-equivalent"
                and p_api.get("input_per_million") is not None
                and p_api.get("output_per_million") is not None
            )
            if not has_api_equiv:
                reasons = sorted({
                    run.get("billing_grade_cost_exclusion_reason")
                    for run in incompatible
                    if run.get("billing_grade_cost_exclusion_reason")
                })
                cost["omitted_models"].append({
                    "model": model,
                    "providers": providers,
                    "reason": (
                        reasons[0] if len(reasons) == 1
                        else "mixed_incompatible_billing_treatments"
                    ),
                    "behavioral_scores_retained": True,
                })
                continue
        p = pricing.get(model)
        if not p:
            continue
        inp = p.get("input_per_million")
        outp = p.get("output_per_million")
        if inp is None or outp is None:
            continue
        entry = {
            "key": model,
            "input": rnd(inp),
            "output": rnd(outp),
            # Filled by the battery block below (est. $ to run the full
            # battery once); None for models lacking battery data — the
            # frontier walk and the scatter both skip None prices.
            "battery": None,
        }
        cost["models"].append(entry)
        price_by_model[model] = entry

    # --- cost.battery: estimated cost per benchmark battery (v2.8.0) ---
    # Uncached basis (user-approved 2026-06-11): every token priced at the
    # current models.yaml list input/output rates with NO cache discounts,
    # using each model's own observed per-run token mix — directly comparable
    # across providers regardless of caching regime. Anthropic token mixes
    # are aggregated live from corpus result.json (anth_token_totals, billing-
    # grade usage meter; input side = input + cache_read + cache_creation,
    # ALL at full input rate — the uncached counterfactual). OpenRouter token
    # mixes come from the billing reconciliation snapshot (billed prompt /
    # completion per covered run; the harness's OpenRouter token counts are
    # tokenizer approximations and are never used for dollars). Full metric
    # definition + staleness-guard rationale: "Battery-cost metric" dev guide
    # above PHASE_MAP. Timed-out runs are excluded upstream at load (v3.3.0),
    # so these token averages already reflect completed runs only.
    BATTERY_REFERENCE_MODEL = "Opus 4.8"
    battery_size = len(case_runs)  # distinct case_ids in the loaded corpus
    snapshot_date = (reconciliation or {}).get("_snapshot_date")
    battery_models = {}

    for model, agg in (anth_token_totals or {}).items():
        pm = price_by_model.get(model)
        n = agg.get("n", 0)
        if pm is None or n == 0:
            continue
        input_side = (agg["input"] + agg["cache_read"]
                      + agg["cache_creation"]) / n
        output_side = agg["output"] / n
        per_run = (input_side * pm["input"] + output_side * pm["output"]) / 1e6
        # Basis tag distinguishes the two live-token lanes sharing this loop:
        # Anthropic mixes are "corpus-live" (billing-grade usage meter);
        # chatgpt-subscription GPT mixes are "api-equivalent" (v3.5.0, Fix 2 —
        # counterfactual list price, not invoiced). The template surfaces the
        # distinction as an "api-equiv" marker on the leaderboard cost cell.
        model_basis = (pricing.get(model, {}) or {}).get("pricing_basis")
        battery_models[model] = {
            "est_cost_per_run": rnd(per_run),
            "est_battery_cost": rnd(per_run * battery_size, 2),
            "tokens_per_run": round(input_side + output_side),
            "n_runs": n,
            "basis": ("api-equivalent" if model_basis == "api-equivalent"
                      else "corpus-live"),
        }

    if reconciliation:
        corpus_runs_by_model = {}
        for r in runs:
            corpus_runs_by_model[r["model"]] = \
                corpus_runs_by_model.get(r["model"], 0) + 1
        for model, rec in reconciliation.get("openrouter_models", {}).items():
            pm = price_by_model.get(model)
            n_cov = rec.get("n_covered_runs")
            bt = rec.get("billed_tokens")
            if (
                pm is None
                or isinstance(n_cov, bool)
                or not isinstance(n_cov, (int, float))
                or n_cov <= 0
                or not isinstance(bt, dict)
            ):
                continue
            prompt_tokens = bt.get("prompt")
            completion_tokens = bt.get("completion")
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in (prompt_tokens, completion_tokens)
            ):
                continue
            input_side = prompt_tokens / n_cov
            output_side = completion_tokens / n_cov
            per_run = (input_side * pm["input"]
                       + output_side * pm["output"]) / 1e6
            # Staleness guard: the snapshot's run universe vs the corpus
            # being embedded right now. WARN, never fail (dev guide).
            snapshot_n = rec.get("n_runs")
            corpus_n = corpus_runs_by_model.get(model, 0)
            stale = snapshot_n is not None and snapshot_n != corpus_n
            if stale:
                print(f"WARNING: battery-cost staleness — {model}: corpus has "
                      f"{corpus_n} runs but the billing snapshot "
                      f"({snapshot_date}) recorded {snapshot_n}; its token "
                      f"mix predates the newer runs. Re-run "
                      f"reconcile_openrouter_costs.py with a fresh billing "
                      f"export.", file=sys.stderr)
            battery_models[model] = {
                "est_cost_per_run": rnd(per_run),
                "est_battery_cost": rnd(per_run * battery_size, 2),
                "tokens_per_run": round(input_side + output_side),
                "n_runs": corpus_n,
                "basis": "billing-snapshot-" + (snapshot_date or "unknown"),
                "snapshot_n_runs": snapshot_n,
                "stale": stale,
            }

    ref_entry = battery_models.get(BATTERY_REFERENCE_MODEL)
    for model, b in battery_models.items():
        if ref_entry and ref_entry["tokens_per_run"]:
            b["token_multiplier_vs_ref"] = rnd(
                b["tokens_per_run"] / ref_entry["tokens_per_run"], 3)
        else:
            b["token_multiplier_vs_ref"] = None
        if ref_entry and ref_entry["est_cost_per_run"]:
            b["cost_multiplier_vs_ref"] = rnd(
                b["est_cost_per_run"] / ref_entry["est_cost_per_run"], 3)
        else:
            b["cost_multiplier_vs_ref"] = None
        pm = price_by_model.get(model)
        if pm is not None:
            pm["battery"] = b["est_battery_cost"]

    cost["battery"] = {
        "battery_size": battery_size,
        "reference_model": BATTERY_REFERENCE_MODEL,
        "snapshot_date": snapshot_date,
        "models": battery_models,
    }

    # --- cost-perf y-value matrix: perf_values[basis][metric][model] ---
    # Performance bases for the Cost vs. Performance scatter: "composite"
    # plus EVERY eval group gid — composite components (P1, P2, P3a, P3b)
    # AND non-composite groups (e.g., skill_routing/P4), so the scatter can
    # be filtered to any single phase group. Non-composite phases may have
    # partial model coverage mid-baseline; models lacking data for a basis
    # are simply absent from that basis's dict, and the template omits them
    # from that view and footnotes the count — partial-coverage frontiers
    # are disclosed, never silent. Metrics: "perfect" (all criteria pass)
    # and "hard" (all hard-tier criteria pass).
    perf_bases = ["composite"] + [g["id"] for g in groups]
    comp_by_metric = {"perfect": composite, "hard": composite_hard}
    rate_field_by_metric = {"perfect": "perfect_rate", "hard": "hard_rate"}
    perf_values = {}
    for basis in perf_bases:
        perf_values[basis] = {}
        for metric in ("perfect", "hard"):
            vals = {}
            for model in models:
                if basis == "composite":
                    comp_entry = comp_by_metric[metric].get(model)
                    if comp_entry is None:
                        continue
                    vals[model] = comp_entry["score"]
                else:
                    cell = per_model_phase.get(model, {}).get(basis)
                    if cell is None:
                        continue
                    vals[model] = cell[rate_field_by_metric[metric]]
            perf_values[basis][metric] = vals
    cost["perf_values"] = perf_values

    # --- efficiency frontiers: Pareto set on (price asc, score desc) ---
    # One frontier per (price formulation x perf basis x metric) combination,
    # keyed frontiers[price_form][perf_basis][metric], over models that have
    # both a published price and a score under that basis/metric. Walking
    # points sorted by (price asc, score desc, name asc) and keeping strict
    # score improvements yields the frontier staircase deterministically: a
    # model is kept iff no cheaper-or-equal model has an equal-or-higher
    # score. Precomputed here (not in JS) so the scatter annotation, the
    # section prose, and the sanity report cannot drift.
    # "battery" (a price formulation since v2.8.0) is the headline form and
    # ordered first (v3.1.0, when blend31 was retired); models without
    # battery data carry battery=None and are skipped by the None/<=0 guard
    # below.
    for form in ("battery", "input", "output"):
        cost["frontiers"][form] = {}
        for basis in perf_bases:
            cost["frontiers"][form][basis] = {}
            for metric in ("perfect", "hard"):
                frontier_pts = []
                for model, score_val in perf_values[basis][metric].items():
                    pm = price_by_model.get(model)
                    if pm is None:
                        continue
                    price = pm[form]
                    if price is None or price <= 0:
                        continue
                    frontier_pts.append((price, -score_val, model))
                frontier_pts.sort()
                frontier = []
                best_score = None
                for price, neg_score, model in frontier_pts:
                    score = -neg_score
                    if best_score is None or score > best_score:
                        frontier.append({
                            "model": model,
                            "price": price,
                            "score": score,
                        })
                        best_score = score
                cost["frontiers"][form][basis][metric] = frontier

    # --- duration.battery: estimated wall-clock latency per battery (v3.3.0) ---
    # A real-world LATENCY proxy, mirroring cost.battery but needing no pricing
    # — so it covers EVERY model (Anthropic, OpenRouter, AND the cost-omitted
    # subscription lane), never gated on provider or billing eligibility. Built
    # from SUMMED per-run duration_s: est_duration_per_run = mean duration_s
    # over that model's completed runs (timed-out runs never reach `runs`),
    # est_battery_duration = per-run x battery_size (the SAME distinct-case
    # count the cost block uses). Per-run durations are parallelization-
    # INVARIANT (independent of config.parallel), unlike summary wall_time_s
    # (a batch clock that depends on run mode) — so the figure is comparable
    # across sets fetched serially vs in parallel. duration_multiplier_vs_ref
    # is vs BATTERY_REFERENCE_MODEL (Opus 4.8), derived from the stored per-run
    # figure exactly as cost_multiplier_vs_ref is.
    DURATION_REFERENCE_MODEL = BATTERY_REFERENCE_MODEL
    duration_models = {}
    for model in models:
        # Duration/latency aggregate contribution rules (Dispatch B + review fix):
        #   - stalled runs are ALWAYS excluded: their wall time is a
        #     watchdog-killed hang, not a task-completion measure, and never
        #     comparable to a real duration.
        #   - completed_early runs contribute score_complete_seconds when present
        #     (time-to-demonstrated-compliance: launch -> first score-complete
        #     pass, excluding the confirmation/kill tail), else are excluded. This
        #     keeps the duration axis populated with a meaningful "time to all
        #     criteria pass" measure instead of dropping early-stopped runs — but
        #     note it is NOT full-task walltime (see README § 8; label accordingly).
        #   - every other run contributes its full duration_s.
        # Keyed on the exact "completed_early"/"stalled" status strings.
        durs = []
        for r in runs:
            if r["model"] != model:
                continue
            status = r.get("status")
            if status == "stalled":
                continue
            if status == "completed_early":
                val = r.get("score_complete_seconds")
            else:
                val = r["duration_s"]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                durs.append(val)
        if not durs:
            continue
        n = len(durs)
        per_run = sum(durs) / n
        duration_models[model] = {
            "est_duration_per_run": rnd(per_run),
            "est_battery_duration": rnd(per_run * battery_size, 1),
            "n_runs": n,
            "basis": "corpus-live",
        }
    dref_entry = duration_models.get(DURATION_REFERENCE_MODEL)
    for model, d in duration_models.items():
        if dref_entry and dref_entry["est_duration_per_run"]:
            d["duration_multiplier_vs_ref"] = rnd(
                d["est_duration_per_run"] / dref_entry["est_duration_per_run"], 3)
        else:
            d["duration_multiplier_vs_ref"] = None

    # duration.frontiers[basis][metric]: Pareto staircase on
    # (duration asc, score desc), reusing perf_values (already built over
    # completed runs) for the y-values. A SEPARATE block (not a parallel
    # cost.frontiers "form") because duration covers models the cost block
    # omits — folding it into cost.frontiers[form] would silently restrict it
    # to priced models. Identical staircase walk to the cost frontier. The
    # template divides every plotted duration by the reference model's
    # est_battery_duration (durScale, a clone of batScale) to render a relative
    # multiplier, exactly as the battery axis does.
    duration_frontiers = {}
    for basis in perf_bases:
        duration_frontiers[basis] = {}
        for metric in ("perfect", "hard"):
            frontier_pts = []
            for model, score_val in perf_values[basis][metric].items():
                dm = duration_models.get(model)
                if dm is None:
                    continue
                price = dm["est_battery_duration"]
                if price is None or price <= 0:
                    continue
                frontier_pts.append((price, -score_val, model))
            frontier_pts.sort()
            frontier = []
            best_score = None
            for price, neg_score, model in frontier_pts:
                score = -neg_score
                if best_score is None or score > best_score:
                    frontier.append({
                        "model": model,
                        "price": price,
                        "score": score,
                    })
                    best_score = score
            duration_frontiers[basis][metric] = frontier

    duration = {
        "battery_size": battery_size,
        "reference_model": DURATION_REFERENCE_MODEL,
        "models": duration_models,
        "frontiers": duration_frontiers,
    }

    # --- provenance: per result set, manifest + disk-vs-summary disclosure ---
    provenance = []
    for rs in sorted(result_sets,
                     key=lambda x: (PHASE_ORDER.get(x["phase"], 99), x["timestamp"])):
        provenance.append({
            "timestamp": rs["timestamp"],
            "phase": rs["phase"],
            "phase_label": rs["phase_label"],
            "schema_version": rs.get("schema_version", 1),
            "schema_classification": rs.get(
                "schema_classification", "legacy_schema_v1"
            ),
            "providers": rs.get("providers", []),
            "billing_grade_cost_eligible": rs.get(
                "billing_grade_cost_eligible", True
            ),
            "billing_grade_cost_exclusion_reason": rs.get(
                "billing_grade_cost_exclusion_reason"
            ),
            "purity_coverage": rs.get("purity_coverage"),
            "daaf_git_sha": rs.get("daaf_git_sha"),
            "config": rs.get("config"),
            "disk_run_count": rs.get("disk_run_count", 0),
            "summary_total_runs": rs.get("summary_total_runs", 0),
            "run_count_discrepancy":
                rs.get("disk_run_count", 0) != rs.get("summary_total_runs", 0),
            # Partial-pass disclosure (progressive-archiving redesign, 2026-07).
            "partial": rs.get("partial", False),
            "runs_expected": rs.get("runs_expected"),
            "runs_completed": rs.get("runs_completed"),
            "error_counts": rs.get("error_counts"),
        })

    # --- totals ---
    # Timeout-blind (v3.3.0): timed-out runs were excluded at load, so
    # total_runs counts completed runs only and there is no per-corpus timeout
    # count here. The per-load excluded count is a console-only maintainer
    # diagnostic (print_summary), never embedded in the payload.
    totals = {
        "total_runs": len(runs),
        "n_models": len(models),
        "n_cases": len(case_runs),
        "n_result_sets": len(result_sets),
        "generation_params": generation_params,
    }

    return {
        "eval_groups": [
            {k: g[k] for k in ("id", "phase", "label", "timestamps",
                               "is_subagent", "criterion_names")}
            for g in groups
        ],
        "per_model_phase": per_model_phase,
        "composite": composite,
        "composite_hard": composite_hard,
        "tiers": tiers,
        "tiers_hard": tiers_hard,
        "tier_rule": tier_rule,
        "tier_rule_hard": tier_rule_hard,
        "consistency": consistency,
        "per_case": per_case,
        "callouts": callouts,
        "cost": cost,
        "duration": duration,
        "provenance": provenance,
        "totals": totals,
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def escape_embedded_json(obj):
    """Serialize an object for embedding inside a <script> block.

    The escaping here is byte-identical to v1's logic -- these are hard-won
    safeguards; do not simplify:
    - Escape all '<' to prevent HTML5 parser state transitions inside <script>
      (covers </script> termination, <!-- escape state, <script double-escape)
    - Strip C1 control characters (U+007F-U+009F) that json.dumps does not
      escape; literal C1 bytes in <script> blocks break browser parsing
    """
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("<", "\\u003c")
    text = "".join(
        ch for ch in text
        if ord(ch) >= 0x20 or ch in "\n\r\t"
        if not (0x7F <= ord(ch) <= 0x9F)
    )
    return text


def generate_html(data_bundle, precomputed):
    """Generate the report HTML by filling the sibling template.

    Mode-agnostic: receives whichever DATA shape build_data_bundle produced
    (inline transcripts for --single-file; transcripts_index for bundles)
    and substitutes it unchanged — the template feature-detects the shape.

    The HTML/CSS/JS lives in viewer_template.html next to this script.
    Dynamic content is substituted via str.replace() on unique placeholder
    tokens -- NOT str.format(), because the template is full of literal
    CSS/JS braces that str.format() would misinterpret as fields.

    Substitution order matters: the fully-controlled small placeholders are
    filled first; the data bundle (which embeds arbitrary transcript content
    that could in principle contain placeholder-like text) is substituted
    last, so loaded content can never be treated as a placeholder.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "viewer_template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    generated_display = data_bundle["generated_at"][:19].replace("T", " ")
    data_json = escape_embedded_json(data_bundle)
    precomputed_json = escape_embedded_json(precomputed)

    # Hero static-fallback counts (v3.1.1): the hero-models / hero-runs span
    # text is substituted at build time from the same embedded totals that
    # renderHero() reads, so the no-JS fallback can never go stale — the JS
    # refill becomes a belt-and-braces no-op writing identical values.
    totals = precomputed.get("totals", {})
    hero_models = str(totals.get("n_models", 0))
    hero_runs = f"{totals.get('total_runs', 0):,}"

    html = html.replace("__GENERATED_DISPLAY__", generated_display)
    html = html.replace("__HERO_MODELS__", hero_models)
    html = html.replace("__HERO_RUNS__", hero_runs)
    html = html.replace("__PRECOMPUTED_JSON__", precomputed_json)
    html = html.replace("__DATA_JSON__", data_json)

    return html


def write_transcript_shards(bundle_dir, index, transcripts, subagent_transcripts):
    """Write per-result-set transcript shards under {bundle_dir}/data/.

    Each shard holds ONLY its set's entries, keys unchanged in the full
    "{result_set}/{run_dir}" composite form, so the template's lookup
    (shard.transcripts[r.result_set+"/"+r.run_dir]) is byte-identical to
    the single-file inline lookup — no key surgery on either side.

    Serialization reuses escape_embedded_json deliberately: shards are
    fetched and JSON.parse'd, never seen by the HTML tokenizer, so the
    \\u003c escaping is not strictly required — but it is a valid JSON
    escape, and one serializer everywhere keeps the C1-control-character
    hygiene without maintaining a second code path.

    Returns (n_shards, total_bytes, (largest_set_ts, largest_bytes)) for
    the bundle report in main().
    """
    data_dir = os.path.join(bundle_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    by_set_main = {}
    for key, val in transcripts.items():
        by_set_main.setdefault(key.split("/", 1)[0], {})[key] = val
    by_set_sub = {}
    for key, val in subagent_transcripts.items():
        by_set_sub.setdefault(key.split("/", 1)[0], {})[key] = val

    stats = []
    for ts in index:
        shard = {
            "transcripts": by_set_main.get(ts, {}),
            "subagent_transcripts": by_set_sub.get(ts, {}),
        }
        path = os.path.join(data_dir, shard_filename(ts))
        with open(path, "w", encoding="utf-8") as f:
            f.write(escape_embedded_json(shard))
        stats.append((ts, os.path.getsize(path)))

    total = sum(size for _, size in stats)
    largest = max(stats, key=lambda x: x[1]) if stats else (None, 0)
    return len(stats), total, largest


# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------

def print_summary(data_bundle, transcripts, subagent_transcripts,
                  n_timed_out_excluded=0):
    """Print a summary of what was loaded.

    Takes the loaded transcript dicts directly (not from data_bundle):
    bundle-mode DATA carries only transcripts_index, so the bundle keys
    are mode-dependent while these counts are not.
    """
    print("\n=== DAAF Benchmark Results Viewer Generator ===\n")

    for rs in data_bundle["result_sets"]:
        err_pct = (
            f" ({rs['errored_runs']/rs['total_runs']*100:.0f}%)"
            if rs["total_runs"] > 0
            else ""
        )
        print(f"  {rs['phase_label']}")
        print(f"    Timestamp:  {rs['timestamp']}")
        print(f"    Runs:       {rs['total_runs']} ({rs['errored_runs']} errored{err_pct})")
        print(f"    Models:     {', '.join(rs['models'])}")
        set_cost = rs.get("total_cost_usd")
        set_cost_label = (
            f"${set_cost:.2f}"
            if isinstance(set_cost, (int, float)) and not isinstance(set_cost, bool)
            else "unavailable"
        )
        print(f"    Cost:       {set_cost_label}")
        print(f"    Criteria:   {len(rs['criterion_names'])} dispatch + "
              f"{len(rs.get('subagent_criterion_names', []))} subagent")
        print()

    total_runs = len(data_bundle["runs"])
    total_transcripts = len(transcripts)
    total_subagent = sum(len(v) for v in subagent_transcripts.values())
    total_cases = len(data_bundle["cases"])
    transcripts_included = "transcripts" in data_bundle or "transcripts_index" in data_bundle
    observed_set_costs = [
        rs["total_cost_usd"] for rs in data_bundle["result_sets"]
        if isinstance(rs.get("total_cost_usd"), (int, float))
        and not isinstance(rs.get("total_cost_usd"), bool)
    ]
    total_cost = sum(observed_set_costs) if observed_set_costs else None

    print(f"  Totals:")
    print(f"    Result sets:           {len(data_bundle['result_sets'])}")
    print(f"    Runs loaded:           {total_runs} completed")
    print(f"    No-signal excluded:    {n_timed_out_excluded} "
          f"(timed_out flag, status stalled/timed_out, or legacy instant-exit "
          f"stub; dropped at load, absent from all metrics and the embedded "
          f"data)")
    print(f"    Cases loaded:          {total_cases}")
    if transcripts_included:
        print(f"    Transcripts condensed: {total_transcripts}")
        print(f"    Subagent transcripts:  {total_subagent}")
    else:
        print(f"    Transcripts:           EXCLUDED from this build "
              f"(--no-transcripts / single-file default; DATA carries neither "
              f"transcripts nor transcripts_index)")
    total_cost_label = f"${total_cost:.2f}" if total_cost is not None else "unavailable"
    print(f"    Total cost:            {total_cost_label}")
    print()


def print_precomputed_report(precomputed):
    """Print a sanity report of the precomputed metrics bundle."""
    print("=== Precomputed Metrics Sanity Report ===\n")

    print("  Runs per eval group:")
    pmp = precomputed["per_model_phase"]
    for g in precomputed["eval_groups"]:
        gid = g["id"]
        n = sum(cells[gid]["n_runs"] for cells in pmp.values() if gid in cells)
        perfect = sum(cells[gid]["perfect_count"]
                      for cells in pmp.values() if gid in cells)
        print(f"    {g['label']}: {n} runs, {perfect} perfect")
    print()

    rule = precomputed.get("tier_rule", {})
    print(f"  Tier rule applied: {rule.get('method', '?')} "
          f"(gap threshold {rule.get('gap_threshold', '?')}) -> "
          f"{len(precomputed['tiers'])} tiers")
    rule_h = precomputed.get("tier_rule_hard", {})
    print(f"  Critical-metric tier rule: {rule_h.get('method', '?')} -> "
          f"{len(precomputed.get('tiers_hard', []))} tiers over "
          f"{len(precomputed.get('composite_hard', {}))} models")
    print("  Composite leaderboard (tier | model | composite | components | n):")
    comp = precomputed["composite"]
    ranked = sorted(comp.items(), key=lambda kv: (-kv[1]["score"], kv[0]))
    for model, entry in ranked:
        comps = " ".join(
            f"{gid.split('_')[-1][:4]}={entry['components'][gid]:.2f}"
            for gid in entry["components_present"]
        )
        partial = " [partial]" if entry["partial_data"] else ""
        print(f"    {entry['tier']:>3} | {model:<22} | {entry['score']:.3f} | "
              f"{comps} | n={entry['n_total']}{partial}")
    print()

    print("  Efficiency frontier, battery-cost formulation, composite/perfect "
          "(cost asc | model | est. battery $ | score; dollars are "
          "maintainer-only — the viewer shows multipliers):")
    bat_frontiers = precomputed["cost"].get("frontiers", {}).get("battery", {})
    for pt in bat_frontiers.get("composite", {}).get("perfect", []):
        print(f"    {pt['model']:<22} | ${pt['price']:8.2f} | "
              f"{pt['score']:.3f}")
    print()

    battery = precomputed["cost"].get("battery") or {}
    bat_models = battery.get("models") or {}
    if bat_models:
        print(f"  Estimated cost per benchmark battery "
              f"({battery.get('battery_size')} probes; uncached basis, "
              f"current list rates; x vs {battery.get('reference_model')}):")
        ranked_bat = sorted(bat_models.items(),
                            key=lambda kv: -(kv[1]["est_battery_cost"] or 0))
        for model, b in ranked_bat:
            mult = b.get("cost_multiplier_vs_ref")
            mult_s = f"{mult:5.2f}x" if mult is not None else "    -"
            stale_s = " [STALE snapshot]" if b.get("stale") else ""
            print(f"    {model:<22} | ${b['est_battery_cost']:8.2f} | "
                  f"{mult_s} | {b['basis']}{stale_s}")
        print()

    totals = precomputed["totals"]
    n_disc = sum(1 for p in precomputed["provenance"] if p["run_count_discrepancy"])
    gw = precomputed["callouts"]["global_weakest"]
    # Timed-out runs were excluded at load (v3.3.0); total_runs already counts
    # completed runs only. The per-load excluded count is reported by
    # print_summary (which receives it) — it is not in this function's scope.
    print(f"  Total runs: {totals['total_runs']} completed | "
          f"models: {totals['n_models']} | cases: {totals['n_cases']} | "
          f"sets: {totals['n_result_sets']} ({n_disc} with run-count discrepancy)")
    # Partial-pass disclosure: a partial summary is mid-flight or was killed
    # before completing all expected runs (progressive-archiving redesign).
    partial_sets = [p for p in precomputed["provenance"] if p.get("partial")]
    if partial_sets:
        print(f"  PARTIAL result sets ({len(partial_sets)} — incomplete passes):")
        for p in partial_sets:
            done = p.get("runs_completed")
            exp = p.get("runs_expected")
            frac = f"{done}/{exp}" if done is not None and exp is not None else "?"
            print(f"    {p['timestamp']} ({p['phase_label']}): "
                  f"{frac} runs completed")
    print(f"  Pricing loaded for {len(precomputed['cost'].get('models', []))} models "
          f"(published list rates; observed spend tracking removed)")
    excluded = (totals.get("generation_params") or {}).get("results_excluded") or []
    if excluded:
        print(f"  Excluded result sets (--exclude-results): {', '.join(excluded)}")
    if gw:
        print(f"  Weakest criterion overall: {gw['name']} "
              f"({gw['passed']}/{gw['total']} = {gw['rate']:.0%}, "
              f"{gw['group_label']})")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    base_dir, results_dir, datasets_dir, output_path = resolve_paths(args)
    single_file = args.single_file is not None

    # Transcript inclusion (v3.4.0). Tri-state: an explicit --transcripts/
    # --no-transcripts wins; otherwise the mode default applies — bundle
    # INCLUDES (lazy shards, the official website artifact), single-file
    # EXCLUDES (transcript-lite offline monolith). See parse_args and the
    # "Transcript-inclusion control" dev guide above PHASE_MAP.
    if args.transcripts is None:
        include_transcripts = not single_file
    else:
        include_transcripts = args.transcripts

    tx_state = "included" if include_transcripts else "EXCLUDED"
    print(f"Results dir: {results_dir}")
    print(f"Datasets dir: {datasets_dir}")
    print(f"Output ({'single-file' if single_file else 'bundle'}, "
          f"transcripts {tx_state}): {output_path}")

    # Load data
    result_sets = load_result_sets(results_dir, args.results, args.exclude_results)
    if not result_sets:
        print("ERROR: No result sets found.", file=sys.stderr)
        sys.exit(1)

    cases = load_cases(datasets_dir)
    runs, anth_token_totals, n_timed_out_excluded = load_runs(
        results_dir, result_sets, cases)

    # Renumber reps globally: runs from different result sets for the same
    # (phase, model, case_id) all have rep=0. Assign sequential rep numbers
    # so the viewer can display multiple reps in separate columns.
    from collections import defaultdict
    rep_counters = defaultdict(int)
    phase_lookup = {rs["timestamp"]: rs["phase"] for rs in result_sets}
    for run in runs:
        phase = phase_lookup.get(run["result_set"], "")
        key = (phase, run["model"], run["case_id"])
        run["rep"] = rep_counters[key]
        rep_counters[key] += 1

    # Transcript condensation is the expensive load step and the dominant byte
    # source; skip it entirely when the build excludes transcripts (v3.4.0
    # single-file default and bundle --no-transcripts).
    if include_transcripts:
        transcripts, subagent_transcripts = load_transcripts(results_dir, runs)
    else:
        transcripts, subagent_transcripts = {}, {}
    model_pricing = load_model_pricing(base_dir)
    reconciliation = load_reconciliation(base_dir)

    # Build bundle (data prep is fully shared between modes; the shapes
    # diverge only here and at write time — see build_data_bundle)
    data_bundle = build_data_bundle(
        result_sets, cases, runs, transcripts, subagent_transcripts,
        model_pricing=model_pricing,
        inline_transcripts=single_file,
        include_transcripts=include_transcripts,
    )

    # Precomputed metrics (embedded as PRECOMPUTED alongside DATA)
    generation_params = {
        "results_filter": args.results if args.results else "all",
        "results_excluded": args.exclude_results if args.exclude_results else [],
        "output_mode": "single-file" if single_file else "bundle",
        "transcripts_included": include_transcripts,
        "generated_at": data_bundle["generated_at"],
        "generator_version": data_bundle["generator_version"],
    }
    precomputed = build_precomputed(result_sets, cases, runs, generation_params,
                                    model_pricing=model_pricing,
                                    anth_token_totals=anth_token_totals,
                                    reconciliation=reconciliation)

    # Print summaries
    print_summary(data_bundle, transcripts, subagent_transcripts,
                  n_timed_out_excluded)
    print_precomputed_report(precomputed)

    # Generate HTML
    html = generate_html(data_bundle, precomputed)

    # Write output
    if single_file:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Single-file artifact written: {output_path}")
        print(f"  File size: {file_size_mb:.2f} MB")
    else:
        os.makedirs(output_path, exist_ok=True)
        index_path = os.path.join(output_path, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)
        index_mb = os.path.getsize(index_path) / (1024 * 1024)
        print(f"  Bundle written: {output_path}/")
        print(f"    index.html:  {index_mb:.2f} MB")
        if include_transcripts:
            # transcripts_index is present on DATA only when transcripts are
            # included; shards are written next to index.html.
            n_shards, shard_bytes, largest = write_transcript_shards(
                output_path, data_bundle["transcripts_index"],
                transcripts, subagent_transcripts)
            print(f"    Shards:      {n_shards} files, "
                  f"{shard_bytes / (1024 * 1024):.2f} MB total in data/")
            if largest[0]:
                print(f"    Largest:     {shard_filename(largest[0])} "
                      f"({largest[1] / (1024 * 1024):.2f} MB)")
            print(f"  Serve over http(s) — transcripts are fetched on demand "
                  f"(e.g. `python3 -m http.server` from the bundle dir); on "
                  f"file:// the Run Explorer shows a fetch-fallback message.")
        else:
            print(f"    Shards:      none (--no-transcripts; index.html only)")
            print(f"  Transcript-less bundle — the Run Explorer shows a "
                  f"'transcripts not included in this build' notice.")
    print(f"  Done.\n")


if __name__ == "__main__":
    main()
