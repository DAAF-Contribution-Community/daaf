# OpenAlex

The backbone backend: authoritative metadata, the citation graph, semantic and
keyword search, cached GROBID full text, OA locations (the same data Unpaywall
serves since late 2025) and an `is_retracted` flag. Adapter:
`scripts/scholar_backends/openalex.py`. Docs: https://help.openalex.org
(`llms.txt` index); pages fetched 2026-10-02 are in the S1 workspace
`research/2026-10-02_FrameworkDev_ScholarlySearch/web_fetches/apis/`.

## Auth

- Key: `OPENALEX_API_KEY` — optional but **strongly recommended**. Free from
  https://openalex.org/settings/api.
- Sent as `Authorization: Bearer <key>` (works on `api.openalex.org` and
  `content.openalex.org`, verified 2026-09-27). The docs also show
  `?api_key=`; the tool never uses it, so the key never reaches a URL, a log
  or a raw artifact.
- **Keyless:** "you can make basic queries with no key at all" (authentication
  page) at $0.10/day, but the deprecations page says "All users need an API
  key (free)". The docs conflict; the tool prints a DEGRADED MODE banner and
  keeps working until OpenAlex refuses.
- The old `mailto` polite pool is gone ("The `mailto` parameter is ignored").

## Endpoints used

| Use | Request | Commands |
|-----|---------|----------|
| Keyword search | `GET /works?filter=title_and_abstract.search:<q>&sort=relevance_score:desc` | `find`, `openalex --mode keyword` |
| Semantic search | `GET /works?search.semantic=<≤2000 chars>` | `find`, `similar`, `openalex --mode semantic` |
| Broad search | `GET /works?search=<q>` (also matches full text) | `openalex --mode broad` |
| Filter list | `GET /works?filter=cites:W…` / `openalex:W1|W2…` | `cites`, `refs` |
| Title lookup | `GET /works?filter=title.search:<title>` (billed as a search) | `work`, `verify` |
| Single work | `GET /works/W…` or `/works/doi:<doi>` (free) | `work`, `verify`, `oa`, `retractions` |
| Full text | `GET content.openalex.org/works/W….grobid-xml` | `fulltext` |

`select=` trims every response to the fields the mapper needs.
`--corpus core|expansion|all` passes the `corpus=` parameter (added August
2026; replaces the deprecated `include_xpac`).

## Cost and limits

| Operation | Per call | Source |
|-----------|----------|--------|
| Single entity by ID/DOI | free | docs + measured |
| List + filter | $0.0001 | docs + measured |
| Search / semantic search / `title.search` filter | $0.001 | docs + measured 2026-10-02 |
| Content download (`fulltext`) | $0.01 | docs |
| HTTP 400 (rejected request) | $0 | measured 2026-10-02 |

Budget: $1/day with a free key, $0.10/day keyless; 100 req/s; semantic search
1 req/s and max 50 results; `per_page` max 100; 100 OR values per filter.
The tool gates the semantic lane at 1.1 s container-wide.

Response headers (measured 2026-10-02 — **both** families are sent):
`x-ratelimit-cost-usd`, `x-ratelimit-remaining-usd`, `x-ratelimit-limit-usd`,
`x-ratelimit-prepaid-remaining-usd`, plus the documented credit family
`x-ratelimit-limit` (10000 = $1), `x-ratelimit-remaining`,
`x-ratelimit-credits-used` (10 per $0.001 search), `x-ratelimit-reset`
(seconds to midnight UTC), `x-ratelimit-onetime-remaining`. The response
`meta` also carries `cost_usd`. The adapter parses both families into the
MANIFEST row (`openalex_cost_usd`, `openalex_budget`).

## Measured behavior

- **`search=` drifts** (2026-09-27): it matches full text and blends in
  citations; Chetty's teacher value-added paper ranked 4th for "school finance
  reform student outcomes". Hence keyword mode = `title_and_abstract.search` +
  `sort=relevance_score:desc`. Its terms are effectively ANDed, so pass
  `--keywords`, not a sentence.
- **Filter values are comma-separated**; commas, `?` and `*` in free text are
  stripped (a title ending in "?" returned HTTP 400).
- **Semantic-search filters** (re-measured 2026-10-02): `has_content.grobid_xml`
  is rejected with HTTP 400 ("not supported with semantic search", listing the
  supported set: author.id, authorships.*, funders.id, has_abstract,
  has_fulltext, institution ids, is_oa, is_retracted, language,
  open_access.is_oa, primary_location.license, primary_location.source.id,
  publication_year, type); `is_oa:true` is accepted. The docs' "most filters
  work as usual" is therefore too generous; their two named exclusions
  (`cited_by_count`, country codes) are not the only ones.
- **Relevance score on semantic search** (re-measured 2026-10-02): returned
  when requested in `select` (`--with-score`; scores 0.89–0.90 for the top 3 of
  a tutoring query). The 2026-09-27 "no score" observation reflected a select
  list without `relevance_score`.
- **`corpus=`** (measured 2026-10-02): `"high-dosage tutoring"` keyword search
  matched 47 works with `corpus=core` and 70 with `corpus=all`.
- **Open year ranges** need comparisons (`publication_year:>2014`).
- **Type negation** `type:!dataset,type:!paratext` works in both modes;
  without it ICPSR "Code for: …" deposits took 4 of the top 6 `similar` slots.
- **Versions:** NBER working papers and journal versions are separate works
  (3–4 records per paper is common); the core's `fuse()` merges them.
- **Abstract coverage:** about 75% in Education (subfield 3304), 2015–2025;
  abstracts arrive as an inverted index (`reconstruct_abstract()`).
- **`group_by=has_abstract`** returned a false 0 in testing; use filter counts.
- **OA `version`** is reported as OpenAlex holds it (a PLOS article came back
  `submittedVersion`, 2026-10-02) — treat it as metadata, not ground truth.

## Storage and ToS

Data is CC0 ("no 'personal use only' carve-out"); raw JSON may be stored and
shared. Cached PDFs/TEI keep the original copyright ("OpenAlex does not grant
any additional rights") — check the license per work. Requested citation:
Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of
scholarly works, authors, venues, institutions, and concepts. arXiv:2205.01833.
`LICENSE_CLASS = "open"`.

## Exit mapping

401/403 → 11 (check the key); 404 → 11 (`work`/`verify` record NOT FOUND);
400 → 11 (bad filter — the message names the supported filters); 429 after
retries → 11 (daily budget or 100 req/s); gate queue too long → 12; network
→ 4; timeout → 6.

## Minimal smoke test

```
bash /daaf/scripts/scholar_search.sh verify 10.1093/qje/qjv036 {PROJECT_DIR}/lit_search --title "The Effects of School Spending on Educational and Economic Outcomes: Evidence from School Finance Reforms" --author Jackson --year 2016   # free; expect CONFIDENT
bash /daaf/scripts/scholar_search.sh openalex '"high-dosage tutoring"' {PROJECT_DIR}/lit_search --limit 2   # $0.001
```
