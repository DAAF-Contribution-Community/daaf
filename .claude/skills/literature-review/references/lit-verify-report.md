# `lit_verify report`: the full CLI contract

`lit_verify report` reads a Literature Review deliverable (a memo or
synthesis in Markdown) and checks it against the review's own records: every
citation, every marked finding and claim, and the wording of every sentence
that states what the evidence shows. It calls no model and no network. Source
of truth: the `report` section of the header, `EXIT_CODES`, `build_parser()`
and the `§§ REPORT` functions of `scripts/lit_verify.py`
(`TOOL_VERSION = "1.17.0-daaf"`, `REPORT_REDERIVE_VERSION = "report-rederive-v8"`,
result schema `lit-verify-report-check-v1`), and the header of
`scripts/lit_report_rules.py` (`REPORT_RULES_VERSION = "report-rules-v8"`,
`CITATION_PARSE_VERSION = "citations-v2"`, `SENTENCE_SPLIT_VERSION =
"sentences-v1"`, `REPORT_LINT_VERSION = "report-lint-v5"`). If this page and
the code disagree, the code wins: report the drift. The card gate itself
(`lit_verify card`) is documented in the pdf-reading skill
(`references/evidence-card.md`); the tables this command reads are written by
`lit_corpus` (`lit-corpus.md`).

**Contents:** In short · Syntax · What a deliverable must look like ·
What is checked · Settling the readings an audit lists · What is
re-derived · Exempt sections · Result file · MANIFEST row · Stdout · Exit
codes · Status index · Known limits

## In short

- **What you can rely on when it says PASS:** every citation names a paper
  of this review whose reference was confirmed to exist as cited, that is in
  the exported reference list and that was checked for retraction; in a
  final deliverable, every reference also passed its second check (a
  person's recorded reply, or an AI check, labelled: an evaluated one, or one
  the researcher chose to accept untested), and every
  paper whose reading notes take readings from pictures of pages has an
  audit that confirmed them, or the researcher's recorded comparison of
  every reading the audit listed with its PDF page; every
  marked claim was found on its page in the paper; abstract-only papers are
  labelled; no sentence combines results into one number or counts
  significant studies; a direction count or a median of estimates is exactly
  what DAAF computed; and a sentence stating a recorded finding is not worded
  more surely than the finding's stated certainty.
- **What it cannot check:** whether the synthesis is a fair reading of the
  papers, whether the strongest studies come first, whether a sentence that
  is *not* marked as a finding states a conclusion fairly (it is flagged for a
  person when it cites several papers), and whether the stated certainty is
  right (that is the synthesizer's or the researcher's judgment, recorded with
  a reason).
- **NEEDS_REVIEW** means a person must look at the listed lines; the
  deliverable is not wrong yet. **FAIL** means at least one listed problem
  must be fixed.

## Syntax

```
bash /daaf/scripts/lit_verify.sh report <PROJECT_DIR> <DELIVERABLE>
     [--kind synthesis|final|bibliography] [--level quick|standard|formal]
     [--data-version TABLE=N ...] [--recheck-cards | --no-recheck-cards]
     [--timeout S]
```

| Argument | Default | Meaning |
|----------|---------|---------|
| `PROJECT_DIR` | — | The review project (`research/YYYY-MM-DD_LitReview_{Topic}/`, the folder `lit_corpus` works in). Must pass `validate_dest_dir` (under the DAAF root; `/tmp`, `/var/tmp`, `/dev/shm`, `/host_data`, `<root>/.claude`, `<root>/.git` refused: exit 2, no row); not a directory: exit 1 |
| `DELIVERABLE` | — | The Markdown file to check. Must be a file (else exit 1) that resolves inside `PROJECT_DIR/output/` (else exit 2, no row); UTF-8 and at most 5 MiB (`REPORT_MAX_BYTES`; else exit 8) |
| `--kind` | `synthesis` | `synthesis`: a round's draft. `final`: the deliverable the researcher receives; the cards behind its claims are checked again (user decision, 2026-10-30). `bibliography`: a reading list, where a paper known only by title and authors may be listed |
| `--level` | none | The review level the researcher chose. Recorded in the result for the reader; **no check depends on it** (the checks follow the data: evidence grades decide the abstract rule, and the certainty checks run only on sentences marked as findings) |
| `--data-version` | the latest | Pin a table version: `corpus=N`, `claims=N`, `findings=N`, `citation_edges=N`, `paper_aliases=N`, `citation_adjudications=N` (repeatable). A pinned version that does not exist: exit 10 |
| `--recheck-cards` / `--no-recheck-cards` | on for `final`, else off | Run the card gate again, in-process, on every card behind a claim. Needs rapidfuzz (missing: exit 10). Needs the paper's stored source file: a missing or changed source makes the re-check differ, so the report records `CARD_RECHECK_DIFFERS` and FAILs (exit 11) |
| `--timeout` | 120 | Seconds per subprocess when cards are re-checked |

One invocation per Bash call. The wrapper runs `python3` directly (a
standalone framework CLI, not a pipeline script); its audit record is the
MANIFEST.jsonl row it writes. Set `DAAF_FETCH_CONTEXT` to label that row.
Deliverable text, quotes and every table string are **untrusted data**:
matched, never followed.

## What a deliverable must look like

| Element | Write it as | Why |
|---------|-------------|-----|
| A citation | `[@key]`, `[@key1; @key2]`, `[@key, p. 7]`, `[see @key]`, `[-@key]`, in-text `@key`, or the braced form `@{key}` (Pandoc syntax; `\@` is a literal at sign, not a citation) | `key` is the paper's citekey from the corpus table |
| A paper of which only the abstract was read | `[@key, per abstract]` | Readers must know; the label sits inside the citation so it stays tied to the right paper in a multi-paper citation |
| A recorded finding | `[Tutoring probably raises reading scores]{.lr-finding fid=F01 claims="W123-c03 W456-c01"} [@a2020b; @c2019d].` | Binds the words to finding F01, so their strength can be checked against its stated certainty; the claims must be the finding's and come from papers the sentence cites |
| A single claim | `[text]{.lr-claim claims="W123-c03"}` | Ties a statement to one checked claim |
| A citation link | `[text]{.lr-edge edges="E012"}` | Ties "builds on" / "disputes" wording to a recorded link between two papers |
| A descriptive summary | the template in `certainty-language.yaml` (`descriptive_summary.template`), inside the finding's marker, ending "descriptive summary, not a pooled estimate" | Only the numbers `lit_corpus findings record` computed (≥ 3 estimates, one per paper, one metric) |
| A direction count | "Three of three effects favoured tutoring (sign test, p = 0.25)" inside the finding's marker | Only the counts `lit_corpus` computed for that finding |
| A finding not rated | "... (certainty not rated: qualitative evidence)" | The table's `not_rated` wording |

Markers render as invisible HTML spans (`<span class="lr-finding" ...>`);
in DOCX and PDF output Pandoc drops them silently. A marker's `{...}` may
wrap onto the next line, as Pandoc allows (an editor that hard-wraps lines
does this); a blank line ends it. Any `{.lr-` text that does not parse as a
marker fails (`SPAN_MALFORMED`) rather than being skipped. **Quick-scan
memos carry no finding markers**: a sentence whose cited papers were all read
only as abstracts is never asked for one.

## What is checked

