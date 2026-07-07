# scripts/smoke_tests/smoke_imports.py
# Import-smoke test: verifies every pinned Python analysis package from the
# Dockerfile pip install blocks imports cleanly and reports its version.
# Sequential inline script (DAAF code style): no functions, section separators,
# print + assert for validation. Exits nonzero on any import failure.
#
# Package list is derived from the five `uv pip install --system` blocks in
# /daaf/Dockerfile (core data science, econometrics, geospatial, visualization,
# ML interpretation/fairness). When the Dockerfile pins change, update this list
# to match. Entries are (import_name, pip_name) because several import names
# differ from their pip package name (e.g. scikit-learn -> sklearn).

# --- Config ---
import importlib
import sys

# (import_name, pip_name) for every pinned package in the Dockerfile pip blocks.
# pip_name is only used for reporting so a failure names the installable package.
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
]

print(f"--- Python import smoke: {len(packages)} pinned packages ---")

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
        version = getattr(mod, "__version__", "no __version__ attr")
        print(f"OK   {pip_name:<16} (import {import_name}) version {version}")
    except Exception as exc:  # noqa: BLE001 -- report any import-time failure
        failures.append((pip_name, import_name, repr(exc)))
        print(f"FAIL {pip_name:<16} (import {import_name}) -> {exc!r}")

# --- Validate ---
# Every listed package must import. Report the full failure list before asserting
# so the execution log names all broken packages, not just the first.
if failures:
    print(f"--- {len(failures)} package(s) failed to import ---")
    for pip_name, import_name, err in failures:
        print(f"  - {pip_name} (import {import_name}): {err}")

assert not failures, f"{len(failures)} pinned package(s) failed to import"

# --- Summary ---
print(f"All {len(packages)} pinned Python packages imported successfully.")
sys.exit(0)
