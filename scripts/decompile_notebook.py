#!/usr/bin/env python3
"""
Decompile a DAAF marimo notebook into individual script files.

This is the inverse of _build_notebook.py. It parses a DAAF marimo notebook
(which uses the Four-Cell Pattern per script) and extracts each script back
into a standalone .py file with its execution log appended — exactly as it
existed before notebook assembly.

After extraction, runs a cross-cell variable reference validation pass using
Python's ast module. Scripts that reference variables not defined within them
(likely cross-cell dependencies from the marimo notebook) are flagged with
warnings in both stdout and a "Dangling Reference Warnings" section in the
output MANIFEST.md. This helps Reproducibility Verification (RV-2) anticipate
scripts that may need modification before re-execution.

Usage:
    python decompile_notebook.py <notebook_path> <output_dir>

Example:
    python scripts/decompile_notebook.py \
        research/2026-02-15_.../2026-02-15_...Analysis.py \
        research/2026-03-24_.../original_files/scripts

Output:
    Creates one .py file per script found in the notebook, organized into
    stage subdirectories matching the original layout:
        output_dir/stage5_fetch/01_fetch-directory_a.py
        output_dir/stage6_clean/01_clean-directory.py
        ...

Each extracted file contains the un-commented code followed by the execution
log re-formatted as comments — a faithful reconstruction of the original
executed script file.
"""

import ast
import re
import sys
from pathlib import Path


def split_cells(notebook_text):
    """Split notebook text into individual cell bodies.

    Each cell starts with @app.cell followed by a def line.
    Returns list of (cell_body, raw_text) tuples.
    """
    # Split on @app.cell boundaries
    parts = re.split(r'\n@app\.cell\n', notebook_text)
    # First part is the file header (imports, marimo boilerplate) — skip it
    cells = []
    for part in parts[1:]:
        cells.append(part)
    return cells


def classify_cell(cell_text):
    """Classify a cell as one of: source_code, execution_log, data_inspect,
    markdown_header, stage_marker, or unknown.

    Returns (cell_type, extracted_content_dict).
    """
    if '# SOURCE:' in cell_text:
        return 'source_code', extract_source_code(cell_text)

    if 'mo.accordion({"Execution Log' in cell_text or "mo.accordion({'Execution Log" in cell_text:
        return 'execution_log', extract_execution_log(cell_text)

    if 'mo.ui.table(' in cell_text:
        return 'data_inspect', {}

    if 'mo.image(' in cell_text:
        return 'data_inspect', {}

    if 'mo.md(' in cell_text:
        # Could be a header or stage marker
        if '#### ' in cell_text:
            return 'markdown_header', extract_header_metadata(cell_text)
        return 'stage_marker', {}

    return 'unknown', {}


def extract_source_code(cell_text):
    """Extract the script source path and un-commented code from a Cell 2."""
    lines = cell_text.split('\n')

    source_path = None
    code_lines = []
    in_code = False
    header_lines_remaining = 0

    for line in lines:
        # Strip the 4-space cell-body indentation
        stripped = line[4:] if line.startswith('    ') else line

        # Find SOURCE path
        if stripped.startswith('# SOURCE:'):
            source_path = stripped.replace('# SOURCE:', '').strip()
            # Next 5 lines are the header block (===, ARCHIVED, preserved at, ===, empty #)
            header_lines_remaining = 5
            continue

        # Skip header block
        if header_lines_remaining > 0:
            header_lines_remaining -= 1
            continue

        # Stop at the pass statement
        if stripped.strip() == 'pass  # Cell must have executable statement':
            break

        # Skip the def line and initial content before SOURCE
        if stripped.startswith('def _'):
            continue

        # Un-comment the code
        if stripped.startswith('# '):
            code_lines.append(stripped[2:])
        elif stripped == '#':
            code_lines.append('')
        elif stripped.strip() == '':
            # Could be trailing whitespace between header and code; skip
            continue

    return {
        'source_path': source_path,
        'code': '\n'.join(code_lines),
    }


def extract_execution_log(cell_text):
    """Extract execution log text from a Cell 3 accordion."""
    # The log is inside triple backticks within the accordion
    # Pattern: mo.accordion({"Execution Log (script_name)": mo.md("""```\n...\n```""")})

    # Extract script name from accordion key
    name_match = re.search(r'Execution Log \(([^)]+)\)', cell_text)
    script_name = name_match.group(1) if name_match else 'unknown'

    # Extract content between the triple backticks
    # The log starts after ```\n and ends before \n```
    backtick_match = re.search(r'```\n(.*?)\n```', cell_text, re.DOTALL)
    if backtick_match:
        log_text = backtick_match.group(1)
    else:
        log_text = ''

    return {
        'script_name': script_name,
        'log_text': log_text,
    }


