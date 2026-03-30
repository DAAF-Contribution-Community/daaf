#!/usr/bin/env python3
"""
Notebook assembler: reads all 30 final scripts and generates the marimo notebook.

This script is a build tool, not an analysis script. It reads script files,
extracts code and execution logs, and writes a marimo .py notebook file.
"""

import re
import textwrap
from pathlib import Path

PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
SCRIPTS_DIR = PROJECT_DIR / "scripts"
OUTPUT_NOTEBOOK = PROJECT_DIR / "2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py"

# --- Script Registry ---
# Each entry: (relative_script_path, output_data_path, checkpoint, is_viz, description, versions)
# versions is a list of all version files (for version history display)

SCRIPTS = [
    # Stage 5: Fetch
    {
        "path": "stage5_fetch/01_fetch-directory.py",
        "output": "data/raw/2026-03-29_ipeds_directory.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.1",
        "title": "Fetch IPEDS Directory",
        "versions": [],
    },
    {
        "path": "stage5_fetch/02_fetch-admissions.py",
        "output": "data/raw/2026-03-29_ipeds_admissions.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.2",
        "title": "Fetch IPEDS Admissions",
        "versions": [],
    },
    {
        "path": "stage5_fetch/03_fetch-grad-rates_a.py",
        "output": "data/raw/2026-03-29_ipeds_grad_rates.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.3",
        "title": "Fetch IPEDS Graduation Rates",
        "versions": ["03_fetch-grad-rates.py", "03_fetch-grad-rates_a.py"],
    },
    {
        "path": "stage5_fetch/04_fetch-fsa-grants_d.py",
        "output": "data/raw/2026-03-29_fsa_grants.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.4",
        "title": "Fetch FSA Grants",
        "versions": ["04_fetch-fsa-grants.py", "04_fetch-fsa-grants_a.py",
                      "04_fetch-fsa-grants_b.py", "04_fetch-fsa-grants_c.py",
                      "04_fetch-fsa-grants_d.py"],
    },
    {
        "path": "stage5_fetch/05_fetch-enrollment-race.py",
        "output": "data/raw/2026-03-29_ipeds_enrollment_race.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.5",
        "title": "Fetch IPEDS Enrollment by Race",
        "versions": [],
    },
    {
        "path": "stage5_fetch/06_fetch-sfr.py",
        "output": "data/raw/2026-03-29_ipeds_sfr.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.6",
        "title": "Fetch IPEDS Student-Faculty Ratio",
        "versions": [],
    },
    {
        "path": "stage5_fetch/07_fetch-retention.py",
        "output": "data/raw/2026-03-29_ipeds_retention.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.7",
        "title": "Fetch IPEDS Retention Rates",
        "versions": [],
    },
    {
        "path": "stage5_fetch/08_fetch-finance.py",
        "output": "data/raw/2026-03-29_ipeds_finance.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.8",
        "title": "Fetch IPEDS Finance",
        "versions": [],
    },
    {
        "path": "stage5_fetch/09_fetch-sfa-grants.py",
        "output": "data/raw/2026-03-29_ipeds_sfa_grants.parquet",
        "cp": "CP1", "is_viz": False, "stage": 5, "step": "5.9",
        "title": "Fetch IPEDS SFA Grants",
        "versions": [],
    },
    # Stage 6: Clean
    {
        "path": "stage6_clean/01_clean-directory.py",
        "output": "data/processed/2026-03-29_directory_clean.parquet",
        "cp": "CP2", "is_viz": False, "stage": 6, "step": "6.1",
        "title": "Clean Directory Data",
        "versions": [],
    },
    {
        "path": "stage6_clean/02_clean-admissions.py",
        "output": "data/processed/2026-03-29_admissions_clean.parquet",
        "cp": "CP2", "is_viz": False, "stage": 6, "step": "6.2",
        "title": "Clean Admissions Data",
        "versions": [],
    },
    {
        "path": "stage6_clean/03_clean-grad-rates_c.py",
        "output": "data/processed/2026-03-29_grad_rates_clean.parquet",
        "cp": "CP2", "is_viz": False, "stage": 6, "step": "6.3",
        "title": "Clean Graduation Rates",
        "versions": ["03_clean-grad-rates.py", "03_clean-grad-rates_a.py",
                      "03_clean-grad-rates_b.py", "03_clean-grad-rates_c.py"],
    },
    {
        "path": "stage6_clean/04_clean-sfa-grants.py",
        "output": "data/processed/2026-03-29_sfa_pell_clean.parquet",
        "cp": "CP2", "is_viz": False, "stage": 6, "step": "6.4",
        "title": "Clean SFA Grants (Pell Share)",
        "versions": [],
    },
    {
        "path": "stage6_clean/05_clean-enrollment-race.py",
        "output": "data/processed/2026-03-29_urm_share_clean.parquet",
        "cp": "CP2", "is_viz": False, "stage": 6, "step": "6.5",
        "title": "Clean Enrollment by Race (URM Share)",
        "versions": [],
    },
    {
        "path": "stage6_clean/06_clean-sfr.py",
        "output": "data/processed/2026-03-29_sfr_clean.parquet",
        "cp": "CP2", "is_viz": False, "stage": 6, "step": "6.6",
        "title": "Clean Student-Faculty Ratio",
        "versions": [],
    },
    {
        "path": "stage6_clean/07_clean-retention.py",
        "output": "data/processed/2026-03-29_retention_clean.parquet",
        "cp": "CP2", "is_viz": False, "stage": 6, "step": "6.7",
        "title": "Clean Retention Rates",
        "versions": [],
    },
    {
        "path": "stage6_clean/08_clean-finance.py",
        "output": "data/processed/2026-03-29_finance_clean.parquet",
        "cp": "CP2", "is_viz": False, "stage": 6, "step": "6.8",
        "title": "Clean Finance Data",
        "versions": [],
    },
    # Stage 7: Transform
    {
        "path": "stage7_transform/01_join-core.py",
        "output": "data/processed/2026-03-29_core.parquet",
        "cp": "CP3", "is_viz": False, "stage": 7, "step": "7.1",
        "title": "Join Core (Directory + Admissions + Grad Rates)",
        "versions": [],
    },
    {
        "path": "stage7_transform/02_join-demographics.py",
        "output": "data/processed/2026-03-29_core_demographics.parquet",
        "cp": "CP3", "is_viz": False, "stage": 7, "step": "7.2",
        "title": "Join Demographics (Pell + URM)",
        "versions": [],
    },
    {
        "path": "stage7_transform/03_join-resources.py",
        "output": "data/processed/2026-03-29_merged.parquet",
        "cp": "CP3", "is_viz": False, "stage": 7, "step": "7.3",
        "title": "Join Resources (SFR + Retention + Finance)",
        "versions": [],
    },
    {
        "path": "stage7_transform/04_create-bands_a.py",
        "output": "data/processed/2026-03-29_analysis.parquet",
        "cp": "CP3", "is_viz": False, "stage": 7, "step": "7.4",
        "title": "Create Selectivity Bands",
        "versions": ["04_create-bands.py", "04_create-bands_a.py"],
    },
    # Stage 8: Analysis
    {
        "path": "stage8_analysis/01_descriptive-by-selectivity.py",
        "output": "output/analysis/2026-03-29_descriptive_by_selectivity.parquet",
        "cp": "CP4", "is_viz": False, "stage": 8, "step": "8.1",
        "title": "Descriptive Statistics by Selectivity Band",
        "versions": [],
    },
    {
        "path": "stage8_analysis/02_crosstab-selectivity-pell_a.py",
        "output": "output/analysis/2026-03-29_crosstab_selectivity_pell.parquet",
        "cp": "CP4", "is_viz": False, "stage": 8, "step": "8.2",
        "title": "Cross-tabulation: Selectivity x Pell Share",
        "versions": ["02_crosstab-selectivity-pell.py", "02_crosstab-selectivity-pell_a.py"],
    },
    {
        "path": "stage8_analysis/03_crosstab-selectivity-urm_a.py",
        "output": "output/analysis/2026-03-29_crosstab_selectivity_urm.parquet",
        "cp": "CP4", "is_viz": False, "stage": 8, "step": "8.3",
        "title": "Cross-tabulation: Selectivity x URM Share",
        "versions": ["03_crosstab-selectivity-urm.py", "03_crosstab-selectivity-urm_a.py"],
    },
    {
        "path": "stage8_analysis/04_correlation-matrix_a.py",
        "output": "output/analysis/2026-03-29_correlation_matrix.parquet",
        "cp": "CP4", "is_viz": False, "stage": 8, "step": "8.4",
        "title": "Correlation Matrix",
        "versions": ["04_correlation-matrix.py", "04_correlation-matrix_a.py"],
    },
    {
        "path": "stage8_analysis/05_outperformers.py",
        "output": "output/analysis/2026-03-29_selectivity_model.parquet",
        "cp": "CP4", "is_viz": False, "stage": 8, "step": "8.5",
        "title": "Outperformer Identification",
        "versions": [],
    },
    {
        "path": "stage8_analysis/06_regression-models.py",
        "output": "output/analysis/2026-03-29_regression_results.parquet",
        "cp": "CP4", "is_viz": False, "stage": 8, "step": "8.6",
        "title": "OLS Regression Models",
        "versions": [],
    },
    {
        "path": "stage8_analysis/07_sector-comparison.py",
        "output": "output/analysis/2026-03-29_sector_comparison.parquet",
        "cp": "CP4", "is_viz": False, "stage": 8, "step": "8.7",
        "title": "Sector Comparison",
        "versions": [],
    },
    # Stage 8: Visualization
    {
        "path": "stage8_analysis/08_viz-scatter-grad-admit.py",
        "output": "output/figures/2026-03-29_grad_rate_vs_admission_rate.png",
        "cp": "CP4", "is_viz": True, "stage": 8, "step": "8.8",
        "title": "Visualization: Graduation Rate vs Admission Rate Scatter",
        "versions": [],
    },
    {
        "path": "stage8_analysis/09_viz-boxplot-selectivity_b.py",
        "output": "output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png",
        "cp": "CP4", "is_viz": True, "stage": 8, "step": "8.9",
        "title": "Visualization: Graduation Rate by Selectivity Band (Boxplot)",
        "versions": ["09_viz-boxplot-selectivity.py", "09_viz-boxplot-selectivity_a.py",
                      "09_viz-boxplot-selectivity_b.py"],
    },
    {
        "path": "stage8_analysis/10_viz-heatmap-selectivity-pell_c.py",
        "output": "output/figures/2026-03-29_heatmap_selectivity_pell.png",
        "cp": "CP4", "is_viz": True, "stage": 8, "step": "8.10",
        "title": "Visualization: Selectivity x Pell Share Heatmap",
        "versions": ["10_viz-heatmap-selectivity-pell.py", "10_viz-heatmap-selectivity-pell_a.py",
                      "10_viz-heatmap-selectivity-pell_b.py", "10_viz-heatmap-selectivity-pell_c.py"],
    },
    {
        "path": "stage8_analysis/11_viz-correlation-heatmap_a.py",
        "output": "output/figures/2026-03-29_correlation_heatmap.png",
        "cp": "CP4", "is_viz": True, "stage": 8, "step": "8.11",
        "title": "Visualization: Correlation Heatmap",
        "versions": ["11_viz-correlation-heatmap.py", "11_viz-correlation-heatmap_a.py"],
    },
    {
        "path": "stage8_analysis/12_viz-sector-comparison_a.py",
        "output": "output/figures/2026-03-29_sector_comparison.png",
        "cp": "CP4", "is_viz": True, "stage": 8, "step": "8.12",
        "title": "Visualization: Sector Comparison",
        "versions": ["12_viz-sector-comparison.py", "12_viz-sector-comparison_a.py"],
    },
    {
        "path": "stage8_analysis/13_viz-residual-scatter.py",
        "output": "output/figures/2026-03-29_actual_vs_predicted.png",
        "cp": "CP4", "is_viz": True, "stage": 8, "step": "8.13",
        "title": "Visualization: Actual vs Predicted (Residual Scatter)",
        "versions": [],
    },
]


