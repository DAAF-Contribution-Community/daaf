#!/usr/bin/env python3
"""Batch-normalize PROJECT_DIR paths in decompiled scripts.

Standalone CLI tool for Reproducibility Verification mode (RV-1).
Scans all .py and .R files in a directory tree, finds canonical PROJECT_DIR
assignments, and rewrites them to point at the reproduction project path.

Supported assignment forms:
    Python: PROJECT_DIR = Path("...")
    Python: PROJECT_DIR = "..."
    R:      PROJECT_DIR <- "..." (or =)
    R:      PROJECT_DIR <- file.path(...) (or =)

Usage:
    python normalize_project_dir.py <scripts_dir> <target_project_dir>

Arguments:
    scripts_dir         Directory containing decompiled .py and/or .R scripts
    target_project_dir  Absolute path to the reproduction project folder

Exit codes:
    0  Completed successfully (regardless of whether changes were made)
    1  Error (directory not found, no .py/.R files, I/O error)
"""

import argparse
import ast
import re
import sys
import unicodedata
from pathlib import Path


def find_script_files(scripts_dir):
    """Recursively find canonical Python and R scripts under scripts_dir."""
    script_files = list(scripts_dir.rglob("*.py"))
    script_files.extend(scripts_dir.rglob("*.R"))
    return sorted(
        script_files,
        key=lambda path: path.relative_to(scripts_dir).as_posix(),
    )


def contains_control_character(value):
    """Return whether a path contains a Unicode control character."""
    return any(unicodedata.category(character) == "Cc" for character in value)


def escape_quoted_literal(value, quote):
    """Escape a path for Python and R's shared quoted-string subset."""
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace(quote, f"\\{quote}")
    return escaped


def decode_quoted_literal(value, quote):
    """Decode the supported quoted-string subset for equality comparison."""
    try:
        decoded = ast.literal_eval(f"{quote}{value}{quote}")
    except (SyntaxError, ValueError):
        return None
    return decoded if isinstance(decoded, str) else None


