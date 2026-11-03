#!/usr/bin/env python3
# =============================================================================
# generate_fixtures.py - regenerate the synthetic pdf_ingest test fixtures
#                        (added 2026-10-13, Lit Review S3, FE-2)
# =============================================================================
#
# Everything in this directory is SYNTHETIC: typst sources written for DAAF's
# tests, compiled with Quarto's bundled typst. No third-party document text
# enters a fixture (the repository is published; FRAMEWORK_INTEGRATION_
# CHECKLIST.md FC11).
#
# Layout (all paths relative to this directory):
#   typ/*.typ              typst sources (hand-written; the only inputs)
#   img/figure_art.png     raster of typ/figure_art.typ (pdftoppm -r 100)
#   img/scan_source.png    grayscale raster of typ/scan_source.typ
#                          (pdftoppm -gray -r 150); embedded as an image by the
#                          image-only fixtures, so they carry no text layer
#   pdf/<name>.pdf         the fixtures the tests ingest:
#                            single_column, two_column, tables, figure,
#                            scanned, rotated, ocr_layer, multipage, hostile
#                          (hostile: forged status / injection lines that the
#                          reading copy must redact and the anchor must keep)
#                          plus rotate_attr.pdf: single_column.pdf with a real
#                          /Rotate 90 page attribute, set with pypdfium2 (typst
#                          cannot write /Rotate)
#   expected/<name>.pNNN.txt  pdftotext default-mode output (-enc UTF-8) for
#                          every fixture page at generation time; the
#                          regeneration test compares freshly compiled text to
#                          these files (text, never bytes)
#
# Determinism: every typst source sets `document(date: none)`, so a recompile
# with the same typst version yields the same text. Intermediate PDFs used
# only to make the rasters go to _build/, which is removed before exit.
#
# Run file-first (DAAF's execution rule): a captured script in a session
# workspace calls this file through subprocess, executed with
# scripts/run_with_capture.sh. Needs: quarto (bundled typst), pdftoppm,
# pdftotext, pdfinfo, and the pypdfium2 Python package.
# =============================================================================

# --- Config ---
import hashlib
import os
import shutil
import subprocess
import sys

FIX_DIR = os.path.dirname(os.path.abspath(__file__))
TYP_DIR = os.path.join(FIX_DIR, "typ")
IMG_DIR = os.path.join(FIX_DIR, "img")
PDF_DIR = os.path.join(FIX_DIR, "pdf")
EXP_DIR = os.path.join(FIX_DIR, "expected")
BUILD_DIR = os.path.join(FIX_DIR, "_build")
FIXTURES = ["single_column", "two_column", "tables", "figure", "scanned", "rotated", "ocr_layer", "multipage",
            "hostile"]
TIMEOUT_S = 300

import pypdfium2 as pdfium

for d in (IMG_DIR, PDF_DIR, EXP_DIR):
    os.makedirs(d, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

try:
    # --- Rasters: figure art and scan source ---
    # INTENT: compile each source drawing to a throwaway PDF in _build/, then
    #   rasterize page 1 to img/. pdftoppm writes the PNG to stdout (no output
    #   prefix), so every write below is this script's own.
    # REASONING: an embedded raster is what makes the figure and image-only
    #   pages realistic (pdfimages lists it; pdftotext finds no text in it).
    for name, ppm_args in (("figure_art", ["-png", "-r", "100"]), ("scan_source", ["-png", "-gray", "-r", "150"])):
        src_pdf = os.path.join(BUILD_DIR, f"{name}.pdf")
        proc = subprocess.run(["quarto", "typst", "compile", "--root", FIX_DIR,
                               os.path.join(TYP_DIR, f"{name}.typ"), src_pdf],
                              capture_output=True, text=True, timeout=TIMEOUT_S)
        print(f"compile {name}.typ -> exit {proc.returncode} {proc.stderr.strip()[:300]}")
        assert proc.returncode == 0, f"typst failed on {name}"
        png = subprocess.run(["pdftoppm", *ppm_args, "-f", "1", "-l", "1", "-singlefile", src_pdf],
                             capture_output=True, timeout=TIMEOUT_S)
        assert png.returncode == 0 and png.stdout[:8] == b"\x89PNG\r\n\x1a\n", f"pdftoppm failed on {name}"
        with open(os.path.join(IMG_DIR, f"{name}.png"), "wb") as f:
            f.write(png.stdout)
        print(f"  img/{name}.png {len(png.stdout)} bytes")

    # --- Fixtures: compile every typst source to pdf/ ---
    for name in FIXTURES:
        out_pdf = os.path.join(PDF_DIR, f"{name}.pdf")
        proc = subprocess.run(["quarto", "typst", "compile", "--root", FIX_DIR,
                               os.path.join(TYP_DIR, f"{name}.typ"), out_pdf],
                              capture_output=True, text=True, timeout=TIMEOUT_S)
        print(f"compile {name}.typ -> exit {proc.returncode} {proc.stderr.strip()[:300]}")
        assert proc.returncode == 0, f"typst failed on {name}"

    # --- Derived fixture: a real /Rotate attribute ---
    # INTENT: typst has no way to write a page's /Rotate entry, so the rotated-
    #   attribute case is single_column.pdf with page 1 set to /Rotate 90.
    doc = pdfium.PdfDocument(os.path.join(PDF_DIR, "single_column.pdf"))
    doc[0].set_rotation(90)
    doc.save(os.path.join(PDF_DIR, "rotate_attr.pdf"))
    doc.close()
    info = subprocess.run(["pdfinfo", "-f", "1", "-l", "1", os.path.join(PDF_DIR, "rotate_attr.pdf")],
                          capture_output=True, text=True, timeout=TIMEOUT_S)
    rot_lines = [l for l in info.stdout.splitlines() if " rot:" in l]
    print(f"rotate_attr.pdf pdfinfo: {rot_lines}")
    assert rot_lines and rot_lines[0].split()[-1] == "90", "rotate_attr.pdf lacks /Rotate 90"

    # --- Expected text: pdftotext default mode per page ---
    # INTENT: the anchor lane's exact output at generation time, one file per
    #   page, for the regeneration test (text comparison, never bytes).
    for old in os.listdir(EXP_DIR):
        if old.endswith(".txt"):
            os.remove(os.path.join(EXP_DIR, old))
    for name in FIXTURES + ["rotate_attr"]:
        path = os.path.join(PDF_DIR, f"{name}.pdf")
        info = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=TIMEOUT_S)
        pages = int([l for l in info.stdout.splitlines() if l.startswith("Pages:")][0].split()[1])
        for n in range(1, pages + 1):
            txt = subprocess.run(["pdftotext", "-f", str(n), "-l", str(n), "-enc", "UTF-8", path, "-"],
                                 capture_output=True, timeout=TIMEOUT_S)
            assert txt.returncode == 0, f"pdftotext failed on {name} p{n}"
            with open(os.path.join(EXP_DIR, f"{name}.p{n:03d}.txt"), "wb") as f:
                f.write(txt.stdout)
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        print(f"pdf/{name}.pdf pages={pages} bytes={os.path.getsize(path)} sha256={digest[:16]}")
finally:
    # --- Cleanup: intermediate PDFs ---
    shutil.rmtree(BUILD_DIR, ignore_errors=True)

# --- Validate ---
assert not os.path.exists(BUILD_DIR), "_build/ was not removed"
print("expected files:", len([n for n in os.listdir(EXP_DIR) if n.endswith(".txt")]))
print("python", sys.version.split()[0], "| pypdfium2", str(pdfium.PYPDFIUM_INFO))
