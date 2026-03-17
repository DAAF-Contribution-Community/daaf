# CLAUDE.md - Data Analyst Augmentation Framework (DAAF)

## Identity

You are operating within the **Data Analyst Augmentation Framework (DAAF)**, a
domain-extensible data analysis and research orchestration system.

**If you are interacting directly with the human user and they are making any kind of request, 
you MUST FIRST invoke the `daaf-orchestrator` skill before responding and doing any work.** 
This skill contains your complete workflow, engagement modes, subagent coordination 
protocols, and quality framework. Subagents being called by the orchestrator's 
Agent tool do not need to load this skill — your behavioral protocol is in 
your agent definition file.

---

## Execution Philosophy (Universal)

These principles apply to all agents writing code in the DAAF system:

- **Iterative validation:** Execute in small, discrete increments (max 1-2
  transformations per cycle). Validate immediately after each transformation.
- **Cardinal rule:** Every transformation has a validation. No exceptions.
- **File-first execution:** You NEVER execute Python code interactively. Every
  operation follows the mandatory file-first pattern:
  1. **WRITE** complete script to the appropriate `scripts/` directory
  2. **EXECUTE** as a single Bash call with absolute paths:
     `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/{script_name}.py`
  3. **CAPTURE** — `run_with_capture.sh` appends stdout/stderr to the script file

  Interactive execution bypasses the audit trail and produces no permanent record
  that can be reviewed by code-reviewer. Never run `python script.py` directly.
  See `agent_reference/EXECUTION_CAPTURE.md` for the complete protocol.
- **Inline Audit Trail (IAT):** Every filter, join, aggregation, and derived
  column must have inline comments using `# INTENT:`, `# REASONING:`, and
  `# ASSUMES:` prefixes documenting intent, reasoning, and assumptions. Sparse
  comments make code unauditable and block QA review.
  See `agent_reference/INLINE_AUDIT_TRAIL.md`.
- **Parquet only:** Save all data files in parquet format. No CSV, no Excel.
- **Immutable script versioning:** When a script fails, the original keeps its
  appended execution log as a historical record. Fixes go into a new versioned
  copy (`_a.py`, `_b.py`, etc.). Never modify a script after its execution log
  is appended — all versions (failed and successful) are kept for audit trail.

---

## Code Style: Sequential Inline Python

All Python code produced by agents follows a **flat, sequential** style. Scripts
read top-to-bottom like lab notebooks — no function definitions, no class
hierarchies, no module abstractions.

**Rules:**
1. **No function definitions** — No `def main()`, no helper functions, no
   `if __name__ == "__main__"` guards
   - *Exceptions:* Marimo cell wrappers (`def _():`) and standalone CLI tools
     requiring argparse
2. **Inline validation** — Use `print()` and `assert` for validation, never a
   separate `validation.py` module
3. **Section separators** — Organize scripts with comment headers:
   `# --- Config ---`, `# --- Load ---`, `# --- Transform ---`,
   `# --- Validate ---`, `# --- Save ---`
4. **No type annotations** — Sequential scripts don't define function signatures
5. **No test files** — Validation is inline (`assert` + `print`), not in
   `tests/` directories

**Why this style?** Research scripts are **write-once, execute-once, archive**
artifacts — fundamentally different from application code. Functions add
cognitive overhead without providing reuse value. Sequential code is immediately
readable and self-documenting through its execution order. Combined with IAT
documentation, a human auditor can follow every decision without running the code.

---

## Context-Efficient Reading

When you are planning to use the `Read` tool to read specific sections from a Markdown file, first run the outline script to see its structure:

```bash
bash scripts/md-outline.sh <file.md>
```

Then use the line numbers from the output to make targeted `Read` calls with `offset` and `limit`:

```
Outline output example:
   44:  Methodology Specification
  149:  Must-Haves (Goal-Backward Verification)
  224:  Common Must-Have Failures
  256:  Phase 1: Discovery Results

To read only the Must-Haves section (lines 149-255):
  Read(file_path="...", offset=149, limit=107)
```

This preserves context window budget — especially important at ELEVATED utilization and above.

**When to use:** Particularly useful for files in `.claude/skills/`, `agents/`, `agent_reference/`, and project documentation (Plan files, LEARNINGS.md, STATE.md).

**When to skip:** When you genuinely need the entire document, or for files you know to be short.

---

## Boundaries & Safety

> **Safety guardrails are enforced programmatically by PreToolUse hooks and permission deny rules.** They are documented here for transparency — the hooks block violations regardless of instructions.

### Credential & Secret Protection

- You MUST NEVER read, display, or commit files matching: `.env`, `.env.*`, `*.pem`, `*.key`, `credentials*`, or `secrets/`
- You MUST NEVER output API keys, tokens, or private key material that appears in tool output — if detected, acknowledge the leak and stop
- You MUST NEVER create `.env` files or write credentials to any file

### Destructive Command Prevention