def extract_code(script_path: Path) -> str:
    """Extract code from script, before the execution log marker."""
    content = script_path.read_text()

    markers = [
        "# =============================================================================\n# EXECUTION LOG",
        "# =======================================================================\n# EXECUTION LOG",
        "# ===== EXECUTION LOG",
    ]

    for marker in markers:
        if marker in content:
            content = content.split(marker)[0]
            break

    return content.strip()


def extract_execution_log(script_path: Path) -> str:
    """Extract execution log section from script (after the marker)."""
    content = script_path.read_text()

    markers = [
        "# =============================================================================\n# EXECUTION LOG",
        "# =======================================================================\n# EXECUTION LOG",
        "# ===== EXECUTION LOG",
    ]

    for marker in markers:
        if marker in content:
            log_section = marker + content.split(marker, 1)[1]
            # Strip comment prefixes for display
            lines = log_section.split('\n')
            clean_lines = []
            for line in lines:
                if line.startswith('# '):
                    clean_lines.append(line[2:])
                elif line.startswith('#'):
                    clean_lines.append(line[1:])
                else:
                    clean_lines.append(line)
            return '\n'.join(clean_lines).strip()

    return "No execution log found in script file."


def comment_out_code(code: str, source_path: str) -> str:
    """Comment out every line of code with '# ' prefix."""
    lines = code.split('\n')
    commented = []
    commented.append(f"# SOURCE: {source_path}")
    commented.append("# " + "=" * 75)
    commented.append("# ARCHIVED SCRIPT CODE (commented out to prevent execution conflicts)")
    commented.append(f"# Full executable script preserved at: {source_path}")
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
    """Escape text for inclusion in triple-quoted strings.
    Replace sequences of 3+ quotes, and handle backslashes."""
    # Replace triple quotes
    text = text.replace("'''", "' ' '")
    text = text.replace('"""', '" " "')
    return text