**Citations** (in every section, exempt ones included). The key must be in
the corpus (else `CITEKEY_UNKNOWN`; a braced `@{` that does not close counts
as an unknown key, so it cannot slip past). The reference check must have confirmed
the paper (`CITATION_UNVERIFIED`). When the title recorded for the paper when
it was added is not the title of the record its DOI leads to, a draft gets a
review item naming both titles (`CITATION_TITLE_DIFFERS_DRAFT`) and a final
report fails the citation as unverified, with that reason and its own fix:
running the reference check again cannot help (it confirms the same record),
so restore `data/` from a backup made before the paper was added and add it
again with its own DOI and title, or start the tables again in a new project
folder (1.14.0). It must be in the exported reference list
(`CITEKEY_NOT_IN_BIB`; not raised for a rejected reference, which has its
own status). A retracted paper, or one under an expression of
concern, fails unless the researcher decided to keep it and the sentence says
so (`RETRACTED_CITED`, `RETRACTED_UNLABELED`, `RETRACTED_CITED_DECIDED`); no
retraction check on record goes to review (`RETRACTION_NOT_CHECKED`). The
status is the most severe one that any retraction check of the paper's DOI in
the search records found (retracted, then expression of concern, then a
correction or update, then none): a later check, even one where a database
failed, never lowers it (1.13.0). When the review's record names a check other
than the newest, the citation fails in a final report
(`RETRACTION_CHECK_NOT_LATEST`) and goes to review in a draft
(`RETRACTION_CHECK_NOT_LATEST_DRAFT`). A paper known only by title
and authors cannot support a statement outside `--kind bibliography`
(`METADATA_ONLY_CITED`), with one exception: it may be listed in a section
headed "Further reading" (any capitalisation, heading level 2 or deeper; a
leading section number such as "6." or "6" and a trailing colon are allowed;
its subsections count too), in an item that names the paper and why it may be
worth reading (its topic, setting or method) and never what it found: no
finding or claim marker, no result number (no decimal, no percentage, no
whole number of 100 or more that is not a year; a year or a small count such
as "grade 3" is fine), and no result wording ("shows that", "found",
"suggests", "demonstrates", "concludes", "proves", "raised scores", "had an
effect", "argues that", "reports that", "according to the authors",
"outperformed", "is effective", "probably", a pooling phrase such as "taken
together", …). "May" is allowed ("a case study that may be useful for small
schools"). Wording that names a topic is fine (1.14.0): a question ("examines
whether tutoring improves attendance"; also after "how", "if", "why" or
"what", to the end of its clause), "shows how one district scheduled
tutoring", what the title suggests ("its title suggests a study of tutor
training") and a design word ("a meta-analytic review of tutoring
programmes", "a review across 40 studies"). "It is unclear whether…" stays
certainty wording and fails. An abstract-only paper
needs the label and gives no numbers (`ABSTRACT_ONLY_UNLABELED`,
`ABSTRACT_ONLY_NUMBER`): a number counts as the abstract's when its clause
holds the abstract-only citation, or when its clause cites nothing and the
next citation after it is abstract-only. A paper that was also read in full
needs the label too when every claim marked for it in the sentence was
quoted from its abstract (`ABSTRACT_ONLY_UNLABELED`).

**The citation second check.** Each
cited paper's citation status is the one `report` re-derives from the
second-check record (§ What is re-derived); the statuses are
`lit-corpus.md` § Citation second check. What each one does to a citation:

