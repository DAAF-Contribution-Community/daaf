#!/usr/bin/env python3
"""
Build the marimo notebook by reading all 34 final-version scripts and assembling
them into the Four-Cell Pattern (header, commented code, log accordion, data load).

This is a build script, not part of the analysis pipeline.
"""

import re
import textwrap
from pathlib import Path

PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
NOTEBOOK_PATH = PROJECT_DIR / "2026-02-15 College Graduation Rate Selectivity Analysis.py"

# Define all 34 final-version scripts in order, with metadata
SCRIPTS = [
    # Stage 5: Fetch (8 scripts)
    {"stage": 5, "step": "1.1", "label": "Fetch IPEDS Directory",
     "script": "stage5_fetch/01_fetch-directory_a.py",
     "output_data": "data/raw/2026-02-15_ipeds_directory.parquet",
     "cp": "CP1 PASSED", "revisions": [("01_fetch-directory.py", "Failed", "open_admissions/enrollment_undergrad not in directory")]},
    {"stage": 5, "step": "1.2", "label": "Fetch IPEDS Graduation Rates",
     "script": "stage5_fetch/02_fetch-grad-rates_b.py",
     "output_data": "data/raw/2026-02-15_ipeds_grad_rates.parquet",
     "cp": "CP1 PASSED", "revisions": [("02_fetch-grad-rates.py", "Failed", "httpx not installed"), ("02_fetch-grad-rates_a.py", "Failed", "cohort_year missing from output")]},
    {"stage": 5, "step": "1.3", "label": "Fetch IPEDS Admissions",
     "script": "stage5_fetch/03_fetch-admissions.py",
     "output_data": "data/raw/2026-02-15_ipeds_admissions.parquet",
     "cp": "CP1 PASSED", "revisions": []},
    {"stage": 5, "step": "1.4", "label": "Fetch FSA Grants (Pell)",
     "script": "stage5_fetch/04_fetch-fsa-grants_d.py",
     "output_data": "data/raw/2026-02-15_fsa_grants.parquet",
     "cp": "CP1 PASSED", "revisions": [("04_fetch-fsa-grants.py", "Failed", "assumed flat column names"), ("04_fetch-fsa-grants_a.py", "Failed", "wrong grant_type rationale"), ("04_fetch-fsa-grants_b.py", "Failed", "grant_type=1 has 100% null data"), ("04_fetch-fsa-grants_c.py", "Investigation", "comprehensive grant_type analysis")]},
    {"stage": 5, "step": "1.5", "label": "Fetch IPEDS Enrollment by Race",
     "script": "stage5_fetch/05_fetch-enrollment-race.py",
     "output_data": "data/raw/2026-02-15_ipeds_enrollment_race.parquet",
     "cp": "CP1 PASSED", "revisions": []},
    {"stage": 5, "step": "2.1", "label": "Fetch IPEDS Student-Faculty Ratio",
     "script": "stage5_fetch/06_fetch-sfr.py",
     "output_data": "data/raw/2026-02-15_ipeds_sfr.parquet",
     "cp": "CP1 PASSED (with WARNINGS)", "revisions": []},
    {"stage": 5, "step": "2.2", "label": "Fetch IPEDS Retention Rates",
     "script": "stage5_fetch/07_fetch-retention.py",
     "output_data": "data/raw/2026-02-15_ipeds_retention.parquet",
     "cp": "CP1 PASSED (with WARNINGS)", "revisions": []},
    {"stage": 5, "step": "2.3", "label": "Fetch Scorecard Earnings",
     "script": "stage5_fetch/08_fetch-scorecard.py",
     "output_data": "data/raw/2026-02-15_scorecard_earnings.parquet",
     "cp": "CP1 PASSED (with WARNINGS)", "revisions": []},
    # Stage 6: Clean (8 scripts)
    {"stage": 6, "step": "3.1", "label": "Clean IPEDS Directory",
     "script": "stage6_clean/01_clean-directory.py",
     "output_data": "data/processed/2026-02-15_directory_clean.parquet",
     "cp": "CP2 PASSED", "revisions": []},
    {"stage": 6, "step": "3.2", "label": "Clean IPEDS Graduation Rates",
     "script": "stage6_clean/02_clean-grad-rates_a.py",
     "output_data": "data/processed/2026-02-15_grad_rates_clean.parquet",
     "cp": "CP2 PASSED", "revisions": [("02_clean-grad-rates.py", "Failed", "scale assumption wrong; suppression rate miscalculated")]},
    {"stage": 6, "step": "3.3", "label": "Clean IPEDS Admissions",
     "script": "stage6_clean/03_clean-admissions.py",
     "output_data": "data/processed/2026-02-15_admissions_clean.parquet",
     "cp": "CP2 PASSED", "revisions": []},
    {"stage": 6, "step": "3.4", "label": "Clean FSA Grants (Pell)",
     "script": "stage6_clean/04_clean-fsa-grants.py",
     "output_data": "data/processed/2026-02-15_fsa_grants_clean.parquet",
     "cp": "CP2 PASSED", "revisions": []},
    {"stage": 6, "step": "3.5", "label": "Clean IPEDS Enrollment by Race",
     "script": "stage6_clean/05_clean-enrollment-race_a.py",
     "output_data": "data/processed/2026-02-15_enrollment_race_clean.parquet",
     "cp": "CP2 PASSED", "revisions": [("05_clean-enrollment-race.py", "Failed", "multiple rows per unitid per race not handled")]},
    {"stage": 6, "step": "4.1", "label": "Clean IPEDS Student-Faculty Ratio",
     "script": "stage6_clean/06_clean-sfr.py",
     "output_data": "data/processed/2026-02-15_sfr_clean.parquet",
     "cp": "CP2 PASSED", "revisions": []},
    {"stage": 6, "step": "4.2", "label": "Clean IPEDS Retention Rates",
     "script": "stage6_clean/07_clean-retention.py",
     "output_data": "data/processed/2026-02-15_retention_clean.parquet",
     "cp": "CP2 PASSED", "revisions": []},
    {"stage": 6, "step": "4.3", "label": "Clean Scorecard Earnings",
     "script": "stage6_clean/08_clean-scorecard.py",
     "output_data": "data/processed/2026-02-15_scorecard_clean.parquet",
     "cp": "CP2 PASSED", "revisions": []},
    # Stage 7: Transform (5 scripts)
    {"stage": 7, "step": "5.1", "label": "Join Core (Directory + Grad Rates + Admissions)",
     "script": "stage7_transform/01_join-core_a.py",
     "output_data": "data/processed/2026-02-15_core_joined.parquet",
     "cp": "CP3 PASSED", "revisions": [("01_join-core.py", "Failed", "join issue")]},
    {"stage": 7, "step": "5.2", "label": "Join Demographics (+ Pell + URM)",
     "script": "stage7_transform/02_join-demographics.py",
     "output_data": "data/processed/2026-02-15_core_demographics.parquet",
     "cp": "CP3 PASSED", "revisions": []},
    {"stage": 7, "step": "6.1", "label": "Join Resources (+ SFR + Retention)",
     "script": "stage7_transform/03_join-resources.py",
     "output_data": "data/processed/2026-02-15_pre_analysis.parquet",
     "cp": "CP3 PASSED", "revisions": []},
    {"stage": 7, "step": "6.2", "label": "Create Selectivity Bands",
     "script": "stage7_transform/04_create-bands.py",
     "output_data": "data/processed/2026-02-15_analysis.parquet",
     "cp": "CP3 PASSED", "revisions": []},
    {"stage": 7, "step": "10.1", "label": "Join Scorecard Earnings",
     "script": "stage7_transform/05_join-scorecard.py",
     "output_data": "data/processed/2026-02-15_analysis_with_earnings.parquet",
     "cp": "CP3 PASSED", "revisions": []},
    # Stage 8.1: Analysis (7 scripts)
    {"stage": 8, "step": "7.1", "label": "Descriptive Statistics by Selectivity",
     "script": "stage8_analysis/01_descriptive-by-selectivity.py",
     "output_data": "output/analysis/2026-02-15_descriptive_by_selectivity.parquet",
     "cp": "QA4a", "revisions": [], "type": "analysis"},
    {"stage": 8, "step": "7.2", "label": "Crosstab: Selectivity x Pell",
     "script": "stage8_analysis/01_crosstab-selectivity-pell.py",
     "output_data": "output/analysis/2026-02-15_crosstab_selectivity_pell.parquet",
     "cp": "QA4a", "revisions": [], "type": "analysis"},
    {"stage": 8, "step": "7.3", "label": "Crosstab: Selectivity x URM",
     "script": "stage8_analysis/01_crosstab-selectivity-urm.py",
     "output_data": "output/analysis/2026-02-15_crosstab_selectivity_urm.parquet",
     "cp": "QA4a", "revisions": [], "type": "analysis"},
    {"stage": 8, "step": "7.4", "label": "Correlation Matrix",
     "script": "stage8_analysis/03_correlation-matrix.py",
     "output_data": "output/analysis/2026-02-15_correlation_matrix.parquet",
     "cp": "QA4a", "revisions": [], "type": "analysis"},
    {"stage": 8, "step": "7.5", "label": "Outperformer Analysis",
     "script": "stage8_analysis/03_outperformers.py",
     "output_data": "output/analysis/2026-02-15_outperformers.parquet",
     "cp": "QA4a", "revisions": [], "type": "analysis"},
    {"stage": 8, "step": "8.1", "label": "Regression Models",
     "script": "stage8_analysis/06_regression-models.py",
     "output_data": "output/analysis/2026-02-15_regression_results.parquet",
     "cp": "QA4a", "revisions": [], "type": "analysis"},
    {"stage": 8, "step": "8.2", "label": "Sector Comparison",
     "script": "stage8_analysis/07_sector-comparison.py",
     "output_data": "output/analysis/2026-02-15_sector_comparison.parquet",
     "cp": "QA4a", "revisions": [], "type": "analysis"},
    # Stage 8.2: Visualization (6 scripts)
    {"stage": 8, "step": "9.1", "label": "Scatter: Graduation Rate vs Admission Rate",
     "script": "stage8_analysis/08_viz-scatter-grad-admit.py",
     "output_figure": "output/figures/2026-02-15_grad_rate_vs_admission_rate.png",
     "cp": "QA4b", "revisions": [], "type": "viz"},
    {"stage": 8, "step": "9.2", "label": "Boxplot: Graduation Rate by Selectivity Band",
     "script": "stage8_analysis/09_viz-boxplot-selectivity_a.py",
     "output_figure": "output/figures/2026-02-15_boxplot_grad_rate_by_selectivity.png",
     "cp": "QA4b", "revisions": [("09_viz-boxplot-selectivity.py", "Failed", "QA revision")], "type": "viz"},
    {"stage": 8, "step": "9.3", "label": "Heatmap: Selectivity x Pell Band",
     "script": "stage8_analysis/10_viz-heatmap-selectivity-pell_a.py",
     "output_figure": "output/figures/2026-02-15_heatmap_selectivity_pell.png",
     "cp": "QA4b", "revisions": [("10_viz-heatmap-selectivity-pell.py", "Failed", "QA revision")], "type": "viz"},
    {"stage": 8, "step": "9.4", "label": "Heatmap: Correlation Matrix",
     "script": "stage8_analysis/11_viz-correlation-heatmap_a.py",
     "output_figure": "output/figures/2026-02-15_correlation_heatmap.png",
     "cp": "QA4b", "revisions": [("11_viz-correlation-heatmap.py", "Failed", "QA revision")], "type": "viz"},
    {"stage": 8, "step": "9.5", "label": "Bar Chart: Sector Comparison",
     "script": "stage8_analysis/12_viz-sector-comparison_a.py",
     "output_figure": "output/figures/2026-02-15_sector_comparison.png",
     "cp": "QA4b", "revisions": [("12_viz-sector-comparison.py", "Failed", "QA revision")], "type": "viz"},
    {"stage": 8, "step": "10.2", "label": "Scatter: Actual vs Predicted Graduation Rate",
     "script": "stage8_analysis/13_viz-residual-scatter.py",
     "output_figure": "output/figures/2026-02-15_actual_vs_predicted.png",
     "cp": "QA4b", "revisions": [], "type": "viz"},
]

