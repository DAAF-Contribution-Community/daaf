#!/usr/bin/env python3
"""Batch-normalize PROJECT_DIR paths in decompiled scripts.

Standalone CLI tool for Reproducibility Verification mode (RV-1).
Scans all .py files in a directory tree, finds PROJECT_DIR = Path("...")
assignments, and rewrites them to point at the reproduction project path.

Usage:
    python normalize_project_dir.py <scripts_dir> <target_project_dir>

Arguments:
    scripts_dir         Directory containing decompiled .py scripts
    target_project_dir  Absolute path to the reproduction project folder

Exit codes:
    0  Completed successfully (regardless of whether changes were made)
    1  Error (directory not found, no .py files, I/O error)
"""

import argparse
import re
import sys
from pathlib import Path


def find_py_files(scripts_dir):
    """Recursively find all .py files under scripts_dir."""
    return sorted(scripts_dir.rglob("*.py"))


def normalize_file(py_path, target_project_dir):
    """Replace PROJECT_DIR = Path("...") with the target path.

    Returns (original_value, True) if a replacement was made,
    (None, False) if no matching line was found.
    """
    pattern = re.compile(
        r"""^(\s*PROJECT_DIR\s*=\s*Path\()(['"])(.*?)\2(\).*)$"""
    )
    text = py_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    original_value = None
    modified = False

    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            prefix = m.group(1)      # e.g. 'PROJECT_DIR = Path('
            quote = m.group(2)        # ' or "
            original_value = m.group(3)
            suffix = m.group(4)       # e.g. ')'
            # Only rewrite if the value actually differs
            if original_value != target_project_dir:
                lines[i] = f"{prefix}{quote}{target_project_dir}{quote}{suffix}\n"
                modified = True
            break  # Only process the first matching line per file

    if modified:
        py_path.write_text("".join(lines), encoding="utf-8")

    return original_value, modified


def main():
    parser = argparse.ArgumentParser(
        description="Batch-normalize PROJECT_DIR in decompiled scripts."
    )
    parser.add_argument(
        "scripts_dir",
        help="Directory containing decompiled .py scripts",
    )
    parser.add_argument(
        "target_project_dir",
        help="Absolute path to the reproduction project folder",
    )
    args = parser.parse_args()

    scripts_dir = Path(args.scripts_dir).resolve()
    target_project_dir = str(Path(args.target_project_dir).resolve())

    if not scripts_dir.is_dir():
        print(f"ERROR: scripts_dir is not a directory: {scripts_dir}", file=sys.stderr)
        sys.exit(1)

    py_files = find_py_files(scripts_dir)
    if not py_files:
        print(f"ERROR: No .py files found in {scripts_dir}", file=sys.stderr)
        sys.exit(1)

    # --- Report header ---
    print("=" * 72)
    print("PROJECT_DIR Batch Normalization Report")
    print("=" * 72)
    print(f"Scripts directory : {scripts_dir}")
    print(f"Target PROJECT_DIR: {target_project_dir}")
    print(f"Files scanned     : {len(py_files)}")
    print("-" * 72)

    # --- Process each file ---
    normalized_count = 0
    skipped_count = 0
    no_match_count = 0

    # Collect rows for the Infrastructure Normalizations table
    table_rows = []

    for py_path in py_files:
        rel_path = py_path.relative_to(scripts_dir)
        original_value, was_modified = normalize_file(py_path, target_project_dir)

        if original_value is None:
            no_match_count += 1
        elif was_modified:
            normalized_count += 1
            table_rows.append((str(rel_path), original_value, target_project_dir))
            print(f"  NORMALIZED: {rel_path}")
            print(f"    original : {original_value}")
            print(f"    new      : {target_project_dir}")
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
        print("| File | Original Value | Normalized Value | Type |")
        print("|------|----------------|------------------|------|")
        for rel, orig, new in table_rows:
            print(
                f"| `{rel}` "
                f"| `PROJECT_DIR = Path(\"{orig}\")` "
                f"| `PROJECT_DIR = Path(\"{new}\")` "
                f"| PROJECT_DIR path |"
            )
    else:
        print("No normalizations were required.")

    print("-" * 72)
    total = len(py_files)
    print(
        f"RESULT: {normalized_count} normalized, {skipped_count} unchanged, "
        f"{no_match_count} no match (out of {total} files scanned)"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
