"""Regenerates the P3 contract bundle (tests/python/fixtures/lit_corpus/contract_bundle/) for the manuscript side.

Fully synthetic: every word and number is invented (lit_corpus.DEMO_PAPERS). The bundle is a complete review
project built by the real tools: four synthetic paper ingests with v3 evidence cards checked by lit_verify, synthetic
scholar_search rows with records files, and every lit_corpus table, export and manifest. Every parquet table is also
written as canonical JSON (data_json/), so a reader without polars or pyarrow can see the rows.

Fixture-only overrides (never available from the CLI): the paper keys user_f1c70001..4 (a user PDF key is normally
the first 8 hex of the PDF's sha256) and the "fixture-" citekey prefix the manuscript side asked for.

Run file-first (needs rapidfuzz and polars): a captured script calls this file with the destination's parent
removed or empty; it refuses to write into a non-empty bundle directory.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "scripts"))
import lit_corpus as lc  # noqa: E402

DEST = os.path.join(HERE, "contract_bundle")
if os.path.isdir(DEST) and os.listdir(DEST):
    sys.exit(f"refusing: {DEST} is not empty (remove it first)")
os.makedirs(DEST, exist_ok=True)
demo = lc.build_demo(DEST, fixture=True)
bad = [(n, c, o[-300:]) for n, c, o in demo["steps"] if c != 0]
print(f"steps: {len(demo['steps'])}; non-zero: {bad}")
read, _ = lc.parquet_io()
os.makedirs(os.path.join(DEST, "data_json"))
for table in lc.TABLES:
    vs = [n for n in os.listdir(os.path.join(DEST, "data")) if n.startswith(table + "_v") and n.endswith(".parquet")]
    if vs:
        latest = max(vs, key=lambda n: int(n.rsplit("_v", 1)[1].split(".")[0]))
        with open(os.path.join(DEST, "data", latest), "rb") as f:
            rows = read(f.read())
        with open(os.path.join(DEST, "data_json", f"{table}.json"), "x", encoding="utf-8") as f:
            json.dump({"source": f"data/{latest}", "rows": rows}, f, indent=1, sort_keys=True, ensure_ascii=False)
# The tool's fcntl lock file is ephemeral coordination, not part of the bundle (review C-I6).
lock = os.path.join(DEST, "data", ".lit_corpus.lock")
if os.path.exists(lock):
    os.remove(lock)
print("bundle written:", sorted(os.listdir(DEST)))
sys.exit(1 if bad else 0)