STAGE_NAMES = {
    5: "Data Fetch",
    6: "Data Cleaning",
    7: "EDA & Transformation",
    8: "Analysis & Visualization",
}


def extract_code_and_log(script_path: Path) -> tuple[str, str]:
    """Read a script file and split into code portion and execution log."""
    content = script_path.read_text()

    # Find execution log marker
    markers = [
        "# =============================================================================\n# EXECUTION LOG",
        "# EXECUTION LOG",
    ]

    code_part = content
    log_part = "No execution log found"

    for marker in markers:
        if marker in content:
            parts = content.split(marker, 1)
            code_part = parts[0].rstrip()
            raw_log = marker + parts[1]
            # Convert comment markers to plain text
            lines = raw_log.split('\n')
            clean_lines = []
            for line in lines:
                if line.startswith('# '):
                    clean_lines.append(line[2:])
                elif line.startswith('#'):
                    clean_lines.append(line[1:])
                else:
                    clean_lines.append(line)
            log_part = '\n'.join(clean_lines).strip()
            break

    return code_part, log_part


def comment_out_code(code: str, script_rel_path: str) -> str:
    """Comment out every line of code with # prefix."""
    lines = code.strip().split('\n')
    commented = []
    commented.append(f"# SOURCE: scripts/{script_rel_path}")
    commented.append("# " + "=" * 75)
    commented.append("# ARCHIVED SCRIPT CODE (commented out to prevent execution conflicts)")
    commented.append(f"# Full executable script preserved at: scripts/{script_rel_path}")
    commented.append("# " + "=" * 75)
    commented.append("#")
    for line in lines:
        if line.strip():
            commented.append("# " + line)
        else:
            commented.append("#")
    commented.append("#")
    commented.append("pass  # Cell must have executable statement")
    return '\n'.join(commented)


