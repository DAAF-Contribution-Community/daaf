# Scite

Citation **stance** — how many citation statements support, contradict or
merely mention a paper (Smart Citation tallies) — plus Scite's curated
**editorial notices** (retractions, corrections, errata, expressions of
concern, comments), which it gathers from Crossref, PubMed and its own notice
detection. No other backend gives stance; for retractions it is a third,
independent source beside OpenAlex and Crossref. Adapter:
`scripts/scholar_backends/scite.py`. Docs: https://docs.scite.ai (fetched
2026-10-02 into `web_fetches/apis/` and re-fetched 2026-10-11 into
`web_fetches/s2_research/` of the S1 workspace
`research/2026-10-02_FrameworkDev_ScholarlySearch/`; drift check: no change).

## Auth

`SCITE_API_KEY` (optional). "Papers and Tallies are public and don't require
an API key. All other Scite endpoints require an API key" (authentication.md).
The key is a Bearer header, created in the API Console
(https://scite.ai/users/me/api) and needs a Pro plan. The tool sends it
**only** to Search; the keyless tally and paper calls go without it, so
keyless use is never tied to the evaluation key. `backends` shows the key by
name only. Without a key, tallies and `retractions` work normally (no banner);
`scite-search` exits 10.

## Endpoints used

| Use | Request | Command |
|-----|---------|---------|
| Tally, one DOI | `GET https://api.scite.ai/tallies/{doi}` (keyless) | `scite-tally <DOI>` |
| Tallies, several DOIs | `POST https://api.scite.ai/tallies`, body = **bare JSON array** of DOIs (keyless, sent as an idempotent read) | `scite-tally <DOI> <DOI> …` |
| Retraction status + notices | `GET https://api.scite.ai/papers/{doi}` (keyless) | `retractions` (Scite leg; `--skip scite` to leave it out) |
| Search | `GET https://api.scite.ai/api_partner/search?term=&limit=` (key) | `scite-search "<q>" --ack-scite-license [--limit 5]` |

Fields used: tallies `supporting, contradicting, mentioning, unclassified,
total, citingPublications` (REST says `contradicting`; Scite's product pages
and MCP say `contrasting` for the same class). Papers: `retracted`,
`editorialNotices[{status, date, noticeDoi, doi}]`, `title`, `authors`,
`journal`, `year`, `slug`. Search: `count`, `countIsApproximate`,
`hits[]` (paper objects with `tally` and `citations[].snippetHidden`).

**`total` vs `citingPublications`.** `total` counts citation statements (one
paper can cite another several times, and statements are classified one by
one); `citingPublications` counts distinct citing papers. They differ in both
directions (measured 2026-10-11: two tallies had fewer statements than
citing papers, one search hit's tally had more). The `scite-tally` digest states this.

## Cost and limits

Papers and tallies are free and keyless. Search needs a Pro key
($50/month or $480/year; "Scite doesn't publish a separate pay-as-you-go API
rate") **and** a separate license for research use (below). Measured keyless
limit: 60 requests/minute, one bucket shared by `/papers` and `/tallies`;
keyed Search reported 13/second and 60/minute (2026-10-11). The shared gate
spaces Scite calls 1.1 s apart on one lane, `scite`. Every Scite command
records the last `RateLimit-*` / `X-RateLimit-*` headers in the MANIFEST row
(`rate_limit_headers`) and prints them. Responses pass a CDN
(`cache-control: s-maxage=1800`), so tallies may be up to 30 minutes stale.

## Measured behavior

Full table: `api-notes.md` § "Measured behavior: Scite (2026-10-11)".
- **Batch body** (2026-10-11, `scite-tally` 2 DOIs): the guide's
  `{"dois": [...]}` returned HTTP 400 `{"message": "Invalid request."}`
  keyless; a bare JSON array returned 200 `{"tallies": {"<doi>": {…}}}`.
- **Keyless `/papers` has no `tally` key** (2026-10-11, Wakefield and QJE),
  though the schema lists one; notices carried no `urls` field.
- **Notice vocabulary** (2026-10-11, Wakefield 1998): `Retracted`,
  `Has correction`, `Has erratum`, `Has expression of concern`, `Comment`.
- **404** (2026-10-11): `{"detail": "Tally not found"}`.
- **Search** (2026-10-11, Pro key): all 3 citation snippets
  `snippetHidden: true` with `snippet: ""`; titles carry
  `<strong class="highlight">` markup (stripped by the mapper).

### Retraction status values

`retraction_check` maps each native notice status by stem, most severe
first, and keeps the native string as `native_status` (shown in the digest
as `status (native)`): contains `retract` / `withdr` / `remov` →
**retracted**; `concern` → **expression of concern**; `correct` / `errat` /
`corrig` → **corrected**; `comment` → **commented** (tool 1.4.0, user
decision 2026-10-12); anything else (including an empty status) →
**updated**. A paper-level `retracted: true` makes the source's status
`retracted` even with no notice. `retracted: false` or an empty notice list →
`none`; a response with neither field → `unknown`.

**`commented` ranks with `none`.** A published comment is not an editorial
change to the paper, so it never raises the combined `retractions` status:
OpenAlex/Crossref `none` plus Scite `commented` is combined **NONE**
(1.2.0–1.3.1 said UPDATED). The comment notices still appear in the digest
(`commented (Comment) notice DOI …`), and stdout shows `scite=commented`.
The combined status reads COMMENTED only when Scite is the only source that
answered (ties keep the first source's status, in adapter order). Within
Scite, any harder notice wins (`updated` > `commented`).

## Storage and ToS

`LICENSE_CLASS = "restricted"` (user decision D-4, 2026-10-11, "accepted for
now"). Every endpoint, keyless included, is "subject to the Scite Terms of
Use" (OpenAPI header of the Papers/Tallies reference). Quoted from
https://scite.ai/terms (fetched 2026-10-11):
- §8: "you agree not to: (a) retrieve Articles, Classifier Results or AI
  Content in bulk or systematically beyond what is reasonably needed for your
  own research use; (b) store, redistribute, sell, license or otherwise make
  such content, or any dataset derived from it, available to any third
  party … Access through the Scite API … is licensed to you personally".
- §4: you will not "(ii) create derivative works of any Classifier Results"
  or "(iii) remove, obscure, or change an author's name or affiliation or any
  Licensor's copyright notices", nor "(iv) knowingly permit anyone other than
  authorized users of the Service to access or use any Classifier Results".
- "Classifier Results" are "the aggregated results of scientific articles
  and other commentaries" — the supporting/contradicting analyses, i.e.
  tallies.
- Search: "Commercial or research use of Search requires a separate license
  agreement" and a Pro key "provides a self-service API key for evaluation"
  (pricing-and-plans.md). Hence `--ack-scite-license`, without which
  `scite-search` is refused (exit 2, MANIFEST row, no request).

There is **no attribution clause**; the obligation is not to remove author
or licensor notices (the `ATTRIBUTION` line says so). How the tool stores it:
- `scite-tally` and `scite-search`: raw `.json` and digest `.md` in
  `lit_search/restricted/`; the MANIFEST row (in `lit_search/`) records
  found / not found per DOI, hit counts, `snippet_hidden` counts and rate
  headers, never a tally value or a result DOI.
- `retractions` (split storage): Scite's raw `/papers` responses go to
  `restricted/<base>.json` (row field `restricted_raw_artifact`,
  `restricted_backends: ["scite"]`); the OpenAlex/Crossref raw log and the
  digest stay in `lit_search/`. The digest carries only Scite's status and
  notice DOIs/dates (facts), never a tally.
- **Test fixtures** `tests/python/fixtures/scholar_search/scite_*.json` are
  **synthetic** (tool 1.4.0, 2026-10-12; user decision: the repository will
  be published). They keep the live responses' shapes (every key path and
  value type, nesting, the measured notice-status vocabulary, rate-limit
  header names, the `<strong class="highlight">` markup, `snippetHidden`)
  with invented values: DOIs under `10.5555/`, invented titles, authors and
  tallies. Until 2026-10-12 the `/papers` fixtures lacked 15 and 14 live key
  paths and `scite_search.json` 48; those keys were added with invented values
  (S2 review cycle 2; paths listed and re-checked to zero missing by session
  scripts 29 and 29_a, which print no live value). Each `_fixture_source`
  names the MANIFEST row its shape came from. No Scite content (tally values,
  notice lists, search hits) is in the repository.
- **Audited scripts** may call `retractions` (facts only) but never
  `scite-tally` or `scite-search`: their stdout carries tally values, and a
  script's stdout is appended to the script file by `run_with_capture.sh`
  (see SKILL.md, "Who may run this").

## Exit mapping

| Situation | Result |
|-----------|--------|
| 404 on `scite-tally` (one DOI) | exit 11, recorded NOT FOUND (digest + row, `found: false`) |
| `scite-tally` batch, some DOIs unknown | exit 0; unknown DOIs listed "not found in Scite"; exit 11 only if none is known |
| 404 inside `retractions` | `scite: not found` (an answer; other sources decide) |
| `scite-search` without `--ack-scite-license` | exit 2 (refused before any request) |
| `scite-search` without `SCITE_API_KEY` | exit 10 |
| 401 / 403 (bad key / missing scope) | exit 11 (`HTTP 401` / `HTTP 403` in the note) |
| 400 / 422 (validation) | exit 11 |
| 429 / 5xx | retried with backoff (GETs and the idempotent batch POST), then exit 11; exit 12 if the shared queue is too long |

## Minimal smoke test

    bash /daaf/scripts/scholar_search.sh scite-tally 10.1093/qje/qjv036 {PROJECT_DIR}/lit_search
    bash /daaf/scripts/scholar_search.sh retractions '10.1016/S0140-6736(97)11096-0' {PROJECT_DIR}/lit_search
