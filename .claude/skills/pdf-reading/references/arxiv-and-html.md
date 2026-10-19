# arXiv papers: the HTML shortcut and its limits

arXiv papers have structured alternatives to the PDF: an HTML rendering and
the LaTeX source. They are good for reading equations and structure. They are
**not** a substitute for the ingested PDF when an evidence card must pass
`lit_verify`, because the gate anchors on `pdf_ingest`'s page text and page
numbers. Facts on this page come from the user's source skill
(`research/2026-10-02_FrameworkDev_ScholarlySearch/pdf-reading/references/extraction-strategies.md`
§ "ArXiv HTML Shortcut") and were not re-probed in FE-4 [inf until probed].

## Detecting an arXiv paper

- The record's IDs from `scholarly-search` (`work`, `oa`: the arXiv leg is
  derived from the ID), a URL on `arxiv.org`, or an ID the user gives.
- When scanning text for an ID, require the `arXiv` prefix (`arXiv:2310.08726`).
  A bare `NNNN.NNNNN` pattern matches many unrelated numbers; the source
  skill's analyzer regex had an optional prefix and matched them (note 10
  § 1) [inf].

## The HTML rendering

Fetch it like any other page, through the `web-retrieval` skill (built-in
WebFetch is blocked):

```
bash /daaf/scripts/web_fetch.sh https://ar5iv.labs.arxiv.org/html/{arxiv_id} {PROJECT_DIR}/web_fetches/
```

- Exit 0: read the `.md` extract first; go to the raw `.html` via `Grep` if
  the extract is thin (`web-retrieval` § Thin-Extract Diagnosis).
- The HTML keeps headings, MathML or LaTeX for equations, figure alt text,
  table structure and citation links (source skill).
- Unavailable or a failed conversion: use the PDF.
- Only retrieval contexts fetch. A reader that wants the HTML hands the need
  back to the orchestrator.

## The LaTeX source

`https://arxiv.org/e-print/{arxiv_id}` returns the source archive (source
skill). `web_fetch.sh` saves it raw (exit 8, not extractable). Unpacking an
archive is a separate, deliberate step (a captured script; no extraction into
`/tmp`). Use it only when exact equations matter.

## What the gate needs

| Need | Use |
|------|-----|
| Equations, section structure, what a figure shows | HTML or LaTeX, cited as such |
| A quote or number that must pass `lit_verify card` (Literature Review evidence cards) | The PDF: `pdf_ingest`, then quote from `pages/` |
| Page numbers for a citation | The PDF (HTML has none) |

An HTML extract is web content with its own provenance (the web_fetch
MANIFEST row). If a claim relies on it, say so in the card's prose; the gate
cannot verify it. Spec §7.1 lists the shortcut as "skip PDF parsing for arXiv
papers"; for gate-checked cards the PDF ingest is still required (flagged to
the orchestrator in FE-4 as a spec gap).
