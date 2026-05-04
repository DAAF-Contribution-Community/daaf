# 9. Logging, Audit Trail, and Session Management

**Classification: DAAF-BUILT** -- Claude Code provides JSONL session transcripts
and the hook lifecycle events through which observability code executes. DAAF
designed and built everything else: the file-first execution protocol with
`run_with_capture.sh`, the immutable script versioning convention, the Inline
Audit Trail comment standard, the structured audit log, the output scanner, the
session archiver (474 lines of jq-powered JSONL-to-Markdown conversion), crash
recovery, log collection, and the interactive log viewer.

**Criticality:** HIGH | **Interdependencies:** 5

---

## Design Intent

An AI coding agent, left to its defaults, executes Python interactively,
produces ephemeral output that vanishes when the session ends, and leaves no
record of what was tried, what failed, or why decisions were made. A human
reviewer who arrives after the fact finds finished data files with no provenance
chain connecting them back to the analytical choices that produced them.

DAAF's logging and audit trail system exists to close this gap. The design goal:
**every analytical operation must exist as a permanent, self-contained,
human-readable artifact that captures the code, the output, the metadata, and
the reasoning -- in a form that cannot be separated or lost.**

This requires solving four problems:

1. **Ephemeral execution** -- Interactive Python leaves no permanent record.
   DAAF needs every operation to be a script on disk with captured output.
2. **Lost failure history** -- Editing a failed script to fix it destroys the
   record of what failed and why. DAAF needs the complete history of attempts.
3. **Opaque code** -- Code without inline documentation cannot be audited
   without re-running it. DAAF needs every transformation to explain its intent,
   reasoning, and assumptions in the source itself.
4. **Session opacity** -- Claude Code's raw JSONL transcripts are
   machine-readable but not human-reviewable. DAAF needs structured, queryable,
   human-readable records of every tool call and every session.

The first tier -- file-first execution, immutable script versioning, and the
Inline Audit Trail -- is DAAF's most distinctive contribution to reproducible
AI-assisted research. No surveyed harness provides anything equivalent. The
second tier -- the audit log, output scanner, session archiver, and log viewer
-- provides operational observability on top of Claude Code's hook
infrastructure.

---

## What It Does

The system provides six capabilities:

1. **File-first execution** -- Every Python operation is written as a script
   file, executed through a wrapper that captures stdout/stderr, and archived
   with the output appended directly to the script. No ephemeral interactive
   execution is possible for coding agents.

2. **Immutable script versioning** -- Once a script has been executed and has
   output appended, it is never modified. Fixes go into versioned copies
   (`_a.py`, `_b.py`). All versions -- failed and successful -- are preserved.

3. **Inline Audit Trail** -- Every data transformation, filter, join, and
   derived column is annotated with `# INTENT:`, `# REASONING:`, and
   `# ASSUMES:` comments that make the script auditable by reading the source
   alone.

4. **Structured audit logging** -- A per-tool-call JSONL log records who made
   each call, when, with what tool, targeting what resource, from which model
   and DAAF version.

5. **Session archiving** -- Complete session transcripts are archived with
   human-readable Markdown renderings, including subagent discovery and crash
   recovery for sessions that terminated abnormally.

6. **Log viewing** -- An interactive HTML viewer provides timeline-based
   exploration of archived sessions with subagent drill-down and file preview.

---

## Current Realization on Claude Code

### File-First Execution Protocol (DAAF-Built)

This is DAAF's signature reproducibility feature. Claude Code does not provide
file-first execution; it is entirely a DAAF invention enforced through three
independent layers.

**The design problem.** Claude Code can execute Python interactively via the
Bash tool: `python3 -c "import pandas; ..."` runs, the output appears in the
conversation, but nothing is written to disk. When the session ends, that
computation is gone -- no script to review, no output to verify, no metadata to
trace.

**The solution: write-execute-capture.** DAAF mandates a three-step pattern for
every Python operation:

1. **WRITE** -- The agent writes a complete Python script to the appropriate
   `scripts/` directory using the Write tool.
2. **EXECUTE** -- The agent runs the script through DAAF's capture wrapper:
   `bash /daaf/scripts/run_with_capture.sh /path/to/script.py`
3. **CAPTURE** -- The wrapper automatically appends the complete stdout/stderr
   output to the script file itself, creating a single self-contained artifact.

**The capture mechanism: `run_with_capture.sh`.** This shell script is the
mechanical heart of file-first execution. It executes
`python3 "$SCRIPT_PATH" 2>&1 | tee "$TEMP_LOG"` (merging stderr into stdout,
displaying output in the terminal while writing to a temp file), captures the
Python process's exit code via `PIPESTATUS[0]`, records duration, and appends
the complete output to the script file as Python comments:

