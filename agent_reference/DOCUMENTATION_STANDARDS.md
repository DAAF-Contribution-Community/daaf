# Documentation Standards

This document is DAAF's single standard for how framework text is written. It sets seven
standards (S1 to S7), says which audience each kind of file serves, and gives author and reviewer
checklists. It is written for the agents and contributors who write or review framework text:
framework-engineer, the Framework Development reviewers, and anyone preparing a contribution.
Other files point here rather than restating these rules.

---

## Purpose and Scope

DAAF has to describe itself reliably, to researchers and to its own agents. A researcher who reads
a wrong or confusing instruction loses trust in the whole framework. An agent that reads one acts
on it. This standard keeps the text that ships with DAAF accurate, readable for the people it is
written for, and complete in itself.

**What it governs:** every file that ships with DAAF (the public repository) and every piece of
text DAAF shows a user:

- documentation: `README.md`, `CONTRIBUTING.md`, `CITATION.cff`, `user_reference/`
- skills, agent definitions, `agent_reference/` files and the orchestrator's mode references
- templates, including the parts of reports, plans and session state that users read or paste
- code comments in framework scripts, hooks and tests
- runtime text: script output, hook denial messages, validation banners, update prompts

**What it does not govern:** the records of a research project (`STATE.md`, `LEARNINGS.md`,
`SESSION_NOTES.md`, execution logs). They record what happened, so history is their content. The
templates that produce them are in scope. Research-script comments follow
`agent_reference/INLINE_AUDIT_TRAIL.md`. § Exemptions lists every case.

**Local customizations.** A user's own changes in their installation may cite their own folders
and notes. The standard applies to them when they contribute those changes to the public
repository.

---

## Audiences

Every passage has one primary reader. Name it before writing, because each audience gets
different rules: plain words for users, precise terms for agents.

| Audience | Files and text | What this means for the writing |
|----------|----------------|---------------------------------|
| **User-facing** | `README.md`, `user_reference/`, `CITATION.cff`; the visible output of `scripts/host/` tools; comments in files users edit (`scripts/host/environment_settings_example.txt`, the Dockerfile's user additions block); orchestrator messages to the user; templates whose output users read or paste (reports, plans, the restart prompt in session state) | Plain language (S3). Lead with what the reader does or gets. The audience test applies to every passage |
| **Contributor-facing** | `CONTRIBUTING.md`; code comments in framework scripts, hooks and `tests/` | Precise technical terms are fine. Comments follow S6 |
| **Agent-facing** | Skills (`.claude/skills/`), agent definitions (`.claude/agents/`), `agent_reference/`, the orchestrator's references | Precise internal terms (stage numbers, gate codes, PSU) are expected. Define each term once in its canonical place and point to it from elsewhere. Skill and agent descriptions are read first by the orchestrator when it routes work, so write them for that reader |
| **Mixed-audience runtime text** | Hook denials, script errors, validation output, update prompts | The first sentence is plain and tells a user what happened and what to do. Agent-facing detail follows |
| **History** | `CHANGELOG.md` and release notes | The one home for how DAAF changed. See § Exemptions |

**Templates serve two readers.** A template's instructions and coordination fields (status codes,
checkpoint fields, guidance for the agent filling it in) are agent-facing. Only the text that lands
in what a user reads or pastes (the report body, the plan narrative, the restart prompt) follows
S3.

Agent-facing text needs internal terms because an agent coordinating a pipeline needs exact names
for its steps. An undefined term still fails: write as if for a capable colleague who is new to
DAAF and has no context from the current session.

**Review priority.** When reviewing or fixing many files, work in this order, because errors cost
most where users meet them first:

1. User reference documents: `README.md`, `user_reference/`, `CITATION.cff`, `CODE_OF_CONDUCT.md`,
   `scripts/host/README.txt`, and `CONTRIBUTING.md`. Its audience is contributors (the table
   above), but it sits in this tier because new contributors meet it early
