# ERIC (Institute of Education Sciences)

The education-specific index: journals OpenAlex ranks poorly, EdWorkingPapers,
REL/IES reports, peer-review and full-text flags. Adapter:
`scripts/scholar_backends/eric.py`. Docs: https://eric.ed.gov/?api (a
Swagger UI over https://eric.ed.gov/api/eric-api.yaml, fetched 2026-10-28).

## Auth

None. JSON via `format=json`.

## Endpoints used

| Use | Request | Command |
|-----|---------|---------|
| Search | `GET https://api.ies.ed.gov/eric/?search=<solr>&format=json&rows≤200&fields=…` (200 is the tool's cap; the API spec says "Default is 20 and max is 2000") | `find`, `eric` |
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
- **ERIC cut the sources it actively catalogs in 2025.** The figures below
  come from secondary sources, university library pages fetched 2026-10-28;
  no ERIC page on the cut was extracted. A CSUDH library post
  (https://libguides.csudh.edu/blogs/system/changes-coming-to-eric-database)
  quotes the ERIC Help Desk: "The number of actively cataloged sources will
  be reduced by approximately 45% starting April 24, 2025", and adds that
  "the 1,283 journals regularly included in ERIC will be reduced to
  approximately 706". The UC Berkeley ERIC guide
  (https://guides.lib.berkeley.edu/education/ERIC), relaying ERIC's June 2025
  journal list, gives a smaller final figure: "159 sources (58 journals and
  101 non-journals) will no longer be included going forward". Records
  already in ERIC stay available ("all records currently in ERIC will remain
  available", the Help Desk notice); new issues of dropped sources are not
  indexed. Check ERIC's current journal list before relying on its coverage
  of a journal.
- EdWorkingPapers has no OpenAlex source record — reach it through `eric`.
- Strings carry HTML entities, sometimes double-escaped; the mapper unescapes
  until stable.

## Storage and ToS

U.S. federal (IES) metadata; abstracts may carry publisher rights. ERIC's
copyright page (https://eric.ed.gov/?copyright, fetched 2026-10-28): "The
authors or publishers retain copyright to these works", and "ERIC does not
retain copyright to the works indexed in the database". `LICENSE_CLASS = "open"`. Attribute
"ERIC, Institute of Education Sciences" when it materially supports findings.

## Exit mapping

HTTP errors → 11; network → 4; timeout → 6. Zero hits is exit 0.

## Minimal smoke test

```
bash /daaf/scripts/scholar_search.sh eric '"high-dosage tutoring"' {PROJECT_DIR}/lit_search --limit 3
```
