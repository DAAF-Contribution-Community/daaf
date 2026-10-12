# Crossref

Keyless DOI metadata: the `verify` fallback and the main source of
retraction, correction and expression-of-concern notices (Retraction Watch
data, acquired by Crossref in 2023). Adapter:
`scripts/scholar_backends/crossref.py`. Docs fetched 2026-10-02 (S1 workspace
`web_fetches/apis/`): REST API overview, access and authentication,
Retraction Watch.

## Auth

None required. Pools:

| Pool | How | Rate | Concurrency |
|------|-----|------|-------------|
| Public | nothing | 5 req/s | 1 |
| Polite | `mailto` param or User-Agent contact | 10 req/s | 3 |
| Plus | paid `Crossref-Plus-API-Token` | 150 req/s | none |

The tool uses the polite pool only when the user sets
`SCHOLARLY_CONTACT_EMAIL` (sent as `mailto`; replaced by
`[SCHOLARLY_CONTACT_EMAIL]` in logged params, raw artifacts, digests,
MANIFEST rows and printed lines).
Unset → public pool, with a one-line note. No address is hard-coded.

## Endpoints used

| Use | Request | Command |
|-----|---------|---------|
| DOI record | `GET /works/{doi}` | `verify`, `oa` (title), `retractions` |
| Title match | `GET /works?query.bibliographic=<title>&rows=5` | `verify title:"…"` |
| Topical search | `GET /works?query=<q>&rows` (+ `from-pub-date`/`until-pub-date`) | `find --backends …,crossref` |
| Notices updating a DOI | `GET /works?filter=updates:{doi}` | `retractions` |

## Cost and limits

Free. 429 when over the pool rate; 403 on a manual block. Headers
`x-rate-limit-limit`, `x-rate-limit-interval`, `x-concurrency-limit` (and
`x-api-pool` on Plus) are recorded in the MANIFEST cost field. The tool gates
the lane at 0.25 s container-wide (public pool, one at a time).

## Measured behavior (2026-10-02)

- **Retraction signals agree:** for the Wakefield 1998 Lancet paper
  (`10.1016/S0140-6736(97)11096-0`) both the work's `updated-by` list and
  `filter=updates:{doi}` returned the 2010 retraction
  (`10.1016/s0140-6736(10)60175-4`) and a 2004 correction, each with
  `source: retraction-watch`. The adapter de-duplicates by (notice DOI, type)
  and records every path that surfaced a notice (`via`).
- For the QJE school-spending paper (`10.1093/qje/qjv036`) both signals were
  empty → status `none` ("no notice on record", not "sound").
- Abstracts arrive as JATS XML; the mapper strips tags.

## Retraction status values

`retraction_check` maps each notice's `type` through `UPDATE_KINDS` and
reports the most severe:

| Status | Notice types |
|--------|--------------|
| `retracted` | `retraction`, `withdrawal`, `removal` |
| `expression of concern` | `expression_of_concern` |
| `corrected` | `correction`, `erratum`, `corrigendum` |
| `updated` | at least one notice exists, but none of the kinds above (e.g. `addendum`, `new_version`) — read the notice; not a hard flag |
| `none` | no notice on record at Crossref (not proof the paper is sound) |

The mapper also marks a record `retracted` when the work's own `updated-by`
list carries a retraction-kind notice, so `verify` (Crossref fallback) and
`find --backends …,crossref` tag it "[RETRACTED per Crossref]". No such
notice leaves `retracted` unknown, never false.

## Storage and ToS

"almost none of the metadata is subject to copyright, and you may use it for
any purpose. Some abstracts … may be subject to copyright". Retraction Watch
data is publicly available through Crossref. `LICENSE_CLASS = "open"`; no
attribution required (courtesy credit is fine).

## Exit mapping

404 on `/works/{doi}` → NOT FOUND leg (verify continues/records it);
429/5xx after retries → 11; network → 4; timeout → 6.

## Minimal smoke test

```
bash /daaf/scripts/scholar_search.sh retractions '10.1016/S0140-6736(97)11096-0' {PROJECT_DIR}/lit_search   # expect RETRACTED
```
