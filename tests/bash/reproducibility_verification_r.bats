#!/usr/bin/env bats
# ============================================================================
# R Reproducibility Verification round-trip and fail-closed intake tests
# ============================================================================
# Exercises the canonical DAAF Stage 9 Quarto contract through decompilation,
# PROJECT_DIR normalization, historical-log stripping, captured R execution,
# and rendering. Negative cases prove malformed or unsafe archives leave no
# extracted script or success manifest. Every test uses a unique workspace
# under scripts/scratch/ and teardown removes it.
# ============================================================================

load 'test_helper'

setup() {
    command -v Rscript >/dev/null 2>&1 || skip "Rscript is not installed"

    ORIGINAL_DIR="$(pwd)"
    TEST_DIR="${REPO_ROOT}/scripts/scratch/repro-r-roundtrip-${BATS_TEST_NUMBER:-0}-$$"
    mkdir -p "${TEST_DIR}"
    cd "${TEST_DIR}" || return 1

    FIXTURE="${REPO_ROOT}/tests/fixtures/reproducibility_verification/canonical_stage9.qmd"
    DECOMPILER="${REPO_ROOT}/scripts/decompile_notebook.R"
    CANONICAL_LOG_BLOCK=$'::: {.callout-note collapse="true" title="Execution Log"}\n```\nEXECUTION LOG\nExit code: 0\n```\n:::'

    export ORIGINAL_DIR TEST_DIR FIXTURE DECOMPILER CANONICAL_LOG_BLOCK
}

teardown() {
    cd "${ORIGINAL_DIR}" || true
    rm -rf "${TEST_DIR}"
}

