# AI Use Disclosure Reference

This document provides framework-wide guidance for attributing and disclosing AI use in all work produced with DAAF. It follows the **GUIDE-LLM** reporting checklist (Feuerriegel et al., 2026, *Nature Human Behaviour*), a consensus-based standard for transparent AI use in behavioral and social science research.

**Loading trigger:** Referenced by the report-writer agent (Stage 11) and available to all modes that produce user-facing deliverables.

---

## Why Disclosure Matters

DAAF's architecture already captures a rich audit trail — immutable scripts, inline audit trail (IAT) comments, QA checkpoint logs, session archives. But this internal record is legible only to someone with access to the project repository. **AI use disclosure translates DAAF's audit trail into a form that external audiences — journal reviewers, funders, collaborators, and the public — can evaluate.** As AI use disclosure norms and requirements continue to evolve rapidly across journals, funders, and institutions, having a structured disclosure process ensures DAAF-produced work meets these emerging standards.

---

## GUIDE-LLM Checklist: DAAF Mapping

The table below maps each GUIDE-LLM core item to its DAAF artifact source and indicates whether the report-writer agent can auto-populate it (`[AUTO]`) or whether the researcher must provide the content (`[RESEARCHER]`). In both tables below, the item names and descriptions are GUIDE-LLM's own wording, from https://llm-checklist.com/checklist/ (accessed 2026-10-06); the DAAF Source, DAAF Advantage, and Populated By columns are DAAF's mapping and additions, not checklist text.

### Core Items

| GUIDE-LLM Item | Description | DAAF Source | Populated By |
|---|---|---|---|
| **A.1** | LLMs were used in this project for … | Plan.md (research question + methodology) | `[AUTO]` — report-writer derives from Plan.md |
| **A.2** | Human-in-the-loop vs. fully automated | DAAF architecture (checkpoint gates) | `[AUTO]` — always "Human-in-the-loop" for Full Pipeline |
| **B.1** | Model name, provider, size, version/ID, date of access, source link | STATE.md Session Metadata (model IDs, session dates, Provider Route) | `[AUTO]` — orchestrator provides session model ID, specialist (subagent) model IDs, and session date(s); the provider is the company that served the models on the recorded Provider Route (see "Provider Route" below and "Multi-Model Sessions") |
| **B.2** | API/web/local access; chat vs. separate call mode | STATE.md Session Metadata (Provider Route) + DAAF architecture | `[AUTO]` — "Claude Code command-line tool, run locally in DAAF's container and connected through [the Provider Route]"; Claude Code is agentic, making many separate model calls per task |
| **B.3** | Relevant parameters (temperature, max tokens, seed, runs) | STATE.md Session Metadata (Model Settings) | `[AUTO]` — "Claude Code's defaults, except [the recorded Model Settings, in plain words]. DAAF sets no temperature, output-length or random-seed values." What reaches the model depends on the route (see "Determining the Provider Route" below): `effortLevel` on Anthropic routes, the provider shim's own settings on the shim routes. When Model Settings is empty or reads "[Not recorded]", write "[Not recorded: the researcher should state the model settings used, such as reasoning effort]". Add any model setting the researcher changed if STATE.md records one |
| **B.4** | Describe any fine-tuning or customization | DAAF framework files | `[AUTO]` — reference to DAAF skills, agents, and system instructions |
| **B.5** | Whether the LLM session retained state across interactions | STATE.md + session archives | `[AUTO]` — "Stateful within sessions; STATE.md tracks cross-session continuity" |
| **C.1** | Exact prompt(s) reported | Agent `.md` files, skill files | `[AUTO]` — reference to version-controlled prompt files in DAAF repository |
| **C.2** | System-wide instructions (if any) | CLAUDE.md | `[AUTO]` — reference to CLAUDE.md in repository |
| **D.1** | Handling of personal/sensitive data | Safety guardrails in CLAUDE.md | `[RESEARCHER]` — researcher must confirm what data was processed and any PII considerations |
| **E.1** | Human validation of LLM outputs | User checkpoints (STATE.md § Pre-Flight Scope Check and the user-checkpoint rows in § Key Decisions Made) + QA summary | `[AUTO]` — what the researcher approved or changed at each checkpoint, named by activity; the QA summary supports the separate automated-review line. Never derive human validation from the CP1-CP4 verdicts in STATE.md § Checkpoint Status: those are automated validation, not human review |
| **E.2** | Any filtering, reformatting, or other post-processing | Script execution logs | `[RESEARCHER]` — researcher documents any manual edits made to AI-generated outputs after delivery |
| **F.1** | Code/notebooks/scripts for LLM calls shared | Marimo notebook (or Quarto notebook for R) + `scripts/` archive | `[AUTO]` — file paths from project structure |
| **G.1** | Funding, support, or relevant relationships | N/A — external to DAAF | `[RESEARCHER]` — researcher must disclose funding sources and any relevant relationships. DAAF addition (not GUIDE-LLM item text): also disclose API costs; the nearest GUIDE-LLM item is the optional "Computational resources" |

