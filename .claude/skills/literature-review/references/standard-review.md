# Standard Review

The default level: DAAF reads the key papers in full, checks every quote and
number on its page, writes a short note per paper (design, quoted limitations,
a stated weight with reasons), and states for each conclusion how sure we can
be and why. Nothing is computed into a rating; every judgment is written out so
the researcher can check it.

## Contents

- [What the researcher gets](#what-the-researcher-gets)
- [Workflow](#workflow)
- [Choosing the key papers](#choosing-the-key-papers)
- [Citation network: snowballing and how papers use each other](#citation-network-snowballing-and-how-papers-use-each-other)
- [Full reads](#full-reads)
- [The synthesis](#the-synthesis)
- [Sensitivity reasoning](#sensitivity-reasoning)
- [Output shape](#output-shape)
- [Order of commands](#order-of-commands)
- [What the researcher should check](#what-the-researcher-should-check)

## What the researcher gets

A synthesis whose every finding sentence names the papers and claims behind it
and states its certainty in fixed words; a note per key paper; a gap register; a
verified reference list; and counts per round (found, screened, read, cited).

## Workflow

1. **Set up** the type, question, criteria, seeds and stopping rule
   (`review-types-and-levels.md`).
2. **Search and screen** (`scholarly-search`; `screening.md`). A second
   screener is optional; if used, record both screeners' decisions.
3. **Propose key papers** and agree them with the researcher (next section).
4. **Snowball** from the key papers (§ Citation network).
5. **Read each key paper in full**, one reader per paper, into a page-checked
   evidence card (`pdf-reading`), and write its paper note (`paper-notes.md`).
6. **Synthesize**: group claims into findings, order by weight and directness,
   state certainty with reasons (`certainty-of-evidence.md`), word it with
   `certainty-language.yaml`, follow `synthesis-methods.md`.
7. **Gaps and next round** (`gaps-and-saturation.md`); stop when the stopping
   rule is met.
8. **Verify** every cited reference (`verify`, `retractions`) and check the
   draft against the guardrails in SKILL.md with `lit_verify report`, which
   checks citations, claim links and wording mechanically
   (`lit-verify-report.md`). The commands, in order: § Order of commands.

## Choosing the key papers

A standard review reads key papers in full rather than everything that exists;
that choice is the level's main trade-off, so make it visible and agree it with
the researcher.

| Source of a key paper | Why it qualifies |
|---|---|
| Seeds the researcher named | The researcher's own anchors; also the recall check |
| Anchors found by several backends, often cited by the other included papers | The field treats them as central |
| The strongest designs bearing on each sub-question | They will anchor findings (randomized trials, well-identified quasi-experiments) |
| The most direct matches to the question's population, setting and outcome | Directness can outweigh design strength for a specific question |
| Recent work from forward snowballing | Catches what supersedes or qualifies the anchors |

Show the proposed list with one line of reasoning per paper, and the included
papers that will **not** be read in full. Those stay as "per abstract" context
or are left out of findings. A paper with no abstract on record can only be
named under a "Further reading" heading: it cannot support a statement,
because nothing about its content was checked. Each item there names the
paper and why it may be worth reading (its topic, setting or method, or the
question it asks), never what it found: "[@chen2018mentoring]: a mentoring
program in rural middle schools" and "[@chen2018mentoring]: examines whether
mentoring improves attendance" pass; "[@chen2018mentoring]: shows that
mentoring raises attendance" and "…: argues that mentoring works" fail (the
full rule: `quick-scan.md` § Step 5: the memo).
Citation counts and venue prestige are reasons a
paper is *visible*, not reasons it is *good*: they may help choose what to read,
never what weight to give (`paper-notes.md` § Signals that are not quality).

## Citation network: snowballing and how papers use each other

Who cites whom, and why, helps find papers that keyword searches miss and shows
how a literature builds on itself. What exists today and what is still to come:

| Capability | Status | How |
|---|---|---|
| **Forward snowballing** (who built on a paper) | Built | `scholar_search cites <ID> DEST [--years 2020-]`: OpenAlex `cites:` filter, sorted by citations (`--sort publication_date:desc` for newest) |
| **Backward snowballing** (what a paper rests on) | Built | `scholar_search refs <ID> DEST`: OpenAlex's matched references, incomplete and sometimes wrong; check odd entries against the paper's own reference list |
| **Close work with no shared links or keywords** | Built | `scholar_search similar <ID> DEST`: OpenAlex semantic search seeded with title and abstract |
| **Citation sentences and intents** | Built (introduced in `scholar_search` 1.7.0, S4) | `scholar_search refs <ID> DEST --s2-context` or `scholar_search cites <ID> DEST --sort publication_date:desc --s2-context` (opt-in) adds, per paper, up to three sentences in which the citation occurs and Semantic Scholar's own "influential" label (not a quality signal), in the digest and the `.records.json` file; on `refs` also its citation intents (`background`, `methodology`, `result`). On `cites` Semantic Scholar sent no intents on any of 300 rows, and under any sort but newest first few papers match (both observed 2026-11-01). One extra Semantic Scholar call; if it is rate-limited after one retry, the OpenAlex result stands and the row says `context_status: rate_limited`; `elided` means the publisher withheld the list, so no sentences exist. It gives a sample of sentences, not coverage (`scholarly-search` `references/semantic-scholar.md`) |
| **Citation-edge table** | Built (introduced in `lit_corpus` 1.0.0, S4) | `lit_corpus edges ingest` records each citing → cited pair seen by a `cites` or `refs` call (with the call that saw it, and any sentence and intents from a source whose licence allows storing them) in `citation_edges_v{N}`, so a synthesis can say "Smith (2020) uses Lee's (2016) method" with an edge id behind it (`[…]{.lr-edge edges="E012"}`), which `lit_verify report` checks (`lit-corpus.md`) |
| **How a paper uses its key references** | Claim type built (card v3, introduced in `lit_verify` 1.9.0, S4); the reader's protocol for recording it comes with the Literature Review mode (S5) | A `citation_use` claim holds the quoted sentence where the paper cites a key reference, `cites_key` and the relation (`builds_on`, `uses_method`, `extends_result`, `contrasts`, `disputes`, `background`), page-checked like any claim; `edges ingest` copies the relation onto the matching edge. Until the S5 reader asks for these claims routinely, a reader writes them when the review needs them |

**Snowballing practice.** Start from the agreed key papers: one hop forward
with a recent `--years` window, one hop backward. Screen what comes back like
any search result. Snowball calls appear in the search log as their own source
("citation searching"), so counts per round keep them apart from database
searches. Webster & Watson's advice for concept-centric reviews is to search
backward, then forward.

**What citation data can and cannot say.**

- A citation shows that one paper mentions another. On its own it says nothing
  about agreement.
- Semantic Scholar's three intents (`background`, `methodology`, `result`) are
  derived only for papers whose full text it holds ("citation intent data is
  limited to papers for which we have access to the full text"), and none of
  them means disagreement. When a citing paper has no intent or context, that
  means Semantic Scholar lacked its full text, not that the citation is
  unimportant.
- **"Builds on" or "uses the method of"** may rest on an intent or a quoted
  citation sentence. **"Disputes", "contradicts" or "challenges"** may rest
  only on a quoted sentence in which the citing paper takes issue with the cited
  one, read and page-checked by the reader. Never infer disagreement from
  intents, citation counts or Scite tallies.
- **Scite tallies** (`scholar_search scite-tally`: supporting and contradicting
  citation statements) prompt a reader to check a paper; they are never a
  verdict, and Scite's results are licence-restricted, so they never enter a
  corpus table (`scholarly-search` § Licensing and attribution).
- Semantic Scholar data is CC BY-NC with required attribution: a deliverable
  that uses citation sentences or intents from it carries the Semantic Scholar
  credit line.

## Full reads

One reader per paper, offline, from the paper's ingested pages, following
`pdf-reading` (ingest, read every page in order, write the evidence card, run
`lit_verify card`, revise at most twice). For the review the card needs, beyond
the claims behind findings:

- the study design and identification strategy, quoted where the paper states it;
- the main limitations, each a quoted claim with its page (`paper-notes.md`);
- the population, setting, intervention or exposure, comparator, outcomes and
  time, for directness;
- authors' stated open questions (they feed the gap register);
- for each key reference the paper builds on or argues with, the sentence where
  it cites it, as a `citation_use` claim (card v3; `pdf-reading`
  `references/evidence-card.md`).

A card that fails the gate does not supply findings until fixed; a
`FULL_TEXT_PARTIAL` card supplies claims from verified pages only, with the
exceptions listed (`pdf-reading` § Quote anchoring).

## The synthesis

1. Group claims into findings by sub-question or outcome; give each finding an
   id (`F01`, …) and list the claim ids it rests on.
2. Within each finding, lead with the papers given substantial weight and the
   most direct ones; present weaker papers as corroborating or conflicting
   context, labelled.
3. State the finding's certainty and a short reason that names claim ids
   (`certainty-of-evidence.md`). No arithmetic: the reason carries the
   judgment.
4. Word each finding sentence from `certainty-language.yaml` for that level,
   with the verb the designs allow. Saying what several studies show together
   is what a synthesis is for: "Taken together, the three trials indicate that
   tutoring probably improves reading scores [@a; @b; @c]" is a good moderate
   finding sentence (`synthesis-methods.md` § Guardrails).
5. Report individual studies' estimates with their citations; a descriptive
   summary only under its rule (`synthesis-methods.md`). One effect number
   credited to several studies, which nobody computed, fails.
6. Label a citation "per abstract" when every claim the sentence marks from
   that paper comes from its abstract, even if the paper was also read in
   full: the reader must know the statement rests on the abstract.
7. Explain disagreement through design, quality, directness or context before
   calling evidence "mixed".

## Sensitivity reasoning

Whenever a conclusion could rest on weaker papers, say what happens without
them: "Restricting to the three studies given substantial weight, the direction
is unchanged" or "… the positive direction rests on the two studies given
limited weight; certainty is low." This echoes SWiM item 4 (criteria used to
prioritise results) and Murad et al. 2017's advice to weigh each study's size,
risk of bias and impact, and it is usually the most useful sentence for the
researcher.

## Output shape

A sensible default; adapt to the review type.

```markdown
# {Title}: standard review
{date} · standard review · {type} · rounds: {n}

## In short
{3–5 sentences: the main findings in their calibrated wording; what the
researcher can rely on; what is uncertain}

## Findings
### F01 {short label}
[Tutoring probably improves reading scores in the early grades]{.lr-finding fid=F01 claims="W123-c03 W456-c01"} [@smith2021tutoring; @lee2019dosage].
Certainty: moderate. Why: {reason naming claim ids}.
Studies: {table of each study's design, weight, estimate as printed, page}.
Boundary conditions: … Sensitivity: …

## Papers read in full
{one line per paper: design, weight, main limitation}

## Gaps
{gap register summary}

## Methods
Search log, screening counts, key-paper choice and its reasons, what was not
read in full, AI disclosure (what was AI-judged, what code checked).

## References
```

Numbers in the "Studies" table are not checked: `lit_verify report` compares
a number with the checked claims only in a sentence that cites the study
(`lit-verify-report.md` § Known limits). Copy each estimate from its claim,
cite the study in its row, and give the estimate in a cited sentence too when
the finding rests on it.

A marker may wrap onto the next line, but never put a blank line inside it,
from `[` to the closing `}`: a blank line breaks the marker, and `lit_verify
report` fails it (`lit-verify-report.md` § What a deliverable must look like).

## Order of commands

The tool calls behind the workflow, in order, so that `lit_verify report` has
every table it reads. `PROJECT_DIR` is the review project; one command per Bash
call. Flags, inputs and exits: `scholarly-search` for `scholar_search`,
`pdf-reading` for `pdf_ingest` and `lit_verify card`, `lit-corpus.md` for
`lit_corpus`, `lit-verify-report.md` for `lit_verify report`.

1. **Search** (workflow step 2): `scholar_search find`, and later `cites` or
   `refs` (with `--s2-context` when citation sentences help) and `similar`,
   with DEST_DIR under `PROJECT_DIR/lit_search/`.
2. **Build the corpus:** `lit_corpus ingest PROJECT_DIR --round R`; settle any
   `dedup_conflicts` with `lit_corpus dedup decide`.
3. **Screen:** `lit_corpus screen sheet`, then `lit_corpus screen record` with
   the title-and-abstract (`ta`) decisions and, once the key papers are agreed
   and read, a full-text (`ft`) decision for each.
4. **Check references:** `scholar_search verify` and `retractions` for each
   paper that may be cited, then `lit_corpus attach verify` and `attach
   retractions`; `lit_corpus attach decision` records the researcher's call on
   a partial match or a retracted paper.
5. **Read the key papers** (workflow step 5): `pdf_ingest` and an evidence card
   per paper in `PROJECT_DIR/papers/{paper_key}/` (`lit_corpus key` prints the
   key), checked with `lit_verify card` (`pdf-reading`).
6. **Collect the claims and notes:** `lit_corpus claims build PROJECT_DIR`;
   `lit_corpus notes record` for a note the synthesizer or the researcher
   writes or changes. For included papers kept as "per abstract" context,
   record each abstract passage the synthesis quotes with `lit_corpus claims
   abstract` (`lit-corpus.md` § Subcommands): a quotation from an abstract
   that is not recorded as a claim goes to review as an unchecked quote.
7. **Citation links**, if snowballing used `cites` or `refs`: `lit_corpus
   edges ingest PROJECT_DIR`.
8. **Findings and gaps:** `lit_corpus findings record` (it computes any
   descriptive summary or sign test) and `lit_corpus gaps record`.
9. **Export and count:** `lit_corpus export-bib PROJECT_DIR` (and `export-ris`
   if wanted); `lit_corpus counts PROJECT_DIR --round R`.
10. **Write the synthesis** under `PROJECT_DIR/output/` and check it:
    `lit_verify report PROJECT_DIR {synthesis path} --level standard` for each
    round's draft, and with `--kind final` on the version the researcher
    receives (that run checks the cards again).
11. **Close the round:** `lit_corpus manifest PROJECT_DIR --round R`.

## What the researcher should check

- The key-paper list, before the reads: a wrong list makes every later step
  wrong.
- Each paper's weight and its reasons: do the quoted limitations support it?
- Each finding's certainty and its reason: is anything holding it down that the
  reason misses?
- Items marked for review, retracted papers, and any reference `verify` could
  not confirm.
