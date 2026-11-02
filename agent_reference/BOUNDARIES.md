# Boundaries Reference

This document defines what the agent should Always Do, must Ask First about, and should Never Do.

---

## Always Do

These actions are **mandatory** for every analysis task.

### Data Integrity

| Action | Rationale |
|--------|-----------|
| Validate data at every checkpoint (CP1-CP4) | Catch errors early |
| Set coded missing values to null in place during cleaning (per domain config; e.g., -1, -2, -3 for education; rows kept), so no statistic includes them | Prevent calculation errors |
| Document suppression rates and limitations | Ensure transparency |
| Save parquet for all data files | Parquet for processing |
| Check for unexpected nulls after transformations | Catch data corruption |
| Verify row counts before and after joins | Detect fan-out or data loss |

### Process

| Action | Rationale |
|--------|-----------|
| Classify engagement mode before executing | Set correct expectations |
| Create Plan document before data acquisition | Establish shared context |
| Complete Final Review (Stage 12) before delivery | Ensure quality and alignment |
| Update STATE.md with all runtime decisions and deviations | Maintain audit trail |
| Update STATE.md Runtime Risks when risks are discovered during execution | Capture issues affecting analysis validity |
| Report progress adaptively (after phases, notable events) | Keep user informed |
| Escalate immediately when data is unavailable | Per design decision |

### Code Quality

| Action | Rationale |
|--------|-----------|
| Include validation assertions in every script (the notebook archives them verbatim) | Self-documenting quality |
| Document every transformation with comments | Reproducibility |

### Documentation

