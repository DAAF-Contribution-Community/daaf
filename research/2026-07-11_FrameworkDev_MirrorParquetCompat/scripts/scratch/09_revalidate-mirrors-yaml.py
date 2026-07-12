# --- Config ---
# INTENT: Confirm mirrors.yaml still parses after appending the R large-file
#   download-timeout note to the huggingface coverage_notes folded block scalar.
# REASONING: The appended text adds another ':' and parenthetical content and a
#   URL-ish token inside the '>' folded block — verify YAML still treats it as a
#   single literal string value and the mirror structure/priority is intact.
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
# both notes must survive in the single coverage_notes scalar
assert "utf8_view" in hf["coverage_notes"], "view-safe note missing from coverage_notes"
assert "download.file()" in hf["coverage_notes"], "R timeout note missing from coverage_notes"
assert "options(timeout" in hf["coverage_notes"], "options(timeout) mention missing"
# structure intact
for k in ("root_url", "format", "url_template", "read_strategy", "timeout", "discovery", "metadata"):
    assert k in hf, f"huggingface mirror missing key {k}"
assert hf["timeout"] == 300, f"huggingface timeout should be 300, got {hf['timeout']}"
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
# Executed: 2026-07-11 23:32:20
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/09_revalidate-mirrors-yaml.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# YAML parsed OK. mirror count = 2
# huggingface coverage_notes chars = 1345
# priority order: huggingface, urban_csv
# VALIDATION PASSED
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