```
# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-05-01 14:30:00 UTC
# Command: python3 /daaf/research/.../scripts/stage7_transform/01_join-data.py
# Duration: 12s
# Exit code: 0
#
# --- STDOUT ---
# Loaded 15,432 rows from schools.parquet
# Joined with poverty data: 14,891 rows matched (96.5%)
# CP3 PASSED: join completeness > 95%
# Saved to analysis_data.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
```

Every output line is prefixed with `# ` by `sed 's/^/# /'`, so the file
remains valid Python after the log is appended. The result is a single file that
is simultaneously the source code, the complete output, and the execution
metadata.

**Re-run protection.** Before executing, `run_with_capture.sh` checks whether
the script already contains an execution log:

```bash
if grep -q "^# EXECUTION LOG" "$SCRIPT_PATH"; then
    echo "WARNING: Script already has an execution log."
    exit 1
fi
```

If a log is present, execution is refused. The agent must create a versioned
copy for any modifications. This enforces immutability: once output is appended,
the script is a sealed artifact.

**Three enforcement layers (defense-in-depth).** DAAF enforces the file-first
protocol through three independent mechanisms, because no single mechanism is
sufficient:

| Layer | Mechanism | What It Prevents | Failure Mode |
|-------|-----------|------------------|--------------|
| **Instructions** | CLAUDE.md behavioral rules | Tells all agents to never execute Python interactively | Soft: model can ignore or forget instructions under context pressure |
| **Hook** | `enforce-file-first.sh` (PreToolUse on Bash, agent-scoped) | Programmatically blocks direct `python`/`python3` Bash commands | Hard: exit code 2 blocks execution; fail-closed on errors |
| **Wrapper** | `run_with_capture.sh` | Captures output and enforces re-run protection | Hard: refuses to execute scripts with existing logs |

The first layer (CLAUDE.md) covers all agents universally but is the weakest.
The second layer (`enforce-file-first.sh`) is registered via agent frontmatter
on exactly four coding agents: research-executor, code-reviewer, debugger, and
data-ingest. The hook detects Python interpreter calls in various forms (bare,
absolute path, `env`-prefixed, `exec`-wrapped, with variable assignments) while
whitelisting legitimate uses (pip, framework utilities in `/daaf/scripts/`). On
detection, exit code 2 blocks execution with an error message explaining the
protocol.

Each layer is independently sufficient for its scope and independently fails
safely -- defense-in-depth through redundancy.

**Why append output TO the script file.** The alternative -- a separate `.log`
file -- allows code and output to be separated by accident (moved, renamed, or
deleted independently). Inline appending means **a single artifact contains
everything**: anyone who has the file has the code, the output, and the
metadata. The file is self-contained, suitable for git tracking and peer review
as a single unit.

### Immutable Script Versioning (DAAF-Built)

**The design problem.** When a script fails, the natural response is to edit it
and re-run. But editing destroys the failure record: what code was tried, what
error occurred, and what output was produced are all lost. For a research audit
trail, failure history is as important as the final success -- it documents what
was attempted, what went wrong, and what was changed to fix it.

**The solution: version on failure, never modify.** DAAF's convention is strict:

1. The original script (e.g., `01_join-data.py`) keeps its appended execution
   log, including any error output. It becomes a permanent historical artifact.
2. A revised copy is created with a letter suffix: `01_join-data_a.py`. Fixes
   are applied only to the new copy.
3. The new copy is executed through `run_with_capture.sh`, receiving its own
   execution log.
4. If the revision also fails, a further copy `01_join-data_b.py` is created.
5. After a maximum of 2 self-revisions (`_a`, `_b`), the agent must escalate
   to the user rather than continuing to iterate.
6. All versions -- failed and successful -- remain in the same directory and
   are committed to git.

The result is a complete, linear record readable as a narrative:

```
01_join-data.py       # v1: FAILED (key mismatch) -- output shows 0 matched rows
01_join-data_a.py     # v2: FAILED (type error) -- output shows cast failure
01_join-data_b.py     # v3: PASSED -- output shows 14,891 rows, CP3 PASSED
```

A reviewer can trace the full debugging history without running any code. The
2-revision cap prevents the agent from endlessly iterating on an approach that
requires human judgment.

### Inline Audit Trail / IAT (DAAF-Built)

