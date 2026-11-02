# Semantic Scholar (Ai2)

Passage search inside open-access papers, extra recall in `find`, and boolean
bulk retrieval. Adapter: `scripts/scholar_backends/semantic_scholar.py`.
Docs: https://api.semanticscholar.org/api-docs/ (OpenAPI spec
https://api.semanticscholar.org/graph/v1/swagger.json, fetched 2026-10-02).

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
| Citation contexts | `GET /graph/v1/paper/DOI:<doi>/citations` or `/references?fields=contexts,intents,isInfluential,externalIds,title,year,authors&limit≤1000&offset=0` (one call, 2 attempts, waits ≤ 60 s for the lane) | `cites` / `refs --s2-context` (tool 1.7.0; adapter `citation_contexts()`) |

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
  HTTP 200 after one retry, total 16 with all 16 records in one page
  (`token: null`, so pagination was not exercised), and three on-topic
  records at the top. The
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
- **Citation contexts** (2026-10-31): a probe got three 429s in a row on
  `/citations` and contexts on 2 of 10 `/references` rows; the tool 1.7.0
  smoke got `/references` on the first attempt at limit 33: 33 rows with a
  `next` page, 20 matched to OpenAlex's 31 reference groups, 4 with a context.
  Intents arrive lower case (`background`, `methodology`, `result`). A missing
  context means S2 lacks the full text, not that the citation is incidental
  (`api-notes.md`, 2026-10-31).
- **Citation-context coverage** (2026-11-01, observed; 3 well-cited papers,
  10 CLI runs, `api-notes.md`):
  - `/citations` lists the **newest citing papers first** and has no sort by
    citation count. Under `cites`' default `cited_by_count:desc`, 0 of 100
    matched on all three papers; with `--sort publication_date:desc`, 52–70
    of 100 matched and 11–22 had a sentence. `--sort publication_year:desc`
    is newest-first too and is treated the same. Since tool 1.8.0 any other
    sort records `context_warning` (row, records file, digest, stderr); the
    sort is kept and S2 is still asked. No warning when the list is elided or
    S2 does not know the paper, since no sort would help.
  - **No intents on `/citations`**: 0 of 300 rows carried one, including rows
    with sentences. Intents were seen only on `/references` (7 of 43 rows on
    one paper). Expect sentences and the influential flag on `cites`.
  - **Publisher elision**: for two of three papers `/references` answered
    HTTP 200 with `"data": null` and "Notice: The following paper fields
    have been elided by the publisher: {'references'}", although both had
    free copies. Since 1.8.0 that is `context_status: elided` with a plain
    digest sentence, never an empty `ok`. A notice counts only when it names
    the list asked for (`references` or `citations`); one naming another
    field, such as the abstract, leaves an empty answer `ok`.
  - S2 rows with a sentence that matched no OpenAlex paper are left out (5 of
    10 on one `refs` call; 20–34 per newest-first `cites` call); since 1.8.0
    the row and records file count them (`context_unmatched_with_text`).
  - "Influential" is S2's own label for a citation, not a measure of the
    paper's quality; the digest says so beside every flag (1.8.0).
  - Read `--s2-context` as a sample of sentences, not coverage of a paper's
    citations.

## Storage and ToS

S2 Data Licenses: the licenses that accompany the data, "such as CC BY-NC or
ODC-BY"; third-party content keeps its own terms. **Attribution is
required**: credit "Semantic Scholar" in published materials, and in
scientific publications that used the API to produce results cite The
Semantic Scholar Open Data Platform (Kinney et al., 2023, arXiv:2301.10140). `LICENSE_CLASS = "cc-by-nc"`: raw JSON may be stored
for research; do not redistribute commercially.

## Exit mapping

403 → 11 (bad key); 429 after retries → 11; gate queue too long → 12; 404 on
DOI → handled by the title fallback; network → 4; timeout → 6.
`--s2-context` never changes the exit code: a 429 after its one retry or a
busy lane → row `context_status: rate_limited`; a 404 or a seed without a
DOI → `not_found`; a 200 with no rows and a publisher-elision notice naming
that list → `elided` (1.8.0; retrying will not help); anything else → `error`; each with
`context_note` and a stderr NOTE, while the OpenAlex list stands.

## Minimal smoke test

```
bash /daaf/scripts/scholar_search.sh snippets "high-dosage tutoring math achievement" {PROJECT_DIR}/lit_search --limit 3
```