def extract_header_metadata(cell_text):
    """Extract metadata from a Cell 1 markdown header."""
    metadata = {}

    # Extract step and label: #### 1.1: Fetch IPEDS Directory
    step_match = re.search(r'#### ([\d.]+): (.+)', cell_text)
    if step_match:
        metadata['step'] = step_match.group(1)
        metadata['label'] = step_match.group(2)

    # Extract final script path
    script_match = re.search(r'\*\*Final Script:\*\* `scripts/(.+?)`', cell_text)
    if script_match:
        metadata['script_path'] = script_match.group(1)

    # Extract output path
    output_match = re.search(r'\*\*Output:\*\* `(.+?)`', cell_text)
    if output_match:
        metadata['output_path'] = output_match.group(1)

    # Extract status
    status_match = re.search(r'\*\*Status:\*\* (.+)', cell_text)
    if status_match:
        metadata['status'] = status_match.group(1)

    return metadata


def reconstruct_script(code, log_text):
    """Reconstruct an original script file from code and execution log.

    Returns the script content as it would have looked after run_with_capture.sh
    appended the execution log. Handles both pre-commented and uncommented log
    text from notebook accordions (the notebook-assembler may or may not strip
    comment prefixes when storing logs in accordion cells).
    """
    log_lines = log_text.split('\n')

    # Detect whether the log text is already comment-prefixed (pre-commented)
    # by checking if early lines look like commented execution log markers.
    # The known assembler (_build_notebook.py) strips comment prefixes, so
    # accordion text is normally plain. But we handle both cases defensively.
    is_precommented = False
    for line in log_lines[:10]:
        stripped = line.strip()
        if stripped in ('# EXECUTION LOG', '# ====', '# ====='):
            is_precommented = True
            break
        if stripped.startswith('# ===') and '=' * 10 in stripped:
            is_precommented = True
            break

    if is_precommented:
        # Strip existing comment prefixes to normalize, then re-add them.
        # This prevents double-commenting (# # EXECUTION LOG).
        cleaned_lines = []
        for line in log_lines:
            if line.startswith('# '):
                cleaned_lines.append(line[2:])
            elif line == '#':
                cleaned_lines.append('')
            else:
                cleaned_lines.append(line)
    else:
        # Log text is plain (not pre-commented). Preserve it exactly —
        # any '# ' at line starts is genuine content (e.g., Python comments
        # captured in stderr), not a comment prefix to strip.
        cleaned_lines = log_lines

    # Re-comment cleanly (single level of '# ' prefix)
    commented_log_lines = []
    for line in cleaned_lines:
        if line:
            commented_log_lines.append('# ' + line)
        else:
            commented_log_lines.append('#')

    commented_log = '\n'.join(commented_log_lines)

    # Combine code + execution log
    script = code.rstrip()
    script += '\n\n\n'

    # Ensure the EXECUTION LOG header is present. run_with_capture.sh checks
    # for "^# EXECUTION LOG" before allowing re-execution, and the RV-2
    # stripping step looks for this marker to remove the log before re-running.
    if '# EXECUTION LOG' not in commented_log:
        script += '# =============================================================================\n'
        script += '# EXECUTION LOG\n'
        script += '# =============================================================================\n'

    script += commented_log
    script += '\n'

    return script