**The design problem.** Code without documentation tells you *how* something was
computed but not *why*. A reviewer who encounters
`df = df.filter(pl.col("enrollment") > 0)` cannot determine whether this
excludes non-operational schools (intentional), removes placeholder zeros (data
quality), or accidentally drops schools with pending data (error). Without
inline documentation, auditing requires re-deriving intent from context --
which may be impossible months later.

**The solution: mandatory comment prefixes.** DAAF requires three types of
inline annotation on every data transformation:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `# INTENT:` | What the code block does and why it exists | `# INTENT: Remove non-operational schools (zero enrollment indicates closed/inactive)` |
| `# REASONING:` | Why this approach was chosen over alternatives | `# REASONING: Using > 0 rather than >= 1 for clarity; both are equivalent for integer enrollment` |
| `# ASSUMES:` | What data properties the code depends on | `# ASSUMES: enrollment column has no nulls (validated in prior step)` |

Scripts are additionally organized with section headers (`# --- Config ---`,
`# --- Load ---`, `# --- Transform ---`, `# --- Validate ---`,
`# --- Save ---`) and each section has a block-comment preamble orienting the
reader.

IAT is specified in CLAUDE.md and enforced during code review. Combined with
file-first execution and immutable versioning, it creates scripts that are fully
self-documenting: the code shows what happened, the output shows what resulted,
and the comments show why each decision was made.

### Audit Log System (DAAF-Built on PostToolUse Hook)

The audit log is a flat, append-only JSONL file at
`.claude/logs/audit.jsonl` that records every tool invocation across all
sessions. It is implemented by `audit-log.sh`, a PostToolUse hook with a
universal matcher (fires for ALL tools, orchestrator and subagents alike).

**Fields per entry (7-8):**

| Field | Source | Description |
|-------|--------|-------------|
| `timestamp` | System clock (UTC ISO 8601) | When the tool call completed |
| `session_id` | Hook JSON `.session_id` | Which session made the call |
| `tool` | Hook JSON `.tool_name` | Which tool was invoked (Read, Bash, Write, etc.) |
| `target` | Extracted per tool type | Human-readable summary: file path for Read/Write/Edit, command for Bash, pattern for Glob/Grep, description for Agent/Task, URL for WebFetch |
| `daaf_version` | `git describe --always --dirty` | Git commit hash for provenance |
| `model` | Cached from context-reporter via `/tmp/claude-model-{SESSION_ID}` | The Claude model name |
| `agent_type` | Hook JSON `.agent_type` (default: `"orchestrator"`) | Who made the call |
| `agent_id` | Hook JSON `.agent_id` (conditional) | Present only for subagent calls |

The `agent_id` field is conditionally included using a `jq` expression that adds
it only when non-empty, keeping orchestrator entries compact.

**Protection:** Deny rules block `Edit(.claude/logs/*)` and
`Write(.claude/logs/*)`. The script uses `>>` exclusively and deliberately omits
`set -e` so parsing failures never block the hook.

**Why JSONL, not SQL.** JSONL was chosen over a database for three reasons:
(1) append-only simplicity with no schema migration, no dependencies, and no
corruption risk from interrupted writes; (2) greppability -- a human can search
the log with standard Unix tools (`grep "tool.*Bash" audit.jsonl`); and
(3) zero infrastructure -- no database server to install, configure, or
maintain in the container.

### Output Scanner (DAAF-Built on PostToolUse Hook)

The output scanner (`output-scanner.sh`) is a PostToolUse hook with a universal
matcher that checks the first 10KB of every tool response for seven credential
patterns:

| Pattern | What It Detects |
|---------|----------------|
| `AKIA[0-9A-Z]{16}` | AWS Access Key IDs |
| `aws_secret_access_key` + 40-char value | AWS Secret Access Keys |
| `sk-[A-Za-z0-9_-]{20,}` | OpenAI/Anthropic API keys |
| `sk_live_` / `rk_live_` / `pk_live_` | Stripe live keys |
| `ghp_` / `gho_` / `ghs_` / `ghr_` / `github_pat_` | GitHub tokens |
| `-----BEGIN...PRIVATE KEY-----` | PEM private key blocks |
| `Bearer [50+ chars]` | Long bearer tokens |

On detection, the scanner emits a warning to stdout, which Claude Code injects
into the model's context. The scanner is **advisory only** -- it always exits 0
and never blocks. PostToolUse hooks cannot undo tool execution (the tool has
already run), so the scanner's role is to prevent the model from echoing or
committing the secret downstream. The 10KB scan limit is a performance
tradeoff: scanning multi-megabyte outputs on every tool call would degrade
performance unacceptably.

