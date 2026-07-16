#!/usr/bin/env python3
"""Audit normalized reproduction scripts for bounded project-path containment.

The CLI is read-only. It recursively scans ``.py`` and uppercase ``.R`` files,
using the same canonical ``PROJECT_DIR`` assignment forms recognized by
``normalize_project_dir.py``:

* Python: ``PROJECT_DIR = Path("...")`` or a quoted string
* R: ``PROJECT_DIR <- "..."`` / ``=`` or ``file.path(...)``

Executable source is separated from immutable appended provenance at the unique
canonical ``# EXECUTION LOG`` boundary. Exact prohibited-root residue in the log
is informational; residue in executable source is an audit finding.

Exit codes:
    0  MATCH: all in-scope files passed.
    1  DIVERGED: in-scope audit findings.
    2  Invalid invocation or unavailable in-scope evidence.

A pass is deliberately bounded: it establishes only that the exact prohibited
root string is absent from executable source and that every in-scope script has
one canonical, statically resolvable ``PROJECT_DIR`` assignment equal to the
expected root. It does not prove arbitrary dynamically constructed paths safe.
"""

import argparse
import ast
import json
import re
import unicodedata
from pathlib import Path


EXIT_MATCH = 0
EXIT_FINDINGS = 1
EXIT_UNAVAILABLE = 2
SUPPORTED_EXTENSIONS = (".py", ".R")
EXECUTION_LOG_BOUNDARY = "# EXECUTION LOG"

PYTHON_PATH_PATTERN = re.compile(
    r"""^(\s*PROJECT_DIR\s*=\s*Path\()(['"])((?:\\.|(?!\2).)*)\2(\).*)$"""
)
PYTHON_STRING_PATTERN = re.compile(
    r"""^(\s*PROJECT_DIR\s*=\s*)(['"])((?:\\.|(?!\2).)*)\2(\s*#.*)?$"""
)
R_STRING_PATTERN = re.compile(
    r"""^(\s*PROJECT_DIR\s*(?:<-|=)\s*)(['"])((?:\\.|(?!\2).)*)\2(\s*#.*)?$"""
)
R_FILE_PATH_PATTERN = re.compile(
    r"""^(\s*PROJECT_DIR\s*(?:<-|=)\s*file\.path\()(.+?)(\)\s*(?:#.*)?)$"""
)

BOUNDED_ASSURANCE = (
    "MATCH means the exact prohibited original root is absent from executable "
    "source and each in-scope supported script has one unique canonical "
    "PROJECT_DIR assignment that statically resolves to the expected reproduction "
    "root. Exact prohibited-root text after a unique canonical # EXECUTION LOG "
    "boundary is retained as informational immutable provenance. This bounded "
    "audit does not prove arbitrary dynamically constructed paths safe."
)


def relative_name(path, scripts_root):
    """Return a stable canonical relative name for a supported script."""
    return path.relative_to(scripts_root).as_posix()


