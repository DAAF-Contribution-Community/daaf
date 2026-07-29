# scripts/smoke_tests/smoke_imports.py
# Package smoke test: verifies all 52 explicitly pinned Python distributions from
# the Dockerfile pip install blocks. Fifty import targets must import cleanly and
# report their installed versions; two distributions without supported import
# targets are checked through package metadata only.
# Sequential inline script (DAAF code style): no functions, section separators,
# print + assert for validation. Exits nonzero on any failed check.
#
# The inventory is derived from every explicit Python pin in the
# `uv pip install --system` blocks in /daaf/Dockerfile (analysis packages plus
# direct provider-shim runtime dependencies). When the Dockerfile pins change,
# update both inventories to match. Import entries are (import_name, pip_name)
# because several import names differ from their pip package name (e.g.
# scikit-learn -> sklearn). The provider shim's direct runtime dependencies carry
# exact version assertions, as do the two metadata-only distributions, making
# those pins image-identity gates rather than only presence checks.
#
# Revision _c adds a metadata-sanity check: every pinned distribution must
# declare a non-empty runtime-dependency list (importlib.metadata.requires),
# except a verified allowlist of genuinely dependency-free packages. Motivated
# by pyfixest 0.40.0, whose wheel shipped with NO Requires-Dist metadata
# (packaging bug) — it installed "successfully" with none of its dependencies
# and only worked because unrelated pins supplied them transitively. A wheel
# whose declared deps silently vanish in a future bump now fails the smoke
# test at rebuild-validation time instead of failing in an analysis session.

# --- Config ---
import importlib
import importlib.metadata
import sys

# (import_name, pip_name) for the 50 pins with supported import targets.
# pip_name is used for metadata lookup and reporting so failures name the
# installable distribution.
packages = [
    # Block 1: core data science
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("polars", "polars"),
    ("scipy", "scipy"),
    ("openpyxl", "openpyxl"),
    ("fastexcel", "fastexcel"),
    ("xlrd", "xlrd"),
    ("requests", "requests"),
    ("pyarrow", "pyarrow"),
    ("urllib3", "urllib3"),
    ("pre_commit", "pre-commit"),
    ("sklearn", "scikit-learn"),
    ("umap", "umap-learn"),
    ("yaml", "pyyaml"),
    ("statsmodels", "statsmodels"),
    ("pyfixest", "pyfixest"),
    ("tabulate", "tabulate"),
    ("great_tables", "great-tables"),
    ("wildboottest", "wildboottest"),
    # Block 2: econometrics & statistical modeling
    ("linearmodels", "linearmodels"),
    ("rdrobust", "rdrobust"),
    ("marginaleffects", "marginaleffects"),
    ("arch", "arch"),
    ("pydynpd", "pydynpd"),
    ("svy", "svy"),
    # Block 3: geospatial
    ("geopandas", "geopandas"),
    ("rasterio", "rasterio"),
    ("xarray", "xarray"),
    ("rioxarray", "rioxarray"),
    ("contextily", "contextily"),
    ("folium", "folium"),
    ("libpysal", "libpysal"),
    ("esda", "esda"),
    ("spreg", "spreg"),
    ("mapclassify", "mapclassify"),
    ("rasterstats", "rasterstats"),
    ("geopy", "geopy"),
    ("osmnx", "osmnx"),
    # Block 4: visualization
    ("matplotlib", "matplotlib"),
    ("seaborn", "seaborn"),
    ("plotnine", "plotnine"),
    ("plotly", "plotly"),
    ("marimo", "marimo"),
    # Block 5: ML interpretation & fairness
    ("shap", "shap"),
    ("fairlearn", "fairlearn"),
    ("lightgbm", "lightgbm"),
    # Block 6: network analysis
    ("igraph", "igraph"),
    # Block 7: synthetic data generation
    ("faker", "faker"),
    # Late direct provider-shim runtime dependency layer
    ("httpx", "httpx"),
    ("uvicorn", "uvicorn"),
]

required_versions = {
    "httpx": "0.28.1",
    "uvicorn": "0.51.0",
}

# These distributions intentionally have no fabricated import target. Their
# installed presence and exact pins are validated through distribution metadata.
metadata_only_distributions = {
    "svy-rs": "0.10.0",
    "svy-io": "0.1.1",
}

explicit_distribution_total = len(packages) + len(metadata_only_distributions)
print(
    f"--- Python package smoke: {len(packages)} import targets + "
    f"{len(metadata_only_distributions)} metadata-only distributions = "
    f"{explicit_distribution_total} explicit pinned distributions ---"
)

