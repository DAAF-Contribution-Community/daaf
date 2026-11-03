# Toolchain: versions, licenses, Dockerfile, rebuilds and tests

What the PDF layer runs on, why each piece was chosen, where it is
installed, and how to check it. Versions and licenses were read on
2026-10-19 from the installed distributions' metadata and the Debian
copyright files [obs].

## Components

| Component | Version | License (as declared) | Used by | Role |
|-----------|---------|-----------------------|---------|------|
| poppler-utils (`pdftotext`, `pdfinfo`, `pdftoppm`, `pdfimages`, `pdffonts`) | 24.02.0-1ubuntu9.9 (read 2026-10-19); the Dockerfile's apt snapshot `20261024T000000Z` (2026-10-28) selects 24.02.0-1ubuntu9.11, Ubuntu security patches of the same upstream release, from the next rebuild | GPL-2 or GPL-3 (Debian copyright file) | pdf_ingest; lit_verify (`pdftotext`, `pdfinfo`, `pdfimages`: re-derivation) | Anchor text, page info, renders, image and font listings; called as separate programs |
| tesseract-ocr (+ `-eng`, `-osd`) | 5.3.4-1build5 | Apache-2.0 | pdf_ingest | OCR on scanned pages only, CPU, `OMP_THREAD_LIMIT=1` |
| pypdfium2 | 5.13.0 | "BSD-3-Clause, Apache-2.0, dependency licenses" | pdf_ingest, lit_verify | Lane B text (lit_verify re-derives it) |
| pdfplumber | 0.11.10 | MIT (classifier) | pdf_ingest, lit_verify | Table hints, image boxes, char rotation (lit_verify: `find_tables` and image boxes where a flag needs it) |
| pdfminer.six | 20260107 | MIT | (pdfplumber) | Layout engine under pdfplumber |
| rapidfuzz | 3.14.6 | MIT | pdf_ingest, lit_verify | Agreement score; the NEAR tier |
| polars (or pyarrow) | as pinned elsewhere in the image | not re-read on 2026-10-19 (not part of the PDF stack block) | both | `page_index.parquet` |

pdfminer.six also pulls in charset-normalizer 3.5.1 and cryptography 50.0.1
(with cffi 2.1.1 and pycparser 3.0 beneath it), and pdfplumber pulls in
pillow. pillow and charset-normalizer were already in the image;
charset-normalizer is pinned at the version it had resolved, 3.5.1. pillow
was 12.3.0 when these versions were read; since 2026-10-28 the Dockerfile
pins 13.0.0 through a one-package `--exclude-newer-package` override (a
security exception: 12.3.0 has 41 published advisories), effective from the
next rebuild. The Dockerfile pins all nine distributions of the stack and
names their licenses in the block comment.

After that rebuild, re-check a few known papers, since a poppler patch
release can still change extraction in rare cases. The cheapest whole-paper
check is `lit_verify card` on an existing card: its `rederive` step re-runs
`pdftotext` with the installed poppler on every page of the source PDF and
compares the text byte for byte with the stored anchors (`rederive.method`),
and `anchor_mismatches` lists the pages that changed. To compare the
ingests themselves, re-ingest (`--reingest`, or a first ingest into a fresh
folder) and compare the anchor text, but compare like with like: a
re-ingest after a poppler update also picks up any `pdf_ingest` change
since the older ingest, so compare two ingests with the same `tool_version`
in `ingest_manifest.json`, for example one made just before the rebuild and
one just after. The manifest does not tell the two poppler builds apart:
its `lanes.anchor.version` is poppler's upstream version only
(`pdftotext version 24.02.0` under 24.02.0-1ubuntu9.9, observed
2026-10-28; 9.11 has the same upstream number, so the string is expected
not to change, inference), so record Ubuntu's package revision with
`dpkg-query -W poppler-utils` beside each ingest.

**Excluded:** PyMuPDF / pymupdf4llm (AGPL; excluded by user decision), pypdf
(not needed: pypdfium2 covers it), Gemini and LlamaParse (upload lanes,
deferred: no keys or SDK in the container), OCRmyPDF (brings LGPL/AGPL
dependencies and produces a PDF DAAF does not need).
poppler-data (CJK CMaps) is not installed; `pdf_ingest` records
`poppler_data_present: false` and the `cjk_risk` flag.