def escape_for_triple_quote(text: str) -> str:
    """Escape text for embedding in triple-quoted strings."""
    # Replace triple backticks with escaped versions to avoid breaking markdown
    text = text.replace("'''", "' ' '")
    return text


def make_cell_id(stage: int, step: str, cell_num: int) -> str:
    """Create a unique cell function name."""
    step_clean = step.replace(".", "_")
    return f"s{stage}_{step_clean}_c{cell_num}"


# Build notebook content
cells = []

# ============================================================
# IMPORTS CELL
# ============================================================
cells.append('''
@app.cell
def _():
    import marimo as mo
    import polars as pl
    from pathlib import Path

    PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
    return PROJECT_DIR, mo, pl, Path
''')

# ============================================================
# NAVIGATION / TOC CELL
# ============================================================
toc_lines = []
toc_lines.append("# College Graduation Rate & Selectivity Analysis — Script Walkthrough")
toc_lines.append("")
toc_lines.append("**Research Question:** Are high college graduation rates a signal of institutional quality, or primarily a reflection of admissions selectivity and student body demographics?")
toc_lines.append("")
toc_lines.append("This notebook displays the executed scripts from `scripts/`. Each section shows:")
toc_lines.append("1. The complete script code (archived, commented out)")
toc_lines.append("2. The execution log (verbatim from script)")
toc_lines.append("3. A data preview (loads the output file)")
toc_lines.append("")
toc_lines.append("## Table of Contents")
toc_lines.append("")

