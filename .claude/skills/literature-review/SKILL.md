---
name: literature-review
description: >-
  Methodology for literature reviews in DAAF, organized by three levels the
  researcher picks at the start: quick scan (abstracts and a short memo of
  pointers), standard review (full reads of key papers, page-checked claims, a
  stated weight per paper, calibrated wording) and formal or systematic review
  (researcher-led protocol, second screener, checklist guides for RoB 2,
  ROBINS-I V2, ROBINS-E, WWC, AMSTAR 2, JBI and CASP, GRADE-style certainty).
  Covers choosing a review type and level, screening, per-paper notes, citation
  snowballing, synthesis without pooling or vote counting, labeled descriptive
  summaries, the certainty phrase table (certainty-language.yaml) and the gap
  register. Use when planning, screening, appraising, synthesizing or reporting
  a literature review, or wording what a body of evidence shows. Not for running
  searches (scholarly-search), reading PDFs (pdf-reading), causal verbs for
  one's own results (data-scientist), or lay audiences (science-communication).
metadata:
  audience: any-agent
  domain: research-methodology
  skill-authored: "2026-10-31"
  skill-last-updated: "2026-11-01"
---

# Literature Review

The methodology behind a DAAF literature review: how deep to go, what to read,
how to say how much weight a paper deserves, how to state how sure we can be
about a conclusion, and which words that allows. The researcher picks one of
three **levels** at the start (quick scan, standard review, formal or systematic
review) beside a **review type** (systematic, scoping, state-of-the-art,
integrative, realist, umbrella, related work). The level sets the reading depth,
the per-paper record and how certainty is handled; the type sets the question
frame and the synthesis method. Some guarantees hold at every level: searches
are recorded, citations are checked against a database record, abstract-only
evidence is labelled, results from different studies are never averaged into one
number, and the wording never sounds surer than the evidence. This skill owns
the method (protocol, screening, paper notes, the formal-level checklist guides,
certainty, synthesis guardrails, the gap register) and the phrase table
`references/certainty-language.yaml`. It points elsewhere for search commands
(`scholarly-search`), reading PDFs into page-checked evidence cards
(`pdf-reading`), study-design threats and causal verbs (`data-scientist`),
exploratory versus pre-specified labels (`creative-verification`), and plain
language for lay readers (`science-communication`). The Literature Review mode
runs this method: its literature-searcher and literature-synthesizer agents
preload this skill, and its paper-reader reads the paper-note and checklist
files by path. Outside that mode, an agent doing review work for the
researcher applies the skill directly.

## In short