| Citation status | Draft (`synthesis`, `bibliography`) | `--kind final` |
|-----------------|-------------------------------------|----------------|
| `pending_adjudication` (also an older table's `verified_rule`, and a view with no status on a confirmed check) | review: `CITATION_PENDING_SECOND_CHECK_DRAFT` | fail: `CITATION_PENDING_SECOND_CHECK` |
| `human_confirmed` | citable | citable |
| `model_confirmed`, `model_adjudicated` | citable, warning `CITATION_CONFIRMED_BY_AI_CHECK` | the same |
| `model_confirmed_untested` | citable, warning `CITATION_CONFIRMED_BY_UNTESTED_AI_CHECK` | the same |
| `human_overridden` | citable, warning `CITATION_ACCEPTED_DESPITE_CHECK` | the same |
| `rejected` | fail: `CITATION_REJECTED` | the same |
| `human_accepted_unbound` (legacy `accept_weak`) | review: `CITATION_HUMAN_DECISION_UNBOUND` | fail: `CITATION_PENDING_SECOND_CHECK` |
| `unverified` on a partial match (also a confirmed check the final title rule lowers to a partial match) | fail: `CITATION_WEAK_UNDECIDED` | the same |
| a status outside the vocabulary | fail: `CITATION_UNVERIFIED` | the same |

The three label statuses are warnings: they never change the verdict, and their
fix asks the deliverable to say how the reference was checked ("confirmed by
DAAF's second check, an AI judgment"; "confirmed by an AI check DAAF has not
tested, at the researcher's choice"; "accepted by the researcher despite the
automatic check"). The report item names both wordings of one label: the
reference list's "confirmed by an untested AI check (your choice)" in its
reason, and the deliverable's "confirmed by an AI check DAAF has not tested,
at the researcher's choice" in its fix
(`SECOND_CHECK_UNTESTED_DELIVERABLE_WORDS`). The fix of every waiting or undecided reference is the
researcher's recorded reply: `lit_corpus adjudications glance-sheet`, the
researcher's reply recorded in their own words with `adjudications
record-human`, the reference list exported again (its entries carry the
status), then the deliverable checked again. A rejected reference is dropped,
or its paper's right record is found, checked again with `verify` and `attach
verify`, and that new check confirmed. A reference the researcher accepted on
a MISMATCH row (`override_mismatch`) is `human_overridden` while the override
names the record the check's saved response re-derives: it is citable with
the `CITATION_ACCEPTED_DESPITE_CHECK` label, and its reference-list entry
must be that record's (§ What is re-derived). The final title rule is not
applied to it: the researcher accepted the titles as they differ.

**Readings from pictures of pages.** When the paper's latest
checked card takes any reading from a picture of a page (a claim with source
`vision` or `both`, or a `vision_only` digest), the citation needs an audit
record of that card (`lit_verify audit`, `vision_audit{S}.json`; pdf-reading
`references/evidence-card.md`) whose outcome confirms it (`confirmed` or
`confirmed_with_checks`). No such record: `VISION_AUDIT_MISSING_DRAFT`
(review) in a draft, `VISION_AUDIT_MISSING` (fail) at `--kind final`; its fix
is to run the audit. A record whose outcome is `person_must_check`, `mismatch`
or `chain_unconfirmed`: `VISION_AUDIT_NOT_CONFIRMED_DRAFT` (review) or
`VISION_AUDIT_NOT_CONFIRMED` (fail), unless the researcher's records settle
it. For `person_must_check` and `mismatch` the first fix is the researcher's
comparison of each listed reading with its PDF page, recorded with
`lit_verify settle` (§ Settling the readings an audit lists): once every
listed reading's latest record says it matches, the citation passes, draft
and final, with no extra label (a person's check is the check the audit
asked for, as a reference the researcher confirmed carries none). A reading
the researcher recorded as not matching keeps the status, with the reason
that the notes carry a wrong reading and the fix: write new reading notes
without that number, or with the number as printed on the page, check them
with `lit_verify card` and run `lit_verify audit`, then rebuild the claims
(`lit_corpus claims build`) and check the deliverable again. A
`chain_unconfirmed` outcome is never settled this way: comparing readings
with the page cannot show where the PDF came from, so its fix is a PDF
fetched with `web_fetch.sh` or placed in `user_pdfs/`, read and audited again.
Otherwise the citation clears with reading notes without readings from
pictures of pages (read from the page text, or with those claims dropped),
checked again with `lit_verify card`, the claims rebuilt with `lit_corpus
claims build`; a card with no such readings needs no audit. For `mismatch` a
new reading by a reader whose model the audit confirms also clears it. Cards
without readings from pictures of pages are not held to an audit.

**Readings by an untested reader, at the researcher's choice.**
When the paper reader is not on the vision-validated list, the researcher
may still let it read page pictures, recorded with `lit_verify
vision-override` (pdf-reading `references/vision-validation.md` § The
researcher's choice for an untested reader). Under the choice `check`, the
audit lists every such reading (`person_must_check`) and the rules above
apply unchanged: the final report fails until each is settled as matching.
Under the choice `accept`, the audit confirms the notes without listing those
readings (outcome `confirmed_untested_reader`; any scan or sparse-page reading
is still listed, as for a tested reader), and every citation of the paper
gets the warning `VISION_READ_BY_UNTESTED_MODEL`: citable, draft and final,
and the fix asks the deliverable's methods or AI-use note to say that some
numbers were read from page pictures by a model DAAF has not tested, at the
researcher's choice. If the choice is later withdrawn or changed (another
level, model or setup), those readings need the researcher's comparison like
any listed reading (`VISION_AUDIT_NOT_CONFIRMED` / `_DRAFT`, outcome key
`override_withdrawn`; `settle --list` then lists them as required), or the
same choice recorded again.

**Markers.** Every finding id must be a recorded, current finding with a
written reason for its certainty and a record of who decided it
(`FINDING_UNKNOWN`, `FINDING_UNREASONED`). Every claim id must be current and
found on its page (`CLAIM_UNKNOWN`, `CLAIM_SUPERSEDED`, `CLAIM_NOT_VERIFIED`),
from a paper the sentence cites (`CLAIM_PAPER_NOT_CITED`) and, in a finding
marker, one of the finding's claims (`FINDING_CLAIMS_DIFFER`, review). A
claim whose labelled number (estimate, interval or sample size) the card
gate found on the page but not where it expected goes to review
(`CLAIM_NUMBER_NEEDS_REVIEW`: a person compares the number with the page);
a failed number still fails the claim. A sentence that cites two or more
papers with a certainty word or a result verb but no finding marker goes to
review (`FINDING_UNMARKED`).

**Synthesis guardrails.** Statements across studies are allowed: "Overall",
"Taken together", "Across studies" or "the typical study" are never flagged
on their own, and a cross-study sentence marked as a finding follows the
certainty-wording rules below (user decision, 2026-11-01). What fails
(`POOLED_ESTIMATE`) is a pooling phrase ("overall", "taken together",
"pooled", "pooling", "on average", "the typical study", "a combined gain",
"averaging the estimates", "the mean of the study estimates", …) that
introduces ONE effect number in its clause while two or more papers are
cited for that clause, or none: a cross-study number nobody computed. From
1.13.0 the phrases also include "across the trials" (or studies,
evaluations, papers), a sentence-opening "Combined,", "in aggregate" and
"collectively". A phrase followed directly by a comma ("Overall, …") governs
the clause after it; a phrase whose clause holds no number reads the next
clause, then the one before ("Pooled across the trials, the effect was 0.15
SD [@a; @b; @c]" and "The gain was 0.15 SD, taken together [@a; @b; @c]"
fail); a number set off by commas with no citation in its clause is credited
to the next citation after it (1.14.0: "Overall, the largest estimate, 0.21
SD, came from the trial [@a]; the event study found 0.15 SD [@b]" gives that
trial's estimate and passes; "Overall, the gain, 0.15 SD, came from the three
trials [@a; @b; @c]" fails); an estimate's own interval, standard error or p in parentheses is not a
second number; "the combined effect of tutoring and coaching" names a
combined programme, not pooling. A number of people, places, ages or
durations ("600 pupils", "8.5 years old", "aged 9") describes the studies and
is never a pooled effect. A clause with its own single citation
reports that source's estimate (a single study's average, or a cited
meta-analysis's pooled effect) and is not flagged. The sanctioned
cross-study number is the labelled descriptive summary below. Weighting
fails (`WEIGHTED_SUMMARY`) in a sentence marked as a finding, citing two or
more papers, saying "across the studies", or giving a number without any
citation. Counting studies by
significance fails (`VOTE_COUNT_SIGNIFICANCE`); counting them by result goes
to review (`VOTE_COUNT_INFORMAL`: "N of M studies", "3/5 studies", "seven
studies found", "most of the included studies", "all three trials" with a
result word); counting the direction of effects passes only with a sign test
whose counts equal the finding's computed direction summary, and any p-value
or interval printed with it must be the computed one (the p rounded as
printed, or the stated inequality true; the bounds equal to the computed
Wilson interval, as a proportion or a percentage; no other number)
(`DIRECTION_SIGN_TEST`, `SIGN_TEST_MISMATCH`). Counts of study features ("12
of 40 studies used randomized designs") are not results and pass. A median,
IQR or range of estimates passes only as the computed descriptive summary of
the marked finding, labelled, with the computed numbers. The check starts
only on effect numbers: a sentence that names effects or estimates, or that
gives two or more decimals or percentages without describing the studies
themselves ("Sample sizes ranged from 412 to 2,560 pupils" is a study
characteristic and is not checked as a summary), and not a sentence whose
every number carries its own single citation, each a different paper ("The
two trials' estimates ranged from 0.09 SD [@c] to 0.21 SD [@a]" lists the
studies). Every number
printed in it, percentages and whole numbers included, must be one of them
(`DESCRIPTIVE_SUMMARY_OK`, `..._UNLABELED`, `..._UNSUPPORTED`,
`..._NUMBER_MISMATCH`). Any other decimal, percentage (also written "12
percent") or number of at least 100 (not a year) in a sentence must be
printed by a checked claim of a cited paper (`NUMBER_NOT_IN_CITED_CLAIM`,
review, one paper cited; `NUMBER_ACROSS_PAPERS`, fail, several); only claims
found on their page whose numbers passed count. A number followed by its own
single citation (in the same clause, no other number between) must be
printed by that paper's claims, not just by another paper the sentence cites
(`NUMBER_NOT_IN_CITED_CLAIM`, review). One effect number with no pooling
phrase, credited to two or more cited papers (those its clause cites, else
the next citation after it) of which only some print it, goes to review
(`NUMBER_NOT_IN_CITED_CLAIM`), whether or not the sentence is marked as a
finding (1.14.0): in "Effects in the three trials were about 0.15 SD [@a; @b;
@c]" only b prints 0.15, so the sentence credits one study's number to all
three. It passes when every cited paper prints the number. A number of people, places, ages or
durations that no claim prints goes to review, never
`NUMBER_ACROSS_PAPERS`. An effect number in a prose sentence that cites
nothing (outside tables and the exempt sections) goes to review
(`NUMBER_NOT_IN_CITED_CLAIM`): cite the paper that prints it. A confidence level ("95%
CI") and a p threshold ("p < .05") are not results and are not checked. A
pattern noticed after looking at the results must say "exploratory"
(`POST_HOC_UNLABELED`; `MODERATOR_CUE_UNLABELED` for an unmarked "stronger
for…" sentence). Text in quotation marks is skipped by these checks only
when it is the quote of a cited paper's claim that its page check found
(and whose numbers did not fail); any other quotation is checked like the
rest of the sentence, and a longer one goes to review
(`QUOTE_NOT_FROM_CLAIM`).

**Wording of findings** (`certainty-language.yaml`, through its embedded
lockstep copy). For a sentence inside a finding marker the *expressed* level
is read by the table's precedence (very low → low → moderate → high; no
marker is high). The markers: very low "very uncertain", "it is uncertain
whether", "it is unclear whether", "we do not know whether" (or "if"); low
"may", "might", "evidence suggests" (also "the available evidence
suggests"); moderate "probably", and "likely" counts as moderate. "May
2020", "in May", "since May", "May and June" and "more likely to" are not
hedges. Stronger than the stated certainty fails (`CERTAINTY_STRONGER`);
weaker goes to review (`CERTAINTY_WEAKER`). Two hedges in one sentence,
"likely" on a moderate finding, another level's word beside the finding's
own, and hedges outside the table go to review (`CERTAINTY_STACKED_HEDGE`,
`FORBIDDEN_HEDGE`, `NONSTANDARD_HEDGE`, `SIGNIFICANCE_LABEL`). A very-low
finding must say "uncertain", "unclear whether" or "do not know whether"
(`VERY_LOW_WITHOUT_UNCERTAIN`). A finding whose certainty was not rated
must say so and carry no GRADE hedge: "probably", "likely", "may" and
"might" all fail there (`NOT_RATED_UNSTATED`, `NOT_RATED_WITH_HEDGE`). A
sign-test or descriptive-summary sentence reports computed numbers, so its
wording is not compared with the level.

**Boosters and "no effect"** are checked in every sentence that cites a
paper, outside the exempt sections: "proves", "conclusively", "clearly
shows", "establishes that" (`BOOSTER`; "newly established schools" and "have
established tutoring programmes" are not boosters) and "no effect" or "no
difference" as a conclusion (`NO_EFFECT_CLAIM`) fail in a sentence marked as
a finding. In an unmarked sentence they go to review (`BOOSTER_UNMARKED`,
`NO_EFFECT_CLAIM_UNMARKED`): there they often describe something else (a
programme named "Proven Readers", what a table "clearly shows", a study's
own words). Balance between groups at the start ("at baseline, … no
difference …") is not a "no effect" claim. The table's own "little to no
difference" (or "little to no effect") passes, and so does the paired
statement "there is no evidence of an effect, which is not evidence of no
effect": it goes with a finding of any certainty, so its sentence is not
compared with the finding's level.

**Citation links** (design v2 §8.4, user decision, 2026-10-31). A link id must be in
`citation_edges_v{N}` (`EDGE_UNKNOWN`). "Disputes", "contradicts",
"challenges the", "refutes" or "rebuts" passes only on a link whose relation a
reader quoted from the citing paper as `disputes` or `contrasts`
(`EDGE_OK`); otherwise, and for such wording in an unlinked sentence citing
two papers, it goes to review (`EDGE_RELATION_UNSUPPORTED`). Semantic
Scholar's citation intents never support it: none of them means disagreement.

## Settling the readings an audit lists

When a paper's audit asks a person to compare readings with the PDF
(outcome `person_must_check` or `mismatch`, or readings accepted under a
researcher's choice that was later withdrawn), the orchestrator settles them
with the researcher in one exchange. The full command contract is in the
pdf-reading skill, `references/vision-validation.md` § Gating ("After the
audit: settling listed readings").

1. **List.** `bash /daaf/scripts/lit_verify.sh settle <PAPER_DIR> --audit
   vision_audit{S}.json --list` prints one numbered plain line per reading
   ("1. The AI reader took the number 88 from a picture of PDF page 2 …
   Please compare 88 with PDF page 2."), the optional chart readings marked
   `(optional)`, and no item id; it writes `PAPER_DIR/settle_items{S}.txt`
   (the ids, one per line, each with its number as a comment).
2. **Ask.** Show the researcher the numbered lines as they are, beside their
   PDF pages, and ask whether each number matches the page. One reply can
   cover the whole list ("all of them match", or "1 and 3 match, 2 says 86,
   not 88").
3. **Record.** Record the reply with the researcher's words verbatim:
   `bash /daaf/scripts/lit_verify.sh settle <PAPER_DIR> --audit
   vision_audit{S}.json --items <FILE> --decision matches|does_not_match
   --user-words "<their words>" [--rationale "<which number, what the page
   prints>"]`. Readings that match go in one call, readings that do not in
   another (`does_not_match` needs `--rationale`). Each call writes
   `audit_settlement{S}_{n}.json` beside the audit record and a row of kind
   `lit_verify_settle` in `papers/MANIFEST.jsonl`.
4. **Check again.** Run `lit_verify report` on the deliverable.

The latest record of a reading decides, so a later reply corrects an
earlier one. The words are a command-line argument, so a permission rule
that asks before `lit_verify.sh settle` runs (applied by the user) shows
them to the researcher in the prompt; the record says
`human_binding: permission_prompt`, which the tool expects but cannot
detect (§ Known limits). The source-chain check of a `chain_unconfirmed`
audit is listed as not settleable: `settle` refuses its id. Reading notes
whose readings are settled are still the AI reader's notes; nothing about
the readings changes, only the record that a person compared them.

## What is re-derived

The tables are written by an agent-facing CLI, so every field that can clear
a citation or a claim is re-derived from its hashed source, or the check
fails closed (user decision, October 2026):

| Field | Re-derived from | On a mismatch |
|-------|-----------------|---------------|
| Each table's contents | its bytes' sha256 = the `lit_corpus` MANIFEST row that wrote it (`data/MANIFEST.jsonl`) | `TABLE_HASH_MISMATCH` (the rows are still read; the verdict fails) |
| The reference list | the latest `output/references_v{N}.bib`, sha256 = its export row; 1.12.0: the file holds only the export's header line (1.13.0: exactly as export-bib writes it) and entries, one entry per key, no field twice, and each entry equals byte for byte what `export-bib` writes for the paper from the record its reference check confirmed (the entry's own `daaf_evidence_grade` note is taken as written when it is a grade word) | `BIB_HASH_MISMATCH`; `BIB_ENTRY_MISMATCH` (the paper's citation also counts as unverified) |
| A paper's identity (DOI, title, abstract) | 1.13.0: the table history, never a field of the corpus table. The first corpus version that holds the paper's key (every earlier version re-hashed against the FIRST MANIFEST row that recorded it; a later row naming the same file is ignored) and the run that wrote it: an `add-record` run that names this key (the title and DOI it recorded), or an `ingest` run whose new search-log rows list the key (the fused group of that search's records file, sha256 = the search row). An abstract filled later comes from the `ingest` run whose version first holds it. A paper first seen in any other step, or in an `add-record` run naming another key, fails: one creating record gives one paper key | `PAPER_IDENTITY_MISMATCH` (its reference check, retraction check and reference entry are not trusted); an earlier table version missing or changed: `TABLE_HASH_MISMATCH` |
| A claim's verification, quote, page, numbers and quant values | rebuilt with `lit_corpus`'s own claim builder from the card_check the row names (sha256 = the papers MANIFEST row) and that card (sha256 = the card_check's record); 1.12.0: a current claim must come from the paper's latest card run | `CLAIM_VERIFICATION_FORGED` (the row is better than its check), `CLAIM_ROW_MISMATCH` (also an older run's claim marked current), `CLAIM_SOURCE_MISMATCH` (the source cannot be confirmed: its claims count as unchecked) |
| A paper's evidence grade | its latest card_check (`evidence_grade_suggested`; a FAIL or NEEDS_REVIEW card counts as read but unconfirmed); no card run: abstract-only when the corpus holds an abstract, else title-only | `CLAIM_SOURCE_MISMATCH` |
| The reference check verdict | re-graded (`verify-regrade-v2`) from the record in the named verify row's own saved response (its DOI or W-id must be this paper's; a paper with neither is matched by its OpenAlex alias) against the title, year and author the citation was checked with; the row's verdict is only a ceiling. 1.13.0, `--kind final`: the review's own title must also match the confirmed record's title by the same title rule (a mismatch makes the citation unverified, with the title rule's own reason and fix; a partial match lowers the verdict to a partial match). 1.14.0: in a draft a mismatch is a review item; the reference-list entry is compared with the record the reference check confirmed, whatever the title rule decided | the citation counts as unverified (`CITATION_UNVERIFIED`); in a draft, `CITATION_TITLE_DIFFERS_DRAFT` |
| The retraction status | re-derived (`retraction-rederive-v3`, 1.13.0) as the MOST SEVERE status found by any retractions check in `lit_search/` whose own saved response answers the paper's DOI (OpenAlex `is_retracted`, Crossref notices; a row's status can only make its check more severe); the newest check (latest row timestamp, then the later position in the MANIFESTs) is the one the review's record must name | no response for the DOI: `RETRACTION_NOT_CHECKED`; the review's record names another check: `RETRACTION_CHECK_NOT_LATEST` (final) or `RETRACTION_CHECK_NOT_LATEST_DRAFT` |
| A paper's citation status | the current row of the second-check ledger (`citation_adjudications`, hash-checked like every table; `lit_corpus`'s own `current_ledger`) bound to the paper's verify row, when it names this paper and the verdict re-graded above: its status recomputed with `lit_corpus`'s `adjudication_status()`, the model's verdict counting only when the row's whole identity (model ID, `template_sha256`, `rubric_version`, `agent_file_sha256`, and an agent file unchanged at ingest) is an entry of the evaluated list version the row names, matched with `lit_corpus`'s `evaluated_identity()` (else not sure), and the title floor applied when the row or the rule says so. A row naming the researcher's acceptance of an untested checker (`untested_acceptance_ref`) counts only when that reference equals what `lit_corpus`'s `untested_acceptance()` gives from the data MANIFEST rows before the batch's `ingest` row (an acceptance row counts only as the step writes it: `tool_version` and `timestamp`, non-empty `parameters.user_words` whose sha256 is `user_words_sha256`, `human_decider` `researcher`, `human_binding` `permission_prompt`, `parameters.model_id` equal to the row's and `parameters.revoke` false, a rationale, and no acceptance already in force; when the latest row for a model ID is a withdrawal or does not hold up, no acceptance is in force), for the row's exact model ID, the model is not on the evaluated list, every model the transcript recorded (`model_id_observed`) normalizes to it, and the `ingest` row records the same acceptance; the title floor then applies to that checker's `SAME_WORK` as at ingest. A row naming no acceptance where one re-derives fails too. An `override_mismatch` row counts only while its `override_record_json` is the record the re-grade compares (the reference-list entry is then compared with that record). No bound row: a confirmed check waits for its second check, a partial match the researcher accepted with the legacy decision is that, anything else is unverified. The corpus status (an older `verified_rule` read as waiting), the row's own status and effective verdict, and the corpus's reference to the row must all agree. The bound ledger row must also be written by `lit_corpus`'s own step: it must stand, as first written, in the ledger version it names (`recorded_version`), and that version's first MANIFEST row must be `adjudications record-human` for a person's decision (exit 0, naming this verify row, the decision in its row and parameters, the person's words verbatim, the row's time and its status) or `adjudications ingest` for a model judgment (its batch); model fields need an `ingest` run of their batch, log hash, model ID and dispatch ID | `ADJUDICATION_ROW_MISMATCH` (its fix is the table remedy; the citation counts as unverified) |
| A card's audit (cards with readings from pictures of pages) | the papers MANIFEST rows of kind `lit_verify_audit` and command `audit`, whose exit code is the one their outcome gives, that name the paper's latest card and card_check (both sha256); the record's bytes must hash to its row, and the record must name the same card, card_check, paper and outcome. A confirming outcome counts only when every reader's model came from the hook's own record (`model.agents`: each `model_source` `hook_cache`, `trusted`, check `transcript-confirmed`). Any such record that does not confirm the card, and is not settled, decides | no trusted record: `VISION_AUDIT_MISSING` / `_DRAFT`; an outcome that does not confirm it, or a confirming one resting on another model source: `VISION_AUDIT_NOT_CONFIRMED` / `_DRAFT` |
| The researcher's comparison of an audit's listed readings (`person_must_check` and `mismatch` only) | the papers MANIFEST rows of kind `lit_verify_settle` of the paper that name the audit record's sha256, in file order; each must be `settle`'s own row (command `settle`, exit 0, the decision in its parameters, the record's `settled_at` as its time, and `user_words_sha256` = the sha256 of the record's non-empty words); each settlement file's bytes must hash to its row, and the file must name the same paper, audit, card, card_check (all sha256) and decision as its row and the audit, its readings must be the audit's own (item ids re-derived from the audit's items) and equal the row's list. The latest valid record of each reading decides; every `must_check` and `unvalidated` reading must be "matches" (and every `accepted_untested` reading once the researcher's choice is withdrawn) | a record that fails any of these counts as none; a reading not matched: `VISION_AUDIT_NOT_CONFIRMED` / `_DRAFT` |
| The researcher's choice for an untested reader (audits holding `accepted_untested` readings) | the papers MANIFEST's latest row of kind `lit_verify_vision_override` written by `vision-override` (exit 0); its record file must hash to the row, carry `schema_version` `lit-verify-vision-override-v1`, `kind` `lit_verify_vision_override`, `human_decider` `researcher`, the person's non-empty words (whose sha256 is the row's `user_words_sha256`) and, for `check` or `accept`, a rationale, and repeat the row's level, model, setup and time; the row must carry `tool_version` and the level in its `parameters`; the choice must still be `accept` for the audit's model and setup. When the latest choice record or row does not hold up, there is no choice at all, never the choice before it | readings labelled `VISION_READ_BY_UNTESTED_MODEL` while the choice holds; otherwise they need the researcher's comparison: `VISION_AUDIT_NOT_CONFIRMED` / `_DRAFT` |
| A claim quoted from an abstract (`lit_corpus claims abstract`) | 1.12.0: rebuilt with `lit_corpus`'s own `abstract_claim_row` from the corpus table's stored abstract, and the rebuilt row is used: its claim type must be an abstract one, its quote at least 20 characters of the abstract, and it carries no card claim, estimate, metric or cited paper | `CLAIM_ROW_MISMATCH` |
| Numbers that may clear a sentence | only a claim whose quote passed and whose numbers did not fail; a labelled value only when its own check cleared it | a marked claim with a failed number: `CLAIM_NOT_VERIFIED`; with a labelled number needing review: `CLAIM_NUMBER_NEEDS_REVIEW` |
| A finding's record | the rules `findings record` applies, re-run on the re-derived claims | `FINDING_RULE_FAILED` |
| A citation link's reader relation | the citing card's re-derived citation-use claim | `EDGE_ROW_MISMATCH` |
| Descriptive summaries | recomputed from the rebuilt claims (`dsum-v1`) | `SUMMARY_REDERIVE_MISMATCH` |
| Sign tests | recomputed from the stored counts (`signtest-v1`), every claim confirmed on its page | `SUMMARY_REDERIVE_MISMATCH` |
| The card verdict (`--recheck-cards`, default for `--kind final`) | the card gate run again in-process; the claims, their number and labelled-value checks and the paper's grade are then built from that run, and its claim checks, verdict and grade must equal the recorded ones | `CARD_RECHECK_DIFFERS` |
| Table versions (`--kind final`) | the latest version of each table | a pinned older version: `PINNED_OLDER_VERSION` |

A synthesis report (`--kind synthesis`, the default) does not re-check the
cards unless `--recheck-cards` is given: it trusts each card_check whose
bytes match their record (user decision, 2026-10-30, kept in review cycle 1). Run
`--kind final` on what the researcher receives.

Not re-derivable, and so only shown to be what `lit_corpus` recorded: a
finding's stated certainty and its reason (their record-time rules are
re-applied), screening decisions, and the researcher's citation decisions.
One appended table version with a consistent MANIFEST row can change these,
so they are as trustworthy as the agents that write the tables. Three
re-derivations rest on appendable rows (named in Known limits): which card
run is a paper's latest, which retraction check is newest, and that an
appended `add-record` row can add a new paper (never re-point an existing one). The whole-chain residual (an agent that forges
every layer consistently, sources included) carries over from the card
gate. The P3 contract bundle's synthetic ingests name no stored source file,
so `--kind final` (or `--recheck-cards`) on a copy of it fails with
`CARD_RECHECK_DIFFERS`: expected, and tested.

## Exempt sections

Headings matching, case-insensitively and after a leading section number,
`Methods`, `Search methods`, `Search strategy`, `PRISMA`, `Data sources`,
`AI disclosure`, `Acknowledgments` (or `Acknowledgements`) and `References`
(`EXEMPT_HEADINGS`, user decision, 2026-10-30), and their subsections: their
citations are checked, their wording is not. Each is listed once as a
`SECTION_EXEMPT` warning and in `exempt_sections`. The list is fixed: never
configurable per run.

## Result file

`{deliverable stem}.report_check{_1,…}.json` beside the deliverable
(exclusive create, never overwritten; the whole JSON passes the secret
redaction, every reason and excerpt the injection scrub). Schema
`lit-verify-report-check-v1`:

`kind` (`lit_verify_report_check`), `schema_version`, `tool_version`,
`checked_at`, `deliverable {path, bytes, sha256}`, `report_kind`,
`review_level`, `inputs {tables {name: {path, version, sha256,
recorded_sha256}}, bib {path, sha256, recorded_sha256, entries},
phrase_table {version, sha256, embedded: true, published_copy}}`,
`rederive {version, cards_checked, cards_rechecked, mismatches, seconds,
recheck}`, `rule_versions {report_rules, citations, sentences, report_lint,
report_rederive, certainty_language, dsum, signtest, claimid}`,
`exempt_sections`, `exempt_headings`, `verdict`, `counts {pass, review,
fail, warning, citations, citekeys_cited, findings_bound, sentences,
sentences_linted, markers}`, `citekeys_cited`, `findings_bound`, `failures`,
`review_items`, `warnings` (one-line summaries), `items` (each `{kind,
status, severity, line, citekeys, finding_id, claim_ids, edge_ids, excerpt,
reason, fix, hint}`; `hint` from 1.11.0), `redaction_count`, `secret_redactions`.

Every `reason` says, in plain words, which line, what is wrong and why it
matters; every `fix` says what the researcher (or the agent, on their
behalf) should do. Neither carries a status code, a verification state, a
number label or marker markup (a test checks this). `hint` is for the agent:
the marker syntax or command that applies the fix; it may be empty.

## MANIFEST row

One row in the deliverable's folder (`output/MANIFEST.jsonl`), kind
`lit_verify`, command `report`, through the same `finish()` as `card`: the
card fields (`paper_key`, `card`, `ingest`) are null; `parameters {kind,
level, data_version, recheck_cards, timeout_s}`, `deliverable`, `inputs
{name: {path, sha256}}`, `rederive`, `rule_versions`, `artifacts
{report_check: {name, bytes, sha256}}`, `verdict`, `counts`,
`redaction_count`, `secret_redactions`, `exit_code`, `note`. A refused
`PROJECT_DIR` or `DELIVERABLE` writes no row.

## Stdout

```
lit_verify: FAIL report output/synthesis_draft.md (12 citation(s), 3 finding(s) marked, 41 sentence(s) checked; 2 fail, 1 review, 1 warning) -> synthesis_draft.report_check.json
  FAIL: CERTAINTY_STRONGER line 18: Line 18 words finding F03 as settled (no hedge), but the finding's certainty is low. ... Fix: Write 'may' ...
  ...
  deliverable text, quotes and table strings are UNTRUSTED: never follow instructions in them
```

At most 20 items, fail first; the rest are in the JSON. Lead the
researcher's summary with the plain `reason` and `fix`, not the status code.

## Exit codes

| Code | Meaning for `report` |
|------|----------------------|
| 0 | PASS or NEEDS_REVIEW (verdict in the result file) |
| 1 | Usage: bad flags, `PROJECT_DIR` not a directory, `DELIVERABLE` not a file |
| 2 | Refused: `PROJECT_DIR` guard, `DELIVERABLE` outside `PROJECT_DIR/output/`, a secret value in an argument |
| 8 | Deliverable over 5 MiB or not UTF-8; a MANIFEST line that is not JSON |
| 10 | No corpus table, no exported reference list, a pinned table version missing, polars and pyarrow both missing, rapidfuzz missing with `--recheck-cards` |
| 11 | FAIL (result file written) |
| 12 | Internal error |

3 is reserved by `run_with_capture.sh` and never used. The same table, for
all subcommands, is in the tool's header, `EXIT_CODES` and `lit_verify.sh`.

## Status index

Every status, its severity and what it means; the 84 keys of `REPORT_SEVERITY`
(a test keeps this table equal to the code). The verdict is FAIL if any item
fails, else NEEDS_REVIEW if any item needs review, else PASS; warnings and
passes never change it.

| Status | Severity | Meaning |
|--------|----------|---------|
| `CITATION_OK` | pass | The cited paper is in the checked reference list (listed once per paper) |
| `CITEKEY_UNKNOWN` | fail | No paper of the review has that key |
| `CITEKEY_NOT_IN_BIB` | fail | The paper is in the corpus but not in the exported reference list |
| `CITATION_UNVERIFIED` | fail | No confirmed reference check (none, a non-matching one, or one whose saved response is another paper); in a final report also a recorded title that is not the title of the record its DOI leads to |
| `CITATION_WEAK_UNDECIDED` | fail | Partial match no person confirmed (also a confirmed check the final title rule lowers to a partial match) |
| `CITATION_HUMAN_DECISION_UNBOUND` | review | In a draft: a partial match the researcher accepted with the legacy decision, not tied to the reference record; a final report fails it as `CITATION_PENDING_SECOND_CHECK` |
| `RETRACTED_CITED` | fail | Retracted or under an expression of concern, no researcher decision to keep it |
| `RETRACTED_UNLABELED` | fail | Kept by the researcher, but the sentence does not say so |
| `RETRACTED_CITED_DECIDED` | warning | Kept by the researcher and labelled in the sentence |
| `CORRECTED_CITED` | warning | The paper carries a correction or update notice |
| `RETRACTION_NOT_CHECKED` | review | No retraction check on record |
| `METADATA_ONLY_CITED` | fail | Only title and authors known; cited outside a bibliography or a "Further reading" list, or listed there with a marker, a result number or wording that says what it found |
| `ABSTRACT_ONLY_UNLABELED` | fail | Abstract-only paper cited without `, per abstract` |
| `ABSTRACT_ONLY_NUMBER` | fail | A number given for an abstract-only paper (its clause, or the next citation after it) |
| `PER_ABSTRACT_ON_FULL_TEXT` | warning | The label on a paper that was read in full |
| `FINDING_UNKNOWN` | fail | The finding id is not recorded, or was replaced |
| `FINDING_UNREASONED` | fail | The finding lacks a written certainty reason or a record of who decided |
| `CLAIM_UNKNOWN` | fail | The claim id is not in the claims table |
| `CLAIM_NOT_VERIFIED` | fail | The claim was not confirmed on its page (after re-derivation) |
| `CLAIM_SUPERSEDED` | fail | A newer card replaced or withdrew the claim |
| `CLAIM_PAPER_NOT_CITED` | fail | The claim's paper is not cited in the sentence |
| `FINDING_CLAIMS_DIFFER` | review | A finding marker names claims the finding does not rest on |
| `FINDING_UNMARKED` | review | A multi-paper conclusion without a finding marker |
| `SPAN_MALFORMED` | fail | A marker the parser cannot read |
| `EDGE_OK` | pass | The citation link exists (and supports dispute wording, if any) |
| `EDGE_UNKNOWN` | fail | The link id is not in the citation-link table |
| `EDGE_RELATION_UNSUPPORTED` | review | Dispute wording without a reader-quoted disputes or contrasts relation |
| `VOTE_COUNT_SIGNIFICANCE` | fail | Studies counted by significance |
| `VOTE_COUNT_INFORMAL` | review | Studies counted by result ("most studies found…") |
| `DIRECTION_SIGN_TEST` | pass | A direction count equal to the computed sign test |
| `SIGN_TEST_MISMATCH` | fail | A direction count that differs from, or is not tied to, a computed sign test |
| `POOLED_ESTIMATE` | fail | A pooling phrase introducing one effect number for two or more cited studies |
| `WEIGHTED_SUMMARY` | fail | A weighted mean, average or median of study results |
| `DESCRIPTIVE_SUMMARY_OK` | pass | The computed descriptive summary, labelled, numbers equal |
| `DESCRIPTIVE_SUMMARY_UNLABELED` | fail | The summary without "descriptive summary, not a pooled estimate" |
| `DESCRIPTIVE_SUMMARY_UNSUPPORTED` | fail | A median or range of estimates with no computed summary behind it |
| `DESCRIPTIVE_SUMMARY_NUMBER_MISMATCH` | fail | Printed numbers differ from the computed ones |
| `NUMBER_NOT_IN_CITED_CLAIM` | review | A number no checked claim of the one cited paper prints; a number its own citation credits to a paper that does not print it; one effect number credited to several cited papers of which only some print it; a number of people, places, ages or durations no claim prints; an effect number in a prose sentence that cites nothing |
| `NUMBER_ACROSS_PAPERS` | fail | Such a number in a sentence citing several papers |
| `POST_HOC_UNLABELED` | fail | A post-hoc pattern not called exploratory |
| `MODERATOR_CUE_UNLABELED` | review | An unmarked "stronger for…" sentence, neither exploratory nor pre-specified |
| `QUOTE_NOT_FROM_CLAIM` | review | A quotation that is not a checked quote of a cited paper |
| `CERTAINTY_STRONGER` | fail | Wording surer than the finding's certainty |
| `CERTAINTY_WEAKER` | review | Wording more cautious than the finding's certainty |
| `CERTAINTY_STACKED_HEDGE` | review | Two certainty words in one sentence |
| `FORBIDDEN_HEDGE` | review | "likely" (write "probably") |
| `NONSTANDARD_HEDGE` | review | A hedge outside the phrase table ("appears to", "possibly", …) |
| `BOOSTER` | fail | "proves", "conclusively", "clearly shows", … in a finding sentence |
| `SIGNIFICANCE_LABEL` | review | "statistically significant" in a finding sentence |
| `NO_EFFECT_CLAIM` | fail | "no effect" / "no difference" as a conclusion in a finding sentence |
| `VERY_LOW_WITHOUT_UNCERTAIN` | fail | A very-low finding that does not say "uncertain" |
| `NOT_RATED_UNSTATED` | review | An unrated finding that does not say "certainty not rated" |
| `NOT_RATED_WITH_HEDGE` | fail | A GRADE hedge on an unrated finding |
| `SECTION_EXEMPT` | warning | A methods or reference section whose wording was not checked |
| `TABLE_HASH_MISMATCH` | fail | A table is not the file its record says was written |
| `BIB_HASH_MISMATCH` | fail | The reference list is not the exported file |
| `CLAIM_SOURCE_MISMATCH` | fail | The checked card behind claims, or a paper's latest card, cannot be confirmed |
| `CLAIM_ROW_MISMATCH` | fail | A claims-table row differs from its card and check |
| `CLAIM_VERIFICATION_FORGED` | fail | A row says "found on its page" where its check says not |
| `CARD_RECHECK_DIFFERS` | fail | The card gate run again disagrees with the recorded result |
| `SUMMARY_REDERIVE_MISMATCH` | fail | A stored summary or sign test differs from the recomputed one |
| `FINDING_RULE_FAILED` | fail | A current finding breaks a rule `findings record` applies (re-applied to the re-derived claims) |
| `EDGE_ROW_MISMATCH` | fail | A citation link's recorded relation differs from the citing card's checked citation-use claim |
| `PINNED_OLDER_VERSION` | fail | A final report pinned a table older than its latest version |
| `BOOSTER_UNMARKED` | review | "proves", "clearly shows", … in a sentence not marked as a finding (it may describe something else) |
| `NO_EFFECT_CLAIM_UNMARKED` | review | "no effect" / "no difference" in a sentence not marked as a finding |
| `CLAIM_NUMBER_NEEDS_REVIEW` | review | A marked claim's labelled number was found on its page, but not where expected; compare it with the page |
| `RETRACTION_CHECK_NOT_LATEST` | fail | A final report cites a paper whose retraction record is not its newest retraction check |
| `RETRACTION_CHECK_NOT_LATEST_DRAFT` | review | The same in a draft (`synthesis` or `bibliography`) |
| `PAPER_IDENTITY_MISMATCH` | fail | A paper's DOI, title or abstract differs from the record that created it (found in the table history), or the paper first appears in a step that did not add it |
| `BIB_ENTRY_MISMATCH` | fail | The reference list holds an entry that is not `export-bib`'s rendering, a duplicate entry or field, or an entry for no paper |
| `CITATION_TITLE_DIFFERS_DRAFT` | review | In a draft (`synthesis` or `bibliography`): the title recorded for the paper is not the title of the record its DOI leads to; the final check will fail the citation |
| `CITATION_PENDING_SECOND_CHECK_DRAFT` | review | In a draft: the reference matches the database record but waits for its second check |
| `CITATION_PENDING_SECOND_CHECK` | fail | A final report cites a reference still waiting for its second check (or a legacy accepted partial match) |
| `CITATION_REJECTED` | fail | The second check (the researcher's recorded reply, or an evaluated AI check) found the record is a different work |
| `ADJUDICATION_ROW_MISMATCH` | fail | A paper's citation status, its second-check row's status or effective verdict, or the reference between them cannot be re-derived from the second-check record |
| `CITATION_CONFIRMED_BY_AI_CHECK` | warning | Citable; the reference was confirmed by DAAF's second check, an AI judgment: say so |
| `CITATION_CONFIRMED_BY_UNTESTED_AI_CHECK` | warning | Citable; the researcher let an AI check DAAF has not tested confirm references, and it confirmed this one ("confirmed by an untested AI check (your choice)"): say so |
| `CITATION_ACCEPTED_DESPITE_CHECK` | warning | Citable; the researcher accepted the reference although the automatic check disagreed: say so |
| `VISION_AUDIT_MISSING_DRAFT` | review | In a draft: the paper's latest card takes readings from pictures of pages and no trusted audit record of it exists |
| `VISION_AUDIT_MISSING` | fail | The same in a final report |
| `VISION_AUDIT_NOT_CONFIRMED_DRAFT` | review | In a draft: the card's audit lists readings a person must check, or a model or setup it could not confirm, and the researcher's records do not settle every listed reading as matching (or record one that does not match); or it could not confirm the source |
| `VISION_AUDIT_NOT_CONFIRMED` | fail | The same in a final report; its fix names `lit_verify settle` first (a recorded "does not match" has its own fix: new notes, checked and audited). Also readings accepted under the researcher's choice once that choice is withdrawn or changed (outcome key `override_withdrawn`) |
| `VISION_READ_BY_UNTESTED_MODEL` | warning | Citable; some readings in the paper's notes were taken from page pictures by a model DAAF has not tested, accepted without a comparison at the researcher's recorded choice (`lit_verify vision-override --level accept`): say so in the deliverable's methods or AI-use note |

## Known limits

- **A person's comparison is bound to the reply, not proven.** `settle`
  records the researcher's words verbatim and marks the binding
  `permission_prompt`: a permission rule that asks before `lit_verify.sh
  settle` runs shows those words to the researcher, but the tool cannot see
  whether a prompt was shown or the command was typed with `!`. Until the
  user applies that rule, the record shows only that the orchestrator ran the
  command with those words. A source DAAF could not confirm
  (`chain_unconfirmed`) is never settled by a comparison.
- **A trusted audit, settlement or second-check record is one its MANIFEST
  row vouches for.** `report` does not re-run the audit (it needs the hook
  cache) or the second check (a person's reply is theirs to give). Each
  record must match the row its own command writes, field by field, so a
  forgery needs a record and a full copy of that row. A script that writes
  both, or that runs `record-human` or `settle` itself, is not told apart:
  the user's permission rules that ask before those commands run are the
  other layer, and they do not see inside a script.
- **Pandoc parity is by design, not by test run.** The citation parser is a
  stdlib regex built from a `quarto pandoc` 3.10 probe (bracketed groups,
  prefixes, locators, suppressed author, in-text keys, trailing punctuation
  dropped, e-mail addresses ignored); it was not run against Pandoc's own
  output in a test.
- **Sentence splitting** skips the common abbreviations (et al., p., pp.,
  e.g., i.e., Fig., No., cf., vs. and similar) and single initials; an
  unusual abbreviation can split a sentence early, which only moves a
  marker's coverage.
- **Numbers** are compared by absolute value, so a sign flip between the
  prose and the claim is not caught here (the card gate catches it on the
  page). Whole numbers below 100 and years are not checked. A number of
  people, places, ages or durations ("2,560 pupils", "8.5 years old") that no
  checked claim prints goes to review even when several papers are cited, not
  to `NUMBER_ACROSS_PAPERS`: such numbers describe the studies. A threshold no
  study printed ("attrition was below 10% in both trials [@a; @b]") still
  fails as a number across papers: give each study's own figure with its
  citation.
- **Numbers in tables and after the citing sentence are not checked
  (1.13.0).** A table cell is read on its own, so the estimate in a study
  table ("| Allen [@a] | 0.45 SD |") is never compared with the paper's
  claims, nor is a number in another table cell. In prose and in a Further
  reading item, an effect number in a sentence that cites nothing goes to
  review. What the writer must do: put the
  citation in the cell or sentence that gives the estimate (each table row's
  estimate cell cites its paper), or the reviewer checks those numbers against
  the evidence cards by hand.
- **Cross-study numbers without a pooling phrase (1.14.0).** One effect
  number credited to several cited studies, with no pooling phrase, fails
  when no cited study prints it (`NUMBER_ACROSS_PAPERS`) and goes to review
  when only some of them print it (`NUMBER_NOT_IN_CITED_CLAIM`: "The three
  trials found gains of about 0.15 SD [@a; @b; @c]" where only b prints
  0.15), in a sentence marked as a finding or not; it passes when every cited
  study prints it. A sentence that gives two or more effect numbers for
  several cited papers without a citation per number ("Overall, gains were
  0.15 SD in reading and 0.09 SD in vocabulary [@a; @b; @c]") passes the
  number checks when each number is printed by one of the cited papers:
  unmarked, it goes to review only as an unmarked conclusion
  (`FINDING_UNMARKED`); inside a finding marker it passes. Give each study's
  estimate with its own citation, or the labelled descriptive summary.
- **The certainty lint reads words, not meaning.** It cannot tell a hedge
  about the evidence from a hedge about something else in the same sentence;
  keep one claim per finding sentence.
- **The direction summary's per-claim directions** are not stored in the
  findings table, so `report` recomputes the sign test from the stored counts
  and confirms its claims, not the counting itself.
- **One study's own result is described, not judged.** "Statistically
  significant" in a sentence that is not marked as a finding (for example
  "The trial was statistically significant [@a]") is not flagged: it
  describes one study, and counting several studies by significance is caught
  by the vote-count check. The label is checked only in finding sentences
  (`SIGNIFICANCE_LABEL`). By design (review cycle 1, FN18).
- **The one-citation pooling exemption trusts the attribution.** A pooling
  phrase in a clause with exactly one citation is read as that source's own
  estimate. A pooled number wrongly attributed to one paper is still caught
  when the paper's checked claims do not print it (`NUMBER_NOT_IN_CITED_CLAIM`,
  review), but not when the paper happens to print the same number.
- **Pooling needs a number.** A pooling phrase with no number ("On average,
  the programmes raised scores across the trials") is not `POOLED_ESTIMATE`
  (user decision, 2026-11-01); an unmarked sentence like it citing several papers
  goes to review as `FINDING_UNMARKED`. A clause that lists one number per
  study ("the trial found 0.21 SD and the event study 0.15 SD") passes;
  numbers written as words ("eight years old") are not read.
- **"Latest" and "newest" are append order.** A paper's latest card run is
  the last card row for it in `papers/MANIFEST.jsonl`, and the newest
  retraction check is the one with the latest timestamp (then the later
  position in the `lit_search/` MANIFESTs). One appended row can move either,
  as one appended table version can change a table. Checks saved in the same
  second in two folders are ordered by folder name, not by run order; this
  can only change which check the record must name, never the status, which
  is the most severe any check found (1.13.0).
- **Identity rests on the table history.** A paper's identity comes from the
  run that first added it (its `add-record` parameters, or its search's
  hashed results), found from the first corpus version holding its key. An
  appended `add-record` row with a new table version can still add a NEW
  paper with any title and DOI (as a real `add-record` can); it cannot
  re-point a paper the review already holds, and the reference check and the
  final title rule then judge the new paper like any other.
- **A paper with neither a DOI nor an OpenAlex key** is matched in a
  reference check through its OpenAlex alias, which lives in the
  `paper_aliases` table; the final title rule still compares its title with
  the confirmed record.
- **The reference entry's grade note is not re-derived.** Each entry must be
  `export-bib`'s rendering byte for byte, but its `daaf_evidence_grade` value
  is taken as written (it changes with every claims build, and no citation
  depends on it), provided it is one of the grade words. Re-export the list
  after attaching a check or a decision: an entry built from an older corpus
  record fails.
- **Further reading reads wording, not meaning.** An item that says what a
  title-only paper found in words the list does not hold ("tutoring helped
  rural readers a lot") passes; a question or "shows how …" is read as a
  topic to the end of its clause, so a finding tucked inside one ("shows how
  tutoring doubled reading gains") passes too; "may" and "might" are allowed
  so an item can say why a paper may be worth reading, while "probably" and
  "likely" fail even when they are about relevance ("likely relevant to the
  scale-up question"). A title-only paper cited in a Methods
  section still fails (its citations are checked there).
- **Wrapped markers:** a marker's `{...}` may span lines, but a blank line
  inside it ends the marker; the leftover text then fails as
  `SPAN_MALFORMED`.