write_canonical_archive() {
    local notebook_path="$1"
    local source_path="$2"

    cat > "${notebook_path}" <<QMD
---
title: "Research Notebook: Decompiler Security Fixture"
format:
  html:
    toc: true
    toc-depth: 2
    code-fold: show
    embed-resources: true
    theme: cosmo
execute:
  echo: true
  eval: false
  warning: false
---

## Archived script

**Output:** \`output/security-fixture.txt\`

\`\`\`{r}
#| label: security-fixture
#| code-fold: false
#| eval: false

# --- VERBATIM COPY of scripts/${source_path} ---
cat("ARCHIVE CODE\\n")
\`\`\`

${CANONICAL_LOG_BLOCK}
QMD
}

append_canonical_bundle() {
    local notebook_path="$1"
    local source_path="$2"

    cat >> "${notebook_path}" <<QMD

## Another archived script

\`\`\`{r}
#| label: second-security-fixture
#| code-fold: false
#| eval: false

# --- VERBATIM COPY of scripts/${source_path} ---
cat("SECOND ARCHIVE CODE\\n")
\`\`\`

${CANONICAL_LOG_BLOCK}
QMD
}

replace_once() {
    local target_file="$1"
    local old_text="$2"
    local new_text="$3"

    python3 - "${target_file}" "${old_text}" "${new_text}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
old = sys.argv[2]
new = sys.argv[3]
text = path.read_text(encoding="utf-8")
if text.count(old) != 1:
    raise SystemExit(
        f"expected exactly one replacement target, found {text.count(old)}: {old!r}"
    )
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
}

assert_rejected_without_outputs() {
    local notebook_path="$1"
    local output_root="$2"
    local expected_message="$3"

    run Rscript "${DECOMPILER}" "${notebook_path}" "${output_root}"

    assert_failure
    assert_output --partial "${expected_message}"
    [ ! -e "${output_root}" ]
}

@test "canonical Quarto archive decompiles normalizes and re-executes in R" {
    local extracted_root="${TEST_DIR}/original_files/scripts"
    local extracted_script="${extracted_root}/stage5_fetch/01_write-fixture.R"
    local project_dir="${TEST_DIR}/reproduction_project"
    local repro_dir="${project_dir}/scripts/repro/stage5_fetch"
    local repro_script="${repro_dir}/01_write-fixture.R"

    run Rscript "${DECOMPILER}" "${FIXTURE}" "${extracted_root}"

    assert_success
    assert_output --partial "Found 1 script chunk(s)"
    assert_output --partial "Done. 1 scripts extracted"
    [ -f "${extracted_script}" ]
    [ -f "${extracted_root}/MANIFEST.md" ]
    grep -F 'PROJECT_DIR <- "/daaf/research/original_fixture"' "${extracted_script}"
    grep -F '# EXECUTION LOG' "${extracted_script}"
    grep -F '# ROUNDTRIP STATUS: PASSED' "${extracted_script}"
    ! grep -F 'This unmarked chunk is notebook scaffolding' "${extracted_script}"
    grep -F '**Decompiled:** 1 scripts' "${extracted_root}/MANIFEST.md"
    grep -F '## Archive Validation' "${extracted_root}/MANIFEST.md"
    grep -F '**Contract:** DAAF Stage 9 Quarto script archive' "${extracted_root}/MANIFEST.md"
    grep -F '**Bundles with canonical callout execution logs:** 1' "${extracted_root}/MANIFEST.md"

    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${extracted_root}" "${project_dir}"

    assert_success
    assert_output --partial "RESULT: 1 normalized, 0 unchanged, 0 no match"
    grep -F "PROJECT_DIR <- \"${project_dir}\"" "${extracted_script}"
    grep -F '/daaf/research/original_fixture' "${extracted_script}"

    run python3 "${REPO_ROOT}/scripts/audit_reproduction_paths.py" \
        "${extracted_root}" "/daaf/research/original_fixture" "${project_dir}"

    assert_success
    assert_output --partial '"overall": "MATCH"'
    assert_output --partial '"code": "ORIGINAL_ROOT_LOG_RESIDUE"'

    mkdir -p "${repro_dir}"
    cp "${extracted_script}" "${repro_script}"
    python3 - "${repro_script}" <<'PY'
from pathlib import Path
import sys

script_path = Path(sys.argv[1])
text = script_path.read_text(encoding="utf-8")
marker = "# EXECUTION LOG"
if marker not in text:
    raise SystemExit("historical execution log marker not found")
log_start = text.index(marker)
separator_start = text.rfind(
    "# =============================================================================",
    0,
    log_start,
)
cut_at = separator_start if separator_start >= 0 else log_start
script_path.write_text(text[:cut_at].rstrip() + "\n", encoding="utf-8")
PY

    ! grep -F '# EXECUTION LOG' "${repro_script}"

    run bash "${REPO_ROOT}/scripts/run_with_capture.sh" "${repro_script}"

    assert_success
    assert_output --partial "ROUNDTRIP STATUS: PASSED"
    [ -f "${project_dir}/output/roundtrip.txt" ]
    grep -Fx 'R RV round trip' "${project_dir}/output/roundtrip.txt"
    grep -F '# EXECUTION LOG' "${repro_script}"
    grep -F '# Exit code: 0' "${repro_script}"
}

@test "canonical Stage 9 Quarto archive renders as an audit document without evaluating archived code" {
    local archive_path="${TEST_DIR}/canonical_stage9.qmd"
    local sentinel_path="${TEST_DIR}/render-must-not-evaluate-${BATS_TEST_NUMBER}.txt"
    local archived_code

    command -v quarto >/dev/null 2>&1 || skip "Quarto is not installed"
    Rscript -e 'if (!requireNamespace("knitr", quietly = TRUE) || !requireNamespace("rmarkdown", quietly = TRUE)) quit(status = 1)' >/dev/null 2>&1 \
        || skip "knitr and rmarkdown are required to render a knitr .qmd"

    cp "${FIXTURE}" "${archive_path}"
    printf -v archived_code \
        'cat("ROUNDTRIP STATUS: PASSED\\n")\nwriteLines("ARCHIVED CODE WAS EVALUATED", "%s")' \
        "${sentinel_path}"
    replace_once \
        "${archive_path}" \
        'cat("ROUNDTRIP STATUS: PASSED\n")' \
        "${archived_code}"

    run quarto render "${archive_path}" --to html

    assert_success
    [ -f "${TEST_DIR}/canonical_stage9.html" ]
    [ ! -e "${sentinel_path}" ]
    grep -F 'VERBATIM COPY of scripts/stage5_fetch/01_write-fixture.R' \
        "${TEST_DIR}/canonical_stage9.html"
    grep -F 'ARCHIVED CODE WAS EVALUATED' "${TEST_DIR}/canonical_stage9.html"
    grep -F 'Execution Log' "${TEST_DIR}/canonical_stage9.html"
}

@test "existing extraction root is rejected without altering its sentinel or merging outputs" {
    local output_root="${TEST_DIR}/existing-output-root"
    local sentinel_path="${output_root}/sentinel.txt"
    local sentinel_before
    local sentinel_after

    mkdir -p "${output_root}"
    printf 'preserve this exact sentinel\\n' > "${sentinel_path}"
    sentinel_before="$(sha256sum "${sentinel_path}")"

    run Rscript "${DECOMPILER}" "${FIXTURE}" "${output_root}"

    assert_failure
    assert_output --partial "output extraction root already exists; refusing to merge or overwrite"
    [ -d "${output_root}" ]
    [ -f "${sentinel_path}" ]
    sentinel_after="$(sha256sum "${sentinel_path}")"
    [ "${sentinel_after}" = "${sentinel_before}" ]
    [ ! -e "${output_root}/stage5_fetch" ]
    [ ! -e "${output_root}/MANIFEST.md" ]
}

@test "generic rich-YAML Quarto document with no marker is rejected" {
    local notebook_path="${TEST_DIR}/generic.qmd"
    local output_root="${TEST_DIR}/generic-output"

    cat > "${notebook_path}" <<'QMD'
---
title: "Generic Quarto document"
format:
  html:
    toc: true
    toc-depth: 2
    code-fold: show
    embed-resources: true
    theme: cosmo
execute:
  echo: true
  eval: false
  warning: false
---

```{r}
#| eval: false
cat("This is ordinary notebook code, not a DAAF archive.\n")
```
QMD

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "no valid script bundles found"
}

@test "traversal source path is rejected without an escaped write" {
    local notebook_path="${TEST_DIR}/traversal.qmd"
    local output_root="${TEST_DIR}/traversal-output"
    local escaped_path="${output_root}/escaped.R"

    write_canonical_archive "${notebook_path}" "stage5_fetch/../escaped.R"

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "forbidden '.' or '..' component"
    [ ! -e "${escaped_path}" ]
}

@test "absolute backslash extra-depth and unsafe source paths are rejected" {
    local notebook_path
    local output_root
    local source_path
    local case_index=0
    local absolute_escape="${TEST_DIR}/absolute-escape.R"
    local -a unsafe_paths=(
        "${absolute_escape}"
        'stage5_fetch\escaped.R'
        'stage5_fetch/extra/escaped.R'
        'stage5_fetch/-unsafe.R'
        'stage5_fetch/lowercase.r'
    )

    for source_path in "${unsafe_paths[@]}"; do
        case_index=$((case_index + 1))
        notebook_path="${TEST_DIR}/unsafe-${case_index}.qmd"
        output_root="${TEST_DIR}/unsafe-output-${case_index}"
        write_canonical_archive "${notebook_path}" "${source_path}"

        run Rscript "${DECOMPILER}" "${notebook_path}" "${output_root}"

        assert_failure
        assert_output --partial "archive source"
        [ ! -e "${output_root}" ]
    done
    [ ! -e "${absolute_escape}" ]
}

@test "marker after ordinary code is rejected" {
    local notebook_path="${TEST_DIR}/marker-middle.qmd"
    local output_root="${TEST_DIR}/marker-middle-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once \
        "${notebook_path}" \
        '#| label: security-fixture' \
        $'ordinary_code <- TRUE\n#| label: security-fixture'

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "first nonblank non-option line"
}

@test "duplicate marker in one chunk is rejected" {
    local notebook_path="${TEST_DIR}/duplicate-marker.qmd"
    local output_root="${TEST_DIR}/duplicate-marker-output"
    local marker='# --- VERBATIM COPY of scripts/stage5_fetch/01_safe.R ---'

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once "${notebook_path}" "${marker}" "${marker}"$'\n'"${marker}"

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "duplicate VERBATIM COPY markers"
}

@test "archive chunk missing an Execution Log is rejected" {
    local notebook_path="${TEST_DIR}/missing-log.qmd"
    local output_root="${TEST_DIR}/missing-log-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once "${notebook_path}" "${CANONICAL_LOG_BLOCK}" ""

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "missing its immediately adjacent Execution Log"
}

@test "empty and whitespace-only archived R source bodies are rejected before output creation" {
    local notebook_path="${TEST_DIR}/empty-source.qmd"
    local output_root="${TEST_DIR}/empty-source-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once "${notebook_path}" 'cat("ARCHIVE CODE\n")' '   '

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "archive source code is empty"
}

@test "empty and whitespace-only R execution logs are rejected before output creation" {
    local notebook_path="${TEST_DIR}/empty-log.qmd"
    local output_root="${TEST_DIR}/empty-log-output"
    local empty_log_block=$'::: {.callout-note collapse="true" title="Execution Log"}\n```\n   \n```\n:::'

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once "${notebook_path}" "${CANONICAL_LOG_BLOCK}" "${empty_log_block}"

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "execution log is empty"
}

@test "all canonical R execution-log placeholder classes are rejected case-insensitively" {
    local payload
    local notebook_path
    local output_root
    local case_index=0
    local -a placeholder_payloads=(
        $'=== EXECUTION LOG ===\n  NO EXECUTION LOG FOUND!!!  '
        '[TODO]'
        '--- tBd ---'
        '# *** Generic Placeholder ***'
        'Please paste the execution log here later.'
        'COPY the complete execution log from the script later!!!'
        '(add actual execution log below later)'
        'VERBATIM COPY FROM SCRIPT.'
    )

    for payload in "${placeholder_payloads[@]}"; do
        case_index=$((case_index + 1))
        notebook_path="${TEST_DIR}/placeholder-${case_index}.qmd"
        output_root="${TEST_DIR}/placeholder-${case_index}-output"
        write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
        replace_once \
            "${notebook_path}" \
            $'EXECUTION LOG\nExit code: 0' \
            "${payload}"

        assert_rejected_without_outputs \
            "${notebook_path}" "${output_root}" \
            "placeholder rather than archived execution evidence"
    done
}

@test "substantive R execution log containing a normal TODO word is accepted" {
    local notebook_path="${TEST_DIR}/substantive-todo-log.qmd"
    local output_root="${TEST_DIR}/substantive-todo-log-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once \
        "${notebook_path}" \
        $'EXECUTION LOG\nExit code: 0' \
        $'Executed: 2026-07-16 19:00:00 UTC\nTODO checks completed successfully\nExit code: 0'

    run Rscript "${DECOMPILER}" "${notebook_path}" "${output_root}"

    assert_success
    [ -f "${output_root}/stage5_fetch/01_safe.R" ]
    [ -f "${output_root}/MANIFEST.md" ]
}

@test "archive chunk with a delayed Execution Log is rejected" {
    local notebook_path="${TEST_DIR}/delayed-log.qmd"
    local output_root="${TEST_DIR}/delayed-log-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once \
        "${notebook_path}" \
        "${CANONICAL_LOG_BLOCK}" \
        $'Narrative text is not an allowed separator.\n\n'"${CANONICAL_LOG_BLOCK}"

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "followed immediately by an Execution Log"
}

@test "malformed or mismatched Execution Log callout is rejected" {
    local notebook_path="${TEST_DIR}/malformed-log.qmd"
    local output_root="${TEST_DIR}/malformed-log-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once \
        "${notebook_path}" \
        '::: {.callout-note collapse="true" title="Execution Log"}' \
        '::: {.callout-warning collapse="false" title="Execution Log"}'

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "must use exactly the .callout-note class"
}

@test "unclosed Execution Log fence and container are rejected" {
    local fence_notebook="${TEST_DIR}/unclosed-log-fence.qmd"
    local fence_output="${TEST_DIR}/unclosed-log-fence-output"
    local container_notebook="${TEST_DIR}/unclosed-log-container.qmd"
    local container_output="${TEST_DIR}/unclosed-log-container-output"

    write_canonical_archive "${fence_notebook}" "stage5_fetch/01_safe.R"
    replace_once \
        "${fence_notebook}" \
        "${CANONICAL_LOG_BLOCK}" \
        $'::: {.callout-note collapse="true" title="Execution Log"}\n```\nEXECUTION LOG'
    assert_rejected_without_outputs \
        "${fence_notebook}" "${fence_output}" "unclosed Execution Log fence"

    write_canonical_archive "${container_notebook}" "stage5_fetch/01_safe.R"
    replace_once \
        "${container_notebook}" \
        "${CANONICAL_LOG_BLOCK}" \
        $'::: {.callout-note collapse="true" title="Execution Log"}\n```\nEXECUTION LOG\n```'
    assert_rejected_without_outputs \
        "${container_notebook}" "${container_output}" "unclosed Execution Log callout"
}

