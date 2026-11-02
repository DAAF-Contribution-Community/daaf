# Data Lookup Mode

Data Lookup mode is for specific lookup questions — coded values, variable definitions, data source details, or quick factual answers. It invokes a single relevant skill and returns a direct answer.

## User Orientation

The mode confirmation already gave the user this preview, so do not repeat it after confirmation. Present these points only when the user signals they are new to DAAF or asks for more detail.

- A quick, focused answer to one specific question -- a coded value, a variable definition, a source detail
- I find the most relevant source reference, read what it says about your question, and answer from it, naming the source and any caveats that matter
- If you pointed me to something (a codebook page, a file, a link), I read it first
- If it turns out your question touches on something broader, I'll let you know and we can explore further

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## Scope Check

- **Tier:** None. A lookup is one focused answer, so there is no scope step: read, then answer.
- **Read first:** anything the user referenced (a codebook page, a file, a URL), before choosing the skill or answering. A web page goes through `web_fetch.sh` (the `web-retrieval` skill). A PDF goes to one `search-agent` digest, which can be the Simple Lookup dispatch itself (§ Invocation Template: Simple Lookup). A data file is described from what the user said and its listing (name, size, type) only; its rows are not read. Pass what you read to the lookup subagent in its `USER-REFERENCED MATERIALS` line.
- **Where reads land:** this mode never creates a project, so fetch artifacts, PDF ingests and any digest stay in the session's staging folder, `{scratchpad}/scope_staging/` (`SKILL.md` § Scope Check > Read First). The answer cites the URL or document title, never the staged path. If the session escalates to a mode that creates a project, they graduate there.
- **If reading widens the question:** the existing rules still hold. Do not run more than one skill or expand into exploration without asking (§ Boundaries); propose Data Discovery instead (§ Escalation Triggers).

The read-first rule and the tier table are in `SKILL.md` § Scope Check.

---

## Data Lookup Workflow

```
Stage 1: Classify as Data Lookup → Confirm with user
    ↓
Read anything the user referenced (§ Scope Check)
    ↓
Identify the single most relevant skill for the question
    ↓
Invoke skill via subagent (search-agent; lookup only)
    ↓
Return direct, focused answer to user
```

## Subagent Invocation

- Invoke **one** subagent with the relevant skill (e.g., `education-data-source-ccd` for a CCD variable question)
- Use the `search-agent` subagent type (`source-researcher` for a Deep Lookup, § Agent Selection); per this mode's scope the dispatch asks for an answer only (no code execution, no data downloads, and no files written outside the staging folder: only a referenced PDF's ingest or a fetch lands there, § Scope Check)
- **Always load `data-scientist`** in addition to the domain skill — it provides methodological rigor for interpreting results
- The subagent loads the skills, finds the answer, and returns it
- If the skill doesn't contain the answer, report that clearly rather than guessing

Review the skill inventory in the system message to identify the correct skill for the question.

### Agent Selection

Match the agent to question complexity:

| Question Type | Agent | Domain Skill | Example |
|--------------|-------|--------------|---------|
| Simple fact, definition, year coverage | `search-agent` (Simple Lookup) | Source or explorer | "What years does CCD cover?" |
| Coded values, suppression patterns, caveats | `source-researcher` (Deep Lookup) | Source (`*-data-source-*`) | "What are the suppression rules for CRDC discipline data?" |
| What data exists (narrow, single-source) | `search-agent` (Simple Lookup) | Explorer | "Does CCD include charter school flags?" |

> **Note:** Broad landscape questions ("What data exists about school poverty?") are better served by Data Discovery Mode. The Explorer row above is for narrow, source-specific existence checks where the user already knows which domain to look in.

**Default:** `search-agent` with the skill (the Simple Lookup template). Use `source-researcher` when the question requires structured investigation of caveats, coded values, or suppression patterns — the cases where its 5-section output contract adds value.

### Invocation Template: Simple Lookup (Default)

