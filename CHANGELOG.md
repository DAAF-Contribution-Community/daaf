# Changelog

All notable changes to DAAF for each release version are documented here, in reverse chronological order.

## Table of Contents

- [Unreleased](#unreleased)
- [v3.0.2 -- 2026-08-18](#v302--2026-08-18)
- [v3.0.1 -- 2026-07-29](#v301--2026-07-29)
- [v3.0.0 -- 2026-07-17](#v300--2026-07-17)
- [v2.1.0 -- 2026-05-02](#v210--2026-05-02)
- [v2.0.1 -- 2026-04-05](#v201--2026-04-05)
- [v2.0.0 -- 2026-03-31](#v200--2026-03-31)
- [v1.0.0 -- 2026-02-22](#v100--2026-02-22)

---

## Unreleased
<!-- AT TAG TIME: assign the version number and date; confirm scope before release -->

### Claude Code 2.1.281 and the Opus 5.5 Default

DAAF's pinned Claude Code CLI advances **2.1.202 to 2.1.261 to 2.1.280 to 2.1.281** across three reviewed bumps, and the shipped session model becomes **Claude Opus 5.5** (`claude-opus-5-5[1m]`). The 2026-09-05 bump to 2.1.261 brought Claude Fable 5.1 and Opus 5 window registration; the 2026-09-23 bump to 2.1.280 brings Opus 5.5 itself, which requires 2.1.280 or later and is now the `opus` alias on the Anthropic API; a 2026-09-24 follow-on bump to 2.1.281 makes Claude Code's dangerous-`rm` check prompt for command-substitution targets even in bypass mode and fixes several stream-handling failures behind proxies and gateways. **2.1.276 is a hard minimum for anyone running the provider shim** — three separate `ANTHROPIC_BASE_URL` gateway regressions landed and were fixed inside the 2.1.265-2.1.275 window. Opus 5.5 also joins DAAF's validated extended-horizon context-threshold profile by explicit user decision. DAAF now coexists with claude.ai account skill and plugin sync, which a repository cannot turn off, and documents how users can opt out in their own settings.

### GPT-6 Astra Support

DAAF now supports OpenAI's **GPT-6 Astra** flagship (model slug `gpt-6-astra`) across both the OpenRouter route (Option C) and the provider-shim lanes (Option F), with parity to the existing GPT-5.6 documentation. The bundled Codex CLI advances to **0.153.2**, and Astra is registered in DAAF's validated context-threshold profile at GPT-5.6 Sol parity.

### Context Monitoring: OpenRouter Claude Names and the GPT-6 Registry

OpenRouter reports Claude models with a dotted version (`anthropic/claude-opus-5.5`), and DAAF's context monitoring used to misread them. An Opus 5.5 subagent at 250k tokens read CRITICAL instead of NOMINAL, and an Opus 4.8 subagent was measured against a 200k window instead of its 1M window. The hook and the agent-panel statusline now classify these names like Anthropic's own `claude-opus-5-5` spelling. Separately, by user policy decision rather than DAAF validation, `gpt-6-sol` now reads like `gpt-5.6-sol`, `gpt-6-luna` like `gpt-5.6-luna`, and any flagship `-pro` slug like its non-pro base. The hook's half ships as a user-applied patch. Follow-up passes:
- extend the same model list to the deploy-smoke context check;
- re-price the GPT models in the installation guide and in DAAFBench, and fix DAAFBench's per-model API-equivalent cost accounting;
- make Sol (strong) plus Luna (fast) the recommended GPT pairing in place of Sol plus Terra;
- make the statusline tolerate effort-suffixed model ids.

### Execution Wrapper Evidence Integrity

`scripts/run_with_capture.sh` now distinguishes computation success from evidence-capture and persistence success. A run that computed correctly but whose execution log was truncated or never appended used to exit 0 and print `SUCCESS`; it now prints an `EVIDENCE INCOMPLETE` banner, retains the capture buffer, and exits 74.

### Truthful Checkpoint and QA Templates

The copyable validation and QA templates (`VALIDATION_CHECKPOINTS.md` CP1-CP4, Join, Substantiveness, CPP1-CPP4, CPP-SKILL; `QA_CHECKPOINTS.md` QA1-QA4b, QAP1-QAP4; Python and R) could report PASS when the evidence for the claim was absent -- a missing convergence field, absent robustness signs, an unrecognized configuration string, an empty column list, a zero that a truthiness guard skipped. Every check now emits one of `[PASS]` (with its numbers), `[WARNING]`, `[FAIL]`/`[BLOCKER]`, `[NOT VERIFIED]`, `[SKIPPED]` (declared not applicable, with a reason), or `[INFO]`; a count line precedes a derived verdict; and a checkpoint with unverified checks cannot read PASSED. CP4 is now unambiguously the Stage 8 post-analysis and visualization checkpoint, with the former report-and-plan sub-checks re-homed as Pre-Output Verification (Stage 12). A permanent regression suite (`tests/python/test_checkpoint_templates.py`) executes the templates from the live reference files against the original defect fixtures.

### Synthetic-Path Checkpoints and Data-Recipe Corrections

The privacy-preserving Data Onboarding path now speaks the same truthful-checkpoint language as every other DAAF checkpoint. Its three review checkpoints (QAS-A disclosure-safety, QAS-B report consistency, QAS-C synthetic-vs-profile fidelity) are defined canonically in `QA_CHECKPOINTS.md`, and two new shipped script-halting validators, CPS-INTAKE (DS-3) and CPS-GEN (DS-5), live in `VALIDATION_CHECKPOINTS.md`; the shipped outbound profiler and synthesizer templates emit counted, evidence-bearing outcome lines instead of a bare boolean. Because a disclosure leak is irreversible, this path carries stricter rules than the rest: disclosure checks can never be declared not-applicable, a check that could not be verified is a BLOCKER, WARNING is not a legal QAS-A verdict, and a passing disclosure check reports counts and thresholds rather than the values it examined. Two data-source skill recipe contradictions (S04) are corrected: the election county-returns skill no longer recommends a bare `mode == 'TOTAL'` filter anywhere, and the SAIPE examples threshold the child-poverty share on its actual 0-1 scale.

### Windows Backups: Named Pipes No Longer Truncate the Copy

A Windows backup could stop partway through while still printing "Successfully copied": one named pipe in the volume (the provider shim leaves stale `output.fifo` files behind) aborted the host-side copy, and every file after it was dropped. In the field report, from a sibling project running a variant of this script, the last progress reading was 94% when the error appeared. A separate probe of the maintainer's volume found that 714 of its 71,820 files sort after the first stale pipe, a loss that would slip under the 1% file-count check (718 files). Backups now delete named pipes, sockets, and device nodes while staging, the same way they already handle symlinks, and print a one-line note saying how many they skipped from the research-data volume. On Windows, the backup also no longer treats an unreadable copy exit code as success.

### Windows Control Panel and Backups: Install Folders With Spaces

If the DAAF install folder sat under a path with a space, such as `C:\Users\John Smith\` or a `OneDrive - Org` folder, every Control Panel option that hands off to another script (Claude Code, the container terminal, Quarto, backup, restore, update, rebuild) failed, and the backup's copy step failed too. PowerShell's `Start-Process` joins a list of arguments with plain spaces and quotes none of them, so the path arrived in pieces. The Windows scripts now quote every argument before handing it over. The Control Panel also no longer reports a child script's unreadable exit status as a clean return, and a backup whose copy step reported an error while every file still arrived now ends with the WITH WARNINGS banner instead of "Backup complete!" on both Windows and macOS/Linux.

### Backups and Restore: Exact, Error-Aware Completeness Checks

A Windows backup could count fewer files than it had actually copied, and its 1% tolerance could just as easily have hidden a real gap. In the field report, Windows PowerShell 5.1 missed 187 correctly copied files in very deep folders, past Windows' classic path-length limit. Backups now check themselves against an exact snapshot of your data taken as the copy starts, with no tolerance. On Windows they count the finished backup inside Docker, which has no path-length limit. When a backup can't count every file in the finished copy, it shows the count as a minimum (like `72834+`) with a warning and ends WITH WARNINGS, or, if it could count nothing at all, stops with an error. It never shows a short "exact" number or "0 files". Backups also print the name of the Docker volume they copy (`Source volume: ...`). On Windows they give an up-front notice when some files will have paths over 260 characters. Restore also shows an unreadable backup's count as a minimum, but more quietly: on Windows the scan of the chosen backup adds a note, and the list of backups shows only the `+`. The macOS/Linux restore goes further and refuses a backup it can't fully read, before it copies anything. After the copy, restore now checks the restored files against the backup exactly, with no tolerance (see "Restore: Your Data Stays Untouched Until the Backup Is Copied and Checked" below), and when it can't count the restored files it says so instead of reporting 0. Like a backup, a restore that printed a warning now ends with `Restore completed WITH WARNINGS -- verify before relying on it` instead of "Restore complete!". On Windows this also happens when it could count only a minimum of the backup's files. Its exit code does not change. The macOS/Linux scripts count the same way as their Windows twins, apart from that deliberate difference in restore.

### Windows Backups: File Names Windows Cannot Create No Longer Stop the Copy

A Windows backup stopped partway when the Docker volume held a single file or folder name that Windows cannot create. In the field report (Docker Client 29.1.3), the copy stopped at a test file whose name held a line break, after 72,386 of 73,785 files; the exact count check caught it and failed the run, but the backup was unusable. Names like that are legal inside DAAF: a line break or other control character, any of `: * ? < > | \` or a double quote, a trailing dot or space, device names such as `CON`, `NUL.txt` or `COM1`, and two paths that differ only in upper/lower case. The Windows backup now leaves those files and folders out on purpose and copies everything else. It lists them by name in a `WARNING:` with the total number of files left out and tells you to rename them inside DAAF and back up again, and it ends WITH WARNINGS. The list is printed right after the final file count, so it still appears if the backup then stops with an error for another reason, and if the list itself cannot be read back from Docker, a separate `WARNING:` says names may have been left out unlisted. Where two paths differ only in case, the one that sorts first is kept. Two folders that differ only in case are merged by Windows, so they are listed but kept. The `Snapshot:` line counts the left-out files separately, so they are not mistaken for changes to your data. The same applies to the Claude Code state volume. On macOS nothing is removed, because these names are legal there, but paths that differ only in case get a `WARNING:` too, since the default macOS disk format treats each pair as one path. Linux backups are unchanged. For contributors, `scripts/check_workspace_invariants.sh` gains a third invariant: it now also fails on any name Windows cannot create and on any case-only name pair anywhere in the workspace outside `.git`, so a leftover test fixture is caught before it reaches a backup, and `CLAUDE.md`'s self-cleaning-probe rule now covers such fixtures.

### Restore: Your Data Stays Untouched Until the Backup Is Copied and Checked

A restore used to erase the DAAF Docker volume first and then copy the backup in. A copy that failed partway, or a Ctrl+C at the wrong moment, could leave DAAF with an empty or half-filled volume. Restore now copies the backup into a temporary Docker volume first and checks it there: the file count must match the backup. Only then does it ask you to type `RESTORE`. After you confirm, it makes sure the temporary copy is still the one it checked, replaces your data with it in one step inside Docker that is designed so a Ctrl+C cannot stop it halfway (confirmed with real Docker in a Windows field test), confirms that the result matches the copy file for file, with exactly the same number of files, and removes the temporary volume. Anything that goes wrong before that last step, including cancelling, leaves your DAAF data unchanged, and the message says so. If the last step itself goes wrong, the checked copy is kept and the message says how to finish; if only the Claude Code part of it fails, the message says your project files were already restored and checked. If the checked copy has vanished just as that step starts, the step replaces nothing and the message says so. Your Claude Code login and history follow the same pattern; a problem preparing them now stops the restore before anything changes, where it used to finish with a warning. Before copying, restore checks that Docker has enough free space and refuses if it doesn't: up to about twice the backup's size, plus a margin, or about the backup's size plus the margin when your current data is about as large as the backup. That check sees only Docker's own disk; on Windows and macOS, that is a virtual disk file on your computer's drive, which needs the room too (Docker Desktop for Linux keeps containers and images in such a file as well, so the same may apply there). If an earlier restore was interrupted, the next one finds the temporary copy it left behind, says whether your data may have been affected, and asks whether to remove it and continue. If something else changes or removes a restore's temporary copy while it waits (a second restore window, for example), the restore notices and stops without removing anything. If Docker does not answer the check for a running DAAF, at the start or just before that last step, the restore stops instead of assuming nothing is running. The Windows restore, started from the Control Panel and interrupted with Ctrl+C while preparing, at the RESTORE prompt, or while replacing the data, now ends with exit code 130 (a Ctrl+C during the short checks after the replacement still ends with 0; the next restore then finds the kept copy), so the Control Panel reports it as not completed instead of as a clean return (verified with PowerShell 7 on Linux; in the Windows field test, a Ctrl+C in the Control Panel's console ended the Control Panel too, so there the restore's own recovery text is what you see). Otherwise the prompts are unchanged: stop DAAF if it is running, pick a backup, type `RESTORE`. A Windows field test on a throwaway install, run while the real one was in use, passed every data-safety check: the real install's data was provably untouched. It found three problems, now fixed: a leftover temporary copy that a never-started Docker container still held could not be removed (the restore now removes such containers itself, and its messages say how to find one), Windows PowerShell 5.1 hid Docker's own error text, and a Ctrl+C while the Claude Code login and history were being replaced said the DAAF data was being replaced.

### Control Panel: Restart Container Applies Your Settings Changes

Docker reads `environment_settings.txt` only when it creates the DAAF container, so a changed API key, provider setting, or port used to mean typing `docker compose down` and launching again by hand. The DAAF Control Panel now has a **Restart Container** option, right after Rebuild Container, that does this for you. It stops and recreates the container (`docker compose down`, never with `-v`, then `docker compose up -d`), waits until the container is ready, and checks it. That usually takes under a minute, with no image build. Your research files and Claude Code login are kept. It asks first (the default is No), because it ends any open Claude Code session, container terminal, or web service for that install, including ones in other windows. It refuses, with nothing changed, if `environment_settings.txt` now sets a different `DAAF_PROJECT_NAME`: that name decides which install and which research data volume Docker uses, so restarting under it would start a different install and your research would appear to be missing. Settings the file marks "rebuild required", such as `DAAF_DEV` or turning on the provider shim for the first time (its section is marked "rebuild required, once"), still need Rebuild Container. **Stop Web Services moves from option 11 to option 12.**

### Detailed Notes

Disclosure: These notes were AI-drafted from the verified change-set and then reviewed by hand.

#### Claude Code Pin: 2.1.202 to 2.1.261 (2026-09-05) to 2.1.280 (2026-09-23) to 2.1.281 (2026-09-24)

Three reviewed pin bumps land together in this release. The **2.1.261** bump (2026-09-05, delta review 2.1.213-2.1.261) was taken as the first version where Claude Fable 5.1 (`claude-fable-5-1`, added 2.1.257) works without the `[1m]`-to-silent-200K window bug fixed at 2.1.260; the same session registered Opus 5's 1M physical window in `context-reporter.sh` and `subagent-bar.sh` after observing bare `claude-opus-5` and `claude-opus-5[1m]` both report a 1M window under `/model` + `/context`, pinned `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, and migrated the eight `Write(path)` deny rules to `Edit(path)` — a migration 2.1.276 later vindicated outright by fixing `/update-config` to stop writing `Write(path)` rules that "file permission checks don't match". The **2.1.280** bump (2026-09-23, delta review 2.1.262-2.1.280, 16 published headings) is driven by Opus 5.5, which the model-configuration docs state requires Claude Code v2.1.280 or later. The delta also brings symlinked-write permission judging, two fixes for a finished subagent's report being lost (one on compaction of the launching conversation), the generalized advisor-header retry for gateways, honored `SessionEnd` hook timeouts, and a correction to the context meter double-counting advisor turns — which had been firing auto-compact at roughly half the real window. Against that: a `Read`/`Edit`-deny-on-unanalyzable-Bash behavior was added at 2.1.268 and reverted at 2.1.273, the second consecutive add-then-revert cycle on deny-rule-on-Bash semantics, so the safety battery is treated as non-optional at every pin rather than assumed stable. The **2.1.281** bump (2026-09-24, delta review of the single 2.1.281 release) follows a day later. Its dangerous-`rm` check now prompts for a recursive `rm` whose target is only command-substitution output even in bypass mode, waiting two minutes before denying; that closes a gap for spellings such as `rm -r "$(pwd)"` that neither `bash-safety.sh` nor DAAF's `rm` deny rules caught. It also fixes proxy and gateway stream failures (a cleanly closed but truncated stream shown as complete, dropped or duplicated stream events, a stop reason lost to a trailing usage-only frame) and several session-resume paths. Two points remain open: whether a headless `-p` run in bypass mode waits the full two minutes on the new prompt is not yet verified, and the new `"attribution": false` setting makes older CLIs, 2.1.280 included, skip the entire settings file that holds it — DAAF does not set it, and the boolean form would make a rollback silently drop every hook registration and deny rule, so it is now permanently prohibited (see Post-Rebuild Guardrails below). **Hard minimum 2.1.276, rollback target 2.1.280.** The floor is the shim: 2.1.265 broke every turn on third-party `ANTHROPIC_BASE_URL` endpoints via an Artifact-tool input-schema regex (fixed 2.1.268) and independently forced Cloud-gateway sign-in through the undocumented `CLAUDE_CODE_USE_GATEWAY` variable (fixed 2.1.266), and 2.1.275 broke every proxied request with an `Input tag 'advisor_20260301'` 400 (fixed 2.1.276). Any pin in 2.1.265-2.1.275 is a known-broken shim lane, which also makes the npm `stable` label (2.1.267 at the 2.1.280 review, 2.1.273 at the 2.1.281 review) unusable here; DAAF pins an exact version with `DISABLE_AUTOUPDATER=1`, so channel labels are informational. The rollback target is 2.1.280 rather than 2.1.261 because 2.1.261 predates Opus 5.5 and cannot run the shipped default model. 2.1.280's live post-rebuild probes had not been run when 2.1.281 was pinned, so both versions are verified in one combined post-rebuild pass. A post-rebuild verification checklist and a shim-safety memo for the separate shim workstream are archived in `research/2026-09-23_FrameworkDev_ClaudeCode_Upgrade_2.1.280/`, and the 2.1.281 delta review and its verification addendum in `research/2026-09-24_FrameworkDev_ClaudeCode_Upgrade_2.1.281/`.

#### Opus 5.5 as the Shipped Default, and Its Threshold Promotion

`.claude/settings.json` moves `env.ANTHROPIC_MODEL` from `claude-opus-5[1m]` to **`claude-opus-5-5[1m]`**. Opus 5.5 (`claude-opus-5-5`, released 2026-09-22) carries a 1M context window, 128K max output, and officially published pricing of **$4 input / $20 output / $0.20 cache-read per Mtok** — verified from Anthropic's model page and concordant with the changelog entry, and now registered in `benchmarks/config/models.yaml` with that citation. The existing `claude-opus-5` entry's $5/$25 is left unchanged but annotated as an unverified user recollection, so the two entries are no longer mistakable for equally sourced. Note that the `opus` alias flips to Opus 5.5 on the Anthropic API at 2.1.280 regardless of this setting, which moves all nine `model: opus` DAAF agents with no config edit; four API behaviors change with it (thinking can no longer be disabled, forced tool use returns 400, thinking blocks are model-bound, and `computer_20251124` is rejected).

Separately, **Opus 5.5 joins the validated extended-horizon context-threshold profile** (ELEVATED 30%/300k, HIGH 40%/400k, CRITICAL 50%/500k) alongside Fable and Mythos. This is recorded as a **user policy decision of 2026-09-23 that deliberately departs from the 2026-07-24 "validate before promoting" doctrine**: no sustained-session DAAF measurement of Opus 5.5 output quality past 300k exists, and the promotion rests on the model's documented long-horizon design plus the user's acceptance of the risk. The provenance is carried in CLAUDE.md, `CONTEXT_THRESHOLDS_REFERENCE.md`, and both glob sites so it is never mistaken for an evidence-backed registration. The profile arm is boundary-anchored: the terminal slug must be exactly `claude-opus-5-5` or `claude-opus-5-5[1m]`, bare or provider-prefixed, so near-misses such as `claude-opus-5-5-mini` stay conservative. It is never the substring `*opus-5*`, which would silently promote every bare Opus 5 agent. Both bats suites carry lock cases asserting that `claude-opus-5` and `claude-opus-5[1m]` still read CRITICAL at 250k. The physical-window arm gains an explicit `*opus-5-5*` too; an executed `case` repro proved the pre-existing `*opus-5*` already matched it, so that arm's behavior is unchanged and the explicit spelling exists only so a future non-1M Opus cannot inherit the coincidence. `context_reporter.bats` and `subagent_bar.bats` each gain ten cases (six window, profile, and bare-Opus-5 lock cases, plus four boundary-anchoring locks). Because `.claude/hooks/` is a user-only surface, the hook's half of the change ships as a user-applied hook edit.

#### claude.ai Skill and Plugin Sync: Coexist, With a User-Scope Opt-Out

Earlier in this development cycle, `settings.json` gained top-level `syncClaudeAiSkills: false` and `syncClaudeAiPlugins: false` to keep claude.ai account skills and plugins out of DAAF sessions (the keys never reached a tagged release). **Those keys never took effect.** The official settings reference limits both to user, local, or managed scope ("A repository can't turn it off for you"), so at project scope they were inert from the start. The post-rebuild pass on 2.1.281 confirmed this: synced account skills appeared in the user's `/skills` UI under their short names and in the model's skill listing as `anthropic-skills:<name>`, and a synced plugin bucket was populated after the rebuild. Both keys are removed rather than left to suggest a protection that does not exist. DAAF can't make a per-user setting durable for every user from the repository, so it now **coexists** with sync. The orchestrator skill's built-in-skills section extends its disambiguation rules to synced skills and plugin-namespaced skills and agents: they are not DAAF components, DAAF protocols take precedence, and plugin-provided agent types are never dispatched for pipeline work. The technical FAQ entry is rewritten to match. It is candid that a synced plugin can carry hooks, agents, and MCP servers that run outside DAAF's audited hook set (one synced plugin was observed registering `PostToolUse(Edit|Write)` and `Stop` hooks). It also gives the opt-out: set both keys to `false` in `~/.claude/settings.json` inside the container, or in `.claude/settings.local.json`. At user scope this also moves synced copies to `~/.claude/{skills,plugins}/.trash/`.

#### Post-Rebuild Guardrails and Documentation Corrections

Findings from the 2.1.281 post-rebuild verification pass, folded back into the ship docs:

- **Boolean `attribution` is permanently prohibited.** A new § 8 row, CC9, in `FRAMEWORK_INTEGRATION_CHECKLIST.md` requires `jq empty` and `jq -e '(.attribution|type) != "boolean"'` after any `settings.json` edit. `tests/bash/settings_permissions.bats` gains a matching case (10 to 11), `BOUNDARIES.md` gains a Never-Do row, and `CONTRIBUTING.md`'s change-surface matrix now cites CC1-CC9. The prohibition holds regardless of the current rollback target, because any older CLI skips the whole file.
- **Local settings outrank the shipped model pin.** The FAQ's session-start-model entry and the installation guide's GPT Step 3 now note that a personal `.claude/settings.local.json` `env` block overrides `settings.json`. A stale local `ANTHROPIC_MODEL` made every session open on the wrong model during the pass, and the fix is to check that file first.
- **Nested dispatch has a harness layer.** With `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, Claude Code is observed (2.1.261, 2.1.281) to withhold the Agent/Task tool from every subagent. The Claude Code changelog says only that the setting "disable[s] nesting". `BOUNDARIES.md` (dispatch-authority invariant and the Defense-in-Depth row), the orchestrator skill, checklist item A1c, and `agent-authoring` now describe that harness limit as the first layer, named agents' `tools:` lists as the second, and `block-nested-dispatch.sh` as the backstop. The hook's header still describes a "fixed, non-configurable depth-5 cap"; that comment correction is a user-only hook edit and is handed off separately.
- **Subagent results return inline under DAAF's settings.** With `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, dispatches on 2.1.281 are observed to run in the foreground and return their full reports inline in the dispatching turn, with no background acknowledgement and no later completion notification. With the same setting, 2.1.281's send-now key cancelled a running tool rather than moving it to the background as its changelog entry describes. The "run in the background by default" clauses in the orchestrator skill's Wave Barrier Discipline section, the mode references, the `WORKFLOW_PHASE` files, `CLAUDE.md`'s async completion note, and the technical FAQ now describe delivery as version- and setting-dependent. The wave-barrier norm itself is unchanged and applies either way. `full-pipeline-mode.md`'s "v2.1.186+" is corrected to 2.1.198, the release whose changelog makes background dispatch the default.
- **Stale glob text corrected.** `CONTEXT_THRESHOLDS_REFERENCE.md` and the Opus 5.5 note above now describe the anchored profile arm instead of the earlier loose `*opus-5-5*` spelling, and several stale bats comments are updated (comments only).

#### Deploy-Smoke Verdicts Require Positive Evidence

The 2.1.281 post-rebuild pass found that several deploy-smoke probes could PASS a run in which no model answered. A stale local `ANTHROPIC_MODEL` produced a `model_not_found` run. The CLI wrote its error sentence as a `<synthetic>` assistant record, and T1.1 accepted it as "a response". Two probes also matched framework prose instead of evidence: T1.4 matched CLAUDE.md text, and T2.6 matched the orchestrator skill's sentence about nested subagents. T1.6 and T1.7 also passed that run without evidence of their own. T1.5 read back caches that T1.6's own synthetic payload had written, and the "200000 is headless behaviour" note was describing that harness constant.

- **Live-run health gate.** A new shared check fails a run if any of these hold:
  - the CLI result has `is_error`, a non-`success` `subtype` other than `error_max_turns`, or a non-null `api_error_status` (every observed value is null, so reading a non-null one as an API failure is inferred and the reason says so);
  - the transcript ends on an assistant record with `isApiErrorMessage` or a placeholder model (DAAFBench's `_is_non_model_marker`), with no real-model answer after it;
  - `modelUsage` names no real model.

  T1.1, T1.7 and all six Tier 2 probes then FAIL with the reason instead of passing or skipping. T1.1 also requires `SMOKE_TIER1_COMPLETE` in the response. Two cases are a WARN instead, because a real model did answer: a recovered transient error (a `<synthetic>` `server_error` record followed by a real answer, seen in about 20 headless GPT-lane transcripts), and a stop at `--max-turns`. For these, T1.1 and the Tier 2 probes judge their own evidence and turn a PASS into WARN with the reason; T1.1 uses the same shared gate helpers as Tier 2.
- **Tier 1.**
  - T1.4 counts only `Context utilization [` inside a hook attachment, once per `toolUseID` (each injection is recorded as both a `hook_success` and a `hook_additional_context` attachment). Absence stays INFO, because a one-tool headless run often ends before the reporter can measure.
  - T1.5 still runs first. It now judges the model cache against the transcript model: PASS when they match, WARN on a mismatch, INFO when the cache is absent. It treats a missing context-window cache as expected, since `-p` renders no statusline.
  - T1.6 builds its payload from the observed model and renders into `evidence/t16_statusline_cache/` via `DAAF_CONTEXT_BAR_CACHE_DIR`, so it can no longer write the session's `/tmp` caches.
  - T1.7 no longer raises `TypeError` on `None` token counts, which used to abort the whole run with no report.
- **Tier 2.**
  - T2.3, named "Web access (WebSearch + fetch protocol)", requires a WebSearch or `web_fetch.sh` call whose result is not an error.
  - Tool-call inputs are read through one normalizer. A `tool_use` whose `input` is a string or list no longer raises `AttributeError` in T2.6 (which aborted the run with no report), and no longer substring-matches in T2.3–T2.5. `_evaluate_t26` documents that a subagent not started by an orchestrator Agent/Task call, such as `/code-review` or a forked skill, reads as unlinked and FAILs, so T2.6 sessions must launch no other subagent.
  - T2.4 requires a successful `polars` Skill call.
  - T2.5 requires `block-remote-isolation.sh`'s own `updatedInput` attachment.
  - T2.6, renamed "Nested-dispatch prevention", judges the subagent transcripts; the main transcript is read only to link each subagent transcript to its top-level call. It PASSes on a real deny record, or when neither the subagent's recorded tool list nor its deferred tool names include Agent/Task. That second case is the depth-1 harness layer, and the detail says the hook backstop was not exercised. The harness layer also PASSes when the subagent tried a nested call anyway and every attempt got an error result because the tool was absent ("No such tool available: Agent"); a live 2026-09-24 run graded exactly that case WARN before this fix. The "because the tool was absent" wording is used only for the harness's "No such tool available" error; other errors get neutral wording. It FAILs when a subagent's own Agent/Task call returns a non-error result, or when a subagent transcript links to no top-level Agent/Task call. Linking uses the transcript's agentId (equal to the parent result's `toolUseResult.agentId`) or its opening prompt (equal to the parent's `input.prompt`). A count check (more transcripts than calls) covers transcripts with neither. Errored top-level calls are kept: a call that "terminated early due to an API error" did start a subagent. So a retried outer dispatch, including one after a terminated-early subagent, does not read as nesting.
- **Tier 0.** T0.7 no longer writes `/tmp`: its synthetic render (session `smoke-synthetic`) points both `DAAF_CONTEXT_BAR_CACHE_DIR` and `DAAF_SUBAGENT_BAR_CACHE_DIR` at `evidence/t07_statusline_cache/`, the same approach T1.6 uses, and a read-only before/after `stat` of the exact `/tmp/claude-*-smoke-synthetic` paths turns the probe to WARN if a renderer ignores its override.
- **New Tier 0 probes.**
  - T0.12 compares `.claude/settings.local.json` `env` against `settings.json` `env`. It FAILs when a model selector is shadowed with a different value and WARNs for any other shadowed key and for a model selector set only in the local file (e.g. `CLAUDE_CODE_SUBAGENT_MODEL`).
  - T0.13 lists synced claude.ai skills and plugins on disk, labels each plugin disabled, enabled or not set from the user, project and local `enabledPlugins` settings (precedence inferred), and names the hook events each plugin registers. It is INFO only, in line with the coexist decision, including when listing the directories fails.

`tests/python/test_deploy_smoke.py` grows from 83 to 146 cases, built from minimal excerpts of the observed failing and passing transcripts. The skill and `interpreting-results.md` are updated to match.

#### Checkpoint and QA Templates: Evidence-Bearing Outcomes

Repairs the S03 finding from the 2026-09-05 review synthesis. Both template families gain an explicit outcome vocabulary and a `not_applicable` applicability mapping: a check whose inputs are missing, empty, `None`/`NULL`/`NA`, wrong-typed, or an unrecognized configuration value emits `[NOT VERIFIED]` naming what is missing (unknown config strings fail outright), and only a declared-with-reason skip emits `[SKIPPED]`. Boolean and max-severity accumulators are replaced by counters; each template prints `Checks: N passed, N warnings, N failed|blockers, N not verified, N skipped` (the QA family adds `N info`) and then a derived verdict. Script-halting checkpoints (CP1-CP4, Join, CPP1-CPP4, CPP-SKILL) print `CP{n} VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED` (NOT VERIFIED forces FAILED; zero checks run is FAILED; FAILED still raises); review checkpoints (QA1-QA4b, QAP1-QAP4) print `QA{n} RESULT: PASSED | WARNING | BLOCKER` (NOT VERIFIED forces at least WARNING, with a documented escalation rule). `[WARN]` is retired in favour of `[WARNING]`; `[FAIL]` (script-halting) and `[BLOCKER]` (review severity) stay distinct. Metric corrections: suppression is recomputed per column (sentinel count over column rows) and compared to the Plan's reported rate with `0` a valid value; aggregation spot-checks use an absolute tolerance base, treat a zero source with a nonzero result as a blocker, and dispatch on an explicit function list; robustness requires both signs and treats `0` as a real sign; `expected_relationship` gains an explicit `aggregated` branch; join cardinality is bounded per (cardinality, join type) pair, and duplicate keys on a side the declared cardinality says is unique are a `[FAIL]`, not a warning; empty inputs fail rather than reporting 0% loss; text-pattern checks are labelled as such and downgraded; the R variants use `[[` indexing, `NA` guards, `perl = TRUE` regexes, and no longer crash on `NULL`/all-`NA` inputs. CP4 semantics are reconciled across the framework: CP4.1 analysis outputs valid, CP4.2 critical nulls, CP4.3 figures, CP4.4 correct data source, `checkpoint:auto` at Stage 8; a new un-numbered Pre-Output Verification (Stage 12) section, owned by data-verifier, carries the former report-section, Plan-consistency, Research-Outcomes and Hypotheses items. The Data Onboarding profiling checkpoints (CPP1-CPP4, CPP-SKILL) move from assert-and-declare to the same accumulator, with the drifted duplicate code in `WORKFLOW_PHASE_DO_PROFILING.md` collapsed to a pointer plus config stanza, CPP4 checking structured interpretation records line by line, and CPP-SKILL enforcing anchored headings, the decision-tree minimum, either coded-values or value-interpretation reference files, and an adjudication channel for manual checklist items. QAP1-QAP4 gain per-check not-applicable / not-verifiable columns, the HIERARCHICAL linkage row, and a count-line/result contract; onboarding gates, both STATE templates, the Plan template's suppression fields, `SCRIPT_EXECUTION_REFERENCE.md`'s standard templates and worked examples and example logs, `WORKFLOW_PHASE4_ANALYSIS.md`'s status contract (log line `PASSED WITH WARNINGS` maps to reported status `WARNING`), and the research-executor, code-reviewer (cr1 templates: the coded-value scan runs over the Plan's declared numeric columns with a `NUMERIC_DTYPES` fallback, one outcome line per column, a `[BLOCKER]` for a declared column absent from the output, and a `QA{n} RESULT:` verdict line), data-verifier, data-ingest, plan-checker, notebook-assembler, and user-reference surfaces are aligned. Regression: `tests/python/test_checkpoint_templates.py` extracts every template block from the two live reference files (asserting block counts), compiles/parses all of them, and runs 37 Python and 11 R fixtures (64 tests) including the four original reproductions; the `tests/python` CI job's discover pattern is widened from `test_deploy_smoke.py` to `test_*.py` so the suite runs in CI (the Python fixture cases skip cleanly when `polars` is absent on the runner and the R parse gate and R fixtures skip without `Rscript`; the block-extraction and Python `compile()` gates always run). `CLAUDE.md`'s reference-file row for `QA_CHECKPOINTS.md` now names QAP1-QAP4 alongside QA1-QA4b.

#### Script Template Placeholders and Deploy-Smoke T2.2

The fourteen script templates in `SCRIPT_EXECUTION_REFERENCE.md` ended with a literal `# EXECUTION LOG` placeholder stub that the wrapper's re-run guard refuses; the stub is now a prose note. The deploy-smoke T2.2 coding probe now anchors on the wrapper's three-line banner frame (`# ` plus forty or more `=` around `# EXECUTION LOG`), requires exactly one such frame, and after it a `# Exit code: 0` record, a `# Capture: COMPLETE` record, the `# Command:` / `# --- STDOUT ---` / `# --- STDERR ---` skeleton, and the run's nonce inside the captured-STDOUT region -- so neither an evidence-incomplete run nor a casually source-forged marker passes (`tests/python/test_deploy_smoke.py` grows to 83 cases). A source that reproduces the wrapper's whole log skeleton is still accepted; only out-of-band capture can close that.

#### Synthetic-Path Checkpoints: Truthful Outcomes on the Privacy-Preserving Path

Carries the S03 contract onto the Data Onboarding synthetic path, which had been left with a two-state model and a divergent `ISSUES` status. The three review checkpoints are now first-class in `QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints, in the QAP shape: per-check stable keys with explicit not-applicable versus not-verifiable states for QAS-A (a1-a11, adding a11: the T4 shareable synthesis log carries no per-variable utility or comparison output), QAS-B (b1-b12), and QAS-C (c1-c11); a `Checks: … , N info` count line; and `QAS-A RESULT: PASSED | BLOCKER`, `QAS-B RESULT: PASSED | WARNING | BLOCKER`, `QAS-C RESULT: …`. § QAS Severity Overrides states the escalations as strictly stronger than the general rules: QAS-A has no `not_applicable` mapping and any `[NOT VERIFIED]` item is a BLOCKER; the disclosure-critical b/c keys are non-declarable and NOT VERIFIED on them is a BLOCKER; evidence on a passing disclosure check is aggregate-only. Two shipped script-halting blocks, CPS-INTAKE (DS-3, twelve checks on the returned profile report: schema, percentile monotonicity, category totals, missingness, correlation well-formedness, a disclosure sweep with aggregate-only evidence and an explicit scan-completeness count, embedded-validation honesty, a raw-value-shaped-field heuristic, identifier value-freedom, cross-tab suppression) and CPS-GEN (DS-5, ten checks on the generated frame separating fidelity deviations from fabrication), are added to `VALIDATION_CHECKPOINTS.md` in Python and R with the five-field accumulator, count line, `CPS-INTAKE VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED` verdict, and raise/stop on FAILED; four checks in each are non-declarable, and declaring one is itself a `[FAIL]` while the check still runs. Both blocks were executed against derived fixtures in both languages before landing (the control-fixture run caught and fixed an unstable `value_counts()` ordering that mis-paired labels and counts). The shipped outbound templates are repaired in place: `profile_data_template.{py,R}` print one counted `[PASS]/[FAIL]/[SKIPPED]/[NOT VERIFIED]` line per embedded check, a `Checks:` line, and a `PROFILE VALIDATION:` verdict; the disclosure sweep `no_subthreshold_cells_emitted` is non-declarable and verifies its own scan completeness (blocks reached versus blocks declared), closing the paths where an empty sweep (`all([])`, `all(logical(0))`) read as clean; the R validate block indexes with `[[ ]]` throughout so a `cells_suppressed`-only entry cannot partial-match into the visible-cell sweep, and every reason is length-guarded so a NULL reason is NOT VERIFIED rather than an opaque R error; the JSON wire enum gains `NOT_VERIFIED`, with no other schema change. `synthesize_local_template.{py,R}` gain the optimized-mode refusal (Python), the exclusive-creation preflight (R), a `SYNTHESIS VALIDATION:` verdict, and no longer write synthpop `compare()` output into the shareable log (it renders real-data marginals; at most one aggregate `S_pMSE` is written; the finding itself is recorded as not verified because synthpop is not installed in the container). `scripts/check_profile_templates.py` gains the four-state expectation model and four negative fixtures (122 to 130 assertions). `tests/python/test_checkpoint_templates.py` extracts the CPS-INTAKE and CPS-GEN fences by heading and marker (validation-block inventory 13 to 15 Python, 10 to 12 R), syntax-gates them, and exercises them with 12 new behavioural fixtures (8 Python, 4 R) built from a derived profile report and synthetic parquet, including the non-declarable-key rule, scan completeness, the tier-2 `[SKIPPED]` correlation path, and an aggregate-only-evidence assertion that the disclosure `[PASS]` line carries no cell count; the module grows from 62 to 78 tests and `tests/python` discovery ran 186 at that point. The skill's `validation-checks.md` becomes a pointer plus skill-local material instead of a second drifting copy of the tables; `WORKFLOW_PHASE_DO_SYNTHETIC.md` restates the three output formats and the DS gates on counts and points DS-3/DS-5 at the shipped blocks with config stanzas; `STATE_TEMPLATE_ONBOARDING.md` tracks five rows (QAS-A, CPS-INTAKE, QAS-B, CPS-GEN, QAS-C) with enums and counts, `ISSUES` retired; onboarding gates, session recovery, BOUNDARIES, code-reviewer, and the agent index are aligned; and `ERROR_RECOVERY.md` gains synthetic-path routing — QAS BLOCKER types (any QAS-A `[NOT VERIFIED]` always blocks) and DS-3/DS-5 rows that separate a CPS block's missing-evidence failure, and a mistyped or non-declarable `not_applicable` key, from a data failure. A three-angle review of the new blocks then found six defects, each fixed and proven in both languages before landing: a correlation matrix whose dimension disagreed with its declared columns raised an uncaught index error instead of reaching a verdict (CPS-GEN); an unrecognized percentile key such as `median` crashed the Python block and produced a misattributed not-verified line in R (CPS-GEN); a cross-tab entry marked `collapsed` skipped the lone-hidden-cell scan even while it still released visible cells; the identifier check was a deny-list that let a raw example value through, and is now an allow-list of structural keys (the raw-value sweep also flags string-valued `example`/`sample`/`min_value`-style keys anywhere in the report); an unrecognized `not_applicable` key was silently ignored and is now a `[FAIL]`; and a declaration with an empty reason silently fell back to running the check instead of reading `[NOT VERIFIED]`. The proof runs also caught an R-only defect in the raw-value tree walk, where a JSON `null` pushed nothing onto the node stack while the path stack still grew, so later FAIL lines named the wrong location. The suite now carries a regression fixture for each of these in both languages, plus a whole-stdout leak scan over every CPS fixture with planted disclosure tokens and a negative control; each new guard was shown to fail when its fix is reverted (14 of 14 mutations caught). The module grows to 113 tests and `tests/python` discovery runs 260.

#### Data-Source Skill Recipe Contradictions (S04)

The `election-data-source-countypres` Common Pitfalls row and the `variable-definitions.md` vote-share recipe instructed a bare `mode == 'TOTAL'` filter, contradicting the skill's own governing `mode-reconstruction.md`; both now route to 3-pattern reconstruction, and the California fetch example is annotated so it is not generalized across states. The `education-data-source-saipe` filtering examples thresholded `est_population_5_17_poverty_pct` at `>= 20` on a column that is a 0-1 proportion (a filter that silently returns zero rows); both examples now use `>= 0.20`, the variable table names the scale, and a `_pct` scale-trap pitfall row is added. A captured probe of the pinned mirror vintage (382,099 rows) confirmed the proportion scale and resolved a separate contradiction over SAIPE missing codes in favour of the source skill: the file carries nulls, not `-1`/`-2`/`-3` sentinels; the explorer skill's generated variable dictionary is caveated accordingly, and the dictionary generator's current revision (`scripts/mirror_maintenance/54_generate-variable-dictionaries_a.py`; the original keeps its execution log) emits that caveat for every source so it survives regeneration. The explorer skill's general `-1/-2/-3/-99` sentinel legend now says it is the Portal's declared convention rather than a guarantee about any mirror file, and tells readers to test for both nulls and sentinels. New regression suite `tests/python/test_data_recipe_fixtures.py` (25 tests) executes the live reconstruction block from `mode-reconstruction.md` against a four-county fixture and guards both skills against textual drift.

#### Execution Wrapper: Evidence Persistence Verification

The file-first execution wrapper tracks three outcomes separately — the script's exit code (computation), the `tee` status into a capture buffer (capture), and the appended execution log verified on disk (persistence: exactly one `# EXECUTION LOG` marker, closing banner last, exit-code line present). `SUCCESS` / `Execution log appended` print only when all three hold; otherwise the wrapper exits **74** with a banner naming the failed outcome and the retained buffer path. The buffer now lives next to the script (`.<script>.capture.XXXXXX`, inside the backup boundary, never `/tmp`) and is deleted only after a verified run. Interruptions (SIGINT/SIGTERM) append no log, retain the buffer, and exit 130/143 (the banner says if an unverified log was already appended). Concurrent duplicate runs are detected post-append by marker count (no locking). The appended log gains a `# Capture: COMPLETE|INCOMPLETE (...)` header line; a captured output line reading exactly `EXECUTION LOG` is archived as `#  EXECUTION LOG` so script output cannot forge a marker; a missing argument now prints usage. Contract updates: `SCRIPT_EXECUTION_REFERENCE.md` (new § Evidence Persistence Verification), `ERROR_RECOVERY.md` (new § Execution Wrapper Evidence Outcomes), `BOUNDARIES.md`, `CLAUDE.md`, `VALIDATION_CHECKPOINTS.md`, the research-executor and data-ingest agent files, and the Reproducibility Verification mode ASSESS step. Regression: `tests/bash/run_with_capture.bats` grows from 12 to 27 cases, including fault injection for tee/append/duplicate-marker/unwritable-directory/interruption. Repairs the S02 finding from the 2026-09-05 review synthesis.

#### Codex CLI Pinned to 0.153.2

The bundled Codex CLI moves from 0.144.1 to **0.153.2** (0.153.1 is the minimum version that lists `gpt-6-astra` in its model catalog). Primary-source verification of the 0.145–0.153 release range found no changes to the `codex login --device-auth` flow, `auth.json` schema/location, or token-refresh behavior that the ChatGPT-subscription lane depends on.

#### GPT-6 Astra Shim Support

The provider shim accepts `gpt-6-astra` on both auth lanes (OpenAI API key and ChatGPT subscription). One behavioral caveat: Astra does not support reasoning-effort `none` — the shim clamps a requested `none` to `low` for Astra. The `max` effort level is supported (as it is for the gpt-5.6 family).

#### Sol-Parity Threshold Registration

`gpt-6-astra` / `gpt-6-astra[1m]` (bare or provider-prefixed) join DAAF's validated extended-horizon context-threshold profile at GPT-5.6 Sol parity (ELEVATED 60%/300k, HIGH 75%/400k, CRITICAL 90%/500k). Astra's physical window is **1,050,000 tokens** (128,000-token max output) on the API and OpenRouter routes. The ChatGPT-subscription (Codex) lane's backend cap was **measured directly on 2026-09-05 at 919,000 tokens** for both `gpt-6-astra` (accepted 919,053 real input tokens, rejected 922,552) and `gpt-5.6-sol` (accepted 910,827, rejected 921,973) — consistent with Astra's documented 922,000-token maximum input (1,050,000 window minus 128,000 max output). This lane-wide 919,000 figure **replaces the stale ~370,000 cap** measured for Sol alone on 2026-07-16, and is now reflected across the canonical context-threshold reference, the environment-settings example, the installation guide, the technical FAQ, the deploy-smoke T0.4 check, and the DAAFBench registry. Near-miss slugs such as `gpt-6-astra-pro` — a real OpenRouter slug — remain on conservative thresholds (superseded by the 2026-09-29 policy decision on flagship `-pro` slugs; see "Context Monitoring: Dotted Claude IDs and the GPT-6 Registry Extension" below). Sol's own tier history is unchanged.

#### DAAFBench and Deploy-Smoke Coverage

`benchmarks/config/models.yaml` gains GPT-6 Astra entries on both routes: `openai/gpt-6-astra` (OpenRouter, $10 prompt / $50 completion per 1M) and `gpt-6-astra` on the ChatGPT-subscription lane (919,000-token lane ceiling, OpenAI API-equivalent pricing $10/$1 cached/$12.50 cache-write/$50 output per 1M short-context, doubled tier above 272k input). The existing GPT-5.6 chatgpt-lane entries were corrected from the stale 370,000 ceiling to the measured 919,000. `scripts/deploy_smoke/profiles.yaml` gains an `openrouter-astra` profile mirroring the existing OpenRouter GPT profile.

#### Documentation and Configuration

The environment-settings example, installation guide, technical FAQ, canonical context-threshold reference, orchestrator mode references, and boundary/hook-coverage docs were updated for Astra parity. A stale GPT-5.6 Sol threshold line in the environment-settings example (previously stated as `40%/60%/75%`) was corrected to the canonical `60%/75%/90%` percentages during the pass.

#### Context Monitoring: Dotted Claude IDs and the GPT-6 Registry Extension

**Dotted Claude IDs (bug fix).** OpenRouter reports Claude models as `anthropic/claude-opus-5.5`, `anthropic/claude-opus-4.8`, or `claude-opus-5.5[1m]`, while every Claude pattern in `context-reporter.sh` and `subagent-bar.sh` expects the hyphenated form. Reproduced on 2026-09-29 against the live scripts, a dotted Opus 5.5 subagent at 250k read `[CRITICAL]` instead of NOMINAL: it missed the anchored extended-horizon profile arm, and its window was right only because the loose `*opus-5*` window glob happens to match `opus-5.5`. A dotted Opus 4.8 subagent at 150k read `[CRITICAL] 150k / 200k (75%)` instead of `[ELEVATED] 150k / 1000k (15%)`. Both scripts now carry a byte-identical `normalize_model_id` function (the hook once the user-applied patch `research/2026-09-29_FrameworkDev_OpenRouterDottedModelNames/context-reporter_dotted.patch` is in). It rewrites only an ID that ends in `claude-<family>-<major>.<minor>`, optionally followed by `[1m]`, to the hyphenated form, and keeps any provider prefix. Every other ID passes through unchanged, so near misses such as `anthropic/claude-opus-5.5-mini` stay conservative. The function is applied at classification points only: the same/different-model comparison, with both sides normalized because the session model cache can hold either the requested or the response spelling; the window lookup; the ChatGPT-lane flagship predicate; and the profile. The model caches and the agent-panel row label keep the raw name. `context-bar.sh` needs no change for this: it has no Claude window arm, and on OpenRouter it reads the window from the catalogue, where the dotted IDs are native.

**GPT registry extension (user policy decision of 2026-09-29, not validation).** Any flagship `-pro` slug is read exactly as its non-pro base, with `-pro` placed before the optional `[1m]`. That means the same window, the same 919k ChatGPT-lane cap eligibility, and the same profile. `gpt-6-sol` is treated like `gpt-5.6-sol`: 1,050,000 window, 919k lane cap, GPT extended-horizon profile. `gpt-6-luna` is treated like `gpt-5.6-luna`: 1,050,000 window, conservative profile. There is no `gpt-6-terra`, and bare `gpt-6`, GPT-6 mini/chat, and mini/chat `-pro` spellings stay unregistered. The flagship window grammar in all three statusline and hook scripts becomes `^(gpt-5\.(4|5|6)(-(sol|terra|luna))?|gpt-6-(astra|sol|luna))(-pro)?(\[1m\])?$`. The Sol/Astra case arm becomes an anchored ERE on the provider-stripped slug, `^(gpt-5\.6-sol|gpt-6-(astra|sol))(-pro)?(\[1m\])?$`, and the Fable/Mythos/Opus 5.5 arm still comes first. The windows follow the live OpenRouter catalogue fetched on 2026-09-29, which lists `context_length` 1050000 for every new member and has no `gpt-6-terra` entry. The 919k cap for the new members is inherited by policy, not measured. One caveat, retested on 2026-09-29 (`research/2026-09-29_FrameworkDev_OpenRouterDottedModelNames/preliminary_notes/2026-09-29_openrouter-pro-retest.md`). DAAFBench's 2026-07-10 hard prompt-length wall at ~200k reported tokens on the Anthropic-compatible endpoint is gone. `gpt-6-sol-pro`, `gpt-5.6-sol-pro`, and `gpt-6-luna-pro` each accepted more than 930k reported tokens. `gpt-6-astra-pro`'s ceiling was not tested and is extrapolated. The inflated token accounting persists on both OpenRouter endpoints: 4.11x the base's input tokens for `gpt-5.6-sol-pro` and about 3.12x for the GPT-6 `-pro` slugs. No wall was observed up to about 943k reported tokens (`gpt-6-astra-pro` untested), consistent with the catalogue's 1,050,000 `context_length`, so the 1.05M window is kept in DAAF's reported-token unit; that 1,050,000 is the actual ceiling remains inference. The absolute gates fire at roughly a third to a quarter of the real content depth. That is conservative. Billing is roughly 3x the base for the GPT-6 `-pro` slugs, whose per-token prices equal their bases', and about 8x for `gpt-5.6-sol-pro`, whose per-token price is 2x its base. These multiples are derived from the token ratios and list prices, not verified against invoices. The user kept the `-pro` window as built. The profile table in CLAUDE.md and `CONTEXT_THRESHOLDS_REFERENCE.md` is renamed "GPT Sol/Astra extended-horizon" and says which members are validated and which were admitted by policy. `BOUNDARIES.md`, the two orchestrator mode references, the installation guide, the technical FAQ's window list, the deploy-smoke interpretation guide, and the DAAFBench README and registry comments are updated to match.

**Tests and deployment.** `subagent_bar.bats` grows from 94 to 115 cases, `context_bar.bats` from 91 to 96, and `context_reporter.bats` from 96 to 115. The new cases include lockstep checks on the normalize function, both EREs, and the GPT flagship-family pre-filter glob; cross-script window-agreement checks; and near-miss locks. A review fix also routes malformed GPT flagship-family IDs such as `gpt-6-sol[1m]-pro` to 200,000 in `subagent-bar.sh` (previously 1,000,000 via its generic Claude `[1m]` arm), matching the hook and `context-bar.sh`. Five existing near-miss rows that used `gpt-6-astra-pro` or `gpt-5.6-sol-pro` now use `…-pro-x` (two each in the reporter and subagent-bar suites, one in `context_bar.bats`), and `context_bar.bats`' Astra near-miss row drops `gpt-6-luna`, which now maps to 1.05M on purpose. `.claude/hooks/` is user-only, so the hook's half ships as `research/2026-09-29_FrameworkDev_OpenRouterDottedModelNames/context-reporter_dotted.patch`. Until the user applies it, 16 new `context_reporter.bats` cases fail by design against the live hook, and all 115 pass against the tested draft. The user applied the patch on 2026-09-29, and all 326 cases across the three suites then passed against the live scripts.

**Follow-ups (deploy-smoke, DAAFBench counts, OpenRouter prices).** The deploy-smoke classifier in `scripts/deploy_smoke/route_detection.py` is Python and separate from the Bash scripts. It now matches the GPT-6 flagships with `_GPT_FLAGSHIP_RE`, a pattern byte-identical to the Bash flagship grammar, and a new lockstep test in `tests/python/test_deploy_smoke.py` compares the two. As a result, Tier-0 check T0.4 now enforces the 919,000-token ChatGPT-lane cap for `gpt-6-sol`, `gpt-6-luna`, and the flagship `-pro` forms, just as it already did for `gpt-5.6-sol` and `gpt-6-astra`. Previously `gpt-6-astra-pro` was deliberately unmapped. Unlike the Bash scripts, the classifier drops everything from the first `#` before matching, as the provider shim does, so an effort-suffixed selector such as `gpt-6-astra[1m]#xhigh` keeps the cap. The T0.4 messages now say the cap was measured for Sol and Astra and applied to the other flagships by policy. `tests/python/test_deploy_smoke.py` grows to 147 cases; in `tests/bash/deploy_smoke.bats`, the classifier table grows from 24 to 40 rows and the T0.4 table from 12 to 22. Separately, `benchmarks/tests/test_chatgpt_route.py` and `benchmarks/README.md` now count the 2026-09-23 `opus-55` registry entry (44 entries, 10 Anthropic), which clears two failures that predated this session. The installation guide's OpenRouter GPT table is re-priced from the 2026-09-29 catalogue:
- GPT-5.6 Sol: $2 / $10, was $5 / $30.
- GPT-5.6 Terra: $2 / $12, was $1 / $6.
- GPT-5.6 Luna: $0.20 / $1.20, was $0.10 / $0.60.

Long-context rates are added, and the table notes that `gpt-5.5-pro` / `gpt-5.4-pro` list at 6x and 12x their bases' per-token price. The 2026-08-11 OpenRouter 50% Terra/Luna discount is no longer listed in the catalogue. A later pass re-priced DAAFBench to match, keeping its two price sources separate:
- In `benchmarks/config/models.yaml`, the OpenRouter entries follow the 2026-09-29 catalogue. The ChatGPT-subscription API-equivalent schedules follow OpenAI's direct price list, where only Sol changed, to its promotional $4 / $20. The file records the prior schedule so it can be reverted when the promotion ends.
- `benchmarks/README.md` and the viewer's caveat text are updated to match.
- `compute_accounting()` in `benchmarks/harness/cost_estimator.py` now prices each ChatGPT-lane model at its own `api_equivalent_pricing`. Before this fix it used the Luna constants for every model. A model with no usable schedule now reports the new `unavailable_api_equivalent_pricing` status instead of borrowing Luna's rates. `benchmarks/tests/test_subscription_accounting.py` gains 10 regression tests, or 15 checks counting subtests. 14 of those checks fail against the pre-fix module. The remaining one, a check that Luna's pricing is unchanged, passes on both by design. A review-fix pass adds rejection cases for a bool, NaN or infinite rate and for a bool or float threshold, plus a test at exactly the threshold and one token above it. Together these catch all five deliberately broken versions of the code that the original tests missed.
- The viewer's battery cost and cost charts are recomputed from `models.yaml` at build time and were never affected. The per-run evidence panel shows archived scenario figures as recorded, so archived Sol and Terra runs keep their Luna-priced scenarios; no archived exact cost was affected, since all such values are null. `benchmarks/CHANGELOG.md` records the change.

**GPT recommendations (user decision of 2026-09-29).** GPT-5.6 Terra is no longer recommended. The recommended two-tier pairing is Sol for the strong tier and Luna for the fast tier, with Luna no longer described as unused. Examples use `gpt-6-sol` and `gpt-6-luna`, and Astra is the premium strong-tier alternative. The installation guide, technical FAQ, `scripts/host/environment_settings_example.txt`, and the orchestrator's alternative-provider example are updated. Examples for the direct-API and ChatGPT-subscription shim lanes note that no GPT-6 Sol or Luna request has been sent through the shim yet, with `gpt-5.6-sol` / `gpt-5.6-luna` as the fallback. The shim forwards any model name, so it does not block these slugs.

**Statusline effort suffix.** `context-bar.sh` now drops everything from the first `#` in the statusline's `.model.id` before it caches or classifies the model. The fix is defensive: it is unverified whether Claude Code's `.model.id` carries the effort suffix. If it does, a shim session configured as `gpt-6-astra[1m]#xhigh` now gets the flagship window and the 919,000-token ChatGPT-lane cap. The session-model cache that the hook reads would also hold the bare id; with the suffix, the hook fell back to the conservative profile whenever the transcript had not changed since its last run. That fallback was reproduced with scratch probes: 350k tokens read CRITICAL before the fix and ELEVATED at 350k / 919k after. `tests/bash/context_bar.bats` grows from 96 to 102 cases, and 5 of the 6 new cases fail against the pre-fix script (the sixth checks near misses and passes on both). `tests/bash/context_reporter.bats` grows from 115 to 117 with two chain cases: hook, then statusline with a `#` id, then hook again with the transcript unchanged. Both fail against the pre-fix statusline.

#### Backup Staging: Special Files and the Windows Copy Exit Code

**Special files (both twins).** Upstream source (`moby/go-archive` and `docker/cli`, fetched to `research/2026-09-29_FrameworkDev_BackupFifo/web/`) shows the failure chain. On Windows, the archive extractor creates nothing for a FIFO or device entry, then fails its `chtimes` timestamp call on the missing path, and `Unpack` returns on that first error, so every later entry is dropped. The CLI prints "Successfully copied" before returning the error. The field report (a sibling project on a variant script) shows the last progress reading at 94% when the error appeared; its final file count was never observed. Separately, a probe of the maintainer volume projected the loss: 714 of 71,820 regular files sort after the first stale FIFO in walk order, under the 718-file (1%) tolerance. The staging program in `backup_daaf.sh` / `backup_daaf.ps1` (still byte-identical, still quote-free) gains a final `find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +` after the symlink strip. No manifest is written and restore is unchanged: these objects carry no data. The volume scan appends a fifth line, the special-file count, after the four existing values, so the parsing contract is unchanged. Both twins read a missing or non-numeric fifth line as 0; the PowerShell twin bounds-checks the index because `Set-StrictMode 3.0` throws on an out-of-range read. A nonzero count prints `Note: skipping N named pipe/socket/device file(s) -- runtime-only, not backed up.` as information only: stale FIFOs are expected, so the banner stays plain.

**Copy exit code (`backup_daaf.ps1`).** The `Start-Process -PassThru` copy process now has its `Handle` cached right after launch. Without that, `ExitCode` can read as `$null` once the process has exited, a widely reported .NET/PowerShell behavior that is inferred here, not reproduced, since it needs a Windows host. The old `else { 0 }` then turned that into a clean exit and disarmed the corroborated short-copy check. An unreadable code is now UNKNOWN. The fatal and Note branches require a known code; an unknown code always latches the WITH WARNINGS banner, adds a loud zero-tolerance WARNING on any shortfall, and is an ERROR when the scan expected files but none arrived. It is not fatal, because a missing signal is not a second failure signal. The `.sh` twin's `wait` capture was probed and returns the child's real status (a 7 read back as 7), so it is unchanged.

**Tests.** `tests/bash/backup_daaf.bats` grows from 47 to 54 cases. The new cases include a behavioral run of the real extracted staging program under the local `sh` against a tree with a FIFO, a UNIX socket, and a symlink (mutation-checked: a strip narrowed to `-type p` leaves the socket in place and fails the test), and scan/note cases for 5-line, zero, legacy 4-line, and non-numeric scans (mutation-checked: removing the count sanitisation fails the test). `tests/powershell/backup_daaf.Tests.ps1` grows from 68 to 82. The new cases include structural checks of the exit-code read (the regression guard), two labelled idiom-documentation tests that run a copy of the read idiom, and a non-Windows end-to-end block that runs the real script against a fake `docker` on `PATH`. `backup_twin_parity.bats` passes with only a header-comment update.

#### Host PowerShell: Argument Quoting and Child Exit Status

A read-only sweep of all 16 host `.ps1` files (`research/2026-09-29_FrameworkDev_BackupFifo/2026-09-29_Host_PS_Sweep_Findings.md`) found two defect classes.

**Argument splitting (HIGH).** `Start-Process -ArgumentList @(...)` joins the array with single spaces and quotes nothing; the Start-Process reference says so directly, and PowerShell#5576 lists Windows PowerShell 5.1 as affected. `daaf.ps1`'s two delegates passed the child path (under the install folder) unquoted, and `backup_daaf.ps1` passed the host backup path the same way, so both broke for any install path containing a space. `test_migration.ps1`'s two harness launchers had the same bug for `$Path`. The ad-hoc quoting loops beside them also missed trailing backslashes, backslashes before a quote, and quote-bearing tokens without whitespace. The sweep reproduced the split and the argument merge on pwsh 7.6 under Linux, which applies the same Windows argv rules. A new `ConvertTo-DaafNativeArg` helper in `daaf_lib.ps1` quotes one argument as the inverse of the Windows argv parser, and every call site now passes ONE pre-joined string built from it. `backup_daaf.ps1` and `test_migration.ps1` are standalone, so they carry byte-identical inline copies. A false comment claiming the array form was "quoted robustly" is corrected, and so is a comment that described the staging program as an `-ArgumentList` element (it is passed by direct call).

**Unreadable child exit status (MEDIUM).** Both `daaf.ps1` delegates read `$proc.ExitCode` without first caching `$proc.Handle`. On Windows, with `-NoNewWindow` and/or `-RedirectStandard*`, that value can read `$null` in Windows PowerShell 5.1 and PowerShell 6.0 through 7.4.0; PowerShell 7.4.1 fixed it (PowerShell#5421, #20400, and the 7.4.1 release notes; SO 10262231, answer 23797762). The `$ec -and $ec -ne 0` / `-not $ec -or $ec -eq 0` tests then reported the child as clean. Each delegate now caches the handle immediately, reads the exit code defensively, and prints a distinct "Could not read the exit status of <script>" message for `$null`, matching `backup_daaf.ps1`'s `$CopyExitKnown` handling. The null-as-success behavior itself is inferred from those sources and the in-repo `test_migration.ps1` field failure; it does not reproduce on Linux.

**Backup banner (both twins).** A known nonzero `docker cp` exit with a full file count still exits 0 but now latches the WITH WARNINGS banner.

**Skill references.** `shell-scripting`'s `gotchas.md` gains entries for the `-ArgumentList` join, the `-PassThru` null `ExitCode`, and the Windows `docker cp` abort at the first FIFO, device node, or uncreatable symlink. Its `$LASTEXITCODE` entry no longer shows `$LASTEXITCODE -and $LASTEXITCODE -ne 0` as a GOOD pattern, because that form reads an unknown status as success. `powershell-standards.md` gains a child-process launch section and two checklist items, and `SKILL.md`'s indexes point at all of them.

**Tests.** A new `tests/powershell/native_arg_quoting.Tests.ps1` (56 cases) covers the helper's quoting rules, an exact argv round trip through real PowerShell and `sh` children whose script sits in a directory with a space, byte parity of both inline copies with a self-test, and AST guards over `scripts/host/*.ps1`, which comments cannot satisfy. The guards match `Start-Process` and its `saps` / `start` aliases, resolve parameter prefixes and aliases (`-Arg`, `-Args`), and fail on splatting, a positional `-ArgumentList`, or an unparseable file. They reject any array-form or unquoted `-ArgumentList`, pin the inventory (five `-ArgumentList` sites plus two FilePath-only opens), require that every `Start-Process -PassThru` result is first used for a `.Handle` read, and reject truthiness coercion of `daaf.ps1`'s `$ec`. Each guard has self-test snippets proving it rejects the known-bad shapes. The file also checks that `test_migration.ps1`'s launchers drop a `$null` script-argument list. `daaf.Tests.ps1` grows from 59 to 69, with argument-capture, `$null`-argument, and null/1/0 exit-status cases for both delegates. `backup_daaf.Tests.ps1` grows from 82 to 85: an end-to-end run from a working directory with a space against a fake `docker` that rejects a split `cp`, the banner latch, and structural checks. The `backup_daaf.bats` Note case now isolates the latch and asserts the banner. Reverting each fix on a scratch copy fails its new tests (5 of 5 mutations caught). A follow-up review pass added eight more scratch mutations (a positional array, a splatted call, and a `saps` alias call; the old `$` helper anchor; the removed `$null` filters in `daaf.ps1` and in `test_migration.ps1`; a commented-out `.Handle` cache; `if (!$ec)`). All eight were caught.

#### Backup and Restore: Exact, Error-Aware Completeness Checks

**Field report (2026-09-29, Windows 11, Windows PowerShell 5.1, `LongPathsEnabled = 0`).** A backup scanned 73,031 files, then counted 72,834 in the host copy, and the 1% tolerance (730) passed it as "Backup complete!". A container-side count of the same folder found 73,021. So 187 files had been copied correctly by `docker cp` but were invisible to `Get-ChildItem -Recurse -ErrorAction SilentlyContinue`, which skipped folders past the path-length limit without a word. A volume-vs-backup diff indicates, by inference, that the other 10 were live-volume changes between the scan and the snapshot, not copy loss.

**Exact verification (both twins).** The staging step prints the frozen snapshot's own counts (`STAGED_FILES`/`STAGED_KB`), and the finished backup is compared with them at zero tolerance, using the same root-relative exclusions on both sides. The 1% tolerance survives only as a stated fallback when those numbers can't be read. A shortfall is reported as files missing from the backup. Extra files, such as an OS-added `desktop.ini` or `.DS_Store`, are reported as not a loss. A `Snapshot:` line shows any drift between the scan and the snapshot.

**Counting on Windows.** `backup_daaf.ps1` counts the finished backup folder, and `restore_from_backup.ps1` counts the backup selected for restore, inside Docker through a read-only bind mount, with a byte-identical program. It prints a sentinel only when it can see the root `.daaf-symlinks` (Docker Desktop can present an empty bind-mount view for some drives), and it withholds its count when `find` hits a read error. Otherwise PowerShell counts, with `-ErrorVariable` captured, and any error makes its count a stated lower bound. Restore's list of available backups stays on PowerShell for speed (one container run per listed backup would be slow), so it can show a `+` there even when the Docker count of the selected backup is exact.

**Read errors in the backup-folder and restore counts never pass as exact numbers.** Each of these counts reports a read error as a lower bound (`N+`) or as unavailable, and the snapshot count falls back to the live-volume scan. The backup's data-volume count latches the WITH WARNINGS banner on a lower bound, and so does the Windows restore's count of the selected backup (see the restore banner below); on macOS/Linux the backup's separate size total does too when only it hit an error. The Claude-state counts in both backups are display-only. Two kinds of count are outside this rule: the live-volume source scans capture no read errors (whenever the snapshot markers can be read, the snapshot, not the scan, is what the backup is checked against), and the progress readings during the copy are display-only. A short lower-bound count after a copy error is a WARNING, not the fatal short-copy error. A lower bound of 0 exits 1 as "could not be verified", so an update or migration that triggered the backup stops. The macOS/Linux restore refuses a backup it cannot fully read, before it copies anything, because the copy would most likely fail partway on the same files and only the refusal can name them (see "Restore: Copy-Then-Swap" below, under which a failed copy no longer touches the live volume). When the post-restore count cannot run cleanly, restore warns and exits 0 instead of reporting "0 files", since the data was already copied.

**Restore banner (both twins).** Restore now latches a WITH WARNINGS banner the way the backup twins do (`HAD_WARNINGS` / `$HadWarnings`). Every warning on a run that still completes latches it: a failed permission replay, a failed symlink replay, a post-restore count that could not be read, and a failed Claude-state symlink replay. (Copy-then-swap, below, adds a free-space check that could not run and a temporary copy that could not be removed, makes a failed Claude-state copy stop the restore before anything changes, and turns a post-restore file-count difference, which this pass first latched as a warning, into an error.) The Windows twin also latches when the selected backup's count is a lower bound. The post-restore check can then show that the restore is consistent with the backup, but not that it is complete. The macOS/Linux twin refuses such a backup instead. A latched run ends `Restore completed WITH WARNINGS -- verify before relying on it` instead of `Restore complete!`, and its exit code is unchanged: still 0, so the Control Panel callers (`daaf.sh` `run_delegate`, `daaf.ps1` `Invoke-DaafDelegate`), which read only the exit code, behave as before. The NOTEs for a backup that predates the permission manifest or the Claude volume do not latch. Neither do the Windows notes about falling back to a PowerShell count that then read every file, matching `backup_daaf.ps1`'s notes.

**Also in this pass.** Both backups print `Source volume: <name>` and warn when the backup folder lacks its `.daaf-symlinks` manifest. The Windows scan gives a notice when files will exceed 260 characters in the backup folder. The macOS/Linux twins use count predicates and counting semantics equivalent to the Windows twins': the same root-relative exclusions, and exactly one count per file, so a name holding a newline counts once. They get there by different means. The `.sh` host counts count NULs (`find -print0`, piped through `LC_ALL=C tr` so macOS's `tr` accepts any byte in a name), while the Windows side counts one `stat` line per file inside Docker, or one file object in its PowerShell fallback. Message wording differs by platform where intended, for example in the example file names and the hint about names a disk cannot store. `shell-scripting` gains a gotcha for the PowerShell 5.1 long-path skip, a `powershell-standards.md` checklist item, and `TMPDIR` guidance for in-container test runs. The installation guide and technical FAQ explain the new messages.

**Tests.** `tests/bash/backup_daaf.bats` grows from 54 to 78 cases, `backup_twin_parity.bats` from 13 to 30, and `restore_from_backup.bats` from 50 to 66. `tests/powershell/backup_daaf.Tests.ps1` grows from 85 to 136, and `restore_from_backup.Tests.ps1` from 52 to 72. The new cases cover the new branches. The twin-parity cases pin the shared container programs, the restore banner strings, the set of WARNING messages the restore twins can print, and their latch counts. Removing one restore latch in a scratch copy fails the banner tests: the Claude-symlink latch in the `.sh`, the lower-bound latch in the `.ps1`.

#### Backup Staging: Names Windows Cannot Create, and Case-Only Clashes

**Field report (2026-09-30, Windows, Docker Client 29.1.3 / Docker Desktop 4.55.0).** `docker cp` stopped at `...\scratch\review3_consistency\fx\sub\name<LF>nl: The filename, directory name, or volume label syntax is incorrect.` after 72,386 of 73,785 files. The zero-tolerance check failed the run (exit 1). Upstream source review (moby/go-archive, Microsoft's naming rules; not executed on a Windows host) found the same abort for control bytes 0x01-0x1F, `< > " | ? *`, and the device names, with `:`, `\`, and a trailing dot or space handled differently by the older and newer (Docker CLI 29.7+) extraction code, and case-only clashes on NTFS silently keeping one of two files, merging two folders, or aborting on a file and a folder.

**Staging step (byte-identical in both twins, switched per host).** Right after `cd /staging` and before the symlink manifest, the staging program runs a new step when `DAAF_STAGE_NAMES` is set (`docker run ... -v ... -e DAAF_STAGE_NAMES=...`). With `win`, which only `backup_daaf.ps1` passes, for both volumes, it removes every non-symlink entry whose own name Windows cannot create (a folder takes its subtree; `-prune` keeps its children off the list). It then removes all but the first path, in C-locale byte order, of each case-insensitive full-path clash that involves a file, and lists folder+folder clashes without removing them. With `casewarn`, which `backup_daaf.sh` passes on macOS, it only lists case clashes. On Linux the `.sh` passes an empty value and the step does not run. Symlinks are never removed by this step, so the fatal tab/newline symlink gate (exit 3, asserted by `ci-integration.yml`) is unchanged, and a symlink inside a removed folder never enters `.daaf-symlinks`. The step prints `STAGE_STRIP_NAME` / `STAGE_CASE_FILE` / `STAGE_CASE_DIR` lines, with every control byte shown as `?`, and `STAGED_STRIPPED_NAMES` / `STAGED_STRIPPED_FILES` markers before the final `STAGED_FILES`/`STAGED_KB`, so a hostile name cannot forge a marker. The program stays free of double quotes. The pinned tail and the shared count predicate are untouched. The case listing's two batched `find -exec printf ... {} +` actions are top-level `-o` branches, not a `\( \)` group: busybox `find` never runs the last batch of an `-exec ... {} +` inside parentheses (`flush_exec_plus()` walks only top-level actions; Alpine aports MR !75008), so the grouped form, which review round 7 caught before release, would have listed nothing under busybox while passing every GNU-based test.

**Host side.** `backup_daaf.ps1` gains `Write-DaafNameReport`, which prints `WARNING: N file or folder name(s) in the Docker volume cannot be created on Windows,` (or `Claude Code state volume`) with the list capped at 20 entries plus `... and N more`, the total number of files left out, and the rename advice. A separate `WARNING: N folder path(s) in the Docker volume are the same as another folder path` covers merged folder pairs. When the data-volume staging exited 0 but its log lacks the `STAGED_STRIPPED_NAMES=` marker that win mode always prints (`docker logs` failed, came back empty, or was cut short), `WARNING: Could not read the list of names in the Docker volume that Windows cannot create,` says names may have been left out unlisted (the Claude volume gets the same check when its staging exited 0). Its next step reads `bash scripts/check_workspace_invariants.sh --names-only` for the data volume and `DAAF_INVARIANT_ROOT=/home/appuser/.claude bash scripts/check_workspace_invariants.sh --names-only` for the Claude volume; `--names-only` runs only the checker's names check, because its symlink and repo-root checks would flag files that belong in Claude Code's folder and say to delete them. All three latch WITH WARNINGS, and on the success path the exit status stays 0. `backup_daaf.sh` prints `WARNING: N path(s) in the Docker volume are the same as another path except for upper/lower` case on macOS; when a macOS staging run exited 0 but its log lacks the final `STAGED_FILES=` or `STAGED_COUNT_ERRORS=` marker, `WARNING: Could not read the list of paths in the Docker volume that differ only in upper/lower` case says such pairs may be in the backup unnamed, and latches too (never on Linux). Its missing-files hint adds that on a Mac any such pairs are listed in a WARNING above, as the `.ps1`'s does. The `.ps1`'s missing-files hint no longer blames names Windows cannot create, which are now left out before the copy, and names the remaining case gap instead: letters outside A-Z. The copy-progress line in both twins now counts with the snapshot's root exclusions; it read one file too many at the end of the copy (`Progress: 73848 / 73847 files` in the field run of 2026-10-01) because it counted the root `.daaf-symlinks` manifest. Both twins print these lists right after the final count line and before the zero-file and corroborated short-copy fatal exits, once per volume; the Claude volume's list prints after its copy whether that copy succeeded or failed. In both twins the `Snapshot:` line adds back `STAGED_STRIPPED_FILES` before blaming a difference on live-volume change. The executable-permission manifest is still read from the live volume, so it can list a removed file. Restore skips paths that do not exist, so that is harmless. A name holding a newline in that manifest remains a pre-existing edge case. `shell-scripting`'s gotcha for the Windows `docker cp` abort now covers names and case clashes, and the technical FAQ and installation guide explain the new warnings.

**Tests.** `tests/bash/backup_daaf.bats` grows from 78 to 100 cases. The new cases run the real extracted staging program under the local `sh` (dash with GNU find, awk, tr and sort, not busybox) against fixtures with every name class, look-alikes that must stay (`com0`, `console`, `nulx`), case pairs of each kind, a symlink inside a removed folder, a tab-named symlink that must still hit the fatal gate, a name built to forge a marker, and the switch set to off and to `casewarn`. Adversarial fixtures add leading-dash, spaced, `%s`- and backslash-bearing clash pairs, a tab-named folder with children, a hostile-named folder hiding a case clash, and a newline name that embeds a `STAGE_CASE_FILE` line. Host-side cases cover the `.sh` switch values, the macOS warning and latch, the 20-entry cap, the snapshot arithmetic, the list printed exactly once before both fatal exits and after a failed Claude copy, the unreadable macOS list for each volume, and the progress line during a copy. `tests/powershell/backup_daaf.Tests.ps1` grows from 136 to 158, with unit tests of `Write-DaafNameReport` (including the unreadable-list case and its Claude-volume hint), structural pins of the switch on both launches, of both latches, of the report's placement and of the progress count, and end-to-end runs against a fake `docker` (the list before both fatal exits; a log without the name markers; a failed `docker logs`; the progress line during a copy). `backup_twin_parity.bats` grows from 30 to 32: a guard that fails on any batched `-exec ... {} +` inside `\( \)` in every `scripts/host` file that runs busybox (backup, restore, migrate and test_migration, both twins) and in the extracted staging programs, and a self-test that rebuilds the pre-fix case-listing line in a copy of `backup_daaf.sh` and must be flagged. Six scratch mutations were all caught in the first pass: the switch ignored in the program, the switch not passed by the `.ps1`, the removal dropped, the `.sh` latch removed, the `.ps1` latch removed, and the stripped files left out of the snapshot arithmetic. The 2026-10-01 follow-up pass was checked the same way: 5 of 5 `.sh` mutations (the old progress count, the data-volume expectation dropped, the new latch dropped, the Claude hint path dropped, the expectation forced on for a failed Claude staging) and 4 of 4 `.ps1` mutations (the old progress count, the Claude hint path dropped, the hint path ignored, the old missing-files hint) were caught. A one-shot probe on the user's Windows host then ran the staging program under real busybox and matched the expected output exactly (`CANARY_PARENS=0` confirmed the busybox bug the fix avoids).

#### Workspace Invariant 3: Names Windows Cannot Create

**Why.** The name that stopped the field backup was a leftover review fixture, and `scripts/check_workspace_invariants.sh`, the pre-checkpoint lint for objects git cannot see, did not look at names. It now enforces a third invariant alongside unauthorized symlinks and repo-root leak artifacts: no file or folder name Windows cannot create (control characters 0x01-0x1F, `< > : " | ? * \`, a trailing dot or space, or a reserved device name: `CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`, `COM¹`-`COM³`/`LPT¹`-`LPT³`, `CONIN$`, `CONOUT$`, in any case and with any extension), and no two names in one folder that differ only in (ASCII) case. The classes match the backup staging step's. There is no allowlist, because a hostile name anywhere in the volume breaks a Windows backup, and `.git` internals are skipped.

**How.** One `find -printf` walk with NUL-separated records feeds a single `awk` (`LC_ALL=C`) that classifies every name, tags each offender with its reasons, and pairs sibling case clashes; offenders come back NUL-delimited and are printed with control characters made visible by `cat -A`. The walk's summary record must arrive, or the check fails closed. A new `--names-only` flag (combinable with `-q`) runs only this third check, with its own `OK:` line and neutral advice in place of the "test fixture or scratch probe likely leaked them" guess; it is what the backup's unreadable-list hint runs, and with `DAAF_INVARIANT_ROOT` (now documented for users too, not only for tests) it checks the Claude Code state volume at `/home/appuser/.claude`, where the full check would list Codex's symlinks and other Claude Code files as objects to delete. `tests/bash/check_workspace_invariants.bats` grows from 12 to 31 cases. The `CLAUDE.md` self-cleaning-probe paragraph, `shell-scripting`'s `bash-standards.md` hygiene section and `testing.md`, the Framework Development mode reference, and the deploy smoke test's T0.10 description now cover hostile-named fixtures and case pairs.

#### Restore: Copy-Then-Swap

**Why.** Until this change, both restore twins cleared the live data volume (`Clearing Docker volume...`) and then `docker cp`'d the backup into it, and they cleared and refilled the Claude Code state volume the same way. Any failure after the clear left the live volume empty or partial. The helper container's create failing printed `The Docker volume has already been cleared and is now EMPTY.`, and a failed copy or ownership repair said the volume "may be in an inconsistent state". A failed Claude-state clear or copy only warned, after the data volume had already been replaced. Scoping (`research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/`) found three mechanics the redesign has to respect, and review round 1 a fourth:
- A container's `sh -c` running as PID 1 still catches SIGINT, so a forwarded Ctrl+C would stop a clear-then-copy program after the clear and before the copy.
- `docker volume create` silently reuses an existing volume of the same name.
- `docker volume ls --filter name=` is an unanchored regex.
- A `docker run -v NAME:/path` whose volume no longer exists creates a new, empty one ("If you start a container with a volume that doesn't yet exist, Docker creates the volume for you", Docker's volumes guide). A temporary volume that vanished while the restore waited at its prompt (removed by a second restore window, for example) would come back empty at the next mount, and an empty source compared equal to the empty tree the swap leaves behind.

**New flow (both twins, same order; user decisions D1-D5 of 2026-10-01).**
1. **Leftovers.** The script checks `<data volume>-restore-swap` and `<Claude volume>-restore-swap` with `docker container inspect`, and the two `-restore-tmp` volumes with `docker volume inspect`: exact names only, never a `--filter name=` match.
   - A swap container that is still running refuses the restore (exit 1). Its state is read from stdout only, and any line that is exactly `true` counts as running (review round 2, I-A: read through `2>&1 | tail -n 1` in the `.sh`, or merged and joined in the `.ps1`, a Docker warning on stderr could make a running swap look stopped, and the user was then offered `docker rm -f` of a live swap).
   - An inspect that fails with text other than "no such volume/container/object" is not read as "absent". It falls back to an exact whole-line match against Docker's own name list, stdout only (`docker volume ls -q` or `docker ps -a --format '{{.Names}}'`; for a container that is listed, `docker ps --format '{{.Names}}'` decides running or stopped), because Docker's error wording can change (review round 2, S3). Only when that list fails too does the restore refuse (`ERROR: Could not check for a temporary copy left by an earlier restore`, exit 1, nothing created). Read as "absent", a failed inspect could have let `docker volume create` reuse a leftover that held the only complete copy of an interrupted swap, which a failed restore would then have removed.
   - A leftover temp volume or a stopped swap container prints which case applies. If the state marker `.daaf-restore-swap-started` is in the temp volume, or a stopped swap container exists, the earlier run had started replacing data. If the marker is absent, it had not. If the probe fails, the answer is unknown.
   - It then prints `If another restore window is still open, answer n.` and asks `Remove it and continue? (y/n)` (D3). End of input is a no. The question appears only when a leftover exists, so CI's `y\n1\nRESTORE\n` input is unchanged.
   - When the earlier run had started (or that could not be checked), every later "nothing changed" message of this run says instead `This restore did not change anything, but your DAAF data may still be` / `incomplete from the earlier restore. Run the restore again to finish it.`, so a cancel or refusal no longer reads as "your data is fine".
   - The still-running refusal and the inspect refusal add `If this keeps happening, restart Docker Desktop and try again.`: an interrupted `docker cp` can leave a container that cannot be removed until Docker Desktop restarts (docker/cli#3447, docker/for-mac#4491). The leftover-removal error carried the same line until the field-test fixes, which remove the never-started container that held the leftover in the 2026-10-05 field test and print the commands that do (see "Restore: Field-Test Fixes" below).
2. **Free space (D5), measured inside Docker only.** The restore refuses below max(B, 2B - L) + max(10% of B, 1,048,576 KB). B is the backup's data plus Claude-state KB, and L is the live data volume's `du -sk`. The messages print KB / 1,048,576 with one decimal and the label "GB", so their "GB" is a binary gigabyte (about 7% more than 10^9 bytes); the user docs call the floor "about 1 GB". The quote-free `SPACE_PROGRAM` reads `stat -f` (free blocks times block size), with no pipeline, so a failure propagates. An unmeasurable figure is a latched WARNING and the restore continues, because running out while preparing is harmless. A second check with the temp copy in place requires F + L >= S + margin before the prompt. If it can't measure, a `Note:` appears at the prompt.
3. **Prepare.** Each temp volume is created with two labels, `docker volume create --label org.daaf.restore-tmp-for=<live> --label org.daaf.restore-run=<token> <live>-restore-tmp`, only after the exact-name check found none. The token is unique to the run (a timestamp, the process ID and a random part).
   - Right after the create, the new volume must be empty (`find /dest -mindepth 1` prints nothing) and carry this run's token. Otherwise `docker volume create` handed back a volume that already existed, most likely another restore's copy, so the restore refuses and leaves it alone (`ERROR: Could not confirm that the new temporary Docker volume '...' is empty`; the volume is not marked as this run's, so nothing removes it).
   - The backup goes into it via `docker create` + `docker cp`. The Claude subfolder is stripped, `chown -R 1000:1000` runs, and the permission and symlink manifests are replayed there.
   - Every prepare-phase helper container carries the `restore-tmp-for` label, so leftovers are reaped by an exact `--filter label=` match. The swap containers are deliberately unlabelled, so a reap can never kill a running swap.
   - The temp copy is then counted with the program that already counts the restored volume; the two are byte-identical and pinned. The count must equal the backup's exactly. In the `.ps1`, when the backup was counted by the PowerShell fallback (Docker could not count it; shown as `N+` when PowerShell also hit read errors), that count is a lower bound and the temp copy must hold at least that many. PowerShell can miss files Docker sees, so an exact gate there could refuse a good copy.
   - The Claude temp volume is prepared the same way. Any failure there now stops the restore with nothing changed (D2), and the old `Failed to clear the Claude Code state volume` / `Failed to restore the Claude Code state volume` WARNINGs are gone.
4. **Confirmation moves after the checked copy (D1).** It reads `The backup was copied into Docker and checked: N files.` Cancelling removes the temp volumes and exits 0. End of input at the prompt (Ctrl+D, a short pipe) is a cancel in both twins (`.ps1`: observed on pwsh 7); in the `.sh` it used to end the script under `set -e` with exit 1 and the temp volume left behind.
5. **Swap.**
   - A running-container re-check covers both live volumes. If `docker ps` itself fails here, the restore refuses with `ERROR: Could not check whether DAAF is running`, rather than treating the failure as "nothing running" (`.sh`) or listing the error text as a container name (`.ps1`).
   - Each temp volume must still carry this run's token (`docker volume inspect --format '{{.Labels}}'`). This is checked before the state marker is written, because that write mounts the volume and would re-create a vanished one empty, and again right before each swap. A volume that is no longer this run's refuses with `ERROR: The temporary copy of the backup in Docker (volume '...') was changed by` something else, and removes nothing, not even prepare helpers by label, which may belong to the other restore. The Claude volume's last check comes after the data swap, so there the same finding goes through the after-swap path (`ERROR: The temporary copy of the Claude Code state (volume '...')`).
   - The state marker is written into each temp volume.
   - Each volume then gets one named, unlabelled container: `docker run --rm --sig-proxy=false --name <live>-restore-swap ... sh -c 'trap : INT TERM HUP; test -f /src/.daaf-restore-swap-started || exit 3; rm -rf /dest/* /dest/.[!.]* /dest/..?* && cp -a /src/. /dest/ && rm -f /dest/.daaf-restore-swap-started'`. It erases nothing unless its source holds the marker this run just wrote, so a source without it (for example, a temp volume that vanished after the marker write and was re-created empty by the swap's own mount) leaves the live volume untouched and exits 3, a code nothing else in the program uses.
   - The host reads a data-swap exit of 3, and only 3, as "nothing was replaced": `ERROR: The temporary copy of the backup in Docker was gone or could not be used` / `(exit N), so NOTHING was replaced. Run the restore again.` plus the usual "nothing changed" sentence, exit 1. Its cleanup is careful: no label reap of helpers, the marker first, and only temps that still carry this run's token are removed. Before review round 2 (S1), the marker guard's refusal (then `&&`, exit 1) was reported as "Your DAAF data may now be incomplete". Every other nonzero exit, Docker's 125 included ("the error is with Docker daemon itself", Docker's Running containers guide, Exit status), goes through the standard after-swap path: checked copy and marker kept, `ERROR: Replacing your DAAF data did not complete (exit N).`, the recovery steps, exit 1. Fix round 2 had also read a 125 as "nothing was replaced" when the swap container was gone afterwards; review round 3 (I-1) dropped that, because a Docker engine restart in the middle of the swap can return 125 after the erase ran, and the engine then removes the `--rm` container, so the careful cleanup would have deleted the only checked copy and claimed nothing was replaced. That reasoning comes from upstream PR discussion (moby PR #34999: a daemon stopped under waiting `docker run` processes gave exit 125; moby PR #46857: `--rm` containers that exited while the engine was down are removed), not from a DAAF reproduction.
   - `SWAP_VERIFY_PROGRAM` then lists both trees and compares the sorted lists. Each list holds the raw mode with type bits, owner, group, size and name, plus each link's target; the root and the marker are left out. A list that could not be written (a failed `sort`) or a tree that could not be entered counts as an error, not a match. This check exists because busybox `cp -a` does not report a failed mode or owner preservation in its exit status (busybox `libbb/copy_file.c`, from source).
   - The host accepts the comparison only with `SWAP_VERIFY=MATCH` plus `SWAP_VERIFY_ENTRIES=n:n` with equal counts, and n > 0 for the data volume. Review round 1 ran the program under dash on two empty trees and got `SWAP_VERIFY=MATCH` / `SWAP_VERIFY_ENTRIES=0:0`, which the old MATCH-only check accepted. An empty Claude volume (0:0) is allowed, because a backup taken before any login can hold one; its token check guards it instead.
   - A failed or unconfirmed swap keeps the temp volumes and prints how to finish: run the restore again, choose the same backup, answer `y`.
   - A Claude Code state failure after the data swap was replaced and checked (its identity re-check, its swap, or its swap check) now says so in plain words: `Your project files (DAAF data) were restored and checked. Only the Claude Code` / `login and session history were not restored.`, then the same keep-and-rerun steps (review round 2, S5; `_restore_fail_claude_after_data` / `Write-DaafRestoreSwapFailure -ClaudeOnly`). The three Claude ERROR lines no longer end with `Your data volume was already replaced.` The data temp keeps its marker there, so the next run reports that the earlier restore had started replacing data (deliberately conservative). When the Claude swap itself ran and failed or did not check out, two more lines follow: `Your previous Claude Code login may also be gone now; running the restore again` / `puts the backup's login and history back.` (review round 3, S-a; `CLAUDE_SWAP_RAN` / `-ClaudeSwapRan`). They are left out when the Claude copy was refused before its swap, and when the Claude swap program refused on its own (exit 3, before its `rm`).
6. **Finish.** The restored volume is counted with the same program as the temp copy, and the two counts must be equal. Any difference, including 0, goes through the after-swap path: `ERROR: After replacing your DAAF data, it holds N files, but the checked` copy held M, temp copy kept, recovery steps, exit 1. This replaces the earlier 1% comparison: `WARNING: File count mismatch.` and `ERROR: Verification failed -- 0 files found in restored volume.` (which advised reinstalling DAAF) are gone from both twins. A count that cannot be read is still a latched WARNING with exit 0. Then each temp volume's marker is deleted and the volume removed, so a temp that cannot be removed is not later reported as an interrupted swap. A failed removal is a latched WARNING that prints the `docker volume rm` command (since the field-test fixes, also how to find and remove a container that still holds the volume).

The three new container programs (`SPACE_PROGRAM`, `SWAP_PROGRAM`, `SWAP_VERIFY_PROGRAM`) are quote-free and byte-identical across the twins.

**Interrupts.** The `.sh` twin traps INT and TERM. Before a swap, the handler removes what the run created, says nothing changed, and exits 130. Its EXIT handler also removes this run's temp volumes on any other exit before a swap (an unexpected `set -e` failure, for example) and says so. During the swaps, the INT handler says the replacement keeps running inside Docker and exits 130 without touching the temp copy. After both swaps finished and were checked, it prints `Restore interrupted after your DAAF data had been replaced and checked, while` the restore was finishing its last checks, keeps the temp copy, suggests running the restore again, and exits 130; before review round 1 it said the data was still "being replaced" there. Just before its closing pause, the EXIT handler re-arms INT and TERM as `trap 'exit "${RESTORE_EXIT_STATUS}"' INT TERM`, so a Ctrl+C at the closing `Press Enter to continue:` pause neither runs the INT handler (whose text would be wrong there) nor changes the exit code (review round 2, I-B; a bare `trap - INT TERM` was not enough: under a pty, a Ctrl+C at that pause still ended bash with 130, observed by the fix engineer on 2026-10-01). Review round 3 (S-b): INT and TERM are now ignored while the EXIT handler's cleanup runs, so a Ctrl+C there can no longer cut that cleanup short, and are re-armed as above just before the pause. The `.ps1` covers preparing, the prompt and the swaps in one `try`/`finally`, with outcomes as flags and no `exit` inside the `try`. Its post-swap count and cleanup run outside that `try`, where a Ctrl+C ends PowerShell without a message. Under pwsh on Linux, a Ctrl+C anywhere inside the `try` (preparing, at the prompt, or during the swap) used to print the right text and then exit 0, not 130 (review round 1's pwsh 7 repro of a `try`/`finally` hit by SIGINT printed `pwsh exit=0`), so the Control Panel, which reads only the exit code, would report an interrupted restore as a clean return. Since 2026-10-02 the last statement of that `finally` ends the process with `[Environment]::Exit(130)` when the run was interrupted and `DAAF_NESTED` is set; `daaf.ps1`'s `Invoke-DaafDelegate` sets it (`$env:DAAF_NESTED = "1"`) for the restore it starts as a child process. "Interrupted" means the `try` did not reach its end, no error was recorded, and no outcome flag explains it: a new `catch` records an unexpected error and rethrows it unchanged, so an error keeps PowerShell's own exit 1, and a Ctrl+C never runs that `catch` (observed). A restore started on its own in the user's PowerShell window still exits 0 when interrupted (known limit): there `[Environment]::Exit` would end the whole PowerShell session and close the window the recovery text was just printed in. Verified under pwsh 7.6 on Linux: in a minimal child-process repro, a SIGINT during a native command or a cmdlet inside the `try` exited 130 in 10 of 10 runs, each time after all 40 lines of the `finally`'s text were printed (an `exit 130` in the `finally` behaved the same there; without either, the exit was 0), and the end-to-end Pester cases exit 130 when interrupted while preparing or during the swap. On Windows PowerShell 5.1, the 2026-10-05 field test pressed a real console Ctrl+C in a restore started from the Control Panel (`.\daaf.ps1`): the restore printed its recovery text, and the Control Panel ended too, straight back to the PowerShell prompt with no `exited without completing (code 130)` line, so the exit code could not be seen there (exit codes were not captured; see "Restore: Field-Test Fixes" below).

**Kept, reworded and fixed.**
- The `.sh` unreadable-backup refusals stay (D4), because they name the unreadable file and a failed or short copy cannot. Their reason now reads "the copy would most likely fail partway on the same problem" or "on the same files".
- The permission and symlink replay WARNINGs say "copied" instead of "restored", because they now print before the prompt.
- The latch set changes. Free space that could not be checked and a temp copy that could not be removed are added; the two Claude clear/restore WARNINGs and the 1% `File count mismatch` WARNING are removed. The latch counts go from 7 to 6 (`.sh`) and from 8 to 7 (`.ps1`).
- The `.ps1` now reads helper container IDs from stdout only. The old `(docker create ... 2>&1).Trim()` could fold a stderr line into the ID. Review round 2 audited every other place where a merged stderr line could be read as a value and moved these to stdout only as well: the leftover swap container's state (both twins, I-A above), the new-temp emptiness listing (both), the `.ps1` helper reap's container IDs, and the `.ps1` first running-container check, which listed a stderr line as a running "container". Since 2026-10-02 that first check also refuses, in both twins, when `docker ps` itself fails, before anything is created: `ERROR: Could not check whether DAAF is running (docker ps failed, exit N),` / `so the restore cannot start safely. This restore has not changed anything.` / `Make sure Docker Desktop is running, then run the restore again.`, exit 1. The `.sh` used to end that check in `|| true` and the `.ps1` did not read its exit code, so a failing `docker ps` read as "nothing running" there (the swap-time re-check already refused).
- **Review round 2, other fixes.**
  - (S7) In the `.sh`, end of input at `Stop the container now? (y/n):` is a "no" (`Restore cancelled. Stop the container manually and try again:`, exit 0) and at the backup number an invalid selection (`ERROR: Invalid selection ''`, exit 1). Both used to end the script silently under `set -e`. The opening pause trap gains `|| true`, so a pause read that fails (no terminal any more) no longer turns the exit status into 1.
  - (S2) An identity refusal ("was changed by") that comes after the state markers were written deletes the marker from this run's other temp, if that temp still carries this run's token, and removes nothing. The next run then no longer reports this refusal as a restore that "had started replacing" the data.
  - (SF2) A new temp that fails its emptiness-and-identity check makes the cleanup careful, as a swap that did not run does: no label reap of prepare helpers (they may be another restore's), and this run's other temps are removed only if they still carry its token.
- **Review round 3, other fixes.** (S-c) On a swap that did not run, the careful-cleanup flag is set before the swap-started flag is cleared, so an interrupt between the two can no longer run the ordinary cleanup.
- The two twins word the copy-failure ERROR differently: the `.ps1` adds a `Docker said:` line, while the `.sh` shows `docker cp`'s own error above its ERROR.
- The backup twins' closing note no longer says the restore clears the volume before copying.

**Docs.** The technical FAQ and installation guide explain the new order, the leftover question, the refusals that leave another restore's copy alone, and the free-space figure: up to about twice the backup plus a margin, and on Windows and macOS the computer's drive needs that room too (and may with Docker Desktop for Linux, which keeps containers and images in a disk image file; that volumes live there too is inference). After review round 2 they also cover a swap that found its temporary copy gone ("NOTHING was replaced"), a Claude-only failure after the data was restored, end of input and the closing Ctrl+C on macOS/Linux, and the exact-name fallback; the claim that a Ctrl+C cannot stop the last step halfway is worded as the design, pending the Windows host probe (the 2026-10-05 field test has since confirmed it, and the FAQ now says so). After review round 3 they say that only a vanished copy means "NOTHING was replaced" (Docker Desktop stopping or restarting during the last step is reported as a failed last step), and that a failed Claude Code swap may have taken the previous login with it. `shell-scripting`'s `gotchas.md` gains four entries: a forwarded Ctrl+C stopping a container's `sh -c` between commands (with reading a container's state from stdout only), `docker volume create` reuse together with the unanchored `--filter name=` (with the exact-name list fallback), `docker run -v` silently re-creating a vanished named volume empty (with a marker guard that has its own exit code, and why Docker's 125 never means "nothing ran", from the two moby PRs above), and in-container `df` on Docker Desktop (including what Docker's FAQ says about Docker Desktop for Linux). Its long-path entry no longer says the volume would already have been cleared, and its busybox `pipefail` note now cites the source; since 2026-10-02 the backup twins' comments on the snapshot count say the same (busybox ash supports `set -o pipefail`, read in the source, not executed; the programs do not turn it on) instead of calling it unverified. The 2026-10-02 pass also adds the startup `Could not check whether DAAF is running` refusal to the FAQ, and `gotchas.md` gains a PowerShell entry: a Ctrl+C inside `try`/`finally` runs the `finally` and then exits 0 under `pwsh -File`, with the repro figures above and the `DAAF_NESTED`-only `[Environment]::Exit(130)` fix.

**Tests.** `tests/bash/restore_from_backup.bats` grows from 66 to 143 cases, `backup_twin_parity.bats` from 32 to 57, and `tests/powershell/restore_from_backup.Tests.ps1` from 72 to 179.
- The shared `mock_docker` in `test_helper.bash` now reports the `-restore-tmp` volumes and `-restore-swap` containers as absent by default.
- The new cases cover the branches above, including the review-round-1 fixes: a temp volume that vanishes or changes at the prompt or after the marker write, MATCH over two empty trees, end of input at both prompts, a failed leftover inspect, a non-empty new temp, the "may still be incomplete" wording, the marker deleted before the final removal, a Ctrl+C after both swaps, and (Pester) a PowerShell-fallback count as a lower bound. Review round 2's fixes add cases, in both suites, for a swap that exits 3 or 125 (with its container gone, or still there), a running swap whose state arrives with a stderr line, a stray stderr line during the new-temp check, the marker removed on an identity refusal, the Claude-only failure text, unrecognised inspect errors with the name list present, absent or failing, and the careful cleanup after a refused new temp; and, in bats, for end of input at the first two prompts and a Ctrl+C at the closing pause (under a real pty). Review round 3 turns the 125 cases into after-swap pins (swap container gone, still there, or not classifiable; both suites) and adds cases for the "old login may be gone" lines (shown after a Claude swap exit of 1 or 125 or a failed Claude check; not after its own refusal, 3, or a refused Claude copy; both suites), a Ctrl+C during the EXIT handler's cleanup and the careful flag set before the swap-started flag (bats), and three parity pins: only a data-swap exit of 3 counts as "nothing replaced" in either twin, the same "old login may be gone" lines keyed on the Claude swap having run, and the `.ps1`'s flag order matching the `.sh`. A live-write guard, with a self-test, fails on any `volume rm`, `volume create`, or write mount of a live volume outside the swap. The 2026-10-02 pass adds, in Pester, SIGINT cases (to the child pwsh, while preparing and during the swap) that exit 130 with `DAAF_NESTED=1` and 0 without it, with the same text and temp handling, an injected error inside the `try` that keeps exit 1, a failing startup `docker ps` (exit 1, nothing created) and two structural pins; in bats, the same startup refusal, a startup stderr line with exit 0 that is not a container, and a structural pin; and two parity pins (both twins' startup check, with a self-test) plus the shared refusal text, now pinned at both places.
- The parity suite pins the three programs as byte-identical and quote-free, pins the swap's trap and `--sig-proxy=false`, and pins the temp check to the post-restore count program. It also runs the real programs under the local `sh`: dash with GNU tools, not busybox.
- Mutation checks on scratch copies: 12 of 12 caught on the bats side and 12 of 12 on the Pester side in the first pass, 11 of 11 for the swap-time `docker ps` fix, and, for the review-round-1 fixes, 21 of 21 against the `.sh` and 19 of 19 on the Pester side. For the review-round-2 fixes: 21 of 21 against the `.sh` (plus 9 of 9 re-runs of round-1 guards) and 16 of 16 against the `.ps1`. For the review-round-3 fixes: 8 of 8 across both twins and the test helper. For the 2026-10-02 pass (the `.ps1` interrupt exit code and the startup `docker ps` refusal): 13 of 13, applied in place and reverted by a trap (9 against the `.ps1`: no `DAAF_NESTED` guard, no exit call, no error exclusion, a `catch` that swallows the error, no startup refusal, stderr merged into the startup names, and three against the structural pins; 4 against the `.sh`: `|| true` restored, the refusal exiting 0, stderr merged into the names, the refusal skipped). The in-container bats fallback `assert_failure` in `tests/bash/test_helper.bash` now checks the expected exit status (it silently ignored it when bats-assert is not installed), so exit-code pins can actually fail there; since review round 3 (S-d) it also fails loudly on a non-numeric expected status, which would otherwise make the comparison error out and the pin pass.
- A one-shot host probe for real busybox (`research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/2026-10-01_restore_busybox_host_probe.md`, throwaway `daafprobe_*` volumes only) was run on the Windows host on 2026-10-05 (Docker 29.1.3, busybox 1.37.0) and passed every gate (its "Field result" section). It covers the three programs (including a swap whose source lacks the marker, which must exit 3 and leave the live volume unchanged), the interrupt behavior, the label format the token check reads (observed: `map[org.daaf.restore-run:probe123 org.daaf.restore-tmp-for:daafprobe_x]`), and whether busybox `cp -a /src/. /dest/` copies the volume root's own mode and owner. It does, as GNU `cp` does (observed: the live root went from `.:700:0:0` to `.:755:1000:1000`), so `daaf-init`'s `chown -R 1000:1000 /daaf /claude-config` at every start (`docker-compose.yml`) is a backstop, not a dependency.

#### Restore: Field-Test Fixes

**Why.** On 2026-10-05 the user ran the restore field test on Windows (Windows PowerShell 5.1.26100, Docker 29.1.3, busybox 1.37.0), against a throwaway `restoretest` install while the real install was running (`research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/2026-10-05_restore_field_test_results.md`). Data safety held in every run, and the real install's volumes were provably untouched:
- A `docker events` log showed 0 write events on them (`ALL_VOLUME_EVENTS=527 LIVE_EVENTS=10 BAD_LIVE_EVENTS=0`; the 10 were the test's own read-only mounts).
- Before/after fingerprints showed nothing added or changed (`ONLY_IN_AFTER=0` for both volumes; the only entries gone were files the running DAAF session itself was rewriting).
- Their creation times were unchanged.

A Ctrl+C during the swap left the swap running to its end inside Docker (Runs 5a and 7). Three defects were found; the user chose to fix all three in both twins.

**D1: a never-started container blocked removal of a leftover.**
- Run 5a pressed Ctrl+C during the data swap. Observed afterwards: a never-started container (state `Created`, unlabelled, randomly named) whose program starts like the swap check's (`sh -c 'export LC_AL…`), referencing the temp volume and the live one, and created in the second the data swap ended. That the Ctrl+C landed between `docker run`'s create and start of the unlabelled swap-check container is inference from those facts and the `docker events` log.
- `--rm` acts only when a container exits, and the label reap does not match an unlabelled container. So, with Docker left running, `docker volume rm` failed with `volume is in use` every time, and the next restore's `y` ended in `ERROR: Could not remove the temporary copy left by the earlier restore.` The user resolved it by hand (`docker rm <ID>`, then `docker volume rm`). A Docker restart was not tried. It is expected to remove such a container: moby's `daemon/daemon.go` `restore()` at tag `docker-v29.1.3` (lines 529-535) queues a `--rm` (AutoRemove) container that is not running for removal, which then runs with `ForceRemove` (inference from source).
- Now every temp removal except the careful cleanup first lists the volume's holders, stdout only: `docker ps -a --filter volume=<temp> --format '{{.ID}} {{.State}}'`. Moby's `volume` filter matches a mount's volume name or its destination path exactly (`daemon/list.go`). A `created`, `exited` or `dead` holder is removed with a plain `docker rm <ID>`, never `-f`: the daemon refuses to remove a running container that way, and `docker rm` never removes a named volume. The volume is removed after that. Any other state, or a list that fails, removes nothing.
- On the leftover path, every leftover volume's holders are checked before anything is removed. Any holder that is not stopped (running, paused, restarting, removing, or unrecognised) refuses with `ERROR: Something is still using the temporary copy left by the earlier restore`; a failed list refuses with `ERROR: Could not check what is using the temporary copy left by the earlier` restore. Both exit 1. A refusal at this check removes nothing. The removal pass lists each volume's holders again, and if something started using one in between, it refuses the same way, after the steps before it (the label reap, the stopped swap containers, any volume already removed) have run.
- A leftover swap container, which the leftover check found stopped, is now removed with a plain `docker rm` instead of `docker rm -f`, and the printed manual command is `docker rm <swap containers>` too. Docker refuses a plain `rm` of a running container, so a swap that another restore window started under the same name while this one waited at its `y/n` question can no longer be killed. If that removal fails, no leftover volume is removed, and the restore stops with `ERROR: Could not remove the temporary copy left by the earlier restore.` and Docker's reason (review round 6, R5). A leftover swap container that is already gone counts as removed: a plain `docker rm` of a missing container exits 1 with `No such container` (the docker CLI's `cli/command/container/rm.go` at v29.1.3 ignores not-found only for `-f`; read from source). Any other failure, such as a container that is still running or a removal already in progress (the daemon's `removal of container ... is already in progress`, moby `daemon/delete.go`, read on master), stops the restore with nothing removed, and running it again a little later works (inference; fix round 8).
- The leftover-removal error drops `If this keeps happening, restart Docker Desktop and try again.`, because the restore now removes a stopped or never-started holder itself and prints the commands that do, and adds Docker's reason (`Docker said: ...`) when there is one. Every message that prints a `docker volume rm` command for a kept or leftover temp now adds `If Docker says it is in use, first run`, the `docker ps -a --filter volume=<name>` command, and `and remove each container it lists with docker rm <ID>, then try again.` A kept temp's message also says why it was kept when that is known: `Something is still using it; another restore may still be running.`, `Could not check what is using it (docker ps failed, exit N).`, or `Docker said: ...`.

**D2: Windows PowerShell 5.1 hid Docker's error text.** Run 3c's copy failure printed no `Docker said:` line. A field probe showed why: under `$ErrorActionPreference = 'SilentlyContinue'`, Windows PowerShell 5.1 drops a native command's stderr even with `2>&1` (`SILENT_LINES=1` against `CONTINUE_LINES=2`). pwsh 7.6 keeps it, so the Linux test suite could not catch this. Every `.ps1` capture that reads Docker's text now runs under `Continue` and restores the previous value afterwards: `Invoke-DaafRestoreDocker`, `Invoke-DaafRestoreDockerSplit`, the scan of the chosen backup, `docker cp`, and the two count runs. `Docker said:` now shows the last non-empty line. After a failed `docker cp`, it shows instead Docker's first line that mentions "denied", when there is one, so the line names the file that could not be read (review round 6, R6; in Run 3b that would be the `Can't add file ...rt_n.txt to tar: open ...: Access is denied.` line, not the closing `unexpected EOF`; inference from that transcript). With no such line, it shows Docker's first `Can't add file` line, which also names the file: Windows translates "Access is denied." on a non-English system, but Docker's own text is not translated (fix round 8). A side effect: on 5.1, the not-found check of an inspect now sees Docker's text too. That `Continue` stays silent and non-terminating on 5.1 is inferred from the field probe; on pwsh 7.6 it was observed.

**D3: a Ctrl+C during the Claude Code swap named the wrong data.** Run 7 pressed Ctrl+C during `Replacing the Claude Code state...` and got `Restore interrupted while your DAAF data was being replaced.`, although the data swap and its check had already finished. That phase now prints `Restore interrupted while the Claude Code state (login and session history) was being replaced.` and `Your project files (DAAF data) were already replaced and checked.` The recovery lines that follow are unchanged.

**Documented, not changed (user decision).** On Windows, a console Ctrl+C during a restore started from the Control Panel ends the Control Panel too: the restore prints its recovery text, then the PowerShell prompt returns (observed with `.\daaf.ps1`). Started by double-click (`daaf.bat`), the window may close before the text can be read (inference, untested). The FAQ says to run the restore again and choose the same backup.

**Also settled.** `docker cp` from Windows with an unreadable file in the backup fails (exit 1) and leaves a partial copy (7 of 8 files arrived, Run 3b); the restore already treats that as a failed copy and replaces nothing.

**Docs.** The technical FAQ gains an item on a temporary copy that Docker says is "in use" (the `docker ps -a --filter volume=` / `docker rm <ID>` / `docker volume rm` steps), and describes the two new leftover refusals, the confirmed Ctrl+C behavior, the Claude Code-phase message, and the Control Panel note. It no longer advises restarting Docker Desktop for a leftover that can't be removed. `shell-scripting`'s `gotchas.md` gains three entries: `docker run --rm`'s create/start gap, Windows PowerShell 5.1 dropping native stderr under `SilentlyContinue`, and a bash `$(fn 2>&1 > /dev/null)` that waits for a background job `fn` forked. It also records as observed what the field run settled: `docker cp` with an unreadable file, a never-started container holding a volume, the busybox interrupt and label-format results, and the console Ctrl+C under the Control Panel.

**Tests.** Restore bats tests 143->159, twin-parity bats tests 57->67, Pester restore `It` blocks 179->207. The fix pass's own checks ran repros of D1 under dash and bash (15 cases each) and pwsh 7.6, D3 in both twins, and caught 7 of 7 mutations. The test passes caught 6 of 6 mutations (bats) and 7 of 7 (Pester). The review fix round caught 5 of 5 (plain `rm` of the leftover swap container, and the "denied" line). Fix round 8 caught 3 of 3 (a vanished leftover swap container counted as removed, in each twin, and the `Can't add file` fallback).

#### Control Panel: Restart Container and Settings Reload

**Why.** `docker-compose.yml` wires `environment_settings.txt` in as a service-level `env_file`, which Compose reads only when it creates the container; `docker compose restart` keeps the environment the container was created with. The docs told users to run `docker compose down` and relaunch, and on a multi-instance install without a `.env` file a bare `docker compose down` targets the default project, not the install the user meant.

**Flow (`daaf.sh` `handle_restart`, `daaf.ps1` `Invoke-DaafRestart`, same order).** The handler runs inside the panel rather than as a delegated host script, because it must refresh the panel's own settings and port display afterwards, which a child process cannot do.
1. Confirm, default No: `y` or `yes` in any case, surrounding spaces ignored; end of input is No.
2. Read the edited file, before any docker command, through the same reload the restart uses later (in a subshell in `daaf.sh`; in `daaf.ps1`, which has no subshell, by snapshotting every `DAAF_*` variable and the settings tracker and restoring them in `finally`). If the file exists but cannot be read, the restart stops with nothing changed and a friendly message that names both causes, another program holding the file open and missing read permission. Both panels detect this through the reload's own failure status, and the bash loader tests the open silently before reading, so only that message shows, as on Windows.
3. Project-name guard on that read. If the file resolves to a different `DAAF_PROJECT_NAME` than the one the panel is running with, the restart stops and explains how to keep this install or switch on purpose. A `DAAF_PROJECT_NAME` the user exported before launching still wins over the file, so only a change made in the file is refused.
4. `docker compose down` with the current settings, so it targets the running project. Never `-v`: the volumes hold the research data and the login.
5. Reload the panel's settings (`reload_daaf_settings`; `Sync-DaafSettingsFile`), so compose interpolation sees edited ports. If the file became unreadable during `down`, the reload fails (the bash loader returns non-zero, the PowerShell one throws), the panel's settings are put back exactly as they were before it, and the container is left stopped with the same friendly message and how to retry, instead of starting on stale settings. A retry still targets the same install.
6. Project-name check again, on the reloaded settings. If the file now names a different project (because it was edited or deleted during `down`), the container is left stopped, `up` is not run, and the panel explains why. The pre-restart settings are put back, which also removes any key the reload adopted from the file meanwhile.
7. Refresh the panel's port display (`set_panel_ports`; `Initialize-DaafPortDisplay`), then `docker compose up -d`, the same readiness poll `rebuild_daaf` uses (30 x 2 s on `docker compose exec -T daaf-docker true`), and a check that `/daaf/CLAUDE.md` exists. On a timeout, the `Docker reported:` lines skip blank lines on both platforms. The poll keeps no log file, so a dry run writes nothing to disk.

Every failure prints guidance (for example, a port already in use at `up -d`) and returns to the menu; no docker failure ends the panel.

**Settings reload in the host libraries.** `load_daaf_settings` and `Import-DaafSettingsFile` let an already-set variable win, so calling them a second time kept every value adopted on the first call: a changed `DAAF_PORT_MARIMO` would have reached the container through `env_file` while compose interpolation kept the old port. Both loaders now record each key they adopt from the file (`_DAAF_KEYS_FROM_FILE` in `daaf_lib.sh`, not exported and reset when the library loads; `$script:DaafKeysFromFile` in `daaf_lib.ps1`, read through `Get-Variable` so it is strict-mode clean). The new `reload_daaf_settings` and `Sync-DaafSettingsFile` remove exactly those keys (only `DAAF_*` names), clear the record, and load the file again. Values the user exported before launching were never recorded, so they still win; a key deleted from the file falls back to the `docker-compose.yml` default; and a key added to the loader's whitelist later takes part with no second key list. `load_daaf_settings` now returns non-zero when the file exists but cannot be read, and `reload_daaf_settings` passes that on. Before, a caller that tested the result saw success, because `set -e` is off inside a condition. The loader tests the open silently first (with `true`, which, unlike `:`, cannot end the shell in POSIX mode), so a failed open prints nothing of its own while any other loader error stays visible. `Import-DaafSettingsFile` reads the file with `-ErrorAction Stop`, so a read failure throws whatever the caller's error preference. Every shipped bash caller now tests the result: `view_quarto.sh`, `view_notebooks.sh`, `view_logs.sh` and `run_vscode.sh` print the same friendly read-failure message and exit 1, where they used to end on bash's bare line (their PowerShell twins already stop with a visible PowerShell error, unchanged). At startup, both panels now show the same friendly read-failure message as the restart: `daaf.sh` instead of ending on bash's bare "Permission denied" line, and `daaf.ps1` instead of a raw PowerShell error, pausing before the window closes unless another DAAF script started it. In `daaf.sh`, the panel's port display now lives in its own `PANEL_PORT_*` variables instead of defaulting the `DAAF_PORT_*` names, so a defaulted port never looks "already set" to the reload and masks a port the user adds to the file later (`daaf.ps1` already kept separate display variables; they are now set by `Initialize-DaafPortDisplay`).

**Menu and docs.** Restart Container is option 11, directly after Rebuild Container; Stop Web Services moves from 11 to 12, and the help screen describes both (Restart Container's entry says it ends any open Claude Code session or web service). The installation guide (Quick Reference, multi-instance settings, authentication setup, the OpenRouter and ChatGPT-subscription provider lanes, the Option F GPT Fast step, the 64K output budget, data source API keys, port troubleshooting, and "Claude Code asks me to log in again"), the technical FAQ (port conflicts, "Claude Code asks me to log in again", the provider shim's later settings changes, the context-window declaration, the 64K output budget, "Context limit reached", the provider shim's invalid-key, ChatGPT-subscription, reasoning-effort, GPT Fast and verbosity entries, and the Harvard Dataverse key), the Data Onboarding mode's API-key guidance, `environment_settings_example.txt` (its header, the port keys, authentication, and the ChatGPT-subscription checklist), and the `run_daaf` note that `environment_settings.txt` "has been modified since this container was started" now point to Restart Container, keeping `docker compose down` plus relaunch as the manual alternative; the host `README.txt` lists restarts among the Control Panel's options. In both guides, the ChatGPT-subscription lane also says to choose Rebuild Container instead when it turns the provider shim on for the first time. The installation guide's GPT Fast step no longer says `CLAUDE_CODE_DISABLE_FAST_MODE` needs a rebuild: the variable reaches the container only through `env_file`, so a recreate applies it. Both "log in again" entries also no longer say `environment_settings.txt` is read on every start: it is applied when the container is created, so a plain `docker compose restart` does not pick up an edit. A `daaf_lib.sh` comment that said `DAAF_DATA_VOLUME_NAME` reaches compose interpolation of the external `daaf-data` volume is corrected: `docker-compose.yml` names that volume with a literal `name:` and never interpolates the variable.

**Tests.** `tests/bash/daaf.bats` grows from 72 to 104 cases, `tests/bash/daaf_lib.bats` from 33 to 45, `tests/powershell/daaf.Tests.ps1` from 69 to 112, and `tests/powershell/daaf_lib.Tests.ps1` from 4 to 6; `view_quarto.bats` (37 to 38), `view_notebooks.bats` (26 to 27), `view_logs.bats` (25 to 26) and `run_vscode.bats` (26 to 27) each gain an unreadable-settings case. The new cases cover the menu, routing and help changes; cancel (including end of input) issuing no docker command; `down` before `up -d` and never `-v`; answers in any case with surrounding spaces, and `y es` refused; the project-name guard refusing a file change and letting an exported name or an explicit `daaf` through; an unreadable settings file before the guard and after `down`; a port added to or changed in the file after startup; the readiness timeout with Docker's message captured; a failed `/daaf/CLAUDE.md` check; and a dry run that writes nothing. Further cases cover a reload that fails after `down` restoring the pre-restart settings (bats and Pester; the file turns unreadable during `down` or during the guard's read, so only the reload's own failure status can catch it), with no raw "Permission denied" line in the bash output; a project name edited, or the file deleted, during `down` leaving the container stopped with the original settings, keys added to the file during `down` removed again on restore, and a retry then proceeding; the notebook, VS Code and log-viewer URLs on non-default host ports (3718-3720); and the startup message for an unreadable file on both panels. The library cases cover the reload picking up file edits, an exported value still winning, the tracker holding only file-adopted keys with no duplicates, and a read failure: `load_daaf_settings` returns non-zero and adopts nothing, a plain `set -e` caller still stops, `reload_daaf_settings` passes the failure on, a failed open still returns a status in POSIX mode (`POSIXLY_CORRECT`), and a loader error other than the failed open stays visible (also through `daaf.sh` startup and both restart reloads); and (Pester) `Import-DaafSettingsFile` throwing on an unreadable file even under `$ErrorActionPreference = 'Continue'`. The bats restart cases run under `set -Eeuo pipefail` with a marker ERR trap, and the Pester restart cases under `Set-StrictMode -Version 3.0`. Mutation checks on scratch copies caught 57 of 59 mutants across the review rounds; the two survivors (a hardcoded notebook-URL port, and a restore that left keys added during `down` in place) are closed by the non-default-port URL cases and the added-keys case above.

---

## v3.0.2 -- 2026-08-18
<!-- AT TAG TIME: confirm this date matches the actual tag date -->

### Data Analyst Augmentation Framework -- Minor Improvements

v3.0.2 is a minor patch release with a few quite nice quality-of-life features and functionality improvements. Your DAAF folder now includes a launcher you can simply double-click to start DAAF -- a `DAAF.lnk` shortcut (with its own icon) on Windows and a `DAAF.command` on macOS -- no more terminal commands to remember! Under the hood this release also gives agents a provenance-preserving way to read web pages (basically, a better, more transparent, and more reproducible "WebFetch" tool for searching the internet!), adds a new analytic stress-testing toolkit for challenging provisional findings, minor GPT-subscription support improvements, and updates the education-data skills to align with the newest version from the Urban Institute Education Data Portal, also adding in a version-pinned data mirror for future reproducibility and consistency.

Two practical notes for existing users. First, **updating from v3.0.1 takes two updater runs to receive the new click-to-run files**: the first run fetches the new update logic itself, and the second run delivers the click-to-run scripts themselves (that second run will also offer a rebuild of the updated image -- accept it). Second, on Windows, some antivirus tools may flag the new `daaf.bat` helper the first time they see it -- this is a known false-positive pattern for unsigned batch files that create shortcuts programmatically; the file ships in the repository where you can read exactly what it does. Feel free to ask Claude or another AI assistant to review the code itself if you'd like a second opinion! I promise it's a false-positive.

### Detailed Notes

Disclosure: These notes were AI-drafted from a verified inventory of the release's commits and then reviewed by hand.

#### Double-Click Launchers for Windows and macOS

Starting DAAF no longer requires opening a terminal:

- **Windows** gets a `DAAF.lnk` shortcut with a proper DAAF icon, backed by a small `daaf.bat` helper. The updater creates the shortcut in your DAAF folder and refreshes it on every update, so it stays correct even if your folder moves.
- **macOS** gets a double-clickable `DAAF.command`.

#### Reading the Web, With Receipts

Agents that need to read a web page (documentation, API references, data-source pages) now do it through a **provenance-preserving fetch utility** instead of the built-in AI-paraphrase fetcher (it's so, so bad!!). Every fetch saves the raw website download, produces a deterministic text extract, and generates a manifest recording what was fetched, when, and from where -- so anything an agent read can be audited later. The extraction stack (Trafilatura and friends, now pinned in the image) arrives with the rebuild; before the rebuild the tool still works with a simpler fallback extractor. Trafilatura thus joins the open-source acknowledgments in the README.

#### Stress-Testing Findings Before You Trust Them

A new **creative-verification** toolkit lets you ask DAAF to challenge a provisional finding rather than just produce it: it turns a concern ("is this effect just a composition artifact?") into competing explanations, bounded discriminating tests, and evidence-calibrated interpretations in a hypothesis/evidence ledger. It's wired into the Ad Hoc Collaboration mode -- ask to "stress-test" or "challenge" a result to invoke it.

#### Updated and Version-Pinned Education Data

The Urban Institute education-data skills moved onto a **revision-pinned data mirror** (vintage 0.26.1): discovery now routes research questions straight to the mirror files that answer them, fetches pin to an exact mirror revision for reproducibility, and all fourteen source skills were deep-updated against the new vintage. Contributor tooling for building, validating, and regenerating the mirror ships alongside.

#### Provider Shim Improvements

The provider shim (the local adapter for OpenAI/ChatGPT routes) advanced to **v1.3.18**: a rebuilt lifecycle manager closes an auto-start race that could collide on startup, GPT responses now default to medium verbosity (less rambling by default), and the setup docs got a plain-language pass plus clearer triage guidance for restart verdicts.

#### Documentation and Orchestration Refinements

- **Clearer end-of-turn briefings.** The orchestrator now follows an explicit communication standard for catching you up after substantive work -- lead with the outcome, select for what matters, expand internal shorthand -- regardless of which model is running the session.
- **A leaner core rulebook.** The always-loaded instruction file was trimmed to universal content, with details relocated to the references that load when actually needed.
- Broken jump links in the changelog and framework docs were repaired.

#### For Contributors

DAAFBench -- DAAF's model-behavior benchmark harness (it measures behavioral adherence to DAAF's protocols, not research quality) -- had an active month: new model onboardings (Grok 4.6, DeepSeek V4 Pro and Flash, Thinking Machines Inkling and Inkling Small), GPT-5.6 repricing with billing reconciliation, a hardened onboarding process, and public results-viewer improvements through v3.8.1 (including a changelog for the viewer itself).

**Full Changelog**: [v3.0.1...v3.0.2](https://github.com/DAAF-Contribution-Community/daaf/compare/v3.0.1...v3.0.2)
<!-- AT TAG TIME: verify tag exists and this compare link resolves -->

---

## v3.0.1 — 2026-07-29

### Data Analyst Augmentation Framework -- Minor Fixes

v3.0.1 is a simple patch release: no flashy new functionality to be aware of, just steady work making v3.0.0's foundations more solid and adding a handful of genuinely useful conveniences on top. Most of it is under-the-hood hardening -- backups that fail loudly instead of quietly, lifecycle scripts that handle more edge cases, and OpenAI provider routing that's steadier and easier to sign into -- alongside a few new opt-in features worth knowing about: read-only host-folder mounts (give DAAF access to an actual folder on your computer!), setting up a shared research workspace across separate DAAF installs, and speed controls for the GPT provider route.

One practical note for existing users: updating will prompt a rebuild (the updater detects the Dockerfile change and offers it to you) -- accept it and you're done.

### Detailed Notes

Disclosure: These notes were AI-drafted from a verified inventory of the release's commits and then reviewed by hand -- they're kept concise for a patch release, but they capture what actually changed.

#### Provider Shim Improvements

The provider shim (the local adapter that lets DAAF run on your OpenAI or ChatGPT account) advanced to **v1.3.9**, with the work concentrated in making it smoother for operating with daily use:

- **Multimodal handling** so image-bearing requests translate cleanly through the shim (e.g., for data visualization design work).
- **GPT Fast / GPT Priority speed controls** -- a new operator command, `bash /daaf/scripts/provider_shim/gpt_fast.sh {on|off|status}`, lets you opt into faster priority service on the GPT route, turn it back off, and check the current state at a glance.
- **Better logging and diagnostics** for when something needs troubleshooting.
- **Steadier stability and sign-in.** ChatGPT-lane authentication is now handled by the bundled `codex` CLI, which makes signing in more reliable, and your ChatGPT plan-usage quota is now surfaced right in the status bar.

#### Link Host Folders and Share a Workspace Across Installs

Two new opt-in conveniences for people whose data or workflows don't fit neatly inside a single Docker container management system:

- **Read-only host-folder mounts.** You can now expose a folder from your own machine to DAAF as a read-only `/host_data` mount -- handy for large local datasets you'd rather not copy in by hand. It's read-only by design, so DAAF can draw from it but never writes back (or corrupts data!); the usual reproducibility conventions still ask you to copy anything you actually use into the project itself, but feel free to override as you see fit.
- **A shared research workspace.** A new `DAAF_DATA_VOLUME_NAME` setting lets two installs point at the same research volume, so you can (for example) run one body of work across two differently-configured containers (pit Claude models against GPT models, for example!).

#### Analytics Stack: pyfixest 0.60

The Python fixed-effects library `pyfixest` moved from 0.40 to **0.60**. The old 0.40 wheel shipped broken dependency metadata; 0.60 is clean and current. The corresponding skill got a full refresh so agents work against the real 0.60 API rather than a stale mental model, a now-incorrect cross-skill note (about `feglm` fixed-effects support) was corrected in the same sweep, and new smoke tests guard the analytical stack against silent breakage on future rebuilds.

#### Safer Housekeeping

A cluster of quiet reliability fixes across the host tooling and the safety system:

- **DAAF File Backups fail loudly, not silently.** If a copy is corroborated as truncated, the backup now reports a hard failure instead of a false success.
- **Hardened lifecycle scripts.** Parsing, rounding, and environment handling were tightened on both the Bash and PowerShell sides, closing a class of platform-specific edge cases.
- **Broader write-protection** for session logs and audit trails, keeping the record tamper-resistant.
- **Effort level is now an overridable default** rather than a hard pin, so the `/effort` command works as expected.

#### Status Bar and Context Monitoring

The status bar now surfaces your Codex plan-usage quota if you're using that route, and both its rendering and the underlying model detection were hardened so the display stays accurate across a wider range of setups.

#### For Contributors

A couple of contributor-facing improvements. DAAFBench -- DAAF's model-behavior benchmark harness -- got reliability work and scoring-validity corrections. In the interest of transparency: one scoring correction was significant enough that I rescored the archived results in place, and previously published GPT dispatch-compliance numbers rose as a result (from roughly 49% to 74%). On the testing side, the provider shim gained a dedicated CI suite (184 offline tests), and the Bash/PowerShell test coverage expanded further.

**Full Changelog**: [v3.0.0...v3.0.1](https://github.com/DAAF-Contribution-Community/daaf/compare/v3.0.0...v3.0.1)
<!-- AT TAG TIME: verify tag exists and this compare link resolves -->

---

## v3.0.0 — 2026-07-17

### Data Analyst Augmentation Framework -- Opening Doors

If v1.0.0 was about proving the concept of DAAF, v2.0.0 (*Gaining Altitude*) about rebuilding DAAF’s core framework engine for far greater flexibility and robustness, and v2.1.0 (*The Frictionless Update*) was about making it genuinely easy to install and run, then v3.0.0 is about something more fundamental to the mission of DAAF: *who gets to use DAAF at all.* This is an update designed to better meet researchers where they are. Every earlier version was geared towards a particular kind of user: someone who's comfortable enough in Python, who has an Anthropic subscription/API budget to spend, whose data is non-proprietary and/or public enough to be safe to share with AI assistants, and who just wants to run a single project on a single machine. Each of those assumptions was a barrier to entry and a limitation of what DAAF could offer to researchers across the sciences.

v3.0.0 takes almost all of these most impactful walls down, and I'm hoping that if you're reading this, you'll find DAAF is now for **you**. 

- The **language wall** falls as R becomes a first-class execution lane: enormous for social science, education research, epidemiology, and policy analysis, where R is often the native tongue. (Coming from Stata? Tell DAAF and it’ll translate any R or Python code it writes for you in the comments!)
- The **provider and cost wall** falls because DAAF can now run AI models from all major contenders: use an Anthropic API key or Claude subscription, use an OpenRouter account and API key (for any and all models available, inclusive of Claude/OpenAI/open-source), and/or use an OpenAI API key or ChatGPT subscription. Claude Code remains the driver of the system, but it can now "speak" with pretty much any service you have access to (which is especially valuable and timely given the currently intense cost-competition happening across the industry!).
- The **sensitive data wall** gets softened for researchers whose data can never leave a secure environment (HIPAA- or FERPA-governed, enclave-bound, or otherwise restricted): DAAF now comes bundled with a privacy-preserving synthetic-data generation and analysis workflow. In other words, DAAF helps you summarize/profile an existing dataset with a helper script from afar (with as much or as little detail as you can provide under your data protection agreements) and then uses the summary statistical output to construct a fully synthetic "twin" dataset it can operate on and analyze to help you rapidly prototype code *without ever exposing it to your real data.*
- The **operations wall** falls with a consolidated and much more user-friendly DAAF Control Panel interface on every operating system (no more remembering "run_daaf.sh" or "backup_daaf.sh" -- it's just "daaf.sh" for everything now!), more advanced configuration options for any type of setup, a self-healing updater, better and more sophisticated backup processes, and security hardening throughout. I've updated the Claude Code version in the container, bringing a ton of nice quality-of-life updates there (much better subagent viewability) plus access to Fable, and do a better job of saving your Claude Code configurations (so rebuilding is now truly painless! No more logging in over and over).
- And the **scale wall** falls as DAAF can now support installing arbitrarily many versions of DAAF with different configurations, environments, and setups: run multiple projects side by side, each in its own container, on its own provider or endpoint, even its own DAAF version. For example, I now have my Anthropic subscription working with Claude in one container, while my OpenAI subscription works with GPT-5.6 Sol in another container! Advanced users can even point them to the same research work and have them duke it out.

All of this comes while actually *enhancing the safety guardrails in the same sweep*. This release expands DAAF's defense-in-depth safety guards, adds more pre-flight system checks, hardens and enhances the development environment experience and workflow for contributors, fixes several research-integrity gaps, and is backed by extensive model-performance testing through our new [DAAFBench analyses](https://daaf.openaugments.org/bench).

Everything about DAAF is free and open-source, and always will be. The goal with today's update is to make DAAF accessible and relevant to more researchers, in more circumstances, as carefully and responsibly as ever.

**New to DAAF? Start with the new Getting Started video.** To go with this release, I've recorded a full tutorial and walkthrough: **[Claude Code for Social Scientists: Get Started with DAAF in 30 Minutes](https://youtu.be/BPlR9bXZxnY)**. It takes you through the entire installation process and gets you oriented to the whole environment: the Docker setup, Claude Code, and DAAF itself, plus the everyday essentials like managing files in the browser editor, using the session log viewer, and keeping your installation up to date.

I've worked really hard to get all of these various systems up and running and robust enough for daily use. That being said, everything requires testing and feedback from users to improve so I know how things go under real-world conditions! Whether you’re one of the ~2,000 unique installers of DAAF so far or just getting started today, I’d love to hear from you!! If you have any feedback, ideas, suggestions, or just want to let me know how it’s going, I’d love to hear from you at our [Discord community](https://discord.gg/7FWTnZJDqy) or at [support@openaugments.org](mailto:support@openaugments.org).

### Important Notes for Existing Users

If you're coming from an existing installation, v3.0.0 is a larger release than its recent predecessors, and a few things will need your attention to update smoothly.

- **Back up your work.** For those coming from v2.1.0 (anyone who has the update_daaf.sh/ps1 script), the updater automatically asks you to back up your work. You should do this just in case! Otherwise, download your /research folder from the Docker Volume just in case for safe keeping. I've developed some really careful systems to not do anything harmful while updating, but better safe than sorry.
- **Run your updater TWICE.** Because of a limitation in the older updater, you'll just need to run your updater script twice in a row. The **first run** applies most everything, as well as some helpful updates to the updater itself. The **second run** uses the freshly upgraded updater to deliver the new daaf.sh/daaf.ps1 control panel for you to start using instead of the older helper scripts (keep them there! daaf.sh/ps1 uses them behind the scenes). If everything is already current, it simply reports "Already up to date!", and it is always safe to re-run. 
- If coming from a **pre-v2.1.0** installation (any install without the built-in `update_daaf` script in your installation folder), use the `migrate_daaf` path instead: see the [migration guide in the Installation and Quickstart guide](user_reference/01_installation_and_quickstart.md#migrating-from-an-older-installation).
- When you've started it up again, **confirm your execution language.** Python remains the default, set in CLAUDE.md for all agents to respect, but R is now a fully supported alternative. If you want to change the default, just ask Claude. You can also set it on a per-project basis; just let Claude know when you start a project or revisit an older project.
- **New safety/reproducibility/auditability rules your custom scripts and workflows must respect.** A handful of constraints are now enforced to protect reproducibility and the core audit trail: runtime package installs are blocked for **both Python and R** (ask Claude to instead add packages to the Dockerfile's user-additions block and rebuild) to ensure actual reproducibility and portability; scratch and intermediate files must be written inside the project folder, never in the Docker container's ephemeral `/tmp` (so you can keep them in the Docker Volume and via backups, otherwise they just disappear on rebuild!); shell commands must run one per call (no `&&`, `;`, or `||` chaining); and agents no longer make git commits by default. That last item is a new opt-in **"Git commit management"** preference — leave it off and every script version is still preserved in the working tree as your complete audit trail; turn it on and DAAF may offer commits at natural milestones for you to approve.
- **Running more than one instance.** You can now run as many distinct installs of DAAF as you'd like! You'll need to set up some command line arguments before installing to do so: Give each simultaneous instance a distinct `DAAF_PROJECT_NAME` and non-conflicting `DAAF_PORT_*` values in its `environment_settings.txt` so their containers and browser ports don't collide. See the Advanced Configuration section of the [Installation and Quickstart guide](user_reference/01_installation_and_quickstart.md#advanced-installation--configuration).

If you run into any issues, please don't hesitate to create a GitHub Issue, reach us on our [Discord community](https://discord.gg/7FWTnZJDqy), or email [support@openaugments.org](mailto:support@openaugments.org).

### Detailed Notes

Disclosure: Headline info above was initially drafted by Fable and then edited carefully by hand. Detailed notes below are all Fable but capture the right info!

#### First-Class R Support

DAAF now treats your execution language as a first-class choice. Pick R — at first run or any time — and the entire pipeline follows: code-producing agents write `.R` scripts instead of `.py`, load R libraries instead of their Python counterparts, and assemble **Quarto** notebooks instead of Marimo. Python remains the default and is unchanged; nothing about existing Python work is disturbed.

Under the hood, this is a routing architecture rather than one skill pretending to know every library. The `data-scientist` methodology skill picks the right *method* for your question, then routes to a language-specific library skill for the implementation. v3.0.0 adds **18 new skills (growing the catalog from 36 to 54)**, most of them the R analytic stack: `tidyverse` (data manipulation), `ggplot2` (graphics), `fixest` and `plm` (fixed-effects and panel models), `r-stats` (regression, GLMs, time series), `survey-r` (complex surveys), `sf-terra` (spatial), `tidymodels` (machine learning), `igraph-r` (networks), `gt` (tables), `plotly-r` (interactive graphics), and `quarto` (notebooks). Python's side grew too, with `great-tables` (publication-quality tables) and `igraph` (network analysis). Rounding out the eighteen: `python-r-translation` and `stata-r-translation` for readers coming from other languages, and the `synthetic-data-workflow` and `daaf-deploy-smoke-testing` skills described elsewhere in these notes. Method-to-library routing now happens by execution language, so "use a fixed-effects model" resolves to `fixest` in R and `pyfixest` in Python automatically. R scripts are held to the same **file-first execution** discipline as Python (direct `Rscript` calls are blocked in coding agents in favor of the audited capture wrapper), and the image ships R **smoke tests** covering the analytical stack.

The R lane reaches DAAF's bundled data expertise, too. All 15 existing data-source skills — the federal education catalog (CCD, IPEDS, CRDC, College Scorecard, EDFacts, SAIPE, and more) plus county-level presidential election returns — gained R-oriented access and filtering examples alongside strengthened source-specific safeguards: coded-value and suppression handling, coverage and selection limits, reporting lags, and historical-change cautions stay attached to the code that needs them. Each source skill also makes its verification hierarchy explicit — trust the actual data first, the source's live codebook second, and the skill's summary third — so an agent that hits a discrepancy investigates instead of assuming its own documentation is right. To be clear about scope: no new data sources were added in this release; this is the same catalog, made more careful and more bilingual.

**R is engineered for parity.** Every method family routes to an R equivalent, notebooks compile to Quarto, and — new in this release — reproducibility verification enforces *synchronized, fail-closed parity contracts for both languages* (see *Reproducibility Verification Hardening* below). Our standing position: **if you find a workflow that works in Python but not R, we treat that as a bug — please report it.**

That said, parity is a goal we hold ourselves to, not a blanket guarantee, and a few asymmetries are worth knowing about:

- **One intentional difference:** under the new UTF-8 locale, base R's `sort()` and `order()` use ICU dictionary-style collation rather than raw byte order (see the *R Unicode (UTF-8) Handling Fix* section below). This is the correct, standard behavior; it is called out so a re-ordered result doesn't surprise you.
- **Causal-inference reference code is currently Python-oriented** (matching/IPW/AIPW, synthetic control, causal ML/DML/CATE, Heckman selection, mediation). R users are routed to `fixest`/`plm`/`r-stats` plus the R library skills; the identification logic is identical, but the worked examples are Python-first. Worth checking for your workflow.
- **A couple of methods are Python-only today:** the DBSCAN and HDBSCAN density-clustering algorithms, and complete point-pattern spatial modeling in R is not claimed. If one of these is central to your study, confirm the route before committing.
- **Regression-table tooling differs by design:** R has a `modelsummary` pathway alongside `gt`; Python's `great-tables` handles formatted data tables and points regression output to the estimator's own tables (e.g., `pyfixest`'s `etable()`). Plan cross-language reports with that in mind.

Bayesian modeling, survival analysis, and deep learning remain outside DAAF's current skill coverage in either language — escalate rather than assume a route exists.

One more thing that makes the whole system friendlier: **if you read code most comfortably in another language, just say so.** Whether you're a Stata user working in Python, a Python user working in R, or an R user working in Python, DAAF can add inline translational comments in your home language via its translation skills — set once as a persistent preference and applied automatically from then on.

#### Runtime Modernization: Ubuntu Noble, R 4.5.3, and Quarto

To carry the R toolchain, the container moved to a modern **Ubuntu 24.04 "Noble"** base image with system Python 3.12, **R 4.5.3**, and a pinned **Quarto** install, on freshly organized and pinned package layers. R packages install from prebuilt binaries on both Intel and Apple Silicon, so the framework's R stack no longer compiles from source on Macs. Because this is a base-image change, **an image rebuild is required** before you rely on v3.0.0 — when you update, the updater detects the Docker-file changes and offers to run the rebuild for you (you can also run `rebuild_daaf` yourself any time). Adding your own packages still goes through the Dockerfile's user-additions block followed by a rebuild, which keeps the environment reproducible.

#### Provider Routes: Run DAAF on Your Own Account

DAAF no longer assumes one way to reach a model. You can run it on:

- **Anthropic** — your Claude subscription (interactive login or OAuth token) or a direct `ANTHROPIC_API_KEY`. This is the **supported** baseline route.
- **OpenRouter** — point DAAF at OpenRouter for broader model and provider flexibility, configured entirely through `environment_settings.txt`.
- **OpenAI API via DAAF's provider shim** — a local adapter translates between Claude Code and an OpenAI backend, so an `OPENAI_API_KEY` can drive DAAF.
- **Your existing ChatGPT subscription** — the same shim, in its ChatGPT/Codex mode, lets a ChatGPT subscription power DAAF. This route has a lower backend context ceiling (~370k tokens, measured) than the API routes. You'll authenticate with the bundled Codex program in the background (using its CLI).

The three newer routes (OpenAI API, OpenRouter, ChatGPT-subscription) are **supported pathways under active, extensive testing** — they work, and we want your reports as more people use them. Model-name remapping environment variables let you map DAAF's model tiers onto whatever your provider offers, and context-window detection now queries each route for the real context length of the model you're actually running (the ChatGPT lane instead applies its measured backend ceiling), so DAAF's context-management math stays honest across providers.

#### The DAAF Control Panel: One Front Door for Everything

Day-to-day operations used to mean remembering half a dozen helper scripts (`run_daaf`, `backup_daaf`, `view_logs`, ...). Those scripts still exist — but you no longer need to think about them. A single menu-driven **Control Panel** (`daaf.sh` on macOS/Linux, `daaf.ps1` on Windows) is now the one front door: launch Claude Code, browse and edit files in the browser VS Code, inspect session logs, open Python (Marimo) or R (Quarto) notebooks, or drop into a container shell — plus backup, restore, update, and rebuild — all from one numbered menu. The panel also shows a live services dashboard that checks whether each browser service (notebooks, session logs, editor) is *actually listening* right now, not just configured to exist, so "is it running?" has a real answer at a glance.

Both panels are first-class citizens on their platform. The Windows panel is native PowerShell (compatible back to Windows PowerShell 5.1) rather than a Bash-shaped experience through a compatibility layer, and it takes real care with interactive sessions so Claude Code and container shells behave properly when launched from a menu. The macOS/Linux panel runs on the stock Bash 3.2 that ships with every Mac — no newer Bash required. And both are multi-instance aware: they read your instance's project name and ports, so the panel always talks to *its own* containers and services.

#### Self-Healing Updater and Drift Healing

The `update_daaf` script continues to get more resilient:

- **Self-healing sync:** Host tool files that a previous update missed (for example, because they were added in a release you skipped over) are now delivered automatically on the next run, even when there is nothing new to pull.
- **Drift healing:** If a host script on your machine differs from the repository version and was not part of this update, the updater now heals it automatically: your existing copy is first saved alongside it as `<name>.pre-update`, then the file is updated to the repository version. Host tool scripts have no supported local-edit use case -- all of your configuration lives in `environment_settings.txt`, which the updater never syncs or touches -- so a differing host script means staleness, not customization. If the backup cannot be written, the file is **never overwritten**; the updater instead warns you by name and prints the exact command to adopt the repository version manually. The closing summary explains which files were healed and how to restore any of them by renaming its `.pre-update` copy back.
- **Clearer conflict guidance:** When re-applying your local Dockerfile / docker-compose customizations conflicts with an update, the message now explains plainly what happened, reassures you that your changes are safe in a git stash, and points you to DAAF's User Support mode for a guided walkthrough.

Underneath all of the host tooling, every host-facing script is now held to strict plain-ASCII text, enforced by an automated lint gate — quietly ending a class of character-encoding corruption that could break these scripts on some Windows and macOS terminal configurations.

#### Smarter, Safer Backups and Restore

The backup and restore pathway grew up in this release, because copying a Docker volume across platforms is deceptively tricky:

- **Backups verify themselves.** Before copying, the backup checks that your disk has room (with a buffer to spare). Afterwards, it doesn't just trust the copy command's exit code — it compares file counts and byte totals between the source and the backup and warns you about any meaningful discrepancy.
- **Windows backups no longer silently truncate.** Symlinks inside the volume could abort a Windows-side copy partway through and quietly drop everything after them. Backups now stage the data in a helper container, record symlinks in a manifest, and stream a symlink-free tree to your host — the links are replayed faithfully on restore. A companion permissions manifest means a Windows round trip no longer scrambles which files are executable.
- **Your Claude sign-in and session history are backed up too.** Alongside the research data, backups capture the persistent Claude state volume (described under *Keeping Pace with Claude Code* below), so a restored machine picks up with your login and session history intact. Because of that, **a backup folder is sensitive** — the backup finishes with an explicit warning to store it privately and never attach it to tickets, repositories, or shared drives.
- **Restore is deliberately explicit.** Restoring shows you exactly what will be overwritten and requires typing `RESTORE` to proceed — and if something fails partway, it tells you plainly what state your volumes are in rather than pretending success.

#### Multi-Instance Support

You can now run more than one DAAF instance on the same machine without them colliding. New `DAAF_PROJECT_NAME` and `DAAF_PORT_*` settings in `environment_settings.txt` let each instance use its own container name and its own published host ports (Marimo, log viewer, VS Code). The container name is derived from your compose project rather than hardcoded, so the helper scripts target the right container automatically.

#### Environment Settings: Seeded Automatically, Handled Safely

All of your configuration lives in one place — `environment_settings.txt` in your installation folder — and v3.0.0 makes that file much easier to live with. The installer now creates it for you from the annotated template and carries forward any setup values you provided at install time (a custom project name, ports, and so on), so a customized installation keeps its identity across future launches and updates; an existing settings file is never overwritten. On the host side, the lifecycle scripts read only a small allowlist of instance keys from the file and never execute it as code — a deliberate safety choice, because the same file holds your API keys. And when a script does need to persist a setting on your behalf, it writes carefully: your comments and structure are preserved, and it tells you exactly what it changed.

The browser code editor now ships with a tenth extension, [vscode-archive](https://open-vsx.org/extension/YuTengjing/vscode-archive), which adds a right-click **Compress** menu in the file explorer. This closes a long-standing gap: the editor's built-in "Download..." action only handles whole folders in Chrome and Edge (and even there copies files one by one rather than producing an archive). Now, in any browser, you can right-click a folder, compress it to a single `.zip`, and download that — making it much easier to get your research files out of the container. The Installation and Quickstart guide has a new walkthrough of getting files into and out of the container, and the technical FAQ has a new entry on downloading whole folders.

#### Privacy-Preserving Synthetic Data Workflow

DAAF can now help you work with data that **can't leave your secure environment** -- sensitive, proprietary, PII-bearing, HIPAA/FERPA-governed, or enclave-bound data that shouldn't enter the container at all. A new `synthetic-data-workflow` skill adds a privacy-preserving path to Data Onboarding: at the start of onboarding, a **sensitivity gate** asks directly whether your data is safe to bring in. If it isn't, DAAF hands you a self-contained, disclosure-controlled profiling script that you run locally, wherever the data lives. Only a summary profile report crosses the boundary -- you review every number in it first -- and DAAF builds a realistically-shaped **synthetic** dataset and a data source skill from that report alone. You develop and debug your entire analysis against the synthetic stand-in, then run the finished, vetted code against the real data yourself to get the actual results. The synthetic data is a code-development scaffold, not an analytic substitute, and every synthetic-derived skill and report says so. Your data-governance, disclosure-review, and legal obligations remain your own to meet — the workflow reduces exposure; it doesn't adjudicate it. A four-tier disclosure ladder (schema, marginals, relationships, and full local high-fidelity synthesis) lets you share only as much as your work truly requires. See the new technical-FAQ entry, "Can I use DAAF with data that can't leave my secure environment?"

To power the in-container generation step, the framework image now includes `simstudy` and `fabricatr` (R) and `faker` (Python) as core, presence-gated packages, with matching smoke tests (`scripts/smoke_tests/smoke_synthetic_data_workflow.R`/`.py`). Tier 4 synthesis tools (`synthpop`, `sdv`) are deliberately excluded from the image -- that tier runs on your own machine, never in the container.

#### R Unicode (UTF-8) Handling Fix

DAAF's container previously shipped with no locale configured, which left R running under the bare POSIX/C locale. Python is immune to this -- it quietly coerces itself to UTF-8 at startup -- but R has no equivalent mechanism, so it would **silently corrupt non-ASCII (UTF-8) text**: reading a Unicode-containing YAML config could return nothing at all (a NULL with only a warning), and accented or non-Latin characters in data or scripts could come back byte-mangled. This release fixes the root cause by setting the image locale to `C.UTF-8` (via `LANG`/`LC_ALL`), so R handles Unicode correctly out of the box. `C.UTF-8` was chosen deliberately over a full locale like `en_US.UTF-8` because it ships in the base image with no extra packages and leaves number and date formatting untouched -- it keeps `.` as the decimal separator and English diagnostic messages. As defense-in-depth, the education-data-query skill's R fetch pattern now also self-heals the locale at runtime for anyone still on an older image, and a new zero-cost check in the deployment smoke suite asserts R's locale is correct after any rebuild.

**One intentional behavior change to be aware of:** under a UTF-8 locale, base R's `sort()` and `order()` switch from raw byte order to ICU dictionary-style collation, so alphabetical sorts that mix upper/lower case or accented characters may order slightly differently than before. This is the correct, standard behavior and affects only base-R sorting -- `dplyr::arrange()` and the shell `sort` command are locale-independent and unaffected. An image rebuild is required for the fix to take effect.

#### Safety and Execution Boundaries

Every new door in this release comes with a matching guardrail, because the whole point of DAAF is that its output is *worth reviewing* — and that depends on the container staying in a known, reproducible state. v3.0.0 strengthens several protections, all aimed at the same thing: making it hard to accidentally knock the container out of that state.

- **No surprise package installs — now in R too.** Installing packages at runtime is blocked for both Python and R, at two layers: a check on shell commands and a scan of script contents (so an `install.packages()` buried inside an R script is caught before it runs). Packages belong in the Dockerfile so that a rebuild reproduces your environment exactly.
- **Scratch files stay inside the project.** Writing working files to `/tmp` is blocked, because `/tmp` sits outside DAAF's backup and audit boundary; intermediate files live in the project where they're preserved and reviewable.
- **One command per shell call.** Chaining commands with `&&`, `;`, or `||` is blocked so each action stays individually visible to the safety and permission layers.
- **Dispatch guardrails.** Requests for remote or worktree `isolation` are stripped from subagent dispatches (neither works in the container), and a subagent can't request a more expensive model tier than the session is using — respecting your cost choices. A subagent also can't spawn its own subagents; work returns to the coordinator for redelegation.

None of these change how you do research; they're the seatbelts that let DAAF move fast without losing the audit trail.

#### Two-Tier Model Routing: Right-Sized Intelligence

Behind the scenes, DAAF's coordinator delegates work to specialist agents — and in v3.0.0 that delegation became deliberately cost-aware. Every specialist role now has a considered default tier: high-judgment roles (research planning, adversarial code review, final verification, debugging, and the analysts who produce your actual data work) run on the most capable model tier, while well-specified mechanical roles (structured lookups, notebook assembly, reference tracing) run on a faster, cheaper one. The coordinator can escalate a specific dispatch when the task turns out to be harder than its role suggests — a failed attempt gets retried with more capability, and the last-line quality gates are never downgraded. The principle is simple: you shouldn't pay flagship prices for mechanical steps, and a session you deliberately started on a cheaper model should never quietly dispatch more expensive helpers (that's the model-ceiling guard above). On alternative providers, the same two-tier logic maps onto whichever models you've configured.

#### Research-Workflow Integrity

A cluster of smaller fixes makes DAAF a more faithful research partner, led by what you'll actually notice:

- **Agents no longer commit to git by default.** Your working tree — with every preserved script version — is the complete audit trail, untouched. A new opt-in "Git commit management" preference turns on milestone commit offers if you'd rather have them (only ever executed with your approval).
- **A sanctioned way to revise a script.** A new `create_script_revision.sh` utility makes the next version of a failed script while preserving the original's immutable execution log, so the record of what was tried stays intact.
- **Plans and state stay in sync.** After you accept a change to a research plan, DAAF now re-syncs the session state file so a later session resumes from an accurate picture, and a single canonical scope policy keeps plan sizing consistent.
- **Claims are graded by evidence.** Agents across the fleet now distinguish what they *observed* — a command that actually ran, quoted with its output — from what they *inferred*, and they're required to say which is which. Claims that something is unavailable or impossible carry the highest evidence bar (those false negatives fail silently and compound), and completion accounting comes from tool output rather than memory. In short: when DAAF tells you something ran, it's because it ran.

#### Reproducibility Verification Hardening

DAAF's Reproducibility Verification mode — re-run an existing analysis and compare the results against the originals — was formalized and hardened in this release, with Python and R held to the same synchronized checks. The comparison machinery is now **fail-closed**: if something can't be verified, it stops and says so rather than quietly passing. Under the hood that means a path-containment audit that keeps a reproduction inside its own sandbox, artifact-by-artifact comparison against the original data files, and tolerance-aware log comparison that can tell a trailing-decimal difference from a real divergence. During this release's development, all six reproducibility test suites passed at 98/98 checks. As ever, reproducibility support helps you re-run and compare an analysis — it does not guarantee bit-identical results, because environment drift and re-fetched data are real.

#### Keeping Pace with Claude Code: Fable Support, Background Agents, and Live Telemetry

DAAF rides on Claude Code, and Claude Code has been moving fast — this release updates the pinned version from 2.1.112 to **2.1.202** and adapts DAAF to genuinely take advantage of what arrived in between.

- **Fable-ready.** Anthropic's new Claude 5 family (Fable, and its restricted-availability sibling Mythos) is recognized everywhere model identity matters in DAAF. Because these models sustain quality much deeper into large context windows, DAAF's session-health system gives them their own validated thresholds — double the token budget before the first caution light, compared to the conservative defaults that still govern Opus, Sonnet, and non-Claude models — and the cost-control guard that keeps specialist agents from out-ranking your chosen session model understands the new tier ordering. If you run DAAF on Fable, the framework knows exactly what it's working with.
- **Specialist agents now work in the background.** Newer Claude Code releases run subagents as background processes, and DAAF leaned in: the old one-at-a-time foreground restriction is retired, so a wave of specialists can genuinely work in parallel. To keep that parallelism from costing rigor, the coordinator follows an explicit "wave barrier" discipline — it waits for every specialist in a dispatched wave to report back before drawing conclusions, so an early result never gets over-weighted just because it arrived first.
- **Live telemetry for every agent.** A new status bar shows your session's model, git branch, reasoning-effort level, a live context meter, and (on subscription plans) your rate-limit windows — and a companion agent panel shows each background specialist's model, status, and its own context meter. Under the hood, DAAF's monitoring became fully subagent-aware: every specialist is measured against its own transcript and its own model's context window, never the coordinator's, so workload warnings always land with the right agent.
- **Log in once — your Claude setup now survives everything short of deleting it.** Claude Code's configuration and state — your login, your settings, and your full session history with resumable transcripts (plus your Codex login, on the ChatGPT lane) — now live in their own persistent Docker volume, separate from the research workspace. Container restarts, updates, and even full image rebuilds no longer log you out or erase your session history: you can rebuild the image and then resume yesterday's session right where it left off. Only explicitly removing the volume clears this state. A huge quality-of-life win for anyone who rebuilds often.
- **Smaller adaptations continue throughout.** Dispatch-time guards now use Claude Code's newer hook protocols (that's what powers the isolation stripping and model-ceiling checks described above), session bookkeeping survives container rebuilds, and the harness defaults are tuned for research work — high reasoning effort, hour-long prompt caching, and no silent auto-compaction of your session history.

#### Testing: Deployment Smoke Checks and DAAFBench

Two new contributor-facing testing systems back this release. **Deployment smoke testing** verifies that a *live* DAAF install actually works end to end through whatever provider route it's configured for — tiered probes cover everything from a zero-cost preflight (route and environment coherence, hooks, statuslines, shim health) through a small live functional battery, plus a zero-cost deterministic battery of the framework's own test suites — a battery that now begins by testing the smoke harness itself, so the checks are themselves checked. **DAAFBench** is how we studied model behavior: we extensively tested how different models perform across DAAF's protocol pipeline — including over the new provider routes, with every archived result carrying fail-closed provenance of exactly which model and route produced it — in order to understand and harden real-world behavior, and we share the results publicly at https://daaf.openaugments.org/bench.

This release expands deterministic tests, analytical-library smokes, deployment-smoke tooling, and DAAFBench protocol-adherence evaluation; these layers have distinct scopes and do not certify scientific validity, research quality, or every provider route. Where we cite results, we cite what actually ran — for example, the six reproducibility suites recorded above at 98/98, and the safety-hook battery recorded at 119/119 as the R package-install guard landed — rather than any blanket "all tests pass" claim.

#### For Contributors

If you'd like to contribute, the CONTRIBUTING guide has expanded for v3: it now maps which kind of change touches which registration points, spells out the evidence a pull request should carry (including honest disclosure of which platform and provider route you tested), and adds guidance for custom-agent compatibility and interpreting benchmark results. Start there — see [CONTRIBUTING.md](CONTRIBUTING.md).

**Full Changelog**: [v2.1.0...v3.0.0](https://github.com/DAAF-Contribution-Community/daaf/compare/v2.1.0...v3.0.0)
<!-- AT TAG TIME: verify tag exists and this compare link resolves -->

---

## v2.1.0 — 2026-05-02

### Data Analyst Augmentation Framework -- The Frictionless Update

If v2.0.0 was about building out the reliability, robustness, and extensibility of DAAF's core analytical engine, v2.1.0 is about making it actually easy to set up, run, and maintain for real-world workflows and collaboration. For example, the original installation process asked users to juggle Docker commands, download and unzip GitHub repos, and manage the Docker volume filesystem. That friction was one of the biggest barriers to adoption, and this release implements a huge number of quality-of-life improvements to fix that. A single command now handles the entire installation. Named helper scripts replace every Docker incantation you'd need to remember and handle all of the back-end container management for you. A one-line update system means you can stay current without losing your work, regardless of when you installed DAAF for the first time. And a new session log viewer gives you a window into what DAAF is actually doing every step of the way, which is crucial for diagnostics and intuition when using the system.

Beyond the operations story, this release also sets up a number of smaller infrastructural improvements -- for example, specialist agents can return more detailed findings, and I've implemented a code-testing pipeline to help ensure every release of DAAF ships without unexpected issues or bugs. More details for the highlights of this release are listed out below!

### One-Line Installer

DAAF can now be installed with a single command on both macOS/Linux and Windows. The previous multi-step manual process has been replaced by a one-line installer that handles everything automatically -- downloading the necessary files, building the Docker image, and setting up your workspace.  Getting started with DAAF and Claude Code in a secure, well-curated, and fully reproducible environment for research has never been easier! This took a LOT of experimentation and testing, since these scripts are designed to be run on your computer, and I had to account for various versions of Windows, MacOSX, etc. etc. which is quite a headache.

### Helper Scripts for Everyday Operations

A complete suite of "helper" convenience scripts (available for both macOS/Linux and Windows) now makes it painless and straightforward to handle the most common DAAF operations. Instead of remembering Docker commands, you can simply run a script:

- **`run_daaf`** -- Start DAAF and Claude Code (automatically sets up the docker container and runs the main commands for you)
- **`update_daaf`** -- Update to the latest DAAF version available, backing up your work automatically before making changes, and helping you integrate framework changes and customizations together (more on that below)
- **`backup_daaf`** / **`restore_from_backup`** -- Save and restore snapshots of your entire DAAF workspace effortlessly. Also allows for painless sharing of entire repositories with colleagues!
- **`rebuild_daaf`** -- Rebuild the Docker image when needed to update configurations, library installs, updates, etc.
- **`view_logs`** -- Open the session log viewer in your browser to easily inspect and view what DAAF is doing at every step of its work (more on that below)
- **`run_vscode`** -- Open a full VS Code editor in your browser for browsing, editing, uploading, downloading, and reviewing files inside the container (more on that below)
- **`view_notebooks`** -- Open Marimo to browse your analysis notebooks

Every script has both a Bash (.sh, for MacOSX and Linux) and PowerShell (.ps1, for Windows) variant, and all are covered by automated tests and quality checks. This was, by far, the most time-consuming part of this release -- making cross-platform shell scripts that work reliably across macOS, Linux, and Windows is genuinely hard, and the number of edge cases to navigate and problem-solve for was humbling. I suspect there will still be some issues that I couldn't identify on my own, so please do let me know what errors and problems you encounter!

### Update and Migration Pathway

Existing DAAF users can now update to the latest version without losing their work or framework customizations in a very guided process. The `update_daaf` script automatically backs up your workspace before making any changes and uses intelligent file-change detection to handle file conflicts gracefully -- leaning on Claude Code itself to help resolve conflicts between your customizations and new framework updates. 

For anyone coming from an older version that doesn't have this script built-in (so anything before this very release), a dedicated `migrate_daaf` script detects your installation type, connects you to the update process, and gets everything organized in a guided walkthrough. Check the [Installation and Quickstart guide](user_reference/01_installation_and_quickstart.md#migrating-from-an-older-installation) for details -- just one line of code to run in your terminal to get caught up.

### Session Log Viewer

A new in-browser session transcript viewer makes it much easier to see what DAAF is doing under the hood and to diagnose issues when they arise. You can browse past sessions, search across transcripts, filter by session, and inspect individual tool calls -- all from a clean web interface. Launch it with the `view_logs` helper script. This has been genuinely useful for development too -- being able to trace exactly what happened in a subagent's session has saved hours of debugging.

### In-Browser VS Code (code-server)

DAAF now ships with a full VS Code editor (code-server) that runs inside the container and opens right in your browser. Before this, if you wanted to look at files DAAF produced -- scripts, data, reports, logs -- your options were scrolling through the terminal, digging through Docker Desktop's clunky file browser, or copying files out to your host machine. None of that is a great experience when you're trying to review an analysis or understand what happened during a session.

Now you just run `run_vscode` from your installation folder and a complete file editor and browser environment opens in your browser -- file tree, syntax highlighting, search across files, Git history, upload and download files, all of it. It comes pre-loaded with nine extensions (Python, GitLens, Git Graph, Rainbow CSV, Markdown support, and more) and a clean dark theme, so it's ready to use immediately. Everything stays inside the container's security boundary, and you don't need to change anything on your own computer to manage it.

This is one of those changes that sounds minor on paper but makes a huge difference in practice. DAAF produces a *lot* of artifacts over the course of a session, and being able to browse and inspect them in a real editor — instead of one file at a time in the terminal — makes reviewing work dramatically more natural. It's also a much friendlier way to explore the framework itself if you're learning how DAAF works or building new skills and agents.

### Environment Variable Support

DAAF now supports secure environment variable configuration via an `environment_settings.txt` file that lives on your host machine (outside the container and inaccessible to Claude). You can set API keys for Claude Code authentication, data source access, and alternative providers -- all in one place. The file is automatically loaded at container startup, and DAAF's safety system prevents Claude from ever reading or accessing it directly. An annotated example template (`environment_settings_example.txt` in your `daaf-docker/` folder) walks you through every option.

### OpenRouter Support (Experimental)

DAAF now supports running Claude Code through OpenRouter as an alternative to a direct Anthropic API key, opening the door for greater model and provider flexibility. Configuration is handled entirely through the `environment_settings.txt` file -- no code changes needed. Context window detection was also updated to correctly query OpenRouter's API for the real context length of whatever model you're running. **Note:** This integration is experimental. It works, but you may encounter rough edges. Direct Anthropic API access remains the recommended and most reliable option.

### Preliminary Phase Notes Persistence

Specialist agent findings (source research, data profiling, synthesis) are now saved to disk as complete markdown files in `output/preliminary_notes/`. Previously, DAAF's coordinator held compressed summaries in its own working memory -- which meant later stages of analysis were working from shortened versions of earlier findings. Now the full findings are saved to a file and later agents read directly from that file, so nothing is lost to summarization. This is a quiet change, but it meaningfully improves analytical continuity across long sessions.

### Shell Scripting Skill

A new `shell-scripting` skill teaches Claude the conventions and standards used across all of DAAF's helper scripts -- covering Bash, PowerShell, error handling, testing, and cross-platform gotchas. Five reference files (~2,200 lines total) cover everything from script templates to testing patterns. This means that when DAAF needs to write or modify shell scripts (or when contributors submit new ones), they'll follow consistent, well-tested patterns.

### Automated Testing and Quality Checks

New automated pipelines run on every proposed code change to help ensure that DAAF's helper scripts remain reliable as the project evolves:

- **Script quality scanning** catches common scripting errors and enforces DAAF-specific conventions automatically on every code change
- **Unit test suites** verify that both the Bash and PowerShell variants of every helper script behave correctly in isolation
- **Full lifecycle tests** exercise the complete workflow -- install, run, backup, update, rebuild, and migrate -- in a fresh Docker environment to catch problems that only appear when everything runs together
- **Pre-commit checks** flag scripting issues before they're even committed, so problems are caught as early as possible

### Under the Hood

- **Specialist agent word limits raised:** Agents can now return substantially longer findings (general agents doubled from 1,000 to 2,000 words; data profiling agents from 2,500 to 3,500), reducing the chance of truncated or incomplete results
- **Prompt caching enabled:** Repeated sessions now benefit from cached context via a new default Claude setting, improving token efficiency and reducing cost
- **Session log collection fixed:** The log collector now correctly finds all agent transcripts from a session, even when sub-agents never directly mention the project directory
- **System prompt trimmed:** Removed ~144 lines of illustrative examples from the always-loaded system prompt -- content that was consuming working memory on every single turn without adding operational value
- **Container startup simplified:** Git identity configuration moved into the image build itself, eliminating an extra startup step and simplifying the boot process
- **Claude Code updated** to version 2.1.112, from the latest pin of 2.1.87

### What's Coming Next

- **R Support** -- Bringing first-class R language support to DAAF, as well as dual-language handling for Python and R in tandem. Long time coming, but will be worth it!
- **Benchmarking tests** -- Creating an automated benchmarking process for DAAF with test cases for plan quality, code generation adherence, and quality checkpoint compliance: the beginning of systematic testing for how well different Claude models follow DAAF's conventions (and thus understanding what settings matter, and/or whether other models from other providers like open-source options are viable yet).
- **More video tutorials and walkthroughs** -- Expanding the library of guided video content

**Full Changelog**: [v2.0.1...v2.1.0](https://github.com/DAAF-Contribution-Community/daaf/compare/v2.0.1...v2.1.0)

---

## v2.0.1 — 2026-04-05

### Data Analyst Augmentation Framework — Minor Revisions

Minor revisions: Adds an explicit "User Support Mode" as DAAF's 9th engagement mode (with better documentation reading/routing for a variety of issues/questions related to DAAF, Claude Code, Docker, and Git), hardens session archiving in the event of accidental crash or unintended closes/session termination, improves user documentation with diagrams and extended content, and archives complete session logs for both sample projects (college selectivity analysis) for better transparency and future educational materials.

**Full Changelog**: [v2.0.0...v2.0.1](https://github.com/DAAF-Contribution-Community/daaf/compare/v2.0.0...v2.0.1)

---

## v2.0.0 — 2026-03-31

### Data Analyst Augmentation Framework — Gaining Altitude Release

DAAF v2.0.0 is a ground-up architectural overhaul driven by four reinforcing goals: greater **extensibility and customizability**, broad **methodological capability expansions**, heightened alignment with **reproducibility best practices as the default**, and improved **token efficiency**. The v1.0.0 framework worked, but it was overly monolithic and fragile; every session loaded thousands of lines of workflow documentation regardless of the task, and adding new capabilities (data domains, analytical methods, engagement patterns) required modifying deeply entangled files ad hoc every single time. v2.0.0 decomposes the system into modular, progressively-disclosed components that load just-in-time, so the orchestrator and agents see only what they need for the current task/mode at hand. This same modularity makes the framework straightforwardly extensible: new data domains, analytical skills, engagement modes, and agent types can be added by authoring self-contained files and running a registration checklist. Not only that, but the new Framework Development mode makes all of these processes and updates happen basically without effort; the meta-improvement systems are working fantastically (having used it extensively for this release!). The net effect is a system that uses context more efficiently, adheres to its own protocols more reliably, can cover far more methodological territory, and scales to new research domains without architectural friction. Finally, the addition of new modes like Ad Hoc Collaboration and Reproducibility Verification begin to move DAAF from a nascent proof-of-concept to a tool that can start to genuinely add value across many domains of the research and science community.

### The Headline Changes

- **Architecture:** `CLAUDE.md` shrinks from ~1,800 lines to ~500 lines of universal conventions. Orchestration logic moves into a dedicated `daaf-orchestrator` skill with reference files loaded just-in-time — so a light-lift Data Lookup session never loads the 1,950-line Full Pipeline spec. Monolithic workflow documentation is split into phase-specific files, each loaded only when the orchestrator reaches that phase. The research Plan document is decomposed into 3 purpose-specific files (Plan, Plan\_Tasks, State), allowing the orchestrator to hold strategy and status in context while referencing task details by path.

- **Engagement Modes: 4 to 8.** New modes: Data Onboarding (formerly Data Ingest, now a full orchestrated mode with API acquisition and multi-file support), Ad Hoc Collaboration, Reproducibility Verification, and Framework Development modes. Existing modes of Data Lookup (renamed from Targeted Assist), Data Discovery (renamed from Discovery), and Full Pipeline are greatly improved across the board.

- **Analytical Skills: 7 new library skills + 2 translation skills.** Each skill follows the same SKILL.md + deep references architecture, so adding support for a new library is a matter of authoring — not framework modification. New skills: statsmodels, pyfixest, linearmodels, scikit-learn (unsupervised + supervised + fairness), geopandas, svy (complex survey analysis), science-communication, plus a major expansion of the data-scientist methodology skill with 8 new reference files covering causal inference, descriptive analysis, survey analysis, geospatial, unsupervised, supervised ML, and statistical modeling. Two cross-language translation skills (r-python-translation, stata-python-translation) enable inline code annotations for users coming from R or Stata backgrounds, powered by a persistent user language preference system.

- **Citation Propagation and Verification.** A distributed citation flow spans the entire pipeline: 13 skills carry canonical citation blocks with inclusion thresholds, the research-executor tracks citations as it works, the orchestrator accumulates them in STATE.md, and the report-writer renders a four-subsection References section with rationale lines. A centralized `CITATION_REFERENCE.md` index covers ~30 methods and tools. A pre-launch audit verified 1,005 references across 46 files and corrected 58 errors (fabricated authors, incorrect API claims, deprecated parameters, dead URLs).

- **Claude Code Platform Adaptations.** Systematic adjustments to DAAF's infrastructure based on testing against Claude Code's actual runtime behavior: a new search-agent replaces generic Plan dispatches (which lacked reasoning depth), subagent transcripts are now archived alongside orchestrator sessions, the 250-character frontmatter truncation limit is accommodated with a two-tier description architecture, the Dockerfile is fully pinned and smoke-tested, and audit logs now carry per-agent identity for traceability.

- **Agent Architecture:** All agents relocated to `.claude/agents/` for native Claude Code discovery. Named agent dispatch replaces generic `subagent_type`, so each agent loads exactly its own protocol and preloaded skills — no wasted context on irrelevant behavioral instructions. Per-agent hook enforcement (`enforce-file-first.sh`) mechanically blocks direct Python execution in coding agents, ensuring protocol adherence at the infrastructure layer rather than relying on prompt compliance alone.

- **Research Integrity:** AI Use Disclosure section (GUIDE-LLM aligned) added to all reports. `CITATION.cff` for machine-readable software citation. Session metadata tracking (DAAF version, model ID, timestamps). Session log collection utilities. First-time user transparency statement on LLM limitations and researcher responsibility.

- **Self-Modification:** Framework Development mode + `framework-engineer` agent + `FRAMEWORK_INTEGRATION_CHECKLIST.md` make DAAF formally self-extensible. New skills, agents, and modes can be added through structured authoring and a registration checklist — the framework is designed to grow without requiring core rewrites.

---

### Detailed Notes

Note that Claude absolutely had to help me write most of this, there were like 100 commits to shift through major changes on.

**Reading lens:** Nearly every change below serves one or both of two goals. _Token efficiency:_ reducing what gets loaded into context so agents see only relevant instructions and adhere to them more reliably. _Extensibility:_ making it easy to add new data domains, analytical methods, engagement modes, and agent types without modifying core framework files. These goals reinforce each other -- modular components are both cheaper to load and easier to extend.

#### 1. Core Architecture Streamlining

##### 1.1 Orchestrator Extraction and Progressive Disclosure

The most fundamental change in v2.0.0 is the extraction of orchestration logic from `CLAUDE.md` into the `daaf-orchestrator` skill (`SKILL.md` + 9 reference files). `CLAUDE.md` retains only universal execution philosophy, code style rules, project conventions, and safety boundaries -- content that applies to all agents equally. The orchestrator skill handles mode classification, user communication, subagent dispatch, and workflow coordination.

This enables far better **progressive disclosure**: the orchestrator loads only the reference file for the confirmed engagement mode, rather than ingesting thousands of lines of workflow documentation upfront. Each mode reference file is self-contained with its own invocation templates, gate definitions, PSU (Phase Status Update) templates, and escalation triggers.

Had to figure out a way to ensure that the daaf-orchestrator skill correctly got loaded only by the LLM assistant interacting directly with the user, and ensure that it does so reliably regardless of how the user starts the conversation (via some reminder hooks and checks). This'll be one of those things that's unfortunately annoyingly hard to port to other systems, because the way this works is currently very Claude Code specific. See 4.2 below for more information.

##### 1.2 Workflow Phase Decomposition

The monolithic `02_WORKFLOW_STAGES.md` (1,628 lines) and `03_SKILL_INVOCATIONS.md` (1,847 lines) are replaced by five phase-specific workflow files for the Full Pipeline Mode:

| File | Content |
|------|---------|
| `WORKFLOW_PHASE1_DISCOVERY.md` | Stages 1-3.5: Goal refinement, data exploration, source deep-dives, synthesis |
| `WORKFLOW_PHASE2_PLANNING.md` | Stages 4-4.5: Plan creation, plan verification |
| `WORKFLOW_PHASE3_ACQUISITION.md` | Stages 5-6: Data fetch, cleaning, QA |
| `WORKFLOW_PHASE4_ANALYSIS.md` | Stages 7-10: Transform, analysis, visualization, QA aggregation |
| `WORKFLOW_PHASE5_SYNTHESIS.md` | Stages 11-12: Report writing, final verification |

Each file contains stage-specific invocation templates, gate criteria, verification checklists, and PSU content. The orchestrator loads them progressively as execution advances through phases, which makes session restarts far more efficient and focused, with better instructional adherence along the way.

**Data Onboarding** also receives its own progressive workflow files in the same manner, now that it's been upgraded to a full-fledged mode

- `WORKFLOW_PHASE_DO_PROFILING.md` (~855 lines) — Parts A-D profiling protocol
- `WORKFLOW_PHASE_DO_AUTHORING.md` (~270 lines) — Skill authoring and validation

##### 1.3 Plan Document Decomposition

The research Plan document is split into three purpose-specific files:

| Document | Purpose |
|----------|---------|
| `Plan.md` | Research strategy, methodology, goals, hypotheses, scope decisions |
| `Plan_Tasks.md` | Executable Transformation Sequence — task blocks for subagent dispatch, organized in parallelizable waves |
| `STATE.md` | Session state for recovery — current stage, script status, gate status, blockers, session metadata |

This separation allows the orchestrator to hold `Plan.md` and `STATE.md` in full context while referencing `Plan_Tasks.md` only by path, significantly improving context efficiency for multi-stage sessions.

**New templates:** `PLAN_TASKS_TEMPLATE.md`, expanded `STATE_TEMPLATE.md`

##### 1.4 Deleted Legacy Files

| Removed File | Replacement |
|--------------|-------------|
| `agent_reference/01_PROTOCOLS.md` | Content distributed to `full-pipeline.md` and `session-recovery.md` |
| `agent_reference/02_WORKFLOW_STAGES.md` | Five `WORKFLOW_PHASE*.md` files |
| `agent_reference/03_SKILL_INVOCATIONS.md` | Inline in `WORKFLOW_PHASE*.md` files |
| `agent_reference/07_CONTEXT_MANAGEMENT.md` | Consolidated into `CLAUDE.md` and `daaf-orchestrator/SKILL.md` |
| `agent_reference/08_LESSONS_LEARNED.md` | Replaced by per-project `LEARNINGS.md` |
| `agent_reference/EXECUTION_CAPTURE.md` | Merged into `SCRIPT_EXECUTION_REFERENCE.md` |
| `agent_reference/PLAN_TEMPLATE_INGEST.md` | Deleted (Data Onboarding does not produce a Plan.md) |
| `scripts/md-outline.sh` | Deleted (superseded by direct file reads) |
| `agents/README.md` (old location) | Replaced by `.claude/agents/README.md` |

##### 1.5 File Renames

| Old Name | New Name |
|----------|----------|
| `04_BOUNDARIES.md` | `BOUNDARIES.md` |
| `05_VALIDATION_CHECKPOINTS.md` | `VALIDATION_CHECKPOINTS.md` |
| `06_ERROR_RECOVERY.md` | `ERROR_RECOVERY.md` |
| `SCRIPT_TEMPLATE.md` | `SCRIPT_EXECUTION_REFERENCE.md` |
| `data-ingest-mode.md` | `data-onboarding-mode.md` |
| `STATE_TEMPLATE_INGEST.md` | `STATE_TEMPLATE_ONBOARDING.md` |
| `discovery-mode.md` | `data-discovery-mode.md` |
| `targeted-assist-mode.md` | `data-lookup-mode.md` |
| `revision-mode.md` | `revision-and-extension-mode.md` |

---

#### 2. Expanded and Refined Engagement Modes (from 4 to 8)

##### 2.1 Data Onboarding Mode (formerly Data Ingest)

Elevated from a simple agent invocation to a fully orchestrated mode with its own state template, profiling protocol, and skill authoring workflow. The mode profiles datasets across four parts (Structural, Statistical, Relational, Interpretation) using up to 11 scripts, with orchestrator checkpoints after setup and after critical findings review.

**New in v2.0.0:**

- **API acquisition (DI-0):** Conditional phase for API-based data sources. The agent researches the API, writes an acquisition script, and stops for user review before execution (external network call boundary).
- **Multi-file support:** Two classification types — HORIZONTAL (same structure, union-able) and HIERARCHICAL (different entity levels, must be linked). Hierarchical mode adds per-file script suffixes, a cross-file inventory script, and a mandatory cross-level linkage test script.
- **Progressive disclosure:** Profiling protocol extracted to `WORKFLOW_PHASE_DO_PROFILING.md`, skill authoring to `WORKFLOW_PHASE_DO_AUTHORING.md` — loaded just-in-time.
- **Terminology:** "Phase A/B/C/D" renamed to "Part A/B/C/D" to avoid collision with Full Pipeline's use of "phases."
- **Verbosity standards:** Subagent output cap raised from 1,000 to 2,500 words. Scripts must print complete per-column stats — execution logs are archival with no size limit.
- **Skill quality targets:** New required `analytical-context.md` reference file (including mandatory "What is NOT Included" exclusion table and "Temporal Scope" section). Reference content targets 3x-6x the SKILL.md line count with a hard minimum floor of 3x. Per-file minimums (150-200+ lines).
- **Domain Assessment protocol:** Before authoring reference files, the engineer must identify analytical domains, group columns into clusters, and create dedicated topic-specific reference files for any domain requiring 50+ lines of explanation.
- **Exclusion documentation pipeline:** DI-1 intake collects known exclusions, profiling scripts extract exclusion statements from documentation ("does not include," "excludes," "limited to"), and `analytical-context.md` requires a structured exclusion table (minimum 2 entries).
- **Cross-dataset discovery:** A new authoring step globs for all sibling DAAF data source skills to identify complementary sources sharing join keys, with worked Polars join examples in the skill.
- **Edge case handling:** When profiling confirms no coded/sentinel values, `value-interpretation.md` is created instead of an empty `coded-values.md`, documenting negative value semantics, null patterns, and expected ranges.
- **Profiling script bundling:** Profiling scripts are now bundled with skills in a `scripts/` subdirectory for provenance.
- **Naming convention:** Formal `{domain}-data-source-{acronym}` pattern with validation regex.

##### 2.2 Ad Hoc Collaboration Mode (NEW)

A flexible, user-driven dispatch loop without fixed stages, gates, or mandatory deliverables. The orchestrator operates as a thought partner, responding to conversational questions or dispatching to specialized agents as needed. Thanks to Alberto Guzman-Alvarez and Preston Magouirk for the great nudging in this direction!

**Key features:**

- Deferred workspace creation — folder only created when first artifact is produced
- `SESSION_NOTES.md` as lightweight continuity artifact (replacing STATE.md)
- Orchestrator loads `data-scientist` skill directly (exception to the standard subagent-loads-skills pattern)
- 2,000-word agent output cap (vs. standard 1,000-word pipeline cap)
- Dispatch table mapping user needs to agents

##### 2.3 Reproducibility Verification Mode (NEW)

A four-stage workflow for re-executing an existing analysis and comparing outputs against originals:

| Stage | Activity |
|-------|----------|
| RV-1 | Intake, setup, notebook decompilation into individual scripts |
| RV-2 | Sequential re-execution with comparison |
| RV-3 | Report claim verification against reproduced data |
| RV-4 | Synthesis into Reproduction Report |

**Supporting infrastructure:**

- `decompile_notebook.py` — CLI tool to extract individual scripts from a marimo notebook with a `MANIFEST.md`
- `compare_execution_logs.py` — programmatic comparison of original vs. reproduced script execution logs (row counts, column counts, key statistics, checkpoint pass/fail)
- `collect_session_logs.sh` — finds and copies matching session transcripts into a project's `logs/` directory
- `normalize_project_dir.py` — batch path normalization across decompiled scripts
- `REPRODUCTION_REPORT_TEMPLATE.md` — the Reproduction Report serves as both deliverable and session state document
- Mode-specific behavioral overrides in `code-reviewer`, `data-verifier`, and `report-writer` agents

##### 2.4 Framework Development Mode (NEW)

Enables structured, auditable self-modification of DAAF framework components (skills, agents, modes, templates, hooks, configuration).

**Key features:**

- `framework-engineer` agent with six core behaviors: template fidelity, read-before-write, integration completeness, cross-file consistency, minimal disruption, draft-then-place
- `FRAMEWORK_INTEGRATION_CHECKLIST.md` — canonical registration-point checklist for all component types (skills, agents, modes) with mandatory and conditional items
- Two checkpoints: after scoping (confirm approach) and after review pass (approve final state)
- Bidirectional escalation paths to/from all other modes
- **LEARNINGS.md feedback loop:** New "Incorporate Learnings" work type closes the gap between System Update Action Plans generated at project completion and their consumption back into the framework. A 3-subagent exploration protocol scans all `research/*/LEARNINGS.md` files, checks which items have already been addressed, and proposes prioritized execution order. Full Pipeline and Data Onboarding delivery messages proactively suggest Framework Development mode when action plan items exist.

This works so darn well, I'm really mad I didn't make this sooner! It's made the last legs of development on DAAF v2.0.0 so, so, so much better.

##### 2.5 Data Lookup Mode (renamed from Targeted Assist)

Renamed for clarity — the previous name was ambiguous about the mode's purpose. No behavioral changes; purely a nomenclature improvement.

##### 2.6 Data Discovery Mode (renamed from Discovery)

Renamed for disambiguation from the general concept of "discovery." No behavioral changes.

##### 2.7 Revision and Extension Mode (expanded from Revision Mode)

- Renamed to clarify that the mode handles both fixing existing work and extending it with new analyses
- Added formal escalation triggers, output format (Revision Status Update template), and session recovery guidance
- Added "AI Use Disclosure in Revisions" section for disclosure inheritance across versions

##### 2.8 Mode Confirmation Hard Gate

A formal "HARD GATE" is introduced at mode classification: the orchestrator must confirm the mode with the user and receive explicit approval before proceeding. A **Turn Boundary Rule** enforces that no reference files are loaded and no subagents are dispatched in the same turn as the confirmation message. A **Confirmation Self-Check** checklist validates compliance.

---

#### 3. Agent Architecture

##### 3.1 Agent Relocation

All agent definition files moved from `agents/` to `.claude/agents/` to leverage Claude Code's native subagent discovery mechanism. The old `agents/` directory and its 1,180-line README are removed.

A new `.claude/agents/README.md` (~630 lines) serves as the agent index with key inputs, outputs, and cross-references. This also allows the Orchestrator to more efficiently launch agents with pre-loaded agent protocols and default Skills, saving tokens and improving adherence.

##### 3.2 Named Agent Dispatch

All `subagent_type` values changed from generic strings (`"general-purpose"`, `"Plan"`) to agent-specific names (`"research-executor"`, `"code-reviewer"`, `"data-planner"`, etc.). Claude Code automatically loads the agent's protocol file and applies its `tools` and `permissionMode` settings.

##### 3.3 New Agents

| Agent | Purpose |
|-------|---------|
| `framework-engineer` | Framework artifact authoring and integration (Framework Development Mode) |
| `search-agent` | DAAF-native read-only explorer replacing generic `Plan` dispatches across all modes (see §11.1) |
| `data-ingest` (expanded) | Dataset profiling with multi-file and API support (Data Onboarding Mode) |

##### 3.4 Agent Invocation Template Consolidation

Invocation templates were removed from individual agent files and consolidated into the canonical `WORKFLOW_PHASE*.md` files, eliminating hundreds of lines of duplication. Agent files now focus exclusively on behavioral protocol and anti-patterns.

##### 3.5 Universal Tool Access

The `Skill` tool was added to all 14 agent frontmatter `tools` lists, enabling direct skill invocation from any agent. The `debugger` also gained `WebFetch` and `WebSearch`.

---

#### 4. Enforcement Infrastructure

##### 4.1 File-First Execution Hook (`enforce-file-first.sh`)

A PreToolUse hook that mechanically blocks direct `python`/`python3` invocations, enforcing the file-first execution protocol at the hook layer. Registered per-agent (research-executor, code-reviewer, debugger, data-ingest) rather than globally. Uses fail-closed design with an ERR trap. Framework utility scripts in `/daaf/scripts/` are whitelisted. Currently scoped narrowly to code agents in the pipeline, though we may want to consider adding to the orchestrator and all agents eventually (just gets complicated with things like Marimo notebooks and other utility scripts).

##### 4.2 Orchestrator Loading Enforcement

Two new hooks ensure the `daaf-orchestrator` skill is loaded at session start:

- `remind-orchestrator.sh` (UserPromptSubmit) — injects a reminder if the skill hasn't been loaded
- `flag-orchestrator-loaded.sh` (PostToolUse on Skill) — writes a session flag when loaded, silencing reminders

##### 4.3 Claude-Code-Guide Denial (`deny-claude-code-guide.sh`)

Blocks the built-in `claude-code-guide` subagent type (Haiku model) from being dispatched within DAAF, as it lacks the reasoning depth for framework-aware work and often is just plain wrong. Hook suggests we launch a search-agent to look directly at the Claude Code documentation online via websearch and webfetch tools. Provides alternative guidance. It's such a good idea with such bad execution; why did they do it like this?

##### 4.4 Context Reporter Improvements

- Time-based rate limiting (60-second injection interval) replacing content-based deduplication
- Human-readable timestamps in utilization messages
- Baseline estimate adjusted from 40k to 20k tokens
- **Subagent support fix:** The hook relied on a session-specific cache file for `MAX_CONTEXT` that did not exist for subagents (different session IDs). Fixed with a fallback chain that finds the parent orchestrator's cache. `CLAUDE.md` expanded with subagent-specific threshold-action table, early return protocol (5 required elements: file paths, findings summary, incomplete task list, decisions/assumptions, confidence assessment), and STATE.md coordination guidance for subagents returning under context pressure.
- Adjusted context utilization thresholds to be either percentages OR raw token counts at 150k, 200k, and 250k. While Opus and Sonnet can now handle token windows of up to 1m tokens, there's A LOT of evidence that its performance deteriorates quickly -- and regardless, costs skyrocket per turn because of it. May need to revisit later.

##### 4.5 Logging and Audit

- Session log exclusion removed from `.claudeignore` — transcripts now visible for reproducibility collection
- Edit/Write deny rules added for `.claude/logs/` to prevent audit log modification
- `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS: "1"` added to settings
- **Per-agent audit traceability:** `agent_type` and `agent_id` fields added to every JSONL audit log entry, enabling post-session filtering by specific agent. Orchestrator calls default to `"orchestrator"`; subagent calls populate the actual agent type and unique ID.
- Added some utility scripts that automatically pull in copies of relevant session logs into a given project for full auditability in the full pipeline mode.

---

#### 5. Analytical Skills

##### 5.1 New Python Library Skills

| Skill | Lines (SKILL.md + refs) | Key Coverage |
|-------|------------------------|--------------|
| **statsmodels** | ~4,300 | OLS/WLS/GLS, GLM (logit, probit, Poisson, NB), robust regression, ARIMA/SARIMAX/VAR, mixed effects, diagnostics, hypothesis testing |
| **pyfixest** | ~2,400 | High-dimensional FE (OLS/IV/Poisson), DiD (TWFE, did2s, lpdid, Sun-Abraham), wild bootstrap, publication tables via `etable()`. Targets v0.40.0 with breaking-change documentation. |
| **linearmodels** | ~2,900 | PanelOLS (FE/RE), BetweenOLS, FirstDifferenceOLS, Fama-MacBeth, IV2SLS/LIML/GMM, SUR, IV3SLS, asset pricing. Cross-library syntax comparison tables. |
| **scikit-learn** | ~3,000 | KMeans, DBSCAN, HDBSCAN, PCA, t-SNE, UMAP, GMM (unsupervised). Logistic regression, random forest, gradient boosting, SVM, Ridge/Lasso (supervised). Preprocessing, pipelines, cross-validation, feature selection. Targets v1.8.0. |
| **geopandas** | ~3,400 | GeoDataFrames, spatial joins, CRS/projections, raster integration (rasterio, xarray), PySAL ecosystem (Moran's I, LISA, spatial regression), visualization (matplotlib + contextily, folium, lonboard). Targets v1.1.3. |
| **svy** | ~1,700 | Complex survey data analysis: design specification (strata, PSU, weights, FPC), variance estimation (Taylor linearization, BRR, jackknife, bootstrap), survey-weighted GLM regression (gaussian, binomial, Poisson), domain/subpopulation estimation, calibration, survey data I/O. Targets v0.13.0 (supersedes archived samplics). |
| **science-communication** | ~1,700 | Audience analysis, narrative frameworks (Pyramid Principle, SCQA, AIDA), plain-language translation, hedging/uncertainty (IPCC calibrated), deliverable templates (executive summary, policy brief), accessibility/equity, pre-release review checklist. |

Each skill follows the SKILL.md + deep references architecture with decision trees for routing and explicit boundary documentation against sibling skills.

##### 5.2 Cross-Language Translation Skills and User Language Preferences

Two translation skills provide verb-by-verb mappings from R and Stata to their Python equivalents, enabling inline code annotations for users with non-Python backgrounds.

| Skill | Lines (SKILL.md + refs) | Key Coverage |
|-------|------------------------|--------------|
| **r-python-translation** | ~7,400 | tidyverse → polars, ggplot2 → plotnine, fixest → pyfixest, survey → svy, sf → geopandas, plm → linearmodels. Paradigm differences, gotchas, external resources. |
| **stata-python-translation** | ~8,700 | Data management, strings/dates/labels, regression modeling, causal inference, visualization, survey/spatial/ML, workflow/environment. Mirrors the R skill architecture. |

**User Language Preference System:** A persistent, cross-session preference mechanism stored in `CLAUDE.md` § User Preferences. The orchestrator detects R/Stata background signals (explicit: "I use R"; implicit: R/Stata syntax in pseudocode), proposes persisting the preference, and silently propagates a translation directive to all 4 code-producing agents (research-executor, code-reviewer, debugger, data-ingest) across all sessions. Wired into 5 mode reference documents and 2 workflow phase invocation templates.

##### 5.3 Supervised ML Track

- New `supervised-ml.md` methodology reference for the `data-scientist` skill covering prediction vs. inference (Shmueli 2010), bias-variance tradeoff, cross-validation strategies, model selection, feature importance caveats, algorithmic fairness impossibility theorems, and reporting standards
- New `scikit-learn/references/interpretation.md` — SHAP (TreeExplainer, KernelExplainer), permutation importance, partial dependence, ICE plots
- New `scikit-learn/references/fairness.md` — fairlearn MetricFrame, ThresholdOptimizer, ExponentiatedGradient, demographic parity, equalized odds
- LightGBM and XGBoost sections added to classification and regression references
- Supervised ML routing wired into Full Pipeline modeling library selection

##### 5.4 Data-Scientist Skill Expansion

The `data-scientist` skill was restructured from a single "statistical analysis" routing branch into seven methodology-specific routing trees with eight new reference files (~5,050 lines total):

| Reference File | Coverage |
|---|---|
| `causal-inference.md` | DAGs, potential outcomes, RCT, IV/2SLS, RD, DiD, synthetic control, matching/PSM |
| `descriptive-analysis.md` | Summary statistics, distributions, cross-tabulations, temporal patterns |
| `statistical-modeling.md` | Model selection, assumption checking, diagnostics |
| `survey-analysis.md` | Complex survey design anatomy, weight selection, variance estimation methods, domain estimation, plausible values, survey-weighted regression, federal survey reference table, pitfalls checklist |
| `exploratory-unsupervised.md` | Clustering, PCA, nonlinear embeddings, cluster validation |
| `supervised-ml.md` | Prediction vs. inference, cross-validation, fairness, reporting |
| `geospatial-analysis.md` | MAUP, CRS, spatial autocorrelation, spatial regression |
| `geospatial-operations.md` | Spatial joins, weights, LISA, interpolation, zonal statistics |

A ~125-row topic index in SKILL.md maps specific analytical topics to the correct reference file. Beefy, but definitely worthwhile and still extensible.

##### 5.5 Modeling Library Pipeline Wiring

- `data-planner` task specs now require a `<skill>` element specifying the modeling library
- `research-executor` skill loading tables updated with conditional library loading and fallback rules
- `debugger` gains a "Modeling Library Gotchas" section with per-library failure mode summaries
- `report-writer` gains conditional Step 5.5 for science-communication skill loading when target audience is non-technical
- `PLAN_TEMPLATE.md` gains a "Target Audience" field controlling communication skill routing

---

#### 6. Research Integrity and Attribution

##### 6.1 AI Use Disclosure (GUIDE-LLM Alignment)

A structured AI Use Disclosure section is added to all reports, mapping to the GUIDE-LLM v2026 reporting checklist (Feuerriegel et al.). `AI_DISCLOSURE_REFERENCE.md` maps every checklist item (A.1 through G.1) to its DAAF artifact source, tagged as `[AUTO]` (auto-populated by report-writer) or `[RESEARCHER]` (requires human completion).

Session metadata (DAAF version via git commit hash, model ID, session dates, transcript path) is captured in STATE.md at project setup and passed through to the report-writer.

AI disclosure guidance is added for all modes — including Data Discovery, Data Lookup, Revision and Extension, and Reproducibility Verification.

##### 6.2 Citation Framework

- `CITATION.cff` — machine-readable software citation (CFF standard) identifying DAAF 2.0.0 as citable software
- APA and BibTeX citation formats in README
- Layered citation guidance (DAAF + Claude + data sources + GUIDE-LLM)
- "Software & Tools" citations sub-section in report template
- FORCE11 software citation principles alignment

##### 6.3 Citation Propagation System

A distributed citation flow that tracks methodological and software attribution across the entire pipeline, from skill loading through report generation:

1. **Skill-level citation blocks:** 13 skills now carry `## Citation` sections with canonical citation text, "Cite when" / "Do not cite when" inclusion thresholds, and secondary citation guidance.
2. **Research-executor tracking:** New `Citation Tracking` core behavior and `Citations` output section. The executor reports a table of `software`/`method` type citations with rationale as part of its return format.
3. **Orchestrator accumulation:** STATE.md gains a `Citations Accumulated` section with four tables (Data Sources, Methodological References, Software & Tools, Reporting Standards). DAAF, marimo, and GUIDE-LLM are pre-populated at project setup.
4. **Report-writer rendering:** The References section is now sourced from STATE.md (not verbatim Stage 6 text) and rendered as four subsections with "_Cited because:_" rationale lines for non-data-source entries.
5. **Verification:** The data-verifier gains a citation verification step. `CITATION_REFERENCE.md` serves as a centralized index covering ~30 methods and tools with inclusion thresholds and a parsimony principle ("A report with 5 well-justified citations is better than one with 30 perfunctory ones").

User-facing documentation (first-run transparency statement, Understanding DAAF guide, Best Practices guide) updated to explain the References section and advise researchers that citations are "best-effort, not guaranteed."

##### 6.4 Pre-Launch Citation Audit

A systematic audit verified 1,005 citations, references, URLs, and attributed API claims across 46 skill reference files in 12 skill areas. 58 corrections applied:

- **HIGH (5):** Fabricated author names, wrong page numbers, reversed author order, wrong journal name
- **MEDIUM (19):** Incorrect API claims across polars (6), statsmodels (3), linearmodels (3), marimo (3), scikit-learn (1), plotnine (1), plotly (2)
- **LOW (32):** Outdated claims, deprecated parameters, incomplete option lists, dead URLs

---

#### 7. Skill Metadata and Authoring

##### 7.1 Controlled Vocabulary

Formal controlled vocabulary defined for skill frontmatter:

- `audience`: `any-agent`, `research-orchestrator`, `research-planner`, `research-coders`, `research-writers`
- `domain`: `data-source`, `data-access`, `data-documentation`, `python-library`, `research-methodology`, `research-orchestration`, `research-communication`, `skill-development`
- Standard keys: `library-version`, `skill-authored`, `skill-last-updated`

Applied uniformly across all 35 skill files with description enrichment.

##### 7.2 Skill Authoring Guide Updates

- "Concise is Key" replaced with "Right-Size Each Level": SKILL.md concise, reference files comprehensive
- Reference file density guidelines: 3x-6x ratio of reference lines to SKILL.md lines
- Anemic reference files flagged as harmful as bloated SKILL.md files
- Data source skill naming convention: `{domain}-data-source-{acronym}` with validation regex
- **250-character frontmatter limit accommodation** — see §11.2

---

#### 8. User Experience

##### 8.1 Tone and Voice Standards

Comprehensive tone specification added to the orchestrator:

- **Warm:** Encouraging, acknowledges good questions, celebrates interesting findings
- **Thoughtful:** Explains _why_ things matter, connects dots between phases
- **Patient and methodical:** Never rushes past decision points, confirms understanding
- **Educational:** Explains data caveats and methodology tradeoffs as they arise
- **Direct but not terse:** Concise without being cold
- **Honest about uncertainty:** Plain acknowledgment of ambiguity and limitations

##### 8.2 Plain-Language Communication

A translation table maps internal terminology to user-facing language (e.g., "PSU" becomes "phase checkpoint," "QA" becomes "quality review," "Stage N" becomes "step" or activity description). Internal terms like "Composite execution pattern" and "Gate GN" are never exposed.

##### 8.3 Welcome Preamble

Every conversation begins with a brief introduction to DAAF. An expanded orientation is triggered on newcomer signals ("how does this work," "what can you do"). Context-sensitive help table maps user signals to appropriate documentation files.

##### 8.4 First-Time User Transparency Statement

A first-run onboarding hook detects new users (via `activity.log` session count) and presents a candid transparency statement before the normal welcome flow. The statement covers what DAAF is and isn't, inherent LLM limitations (hallucination, sycophancy, over-confidence, non-determinism), the probabilistic nature of DAAF's quality improvements, the primacy of researcher expertise, and practical guidance for new users. Delivered in conversational tone, not as a terms-of-service wall.

---

#### 9. Infrastructure and Environment

##### 9.1 Dockerfile

New package layers for:

- **Econometrics:** linearmodels, rdrobust, marginaleffects, arch, pydynpd, svy
- **Geospatial:** geopandas, rasterio, xarray, rioxarray, contextily, folium, libpysal, esda, spreg, mapclassify, rasterstats, geopy, osmnx
- **Geospatial system libraries:** libgdal-dev, gdal-bin, libgeos-dev, libproj-dev (required by fiona, a transitive dependency of rasterstats)
- **ML:** shap, fairlearn, lightgbm, umap-learn
- **Utilities:** poppler-utils (PDF support), tabulate, great-tables, wildboottest, fastexcel

**Post-smoke-test stabilization:** 16 previously-floating packages pinned to exact versions for reproducible builds. `samplics` removed (superseded by svy). `kaleido` removed (Chromium dependency incompatible with container; plotly skill updated with workaround guidance to use plotnine for static figures). A follow-up smoke test run (246 tests) corrected additional skill documentation in pyfixest, svy, and plotly. Docker volume permissions fixed for macOS (named volumes with root ownership blocking `appuser`).

Model configuration updated to `claude-opus-4-6[1m]` (1M context window).

##### 9.2 New Utility Scripts

| Script | Purpose |
|--------|---------|
| `scripts/decompile_notebook.py` | Extract individual scripts from a marimo notebook |
| `scripts/compare_execution_logs.py` | Compare original vs. reproduced execution logs |
| `scripts/collect_session_logs.sh` | Find and copy matching session transcripts |
| `scripts/normalize_project_dir.py` | Batch path normalization across decompiled scripts |

##### 9.3 Installation Simplification

Git removed as a host-machine prerequisite. Installation now uses ZIP download (`curl`/`Invoke-WebRequest`) instead of `git clone`, reducing prerequisites from four to three. `docker-compose.yml` gains `name: daaf` for folder-independent volume naming (ZIP extracts to `daaf-main/` rather than `daaf/`). Update procedure rewritten with ZIP-based commands that copy framework files into the Docker volume while preserving the `research/` folder.

##### 9.4 CLAUDE.md Philosophy

The Identity section was expanded from a brief description to a full philosophical statement: DAAF as a "force-multiplying exo-skeleton," the five core requirements (Transparent, Rigorous, Reproducible, Responsible, Scalable), and the primacy of human researcher judgment.

---

#### 10. Documentation

##### 10.1 New Reference Files

| File | Purpose |
|------|---------|
| `AI_DISCLOSURE_REFERENCE.md` | GUIDE-LLM checklist mapping for all modes |
| `FRAMEWORK_INTEGRATION_CHECKLIST.md` | Registration-point checklists for skills, agents, modes |
| `MODE_TEMPLATE.md` | Template for authoring new engagement modes |
| `PLAN_TASKS_TEMPLATE.md` | Template for the task-block document |
| `REPRODUCTION_REPORT_TEMPLATE.md` | Template for Reproducibility Verification output |
| `STATE_TEMPLATE_ONBOARDING.md` | State template for Data Onboarding mode |
| `CITATION_REFERENCE.md` | Citation index for pipeline citation propagation and verification |

##### 10.2 Expanded Templates

- `AGENT_TEMPLATE.md` — expanded with per-agent hook registration, skills-in-frontmatter guidance
- `DATA_SOURCE_SKILL_TEMPLATE.md` — API data access skeleton, multi-file structure section, analytical-context.md requirement
- `MODE_TEMPLATE.md` — expanded from 6-item to 13-item checklist with naming conventions and exemplar references
- `REPORT_TEMPLATE.md` — AI Use Disclosure section, Software & Tools citations
- `STATE_TEMPLATE.md` — session metadata, per-script QA status, gate status tracking

##### 10.3 User Documentation Updates

All files in `user_reference/` updated to reflect eight engagement modes, three-document Plan structure, Data Onboarding capabilities, and Framework Development mode. Best practices and extending-DAAF guides revised.

---

#### 11. Claude Code Platform Adaptations

Changes driven by testing DAAF against Claude Code's actual runtime behavior, addressing platform constraints and improving observability.

##### 11.1 search-agent Replaces Generic Plan Dispatches

Generic `Plan` subagent dispatches lacked reasoning depth for DAAF's domain-aware exploration tasks. A new `search-agent` (413-line agent definition, full 12-section template) serves as DAAF's 14th agent — a broad-purpose, read-only explorer with web access (WebSearch, WebFetch) and skill-aware domain knowledge. All exploration dispatches across Data Discovery, Data Lookup, Framework Development, and Full Pipeline modes changed from `Plan` to `search-agent`. The `Plan` generic type is de-prioritized rather than removed. The `Explore` subagent type remains blocked (runs on Haiku); error messages now recommend `search-agent`.

##### 11.2 Frontmatter Description Truncation Accommodation

Claude Code silently truncates skill frontmatter `description` fields at ~250 characters. All 35 DAAF skills (previously 381-813 chars) were losing trigger and disambiguation text without any visible error. All descriptions condensed to fit within 250 characters. Full descriptions preserved as plain paragraphs immediately after the `# Title` heading in each SKILL.md body. The skill-authoring reference (`frontmatter.md`) updated with the 250-char hard limit, budget priorities, and the "Full Description in Body" pattern.

##### 11.3 Subagent Transcript Archiving

Previously, only the orchestrator's session transcript was archived. A new observability pipeline captures subagent activity:

- **`subagent-registry.sh`** — new `SubagentStop` hook records each subagent's metadata (agent\_type, agent\_id, transcript\_path, tool\_uses, duration) to a per-session JSONL registry file
- **`archive-session.sh` expansion** — at session end, copies each subagent's JSONL transcript into the archive with `_subagent_{id}` suffixes, renders companion Markdown files, and appends a "Subagent Activity" summary table to the orchestrator's Markdown archive
- **Unified naming convention:** `{date}_{time}_{session}_orchestrator.{jsonl,md}` and `{date}_{time}_{session}_subagent_{id}.{jsonl,md}` — all files from one session sort together

##### 11.4 Script Execution Portability

- `run_with_capture.sh` changed from `python` to `python3` for PEP 394 portability
- Copy-into-project pattern eliminated across 17 files — all execution now references the canonical copy at `{BASE_DIR}/scripts/run_with_capture.sh` rather than per-project copies
- Shell script executable permission convention established: all `.sh` files must be committed with mode `100755` via `git update-index --chmod=+x`, documented across 6 framework files (CLAUDE.md, framework-engineer agent, integration checklist, script execution reference, skill-authoring reference, framework-development mode)

---

### Breaking Changes Summary

These changes affect the internal framework structure. External users consuming DAAF analyses are unaffected.

| Change | Impact | Migration |
|--------|--------|-----------|
| `CLAUDE.md` reduced to conventions only | Orchestration logic must be loaded via `daaf-orchestrator` skill | Load skill at session start (enforced by hooks) |
| Agents moved from `agents/` to `.claude/agents/` | Path references must update | All internal references updated |
| `subagent_type` changed to agent-specific names | Orchestrator dispatch must use named agents | All invocation templates updated |
| Plan split into Plan + Plan\_Tasks + State | Existing single-Plan projects structurally incompatible | Create Plan\_Tasks.md and STATE.md from existing Plan |
| Multiple reference files renamed/deleted | Hardcoded path references break | See File Renames table above |
| "Data Ingest" renamed to "Data Onboarding" | Mode name references must update | All internal references updated |
| "Phase A/B/C/D" renamed to "Part A/B/C/D" | Data Onboarding terminology must update | All internal references updated |
| Direct `python` calls blocked in coding agents | Must use `run_with_capture.sh` wrapper | Already enforced by hook |
| `claude-code-guide` subagent blocked | Cannot dispatch Haiku-based guide agent | Use `search-agent` (has WebFetch/WebSearch) |
| Generic `Plan` dispatches replaced by `search-agent` | Exploration tasks use named agent | All invocation templates updated |
| `run_with_capture.sh` path changed from `{PROJECT_DIR}` to `{BASE_DIR}` | Per-project copy references break | All execution now uses `{BASE_DIR}/scripts/run_with_capture.sh` |

**Full Changelog**: [v1.0.0...v2.0.0](https://github.com/DAAF-Contribution-Community/daaf/compare/v1.0.0...v2.0.0)

---

## v1.0.0 — 2026-02-22

### Data Analyst Augmentation Framework — Launch Release

The initial public release of DAAF, an open-source, extensible AI-augmented research workflow for Claude Code that allows skilled researchers to rapidly scale their expertise and accelerate data analysis — without sacrificing transparency, rigor, or reproducibility.

#### Core Framework

- Multi-stage research pipeline with mandatory validation and quality checkpoints at every stage
- Specialized agents that tackle each stage of the research pipeline with specific insights, strategies, and expertise (e.g., research-executor, code-reviewer, data-planner, plan-checker, data-verifier, source-researcher)
- Per-script QA with adversarial code review where every transformation has a validation, and all data operations are stored in a file-first format for maximum auditability

#### Skills Ecosystem

- Analytical tools for data analysis: Polars, plotnine, Plotly, marimo, data-scientist
- Data sources: 15 source-specific data skills (CCD, IPEDS, CRDC, Scorecard, EDFacts, MEPS, SAIPE, FSA, NHGIS, NCCS, PSEO, EADA, NACUBO, Campus Safety) plus query, explorer, and context skills, to answer hundreds of meaningful research questions about education out-of-the-box
- Extensibility tools to easily expand the data domains to any field/dataset you need

#### Documentation

- User guides: installation/quickstart, understanding DAAF, best practices, extending DAAF, philosophy FAQ, technical FAQ
- 10-minute demo video walkthrough
- Complete example project for review (College Graduation Rate Selectivity Analysis)

#### Infrastructure

- Docker containerized environment with defense-in-depth security
- Pre-commit hooks, audit logging, session archiving
- LGPL-3.0 license (core framework open; extensions can be proprietary)