# Group by stage for TOC
current_stage = None
for s in SCRIPTS:
    if s["stage"] != current_stage:
        current_stage = s["stage"]
        toc_lines.append(f"### Stage {current_stage}: {STAGE_NAMES[current_stage]}")
        toc_lines.append("")
        toc_lines.append("| Step | Script | Status |")
        toc_lines.append("|------|--------|--------|")
    script_name = Path(s["script"]).name
    rev_note = f" ({len(s['revisions'])} revisions)" if s["revisions"] else ""
    toc_lines.append(f"| {s['step']} | `{script_name}` | {s['cp']}{rev_note} |")

toc_lines.append("")
toc_lines.append(f"**Total: {len(SCRIPTS)} scripts across 4 stages.**")

toc_text = '\n'.join(toc_lines)

cells.append(f'''
@app.cell
def _(mo):
    mo.md("""{toc_text}""")
    return
''')

# ============================================================
# STAGE SECTIONS
# ============================================================
current_stage = None
current_substage = None  # Track 8.1 vs 8.2

for idx, s in enumerate(SCRIPTS):
    stage = s["stage"]
    step = s["step"]
    label = s["label"]
    script_rel = s["script"]
    script_path = PROJECT_DIR / "scripts" / script_rel
    script_name = Path(script_rel).name
    cp_status = s["cp"]
    revisions = s["revisions"]
    script_type = s.get("type", "data")  # data, analysis, viz

    # Stage section marker
    if stage != current_stage:
        current_stage = stage
        current_substage = None
        cells.append(f'''
@app.cell
def _(mo):
    mo.md("---\\n## Stage {stage}: {STAGE_NAMES[stage]}")
    return
''')

    # Sub-stage markers for Stage 8
    if stage == 8:
        if script_type == "analysis" and current_substage != "analysis":
            current_substage = "analysis"
            cells.append(f'''
@app.cell
def _(mo):
    mo.md("### Stage 8.1: Statistical Analysis")
    return
''')
        elif script_type == "viz" and current_substage != "viz":
            current_substage = "viz"
            cells.append(f'''
@app.cell
def _(mo):
    mo.md("### Stage 8.2: Visualization")
    return
''')

    # ---- CELL 1: Header (Markdown) ----
    header_lines = []
    header_lines.append(f"#### {step}: {label}")
    header_lines.append("")
    header_lines.append(f"**Final Script:** `scripts/{script_rel}`")
    if script_type == "data" or script_type == "analysis":
        output_path = s.get("output_data", "")
        header_lines.append(f"**Output:** `{output_path}`")
    elif script_type == "viz":
        output_path = s.get("output_figure", "")
        header_lines.append(f"**Output:** `{output_path}`")
    header_lines.append(f"**Status:** {cp_status}")

    if revisions:
        header_lines.append("")
        header_lines.append("| Version | Status | Issue |")
        header_lines.append("|---------|--------|-------|")
        for rev_name, rev_status, rev_issue in revisions:
            header_lines.append(f"| `{rev_name}` | {rev_status} | {rev_issue} |")
        header_lines.append(f"| `{script_name}` | **PASSED** | Final version |")
        header_lines.append("")
        stage_dir = str(Path(script_rel).parent)
        header_lines.append(f"Failed versions preserved in `scripts/{stage_dir}/` for audit.")

    header_text = '\n'.join(header_lines)
    cid = make_cell_id(stage, step, 1)

    cells.append(f'''
@app.cell
def _(mo):
    mo.md("""{header_text}""")
    return
''')

    # ---- CELL 2: Script Code Archive (Commented Out) ----
    if script_path.exists():
        code_part, log_part = extract_code_and_log(script_path)
        commented_code = comment_out_code(code_part, script_rel)
    else:
        commented_code = f"# ERROR: Script not found at scripts/{script_rel}\npass"
        log_part = "Script file not found — cannot extract execution log."

    # Indent for cell body
    commented_indented = textwrap.indent(commented_code, "    ")

    cells.append(f'''
@app.cell
def _():
{commented_indented}
''')

    # ---- CELL 3: Execution Log (Accordion) ----
    log_escaped = escape_for_triple_quote(log_part)
    # Truncate very long logs to keep notebook manageable
    log_lines = log_escaped.split('\n')
    if len(log_lines) > 200:
        log_escaped = '\n'.join(log_lines[:200]) + f"\n\n... (truncated, {len(log_lines) - 200} more lines in script file)"

    cells.append(f'''
@app.cell
def _(mo):
    mo.accordion({{"Execution Log ({script_name})": mo.md("""```
{log_escaped}
```""")}})
    return
''')

    # ---- CELL 4: Data Inspection ----
    var_suffix = f"s{stage}_{step.replace('.', '_')}"

    if script_type == "viz":
        fig_path = s.get("output_figure", "")
        cells.append(f'''
@app.cell
def _(mo, PROJECT_DIR):
    mo.image(src=str(PROJECT_DIR / "{fig_path}"))
''')
    elif script_type == "analysis":
        data_path = s.get("output_data", "")
        cells.append(f'''
@app.cell
def _(pl, mo, PROJECT_DIR):
    df_{var_suffix} = pl.read_parquet(PROJECT_DIR / "{data_path}")
    mo.ui.table(df_{var_suffix}.head(100))
''')
    else:
        data_path = s.get("output_data", "")
        cells.append(f'''
@app.cell
def _(pl, mo, PROJECT_DIR):
    df_{var_suffix} = pl.read_parquet(PROJECT_DIR / "{data_path}")
    mo.ui.table(df_{var_suffix}.head(100))
''')