- You MUST NEVER run `rm -rf` targeting `/`, `~`, `$HOME`, `.`, `..`, or `*`
- You MUST NEVER run `git push --force`, `git reset --hard`, `git clean -f`, `git checkout .`, `git restore .`, or `git branch -D`
- You MUST NEVER run `sudo`, `su`, `chmod 777`, or `chmod u+s`
- You MUST NEVER pipe downloaded content to a shell (`curl ... | bash`)
- You MUST NEVER upload local files via `curl -d @file` or `--upload-file`
- You MUST NEVER run `docker run`, `mount`, or `chroot` inside this environment

### Repository & Remote Safety

- You MUST NOT push to any remote repository without explicit user instruction — `git push` is not in the auto-allow list and will prompt for confirmation each time
- You MUST NOT modify CI/CD pipelines, GitHub Actions workflows, or branch protection rules

### Scope Boundaries

- You SHOULD confirm before modifying files outside the `research/` and `scripts/` directories during Full Pipeline execution
- You MUST NOT expand analysis scope, change methodology, or add data sources without user approval (see daaf-orchestrator skill for behavioral boundaries)

### Defense-in-Depth Architecture

| Layer | Mechanism | What It Covers |
|-------|-----------|----------------|
| **PreToolUse Hook** | `bash-safety.sh` — exit code 2 blocks execution | Destructive commands, privilege escalation, pipe-to-shell, data exfiltration, container escape |
| **Permission Deny Rules** | `settings.json` deny list | `rm -rf`, `sudo`, `docker`, credential file reads/writes |
| **Permission Allow List** | `settings.json` allow list | Only approved tools auto-execute; everything else prompts |
| **PostToolUse Hooks** | `audit-log.sh`, `output-scanner.sh` | Audit trail, secret detection in output |
| **Context Reporting Hook** | `context-reporter.sh` | Context utilization injection for gating decisions |
| **Session Archive Hook** | `archive-session.sh` | Session transcript archiving on exit |
| **Container Isolation** | Docker with `cap_drop: ALL`, non-root user | OS-level blast radius containment |
| **`.claudeignore`** | File-level exclusion | Prevents indexing of credentials and session logs |
| **Pre-commit Hooks** | `.pre-commit-config.yaml` | Catches large files, private keys, merge conflicts at commit time |

---

## Project Conventions

### Bash Command Rule: One Command Per Call

**Rule:** Every Bash tool call must contain exactly one command. No `&&`, `;`, or `||` chaining, to better prevent running up against safety boundaries and permission triggers.

- **Wrong:** `mkdir -p /path && cp file /path && ls /path`
- **Right:** Three separate Bash calls, each with one command

**Script execution:** Use absolute paths — no `cd` required:
```
bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage5_fetch/01_fetch-ccd.py
```

### Version Control Protocol

**Every change creates new version files.** No in-place modifications.

**Version Suffix Convention:**
- Original: `2026-01-24_School_Poverty_Analysis`
- Revision 1: `2026-01-24a_School_Poverty_Analysis`
- Revision 2: `2026-01-24b_School_Poverty_Analysis`
- etc.

**All versions remain in the same folder.**

### File Naming Conventions

| File Type | Pattern | Example |
|-----------|---------|---------|
| Plan | `YYYY-MM-DD[suffix]_[Title]_Plan.md` | `2026-01-24a_School_Poverty_Analysis_Plan.md` |
| Notebook | `YYYY-MM-DD[suffix]_[Title].py` | `2026-01-24a_School_Poverty_Analysis.py` |
| Report | `YYYY-MM-DD[suffix]_[Title]_Report.md` | `2026-01-24a_School_Poverty_Analysis_Report.md` |
| Raw Data | `YYYY-MM-DD[suffix]_[source]_[description].parquet` | `2026-01-24a_ccd_schools.parquet` |
| Processed Data | `YYYY-MM-DD[suffix]_[description].parquet` | `2026-01-24a_analysis_data.parquet` |
| Figures | `YYYY-MM-DD[suffix]_[description].png` | `2026-01-24a_enrollment_trends.png` |

### Project Folder Structure

**Script Versioning:** When a script fails:
- Original `01_task.py` keeps its appended execution log as a historical record
- Revision `01_task_a.py` contains fixes + its own output
- Further revisions use `_b.py`, `_c.py`, etc. (max 2 self-revisions before escalating)
- Never modify a script after its execution log is appended — the script becomes
  an immutable audit artifact
- All versions (failed and successful) remain in the folder for traceability
- Marimo notebook only includes the final successful version

### Script Naming Convention

All executed scripts are archived in the `scripts/` folder with stage-based organization.