def emit_report(
    overall,
    scripts_root,
    original_root,
    expected_root,
    files,
    requested_exclusions,
    excluded_files,
    file_assessments,
    issues,
    excluded_issues,
    informational_evidence,
):
    """Emit deterministic JSON evidence for callers and reports."""
    file_names = [relative_name(path, scripts_root) for path in files]
    excluded_names = sorted(excluded_files)
    excluded_set = set(excluded_names)
    included_names = [name for name in file_names if name not in excluded_set]
    report = {
        "utility": "audit_reproduction_paths",
        "overall": overall,
        "bounded_assurance": BOUNDED_ASSURANCE,
        "inputs": {
            "scripts_root": str(scripts_root),
            "prohibited_original_project_root": str(original_root),
            "expected_reproduction_project_root": str(expected_root),
            "requested_exclusions": list(requested_exclusions),
        },
        "supported_extensions": list(SUPPORTED_EXTENSIONS),
        "files_scanned": len(files),
        "files_in_scope": len(included_names),
        "files_excluded": len(excluded_names),
        "files": file_names,
        "scope": {
            "included_files": included_names,
            "excluded_files": excluded_names,
        },
        "file_assessments": file_assessments,
        "issues": issues,
        "excluded_issues": excluded_issues,
        "informational_evidence": informational_evidence,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


def find_script_files(scripts_root):
    """Return supported scripts in stable project-relative order."""
    files = list(scripts_root.rglob("*.py"))
    files.extend(scripts_root.rglob("*.R"))
    return sorted(files, key=lambda path: relative_name(path, scripts_root))


def contains_control_character(value):
    """Return whether a CLI path contains a Unicode control character."""
    return any(unicodedata.category(character) == "Cc" for character in value)


def resolve_literal_path(value):
    """Resolve an absolute literal path without requiring it to exist."""
    candidate = Path(value)
    if not candidate.is_absolute():
        return None, "relative paths depend on runtime working directory"
    return candidate.resolve(strict=False), None


def parse_quoted_literal(quote, encoded_value):
    """Decode the common Python/R quoted-literal subset used by the normalizer."""
    try:
        value = ast.literal_eval(f"{quote}{encoded_value}{quote}")
    except (SyntaxError, ValueError) as exc:
        return None, f"quoted path is not a valid static literal: {exc}"
    if not isinstance(value, str):
        return None, "quoted path did not resolve to a string"
    return value, None


def resolve_quoted_path(quote, encoded_value):
    """Decode and resolve a canonical quoted path."""
    value, decoding_error = parse_quoted_literal(quote, encoded_value)
    if decoding_error is not None:
        return None, decoding_error
    return resolve_literal_path(value)


def parse_r_file_path(arguments):
    """Resolve canonical R file.path arguments when every component is literal."""
    try:
        values = ast.literal_eval(f"({arguments},)")
    except (SyntaxError, ValueError) as exc:
        return None, f"file.path arguments are not static quoted literals: {exc}"

    if not values or not all(isinstance(value, str) for value in values):
        return None, "file.path arguments must be one or more static quoted strings"

    candidate = Path(values[0])
    for value in values[1:]:
        candidate = candidate / value
    if not candidate.is_absolute():
        return None, "relative file.path values depend on runtime working directory"
    return candidate.resolve(strict=False), None


def canonical_assignment(script_path, line, line_number):
    """Return canonical assignment evidence for one executable source line."""
    match = None
    style = None
    resolved = None
    resolution_error = None

    if script_path.suffix == ".py":
        match = PYTHON_PATH_PATTERN.match(line)
        if match:
            style = "python_path"
            path_suffix = match.group(4)[1:].strip()
            safe_suffix = re.fullmatch(
                r"(?:(?:\.resolve\(\)|\.absolute\(\))\s*)?(?:#.*)?",
                path_suffix,
            )
            if safe_suffix is None:
                resolution_error = (
                    "Path expression has a non-canonical suffix that can change "
                    f"the assigned root: {path_suffix}"
                )
            else:
                resolved, resolution_error = resolve_quoted_path(
                    match.group(2), match.group(3)
                )
        else:
            match = PYTHON_STRING_PATTERN.match(line)
            if match:
                style = "python_string"
                resolved, resolution_error = resolve_quoted_path(
                    match.group(2), match.group(3)
                )

    if script_path.suffix == ".R":
        match = R_STRING_PATTERN.match(line)
        if match:
            style = "r_string"
            resolved, resolution_error = resolve_quoted_path(
                match.group(2), match.group(3)
            )
        else:
            match = R_FILE_PATH_PATTERN.match(line)
            if match:
                style = "r_file_path"
                resolved, resolution_error = parse_r_file_path(match.group(2).strip())

    if match is None:
        return None

    return {
        "line": line_number,
        "text": line,
        "style": style,
        "resolved_root": str(resolved) if resolved is not None else None,
        "resolution_error": resolution_error,
    }


def audit_file(script_path, scripts_root, prohibited_root, expected_root):
    """Return blocking issues and informational evidence for one script."""
    relative_path = relative_name(script_path, scripts_root)
    try:
        text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return (
            [
                {
                    "code": "SCRIPT_UNREADABLE",
                    "file": relative_path,
                    "message": f"Supported script could not be read as UTF-8: {exc}",
                    "evidence": [
                        {
                            "line": None,
                            "text": None,
                            "detail": (
                                "Line evidence is unavailable because the script "
                                "could not be read."
                            ),
                        }
                    ],
                }
            ],
            [],
        )

    all_lines = text.splitlines()
    boundary_lines = [
        line_number
        for line_number, line in enumerate(all_lines, start=1)
        if line == EXECUTION_LOG_BOUNDARY
    ]
    if len(boundary_lines) > 1:
        return (
            [
                {
                    "code": "AMBIGUOUS_EXECUTION_LOG_BOUNDARY",
                    "file": relative_path,
                    "message": (
                        "Multiple canonical # EXECUTION LOG boundaries were found; "
                        "executable source cannot be separated from immutable log "
                        "provenance safely."
                    ),
                    "evidence": [
                        {"line": line_number, "text": EXECUTION_LOG_BOUNDARY}
                        for line_number in boundary_lines
                    ],
                }
            ],
            [],
        )

    if boundary_lines:
        boundary_line = boundary_lines[0]
        source_lines = all_lines[: boundary_line - 1]
        log_lines = all_lines[boundary_line:]
        log_start_line = boundary_line + 1
    else:
        boundary_line = None
        source_lines = all_lines
        log_lines = []
        log_start_line = None

    prohibited_text = str(prohibited_root)
    source_residues = []
    assignments = []
    for line_number, line in enumerate(source_lines, start=1):
        if prohibited_text in line:
            source_residues.append({"line": line_number, "text": line})
        assignment = canonical_assignment(script_path, line, line_number)
        if assignment is not None:
            assignments.append(assignment)

    log_residues = []
    if log_start_line is not None:
        for line_number, line in enumerate(log_lines, start=log_start_line):
            if prohibited_text in line:
                log_residues.append({"line": line_number, "text": line})

    informational_evidence = []
    if log_residues:
        informational_evidence.append(
            {
                "code": "ORIGINAL_ROOT_LOG_RESIDUE",
                "file": relative_path,
                "message": (
                    "Exact prohibited original project root appears in immutable "
                    "historical execution-log provenance. Log-section residue does "
                    "not block the audit; executable source is assessed separately."
                ),
                "boundary_line": boundary_line,
                "evidence": log_residues,
            }
        )

    issues = []
    if source_residues:
        issues.append(
            {
                "code": "ORIGINAL_ROOT_RESIDUE",
                "file": relative_path,
                "message": (
                    "Exact prohibited original project root remains in executable "
                    "script source."
                ),
                "evidence": source_residues,
            }
        )

    if not assignments:
        issues.append(
            {
                "code": "MISSING_PROJECT_DIR_ASSIGNMENT",
                "file": relative_path,
                "message": "No canonical PROJECT_DIR assignment was found in executable source.",
                "evidence": [
                    {
                        "line": 1,
                        "line_end": max(1, len(source_lines)),
                        "text": None,
                        "detail": "Every executable source line was scanned.",
                    }
                ],
            }
        )
        return issues, informational_evidence

    if len(assignments) > 1:
        issues.append(
            {
                "code": "AMBIGUOUS_PROJECT_DIR_ASSIGNMENT",
                "file": relative_path,
                "message": (
                    "Multiple canonical PROJECT_DIR assignments were found in "
                    "executable source; the audit does not trust the first assignment."
                ),
                "evidence": assignments,
            }
        )
        return issues, informational_evidence

    assignment = assignments[0]
    if assignment["resolved_root"] is None:
        issues.append(
            {
                "code": "UNRESOLVABLE_PROJECT_DIR_ASSIGNMENT",
                "file": relative_path,
                "message": "Canonical PROJECT_DIR assignment is not statically resolvable.",
                "evidence": [assignment],
            }
        )
    elif Path(assignment["resolved_root"]) != expected_root:
        issues.append(
            {
                "code": "WRONG_PROJECT_DIR_ASSIGNMENT",
                "file": relative_path,
                "message": "Canonical PROJECT_DIR does not resolve to the expected root.",
                "evidence": [assignment],
            }
        )

    return issues, informational_evidence


def invalid_exclusion_issue(requested_path, detail):
    """Build one deterministic invalid-scope issue."""
    return {
        "code": "INVALID_EXCLUSION",
        "file": requested_path or None,
        "message": (
            "Each --exclude value must be a unique canonical relative path to an "
            "existing supported script beneath scripts_root."
        ),
        "evidence": [{"requested_exclusion": requested_path, "detail": detail}],
    }


def validate_exclusions(requested_exclusions, scripts_root, script_files):
    """Validate exact repeatable exclusions and return canonical relative names."""
    available = {
        relative_name(script_path, scripts_root): script_path
        for script_path in script_files
    }
    validated = []
    seen = set()

    for requested_path in requested_exclusions:
        if contains_control_character(requested_path):
            return None, invalid_exclusion_issue(
                requested_path, "The exclusion contains a control character."
            )
        components = requested_path.split("/")
        if (
            not requested_path
            or requested_path.startswith("/")
            or "\\" in requested_path
            or any(component in ("", ".", "..") for component in components)
        ):
            return None, invalid_exclusion_issue(
                requested_path,
                "The exclusion is not a canonical POSIX-style relative path.",
            )
        if requested_path in seen:
            return None, invalid_exclusion_issue(
                requested_path, "The same exclusion was supplied more than once."
            )
        if Path(requested_path).suffix not in SUPPORTED_EXTENSIONS:
            return None, invalid_exclusion_issue(
                requested_path, "The exclusion does not name a supported .py or .R file."
            )
        if requested_path not in available:
            return None, invalid_exclusion_issue(
                requested_path,
                "No supported file exists at that exact relative path.",
            )

        candidate = available[requested_path]
        try:
            resolved_candidate = candidate.resolve(strict=True)
            resolved_candidate.relative_to(scripts_root)
        except (OSError, RuntimeError, ValueError) as exc:
            return None, invalid_exclusion_issue(
                requested_path,
                f"The exclusion does not resolve to an available file under scripts_root: {exc}",
            )
        if not resolved_candidate.is_file():
            return None, invalid_exclusion_issue(
                requested_path, "The exclusion does not resolve to a regular file."
            )

        seen.add(requested_path)
        validated.append(requested_path)

    return sorted(validated), None


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read-only post-normalization audit of canonical PROJECT_DIR assignments "
            "and exact original-root residue in executable Python/R source."
        ),
        epilog=(
            "Exit codes: 0=MATCH, 1=DIVERGED, 2=invalid invocation or unavailable "
            "evidence. A match is bounded and does not prove dynamically constructed "
            "paths safe."
        ),
    )
    parser.add_argument("scripts_root", help="Root containing decompiled .py and .R scripts")
    parser.add_argument(
        "original_project_root", help="Exact absolute original project root to prohibit"
    )
    parser.add_argument(
        "expected_reproduction_root", help="Expected absolute reproduction project root"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="CANONICAL_RELATIVE_SCRIPT_PATH",
        help=(
            "Exclude one existing .py or .R file by exact canonical path relative to "
            "scripts_root; repeat for multiple files"
        ),
    )
    args = parser.parse_args()

    raw_scripts_root = Path(args.scripts_root)
    raw_original_root = Path(args.original_project_root)
    raw_expected_root = Path(args.expected_reproduction_root)
    requested_exclusions = list(args.exclude)

    if not raw_original_root.is_absolute() or not raw_expected_root.is_absolute():
        emit_report(
            "NOT DIRECTLY VERIFIED",
            raw_scripts_root.resolve(strict=False),
            raw_original_root,
            raw_expected_root,
            [],
            requested_exclusions,
            [],
            [],
            [
                {
                    "code": "INVALID_ROOT_ARGUMENT",
                    "file": None,
                    "message": "Original and expected project roots must be absolute paths.",
                    "evidence": [],
                }
            ],
            [],
            [],
        )
        return EXIT_UNAVAILABLE

    scripts_root = raw_scripts_root.resolve(strict=False)
    original_root = raw_original_root.resolve(strict=False)
    expected_root = raw_expected_root.resolve(strict=False)

    if original_root == expected_root:
        emit_report(
            "NOT DIRECTLY VERIFIED",
            scripts_root,
            original_root,
            expected_root,
            [],
            requested_exclusions,
            [],
            [],
            [
                {
                    "code": "INVALID_ROOT_ARGUMENT",
                    "file": None,
                    "message": (
                        "Prohibited original root and expected reproduction root must differ."
                    ),
                    "evidence": [],
                }
            ],
            [],
            [],
        )
        return EXIT_UNAVAILABLE

    if not scripts_root.is_dir():
        emit_report(
            "NOT DIRECTLY VERIFIED",
            scripts_root,
            original_root,
            expected_root,
            [],
            requested_exclusions,
            [],
            [],
            [
                {
                    "code": "SCRIPTS_ROOT_UNAVAILABLE",
                    "file": None,
                    "message": "Scripts root is not an available directory.",
                    "evidence": [{"path": str(scripts_root)}],
                }
            ],
            [],
            [],
        )
        return EXIT_UNAVAILABLE

    try:
        script_files = find_script_files(scripts_root)
    except OSError as exc:
        emit_report(
            "NOT DIRECTLY VERIFIED",
            scripts_root,
            original_root,
            expected_root,
            [],
            requested_exclusions,
            [],
            [],
            [
                {
                    "code": "SCRIPTS_SCAN_UNAVAILABLE",
                    "file": None,
                    "message": f"Scripts tree could not be scanned: {exc}",
                    "evidence": [{"path": str(scripts_root)}],
                }
            ],
            [],
            [],
        )
        return EXIT_UNAVAILABLE

    if not script_files:
        emit_report(
            "DIVERGED",
            scripts_root,
            original_root,
            expected_root,
            [],
            requested_exclusions,
            [],
            [],
            [
                {
                    "code": "NO_SUPPORTED_SCRIPTS",
                    "file": None,
                    "message": "No supported .py or uppercase .R scripts exist beneath the root.",
                    "evidence": [{"path": str(scripts_root)}],
                }
            ],
            [],
            [],
        )
        return EXIT_FINDINGS

    excluded_files, exclusion_error = validate_exclusions(
        requested_exclusions, scripts_root, script_files
    )
    if exclusion_error is not None:
        emit_report(
            "NOT DIRECTLY VERIFIED",
            scripts_root,
            original_root,
            expected_root,
            script_files,
            requested_exclusions,
            [],
            [],
            [exclusion_error],
            [],
            [],
        )
        return EXIT_UNAVAILABLE

    excluded_set = set(excluded_files)
    included_files = [
        script_path
        for script_path in script_files
        if relative_name(script_path, scripts_root) not in excluded_set
    ]
    if not included_files:
        emit_report(
            "NOT DIRECTLY VERIFIED",
            scripts_root,
            original_root,
            expected_root,
            script_files,
            requested_exclusions,
            excluded_files,
            [],
            [
                {
                    "code": "EMPTY_AUDIT_SCOPE",
                    "file": None,
                    "message": "Validated exclusions leave no supported script in scope.",
                    "evidence": [{"excluded_files": excluded_files}],
                }
            ],
            [],
            [],
        )
        return EXIT_UNAVAILABLE

    file_assessments = []
    issues = []
    excluded_issues = []
    informational_evidence = []

    for script_path in script_files:
        file_name = relative_name(script_path, scripts_root)
        scope = "EXCLUDED" if file_name in excluded_set else "IN_SCOPE"
        file_issues, file_information = audit_file(
            script_path,
            scripts_root,
            original_root,
            expected_root,
        )
        if any(issue["code"] == "SCRIPT_UNREADABLE" for issue in file_issues):
            assessment = "NOT DIRECTLY VERIFIED"
        elif file_issues:
            assessment = "DIVERGED"
        else:
            assessment = "MATCH"

        file_assessments.append(
            {
                "file": file_name,
                "scope": scope,
                "assessment": assessment,
                "issues": file_issues,
                "informational_evidence": file_information,
            }
        )

        scoped_information = [
            {**item, "scope": scope} for item in file_information
        ]
        informational_evidence.extend(scoped_information)
        if scope == "EXCLUDED":
            excluded_issues.extend(file_issues)
        else:
            issues.extend(file_issues)

    if any(issue["code"] == "SCRIPT_UNREADABLE" for issue in issues):
        overall = "NOT DIRECTLY VERIFIED"
        exit_code = EXIT_UNAVAILABLE
    elif issues:
        overall = "DIVERGED"
        exit_code = EXIT_FINDINGS
    else:
        overall = "MATCH"
        exit_code = EXIT_MATCH

    emit_report(
        overall,
        scripts_root,
        original_root,
        expected_root,
        script_files,
        requested_exclusions,
        excluded_files,
        file_assessments,
        issues,
        excluded_issues,
        informational_evidence,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
