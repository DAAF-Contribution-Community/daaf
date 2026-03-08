#!/usr/bin/env python3
"""
College Graduation Rate & Selectivity — Interactive Explorer

Interactive dashboard for exploring institution-level data from the
College Graduation Rate Selectivity Analysis. Hover over points in
the scatterplot to see institution details. Use lasso/box select to
highlight specific institutions in the data table below.

Data: 2,528 four-year institutions (2020), classified as overperformer,
typical, or underperformer relative to their selectivity band (±1 SD
from band median graduation rate).

Launch: marimo run "2026-02-15_College_Graduation_Rate_Selectivity_Explorer.py"
"""

import marimo

__generated_with = "0.10.19"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import plotly.express as px
    from pathlib import Path
    return Path, mo, pl, px


@app.cell
def _(mo):
    mo.md(
        """
        # College Graduation Rate & Selectivity — Interactive Explorer

        **Hover** over points for institution details.
        **Lasso or box select** points to filter the table below.
        Use the dropdowns to narrow by selectivity, sector, performance, or state.
        """
    )
    return


@app.cell
def _(Path, pl):
    PROJECT_DIR = Path(
        "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis"
    )

    _raw = pl.read_parquet(
        PROJECT_DIR / "output/analysis/2026-02-15_outperformers.parquet"
    )

    df_all = _raw.with_columns(
        # Human-readable sector label
        pl.when(pl.col("inst_control") == 1)
        .then(pl.lit("Public"))
        .when(pl.col("inst_control") == 2)
        .then(pl.lit("Private Nonprofit"))
        .otherwise(pl.lit("Other"))
        .alias("sector"),
        # HBCU flag label
        pl.when(pl.col("hbcu") == 1)
        .then(pl.lit("Yes"))
        .otherwise(pl.lit("No"))
        .alias("hbcu_label"),
        # Percentage columns for display and hover
        (pl.col("admission_rate") * 100).round(1).alias("admission_pct"),
        (pl.col("pell_share") * 100).round(1).alias("pell_pct"),
        (pl.col("urm_share") * 100).round(1).alias("urm_pct"),
        pl.col("grad_rate_150pct").round(1).alias("grad_rate_pct"),
        pl.col("retention_rate").round(1).alias("retention_pct"),
    )
    return PROJECT_DIR, df_all


@app.cell
def _(df_all, mo):
    _bands = sorted(
        df_all.select("selectivity_band").unique().to_series().drop_nulls().to_list()
    )
    _states = sorted(
        df_all.select("state_abbr").unique().to_series().drop_nulls().to_list()
    )

    selectivity_filter = mo.ui.dropdown(
        options=["All"] + _bands, value="All", label="Selectivity"
    )
    sector_filter = mo.ui.dropdown(
        options=["All", "Public", "Private Nonprofit"], value="All", label="Sector"
    )
    perf_filter = mo.ui.dropdown(
        options=["All", "overperformer", "typical", "underperformer"],
        value="All",
        label="Performance",
    )
    state_filter = mo.ui.dropdown(
        options=["All"] + _states, value="All", label="State"
    )
    color_by = mo.ui.dropdown(
        options={
            "Performance Flag": "performance_flag",
            "Sector": "sector",
            "Selectivity Band": "selectivity_band",
        },
        value="Performance Flag",
        label="Color by",
    )
    search_box = mo.ui.text(placeholder="Search institution name...", label="Search")

    mo.hstack(
        [selectivity_filter, sector_filter, perf_filter, state_filter],
        justify="start",
        gap=1,
    )
    return (
        color_by,
        perf_filter,
        search_box,
        sector_filter,
        selectivity_filter,
        state_filter,
    )


@app.cell
def _(color_by, mo, search_box):
    mo.hstack([color_by, search_box], justify="start", gap=1)
    return


@app.cell
def _(
    df_all,
    perf_filter,
    pl,
    search_box,
    sector_filter,
    selectivity_filter,
    state_filter,
):
    df_filtered = df_all

    if selectivity_filter.value != "All":
        df_filtered = df_filtered.filter(
            pl.col("selectivity_band") == selectivity_filter.value
        )
    if sector_filter.value != "All":
        df_filtered = df_filtered.filter(pl.col("sector") == sector_filter.value)
    if perf_filter.value != "All":
        df_filtered = df_filtered.filter(
            pl.col("performance_flag") == perf_filter.value
        )
    if state_filter.value != "All":
        df_filtered = df_filtered.filter(pl.col("state_abbr") == state_filter.value)
    if search_box.value:
        df_filtered = df_filtered.filter(
            pl.col("inst_name")
            .str.to_lowercase()
            .str.contains(search_box.value.lower(), literal=True)
        )

    # Scatter plot requires both admission rate and graduation rate
    df_scatter = df_filtered.filter(
        pl.col("admission_rate").is_not_null()
        & pl.col("grad_rate_150pct").is_not_null()
    )
    return df_filtered, df_scatter


@app.cell
def _(df_filtered, df_scatter, mo, pl):
    _n = df_filtered.height
    _np = df_scatter.height
    _no = df_filtered.filter(pl.col("performance_flag") == "overperformer").height
    _nu = df_filtered.filter(pl.col("performance_flag") == "underperformer").height
    _nt = df_filtered.filter(pl.col("performance_flag") == "typical").height

    _gr = df_filtered.select(pl.col("grad_rate_150pct").mean()).item()
    _ar = df_filtered.select((pl.col("admission_rate") * 100).mean()).item()
    _ps = df_filtered.select((pl.col("pell_share") * 100).mean()).item()

    _gr_s = f"{_gr:.1f}%" if _gr is not None else "N/A"
    _ar_s = f"{_ar:.1f}%" if _ar is not None else "N/A"
    _ps_s = f"{_ps:.1f}%" if _ps is not None else "N/A"

    mo.md(
        f"""
    **{_n} institutions** ({_np} in scatter) —
    Overperformers: **{_no}** · Typical: **{_nt}** · Underperformers: **{_nu}** |
    Mean grad rate: **{_gr_s}** · Mean admit rate: **{_ar_s}** · Mean Pell share: **{_ps_s}**
    """
    )
    return