### Optional Items

| GUIDE-LLM Optional Item | DAAF Advantage | Populated By |
|---|---|---|
| Justification for LLM choice | DAAF framework selection rationale | `[RESEARCHER]` — why DAAF/Claude was chosen over alternatives |
| Rationale for prompt design | Agent `.md` files document behavioral protocols; skills document domain knowledge injection | `[AUTO]` — reference to agent and skill architecture |
| Comparison against other methods/LLMs | Not captured by default | `[RESEARCHER]` — if applicable |
| Training data leakage risks addressed | Mitigated by data-driven validation (assert statements, QA checkpoints) | `[RESEARCHER]` — assess for specific analysis context |
| Risk of bias or systematic differences affecting conclusions | LEARNINGS.md + Limitations section | `[AUTO]` partial — LEARNINGS.md entries; `[RESEARCHER]` for interpretation |
| Conversation transcripts | Session archives via `archive-session.sh` | `[AUTO]` — reference to archived session transcripts |
| Ethical implications of the research | Not captured by default | `[RESEARCHER]` — if applicable |
| Computational resources | Session logs (duration, token usage) | `[AUTO]` partial — available from session archives |

---

## DAAF Version and Session Metadata

Every disclosure should include version and temporal metadata to support reproducibility:

| Metadata Item | Source | How to Capture |
|---|---|---|
| **Date of analysis** | Session date(s) from STATE.md or orchestrator | Report-writer uses the date prefix (e.g., "2026-02-11") provided by orchestrator |
| **DAAF version** | Git commit hash of the DAAF repository at time of analysis | Orchestrator captures via `git rev-parse --short HEAD` at project setup and provides to report-writer |
| **Session model ID** | Model driving the orchestrator/main session | From session metadata — record the model ID actually in use at session start, not a hardcoded example (e.g., "claude-opus-4-8[1m]") |
| **Specialist model IDs** | Models driving subagent (specialist) dispatches | From STATE.md Session Metadata (Subagent Model Tiers). Record the distinct opus-tier and sonnet-tier model IDs actually used — see "Multi-Model Sessions" below |
| **Provider Route** | How Claude Code reached its models | From STATE.md Session Metadata (Provider Route). In modes without STATE.md, the orchestrator supplies it. See "Provider Route" below |
| **Model Settings** | Settings that change how the models answer, such as reasoning effort | From STATE.md Session Metadata (Model Settings), recorded with the route. See § Determining the Provider Route |
| **Session transcript** | Archived session log | Project-local copies in `logs/` (collected at completion via `collect_session_logs.sh`); global archives in `.claude/logs/sessions/`. Flag for researcher: *"Your full session transcripts have been collected into your project folder and can be included as supplementary material per GUIDE-LLM optional item on conversation transcripts"* |

### Provider Route

GUIDE-LLM B.1 asks for the provider and B.2 for the access method, and both depend on how the user's installation reaches its models. Write them from the recorded Provider Route, never from a default:

| Provider Route (as recorded) | Provider (B.1) | Access method (B.2) |
|---|---|---|
| Anthropic subscription | Anthropic | Claude Code command-line tool in DAAF's container, signed in with an Anthropic subscription |
| Anthropic API key | Anthropic | Claude Code command-line tool in DAAF's container, using the Anthropic API |
| OpenAI API via DAAF provider shim | OpenAI | Claude Code command-line tool in DAAF's container, using the OpenAI API through DAAF's provider shim |
| ChatGPT subscription via DAAF provider shim | OpenAI | Claude Code command-line tool in DAAF's container, signed in with a ChatGPT subscription through DAAF's provider shim |
| OpenRouter | OpenRouter, plus the maker of each model used | Claude Code command-line tool in DAAF's container, using the OpenRouter API |
| AWS Bedrock | Amazon Web Services (models by their maker, e.g. Anthropic) | Claude Code command-line tool in DAAF's container, using AWS Bedrock |
| Google Vertex AI | Google Cloud (models by their maker, e.g. Anthropic) | Claude Code command-line tool in DAAF's container, using Google Vertex AI |

