# Unpaywall

DOI-in, open-access-answer-out. Since late 2025 Unpaywall runs on the OpenAlex
database: its `is_oa`, `oa_status` and PDF link are the same values as an
OpenAlex work's `open_access` and `best_oa_location`
(help.openalex.org/access/unpaywall, fetched 2026-10-02; confirmed live
2026-10-02, below). In `oa` it is therefore a **fallback leg** after
OpenAlex. Adapter: `scripts/scholar_backends/unpaywall.py`.

## Auth

No key, but every request needs `?email=`. The tool uses the user's
`SCHOLARLY_CONTACT_EMAIL` and nothing else: unset → the leg is **skipped with
a note** (`unpaywall: skipped: SCHOLARLY_CONTACT_EMAIL not set`). The address
is sent only as that parameter and is replaced by `[SCHOLARLY_CONTACT_EMAIL]`
everywhere the tool writes or prints: logged params, the raw `.json`
(including any redirect chain or echoed error body), the digest, the MANIFEST
row, stdout and stderr (`scrub_contact()` in the core).

## Endpoints used

| Use | Request | Command |
|-----|---------|---------|
| OA record | `GET https://api.unpaywall.org/v2/{doi}?email=…` | `oa` |

Response fields used: `doi`, `title`, `year`, `journal_name`, `genre`,
`z_authors[].raw_author_name` (or `given`/`family`), `is_oa`, `oa_status`,
`best_oa_location{url, url_for_pdf, url_for_landing_page, license, version,
host_type, repository_institution}`, `oa_locations[]`.

## Cost and limits

Free. A 100,000 calls/day figure circulates in search snippets but is
**unverified**: unpaywall.org's API and data-format pages are JS-rendered and
produced no extract on 2026-10-02, and the live responses carry no
rate-limit headers. The tool gates the lane at 0.1 s.

## Measured behavior

**2026-10-02, live** — `oa --all-legs` on three DOIs,
`DAAF_FETCH_CONTEXT=FrameworkDev_S1_unpaywall_live`; raw artifact
`research/2026-10-02_FrameworkDev_ScholarlySearch/smoke_s1/2026-10-02T190851Z_scholar_oa_10-1371-journal-pmed-0020124-10-1093-qje-qjv036-10_1ff906cd.json`,
MANIFEST.jsonl line 15. The unit-test fixtures
`tests/python/fixtures/scholar_search/unpaywall_{record,closed,404}.json`
are trimmed from it (they replaced the earlier doc-derived shape).

| DOI | HTTP | Observed |
|-----|------|----------|
| `10.1371/journal.pmed.0020124` (PLOS, gold) | 200 | `oa_status: gold`; `best_oa_location` is the publisher **landing page** (`url_for_pdf: null`, `version: publishedVersion`, `license: cc-by`); the PDF is in a `repository` location (RePEc, `submittedVersion`). 6 `oa_locations` (two share a PMC URL). Matches OpenAlex's `best_oa_location` for the same DOI in the same run. |
| `10.1093/qje/qjv036` (QJE, closed) | 200 | `is_oa: false`, `oa_status: closed`, `best_oa_location: null`, `oa_locations: []` — closed is a 200 answer, not a 404. |
| `10.48550/arxiv.2205.01833` (DataCite/arXiv) | 404 | HTML body (a generic "404 Not Found" page), not JSON — confirms "Crossref DOIs only". |

**Doc-derived shape vs live** (what the old fixture got wrong):
- `z_authors` entries carry `raw_author_name`, `author_position`,
  `is_corresponding` and `raw_affiliation_strings` — no `given` / `family`.
  The mapper falls back to `raw_author_name`, so author names were never
  lost.
- The best location had no `url_for_pdf` here; the doc-derived fixture put a
  PDF on the publisher best location.
- Extra top-level fields not in the doc summary: `first_oa_location`,
  `is_paratext`, `data_standard` (2), `has_repository_copy`,
  `journal_is_in_doaj`, `journal_is_oa`, `journal_issn_l`, `journal_issns`,
  `oa_locations_embargoed`, `published_date`, `publisher`, `updated`.
  Location-level `evidence` and `updated` both read `"deprecated"`.
- `host_type` is always present, so the adapter's old
  `host_type or repository_institution` fallback never reached the
  institution name; candidates now report `repository: <institution>`.
- The response does **not** echo the email (the raw artifact held the
  placeholder only in the three request params).

## Storage and ToS

Same data as OpenAlex (CC0); `LICENSE_CLASS = "open"`. The PDFs it points to
keep their own copyright: record `license` and `version` and redistribute only
CC BY / BY-SA / CC0 items.

## Exit mapping

Never changes `oa`'s exit code on its own:
- unconfigured (no `SCHOLARLY_CONTACT_EMAIL`) → `unpaywall: skipped: …`
  (never exit 10);
- HTTP 404 → `unpaywall: not found (HTTP 404: DOI unknown to Unpaywall,
  which covers Crossref DOIs only)` — an answer, and `oa` continues to
  ERIC/arXiv;
- closed paper → HTTP 200 with `unpaywall: 0 location(s)`;
- other HTTP errors after retries, network failure or timeout →
  `unpaywall: failed: …` and `oa` continues to ERIC/arXiv.

## Minimal smoke test

With `SCHOLARLY_CONTACT_EMAIL` set host-side in `environment_settings.txt`
(recreate the container after editing it):

```
bash /daaf/scripts/scholar_search.sh oa 10.1371/journal.pmed.0020124 {PROJECT_DIR}/lit_search --all-legs
```
