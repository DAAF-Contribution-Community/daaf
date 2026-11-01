# Gaps and Saturation

What the review found missing, how sure we are that it is missing, and when to
stop: the gap register, evidence of absence, the saturation table and counts
per round, and the follow-up plan the researcher approves between rounds.

## Contents

- [The gap register](#the-gap-register)
- [Gap types and modes](#gap-types-and-modes)
- [Evidence of absence](#evidence-of-absence)
- [Gap confidence](#gap-confidence)
- [Could DAAF data answer it?](#could-daaf-data-answer-it)
- [Problematization](#problematization)
- [Counts per round](#counts-per-round)
- [Saturation table](#saturation-table)
- [The follow-up plan](#the-follow-up-plan)
- [Sources](#sources)

## The gap register

One entry per gap:

| Field | Content |
|---|---|
| `gap_id` | `G01`, `G02`, … |
| `statement` | The gap in one sentence |
| `miles_type` | `evidence`, `knowledge`, `practical`, `methodological`, `empirical`, `theoretical`, `population`, or `unclassified` (the default when left out; a researcher's judgment at the formal level, optional at the quick and standard levels, § Gap types and modes) |
| `sa_mode` | `confusion`, `neglect`, `application_spotting`, `problematization`, or `unclassified` (as `miles_type`) |
| evidence of absence | The exact searches that returned nothing, or whose results were all excluded (next sections) |
| `supporting_claim_ids` | Claims that point to the gap (authors' stated open questions, contradictory findings) |
| `confidence` | `high`, `moderate`, `low`: confidence that the gap is real, not a finding's certainty |
| `data_answerable` | Whether data DAAF can reach could answer it, with a note |

`lit_corpus gaps record` fills the evidence of absence from the search
MANIFEST rows themselves, so it is never typed: a gap names the rows'
sha256 and kind (`zero_results` or `none_eligible`), and the tool refuses a
row whose search returned results, or whose results were not all excluded at
screening (`lit-corpus.md` § Subcommands).

## Gap types and modes

Classifying a gap by type and mode is formal-level work. At the quick and
standard levels it is optional: the researcher is not asked to classify gaps,
and the statement, the evidence of absence and the confidence carry the gap.
Leave both fields out of the `lit_corpus gaps record` line; the tool stores
them as `unclassified` (1.1.0, gap-words-v1). The tool does not know the
review's level, so at the formal level the protocol, not the tool, requires
a type and a mode for every gap. A code the agent does give must be one of
the values below (anything else is refused).

**Codes stay in the machine fields.** In anything the researcher reads (the
memo, the synthesis, a checkpoint message), describe a gap in plain words, for
example "G01: a population not yet studied (how sure we are the gap is real:
low)", never "G01 (population, neglect; confidence low)". The tool's own
`output/gap_register_v{N}.md` does the same: each heading gives the gap's
plain words from the tables below, or "not classified", and the evidence
lines say "the search returned nothing" or "every result was excluded at
screening"; the codes stay in the `gap_register` table.

**Miles 2017's seven gap types** (read from a snippet only, so the plain words
are DAAF's paraphrase of the type names, not Miles's definitions):

| Code | Plain words for the researcher |
|---|---|
| `evidence` | studies point different ways |
| `knowledge` | the question has not been studied |
| `practical` | practice and research disagree (Miles: practical-knowledge conflict) |
| `methodological` | a method that could answer it has not been used |
| `empirical` | a claim has not been tested with data |
| `theoretical` | no theory explains it |
| `population` | a population not yet studied |

**Sandberg & Alvesson 2011's gap-spotting modes:**

| Code | Mode | Plain words |
|---|---|---|
| `confusion` | Confusion spotting: competing explanations exist | the explanations disagree |
| `neglect` | Neglect spotting: an area is overlooked, under-researched, or lacks empirical support | an overlooked area |
| `application_spotting` | Application spotting: existing work could be extended or complemented | existing work could be extended |
| `problematization` | Combined or disruptive modes (critical confrontation, a new idea), including problematization (below) | an assumption worth questioning |

## Evidence of absence

A search that found nothing is evidence about the index searched, not proof
that no literature exists (`scholarly-search` § Literature-review workflow).
State absence the way DAAF states any negative claim: quote the probe.

- **Zero results:** the exact query, the backends that answered (not the ones
  that failed), the date and the result count, from the MANIFEST row.
- **None eligible:** a search that returned papers, every one of which was
  excluded at screening; name the exclusion reasons.
- Say what was not searched (paywalled databases, Google Scholar, languages not
  covered; `scholarly-search` § Known gaps).

Levac et al. 2010 warn that gaps identified without assessing evidence quality
"may yield false conclusions". A gap where weak studies exist ("only
correlational evidence") is different from a gap where none exist; say which.

## Gap confidence

DAAF's convention (no published scale was found for gap confidence):

| Confidence | Use when |
|---|---|
| high | Several phrasings and sources returned nothing relevant, snowballing from the key papers found nothing, and the key papers' authors name the gap as open |
| moderate | Searches returned nothing relevant, but coverage has a known hole (a missing database, a language) |
| low | One phrasing returned nothing, or the gap rests on the reader's impression |

## Could DAAF data answer it?

Mark `data_answerable` when a dataset DAAF can reach (for example the Education
Data Portal sources) could address the gap, with a one-line note naming it. The
orchestrator can offer a Full Pipeline analysis for such a gap; whether to
pursue it is the researcher's call.

## Problematization

An optional pass that challenges the assumptions behind a literature rather
than filling gaps in it (Alvesson & Sandberg 2011). Assumption types: "in-house,
root metaphor, paradigm, ideology, and field". Use it when the researcher asks
for it; label its output as an argument, not a finding.

## Counts per round

Each round reports simple counts (no flow diagram; PRISMA 2020 counts are built
by hand at the formal level, `review-types-and-levels.md` § Reporting standards
by level):

| Count | From |
|---|---|
| Records found, per source, and unique works after merging versions | The search log (MANIFEST rows) |
| Records from citation searching (`cites`, `refs`, `similar`) | The search log, kept apart from database searches |
| Screened; included; excluded, by reason code | The screening log (`screening.md`) |
| Read in full, by reading depth (`FULL_TEXT_VERIFIED`, `FULL_TEXT_PARTIAL`) | Evidence cards and their checks |
| Abstract-only | The screening log and cards |
| Cited in the latest deliverable | The deliverable's citations |
| Second-screener disagreements | The screening log |

`lit_corpus counts` produces this table (`output/counts_v{N}.json` and `.md`;
`--round R` for one round, `--deliverable PATH` for the cited count).

## Saturation table

Per round, list what was new: concepts or themes, findings, gaps. When rounds
stop adding concepts, the review is "nearing completion" (Webster & Watson
2002). The table is the evidence the researcher uses to apply the stopping rule
(`review-types-and-levels.md` § Stopping rules).

| Round | Searches run | New papers included | New concepts or themes | New findings | New gaps |
|---|---|---|---|---|---|
| 1 | … | … | … | … | … |

## The follow-up plan

At the end of each round, propose the next one for the researcher to approve:
recommended searches and snowball targets, with the expected yield, the reading
load and the cost (search costs from `scholarly-search` § Costs and exit codes;
reading costs per paper). Name what stopping now would leave open.

## Sources

Miles 2017 (snippet only); Sandberg & Alvesson 2011, Organization; Alvesson &
Sandberg 2011, Academy of Management Review; Levac et al. 2010; Webster &
Watson 2002; Müller-Bloch & Kranz 2015. Read for DAAF's 2026-10-02 methodology
survey.
