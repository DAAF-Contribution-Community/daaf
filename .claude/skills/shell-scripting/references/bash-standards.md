# Bash Standards

Comprehensive standards for writing Bash scripts in DAAF. Covers preamble rules, quoting discipline, variable handling, ShellCheck integration, signal handling, and prohibited patterns.

---

## Preamble

Every Bash script starts with exactly these two lines:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

**What each flag does:**

| Flag | Name | Behavior | Nuance |
|------|------|----------|--------|
| `-e` | errexit | Exit immediately on non-zero return | Commands in conditionals (`if cmd; then`) are automatically exempt |
| `-u` | nounset | Exit on unbound (undeclared) variables | Use `${VAR:-default}` for intentionally optional variables |
| `-o pipefail` | pipefail | Pipeline returns the exit code of the *last* failing command, not the last command | Without this, `failing_cmd \| grep foo` returns grep's exit code, hiding the failure |

**When to add `set -E`:**

Add `set -E` (errtrace) when using `trap ... ERR` inside functions or subshells. Without `-E`, ERR traps are not inherited by functions:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "ERROR on line $LINENO" >&2; exit 1' ERR
```

**Exception — hooks that must inspect failures:**

Hooks that need to examine a failure and decide whether to block or allow should not use `set -e`. Instead, use an explicit ERR trap with controlled exit codes:

```bash
#!/usr/bin/env bash
set -uo pipefail
# Deliberately omit -e: this hook inspects failures and decides exit code

trap 'echo "ERROR: unexpected failure in hook" >&2; exit 2' ERR

# ... inspection logic with explicit error handling ...
```

This pattern is used by `bash-safety.sh` and `enforce-file-first.sh` in DAAF.

---

## Quoting Discipline

Unquoted variables are the single most common source of Bash bugs. The rule is simple: **quote everything.**

### Always Quote

```bash
# Variables
echo "$var"
echo "${var}"

# Command substitutions
result="$(some_command)"

# Array expansion
for item in "${array[@]}"; do

# Paths with possible spaces
cp "$source" "$destination"
```

### Use Braces for Adjacency

```bash
# Good: braces disambiguate where the variable name ends
echo "${var}_suffix"
echo "${filename}.bak"