```python
Agent({
    description: "Data Lookup: [question summary]",
    prompt: """You are answering a specific data lookup question.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

## SKILL LOADING
Call the skill tool with name 'data-scientist'.
Then, call the skill tool with name '[skill-name-from-catalog]'.

If a skill fails to load, report the failure clearly and attempt to answer
from base knowledge. Flag reduced confidence due to the missing skill.

## QUESTION
{user's specific question}

USER-REFERENCED MATERIALS: {absolute paths of anything the user pointed to,
with one line on what each holds, or "none"}

[If a referenced PDF must be read: Load the pdf-reading skill and ingest the
PDF with pdf_ingest.sh into {scratchpad}/scope_staging/papers/ (absolute path),
the staging folder CLAUDE.md § Project Conventions > Scratch Files allows. Write
nothing else, and cite the paper by title, not by that path.]

If you fetch a web page, the web_fetch.sh DEST_DIR is
{scratchpad}/scope_staging/web_fetches/ (absolute path), never another folder;
cite the page by URL, not by its staged path.

## RESPONSE FORMAT
**Hard cap: 750 words.** Answer directly and concisely.

Provide:
- The specific values, definitions, or information requested
- Source attribution (which skill/documentation provided the answer)
- Any important caveats or limitations
- Confidence level (HIGH/MEDIUM/LOW) with brief rationale

If the question cannot be fully answered from the available skill, say so
clearly and suggest what additional exploration might help.""",
    subagent_type: "search-agent"
})
```

### Invocation Template: Deep Lookup (source-researcher)

Use when the question requires investigating caveats, coded values, or suppression patterns in depth.

```python
Agent({
    description: "Data Lookup: [question summary]",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

## SKILL LOADING
Call the skill tool with name 'data-scientist'.
Then, call the skill tool with name '{domain}-data-source-{source}'.

If a skill fails to load, STOP and report the failure (see STOP Conditions
in your agent protocol).

## CONTEXT
**Question:** {user's specific question}
**Source:** {source_name}
**Variables of interest:** {variables, if applicable}
**USER-REFERENCED MATERIALS:** {absolute paths of anything the user pointed to,
with one line on what each holds, or "none"}

## TASK
Answer the user's specific question using the source-researcher protocol.
Focus your investigation on the sections most relevant to the question —
you do not need to produce a complete 5-section report if the question
only touches one area (e.g., coded values only → focus on VARIABLES section).

## SCOPE (Data Lookup mode)
Answer from the skill, its references and any user-referenced materials
listed above only: no probe scripts, no data downloads, no files written.
Return the answer as text.

## RESPONSE FORMAT
**Hard cap: 750 words.** Return only the sections relevant to the question.

- The specific answer to the question
- Supporting detail from the relevant report section(s)
- Confidence level (HIGH/MEDIUM/LOW) with rationale
- Any caveats or warnings the user should know""",
    subagent_type: "source-researcher"
})
```

## Response Format

Provide a direct, actionable answer:

```
**[Variable/concept name]**

[Direct answer to the question]

**Source:** [Which skill/data source this comes from]

*If referencing in published work, see `agent_reference/AI_DISCLOSURE_REFERENCE.md` for disclosure guidance.*
```

Keep responses concise. The user asked a specific question — answer it specifically.

This is the Data Lookup instance of DAAF's Turn-End Briefing standard: lead with the answer, spend only the words that earn the user's attention, and attribute sources by name. For a single focused lookup the briefing essentially *is* the direct answer, so the standard mostly cautions against over-structuring a short reply. See the master statement in `SKILL.md` § User-Facing Communication Standards > "Turn-End Briefing."

## Boundaries

These boundaries supplement the universal safety boundaries in `CLAUDE.md`. The detailed execution boundaries in `agent_reference/BOUNDARIES.md` do not apply to Data Lookup mode (no code execution, no data transformations, no commits).

**Always Do:**
- Answer the specific question asked
- Keep response focused and concise
- Suggest Data Discovery Mode if broader exploration needed
- Provide direct, actionable information

**Never Do:**
- Execute multiple skills without confirmation
- Create Plan files or generate code
- Expand into full data discovery without confirmation
- Assume Full Pipeline is needed from a single question

## Escalation Triggers

**To Data Discovery Mode** — when the question reveals broader data exploration is needed:
> "This question touches on broader data exploration. Would you like me to switch to Data Discovery Mode?"

**To Full Pipeline** — when the lookup reveals an actionable analysis opportunity:
> "This lookup suggests an interesting analysis could be done. Would you like me to explore this further?"

Wait for explicit user confirmation before switching modes.
