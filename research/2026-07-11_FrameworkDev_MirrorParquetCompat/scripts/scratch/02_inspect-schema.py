#!/usr/bin/env python3
"""
Inspect parquet provenance and embedded Arrow schema for the failing (SAIPE) vs
working (MEPS) mirror files.

Goal: establish (a) writer provenance via `created_by`, (b) presence of the
ARROW:schema metadata hint, and (c) which columns the embedded schema declares
as view types (utf8_view / large_utf8_view / binary_view). This confirms or
refutes the "Polars-written StringView" hypothesis.
"""

# --- Config ---
import os
import base64
import pyarrow as pa
import pyarrow.parquet as pq

SCRATCH = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "FAILING (SAIPE districts)": os.path.join(SCRATCH, "saipe_districts_FAILING.parquet"),
    "WORKING (MEPS schools)": os.path.join(SCRATCH, "meps_schools_WORKING.parquet"),
}

print(f"pyarrow version: {pa.__version__}")
print("=" * 70)

# --- Profile ---
for label, path in FILES.items():
    print(f"\n### {label}")
    print(f"file: {os.path.basename(path)}")

    # INTENT: read parquet-level metadata (writer identity lives here, not in the
    # logical schema). created_by is the parquet-writer signature string.
    pf = pq.ParquetFile(path)
    meta = pf.metadata
    print(f"created_by      : {meta.created_by!r}")
    print(f"num_rows        : {meta.num_rows:,}")
    print(f"num_columns     : {meta.num_columns}")
    print(f"num_row_groups  : {meta.num_row_groups}")

    # INTENT: read_schema returns the *parquet* logical schema as pyarrow sees it,
    # plus the key/value metadata dict. The ARROW:schema key (if present) holds a
    # base64-encoded IPC-serialized Arrow schema — the writer's original type hint.
    schema = pq.read_schema(path)
    kv = schema.metadata or {}
    kv_keys = [k.decode() if isinstance(k, bytes) else k for k in kv.keys()]
    print(f"schema metadata keys: {kv_keys}")

    has_arrow_schema = b"ARROW:schema" in kv
    print(f"ARROW:schema present: {has_arrow_schema}")

    # REASONING: pq.read_schema already materializes the embedded ARROW:schema into
    # the returned pyarrow schema types. So the surfaced field types ARE the view
    # types if the writer declared them. Enumerate every field's type and flag views.
    view_cols = []
    for field in schema:
        t = field.type
        tstr = str(t)
        # ASSUMES: view types stringify containing "view" (utf8_view, binary_view,
        # large_string_view etc.); pa.types helpers give a robust check too.
        is_view = "view" in tstr.lower()
        if is_view:
            view_cols.append((field.name, tstr))
    print(f"view-typed columns (from surfaced schema): {len(view_cols)}")
    for name, tstr in view_cols:
        print(f"    - {name}: {tstr}")

    # INTENT: independently decode the raw ARROW:schema IPC blob to cross-check the
    # surfaced types (guards against pyarrow silently downcasting on read). The blob
    # is base64-encoded; deserialize via ipc.read_schema on a Buffer.
    if has_arrow_schema:
        raw = kv[b"ARROW:schema"]
        try:
            decoded = base64.b64decode(raw)
            buf = pa.py_buffer(decoded)
            embedded = pa.ipc.read_schema(buf)
            emb_view = [(f.name, str(f.type)) for f in embedded if "view" in str(f.type).lower()]
            print(f"embedded ARROW:schema view columns: {len(emb_view)}")
            for name, tstr in emb_view:
                print(f"    * {name}: {tstr}")
        except Exception as e:
            # REASONING: newer pyarrow base64-decodes ARROW:schema internally; a raw
            # decode may not be needed. Report rather than fail — surfaced schema above
            # is the authoritative signal.
            print(f"    (raw ARROW:schema decode note: {type(e).__name__}: {e})")

print("\n" + "=" * 70)
print("SUMMARY: compare created_by and view-column counts across the two files above.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:30:12
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/02_inspect-schema.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# pyarrow version: 23.0.0
# ======================================================================
# 
# ### FAILING (SAIPE districts)
# file: saipe_districts_FAILING.parquet
# created_by      : 'Polars'
# num_rows        : 368,967
# num_columns     : 10
# num_row_groups  : 4
# schema metadata keys: []
# ARROW:schema present: False
# view-typed columns (from surfaced schema): 1
#     - district_name: string_view
# 
# ### WORKING (MEPS schools)
# file: meps_schools_WORKING.parquet
# created_by      : 'Polars'
# num_rows        : 1,345,122
# num_columns     : 11
# num_row_groups  : 11
# schema metadata keys: []
# ARROW:schema present: False
# view-typed columns (from surfaced schema): 0
# 
# ======================================================================
# SUMMARY: compare created_by and view-column counts across the two files above.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
