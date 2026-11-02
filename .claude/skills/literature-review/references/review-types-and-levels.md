# Review Types and Levels

How to set up a review: which type answers the researcher's question, which
level fits their time and purpose, how the two combine, and what has to be
fixed before the first search. Researcher-facing passages (the level menu in
SKILL.md, the quick-scan and standard-review questions in § Questions to ask,
by level) are written to be shown as they stand.

## Contents

- [Two choices, made together](#two-choices-made-together)
- [The levels in depth](#the-levels-in-depth)
- [Review types](#review-types)
- [The intent menu](#the-intent-menu)
- [How type and level combine](#how-type-and-level-combine)
- [Questions to ask, by level](#questions-to-ask-by-level)
- [Question frames](#question-frames)
- [Stopping rules](#stopping-rules)
- [Reporting standards by level](#reporting-standards-by-level)
- [Changing level or re-steering](#changing-level-or-re-steering)
- [Sources](#sources)

## Two choices, made together

The researcher makes two choices at the start:

1. **The review type** decides what question is answered and how the evidence is
   put together (a scoping review charts a field; a systematic review answers a
   focused question; a realist review explains mechanisms).
2. **The level** decides how deep DAAF goes: abstracts only, full reads of key
   papers, or a researcher-led formal process. Machine field `review_level`:
   `quick`, `standard` (default), `formal`.

Say plainly to the researcher that the type decides almost everything else, and
that they can re-steer at every round checkpoint. This mirrors the rapid-review
family, where "the defining feature is the dialogue between client and review
team" and "any modifications… must be explicitly declared" (Sutton et al. 2019).

## The levels in depth

The level menu shown to the researcher is in SKILL.md § The level menu. This
section adds what each level produces and costs, so an agent can answer
follow-up questions.

| | Quick scan | Standard review | Formal / systematic |
|---|---|---|---|
| What is read | Titles and abstracts | Full text of the key papers, one reader per paper | Full text of every included paper |
| Claims | From abstracts, labelled "per abstract" | Page-checked quotes and numbers (`lit_verify card`) | Same |
| Per-paper record | None | Design, quoted limitations, a stated weight with reasons (`paper-notes.md`) | The same, plus checklist answers with quotes, filled in with the researcher (`formal-review.md`) |
| Screening | One pass, decisions recorded | One pass; a second screener optional and recorded | Written protocol; a second person decides on every full text, recorded; the researcher resolves disagreements |
| Findings | Optional; "certainty not rated: abstracts only" | Stated certainty with a written reason | The researcher's GRADE-style rating, with notes per domain |
| Output | Short memo with verified citations | Synthesis with calibrated wording; gap register | The same, with the protocol, checklists and judgments attached |
| Researcher's time | Minutes: the question, any seed papers, and a read of the memo | Agreeing the key-paper list; reviewing weights and certainty | Substantial: protocol, every judgment call, disagreements |

**Pros and cons, in plain words.**

- **Quick scan.** Fast and cheap, and good for getting bearings or for pointers
  when the researcher will read the papers. But abstracts can overstate results
  and leave out limitations, so the memo reports what papers claim, not how
  well they show it, and states no certainty.
- **Standard review.** A reliable picture of what the evidence shows, with every
  quote and number checked on its page. But the weight of each paper is a
  reasoned judgment, not a checklist score, and the key papers are chosen with
  the researcher rather than every eligible paper being read.
- **Formal / systematic.** A documented, defensible appraisal suitable for
  publication as a systematic review. But it takes much more of the
  researcher's time, and more reading and cost per paper. It is "its own type
  of research process", led by the researcher; DAAF supplies checklists and
  records rather than ratings.

## Review types

From Grant & Booth 2009 (via Price 2022), Paré et al. 2015 Table 9.1, Snyder
2019 and the Campbell evidence-and-gap-map guidance, as read for DAAF's 2026-10-02
methodology survey.

| Type | Question it answers | Search breadth | Appraisal | Synthesis | Typical output |
|---|---|---|---|---|---|
| Narrative / traditional | What has been written on a topic? Does not "seek generalization or cumulative knowledge" | Selective | None formal | Thematic, chronological or conceptual | Essay, background section |
| Descriptive / mapping | What patterns and gaps exist relative to existing propositions, theories or methods? | A "representative number of works" | None formal | Frequencies, content analysis | Counts, categorizations |
| Scoping | How big is the literature, what is its nature, is a systematic review warranted? | Comprehensive, iterative; explicit criteria | "No formal quality… assessment" | Numerical summary plus thematic | Charted table and narrative |
| State-of-the-art | What is the most current thinking? | "The most current literature" | n/a | Narrative | Frontier summary |
| Systematic | Answers a clearly formulated question in depth | "Exhaustive… a priori inclusion and exclusion criteria" | Risk of bias per study; certainty per outcome | Structured narrative (DAAF never meta-analyzes) | Answer plus certainty |
| Rapid | A policy or practice question under time limits | "Determined by time constraints" | "Time-limited formal quality assessment" | Narrative, tabular | Brief with declared shortcuts |
| Umbrella / overview | What do existing reviews conclude? | Reviews only | AMSTAR 2 plus GRADE | Tabular | Review of reviews |
| Realist | "What works for whom under what circumstances, how and why?" | Systematic or "iterative and purposive" | Fit for purpose | Context–mechanism–outcome theory | Program theory |
| Critical | Strengths, weaknesses and contradictions in theory and method | Representative or illustrative | Judged "according to contribution" | Interpretive | Critique, new model |
| Integrative / semi-systematic | How has the field developed? | "May or may not be systematic" | Varies | Qualitative or mixed | New framework |
| Evidence and gap map | Where is evidence present or absent across intervention × outcome? | Systematic search | Optional | Coding into a matrix | Grid |

Meta-analysis is a review type DAAF does not perform: no pooled effect is ever
computed (SKILL.md § Synthesis guardrails). Sutton et al. 2019 identified "48
review types… categorised into seven families": traditional, systematic, review
of reviews, rapid, qualitative, mixed-methods and purpose-specific.

## The intent menu

The researcher picks an intent; the intent sets the defaults below, and the
researcher can change any of them.

| Researcher's intent | Review type(s) | Default level | Default synthesis | Parameters the researcher sets |
|---|---|---|---|---|
| **Get my bearings**, or **pointers** to papers I will read myself | Narrative, explicitly selective | Quick scan | A short memo: where to start reading, what the abstracts report, gaps that seem to exist | The question; any seed papers |
| Map the **frontier**: what are people pushing on? | State-of-the-art plus semi-systematic | Quick or standard | Thematic plus concept matrix plus an "active questions" list | Time horizon, seeds, preprints yes or no, forward-citation depth |
| What is the literature's **answer** to a question, and when does it apply? | Focused review (rapid if time-boxed); a systematic review only at the formal level | Standard; formal if the researcher wants a systematic review | SWiM-structured or narrative synthesis with boundary conditions; a table of individual studies' estimates, never pooled | PICO/PECO, eligible designs, outcome measures |
| How is X **measured or operationalized**? | Scoping (methods-focused) | Standard | Charting table (instrument, validity evidence, sample) | PCC, fields to chart |
| **Theory or conceptual** landscape; mechanisms | Critical or integrative; realist when mechanism-focused | Standard | Concept matrix; context–mechanism–outcome tables | Disciplines, organizing concepts |
| **Gaps and contribution** opportunities | Scoping plus evidence-and-gap map plus a gap pass | Standard | Gap grid; gap register; optional problematization | Matrix axes (4–6 × 4–6), problematization yes or no |
| **Related work** for my paper | Narrative, explicitly selective | Quick or standard | Positioned narrative with a selectivity statement | Anchor papers, length, recency, one-hop snowball |
| Do **existing reviews** agree? | Umbrella | Standard or formal | Review-of-reviews table with overlap handling | Review-quality guide (AMSTAR 2) |

## How type and level combine

- A **systematic review implies the formal level.** Calling a standard review
  "systematic" would claim a protocol, a second screener and checklist
  appraisal that did not happen.
- **Scoping and mapping reviews** run at the standard level by default. Scoping
  reviews do not appraise by design, so each finding either states a certainty
  with a reason or carries "certainty not rated", decided per finding; paper
  notes keep the design label and quoted limitations, and weight is optional.
  Levac et al. 2010 warn that gaps claimed without assessing quality "may yield
  false conclusions", so the gap register still marks where evidence is weak.
- **Related work and frontier scans** fit a quick scan when the researcher will
  read the papers; a standard review when the text will make claims about what
  the evidence shows.
- **Umbrella reviews** at the formal level use `guide-reviews.md`; at the
  standard level, the paper note for each review records its design and quoted
  limitations, with AMSTAR 2's critical items as prompts.
- **Realist and thematic syntheses** of qualitative evidence carry "certainty
  not rated: qualitative evidence" at every level (`certainty-of-evidence.md`).

## Questions to ask, by level

Every review fixes the same parameters before the first search, but it does
not ask about all of them. Ask what the level needs; set the rest to a stated
default, and tell the researcher what the defaults were and that any of them
can change at the next round. A quick scan should take the researcher a
minute to set up.

| Parameter | Quick scan | Standard review | Formal / systematic |
|---|---|---|---|
| The question | Asked | Asked | Asked, in its frame (§ Question frames) |
| Seed papers the researcher expects to find (the recall check) | Asked, optional | Asked | Asked |
| Time horizon | Default: as the question implies, stated in the memo | Asked | In the protocol |
| Inclusion and exclusion criteria (`screening.md`) | Default: DAAF drafts them from the question and writes them in the scan plan | DAAF drafts; the researcher confirms | In the protocol |
| Sources: search backends, grey literature, preprints | Default: `scholar_search find`'s default backends (OpenAlex, Semantic Scholar, ERIC; ERIC skipped outside education); no grey literature | Asked, with DAAF's suggestion | In the protocol |
| Stopping rule (§ Stopping rules) | Default: one or two rounds | Asked | In the protocol (systematic: exhaustive completion) |
| Breadth: selective, representative or exhaustive | Default: selective | Default: representative; asked if unclear | In the protocol |
| Depth: which papers get a full read | Fixed by the level: none | Fixed by the level: the key papers agreed with the researcher | Fixed by the level: every included paper |
| Outputs wanted | Default: the memo | Asked | In the protocol |
| Vision preference for tables in PDFs | Not used (no PDFs are read) | Read from CLAUDE.md § User Preferences, not asked | Read from CLAUDE.md; recorded in the protocol |

For a quick scan, the setup is two questions, shown as written:

> **What question should the scan look into?** One or two sentences is enough.
>
> **Are there papers you already know should turn up?** Optional. DAAF uses them to check that the searches are finding the right things.
>
> Everything else (time span, sources, how many rounds) gets a sensible default, listed at the end of the memo; tell DAAF if you want any of it changed.

For a standard review, the setup questions, shown as written (ask the
question marked "only if unclear" only when the research question leaves it
open):

> **What question should the review answer?** A few sentences: who it is about, what is being tried or studied, and which results matter to you.
>
> **Are there papers you already know should turn up?** DAAF uses them to check that the searches are finding the right things, and they are strong candidates for a full read.
>
> **How far back should we look?** For example, the last ten years, or since a policy or a way of measuring changed.
>
> **Where should we search?** DAAF suggests the main research databases (OpenAlex, Semantic Scholar, and ERIC for education). Should we also look for reports from government agencies and research organizations, or for papers not yet peer reviewed?
>
> **Should we stop after a set number of search rounds, or when new rounds stop turning up new ideas?**
>
> **Should the review give a fair picture of the research, or try to find everything?** *(only if unclear)* A fair picture means a well-chosen set of studies that represents the field; finding everything takes much longer.
>
> **Which studies count?** DAAF drafts the rules for which studies are in and which are out (for example, ages, countries, years and kinds of study) from your question. Please check them before we start choosing papers.
>
> **What would you like at the end?** For example, a background section for a paper, a briefing for a decision, or a table of the studies.
>
> DAAF then proposes the key papers to read in full, and you agree the list before any reading starts.

The answers and the defaults go in the protocol (formal) or the opening notes
of the review (quick, standard), so every later choice can be checked against
them. A quick scan's defaults also appear in the memo's "How this was done"
section (`quick-scan.md` § Step 5: the memo).

## Question frames

| Frame | Parts | Fits |
|---|---|---|
| PICO | Population, Intervention, Comparator, Outcome | Effect questions |
| PECO | Population, Exposure, Comparator, Outcome | Exposures that are not deliberate interventions (poverty, segregation) |
| PCC | Population, Concept, Context | Scoping reviews (JBI) |
| SPIDER | Sample, Phenomenon of Interest, Design, Evaluation, Research type | Qualitative questions |

PCC and SPIDER were read only from search snippets in DAAF's survey (the JBI
manual page and the SPIDER paper were not fetched).

## Stopping rules

Choose one before the first search, because a rule chosen after seeing results
can be bent to fit them.

| Rule | When it ends | Source |
|---|---|---|
| Concept saturation | A round finds no new concepts ("nearing completion when you are not finding new concepts") | Webster & Watson 2002 |
| Evidence saturation | Iterative searching "until evidence saturation is reached" | Rapid realist reviews, via Sutton et al. 2019 |
| Round cap | A fixed number of search rounds | DAAF option |
| Corpus cap | A fixed number of included papers | DAAF option |
| Exhaustive completion | Every planned source and string run (formal level) | — |

There is no validated tool "to inform when to stop searching" (Sutton et al.
2019), so the researcher's judgment decides; the saturation table per round
(`gaps-and-saturation.md`) shows the evidence for it.

## Reporting standards by level

| Standard | What it is | Used at |
|---|---|---|
| PRISMA-S | 16 items for reproducible search reporting (sources, strings, dates, limits, deduplication) | Every level: the search log covers it, because `scholar_search` records every call |
| Simple counts per round | Found, screened, read in full, cited (`gaps-and-saturation.md`) | Quick and standard |
| PRISMA 2020 | "27-item checklist… flow diagrams"; "not intended to guide… conduct"; points to SWiM at item 13d | Formal level, systematic reviews |
| PRISMA-ScR | "20 essential reporting items and 2 optional items" | Formal level, scoping reviews |
| Selectivity statement | How and why papers were chosen | Every selective review (related work, frontier, narrative) |
| Rapid-review shortcut table | Each shortcut taken, declared | Rapid reviews |
| AI disclosure (RAISE) | What was AI-judged and what was mechanically verified; authors "remain ultimately responsible" | Every level |

No DAAF tool produces PRISMA 2020 flow-diagram counts (the researcher chose
to keep the formal level researcher-led: `formal-review.md` § What is
deferred, and why); at the formal level, build the counts by hand from the
screening log and the per-round counts (`lit_corpus counts`) and say so.

## Changing level or re-steering

The researcher can raise the level, or change the type, at any round
checkpoint. Treat every change as a new protocol version: record what changed,
why, and who decided, and keep the old version. A quick scan raised to a
standard review keeps its search log and screening decisions; the papers then
chosen as key papers are read in full, and any claim that was "per abstract"
is replaced by a page-checked claim or keeps its label. Lowering a level after
findings have been stated needs the same record, because readers of the
earlier version may have relied on it.

## Sources

Read in full for DAAF's 2026-10-02 methodology survey unless marked:
Grant & Booth 2009 (via Price 2022 and a library summary; the original was not
fetched); Paré et al. 2015 (Table 9.1); Snyder 2019 (Table 1); Sutton et al.
2019, Health Info Libr J; Levac et al. 2010, Implementation Science 5:69;
Webster & Watson 2002; the Campbell evidence-and-gap-map guidance
(PMC8356343); PRISMA 2020
(PMC8008539); PRISMA-S (prisma-statement.org/prisma-search); PRISMA-ScR
(prisma-statement.org/scoping); the RAISE position statement of Cochrane,
Campbell, JBI and CEE (PMC12603384). Snippet only: JBI PCC, SPIDER, Garritty et
al. 2024.
