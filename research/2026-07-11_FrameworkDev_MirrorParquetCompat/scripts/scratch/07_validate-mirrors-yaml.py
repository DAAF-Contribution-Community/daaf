# --- Config ---
# INTENT: Confirm mirrors.yaml still parses after adding the view-safe provenance
#   note to the huggingface coverage_notes block scalar.
# REASONING: The note contains '<utf8_view>' angle brackets and a ':' — verify these
#   are safe inside a YAML '>' folded block scalar (they should be literal text).
import yaml

path = "/daaf/.claude/skills/education-data-query/references/mirrors.yaml"

# --- Load ---
with open(path) as f:
    config = yaml.safe_load(f)

# --- Validate ---
mirrors = config["mirrors"]
assert isinstance(mirrors, list), "mirrors must be a list"
hf = mirrors[0]
assert hf["name"] == "huggingface", f"expected huggingface first, got {hf['name']}"
assert "utf8_view" in hf["coverage_notes"], "provenance note missing from coverage_notes"
assert "view-safe" in hf["coverage_notes"], "view-safe mention missing"
# confirm other keys intact
for k in ("root_url", "format", "url_template", "read_strategy", "discovery", "metadata"):
    assert k in hf, f"huggingface mirror missing key {k}"
assert mirrors[1]["name"] == "urban_csv", "second mirror should be urban_csv (priority order intact)"

# --- Summary ---
print(f"YAML parsed OK. mirror count = {len(mirrors)}")
print(f"huggingface coverage_notes chars = {len(hf['coverage_notes'])}")
print("priority order: " + ", ".join(m["name"] for m in mirrors))
print("VALIDATION PASSED")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:37:09
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/07_validate-mirrors-yaml.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# YAML parsed OK. mirror count = 2
# huggingface coverage_notes chars = 764
# priority order: huggingface, urban_csv
# VALIDATION PASSED
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