## Where it is installed

- `poppler-utils`: the early system-deps apt block of the Dockerfile.
- Tesseract: the "Install Geospatial System Libraries (GDAL/GEOS/PROJ) + PDF
  OCR (Tesseract)" apt layer (merged 2026-10-14 to share its index refresh).
- Python packages: the "Install the DAAF PDF reading stack" `uv pip install
  --system` block in the Python section, before the provider-shim block,
  pinned at or before the frozen environment date, except pillow (one-package
  override, above).

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
manifest records each lane's tool version as the tool reports it. For the
Python packages that is the exact version (`pypdfium2` `5.13.0`); for
poppler and Tesseract it is the upstream version without Ubuntu's package
revision (`pdftotext version 24.02.0`, `tesseract 5.3.4`), so a patch
release such as poppler 24.02.0-1ubuntu9.9 to 9.11 does not show there:
`dpkg-query -W poppler-utils tesseract-ocr` gives the package versions.

## Checking the environment

`pdf_ingest` records what it found: `lanes` (tool, version as the tool reports it, invocation)
and `lanes_unavailable` in every `ingest_manifest.json`, and
`lanes_unavailable` on stdout and in the MANIFEST row. That record is the
check: there is no separate probe to run. Missing required pieces exit 10
with the names.

## Tests

Tool source: `scripts/pdf_ingest.py`, `scripts/lit_verify.py` (its `report`
rules in `scripts/lit_report_rules.py`) and `scripts/pdf_text_common.py`
(NORMALIZE, SKELETON, ladder and number rules).

Tool versions: `pdf_ingest` 1.2.2-daaf (`HTML_EXTRACT_VERSION`
`arxiv-html-v1`), `lit_verify` 1.17.0-daaf (card schemas v1, v2 and v3,
result schema `lit-verify-card-check-v3`, re-derivation `rederive-v2`;
`report`: `lit-verify-report-check-v1`, `report-rederive-v8`, rules in
`lit_report_rules.py`),
`pdf_text_common` `normalize-v1`, `ladder-v4`, `numbers-v6`,
`column-check-v1`, `overlap-v1`. The arXiv HTML lane uses only the
Python standard library (`html.parser`) and polars: no new dependency.
`lit_verify` re-derives PDF anchors with poppler's `pdftotext` and `pdfinfo`,
and (1.8.0) page flags with `pdfimages` (exit 10 without any of the three),
all reading a sealed memfd (Linux); lane B with pypdfium2 (without it lane B
is not used); pdfplumber only for `table` / image checks where needed
(without it those flags are read conservatively, `FLAGS_NOT_REDERIVED`).
Re-derivation cost per card (2026-10-27, the nine bake-off cards):
0.065–0.30 s, and 1.67 s for the 192-page report (0.97 s under 1.7.0; the
extra `pdfimages -list` and `pdfinfo -f 1 -l N` passes plus `find_tables`
on its 2 cited caption-less table pages).

| Suite | Count | Needs |
|-------|------------------|-------|
| `tests/python/test_pdf_ingest.py` | 59 | poppler-utils, tesseract, quarto (bundled typst) for the regeneration test, pypdfium2, pdfplumber, rapidfuzz, polars; skipped without them |
| `tests/python/test_lit_verify.py` | 264 | rapidfuzz and polars or pyarrow (polars for the arXiv HTML cases); end-to-end tests run real `pdf_ingest` and re-derivation (poppler, pypdfium2); the `report` rule tests are stdlib, its on-disk tests copy the `lit_corpus` P3 contract bundle, and the phrase-table lockstep test needs PyYAML |
| `tests/python/test_scholar_search.py` (regression, shares `web_retrieval_common.py`) | 296 | none beyond the image |
| `tests/python/test_web_fetch_scrub.py` (`web_fetch.py`'s own injection scrub, kept in step with the shared one) | 7 | none (reads the source; no network) |
| `bash /daaf/scripts/lit_verify.sh selftest <scratch dir>` | 98 expectations (56 card, 18 `route`, `audit`, `settle` and `vision-override`, 24 `report`) | rapidfuzz, polars or pyarrow, and polars (the arXiv HTML case runs `pdf_ingest --source arxiv-html`; the `report` cases build a synthetic review with `lit_corpus`); no PDF tools (its ingests are synthetic) |

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