@app.cell
def _(color_by, df_scatter, mo, px):
    _color = color_by.value

    _cmaps = {
        "performance_flag": {
            "overperformer": "#2ca02c",
            "typical": "#aaaaaa",
            "underperformer": "#d62728",
        },
        "sector": {"Public": "#1f77b4", "Private Nonprofit": "#ff7f0e"},
        "selectivity_band": {
            "Highly Selective": "#1b9e77",
            "Selective": "#d95f02",
            "Moderately Selective": "#7570b3",
            "Less Selective/Open": "#e7298a",
        },
    }
    _orders = {
        "performance_flag": {
            "performance_flag": ["overperformer", "typical", "underperformer"]
        },
        "sector": {"sector": ["Public", "Private Nonprofit"]},
        "selectivity_band": {
            "selectivity_band": [
                "Highly Selective",
                "Selective",
                "Moderately Selective",
                "Less Selective/Open",
            ]
        },
    }

    _pdf = df_scatter.to_pandas()

    _fig = px.scatter(
        _pdf,
        x="admission_pct",
        y="grad_rate_pct",
        color=_color,
        color_discrete_map=_cmaps.get(_color, {}),
        category_orders=_orders.get(_color, {}),
        custom_data=["unitid"],
        hover_name="inst_name",
        hover_data={
            "admission_pct": False,
            "grad_rate_pct": False,
            "unitid": False,
            "state_abbr": True,
            "selectivity_band": True,
            "sector": True,
            "performance_flag": True,
            "pell_pct": ":.1f",
            "urm_pct": ":.1f",
            "retention_pct": ":.1f",
            "student_faculty_ratio": True,
            "enrollment_undergrad": True,
            "hbcu_label": True,
        },
        labels={
            "state_abbr": "State",
            "selectivity_band": "Selectivity",
            "performance_flag": "Performance",
            "pell_pct": "Pell Share (%)",
            "urm_pct": "URM Share (%)",
            "retention_pct": "Retention (%)",
            "student_faculty_ratio": "S:F Ratio",
            "enrollment_undergrad": "UG Enrollment",
            "hbcu_label": "HBCU",
            "sector": "Sector",
        },
        opacity=0.6,
    )

    _fig.update_layout(
        title="Graduation Rate vs. Admission Rate (hover for details, lasso to select)",
        xaxis_title="Admission Rate (%)",
        yaxis_title="Graduation Rate (%, 6-year)",
        height=600,
        template="plotly_white",
        legend_title_text=_color.replace("_", " ").title(),
        dragmode="lasso",
    )
    _fig.update_traces(marker=dict(size=8, line=dict(width=0.5, color="white")))

    scatter = mo.ui.plotly(_fig)
    scatter
    return (scatter,)


@app.cell
def _(df_filtered, mo, pl, scatter):
    _sel = scatter.value
    _display = df_filtered
    _title = f"### All Filtered Institutions ({df_filtered.height})"

    # Extract selected unitids from plotly lasso/box selection
    if _sel is not None:
        _ids = []
        try:
            if isinstance(_sel, dict):
                for _p in _sel.get("points", []):
                    if "customdata" in _p and _p["customdata"]:
                        _ids.append(_p["customdata"][0])
            elif isinstance(_sel, list):
                for _p in _sel:
                    if isinstance(_p, dict):
                        if "customdata" in _p and _p["customdata"]:
                            _ids.append(_p["customdata"][0])
        except Exception:
            _ids = []

        if _ids:
            _display = df_filtered.filter(pl.col("unitid").is_in(_ids))
            _title = f"### Selected Institutions ({_display.height})"

    _table = (
        _display.select(
            [
                "inst_name",
                "state_abbr",
                "sector",
                "selectivity_band",
                "performance_flag",
                "grad_rate_pct",
                "admission_pct",
                "pell_pct",
                "urm_pct",
                "retention_pct",
                "student_faculty_ratio",
                "enrollment_undergrad",
                "hbcu_label",
            ]
        )
        .rename(
            {
                "inst_name": "Institution",
                "state_abbr": "State",
                "sector": "Sector",
                "selectivity_band": "Selectivity",
                "performance_flag": "Performance",
                "grad_rate_pct": "Grad Rate %",
                "admission_pct": "Admit Rate %",
                "pell_pct": "Pell %",
                "urm_pct": "URM %",
                "retention_pct": "Retention %",
                "student_faculty_ratio": "S:F Ratio",
                "enrollment_undergrad": "UG Enrollment",
                "hbcu_label": "HBCU",
            }
        )
        .sort("Institution")
    )

    mo.vstack(
        [
            mo.md(_title),
            mo.ui.table(_table, page_size=20, selection=None),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ---
        **Data:** IPEDS Directory, Graduation Rates (2015 cohort), Admissions, Fall Enrollment,
        Student-Faculty Ratio, Retention; FSA Pell Grants — all 2020 analysis year.
        **Performance classification:** ±1 SD from selectivity band median graduation rate.
        **Scope:** 2,528 four-year degree-granting public and private nonprofit institutions.
        Institutions missing admission rate (open-admission) or graduation rate appear in the table but not the scatter.
        """
    )
    return


if __name__ == "__main__":
    app.run()
