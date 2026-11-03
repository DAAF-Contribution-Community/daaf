# Long papers and chunked reading

How to read a document too long for one careful pass: technical reports,
dissertations, government reports over ~60 pages. The rules: one paper per
dispatch; sequential chunks over ~60 pages with a running-notes block, the
Chain-of-Agents pattern (https://arxiv.org/abs/2406.02818, accessed
2026-10-02) [doc]; and the overlap-page lesson of the
user's source skill. The source skill's parallel chunk agents are dropped:
only the orchestrator dispatches, and parallel chunks lose the running notes.

## When to chunk

- Up to ~60 pages: one reader reads the whole paper. A 30-page paper is
  about 25–35k text tokens plus ~8 renders at ~4k each [inf].
- Over ~60 pages: the orchestrator splits the paper on page boundaries into
  sequential dispatches. The ingest is done **once** for the whole PDF (one
  paper key, one manifest); chunks are page ranges of it.
- `pdf_ingest` refuses more than 600 pages by default (exit 7). Raise
  `--max-pages` deliberately for a longer document, and say so.
- A reader at ELEVATED context or above returns early with its notes
  (CLAUDE.md § Subagent Context Monitoring); the orchestrator re-dispatches
  the rest.

## The running-notes block

Each chunk's reader returns, and the next chunk's reader receives, a block
like:

```
RUNNING NOTES (paper KEY, through page P of N)
- Structure so far: sections and the pages they span
- Definitions and abbreviations introduced (page)
- Tables and figures seen, with the page each is on
- Claims recorded so far: claim_ids and pages
- Open threads: a table continued on the next page; a forward reference
- Pages covered so far: 1..P (every page has a coverage entry)
```

Notes summarize; they never stand in for a quote. Every quote in the final
card is copied from `pages/` by the reader who records it.

## Assembling one card

The card covers pages 1..N in one `coverage` array, so the chunks contribute
entries to a single card:
- The orchestrator (or the last chunk's reader) assembles one
  `evidence_card.md` from the chunk returns, keeping each entry as written.
- Claim IDs are unique across chunks (prefix by chunk, e.g. `K2.C4`).
- `lit_verify card` runs once on the assembled card; the revision loop
  (at most two) applies to the assembled card.

## Overlap pages

A sentence or table that crosses a chunk boundary belongs to the chunk where
it starts. Give the next reader the last page of the previous chunk as
read-only context, and state in the running notes which items continue. A
quote that crosses the page break uses `page_end` like any other span. Do not
record the same page twice: `coverage` rejects a duplicate page (exit 8).

## Very long or scanned documents

Scanned reports (often old federal documents) are slow to OCR (one thread,
300 DPI) and read only as `PASS_OCR` at best, so their cards are capped at
PARTIAL. If the OCR mean confidence in `ingest_manifest.json` is low across
many pages, tell the orchestrator before reading: the paper may not support
numeric claims at all.