def make_version_table(versions: list[str], stage_dir: str, final_name: str) -> str:
    """Create a version history markdown table."""
    if not versions or len(versions) <= 1:
        return ""

    rows = []
    for v in versions:
        if v == final_name:
            rows.append(f"| `{v}` | **PASSED (Final)** |")
        else:
            rows.append(f"| `{v}` | Failed |")

    table = "\n**Version History:**\n\n| Version | Status |\n|---------|--------|\n"
    table += "\n".join(rows)
    table += f"\n\nFailed versions preserved in `scripts/{stage_dir}/` for audit."
    return table


def indent(text: str, spaces: int = 4) -> str:
    """Indent every line of text."""
    prefix = " " * spaces
    return '\n'.join(prefix + line if line.strip() else line for line in text.split('\n'))


# --- Build Notebook ---

cells = []

# Cell: Imports
cells.append('''@app.cell
def _():
    import marimo as mo
    import polars as pl
    from pathlib import Path
    return Path, mo, pl''')

# Cell: PROJECT_DIR constant
cells.append('''@app.cell
def _(Path):
    PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
    return (PROJECT_DIR,)''')

# Cell: Title and Navigation
nav_rows = []
for s in SCRIPTS:
    nav_rows.append(f"    | {s['step']} | `{s['path'].split('/')[-1]}` | {s['cp']} PASSED |")
