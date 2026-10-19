# Quickstart

## Installation

No installation needed in DAAF: `marimo` (0.25.0) is pre-installed in the
container as DAAF's standard notebook format. Runtime installs are blocked in
DAAF (`pip install`/`uv add` are refused both at the command line and inside
executed scripts — see CLAUDE.md § Runtime Package Installation). If a marimo
extra (e.g., `marimo[recommended]` for SQL cells, AI completion, and in-viewer
plotting) is genuinely required, escalate to the user to add it to the Dockerfile
(user additions block near the end) and rebuild.

## CLI Commands

### Create/Edit Notebooks

```bash
# Launch notebook server (browse/create notebooks)
marimo edit

# Create or edit specific notebook
marimo edit my_notebook.py

# Watch for external edits (VS Code, vim, etc.)
marimo edit --watch my_notebook.py
```

### Run as App

```bash
# Serve notebook as read-only web app
marimo run my_notebook.py

# With custom host/port
marimo run my_notebook.py --host 0.0.0.0 --port 8080
```

### Run as Script

```bash
# Execute notebook as Python script
python my_notebook.py

# With CLI arguments
python my_notebook.py -- --arg1 value1
```

### Tutorials

```bash
# List all tutorials
marimo tutorial

# Recommended sequence
marimo tutorial intro      # Start here
marimo tutorial dataflow   # Understand reactivity
marimo tutorial ui         # Interactive elements
marimo tutorial markdown   # Formatting
marimo tutorial plots      # Visualization
marimo tutorial sql        # SQL cells
```

### Check (Lint)

`marimo check` reads notebooks without running them and reports structural, runtime, and formatting problems.

```bash
# Human-readable report
marimo check notebook.py

# Machine-readable report, breaking rules only (comma-separated codes or prefixes)
marimo check notebook.py --format json --select MB

# Everything except two formatting rules
marimo check notebook.py --ignore MF004,MF007
```

Options in 0.25.0 (`marimo check --help`): `--select` and `--ignore` take comma-separated codes or prefixes; `--format full|json`; `--strict` makes warnings return a non-zero exit code; `--fix` rewrites files in place, and `--unsafe-fixes` also applies fixes "that may change code behavior (e.g., removing empty cells)". There is no `--output` flag; redirect stdout to keep a report.

**JSON output and exit codes.** `--format json` prints `{"issues": [...], "summary": {"total_files", "files_with_issues", "total_issues", "fixed_issues", "errored"}}`. Each issue carries `code`, `name`, `severity`, `message`, `line`, `fixable`, and usually `cell_id`. A breaking issue gives exit code 1 and `"errored": true`. Read the exit code together with `summary.errored` and `summary.files_with_issues`, not `total_issues` alone: a missing file also gives exit 1 and `"errored": true`, but with `"total_issues": 0`.