**What you can rely on, at every level.** Every search is saved with its exact
query and results. Every cited reference has been matched to a database record,
so it exists as cited. Anything taken only from an abstract says "per abstract".
Studies are never averaged or pooled into one number (a labelled median and
range of the studies' own results may be shown). Words such as "probably"
and "may" follow a fixed table, so a sentence never sounds surer than the
evidence behind it.

**What changes with the level.**

- **Quick scan:** DAAF reads titles and abstracts and writes a short memo: what
  studies report, which papers look most useful, and where the gaps seem to be.
  Particularly useful when you plan to read the papers yourself and want
  pointers. It says what papers claim, not how well they show it.
- **Standard review (the default):** DAAF reads the key papers in full and
  checks every quote and number against the page it came from. Each paper gets a
  short note: its design, its main limitations (quoted, with pages) and how much
  weight it deserves, with reasons. Each conclusion states how sure we can be,
  and why.
- **Formal or systematic review:** you lead a formal process. DAAF supplies the
  published checklists, drafts answers with quotes, keeps every record and
  checks every quote and citation; you make the judgment calls.

**What you should check.** In a quick scan: whether the "where to start" list
matches your sense of the field, and whether a gap is real or only a search that
missed a phrasing (the memo names the queries that came back empty). In a
standard review: the list of key papers, the weight given to each paper and its
reasons, the certainty stated for each conclusion and its reasons, and anything
marked for review. At the formal level, every checklist judgment and every
certainty rating is yours.

## The level menu

This is what the researcher sees at the start of a review (orchestrator: show
it as written; details and the type-by-level table are in
`references/review-types-and-levels.md`).

> **How deep should this review go?** You can change your mind after any round (one cycle of searching, choosing and reading papers, after which DAAF reports back); DAAF keeps a record of every choice.
>
> **Quick scan.** DAAF searches the literature, reads titles and abstracts, and writes a short memo: what studies report, which papers look most useful, and where the gaps seem to be. Every reference is matched to a database record and you look over the reference list before the memo is final, and every statement drawn from an abstract says so.
> - *Good for:* getting your bearings, or finding pointers when you plan to read the papers yourself.
> - *Trade-off:* abstracts can overstate results and leave out limitations, so the memo says what papers claim, not how well they show it.
> - *Your time:* minutes: the question, any papers you already know should turn up, a read of the memo, and a look over the reference list (about a minute per 10 references).
>
> **Standard review** *(recommended for most questions).* DAAF reads the key papers in full. Every quote and number it uses is checked against the page it came from. For each paper you get a short note: the study design, its main limitations (quoted, with page numbers) and how much weight it deserves, with the reasons. The synthesis states how sure we can be about each conclusion, and the wording follows that ("probably", "may", …).
> - *Good for:* a reliable picture of what the evidence shows, for a paper's background, a grant, or a decision.
> - *Trade-off:* the weight of each paper is a reasoned judgment, not a formal checklist score, and DAAF chooses the key papers with you rather than reading everything that exists.
> - *Your time:* agreeing the list of key papers before they are read, a check-in after each round, checking the weights and how sure each conclusion is, and a look over the reference list before the final version (about a minute per 10 references).
>
> **Formal / systematic review.** You lead a formal, publishable process: a plan written before any searching (the protocol), fixed rules for which studies count, a second person checking those choices, a published checklist for each kind of study, and a formal rating of how sure we can be about each conclusion. DAAF drafts each checklist answer with the passage that supports it, keeps every record and checks every quote and citation; you make every judgment call. (The checklists are the standard published ones, such as RoB 2 for randomized trials and ROBINS-I for other studies of a program or policy; the rating follows the GRADE method.)
> - *Good for:* a publishable systematic review, or when you need a fully documented, defensible appraisal.
> - *Trade-off:* much more of your time, and more reading and cost per paper.
> - *Your time:* substantial: the protocol, every checklist judgment and rating, settling disagreements between the two people choosing studies, and a look over the reference list before the final version.
>
> **At every level:** searches are recorded, citations are checked, abstract-only evidence is labelled, results from different studies are never averaged into one number, and the wording never sounds surer than the evidence.

## The tools and agents behind the method

Every piece below is built. In the Literature Review mode the orchestrator
dispatches the agents and runs every gate it does not author
(`.claude/skills/daaf-orchestrator/references/literature-review-mode.md`);
outside that mode, the orchestrator or a dispatched agent runs the tools
directly and says so in the output.

| Piece | What it does |
|-------|--------------|
| `scholar_search.sh` (search, `verify`, `retractions`, `cites`, `refs`, `similar`, `oa`) | Searches and reference checks, each call recorded |
| `pdf_ingest.sh` and `lit_verify.sh card` | Page-checked quotes and numbers; card schemas v1, v2 and v3 (v3: `claim_type`, incl. `limitation` with `limitation_kind`, `appraisal` and `citation_use`; gate-checked `quant` values; a `paper_note` block) |
| `lit_corpus` | Corpus, screening log, counts per round, claims, paper-notes and findings tables, descriptive summaries, sign tests, gap register, citation-edge table, BibTeX/RIS, review manifest, and the second-check ledger with the reference glance (`references/lit-corpus.md`) |
| `lit_verify report` | Checks a deliverable's citations, claim links and wording against the review's tables (`references/lit-verify-report.md`) |
| `lit_verify route`, `audit` and `settle` | Record the install route; check who read a card's page pictures, on which route, and where the PDF came from; record a person's comparison of listed readings with the page (`pdf-reading` `references/vision-validation.md` § Gating) |
| `scholar_search` records files and `cites`/`refs --s2-context` | Semantic Scholar citation sentences; intents on `refs` only |
| Literature Review mode and its agents: literature-searcher, paper-reader, literature-synthesizer | The three levels with the researcher's check-ins; one reader per paper; deliverables written only from page-checked claims |
| The citation second check | No adjudicator model has passed its evaluation, so the citation-adjudicator agent is not dispatched: the second check of every reference whose automatic check matched its record is the researcher's reference glance before any final deliverable (`references/lit-corpus.md` § Citation second check) |

## Scope

| This skill covers | Go elsewhere for |
|-------------------|------------------|
| Choosing a review type and level; the protocol; stopping rules | Search commands, flags, rate limits, licensing of search data: `scholarly-search` |
| Screening rules, a second screener, seed recall | Reading a PDF, evidence cards, the quote and number gate, evidence grades: `pdf-reading` |
| Per-paper notes: design, quoted limitations, weight, directness | Design threats (what a DiD, RD or IV paper must show): `data-scientist` `references/causal-inference.md` § Threats to Validity Checklist |
| Formal-level checklist guides (RoB 2, ROBINS-I V2, ROBINS-E, WWC, AMSTAR 2, JBI, CASP) | Causal versus associational verbs: `data-scientist` `references/research-questions.md` § Causal vs. Correlational Language |
| Certainty of a finding and the phrase table | Exploratory versus pre-specified labels: `creative-verification` `references/interpretation-and-evidence.md` § Four-Way Test Labeling |
| Synthesis methods and guardrails; descriptive summaries; sign tests | Plain-language translation for lay readers (its hedging scale uses different words): `science-communication` `references/plain-language.md` |
| The gap register, saturation, the follow-up plan | Grey literature retrieval: `web-retrieval` |

The phrase table covers statements about what a **body of evidence** shows. It
does not govern how the researcher words results of their own analysis.

## Vocabulary

One term per idea; mixing them is how a weak paper ends up sounding like a
strong conclusion.

| Term | Means only | Never use it for |
|------|-----------|------------------|
| **level** (`review_level`: `quick`, `standard`, `formal`) | How deep the review goes, chosen by the researcher | "tier": DAAF uses "level" here because "tier" already means other things (design-strength tiers, ESSA tiers) |
| **weight** of a paper (`substantial`, `moderate`, `limited`) | How much a paper should count in the synthesis, with reasons that name its quoted limitations | a quality score or a checklist total |
| **certainty** of a finding (`high`, `moderate`, `low`, `very_low`) | How sure we can be about a synthesized conclusion | a single study, the AI reader's confidence, a gap |
| **confidence** | The AI reader's (the agent that read the paper) confidence in its own card (H/M/L), and a gap's confidence | a finding's certainty |
| **reading depth** (machine: `evidence_grade`) | What was actually read: `FULL_TEXT_VERIFIED`, `FULL_TEXT_PARTIAL`, `ABSTRACT_ONLY`, `METADATA_ONLY` (`pdf-reading`) | GRADE certainty |
| **risk of bias** (the tool's own scale) | A formal-level checklist judgment on one result | "high-quality study" (Waddington et al. 2026 advise against quality labels) |
| **directness** (direct, partly, indirect) | How closely a study's population, intervention, comparator, outcome, setting and time match the review question | search relevance rank |
| **descriptive summary** | The unweighted median, IQR and range of at least 3 estimates from at least 3 papers on one metric, labelled "descriptive summary, not a pooled estimate" | "average", "overall", "pooled" or "typical" effect |
| **checklist answer** | A formal-level answer to one checklist item, with its quote | a rating; the rating is the researcher's |

## Which file?

```
What are you doing?
├─ Setting up a review (type, level, question, stopping rule)
│     → references/review-types-and-levels.md
├─ Quick scan → references/quick-scan.md
├─ Standard review
│   ├─ Choosing key papers, snowballing, the synthesis → references/standard-review.md
│   └─ Writing a paper's note (design, limitations, weight) → references/paper-notes.md
├─ Formal or systematic review → references/formal-review.md, then one guide:
│   ├─ Randomized trials (RoB 2) ............................ references/guide-randomized.md
│   ├─ Non-randomized interventions, exposures, DiD, RD, IV . references/guide-nonrandomized.md
│   ├─ Education effect studies (WWC lens, optional) ....... references/guide-education-wwc.md
│   ├─ Descriptive, correlational, survey studies ........... references/guide-descriptive.md
│   ├─ Qualitative studies (JBI, CASP) ...................... references/guide-qualitative.md
│   ├─ Systematic reviews, umbrella reviews (AMSTAR 2) ...... references/guide-reviews.md
│   └─ Theory and conceptual papers ......................... references/guide-theory.md
├─ Screening (any level) → references/screening.md
├─ Stating how sure we can be about a finding → references/certainty-of-evidence.md
│     and the words for it → references/certainty-language.yaml
├─ Choosing a synthesis method; descriptive summaries; sign tests
│     → references/synthesis-methods.md
└─ Gaps, saturation, the next round's plan → references/gaps-and-saturation.md
```

Each guide is self-contained, so an agent reading one paper loads only the guide
for that paper's design.

## Who does what

| Level | The AI does | Code checks | The researcher decides |
|-------|-------------|-------------|------------------------|
| Quick scan | Searches, screens abstracts once, drafts the memo | `scholar_search verify` and `retractions` on every cited reference; `lit_verify report` checks the memo's citations and "per abstract" labels, once `lit_corpus` holds the papers (`references/quick-scan.md` § Order of commands) | The question; whether to go deeper |
| Standard | Proposes key papers; reads them in full; writes paper notes with a stated weight; states each finding's certainty with a reason | `lit_verify card` checks every quote and number on its page; `verify`, `retractions`; `lit_corpus` refuses a certainty without a reason; `lit_verify report` checks citations, claim links and wording | The key-paper list; accepts or changes weights and certainty; any retracted or doubtful citation |
| Formal | Drafts checklist answers with quotes; keeps the protocol, screening log and counts; drafts certainty notes per domain | As standard; checklist answers are quote-checked like any claim (card v3) | The protocol; every checklist judgment; every certainty rating; screening disagreements (a second person decides on every full text) |

AI-drafted checklist judgments are unreliable: in published tests, language
models agreed with human RoB 2 assessors at κ 0.06 to 0.22 (Eisele-Metzger et
al. 2025; Nyrhi et al. 2026), and their stated judgments diverged from their own
answers to the tool's questions (domain 2, mean 42%; Choi et al. 2026). DAAF
has read only the abstracts of these three studies, and the models they tested
may not be the one doing this review. That is why, at the formal level, the AI
answers items with quotes and the researcher makes the calls.

## Certainty wording in one table

The full table, with allowed and forbidden words per level and the lint
patterns, is `references/certainty-language.yaml`. Read it there; do not copy it
into other files, because a copy drifts.

| Certainty | Canonical wording | Example |
|-----------|-------------------|---------|
| high | the bare verb, or "results in" | "Tutoring improves reading scores." |
| moderate | "probably" | "Tutoring probably improves reading scores." |
| low | "may" ("the evidence suggests" also fits) | "Tutoring may improve reading scores." |
| very low | "the evidence is very uncertain" | "The evidence is very uncertain about the effect of tutoring on reading scores." |
| not rated | "certainty not rated: abstracts only" or "… qualitative evidence" | used for quick-scan findings and qualitative themes |

"Likely" is not used in finding sentences: GRADE allows it at moderate, but it
also reads as a probability term, so DAAF keeps one moderate word. "No effect"
is never a conclusion; say "little to no difference", and only with an
importance threshold declared in advance. The verb comes from the designs: an
associational body of evidence says "is associated with", not "improves".

## Synthesis guardrails

Each rule exists because the opposite is a known way reviews mislead.

- **No pooling, averaging or weighting of effects across studies.** Studies
  differ in design and quality; a single number hides that. Report each study's
  estimate with its citation. Statements across studies are the point of a
  review and are fine at the finding's certainty: "Taken together, the three
  trials indicate that tutoring probably improves reading scores [@a; @b; @c]"
  (moderate). What fails is one effect number credited to several studies that
  nobody computed.
- **Descriptive summaries only with at least 3 estimates from at least 3 papers
  on a common metric**, unweighted (median, IQR, range), labelled "descriptive
  summary, not a pooled estimate". Cochrane notes these statistics ignore study
  size and their performance "has not been evaluated" (ch.12).
- **No vote counting by significance.** "7 of 10 studies found significant
  effects" misleads, because small studies miss real effects. Counting the
  direction of effects with a sign test is allowed. Informal counts ("most
  studies found") also count as vote counting (Cochrane ch.12).
- **Order by weight and directness, not by how many studies agree.** Stronger,
  more direct studies anchor statements; weaker ones are labelled context.
- **Sensitivity reasoning** whenever a conclusion could rest on weaker studies:
  "restricting to the studies given substantial weight, the direction is …".
- **Explain disagreement** through design, quality or context before calling
  evidence "mixed".
- **Abstract-only evidence is labelled** inside the citation and never supplies
  effect sizes or boundary conditions.
- **Post-hoc moderators are labelled "exploratory".**
- **"Disputes" or "contradicts"** rests only on a quoted sentence in which a
  paper takes issue with another, never on citation counts or on Semantic
  Scholar's citation intents (none of which means disagreement).
- **"No evidence of an effect" is not "evidence of no effect"** (Cochrane
  §15.6.4); if one is mentioned, mention the other.

Details and the method per review type: `references/synthesis-methods.md`.

## In-prose markers

Markers bind a sentence to its evidence so a reader, and `lit_verify report`
(`references/lit-verify-report.md`), can check it.

| Marker | Means |
|--------|-------|
| `[@citekey]` | A citation (Pandoc syntax) |
| `[@citekey, per abstract]` | Only the abstract was read, or (for a paper also read in full) every claim the sentence marks from it comes from its abstract |
| `[sentence]{.lr-finding fid=F03 claims="W123-c03 W456-c01"}` | The sentence states finding F03, resting on those claims; its wording is checked against F03's certainty |
| `[sentence]{.lr-claim claims="W123-c03"}` | The sentence reports one paper's claim |
| `[sentence]{.lr-edge edges="E012"}` | The sentence describes how one paper uses another (citation-edge table); "disputes" or "contradicts" needs a reader-quoted relation |

Quick-scan memos use citations and the "per abstract" label only, no finding
markers: nothing in them is a rated finding. A paper with no abstract on record
and no full read is named only under a "Further reading" heading, by its
topic, setting, method or the question it asks, and never by what it found
(`references/quick-scan.md` § Step 5: the memo). Claim ids (`W123-c03`), finding
ids (`F01`) and link ids (`E012`) come from `lit_corpus`'s tables
(`references/lit-corpus.md`).

## Reference files

| File | Read when |
|------|-----------|
| `references/review-types-and-levels.md` | Setting up a review: types, intent menu, levels in depth, question frames, stopping rules, reporting standards, changing level |
| `references/quick-scan.md` | Running a quick scan: search plan, abstract screening, memo shape, labels, order of commands |
| `references/standard-review.md` | Running a standard review: key papers, snowballing and the citation network, full reads, synthesis, what the researcher checks, order of commands |
| `references/paper-notes.md` | Writing a paper's note: design label, quoted limitations, weight, directness |
| `references/screening.md` | Screening at any level: criteria, decisions, reason codes, second screener, seed recall |
| `references/formal-review.md` | A formal or systematic review: protocol, roles, routing to a guide, the researcher's certainty rating |
| `references/guide-randomized.md` | Formal level, randomized trials: RoB 2 |
| `references/guide-nonrandomized.md` | Formal level, non-randomized studies: ROBINS-I V2, ROBINS-E, DAAF's design checks for DiD, RD, IV, matching, synthetic control, ITS |
| `references/guide-education-wwc.md` | Formal level, education effect studies: WWC v5.0 as an optional lens |
| `references/guide-descriptive.md` | Formal level, descriptive and cross-sectional studies: JBI, AXIS, DAAF's descriptive checklist |
| `references/guide-qualitative.md` | Formal level, qualitative studies: JBI and CASP; why certainty is not rated |
| `references/guide-reviews.md` | Formal level, reviews of reviews: AMSTAR 2 |
| `references/guide-theory.md` | Formal level, theory and conceptual papers: DAAF's profile |
| `references/certainty-of-evidence.md` | Stating a finding's certainty and its reason; the formal-level rating; not-rated findings |
| `references/certainty-language.yaml` | The words for each certainty level; lint patterns (machine-readable) |
| `references/synthesis-methods.md` | Choosing and reporting a synthesis method; descriptive summaries; sign tests; guardrails |
| `references/gaps-and-saturation.md` | The gap register, evidence of absence, saturation, counts per round, the follow-up plan |
| `references/lit-corpus.md` | Running `lit_corpus`: subcommands, inputs, tables and columns, keys and citekeys, exits |
| `references/lit-verify-report.md` | Running `lit_verify report` on a memo or synthesis: markers, checks, statuses, plain reasons, exits |

## Topic index

| Topic | File |
|-------|------|
| Review typology, families, intent menu | `references/review-types-and-levels.md` |
| PICO, PECO, PCC, SPIDER | `references/review-types-and-levels.md` |
| Stopping rules | `references/review-types-and-levels.md` |
| PRISMA 2020, PRISMA-S, PRISMA-ScR, RAISE disclosure | `references/review-types-and-levels.md`, `references/formal-review.md` |
| Changing level mid-review | `references/review-types-and-levels.md` |
| Abstract-only claims, the quick-scan memo | `references/quick-scan.md` |
| Order of commands, search to `lit_verify report` | `references/quick-scan.md`, `references/standard-review.md` |
| `lit_corpus`: subcommands, tables and columns, paper keys and citekeys, exits | `references/lit-corpus.md` |
| `lit_verify report`: markers, statuses and plain reasons, exits | `references/lit-verify-report.md` |
| Choosing key papers, anchors, seeds | `references/standard-review.md` |
| Forward and backward snowballing, citation contexts, the edge table | `references/standard-review.md` |
| Paper weight words and reasons | `references/paper-notes.md` |
| Signals that are not quality (citations, venue) | `references/paper-notes.md` |
| Exclusion reason codes, second screener, disagreements | `references/screening.md` |
| AI as a screener | `references/screening.md` |
| Checklist answers as quote-checked claims | `references/formal-review.md` |
| RoB 2 domains and overall rule | `references/guide-randomized.md` |
| ROBINS-I V2 triage and overall rule; ROBINS-E | `references/guide-nonrandomized.md` |
| Pre-trends, bunching, instrument checks (DAAF) | `references/guide-nonrandomized.md` |
| WWC attrition, baseline equivalence, ESSA tiers | `references/guide-education-wwc.md` |
| AMSTAR 2 critical items | `references/guide-reviews.md` |
| GRADE domains without pooling (Murad 2017) | `references/certainty-of-evidence.md` |
| GRADE-CERQual (deferred) | `references/guide-qualitative.md`, `references/certainty-of-evidence.md` |
| Phrase per certainty level; "likely"; "no effect" | `references/certainty-language.yaml` |
| SWiM, narrative, thematic, concept matrix, EGM, realist | `references/synthesis-methods.md` |
| Descriptive summary, sign test, vote counting | `references/synthesis-methods.md` |
| Gap types, evidence of absence, problematization | `references/gaps-and-saturation.md` |
| Counts per round, saturation table, follow-up plan | `references/gaps-and-saturation.md` |