nav_table = "\n".join(nav_rows)

cells.append(f'''@app.cell
def _(mo):
    mo.md("""
    # College Graduation Rate & Selectivity Analysis -- Script Walkthrough

    **Research Question:** How does institutional selectivity (admission rate) relate to college graduation rates, and what roles do student composition and institutional resources play in mediating this relationship?

    This notebook displays the executed scripts from `scripts/`. Each section shows:
    1. The complete script code (archived from the file, commented out)
    2. The execution log (verbatim from the file)
    3. A data preview (loads the output file)

    ## Scripts Included

    | Step | Script | Status |
    |------|--------|--------|
{nav_table}
    """)
    return''')

# Process each stage
current_stage = None
stage_names = {5: "Data Fetch", 6: "Data Cleaning", 7: "Data Transformation", 8: "Analysis & Visualization"}

for s in SCRIPTS:
    script_path = SCRIPTS_DIR / s["path"]
    script_name = s["path"].split("/")[-1]
    stage_dir = s["path"].split("/")[0]

    # Stage separator
    if s["stage"] != current_stage:
        current_stage = s["stage"]
        stage_label = stage_names[current_stage]
        cells.append(f'''@app.cell
def _(mo):
    mo.md("---\\n## Stage {current_stage}: {stage_label}")
    return''')

    # Cell 1: Header (markdown)
    version_table = ""
    if s["versions"] and len(s["versions"]) > 1:
        version_table = make_version_table(s["versions"], stage_dir, script_name)

    header_md = f"""
    ### {s['step']}: {s['title']}

    **Script:** `scripts/{s['path']}`
    **Output:** `{s['output']}`
    **Status:** {s['cp']} PASSED
    {version_table}"""

    cells.append(f'''@app.cell
def _(mo):
    mo.md("""{header_md}
    """)
    return''')

    # Cell 2: Script code (commented out)
    code = extract_code(script_path)
    commented_code = comment_out_code(code, f"scripts/{s['path']}")
    # Indent for inside the function
    indented_code = indent(commented_code, 4)

    cells.append(f'''@app.cell
def _():
{indented_code}
    return''')

    # Cell 3: Execution log (accordion)
    log_text = extract_execution_log(script_path)
    log_escaped = escape_for_triple_quote(log_text)

    cells.append(f"""@app.cell
def _(mo):
    mo.accordion({{"Execution Log ({script_name})": mo.md('''```
{log_escaped}
```''')}})
    return""")

    # Cell 4: Data inspection
    if s["is_viz"]:
        # Visualization: use mo.image()
        cells.append(f'''@app.cell
def _(mo, PROJECT_DIR):
    mo.image(src=str(PROJECT_DIR / "{s['output']}"))
    return''')
    else:
        # Data: use pl.read_parquet() + mo.ui.table()
        var_suffix = s["step"].replace(".", "_")
        cells.append(f'''@app.cell
def _(pl, mo, PROJECT_DIR):
    df_{var_suffix} = pl.read_parquet(PROJECT_DIR / "{s['output']}")
    mo.ui.table(df_{var_suffix}.head(100))
    return''')