def validate_references(code):
    """Check for names referenced but never defined in a script's code.

    Uses Python's ast module to find all Name nodes that are loaded (read)
    vs stored (assigned/defined). Returns a list of names that are referenced
    but never defined within the script. Filters out common builtins, stdlib
    modules, and standard DAAF imports to reduce false positives.

    Returns list of (name, line_number) tuples for dangling references.
    """
    # Common names that are always available (builtins, common imports, etc.)
    # We intentionally keep this conservative — better to have a few false
    # positives than miss real dangling references.
    KNOWN_SAFE = {
        # Python builtins
        'print', 'len', 'range', 'str', 'int', 'float', 'bool', 'list',
        'dict', 'set', 'tuple', 'type', 'isinstance', 'enumerate', 'zip',
        'map', 'filter', 'sorted', 'reversed', 'min', 'max', 'sum', 'abs',
        'round', 'any', 'all', 'open', 'None', 'True', 'False',
        'ValueError', 'TypeError', 'KeyError', 'IndexError', 'FileNotFoundError',
        'RuntimeError', 'Exception', 'AssertionError', 'StopIteration',
        'NotImplementedError', 'ZeroDivisionError', 'OSError', 'IOError',
        'super', 'property', 'staticmethod', 'classmethod', 'object',
        'hasattr', 'getattr', 'setattr', 'delattr', 'callable', 'id',
        'hash', 'repr', 'format', 'input', 'vars', 'dir', 'help',
        'hex', 'oct', 'bin', 'ord', 'chr', 'ascii', 'iter', 'next',
        'slice', 'memoryview', 'bytearray', 'bytes', 'frozenset',
        'complex', 'divmod', 'pow', 'eval', 'exec', 'compile',
        'breakpoint', 'exit', 'quit',
        '__name__', '__file__', '__doc__', '__all__',
        # Common stdlib modules used at top-level
        'os', 'sys', 'math', 'json', 'csv', 'datetime', 'time',
        'warnings', 'logging', 'pathlib', 'collections', 'functools',
        'itertools', 'io', 'copy', 'glob', 'shutil', 'tempfile',
        'textwrap', 're', 'hashlib', 'urllib', 'subprocess',
        # Common DAAF / data science imports
        'pl', 'pd', 'np', 'plt', 'sns', 'sm', 'scipy', 'sklearn',
        'Path', 'polars', 'pandas', 'numpy', 'matplotlib', 'seaborn',
        'plotnine', 'statsmodels', 'yaml', 'toml',
        'ggplot', 'aes', 'geom_point', 'geom_line', 'geom_bar',
        'geom_boxplot', 'geom_col', 'geom_hline', 'geom_vline',
        'geom_text', 'geom_label', 'geom_tile', 'geom_jitter',
        'geom_smooth', 'geom_abline', 'geom_ribbon', 'geom_area',
        'geom_histogram', 'geom_density', 'geom_segment', 'geom_rect',
        'facet_wrap', 'facet_grid',
        'labs', 'theme', 'theme_minimal', 'theme_bw', 'theme_classic',
        'theme_void', 'theme_gray', 'theme_light', 'theme_dark',
        'scale_fill_manual', 'scale_color_manual', 'scale_fill_brewer',
        'scale_color_brewer', 'scale_fill_gradient', 'scale_fill_gradient2',
        'scale_color_gradient', 'scale_color_gradient2',
        'scale_x_continuous', 'scale_y_continuous',
        'scale_x_discrete', 'scale_y_discrete',
        'scale_x_log10', 'scale_y_log10',
        'scale_fill_viridis_c', 'scale_fill_cmap',
        'coord_flip', 'coord_cartesian',
        'element_text', 'element_blank', 'element_rect', 'element_line',
        'ggsave', 'position_jitter', 'position_dodge',
        'guide_legend', 'guides', 'after_stat',
        'stat_summary', 'annotate',
        # matplotlib direct usage
        'figure', 'Figure', 'FigureCanvasSVG', 'FigureCanvasAgg',
        'subplots_adjust',
    }

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # Can't parse — skip validation

    # Collect all names that are defined (assigned, imported, used as targets)
    defined = set()
    # Collect all names that are referenced (loaded)
    referenced = []  # (name, lineno)

    for node in ast.walk(tree):
        # Definitions: assignments, imports, for-loop targets, with-as, etc.
        if isinstance(node, ast.Import):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*':
                    continue  # Can't track star imports
                defined.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                defined.add(arg.arg)
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                defined.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        defined.add(elt.id)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                defined.add(node.name)
        elif isinstance(node, ast.Lambda):
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                defined.add(arg.arg)
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)
        elif isinstance(node, ast.withitem):
            if node.optional_vars and isinstance(node.optional_vars, ast.Name):
                defined.add(node.optional_vars.id)
        elif isinstance(node, ast.comprehension):
            if isinstance(node.target, ast.Name):
                defined.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        defined.add(elt.id)

        # References: names that are loaded (read)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            referenced.append((node.id, node.lineno))

    # Find dangling references (referenced but not defined, and not known-safe)
    dangling = []
    seen = set()
    for name, lineno in referenced:
        if name not in defined and name not in KNOWN_SAFE and name not in seen:
            dangling.append((name, lineno))
            seen.add(name)

    return dangling