**Do not combine `--strict` with `--format json` on 0.25.0.** The command crashes (`UnboundLocalError` for `fixed` in marimo's `cli.py`) after printing the JSON and exits 1 even when there are no issues. Use non-strict JSON and the exit-code reading above.

**Rules shipped in 0.25.0** (registry: `marimo/_lint/rules/__init__.py` and the `breaking/`, `runtime/`, `formatting/`, `wasm/` subpackages):

| Code | Name | Severity | Fixable |
|------|------|----------|---------|
| MB001 | unparsable-cells | breaking | no |
| MB002 | multiple-definitions | breaking | no |
| MB003 | cycle-dependencies | breaking | no |
| MB004 | setup-cell-dependencies | breaking | no |
| MB005 | invalid-syntax | breaking | no |
| MR001 | self-import | runtime | no |
| MR002 | branch-expression | runtime | no |
| MR003 | reusable-definition-order | runtime | unsafe |
| MR004 | private-import-alias | runtime | no |
| MF001 | general-formatting | formatting | yes |
| MF002 | parse-stdout | formatting | no |
| MF003 | parse-stderr | formatting | no |
| MF004 | empty-cells | formatting | unsafe |
| MF005 | sql-parse-error | formatting | no |
| MF006 | misc-log-capture | formatting | no |
| MF007 | markdown-indentation | formatting | yes |
| MW001 | incompatible-import | wasm | no |
| MW002 | unsafe-system-call | wasm | no |
| MW003 | incompatible-package | wasm | no |

The MW (WebAssembly) rules are off by default and run only when `--select` names them. Breaking (MB) issues are the ones that stop a notebook from running: `marimo run` checks the notebook first (`--check`, the default) and refused to start notebooks with MB001 and MB002 issues when tested on 0.25.0.

**Never run `--fix` or `--unsafe-fixes` on a DAAF Stage 9 notebook.** Every archive cell (comment lines plus `pass`) is reported as MF004 empty-cells with `"fixable": "unsafe"`, so `--unsafe-fixes` would delete the archived code. MF007 is a safe fix, but it rewrites the whitespace of `mo.md()` blocks in a notebook that is meant to be a literal archive. The Stage 9 check commands are defined in `.claude/agents/notebook-assembler.md`.

### Export

```bash
# Export to HTML (runs every cell; writes __marimo__/session/ next to the
# notebook, see apps-deployment.md > HTML)
marimo export html notebook.py -o output.html

# Export to WASM (runs in browser)
marimo export html-wasm notebook.py -o output_dir/

# Export to Jupyter notebook (needs nbformat, which the DAAF image does not
# include; adding it is a Dockerfile change and a rebuild)
marimo export ipynb notebook.py -o output.ipynb

# Export to flat Python script
marimo export script notebook.py -o flat_script.py
```

### Convert from Jupyter (Inbound)

```bash
# Convert .ipynb INTO marimo (inbound only — marimo convert is for importing)
marimo convert notebook.ipynb -o notebook.py
# To export FROM marimo to other formats, use: marimo export {format}
# e.g., marimo export md notebook.py, marimo export html notebook.py
```

## First Notebook

### Basic Structure

Every marimo notebook starts with importing the library:

```python
import marimo as mo
```

### Cell Basics

- Each cell is a block of Python code
- The **last expression** in a cell is its output
- Cells execute based on **variable dependencies**, not position

```python
# Cell 1: Define data
data = [1, 2, 3, 4, 5]

# Cell 2: Process (runs after Cell 1 because it reads 'data')
total = sum(data)
total  # This is the output
```

### Adding Markdown

```python
mo.md("# My Analysis")
```

With Python values:

```python
mo.md(f"The total is **{total}**")
```

### Adding Interactivity

```python
slider = mo.ui.slider(1, 100, value=50, label="Choose a value")
slider  # Display it
```

Access value in another cell:

```python
mo.md(f"You selected: {slider.value}")
```

## File Format

marimo notebooks are **pure Python** (`.py` files):

```python
import marimo

__generated_with = "0.25.0"
app = marimo.App()

@app.cell
def _():
    import marimo as mo
    return (mo,)

@app.cell
def _(mo):
    mo.md("# Hello marimo!")
    return

if __name__ == "__main__":  # marimo framework boilerplate (auto-generated)
    app.run()
```

Benefits:
- Git-friendly (no JSON merge conflicts)
- Executable as scripts
- Import functions from other notebooks

## Package Management

### Auto-install on Import

marimo can detect missing packages and offer to install them; accepting the offer makes marimo attempt the install. Enable in settings.

### Inline Dependencies (PEP 723)

Add dependencies to notebook header:

```python
# /// script
# dependencies = ["pandas", "altair"]
# ///
```

Run in isolated environment:

```bash
marimo edit --sandbox notebook.py
```

> **Not inside DAAF:** neither mechanism belongs in the container, for different reasons. `--sandbox` (on `marimo edit` and `marimo run` in 0.25.0: `--sandbox [uv|pixi]`, default `uv`) runs the notebook in a separate environment that uv or Pixi builds by installing the notebook's PEP 723 dependencies from a package index; that environment is not the one the Dockerfile defines, so its results cannot be reproduced from the image. It also rewrites the notebook file: it adds an empty `# /// script` dependency block when the notebook has none, and with uv it adds a `requires-python` line to an existing block that lacks one. The auto-install offer makes marimo attempt to install missing packages into the live container environment (with `uv pip install` or `python -m pip install`), which is runtime package installation: a rebuild silently reverts it (CLAUDE.md § Runtime Package Installation). Inside the DAAF container, run notebooks against the image's pinned packages and add a package through the Dockerfile and a rebuild (see Installation above).
>
> A notebook that carries a PEP 723 block can also trigger a prompt: when uv is installed and the terminal is interactive, `marimo edit` and `marimo run` ask whether to run in a sandbox. Without an interactive terminal they default to no sandbox; `--no-sandbox` skips the question.

## VS Code / Cursor Integration

Install the [marimo VS Code extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo) for:
- Edit notebooks in VS Code
- Syntax highlighting
- Run notebooks directly

## Next Steps

- Learn about [reactivity](./reactivity.md) to understand how cells execute
- Add [UI elements](./ui-elements.md) for interactivity
- Work with [data and SQL](./sql-data.md)

## Official Resources

- Docs: https://docs.marimo.io
- GitHub: https://github.com/marimo-team/marimo
- Discord: https://marimo.io/discord
- Gallery: https://marimo.io/gallery