def normalize_file(script_path, target_project_dir):
    """Replace the first canonical PROJECT_DIR assignment with the target path.

    Returns (original_expression, normalized_expression, was_modified,
    pattern_style), where pattern_style is 'Path', 'string', or 'file.path'
    (or None if no canonical assignment matched).
    """
    python_path_pattern = re.compile(
        r"""^(\s*PROJECT_DIR\s*=\s*Path\()(['"])((?:\\.|(?!\2).)*)\2(\).*)$"""
    )
    python_string_pattern = re.compile(
        r"""^(\s*PROJECT_DIR\s*=\s*)(['"])((?:\\.|(?!\2).)*)\2(\s*#.*)?$"""
    )
    r_string_pattern = re.compile(
        r"""^(\s*PROJECT_DIR\s*(?:<-|=)\s*)(['"])((?:\\.|(?!\2).)*)\2(\s*#.*)?$"""
    )
    r_file_path_pattern = re.compile(
        r"""^(\s*PROJECT_DIR\s*(?:<-|=)\s*file\.path\()(.+?)(\)\s*(?:#.*)?)$"""
    )

    text = script_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    original_expression = None
    normalized_expression = None
    modified = False
    pattern_style = None

    for i, line in enumerate(lines):
        if script_path.suffix == ".py":
            match = python_path_pattern.match(line)
            if match:
                prefix = match.group(1)
                quote = match.group(2)
                original_value = match.group(3)
                suffix = match.group(4)
                escaped_target = escape_quoted_literal(target_project_dir, quote)
                original_expression = (
                    f"PROJECT_DIR = Path({quote}{original_value}{quote})"
                )
                normalized_expression = (
                    f"PROJECT_DIR = Path({quote}{escaped_target}{quote})"
                )
                pattern_style = "Path"
                if decode_quoted_literal(original_value, quote) != target_project_dir:
                    lines[i] = (
                        f"{prefix}{quote}{escaped_target}{quote}{suffix}\n"
                    )
                    modified = True
                break

            match = python_string_pattern.match(line)
            if match:
                prefix = match.group(1)
                quote = match.group(2)
                original_value = match.group(3)
                trailing = match.group(4) or ""
                escaped_target = escape_quoted_literal(target_project_dir, quote)
                original_expression = (
                    f"PROJECT_DIR = {quote}{original_value}{quote}"
                )
                normalized_expression = (
                    f"PROJECT_DIR = {quote}{escaped_target}{quote}"
                )
                pattern_style = "string"
                if decode_quoted_literal(original_value, quote) != target_project_dir:
                    lines[i] = (
                        f"{prefix}{quote}{escaped_target}{quote}{trailing}\n"
                    )
                    modified = True
                break

        if script_path.suffix == ".R":
            match = r_string_pattern.match(line)
            if match:
                prefix = match.group(1)
                quote = match.group(2)
                original_value = match.group(3)
                trailing = match.group(4) or ""
                escaped_target = escape_quoted_literal(target_project_dir, quote)
                operator = "<-" if "<-" in prefix else "="
                original_expression = (
                    f"PROJECT_DIR {operator} {quote}{original_value}{quote}"
                )
                normalized_expression = (
                    f"PROJECT_DIR {operator} {quote}{escaped_target}{quote}"
                )
                pattern_style = "string"
                if decode_quoted_literal(original_value, quote) != target_project_dir:
                    lines[i] = (
                        f"{prefix}{quote}{escaped_target}{quote}{trailing}\n"
                    )
                    modified = True
                break

            match = r_file_path_pattern.match(line)
            if match:
                prefix = match.group(1)
                original_arguments = match.group(2).strip()
                suffix = match.group(3)
                quote_match = re.search(r"['\"]", original_arguments)
                quote = quote_match.group(0) if quote_match else '"'
                escaped_target = escape_quoted_literal(target_project_dir, quote)
                operator = "<-" if "<-" in prefix else "="
                original_expression = (
                    f"PROJECT_DIR {operator} file.path({original_arguments})"
                )
                normalized_expression = (
                    f"PROJECT_DIR {operator} "
                    f"file.path({quote}{escaped_target}{quote})"
                )
                pattern_style = "file.path"
                normalized_arguments = f"{quote}{escaped_target}{quote}"
                if original_arguments != normalized_arguments:
                    lines[i] = (
                        f"{prefix}{normalized_arguments}{suffix}\n"
                    )
                    modified = True
                break

    if modified:
        script_path.write_text("".join(lines), encoding="utf-8")

    return (
        original_expression,
        normalized_expression,
        modified,
        pattern_style,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Batch-normalize PROJECT_DIR in decompiled Python and R scripts."
    )
    parser.add_argument(
        "scripts_dir",
        help="Directory containing decompiled .py and/or .R scripts",
    )
    parser.add_argument(
        "target_project_dir",
        help="Absolute path to the reproduction project folder",
    )
    args = parser.parse_args()

    if contains_control_character(args.target_project_dir):
        print(
            "ERROR: target_project_dir contains an unsupported control character; "
            "no files were modified.",
            file=sys.stderr,
        )
        sys.exit(1)

    scripts_dir = Path(args.scripts_dir).resolve()
    target_project_dir = str(Path(args.target_project_dir).resolve())

    if not scripts_dir.is_dir():
        print(f"ERROR: scripts_dir is not a directory: {scripts_dir}", file=sys.stderr)
        sys.exit(1)

    script_files = find_script_files(scripts_dir)
    if not script_files:
        print(
            f"ERROR: No .py or .R files found in {scripts_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Report header ---
    print("=" * 72)
    print("PROJECT_DIR Batch Normalization Report")
    print("=" * 72)
    print(f"Scripts directory : {scripts_dir}")
    print(f"Target PROJECT_DIR: {target_project_dir}")
    print(f"Files scanned     : {len(script_files)}")
    print("-" * 72)

    # --- Process each file ---
    normalized_count = 0
    skipped_count = 0
    no_match_count = 0

    # Collect rows for the Infrastructure Normalizations table
    table_rows = []

    for script_path in script_files:
        rel_path = script_path.relative_to(scripts_dir)
        (
            original_expression,
            normalized_expression,
            was_modified,
            pattern_style,
        ) = normalize_file(script_path, target_project_dir)

        if original_expression is None:
            no_match_count += 1
        elif was_modified:
            normalized_count += 1
            table_rows.append(
                (
                    str(rel_path),
                    original_expression,
                    normalized_expression,
                    pattern_style,
                )
            )
            print(f"  NORMALIZED: {rel_path}")
            print(f"    original : {original_expression}")
            print(f"    new      : {normalized_expression}")
        else:
            skipped_count += 1
            print(f"  UNCHANGED : {rel_path} (already has target value)")

    # --- Summary ---
    print("-" * 72)
    print(f"Normalized : {normalized_count}")
    print(f"Unchanged  : {skipped_count}")
    print(f"No match   : {no_match_count}")
    print()

    # --- Markdown table for Reproduction Report ---
    if table_rows:
        print("Infrastructure Normalizations (paste into Reproduction Report):")
        print()
        print("| File | Original Expression | Normalized Expression | Type |")
        print("|------|---------------------|-----------------------|------|")
        for rel_path, original, normalized, style in table_rows:
            print(
                f"| `{rel_path}` "
                f"| `{original}` "
                f"| `{normalized}` "
                f"| PROJECT_DIR {style} |"
            )
    else:
        print("No normalizations were required.")

    print("-" * 72)
    total = len(script_files)
    print(
        f"RESULT: {normalized_count} normalized, {skipped_count} unchanged, "
        f"{no_match_count} no match (out of {total} files scanned)"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