| Stage | Directory | Pattern | Example |
|-------|-----------|---------|---------|
| 5 (Fetch) | `scripts/stage5_fetch/` | `{step:02d}_{task-name}.py` | `01_fetch-ccd.py` |
| 6 (Clean) | `scripts/stage6_clean/` | `{step:02d}_{task-name}.py` | `01_clean-ccd.py` |
| 7 (Transform) | `scripts/stage7_transform/` | `{step:02d}_{task-name}.py` | `01_join-data.py` |
| 8 (Analysis & Viz) | `scripts/stage8_analysis/` | `{step:02d}_{task-name}.py` | `01_regression-poverty.py` |
| Debug | `scripts/debug/` | `{seq:02d}_diag-{slug}.py` | `01_diag-key-mismatch.py` |

**Step numbering:** Use the step number from the Transformation Sequence (e.g., Step 1.1 → `01`, Step 2.3 → `03`).

See `agent_reference/SCRIPT_TEMPLATE.md` for complete script template and examples.

---

## Example Project Structure

```
research/2026-01-24_School_Poverty_Analysis/
├── 2026-01-24_School_Poverty_Analysis_Plan.md
├── 2026-01-24_School_Poverty_Analysis.py
├── 2026-01-24_School_Poverty_Analysis_Report.md
├── LEARNINGS.md                                   # Session learnings (REQUIRED)
├── scripts/                                       # All executed scripts (code archive)
│   ├── run_with_capture.sh           # Copied from /daaf/scripts/ during project setup
│   ├── stage5_fetch/
│   │   ├── 01_fetch-ccd.py
│   │   ├── 02_fetch-ipeds.py
│   ├── stage6_clean/
│   │   ├── 01_clean-ccd.py
│   ├── stage7_transform/
│   │   └── 01_join-data.py
│   │   └── 02_process-data.py
│   ├── stage8_analysis/
│   │   ├── 01_regression-poverty.py
│   │   └── 02_enrollment-plot.py
│   ├── cr/                           # Code-review inspection scripts (iterative)
│   │   ├── stage5_01_cr1.py          # CR for 01_fetch-ccd.py (standard + profiling)
│   │   ├── stage5_02_cr1.py          # CR for 01_fetch-ipeds.py (standard + profiling)
│   │   ├── stage6_01_cr1.py          # CR for 01_clean-ccd.py
│   │   ├── stage7_01_cr1.py          # CR for 01_join-data.py
│   │   ├── stage7_02_cr1.py          # CR for 02_process-data.py
│   │   ├── stage7_02_cr2.py          # Additional checks for 02_process-data.py
│   │   ├── stage8_01_cra1.py          # QA4a for 01_regression-poverty.py (analysis)
│   │   ├── stage8_01_cra2.py          # Additional QA4a checks for 01_regression-poverty.py
│   │   └── stage8_02_crb1.py          # QA4b for 02_enrollment-plot.py (visualization)
│   └── debug/                                     # If debugging occurred
│       └── 01_diag-key-mismatch.py
├── data/
│   ├── raw/
│   │   ├── 2026-01-24_ccd_schools.parquet
│   │   ├── 2026-01-24_meps_poverty.parquet
│   └── processed/
│       ├── 2026-01-24_ccd_clean.parquet
│       ├── 2026-01-24_analysis.parquet
├── output/
│   ├── analysis/
│   │   └── 2026-01-24_regression_results.parquet
│   └── figures/
│       └── 2026-01-24_poverty_distribution.png
└── STATE.md                                       # Session state (REQUIRED for Full Pipeline)
```

---

## Reference Files

| File | Purpose |
|------|---------|
| `agent_reference/EXECUTION_CAPTURE.md` | File-first code execution protocol |
| `agent_reference/INLINE_AUDIT_TRAIL.md` | Script documentation standards (IAT) |
| `agent_reference/SCRIPT_TEMPLATE.md` | Script format with stage-specific examples |
| `agent_reference/PLAN_TEMPLATE.md` | Research plan template |
| `agent_reference/STATE_TEMPLATE.md` | Session state file template |
| `agent_reference/QA_CHECKPOINTS.md` | QA checkpoint definitions (QA1-QA4b) |
| `agent_reference/05_VALIDATION_CHECKPOINTS.md` | Validation checkpoint code templates |
| `agent_reference/REPORT_TEMPLATE.md` | Output report template |
| `agent_reference/08_LESSONS_LEARNED.md` | Lessons learned protocol |
| `agent_reference/01_PROTOCOLS.md` | Core orchestration protocols |
| `agent_reference/02_WORKFLOW_STAGES.md` | Workflow stage definitions |
| `agent_reference/03_SKILL_INVOCATIONS.md` | Skill invocation templates per stage |
| `agent_reference/04_BOUNDARIES.md` | Agent boundary definitions |
| `agent_reference/06_ERROR_RECOVERY.md` | Error recovery protocols |
| `agent_reference/07_CONTEXT_MANAGEMENT.md` | Context window management |
| `agent_reference/DATA_SOURCE_SKILL_TEMPLATE.md` | Data source skill authoring template |
| `agent_reference/AGENT_TEMPLATE.md` | Agent definition file template |
| `agents/README.md` | Agent index and usage guide |
