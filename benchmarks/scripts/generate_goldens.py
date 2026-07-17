"""Generate golden checkpoint JSONL files from a bootstrap template.

Reads the bootstrap template (7 lines) and all cases.jsonl files from the
datasets directory, then produces one golden JSONL per test case with the
user prompt substituted into line 3.

Usage:
    python3 benchmarks/scripts/generate_goldens.py
    python3 benchmarks/scripts/generate_goldens.py --template /path/to/template.jsonl
    python3 benchmarks/scripts/generate_goldens.py --datasets-dir /path/to/datasets
"""

import argparse
import copy
import json
from pathlib import Path


def find_cases_files(datasets_dir):
    """Recursively find all cases.jsonl files under datasets_dir."""
    return sorted(datasets_dir.rglob("cases.jsonl"))


def load_template(template_path):
    """Load template as a list of parsed JSON records (one per line)."""
    records = []
    with open(template_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def load_cases(cases_path):
    """Load test cases from a cases.jsonl file."""
    cases = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                cases.append(json.loads(stripped))
    return cases


def generate_golden(template_records, prompt_text):
    """Create a golden checkpoint by injecting prompt_text into line 3's message.content."""
    records = copy.deepcopy(template_records)
    # Line 3 (index 2) is the user record
    records[2]["message"]["content"] = prompt_text
    return records


def write_golden(records, output_path):
    """Write golden records as a JSONL file (exactly 7 lines)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate golden checkpoint JSONL files from bootstrap template"
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("/daaf/benchmarks/golden/bootstrap_template.jsonl"),
        help="Path to the bootstrap template JSONL (default: /daaf/benchmarks/golden/bootstrap_template.jsonl)",
    )
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=Path("/daaf/benchmarks/datasets"),
        help="Root directory to search for cases.jsonl files (default: /daaf/benchmarks/datasets)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/daaf/benchmarks/golden"),
        help="Root output directory for golden files (default: /daaf/benchmarks/golden)",
    )
    args = parser.parse_args()

    # Validate inputs
    if not args.template.exists():
        raise FileNotFoundError(f"Template not found: {args.template}")
    if not args.datasets_dir.exists():
        raise FileNotFoundError(f"Datasets directory not found: {args.datasets_dir}")

    # Load template
    template_records = load_template(args.template)
    print(f"Loaded template: {args.template} ({len(template_records)} lines)")

    if len(template_records) != 7:
        raise ValueError(
            f"Expected 7 lines in template, got {len(template_records)}"
        )

    # Discover all cases.jsonl files
    cases_files = find_cases_files(args.datasets_dir)
    if not cases_files:
        print("No cases.jsonl files found. Nothing to generate.")
        return

    print(f"Found {len(cases_files)} cases.jsonl file(s):")
    for cf in cases_files:
        print(f"  {cf}")

    # Generate goldens
    summary = {}
    total = 0

    for cases_path in cases_files:
        cases = load_cases(cases_path)
        for case in cases:
            case_id = case["id"]
            category = case["category"]
            prompt = case["prompt"]

            golden_records = generate_golden(template_records, prompt)
            output_path = args.output_dir / category / f"{case_id}.jsonl"
            write_golden(golden_records, output_path)

            summary.setdefault(category, 0)
            summary[category] += 1
            total += 1

    # Print summary
    print(f"\nGenerated {total} golden checkpoint(s):")
    for category in sorted(summary):
        print(f"  {category}: {summary[category]}")


if __name__ == "__main__":
    main()
