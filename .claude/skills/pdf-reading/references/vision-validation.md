# Vision: policy, gating, routes and the validation probe

When an agent may look at page images, how that choice is recorded and
audited, how each provider route treats images, and how a model earns a
place on the vision-validated list. The list itself lives in SKILL.md
§ "Vision-validated model list" (one source of truth); this page holds its
rules, candidates and history.

Labels: **[obs]** observed by a command or code read in a DAAF session,
**[doc]** quoted from vendor documentation fetched into a DAAF workspace,
**[inf]** inference. Sources: spec `research/2026-10-02_FrameworkDev_ScholarlySearch/2026-10-02_LitReview_Spec.md`
§7.3; preliminary notes 08 (§ 4) and 10 (§ 4) there; and the shim session's
memo `research/2026-09-06_FrameworkDev_GPT_Shim_Native_Search/opus_audit_2026-10-12/REPLY_2026-10-13_ImageFidelity.md`.

**Contents:** Why vision is gated · Modes · Gating (Option C) · Routes ·
Cost · The validation probe · Promotion and demotion · Candidates · List
history

## Why vision is gated

Vision transcription of tables is not cell-level numeric fidelity.
ParseBench's table metric (GriTS + TableRecordMatch, a structure score) gave
Opus 5.5 93.86 and Fable 5.1 91.52 [doc, vendor benchmark]; WildTableBench
reports "Only one model exceeds 50% accuracy" [doc]; a meta-analysis
extraction study found "near-zero reliability" for full numeric tuples [doc]
(note 08 § 4). A structure score near 94 says nothing about whether a sign or
a decimal survived [inf]. So vision stays a **second reading**: it may
corroborate the text layer, read a scanned page, or flag a text-layer
problem, but it is never ground truth, and every text/vision disagreement is
logged in the card (spec §7.3; user decision D-20 item 4, which overrides the
source skill's "prefer vision").

## Modes

CLAUDE.md § User Preferences, "PDF page-image cross-checking" (D-7, applied
2026-10-13):

| Mode | Renders | Reader looks at |
|------|---------|-----------------|
| `auto` (default) | `pdf_ingest --render flagged` | Only pages `pdf_ingest` flags as needing vision (tables, figures, numeric-dense, scanned, garbled, rotated, low agreement, suspected OCR layer) |
| `all-pages` | `pdf_ingest --render all` | Every page (about +4k tokens a page on Anthropic; ~+120k for a 30-page paper) |
| `off` | any | Nothing; text layer only |

Both `auto` and `all-pages` apply **only** when the reader's exact model ID
and route are on the list (user decision D-20 item 3). Otherwise the reader
works from the text layer and lane B only, the card says `vision:
unavailable` (front matter) and `vision_validated: false` (block), and
renders stay unopened. Rendering still happens under `auto`, so a later
validated reader or a human can use the same images.

## Gating (Option C, user-agreed)

A script cannot tell which subagent model runs it: no agent-ID environment
variable was observed (note 10 § 4) [obs]. So the check is done by the
reader and audited by the orchestrator.

**Reader, before any vision use:**
1. Take your exact model ID from your system prompt ("The exact model ID is
   …") and drop a trailing `[1m]`. List keys are written bare: Claude Code
   strips `[1m]` before sending, and `.message.model` carries the bare name
   [obs, memo § 4].
2. Take the route from the dispatch (the orchestrator knows the install
   route; the five names are below). A reader that is not told its route
   treats vision as unavailable.
3. Look for an exact (model ID, route) row in SKILL.md's list. No row → text
   only.
4. Record in the card. Block: `reader_model` (the bare ID), `vision_mode`,
   `vision_validated` (true only on a row match), `vision_list_version`.
   Front matter: `reader_model_source: self-report`, `reader_route`,
   `vision: validated|unavailable`.

**Orchestrator, after the reader returns:**
1. Read the transcript-derived model: the `context-reporter` hook cache
   `/tmp/claude-subagent-model-<session>-<agent_id>` (reading `/tmp` caches is
   permitted; never write there) or `.message.model` in the subagent's
   transcript.
2. Compare it with the card's `reader_model`. Match →
   `transcript-confirmed`; otherwise a mismatch: treat every vision-derived
   item as unvalidated (re-read text-only or downgrade the claims) and tell
   the user.
3. Record the result outside the card (session state or the review's
   evidence ledger), keyed by the card's SHA-256. Editing the card would
   break the hash its `card_check` JSON records.

**Shim caveat.** Over the GPT provider shim, `.message.model` is the requested
model name echoed back by the shim, not the upstream's own report of which
model served the request [obs, memo § 4]. It is safe to key the list on, but
it is not independent confirmation of the serving model.

`lit_verify` enforces consistency with what the card declares
(`vision_mode` not `off` and `vision_validated` true, or every vision claim
fails). From 1.6.0 it also carries a copy of the list
(`VISION_VALIDATED_LISTS`, one entry per list version): `vision_validated`
true for a `reader_model` that is not on the card's `vision_list_version`
entry fails as `VISION_NOT_ON_LIST`, as does an unknown list version, and
vision then counts as unavailable for that card. It reads only the block,
never the front matter, so it checks the model ID, not the route; identity
and route stay with the orchestrator audit above. The embedded copy is
`VISION_LIST_VERSION` and `VISION_VALIDATED_LISTS` in
`scripts/lit_verify.py` (1.7.0: one version, `vision-list-2026-10-19`, with
no rows), recorded in every `card_check` under `constants`, so a check
result shows which list it was judged against.

## Routes

The five install routes (names as in the `daaf-deploy-smoke-testing` skill):
`anthropic-subscription`, `anthropic-api`, `chatgpt-subscription` (GPT shim),
`openai-api` (GPT shim), `openrouter`. A list row names one route; a model
validated on one route is not validated on another, because image handling
differs by route [inf, note 10 § 4].

| Route family | Image rules | DAAF consequence |
|--------------|-------------|------------------|
| Anthropic (subscription, API) | Once a request holds more than 20 images, earlier turns included, every image is capped at 2000 px and larger ones "are rejected with an invalid_request_error" [doc, note 08 § 4]. On Amazon Bedrock and Google Cloud, PDF document blocks also count toward the 20 [doc]. Token cost ≈ ⌈width / 28⌉ × ⌈height / 28⌉ [doc] | `pdf_ingest` renders at 2000 px (long side), so a long reading conversation never trips the rejection |
| GPT shim (chatgpt-subscription, openai-api) | The shim sends each image as `input_image` with `detail: "auto"` and does no resizing of its own [obs, memo § 1]. In the shim's Brief 04 (shim 1.4.9, ChatGPT lane), `auto` delivered native resolution on gpt-6-sol, gpt-6.1-sol, gpt-6-luna, gpt-6-astra and gpt-5.6-sol: 3,705 image tokens each for a 1547×2000 page, 20/20 normal and 20/20 small numbers [obs; one synthetic page per model, not a repeatability study, no dense tables or reading order]. OpenAI has **no** "more than 20 images" rule: within a model's patch budget oversize images are downscaled **silently**; an image above 30,000 patches is rejected, not resized; up to 1,500 images and 512 MB per request [doc, memo § 3]. A 2000 px page is about 3,100 patches [inf, arithmetic] | Our renders pass at native size today; a downscale would be silent, so the table probe, not the absence of errors, is the gate |
| OpenRouter | No DAAF observation recorded | Treat as unprobed |

**Read on a `.pdf`.** Claude Code's Read tool sends a PDF as rendered page
images on both the Anthropic and the shim routes [obs, memo § 2]. That is
vision use, and the resolution and page choice are not ours. Use
`pdf_ingest`'s renders instead, and only when vision is validated.

The shim session recommends keeping shim-routed GPT models `vision:
unavailable` until the table probe below passes on that route (memo,
"Bottom line"). If a shim change alters image handling, re-run the probe after
it (memo § 5).

## Cost

| Route | Per 2000 px page | 30-page paper, every page |
|-------|------------------|---------------------------|
| Anthropic | ≈ 4k tokens (a 1547×2000 page: 56 × 72 = 4,032 by the formula) | ≈ +120k |
| GPT shim, native size | ≈ 3,705 tokens (3,087 patches × 1.2) [obs] | ≈ +111k [inf] |

`auto` usually touches a handful of flagged pages; `all-pages` is the
expensive mode. A 300-DPI crop is smaller than a full page.

## The validation probe (not yet run)

The probe and its scorer are a **later S3 step**; nothing below has been run.
Design from note 08 § 4, with the D-20 thresholds:

1. **Fixtures**, versioned with SHA-256: about 12 synthetic tables typeset
   with Quarto's bundled typst from a seeded table of roughly 300 numeric
   cells, covering U+2212 and ASCII minus, SEs in parentheses, stars and
   daggers, `.05` without a leading zero, thousands separators, 8-pt type, a
   landscape page, two tables side by side, merged headers; optionally a few
   pages from CC-BY papers with ground truth taken from the text layer and
   hand-checked. Synthetic only for anything committed (the repository is
   published).
2. **Rendering** identical to production: `pdftoppm -png -scale-to 2000`
   (via `pdf_ingest`), plus 300-DPI crops.
3. **Prompt**: transcribe as TSV, verbatim, no inference; "transcribe all
   cells; do not stop early" (lessons kept from the source skill's prompt
   patterns).
4. **Scoring script** (captured, `run_with_capture.sh`): normalize numbers
   with `pdf_text_common`'s number rules, match cells exactly keyed by (row
   label, column label), and count sign errors, decimal shifts, invented
   cells and missing cells.