### Session Archiving (DAAF-Built on SessionEnd Hook)

Session archiving is handled by `archive-session.sh` (474 lines), the most
complex hook in DAAF, registered as a SessionEnd hook with a 60-second timeout
(the longest of all hooks, reflecting the work involved in processing large
transcripts).

**What it produces.** For each session, the archiver creates:

- `{date}_{time}_{session-short}_orchestrator.jsonl` -- Raw JSONL copy of the
  main session transcript
- `{date}_{time}_{session-short}_orchestrator.md` -- Human-readable Markdown
  rendering with formatted messages, collapsible thinking blocks, tool-specific
  formatting, and token usage summaries
- `{date}_{time}_{session-short}_subagent_{agent-id-short}.jsonl` -- Per-subagent
  transcript copies
- `{date}_{time}_{session-short}_subagent_{agent-id-short}.md` -- Per-subagent
  Markdown renderings

**Subagent discovery.** The archiver discovers subagent transcripts from Claude
Code's native file hierarchy
(`{transcript_dir}/{session-uuid}/subagents/agent-{id}.jsonl`) and reads
`.meta.json` sidecar files for agent type metadata. Each subagent gets its own
archive pair, and a summary table is appended to the orchestrator's Markdown
with agent type, ID, timestamp, duration, tool use count, and archive file
references.

**JSONL-to-Markdown conversion.** The Markdown rendering formats user messages,
assistant messages (with collapsible thinking blocks truncated at 2,000
characters), tool calls (with type-specific formatting: bash commands in code
blocks, file paths, task dispatches), and tool results (truncated at 1,000
characters).

**Idempotency.** The archiver uses file-size comparison to handle re-archival
safely: if an archive already exists for a session and the source transcript
has not grown, archival is skipped. If the source has grown (e.g., a crash
recovery archived a still-running session prematurely), the stale archive is
replaced.

**Pending log collection.** After archiving, the script processes any pending
log collection markers left by `collect_session_logs.sh`, copying session
archives to project-specific `logs/` directories. This is a deferred-copy
mechanism: the collection script marks projects for collection, and the actual
copy happens at SessionEnd when the transcript is complete.

### Crash Recovery (DAAF-Built on SessionStart Hook)

The recovery hook (`recover-session-logs.sh`) fires on SessionStart and has two
sections:

**Foreground (fast, under 1 second):** Creates log directories and appends a
one-line entry to `.claude/logs/activity.log`:
```
Session started: 2026-05-01 14:30:00 | DAAF: v1.0.0-238-g764f666 | Session: abeffb6e
```

**Background (detached subprocess):** The recovery logic runs fully detached
(`( ... ) </dev/null >/dev/null 2>&1 &` with `disown`) so it never blocks
session startup. It reconciles Claude Code's native transcript directory against
DAAF's archive directory, builds an associative array of already-archived
session IDs with their file sizes, and scans transcripts modified since the last
recovery (timestamp-gated via a `.last_recovery` touch file). For each
unarchived or grown transcript, it synthesizes a JSON payload with
`reason: "recovered"` and pipes it to `archive-session.sh`, which derives the
archive timestamp from the transcript's last entry rather than the wall clock.

The background pattern ensures the session is interactive immediately; recovery
completes silently, with results available by the next SessionEnd or
SessionStart.

### Log Collection and Viewer (DAAF-Built)

**Log collection** (`scripts/collect_session_logs.sh`) retrospectively gathers
all session transcripts referencing a specific research project into its `logs/`
directory, with a deferred-collection marker ensuring the current session's
transcript is collected at SessionEnd.

**Log viewer.** Three files cooperate: `generate_log_viewer.sh` (shell wrapper +
HTTP server), `generate_log_viewer.py` (JSONL-to-manifest converter), and
`log_viewer.html` (1,731-line self-contained HTML/CSS/JS application). The
manifest groups entries by session, merges streaming chunks, back-patches tool
results, and links subagent transcripts to dispatch points. The viewer renders a
horizontal timeline with subagent bars, clickable blocks for detail views, and a
file preview panel.

---

## Design Choices and Rationale

The most important design choices are documented inline above, in the subsection
where each feature is described. This section collects the key rationales for
quick reference.

**Why append output TO the script file** rather than a separate `.log` file: a
single artifact cannot be accidentally separated. One file contains the code,
the output, and the metadata -- there is no possibility of orphaned logs or
mismatched code-output pairs.