2. Files users run or edit directly: `scripts/host/` (output and the comments in
   `environment_settings_example.txt`), the `Dockerfile` and `docker-compose.yml`, the status line
   scripts in `.claude/scripts/`
3. The orchestrator skill and its references, which govern most user-facing agent messages, and
   `agent_reference/WORKFLOW_PHASE*.md`, which hold checkpoint text users see
4. Files users review, edit or paste during a project: the templates for reports, plans and
   session state (`REPORT_TEMPLATE.md`, `REPRODUCTION_REPORT_TEMPLATE.md`, `PLAN_TEMPLATE.md`,
   `PLAN_TASKS_TEMPLATE.md`, `STATE_TEMPLATE*.md`; session state holds the restart prompt), and
   `agent_reference/AI_DISCLOSURE_REFERENCE.md`, whose disclosure text lands in user deliverables
5. Runtime messages: hooks in `.claude/hooks/` and the scripts `scripts/*.sh`
6. Everything else

The triage lint groups its output by these six tiers (§ The Triage Lint). It does not scan
`CHANGELOG.md`: review that by hand, as history (§ Exemptions).

### The Audience Test

For each passage in a user-facing file, ask: **"Would a researcher who just installed DAAF need
this, here?"**

If not, move it. Contributor detail goes to `CONTRIBUTING.md`, agent detail to the skill or
reference that owns it. Detail a curious user may want stays under a bold lead line:

```markdown
**Optional reading — under the hood.** <the detail a curious user may want>.
```

Never label a passage "safe to skip": that tells the reader the text does not matter, which is a
reason to cut it, not to keep it.

---

## The Seven Standards

### S1 Accurate

**Rule.** Every statement about how DAAF behaves is checked against the file that implements it:
the script, hook, setting or template. Counts and lists are derived from the repository at the
time of writing, not recalled. When a claim cannot be checked, say so or leave it out.

**Why.** A confident wrong statement is the worst outcome: readers act on it, and agents repeat it
until it reads as settled fact.

