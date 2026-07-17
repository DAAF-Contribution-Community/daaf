# scripts/smoke_tests/smoke_geo.py
# Functional smoke test for the Python geospatial stack: geopandas, rasterio,
# rasterstats, pyarrow. Unlike smoke_imports.py (import-only), this exercises
# real GDAL/PROJ/GEOS file I/O and raster ops -- the migration risk surface for
# the Ubuntu Noble base image (GDAL 3.6 -> 3.8, PROJ 9.4 jump).
#
# Sequential inline script (DAAF code style): no functions, section separators,
# print + assert for validation. Exits nonzero on any failure.
#
# Scratch files go under a per-script working directory inside smoke_tests
# (NEVER /tmp -- outside the backup/audit boundary per CLAUDE.md). Created on
# entry, removed on exit via a try/finally.

# --- Config ---
import os
import shutil
import sys

import geopandas
import numpy as np
import pyarrow
import pyarrow.parquet as pq
import rasterio
import rasterstats
from rasterio.transform import from_origin
from shapely.geometry import Point, Polygon

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(SMOKE_DIR, "geo_smoke_work")
os.makedirs(WORK_DIR, exist_ok=True)

print("=== geo (Python geospatial) Smoke Test ===\n")

try:
    # --- Test 1: Versions ---
    print("Test 1: Version checks")
    print(f"  geopandas:   {geopandas.__version__}")
    print(f"  rasterio:    {rasterio.__version__}")
    print(f"  rasterstats: {rasterstats.__version__}")
    print(f"  pyarrow:     {pyarrow.__version__}")
    # GDAL version as seen through rasterio -- the migration jump target.
    print(f"  GDAL (via rasterio): {rasterio.__gdal_version__}")
    print("  PASS\n")

    # --- Test 2: geopandas GeoDataFrame + buffer + GeoPackage round-trip ---
    print("Test 2: geopandas construct + buffer + to_file/read_file (GeoPackage)")
    pts = geopandas.GeoDataFrame(
        {"id": [1, 2, 3], "name": ["a", "b", "c"]},
        geometry=[Point(0, 0), Point(1, 1), Point(2, 0)],
        crs="EPSG:4326",
    )
    assert len(pts) == 3
    # Reproject to an equal-area CRS before buffering (buffer in degrees is
    # meaningless); EPSG:5070 is CONUS Albers, matching the R smoke.
    pts_proj = pts.to_crs("EPSG:5070")
    buffered = pts_proj.copy()
    buffered["geometry"] = pts_proj.buffer(50000)  # 50 km
    assert all(buffered.geometry.geom_type == "Polygon")
    assert all(buffered.geometry.is_valid)

    gpkg_path = os.path.join(WORK_DIR, "points.gpkg")
    buffered.to_file(gpkg_path, driver="GPKG")
    assert os.path.exists(gpkg_path)
    gpkg_read = geopandas.read_file(gpkg_path)
    assert len(gpkg_read) == 3
    assert gpkg_read.crs.to_epsg() == 5070
    print(f"  Buffered 3 points to polygons; GeoPackage round-trip: {len(gpkg_read)} rows")
    print("  PASS\n")

    # --- Test 3: rasterio create + write/read GeoTIFF + stats ---
    print("Test 3: rasterio write/read GeoTIFF + read stats")
    # Small 10x10 raster in EPSG:5070 covering the buffered-point extent.
    arr = np.arange(100, dtype="float32").reshape(10, 10)
    minx, miny, _, maxy = buffered.total_bounds
    res = 20000.0  # 20 km cells -> 10x10 covers the buffered points
    transform = from_origin(minx, maxy, res, res)
    tif_path = os.path.join(WORK_DIR, "raster.tif")
    with rasterio.open(
        tif_path, "w", driver="GTiff", height=10, width=10, count=1,
        dtype="float32", crs="EPSG:5070", transform=transform,
    ) as dst:
        dst.write(arr, 1)
    assert os.path.exists(tif_path)
    with rasterio.open(tif_path) as src:
        read_arr = src.read(1)
        assert read_arr.shape == (10, 10)
        assert np.isfinite(read_arr).all()
        rmin, rmax = float(read_arr.min()), float(read_arr.max())
    print(f"  Raster 10x10 written/read; value range [{rmin}, {rmax}]")
    print("  PASS\n")

    # --- Test 4: rasterstats zonal stats of raster against a polygon ---
    print("Test 4: rasterstats zonal_stats (raster x polygon)")
    # A polygon covering roughly the raster center.
    cx = minx + res * 5
    cy = maxy - res * 5
    half = res * 2
    poly = Polygon([
        (cx - half, cy - half), (cx + half, cy - half),
        (cx + half, cy + half), (cx - half, cy + half),
    ])
    zs = rasterstats.zonal_stats(
        [poly], tif_path, stats=["mean", "min", "max", "count"], geojson_out=False
    )
    assert len(zs) == 1
    assert zs[0]["count"] > 0
    assert np.isfinite(zs[0]["mean"])
    print(f"  Zonal stats over polygon: count={zs[0]['count']}, mean={zs[0]['mean']:.2f}")
    print("  PASS\n")

    # --- Test 5: pyarrow parquet round-trip ---
    print("Test 5: pyarrow parquet round-trip")
    tbl = pyarrow.table({
        "i": [1, 2, 3, 4],
        "x": [1.5, 2.25, -3.75, 0.0],
        "s": ["alpha", "beta", "gamma", "delta"],
    })
    pq_path = os.path.join(WORK_DIR, "roundtrip.parquet")
    pq.write_table(tbl, pq_path, compression="snappy")
    assert os.path.exists(pq_path)
    tbl_read = pq.read_table(pq_path)
    assert tbl_read.num_rows == 4
    assert tbl_read.column_names == ["i", "x", "s"]
    assert tbl_read.column("s").to_pylist() == ["alpha", "beta", "gamma", "delta"]
    print(f"  Parquet round-trip: {tbl_read.num_rows} rows, cols {tbl_read.column_names}")
    print("  PASS\n")

    # --- Summary ---
    print("=== All 5 tests PASSED ===")
    print(
        f"Tested: geopandas {geopandas.__version__} / rasterio {rasterio.__version__} "
        f"/ rasterstats {rasterstats.__version__} / pyarrow {pyarrow.__version__}"
    )
finally:
    shutil.rmtree(WORK_DIR, ignore_errors=True)

sys.exit(0)