def decompile(notebook_path, output_dir):
    """Main decompilation: parse notebook, extract scripts, write files."""
    notebook_path = Path(notebook_path)
    output_dir = Path(output_dir)

    if not notebook_path.exists():
        print(f"Error: Notebook not found: {notebook_path}")
        sys.exit(1)

    print(f"Decompiling: {notebook_path}")
    print(f"Output dir:  {output_dir}")
    print()

    notebook_text = notebook_path.read_text()
    cells = split_cells(notebook_text)
    print(f"Found {len(cells)} cells")

    # Group cells into script bundles (Cell 1 header, Cell 2 code, Cell 3 log)
    # Strategy: iterate cells, match source_code cells with their adjacent log cells
    scripts_extracted = []

    # Build classified list
    classified = []
    for cell in cells:
        cell_type, content = classify_cell(cell)
        classified.append((cell_type, content))

    # Pair source_code cells with their preceding markdown_header and
    # following execution_log cells to capture full metadata per script.
    i = 0
    pending_header = {}
    while i < len(classified):
        cell_type, content = classified[i]

        # Track the most recent markdown_header — it precedes the source_code cell
        if cell_type == 'markdown_header':
            pending_header = content

        if cell_type == 'source_code' and content.get('source_path'):
            source_path = content['source_path']
            code = content['code']

            # Look ahead for the matching execution log
            log_text = ''
            for j in range(i + 1, min(i + 3, len(classified))):
                if classified[j][0] == 'execution_log':
                    log_text = classified[j][1].get('log_text', '')
                    break

            scripts_extracted.append({
                'source_path': source_path,
                'code': code,
                'log_text': log_text,
                'header_metadata': pending_header,
            })
            pending_header = {}

        i += 1

    print(f"Extracted {len(scripts_extracted)} scripts")
    print()

    # Write each script to the output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    for script_info in scripts_extracted:
        source_path = script_info['source_path']
        code = script_info['code']
        log_text = script_info['log_text']

        # Reconstruct the original script file
        script_content = reconstruct_script(code, log_text)

        # Create subdirectory structure matching original layout
        # source_path is like "stage5_fetch/01_fetch-directory_a.py"
        output_path = output_dir / source_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(script_content)
        # Extract stage directory and original output from header metadata
        stage_dir = str(Path(source_path).parent) if '/' in source_path else '—'
        header_meta = script_info.get('header_metadata', {})
        original_output = header_meta.get('output_path', '—')

        manifest.append({
            'source_path': source_path,
            'output_path': str(output_path),
            'stage': stage_dir,
            'original_output': original_output,
            'code_lines': len(code.split('\n')),
            'has_log': bool(log_text.strip()),
        })
        print(f"  -> {source_path} ({len(code.split(chr(10)))} code lines, log: {'yes' if log_text.strip() else 'no'})")

    # --- Validate cross-cell references ---
    print()
    scripts_with_warnings = []
    for script_info in scripts_extracted:
        code = script_info['code']
        source_path = script_info['source_path']
        dangling = validate_references(code)
        if dangling:
            scripts_with_warnings.append((source_path, dangling))
            names_str = ', '.join(f'{n} (line {ln})' for n, ln in dangling)
            print(f"  WARNING: {source_path} — dangling references: {names_str}")
        script_info['dangling_refs'] = dangling

    if scripts_with_warnings:
        print(f"\n  {len(scripts_with_warnings)} script(s) have dangling references (variables used but never defined).")
        print("  These may be cross-cell dependencies lost during decompilation.")
        print("  Review these scripts before re-execution in Reproducibility Verification.")
    else:
        print("  Reference validation: all scripts are self-contained (no dangling references detected).")

    # Write manifest
    manifest_path = output_dir / 'MANIFEST.md'
    manifest_lines = [
        '# Decompiled Script Manifest',
        '',
        f'**Source Notebook:** `{notebook_path.name}`',
        f'**Decompiled:** {len(scripts_extracted)} scripts',
        '',
        '| # | Script | Stage | Original Output | Code Lines | Has Log |',
        '|---|--------|-------|-----------------|-----------|---------|',
    ]
    for idx, m in enumerate(manifest, 1):
        manifest_lines.append(
            f"| {idx} | `{m['source_path']}` | {m['stage']} | `{m['original_output']}` | {m['code_lines']} | {'Yes' if m['has_log'] else 'No'} |"
        )

    # Add dangling reference warnings to manifest
    if scripts_with_warnings:
        manifest_lines.append('')
        manifest_lines.append('## Dangling Reference Warnings')
        manifest_lines.append('')
        manifest_lines.append('The following scripts reference variables that are not defined within the script.')
        manifest_lines.append('These may be cross-cell dependencies from the marimo notebook that were lost during decompilation.')
        manifest_lines.append('Scripts with dangling references may fail during re-execution and require modification.')
        manifest_lines.append('')
        manifest_lines.append('| Script | Undefined Names | Lines |')
        manifest_lines.append('|--------|----------------|-------|')
        for source_path, dangling in scripts_with_warnings:
            names = ', '.join(f'`{n}`' for n, _ in dangling)
            lines = ', '.join(str(ln) for _, ln in dangling)
            manifest_lines.append(f'| `{source_path}` | {names} | {lines} |')

    manifest_path.write_text('\n'.join(manifest_lines) + '\n')
    print(f"\nManifest written to: {manifest_path}")

    print(f"\nDone. {len(scripts_extracted)} scripts extracted to {output_dir}")
    return scripts_extracted


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python decompile_notebook.py <notebook_path> <output_dir>")
        print()
        print("Example:")
        print("  python scripts/decompile_notebook.py \\")
        print("    research/2026-02-15_.../2026-02-15_...Analysis.py \\")
        print("    research/2026-03-24_.../original_files/scripts")
        sys.exit(1)

    decompile(sys.argv[1], sys.argv[2])