| Action | Rationale |
|--------|-----------|
| Store original request verbatim in Plan | Accurate reference |
| Cite data sources properly (use domain context skill, e.g., `education-data-context`) | Academic integrity |
| Record all methodology decisions with rationale | Reproducibility |
| Version all files (never overwrite) | Audit trail |
| Include limitations section in every report | Transparency |
| Keep working files in `{PROJECT_DIR}/scripts/scratch/` (never `/tmp`, never Claude Code's scratchpad, except scratchpad staging under orchestrator `SKILL.md` § Scope Check > Read First), and move any scratch file to its named home before something outside scratch cites it | Provenance — scratch stays inside the backup and audit boundary but is never relied on; cited files live where they will be kept (CLAUDE.md § Project Conventions > Scratch Files; `SCRIPT_EXECUTION_REFERENCE.md` § Scratch Graduation Check) |

---

## Ask First Before

These actions require **explicit user approval** before proceeding.

### Scope Changes

| Action | Why Ask |
|--------|---------|
| Expanding analysis beyond original request scope | May exceed user expectations |
| Adding data sources not in original scope | Changes methodology |
| Changing methodology after Plan is created | Invalidates prior decisions |
| Switching engagement modes mid-execution | Changes deliverables |

### Resource-Intensive Operations

| Action | Why Ask |
|--------|---------|
| Queries that might return >100K records | Performance impact |
| Analyses spanning >10 years of data | Time and complexity |
| Operations requiring extended runtime | User may want to adjust |
| Pulling data from multiple sources requiring complex joins | Complexity risk |

### Structural Changes

| Action | Why Ask |
|--------|---------|
| Creating additional output formats beyond Plan | Scope creep |
| Modifying project folder structure | Affects organization |
| Adding dependencies not in standard toolkit | Environment impact |
| Creating files outside the project folder | Organization |

### Analysis Decisions

| Action | Why Ask |
|--------|---------|
| Choosing between multiple valid methodologies | User preference matters |
| Applying imputation for missing values | Methodological choice |
| Aggregating to higher level due to suppression | Changes granularity |
| Excluding populations or years | May affect conclusions |

---

## Never Do

These actions are **prohibited** under all circumstances.

### Data Security

| Prohibition | Consequence |
|-------------|-------------|
| Commit API keys, credentials, or tokens | Security breach |
| Store PII or sensitive data unencrypted | Privacy violation |
| Share data outside the research folder | Data governance |
| Expose raw data in public outputs | Privacy risk |
| Write working files to `/tmp` (redirects, `cp`/`mv`/`tee`/`mkdir`/`touch`, downloads, `sed -i`, extraction, `git clone`) | Provenance loss — `/tmp` is outside the backup and audit boundary; the `bash-safety.sh` hook and `settings.json` deny rules block the writes they can see, but not a `/tmp` path held in a variable, a program's `/tmp` output argument, or Python `tempfile`/R `tempdir()`/`mktemp` defaults inside a script (CLAUDE.md § Provenance Boundary). Correct approach: use `{PROJECT_DIR}/scripts/scratch/`, and pass it explicitly to temp-file APIs. Reading DAAF's `/tmp` coordination caches is fine — only writes are blocked |
| Modify the safety system via shell writes (`cp`/`mv`/`tee`/redirect/`sed -i`/`chmod` into `.claude/hooks/`, `.claude/logs/`, `benchmarks/harness/hooks/`, or `.claude/settings*.json`) | Bypasses the `Edit(...)` deny rules (which bind only the file-editing tools; an `Edit` rule covers `Write` too — "Edit rules apply to all built-in tools that edit files", and `Write(path)` rules "never match" (Claude Code permissions docs; verified live on 2.1.261) — so no separate `Write(...)` rule exists) and risks deregistering hooks (settings.json is the root of trust); blocked by the `bash-safety.sh` §7 anti-tampering guard. Hook/log/settings changes are **user-only** — the user applies them directly (or via a `!`-typed command). Reads and git index ops (`git add`, `git update-index --chmod=+x`) stay open |
| Set `attribution` to a boolean (`"attribution": false`) in any shared settings file (`.claude/settings.json`) | Claude Code 2.1.281 added the boolean form, but older CLIs — including DAAF's rollback target — skip a settings file that holds it, silently dropping every hook registration and deny rule. Keep the object form (`{"commit": "...", "pr": "..."}`). Checked by `FRAMEWORK_INTEGRATION_CHECKLIST.md` CC9 and a `tests/bash/settings_permissions.bats` case |
| Install or remove packages at runtime — **Python:** `pip`/`pip3`/`pipx`, `python -m pip`, `uv`/`uvx`, `easy_install`, `conda`; **R:** `R CMD INSTALL`, R-eval/in-script `install.packages()` (plus the `remotes`/`devtools`/`pak`/`renv`/`BiocManager` install verbs); **LaTeX and Quarto tools:** `tlmgr` install/update/remove, `quarto install`/`update`/`uninstall`, R's `tinytex::install_tinytex()`/`tlmgr_install()`/`tlmgr_update()` | Unreproducible drift — the container is defined by the Dockerfile and a rebuild silently reverts runtime installs. Command-line forms are blocked by the `bash-safety.sh` §8 package guard and `settings.json` deny rules; install and removal calls written *inside* a `.py`/`.R` script are blocked by `run_with_capture.sh`'s pre-execution content scan (exit 3, no log appended; read-only list-form `uv pip compile`/`list`/`freeze`/`show` calls run). Neither covers the LaTeX and Quarto tools: the root-owned TinyTeX tree makes `tlmgr install` fail, but the forms that write into the home folder are guarded only by this rule (CLAUDE.md § Runtime Package Installation), and a LaTeX package goes in the Dockerfile's `TT_PKGS` list. Correct approach: add the package to the Dockerfile and rebuild (`bash rebuild_daaf.sh` from `daaf-docker`) — preferably in the user additions block near the end of the Dockerfile, which rebuilds fast via layer caching (place it earlier only when functionally required). `uv pip list`/`show`/`freeze` and R `installed.packages()` reads stay open |

### Analysis Integrity

| Prohibition | Consequence |
|-------------|-------------|
| Violate domain governance rules (e.g., cross-state assessment comparison in education) | **NEVER valid** per domain governance |
| Skip validation checkpoints | Data quality unknown |
| Ignore LOW confidence findings without resolution | Silent failures |
| Proceed after STOP condition without user guidance | Quality compromise |
| Present suppressed data as complete | Misleading results |
| Impute without explicit documentation | Hidden assumptions |

### Process Violations

| Prohibition | Consequence |
|-------------|-------------|
| Overwrite existing version files | Loss of audit trail |
| Deliver without completing Final Review | Quality unknown |
| Execute code without understanding what it does | Risk of errors |
| Generate outputs that contradict the Plan | Inconsistent deliverables |
| Skip mode classification | Wrong deliverables |
| Create Plan before completing discovery | Incomplete context |
| Dispatch a subagent from within a subagent (nested dispatch) | Breaks orchestration integrity — all dispatch authority belongs to the orchestrator |
| Drop content the Write tool rejected as a "report file", or route around the rejection with shell writes, a script, or by creating the file with Edit (CLAUDE.md § Project Conventions > Subagent File Output). Edit is the recovery only for an already-existing file the dispatch asks you to change, never for a research version file (see "Overwrite existing version files" above) | Lost audit-trail content, or a vendor guard defeated instead of avoided |

**Dispatch-authority invariant:** Subagents never dispatch other subagents. All dispatch authority belongs to the orchestrator; a subagent that needs more work done returns that work to the orchestrator for redelegation (the early-return protocol in CLAUDE.md § Context & Session Health), rather than spawning nested subagents. This invariant is enforced on three layers: (1) the harness — `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in `settings.json` `env` makes Claude Code withhold the `Agent`/`Task` tool from every subagent (observed 2026-11-02, Claude Code 2.1.281; the Claude Code changelog says only that the setting disables nesting), so under the shipped configuration no subagent, named or generic, has a dispatch tool at all; (2) every named agent carries an explicit `tools:` list that omits `Agent`/`Task` (so it structurally cannot nest even if the depth limit were lifted); and (3) the `block-nested-dispatch.sh` PreToolUse hook, a backstop that denies any Task/Agent dispatch originating inside a subagent — covering the generic built-in types (`general-purpose`, `Plan`), which inherit `Agent`/`Task` with no DAAF-authored `tools:` list, if the spawn-depth limit is ever removed or regresses.

### Code Practices

| Prohibition | Consequence |
|-------------|-------------|
| Use bare `except:` without specific exception (Python) | Hidden errors |
| Print to stdout in production notebooks | Pollution |
| Hard-code file paths with user-specific directories | Non-portable |
| Leave debugging code in final notebooks | Unprofessional |

### File-First Execution Violations

| Prohibition | Consequence |
|-------------|-------------|
| Execute Python or R interactively before writing to a script file | No audit trail, not reproducible |
| Use `mcp__ide__executeCode` for analysis code (except quick exploration) | Hidden execution, no version control |
| Save scripts without embedded execution logs | Missing proof of what happened |
| Modify scripts after appending execution log (create new version instead) | Destroys audit trail |
| Create new Stage 9 analysis code that was not first executed as a script (the format-specific, non-transforming data inspection/display chunk is the only exception) | Unvalidated analytical logic in notebook |

**See:** Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

---

## Mode-Specific Boundaries

Different engagement modes have different boundary considerations. These **supplement** (not replace) the general boundaries above.

### Full Pipeline Mode

**Always Do:**
- Complete all five protocols in sequence
- Create plan file after receiving clarifications
- Complete Final Review (Stage 12) before delivery
- Generate all three deliverables (Plan, Notebook, Report)

**Never Do:**
- Skip any protocol
- Deliver without all three deliverables
- Proceed without resolving LOW confidence findings

---

### Data Discovery Mode, Data Lookup Mode, Ad Hoc Collaboration Mode, Revision and Extension Mode, Data Onboarding Mode

Mode-specific boundaries for these engagement modes are defined in their respective reference files:
- `.claude/skills/daaf-orchestrator/references/data-discovery-mode.md`
- `.claude/skills/daaf-orchestrator/references/data-lookup-mode.md`
- `.claude/skills/daaf-orchestrator/references/ad-hoc-collaboration-mode.md`
- `.claude/skills/daaf-orchestrator/references/revision-and-extension-mode.md`
- `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md`

---

### Synthetic Data Path (Privacy-Preserving Onboarding)

These boundaries apply whenever the Data Onboarding **sensitivity gate** has routed an engagement to the privacy-preserving synthetic-data workflow (raw data must never enter the container). They supplement the general Data Security boundaries above. See the `synthetic-data-workflow` skill for the full doctrine.

**Always Do:**
- Keep the real data out of the container. Once the synthetic path is chosen, the only artifact that crosses the boundary is the user's disclosure-controlled **profile report** (and, for T4, locally-generated synthetic rows).
- Label every synthetic artifact with its provenance. Skills built this way carry `metadata.data-provenance: synthetic-*` and a Synthetic Data Notice; reports and outputs carry the scaffold-not-substitute caveat and the "finalize against the real data" requirement.
- Treat the disclosure-safety review of the outbound profiling script (QAS-A) as a **BLOCKER** gate: `WARNING` is not a legal QAS-A verdict, and a `[NOT VERIFIED]` item is itself a BLOCKER — an emission path that could not be traced is an unproven-safe path, and a leak is irreversible once the report is shared. The disclosure-critical checks may never be declared `not_applicable`; a declaration is itself the finding. Definitions: `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints (QAS-A, QAS-B, QAS-C) and § QAS Severity Overrides (Synthetic Path).

**Never Do:**
- Request or accept raw sensitive data — raw extracts, unsuppressed cross-tabs, example values, or the fitted synthesis model — once the synthetic path is chosen. If a request would require any of these, stop and re-scope to a tier that does not.
- Attempt to reconstruct, infer, or reverse suppressed values, small cells binned to `__OTHER__`, or identifier contents from the profile report.
- Present synthetic-data results as findings, or ship a synthetic-derived skill or output without provenance labeling.

**If raw microdata is pasted into the conversation:** STOP. Do not analyze, transform, or persist it. Note that raw sensitive data was exposed inline, and redirect the user to the sensitivity gate / synthetic-data protocol (per the general "If You Catch Yourself Violating a Boundary" procedure below).

---

### Reproducibility Verification Mode

**Always Do:**
- Accept exactly one user-selected original Report and one supported DAAF Stage 9 Marimo or Quarto archive; stop on ambiguous candidates or mixed notebook formats.
- Use a new reproduction destination and a new decompiler extraction root. Never reuse, merge, or overwrite either automatically.
- Run `normalize_project_dir.py`, then run `audit_reproduction_paths.py` with one repeatable validated `--exclude <canonical-relative-script-path>` per exact pre-RV-2 script exclusion. Require global exit 0 / MATCH, computed only from in-scope files, plus each dispatched script's deterministic `file_assessments` entry as `IN_SCOPE` + `MATCH`. Keep excluded files and `excluded_issues` explicit but never count them as matches. Audit executable source before the unique canonical `# EXECUTION LOG` boundary: exact original-root residue afterward is informational `ORIGINAL_ROOT_LOG_RESIDUE`, while ambiguous boundaries fail closed. State the bounded assurance; dynamic paths are not proven safe.
- In frozen-input mode, hash copied raw files, exclude Stage 5 by explicit pre-RV-2 scope design, begin downstream, and verify raw hashes remain unchanged. Do not imply acquisition or mirrors were tested.
- Use `compare_execution_logs.py` only for shared printed metrics aligned by identity/stable context rather than position: exit 0 CONSISTENT only, 1 DIVERGED, 2 invalid invocation or input read/parse failure, and 3 INCOMPLETE/INCONCLUSIVE = NOT DIRECTLY VERIFIED, never success. Use `compare_reproduction_artifacts.py` for supported Parquet/exact-byte evidence and preserve JSON under exit 0 MATCH, 1 DIVERGED, 2 invalid/unsupported, and 3 NOT DIRECTLY VERIFIED. Its defaults bound each Parquet input to 536870912 bytes and 1000000 rows before full materialization and tolerant matching to 1000000 candidate pairs; exact-key/cardinality divergence is established before the pair limit, and duplicate assessment follows actual verification. Correct exit-2 invocations or use the separate evidence path; review figures visually and use defined inspectable representations for tables/models or mark NOT DIRECTLY VERIFIED.
- Make every reproduction copy and every `_repro_a`/`_repro_b` with the revision tool, never by hand or with a plain `cp`. To re-run a logged script, create the folder for the copy if needed (`mkdir -p`), then run `bash /daaf/scripts/create_script_revision.sh <source> <destination>`; it copies the code without the execution log. Verify no inherited log before fixes and execution.
- Grade environment evidence by language: Python runtime, Marimo, and imported package versions; R runtime, Quarto, repository/snapshot metadata, and `installed.packages()` versions. Put any diagnostic scripts in project `scripts/repro_checks/`, execute them through `run_with_capture.sh`, and retain their logs; never infer exact R versions from unversioned install lists or snapshot dates.
- Use only FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED overall, and MATCH / DIVERGED / NOT DIRECTLY VERIFIED for RV-3 rows. Any in-scope evidence gap caps the verdict at PARTIALLY REPRODUCED.

**Never Do:**
- Treat missing evidence, any comparator exit 2 or 3, or an unsupported comparison as a match; claim exact-byte identity proves semantic equivalence; or use the log helper as an artifact comparator. For the log helper, exit 2 is invalid invocation/input read/parse failure and exit 3 is INCOMPLETE/INCONCLUSIVE; for the artifact helper, exit 2 is invalid/unsupported and exit 3 is NOT DIRECTLY VERIFIED. Correct or reroute exit 2; every exit 3 remains NOT DIRECTLY VERIFIED evidence.
- Execute Stage 5 in frozen mode, relabel a design exclusion as reproduced/failed, or convert an ad hoc skip into a retroactive exclusion.
- Write or recommend runtime package-install calls while inventorying environments.

**Ask First:**
- Before excluding any script, claim, figure, artifact, finding, or required dimension. Only exact user-approved exclusions recorded before RV-2 leave verdict denominators.

**See** `reproducibility-verification-mode.md` § Boundaries for the full workflow contract.

---

### Literature Review Mode

A review commits the researcher's reading time and plan usage, and its deliverable carries their name, so every judgment call stays theirs and every check DAAF runs is recorded. These boundaries mirror `literature-review-mode.md` § Boundaries, which governs where the two differ.

**Always Do:**
- Show the level menu as written, and create the project folder before the scope check (the review plan)
- Run `lit_verify route` and copy its `ROUTE:` line verbatim into every reader and data-verifier dispatch
- Audit every reader's latest card, once, in the session that dispatched its readers, with each reader dispatch's agent ID (one per chunk), before its claims are used in a deliverable
- Run `lit_verify report` on every deliverable, and `--kind final` on the version the researcher receives, before the researcher's approval counts; the orchestrator runs every gate it does not author
- Show the reference glance list before every final deliverable while no adjudicator identity is evaluated, and record the reply with the user's words verbatim
- Give the researcher each round and final synthesis as its HTML copy (made before the round check-in and the final review), with the `.md` named as the checked source
- Record every researcher decision (key papers, full-text decisions, checklist judgments, weights, ratings, reference replies, page comparisons) in the user's own words
- Keep at most 5 readers in flight and one searcher at a time
- Update STATE.md after every dispatch return and every checkpoint reply

**Ask First Before:**
- Any paid call (Elicit, licensed Scite): the user names it, and it goes into the dispatch's SPEND APPROVED line
- Changing the protocol, the level or the stopping rule (a new protocol version)
- Reading in full a paper outside the approved key-paper list (standard level)
- More than 5 readers in flight
- Keeping a retracted paper, or a reference whose record does not match

**Never Do:**
- Dispatch the citation-adjudicator while the evaluated list holds no matching identity, or add anything to its prompt
- Type a route, a row hash, a paper key or a claim id; paraphrase or compose a user's words for `record-human`, `settle`, `screen record` or `researcher_grade`
- Cite a reference waiting for its second check, or a paper with an unconfirmed reading audit, in a final deliverable
- Average, pool or vote-count results across studies, or let wording outrun certainty
- Edit a checked card, a recorded input or an execution log; re-pack an un-ingested batch; edit `citation-adjudicator.md` between pack and ingest
- Settle a `chain_unconfirmed` audit by a page comparison
- Let the synthesizer run `lit_verify report` on its own deliverable
- Show internal codes, agent names, status codes or `settle` item ids to the user
- Let a second screener record its pass a second time after seeing the disagreement count (it records its pass once)

**Agent-specific boundaries** (each agent file's § Boundaries is the full list):
- **literature-searcher:** executes only the protocol version the dispatch names; never records a `researcher` screening pass, an `attach decision` or any `adjudications` subcommand; makes a paid call only when the dispatch's SPEND APPROVED line names it; in a second-screener pass reads nothing that can show the first screener's decisions, and the orchestrator's prompt carries none of them
- **paper-reader:** one paper per dispatch; never searches, fetches or ingests; never edits a card once `lit_verify card` has read it (a revision is a new card file); opens page images only when its model and the dispatch's ROUTE line are on the vision-validated list, and only up to the image cap
- **literature-synthesizer:** cites only references whose citation status the deliverable's kind (draft or final) allows; never pools, averages or vote-counts results; never opens a PDF; never records `researcher_grade` without the researcher's words quoted verbatim in the dispatch
- **citation-adjudicator:** reads only the one bundle its prompt names (Read is its only tool; `lit_corpus adjudications ingest` refuses the whole batch on any other Read in the audit log). The agent-scoped `adjudicator-read-scope.sh` hook (§ Defense-in-Depth Architecture) refuses every other tool call, and every Read that is not of a bundle file (`research/…/data/adjudication_bundles/{batch_id}.json`), before the call runs; it cannot tell which bundle the prompt names, so the agent's instructions and ingest's audit-log scan keep it to that one

**See** `literature-review-mode.md` § Boundaries for the full workflow contract.

---

### Framework Development Mode

**See** `framework-development-mode.md` § Boundaries for Always Do / Ask First / Never Do rules specific to framework modification workflows. Key constraints: mandatory scoping before modifications, canonical template compliance, integration checklist execution, and explicit user approval before modifying CLAUDE.md or settings.json (settings.json through the Edit tool only). Hooks are user-only: the `Edit(.claude/hooks/*)` deny rule and `bash-safety.sh` block every agent write, with or without permission, so framework work drafts a hook change in the session workspace's `drafts/` folder and gives the user the command to apply it (`ERROR_RECOVERY.md` § PreToolUse Safety-Hook Blocks).

New or changed text in any file that ships with DAAF meets `agent_reference/DOCUMENTATION_STANDARDS.md` for its audience, and cites only files that ship and public URLs (§ S4 Self-Contained).

---

### User Support Mode

User Support is DAAF's lightest mode — a read-only, conversational interaction where the orchestrator answers questions about the framework directly. No subagents by default (one rare, user-approved exception below), no workspace (fetched pages stay in the session's staging folder), no state files, no code execution (the update-conflict walkthrough's file edits and git commands are the one exception, below).

**Always Do:**
- Answer from pre-loaded documentation and framework knowledge
- Route to the appropriate mode when the user's needs evolve beyond questions
- Confirm with the user before escalating to another mode

**Ask First Before:**
- Dispatching a subagent. The one permitted dispatch is a single `search-agent` for a targeted lookup the reference index cannot answer, and it should be rare (`user-support-mode.md` § Subagent Invocation)
- Editing a conflicted file in the update-conflict walkthrough: each resolution waits for the user's approval, file by file (`user-support-mode.md` § Update Conflict Resolution Walkthrough)

**Never Do:**
- Execute code (no scripts, no Python/R, no data operations). The one exception is the update-conflict walkthrough: editing the conflicted files the user approved and running its git commands (`git status`, `git diff`, `git add <file>`, the completion command), as `user-support-mode.md` § Update Conflict Resolution Walkthrough describes
- Create a project workspace, STATE.md, LEARNINGS.md, or any project artifacts (`web_fetch.sh` artifacts, and a PDF digest's ingest and record, go to the session's staging folder, which is not a workspace: orchestrator `SKILL.md` § Scope Check > Read First)
- Dispatch coding agents (research-executor, debugger, code-reviewer, data-ingest), or any subagent other than the single `search-agent` above
- Load domain-specific data skills (User Support is framework-oriented, not data-oriented)
- Produce formal deliverables (all output is conversational)

**Commits in the update-conflict walkthrough.** CLAUDE.md § User Preferences sets "Git commit management: disabled", under which no agent runs `git commit`. The walkthrough is a deliberate exception, scoped to it alone: the user chose to resolve the update's conflicts with DAAF, and the update is not finished until the merge is committed or the rebase continued. After the user has approved the resolutions, the orchestrator runs the completion command itself (`git commit` for a merge conflict, `git rebase --continue` for a rebase conflict). The stash case never commits (`user-support-mode.md` § Update Conflict Resolution Walkthrough > Commits in this walkthrough).

**See also** `user-support-mode.md` § Boundaries for the complete boundary specification.

---

### QA-Specific Boundaries (Stages 5-8)

**Always Do:**
- Invoke code-reviewer after EVERY script execution in Stages 5-8
- Create QA scripts in `scripts/cr/` for every reviewed script
- Address BLOCKER issues before proceeding. A BLOCKER whose fix brings the code back to what the Plan already specifies (a MISALIGNED row under Methodology Alignment that a revision can correct, such as a LEFT join where the Plan says INNER) goes through revision (max 2). A methodology BLOCKER — the Plan's own methodology looks wrong for the data, or the Plan does not settle the choice — is a code-reviewer STOP with Issue Category `Methodology Conflict` and escalates to the user immediately.
- Log WARNING issues for Stage 10 aggregation
- Preserve all script versions (failed and successful) as audit trail
- Include QA script execution log in the QA script file

**Never Do:**
- Skip QA review for "simple" scripts (all scripts get QA)
- Proceed with unresolved BLOCKER issues
- Modify scripts after QA review (create new version instead)
- Create QA-of-QA loops (QA scripts themselves don't need QA review)
- Rubber-stamp scripts that passed CP validation (QA is secondary verification)
- Allow code-reviewer to directly modify execution scripts (separation of concerns)

**Ask First Before:**
- Overriding a BLOCKER with justification (rare; should escalate instead)
- Skipping QA for an entire stage (never allowed in Full Pipeline mode)
- Changing QA script naming convention

**BLOCKER Escalation:** See `ERROR_RECOVERY.md` § QA BLOCKER Recovery for the full escalation flow.

---

## Autonomous Deviation Rules

When executing Plan tasks, the agent **WILL discover work not in the plan.** This is normal. Apply these rules automatically to enable efficient execution while maintaining quality. Track all deviations for documentation.

---

### RULE 1: Auto-Fix Bugs (Always Allowed)

**Trigger:** Code doesn't work as intended (broken behavior, incorrect output, errors)

**Action:** Fix immediately, document in Plan under "Deviations Applied"

**Data Science Trigger Examples:**

| Category | Examples |
|----------|----------|
| **Wrong Query** | Polars filter using wrong column name, incorrect join key, filter condition inverted |
| **Logic Errors** | Off-by-one in row slicing, inverted condition (`>` vs `<`), wrong aggregation function |
| **Type Errors** | Filtering string column with integer, datetime vs string mismatch, float vs int division |
| **Validation Failures** | Assertion fails due to incorrect expected value, checkpoint logic wrong |
| **Reference Errors** | Using undefined variable, wrong DataFrame reference after transformation |
| **Data Corruption** | Mutation of source DataFrame, accidental column overwrite, incorrect in-place operation |

**Process:**
1. Fix the bug inline
2. Add/update validation to prevent regression
3. Verify fix works
4. Continue task
5. Track in deviations list: `[Rule 1 - Bug] [description]`

**Example:**
```python
# Plan specified:
df.filter(pl.col("year") == 2020)

# But year column is string type, agent auto-fixes to:
df.filter(pl.col("year") == "2020")

# Document: "[Rule 1 - Bug] Fixed type mismatch in year filter (string, not int)"
```

**No user permission needed.** Bugs must be fixed for correct operation.

---

### RULE 2: Auto-Add Missing Critical Functionality (Always Allowed)

**Trigger:** Code is missing essential features for correctness, data integrity, or basic operation

**Action:** Add immediately, document in Plan under "Deviations Applied"

**Data Science Trigger Examples:**

| Category | Examples |
|----------|----------|
| **Missing Null Handling** | No check for null before division, missing `.drop_nulls()` before aggregation, no handling of `-1/-2/-3` coded values |
| **No Data Validation** | No row count check after filter, no shape validation after join, missing assertion for expected columns |
| **Missing Error Handling** | No try/except around data access calls, no handling for empty DataFrame, no timeout for large queries |
| **No Pre/Post State Capture** | Transformation without capturing row count before/after, no logging of data characteristics |
| **Missing Type Coercion** | No explicit casting before comparison, missing `.cast()` for safe operations |
| **No Bounds Checking** | No validation that percentages are 0-100, no check for negative enrollment values |

**Process:**
1. Add the missing functionality inline
2. Verify it works
3. Continue task
4. Track in deviations list: `[Rule 2 - Missing Critical] [description]`

**Example:**
```python
# Plan specified transformation, agent adds validation:
pre_rows = len(df)
df = df.filter(...)
post_rows = len(df)
assert post_rows > 0, "Filter removed all rows unexpectedly"
assert post_rows >= pre_rows * 0.1, f"Filter removed {100 - (post_rows/pre_rows)*100:.1f}% of rows"

# Document: "[Rule 2 - Missing Critical] Added row count validation after filter"
```

**Critical = required for correct/secure/reproducible operation.**
**No user permission needed.** These are not "features" - they're requirements for basic correctness.

---

### RULE 3: Auto-Fix Blocking Issues (Always Allowed)

**Trigger:** Something prevents you from completing the current task

**Action:** Fix immediately to unblock, document in Plan under "Deviations Applied"

**Data Science Trigger Examples:**

| Category | Examples |
|----------|----------|
| **Missing Dependency** | `import polars` fails, missing `plotnine` package |
| **Import Errors** | Wrong import path, circular import, missing `__init__.py` |
| **Data Access Connection Issues** | Data access timeout, mirror service unavailable, mirror file path changed |
| **File Path Errors** | Parquet file not found, wrong directory structure, missing data folder |
| **Environment Issues** | Missing mirror configuration (mirrors.yaml), wrong Python/R version |
| **Data Format Issues** | Data file has unexpected encoding, parquet schema mismatch, date format parsing failure |

**Process:**
1. Fix the blocking issue
2. Verify task can now proceed
3. Continue task
4. Track in deviations list: `[Rule 3 - Blocking] [description]`

**Example:**
```python
# Task requires reading parquet but file path is wrong:
# Plan: df = pl.read_parquet("data/raw/ccd_schools.parquet")
# Actual structure has date prefix:
df = pl.read_parquet("data/raw/2026-01-31_ccd_schools.parquet")

# Document: "[Rule 3 - Blocking] Corrected parquet file path to include date prefix"
```

**No user permission needed.** Can't complete task without fixing blocker.

---

### RULE 4: Ask About Methodological Changes (Always Escalate)

**Trigger:** Fix/addition requires significant structural or methodological modification

**Action:** STOP, present to user, wait for decision

**Data Science Trigger Examples:**

| Category | Examples |
|----------|----------|
| **Changing Analysis Methodology** | Switching from mean to median aggregation, changing from cross-sectional to longitudinal approach |
| **Adding New Data Sources** | Incorporating additional dataset not in Plan, adding new mirror or data source |
| **Modifying Aggregation Approach** | Changing from school-level to district-level, altering grouping variables |
| **Changing Join Strategy** | Switching from inner join to left join, changing join keys |
| **Altering Population/Sample** | Excluding years not originally planned, filtering to different states |
| **Changing Model Specification** | Switching regression type, changing dependent/independent variables, altering model assumptions |
| **Switching Libraries** | Changing from Polars to pandas, switching visualization library |
| **Schema Changes** | Adding new columns to output, changing output data structure |
| **Imputation Decisions** | Deciding to impute missing values, choosing imputation method |

**Process:**
1. STOP current task
2. Document what you found, proposed change, why needed, impact, alternatives
3. Return to orchestrator/user with decision needed
4. WAIT for user decision
5. Continue with decision

**Example:**
```markdown
**STOP: Methodological Decision Required**

**What I Found:**
Inner join between CCD and MEPS loses 15% of schools (no poverty match).

**Proposed Change:**
Switch to left join and document unmatched schools.

**Why Needed:**
Current approach excludes schools we may want to analyze.

**Impact:**
- Changes row count from 85K to 100K
- Introduces null values in poverty columns for unmatched schools
- Affects downstream aggregations

**Alternatives:**
1. Keep inner join, document loss (current Plan)
2. Left join, exclude unmatched from calculations
3. Left join, impute poverty values for unmatched

**Recommendation:** Option 2 - Left join with explicit exclusion in calculations.

Awaiting your guidance before proceeding.
```

**User decision required.** These changes affect analysis methodology and conclusions.

---

### RULE 5: QA-Triggered Revisions (Always Execute)

**Trigger:** code-reviewer returns any BLOCKER that is not a `Methodology Conflict` STOP: its fix brings the code back to what the Plan specifies, or corrects a defect (a bug, a stub, a validation gap) without changing the method. Such a fix is not a methodology choice, so Rule 4 does not apply. A code-reviewer STOP with another Issue Category routes as `.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md` § Gate Status Translation says (`Stub Detection` and `Validation Gap` come here; `Data Corruption` goes to debugger)

**Action:** Create versioned revision, apply fix, re-execute

**QA BLOCKER Categories:**

| Category | Examples | Action |
|----------|----------|--------|
| **Correctness Issue** | Wrong join type, incorrect filter logic, type mismatch | Fix immediately via revision |
| **Validation Gap** | Missing checkpoint, inadequate invariant check | Add validation via revision |
| **Stub/Placeholder** | TODO, FIXME, pass, NotImplementedError in code | Complete implementation via revision |
| **Data Corruption** | Output has unexpected nulls, wrong row count | Fix transformation via revision |
| **Statistical Analysis Issue** | Incorrect regression specification in Stage 8 analysis, wrong model variables, invalid assumptions | Fix via revision (or escalate if methodology change needed) |
| **Methodology Conflict** | The Plan's own methodology looks wrong for the data, or the Plan does not settle the choice (code-reviewer raises a STOP with Issue Category `Methodology Conflict`) | STOP → Escalate to user (becomes Rule 4) |

**Process:**
1. Receive QA BLOCKER from code-reviewer
2. Check whether it is a methodology BLOCKER (a `Methodology Conflict` STOP) → If yes, escalate (Rule 4)
3. Create versioned revision file (`_a.py`/`_a.R`, `_b.py`/`_b.R`, etc.)
4. Apply fix as suggested by code-reviewer
5. Execute and capture output
6. Return for re-QA
7. Max 2 revision attempts; after that, escalate

**Example:**
```markdown
# QA BLOCKER: Wrong join type

## Issue
code-reviewer found: Script uses a LEFT join, but the Plan specifies an INNER join
(1:1 cardinality). The fix brings the code back to what the Plan specifies, so this
is a revision, not a methodology escalation.

## Action (Rule 5)
Create revision: 01_join-data_a.py (or _a.R for R scripts)
Fix: Change the join type from "left" to "inner", as the Plan specifies; assert the matched row count
Execute and capture
Return for re-QA

## Document
[Rule 5 - QA Fix] Changed join type from left to inner per Plan specification
```

**Escalation Path:**
- Attempt 1: Fix per QA suggestion → Re-QA → If still BLOCKER → Attempt 2
- Attempt 2: Different fix approach → Re-QA → If still BLOCKER → STOP, escalate to user

**No user permission needed** for non-methodology BLOCKER fixes. These are correctness issues.

---

### Rule Priority Order

When multiple rules could apply, use this priority:

1. **If Rule 4 applies** → STOP and escalate (methodological decision)
2. **If Rule 5 applies (QA BLOCKER)** → Fix via revision, re-QA (unless methodology issue → Rule 4)
3. **If Rules 1-3 apply** → Fix automatically, document
4. **If genuinely unsure which rule** → Apply Rule 4 (escalate for decision). A QA BLOCKER whose fix corrects a defect without changing the method is not an unsure case: it is Rule 5 (see the Rule 5 Trigger)

**Edge Case Guidance:**

| Scenario | Rule | Rationale |
|----------|------|-----------|
| "Filter crashes on null column" | Rule 1 (Bug) | Code doesn't work |
| "No validation after filter" | Rule 2 (Missing Critical) | Essential for correctness |
| "Need to add missing import" | Rule 3 (Blocking) | Can't proceed without it |
| "Need to add new column from different source" | Rule 4 (Methodology) | Changes analysis scope |
| "This validation is wrong" | Rule 1 (Bug) | Incorrect behavior |
| "No null check before division" | Rule 2 (Missing Critical) | Required for safety |
| "Should switch to left join" | Rule 4 (Methodology) | Affects results |

**Decision Heuristic:** Ask yourself "Does this affect correctness, data integrity, or ability to complete task?"
- **YES (local fix)** → Rules 1-3 (fix automatically)
- **YES (structural change)** → Rule 4 (escalate for user decision)
- **MAYBE** → Rule 4 (escalate to be safe)

---

### Escalation Threshold: System Design Impact

The key principle for deciding whether to auto-fix or escalate is **system design impact**, not complexity.

**Auto-fix (Rules 1-3) when impact is:**
- Single function/file scope
- No methodology changes
- No changes to data sources
- No changes to aggregation level
- No changes to population/sample
- Behavior change is localized

**Escalate (Rule 4) when impact is:**
- New data sources or endpoints
- Different aggregation approach
- Changed join strategy affecting results
- Population or year exclusions
- Library or framework switches
- Changes affecting analysis conclusions
- Methodology changes

**Quick Test:** "Would this change require updating the Plan's methodology section?" If yes → escalate.

---

### What ALWAYS Requires User Approval

These actions can NEVER be taken autonomously, regardless of perceived benefit:

| Action | Why Approval Required |
|--------|----------------------|
| Scope expansion beyond Plan | Changes deliverables |
| Additional data sources | Affects methodology and timeline |
| Methodology changes | Invalidates prior decisions |
| Removing validation steps | Reduces quality assurance |
| Skipping checkpoints | Violates protocol |
| Changing output formats | Affects stakeholder expectations |
| Aggregating to different level | Changes analysis granularity |
| Excluding populations or years | Affects conclusions |

---

### Deviation Documentation Format

All deviations must be documented in the Plan's "Deviations from Plan" section:

```markdown
## Deviations from Plan

| Deviation | Rule | Stage | Impact | Notes |
|-----------|------|-------|--------|-------|
| Fixed type mismatch in year filter | Rule 1 (Bug) | 7 | None | year column was string, not int |
| Added null check before division | Rule 2 (Missing Critical) | 7 | None | Prevents divide-by-zero |
| Corrected parquet file path | Rule 3 (Blocking) | 5 | None | Path needed date prefix |
```

---

### Deviation Decision Tree

```
Is this a bug fix (code doesn't work as intended)?
├─ YES → RULE 1: Fix immediately, document
└─ NO → Continue

Does this add validation, error handling, or data safety checks?
├─ YES → RULE 2: Add immediately, document
└─ NO → Continue

Is this fixing something that blocks task completion?
├─ YES → RULE 3: Fix immediately, document
└─ NO → Continue

Does this change methodology, data sources, or analysis approach?
├─ YES → RULE 4: STOP, escalate for user decision
└─ NO → Continue

Is this an improvement or optimization not required for correctness?
├─ YES → Track for "Future Improvements", do NOT implement
└─ NO → Ask: Is this necessary for task completion?
    ├─ YES → Likely Rule 3 or 4, re-evaluate
    └─ NO → Skip entirely
```

---

## Git Commit Protocol

**Default policy: DAAF does not commit research artifacts.** The DAAF user base is
typically not git-native, and users must never be interrupted by git permission
prompts they did not ask for. By default, neither the orchestrator nor any
subagent runs `git add` or `git commit` for research work. **The working tree is
the audit trail:** every script version (failed and successful), data file, and
output is preserved on disk, which is what makes the analysis reviewable and
reproducible. Read-only git commands (`git status`, `git diff`, `git log`) remain
available to any agent.

**Git commit management is an opt-in User Preference** (`CLAUDE.md` § User
Preferences > "Git commit management"). It is `disabled` by default.

**Who may commit (only when the preference is enabled):**
- **The orchestrator only.** Commits are *proposed* by the orchestrator at natural
  milestones (plan approval, phase/stage completion, delivery) and executed *only
  after the user approves in-session*. Committing is never autonomous.
- **Subagents never commit — under either setting.** A subagent's role is to report
  a *suggested* commit message in its output (see each agent's Output Format),
  never to run `git`.
- **Exception, under either setting:** the orchestrator finishes the merge or
  rebase in User Support's update-conflict walkthrough once the user has approved
  the resolutions (§ User Support Mode > Commits in the update-conflict
  walkthrough).

**Suggested commit messages (always).** Regardless of the preference, agents may
include a suggested commit message in their return output for the user/orchestrator
to use if desired. The philosophy for those messages: *describe outcomes, not
process — a git log built from them should read as a changelog of shipped work.*

**The remainder of this section — message format, types, examples, and safety
rules — applies only when git commit management is enabled and a commit has been
user-approved.**

### Commit Message Format

```
{type}({stage}-{task}): {description}

- Validation: {CP status}
- Rows: {count}
- Files: {file list}

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New data acquisition, transformation | `feat(05-01): Fetch CCD enrollment data` |
| `fix` | Bug fixes, data corrections | `fix(07-02): Handle negative values in join` |
| `chore` | Metadata, STATE.md updates | `chore(wave-1): Update transformation progress` |
| `test` | Test additions | `test(10-01): Add enrollment validation tests` |
| `docs` | Report, documentation | `docs(11-01): Generate stakeholder report` |

### Per-Task Commit Examples

**Data Fetch (Stage 5):**
```
feat(05-01): Fetch CCD school enrollment data

- Validation: CP1 PASSED
- Rows: 98,234
- Files: data/raw/2026-01-31_ccd_schools.parquet

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Data Cleaning (Stage 6):**
```
feat(06-01): Clean CCD data, filter coded values

- Validation: CP2 PASSED
- Rows: 94,102 (4% removed)
- Suppression rate: 12%
- Files: data/processed/2026-01-31_ccd_clean.parquet

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Transformation (Stage 7):**
```
feat(07-02): Join CCD schools with MEPS poverty data

- Validation: CP3 PASSED (join validation)
- Rows: 91,847 (1:1 cardinality confirmed)
- Files: data/processed/2026-01-31_analysis.parquet

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Bug Fix During Execution:**
```
fix(07-02): Correct type mismatch in year filter

- Issue: Year column was string, filter used integer
- Resolution: Changed filter to use string comparison
- Rows affected: All (was filtering to 0)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Wave Completion Commit

After all tasks in a wave complete, optionally commit metadata:

```
chore(wave-2): Complete data cleaning phase

Completed tasks:
- clean-ccd: 94,102 rows (CP2 PASSED)
- clean-meps: 97,503 rows (CP2 PASSED)

Updated: STATE.md transformation progress

Co-Authored-By: Claude <noreply@anthropic.com>
```

### What NOT to Commit

| Don't Commit | Reason |
|--------------|--------|
| Mid-task work | Incomplete state |
| Failed validation | Not shippable |
| Debug attempts | Process noise |
| Temporary files | Not deliverables |

### Commit Safety Rules

- **NEVER** use `--amend` after hook failures (creates new commit instead)
- **NEVER** use `--force` push to main/master
- **NEVER** skip hooks with `--no-verify`
- **ALWAYS** stage specific files (not `git add -A`)
- **ALWAYS** review diff before committing

---

## STOP Conditions

These conditions trigger an immediate STOP with escalation to user.

### Automatic STOP Triggers

| Condition | Stage | Response |
|-----------|-------|----------|
| Data access mirror returns empty data | Stage 5 | STOP, report to user, await guidance |
| Suppression rate >50% | Stage 6 | STOP, report issue, propose alternatives |
| Domain governance rule violated (e.g., cross-state assessment comparison in education) | Stage 6 | BLOCK with explanation (never valid per domain governance) |
| Row count drops >90% after transformation | Stage 7 | STOP, verify transformation logic |
| **QA BLOCKER after 2 revisions** | 5-QA to 8-QA | STOP, escalate to user |
| **QA methodology conflict** (code-reviewer STOP, Issue Category `Methodology Conflict`) | 5-QA to 8-QA | STOP, escalate immediately |
| Marimo `marimo check` gate or `marimo export html` check, or `quarto render`, fails after 2 fix attempts | Stage 9 | STOP, report error details; the checks validate notebook structure, assembly and enabled previews, not archived Stage 5-8 re-execution |
| Stage 9 display input (Parquet or figure, Marimo or Quarto) is missing and is a declared Stage 5-8 output: its file name appears in the project's `*_Plan.md`, `*_Plan_Tasks.md` or `STATE.md` | Stage 9 | STOP, report the missing path as an upstream failure; never drop the display to hide it |
| Marimo execution log cannot be archived verbatim: it contains both `'''` and `"""`, Step 6a reports MB001 inside a log accordion whose delimiter is already the one notebook-assembler's Grep rule picks, the log holds a character the bundle or decompiler cannot carry (a NUL byte, bytes that are not valid UTF-8, a carriage return inside a line), or the Step 6c fidelity check fails (a final script missing, an earlier or renamed version archived, or a decompiled archived script that differs from its original). Backslashes and code-fence lines alone are fine: logs sit in a raw literal inside an outer fence longer than any backtick run in the log | Stage 9 | STOP, report the script path and the offending line, missing or extra paths, or differing lines; never edit archived code or log text |
| Data unavailable in data skills | Stage 2-3 | STOP, escalate immediately |
| LOW confidence finding unresolved | Any | Cannot proceed |

### STOP Message Format

See `ERROR_RECOVERY.md` "Escalation Format" for the authoritative STOP/escalation message template.

---

## Boundary Violations

### If You Catch Yourself Violating a Boundary

1. **STOP** the current action immediately
2. **Document** what happened
3. **Report** to user with:
   - What boundary was violated
   - What the impact might be
   - How to remediate
4. **Await** guidance before continuing

### If User Requests a Boundary Violation

Explain why the boundary exists and propose alternatives:

```markdown
**Boundary Notice**

You've requested [action], which falls under "Never Do" because [reason].

**Risk:** [What could go wrong]

**Alternatives:**
1. [Alternative approach that achieves similar goal]
2. [Modified version that stays within boundaries]

Would you like me to proceed with one of these alternatives?
```

For security-related Never Do items, do not proceed even if user insists.

---

## Defense-in-Depth Architecture (Enforcement Layers)

> This is the full layer-by-layer table; CLAUDE.md § Boundaries & Safety > Defense-in-Depth Architecture summarizes it and points here. Each hook's header comments document its exact coverage.

| Layer | Mechanism | What It Covers |
|-------|-----------|----------------|
| **PreToolUse Hook** | `bash-safety.sh` — exit code 2 blocks execution | **Body and site file:** the hook body is site-neutral and holds no project value. DAAF's settings (`SITE_ROOT='/daaf'`, `SITE_EXTRA_PROTECTED_DIRS` = `benchmarks/harness/hooks`, and the scratch-dir, rebuild and environment-print hints its messages use) live in `.claude/hooks/bash-safety.site.sh`, which the body sources from its own directory at startup; the site file is never registered as a hook in `settings.json`. It loads **fail-closed**: the ERR trap is installed before the source, so a missing or unreadable site file, one that fails to load (a syntax error or a failing command), an empty or malformed `SITE_ROOT`, or a malformed `SITE_EXTRA_PROTECTED_DIRS` entry (in either, a trailing or doubled slash or a `.` or `..` component counts as malformed) blocks every command, with a message saying the site file is broken, until the user repairs the file. A site file may also define optional site guards (`site_extension_guards`), which run after every body guard under a scoped `set -E`. A site guard must return 0 when it allows (end it with `return 0`; write each check as `if …; then block …; fi`, not a final `[[ … ]] && block …`): a failing command or a non-zero return inside it blocks every command, with a message naming the site guard. DAAF's defines none. The site file runs with the hook's own authority (one that calls `exit 0` would allow everything), so its defence is its location: §7 and the `Edit(.claude/hooks/*)` deny rule cover it like every hook file, and it is user-only. **Input posture:** fails closed (exit 2) when `jq` is missing, stdin is empty, or stdin is not exactly one JSON object (concatenated objects, malformed text, whitespace only, a bare scalar or array). A **stage 0 classifier** builds the scanned text before any pattern runs. 0a excises a heredoc body only when its receiver is a data consumer (`cat`, `tee`, `grep`, `jq`, `git commit`, …); a heredoc into, or piped into, a shell or interpreter stays scanned, line by line. 0b excises `git commit -m` message bodies. 0c classifies every other quoted span: a carrier body (`bash -c`, `eval`, `xargs`, `ssh`, `find -exec`, or a quoted payload the same command writes to a file and then executes) is *promoted* to command position; a whole-word argument is *excised* only when its receiver is provably a data consumer, and never inside `$(`/`<(`/backtick; a `VAR=` value or a double-quoted span containing backtick/`$(`/`${` is *kept*; everything else is *canonicalized* by stripping the quotes. 0d drops inert backslash escapes, and 0e blocks `$IFS` outright. Any ambiguity keeps the text (fail-closed), and commands over 20 kB skip 0c/0d and are scanned raw. Wrapper prefixes, including an allowlisted argument-taking flag with its argument (`env -u HOME`, `nice -n 5`, `timeout -s KILL 5`, `exec -a x`, `stdbuf`, `doas`, `ionice`, `flock`, …), leading `VAR=value` assignments, shell keywords (`if`/`then`/`do`/`!`) and `/bin/`-, `/usr/bin/`- or `/usr/local/bin/`-qualified verbs do not defeat a segment anchor. A segment opens at the start, after `;`, `&` or `\|`, at `(`, `)` or `{`, at a backtick or `$(`, and after `-exec`, so a command inside a subshell, group or substitution is checked like any other, by the safety-system, `ln`, `mktemp` and package-install guards too. The `ln`, `mktemp` and package-install guards open at `(` only at a token start, not right after a letter, digit, `_` or `.`, so a function call in kept interpreter code (`print("pip install …")`) is not read as a command. **Then blocks** — **recursive deletes** of `/`, `~`, `$HOME`/`/home/<user>`, the working directory through `$PWD` (both variables also braced or quoted), `.`, `..`, `*`, dot-globs, top-level system directories, `.claude`, and the project root and its `.git`, including a target that a closing backtick ends (`` `rm -rf ~` ``). The root counts whether written literally (`/daaf`) or through `$CLAUDE_PROJECT_DIR`/`$PROJECT_DIR`/`$BASE_DIR`, quoted or not; a nested clone's `.git` passes. Also blocked: a word-anywhere backstop for the catastrophic targets behind unknown wrappers, `rm -rf /*$(…)`, and an unfiltered `find <root or home> -delete`. **Destructive git:** force push incl. flag bundles, `+refspec` and `--delete`/`:ref`; hard reset; `clean -f`; whole-tree `checkout`/`restore`/`switch -f`; branch force-delete. Git global options such as `-C dir` before the verb do not hide these. **Privilege escalation:** `sudo`, `su`, `doas`, also path-qualified; world-writable/setuid `chmod` incl. `1777`, comma-list modes, `--reference=<system path>`, and `install -m`. **Download-execute:** one pipe-receiver vocabulary is shared by the heredoc, quoted-payload, unquoted `echo`/`printf`-feed and downloader guards. It covers `\|` or `\|&`; wrapper, flag-argument and `VAR=` prefixes; quoted, escaped or path-qualified receivers (`\| "bash"`, `\| /bin/bash`, `\| env -u HOME bash`); any shell incl. `mksh`/`fish` and `. /dev/stdin`; and a receiver followed by `;`, `&`, `\|`, `)` or a backtick. Also the `$(curl …)` family (`bash -c "$(curl …)"`, `eval "$(curl …)"`, `bash <<< "$(curl …)"`, a capture in command position), `bash <(curl …)`, and curl/wget file exfiltration. **Write-then-execute:** a file the same command writes with a dangerous payload and then executes (counted only at an execution position). **Container escape:** `docker run`, `mount`/`umount`/`chroot`. **Ephemeral writes:** shell *writes* to `/tmp`, `/var/tmp` and `/dev/shm`, incl. `//tmp`, `/./tmp`, `tar -C`, `--directory=`, downloads through a bundled curl flag (`curl -sSLo /tmp/x`), `--output=`, `firecrawl -o` or wget `--output-document`, `ln` in either direction, and `mktemp` without a non-ephemeral target, also when `mktemp` sits in `(…)`, `{ …; }`, backticks or `$(…)` (`x=$(mktemp)`), and the output flags and output arguments of the safety-system writers below aimed at an ephemeral root (`sort -o /tmp/x f`, `tar -czf /tmp/a.tgz d`, `git archive -o`, `pandoc -o`, `gpg -o`, `wget -a`, `uniq IN OUT`; one shared list serves both checks). Reads of DAAF's /tmp caches, and reading from /tmp into the project (`sort /tmp/x -o <project file>`), stay open. **Safety-system writes** to `.claude/hooks/` (the site file included), `.claude/logs/`, `.claude/settings*.json` and `benchmarks/harness/hooks/`: `cp`/`mv`/`shred`/`unlink`/`git rm`/`git mv`, `-t` destinations, glob path components, `>\|`, `sed -Ei`/`perl -pi` (like the `tar -C`/`unzip -d` and `find -delete` checks, also `/bin/`-, `/usr/bin/`- or `/usr/local/bin/`-qualified: `/bin/sed -i … .claude/settings.json`), `find -exec`/`xargs` mutators, a following command (`…; echo done`), and copying, moving or extracting into `.claude/` itself. Also **output-flag writers** whose flag argument is a protected path (`curl -o`/`--output`/`--output-dir`, `wget -O`/`-o`/`-P`/`--output-document`/`--directory-prefix`, `firecrawl -o`, `sort -o`; bundled, attached or `=` forms such as `curl -sSLo .claude/hooks/x.sh URL`); **output-argument writers** (`tar` creating, appending to or deleting from a protected `-f`/`--file` archive, `git archive -o`, `pandoc -o`, `gpg -o`, `wget -a`, `uniq IN OUT` with a protected second operand); and every one of these inside a subshell, group or substitution (`(cp x .claude/hooks/y)`, `{ cp …; }`, `x=$(rm .claude/hooks/y)`, `diff <(cp …) f`). A protected path read as input (`sort -o out.txt .claude/settings.json`, `tar -xf`), archived as a source, or contained in a URL that has a scheme (`https://…/.claude/hooks/x.sh`) stays allowed. These changes are user-only; reads and `git update-index --chmod=+x` stay open. **Package installs** at runtime across pip/uv/conda/R spellings, also inside a subshell, group or substitution or after a shell keyword (`if …; then pip install x; fi`), pointing to the Dockerfile rebuild. Fixed false positives include prose naming a verb inside a data-consumer argument, `ls $mount`, `git branch -d`, and in-project deletes. **Accepted residuals** are listed in the hook header, and most are pinned by ALLOW-today tests: substitution-computed command names and targets (`$(echo rm)`, `D=/; rm -rf "$D"`); variable-indirected text evaluated later (`A='sudo id' eval "$A"`); runtime-computed stdin into a shell (`jq -r .cmd f \| bash`); receivers not modelled (`\| ${SHELL}`, `\| ssh host`, `\| awk -f -`); variable-rooted targets with no working-directory arm or no quote support (`find "$PWD" -delete`, a quoted `rm -rf "${D}/usr"`); wrapper spellings outside the allowlisted flag set, and the separate wrapper list of the unquoted `echo`/`printf`-feed rewrite; interpreter bodies (scanned for literal patterns, not decomposed); write-then-execute through another spelling of the file; cwd-relative evasion across calls; program-argument /tmp writes; output writers and spellings not on the list (`split`, `sponge`, `iconv -o`, `xxd -r IN OUT`; `git worktree add`, `git format-patch -o`, `git bundle create`, `git diff --output`; curl `-D`/`-c`/`--trace`; abbreviated or alternate flags such as `sort --out=`, `tar --cre`, `uniq IN -- OUT` and wget `--output-file`; the attached or long directory forms of an extraction into a protected path, `--directory=`, `-C.claude/…`, `-d.claude/…`); a quoted destination holding a space given to `sort`, `uniq` or `tee` (`sort -o '/tmp/x y' f`), which stage 0 excises as data; program paths other than `/bin/`, `/usr/bin/` and `/usr/local/bin/` before a verb, and, outside the safety-system checks (which all accept those three qualifiers), a few verbs that take no path qualifier at all (`/usr/bin/find / -delete`, `/bin/ln -s f /tmp/x`, `/usr/bin/mktemp`, `/usr/bin/docker run`, path-qualified `conda`/`uv`/R installs; FC527-FC531); an ephemeral path reached through `..` (`sort -o /daaf/../tmp/x f`); these writer spellings, unqualified verbs and `..` paths are recorded residuals, not planned work, because a well-behaved agent does not type them and a regex classifier is not the boundary against a deliberate adversary; the >20 kB raw-scan trade; and a single stdin object whose `tool_name` is not a string (an array, object, `null`, number, or missing key), which reads as "not Bash" and is allowed unscanned. The stdin gate checks the object count, not the field type, and the claim that Claude Code always sends a string is inference. This is the same class as `enforce-single-command.sh` R7. It is pinned as FC240 in both suites and recorded in the hook header. **Accidental environment disclosure (§9):** blocks a bare `env`/`set`/`export -p`/`printenv` whose output reaches a terminal or a file (a pipe into a filter, `env \| grep PATH`, is not a sink and stays allowed); an `echo`/`printf`/`declare -p`/`typeset -p`/`printenv NAME` of an uppercase variable whose last `_`-segment is one of `KEY APIKEY TOKEN SECRET PASSWORD PASSWD PASSPHRASE CREDENTIAL CREDS DSN PAT` (plurals, single-segment names and `…_SESSION`/`…_AUTH`/`…_COOKIE` are exempt; an additive stage-0 accumulator keeps such expansions visible even inside excised data spans); any `/proc/<pid>/environ` read; and an interpreter one-liner that prints a whole environment object (`os.environ`, `Sys.getenv()`, `process.env`, `%ENV`, `ENVIRON`, …; single-variable reads pass). Every §9 refusal names the category and a safe alternative (presence or length check, `compgen -v`, or a script run via `run_with_capture.sh`), never the matched text. Posture is accidental-dump only, mirroring the `run_with_capture.sh` scan: documented residuals are the pipe and `2>` sinks, values copied into another variable first, lowercase or run-time-computed names, and interpreter dumps written to files; accepted false positives are any uppercase variable with a credential last segment echoed (`$CACHE_KEY`), and env tokens inside quoted search patterns or code strings that stage 0 did not excise (a grep *for* `/proc/self/environ`, a regex alternation ending `\|env)`, a jq filter containing `(set)`) — measured at 4 of 5,732 recorded session commands, all hook-maintenance work. Pinned as FC241-FC280 in both suites. The `settings.json` deny rules (Permission Deny Rules row below) remain the tool-permission backstop. **Adversarial-coverage gap (accepted):** two mechanisms, the write-then-execute execution-position test (`_exec_recurs`) and the unquoted `echo`/`printf`-into-a-shell rewrite (F12), have functional pins but no adversarial red-team cases; such cases should come from a human author. Accepted false positives include `install -d .claude`; whitespace-free quoted search patterns, which stage 0 canonicalizes instead of excising, so their `\|`, `(` and `{` read as segment openers (`grep -E "(tmp\|mktemp)" f`, `grep -E "(mktemp)" f`, `grep -n -E "tmp\|mktemp" f`, `grep -n "{cp" .claude/hooks/x`, and an alternation ending in an output-writer name read against a protected path or a /tmp file, `grep -nE "x\|uniq" f .claude/hooks/x` and `grep -c -E "error\|uniq" /tmp/claude-ctx-window-x /tmp/claude-model-x`; workaround: pass each alternative as its own `-e` pattern (`grep -n -e tmp -e mktemp f`) or bracket the character, `"[{]cp"`, which return the same lines, whereas a space in the pattern changes what grep searches for; the fix would be a stage-0 change and is deferred on purpose, because the class fails closed (a read-only search is refused, nothing dangerous is allowed), every check reads stage 0's output, so a change there risks regressions across the whole classifier, and a replay of recorded session commands (a sample of 11,731 plus all 11,404 commands a changed rule could read, out of 46,923 distinct) found 3 such blocks); two more search-pattern shapes of the same deferred class, an escaped paren (`grep -n -E '"Bash\(rm' .claude/settings.json`; workaround: bracket it, `[(]`) and a backtick inside a double-quoted pattern (`` grep -nE "x\|bare \`pip install\|y" README.md ``; workaround: single-quote the pattern); a scheme-less URL after `curl -O` that names a protected path; a quoted grep pattern piped via `2>&1` into `python3 script.py`; and the shared wrapper flag-letter class, where one argument-taking letter set serves every wrapper, so a wrapper flag that takes no argument swallows the real command and that command's first argument is read as the verb (`strace -D grep mount f`; FC211, FC212, FC239). Fail-closed (ERR trap → exit 2). Two timing gates must each finish under 2 s: `tests/fixtures/bash_safety/perf_probe.sh` (~20 kB, 300 quoted spans + 20 heredocs) and `perf_gate.sh` (32 kB and 64 kB padded commands must still BLOCK). They matter because settings.json gives the hook 5 s, and a PreToolUse hook that times out does not block: the call continues through the normal permission flow (verified against the Claude Code hooks reference on 2026-11-02; settings.json sets no `onFailure` for this hook). Regression battery: `scripts/test_safety_hooks.sh` (1081 cases) + `tests/bash/bash_safety.bats` (996 cases), including fixture rows that run a copy of the hook beside a missing, unreadable, failing or malformed site file, or one that defines site guards. The 936 cases that carry a case ID are mirrored 1:1 (the two ID sets match); older cases without one (145 in the battery, 60 in bats) are not paired one-for-one. To test a draft, keep a `bash-safety.site.sh` beside it: without one every row blocks, by design |
| **Wrapper Content Scan** | `run_with_capture.sh` — exit code 3 blocks execution | Pre-execution scan of the script BODY for package-install and package-removal calls that shell-level hooks cannot see (the dominant path for R `install.packages()` inside a `.R` script, and `os.system("pip install ...")`/`subprocess` forms in Python). Excludes full-line comments (an inline trailing-comment token is an accepted false positive). On a hit the wrapper refuses to execute, appends **no** execution log (so immutable versioning does not engage and the script stays editable in place), and points to the Dockerfile-rebuild path. Complements the `bash-safety.sh` §8 command-line guard. A second scan refuses **environment-secret prints**: whole-environment dumps (`os.environ` printed or serialized, `Sys.getenv()` with no name), `os.environ.items()`/`.values()` with an output sink on the same line or as a `for` loop header (env-scrubbing comprehensions that build a child environment are allowed), credential-named lookups (the shared `SECRET-NAME-VOCAB v1` list) inside print/log sinks, R bare top-level credential lookups (which auto-print), and shell-outs that dump the environment. Same outcome: exit 3, no log appended, script editable in place; the refusal names the line number and category, never the line text. The secret scan is an accidental-dump guard, not an adversarial one. A third scan refuses **researcher-decision commands**: a non-comment line holding `record-human` (`lit_corpus adjudications record-human`), or a script that names `lit_verify` and has non-comment lines with the word `settle` and a `--decision` flag (or a prefix down to `--d`); `settle --list` runs. Same outcome; the refusal cites each line as `N:text`. Only the orchestrator records these decisions, at a permission prompt (`SCRIPT_EXECUTION_REFERENCE.md` § Researcher-Decision Command Scan). All three scans read the file as text (`grep -a`), so a NUL byte cannot disable them; their deliberate non-matches and residuals are listed in each scan's section comments in the script. Regression suite: `tests/bash/run_with_capture.bats` (88 cases) |
| **Wrapper Evidence Verification** | `run_with_capture.sh` — exit code 74 signals an incomplete audit record | Post-execution integrity of the audit trail: the wrapper tracks computation (script exit), capture (`tee` status into a project-local buffer next to the script, never `/tmp`), and persistence (log appended and verified — exactly one marker, closing banner last, exit-code line present) as separate outcomes. `SUCCESS` and `Execution log appended` are printed only when all three hold; otherwise an `EVIDENCE INCOMPLETE` banner names the failed outcome, the capture buffer is retained as evidence, and the wrapper exits 74 so a run with a missing or truncated record cannot be accepted downstream as a completed audited run. Interruptions (SIGINT/SIGTERM) append no log and retain the buffer (exit 130/143). Concurrent duplicate runs are detected (marker count ≠ 1), not locked out. Regression suite: `tests/bash/run_with_capture.bats` (integrity section) |
| **PreToolUse Hook** | `enforce-single-command.sh` — exit code 2 blocks execution | Blocks command chaining (`&&`, `\|\|`, `;`, a lone background `&`, newline-separated commands). Quote-, comment-, and nesting-aware scanner: word-initial `#` comments are dropped first, heredoc bodies are removed only when the `<<` is genuinely outside quotes (not `<<<`, not inside `$((…))`; CRLF terminators close the body), and shell-carrier bodies (`bash -c`, `sh -c`, `eval`, `source`) are scanned recursively to depth 3 while `python3 -c "a; b"` stays a single command. Compound-command (`for`/`while`/`if`/`case`) `;` exemption. Known residuals, each pinned by an ALLOW-today test (R1 and R2 in the bats suite; R6 and R7 in both suites): the exemption covers the whole command once a compound keyword starts it (R1, deferred); bare `( a; b )` subshell groups are not scanned (R2, deferred); `ssh host 'a && b'` is not decomposed (R6, a deliberate scope choice: the remote body runs on the remote host, not in this Bash call; ssh is a carrier for bash-safety's stage 0c but not for the chain scanner); and a single object whose `tool_name` is not a string (an array, object, number or null) reads as "not Bash" and is allowed (R7; the stdin gate checks the object count, not the field type; that Claude Code always sends a string is inference). Pipes (`\|`, `\|&`) and `$(a; b)` computed arguments are one command by design. Convention hook: fails open on scanner malfunction; fails closed on missing `jq`, empty input, or stdin that is not exactly one JSON object (concatenated objects, malformed text, whitespace only, a bare scalar or array). Enforces the "One Command Per Call" rule. Regression suites: `tests/bash/enforce_single_command.bats` (98 cases) + `scripts/test_enforce_single_command.sh` (122 cases) |
| **PreToolUse Hook (agent-scoped)** | `enforce-file-first.sh` — registered in the frontmatter of every agent with `Bash` in its `tools` (research-executor, code-reviewer, debugger, data-ingest, search-agent, source-researcher, research-synthesizer, data-planner, notebook-assembler, report-writer, framework-engineer, data-verifier, integration-checker, plan-checker, literature-searcher, paper-reader, literature-synthesizer) | Blocks direct `python`/`python3` execution and all R batch entry points (`Rscript`, and bare `R` with `-e`/`-f`/`CMD BATCH`/redirected `--no-save` etc.); enforces `run_with_capture.sh` wrapper for audit trail. Whitelist: `python`, `python3` or `Rscript` followed directly by the path of a script in `/daaf/scripts/` itself (not a subfolder, no interpreter flags between) is allowed; the test is a substring match over the whole command, and a match allows the whole command. A read-only search whose regex alternation names an interpreter (`grep -E 'a\|python3 x'`) is blocked, because the `\|` reads as a pipe; pass one `-e` pattern per alternative instead. Read-only agents with Bash register it too, because under auto mode Claude Code ignores a subagent's `permissionMode`. It does not block other writing commands (`quarto render`, redirects). Not active for the orchestrator, or for citation-adjudicator, whose only tool is Read (no Bash, so no hook to register; it registers `adjudicator-read-scope.sh`, next row); every other DAAF agent holds Bash. Fails closed (exit 2) on missing `jq`, empty stdin, or an unexpected error, and on stdin that is not exactly one JSON object (concatenated values, malformed text, whitespace only, a bare scalar or array). Regression suite: `tests/bash/enforce_file_first.bats` (49 cases) |
| **PreToolUse Hook (agent-scoped)** | `adjudicator-read-scope.sh` — registered in the frontmatter of citation-adjudicator only, matcher `""` (every tool); a deny prints a JSON `permissionDecision: deny`, the same reason on stderr, and exits 2 | Keeps the reference checker to its citation bundle. Allows only a Read whose path is absolute and already canonical (`realpath -m -s` and `realpath -m` both return it unchanged, so no `..`, `.`, `//`, trailing slash or symlink anywhere along it), lies under `<DAAF root>/research/` (root: `$CLAUDE_PROJECT_DIR`, else `/daaf`) at `<project>/data/adjudication_bundles/<batch_id>.json` with `<batch_id>` matching `BATCH_ID_RE` in `scripts/lit_corpus.py` (so the `{batch_id}_prompt.txt` beside it is refused), and names an existing regular file. Every other tool call of the agent is denied. A call whose `agent_type` names another agent passes untouched; a call with no `agent_type` is checked. The hook cannot tell which bundle the prompt names: ingest's audit-log scan, which requires every Read of the dispatch to resolve to that bundle, is the second check, and the only check in a session where the hook does not run. Frontmatter hooks of a project agent run only after the workspace trust dialog is accepted, and a `claude -p` session does not count as accepting it (verified against the Claude Code hooks reference on 2026-10-27). Exit 2 blocks even when the JSON is malformed, so the deny does not depend on it. Fails closed (exit 2) on missing `jq` or `realpath`, empty stdin, stdin that is not exactly one JSON object, a `tool_name` or `file_path` with a control character, a DAAF root of `/`, or an unexpected error (ERR trap); neither the trap nor the deny path uses `jq`. A registered hook whose script is missing or cannot start does not block on Claude Code 2.1.281 (the `onFailure: "block"` field needs 2.1.295 or later; verified against the Claude Code hooks reference on 2026-10-27), so the script is installed before its registration. A run that reaches its `timeout: 5` does not block either: on Claude Code 2.1.281, which predates `onFailure: "block"`, a timed-out PreToolUse hook lets the call continue through the normal permission flow, and ingest's audit-log scan is then the check (verified against the Claude Code hooks reference on 2026-11-02). Regression suite: `tests/bash/adjudicator_read_scope.bats` (38 cases) |
| **PreToolUse Hook** | `enforce-model-ceiling.sh` — registered on subagent dispatch (`Task`/`Agent`); denies via `permissionDecision: deny` | Blocks subagent dispatches on a model tier *above* the session model, preserving the user's cost-control choice; also blocks Claude-tier requests on non-Claude sessions (alternative providers) with a pointer to the env-var remaps. Cost-control guard, **fail-open by design** — if it cannot detect the session model (or `jq`/agent file is unavailable) it allows the dispatch, unlike the fail-closed safety hooks above. Stands down when `ANTHROPIC_DEFAULT_OPUS_MODEL` or `ANTHROPIC_DEFAULT_SONNET_MODEL` is set (it cannot rank custom models) or `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is `1`/`true`. `CLAUDE_CODE_SUBAGENT_MODEL` alone does not stand it down. Its deny messages name the session tier's alias or the four `ANTHROPIC_DEFAULT_*_MODEL` settings. Regression suite: `tests/bash/enforce_model_ceiling.bats` (27 cases) |
| **PreToolUse Hook** | `block-remote-isolation.sh` — registered on subagent dispatch (`Task`/`Agent`); sanitizes via `permissionDecision: allow` + full-object `updatedInput` rewrite | Strips the optional `isolation` parameter from Agent/Task dispatches whenever the key is present, regardless of value (key-presence contract shared with the provider shim's `_sanitize_tool_args`): `remote` cloud environments are unavailable in the container and hang forever; `worktree` runs the subagent against a stale default-branch checkout. Emits `updatedInput` as the complete original tool input minus `isolation`, because Claude Code *replaces* (never merges) tool input with `updatedInput`. Availability/sanitization guard, **fail-open by design** — missing `jq`, malformed stdin, or non-object tool input allows the dispatch unmodified. Regression suite: `tests/bash/block_remote_isolation.bats` |
| **PreToolUse Hook** | `block-nested-dispatch.sh` — registered on subagent dispatch (`Task`/`Agent`); denies via `permissionDecision: deny` | Blocks Agent/Task dispatches that originate *inside* a subagent, reading the caller-identifying `agent_id`/`agent_type` stdin fields (`agent_id` is present only when the hook fires inside a subagent or an in-process agent-team teammate, per the Claude Code hooks reference; DAAF uses no agent teams; a deny also fires on any `agent_type` value other than `orchestrator`): in DAAF all dispatch authority belongs to the orchestrator, so a subagent returns remaining work for redelegation rather than spawning nested subagents. Every named agent already omits Agent/Task from its explicit `tools:` list; this hook closes the gap for generic built-in types (`general-purpose`, `Plan`) that inherit Agent/Task with no DAAF-authored `tools:` list to restrict them. It is the backstop layer behind the harness spawn-depth limit (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in `settings.json` `env`), under which subagents receive no Agent/Task tool at all (observed 2026-11-02, Claude Code 2.1.281), so in the shipped configuration the hook fires only if that limit is lifted or regresses. Covers spawn-style dispatch only (the Task/Agent matchers); primitives that route work to already-running agents are governed by agents' `tools:` lists alone. Orchestration-discipline guard, **fail-open by design** — missing `jq`, empty/malformed stdin, or any unexpected error allows the dispatch (a nested agent that slips through still runs under bash-safety.sh and all deny rules, which apply inside subagents). Regression suite: `tests/bash/block_nested_dispatch.bats` |
| **PreToolUse Hook** | `deny-claude-code-guide.sh` — registered on subagent dispatch (`Task`/`Agent`); denies via `permissionDecision: deny` | Blocks dispatch of the built-in `claude-code-guide` agent (an opaque system prompt, at odds with DAAF's transparency requirement; it also runs on the Haiku model, a tier DAAF does not use for subagents, per the Claude Code subagents docs, verified 2026-11-02) and points to a `search-agent` with WebSearch plus the web-retrieval protocol instead. Other subagent types are always allowed, including on empty or malformed stdin (fail-open for everything except the banned type). A jq-free raw-text match blocks the banned pair when `jq` is absent (stderr + exit 2); the ERR trap is jq-free and fails closed; and a concatenated stdin stream is denied when any parsed value (or array element) carries the banned `subagent_type`, with the raw-text match also applied after a parse error. Plain malformed stdin with no banned pair still allows. Regression suite: `tests/bash/deny_claude_code_guide.bats` (32 cases) |
| **PreToolUse Hook** | `enforce-explore-model.sh` — registered on subagent dispatch (`Task`/`Agent`); denies via `permissionDecision: deny` | Blocks `Explore`-type dispatches (Explore starts without CLAUDE.md and cannot write files; Claude Code subagents docs, verified 2026-11-02) and points to `search-agent`, DAAF's web-capable search and information-gathering agent, which follows DAAF's conventions and writes its own record. A routing preference rather than a safety boundary, so other subagent types are allowed on every path. Already jq-independent: without `jq` a raw-text match blocks the Explore pair (stderr + exit 2), and the ERR trap is jq-free and fails closed. A concatenated stdin stream is denied when any parsed value (or array element) carries `subagent_type: "Explore"`, with the raw-text match also applied after a parse error; plain malformed stdin with no Explore pair still allows. Regression suite: `tests/bash/enforce_explore_model.bats` (29 cases) |
| **Permission Deny Rules** | `settings.json` deny list | `rm -rf`, `sudo`, `docker`, credential file reads/writes, shell commands that print environment values (`Bash(env)`, `Bash(printenv*)`, `Bash(export -p*)`, `Bash(set)`, `Bash(cat /proc/*)`; the tool-permission counterpart of the `run_with_capture.sh` environment-secret print scan and of the `bash-safety.sh` §9 accidental-disclosure guard, which covers the wrapped, redirected and credential-named shapes these exact-string rules cannot see; pinned as exact strings in `tests/bash/settings_permissions.bats`), audit log writes/edits, runtime package installs (`pip`/`pip3`/`pipx install`, `python -m pip install`, `uv pip install`, `uv add`, `uvx`, `conda install`, `conda create`, `easy_install` — the tool-permission backstop to the bash-safety.sh §8 package guard), file-editing tools to /tmp (`Edit(//tmp/**)`, which covers `Write` as well, because Claude Code checks file edits against `Edit(path)` rules only (permissions docs; verified live on 2.1.261) — complements the bash-safety.sh /tmp guard, which covers shell writes the deny rules cannot see; neither covers a `/tmp` path held in a shell variable, a program's `/tmp` output argument, or temp-file API defaults inside a script, which stay instruction-enforced per CLAUDE.md § Provenance Boundary) |
| **Permission Allow List** | `settings.json` allow list | Only approved tools auto-execute; everything else prompts, except in auto mode, where a call that matches no rule may run without a prompt (Claude Code's auto-mode classifier decides; observed for `git push` when no ask rule covered it) |
| **Permission Ask Rules** | `settings.json` `permissions.ask` | Commands that always prompt, auto mode included (rules are evaluated deny, then ask, then allow): `Bash(git push)`, `Bash(git push *)`, `Bash(git -C * push)` and `Bash(git -C * push *)`, so `git push …` and `git -C <dir> push …` ask first (CLAUDE.md § Repository & Remote Safety). Ask rules match the command as written, so `git -c <key>=<value> push` or a push wrapped in another command such as `bash -c` can slip past them; closing that needs a hook change, which is deferred. `Bash(*lit_corpus*record-human*)` and `Bash(*lit_verify*settle*--d*)` make the two Literature Review commands that record a person's decision ask first, so the person approves the call that carries their own words; a script that calls them is refused by `run_with_capture.sh` (exit 3). Pinned in `tests/bash/settings_permissions.bats` |
| **PostToolUse Hooks** | `audit-log.sh`, `output-scanner.sh` | Audit trail (`audit-log.sh`); secret detection in output (`output-scanner.sh`). The scanner reads the first 10 kB of `tool_response`, whether it is a string, an object or an array: objects and arrays are rendered as compact JSON text first, so nested secrets are scanned. It looks for AWS keys, `sk-`/Stripe/GitHub tokens, private-key headers and long Bearer tokens. Its warning reaches the model only as one JSON object carrying `hookSpecificOutput.additionalContext`, because Claude Code writes a PostToolUse hook's plain stdout only to its debug log (verified against the Claude Code hooks reference on 2026-11-02). The warning names the matched families and tells the model not to display, log or commit the values; what to do next is in CLAUDE.md § Boundaries & Safety > Credential & Secret Protection. Advisory only: it always exits 0 and never blocks. `audit-log.sh` writes each call's target (a Bash command's first 200 characters, or a file path). `audit-log.sh` applies pattern redaction (the scanner's credential families plus `Authorization:` values, long Bearer tokens and credential-named assignments, extended by the inline-literal rules below) and **value-based** redaction to `[REDACTED:env:NAME]` for the value of any credential-named environment variable (the shared `SECRET-NAME-VOCAB v1` list), before the 200-character cut; for every target the value step runs on a 65,536-character window before the 4,000-character regex cap. It builds the record in one NUL-safe `jq` pass, and a fallback pass keeps the record (session, tool and agent fields) while withholding the target if the value step fails. `output-scanner.sh` adds a value-based warning that names the matching variable, never its value, comparing at most the first 512 characters of each value. Both hooks guard against an inherited xtrace (`set +x`), so values are never traced to stderr. Values under 8 characters, path- or plain-URL-shaped values, and transformed or encoded values are not value-matched. Whether Claude Code passes credential variables to hook processes at all is unverified; a user can check it once: add a clearly fake credential-named entry (a name ending in `_API_KEY`, a made-up value of 8 or more characters) to `environment_settings.txt` in the `daaf-docker/` folder, restart the container, have the agent run a harmless command whose output contains that value, then check two things: once the scanner emits its warning as `additionalContext`, the agent should tell you that a credential appeared in the tool output (the scanner's "value of NAME appears in this tool output" warning goes to the agent with the tool result and is not shown as a chat message, so ask the agent whether it received one), and `[REDACTED:env:NAME]` should be on the newest line of `.claude/logs/audit.jsonl`. If neither appears, the value-based checks are inert while the pattern families still work; remove the fake entry and restart afterwards. `audit-log.sh` caps every target at 4,000 characters before the pattern rules (non-Bash targets are then logged up to 3,872), because a keyword-dense target of roughly 6,000 or more characters exceeds jq's regex backtracking limit. It keeps the record with a `[REDACTED:pattern-step-failed]` target if the regex step still fails, and writes the all-"unknown" record with `printf` when `jq` is missing. The pattern step in `audit-log.sh` also redacts inline literals (`output-scanner.sh` does not). Credential-named assignments cover hyphenated API-key request headers and segment-bounded PASS/PASSPHRASE key names (no letter or digit directly before or after, so `bypass` or `compass` do not match), and a quoted value is replaced up to its closing quote; a purely numeric value on a token-named key is kept, so usage counters are not redacted. The value after a credential-named long flag (space, `=` or quoted form, from one character) and the password part of curl's `--user`/`-u` NAME:PASSWORD value (curl commands only; a `\` line continuation does not end the scan) become `[REDACTED:credential-flag]`. A URL userinfo password, up to the last `@` before the host, becomes `[REDACTED:url-userinfo]`, keeping the scheme, user name and host. None of these rules relabels a value that starts with an earlier marker. Still logged: short flags such as `-p`, user-name-only userinfo, API-key header values under 8 characters, and a few rarer shapes (for example a userinfo password holding a raw `/`). Some over-redaction is accepted instead, such as the value after any long flag whose name ends in a credential keyword (`--no-password X` redacts `X`). The scanner does not flag these shapes in tool output. Regression suites: `tests/bash/output_scanner.bats` (60 cases) + `tests/bash/audit_log.bats` (91 cases, including 23 for the inline-literal rules and their helper, whose fake credential shapes are generated at run time by `tests/bash/helpers/fake_shapes.bash`) |
| **Context Reporting Hook** | `context-reporter.sh` — fires for orchestrator and all subagents via `PreToolUse` | Context utilization injection for gating decisions (orchestrator + subagents). Selects the Context Quality Curve threshold profile from each agent's *own* exact model ID: Claude Fable/Mythos, plus `claude-opus-5-5` (bare and `[1m]`) — admitted 2026-09-23 by user policy decision, not by DAAF quality validation — use 40%/400k, 50%/500k, and 60%/600k, set by user policy decision on 2026-10-23, not by DAAF quality validation (Fable/Mythos were validated at 30%/300k, 40%/400k, 50%/500k); exact terminal GPT 5.6 Sol and GPT-6 Astra model slugs, plus GPT-6 Sol and the `-pro` form of all three (admitted 2026-09-29 by user policy decision, not by DAAF quality validation), bare or provider-prefixed and each optionally followed by `[1m]` (`gpt-5.6-sol` / `gpt-6-astra` / `gpt-6-sol` / `gpt-6-sol-pro[1m]`), and GPT-6.1 Sol (`gpt-6.1-sol`, with its `-pro` form; admitted 2026-10-12 by user policy decision), use 60%/300k, 75%/400k, and 90%/500k; Opus except `claude-opus-5-5`, Sonnet, unknown IDs, every other GPT variant, GLM, and all other alternative-provider models use the conservative default of 40%/150k, 60%/200k, and 75%/250k unless individually validated and registered. Subagent measurements use the physical window provisioned for the subagent's *own* model (per-model mapping when it differs from the session model; Claude IDs map to 1,000,000 for Fable/Mythos 5, Opus 4.7, 4.8, 5 and 5.5, Sonnet 5.x (`claude-sonnet-5`, `claude-sonnet-5-5`) and Haiku 5.5, bare or with `[1m]`, and for any other ID outside the GPT family pre-filter that carries `[1m]` (see `agent_reference/CONTEXT_THRESHOLDS_REFERENCE.md`); other Claude IDs (e.g. Sonnet 4.6, Haiku 4.5) map to 200,000; GPT (OpenAI) model IDs map to their real windows — 1,050,000 for gpt-5.4/5.5, the wider gpt-5.6 family (Sol/Terra/Luna), gpt-6-astra, gpt-6-sol, and gpt-6-luna, plus the flagship `-pro` forms (2026-09-29 policy decision), and gpt-6.1-sol (2026-10-12 policy decision), on API/OpenRouter routes (the ChatGPT-subscription/Codex lane is backend-capped at 919,000, measured 2026-09-05 for both `gpt-6-astra` and `gpt-5.6-sol`, and the hook lane-gates it via `DAAF_PROVIDER_SHIM`+`SHIM_BACKEND_MODE`), 400,000 for gpt-5.2/gpt-5.4-mini, 128,000 for -chat; exact `z-ai/glm-5.2` and terminal date snapshots map to the OpenRouter-reported 1,048,576-token physical window). Threshold-profile selection and physical-window mapping are separate lookups: Terra, Luna (including `gpt-6-luna` and their `-pro` forms), mini, chat, date snapshots, future GPT variants, trailing modifiers, and all GLM IDs remain conservative unless separately registered. Provider-dotted Claude IDs (OpenRouter's `anthropic/claude-opus-5.5`) are normalized to the hyphenated form for classification only; caches keep the raw ID (see `agent_reference/CONTEXT_THRESHOLDS_REFERENCE.md`). The model lookup parses the transcript line by line, so a partly written last line does not hide the model, and for a subagent it falls back to the model attachment at the top of the subagent's transcript when no record carries a model yet. Model cached in `/tmp/claude-subagent-model-*`, shared with `subagent-bar.sh`. |
| **Statusline (main bar)** | `context-bar.sh` — registered via `statusLine` in `settings.json`; fail-open, exits 0 on all paths | Live session display: model, directory, branch, context-utilization bar, effort level, subscription rate-limit windows. Shares the session context-window size with hooks via `/tmp/claude-ctx-window-*` (bare-integer contract consumed by `context-reporter.sh`) |
| **Statusline (agent panel)** | `subagent-bar.sh` — registered via `subagentStatusLine` in `settings.json`; fail-open, exits 0 on all paths | Per-subagent rows in the agent panel: agent type, model, status, token count, and a context bar colored by the Context Quality Curve threshold profile selected from each subagent's *own* exact model ID (Claude Fable/Mythos, plus `claude-opus-5-5` (bare and `[1m]`) — admitted 2026-09-23 by user policy decision, not by DAAF quality validation: 40%/400k, 50%/500k, 60%/600k, set by user policy decision on 2026-10-23, not by DAAF quality validation (Fable/Mythos were validated at 30%/300k, 40%/400k, 50%/500k), with the six threshold assignment lines kept byte-identical with `context-reporter.sh` by a lockstep test in `tests/bash/context_reporter.bats`; exact terminal GPT 5.6 Sol and GPT-6 Astra model slugs, plus GPT-6 Sol and the `-pro` form of all three (admitted 2026-09-29 by user policy decision, not by DAAF quality validation), bare or provider-prefixed and each optionally followed by `[1m]` (`gpt-5.6-sol` / `gpt-6-astra` / `gpt-6-sol` / `gpt-6-sol-pro[1m]`), plus GPT-6.1 Sol (`gpt-6.1-sol`, with its `-pro` form; admitted 2026-10-12 by user policy decision): 60%/300k, 75%/400k, 90%/500k; conservative default for all others unless individually validated and registered: 40%/150k, 60%/200k, 75%/250k). The bar is computed against the physical window provisioned for that subagent's own model (per-model mapping when it differs from the session model; Claude IDs map to 1,000,000 for Fable/Mythos 5, Opus 4.7, 4.8, 5 and 5.5, Sonnet 5.x (`claude-sonnet-5`, `claude-sonnet-5-5`) and Haiku 5.5, bare or with `[1m]`, and for any other ID outside the GPT family pre-filter that carries `[1m]` (see `agent_reference/CONTEXT_THRESHOLDS_REFERENCE.md`); other Claude IDs (e.g. Sonnet 4.6, Haiku 4.5) map to 200,000; GPT (OpenAI) model IDs map to their real windows — 1,050,000 for gpt-5.4/5.5, the wider gpt-5.6 family (Sol/Terra/Luna), gpt-6-astra, gpt-6-sol, and gpt-6-luna, plus the flagship `-pro` forms (2026-09-29 policy decision), and gpt-6.1-sol (2026-10-12 policy decision), on API/OpenRouter routes (the ChatGPT-subscription/Codex lane is backend-capped at 919,000, measured 2026-09-05 for both `gpt-6-astra` and `gpt-5.6-sol`, and the hook lane-gates it via `DAAF_PROVIDER_SHIM`+`SHIM_BACKEND_MODE`), 400,000 for gpt-5.2/gpt-5.4-mini, 128,000 for -chat; exact `z-ai/glm-5.2` and terminal date snapshots map to the OpenRouter-reported 1,048,576-token physical window). Threshold-profile selection and physical-window mapping are separate lookups: Terra, Luna (including `gpt-6-luna` and their `-pro` forms), mini, chat, date snapshots, future GPT variants, trailing modifiers, and all GLM IDs remain conservative unless separately registered. Provider-dotted Claude IDs (OpenRouter's `anthropic/claude-opus-5.5`) are normalized to the hyphenated form for classification only; caches keep the raw ID (see `agent_reference/CONTEXT_THRESHOLDS_REFERENCE.md`). Each row's model comes from the same line-wise lookup as `context-reporter.sh`, with the same model-attachment fallback for a subagent transcript that has no model record yet. Read-only consumer of the `/tmp/claude-ctx-window-*` cache; shares the per-subagent model cache (`/tmp/claude-subagent-model-*`) with `context-reporter.sh`. |
| **Session Archive Hook** | `archive-session.sh` | Session transcript archiving on exit |
| **Session Recovery Hook** | `recover-session-logs.sh` — fires on `SessionStart` | Activity logging + crash recovery: archives orphaned transcripts from sessions that terminated without reaching `SessionEnd` |
| **Container Isolation** | Docker with `cap_drop: ALL`, non-root user | OS-level blast radius containment |
| **`.claudeignore`** | File-level exclusion | Prevents indexing of credentials |
| **Pre-commit Hooks** | `.pre-commit-config.yaml` | Catches large files, private keys, merge conflicts at commit time |