# --- Import & Report ---
# INTENT: import each package and capture its version so a version-visible
#   record lands in the appended execution log.
# REASONING: a bare import check hides which build was tested; printing the
#   version makes the smoke result auditable against the Dockerfile pins.
# ASSUMES: import failures raise ImportError/ModuleNotFoundError, which we
#   collect rather than let abort the loop, so one failure does not mask others.
failures = []
for import_name, pip_name in packages:
    try:
        mod = importlib.import_module(import_name)
        version = importlib.metadata.version(pip_name)
        expected_version = required_versions.get(pip_name)
        if expected_version is not None and version != expected_version:
            raise AssertionError(
                f"expected pinned version {expected_version}, found {version}"
            )
        pin_note = f" [pinned={expected_version}]" if expected_version else ""
        print(
            f"OK   {pip_name:<16} (import {import_name}) "
            f"version {version}{pin_note}"
        )
    except Exception as exc:  # noqa: BLE001 -- report any import-time failure
        failures.append((pip_name, import_name, repr(exc)))
        print(f"FAIL {pip_name:<16} (import {import_name}) -> {exc!r}")

# INTENT: verify presence and exact versions for distributions that do not expose
#   supported import targets.
# REASONING: inventing module names would turn an image-inventory check into a
#   false import contract; distribution metadata verifies the pins directly.
# ASSUMES: importlib.metadata.version() raises PackageNotFoundError when an
#   expected distribution is absent.
metadata_failures = []
for pip_name, expected_version in metadata_only_distributions.items():
    try:
        version = importlib.metadata.version(pip_name)
        if version != expected_version:
            raise AssertionError(
                f"expected pinned version {expected_version}, found {version}"
            )
        print(
            f"OK   {pip_name:<16} (metadata only) "
            f"version {version} [pinned={expected_version}]"
        )
    except Exception as exc:  # noqa: BLE001 -- report every metadata failure
        metadata_failures.append((pip_name, repr(exc)))
        print(f"FAIL {pip_name:<16} (metadata only) -> {exc!r}")

# --- Metadata Sanity ---
# INTENT: assert every pinned distribution declares a non-empty runtime-
#   dependency list, except a verified allowlist of genuinely dependency-free
#   packages.
# REASONING: pyfixest 0.40.0 shipped a wheel with zero Requires-Dist entries (a
#   packaging bug) — installers resolved it "successfully" without any of its
#   real dependencies, and the import only worked because unrelated pins
#   supplied them transitively. requires() returning None/empty for a package
#   known to have dependencies is exactly that failure mode; catching it here
#   turns a latent, environment-dependent break into a rebuild-time failure.
# ASSUMES: the allowlist below is verified against the current image (probed
#   2026-07-24: numpy, pyarrow, and pyyaml are the only pinned distributions
#   whose requires() is legitimately empty — all three are famously
#   self-contained). If a future pin is genuinely dependency-free, add it here
#   with a comment; do NOT allowlist a package just to silence this check
#   without confirming upstream that it truly has no runtime deps.
dependency_free_allowlist = {"numpy", "pyarrow", "pyyaml"}

metadata_sanity_failures = []
all_pinned_distributions = [pip_name for _, pip_name in packages] + list(
    metadata_only_distributions
)
for pip_name in all_pinned_distributions:
    try:
        declared = importlib.metadata.requires(pip_name)
        if pip_name in dependency_free_allowlist:
            print(f"OK   {pip_name:<16} (metadata sanity) allowlisted dependency-free")
            continue
        if not declared:
            raise AssertionError(
                "declares NO runtime dependencies (pyfixest-0.40.0-style "
                "metadata bug, or a newly dependency-free release — verify "
                "upstream before allowlisting)"
            )
        print(
            f"OK   {pip_name:<16} (metadata sanity) "
            f"{len(declared)} declared dependency spec(s)"
        )
    except Exception as exc:  # noqa: BLE001 -- report every sanity failure
        metadata_sanity_failures.append((pip_name, repr(exc)))
        print(f"FAIL {pip_name:<16} (metadata sanity) -> {exc!r}")

# --- Validate ---
# Every import target and metadata-only distribution must pass. Report complete
# failure lists before asserting so one broken distribution does not mask others.
if failures:
    print(f"--- {len(failures)} package(s) failed to import ---")
    for pip_name, import_name, err in failures:
        print(f"  - {pip_name} (import {import_name}): {err}")

if metadata_failures:
    print(
        f"--- {len(metadata_failures)} metadata-only distribution(s) failed ---"
    )
    for pip_name, err in metadata_failures:
        print(f"  - {pip_name} (metadata only): {err}")