# Summary cell
cells.append('''@app.cell
def _(mo):
    mo.md("""
    ---
    ## Summary

    | Stage | Scripts | Status |
    |-------|---------|--------|
    | Stage 5 (Fetch) | 9 | All passed |
    | Stage 6 (Clean) | 8 | All passed |
    | Stage 7 (Transform) | 4 | All passed |
    | Stage 8 (Analysis) | 7 | All passed |
    | Stage 8 (Visualization) | 6 | All passed |

    **Output Files:**
    - Final analysis data: `data/processed/2026-03-29_analysis.parquet`
    - Analysis results: `output/analysis/` (7 parquet files)
    - Figures: `output/figures/` (6 PNG files)

    **All scripts preserved in:** `scripts/`
    """)
    return''')

# --- Assemble notebook ---
header = '''#!/usr/bin/env python3
"""
College Graduation Rate & Selectivity Analysis -- Script Walkthrough

This notebook DISPLAYS the executed scripts from the scripts/ directory.
It does NOT contain new analysis code. Each script is archived verbatim
with its execution log for audit trail purposes.

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

notebook_content = header + "\n\n".join(cells) + footer

OUTPUT_NOTEBOOK.write_text(notebook_content)
print(f"Notebook written to: {OUTPUT_NOTEBOOK}")
print(f"Total cells: {len(cells)}")
print(f"File size: {OUTPUT_NOTEBOOK.stat().st_size:,} bytes")
print(f"Line count: {len(notebook_content.splitlines())}")
