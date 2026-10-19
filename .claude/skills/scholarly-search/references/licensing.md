# Licensing, storage and attribution across backends

What may be stored, what may be shared, and what must be credited, per
backend. The tool enforces the storage split mechanically: every MANIFEST row
carries `license_class` (the most restrictive class among the backends the
command **selected** — the row's `backends_selected` — decided before any
request is sent, so a selected backend that then fails or is skipped still
sets the class; the one exception is split storage, below), and artifacts from `restricted` backends are written to
`lit_search/restricted/`, which is excluded from any shareable bundle and must
be named in the AI/data disclosure. Sources: vendor docs and terms fetched
2026-10-02 (S1 workspace `web_fetches/apis/`, summarized in
`preliminary_notes/05_research_scholarly_apis.md` §4) and 2026-10-11
(`web_fetches/s2_research/`, `preliminary_notes/07_research_s2_elicit_scite.md`).

**Split storage (`retractions`, tool 1.2.0).** `retractions` is the one
command whose digest holds facts only (status, notice DOIs, dates). When it
mixes restricted and open backends (by default OpenAlex + Crossref + Scite),
the restricted backends' raw responses go to `restricted/<base>.json` (row:
`restricted_raw_artifact`, `restricted_backends`, `restricted_storage`), the
open raw log and the digest stay in `lit_search/`, and the row's
`license_class` describes what stays in `lit_search/` (`open`). With only
restricted backends selected (`--skip openalex --skip crossref`) everything
goes to `restricted/` as usual; `--skip scite` keeps Scite out entirely.

## License classes

| Class | Meaning | Storage | Sharing |
|-------|---------|---------|---------|
| `open` | CC0 or "use for any purpose" metadata | `lit_search/` | Shareable with the project |
| `cc-by-nc` | Non-commercial with attribution | `lit_search/` | Research sharing with attribution; no commercial redistribution |
| `restricted` | Vendor terms bar redistribution or derived datasets | `lit_search/restricted/` | **Never** shared or bundled |

User-supplied PDFs are a separate, private class (`private`, spec §13) handled
by the PDF layer: see the `pdf-reading` skill § Privacy.

## Matrix

| Backend | Class | Cache raw JSON? | OA PDFs | Attribution | Status |
|---------|-------|-----------------|---------|-------------|--------|
| OpenAlex | open | Yes — CC0, "no 'personal use only' carve-out" | Downloadable; "PDFs retain their original copyright" | Requested: Priem, Piwowar & Orr (2022), arXiv:2205.01833 | Built (S1) |
| Semantic Scholar | cc-by-nc | Yes, under S2 Data Licenses (CC BY-NC or ODC-BY) | Not via S2 | **Required**: credit "Semantic Scholar"; cite the Open Data Platform paper (arXiv:2301.10140) | Built (S1) |
| ERIC | open | Yes (U.S. federal metadata; abstracts may carry publisher rights) | `files.eric.ed.gov` PDFs: per-document rights | Courtesy: "ERIC, Institute of Education Sciences" | Built (S1) |
| Crossref | open | Yes — "use it for any purpose"; some abstracts copyrighted | n/a | Not required | Built (S1) |
| Unpaywall | open | Yes (same data as OpenAlex) | Points to PDFs that keep their own license | Not required | Built (S1) |
| arXiv (derived leg) | open | Metadata CC0 | Store and use "for research purposes"; no redistribution without the rights holder | — | Derived, no API call |
| **Scite** | restricted | **Restricted** (decision D-4, "accepted for now"): Terms §8(b) bar storing, redistributing or making content (incl. Classifier Results = tallies) "or any dataset derived from it, available to any third party", keyless endpoints included. Keyless tallies and retraction notices on by default; `scite-search` behind `--ack-scite-license` (Pro key is "for evaluation"; research use of Search needs a separate license). `scite-tally`/`scite-search` artifacts all in `restricted/`; `retractions` splits (Scite raw in `restricted/`, facts-only digest open). The `tests/python/fixtures/scholar_search/scite_*.json` fixtures are synthetic (tool 1.4.0, 2026-10-12): live response shapes with invented values, no Scite content (see `scite.md`) | Not via Scite | No attribution clause; never remove author/licensor notices (§4(iii)) | Built (S2, 2026-10-11) |
| **Elicit** | restricted | "You may store and reuse API Outputs" (§3.5), but "You may not aggregate search results to build or contribute to a standalone search index, database, or corpus" (§3.5), and "you will delete any cached API Outputs within 30 days" of termination (§12.3). No submitting personal data, "includes names" (§2); no use of outputs "to train, fine-tune, evaluate, or improve any machine learning model or AI system" (§3.2(b)); outputs are non-deterministic (§4.2). Every `elicit-*` artifact is in `restricted/` (report bodies as `restricted/<base>_report.md`; presigned export links never leave it); the MANIFEST row holds counts, statuses and the sessionId only. Opt-in to `find` only. The `tests/python/fixtures/scholar_search/elicit_*.json` fixtures are synthetic (tool 1.4.0, 2026-10-12): the trial's response shapes with invented values, no Elicit output (see `elicit.md`) | `fullTextUrl` carries no license: never treated as OA (`oa` decides) | **Disclose AI generation** wherever a report or summary is used (§3.4); no citation clause | Built (S2, 2026-10-11) |

## Redistribution rule for papers

A PDF's license comes from its OA location (`oa` reports it). Share only
CC BY, CC BY-SA and CC0 items. Everything else — including "free to read"
publisher copies with no license (`license: unknown`) — is stored for private
research use and never redistributed.

## Attribution in deliverables

The literature-review deliverable's data-sources section must carry the
OpenAlex citation and the Semantic Scholar credit whenever those backends
contributed records (check `backends_selected` in MANIFEST rows). When any
part of an Elicit report (title, summary, abstract, body) is used, the
deliverable must disclose that it was AI-generated by Elicit (API Terms
§3.4), and the AI/data disclosure must name it. Elicit search hits are
bibliographic records: `verify` them and cite the papers themselves.
`bash /daaf/scripts/scholar_search.sh backends` prints each adapter's
attribution line to stdout, with or without a DEST_DIR (with one, the lines
are also in the digest).