When no route was recorded, write "[Not recorded: the researcher should state how DAAF connected to its models]" rather than guessing. How the orchestrator finds the route is in § Determining the Provider Route below.

### Multi-Model Sessions

DAAF dispatches subagents under a two-tier model-routing convention (documented in `.claude/skills/daaf-orchestrator/SKILL.md` > "Model Selection for Subagent Dispatch"). A single analysis session can therefore involve up to three distinct models: the **session model** (orchestrator), an **opus-tier specialist model**, and a **sonnet-tier specialist model**. Disclosures should list all distinct models actually used — the session model plus each specialist tier that was dispatched — not a single "Model ID".

Record **resolved** model IDs (e.g., `claude-opus-4-8[1m]`) when known. The `opus`/`sonnet` values in agent frontmatter are aliases that resolve per provider and drift over time, so when a resolved ID is unavailable, record the alias plus the session date so the resolution can be reconstructed. Note the alt-provider case: users may remap Claude Code's tier aliases via the `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL` env vars (DAAF's alternative-provider guidance sets these alongside `ANTHROPIC_DEFAULT_FABLE_MODEL` / `ANTHROPIC_DEFAULT_HAIKU_MODEL`, which no DAAF agent uses; all four names appear in the Claude Code 2.1.281 executable, observed 2026-11-02), in which case specialist models may not be Claude models at all and should be disclosed as whatever provider/model actually served the tier. DAAF's shipped session default is the `opus` alias (`ANTHROPIC_DEFAULT_MODEL=opus` in `.claude/settings.json`), so the OPUS remap should set the session model too (inferred from Claude Code's alias resolution, not tested on every route; `/status` shows the model in use). Record the session model ID actually in use, not the alias. Claude Code's own housekeeping calls (naming the session, summarizing it for `--resume`) use the HAIKU alias: a Haiku model on an Anthropic route, or the model `ANTHROPIC_DEFAULT_HAIKU_MODEL` names on another route (unverified: not checked against Claude Code's documentation). They produce no research content, but list that model too when disclosing the full set of models a session used.

**Note on session transcripts:** DAAF automatically archives full session transcripts via the `archive-session.sh` hook. These transcripts are a powerful differentiator — most AI-assisted research cannot point to a complete record of the human-AI interaction. Researchers are encouraged to include these as supplementary material when submitting to journals, as they provide unparalleled transparency into the AI-assisted research process.

---

## Determining the Provider Route

The orchestrator fills STATE.md § Session Metadata > Provider Route and > Model Settings when it creates STATE.md. Reproducibility Verification fills the Provider Route in the Reproduction Report's Reproduction Environment table the same way, and a mode without STATE.md uses this section when its disclosure needs the route. The values come from the container's settings, which Docker Compose loads from the user's `environment_settings.txt` (template: `scripts/host/environment_settings_example.txt`). Read only settings that hold no secret, and check a credential for presence only, never its value (CLAUDE.md § Credential & Secret Protection). Run each command as its own Bash call:

1. **Switches:** `echo "shim=${DAAF_PROVIDER_SHIM:-} backend=${SHIM_BACKEND_MODE:-} gateway=${SHIM_BACKEND_BASE_URL:-} effort=${SHIM_REASONING_EFFORT:-} verbosity=${SHIM_TEXT_VERBOSITY:-} bedrock=${CLAUDE_CODE_USE_BEDROCK:-} vertex=${CLAUDE_CODE_USE_VERTEX:-} base_url=${ANTHROPIC_BASE_URL:-}"`. None of these holds a credential.
2. **Credentials, by length only:** `echo "apikey_len=${#ANTHROPIC_API_KEY} oauth_len=${#CLAUDE_CODE_OAUTH_TOKEN}"`. A length above 0 means the credential is set. Use the length rather than the presence test `[ -n "${ANTHROPIC_API_KEY:+set}" ]`: that test answers only through its exit status, and the Bash tool showed the same empty result for a set and an unset variable (observed on Claude Code 2.1.281, 2026-11-02). Never echo a credential-named variable itself; `bash-safety.sh` blocks it.