# Bad: shell tries to expand $var_suffix as one variable
echo "$var_suffix"
```

### Glob Safety

```bash
# Good: ./ prefix prevents filenames starting with - from being parsed as options
for f in ./*.txt; do

# Bad: a file named -rf.txt would be interpreted as an option
for f in *.txt; do
```

### Arrays for Command Arguments

When building command-line arguments dynamically, use arrays instead of string concatenation:

```bash
# Good: each element is a separate argument, properly quoted
local -a cmd_args=("--flag" "$value" "--output" "$outfile")
my_command "${cmd_args[@]}"

# Bad: word splitting and glob expansion can corrupt arguments
cmd_args="--flag $value --output $outfile"
my_command $cmd_args
```

### Separate Declaration from Assignment

When using `local` with command substitution, separate the declaration from the assignment. The `local` builtin always returns 0, masking the exit code of the command substitution:

```bash
# Good: if cmd fails, set -e catches it
local result
result=$(some_command)

# Bad: local masks the exit code — if some_command fails, $? is still 0
local result=$(some_command)
```

This is ShellCheck SC2155 and one of the most insidious Bash bugs. See `gotchas.md` for details.

---

## Variable Handling

### Readonly for Constants

```bash
readonly BASE_DIR="/daaf"
readonly MAX_RETRIES=3
```

### Default Values

```bash
# Provide a default if unset (compatible with set -u)
verbose="${VERBOSE:-0}"
config_file="${CONFIG_FILE:-./config.yml}"

# Provide a default if unset or empty
output_dir="${OUTPUT_DIR:-.}"
```

### Parameter Validation

```bash
# Require a positional argument
if [ $# -lt 1 ]; then
    echo "Usage: $(basename "$0") <input-file>" >&2
    exit 1
fi

input_file="$1"

# Validate the argument
if [ ! -f "$input_file" ]; then
    echo "ERROR: File not found: $input_file" >&2
    exit 1
fi
```

---

## Never Do

These patterns are banned in DAAF scripts:

| Pattern | Problem | Alternative |
|---------|---------|-------------|
| `eval "$cmd"` | Arbitrary code execution, injection attacks | Use arrays: `"${cmd[@]}"` |
| `` `command` `` (backticks) | Cannot nest, harder to read | `$(command)` |
| Parsing `ls` output | Breaks on spaces, newlines, special chars in filenames | `for f in ./*.ext` or `find ... -print0 \| xargs -0` |
| `$*` when you mean `"$@"` | Joins all arguments into a single string | `"$@"` preserves individual arguments |
| `[ $var = "value" ]` | Word splitting if var is empty or contains spaces | `[ "$var" = "value" ]` or `[[ $var = "value" ]]` |

---

## ShellCheck Integration

[ShellCheck](https://www.shellcheck.net/) is the standard linter for Bash scripts.

### Running ShellCheck

```bash
shellcheck -x -S warning script.sh
```

| Flag | Purpose |
|------|---------|
| `-x` | Follow `source`/`.` includes to check sourced files |
| `-S warning` | Set minimum severity to warning (skip style/info) |

### Top Findings to Watch

| Code | Description | Fix |
|------|-------------|-----|
| SC2086 | Unquoted variable | Add double quotes: `"$var"` |
| SC2046 | Unquoted command substitution | Add double quotes: `"$(cmd)"` |
| SC2155 | `local var=$(cmd)` masks return code | Separate: `local var; var=$(cmd)` |
| SC2164 | `cd` without `\|\| exit` | Add fallback: `cd "$dir" \|\| exit 1` |
| SC2006 | Backtick command substitution | Use `$(...)` instead |

### Suppressing Warnings

Only suppress with an inline comment explaining why:

```bash
# shellcheck disable=SC2034 -- variable used by sourced script
readonly MY_CONFIG="value"
```

Bare `# shellcheck disable=SCXXXX` without an explanation comment is not acceptable — the reasoning must be documented.

---

## Signal Handling and Cleanup

### Basic Cleanup Pattern

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Variables ---
TMPDIR=""

# --- Cleanup (register immediately after variables) ---
cleanup() {
    rm -f "${TMPDIR:?}/"*  # -f makes it idempotent
    rmdir "$TMPDIR" 2>/dev/null || true
}
trap cleanup EXIT

# --- Setup ---
TMPDIR="$(mktemp -d)"

# ... rest of script ...
```

**Key principles:**

1. **Place `trap` immediately after variable declarations**, before any operations that create state needing cleanup
2. **Use `trap ... EXIT`** — it fires on normal exit, errors (`set -e`), and most signals (SIGINT, SIGTERM)
3. **Create temp files with `mktemp`**, then register for cleanup immediately
4. **Make cleanup idempotent**: use `rm -f` (not `rm`), guard with `|| true` where needed
5. **Use single quotes in trap string** to defer variable expansion:

```bash
# Good: $TMPFILE expands at trap execution time (uses current value)
trap 'rm -f "$TMPFILE"' EXIT

# Bad: $TMPFILE expands at trap definition time (may be empty)
trap "rm -f $TMPFILE" EXIT
```

### ERR Trap for Diagnostics

For scripts where you want to report the failing line on unexpected errors:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "ERROR: Script failed at line $LINENO. Command: $BASH_COMMAND" >&2' ERR

# ... script body ...
```

The `-E` flag ensures the ERR trap is inherited by functions and subshells.

### Composable Scripts (DAAF_NESTED)

When one script calls another, suppress interactive features (like pause-before-exit) in the inner script:

```bash
# In the outer script:
export DAAF_NESTED=1
bash ./inner_script.sh
unset DAAF_NESTED

# In the inner script:
if [ "${DAAF_NESTED:-}" = "1" ]; then
    exit "$exit_code"
fi
# ... interactive pause logic ...
```

---

## Script Structure

Organize scripts with clear section headers:

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Config ---
readonly BASE_DIR="/daaf"
readonly MAX_RETRIES=3

# --- Functions ---
# (Keep minimal — prefer inline logic for simple scripts)

# --- Preflight ---
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found" >&2; exit 1; }

# --- Main ---
echo "[1/3] Starting operation..."
# ...
echo "[2/3] Processing..."
# ...
echo "[3/3] Finalizing..."

echo "Done."
```

### Progress Indicators

Use numbered steps for multi-step scripts so the user can track progress:

```bash
echo "[1/4] Checking prerequisites..."
echo "[2/4] Backing up current state..."
echo "[3/4] Applying changes..."
echo "[4/4] Verifying results..."
```

---

## Compliance Checklist

Use this checklist when writing or reviewing any Bash script:

| # | Item | Check |
|---|------|-------|
| 1 | Shebang is `#!/usr/bin/env bash` | First line |
| 2 | `set -euo pipefail` (add `-E` if using ERR trap in functions) | Second line |
| 3 | All variables double-quoted | No bare `$var` |
| 4 | `local` declarations separate from `$(cmd)` assignments | No `local x=$(cmd)` |
| 5 | No `eval`, no backticks, no `ls` parsing | `grep -n 'eval\|` `` ` `` |
| 6 | `trap cleanup EXIT` for any temp files or state | After variable block |
| 7 | Cleanup function is idempotent | Uses `rm -f`, `|| true` |
| 8 | ShellCheck passes with `-x -S warning` | `shellcheck -x -S warning script.sh` |
| 9 | Errors go to stderr with actionable guidance | `echo "ERROR: ..." >&2` (or `error()` helper — see `error-handling.md`) |
| 10 | Positional arguments validated with usage message | `if [ $# -lt N ]; then` |
| 11 | External dependencies checked at script start | `command -v tool` block |
| 12 | Progress steps use `[N/M]` format | Visual scan |
