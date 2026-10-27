# Toolchain: versions, licenses, Dockerfile, rebuilds and tests

What the PDF layer runs on, why each piece was chosen, where it is
installed, and how to check it. Versions and licenses were read on
2026-10-19 from the installed distributions' metadata and the Debian
copyright files (FE-4 script
`research/2026-10-02_FrameworkDev_ScholarlySearch/scripts/57_fe4_preedit_diffs_and_licenses.py`,
its appended log) [obs].

## Components

| Component | Version | License (as declared) | Used by | Role |
|-----------|---------|-----------------------|---------|------|
| poppler-utils (`pdftotext`, `pdfinfo`, `pdftoppm`, `pdfimages`, `pdffonts`) | 24.02.0-1ubuntu9.9 | GPL-2 or GPL-3 (Debian copyright file) | pdf_ingest; lit_verify (`pdftotext`, `pdfinfo`, `pdfimages`: re-derivation) | Anchor text, page info, renders, image and font listings; called as separate programs |
| tesseract-ocr (+ `-eng`, `-osd`) | 5.3.4-1build5 | Apache-2.0 | pdf_ingest | OCR on scanned pages only, CPU, `OMP_THREAD_LIMIT=1` |
| pypdfium2 | 5.13.0 | "BSD-3-Clause, Apache-2.0, dependency licenses" | pdf_ingest, lit_verify | Lane B text (lit_verify re-derives it) |
| pdfplumber | 0.11.10 | MIT (classifier) | pdf_ingest, lit_verify | Table hints, image boxes, char rotation (lit_verify: `find_tables` and image boxes where a flag needs it) |
| pdfminer.six | 20260107 | MIT | (pdfplumber) | Layout engine under pdfplumber |
| rapidfuzz | 3.14.6 | MIT | pdf_ingest, lit_verify | Agreement score; the NEAR tier |
| polars (or pyarrow) | as pinned elsewhere in the image | not re-read in FE-4 (not part of the PDF stack block) | both | `page_index.parquet` |

pdfminer.six also pulls in cryptography 50.0.1, cffi 2.1.1 and pycparser 3.0;
the Dockerfile pins all nine distributions of the stack and names their
licenses in the block comment.

**Excluded:** PyMuPDF / pymupdf4llm (AGPL; user decision D-2), pypdf (not
needed: pypdfium2 covers it), Gemini and LlamaParse (upload lanes, deferred:
no keys or SDK in the container; spec §1), OCRmyPDF (brings LGPL/AGPL
dependencies and produces a PDF DAAF does not need; note 08 § 3).
poppler-data (CJK CMaps) is not installed; `pdf_ingest` records
`poppler_data_present: false` and the `cjk_risk` flag.

## Where it is installed

- `poppler-utils`: the early system-deps apt block of the Dockerfile.
- Tesseract: the "Install Geospatial System Libraries (GDAL/GEOS/PROJ) + PDF
  OCR (Tesseract)" apt layer (merged 2026-10-14 to share its index refresh).
- Python packages: the "Install the DAAF PDF reading stack" `uv pip install
  --system` block in the Python section, before the provider-shim block,
  pinned at or before the frozen environment date.

All framework layers, never the USER ADDITIONS block (checklist FC17). The
image was rebuilt with the stack on 2026-10-13.

## Adding or changing a dependency

Runtime installs are blocked by DAAF's hooks and `run_with_capture.sh`. A
change goes into the Dockerfile's framework layers (Ask First, checklist
FC17: pin every distribution, dry-run `uv pip compile` on both architectures,
update the `daaf-apt-update` count in `tests/bash/daaf_lib.bats` for a new
apt layer), then the user rebuilds: exit the container, then
`bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1` on Windows) from `daaf-docker`.
After a rebuild that changes a lane, re-ingest with `--reingest`; the ingest
manifest records the exact tool versions per lane.

## Checking the environment

`pdf_ingest` records what it found: `lanes` (tool, exact version, invocation)
and `lanes_unavailable` in every `ingest_manifest.json`, and
`lanes_unavailable` on stdout and in the MANIFEST row. That record is the
check: there is no separate probe to run. Missing required pieces exit 10
with the names.

## Tests

Tool versions: `pdf_ingest` 1.2.2-daaf (`HTML_EXTRACT_VERSION`
`arxiv-html-v1`), `lit_verify` 1.8.0-daaf (card schemas v1 and v2, result
schema `lit-verify-card-check-v2`, re-derivation `rederive-v2`),
`pdf_text_common` `normalize-v1`, `ladder-v4`, `numbers-v6`,
`column-check-v1`, `overlap-v1`. The arXiv HTML lane uses only the
Python standard library (`html.parser`) and polars: no new dependency.
`lit_verify` re-derives PDF anchors with poppler's `pdftotext` and `pdfinfo`,
and (1.8.0) page flags with `pdfimages` (exit 10 without any of the three),
all reading a sealed memfd (Linux); lane B with pypdfium2 (without it lane B
is not used); pdfplumber only for `table` / image checks where needed
(without it those flags are read conservatively, `FLAGS_NOT_REDERIVED`).
Re-derivation cost per card (S3-C1a, 2026-10-27, the nine bake-off cards):
0.065–0.30 s, and 1.67 s for the 192-page report (0.97 s under 1.7.0; the
extra `pdfimages -list` and `pdfinfo -f 1 -l N` passes plus `find_tables`
on its 2 cited caption-less table pages).

| Suite | Count (S3-D run, 2026-10-27, WS script 122) | Needs |
|-------|------------------|-------|
| `tests/python/test_pdf_ingest.py` | 59 | poppler-utils, tesseract, quarto (bundled typst) for the regeneration test, pypdfium2, pdfplumber, rapidfuzz, polars; skipped without them |
| `tests/python/test_lit_verify.py` | 121 | rapidfuzz and polars or pyarrow (polars for the arXiv HTML cases); end-to-end tests run real `pdf_ingest` and re-derivation (poppler, pypdfium2) |
| `tests/python/test_scholar_search.py` (regression, shares `web_retrieval_common.py`) | 250 (6 expected failures) | none beyond the image |
| `tests/python/test_web_fetch_scrub.py` (`web_fetch.py`'s own injection scrub, kept in step with the shared one) | 7 | none (reads the source; no network) |
| `bash /daaf/scripts/lit_verify.sh selftest <scratch dir>` | 44 expectations | rapidfuzz, polars or pyarrow, and polars (the arXiv HTML case runs `pdf_ingest --source arxiv-html`); no PDF tools (its ingests are synthetic) |

Run the suites file-first: a captured `.py` under the session's `scripts/`
calls `python3 -m unittest discover -s /daaf/tests/python -p "test_pdf_ingest.py"`
through `subprocess` and is executed with `run_with_capture.sh`. Fixtures are
synthetic (the repository is published) and regenerate from their typst
sources with `tests/python/fixtures/pdf_ingest/generate_fixtures.py`. The
CONTRIBUTING change-surface matrix has a row for each CLI.

## Citing the tools

When PDF-derived evidence supports a deliverable, the methods or data
section can name the extraction stack and versions from the ingest
manifests (poppler `pdftotext` for page text, Tesseract for OCR pages). The
README acknowledgments credit the stack.