if metadata_sanity_failures:
    print(
        f"--- {len(metadata_sanity_failures)} distribution(s) failed metadata sanity ---"
    )
    for pip_name, err in metadata_sanity_failures:
        print(f"  - {pip_name} (metadata sanity): {err}")

assert not failures, f"{len(failures)} pinned package(s) failed to import"
assert not metadata_failures, (
    f"{len(metadata_failures)} metadata-only distribution(s) failed"
)
assert not metadata_sanity_failures, (
    f"{len(metadata_sanity_failures)} distribution(s) failed the "
    "declared-dependency metadata sanity check"
)

# --- Summary ---
print(f"All {len(packages)} import targets imported successfully.")
print(
    f"All {len(metadata_only_distributions)} metadata-only distributions "
    "were present at their exact pinned versions."
)
print(
    f"All {explicit_distribution_total} pinned distributions passed the "
    f"declared-dependency metadata sanity check "
    f"({len(dependency_free_allowlist)} verified dependency-free)."
)
print(
    f"PASS: {len(packages)} import targets + "
    f"{len(metadata_only_distributions)} metadata-only distributions = "
    f"{explicit_distribution_total} explicit pinned distributions verified."
)
sys.exit(0)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-24 20:48:34
# Command: python3 /daaf/scripts/smoke_tests/smoke_imports_c.py
# Duration: 14s
# Exit code: 0
#
# --- STDOUT ---
# --- Python package smoke: 50 import targets + 2 metadata-only distributions = 52 explicit pinned distributions ---
# OK   numpy            (import numpy) version 2.4.2
# OK   pandas           (import pandas) version 3.0.0
# OK   polars           (import polars) version 1.39.3
# OK   scipy            (import scipy) version 1.17.0
# OK   openpyxl         (import openpyxl) version 3.1.5
# OK   fastexcel        (import fastexcel) version 0.19.0
# OK   xlrd             (import xlrd) version 2.0.2
# OK   requests         (import requests) version 2.32.5
# OK   pyarrow          (import pyarrow) version 23.0.0
# OK   urllib3          (import urllib3) version 2.6.3
# OK   pre-commit       (import pre_commit) version 4.5.1
# OK   scikit-learn     (import sklearn) version 1.8.0
# OK   umap-learn       (import umap) version 0.5.11
# OK   pyyaml           (import yaml) version 6.0.3
# OK   statsmodels      (import statsmodels) version 0.14.6
# OK   pyfixest         (import pyfixest) version 0.60.0
# OK   tabulate         (import tabulate) version 0.10.0
# OK   great-tables     (import great_tables) version 0.21.0
# OK   wildboottest     (import wildboottest) version 0.3.2
# OK   linearmodels     (import linearmodels) version 7.0
# OK   rdrobust         (import rdrobust) version 1.3.0
# OK   marginaleffects  (import marginaleffects) version 0.5.0
# OK   arch             (import arch) version 8.0.0
# OK   pydynpd          (import pydynpd) version 0.2.1
# OK   svy              (import svy) version 0.19.0
# OK   geopandas        (import geopandas) version 1.1.3
# OK   rasterio         (import rasterio) version 1.5.0
# OK   xarray           (import xarray) version 2026.2.0
# OK   rioxarray        (import rioxarray) version 0.22.0
# OK   contextily       (import contextily) version 1.7.0
# OK   folium           (import folium) version 0.20.0
# OK   libpysal         (import libpysal) version 4.14.1
# OK   esda             (import esda) version 2.9.0
# OK   spreg            (import spreg) version 1.9.0
# OK   mapclassify      (import mapclassify) version 2.10.0
# OK   rasterstats      (import rasterstats) version 0.20.0
# OK   geopy            (import geopy) version 2.4.1
# OK   osmnx            (import osmnx) version 2.1.0
# OK   matplotlib       (import matplotlib) version 3.10.8
# OK   seaborn          (import seaborn) version 0.13.2
# OK   plotnine         (import plotnine) version 0.15.3
# OK   plotly           (import plotly) version 6.5.2
# OK   marimo           (import marimo) version 0.19.11
# OK   shap             (import shap) version 0.51.0
# OK   fairlearn        (import fairlearn) version 0.12.0
# OK   lightgbm         (import lightgbm) version 4.6.0
# OK   igraph           (import igraph) version 1.0.0
# OK   faker            (import faker) version 40.31.0
# OK   httpx            (import httpx) version 0.28.1 [pinned=0.28.1]
# OK   uvicorn          (import uvicorn) version 0.51.0 [pinned=0.51.0]
# OK   svy-rs           (metadata only) version 0.10.0 [pinned=0.10.0]
# OK   svy-io           (metadata only) version 0.1.1 [pinned=0.1.1]
# OK   numpy            (metadata sanity) allowlisted dependency-free
# OK   pandas           (metadata sanity) 84 declared dependency spec(s)
# OK   polars           (metadata sanity) 31 declared dependency spec(s)
# OK   scipy            (metadata sanity) 38 declared dependency spec(s)
# OK   openpyxl         (metadata sanity) 1 declared dependency spec(s)
# OK   fastexcel        (metadata sanity) 5 declared dependency spec(s)
# OK   xlrd             (metadata sanity) 5 declared dependency spec(s)
# OK   requests         (metadata sanity) 6 declared dependency spec(s)
# OK   pyarrow          (metadata sanity) allowlisted dependency-free
# OK   urllib3          (metadata sanity) 5 declared dependency spec(s)
# OK   pre-commit       (metadata sanity) 5 declared dependency spec(s)
# OK   scikit-learn     (metadata sanity) 53 declared dependency spec(s)
# OK   umap-learn       (metadata sanity) 18 declared dependency spec(s)
# OK   pyyaml           (metadata sanity) allowlisted dependency-free
# OK   statsmodels      (metadata sanity) 28 declared dependency spec(s)
# OK   pyfixest         (metadata sanity) 17 declared dependency spec(s)
# OK   tabulate         (metadata sanity) 1 declared dependency spec(s)
# OK   great-tables     (metadata sanity) 30 declared dependency spec(s)
# OK   wildboottest     (metadata sanity) 5 declared dependency spec(s)
# OK   linearmodels     (metadata sanity) 67 declared dependency spec(s)
# OK   rdrobust         (metadata sanity) 6 declared dependency spec(s)
# OK   marginaleffects  (metadata sanity) 22 declared dependency spec(s)
# OK   arch             (metadata sanity) 59 declared dependency spec(s)
# OK   pydynpd          (metadata sanity) 4 declared dependency spec(s)
# OK   svy              (metadata sanity) 11 declared dependency spec(s)
# OK   geopandas        (metadata sanity) 23 declared dependency spec(s)
# OK   rasterio         (metadata sanity) 26 declared dependency spec(s)
# OK   xarray           (metadata sanity) 41 declared dependency spec(s)
# OK   rioxarray        (metadata sanity) 7 declared dependency spec(s)
# OK   contextily       (metadata sanity) 8 declared dependency spec(s)
# OK   folium           (metadata sanity) 6 declared dependency spec(s)
# OK   libpysal         (metadata sanity) 36 declared dependency spec(s)
# OK   esda             (metadata sanity) 27 declared dependency spec(s)
# OK   spreg            (metadata sanity) 20 declared dependency spec(s)
# OK   mapclassify      (metadata sanity) 33 declared dependency spec(s)
# OK   rasterstats      (metadata sanity) 18 declared dependency spec(s)
# OK   geopy            (metadata sanity) 24 declared dependency spec(s)
# OK   osmnx            (metadata sanity) 13 declared dependency spec(s)
# OK   matplotlib       (metadata sanity) 13 declared dependency spec(s)
# OK   seaborn          (metadata sanity) 22 declared dependency spec(s)
# OK   plotnine         (metadata sanity) 33 declared dependency spec(s)
# OK   plotly           (metadata sanity) 34 declared dependency spec(s)
# OK   marimo           (metadata sanity) 33 declared dependency spec(s)
# OK   shap             (metadata sanity) 63 declared dependency spec(s)
# OK   fairlearn        (metadata sanity) 4 declared dependency spec(s)
# OK   lightgbm         (metadata sanity) 8 declared dependency spec(s)
# OK   igraph           (metadata sanity) 27 declared dependency spec(s)
# OK   faker            (metadata sanity) 2 declared dependency spec(s)
# OK   httpx            (metadata sanity) 12 declared dependency spec(s)
# OK   uvicorn          (metadata sanity) 9 declared dependency spec(s)
# OK   svy-rs           (metadata sanity) 1 declared dependency spec(s)
# OK   svy-io           (metadata sanity) 1 declared dependency spec(s)
# All 50 import targets imported successfully.
# All 2 metadata-only distributions were present at their exact pinned versions.
# All 52 pinned distributions passed the declared-dependency metadata sanity check (3 verified dependency-free).
# PASS: 50 import targets + 2 metadata-only distributions = 52 explicit pinned distributions verified.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
