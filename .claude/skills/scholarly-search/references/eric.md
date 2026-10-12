# ERIC (Institute of Education Sciences)

The education-specific index: journals OpenAlex ranks poorly, EdWorkingPapers,
REL/IES reports, peer-review and full-text flags. Adapter:
`scripts/scholar_backends/eric.py`. Docs: https://eric.ed.gov/?api (not
re-fetched in S1).

## Auth

None. JSON via `format=json`.

## Endpoints used

| Use | Request | Command |
|-----|---------|---------|
| Search | `GET https://api.ies.ed.gov/eric/?search=<solr>&format=json&rows≤200&fields=…` | `find`, `eric` |
| Full text by title | same, `title:"<phrase>" AND e_fulltextauth:1` | `oa` (ERIC leg) |
| PDF | `https://files.eric.ed.gov/fulltext/{ED…}.pdf` (when `e_fulltextauth` is 1) | digest access links, `oa` |

Fields requested: id, title, author, publicationdateyear, source,
peerreviewed, description (the abstract), publicationtype, url,
e_fulltextauth, subject.

## Cost and limits

Free; rate limit undocumented. The tool does not gate ERIC (low volume).

## Measured behavior (2026-09-27)

- **Solr's default operator is OR**: "school finance reform" returned 171,348
  hits; AND-joined it returned 183. `build_query()` AND-joins plain words and
  passes quotes, `AND`/`OR`/`NOT` and `field:` syntax through.
- **Filters:** `peerreviewed:T`, `e_fulltextauth:1` (not `T`),
  `publicationdateyear:[2018 TO *]`; `find` appends
  `AND NOT publicationtype:Dissertations*` unless `--include-dissertations`.
- **No DOI field and no citation counts** (`cites n/a`); ERIC-only entries
  have no DOI, so `oa` reaches ERIC through a confident (≥ 0.90) title match.
- ERIC stopped indexing 159 sources in 2025. EdWorkingPapers has no OpenAlex
  source record — reach it through `eric`.
- Strings carry HTML entities, sometimes double-escaped; the mapper unescapes
  until stable.

## Storage and ToS

U.S. federal (IES) metadata; abstracts may carry publisher rights. ERIC
terms were not re-fetched in S1. `LICENSE_CLASS = "open"`. Attribute
"ERIC, Institute of Education Sciences" when it materially supports findings.

## Exit mapping

HTTP errors → 11; network → 4; timeout → 6. Zero hits is exit 0.

## Minimal smoke test

```
bash /daaf/scripts/scholar_search.sh eric '"high-dosage tutoring"' {PROJECT_DIR}/lit_search --limit 3
```