**Why three enforcement layers for file-first:** Instructions can be ignored
under context pressure. The hook is scoped to four coding agents and does not
cover the orchestrator. The wrapper requires voluntary use. Together, the three
layers provide overlapping coverage where each compensates for the others' gaps.

**Why re-run protection exists:** Without it, executing a script twice would
double-append output, corrupting the log. The `^# EXECUTION LOG` check
maintains the one-to-one correspondence between a script file and a single
execution event.

**Why JSONL, not SQL for the audit log:** (1) Append-only simplicity -- no
schema, no dependencies, no corruption from interrupted writes; (2) greppability
with standard Unix tools; (3) zero infrastructure in the container.

**Why JSONL-to-Markdown conversion for session archives:** Human researchers
need a format readable in any text editor or Markdown viewer, not raw JSONL
requiring specialized tooling.

**Why crash recovery runs as a detached background process:** Recovery may
process multiple orphaned transcripts; running synchronously would delay session
startup. The detached subprocess ensures immediate interactivity.

---

## Replication Specification

### File-First Execution Protocol

**Required capabilities:** Script file creation before execution; command
execution mechanism that can invoke a wrapper script; pre-execution interception
(PreToolUse equivalent) scoped to specific agent types with blocking semantics;
a wrapper that captures stdout/stderr and appends to the source file.

**Acceptance criteria:** No coding agent can execute Python interactively. Every
executed script contains its own output. Re-executing a script with an existing
log fails with a clear error. The enforcement hook fails closed.

**Degraded-mode options:** If pre-execution interception is unavailable, the
wrapper's re-run protection plus strong instructions provide partial coverage.
Output can alternatively write to a sidecar `.log` file, losing the
single-artifact property but preserving traceability.

### Immutable Script Versioning

**Acceptance criteria:** No script with an execution log is ever modified. Each
revision produces an independent file with its own log. All versions remain in
the same directory. Maximum 2 self-revisions before escalation.

### Inline Audit Trail

**Acceptance criteria:** Every data transformation has INTENT, REASONING, and
ASSUMES annotations. Scripts are comprehensible to a domain expert reading the
source alone.

### Audit Log

**Required capabilities:** Post-execution hook for all tool calls; structured
JSON input with tool name, session ID, agent identity; append-only file writes;
permission system preventing AI from editing log files.

**Acceptance criteria:** Every tool call produces a log entry with timestamp,
session ID, tool, target, version, model, and agent identity. The AI cannot
modify or delete entries.

### Session Archiving

**Required capabilities:** Session lifecycle event (SessionEnd equivalent);
access to the raw transcript; subagent transcript discovery; structured text
conversion.

**Acceptance criteria:** Every session produces raw and human-readable archives.
Subagent transcripts are discovered and archived alongside the orchestrator.
Archiving is idempotent. Abnormally terminated sessions are recovered on next
SessionStart.

---

## Harness Landscape

File-first execution, immutable script versioning, and the Inline Audit Trail
have no equivalents in any surveyed harness. These are purely DAAF conventions
that must be reimplemented as instructions, hooks, and wrapper scripts on any
target platform.

For the audit log and session archiving, the harness landscape is more
favorable. Any harness with PostToolUse hooks can implement an audit logger.
Codex provides session transcript access and could support archiving. OpenCode's
hook system (4 of 5 event types) could support most observability hooks. Cursor
and Windsurf have more limited hook support and would require middleware or
plugin extensions for equivalent logging.

The output scanner is straightforward to port to any harness with post-execution
hooks -- it requires only regex matching against tool output, with no
harness-specific dependencies beyond receiving the tool response content.

---

## Dependencies

**This section depends on:**
- **Section 7 (Hook System)** -- The audit log, output scanner, session
  archiver, crash recovery, and file-first enforcement hook all run as hooks
  registered through the infrastructure documented in Section 7.
- **Section 5 (Permission System)** -- Deny rules protecting `.claude/logs/*`
  and `.claude/hooks/*` prevent the AI from tampering with the audit trail or
  modifying its own enforcement scripts.
- **Section 10 (Tool System)** -- The one-command-per-Bash-call rule in
  Section 10 supports file-first execution by ensuring each Bash call is
  independently evaluated by the `enforce-file-first.sh` hook.
- **Section 3 (Instruction Loading)** -- CLAUDE.md carries the behavioral
  instructions for file-first execution, immutable versioning, and IAT
  conventions that form the instruction layer of enforcement.

**Other sections depend on this:**
- **Section 12 (Distinctive Design Contributions)** -- File-first execution,
  immutable versioning, and IAT are featured as three of DAAF's six most
  original architectural inventions.