5. **Promotion rule**: 3 independent runs, every one meeting **all** of:
   ≥ 99.5% numeric exact match overall; 0 sign errors; 0 decimal shifts;
   0 invented cells. (Note 08 also proposed ≥ 98% on the 8-pt and rotated
   subsets; adopt it if the bake-off shows those subsets behave differently.)
6. **Record**: model ID (bare, as transcript-derived), route, effort setting,
   fixture version and hashes, per-cell diff parquet, run dates, and the
   captured script paths. Re-probe when the model ID, the route's image
   handling (for example a shim `detail` change) or the render recipe
   changes.

The shim session's Brief 04 fixture and scorer (one page, 40 numbers) can be
reused as a smoke test; it is too small to be the gate (memo § 5).

## Promotion and demotion

- Add a row to SKILL.md's list only with the probe record path, and bump
  `vision_list_version` (e.g. `vision-list-2026-11-02`). Add the same
  version and rows to `lit_verify`'s `VISION_VALIDATED_LISTS` (and set
  `VISION_LIST_VERSION`), or cards read under it fail `VISION_NOT_ON_LIST`.
  Update `skill-last-updated`. Never add a model ID that was not transcript-derived
  in the probe run.
- Remove a row (and bump the version) when a re-probe fails or the route's
  image handling changes untested. Cards keep the version they were read
  under, so older cards stay interpretable.

