#!/usr/bin/env python3
"""
Decompile a canonical DAAF Stage 9 marimo archive into Python scripts.

The accepted notebook is the archive-shaped marimo application emitted by the
DAAF notebook-assembler agent. Each script bundle must contain an immediately
adjacent header cell, commented source archive cell, and matching execution-log
accordion cell. The complete notebook and extraction plan are validated before
the requested output root is created.

A bounded set of legacy DAAF details remains supported: ``####`` step headings,
``**Final Script:**`` metadata, SOURCE values without the canonical ``scripts/``
prefix, wrapped ``mo.accordion`` calls, and pre-commented execution logs.
Arbitrary marimo applications are not accepted merely because they import
marimo.

Usage:
    python scripts/decompile_notebook.py <notebook_path> <output_dir>

Output policy:
    The output root must not already exist. This utility never merges with or
    overwrites an existing extraction tree.

Framework-utility exception: this standalone CLI is not a research execution
artifact and is directly runnable from /daaf/scripts/.
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path, PurePosixPath


ALLOWED_STAGES = {
    "stage5_fetch",
    "stage6_clean",
    "stage7_transform",
    "stage8_analysis",
}
CELL_DECORATOR_RE = re.compile(r"^@app\.cell[ \t]*$")
CELL_DECORATOR_HINT_RE = re.compile(r"^@app\.cell\b")
SOURCE_MARKER_RE = re.compile(r"^# SOURCE:[ \t]*(.*)$")
SOURCE_HINT_RE = re.compile(r"^#\s*SOURCE\b", re.IGNORECASE)
SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.py$")
HEADER_SEPARATOR_RE = re.compile(r"^    # ={10,}[ \t]*$")
LOG_DECORATION_RE = re.compile(r"^[=\-_*]+$")
PLACEHOLDER_LOG_FORMS = {
    "no execution log found",
    "todo",
    "tbd",
    "placeholder",
    "generic placeholder",
    "execution log placeholder",
    "placeholder execution log",
    "execution log todo",
    "todo execution log",
    "execution log tbd",
    "tbd execution log",
    "verbatim copy from script",
    "verbatim copy from the script",
}
PLACEHOLDER_INSTRUCTION_WORDS = {
    "a",
    "actual",
    "add",
    "an",
    "and",
    "below",
    "complete",
    "copy",
    "execution",
    "from",
    "full",
    "generic",
    "here",
    "is",
    "later",
    "log",
    "paste",
    "placeholder",
    "please",
    "real",
    "script",
    "text",
    "the",
    "this",
    "tbd",
    "todo",
    "verbatim",
}


class DecompileError(Exception):
    """Raised for a rejected notebook or unsafe extraction plan."""


def fail(message):
    """Raise a user-facing fail-closed validation error."""
    raise DecompileError(message)


def split_cells(notebook_text):
    """Split a marimo source file at exact canonical ``@app.cell`` lines."""
    lines = notebook_text.splitlines()
    decorator_indices = [
        index for index, line in enumerate(lines) if CELL_DECORATOR_RE.fullmatch(line)
    ]
    malformed_decorators = [
        index + 1
        for index, line in enumerate(lines)
        if CELL_DECORATOR_HINT_RE.match(line)
        and not CELL_DECORATOR_RE.fullmatch(line)
    ]
    if malformed_decorators:
        fail(
            "malformed or unsupported @app.cell decorator at notebook line "
            f"{malformed_decorators[0]}"
        )
    if not decorator_indices:
        fail("no canonical @app.cell boundaries found")

    cells = []
    for position, decorator_index in enumerate(decorator_indices):
        next_index = (
            decorator_indices[position + 1]
            if position + 1 < len(decorator_indices)
            else len(lines)
        )
        cells.append(
            {
                "text": "\n".join(lines[decorator_index + 1 : next_index]),
                "line": decorator_index + 2,
            }
        )
    return "\n".join(lines[: decorator_indices[0]]), cells


def validate_notebook_identity(notebook_text, preamble):
    """Require the bounded DAAF notebook-assembler marimo identity."""
    try:
        tree = ast.parse(notebook_text)
    except SyntaxError as error:
        fail(
            "notebook is not valid Python syntax "
            f"at line {error.lineno}: {error.msg}"
        )

    imports_marimo = any(
        isinstance(node, ast.Import)
        and any(alias.name == "marimo" for alias in node.names)
        for node in tree.body
    )
    has_app_assignment = any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(
            node.value,
            ast.Call,
        )
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "marimo"
        and node.value.func.attr == "App"
        and (
            (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "app"
                    for target in node.targets
                )
            )
            or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "app"
            )
        )
        for node in tree.body
    )
    if not imports_marimo or not has_app_assignment:
        fail("notebook lacks the canonical marimo import and app assignment")

    canonical_signature = "Generated by notebook-assembler agent."
    legacy_signature = (
        "This notebook DISPLAYS the executed scripts from the scripts/ directory."
    )
    legacy_safety_statement = "It does NOT contain new analysis code."
    if canonical_signature not in preamble and not (
        legacy_signature in preamble and legacy_safety_statement in preamble
    ):
        fail(
            "notebook lacks the DAAF notebook-assembler archive identity; "
            "arbitrary marimo applications are not accepted"
        )


def source_marker_tokens(cell):
    """Return wrapper-level SOURCE comment tokens without inspecting strings."""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(cell["text"]).readline)
        comments = [
            token
            for token in tokens
            if token.type == tokenize.COMMENT
            and token.start[1] == 4
            and SOURCE_HINT_RE.match(token.string)
        ]
    except (IndentationError, tokenize.TokenError) as error:
        fail(
            "malformed Python cell while inspecting SOURCE markers near "
            f"notebook line {cell['line']}: {error}"
        )
    return comments


def normalize_source_path(raw_source_path, notebook_line):
    """Validate and normalize a canonical or bounded-legacy SOURCE path."""
    if not raw_source_path:
        fail(f"empty SOURCE path at notebook line {notebook_line}")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw_source_path):
        fail(f"SOURCE path contains a control character at notebook line {notebook_line}")
    if "\\" in raw_source_path:
        fail(f"SOURCE path must use forward slashes: {raw_source_path}")
    if raw_source_path.startswith("/") or re.match(r"^[A-Za-z]:/", raw_source_path):
        fail(f"SOURCE path must be relative, not absolute: {raw_source_path}")

    raw_components = raw_source_path.split("/")
    if any(component in {".", ".."} for component in raw_components):
        fail(
            "SOURCE path contains a forbidden '.' or '..' component: "
            f"{raw_source_path}"
        )

    if raw_components and raw_components[0] == "scripts":
        components = raw_components[1:]
        path_form = "canonical"
    else:
        components = raw_components
        path_form = "legacy"

    if len(components) != 2 or any(not component for component in components):
        fail(
            "SOURCE path must contain exactly one canonical stage directory "
            f"and one filename: {raw_source_path}"
        )
    stage, filename = components
    if stage not in ALLOWED_STAGES:
        fail(f"SOURCE path has a noncanonical stage directory: {raw_source_path}")
    if not SAFE_FILENAME_RE.fullmatch(filename):
        fail(
            "SOURCE filename is unsafe or does not end in .py: "
            f"{raw_source_path}"
        )

    normalized = PurePosixPath(stage, filename).as_posix()
    return normalized, path_form


def extract_source_code(cell):
    """Validate one archive cell and recover its source path and code."""
    marker_tokens = source_marker_tokens(cell)
    if not marker_tokens:
        return None

    lines = cell["text"].splitlines()
    nonblank_indices = [index for index, line in enumerate(lines) if line.strip()]
    if len(nonblank_indices) < 2 or lines[nonblank_indices[0]] != "def _():":
        fail(
            "SOURCE marker is not inside a canonical def _() archive cell near "
            f"notebook line {cell['line']}"
        )
    marker_index = nonblank_indices[1]
    first_marker_tokens = [
        marker for marker in marker_tokens if marker.start[0] - 1 == marker_index
    ]
    if len(first_marker_tokens) != 1:
        fail(
            "SOURCE marker must be the first body item in a canonical def _() "
            f"archive cell near notebook line {cell['line']}"
        )

    marker_token = first_marker_tokens[0]
    marker_match = SOURCE_MARKER_RE.fullmatch(marker_token.string)
    if marker_match is None:
        fail(
            "malformed SOURCE marker at notebook line "
            f"{cell['line'] + marker_token.start[0] - 1}"
        )
    raw_source_path = marker_match.group(1).strip()
    marker_line = cell["line"] + marker_token.start[0] - 1
    source_path, path_form = normalize_source_path(raw_source_path, marker_line)

    header_marker_tokens = [
        marker
        for marker in marker_tokens
        if marker_index < marker.start[0] - 1 <= marker_index + 5
    ]
    if header_marker_tokens:
        diagnostic = (
            "duplicate SOURCE markers"
            if any(
                SOURCE_MARKER_RE.fullmatch(marker.string)
                for marker in header_marker_tokens
            )
            else "malformed SOURCE marker"
        )
        fail(
            f"{diagnostic} in archive header opened near notebook line "
            f"{cell['line']}"
        )

    prefix_nonblank = [line for line in lines[:marker_index] if line.strip()]
    if prefix_nonblank != ["def _():"]:
        fail(
            "SOURCE marker must be the first body item in a canonical def _() "
            f"archive cell near notebook line {cell['line']}"
        )

    if marker_index + 5 >= len(lines):
        fail(f"incomplete archive header after SOURCE marker for {source_path}")
    header = lines[marker_index + 1 : marker_index + 6]
    if not HEADER_SEPARATOR_RE.fullmatch(header[0]):
        fail(f"malformed archive separator after SOURCE marker for {source_path}")
    if header[1] != "    # ARCHIVED SCRIPT CODE (commented out to prevent execution conflicts)":
        fail(f"malformed ARCHIVED SCRIPT CODE header for {source_path}")
    expected_preserved = (
        "    # Full executable script preserved at: " + raw_source_path
    )
    if header[2] != expected_preserved:
        fail(
            "archive preserved-path header does not match its SOURCE marker for "
            f"{source_path}"
        )
    if not HEADER_SEPARATOR_RE.fullmatch(header[3]) or header[4] != "    #":
        fail(f"malformed archive header terminator for {source_path}")

    pass_indices = [
        index
        for index, line in enumerate(lines)
        if line == "    pass  # Cell must have executable statement"
    ]
    if len(pass_indices) != 1:
        fail(
            "archive cell must contain exactly one canonical pass statement for "
            f"{source_path}"
        )
    pass_index = pass_indices[0]
    code_start = marker_index + 6
    if pass_index < code_start:
        fail(f"archive pass statement precedes code for {source_path}")

    code_lines = []
    for line_index, line in enumerate(lines[code_start:pass_index], start=code_start):
        if line.startswith("    # "):
            code_lines.append(line[6:])
        elif line == "    #":
            code_lines.append("")
        else:
            fail(
                "archive code line is not safely comment-prefixed for "
                f"{source_path} at notebook line {cell['line'] + line_index}"
            )
    if not any(line.strip() for line in code_lines):
        fail(f"archive source code is empty for {source_path}")

    saw_return = False
    for trailing_index, line in enumerate(lines[pass_index + 1 :], start=pass_index + 1):
        if not line.strip() or (line.startswith("#") and not line.startswith("    ")):
            continue
        if line == "    return" and not saw_return:
            saw_return = True
            continue
        fail(
            "ambiguous executable content follows the archive pass statement for "
            f"{source_path} at notebook line {cell['line'] + trailing_index}"
        )

    return {
        "source_path": source_path,
        "raw_source_path": raw_source_path,
        "path_form": path_form,
        "code": "\n".join(code_lines).rstrip(),
        "line": marker_line,
    }


def extract_header_metadata(cell):
    """Extract canonical or documented legacy metadata from one literal md cell."""
    tree = ast.parse(cell["text"])
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1:
        return None

    markdown_calls = [
        statement.value
        for statement in functions[0].body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and is_named_attribute(statement.value.func, "mo", "md")
    ]
    if len(markdown_calls) != 1:
        return None
    markdown_call = markdown_calls[0]
    if (
        len(markdown_call.args) != 1
        or markdown_call.keywords
        or not isinstance(markdown_call.args[0], ast.Constant)
        or not isinstance(markdown_call.args[0].value, str)
    ):
        return None

    markdown_text = markdown_call.args[0].value
    step_match = re.search(r"#{3,4} ([\d.]+): ([^\n\r]+)", markdown_text)
    script_match = re.search(
        r"\*\*(?:Final )?Script:\*\* `scripts/(.+?)`",
        markdown_text,
    )
    if not step_match or not script_match:
        return None

    output_match = re.search(r"\*\*Output:\*\* `(.+?)`", markdown_text)
    status_match = re.search(r"\*\*Status:\*\* ([^\n\r]+)", markdown_text)
    return {
        "step": step_match.group(1),
        "label": step_match.group(2).strip(),
        "script_path": script_match.group(1),
        "output_path": output_match.group(1) if output_match else "—",
        "status": status_match.group(1).strip() if status_match else "—",
        "heading_form": "legacy" if step_match.group(0).startswith("####") else "canonical",
        "script_label_form": (
            "legacy" if "**Final Script:**" in markdown_text else "canonical"
        ),
    }


def is_named_attribute(node, owner, attribute):
    """Return whether an AST node is exactly ``owner.attribute``."""
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
        and node.attr == attribute
    )


def has_accordion_syntax(cell):
    """Detect an accordion call lexically for targeted malformed diagnostics."""
    return re.search(r"\bmo\.accordion\s*\(", cell["text"]) is not None


def is_placeholder_execution_log(log_text):
    """Recognize only whole-payload assembler placeholder signals."""
    normalized_lines = []
    for line in log_text.splitlines():
        normalized_line = re.sub(r"^\s*#\s?", "", line).strip()
        if normalized_line and not LOG_DECORATION_RE.fullmatch(normalized_line):
            normalized_lines.append(normalized_line)

    normalized = " ".join(normalized_lines).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).strip()
    if not normalized:
        return False

    candidate_forms = [normalized]
    execution_log_prefix = "execution log "
    if normalized.startswith(execution_log_prefix):
        candidate_forms.append(normalized[len(execution_log_prefix) :].strip())

    for candidate in candidate_forms:
        if candidate in PLACEHOLDER_LOG_FORMS:
            return True

        words = candidate.split()
        word_set = set(words)
        is_log_instruction = (
            bool(word_set.intersection({"paste", "copy", "add"}))
            and {"execution", "log"}.issubset(word_set)
            and word_set.issubset(PLACEHOLDER_INSTRUCTION_WORDS)
        )
        if is_log_instruction:
            return True

        is_generic_placeholder = (
            "placeholder" in word_set
            and word_set.issubset(PLACEHOLDER_INSTRUCTION_WORDS)
        )
        if is_generic_placeholder:
            return True

        if (
            {"verbatim", "copy", "from", "script"}.issubset(word_set)
            and word_set.issubset(PLACEHOLDER_INSTRUCTION_WORDS)
        ):
            return True

    return False


def extract_execution_log(cell):
    """Validate a canonical (possibly wrapped) execution-log accordion cell."""
    if not has_accordion_syntax(cell):
        return None

    try:
        tree = ast.parse(cell["text"])
    except SyntaxError as error:
        fail(
            "malformed execution-log cell near notebook line "
            f"{cell['line']}: {error.msg}"
        )

    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1:
        fail(
            "execution-log cell must contain exactly one function wrapper near "
            f"notebook line {cell['line']}"
        )
    function = functions[0]
    accordion_expressions = [
        statement
        for statement in function.body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and is_named_attribute(statement.value.func, "mo", "accordion")
    ]
    if len(accordion_expressions) != 1:
        fail(
            "execution-log cell must contain exactly one mo.accordion call near "
            f"notebook line {cell['line']}"
        )
    allowed_statements = tuple(accordion_expressions) + tuple(
        statement
        for statement in function.body
        if isinstance(statement, ast.Return) and statement.value is None
    )
    if len(allowed_statements) != len(function.body):
        fail(
            "execution-log cell contains ambiguous executable content near "
            f"notebook line {cell['line']}"
        )

    accordion_call = accordion_expressions[0].value
    if len(accordion_call.args) != 1 or accordion_call.keywords:
        fail(
            "mo.accordion execution log must have exactly one positional mapping "
            f"argument near notebook line {cell['line']}"
        )
    mapping = accordion_call.args[0]
    if not isinstance(mapping, ast.Dict) or len(mapping.keys) != 1:
        fail(
            "execution-log accordion must contain exactly one mapping entry near "
            f"notebook line {cell['line']}"
        )

    key = mapping.keys[0]
    value = mapping.values[0]
    if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
        fail(f"execution-log accordion key must be a string near notebook line {cell['line']}")
    name_match = re.fullmatch(r"Execution Log \(([^)]+)\)", key.value)
    if name_match is None:
        fail(
            "execution-log accordion key must match 'Execution Log (filename.py)' "
            f"near notebook line {cell['line']}"
        )

    if (
        not isinstance(value, ast.Call)
        or not is_named_attribute(value.func, "mo", "md")
        or len(value.args) != 1
        or value.keywords
        or not isinstance(value.args[0], ast.Constant)
        or not isinstance(value.args[0].value, str)
    ):
        fail(
            "execution-log accordion value must be one literal mo.md string near "
            f"notebook line {cell['line']}"
        )
    fenced_text = value.args[0].value
    fence_match = re.fullmatch(r"```\n(.*)\n```", fenced_text, re.DOTALL)
    if fence_match is None:
        fail(
            "execution-log markdown must contain exactly one complete plain fenced "
            f"body near notebook line {cell['line']}"
        )
    log_text = fence_match.group(1)
    if not log_text.strip():
        fail(f"execution log is empty near notebook line {cell['line']}")
    if is_placeholder_execution_log(log_text):
        fail(
            "execution log is a placeholder rather than archived execution "
            f"evidence near notebook line {cell['line']}"
        )

    return {
        "script_name": name_match.group(1),
        "log_text": log_text,
        "line": cell["line"] + accordion_expressions[0].lineno - 1,
    }


def classify_cells(cells):
    """Validate marker syntax and classify every relevant marimo cell."""
    classified = []
    for cell in cells:
        source = extract_source_code(cell)
        if source is not None:
            classified.append(("source_code", source))
            continue

        if has_accordion_syntax(cell):
            log = extract_execution_log(cell)
            classified.append(("execution_log", log))
            continue

        header = extract_header_metadata(cell)
        if header is not None:
            classified.append(("markdown_header", header))
            continue

        classified.append(("other", {}))
    return classified


def build_archive_plan(classified):
    """Require unambiguous adjacent header/source/log bundles."""
    scripts = []
    seen_source_paths = set()
    associated_log_indices = set()

    for index, (cell_type, content) in enumerate(classified):
        if cell_type != "source_code":
            continue

        source_path = content["source_path"]
        if source_path in seen_source_paths:
            fail(f"duplicate SOURCE path: {source_path}")
        seen_source_paths.add(source_path)

        if index == 0 or classified[index - 1][0] != "markdown_header":
            fail(
                f"archive source {source_path} is missing its immediately preceding "
                "script header cell"
            )
        header = classified[index - 1][1]
        header_source, _ = normalize_source_path(
            header["script_path"],
            content["line"],
        )
        if header_source != source_path:
            fail(
                "script header/source mismatch: header names "
                f"{header_source}, SOURCE names {source_path}"
            )

        if index + 1 >= len(classified) or classified[index + 1][0] != "execution_log":
            fail(
                f"archive source {source_path} must be followed immediately by its "
                "execution-log accordion cell"
            )
        log = classified[index + 1][1]
        expected_name = PurePosixPath(source_path).name
        if log["script_name"] != expected_name:
            fail(
                "execution-log/source mismatch for "
                f"{source_path}: accordion names {log['script_name']}"
            )
        associated_log_indices.add(index + 1)

        scripts.append(
            {
                **content,
                "log_text": log["log_text"],
                "header_metadata": header,
                "log_line": log["line"],
            }
        )

    for index, (cell_type, _) in enumerate(classified):
        if cell_type == "execution_log" and index not in associated_log_indices:
            if index > 0 and classified[index - 1][0] == "execution_log":
                fail("duplicate execution-log accordion after an archive bundle")
            fail("execution-log accordion is not immediately associated with a SOURCE archive cell")

    if not scripts:
        fail(
            "no valid script bundles found; a canonical DAAF Stage 9 marimo "
            "archive requires at least one source/log bundle"
        )
    return scripts


def reconstruct_script(code, log_text):
    """Rebuild an executed script with a single comment-prefixed log section."""
    log_lines = log_text.split("\n")
    is_precommented = any(
        line.strip() in {"# EXECUTION LOG", "# ====", "# ====="}
        or (line.strip().startswith("# ===") and "=" * 10 in line.strip())
        for line in log_lines[:10]
    )

    if is_precommented:
        cleaned_lines = []
        for line in log_lines:
            if line.startswith("# "):
                cleaned_lines.append(line[2:])
            elif line == "#":
                cleaned_lines.append("")
            else:
                cleaned_lines.append(line)
    else:
        cleaned_lines = log_lines

    commented_log = "\n".join(
        "# " + line if line else "#" for line in cleaned_lines
    )
    script = code.rstrip() + "\n\n\n"
    if "# EXECUTION LOG" not in commented_log:
        script += (
            "# =============================================================================\n"
            "# EXECUTION LOG\n"
            "# =============================================================================\n"
        )
    return script + commented_log + "\n"


def validate_references(code):
    """Statically flag names read but never defined; never evaluate code."""
    known_safe = {
        "print", "len", "range", "str", "int", "float", "bool", "list",
        "dict", "set", "tuple", "type", "isinstance", "enumerate", "zip",
        "map", "filter", "sorted", "reversed", "min", "max", "sum", "abs",
        "round", "any", "all", "open", "None", "True", "False",
        "ValueError", "TypeError", "KeyError", "IndexError", "FileNotFoundError",
        "RuntimeError", "Exception", "AssertionError", "StopIteration",
        "NotImplementedError", "ZeroDivisionError", "OSError", "IOError",
        "super", "property", "staticmethod", "classmethod", "object",
        "hasattr", "getattr", "setattr", "delattr", "callable", "id",
        "hash", "repr", "format", "input", "vars", "dir", "help",
        "hex", "oct", "bin", "ord", "chr", "ascii", "iter", "next",
        "slice", "memoryview", "bytearray", "bytes", "frozenset", "complex",
        "divmod", "pow", "breakpoint", "exit", "quit", "__name__",
        "__file__", "__doc__", "__all__", "os", "sys", "math", "json",
        "csv", "datetime", "time", "warnings", "logging", "pathlib",
        "collections", "functools", "itertools", "io", "copy", "glob",
        "shutil", "tempfile", "textwrap", "re", "hashlib", "urllib",
        "subprocess", "pl", "pd", "np", "plt", "sns", "sm", "scipy",
        "sklearn", "Path", "polars", "pandas", "numpy", "matplotlib",
        "seaborn", "plotnine", "statsmodels", "yaml", "toml", "ggplot",
        "aes", "geom_point", "geom_line", "geom_bar", "geom_boxplot",
        "geom_col", "geom_hline", "geom_vline", "geom_text", "geom_label",
        "geom_tile", "geom_jitter", "geom_smooth", "geom_abline",
        "geom_ribbon", "geom_area", "geom_histogram", "geom_density",
        "geom_segment", "geom_rect", "facet_wrap", "facet_grid", "labs",
        "theme", "theme_minimal", "theme_bw", "theme_classic", "theme_void",
        "theme_gray", "theme_light", "theme_dark", "scale_fill_manual",
        "scale_color_manual", "scale_fill_brewer", "scale_color_brewer",
        "scale_fill_gradient", "scale_fill_gradient2", "scale_color_gradient",
        "scale_color_gradient2", "scale_x_continuous", "scale_y_continuous",
        "scale_x_discrete", "scale_y_discrete", "scale_x_log10",
        "scale_y_log10", "scale_fill_viridis_c", "scale_fill_cmap",
        "coord_flip", "coord_cartesian", "element_text", "element_blank",
        "element_rect", "element_line", "ggsave", "position_jitter",
        "position_dodge", "guide_legend", "guides", "after_stat",
        "stat_summary", "annotate", "figure", "Figure", "FigureCanvasSVG",
        "FigureCanvasAgg", "subplots_adjust",
    }

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    defined = set()
    referenced = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    defined.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            for argument in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                defined.add(argument.arg)
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, ast.Lambda):
            for argument in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                defined.add(argument.arg)
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            referenced.append((node.id, node.lineno))

    dangling = []
    seen = set()
    for name, line_number in referenced:
        if name not in defined and name not in known_safe and name not in seen:
            dangling.append((name, line_number))
            seen.add(name)
    return dangling


def escape_manifest_cell(value):
    """Keep notebook metadata from breaking the manifest table."""
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def build_extraction_plan(scripts, output_dir):
    """Resolve and bounds-check every output before filesystem mutation."""
    requested_root = Path(output_dir).expanduser()
    if not str(requested_root):
        fail("output directory must not be empty")
    if requested_root.exists() or requested_root.is_symlink():
        fail(
            "output directory already exists; refusing to merge with or overwrite "
            f"existing content: {requested_root}"
        )

    resolved_root = requested_root.resolve(strict=False)
    extraction_plan = []
    manifest_rows = []
    for script in scripts:
        candidate = requested_root / PurePosixPath(script["source_path"])
        resolved_candidate = candidate.resolve(strict=False)
        try:
            relative_candidate = resolved_candidate.relative_to(resolved_root)
        except ValueError:
            fail(
                "resolved output candidate escapes the extraction root: "
                f"{script['source_path']} -> {resolved_candidate} "
                f"(root: {resolved_root})"
            )
        if relative_candidate == Path("."):
            fail(f"resolved script output is not beneath the extraction root: {candidate}")

        dangling = validate_references(script["code"])
        script["dangling_refs"] = dangling
        code_lines = len(script["code"].splitlines())
        extraction_plan.append(
            {
                "source_path": script["source_path"],
                "output_path": candidate,
                "resolved_output_path": resolved_candidate,
                "content": reconstruct_script(script["code"], script["log_text"]),
            }
        )
        manifest_rows.append(
            {
                "source_path": script["source_path"],
                "stage": PurePosixPath(script["source_path"]).parent.as_posix(),
                "original_output": script["header_metadata"]["output_path"],
                "code_lines": code_lines,
                "has_log": True,
                "path_form": script["path_form"],
                "heading_form": script["header_metadata"]["heading_form"],
                "script_label_form": script["header_metadata"]["script_label_form"],
            }
        )

    manifest_path = requested_root / "MANIFEST.md"
    resolved_manifest = manifest_path.resolve(strict=False)
    try:
        manifest_relative = resolved_manifest.relative_to(resolved_root)
    except ValueError:
        fail(
            "resolved MANIFEST.md candidate escapes the extraction root: "
            f"{resolved_manifest} (root: {resolved_root})"
        )
    if manifest_relative == Path("."):
        fail("resolved MANIFEST.md candidate is not beneath the extraction root")

    return requested_root, extraction_plan, manifest_rows, manifest_path


def build_manifest(notebook_path, scripts, manifest_rows):
    """Preserve the existing manifest table and append validation metadata."""
    manifest_lines = [
        "# Decompiled Script Manifest",
        "",
        f"**Source Notebook:** `{notebook_path.name}`",
        f"**Decompiled:** {len(scripts)} scripts",
        "",
        "| # | Script | Stage | Original Output | Code Lines | Has Log |",
        "|---|--------|-------|-----------------|-----------|---------|",
    ]
    for index, row in enumerate(manifest_rows, 1):
        manifest_lines.append(
            f"| {index} | `{row['source_path']}` | {row['stage']} | "
            f"`{escape_manifest_cell(row['original_output'])}` | "
            f"{row['code_lines']} | Yes |"
        )

    scripts_with_warnings = [
        (script["source_path"], script["dangling_refs"])
        for script in scripts
        if script["dangling_refs"]
    ]
    if scripts_with_warnings:
        manifest_lines.extend(
            [
                "",
                "## Dangling Reference Warnings",
                "",
                "The following scripts reference variables that are not defined within the script.",
                "These may be cross-cell dependencies from the marimo notebook that were lost during decompilation.",
                "Scripts with dangling references may fail during re-execution and require modification.",
                "",
                "| Script | Undefined Names | Lines |",
                "|--------|----------------|-------|",
            ]
        )
        for source_path, dangling in scripts_with_warnings:
            names = ", ".join(f"`{name}`" for name, _ in dangling)
            lines = ", ".join(str(line_number) for _, line_number in dangling)
            manifest_lines.append(f"| `{source_path}` | {names} | {lines} |")

    canonical_count = sum(
        row["path_form"] == "canonical"
        and row["heading_form"] == "canonical"
        and row["script_label_form"] == "canonical"
        for row in manifest_rows
    )
    legacy_count = len(manifest_rows) - canonical_count
    manifest_lines.extend(
        [
            "",
            "## Archive Validation",
            "",
            "- **Contract:** DAAF Stage 9 marimo script archive",
            f"- **Validated source/log associations:** {len(scripts)}",
            f"- **Canonical bundles:** {canonical_count}",
            f"- **Bundles using bounded legacy metadata/path forms:** {legacy_count}",
            "- **Output policy:** New output root only; no merge or overwrite",
        ]
    )
    return "\n".join(manifest_lines) + "\n", scripts_with_warnings


def decompile(notebook_path, output_dir):
    """Validate a complete archive, then write its scripts and manifest."""
    notebook_path = Path(notebook_path)
    if not notebook_path.is_file():
        fail(f"notebook not found or is not a regular file: {notebook_path}")

    print(f"Decompiling: {notebook_path}")
    print(f"Output dir:  {output_dir}")
    print()

    try:
        notebook_bytes = notebook_path.read_bytes()
    except OSError as error:
        fail(f"could not read notebook: {error}")
    if b"\x00" in notebook_bytes:
        fail("notebook contains a NUL byte")
    try:
        notebook_text = notebook_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        fail(f"notebook is not valid UTF-8: {error}")
    if not notebook_text.strip():
        fail("notebook is empty")

    preamble, cells = split_cells(notebook_text)
    validate_notebook_identity(notebook_text, preamble)
    print(f"Found {len(cells)} cells")

    classified = classify_cells(cells)
    scripts = build_archive_plan(classified)
    print(f"Validated {len(scripts)} source/log bundle(s)")

    requested_root, extraction_plan, manifest_rows, manifest_path = (
        build_extraction_plan(scripts, output_dir)
    )
    manifest_content, scripts_with_warnings = build_manifest(
        notebook_path,
        scripts,
        manifest_rows,
    )

    print()
    if scripts_with_warnings:
        for source_path, dangling in scripts_with_warnings:
            names = ", ".join(
                f"{name} (line {line_number})" for name, line_number in dangling
            )
            print(f"  WARNING: {source_path} — dangling references: {names}")
        print(
            f"\n  {len(scripts_with_warnings)} script(s) have dangling references "
            "(variables used but never defined)."
        )
        print("  These may be cross-cell dependencies lost during decompilation.")
        print("  Review these scripts before re-execution in Reproducibility Verification.")
    else:
        print("  Reference validation: all scripts are self-contained (no dangling references detected).")

    try:
        requested_root.mkdir(parents=True, exist_ok=False)
        for planned, row in zip(extraction_plan, manifest_rows):
            planned["output_path"].parent.mkdir(parents=True, exist_ok=True)
            planned["output_path"].write_text(planned["content"], encoding="utf-8")
            print(
                f"  -> {planned['source_path']} ({row['code_lines']} code lines, log: yes)"
            )
        manifest_path.write_text(manifest_content, encoding="utf-8")
    except OSError as error:
        fail(
            "validated extraction could not be written completely: "
            f"{error}. Inspect and remove the newly created output root before retrying: "
            f"{requested_root}"
        )

    print(f"\nManifest written to: {manifest_path}")
    print(f"\nDone. {len(scripts)} scripts extracted to {requested_root}")
    return scripts


def main(arguments):
    """Standalone command-line entry point."""
    if len(arguments) != 2:
        print(
            "Usage: python decompile_notebook.py <notebook_path> <output_dir>",
            file=sys.stderr,
        )
        return 1
    try:
        decompile(arguments[0], arguments[1])
    except DecompileError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
