# Semantic Scholar (Ai2)

Passage search inside open-access papers, extra recall in `find`, and boolean
bulk retrieval. Adapter: `scripts/scholar_backends/semantic_scholar.py`.
Docs: https://api.semanticscholar.org/api-docs/ (OpenAPI spec fetched
2026-10-02 into the S1 workspace `web_fetches/apis/`).

## Auth

- Key: `SEMANTIC_SCHOLAR_API_KEY` — optional. Request one at
  https://www.semanticscholar.org/product/api#api-key-form.
- Sent as `x-api-key` header. An invalid key returns 403 "Forbidden"; a valid
  one returns 200 or 429, which distinguishes a bad key from throttling.
- Keyless: "1000 requests per second shared among all unauthenticated users…
  may also be further throttled" — usable for a test, not for work.

## Endpoints used

| Use | Request | Command |
|-----|---------|---------|
| Relevance search | `GET /graph/v1/paper/search?query&limit≤20&fields` (no `abstract`) | `find` |
| Passage search | `GET /graph/v1/snippet/search?query&limit` | `snippets` |
| Bulk boolean search | `GET /graph/v1/paper/search/bulk?query` (≤1,000 per call, continuation `token`) | `s2-bulk` |
| DOI / title match | `GET /paper/DOI:<doi>`, `/paper/search/match` | adapter `resolve()` |

## Cost and limits

Free. **1 request per second per key, cumulative across all endpoints** (Ai2
key terms, 2026-09-27). The tool gates the lane at 1.2 s container-wide;
`find` waits ≤ 20 s for a slot and makes 3 attempts; dedicated commands wait
≤ 120 s and make 8 attempts, then exit 12 / 11.

## Measured behavior

- **Heavy server-side throttling** (2026-09-27): ~30% of rapid first attempts
  refused even with a key (backoff recovered 10/10); later 5 of 6 searches
  spaced 5 s apart refused. 2026-10-02: one 429 retry on the bulk call, then
  200.
- **Abstracts at limit ≥ 10** on `/paper/search` were refused on every
  attempt (2026-09-27); the same request without `abstract` succeeded. Hence
  `SEARCH_FIELDS` omits abstracts and `find` fills them from OpenAlex.
- **`/paper/search` is plain relevance text**: quotes, parentheses and
  boolean operators are not syntax there and zeroed a test query;
  `plain_terms()` strips them.
- **`/paper/search/bulk` accepts boolean syntax** (re-measured 2026-10-02):
  `'"high-dosage tutoring" + (achievement | outcomes) -college'` returned
  HTTP 200, total 16, a continuation token, and three on-topic records. The
  docs say bulk results come "without search relevance", so use it for
  exhaustive pulls, not triage. Whether each operator was interpreted (versus
  ignored) was not isolated with a contrasting query — re-measure before
  relying on `-term` exclusions.
- **DOI gaps:** `DOI:10.1093/qje/qjv036` returned 404 (2026-09-27); a title
  match found only a 2015 seminar version. Trust OpenAlex metadata.
- **Snippets** return `{score, paper{corpusId,title,authors,openAccessInfo},
  snippet{text, snippetKind (abstract|body|title), section, snippetOffset}}`;
  OA bodies and abstracts only; no year or venue. Extraction sometimes
  attributes quoted text to the citing paper — verify before citing.
- **Recommendations** (`/recommendations/v1/papers/forpaper/{id}`) draw from
  a recent-papers pool and returned unrelated 2026 items, so `similar` uses
  OpenAlex instead.

## Storage and ToS

S2 Data Licenses: "CC BY-NC or ODC-BY"; third-party content keeps its own
terms. **Attribution is required**: credit "Semantic Scholar" in published
materials and cite The Semantic Scholar Open Data Platform (Kinney et al.,
2023, arXiv:2301.10140). `LICENSE_CLASS = "cc-by-nc"`: raw JSON may be stored
for research; do not redistribute commercially.

## Exit mapping

403 → 11 (bad key); 429 after retries → 11; gate queue too long → 12; 404 on
DOI → handled by the title fallback; network → 4; timeout → 6.

## Minimal smoke test

```
bash /daaf/scripts/scholar_search.sh snippets "high-dosage tutoring math achievement" {PROJECT_DIR}/lit_search --limit 3
```