**Decision order.** The first row that matches wins. The order follows Claude Code's credential priority as the settings template lists it in § [2]: a cloud platform, then a gateway token (OpenRouter's or the shim's), then an Anthropic API key, then a subscription token, then an interactive sign-in.

| Order | What the commands show | Provider Route |
|---|---|---|
| 1 | `bedrock=1` | AWS Bedrock |
| 2 | `vertex=1` | Google Vertex AI |
| 3 | `shim=openai`, `base_url` pointing to the local shim (`http://127.0.0.1:4141` as shipped), and `backend=chatgpt` (any letter case) | ChatGPT subscription via DAAF provider shim |
| 4 | `shim=openai` and `base_url` pointing to the local shim, with `backend` empty or any other value (the shim then uses its OpenAI API lane) | OpenAI API via DAAF provider shim |
| 5 | `base_url` on `openrouter.ai` | OpenRouter |
| 6 | Any other value in the fields of rows 1-5: another `bedrock` or `vertex` value, a `base_url` pointing anywhere else, or `shim` set while `base_url` does not point to the shim | None of the listed routes: ask the user |
| 7 | `apikey_len` above 0 | Anthropic API key |
| 8 | `oauth_len` above 0 | Anthropic subscription (the token comes from `claude setup-token`, which serves a subscription) |
| 9 | Nothing above | Ask the user: a Claude subscription and an Anthropic Console account both sign in interactively, and settings cannot tell them apart |

On row 4, a `gateway` value other than empty or `https://api.openai.com/v1` means the shim sends its requests to another OpenAI-compatible service, such as an institutional gateway (settings template § 4.5). Record the route followed by "(gateway: [host])"; the disclosure then names that gateway's operator as the provider.

**Asking the user (rows 6 and 9).** Ask once, inside the next message that already asks the user something, rather than as a separate interruption. Row 9: "Is DAAF signed in with a Claude subscription (Pro, Max, Team or Enterprise) or with an Anthropic Console account that pays per use?" Record a subscription as Anthropic subscription and a Console account as Anthropic API key. Row 6: "How does DAAF connect to its AI models here: through OpenRouter, an OpenAI account, a company or university service, or a cloud platform such as AWS or Google Cloud?" Leave the field empty until the user answers; if they cannot say, leave it empty, and the disclosure asks the researcher.

**Model Settings, by route.** Record the settings that reach the model on the recorded route:

| Provider Route | Model Settings to record | Where the value comes from |
|---|---|---|
| Anthropic subscription, Anthropic API key | "reasoning effort [value]" | `grep -n '"effortLevel"' /daaf/.claude/settings.json` (`high` as shipped) |
| ChatGPT subscription or OpenAI API via DAAF provider shim | The shim's reasoning effort for each model tier and its response verbosity, e.g. "provider shim: reasoning effort medium for the sonnet tier (`#medium` suffix), high otherwise (shim default); response verbosity medium (shim default)" | Effort for each model: the `#<effort>` suffix on the model's name, else `effort` from command 1, else `high`. Verbosity: `verbosity` from command 1, else `medium`. The model names, with any suffix: `echo "opus_model=${ANTHROPIC_DEFAULT_OPUS_MODEL:-} sonnet_model=${ANTHROPIC_DEFAULT_SONNET_MODEL:-}"` |
| OpenRouter, AWS Bedrock, Google Vertex AI, or not known | "[Not recorded]" | DAAF has not checked which reasoning effort reaches the model on these routes |

On the shim routes `effortLevel` does not set the effort. Claude Code sends "high" for model names it does not recognize, and the shim treats that value as unset and applies its own order instead (settings template § 4.4, "REASONING-EFFORT CONTROL"; `_resolve_effort` in `scripts/provider_shim/anthropic_openai_shim.py`).

---

## Mode-Specific Disclosure Guidance

Different engagement modes involve different levels of AI assistance. The disclosure should match the depth of involvement.

### Full Pipeline Mode

**Depth:** Comprehensive. AI was involved in every stage from data acquisition to report generation.

**Template:** Use the full "AI Use Disclosure" section in REPORT_TEMPLATE.md. The report-writer agent auto-populates `[AUTO]` fields and removes the `[AUTO]` tags from the delivered report; the `[RESEARCHER]` fields keep their tags and prompts until the researcher completes them before publication.

