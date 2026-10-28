# Vision: policy, gating, routes and the validation probe

When an agent may look at page images, how that choice is recorded and
audited, how each provider route treats images, and how a model earns a
place on the vision-validated list. The list itself lives in SKILL.md
§ "Vision-validated model list" (one source of truth); this page holds its
rules, candidates and history.

Labels: **[obs]** observed by a command or code read in a DAAF session,
**[doc]** quoted from vendor documentation fetched into a DAAF workspace,
**[inf]** inference. Sources (maintainer-only, not shipped): spec `research/2026-10-02_FrameworkDev_ScholarlySearch/2026-10-02_LitReview_Spec.md`
§7.3; preliminary notes 08 (§ 4) and 10 (§ 4) there; and the shim session's
memo `research/2026-09-06_FrameworkDev_GPT_Shim_Native_Search/opus_audit_2026-10-12/REPLY_2026-10-13_ImageFidelity.md`.

**Contents:** Why vision is gated · Modes · Gating (Option C) · Routes ·
Cost · The validation probe · Promotion and demotion · Candidates · List
history

## Why vision is gated

Vision transcription of tables is not cell-level numeric fidelity.
ParseBench's table metric (GriTS + TableRecordMatch, a structure score) gave
Opus 5.5 93.86 and Fable 5.1 91.52 [doc, vendor benchmark,
https://github.com/run-llama/ParseBench README]; WildTableBench reports "Only
one model exceeds 50% accuracy" [doc, https://arxiv.org/abs/2605.01018]; a
meta-analysis extraction study found "near-zero reliability" for full
numeric tuples [doc, https://arxiv.org/abs/2602.10881] (all three accessed
2026-10-12). A structure score near 94 says nothing about whether a sign or
a decimal survived [inf]. So vision stays a **second reading**: it may
corroborate the text layer or flag a text-layer problem, and on a page
flagged `scanned` or `ocr_layer_suspected` it is an unvalidated reading (no
model is validated there, § The validation probe). It is never ground truth, and every text/vision disagreement is
logged in the card (user decision, 2026-10-13, which overrides the source
skill's "prefer vision").

## Modes

CLAUDE.md § User Preferences, "PDF page-image cross-checking" (applied
2026-10-13):

| Mode | Renders | Reader looks at |
|------|---------|-----------------|
| `auto` (default) | `pdf_ingest --render flagged` | Only pages `pdf_ingest` flags as needing vision (tables, figures, numeric-dense, scanned, garbled, rotated, low agreement, suspected OCR layer) |
| `all-pages` | `pdf_ingest --render all` | Every page (about +4k tokens a page on Anthropic; ~+120k for a 30-page paper) |
| `off` | any | Nothing; text layer only |

Both `auto` and `all-pages` apply **only** when the reader's exact model ID
and route are on the list (user decision, 2026-10-13). Otherwise the reader
works from the text layer and lane B only, the card says `vision:
unavailable` (front matter) and `vision_validated: false` (block), and
renders stay unopened. Rendering still happens under `auto`, so a later
validated reader or a human can use the same images.

## Gating (Option C, user-agreed)

A script cannot tell which subagent model runs it: no agent-ID environment
variable was observed [obs]. So the check is done by the
reader and audited by the orchestrator.

**Reader, before any vision use:**
1. Take your exact model ID from your system prompt ("The exact model ID is
   …") and drop a trailing `[1m]`. List keys are written bare: Claude Code
   strips `[1m]` before sending, and `.message.model` carries the bare name
   [obs by the GPT-shim maintainer session, 2026-10-13; "the shim session"
   below].
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
   break the hash its `card_check` JSON records. Record the results of
   steps 4 and 5 the same way.
4. Check the card's `reader_route` (front matter) against the install route
   you put in the dispatch. `lit_verify` never reads the route. A mismatch,
   or a route the row does not list: treat every vision-derived item as
   unvalidated and tell the user.
5. Settle each `VISION_ON_SCAN_PAGE` item in the `card_check` (from
   `lit_verify` 1.8.0 part 5; it lists them under `review_items`). The gate
   raises one for every `vision`/`both` claim, and every `vision_only`
   digest it uses, on a page it re-derives from the source as truly scanned
   or as carrying an OCR text layer, so the list is complete for scan and
   OCR-layer pages. Then check by hand what the gate does not flag: vision
   readings on pages with `pages[].class: "sparse"` and on figure or chart
   pages (`figure` flag, class `normal`), which are also outside the list's
   scope. No model is validated on any of these pages, so treat each as an
   unvalidated reading: have a person check it against the page, re-read it
   text-only, or downgrade the claim, and tell the user.

**Shim caveat.** Over the GPT provider shim, `.message.model` is the requested
model name echoed back by the shim, not the upstream's own report of which
model served the request [obs, shim session]. It is safe to key the list on, but
it is not independent confirmation of the serving model.

`lit_verify` enforces consistency with what the card declares
(`vision_mode` not `off` and `vision_validated` true, or every vision claim
fails). From 1.6.0 it also carries a copy of the list
(`VISION_VALIDATED_LISTS`, one entry per list version): `vision_validated`
true for a `reader_model` that is not on the card's `vision_list_version`
entry fails as `VISION_NOT_ON_LIST`, as does an unknown list version, and
vision then counts as unavailable for that card. It reads only the block,
never the front matter, so it checks the model ID, not the route; identity
and route stay with the orchestrator audit above. Of the list's page scope
(§ The validation probe) it checks the scan part, from 1.8.0 part 5: it
re-derives the page flags from the source, and a vision reading on a page
that comes out truly scanned (`pages[].class: "scanned"`) or with an OCR
text layer (`pages[].ocr_layer: true`) is `VISION_ON_SCAN_PAGE`, a review
item, so the card is NEEDS_REVIEW rather than PARTIAL. It does not flag
vision readings on sparse pages or on figure and chart pages, which are
outside the scope too (step 5 above checks them by hand). It applies
whatever the reader's list status; a forged flag in the card or the
manifest cannot hide a scan, except in one documented residual (a scan or
OCR layer whose only image evidence is a pdfplumber image box, removed from
a forged manifest in a document where pdfimages lists images; 0 such pages
in the five bake-off PDFs), and a page whose type could not be re-derived
counts as a scan (`evidence-card.md` § Vision consistency). On such a page
the reader writes `?` for digits it cannot read, labels the reading as an
unvalidated reading of a scan, logs every disagreement and reports it; the
orchestrator settles the review items (step 5 above). The
embedded copy is `VISION_LIST_VERSION` and `VISION_VALIDATED_LISTS` in
`scripts/lit_verify.py` (since 1.8.0 part 4: two versions,
`vision-list-2026-10-19` with no rows, kept so older cards stay
interpretable, and the current `vision-list-2026-10-28` with ten rows, five
model IDs on the two Anthropic routes), recorded in every `card_check` under
`constants`, so a check result shows which list it was judged against.

## Routes

The five install routes (names as in the `daaf-deploy-smoke-testing` skill):
`anthropic-subscription`, `anthropic-api`, `chatgpt-subscription` (GPT shim),
`openai-api` (GPT shim), `openrouter`. A list row names one route; a model
validated on one route is not validated on another, because image handling
differs by route [inf].

| Route family | Image rules | DAAF consequence |
|--------------|-------------|------------------|
| Anthropic (subscription, API) | Once a request holds more than 20 images, earlier turns included, every image is capped at 2000 px and larger ones "are rejected with an invalid_request_error" [doc, Anthropic's vision documentation, fetched 2026-10-12]. On Amazon Bedrock and Google Cloud, PDF document blocks also count toward the 20 [doc]. Token cost ≈ ⌈width / 28⌉ × ⌈height / 28⌉ [doc] | `pdf_ingest` renders at 2000 px (long side), so a long reading conversation never trips the rejection |
| GPT shim (chatgpt-subscription, openai-api) | The shim sends each image as `input_image` with `detail: "auto"` and does no resizing of its own [obs, shim session]. In the shim session's 10-request image test (shim 1.4.9, ChatGPT lane), `auto` delivered native resolution on gpt-6-sol, gpt-6.1-sol, gpt-6-luna, gpt-6-astra and gpt-5.6-sol: 3,705 image tokens each for a 1547×2000 page, 20/20 normal and 20/20 small numbers [obs; one synthetic page per model, not a repeatability study, no dense tables or reading order]. OpenAI has **no** "more than 20 images" rule: within a model's patch budget oversize images are downscaled **silently**; an image above 30,000 patches is rejected, not resized; up to 1,500 images and 512 MB per request [doc, OpenAI's image documentation as quoted by the shim session]. A 2000 px page is about 3,100 patches [inf, arithmetic] | Our renders pass at native size today; a downscale would be silent, so the table probe, not the absence of errors, is the gate |
| OpenRouter | No DAAF observation recorded | Treat as unprobed |

**Read on a `.pdf`.** Claude Code's Read tool sends a PDF as rendered page
images on both the Anthropic and the shim routes [obs, shim session]. That is
vision use, and the resolution and page choice are not ours. Use
`pdf_ingest`'s renders instead, and only when vision is validated.

The shim session recommends keeping shim-routed GPT models `vision:
unavailable` until the table probe below passes on that route: a downscale
over the shim is silent, so only a passed probe shows fidelity. If a shim
change alters image handling, re-run the probe after it.

## Cost

| Route | Per 2000 px page | 30-page paper, every page |
|-------|------------------|---------------------------|
| Anthropic | ≈ 4k tokens (a 1547×2000 page: 56 × 72 = 4,032 by the formula) | ≈ +120k |
| GPT shim, native size | ≈ 3,705 tokens (3,087 patches × 1.2) [obs] | ≈ +111k [inf] |

`auto` usually touches a handful of flagged pages; `all-pages` is the
expensive mode. A 300-DPI crop is smaller than a full page.

## The validation probe (run 2026-10-28)

The thresholds were approved by the user on 2026-10-13. The probe ran on
2026-10-28 on the `anthropic-subscription` route, with this design:

1. **Synthetic fixtures**: 13 table pages typeset with typst from a seeded
   table, 381 numeric cells in all. They cover U+2212 and ASCII minus, SEs
   in parentheses, stars and daggers, `.05` without a leading zero,
   thousands separators, percentages, 8-pt type (two tables), a landscape
   page, two tables side by side, merged headers, and one table printed
   sideways. The key is the seeded table itself.
2. **Real pages** (a realism set): 16 pages from five open papers. Eleven
   table pages from four of the papers were keyed and scored, 1,081 cells. A
   cell is keyed only where poppler's text layer (the anchor) and
   pypdfium2's (lane B) agree on the whole row, so the key is text both
   extractors read the same way. On these 11 pages the two extractors agreed
   on every table row, so no row was left out [obs]. Five real pages were
   transcribed but not scored, since they have no such key: three figure
   pages, one table set as text entries with no numeric columns, and a 1973
   scan from the fifth paper. That scan carries someone else's OCR text
   layer, so `pdf_ingest` flags it `ocr_layer_suspected`, not `scanned`.
   The real pages are not committed (the repository is published).
3. **Rendering** as in production: every page is a `pdf_ingest` render,
   2000 px on the long side (`pdftoppm -png -scale-to 2000`). No 300-DPI
   crops were used, so crops are outside what was measured. The
   transcribers saw only the images, never a text layer. No effort setting
   was passed in the probe dispatches (Claude Code's default).
4. **Prompt**: transcribe every table to TSV, verbatim, no inference, `?`
   for a cell that cannot be read.
5. **Scorer**: a captured script (`run_with_capture.sh`) that runs a
   planted-error self-test (17 cases) before every scoring. Numbers are
   normalized with `pdf_text_common`'s number rules (`numbers-v6`), and each
   keyed cell is classed as exact, sign error, decimal shift, digit error,
   missing or invented. An independent bag-of-numbers recount agreed with
   the cell scores.
6. **Promotion rule**: 3 independent runs, every one meeting **all** of:
   ≥ 99.5% numeric exact match overall; 0 sign errors; 0 decimal shifts;
   0 invented cells. The design research also proposed ≥ 98% on the 8-pt
   and rotated subsets. No separate test was needed: every run was exact on
   every cell, so those subsets were exact too.
7. **Model IDs** are transcript-derived (`.message.model`, read through the
   `context-reporter` hook's cached value) and bare.
8. **Record**: the full probe record (model IDs, route, effort, fixture
   version and hashes, per-cell results, run dates, captured scripts) is
   kept with the maintainers; the shipped rows state the date and the
   measured result.

**Results (observed, 2026-10-28, `anthropic-subscription`):**

| Model ID | Runs passing | Synthetic exact, each run | Real exact, each run | Sign errors | Decimal shifts | Invented numbers |
|----------|--------------|---------------------------|----------------------|-------------|----------------|------------------|
| `claude-opus-5-5` | 3 of 3 | 381/381 | 1,081/1,081 | 0 | 0 | 0 |
| `claude-sonnet-5` | 3 of 3 | 381/381 | 1,081/1,081 | 0 | 0 | 0 |

**Behavior on the unscored 1973 scan** (flagged `ocr_layer_suspected`).
Opus 5.5 wrote `?` for digits it could not read. Sonnet 5, in 2 of 3 runs,
filled unreadable digits from the column's trend instead, which the prompt
forbids. Readings of one damaged cell differed across runs.

**The list's scope.** So this probe validates no model on scans. Every row
covers table pages with a digital text layer: pages with no `scanned` and no
`ocr_layer_suspected` flag in the ingest manifest. Pages with either flag
(truly scanned and sparse pages, and scans carrying an OCR text layer) were not
probed, and figure pages were not scored, so no model is validated on them.
A listed reader may still look at such a page, but the reading is
unvalidated: write `?` for any digit you cannot read, never infer one from
context, the column or a trend; label the reading in the card as an
unvalidated reading of a scan; log every text/vision/OCR disagreement; and
tell the orchestrator (§ Gating, orchestrator step 5). `lit_verify` sends
every vision reading on a truly scanned or OCR-layer page to a person
(`VISION_ON_SCAN_PAGE`, review), because a plausible-looking number read
from a scan often has no clean text to check it against. It does not flag
readings on sparse pages (flagged `scanned`, little text, not mostly one
image) or on figure pages; the orchestrator checks those by hand.

**What the probe does not show:** fidelity on scanned or OCR-layer pages,
figure pages or 300-DPI crops; any route other than `anthropic-subscription`
(the `anthropic-api` rows are inference: the same models under the same
Anthropic image rules); the GPT models over the shim; the models admitted by
policy (§ Promotion and demotion).

Re-probe when the model ID, the route's image handling (for example a shim
`detail` change) or the render recipe changes. The shim session's own image
test (one page, 40 numbers) is a smoke test at most; it is too small to be
the gate.

## Promotion and demotion

A model reaches the list in one of two ways, and its row says which:

- **Probe promotion.** The model passes the probe above on that route. The
  row states the probe date and its measured result; the full probe record
  (model ID, route, effort setting, fixture version and hashes, per-cell
  results, run dates, captured scripts) is kept with the maintainers. The
  model ID is the one transcript-derived in the probe run: never add a
  guessed ID.
- **User policy admission.** The user decides to list a model that has not
  been probed. The row says "admitted <date> by user policy decision, not by
  DAAF quality validation", the list history gives the user's reasoning,
  and this page names where the ID came from, since it was not
  transcript-derived. Probing such a model later turns its row into a probe
  row, or removes it if the probe fails.

A row for a route the probe did not run on is labelled inference. Every
change bumps `vision_list_version` (e.g. `vision-list-2026-11-02`), adds the
same version and rows to `lit_verify`'s `VISION_VALIDATED_LISTS` (and sets
`VISION_LIST_VERSION`, or cards read under the new version fail
`VISION_NOT_ON_LIST`), adds a row to § List history and updates
`skill-last-updated`. Older versions stay in `lit_verify`.

Remove a row (and bump the version) when a re-probe fails or the route's
image handling changes untested. Cards keep the version they were read
under, so older cards stay interpretable.

**Admitted on 2026-10-28** (user policy decision, not DAAF quality
validation; the user's reasoning: "if sonnet 5 passed, those will as well as
strict improvements"). None of these IDs was transcript-derived in a probe:

| Model ID | Where the ID came from |
|----------|------------------------|
| `claude-sonnet-5-5` | Claude Code's gateway-compatibility documentation, fetched 2026-10-12: "while sonnet resolves to claude-sonnet-5-5 … a discovered claude-sonnet-5 still gets its own row" [doc] |
| `claude-fable-5-1` | The model list in Claude Code's environment, and DAAF's `context-reporter` tests, which call `claude-fable-5-1` the real model ID on Claude Code 2.1.261 [obs] |
| `claude-fable-5` | The ID used in DAAF's context-threshold registry (the `context-reporter` hook matches `*fable-5*`; its tests use `claude-fable-5`), and seen as `ANTHROPIC_MODEL` (`claude-fable-5[1m]`) in the environment of an `anthropic-subscription` deploy smoke-test run on 2026-07-15 [obs] |

Anthropic's models overview (fetched 2026-10-12) lists Opus 5.5 and Fable 5.1
as current and Sonnet 5 under Legacy models, replaced by Sonnet 5.5 [doc].

## Candidates (to be probed)

| Candidate | Route(s) | Note |
|-----------|----------|------|
| gpt-6-sol, gpt-6.1-sol, gpt-6-astra, gpt-6-luna | chatgpt-subscription (shim) | Not list entries. The shim lane's models (gpt-6-luna is the sonnet tier) |
| One GPT model | openai-api (shim) | Not a list entry. Parity check: same translation code |
| `claude-sonnet-5-5`, `claude-fable-5-1`, `claude-fable-5` | anthropic-subscription, anthropic-api | Listed by policy admission, not probed; a probe would confirm or remove them |
| All five listed models | anthropic-api | Listed by inference (the admitted models: admitted, route by inference); a probe on that route would confirm it |
| Any model, scanned pages and OCR-layer scans (`scanned` or `ocr_layer_suspected`) | any | No model is validated on them (§ The validation probe) |

Exact model IDs for a probe promotion are taken from the probe runs'
transcripts, never from this table.

## List history

| Version | Date | Change |
|---------|------|--------|
| `vision-list-2026-10-19` | 2026-10-19 | List created empty. No probe run yet |
| `vision-list-2026-10-19` | 2026-10-23 | Unchanged, now also embedded in `lit_verify` (1.6.0): `vision_validated: true` against it fails as `VISION_NOT_ON_LIST` until a model is promoted |
| `vision-list-2026-10-28` | 2026-10-28 | Ten rows, five model IDs, each on `anthropic-subscription` and `anthropic-api`. Probed on `anthropic-subscription` and passed (3 of 3 runs, every cell exact): `claude-opus-5-5`, `claude-sonnet-5`. Admitted by user policy decision, not by DAAF quality validation (not probed): `claude-sonnet-5-5`, `claude-fable-5-1`, `claude-fable-5`; the user's words: "if sonnet 5 passed, those will as well as strict improvements". Every `anthropic-api` row is inference (for the admitted models: admitted, route by inference). Every row covers table pages without a `scanned` or `ocr_layer_suspected` flag; pages with either flag were not probed. Embedded in `lit_verify` 1.8.0 (part 4); `vision-list-2026-10-19` is kept, still empty, so a card read under it still fails `VISION_NOT_ON_LIST` with `vision_validated: true` |