## Candidates (to be probed; not list entries)

| Candidate | Route(s) | Note |
|-----------|----------|------|
| Claude Opus 5.5 | anthropic-subscription, anthropic-api | Current per the models overview fetched for note 08 (§ 4, line 104) |
| Claude Fable 5.1 | anthropic-subscription, anthropic-api | Current, same source |
| Claude Sonnet 5.5 | anthropic-subscription, anthropic-api | Replaces "Sonnet 5", which the same overview lists under Legacy models |
| gpt-6-sol, gpt-6.1-sol, gpt-6-astra, gpt-6-luna | chatgpt-subscription (shim) | The shim lane's models (memo § 5; gpt-6-luna is the sonnet tier) |
| One GPT model | openai-api (shim) | Parity check: same translation code (memo § 5) |

Exact model IDs for these are taken from the probe runs' transcripts, never
from this table.

## List history

| Version | Date | Change |
|---------|------|--------|
| `vision-list-2026-10-19` | 2026-10-19 | List created empty (FE-4, Lit Review S3). No probe run yet |
| `vision-list-2026-10-19` | 2026-10-23 | Unchanged, now also embedded in `lit_verify` (1.6.0, S3-A, D-24): `vision_validated: true` against it fails as `VISION_NOT_ON_LIST` until a model is promoted |