**Key points to document:**
- AI generated all analysis code (data fetching, cleaning, transformation, analysis, visualization)
- All code underwent automated QA review by a separate AI instance (code-reviewer agent)
- Researcher approved the analysis scope at the pre-flight scope check (grounded in any materials they pointed to), then reviewed the data sources found, approved the analysis plan, checked the prepared data's quality, and confirmed the results before the report was written. Name each checkpoint by its activity, never by number (a number reads like the automated validation codes), and write what the researcher approved or changed from STATE.md § Pre-Flight Scope Check and the user-checkpoint rows in § Key Decisions Made
- All scripts, data files, and execution logs are archived for reproducibility

### Data Discovery Mode

**Depth:** Light. AI conducted read-only data exploration; no code was executed, no data was downloaded.

**Template:**
> This exploratory assessment was conducted using DAAF (Data Analyst Augmentation Framework) with [session model ID; and any specialist model IDs if subagents were dispatched] via Claude Code CLI on [date]. DAAF version: [commit hash]. The AI was used solely for read-only data landscape exploration — identifying available data sources, variables, and feasibility considerations. No analytical code was executed and no data was downloaded. The researcher reviewed and directed the exploration throughout. For the full GUIDE-LLM checklist, see the AI_DISCLOSURE_REFERENCE.md in the DAAF repository.

### Data Lookup Mode

**Depth:** Minimal. AI answered a specific factual question from structured documentation.

**Template:**
> AI assistance (DAAF with [session model ID], [date]) was used to look up [specific information] from [data source documentation]. The answer was verified against [source]. DAAF version: [commit hash].

### Revision and Extension Mode

**Depth:** Inherits from original, plus revision scope.

**Template:** Include the original analysis's disclosure, then append:
> **Revision conducted on [date]:** AI assistance was used to [describe revision scope — e.g., "modify the poverty threshold variable and re-run affected analysis stages"]. The same QA review process was applied to all re-executed code. DAAF version: [commit hash].

### Data Onboarding Mode

**Depth:** Moderate. AI profiled dataset structure and generated a reusable data source skill.

**Template:**
> Dataset profiling was conducted using DAAF (Data Analyst Augmentation Framework) with [session model ID, plus specialist model IDs for dispatched subagents — see STATE.md Session Metadata] via Claude Code CLI, connected through [Provider Route from STATE.md Session Metadata], on [date]. DAAF version: [commit hash]. [Standard path: The AI executed structured profiling scripts in four parts (structure, statistics, relationships, interpretation) to characterize the dataset. All profiling scripts underwent automated QA review. / Synthetic path: omit these two sentences; the addition below describes the profiling.] The researcher confirmed the setup scope before profiling and reviewed the profiling findings before the data source skill was finalized. All profiling scripts and execution logs are archived in the project's `scripts/` directory.

**Synthetic Data Path (sensitivity gate):** When onboarding takes the privacy-preserving synthetic-data path — the raw data never entered the container, and DAAF worked only from a user-produced, disclosure-controlled profile report — the disclosure MUST additionally state the synthetic provenance, the disclosure tier, and the finalize-against-real-data requirement. Any deliverable derived from the synthetic data (a data source skill, a report, an analysis output) carries this disclosure. This also satisfies GUIDE-LLM item **D.1** (handling of personal/sensitive data): the raw sensitive data was never transmitted to the model. See the `synthetic-data-workflow` skill.

**Template addition (append to the Data Onboarding paragraph when the synthetic path was used):**
> The source data was sensitive and never entered the DAAF container. Profiling was performed by the researcher locally using a DAAF-provided, disclosure-controlled script at **Tier [N] ([Schema / Marginals / Relationships / Local high-fidelity synthesis])**; only a summary profile report crossed the boundary. DAAF generated a **synthetic** dataset and data source skill from that report alone (generation seed [seed]). This synthetic data is a code-development scaffold, not an analytic substitute — **all findings must be finalized by running the vetted analysis code against the real data in the environment where it lives.** No raw sensitive data or personally identifiable information was transmitted to the AI model.

### Reproducibility Verification Mode

**Disclosure depth:** Moderate

**Where it goes:** the Reproduction Report's `## AI Use Disclosure` section (`agent_reference/REPRODUCTION_REPORT_TEMPLATE.md`), written by the report-writer at RV-4 from the template paragraph below, with the reproduction's models and Provider Route from the Report's Reproduction Environment table.