# ============================================================
# SUMMARY CELL
# ============================================================
# Count scripts per stage
stage_counts = {}
for s in SCRIPTS:
    stage_counts[s["stage"]] = stage_counts.get(s["stage"], 0) + 1

# Count scripts with revisions
revised_count = sum(1 for s in SCRIPTS if s["revisions"])

summary_lines = []
summary_lines.append("---")
summary_lines.append("## Summary")
summary_lines.append("")
summary_lines.append("| Stage | Scripts | Status |")
summary_lines.append("|-------|---------|--------|")
for st, name in STAGE_NAMES.items():
    summary_lines.append(f"| Stage {st} ({name}) | {stage_counts.get(st, 0)} | All passed |")
summary_lines.append("")
summary_lines.append(f"**Total Scripts:** {len(SCRIPTS)}")
summary_lines.append(f"**Scripts with Revisions:** {revised_count}")
summary_lines.append("")
summary_lines.append("**Output Files:**")
summary_lines.append("- Final analysis data: `data/processed/2026-02-15_analysis.parquet`")
summary_lines.append("- Analysis with earnings: `data/processed/2026-02-15_analysis_with_earnings.parquet`")
summary_lines.append("- Statistical results: `output/analysis/`")
summary_lines.append("- Figures: `output/figures/`")
summary_lines.append("- Report: `2026-02-15 College Graduation Rate Selectivity Analysis Report.md`")
summary_lines.append("")
summary_lines.append("**All scripts preserved in:** `scripts/`")

summary_text = '\n'.join(summary_lines)

cells.append(f'''
@app.cell
def _(mo):
    mo.md("""{summary_text}""")
    return
''')


# ============================================================
# ASSEMBLE FINAL NOTEBOOK
# ============================================================

header = '''#!/usr/bin/env python3
"""
College Graduation Rate & Selectivity Analysis — Script Walkthrough

Research Question: Are high college graduation rates a signal of institutional
quality, or primarily a reflection of admissions selectivity and student body
demographics?

This notebook DISPLAYS the executed scripts from the scripts/ directory.
It does NOT contain new analysis code. Each script's code is archived
(commented out) with its execution log in a collapsed accordion.

Generated by notebook-assembler agent.
"""

import marimo

__generated_with = "0.10.19"
app = marimo.App(width="medium")
'''

footer = '''

if __name__ == "__main__":
    app.run()
'''

notebook_content = header + '\n'.join(cells) + footer

NOTEBOOK_PATH.write_text(notebook_content)
print(f"Notebook written to: {NOTEBOOK_PATH}")
print(f"Size: {NOTEBOOK_PATH.stat().st_size:,} bytes")
print(f"Total cells: {len(cells)}")
