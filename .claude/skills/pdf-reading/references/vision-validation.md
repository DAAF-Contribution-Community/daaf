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
ParseBench's table metric is GTRM, "the unweighted average of GriTS and
TableRecordMatch"; TableRecordMatch scores "each matched pair" of row
records "by binary cell-level agreement", and GriTS covers "cell content
recognition" as well as structure [doc, https://arxiv.org/html/2604.08538v3
and https://arxiv.org/abs/2203.12555, accessed 2026-10-28]. On it Opus 5.5
scored 93.86 and Fable 5.1 91.52 [doc, vendor benchmark,
https://github.com/run-llama/ParseBench README, accessed 2026-10-12]. The
93.86 is the row named plain "Anthropic Opus 5.5"; an "Anthropic Opus 5.5
(Effort High)" row scores 94.25 (README, 2026-10-12), and the
`leaderboard.csv` fetched 2026-10-28 still has both and adds "(Effort
Low)" at 92.69 [doc]. WildTableBench reports "Only one model exceeds 50%
accuracy" [doc, https://arxiv.org/abs/2605.01018]; a meta-analysis
extraction study found "near-zero reliability" for full numeric tuples
[doc, https://arxiv.org/abs/2602.10881] (both accessed 2026-10-12). An
aggregate table score near 94 does not show that every sign and decimal
survived: it still allows individual cells with a flipped sign or a shifted
decimal [inf]. So vision stays a **second reading**: it may
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
variable was observed [obs]. So the reader checks itself, and the
orchestrator audits the result with `lit_verify audit`, which takes the
model from records the reader does not write.

**Reader, before any vision use:**
1. Take your exact model ID from your system prompt ("The exact model ID is
   …") and drop a trailing `[1m]`. List keys are written bare: Claude Code
   strips `[1m]` before sending, and `.message.model` carries the bare name
   [obs by the GPT-shim maintainer session, 2026-10-13; "the shim session"
   below].
2. Take the route from the dispatch's `ROUTE:` line, exactly as written. The
   orchestrator copies that line from `lit_verify route` output and never
   types a route (§ Routes, "Where the route comes from"). A dispatch without
   a `ROUTE:` line means vision is unavailable.
3. Look for an exact (model ID, route) row in SKILL.md's list. No row → text
   only.
4. Record in the card. Block: `reader_model` (the bare ID), `vision_mode`,
   `vision_validated` (true only on a row match), `vision_list_version`.
   Front matter: `reader_model_source: self-report`, `reader_route` (the
   route from the `ROUTE:` line), `vision: validated|unavailable`.

**Orchestrator, before the first reader dispatch:** run `lit_verify route`
(§ Routes) and copy its `ROUTE:` line into every paper-reader dispatch.

**Orchestrator, after the reader returns** and `lit_verify card` has checked
its latest card, run the audit on that card:

```
bash /daaf/scripts/lit_verify.sh audit <PAPER_DIR> --card <CARD> --agent-id <ID> [--agent-id <ID> ...]
     [--transcript PATH ...] [--project PROJECT_DIR]
```

`<ID>` is the reader's agent ID, taken from the orchestrator's dispatch
result. Give one `--agent-id` for every reader dispatch that wrote the card:
a paper read in chunks gives one per chunk, and every chunk's reader must
show the card's model. A wrong ID is the case this check cannot see: an ID
of another reader of the same session that ran the same model confirms the
card, so copy each ID from its own dispatch result. `--transcript` names a
reader's own transcript (`agent-<ID>.jsonl`), read when the hook's cache has
no single match. `PROJECT_DIR` defaults to the folder above `papers/`;
`PAPER_DIR` must be `papers/<paper key>/` directly under it. The steps carry
the numbers of the `lit_verify.py` header; the record (step 3) is written
last:

| Step | What `lit_verify audit` does |
|------|------------------------------|
| Inputs | The card (directly inside `PAPER_DIR`) and the `card_check` of the card's latest recorded `lit_verify card` run, bound both ways: the `card_check` bytes must hash to the value its MANIFEST row recorded, and the card bytes to the value the `card_check` recorded. No recorded run, or either mismatch (for example a card edited after its check), is exit 9 |
| 1 Model | For each agent ID: reads the `context-reporter` hook's cache file `claude-subagent-model-<session>-<ID>` (read only; exactly one file must match). `<session>` is `$CLAUDE_CODE_SESSION_ID`, which Claude Code sets in every Bash call, so only the current session's file matches (unset: any session's). Otherwise the last non-synthetic `.message.model` of that agent's `--transcript`. Only a file in the hook's default folder (`/tmp`) is the hook's own record. A folder named in `DAAF_CONTEXT_REPORTER_CACHE_DIR` is read and recorded, but the tool cannot tell a value set for the hook from one set on its own command line. Each agent ID must pass the hook's ID allowlist (letters, digits, `.`, `_`, `-`, starting with a letter or digit, at most 128 characters) before it enters the file pattern; an ID given twice, or a `--transcript` not named `agent-<ID>.jsonl` for a given ID, is exit 8. Recorded per agent (`model.agents`) as `model_source`: `hook_cache`, `hook_cache_env_dir`, `transcript` or `none` |
| 2 Match | Compares the block's `reader_model` with every agent's model, `[1m]` dropped and a dotted Claude ID (`claude-opus-5.5`) hyphenated as the hook does: `mismatch` (any differs), `unknown` (any not found), `source_not_confirmed` (all equal, but one came from a transcript or from a folder named in the environment), or `transcript-confirmed` (all equal and all from the hook's own record). `source_not_confirmed` lists every vision reading for a person, as `unknown` does |
| 4 Route | Compares the front matter's `reader_route` with the latest successful `lit_verify route` row in `papers/MANIFEST.jsonl` recorded no later than the card check (`checked_at`): `match`, `mismatch`, or `unknown` (no such row, or the card names no route). A route recorded after the check does not count. Then looks up the (model, route) row in the card's `vision_list_version`: `listed`, `not_listed`, `unknown` (no recorded route) or `not_applicable` (the card has no vision reading) |
| 5 Pages | `must_check`: every `VISION_ON_SCAN_PAGE` item of the `card_check`, plus every vision reading (a `vision`/`both` claim or a `vision_only` digest) on a page of class `sparse`. `should_look`: every `VISION_FIGURE_UNCORROBORATED` warning, plus one item when the `card_check` has no `rule_versions.vision_figure` (checked before the figure rule existed: check the card again so chart readings are screened) |
| 6 Chain | The whole-chain check (`evidence-card.md` § Re-derivation): the source file must still hash to the value the card check recorded; a `web_fetch` source must be the very row (line, file name, hash, final URL) of a fetch under `PROJECT_DIR/web_fetches/`; a `user_supplied` source must sit under `PROJECT_DIR/user_pdfs/`; any other source kind is unconfirmed |
| 3 Record | Writes `PAPER_DIR/vision_audit{S}.json` (`{S}` = the card's suffix, schema `lit-verify-vision-audit-v1`, rules `vision-audit-v1`), keyed by `card_sha256` and `card_check_sha256`, by exclusive create: an existing record is exit 9, so a second audit needs a new card revision. Appends a MANIFEST row (kind `lit_verify_audit`) to `papers/MANIFEST.jsonl`. The card is never edited: that would break the hash its `card_check` records |

| Outcome | Exit | When (checked in this order) | Orchestrator |
|---------|------|------------------------------|--------------|
| `chain_unconfirmed` | 11 | Step 6 did not confirm the source | Confirm the file is the paper expected before relying on the card; tell the user. A person's comparison of the readings does not settle this: fetch the paper with `web_fetch.sh` or put the user's PDF in `user_pdfs/`, then check and audit again |
| `mismatch` | 11 | The model does not match (even on a card with no vision reading), or a card with vision readings has a route mismatch or no list row | Every vision-derived item (the record's `unvalidated` list) is unvalidated: show them to the user with `lit_verify settle --list` and record the user's comparison with `lit_verify settle` (below), or re-read them text-only or downgrade the claims |
| `person_must_check` | 11 | The card has vision readings and the model is `unknown` or `source_not_confirmed`, or the route is `unknown` (every reading lands in `unvalidated`), or `must_check` lists items | Show the listed readings to the user with `lit_verify settle --list` and record the user's comparison with `lit_verify settle` (below), or re-read them text-only or downgrade the claims |
| `confirmed_with_checks` | 0 | Confirmed, with `should_look` items only | Show the user the listed items: numbers read from charts that the paper's text does not confirm |
| `confirmed` | 0 | Source confirmed; no vision reading, or model, route and list row confirmed with nothing listed | Nothing more |

No model is validated on scan, sparse or figure pages (§ The validation
probe), so every listed reading is an unvalidated reading. The record's
`summary` and each item's `reason`, and the `MUST CHECK:` and `SHOULD LOOK:`
lines the command prints, are written for the researcher and can be shown as
they are. A vision reading on a sparse page, for example:

> The AI reader took the number 88 from a picture of PDF page 2 (its
> position in the file; the printed page number may differ). This page has
> very little text, so nothing on it confirms the reading, and DAAF has
> tested AI reading of page pictures only on pages with tables and full
> text. Please compare 88 with PDF page 2.

Exit codes 1 (usage), 2 (refused path) and 12 (internal error) are as for
`card`: `evidence-card.md` § Exit codes.

**After the audit: settling listed readings.** For `person_must_check` and
`mismatch`, the readings the audit lists are shown to the user, and the
user's comparison of each with its PDF page is recorded. The literature
review report gate reads that record (literature-review
`references/lit-verify-report.md` § Settling the readings an audit lists).

```
bash /daaf/scripts/lit_verify.sh settle <PAPER_DIR> --audit vision_audit{S}.json --list
bash /daaf/scripts/lit_verify.sh settle <PAPER_DIR> --audit vision_audit{S}.json --items FILE
     --decision matches|does_not_match --user-words "..." [--rationale "..."]
```

- **Inputs, checked before anything else (exit 9).** The audit record
  directly inside `PAPER_DIR` (its name must be `vision_audit{S}.json`: else
  exit 8) must hash to its `lit_verify_audit` MANIFEST row and name the same
  card, `card_check`, paper and outcome as that row; the card and its
  `card_check` must still hash to the values the record holds, and the card's
  latest card run must still be the audited check (a card checked again needs
  a new revision and its own audit). Each item's stored id must re-derive.
- **Item ids.** Every `must_check`, `should_look` and `unvalidated` item of
  the record carries its `numbers` and an `item_id`: the first 16 hex
  characters of the SHA-256 of the canonical JSON `["audit-item-id-v1",
  card_sha256, page, claim_id, numbers, why]`. The same reading of the same
  card always has the same id, and an id from another card's audit never
  matches. The chain carries an id too (`why` `chain`, no page or claim).
- **`--list`** prints one numbered plain line per reading, for the
  researcher as it stands: the `must_check` and `unvalidated` readings to
  compare first (`1. The AI reader took the number 88 ...`), then the
  `should_look` figure readings marked `(optional)`, and for
  `chain_unconfirmed` a `Not settled by a comparison:` line. It prints no
  item id. It writes `PAPER_DIR/settle_items{S}.txt`: the ids to compare,
  one per line, each with its number as a comment (`<id>  # 1: PDF page 2,
  88`), ready for `--items`; the optional readings follow as comment lines,
  to be uncommented when chosen. A reply such as "1 and 3 match, 2 does not"
  becomes one `settle` call per decision, each with an items file holding
  the ids of those numbers. Also a MANIFEST row.
- **The decision** records ONE reply of the user for a batch of items: one
  call per decision. `--user-words` is the user's reply verbatim; as a
  command-line argument it appears in the permission prompt when the user has
  added an ask rule for `lit_verify.sh settle` (as for `lit_corpus.sh
  adjudications record-human`). `does_not_match` needs `--rationale` (which
  number, and what the page prints). The record is
  `PAPER_DIR/audit_settlement{S}_{n}.json` (exclusive create, `n` the next
  free number; schema `lit-verify-audit-settlement-v1`, rules
  `audit-settle-v1`): the audit, card and `card_check` SHA-256, the decision,
  the user's words and rationale, `settled_at`, `human_binding:
  permission_prompt` (expected, not detected: a `!`-typed run looks the same)
  and each item (id, group, page, claim, numbers, decision, reason). A
  MANIFEST row of kind `lit_verify_settle` (command `settle`) records it.
  The latest record of an item decides.
- **Refused, nothing written (exit 11):** empty `--user-words`;
  `does_not_match` without `--rationale`; an id listed twice; an id that is
  not an item of this audit (another audit's or another card's included);
  the chain's id ("fetch again, or put the user's PDF in `user_pdfs/` and
  check again"). An items file that is over 64 KiB, not UTF-8, names no item
  or has a first word that is not an id: exit 8.

A settled audit changes nothing in the card or the audit record: the
readings stay the AI reader's, with a record that the user compared them.
After a `does_not_match`, write new reading notes without that number, or
with the number as printed on the page, check them with `lit_verify card`
and run `lit_verify audit`.

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
and route stay with `lit_verify audit` (above). Of the list's page scope
(§ The validation probe) it checks the scan part, from 1.8.0 part 5: it
re-derives the page flags from the source, and a vision reading on a page
that comes out truly scanned (`pages[].class: "scanned"`) or with an OCR
text layer (`pages[].ocr_layer: true`) is `VISION_ON_SCAN_PAGE`, a review
item, so the card is NEEDS_REVIEW rather than PARTIAL. A vision reading on
a sparse page raises no item in the card gate; the audit lists it under
`must_check` (step 5). On a figure or chart page (class `normal`), a
vision-read number in doubt that no page of the paper prints is the warning
`VISION_FIGURE_UNCORROBORATED` (no verdict or grade change;
`evidence-card.md` § Vision consistency), which the audit lists under
`should_look`. The scan rule applies whatever the reader's list status; a
forged flag in the card or the manifest cannot hide a scan, except in one
documented residual (a scan or OCR layer whose only image evidence is a
pdfplumber image box, removed from a forged manifest in a document where
pdfimages lists images; 0 such pages in the five bake-off PDFs), and a page
whose type could not be re-derived counts as a scan (`evidence-card.md`
§ Vision consistency). On such a page the reader writes `?` for digits it
cannot read, labels the reading as an unvalidated reading of a scan, logs
every disagreement and reports it; the audit lists the review items under
`must_check` (step 5) and a person settles them (`lit_verify settle`,
above). The embedded copy is
`VISION_LIST_VERSION` and `VISION_VALIDATED_LISTS` in
`scripts/lit_verify.py` (since 1.8.0 part 6: three versions,
`vision-list-2026-10-19` with no rows and `vision-list-2026-10-28` with ten
rows, five model IDs on the two Anthropic routes, both kept so older cards
stay interpretable, and the current `vision-list-2026-10-30` with sixteen
rows: those ten plus three GPT model IDs on the two GPT shim routes),
recorded in every `card_check` under `constants`, so a check result shows
which list it was judged against.

## Routes

The five install routes (names as in the `daaf-deploy-smoke-testing` skill):
`anthropic-subscription`, `anthropic-api`, `chatgpt-subscription` (GPT shim),
`openai-api` (GPT shim), `openrouter`. A list row names one route; a model
validated on one route is not validated on another, because image handling
differs by route [inf].

**Where the route comes from.** The orchestrator runs

```
bash /daaf/scripts/lit_verify.sh route <PROJECT_DIR>
```

and copies the first line it prints, `ROUTE: <name>`, verbatim into every
paper-reader dispatch; nobody types a route. The subcommand imports
`detect_route()` from `scripts/deploy_smoke/route_detection.py` (the route
detector of the `daaf-deploy-smoke-testing` skill, a pure environment check)
and prints the route's basis, its limits and the list rows for that route.
It appends a row (kind `lit_verify_route`) to `PROJECT_DIR/papers/MANIFEST.jsonl`
with the route, its basis, the detector file's SHA-256, the list version and
its row count for the route, and the environment keys the detector consulted,
recorded by presence only (`set`, `empty` or `unset`), never by value. Run it
before the first reader dispatch: `lit_verify audit` counts only a route row
recorded no later than the card check.

| Route | Basis printed |
|-------|---------------|
| `chatgpt-subscription` | The provider shim controls select the ChatGPT-subscription lane |
| `openai-api` | The provider shim controls select the OpenAI API lane |
| `openrouter` | `ANTHROPIC_BASE_URL` points at OpenRouter |
| `anthropic-api` | No provider shim and no OpenRouter base URL; `ANTHROPIC_API_KEY` is set (non-empty) |
| `anthropic-subscription` | No provider shim, no OpenRouter base URL and no non-empty `ANTHROPIC_API_KEY` |

Limits, also printed:

- **Console API or subscription.** The environment cannot tell a Claude
  Code login with a Console (API) account from a subscription login. This
  changes no vision decision while every listed model has rows on both
  Anthropic routes, as on `vision-list-2026-10-30`; if the two routes ever
  list different models, the output says so, and the login type is
  confirmed by hand before any vision use.
- **OpenRouter.** No list row names `openrouter`, so the output says PDF
  reading is text-only there, and a reader on that route writes `vision:
  unavailable`.

Exits: 0 route detected; 1 `PROJECT_DIR` is not a directory; 2 refused
path (the destination guard, or a secret value in the argument); 10 the
route detector cannot be loaded; 12 internal error (for example a route
name the detector should not return).

| Route family | Image rules | DAAF consequence |
|--------------|-------------|------------------|
| Anthropic (subscription, API) | Once a request holds more than 20 images, earlier turns included, "a stricter per-image dimension limit applies"; images over it "are rejected with an invalid_request_error", and keeping both dimensions at or under 2000 px stays under that limit "on all platforms" [doc, Anthropic's vision documentation, fetched 2026-10-12, same wording 2026-10-28]. On Amazon Bedrock and Google Cloud, PDF document blocks also count toward the 20 [doc]. Token cost ≈ ⌈width / 28⌉ × ⌈height / 28⌉ [doc] | `pdf_ingest` renders at 2000 px (long side), so a long reading conversation never trips the rejection |
| GPT shim (chatgpt-subscription, openai-api) | The shim sends each image as `input_image` with `detail: "auto"` and does no resizing of its own [obs, shim session]. In the shim session's 10-request image test (shim 1.4.9, ChatGPT lane), `auto` delivered native resolution on gpt-6-sol, gpt-6.1-sol, gpt-6-luna, gpt-6-astra and gpt-5.6-sol: 3,705 image tokens each for a 1547×2000 page, 20/20 normal and 20/20 small numbers [obs; one synthetic page per model, not a repeatability study, no dense tables or reading order]. OpenAI has **no** "more than 20 images" rule: within a model's patch budget oversize images are downscaled **silently**; an image above 30,000 patches is rejected, not resized; up to 1,500 images and 512 MB per request [doc, OpenAI's image documentation as quoted by the shim session]. A 2000 px page is about 3,100 patches [inf, arithmetic] | Our renders pass at native size today; a downscale would be silent, so the table probe, not the absence of errors, is the gate |
| OpenRouter | No DAAF observation recorded | Treat as unprobed |

**Read on a `.pdf`.** Claude Code's Read tool sends a PDF as rendered page
images on both the Anthropic and the shim routes [obs, shim session]. That is
vision use, and the resolution and page choice are not ours. Use
`pdf_ingest`'s renders instead, and only when vision is validated.

The shim session recommends keeping shim-routed GPT models `vision:
unavailable` until the table probe below passes on that route: a downscale
over the shim is silent, so only a passed probe shows fidelity. The probe
passed on `chatgpt-subscription` for `gpt-6-sol`, `gpt-6.1-sol` and
`gpt-6-astra` (§ The validation probe). The `openai-api` rows for the same
models were not probed: the user decided on 2026-10-30 to assume parity with
the subscription route, so they are labelled inference. They rest on that
decision, not on a probe: the earlier plan, a parity probe of one GPT model
on `openai-api`, has not been run. If a shim change alters image handling,
re-run the probe after it.

## Cost

| Route | Per 2000 px page | 30-page paper, every page |
|-------|------------------|---------------------------|
| Anthropic | ≈ 4k tokens (a 1547×2000 page: 56 × 72 = 4,032 by the formula) | ≈ +120k |
| GPT shim, native size | ≈ 3,705 tokens (3,087 patches × 1.2) [obs] | ≈ +111k [inf] |

`auto` usually touches a handful of flagged pages; `all-pages` is the
expensive mode. A 300-DPI crop is smaller than a full page.

## The validation probe (run 2026-10-28)

The thresholds were approved by the user on 2026-10-13. The probe ran on
2026-10-28 on the `anthropic-subscription` route (Claude models) and, with
the same images, prompt and pass bar, on the `chatgpt-subscription` route
(GPT models, through DAAF's provider shim; scored 2026-10-30), with this
design:

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
   was passed in the probe dispatches (Claude Code's default). Over the
   shim, the reasoning effort was the shim's configured default, "high",
   not verified per request.
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
   and rotated subsets. No separate test was needed for the models listed by
   probe: every run of theirs was exact on every cell, so those subsets were
   exact too.
7. **Model IDs** are transcript-derived (`.message.model`, read through the
   `context-reporter` hook's cached value) and bare. For the GPT runs they
   were read from each transcriber's transcript; over the shim that value is
   the requested model name echoed back by the shim, not the provider's
   independent report of which model served the request (§ Gating, shim
   caveat).
8. **Record**: the full probe record (model IDs, route, effort, fixture
   version and hashes, per-cell results, run dates, captured scripts) is
   kept with the maintainers; the shipped rows state the date and the
   measured result.

**Results (observed, 2026-10-28, `anthropic-subscription`):**

| Model ID | Runs passing | Synthetic exact, each run | Real exact, each run | Sign errors | Decimal shifts | Invented numbers |
|----------|--------------|---------------------------|----------------------|-------------|----------------|------------------|
| `claude-opus-5-5` | 3 of 3 | 381/381 | 1,081/1,081 | 0 | 0 | 0 |
| `claude-sonnet-5` | 3 of 3 | 381/381 | 1,081/1,081 | 0 | 0 | 0 |

**Results (observed; runs 2026-10-28, scored 2026-10-30; `chatgpt-subscription`
through DAAF's provider shim, in two batches, GPT-6 Astra and GPT-6.1 Sol,
then GPT-6 Sol and GPT-6 Luna; shim version 1.4.13 for both, as recorded
from each batch's preflight check):**

| Model ID | Runs passing | Synthetic exact, each run | Real exact, each run | Sign errors | Decimal shifts | Invented numbers |
|----------|--------------|---------------------------|----------------------|-------------|----------------|------------------|
| `gpt-6-sol` | 3 of 3 | 381/381 | 1,081/1,081 | 0 | 0 | 0 |
| `gpt-6.1-sol` | 3 of 3 | 381/381 | 1,081/1,081 | 0 | 0 | 0 |
| `gpt-6-astra` | 3 of 3 | 381/381 | 1,081/1,081 | 0 | 0 | 0 |
| `gpt-6-luna` | 1 of 3 (failed) | 381/381; 341/381; 341/381 | 981/1,081 + 100 awaiting a ruling (see below); 1,081/1,081; 1,081/1,081 | 0 | 0 | 0; 24; 24 |

An independent recount of the numbers on each image (every key number
present; on synthetic pages, exactly the key's numbers) agreed with the cell
scores on all 18 runs, Claude and GPT: it found no problem in any passing
run, and it found Luna's failure on the same page as the scorer. The
transcripts were audited: each transcriber only read the images it was
assigned and wrote its own run's output files.

**Why `gpt-6-luna` failed.** It misread no digits. In runs 2 and 3 it wrote,
into the file for one synthetic page it was asked to transcribe, the table
from the next image in its list (a page from one of the real papers), the
same way in both runs, and never transcribed the synthetic page itself. That
page's cells count as missing (synthetic 89.50% exact), and 24 of the other
page's 30 numbers count as invented (the scorer matched the other 6 to
numbers printed elsewhere on the synthetic page). Run 1 counts as passing
only because 100 numbers of one real table were set aside awaiting a
person's ruling: the recount found all 100 present, but Luna added an extra
indented column to that table's subgroup rows, which the scorer could not
line up with the key. Runs 2 and 3 fail whatever that ruling, so the model
fails. In a real reading, a page mix-up like this would put numbers from the
wrong page into an evidence card [inf], so the model is not listed. DAAF's
recommended GPT setup runs its lighter agents on GPT-6 Luna, including the
search-agent that reads PDFs by default, so on that setup PDFs are read
from their text only.

**Behavior on the unscored 1973 scan** (flagged `ocr_layer_suspected`). Two
cells are damaged. On the first (1961, first column), every Opus 5.5 run,
one Sonnet 5 run and all 12 GPT runs wrote `?`; Sonnet 5, in the other 2
runs, filled it from the column's trend instead (56.9, 56.6), which the
prompt forbids. On the second (1959, eighth column), half the runs of both
families wrote a definite number: 3 of 6 Claude runs (Opus 5.5 in 1 of 3,
Sonnet 5 in 2 of 3) wrote 36.0, which is also what the page's OCR text
layer reads, and 6 of 12 GPT runs, at least one run of each GPT model,
wrote 36.2, 36.3 or 36.6, values that differ from one another and from the
OCR layer. Whether such values are misreads or guesses cannot be told from
the output [inf]. So on a damaged scan, Claude and GPT models alike
sometimes write a number where the print is unreadable, which is why scans
stay outside every row's scope.

**The list's scope.** So this probe validates no model on scans. Every row
covers table pages with a digital text layer: pages with no `scanned` and no
`ocr_layer_suspected` flag in the ingest manifest. Pages with either flag
(truly scanned and sparse pages, and scans carrying an OCR text layer) were not
probed, and figure pages were not scored, so no model is validated on them.
A listed reader may still look at such a page, but the reading is
unvalidated: write `?` for any digit you cannot read, never infer one from
context, the column or a trend; label the reading in the card as an
unvalidated reading of a scan; log every text/vision/OCR disagreement; and
tell the orchestrator. `lit_verify` sends every vision reading on a truly
scanned or OCR-layer page to a person (`VISION_ON_SCAN_PAGE`, review),
because a plausible-looking number read from a scan often has no clean text
to check it against. A reading on a sparse page (flagged `scanned`, little
text, not mostly one image) raises nothing in the card gate, and on a
figure page the gate warns (`VISION_FIGURE_UNCORROBORATED`) only for a
number in doubt that the paper's text does not print; `lit_verify audit`
lists both for a person (§ Gating, step 5).

**What the probe does not show:** fidelity on scanned or OCR-layer pages,
figure pages or 300-DPI crops; any route other than `anthropic-subscription`
and `chatgpt-subscription` (the `anthropic-api` rows are inference: the same
models under the same Anthropic image rules; the `openai-api` rows are
inference by user decision, parity assumed; OpenRouter is not covered at
all); which model actually served a shim request (the ID is the shim's echo
of the requested name); the models admitted by policy (§ Promotion and
demotion).

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

Anthropic's models overview (fetched 2026-10-12, re-fetched 2026-10-28)
lists Opus 5.5, Sonnet 5.5 and Fable 5.1 among the current models and
Sonnet 5 under Legacy models [doc].

## Candidates (to be probed)

| Candidate | Route(s) | Note |
|-----------|----------|------|
| `gpt-6-luna` | chatgpt-subscription, openai-api (shim) | Probed 2026-10-28 on chatgpt-subscription and failed (runs 2 and 3 failed; scored 2026-10-30; § The validation probe): not a list entry. DAAF recommends it for the lighter (sonnet-tier) agents on GPT installs, so those agents, including the default PDF reader, read text only. A re-probe that passes could list it |
| `gpt-6-sol`, `gpt-6.1-sol`, `gpt-6-astra` | openai-api (shim) | Listed by inference since `vision-list-2026-10-30` (parity with chatgpt-subscription assumed by user decision 2026-10-30); a probe on that route would confirm it |
| Any model | openrouter | Not probed, no rows. The GPT rows do not cover it (OpenRouter IDs are provider-prefixed, e.g. `openai/gpt-6-sol`, and DAAF has no observation of how that route handles images, § Routes) |
| `claude-sonnet-5-5`, `claude-fable-5-1`, `claude-fable-5` | anthropic-subscription, anthropic-api | Listed by policy admission, not probed; a probe would confirm or remove them |
| All five Claude models | anthropic-api | Listed by inference (the admitted models: admitted, route by inference); a probe on that route would confirm it |
| Any model, scanned pages and OCR-layer scans (`scanned` or `ocr_layer_suspected`) | any | No model is validated on them (§ The validation probe) |

Exact model IDs for a probe promotion are taken from the probe runs'
transcripts, never from this table.

## List history

| Version | Date | Change |
|---------|------|--------|
| `vision-list-2026-10-19` | 2026-10-19 | List created empty. No probe run yet |
| `vision-list-2026-10-19` | 2026-10-23 | Unchanged, now also embedded in `lit_verify` (1.6.0): `vision_validated: true` against it fails as `VISION_NOT_ON_LIST` until a model is promoted |
| `vision-list-2026-10-28` | 2026-10-28 | Ten rows, five model IDs, each on `anthropic-subscription` and `anthropic-api`. Probed on `anthropic-subscription` and passed (3 of 3 runs, every cell exact): `claude-opus-5-5`, `claude-sonnet-5`. Admitted by user policy decision, not by DAAF quality validation (not probed): `claude-sonnet-5-5`, `claude-fable-5-1`, `claude-fable-5`; the user's words: "if sonnet 5 passed, those will as well as strict improvements". Every `anthropic-api` row is inference (for the admitted models: admitted, route by inference). Every row covers table pages without a `scanned` or `ocr_layer_suspected` flag; pages with either flag were not probed. Embedded in `lit_verify` 1.8.0 (part 4); `vision-list-2026-10-19` is kept, still empty, so a card read under it still fails `VISION_NOT_ON_LIST` with `vision_validated: true` |
| `vision-list-2026-10-30` | 2026-10-30 | Sixteen rows: the ten `vision-list-2026-10-28` rows unchanged, plus three GPT model IDs, each on `chatgpt-subscription` and `openai-api`. Tested on a ChatGPT subscription through DAAF's provider shim (runs 2026-10-28, scored 2026-10-30) and passed (3 of 3 runs, every cell exact): `gpt-6-sol`, `gpt-6.1-sol`, `gpt-6-astra`. The model names come from DAAF's own records of each request; over the shim those repeat the name DAAF asked for, so DAAF cannot confirm which model OpenAI actually ran. Every `openai-api` row is inference: the user's decision of 2026-10-30 was to promote the passing subscription rows and "assume parity with API for now". `gpt-6-luna` was tested and failed (in 2 of 3 runs it copied a table from the wrong page), so it is not listed. OpenRouter is not covered. Same scope as before: table pages without a `scanned` or `ocr_layer_suspected` flag. Embedded in `lit_verify` 1.8.0 (part 6); `vision-list-2026-10-19` and `vision-list-2026-10-28` are kept, so a card read under either keeps its meaning (a GPT reader under `vision-list-2026-10-28` still fails `VISION_NOT_ON_LIST`) |