**Key points to disclose:**
- AI performed notebook decompilation, a check that no script still pointed at the original project's folders, mechanical re-execution of in-scope scripts, and direct artifact comparison; it distinguished log metrics, supported artifact evidence, visual figure review, and evidence that remained NOT DIRECTLY VERIFIED
- The data strategy: re-fetch (the original data-download scripts were re-run) or frozen inputs (the data-download scripts were excluded by the user's choice, raw-file hashes verified, data download and mirrors not tested)
- AI performed methodological review at the user-selected depth and claim verification across Report claims, figures, findings, artifacts, and required dimensions
- The model/runtime provenance actually observed for the orchestrator, specialists, language runtime, notebook tool, and imported packages, with unknown versions identified rather than inferred
- Any exact scope exclusions the user approved before re-running began, kept separate from evidence gaps and ad hoc skips
- That the researcher reviewed the final Reproduction Report, exercised judgment about the significance of all findings, deviations, and evidence limitations, and remained responsible for the final verdict. The report-writer writes this disclosure as the reproduction's last step, before the researcher has read the report, so this sentence carries a `[RESEARCHER]` tag for the researcher to confirm, never a statement made for them

**Template paragraph:**
> This reproduction was conducted using DAAF's Reproducibility Verification mode with [session model ID, plus the specialist model IDs dispatched] via Claude Code CLI, connected through [Provider Route], on [date(s)]. DAAF version: [commit hash]. An AI agent decompiled the delivered [Marimo/Quarto] notebook, which archives the executed analysis scripts, checked that no script still pointed at the original project's folders, and re-executed [N] in-scope scripts. [Data strategy: the original data-download scripts were re-run / frozen raw inputs were hash-verified and the data-download scripts were excluded by the user's choice, so data download and mirrors were not tested.] Log comparison was limited to metrics printed in both logs; supported Parquet or exact-byte artifacts were compared directly, figures were visually reviewed, and unsupported or missing evidence was labeled NOT DIRECTLY VERIFIED. The AI performed artifact comparison, methodological review, and claim verification against reproduced evidence, and recorded model/runtime provenance with unknown versions left explicit. `[RESEARCHER]` [Confirm after reading this report, then remove the tag: "The human researcher reviewed the Reproduction Report, applied judgment to deviations, scope exclusions, methodological concerns, provenance, and evidence gaps, and remained responsible for the final verdict of [FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED]."]

### Literature Review Mode

**Depth:** Moderate to comprehensive, scaling with the review level (quick scan, standard review, formal systematic review).

**Where it goes:** the deliverable's Methods section carries the disclosure (the literature-synthesizer writes it from the dispatch and the review's tables), and the final check-in summarizes it for the researcher in plain words. Literature reviews follow the RAISE guidance on AI in evidence synthesis (`literature-review` skill, `formal-review.md` § Reporting): state what AI judged or drafted, what code checked, and that the researcher made every judgment call and remains responsible for the review.

**Key points to disclose:**
- **What AI did:** ran the searches and citation-following, drafted screening decisions (title and abstract; full text at the formal level), read papers and wrote reading notes, drafted checklist answers and a weight per paper, and drafted every synthesis and memo
- **What code checked, not AI:** every search is saved with its exact wording and results; every reference was looked up in a database and checked for retraction, and each cited one was confirmed against its record; every quote and number was found on the PDF page it cites; the wording of each conclusion matches its stated certainty; no results were pooled or averaged across studies
- **How each reference was confirmed**, using the deliverable's own labels: "you confirmed it" (the researcher's reference glance), "accepted by you" (the researcher kept a reference whose record did not match, or reversed the second check, with a recorded reason), and, only once an evaluated adjudicator exists, "confirmed by DAAF's second check (an AI judgment)"
- **Numbers read from pictures of pages:** whether any were used, the model that read them, and that each was confirmed by the reading audit or compared with the page by the researcher
- **What the researcher decided:** the review plan and each change to it, the papers read in full (or every full-text inclusion and the checklist judgments, at the formal level), the certainty ratings at the formal level, the reference replies and page comparisons, all recorded in their own words
- **Where AI stood in for a person:** an AI second screener at the formal level is a declared protocol deviation; a quick scan states that it had no second screener and rates no certainty
- **Models:** the session model plus each specialist model dispatched (search, reading, writing; see "Multi-Model Sessions" above)

