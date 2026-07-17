#!/usr/bin/env python3
"""Build deterministic Parquet fixtures for compare_reproduction_artifacts.bats."""

import argparse
from datetime import date, datetime
from pathlib import Path

import polars as pl

parser = argparse.ArgumentParser()
parser.add_argument("output_dir")
args = parser.parse_args()

output_dir = Path(args.output_dir)
output_dir.mkdir(parents=True, exist_ok=True)

base = pl.DataFrame(
    {
        "id": pl.Series([1, 2, 3], dtype=pl.Int64),
        "label": pl.Series(["alpha", "beta", None], dtype=pl.String),
        "enabled": pl.Series([True, False, True], dtype=pl.Boolean),
        "day": pl.Series(
            [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)],
            dtype=pl.Date,
        ),
        "moment": pl.Series(
            [
                datetime(2025, 1, 1, 10, 0),
                datetime(2025, 1, 2, 11, 0),
                datetime(2025, 1, 3, 12, 0),
            ],
            dtype=pl.Datetime("us"),
        ),
        "score": pl.Series([1.0, 2.0, 3.0], dtype=pl.Float64),
        "all_missing": pl.Series([None, None, None], dtype=pl.Null),
    }
)
base.write_parquet(output_dir / "base.parquet")
base.clone().write_parquet(output_dir / "base_copy.parquet")
base.reverse().write_parquet(output_dir / "base_reordered.parquet")

pl.DataFrame({"score": pl.Series([1.0], dtype=pl.Float64)}).write_parquet(
    output_dir / "float_original.parquet"
)
pl.DataFrame({"score": pl.Series([1.0000009], dtype=pl.Float64)}).write_parquet(
    output_dir / "float_within.parquet"
)
pl.DataFrame({"score": pl.Series([1.0000011], dtype=pl.Float64)}).write_parquet(
    output_dir / "float_outside.parquet"
)
pl.DataFrame(
    {"score": pl.Series([1.0, 1.0000015], dtype=pl.Float64)}
).write_parquet(output_dir / "float_ambiguous_original.parquet")
pl.DataFrame(
    {"score": pl.Series([1.00000075, 1.0], dtype=pl.Float64)}
).write_parquet(output_dir / "float_ambiguous_reproduced.parquet")

pl.DataFrame({"id": pl.Series([1, 2], dtype=pl.Int64)}).write_parquet(
    output_dir / "schema_original.parquet"
)
pl.DataFrame({"id": pl.Series([1, 2], dtype=pl.Int32)}).write_parquet(
    output_dir / "schema_different.parquet"
)
pl.DataFrame(
    {
        "first": pl.Series([1, 2], dtype=pl.Int64),
        "second": pl.Series(["a", "b"], dtype=pl.String),
    }
).write_parquet(output_dir / "schema_order_original.parquet")
pl.DataFrame(
    {
        "second": pl.Series(["a", "b"], dtype=pl.String),
        "first": pl.Series([1, 2], dtype=pl.Int64),
    }
).write_parquet(output_dir / "schema_order_swapped.parquet")

pl.DataFrame(
    {
        "id": pl.Series([1, 2], dtype=pl.Int64),
        "label": pl.Series(["a", None], dtype=pl.String),
    }
).write_parquet(output_dir / "null_original.parquet")
pl.DataFrame(
    {
        "id": pl.Series([1, 2], dtype=pl.Int64),
        "label": pl.Series(["a", "b"], dtype=pl.String),
    }
).write_parquet(output_dir / "null_different.parquet")

pl.DataFrame(
    {
        "id": pl.Series([1, 2], dtype=pl.Int64),
        "label": pl.Series(["a", "b"], dtype=pl.String),
    }
).write_parquet(output_dir / "value_original.parquet")
pl.DataFrame(
    {
        "id": pl.Series([1, 2], dtype=pl.Int64),
        "label": pl.Series(["a", "changed"], dtype=pl.String),
    }
).write_parquet(output_dir / "value_different.parquet")

pl.DataFrame(
    {
        "id": pl.Series([1, 1, 2], dtype=pl.Int64),
        "score": pl.Series([10.0, 10.0, 20.0], dtype=pl.Float64),
    }
).write_parquet(output_dir / "duplicates_original.parquet")
pl.DataFrame(
    {
        "id": pl.Series([2, 1, 1], dtype=pl.Int64),
        "score": pl.Series([20.0, 10.0, 10.0], dtype=pl.Float64),
    }
).write_parquet(output_dir / "duplicates_reordered.parquet")
pl.DataFrame(
    {
        "id": pl.Series([1, 2, 2], dtype=pl.Int64),
        "score": pl.Series([10.0, 20.0, 20.0], dtype=pl.Float64),
    }
).write_parquet(output_dir / "duplicates_different.parquet")

pl.DataFrame(
    {
        "id": pl.Series(([1] * 20) + ([2] * 20), dtype=pl.Int64),
        "score": pl.Series(([10.0] * 20) + ([20.0] * 20), dtype=pl.Float64),
    }
).write_parquet(output_dir / "cardinality_overflow_original.parquet")
pl.DataFrame(
    {
        "id": pl.Series(([1] * 19) + ([2] * 21), dtype=pl.Int64),
        "score": pl.Series(([10.0] * 19) + ([20.0] * 21), dtype=pl.Float64),
    }
).write_parquet(output_dir / "cardinality_overflow_reproduced.parquet")

pl.DataFrame(
    {
        "id": pl.Series([1, 2], dtype=pl.Int64),
        "items": pl.Series([[1, 2], [3]], dtype=pl.List(pl.Int64)),
    }
).write_parquet(output_dir / "nested_original.parquet")
pl.DataFrame(
    {
        "id": pl.Series([1, 2], dtype=pl.Int64),
        "items": pl.Series([[1, 2], [3]], dtype=pl.List(pl.Int64)),
    }
).write_parquet(output_dir / "nested_reproduced.parquet")

pl.DataFrame(
    {"score": pl.Series([1.0, float("nan")], dtype=pl.Float64)}
).write_parquet(output_dir / "nan_original.parquet")
pl.DataFrame(
    {"score": pl.Series([1.0, float("nan")], dtype=pl.Float64)}
).write_parquet(output_dir / "nan_reproduced.parquet")