@test "duplicate Execution Log container is rejected" {
    local notebook_path="${TEST_DIR}/duplicate-log.qmd"
    local output_root="${TEST_DIR}/duplicate-log-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once \
        "${notebook_path}" \
        "${CANONICAL_LOG_BLOCK}" \
        "${CANONICAL_LOG_BLOCK}"$'\n\n'"${CANONICAL_LOG_BLOCK}"

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "duplicate Execution Log container"
}

@test "unclosed archive R chunk is rejected" {
    local notebook_path="${TEST_DIR}/unclosed-chunk.qmd"
    local output_root="${TEST_DIR}/unclosed-chunk-output"

    cat > "${notebook_path}" <<'QMD'
---
title: "Unclosed archive chunk"
format:
  html:
    toc: true
    toc-depth: 2
    code-fold: show
    embed-resources: true
    theme: cosmo
execute:
  echo: true
  eval: false
  warning: false
---

```{r}
#| code-fold: false
#| eval: false
# --- VERBATIM COPY of scripts/stage5_fetch/01_safe.R ---
cat("unclosed\n")
QMD

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "unclosed R chunk"
}

@test "duplicate source path across bundles is rejected" {
    local notebook_path="${TEST_DIR}/duplicate-source.qmd"
    local output_root="${TEST_DIR}/duplicate-source-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_duplicate.R"
    append_canonical_bundle "${notebook_path}" "stage5_fetch/01_duplicate.R"

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "duplicate archive source path"
}

@test "missing canonical YAML frontmatter is rejected" {
    local notebook_path="${TEST_DIR}/missing-yaml.qmd"
    local output_root="${TEST_DIR}/missing-yaml-output"

    cat > "${notebook_path}" <<'QMD'
# No frontmatter

```{r}
#| code-fold: false
#| eval: false
# --- VERBATIM COPY of scripts/stage5_fetch/01_safe.R ---
cat("unsafe intake\n")
```
QMD

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "frontmatter must begin on the first line"
}

@test "syntactically malformed canonical YAML is rejected" {
    local notebook_path="${TEST_DIR}/malformed-yaml.qmd"
    local output_root="${TEST_DIR}/malformed-yaml-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once "${notebook_path}" 'format:' 'format: ['

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "malformed canonical YAML frontmatter"
}

@test "missing or incorrect load-bearing canonical YAML metadata is rejected" {
    local missing_title_notebook="${TEST_DIR}/missing-title.qmd"
    local missing_title_output="${TEST_DIR}/missing-title-output"
    local wrong_echo_notebook="${TEST_DIR}/wrong-echo.qmd"
    local wrong_echo_output="${TEST_DIR}/wrong-echo-output"

    write_canonical_archive \
        "${missing_title_notebook}" "stage5_fetch/01_safe.R"
    replace_once \
        "${missing_title_notebook}" \
        'title: "Research Notebook: Decompiler Security Fixture"' \
        'subtitle: "Title deliberately omitted"'
    assert_rejected_without_outputs \
        "${missing_title_notebook}" \
        "${missing_title_output}" \
        "requires nonempty scalar title metadata"

    # The execute block is load-bearing archive semantics and remains fatal,
    # unlike the cosmetic format.html.* keys which are now non-fatal warnings.
    write_canonical_archive "${wrong_echo_notebook}" "stage5_fetch/01_safe.R"
    replace_once "${wrong_echo_notebook}" 'echo: true' 'echo: false'
    assert_rejected_without_outputs \
        "${wrong_echo_notebook}" \
        "${wrong_echo_output}" \
        "execute.echo must be true"
}

@test "cosmetically deviant but semantically valid archive decompiles with a warning" {
    local notebook_path="${TEST_DIR}/cosmetic-deviation.qmd"
    local output_root="${TEST_DIR}/cosmetic-deviation-output"
    local extracted_script="${output_root}/stage5_fetch/01_safe.R"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.R"
    replace_once "${notebook_path}" 'theme: cosmo' 'theme: flatly'
    replace_once "${notebook_path}" 'toc-depth: 2' 'toc-depth: 3'

    run Rscript "${DECOMPILER}" "${notebook_path}" "${output_root}"

    assert_success
    [ -f "${extracted_script}" ]
    [ -f "${output_root}/MANIFEST.md" ]
    assert_output --partial "Cosmetic YAML warnings"
    assert_output --partial "format.html.theme is not 'cosmo'"
    grep -F '## Cosmetic YAML Warnings' "${output_root}/MANIFEST.md"
    grep -F "format.html.theme is not 'cosmo'" "${output_root}/MANIFEST.md"
    grep -F "format.html.toc-depth is not 2" "${output_root}/MANIFEST.md"
    grep -F '## Archive Validation' "${output_root}/MANIFEST.md"
}

@test "noncanonical stage and non-R extensions are rejected" {
    local notebook_path="${TEST_DIR}/invalid-stage.qmd"
    local output_root="${TEST_DIR}/invalid-stage-output"

    write_canonical_archive "${notebook_path}" "stage4_plan/01_safe.R"
    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "noncanonical stage directory"

    notebook_path="${TEST_DIR}/invalid-extension.qmd"
    output_root="${TEST_DIR}/invalid-extension-output"
    write_canonical_archive "${notebook_path}" "stage5_fetch/01_safe.py"
    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "does not end in uppercase .R"
}

@test "archive chunks missing either required option are rejected" {
    local eval_notebook="${TEST_DIR}/missing-eval-option.qmd"
    local eval_output="${TEST_DIR}/missing-eval-option-output"
    local fold_notebook="${TEST_DIR}/missing-fold-option.qmd"
    local fold_output="${TEST_DIR}/missing-fold-option-output"

    write_canonical_archive "${eval_notebook}" "stage5_fetch/01_safe.R"
    replace_once "${eval_notebook}" '#| eval: false' '#| warning: false'
    assert_rejected_without_outputs \
        "${eval_notebook}" "${eval_output}" "requires exactly one '#| eval: false'"

    write_canonical_archive "${fold_notebook}" "stage5_fetch/01_safe.R"
    replace_once "${fold_notebook}" '#| code-fold: false' '#| echo: true'
    assert_rejected_without_outputs \
        "${fold_notebook}" "${fold_output}" \
        "requires exactly one '#| code-fold: false'"
}

@test "later invalid bundle leaves no partial scripts or manifest" {
    local notebook_path="${TEST_DIR}/late-invalid.qmd"
    local output_root="${TEST_DIR}/late-invalid-output"

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_would-be-valid.R"
    cat >> "${notebook_path}" <<'QMD'

```{r}
#| code-fold: false
#| eval: false
# --- VERBATIM COPY of scripts/stage6_clean/02_invalid.R ---
cat("missing log\n")
```
QMD

    assert_rejected_without_outputs \
        "${notebook_path}" "${output_root}" "missing its immediately adjacent Execution Log"
    [ ! -e "${output_root}/stage5_fetch/01_would-be-valid.R" ]
    [ ! -e "${output_root}/MANIFEST.md" ]
}

@test "dangling-reference analysis never evaluates notebook-derived code" {
    local notebook_path="${TEST_DIR}/no-static-eval.qmd"
    local output_root="${TEST_DIR}/no-static-eval-output"
    local sentinel_path="${TEST_DIR}/must-not-be-created.txt"
    local escaping_code
    escaping_code=$'}\nwriteLines("PWNED", "'"${sentinel_path}"$'")\nfunction() {'

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_untrusted.R"
    replace_once \
        "${notebook_path}" \
        'cat("ARCHIVE CODE\n")' \
        "${escaping_code}"

    run Rscript "${DECOMPILER}" "${notebook_path}" "${output_root}"

    assert_success
    [ -f "${output_root}/stage5_fetch/01_untrusted.R" ]
    [ -f "${output_root}/MANIFEST.md" ]
    [ ! -e "${sentinel_path}" ]
}

@test "bounded legacy details Execution Log fallback remains supported" {
    local notebook_path="${TEST_DIR}/legacy-log.qmd"
    local output_root="${TEST_DIR}/legacy-log-output"
    local extracted_script="${output_root}/stage5_fetch/01_legacy.R"
    local legacy_log_block=$'<details>\n<summary>Execution Log</summary>\n```\nEXECUTION LOG\nExit code: 0\n```\n</details>'

    write_canonical_archive "${notebook_path}" "stage5_fetch/01_legacy.R"
    replace_once \
        "${notebook_path}" "${CANONICAL_LOG_BLOCK}" "${legacy_log_block}"

    run Rscript "${DECOMPILER}" "${notebook_path}" "${output_root}"

    assert_success
    [ -f "${extracted_script}" ]
    [ -f "${output_root}/MANIFEST.md" ]
    grep -F '# EXECUTION LOG' "${extracted_script}"
    grep -F '# Exit code: 0' "${extracted_script}"
}