**Template paragraph:**
> This [quick scan / literature review / systematic review] was conducted using DAAF's Literature Review mode with [session model ID, plus the specialist model IDs for searching, reading and writing] via Claude Code CLI on [date(s)]. DAAF version: [commit hash]. AI ran the searches, [drafted screening decisions,] [read [n] papers in full and wrote page-checked reading notes,] and drafted the synthesis. Code, not AI, checked that every reference matches a database record and has no retraction notice, that every quote and number appears on the page it cites, and that each conclusion's wording matches its stated certainty; no results were pooled across studies. The researcher approved the review plan [and its [n] revisions], chose the papers read in full, [made every full-text inclusion, checklist judgment and certainty rating,] and confirmed each reference ([k] references accepted by the researcher despite the automatic check [, and [m] confirmed by DAAF's second check, an AI judgment]). The search record, screening log, reading notes and their checks are archived in the project folder; the researcher remains responsible for the review.

### User Support Mode

**Depth:** None — User Support produces no research artifacts, analysis outputs, or formal deliverables. All interaction is conversational guidance about DAAF itself.

**Guidance:** User Support conversations typically require no AI disclosure because they produce no publishable or shareable research output. If a User Support session leads to mode escalation (e.g., the user decides to start a Full Pipeline analysis), the escalated mode's disclosure guidance applies to the work produced in that mode — the preceding User Support conversation is not separately disclosable.

**Exception:** If a researcher cites specific guidance received during a User Support session in a methods section (e.g., "DAAF's orchestrator recommended using Data Onboarding mode before analysis"), a brief acknowledgment is sufficient:
> Methodological guidance was obtained through DAAF's User Support mode ([session model ID], [date]). DAAF version: [commit hash].

---

### Ad Hoc Collaboration Mode

**Depth:** Variable — depends on what the collaboration produced.

**Where it goes:** the session notes' `## AI Disclosure` section (`.claude/skills/daaf-orchestrator/references/ad-hoc-collaboration-mode.md` § Session Notes and Continuity > What SESSION_NOTES.md Contains), and the researcher's own methods text when they publish work the session contributed to. Use the templates below for both, so the model, date and version are recorded.

**Guidance:** Ad Hoc Collaboration ranges from quick methodological advice to substantive code writing, code review or analytical suggestions. The disclosure should scale accordingly:

- **Light collaboration** (methodological question, interpretation advice): Use the Data Lookup template adapted for the collaboration context.
- **Substantive collaboration** (code generation, analytical approach design, data interpretation): Use a template similar to:

> AI assistance (DAAF with [session model ID; and any specialist model IDs if subagents were dispatched], [date], version [commit hash]) was used for [specific purpose — e.g., "designing the regression specification" or "reviewing data cleaning logic"]. The researcher independently verified [what was verified] and takes responsibility for all final analytical decisions.

### Framework Development Mode

**Depth:** Minimal

**Template:**
> This [component type] was created/modified using DAAF (Data Analyst Augmentation Framework) in Framework Development mode. DAAF provided template guidance, integration checklist execution, and cross-file consistency verification. The framework developer directed all design decisions and reviewed all changes.

**Key points to document:**
- What framework components were created or modified
- That the human developer made all design decisions
- That canonical templates were followed

---

## Boilerplate: Methods Section Language

For researchers writing up DAAF-assisted work for publication, the following boilerplate can be adapted for a manuscript's methods section:

### Short Version (for methods sections with space constraints)

> Data analysis was conducted using the Data Analyst Augmentation Framework (DAAF; Kim, 2026), an open-source AI-assisted research orchestration system built on Claude Code (Anthropic), using [session model ID and its provider; list specialist model IDs too if subagents were dispatched]. DAAF enforces human-in-the-loop oversight through structured checkpoints, automated code review, and full audit trail preservation. All analysis code, data files, and AI interaction transcripts are archived for reproducibility. A completed GUIDE-LLM checklist (Feuerriegel et al., 2026) is included as supplementary material.

### Long Version (for detailed methods sections or supplementary materials)

> Data analysis was conducted using the Data Analyst Augmentation Framework (DAAF; Kim, 2026), an open-source AI-assisted research orchestration system built on Claude Code (Anthropic). DAAF structures the analysis pipeline into discrete phases — discovery, planning, data acquisition, analysis, and synthesis — with mandatory human review checkpoints between each phase. The AI generated all analysis code, which was then reviewed by a separate AI instance acting as an automated quality reviewer before the researcher's own review. The researcher approved the analysis scope before any data exploration began, then reviewed the data sources found, approved the analysis plan, checked the prepared data's quality, and confirmed the results before the report was written.
>
> The models used were [session model ID for the orchestrator, plus the specialist model IDs for each subagent tier dispatched — e.g., "claude-opus-4-8[1m] for the orchestrator and opus-tier specialists, claude-sonnet-4-5 for sonnet-tier specialists"; see the DAAF two-tier routing convention], accessed through the Claude Code command-line tool, connected through [the Provider Route, e.g. "an Anthropic subscription"], with Claude Code's default settings except [the recorded Model Settings, e.g. "reasoning effort, which DAAF sets to high", or "[Not recorded: the researcher should state the model settings used]"], on [date(s)]. DAAF version [commit hash] was used. [The data privacy statement the researcher confirmed in the report's Data Privacy field (GUIDE-LLM D.1).] The complete set of analysis scripts with execution logs, intermediate data files, a consolidated analytic notebook, and the full AI session transcript are available as supplementary materials. All AI prompts and system instructions are version-controlled in the DAAF repository. A completed GUIDE-LLM reporting checklist (Feuerriegel et al., 2026) is included as Supplementary Material [X].

---

## Journal-Specific Considerations

AI disclosure requirements vary across journals and are evolving rapidly. The following is general guidance, last checked on 2026-10-27 against Nature's live page and Wayback captures of the APA (2026-10-14) and PNAS (2026-07-31) policy pages (Science could not be fetched):

| Context | Typical Requirement | DAAF Coverage |
|---|---|---|
| **APA journals** | Disclose AI use in methods; AI cannot be listed as author | Full Pipeline disclosure section covers this; ensure researcher is sole author |
| **Nature portfolio** | Risk-tier policy: disclose AI use for transparency, and AI that influences methods or interpretation is permitted only with human oversight and disclosure; assigning authorship or accountability to AI is not permitted | Methods boilerplate + GUIDE-LLM checklist as supplement |
| **Science** | Disclose AI use; no AI authorship (not re-verified: science.org blocks automated fetches; confirm on the live page) | Methods boilerplate covers this |
| **PNAS** | Disclose AI use in methods | Methods boilerplate covers this |
| **Funder requirements** | Varies — increasingly requiring AI disclosure | DAAF judgment: a GUIDE-LLM checklist supplement is a reasonable default; confirm each funder's own rules |
| **Preprint servers** | Generally no strict requirement, but disclosure is best practice | Include at minimum the short methods boilerplate |

**General best practice:** Include the completed GUIDE-LLM checklist as supplementary material regardless of journal requirements. This future-proofs the submission against evolving standards and signals methodological rigor.

**Important:** Always check the specific submission guidelines of your target venue. Requirements are changing frequently. The guidance above reflects general trends and may not capture recent policy updates.

---

## GUIDE-LLM Citation

When referencing the GUIDE-LLM framework in publications, use:

> Feuerriegel, S., Barrie, C., Crockett, M. J., … Ribeiro, M. H. (2026). A reporting checklist for large language models in behavioural science. *Nature Human Behaviour*, 10(7), 1182–1186. https://doi.org/10.1038/s41562-026-02492-7

Checklist website: https://llm-checklist.com/ (accessed 2026-10-06).

---

## DAAF Citation

When citing DAAF in publications, use:

> Kim, B. H. (2026). *DAAF: The Data Analyst Augmentation Framework* (Version 3.1.0) [Computer software]. https://github.com/DAAF-Contribution-Community/daaf

**BibTeX:**

```bibtex
@software{kim2026daaf,
  author = {Kim, Brian Heseung},
  title = {{DAAF}: The Data Analyst Augmentation Framework},
  year = {2026},
  url = {https://github.com/DAAF-Contribution-Community/daaf},
  version = {3.1.0},
  license = {LGPL-3.0-or-later}
}
```

**Version note:** If the version in `CITATION.cff` at the DAAF repository root differs from the version shown above, use the version (and the year of its `date-released:` field) from `CITATION.cff`.

---

## Integration Points

This reference is consumed by:

| Consumer | How It's Used |
|---|---|
| **report-writer** (Stage 11) | Populates the "AI Use Disclosure" section of REPORT_TEMPLATE.md using `[AUTO]` field mappings |
| **Orchestrator** (all modes) | Provides mode-specific disclosure templates for non-pipeline outputs |
| **literature-synthesizer** (Literature Review) | Writes the deliverable's Methods-section disclosure per § Literature Review Mode |
| **Researcher** (post-delivery) | Completes `[RESEARCHER]` fields, adapts methods boilerplate for manuscripts, prepares GUIDE-LLM checklist as supplementary material |