| Don't | Do |
|-------|----|
| "`run_with_capture.sh` exits 1 when the log cannot be appended." (recalled) | "`run_with_capture.sh` exits 74 when the audit record is incomplete." (read in the script's exit table) |
| "DAAF has twelve agents." (from memory) | Count the files in `.claude/agents/` and write the number found |

### S2 Clear

**Rule.** Lead with the outcome or the action, and give the reason in one clause. Use one term per
concept everywhere. Write steps as goal, then an imperative verb, then the result. Define a term
the first time a reader meets it. Keep sentences short. User-facing prose is warm and direct, the
voice of a knowledgeable colleague; `user_reference/06_faq_philosophy.md` is the calibration
example.

**Why.** Readers scan for what to do. A term that changes between files reads as a second concept
([Google: Write for a global audience](https://developers.google.com/style/translation);
[Google: Procedures](https://developers.google.com/style/procedures)).

| Don't | Do |
|-------|----|
| "Run `create_script_revision.sh`, which strips the log, on the failed script to make a fix copy." | "To fix a failed script, run `bash /daaf/scripts/create_script_revision.sh <failed> <new>`. It copies the code without the execution log, so the copy can run." |
| "Invalid destination." | "The destination must be inside the project folder. Choose a path under your project and run the command again." |

### S3 Plain for Users

**Rule.** User-facing text names no internal codes: no stage or phase numbers, gate codes, PSU,
QA or CP checkpoint codes, Data Onboarding or Reproducibility sub-phase codes. Write around them
by describing the activity. A code the user actually sees (a project folder such as
`scripts/stage5_fetch/`, a file name, a validation banner such as `CP2 VALIDATION`) stays, and is
explained in plain words where the user meets it.

The glossary of internal terms and their user-facing wording is the orchestrator's Plain-Language
Rule table (`.claude/skills/daaf-orchestrator/SKILL.md` § User-Facing Communication Standards >
Plain-Language Rule). Add new terms there, not to a second list. One exception: a mode reference
file may keep a glossary of its own terms when the Plain-Language Rule table has a row pointing to
it (Literature Review: `literature-review-mode.md` § Plain-Language Vocabulary). A term
goes there only when it belongs to that mode; every other term goes in the Plain-Language Rule
table.

**Why.** Users judge the work by what they can follow. Internal codes are coordination language
between agents; to a researcher they are noise
([Google: Jargon](https://developers.google.com/style/jargon)).

| Don't | Do |
|-------|----|
| "Stage 6 passed CP2. Proceeding to Gate G7." | "The cleaned data passed its automated checks. Next I join the two sources." |
| "The Stage 5 scripts are in `scripts/stage5_fetch/`." (a stage code, and the folder unexplained) | "The scripts that download your data are in `scripts/stage5_fetch/`." |

### S4 Self-Contained

**Rule.** A shipped file cites only shipped files and public URLs. It never cites a development
workspace under `research/` (the folder of a Framework Development or other working session,
even if a file in it is tracked), a scratch folder, a tool or skill that exists only on a
maintainer's machine, or any other file a user's installation does not have. When a finding from
development work matters, state it in a sentence where it is needed. "Shipped" means tracked in
the public repository: `git ls-files <path>` prints it. The sample projects under `research/`
ship on purpose (`README.md` and `user_reference/02_understanding_daaf.md` link to them), so
citing them is fine.

**Why.** A citation a user cannot follow is a broken promise, and an agent that follows it finds
nothing and guesses ([Google: Cross-references](https://developers.google.com/style/cross-references)).

| Don't | Do |
|-------|----|
| "Why the lane pauses: see the design notes in `research/<date>_FrameworkDev_Search/`." | "The lane pauses for 300 seconds because the vendor blocks the caller's IP address for that long after a 429 response (verified against the Elicit API documentation on 2026-10-11)." |
| "Run the release checklist tool before tagging." (a tool that does not ship) | Describe the check itself, or leave it to contributor documentation that ships |

### S5 Current State

**Rule.** Describe how DAAF works in this release. Avoid change narration and time-relative words
("currently", "now", "new", "no longer", "formerly", "was changed", "since vX", "as of"). Give
reasons in the present tense, not as a story. History lives in `CHANGELOG.md`.

The word list targets narration about DAAF itself. A fact about an external tool's versions or
renames (a library function renamed in a given release, for example) is an external fact: state
it, with a version or date per § Dated Stamps.

Three things are allowed:

- **Present-tense reasons.** "`run_with_capture.sh` refuses a plain `cp` of a logged script
  because the copy carries the log marker."
- **The data's own history.** Data-source skills record schema and coding changes across survey
  years (for example `.claude/skills/education-data-source-ccd/references/historical-changes.md`).
  That is a current fact about the data, not about DAAF.
- **A short "recognizing older forms" note** where agents will meet legacy material in a user's
  files, fenced as a note and phrased as what to do:

  ```markdown
  > **Recognizing older forms.** Some projects keep scratch files in a root-level `scratch/`
  > folder. Treat it as project scratch and graduate cited files the same way.
  ```

A change story is never allowed, in any file outside § Exemptions.

**Why.** A reader of this release needs to know how it works, not how it used to. Time-relative
words go stale silently and assume the reader knew an earlier version
([Google: Timeless documentation](https://developers.google.com/style/timeless-documentation)).

| Don't | Do |
|-------|----|
| "The Scope Check (formerly Scope Review) was changed to run after reading the user's materials." | "The Scope Check runs after the materials the user pointed to are read, so the approved scope rests on them." |
| "These new subcommands let you check retractions." | "These subcommands check retractions." |

### S6 Comments Earn Their Place

**Rule.** A comment says what a block is for and why it is done this way. It does not restate each
line or narrate the code's history. A note about a past bug stays only while the constraint it
guards still holds, and is phrased as that constraint. Research scripts follow
`agent_reference/INLINE_AUDIT_TRAIL.md` unchanged.

**Why.** The code shows what it does. A comment carries what the code cannot: the purpose and the
reasoning behind a choice. History in a comment goes stale and hides the reason that still matters
([Google eng-practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)).

Don't:

```bash
# Loop over the files. We used ls here until the March bug (commit abc1234), then switched.
for f in "$DIR"/*.sh; do
```

Do:

```bash
# Glob, not ls: file names may contain spaces or newlines.
for f in "$DIR"/*.sh; do
```

### S7 Reachable by an End User

**Rule.** Anything a document, skill or workflow tells a user or an agent to do works on a standard
installation configured with the repository's own documentation. A requirement beyond that (the
`DAAF_DEV=1` image, a paid account, an API key) is named as a requirement, with how to meet it.
Never point to a script or file that does not ship.

**Why.** A step that only works on the maintainer's machine fails for every user, usually at the
point where they need it. Name what a step requires before the reader starts it.

| Don't | Do |
|-------|----|
| "Run the shell test suite to check the scripts." | "Run the shell test suite (`bats tests/bash/`). It needs the `DAAF_DEV=1` image: see `user_reference/01_installation_and_quickstart.md`, "Building with the developer test toolchain (DAAF_DEV)"." |

An author who finds a dependency that end users cannot reach reports it to the maintainer instead
of documenting around it.

---

## Dated Stamps

**Stamp only facts that change outside DAAF's own versioning:** model names and limits, Claude Code
version behavior, vendor APIs and pricing, external documentation. DAAF does not control these, so
the reader needs to know when the fact was true.

**Form:** "(observed YYYY-MM-DD, Claude Code 2.1.281)" or "verified against <source> on
YYYY-MM-DD". Name the external thing in the stamp, and add no backstory around it.

**Claims about DAAF's own behavior carry no stamp.** Each release is internally consistent: the
documentation describes the code it ships with.

| Don't | Do |
|-------|----|
| "`run_with_capture.sh` exits 74 on an incomplete record (verified 2026-10-05)." | "`run_with_capture.sh` exits 74 when the audit record is incomplete." |
| "An earlier probe reported a lower limit; that figure is superseded by the probe below, which ..." | "The ChatGPT-subscription lane caps context at 919,000 tokens (observed 2026-09-05, `gpt-6-astra` and `gpt-5.6-sol`)." |
| "Claude Code rejects the Write." (no stamp on a vendor behavior) | "Claude Code rejects the Write for subagents (observed 2026-10-19, Claude Code 2.1.281)." |

**Before removing a stamp, re-verify the claim against the current code or source.** Removing a
stamp turns a dated observation into a present-tense claim. If the claim does not hold, fix the
claim; if it cannot be checked, keep the stamp or label the claim as unverified.

---

## Exemptions

| Item | What is exempt | What still applies |
|------|----------------|--------------------|
| `CHANGELOG.md` and release notes | S5: history is their content | S1, S4. Write entries for users: what changed and what it means for them |
| Research-project records: `STATE.md`, `LEARNINGS.md`, `SESSION_NOTES.md`, a project's notes and reviews | The whole standard: they record what happened | The templates that produce them are in scope |
| Execution logs, and scripts with an appended execution log | Everything. They are immutable audit records: never edit them. The triage lint allowlists them | Nothing |
| Quoted error text, vendor text and example output | S2, S3, S5 inside the quotation: it is quoted verbatim | S1: quote accurately and say where it came from |
| Data-source history (schema and coding changes across collection years) | S5 | S1 to S4, S6, S7 |
| A fenced "recognizing older forms" note (S5) | S5, for that note only | Everything else |
| Research-script comments | S6 is replaced by `agent_reference/INLINE_AUDIT_TRAIL.md` | S1, S4 |

---

## Checklists

**Author checklist.** Before returning new or changed text:

- [ ] I named the audience of each file I changed (§ Audiences) and wrote to it.
- [ ] Every claim about DAAF behavior was checked against the file that implements it; counts and
  lists come from the repository, not memory.
- [ ] User-facing text names no internal codes; any code the user sees is explained where it
  appears; each passage passes the audience test.
- [ ] Every path I cite is shipped (`git ls-files` prints it, or it is new in this change) or is a
  public URL. A development finding I needed is stated in a sentence, not cited.
- [ ] The text describes this release: no change narration, no time-relative words; reasons are in
  the present tense; history went to `CHANGELOG.md`.
- [ ] Comments say what a block is for and why, with no history.
- [ ] Stamps appear only on external facts, in the standard form; any stamp I removed was
  re-verified first.
- [ ] Any requirement beyond a standard installation is named, with how to meet it.

**Reviewer checklist.** When reviewing changed text:

- [ ] Ran the triage lint on the change (§ The Triage Lint) and quoted its summary; each hit in a
  changed file is fixed or justified.
- [ ] Checked the load-bearing behavior claims against the files that implement them.
- [ ] Read each user-facing passage as a researcher who just installed DAAF (the audience test).
- [ ] Judged the text against this standard, not against neighboring text. A neighbor that breaks
  the standard is reported, not used as the reason to accept a match.
- [ ] Every cited path resolves in the shipped tree.
- [ ] No history narration outside § Exemptions.
- [ ] Mixed-audience messages open with a plain sentence a user can act on.
- [ ] Each removed stamp has re-verification evidence in the author's return.

---

## The Triage Lint

`tests/lint/docs-triage.sh` finds the machine-checkable patterns this standard rules out. It is a
review queue, not a gate: every hit needs a human judgment, and many are legitimate.

```bash
bash /daaf/tests/lint/docs-triage.sh
```

It scans the shipped set (tracked files, minus `research/`, the changelogs and `*.jsonl`), prints
a count summary first, then the hits grouped by review priority (§ Audiences), family and file,
as `file:line:text`.

| Family | Finds | Standard |
|--------|-------|----------|
| **A** | Unshipped references: `research/` workspace paths, tools that exist only on a maintainer's machine, text that labels itself as for the maintainer only | S4, S7 |
| **B** | History wording (strong combined patterns only) in `*.md`, `*.txt` and `*.cff` files outside `tests/` | S5 |
| **C** | Dated stamps with no external-context token on the line, in the tier 1 and 2 files and `agent_reference/`. Skills, agents and hooks are not date-scanned: check stamps there by hand | § Dated Stamps |
| **D** | Internal codes in user-facing files (`README.md`, `user_reference/`, `scripts/host/`, the report, plan and session-state templates, `agent_reference/AI_DISCLOSURE_REFERENCE.md`) | S3 |
| **E** | Paths hidden by `.git/info/exclude`. It needs a maintainer checkout and is skipped with a note when that file is absent, as in CI | S4 |

**Options:**

- `--family A,E` limits the scan to the listed families. `--family '*'` scans all of them, the
  same as giving no `--family`.
- `--tier 1,2` limits output to the listed review-priority tiers (§ Audiences > Review priority).
- `--format tsv` prints tab-separated rows for sorting or comparing runs.
- `--untracked` also scans new files that are not yet staged, so a change can be checked before
  it is committed.
- `--strict` exits 1 on any hit in family A or E that is not allowlisted. It counts only hits
  inside the `--tier` filter, so a strict release check runs without `--tier`. Without `--strict` the lint
  exits 0 whenever the scan completes, whatever it finds; it exits 2 only when it cannot run (bad
  arguments, not a git work tree).

The lint has no file arguments. To check a change, run it with `--untracked` and read the hits in
the files you changed.

**Allowlist.** A hit that is correct as written goes in `tests/lint/docs-triage-allowlist.tsv`, one
row per exception, with four tab-separated columns:

| Column | Holds |
|--------|-------|
| `path_glob` | The file or files, as a glob (`*` matches across `/`) |
| `family` | A family letter, a comma list (`A,E`), or `*` for all families |
| `fragment` | Text the hit must contain, or `*` for every hit of that family in the matched files |
| `reason` | Why the hit is correct as written |

Keep entries narrow: a fragment rather than `*` wherever one will do. On a run without a
`--family` filter, the lint reports allowlist entries that match nothing, so remove those when it
names them.
