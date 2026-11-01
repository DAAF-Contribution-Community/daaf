#!/usr/bin/env python3
# =============================================================================
# lit_report_rules.py - the pure rules behind `lit_verify report` (added
#                       2026-10-31, Lit Review S4, dispatch D4; design
#                       2026-10-31_S4_Design_v2 §6.2 and 2026-10-30_S4_Design
#                       §6.2, both in the maintainer-only workspace
#                       research/2026-10-02_FrameworkDev_ScholarlySearch/)
# =============================================================================
#
# Stdlib only, no I/O, no network (like pdf_text_common.py): the Pandoc-style
# citation parser, the finding / claim / edge span parser, the sentence
# splitter, the language lints and the embedded certainty phrase table.
# `check_report(text, view, kind)` takes a deliverable's Markdown and a VIEW of
# the review's tables that lit_verify has already RE-DERIVED from their hashed
# sources (user decision of October 2026: every field that can clear a citation or a claim comes from
# its source, or the gate fails closed), and returns result items. lit_verify
# owns the CLI, the I/O, the re-derivation, the result JSON and the MANIFEST
# row; this module owns the rules, so they can be tested on in-memory dicts on
# a runner without polars, rapidfuzz or Pandoc.
#
# --- What the checks are (statuses in REPORT_SEVERITY; reasons are plain) ---
#   Citations   every Pandoc citation ([@k], [@k1; @k2], [@k, p. 7],
#               [see @k], [-@k]) and every bare in-text @k must name a paper
#               of the review that is in the exported reference list, whose
#               reference check (scholar_search verify) confirmed it, and that
#               was checked for retraction. A paper of which only the abstract
#               was read is cited [@k, per abstract]; one of which only the
#               title and authors are known is never cited for a statement.
#   Markers     a recorded finding: [text]{.lr-finding fid=F01 claims="..."};
#               a single claim: [text]{.lr-claim claims="..."}; a citation
#               link: [text]{.lr-edge edges="E001"}. Every id must exist; a
#               claim must be current, found on its page, and come from a
#               paper the sentence cites. Quick-scan memos carry no finding
#               markers: a sentence that rests only on abstracts is not asked
#               for one.
#   Synthesis   no pooled, averaged or weighted effect; no counting of
#               significant studies (informal counts go to a human); a
#               direction count only with the sign test the corpus computed;
#               a median / IQR / range of estimates only as the labelled
#               descriptive summary the corpus computed, numbers equal.
#   Wording     a sentence bound to a finding may not sound surer than the
#               finding's stated certainty (stronger: fail; weaker: review),
#               through the embedded phrase table (CERTAINTY_LANGUAGE).
#   Edges       "disputes" / "contradicts" wording only on a citation link
#               whose relation a reader quoted (disputes or contrasts).
#   Exempt      headings in EXEMPT_HEADINGS (fixed, user decision, 2026-10-30):
#               citations are still checked there, the wording is not.
#
# --- The phrase table -------------------------------------------------------
#   CERTAINTY_LANGUAGE is a LOCKSTEP COPY of
#   .claude/skills/literature-review/references/certainty-language.yaml (the
#   published copy other workflows read). The gate reads only this embedded
#   copy, so editing the YAML cannot loosen the lint (user decision of October 2026 spirit), and the
#   module stays stdlib (PyYAML is not on the CI runner). A test asserts the
#   two are equal (skipped without PyYAML). Change both together and bump
#   table_version.
#
# Deliverable text, quotes and every table string are UNTRUSTED data: they
# are matched, never followed. This is a library module of a standalone CLI
# (the documented exception to DAAF's no-function-definitions rule, CLAUDE.md
# § Code Style, as pdf_text_common.py is).
# =============================================================================

import bisect
import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# §§ VERSIONS (recorded in every report_check's rule_versions)
# v2 (lit_verify 1.11.0, S4 review-fix round E1, 2026-10-31): citations-v2 reads Pandoc's [@{key}] form and an
#   escaped \@ is not a citation; markers may wrap across lines (a {.lr- attribute that does not parse is
#   SPAN_MALFORMED); report-lint-v2 widens the pooling and vote-count patterns, masks "little to no difference" and
#   the paired "no evidence of an effect" statement, checks boosters and "no effect" on every citing sentence, drops
#   CI levels and p thresholds from the number check, compares a sign-test sentence's p with the computed one, and
#   reads percentages in descriptive summaries; plain reasons with no internal codes, agent hints in `hint`.
# Phrase table 2026-10-31c (round E3): contract_version 0.2.0 only; no wording or pattern changed.
# v3 (lit_verify 1.12.0, S4 review-fix round F1, 2026-11-01; review cycle 2, user decision, 2026-11-01):
#   report-lint-v3. Pooling (user decision 2026-11-01, item 2): a pooling phrase ("overall", "taken together", "pooled", "pooling", "on
#   average", "the typical study", "combined" in the pooling sense, ...) is never flagged on its own; it fails only
#   when it introduces ONE effect number in its clause and two or more papers are cited for it, outside the computed
#   descriptive-summary and sign-test sentences. Boosters and "no effect" fail on finding sentences and go to review
#   on unmarked ones (BOOSTER_UNMARKED, NO_EFFECT_CLAIM_UNMARKED); "at baseline ... no difference" is masked; "has
#   established" counts only with "that". The descriptive-summary check starts only on effect numbers (decimals or
#   percentages, or a sentence naming effects or estimates); ABSTRACT_ONLY_NUMBER reads the clause of the
#   abstract-only citation; only quotes of claims found on their page exempt a sentence (C2-CW1); a citation whose
#   marked claims all come from the abstract needs "per abstract" (q-I4); a title-only paper may be listed under a
#   "Further reading" heading (user decision 2026-11-01, item 3); a labelled number needing review is a review item (C2-QW5).
#   report-rules-v3 adds the statuses BOOSTER_UNMARKED, NO_EFFECT_CLAIM_UNMARKED, CLAIM_NUMBER_NEEDS_REVIEW,
#   RETRACTION_CHECK_NOT_LATEST, RETRACTION_CHECK_NOT_LATEST_DRAFT, PAPER_IDENTITY_MISMATCH, BIB_ENTRY_MISMATCH.
# Phrase table 2026-11-01: BOOSTER drops the bare "has/have established"; POOLED_ESTIMATE lists the pooling phrases
#   above; magnitude.not_when masks "at baseline ... no difference"; contract_version 0.3.0.
# v4 (lit_verify 1.13.0, S4 review-fix round G1, 2026-11-01; review cycle 3 W2-W5, consistency I1, I2, I7):
#   report-lint-v4. Pooling: "across the trials", a sentence-opening "Combined,", "in aggregate" and "collectively"
#   join the phrases; a phrase whose own clause holds no number reads the next clause, then the one before, so
#   "Pooled across the trials, the effect was 0.15 SD" and "The gain was 0.15 SD, taken together" fail; a clause
#   holding a number of people, places, ages or durations ("600 pupils", "8.5 years old") is not a pooled effect,
#   and such a number not in a cited claim goes to review, never NUMBER_ACROSS_PAPERS. A range whose every number
#   carries its own single citation lists studies, not a descriptive summary. A number followed by its own single
#   citation must be printed by that paper's checked claims (else review). An effect number in a sentence that cites
#   nothing, outside tables and the exempt sections, goes to review. "Further reading": a leading section number and
#   a trailing colon are allowed in the heading, and an item citing a title-only paper may not say what the paper
#   found (result verbs, effect wording, certainty or pooling phrases): METADATA_ONLY_CITED.
#   report-rules-v4: no status added or removed (71); POOLED_ESTIMATE's reason no longer says no study prints the
#   number. Phrase table 2026-11-01b: the POOLED_ESTIMATE pattern only.
# v5 (lit_verify 1.14.0, S4 polish pass H, 2026-11-01; round-G re-review W1-W5):
#   report-lint-v5. "Further reading": a question ("examines whether tutoring improves attendance", also after
#   "how", "if", "why", "what"), "shows how ...", "its title suggests" and design words ("a meta-analytic review",
#   "a review across 40 studies") name a topic and pass; statements of a finding fail also as "argues that",
#   "reports that", "according to the authors", "outperformed", "works", "is effective". Pooling: when a phrase's
#   region holds no citation, its number is credited to the next citation after it (no other result number
#   between) before all the sentence's papers, so "Overall, the largest estimate, 0.21 SD, came from the trial
#   [@a]; ..." is not a pooled estimate. One effect number, with no pooling phrase, credited to two or more cited
#   papers of which only some print it, goes to review (NUMBER_NOT_IN_CITED_CLAIM), marked as a finding or not.
#   report-rules-v5: CITATION_TITLE_DIFFERS_DRAFT (review; 72 statuses); CITATION_UNVERIFIED takes the fix
#   lit_verify gives for the paper (the title rule's own fix). Phrase table unchanged (2026-11-01b).
REPORT_RULES_VERSION = "report-rules-v5"       # this module as a whole
CITATION_PARSE_VERSION = "citations-v2"        # Pandoc 3.10 citation syntax, stdlib regex
SENTENCE_SPLIT_VERSION = "sentences-v1"
REPORT_LINT_VERSION = "report-lint-v5"

# §§ CERTAINTY LANGUAGE (lockstep copy of certainty-language.yaml; see header)
CERTAINTY_LANGUAGE = {
    "schema_version": "certainty-language-v1",
    "table_version": "2026-11-01b",
    "contract_version": "0.3.0",
    "axis": "body_of_evidence_certainty",
    "keys_are": ["high", "moderate", "low", "very_low"],
    "stated_by": ("At the standard level the synthesizer states the level with a written reason; at the formal level "
                  "the researcher decides it. This table does not compute a level; it only fixes the words for the "
                  "level stated."),
    "basis": [
        "Cochrane Handbook ch.15 Table 15.6.b, Suggested narrative statements for phrasing conclusions (chapter last "
        "updated 2023-08)",
        "Santesso et al. 2020, GRADE guidelines 26, J Clin Epidemiol 119:126-135, doi:10.1016/j.jclinepi.2019.10.014 "
        "(abstract read; full text not obtained)",
        "Cochrane EPOC, Reporting the effects of an intervention in EPOC reviews (version 2018-06-21)",
        "Murad et al. 2017, Evid Based Med 22:85-87, doi:10.1136/ebmed-2017-110668 (rating certainty without a pooled "
        "estimate)",
    ],
    "daaf_adaptations": [
        "'likely' is not allowed (GRADE allows it at moderate; DAAF keeps one moderate word, 'probably', because "
        "'likely' also reads as an IPCC probability term of 66-100 percent)",
        "associational bodies of evidence use 'is associated with' in place of a causal verb (verb choice: "
        "data-scientist references/research-questions.md)",
        "the descriptive-summary rule (an unweighted median, IQR and range of at least 3 estimates on one metric, "
        "labelled) replaces 'no aggregation of any kind'; nothing weighted, averaged or pooled",
    ],
    "levels": {
        "high": {
            "label": "high",
            "plain_meaning": "We are confident this is true; further research is very unlikely to change it.",
            "canonical": "",
            "templates": {"effect": "{X} {verb}s {Y}.",
                          "large": "{X} results in a large {reduction|increase} in {Y}.",
                          "small": "{X} {verb}s {Y} slightly.",
                          "little_or_no_difference": "{X} results in little to no difference in {Y}."},
            "markers": [],
            "allowed_variants": ["results in", "slightly", "does not {verb}"],
            "forbidden": [r"\bmay\b", r"\bmight\b", r"\bprobably\b", r"\blikely\b", r"\bsuggests?\b",
                          r"\buncertain\b"],
        },
        "moderate": {
            "label": "moderate",
            "plain_meaning": "This is probably true; better studies might change it.",
            "canonical": "probably",
            "templates": {"effect": "{X} probably {verb}s {Y}.",
                          "large": "{X} probably results in a large {reduction|increase} in {Y}.",
                          "small": "{X} probably {verb}s {Y} slightly.",
                          "little_or_no_difference": "{X} probably results in little to no difference in {Y}."},
            "markers": [r"\bprobably\b"],
            "allowed_variants": ["probably results in", "probably does not {verb}"],
            "forbidden": [r"\bmay\b", r"\bmight\b", r"\bsuggests?\b", r"\bpossibly\b", r"\buncertain\b",
                          r"\blikely\b"],
        },
        "low": {
            "label": "low",
            "plain_meaning": "This may be true, but better studies could well change it.",
            "canonical": "may",
            "templates": {"effect": "{X} may {verb} {Y}.",
                          "large": "{X} may result in a large {reduction|increase} in {Y}.",
                          "small": "{X} may {verb} {Y} slightly.",
                          "little_or_no_difference": "{X} may result in little to no difference in {Y}."},
            "markers": [r"\bmay\b", r"\bmight\b", r"\b(the\s+)?(\w+\s+)?evidence suggests\b"],
            "allowed_variants": ["the evidence suggests", "evidence suggests", "may not {verb}"],
            "forbidden": [r"\bprobably\b", r"\blikely\b", r"\bvery uncertain\b"],
        },
        "very_low": {
            "label": "very low",
            "plain_meaning": "We do not know whether this is true; the evidence is very weak.",
            "canonical": "the evidence is very uncertain",
            "templates": {"effect": "The evidence is very uncertain about the effect of {X} on {Y}.",
                          "direction": "{X} may {verb} {Y}, but the evidence is very uncertain."},
            "markers": [r"\bvery uncertain\b", r"\b(we\s+)?do(n't|\s+not)\s+know\s+(whether|if)\b",
                        r"\bit is uncertain whether\b", r"\bunclear whether\b"],
            "allowed_variants": ["it is uncertain whether", "it is unclear whether", "we do not know whether",
                                 "{X} may {verb} {Y}, but the evidence is very uncertain"],
            "forbidden": [r"\bprobably\b", r"\blikely\b", r"\bsuggests?\b"],
            "required_any": [r"\buncertain\b", r"\bunclear whether\b", r"\bdo(n't|\s+not)\s+know\s+(whether|if)\b"],
        },
    },
    "expressed_level_precedence": ["very_low", "low", "moderate", "high"],
    "not_rated": {
        "abstracts_only": "certainty not rated: abstracts only",
        "qualitative_evidence": "certainty not rated: qualitative evidence",
        "required_phrase": r"\bcertainty not rated\b",
        "forbidden": [r"\bprobably\b", r"\blikely\b", r"\bmay\b", r"\bmight\b"],
    },
    "magnitude": {
        "large": "a large {reduction|increase}",
        "small_important": "slightly",
        "trivial": "little to no difference",
        "never": [r"\bno effect\b", r"\bno difference\b"],
        "not_when": [r"\b(little|small)\s+(to|or)\s+no\s+(difference|effect)\b",
                     r"\bno\s+evidence\s+of\s+(an?\s+)?(effect|difference)\b",
                     r"\b(is\s+)?not\s+evidence\s+of\s+no\s+(effect|difference)\b",
                     r"\bat\s+baseline\b[^.;:]{0,120}?\bno\s+(effect|difference)\b",
                     r"\bno\s+(effect|difference)\b[^.;:]{0,120}?\bat\s+baseline\b"],
        "paired_absence": r"\bno\s+evidence\s+of\s+(an?\s+)?(effect|difference)\b",
    },
    "global_forbidden": [
        {"id": "BOOSTER",
         "pattern": r"\b(proves?|proven|conclusively|definitively|establish(es|ed) that|"
                    r"clearly (shows?|demonstrates?|improves?|raises?|reduces?|increases?|works?|helps?))\b"},
        {"id": "POOLED_ESTIMATE",
         "pattern": r"\b(pooled|pooling|pools?|meta-analytic|overall|taken together|on average|average (effect|impact|"
                    r"estimate|gain)|mean effect|summary (effect|estimate)|combined (effect|estimate|gain|impact)|"
                    r"the typical (study|trial|evaluation|effect)|typical effect|averag(ed|ing) (the|across|over|these|"
                    r"those|their)|mean of the( \w+)? (estimates|effects|studies|trials)|across (the |these |those |"
                    r"all |both )?(\w+ )?(studies|trials|evaluations|papers)|combined(?=,)|in aggregate|collectively)\b"},
        {"id": "WEIGHTED_SUMMARY", "pattern": r"\bweighted (mean|average|median)\b"},
        {"id": "SIGNIFICANCE_LABEL", "pattern": r"\b(statistically significant|non-?significant)\b"},
        {"id": "NO_EFFECT_CLAIM", "pattern": r"\bno (effect|difference)\b"},
        {"id": "FORBIDDEN_HEDGE", "pattern": r"\blikely\b"},
        {"id": "NONSTANDARD_HEDGE", "pattern": r"\b(could|possibly|appears? to|seems? to|perhaps)\b"},
    ],
    "descriptive_summary": {
        "min_estimates": 3,
        "required_label": "descriptive summary, not a pooled estimate",
        "allowed_statistics": [r"\bmedian\b", r"\binterquartile range\b", r"\bIQR\b", r"\brange\b"],
        "template": ("Across {k} studies reporting {metric}, the estimates ranged from {min} to {max} (median {median}; "
                     "IQR {q1} to {q3}; descriptive summary, not a pooled estimate)."),
    },
    "vote_counting": {
        "count_pattern": (r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
                          r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s+(of|out of)\s+(the\s+)?(\d+|[a-z]+)"
                          r"\s+(\w+\s+)?(studies|trials|evaluations|papers|estimates|effects)\b"),
        "quantifier_pattern": (r"(?<!the )\b(most|the majority|many|few|several|half|nearly all|almost all|a minority|all|"
                               r"none)(\s+of)?\s+(the\s+|these\s+|those\s+)?(\w+\s+)?(included\s+|reviewed\s+|"
                               r"eligible\s+)?(studies|trials|evaluations|papers)\b"),
        "count_bare_pattern": (r"\b(\d+|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
                               r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s+(\w+\s+)?(studies|trials|"
                               r"evaluations|papers)\s+(found|reported|showed|observed|detected|estimated|yielded)\b"),
        "fraction_pattern": r"\b(\d+)\s*/\s*(\d+)\s+(\w+\s+)?(studies|trials|evaluations|papers|estimates|effects)\b",
        "significance_pattern": r"(significan|statistically|p\s*[<=≤]|null (result|finding)|failed to find)",
        "result_verb_pattern": (r"\b(found|show(ed|s)?|favou?r|improv|reduc|increas|rais|lower|boost|gain|positive|"
                                r"negative|benefit|harm|effective|ineffective|worked|helped)"),
        "sign_test_pattern": r"\b(sign test|binomial)\b",
    },
    "polysemy_exceptions": {
        "may": {"not_when": r"\bMay\s+(\d{1,2}|\d{4})\b|\b(?i:in|since|until|by|from|of|during|through|before|after)"
                            r"\s+May\b|\bMay\s+(and|or|to|through)\s+[A-Z]"},
        "likely": {"not_after": ["more", "less", "as", "equally", "most", "least"]},
        "could": {"not_when": r"\bcould not be\s+\w+ed\b"},
    },
    "stacking": {"max_level_markers_per_sentence": 1},
    "labels": {"abstract_only": "per abstract", "exploratory": "exploratory", "prespecified": "pre-specified",
               "retracted": "retracted"},
}
CERTAINTY_LANGUAGE_VERSION = CERTAINTY_LANGUAGE["table_version"]
CERTAINTY_LANGUAGE_SHA256 = hashlib.sha256(json.dumps(CERTAINTY_LANGUAGE, sort_keys=True, separators=(",", ":"),
                                                      ensure_ascii=False).encode("utf-8")).hexdigest()

# §§ STATUSES (their own table: the card gate's SEVERITY is untouched)
# INTENT: one severity per status. Verdict: FAIL if any fail, else
#   NEEDS_REVIEW if any review, else PASS (no partial: a report is either
#   checked, or a person must look). Every key is documented in
#   literature-review references/lit-verify-report.md § Status index (a test
#   counts them).
REPORT_SEVERITY = {
    # citations
    "CITATION_OK": "pass", "CITEKEY_UNKNOWN": "fail", "CITEKEY_NOT_IN_BIB": "fail", "CITATION_UNVERIFIED": "fail",
    "CITATION_WEAK_UNDECIDED": "fail", "CITATION_HUMAN_DECISION_UNBOUND": "review", "RETRACTED_CITED": "fail",
    "RETRACTED_UNLABELED": "fail", "RETRACTED_CITED_DECIDED": "warning", "CORRECTED_CITED": "warning",
    "RETRACTION_NOT_CHECKED": "review", "METADATA_ONLY_CITED": "fail", "ABSTRACT_ONLY_UNLABELED": "fail",
    "ABSTRACT_ONLY_NUMBER": "fail", "PER_ABSTRACT_ON_FULL_TEXT": "warning",
    # markers: findings, claims, edges
    "FINDING_UNKNOWN": "fail", "FINDING_UNREASONED": "fail", "CLAIM_UNKNOWN": "fail", "CLAIM_NOT_VERIFIED": "fail",
    "CLAIM_SUPERSEDED": "fail", "CLAIM_PAPER_NOT_CITED": "fail", "FINDING_CLAIMS_DIFFER": "review",
    "FINDING_UNMARKED": "review", "SPAN_MALFORMED": "fail", "EDGE_OK": "pass", "EDGE_UNKNOWN": "fail",
    "EDGE_RELATION_UNSUPPORTED": "review",
    # synthesis guardrails
    "VOTE_COUNT_SIGNIFICANCE": "fail", "VOTE_COUNT_INFORMAL": "review", "DIRECTION_SIGN_TEST": "pass",
    "SIGN_TEST_MISMATCH": "fail", "POOLED_ESTIMATE": "fail", "WEIGHTED_SUMMARY": "fail",
    "DESCRIPTIVE_SUMMARY_OK": "pass", "DESCRIPTIVE_SUMMARY_UNLABELED": "fail",
    "DESCRIPTIVE_SUMMARY_UNSUPPORTED": "fail", "DESCRIPTIVE_SUMMARY_NUMBER_MISMATCH": "fail",
    "NUMBER_NOT_IN_CITED_CLAIM": "review", "NUMBER_ACROSS_PAPERS": "fail", "POST_HOC_UNLABELED": "fail",
    "MODERATOR_CUE_UNLABELED": "review", "QUOTE_NOT_FROM_CLAIM": "review",
    # certainty wording
    "CERTAINTY_STRONGER": "fail", "CERTAINTY_WEAKER": "review", "CERTAINTY_STACKED_HEDGE": "review",
    "FORBIDDEN_HEDGE": "review", "NONSTANDARD_HEDGE": "review", "BOOSTER": "fail", "SIGNIFICANCE_LABEL": "review",
    "NO_EFFECT_CLAIM": "fail", "VERY_LOW_WITHOUT_UNCERTAIN": "fail", "NOT_RATED_UNSTATED": "review",
    "NOT_RATED_WITH_HEDGE": "fail",
    # sections
    "SECTION_EXEMPT": "warning",
    # re-derivation (lit_verify, user decision of October 2026: from the hashed sources, or fail closed)
    "TABLE_HASH_MISMATCH": "fail", "BIB_HASH_MISMATCH": "fail", "CLAIM_SOURCE_MISMATCH": "fail",
    "CLAIM_ROW_MISMATCH": "fail", "CLAIM_VERIFICATION_FORGED": "fail", "CARD_RECHECK_DIFFERS": "fail",
    "SUMMARY_REDERIVE_MISMATCH": "fail",
    # report-rederive-v2 (lit_verify 1.11.0): record-time rules re-applied, edges re-derived, final reads the latest
    "FINDING_RULE_FAILED": "fail", "EDGE_ROW_MISMATCH": "fail", "PINNED_OLDER_VERSION": "fail",
    # report-rules-v3 / report-rederive-v3 (lit_verify 1.12.0, review cycle 2)
    "BOOSTER_UNMARKED": "review", "NO_EFFECT_CLAIM_UNMARKED": "review", "CLAIM_NUMBER_NEEDS_REVIEW": "review",
    "RETRACTION_CHECK_NOT_LATEST": "fail", "RETRACTION_CHECK_NOT_LATEST_DRAFT": "review",
    "PAPER_IDENTITY_MISMATCH": "fail", "BIB_ENTRY_MISMATCH": "fail",
    # report-rules-v5 (lit_verify 1.14.0, polish pass H)
    "CITATION_TITLE_DIFFERS_DRAFT": "review",
}
REPORT_KINDS = ("synthesis", "final", "bibliography")
REVIEW_LEVELS = ("quick", "standard", "formal")
# INTENT (user decision, 2026-10-30): the fixed headings whose WORDING is not linted
#   (citations there are still checked). Matched case-insensitively after a
#   leading section number ("2.", "2.1") and trailing punctuation are removed;
#   a subsection of an exempt section is exempt too. Never configurable per
#   run. "Acknowledgements" is the British spelling of the same heading.
EXEMPT_HEADINGS = ("methods", "search methods", "search strategy", "prisma", "data sources", "ai disclosure",
                   "acknowledgments", "acknowledgements", "references")
# INTENT (user decision 2026-11-01, item 3): the one heading under which a paper known only by its title and authors may be listed (a
#   reading list inside a synthesis): matched exactly, case-insensitively, at heading level 2 or deeper; its
#   subsections count too. An item there carries no finding or claim marker and no number.
FURTHER_READING_HEADING = "further reading"
GRADES_FULL_TEXT = ("FULL_TEXT_VERIFIED", "FULL_TEXT_PARTIAL", "UNCONFIRMED")
LEVEL_RANK = {"very_low": 0, "low": 1, "moderate": 2, "high": 3}
VERIFIED = ("verified", "verified_partial", "abstract_verified")    # abstract_verified: a quote of the stored abstract
DISPUTE_RELATIONS = ("disputes", "contrasts")
MAX_EXCERPT = 200

# §§ PATTERNS
CITEKEY_CHARS = r"[A-Za-z0-9_][\w:.#$%&\-+?<>~/]*"
KEY_TRAIL = ".:#$%&-+?<>~/"                    # Pandoc drops trailing punctuation from a key
BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")
# INTENT (citations-v2): Pandoc also reads @{key} (any characters but braces); an "@" after a backslash (\@) is
#   an escaped literal, not a citation (Pandoc's AST shows no citation there).
ITEM_KEY_RE = re.compile(r"(?<![\w@\\])(-?)@(?:\{([^{}\n]*)\}|(" + CITEKEY_CHARS + r"))")
BARE_KEY_RE = re.compile(r"(?<![\w@\[;\\-])@(?:\{([^{}\n]*)\}|(" + CITEKEY_CHARS + r"))")
BRACE_OPEN_RE = re.compile(r"(?<![\w\\])-?@\{")
# INTENT (report-lint-v2, C-W1): a marker's attributes may wrap across lines (Pandoc accepts newlines inside
#   {...}); a blank line still ends it. Any "{.lr-" text that does not parse as a marker is SPAN_MALFORMED.
SPAN_ATTR_RE = re.compile(r"\]\{((?:[^{}\n]|\n(?![ \t]*\n))*)\}")
LR_ATTR_RE = re.compile(r"\{\s*\.lr-")
ATTR_PAIR_RE = re.compile(r"""([A-Za-z_][\w-]*)=(?:"([^"]*)"|'([^']*)'|([^\s"'}]+))""")
SPAN_CLASSES = ("lr-finding", "lr-claim", "lr-edge")
FENCE_RE = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
HEADING_RE = re.compile(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t#]*$")
TABLE_LINE_RE = re.compile(r"^[ \t]*\|")
LIST_ITEM_RE = re.compile(r"^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+")
ABBREVIATIONS = {"al", "p", "pp", "e.g", "i.e", "fig", "figs", "no", "nos", "cf", "vs", "eq", "vol", "ch", "sec",
                 "approx", "ca", "dr", "mr", "ms", "st", "ed", "eds", "tab", "app", "suppl"}
QUOTE_RE = re.compile(r'"([^"\n]{2,600})"|\u201c([^\u201d\n]{2,600})\u201d')
NUM_RE = re.compile(r"(?<![\w.,\-−])(?:[-−]\s?)?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?|(?<![\w.,])[-−]?\.\d+%?")
WORD_NUMBERS = {w: i for i, w in enumerate(("zero one two three four five six seven eight nine ten eleven twelve "
                                            "thirteen fourteen fifteen sixteen seventeen eighteen nineteen "
                                            "twenty").split())}
DSUM_TRIGGER_RE = re.compile(r"\b(median|interquartile range|IQR|ranged?\s+from)\b", re.IGNORECASE)
ACROSS_RE = re.compile(r"\bacross\s+(the\s+)?(\w+\s+)?(studies|trials|papers|evaluations|estimates)\b", re.IGNORECASE)
MODERATOR_RE = re.compile(r"\b(only among|stronger (for|in|among)|larger (for|in|among)|moderated by|varied by|"
                          r"concentrated in)\b", re.IGNORECASE)
DISPUTE_RE = re.compile(r"\b(disput(es|ed)|contradict(s|ed)|challeng(es|ed) (the|their|its|this|these)|refut(es|ed)|"
                        r"rebut(s|ted))\b", re.IGNORECASE)
RETRACTED_WORD_RE = re.compile(r"\b(retracted|retraction|expression of concern)\b", re.IGNORECASE)
PER_ABSTRACT_RE = re.compile(r"\bper abstract\b", re.IGNORECASE)
EXPLORATORY_RE = re.compile(r"\bexploratory\b", re.IGNORECASE)
PRESPECIFIED_RE = re.compile(r"\bpre-?specified\b", re.IGNORECASE)
P_VALUE_RE = re.compile(r"\bp\s*[<=≤]", re.IGNORECASE)


def _ci(p):
    return re.compile(p, re.IGNORECASE)


VOTE = {k: _ci(v) for k, v in CERTAINTY_LANGUAGE["vote_counting"].items()}
GLOBAL = {g["id"]: _ci(g["pattern"]) for g in CERTAINTY_LANGUAGE["global_forbidden"]}
LEVEL_MARKERS = {lv: [_ci(p) for p in d["markers"]] for lv, d in CERTAINTY_LANGUAGE["levels"].items()}
LEVEL_FORBIDDEN = {lv: [_ci(p) for p in d["forbidden"]] for lv, d in CERTAINTY_LANGUAGE["levels"].items()}
LIKELY_RE = re.compile(r"\blikely\b", re.IGNORECASE)
LIKELY_NOT_AFTER_RE = re.compile(r"\b(" + "|".join(CERTAINTY_LANGUAGE["polysemy_exceptions"]["likely"]["not_after"])
                                 + r")\s+likely\b", re.IGNORECASE)
MAY_MONTH_RE = re.compile(CERTAINTY_LANGUAGE["polysemy_exceptions"]["may"]["not_when"])     # case-sensitive: "May 2020"
COULD_PASSIVE_RE = _ci(CERTAINTY_LANGUAGE["polysemy_exceptions"]["could"]["not_when"])
NOT_RATED_RE = _ci(CERTAINTY_LANGUAGE["not_rated"]["required_phrase"])
NOT_RATED_FORBIDDEN = [_ci(p) for p in CERTAINTY_LANGUAGE["not_rated"]["forbidden"]]
DSUM_LABEL = CERTAINTY_LANGUAGE["descriptive_summary"]["required_label"]
VERY_LOW_REQUIRED = [_ci(p) for p in CERTAINTY_LANGUAGE["levels"]["very_low"]["required_any"]]
CANONICAL_WORDS = {"high": "the plain verb with no hedge (for example 'results in')", "moderate": "'probably'",
                   "low": "'may'", "very_low": "'the evidence is very uncertain'"}
NOT_RATED_WORDS = {k: v for k, v in CERTAINTY_LANGUAGE["not_rated"].items() if k in ("abstracts_only",
                                                                                     "qualitative_evidence")}
# report-lint-v2: the table's own "little to no difference" and the paired absence statement are not "no effect"
#   claims (M-B1); the paired statement is reported beside any level, so its sentence is not compared with one.
NO_EFFECT_OK = [_ci(p) for p in CERTAINTY_LANGUAGE["magnitude"]["not_when"]]
PAIRED_ABSENCE_RE = _ci(CERTAINTY_LANGUAGE["magnitude"]["paired_absence"])
# Numbers that are not results: a confidence level ("95% CI") and a p threshold ("p < .05").
CI_LEVEL_RE = re.compile(r"\b(80|90|95|99)\s?%\s*(?=(CI\b|confidence|credible|uncertainty))", re.IGNORECASE)
P_THRESHOLD_RE = re.compile(r"\bp\s*[<>≤≥]\s*0?\.\d+", re.IGNORECASE)
# "12 percent" is a percentage too (an abstract's or a summary's number).
PERCENT_WORD_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:percent|per cent|percentage points?)\b", re.IGNORECASE)
PERCENT_AFTER_RE = re.compile(r"\s*(?:percent|per cent|percentage points?)\b", re.IGNORECASE)
P_PRINTED_RE = re.compile(r"\bp\s*([=<>≤≥])\s*(0?\.\d+|1(?:\.0+)?)", re.IGNORECASE)
# report-lint-v3: a comma inside a number ("1,830") is not a clause break.
CLAUSE_BREAK_RE = re.compile(r",(?!\d)|[;:]|\s[–—-]\s|\bwhile\b|\bwhereas\b|\bbut\b", re.IGNORECASE)
# report-lint-v3 (user decision 2026-11-01, item 2): "the combined effect of tutoring and coaching" names a combined intervention, not
#   a pooled number.
COMBINED_INTERVENTION_RE = re.compile(r"\bcombined\s+(effect|impact|gain|estimate)s?\s+of\s+[\w-]+(\s+[\w-]+){0,3}"
                                      r"\s+(and|with|plus)\b", re.IGNORECASE)
# A parenthesis that qualifies an estimate (its interval, standard error, p or range) holds no second effect number.
QUALIFIER_PAREN_RE = re.compile(r"\(\s*(?:(?:80|90|95|99)\s?%|CI\b|SE\b|s\.e\.|standard error|confidence|credible|p\s*[<=>≤≥]|"
                                r"range|IQR|interquartile)[^()]*\)", re.IGNORECASE)
# report-lint-v3 (C2-QW1): the descriptive-summary check starts on effect numbers only: a sentence that names
#   effects or estimates, or two or more decimals or percentages that are not study characteristics.
EFFECT_WORDS_RE = re.compile(r"\b(effects?|effect sizes?|estimates?|coefficients?|impacts?|gains?|SD|standard "
                             r"deviations?|odds ratios?|risk ratios?|correlations?)\b", re.IGNORECASE)
CHARACTERISTIC_RE = re.compile(r"\b(years?|months?|weeks?|days?|hours?|minutes?|sessions?|pupils?|students?|"
                               r"participants?|children|schools?|classes|classrooms?|teachers?|districts?|sample sizes?|"
                               r"ages?|aged)\b", re.IGNORECASE)
# The level a hedge word belongs to, for the NONSTANDARD_HEDGE reason (M-W13).
WORD_LEVEL = {"uncertain": "very_low", "unclear": "very_low", "may": "low", "might": "low", "suggest": "low",
              "suggests": "low", "probably": "moderate", "likely": "moderate"}
PLAIN_VERIFICATION = {"wrong_page": "DAAF found the quote on a different page than the one cited",
                      "vision_only": "it was found only in the page image, not in the page's text",
                      "needs_review": "a person still needs to check it",
                      "unverified": "DAAF did not find the quote on its page",
                      "unconfirmed": "its check result could not be confirmed"}
PLAIN_VERIFY_VERDICT = {"MISMATCH": "the reference check found a different paper under that identifier",
                        "NOT FOUND": "the reference check found no matching record",
                        "EXISTS": "the identifier exists, but no title was compared with the citation"}


def stat_numbers(sl):
    # The result numbers of a (masked) sentence: CI levels and p thresholds removed, "12 percent" read as 12%.
    t = CI_LEVEL_RE.sub(lambda m: " " * len(m.group(0)), sl)
    t = P_THRESHOLD_RE.sub(lambda m: " " * len(m.group(0)), t)
    t = PERCENT_WORD_RE.sub(lambda m: m.group(1) + "%", t)
    return [x for x in numbers_in(t) if is_stat_number(x)]


def rounded_equal(printed, value):
    # A printed number equals a computed value when the value, rounded half-up to the printed decimals, prints it.
    try:
        d = Decimal(("0" + printed) if printed.startswith(".") else printed)
        places = max(0, -d.as_tuple().exponent)
        return Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP) == d
    except (InvalidOperation, ValueError, TypeError):
        return False


def p_matches(op, printed, computed):
    if computed is None:
        return False
    try:
        pv, cv = Decimal(("0" + printed) if printed.startswith(".") else printed), Decimal(str(computed))
    except (InvalidOperation, ValueError):
        return False
    if op == "=":
        return rounded_equal(printed, computed)
    return {"<": cv < pv, "≤": cv <= pv, ">": cv > pv, "≥": cv >= pv}.get(op, False)


def ci_matches(token, ci95):
    # A printed interval bound equals a computed Wilson bound (as a proportion, or as a percentage).
    for b in ci95 or []:
        if token.endswith("%") and rounded_equal(token[:-1], Decimal(str(b)) * 100):
            return True
        if not token.endswith("%") and rounded_equal(token, b):
            return True
    return False


def mask_no_effect_ok(t):
    for r in NO_EFFECT_OK:
        t = r.sub(lambda m: " " * len(m.group(0)), t)
    return t


def clause_bounds(sl, start, end):
    # (c_start, c_end) of the clause holding sl[start:end]. A phrase followed directly by a clause break
    #   ("Overall, ...", "Taken together, ...") governs the clause after that break.
    cuts = list(CLAUSE_BREAK_RE.finditer(sl))
    c_start = max([m.end() for m in cuts if m.end() <= start] + [0])
    after = [m for m in cuts if m.start() >= end]
    if after and not sl[end:after[0].start()].strip():
        return c_start, (after[1].start() if len(after) > 1 else len(sl))
    return c_start, (after[0].start() if after else len(sl))


def effect_numbers(clause):
    # The result numbers of a clause, with an estimate's qualifying parenthesis (interval, SE, p, range) removed.
    return stat_numbers(QUALIFIER_PAREN_RE.sub(lambda m: " " * len(m.group(0)), clause))


# report-lint-v4 (review cycle 3 W3): a number that describes the studies (people, places, ages, durations), not
#   their results: "600 pupils", "412 to 2,560 pupils", "8.5 years old", "aged 9.5", "enrolled about 600".
CHAR_TAIL = (r"(?:\s*(?:to|and|or|-|–)\s*[\d,.]+)?\s+(?:[\w-]+\s+)?(?:pupils?|students?|participants?|children|adults?|"
             r"schools?|classes|classrooms?|teachers?|districts?|households?|families|respondents?|"
             r"(?:years?|months?|weeks?|days?|sessions?|hours?|minutes?)(?!\s+of\s+(?:learning|schooling|progress|"
             r"growth))|year-olds?)\b")
CHAR_HEAD = (r"\b(?:aged?|ages?|enrolled|sample(?:\s+size)?\s+of|n\s*=)\s*(?:about|around|approximately|roughly|some|"
             r"over|nearly|under|almost)?\s*")


def is_characteristic(text, token):
    # True when `token` (a printed number of `text`) describes the studies rather than a result.
    t = re.escape(token)
    return bool(re.search(t + CHAR_TAIL, text, re.IGNORECASE) or re.search(CHAR_HEAD + t, text, re.IGNORECASE))


def clause_spans(sl):
    # [(start, end)] of every clause of a sentence, in order (CLAUSE_BREAK_RE).
    out, s = [], 0
    for m in CLAUSE_BREAK_RE.finditer(sl):
        out.append((s, m.start()))
        s = m.end()
    out.append((s, len(sl)))
    return out


def own_citations(t, groups):
    # report-lint-v4 (W3, consistency I7): [(number token, key or None)] for every result number of `t` (a masked
    #   sentence); key is the paper of the number's OWN citation: the next citation group after it, in the same
    #   clause, holding one key, with no other result number between. `groups`: [(offset in t, [keys])], sorted.
    breaks = [m.start() for m in CLAUSE_BREAK_RE.finditer(t)]
    nums = [nm for nm in NUM_RE.finditer(t) if is_stat_number(nm.group(0))]
    out = []
    for i, nm in enumerate(nums):
        g = next((g for g in groups if g[0] >= nm.end()), None)
        lim = g[0] if g else -1
        own = g is not None and len(g[1]) == 1 and not any(nm.end() <= o.start() < lim for o in nums[i + 1:]) and \
            not any(nm.end() <= b < lim for b in breaks)
        out.append((nm.group(0), g[1][0] if own else None))
    return out


# report-lint-v4 (review cycle 3 W5): wording that says what a paper found, which a "Further reading" item citing a
#   title-only paper may not carry (its topic, setting or method is fine). "may" and "might" are left out: an item
#   may say why a paper may be worth reading. report-lint-v5 (round-G re-review W2): also a finding stated in other
#   words ("argues that", "reports that", "according to the authors", "outperformed", "is effective").
FURTHER_RESULT_RE = re.compile(
    r"\b(shows?|showed|shown|finds?|found|demonstrat(es|ed|ing)|suggests?|suggested|indicat(es|ed)|conclud(es|ed)|"
    r"proves?|proved|proven|establish(es|ed)|reveal(s|ed)|confirm(s|ed)|improves|raises|reduces|increases|lowers|"
    r"boosts|doubles|halves|(improved|raised|reduced|increased|lowered|boosted|doubled|halved|cut)\s+(\w+\s+){0,2}?"
    r"(scores?|achievement|attainment|attendance|outcomes?|performance|learning|reading|literacy|numeracy|rates?|gaps?|"
    r"gains?|by)|(had|has|have|having)\s+(\w+\s+){0,2}?effects?|effects?\s+(was|were|is|are)|no\s+(effect|difference)|"
    r"probably|likely|evidence suggests|very uncertain|unclear whether|do(n't|\s+not)\s+know\s+(whether|if)|"
    r"(argues?|argued|reports|reported|claims?|claimed|states|stated|notes|noted|says|said)\s+that|"
    r"according\s+to\s+(the|its|their)\s+(authors?|study|paper|results?|findings?|evaluation|trial)|"
    r"outperform(s|ed|ing)?|(is|are|was|were)\s+(\w+\s+)?(cost-)?effective)\b",
    re.IGNORECASE)
# report-lint-v5 (round-G re-review W2): wording that names a topic, not a result, masked before the check above: a
#   question ("examines whether tutoring improves attendance", also after "how", "if", "why", "what"; to the end of
#   its clause; "shows how ..." describes a topic too) and what the title suggests ("its title suggests a study of
#   tutor training"). "It is unclear whether" and "we do not know whether" stay certainty wording.
FURTHER_TOPIC_RE = re.compile(
    r"(?:\b(?:shows?|showed|shown|illustrates?|describes?)\s+)?(?<!unclear )(?<!know )(?<!certain )"
    r"\b(?:whether|how|if|why|what)\b[^,;:.!?()–—]*"
    r"|\b(?:its|the|their)\s+titles?\s+(?:suggests?|indicates?|implies|points?\s+to)\b",
    re.IGNORECASE)
# report-lint-v5 (round-G re-review W2): the pooling phrases that summarise results, for "Further reading" items; the
#   design words of POOLED_ESTIMATE ("a meta-analytic review", "a review across 40 studies", "a pooled analysis")
#   name a study's method there, not a result.
FURTHER_POOL_RE = re.compile(r"\b(pooled\s+(effects?|estimates?|gains?|impacts?|results?)|overall|taken together|"
                             r"on average|average (effect|impact|estimate|gain)|mean effect|summary (effect|estimate)|"
                             r"combined (effect|estimate|gain|impact)|typical effect|in aggregate|collectively)\b",
                             re.IGNORECASE)


# §§ SMALL HELPERS
def one_line(text, limit=MAX_EXCERPT):
    t = " ".join(str(text or "").split())
    return t if len(t) <= limit else t[:limit - 1] + "\u2026"


def norm_words(text):
    # Lowercase words and digits only, for the quotation-from-claim test.
    return " ".join(re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", str(text or "").lower()))


def num_value(token):
    # The absolute Decimal value of a printed number ("−0.087", "1,204", "12.5%"), or None.
    t = token.replace(",", "").replace("\u2212", "-").replace(" ", "").rstrip("%")
    try:
        return abs(Decimal(t))
    except (InvalidOperation, ValueError):
        return None


def is_stat_number(token):
    # A number worth checking: a decimal, a percentage, or a whole number of at least 100 that is not a year.
    # REASONING: small whole numbers are mostly counts of studies or groups ("three studies"), and years and
    #   page numbers are not results; checking them would bury the real problems.
    if "." in token or token.endswith("%"):
        return True
    v = num_value(token)
    return v is not None and v >= 100 and not (1900 <= v <= 2099 and "," not in token)


def numbers_in(text):
    return [m.group(0) for m in NUM_RE.finditer(text)]


def count_value(word):
    w = word.lower()
    if w.isdigit():
        return int(w)
    return WORD_NUMBERS.get(w)


def blank(chars, start, end):
    for i in range(max(0, start), min(len(chars), end)):
        if chars[i] != "\n":
            chars[i] = " "


# §§ PARSING
def parse_spans(text):
    # [{class, attrs, start, end, inner_start, inner_end, open_end, attr_start}] and malformed problems
    #   [{start, detail}]. A span is [inner]{.lr-... key=value ...}; brackets inside it nest.
    spans, problems, read = [], [], []
    for m in SPAN_ATTR_RE.finditer(text):
        attrs_text = m.group(1)
        classes = re.findall(r"(?:^|\s)\.([\w-]+)", attrs_text)
        lr = [c for c in classes if c.startswith("lr-")]
        if not lr:
            continue
        read.append((m.start(), m.end()))
        close = m.start()          # the "]" of "]{"
        depth, i = 0, close - 1
        while i >= 0:
            ch = text[i]
            if ch == "]":
                depth += 1
            elif ch == "[":
                if depth == 0:
                    break
                depth -= 1
            elif ch == "\n" and i > 0 and text[i - 1] == "\n":
                i = -1               # a span never crosses a paragraph break
                break
            i -= 1
        if i < 0:
            problems.append({"start": m.start(), "detail": "no opening bracket for the marker"})
            continue
        attrs = {}
        for pm in ATTR_PAIR_RE.finditer(attrs_text):
            attrs[pm.group(1)] = next(g for g in pm.groups()[1:] if g is not None)
        cls = lr[0]
        problem = None
        if len(lr) != 1 or cls not in SPAN_CLASSES:
            problem = f"unknown marker class {'.' + ', .'.join(lr)}"
        elif cls == "lr-finding" and not re.match(r"^F\d{2,3}$", attrs.get("fid", "")):
            problem = "a finding marker needs fid=F01 (an F and two or three digits)"
        elif cls in ("lr-finding", "lr-claim") and cls == "lr-claim" and not attrs.get("claims", "").split():
            problem = "a claim marker needs claims=\"...\" with at least one claim id"
        elif cls == "lr-edge" and not all(re.match(r"^E\d{3,}$", e) for e in attrs.get("edges", "").split() or [""]):
            problem = "a citation-link marker needs edges=\"E001\" (an E and three or more digits)"
        if problem:
            problems.append({"start": i, "detail": problem})
            continue
        spans.append({"class": cls, "attrs": attrs, "start": i, "end": m.end(), "inner_start": i + 1,
                      "inner_end": close, "attr_start": close})
    for lm in LR_ATTR_RE.finditer(text):
        if not any(s <= lm.start() < e for s, e in read):
            problems.append({"start": lm.start(), "detail": "its {.lr-...} part is not attached directly to a "
                             "[bracketed] text, is broken by a blank line, or is not closed"})
    return spans, problems


def parse_citations(text):
    # Citations in Pandoc 3.10 syntax: bracketed groups ([@k], [@k1; @k2], [@k, p. 7], [see @k], [-@k]) and bare
    #   in-text @k. Returns ([{key, start, end, group_start, group_end, suffix, per_abstract, in_text}], groups).
    #   An "@" preceded by a word character (an e-mail address) is not a citation.
    cites, groups = [], []
    taken = []
    for m in BRACKET_RE.finditer(text):
        inner = m.group(1)
        after = text[m.end():m.end() + 1]
        if after in ("{", "("):
            continue                    # a span or a link, not a citation
        if not ITEM_KEY_RE.search(inner):
            continue
        groups.append((m.start(), m.end()))
        taken.append((m.start(), m.end()))
        pos = m.start() + 1
        for part in inner.split(";"):
            km = ITEM_KEY_RE.search(part)
            if km:
                key = km.group(2) if km.group(2) is not None else km.group(3).rstrip(KEY_TRAIL)
                suffix = part[km.end():]
                start = pos + km.start()
                cites.append({"key": key, "start": start, "end": start + len(km.group(0)), "group_start": m.start(),
                              "group_end": m.end(), "suffix": suffix.strip(),
                              "per_abstract": bool(PER_ABSTRACT_RE.search(suffix)), "in_text": False})
            pos += len(part) + 1
    for m in BARE_KEY_RE.finditer(text):
        if any(s <= m.start() < e for s, e in taken):
            continue
        key = m.group(1) if m.group(1) is not None else m.group(2).rstrip(KEY_TRAIL)
        end = m.end() if m.group(1) is not None else m.start() + 1 + len(key)
        cites.append({"key": key, "start": m.start(), "end": end, "group_start": m.start(),
                      "group_end": end, "suffix": "", "per_abstract": False, "in_text": True})
    # REASONING (citations-v2, fail closed): an "@{" the patterns above did not read (an unclosed or nested brace)
    #   is still a citation to Pandoc; it is reported as an unknown key rather than skipped.
    for m in BRACE_OPEN_RE.finditer(text):
        at = m.start() + (1 if text[m.start()] == "-" else 0)
        if not any(c["start"] <= at < c["end"] or (c["group_start"] <= at < c["group_end"] and not c["in_text"])
                   for c in cites):
            cites.append({"key": "@{" + text[at + 2:at + 30].split("\n")[0], "start": at, "end": at + 2,
                          "group_start": at, "group_end": at + 2, "suffix": "", "per_abstract": False,
                          "in_text": True})
    cites.sort(key=lambda c: c["start"])
    return cites, groups


def sections_of(text):
    # [(start, end, title, line_start, exempt)] for every heading; a subsection of an exempt section is exempt.
    heads = [(m.start(), len(m.group(1)), m.group(2).strip(), m.end()) for m in HEADING_RE.finditer(text)]
    out, stack = [], []
    for i, (start, level, title, hend) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        while stack and stack[-1][0] >= level:
            stack.pop()
        name = re.sub(r"^[\d.]+\s*", "", title).strip().rstrip(":.").strip().lower()
        own = name in EXEMPT_HEADINGS
        exempt = own or any(e for _, e, _ in stack)
        # user decision 2026-11-01 (item 3): the "Further reading" heading, level 2 or deeper; report-lint-v4 (q-I3,
        #   consistency I2): matched like the exempt headings, after a leading section number and trailing ":." go
        further = (level >= 2 and name == FURTHER_READING_HEADING) or any(f for _, _, f in stack)
        stack.append((level, exempt, further))
        out.append({"start": start, "end": end, "heading_end": hend, "title": title, "exempt": exempt, "own": own,
                    "further": further})
    return out


def split_units(lint):
    # Sentence units (start, end) of the masked lint text: paragraphs split at sentence ends; table cells and list
    #   items are units of their own; heading lines are skipped (they were masked). No split after et al., p., pp.,
    #   e.g., i.e., Fig., No., cf., vs. and similar, inside a decimal, or before a lowercase word.
    units = []
    lines, pos = lint.split("\n"), 0
    para = None

    def close():
        if para is not None:
            units.extend(sentences_in(lint, para[0], para[1]))
    for ln in lines:
        start, end = pos, pos + len(ln)
        pos = end + 1
        if not ln.strip():
            close()
            para = None
            continue
        if TABLE_LINE_RE.match(ln):
            close()
            para = None
            cell = start
            for part in ln.split("|"):
                if part.strip() and not re.fullmatch(r"[\s:\-]+", part):
                    units.append((cell, cell + len(part)))
                cell += len(part) + 1
            continue
        if LIST_ITEM_RE.match(ln):
            close()
            para = [start, end]
            continue
        if para is None:
            para = [start, end]
        else:
            para[1] = end
    close()
    return [(s, e) for s, e in units if lint[s:e].strip()]


def sentences_in(lint, start, end):
    out, s = [], start
    for m in re.finditer(r"[.!?]['\"\u201d\u2019)\]]*(\s+|$)", lint[start:end]):
        cut = start + m.start()
        nxt = start + m.end()
        if nxt < end:
            ch = lint[nxt]
            if not (ch.isupper() or ch.isdigit() or ch in "\"'\u201c\u2018[(@"):
                continue
        word = re.search(r"([A-Za-z.]+)$", lint[s:cut + 1].rstrip("."))
        w = (word.group(1).lower().strip(".") if word else "")
        if w in ABBREVIATIONS or w.endswith(" et al") or (len(w) == 1 and w.isalpha()):
            continue
        out.append((s, start + m.end()))
        s = start + m.end()
    if lint[s:end].strip():
        out.append((s, end))
    return out


# §§ THE CHECK
def check_report(text, view, kind="synthesis"):
    # The report gate on one deliverable (pure). `view` holds the RE-DERIVED review state:
    #   papers   {citekey: {paper_key, grade, verify_verdict, verify_note, accept_weak, retraction_status,
    #             include_retracted, in_bib}}; grade FULL_TEXT_VERIFIED | FULL_TEXT_PARTIAL | UNCONFIRMED |
    #             ABSTRACT_ONLY | METADATA_ONLY
    #   claims   {claim_id: {paper_key, citekey, status, superseded_by, verification, quote, numbers}}
    #   findings {finding_id: {status, certainty_scheme, certainty, certainty_reason, decided_by, not_rated_reason,
    #             moderator_status, claim_ids, dsum, dirs}}
    #   edges    {edge_id: {citing_key, cited_key, reader_relation}}
    # Returns (items, info).
    papers, claims = view.get("papers") or {}, view.get("claims") or {}
    findings, edges = view.get("findings") or {}, view.get("edges") or {}
    key_of_paper = {p["paper_key"]: ck for ck, p in papers.items()}
    items = []
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line_of(off):
        return bisect.bisect_right(line_starts, off)

    def add(kind_, status, line, reason, fix="", hint="", **f):
        # reason and fix are for the researcher (plain words, no internal codes); hint is markup for the agent.
        items.append(dict({"kind": kind_, "status": status, "severity": REPORT_SEVERITY[status], "line": line,
                           "citekeys": [], "finding_id": None, "claim_ids": [], "edge_ids": [], "excerpt": None,
                           "reason": reason, "fix": fix, "hint": hint}, **f))

    # --- Masking: code, comments, then the markup the lints must not read ---
    chars = list(text)
    for rx in (FENCE_RE, INLINE_CODE_RE, COMMENT_RE):
        for m in rx.finditer("".join(chars)):
            blank(chars, m.start(), m.end())
    clean = "".join(chars)
    sections = sections_of(clean)
    spans, span_problems = parse_spans(clean)
    cites, groups = parse_citations(clean)
    for c in cites:
        if any(s["attr_start"] <= c["start"] < s["end"] for s in spans):
            c["in_attr"] = True
    cites = [c for c in cites if not c.get("in_attr")]
    for s, e in groups:
        blank(chars, s, e)
    for c in cites:
        if c["in_text"]:
            blank(chars, c["start"], c["end"])
    for sp in spans:
        blank(chars, sp["start"], sp["inner_start"])
        blank(chars, sp["attr_start"], sp["end"])
    for sec in sections:
        blank(chars, sec["start"], sec["heading_end"])
    lint = "".join(chars)
    units = split_units(lint)

    def section_at(off):
        cur = None
        for sec in sections:
            if sec["start"] <= off:
                cur = sec
        return cur

    exempt_list = []
    for sec in sections:
        if sec["own"]:
            exempt_list.append(sec["title"])
            add("section", "SECTION_EXEMPT", line_of(sec["start"]),
                f"The section '{one_line(sec['title'], 80)}' (line {line_of(sec['start'])}) is a methods or reference "
                "section: its citations were checked, but its wording was not.")
    for pb in span_problems:
        ln = line_of(pb["start"])
        add("span", "SPAN_MALFORMED", ln, f"Line {ln} has a finding, claim or citation-link marker DAAF cannot read, "
            "so the statement it marks was not checked.",
            "Have the marker rewritten in the documented form; until then the statement counts as unchecked.",
            f"Problem: {pb['detail']}. Write it as [text]{{.lr-finding fid=F01 claims=\"key-c01 key-c02\"}}, "
            "[text]{.lr-claim claims=\"key-c01\"} or [text]{.lr-edge edges=\"E001\"}; the {...} part directly after "
            "the closing bracket.")

    # --- Units: each sentence, its citations and the spans that cover it ---
    unit_info = []
    for s, e in units:
        ucites = [c for c in cites if s <= c["start"] < e or (c["group_start"] < e and s < c["group_end"]
                                                             and c["group_start"] >= s)]
        uspans = [sp for sp in spans if sp["inner_start"] < e and s < sp["inner_end"]]
        # q-I4: the claims a unit's markers name (a finding marker without claims= names its finding's claims)
        marked = []
        for sp in uspans:
            ids = sp["attrs"].get("claims", "").split()
            if not ids and sp["class"] == "lr-finding":
                ids = list((findings.get(sp["attrs"].get("fid")) or {}).get("claim_ids") or [])
            marked += ids
        unit_info.append({"start": s, "end": e, "cites": ucites, "spans": uspans, "marked": marked,
                          "line": line_of(s + len(lint[s:e]) - len(lint[s:e].lstrip())),
                          "exempt": bool((section_at(s) or {}).get("exempt")),
                          "further": bool((section_at(s) or {}).get("further"))})
    unit_of_cite = {}
    for u in unit_info:
        for c in u["cites"]:
            unit_of_cite.setdefault(c["start"], u)
    # cites that fall in no unit (e.g. a citation alone on a heading line) still get checked
    for c in cites:
        if c["start"] not in unit_of_cite:
            unit_of_cite[c["start"]] = {"start": c["start"], "end": c["end"], "cites": [c], "spans": [], "marked": [],
                                        "line": line_of(c["start"]), "exempt": True, "further": False}

    # --- Citations (every section, exempt ones included) ---
    key_done, cited_keys = set(), set()
    for c in cites:
        u = unit_of_cite[c["start"]]
        ln, key = line_of(c["start"]), c["key"]
        sent = text[u["start"]:u["end"]]
        p = papers.get(key)
        cited_keys.add(key)
        if p is None:
            if ("unknown", key) not in key_done:
                key_done.add(("unknown", key))
                add("citation", "CITEKEY_UNKNOWN", ln,
                    f"Line {ln} cites @{one_line(key, 60)}, but no paper in this review has that citation key, so "
                    "readers cannot trace the source.",
                    "Correct the key to one in the review's reference list, or add the paper to the review first.",
                    citekeys=[key])
            continue
        problems = 0
        if key not in key_done:
            key_done.add(key)
            v = p.get("verify_verdict")
            if v not in ("CONFIDENT", "WEAK"):
                problems += 1
                detail = p.get("verify_note") or (PLAIN_VERIFY_VERDICT.get(v, "the reference check did not confirm "
                                                                          "it") if v else
                                                  "no reference check is on record")
                # report-rules-v5: the fix lit_verify gives for this paper (the final title rule's own), if any
                add("citation", "CITATION_UNVERIFIED", ln,
                    f"Line {ln} cites {key}, but DAAF could not confirm that this reference exists as cited ({detail}).",
                    p.get("verify_fix") or "Do not cite it until the reference is checked again and confirmed.",
                    citekeys=[key])
            elif v == "WEAK" and not p.get("accept_weak"):
                problems += 1
                add("citation", "CITATION_WEAK_UNDECIDED", ln,
                    f"Line {ln} cites {key}. DAAF's reference check found only a partial match for it, and no one has "
                    "decided to accept it.", "Ask the researcher to look at the reference and record a decision, or "
                    "drop the citation.", citekeys=[key])
            elif v == "WEAK":
                problems += 1
                add("citation", "CITATION_HUMAN_DECISION_UNBOUND", ln,
                    f"Line {ln} cites {key}. The reference check found only a partial match; the researcher accepted "
                    "it, but that decision is not yet tied to the exact reference record.",
                    "Keep it if you agree; a person should confirm the reference before the review is final.",
                    citekeys=[key])
            if v in ("CONFIDENT", "WEAK") and not p.get("in_bib"):
                problems += 1
                add("citation", "CITEKEY_NOT_IN_BIB", ln,
                    f"Line {ln} cites {key}, a paper the review holds but did not put in its reference list (the list "
                    "holds only included, checked papers).",
                    "Cite only included papers, or include this one at screening and export the reference list again.",
                    citekeys=[key])
            rs = p.get("retraction_status")
            if rs in (None, "unknown"):
                problems += 1
                add("citation", "RETRACTION_NOT_CHECKED", ln,
                    f"Line {ln} cites {key}, but no retraction check is on record for it, so DAAF cannot say whether "
                    "it was retracted.", "Run the retraction check for this paper and attach it to the review.",
                    citekeys=[key])
            elif rs in ("corrected", "updated"):
                add("citation", "CORRECTED_CITED", ln,
                    f"Line {ln} cites {key}, which carries a published {rs} notice.",
                    "Check that the result you cite is the corrected one.", citekeys=[key])
            if p.get("retraction_not_latest"):
                # report-rederive-v4: the status is the most severe found by any check in the search records; the
                #   review's record must still name the newest check (fail in a final report, review in a draft)
                problems += 1
                add("citation", "RETRACTION_CHECK_NOT_LATEST" if kind == "final" else
                    "RETRACTION_CHECK_NOT_LATEST_DRAFT", ln,
                    f"Line {ln} cites {key}. The review's record of its retraction check is not the newest check in "
                    "the search records, so the record is out of date (DAAF judged the paper by the most serious "
                    "result any of its checks found).", "Attach the newest retraction check of this paper to the "
                    "review, then check "
                    "the deliverable again.", "lit_corpus attach retractions with the newest retractions row",
                    citekeys=[key])
            td = p.get("title_differs")
            if td and v in ("CONFIDENT", "WEAK"):
                # report-rules-v5 (round-G re-review I8): the final title rule, shown in a draft while the agent can
                #   still act; the final check fails the citation (CITATION_UNVERIFIED with the same fix)
                problems += 1
                add("citation", "CITATION_TITLE_DIFFERS_DRAFT", ln,
                    f"Line {ln} cites {key}. The title recorded when this paper was added ('"
                    f"{one_line(td.get('recorded'), 80)}') is not the title of the record its DOI leads to ('"
                    f"{one_line(td.get('record'), 80)}'), so the DOI may belong to another paper. The final check "
                    "will fail this citation.",
                    p.get("verify_fix") or "Check the paper's DOI and title before the final check.",
                    citekeys=[key])
        rs = p.get("retraction_status")
        if rs in ("retracted", "expression of concern"):
            problems += 1
            what = "retracted" if rs == "retracted" else "given an expression of concern"
            if not p.get("include_retracted"):
                add("citation", "RETRACTED_CITED", ln,
                    f"Line {ln} cites {key}, which has been {what}. Such a paper should not support a statement unless "
                    "the researcher decides to include it.",
                    "Remove the citation, or record the researcher's decision to include it and say so in the "
                    "sentence.", citekeys=[key])
            elif not RETRACTED_WORD_RE.search(sent):
                add("citation", "RETRACTED_UNLABELED", ln,
                    f"Line {ln} cites {key}, which has been {what}; the researcher chose to keep it, but the sentence "
                    "does not tell readers.", "Say in the sentence that the paper was retracted (or carries an "
                    "expression of concern).", citekeys=[key])
            else:
                add("citation", "RETRACTED_CITED_DECIDED", ln,
                    f"Line {ln} cites {key}, which has been {what}; the researcher chose to keep it and the sentence "
                    "says so.", citekeys=[key])
        grade = p.get("grade")
        only_key = len({x["key"] for x in u["cites"]}) == 1
        # q-I4: claims marked in this sentence that all come from the paper's abstract need the label too
        kc = [cid for cid in u.get("marked") or [] if (claims.get(cid) or {}).get("paper_key") == p["paper_key"]]
        abstract_marked = bool(kc) and all(claims[cid].get("verification") == "abstract_verified" for cid in kc)
        # user decision 2026-11-01 (item 3): a title-only paper may be listed under a "Further reading" heading (no
        #   marker, no number); report-lint-v4 (W5): and no wording that says what it found
        ulint = lint[u["start"]:u["end"]]
        # report-lint-v5 (W2): a question, "shows how ..." or "its title suggests" names a topic (masked first)
        topic = FURTHER_TOPIC_RE.sub(lambda m: " " * len(m.group(0)), ulint)
        stated = FURTHER_RESULT_RE.search(topic) or FURTHER_POOL_RE.search(topic)
        further_ok = u.get("further") and not u.get("spans") and not stat_numbers(ulint) and not stated
        if grade == "METADATA_ONLY" and kind != "bibliography" and u.get("further") and not further_ok and stated \
                and not u.get("spans") and not stat_numbers(ulint):
            problems += 1
            add("citation", "METADATA_ONLY_CITED", ln,
                f"Line {ln} lists {key} under Further reading but says what it found ('{one_line(stated.group(0), 40)}'"
                "). A Further reading list names papers to read; it cannot say what they found, because nothing about "
                "their content was checked.",
                "Say only what the paper is about and why it may be worth reading (its topic, setting or method), for "
                "example 'A district case study of how tutoring was rolled out'; or read at least its abstract and "
                "cite it 'per abstract' where the finding is discussed.", citekeys=[key])
        elif grade == "METADATA_ONLY" and kind != "bibliography" and not further_ok:
            problems += 1
            add("citation", "METADATA_ONLY_CITED", ln,
                f"Line {ln} cites {key}, but DAAF holds only its title and authors (neither its abstract nor its full "
                "text was read), so it cannot support a statement.",
                "Read at least its abstract (and label the citation 'per abstract') or its full text, or list it under "
                "a heading 'Further reading' (a section number before it is fine), on a line with no finding or claim "
                "marker, no number and nothing about what the paper found.", citekeys=[key])
        elif grade == "ABSTRACT_ONLY" and not (c["per_abstract"] or (only_key and PER_ABSTRACT_RE.search(sent))):
            problems += 1
            add("citation", "ABSTRACT_ONLY_UNLABELED", ln,
                f"Line {ln} cites {key}, but only the abstract of that paper was read. Readers need to know that: "
                "abstracts can overstate results and leave out limitations.",
                f"Write the citation as [@{key}, per abstract], and do not use effect sizes from it.", citekeys=[key])
        elif grade in GRADES_FULL_TEXT and abstract_marked and not c["per_abstract"]:
            problems += 1
            add("citation", "ABSTRACT_ONLY_UNLABELED", ln,
                f"Line {ln} cites {key} for claims that were all quoted from its abstract, although the paper was "
                "also read in full. Readers need to know the statement rests on the abstract.",
                f"Write the citation as [@{key}, per abstract], or point to claims checked on the paper's pages.",
                citekeys=[key])
        elif grade in GRADES_FULL_TEXT and c["per_abstract"] and not abstract_marked:
            add("citation", "PER_ABSTRACT_ON_FULL_TEXT", ln,
                f"Line {ln} labels {key} 'per abstract', but the paper was read in full.",
                "Remove the label, unless the statement really comes from the abstract only.", citekeys=[key])
        if problems == 0 and ("ok", key) not in key_done:
            key_done.add(("ok", key))
            add("citation", "CITATION_OK", ln, f"Line {ln}: {key} is in the review's checked reference list.",
                citekeys=[key])

    # --- Findings referenced by markers: the finding itself ---
    bound_fids = sorted({sp["attrs"].get("fid") for sp in spans if sp["class"] == "lr-finding"})
    for fid in bound_fids:
        sp0 = next(sp for sp in spans if sp["class"] == "lr-finding" and sp["attrs"].get("fid") == fid)
        ln = line_of(sp0["start"])
        f = findings.get(fid)
        if f is None or f.get("status") != "current":
            why = "is not recorded" if f is None else "was replaced by a newer version"
            add("finding", "FINDING_UNKNOWN", ln, f"Line {ln} marks finding {fid}, which {why} in the review's "
                "findings.", "Use the id of a recorded, current finding.", finding_id=fid)
            continue
        scheme = f.get("certainty_scheme")
        missing = []
        if scheme in ("stated", "researcher_grade") and not str(f.get("certainty_reason") or "").strip():
            missing.append("no written reason for its certainty")
        if not f.get("decided_by"):
            missing.append("no record of who decided it")
        if missing:
            add("finding", "FINDING_UNREASONED", ln,
                f"Finding {fid} (line {ln}) has {' and '.join(missing)}. Without it, readers cannot see why the "
                "evidence earns the stated certainty.",
                "Record the finding again with a reason that names the claims behind its certainty, and who decided "
                "it.", finding_id=fid)
        for cid in f.get("claim_ids") or []:
            claim_problem(add, claims, cid, ln, finding=fid)

    # --- Spans: claims and edges ---
    for sp in spans:
        ln = line_of(sp["start"])
        covered = [u for u in unit_info if sp["inner_start"] < u["end"] and u["start"] < sp["inner_end"]]
        span_keys = {c["key"] for u in covered for c in u["cites"]}
        if sp["class"] in ("lr-finding", "lr-claim"):
            ids = sp["attrs"].get("claims", "").split()
            fid = sp["attrs"].get("fid")
            for cid in ids:
                if claim_problem(add, claims, cid, ln, finding=fid):
                    continue
                ck = key_of_paper.get(claims[cid]["paper_key"]) or claims[cid].get("citekey")
                if ck not in span_keys:
                    add("claim", "CLAIM_PAPER_NOT_CITED", ln,
                        f"Line {ln} relies on claim {cid}, which comes from {ck}, but the sentence does not cite that "
                        "paper.", "Cite the paper the claim comes from in the same sentence, or point to a claim of a "
                        "paper you cite.", claim_ids=[cid], citekeys=[ck], finding_id=fid)
            f = findings.get(fid) if fid else None
            if f and f.get("status") == "current":
                extra = [cid for cid in ids if cid not in (f.get("claim_ids") or [])]
                if extra:
                    add("finding", "FINDING_CLAIMS_DIFFER", ln,
                        f"Line {ln} ties claims {', '.join(extra)} to finding {fid}, but the finding does not rest on "
                        "them.", "Use the finding's own claims, or record the finding again with these claims.",
                        finding_id=fid, claim_ids=extra)
        elif sp["class"] == "lr-edge":
            eids = sp["attrs"].get("edges", "").split()
            unknown = [x for x in eids if x not in edges]
            for x in unknown:
                add("edge", "EDGE_UNKNOWN", ln, f"Line {ln} points to citation link {x}, which is not in the "
                    "review's table of citation links.", "Use the id of a recorded citation link.", edge_ids=[x])
            sent = " ".join(lint[u["start"]:u["end"]] for u in covered) or lint[sp["inner_start"]:sp["inner_end"]]
            dm = DISPUTE_RE.search(sent)
            known = [edges[x] for x in eids if x in edges]
            if dm and not any(e.get("reader_relation") in DISPUTE_RELATIONS for e in known):
                add("edge", "EDGE_RELATION_UNSUPPORTED", ln,
                    f"Line {ln} says one paper {dm.group(0).lower()} another, but no reader has quoted, from the "
                    "citing paper, the sentence where it disputes or contrasts with the other one.",
                    "Have the reader quote that sentence on the citing paper's evidence card (as a citation use: "
                    "disputes or contrasts), or describe the papers' results side by side without that verb.",
                    edge_ids=eids)
            elif known and not unknown:
                add("edge", "EDGE_OK", ln, f"Line {ln}: citation link(s) {', '.join(eids)} are recorded"
                    + (" with a quoted relation." if dm else "."), edge_ids=eids)

    # --- Sentence lints (non-exempt units) ---
    linted = 0
    for u in unit_info:
        if u["exempt"]:
            continue
        linted += 1
        ln, s, e = u["line"], u["start"], u["end"]
        orig = text[s:e]
        ukeys = list(dict.fromkeys(c["key"] for c in u["cites"]))
        known_keys = [k for k in ukeys if k in papers]
        fids = list(dict.fromkeys(sp["attrs"].get("fid") for sp in u["spans"] if sp["class"] == "lr-finding"))
        has_edge = any(sp["class"] == "lr-edge" for sp in u["spans"])
        excerpt = one_line(lint[s:e])
        # quotations: a quote of a claim of a cited paper is exempt from the lints; any other is linted
        sent_chars = list(lint[s:e])
        # report-lint-v3 (C2-CW1): only a quote that its page check found (and whose numbers did not fail) exempts
        cited_quotes = [norm_words(cl.get("quote")) for cl in claims.values()
                        if key_of_paper.get(cl["paper_key"]) in known_keys and cl.get("status") == "current"
                        and cl.get("verification") in VERIFIED and not cl.get("numbers_failed")]
        for qm in QUOTE_RE.finditer(lint[s:e]):
            q = qm.group(1) or qm.group(2)
            nq = norm_words(q)
            if nq and any(nq in cq for cq in cited_quotes):
                blank(sent_chars, qm.start(), qm.end())
            elif len(q.split()) >= 5 and known_keys:
                add("sentence", "QUOTE_NOT_FROM_CLAIM", ln,
                    f"Line {ln} quotes text ('{one_line(q, 80)}') that is not a checked quote of the paper it cites.",
                    "Quote only text recorded as a claim on the paper's evidence card (checked on its page), or "
                    "paraphrase without quotation marks.", citekeys=known_keys, excerpt=excerpt)
        sl = "".join(sent_chars)
        # the descriptive-summary label itself ("... not a pooled estimate") is not a pooling claim
        sl = re.sub(re.escape(DSUM_LABEL), lambda m: " " * len(m.group(0)), sl, flags=re.IGNORECASE)
        stat_nums = stat_numbers(sl)
        abstract_keys = [k for k in known_keys if papers[k].get("grade") == "ABSTRACT_ONLY"]
        if abstract_keys and stat_nums:
            # report-lint-v3 (C2-QW1): a number is the abstract's when its clause holds the abstract-only
            #   citation, or its clause cites nothing and the next citation after it is abstract-only
            hit_num, hit_key = None, None
            groups_in = sorted({(c["group_start"] - s, c["key"]) for c in u["cites"]})
            t = P_THRESHOLD_RE.sub(lambda m: " " * len(m.group(0)), CI_LEVEL_RE.sub(lambda m: " " * len(m.group(0)), sl))
            for nm in NUM_RE.finditer(t):
                if not (is_stat_number(nm.group(0)) or PERCENT_AFTER_RE.match(t, nm.end())):
                    continue
                c0, c1 = clause_bounds(t, nm.start(), nm.end())
                owners = [k for g, k in groups_in if c0 <= g < c1]
                if not owners:
                    nxt = [g for g, _ in groups_in if g >= nm.end()]
                    owners = [k for g, k in groups_in if nxt and g == nxt[0]]
                hit_key = next((k for k in owners if k in abstract_keys), None)
                if hit_key:
                    hit_num = nm.group(0)
                    break
            if hit_key:
                add("sentence", "ABSTRACT_ONLY_NUMBER", ln,
                    f"Line {ln} gives a number ({hit_num}) for {hit_key}, of which only the abstract was read. "
                    "Numbers from abstracts are not checked against the paper.",
                    "Read the paper in full and cite the number from its page, or drop the number.",
                    citekeys=[hit_key], excerpt=excerpt)
        bound = [findings[x] for x in fids if x in findings and findings[x].get("status") == "current"]
        fid0 = fids[0] if fids else None
        dirs = next((f.get("dirs") for f in bound if f.get("dirs")), None)
        dsum = next((f.get("dsum") for f in bound if f.get("dsum")), None)
        special = False          # a sign-test or descriptive-summary sentence (its numbers are checked there)

        # vote counting and the sign test
        cm = VOTE["count_pattern"].search(sl)
        fm = VOTE["fraction_pattern"].search(sl)
        qm_ = VOTE["quantifier_pattern"].search(sl) or VOTE["count_bare_pattern"].search(sl)
        hit = cm or fm or qm_
        # (u, n) of an "N of M" or "N/M" count, for the sign test
        un = ((count_value(cm.group(1)), count_value(cm.group(4))) if cm else
              (int(fm.group(1)), int(fm.group(2))) if fm else None)
        # REASONING: the counted noun ("15 effects") is not a result verb: result words are read with the count removed
        rest = sl if not hit else sl[:hit.start()] + " " * (hit.end() - hit.start()) + sl[hit.end():]
        if hit:
            sign_test = VOTE["sign_test_pattern"].search(sl)
            sig_text = P_VALUE_RE.sub(" ", rest) if sign_test else rest
            if VOTE["significance_pattern"].search(sig_text):
                add("sentence", "VOTE_COUNT_SIGNIFICANCE", ln,
                    f"Line {ln} counts how many studies had significant results ('{one_line(hit.group(0), 80)}'). "
                    "Counting significant results misleads: small studies can miss real effects.",
                    "Describe each study's result and its size, strongest studies first, or count only the direction "
                    "of effects with a sign test.", citekeys=known_keys, finding_id=fid0, excerpt=excerpt)
                special = True
            elif sign_test and un:
                special = True
                u_, n_ = un
                # report-lint-v2: a printed p (and any other number) must be the computed one, rounded as printed
                pp = P_PRINTED_RE.search(sl)
                p_ok = pp is None or (dirs is not None and p_matches(pp.group(1), pp.group(2), dirs.get("p_two_sided")))
                others = [t for t in stat_numbers(P_PRINTED_RE.sub(lambda m: " " * len(m.group(0)), sl))
                          if not (dirs and ci_matches(t, dirs.get("ci95")))]
                if dirs and (u_, n_) == (dirs.get("u"), dirs.get("n")) and p_ok and not others:
                    add("sentence", "DIRECTION_SIGN_TEST", ln,
                        f"Line {ln}: the count of effects in each direction ({u_} of {n_}) matches the sign test "
                        f"computed for finding {fid0}.", citekeys=known_keys, finding_id=fid0, excerpt=excerpt)
                else:
                    want = (f"{dirs.get('u')} of {dirs.get('n')}, p = {dirs.get('p_two_sided')}, 95% interval "
                            f"{(dirs.get('ci95') or [None, None])[0]} to {(dirs.get('ci95') or [None, None])[1]}"
                            if dirs else None)
                    why = (f"differs from the sign test computed for finding {fid0} ({want})" if dirs else
                           "is not tied to a recorded finding with a computed direction count")
                    add("sentence", "SIGN_TEST_MISMATCH", ln,
                        f"Line {ln} reports a direction count ('{one_line(hit.group(0), 60)}') that {why}.",
                        "Use the counts, p-value and interval DAAF computed for the finding; they are never typed by "
                        "hand.", "Mark the sentence with its finding and copy the numbers from the finding's computed "
                        "direction summary.", citekeys=known_keys, finding_id=fid0, excerpt=excerpt)
            elif VOTE["result_verb_pattern"].search(rest):
                add("sentence", "VOTE_COUNT_INFORMAL", ln,
                    f"Line {ln} counts studies by their result ('{one_line(hit.group(0), 80)}'). A count says nothing "
                    "about how large or how trustworthy each result is.",
                    "Report each study's result, strongest studies first, or count the direction of effects with the "
                    "sign test DAAF computes for a finding.", citekeys=known_keys, finding_id=fid0, excerpt=excerpt)

        # descriptive summary
        # report-lint-v3 (C2-QW1): only effect numbers start the check ("Sample sizes ranged from 412 to 2,560
        #   pupils" describes the studies, not their results)
        quant_nums = [t for t in stat_nums if "." in t or t.endswith("%")]
        effect_talk = EFFECT_WORDS_RE.search(sl) or (len(quant_nums) >= 2 and not CHARACTERISTIC_RE.search(sl))
        # report-lint-v4 (W3, I7): the paper each result number is credited to by its own single citation; a range
        #   whose every number carries its own citation (each a different paper) lists studies, not a summary
        cgroups = {}
        for c in u["cites"]:
            cgroups.setdefault(c["group_start"] - s, []).append(c["key"])
        t_nums = P_THRESHOLD_RE.sub(lambda m: " " * len(m.group(0)), CI_LEVEL_RE.sub(lambda m: " " * len(m.group(0)),
                                                                                    sl))
        owned = own_citations(t_nums, sorted(cgroups.items()))
        per_study = bool(owned) and all(k for _, k in owned) and len({k for _, k in owned}) == len(owned)
        if DSUM_TRIGGER_RE.search(sl) and len(stat_nums) >= 2 and effect_talk and not per_study and (
                bound or len(known_keys) >= 2 or ACROSS_RE.search(sl)):
            special = True
            if not dsum:
                why = (f"finding {fid0} has no summary computed by DAAF" if bound else
                       "the sentence is not marked with a recorded finding whose summary DAAF computed")
                add("sentence", "DESCRIPTIVE_SUMMARY_UNSUPPORTED", ln,
                    f"Line {ln} gives a median or range of study estimates, but {why}.",
                    "Use only the summary DAAF computed for a recorded finding (three or more estimates on one "
                    "measure), and mark the sentence with that finding.", citekeys=known_keys, finding_id=fid0,
                    excerpt=excerpt)
            else:
                allowed = {num_value(str(dsum.get(k))) for k in ("median", "q1", "q3", "min", "max")
                           if dsum.get(k) is not None}
                printed = list(stat_nums)        # report-lint-v2: percentages and whole numbers too, not only decimals
                bad = [t for t in printed if num_value(t) not in allowed]
                median_missing = re.search(r"\bmedian\b", sl, re.I) and num_value(str(dsum.get("median"))) not in {
                    num_value(t) for t in printed}
                if not re.search(re.escape(DSUM_LABEL), orig, re.IGNORECASE):
                    add("sentence", "DESCRIPTIVE_SUMMARY_UNLABELED", ln,
                        f"Line {ln} gives a median or range of study estimates without saying it is a descriptive "
                        "summary. Readers could take it for a pooled estimate.",
                        f"Add the words '{DSUM_LABEL}'.", finding_id=fid0, excerpt=excerpt)
                if bad or median_missing:
                    want = (f"median {dsum.get('median')}, IQR {dsum.get('q1')} to {dsum.get('q3')}, range "
                            f"{dsum.get('min')} to {dsum.get('max')}, {dsum.get('k')} studies")
                    add("sentence", "DESCRIPTIVE_SUMMARY_NUMBER_MISMATCH", ln,
                        f"Line {ln} prints {', '.join(bad) if bad else 'a median'} that is not what DAAF computed for "
                        f"finding {fid0} ({want}).", "Copy the computed numbers exactly.", finding_id=fid0,
                        excerpt=excerpt)
                elif re.search(re.escape(DSUM_LABEL), orig, re.IGNORECASE):
                    add("sentence", "DESCRIPTIVE_SUMMARY_OK", ln,
                        f"Line {ln}: the descriptive summary matches what DAAF computed for finding {fid0} and is "
                        "labelled.", finding_id=fid0, excerpt=excerpt)

        # pooling and weighting
        # report-lint-v3 (user decision 2026-11-01, item 2): "Overall", "Taken together", "the typical study" and the other
        #   pooling phrases are never flagged on their own (a cross-study statement bound to a finding follows the
        #   certainty-wording rules). A phrase fails only when it introduces ONE effect number in its clause and two
        #   or more papers are cited for that clause (or none at all): a cross-study number nobody computed (user decision 2026-10-30).
        #   A clause with its own single citation reports that source's estimate (a cited meta-analysis); a
        #   sign-test or descriptive-summary sentence prints computed numbers and is checked above.
        scoped = bool(bound) or len(known_keys) >= 2 or ACROSS_RE.search(sl) or (not ukeys and stat_nums)
        pool_text = COMBINED_INTERVENTION_RE.sub(lambda m: " " * len(m.group(0)), sl)
        pooled = None
        for pm in ([] if special else GLOBAL["POOLED_ESTIMATE"].finditer(pool_text)):
            c0, c1 = clause_bounds(pool_text, pm.start(), pm.end())
            # report-lint-v4 (W2): a phrase whose own clause holds no number reads the next clause, then the one
            #   before ("Pooled across the trials, the effect was 0.15 SD"; "The gain was 0.15 SD, taken together")
            if not effect_numbers(pool_text[c0:c1]):
                spans_ = clause_spans(pool_text)
                nxt = [sp for sp in spans_ if sp[0] >= c1]
                prv = [sp for sp in spans_ if sp[1] <= c0]
                if nxt and effect_numbers(pool_text[nxt[0][0]:nxt[0][1]]):
                    c1 = nxt[0][1]
                elif prv and effect_numbers(pool_text[prv[-1][0]:prv[-1][1]]):
                    c0 = prv[-1][0]
            region = pool_text[c0:c1]
            toks = effect_numbers(region)
            # W3: one number in the region, and it is a result, not a count of people, an age or a duration
            nums = {num_value(t) for t in toks}
            keys_for = {c["key"] for c in u["cites"] if c0 <= c["group_start"] - s < c1}
            if not keys_for and toks:
                # report-lint-v5 (round-G re-review W5): a region with no citation credits its number to the next
                #   citation after it, when no other result number comes between ("Overall, the largest estimate,
                #   0.21 SD, came from the trial [@a]; ..."); only with no citation after it, to all the sentence's
                #   papers
                end = c0 + region.find(toks[0]) + len(toks[0])
                nxt_g = next(((g, ks) for g, ks in sorted(cgroups.items()) if g >= end), None)
                if nxt_g and not effect_numbers(pool_text[end:nxt_g[0]]):
                    keys_for = set(nxt_g[1])
            keys_for = keys_for or set(ukeys)
            if len(nums) == 1 and not is_characteristic(region, toks[0]) and (len(keys_for) >= 2 or not ukeys):
                pooled = pm
                break
        if pooled:
            add("sentence", "POOLED_ESTIMATE", ln,
                f"Line {ln} gives one number for several studies together ('{one_line(pooled.group(0), 60)}'). The "
                "number is credited to several studies, but no one computed it across them, and this review does not "
                "combine results, because the studies differ in design and quality.",
                "Give each study's estimate with its own citation, or, with three or more estimates on one measure, "
                "the labelled descriptive summary (median and range) that DAAF computes for a recorded finding.",
                "Per study: 'Tutoring raised scores by 0.21 SD in one trial [@a] and by 0.15 SD in another [@b].' "
                "Summary: the descriptive_summary.template of certainty-language.yaml inside the finding's marker.",
                citekeys=known_keys, finding_id=fid0, excerpt=excerpt)
        wm = GLOBAL["WEIGHTED_SUMMARY"].search(sl)
        if wm and scoped:
            add("sentence", "WEIGHTED_SUMMARY", ln,
                f"Line {ln} reports a weighted average of study results ('{one_line(wm.group(0), 40)}'). Weighting "
                "results is a form of pooling, which this review does not do.",
                "Report each study's estimate with its citation, or the descriptive summary DAAF computed for a "
                "finding (unweighted, labelled).", citekeys=known_keys, finding_id=fid0, excerpt=excerpt)

        # numbers against the cited claims
        if not special and known_keys and stat_nums:
            pkeys = {papers[k]["paper_key"] for k in known_keys}
            claim_nums, nums_by_paper = set(), {}
            for cl in claims.values():
                # Q-W1: only numbers of claims found on their page count (the view holds no failed number)
                if cl["paper_key"] in pkeys and cl.get("status") == "current" and cl.get("verification") in VERIFIED:
                    for t in cl.get("numbers") or []:
                        for tok in numbers_in(str(t)):
                            v = num_value(tok)
                            if v is not None:
                                claim_nums.add(v)
                                nums_by_paper.setdefault(cl["paper_key"], set()).add(v)
            own_of = {}
            for tok, k in owned:
                own_of.setdefault(tok, k)
            # report-lint-v5 (round-G re-review W3): the distinct effect numbers of the sentence (not people, places,
            #   ages or durations), for the one-number rule below
            effect_vals = {num_value(x) for x in stat_nums if not is_characteristic(sl, x)}
            for t in stat_nums:
                ok_ = own_of.get(t)
                if ok_ in known_keys and len(pkeys) >= 2:
                    # report-lint-v4 (consistency I7): a number with its own citation must be that paper's number
                    if num_value(t) in nums_by_paper.get(papers[ok_]["paper_key"], set()):
                        continue
                    add("sentence", "NUMBER_NOT_IN_CITED_CLAIM", ln,
                        f"Line {ln} gives the number {t} for {ok_}, but none of the checked claims of that paper "
                        "contains it" + (" (another paper the sentence cites does)" if num_value(t) in claim_nums
                                         else "") + ".",
                        "Give each paper the number it prints (from its evidence card), or check it by hand.",
                        citekeys=[ok_], excerpt=excerpt)
                    break
                if num_value(t) in claim_nums:
                    # report-lint-v5 (W3): ONE effect number, no pooling phrase, no citation of its own, credited to
                    #   two or more papers (those its clause cites, else the next citation after it, else all) of
                    #   which only some print it: one study's number given for all of them goes to a person
                    if len(effect_vals) == 1 and not pooled and ok_ is None and not is_characteristic(sl, t):
                        nm_ = next((m for m in NUM_RE.finditer(t_nums) if m.group(0) == t), None)
                        credited = set()
                        if nm_ is not None:
                            # the number's own clause (clause_bounds would widen it when a comma follows the number)
                            c0, c1 = next(((a_, b_) for a_, b_ in clause_spans(t_nums) if a_ <= nm_.start() <= b_),
                                          (0, len(t_nums)))
                            credited = {k for g, ks in cgroups.items() if c0 <= g < c1 for k in ks}
                            if not credited:
                                nxt_g = next((ks for g, ks in sorted(cgroups.items()) if g >= nm_.end()), None)
                                credited = set(nxt_g or [])
                        cpk = {papers[k]["paper_key"] for k in (credited or set(known_keys)) if k in papers}
                        printers = sorted(key_of_paper.get(pk, pk) for pk in cpk
                                          if num_value(t) in nums_by_paper.get(pk, set()))
                        if len(cpk) >= 2 and 0 < len(printers) < len(cpk):
                            add("sentence", "NUMBER_NOT_IN_CITED_CLAIM", ln,
                                f"Line {ln} gives one number ({t}) for {len(cpk)} cited studies together, but only "
                                f"{', '.join(printers)} prints it: the number comes from one of the cited studies, "
                                "while the sentence credits it to all of them.",
                                "Give each study's estimate with its own citation, or, with three or more estimates "
                                "on one measure, the labelled descriptive summary DAAF computes for a recorded "
                                "finding.", citekeys=known_keys, excerpt=excerpt)
                            break
                    continue
                # report-lint-v3 (C2-QW1) / v4 (W3): a number of people, places, ages or durations ("412 to 2,560
                #   pupils", "8.5 years old") describes the studies; across papers it goes to a person rather than
                #   failing as a combined result
                count = is_characteristic(sl, t)
                across = len(pkeys) >= 2 and not count
                add("sentence", "NUMBER_ACROSS_PAPERS" if across else "NUMBER_NOT_IN_CITED_CLAIM", ln,
                    (f"Line {ln} gives the number {t} while citing several papers, and no checked claim of those "
                     "papers contains it. A number printed by no single study may be a combined result." if across
                     else f"Line {ln} gives the number {t}, which none of the checked claims of the "
                     + ("papers" if len(pkeys) >= 2 else "paper") + " it cites contains."),
                    ("Tie each number to the one study that reports it, or use the descriptive summary DAAF computed."
                     if across else "Use the number as the paper prints it (from its evidence card), or check it by "
                     "hand."), citekeys=known_keys, excerpt=excerpt)
                break

        # report-lint-v4 (review cycle 3 W4): an effect number in a prose sentence that cites nothing cannot be checked
        #   against any paper (table cells are not read this way: Known limits)
        row_start = text.rfind("\n", 0, s) + 1
        in_table = bool(TABLE_LINE_RE.match(text[row_start:text.find("\n", s) if "\n" in text[s:] else len(text)]))
        uncited = [t for t in stat_nums if not is_characteristic(sl, t)]
        if not special and not ukeys and not pooled and uncited and EFFECT_WORDS_RE.search(sl) and not in_table:
            add("sentence", "NUMBER_NOT_IN_CITED_CLAIM", ln,
                f"Line {ln} gives the number {uncited[0]} without citing the paper it comes from, so DAAF cannot check "
                "it against any paper.", "Cite the paper that prints the number in the same sentence, or check the "
                "number by hand.", excerpt=excerpt)

        # unbound conclusions, moderators and dispute wording
        if not bound:
            all_abstract = known_keys and all(papers[k].get("grade") in ("ABSTRACT_ONLY", "METADATA_ONLY")
                                              for k in known_keys)
            marker = any(r.search(sl) for lvl in ("very_low", "low", "moderate") for r in LEVEL_MARKERS[lvl])
            if len(known_keys) >= 2 and not all_abstract and (marker or VOTE["result_verb_pattern"].search(rest)):
                add("sentence", "FINDING_UNMARKED", ln,
                    f"Line {ln} draws a conclusion from several papers but is not marked as one of the review's "
                    "recorded findings, so DAAF cannot check its wording against a certainty level.",
                    "Have the conclusion recorded as one of the review's findings (with its certainty and reason), "
                    "or describe each paper's result separately.",
                    "Mark it [text]{.lr-finding fid=F01 claims=\"...\"} after `lit_corpus findings record`.",
                    citekeys=known_keys, excerpt=excerpt)
            # report-lint-v3 (C2-QW1): boosters and "no effect" on an unmarked sentence go to a person (they fail on
            #   a finding sentence): descriptive uses ("clearly show the attrition", "the Proven Readers programme")
            #   are common there
            if known_keys:
                lint_global(add, sl, ln, excerpt, bound=False, citekeys=known_keys)
            mm = MODERATOR_RE.search(sl)
            if mm and known_keys and not (EXPLORATORY_RE.search(sl) or PRESPECIFIED_RE.search(sl)):
                add("sentence", "MODERATOR_CUE_UNLABELED", ln,
                    f"Line {ln} says an effect differs between groups ('{mm.group(0)}') without saying whether that "
                    "comparison was planned.",
                    "Say 'exploratory' (noticed in the results) or 'pre-specified' (planned in the protocol).",
                    citekeys=known_keys, excerpt=excerpt)
        if not has_edge and len(known_keys) >= 2:
            dm = DISPUTE_RE.search(sl)
            if dm:
                add("edge", "EDGE_RELATION_UNSUPPORTED", ln,
                    f"Line {ln} says one paper {dm.group(0).lower()} another, but the sentence points to no citation "
                    "link whose relation a reader quoted from the citing paper.",
                    "Have the reader quote, on the citing paper's evidence card, the sentence where it disputes or "
                    "contrasts with the other paper, and mark the sentence with that link; or describe the papers' "
                    "results side by side without that verb.", citekeys=known_keys, excerpt=excerpt)

        # certainty wording on sentences bound to a finding
        # REASONING: a sign-test or descriptive-summary sentence reports numbers DAAF computed, not the conclusion,
        #   so its (unhedged) wording is not compared with the finding's certainty; the other word checks still run.
        for f, fid in [(findings[x], x) for x in fids if x in findings and findings[x].get("status") == "current"]:
            lint_certainty(add, f, fid, sl, ln, excerpt, compare=not special)
    info = {"exempt_sections": exempt_list, "citations": len(cites), "citekeys_cited": sorted(cited_keys),
            "findings_bound": bound_fids, "sentences": len(units), "sentences_linted": linted,
            "spans": len(spans)}
    return items, info


def claim_problem(add, claims, cid, ln, finding=None):
    # Adds the item for a claim id that cannot carry a statement; returns True when it did.
    c = claims.get(cid)
    if c is None:
        add("claim", "CLAIM_UNKNOWN", ln, f"Line {ln} points to claim {one_line(cid, 60)}, which is not in the "
            "review's claims table.", "Use the id of a current claim (from the claims table).", claim_ids=[cid],
            finding_id=finding)
        return True
    if c.get("status") != "current":
        by = f" (by {c['superseded_by']})" if c.get("superseded_by") else ""
        add("claim", "CLAIM_SUPERSEDED", ln, f"Line {ln} relies on claim {cid}, which a newer version of its "
            f"evidence card replaced or withdrew{by}.", "Point to the current claim instead.", claim_ids=[cid],
            finding_id=finding)
        return True
    if c.get("verification") not in VERIFIED:
        why = PLAIN_VERIFICATION.get(c.get("verification"), "its quote was not confirmed on its cited page")
        add("claim", "CLAIM_NOT_VERIFIED", ln, f"Line {ln} relies on claim {cid}, which was not confirmed when its "
            f"evidence card was checked ({why}).",
            "Correct the evidence card and check it again, or do not rely on this claim.", claim_ids=[cid],
            finding_id=finding)
        return True
    if c.get("numbers_failed"):
        # Q-W1: a claim whose number (or a labelled estimate, CI or n) failed its page check cannot carry a statement
        add("claim", "CLAIM_NOT_VERIFIED", ln, f"Line {ln} relies on claim {cid}; its quote was found, but a number "
            "in it was not found as printed on its page, so the claim is not checked.",
            "Correct the number on the evidence card and check it again, or do not rely on this claim.",
            claim_ids=[cid], finding_id=finding)
        return True
    if c.get("numbers_review"):
        # report-rules-v3 (C2-QW5): a labelled number found on its page, but not where expected: a person decides
        add("claim", "CLAIM_NUMBER_NEEDS_REVIEW", ln, f"Line {ln} relies on claim {cid}. A labelled number in it (its "
            "estimate, interval or sample size) was found on the cited page, but not where DAAF expected it, so a "
            "person must compare the number with the page before the claim is relied on.",
            "Compare the number with the paper's page: if it is right, keep the claim; if not, correct the evidence "
            "card and check it again.", claim_ids=[cid], finding_id=finding)
    return False


def lint_global(add, sl, ln, excerpt, bound=True, **kw):
    # Boosters and "no effect" claims, in any non-exempt sentence that cites a paper: fail when the sentence states
    #   a recorded finding (bound), review otherwise (report-lint-v3).
    t = MAY_MONTH_RE.sub(lambda m: " " * len(m.group(0)), sl)
    bm = GLOBAL["BOOSTER"].search(t)
    if bm and bound:
        add("sentence", "BOOSTER", ln, f"Line {ln} says the evidence '{bm.group(0)}' the result. A synthesis does not "
            "prove; even high-certainty findings can change.", "State the result plainly, without that word.",
            excerpt=excerpt, **kw)
    elif bm:
        add("sentence", "BOOSTER_UNMARKED", ln, f"Line {ln} uses '{bm.group(0)}'. Said of what the evidence shows, "
            "the word overstates it (a synthesis does not prove); said of something else, such as a programme's name "
            "or what a table shows, it may be fine, so a person should look.",
            "If the word describes the evidence, state the result plainly without it; otherwise leave it.",
            excerpt=excerpt, **kw)
    nm = GLOBAL["NO_EFFECT_CLAIM"].search(mask_no_effect_ok(t))
    if nm and bound:
        add("sentence", "NO_EFFECT_CLAIM", ln, f"Line {ln} says there is '{nm.group(0)}'. Studies can show only that "
            "an effect is small or uncertain, not that it is zero.", "Write 'little to no difference' (or 'little to "
            "no effect'), with the certainty wording for the finding; or say there is no evidence of an effect, "
            "which is not evidence of no effect.", excerpt=excerpt, **kw)
    elif nm:
        add("sentence", "NO_EFFECT_CLAIM_UNMARKED", ln, f"Line {ln} says there is '{nm.group(0)}'. As a conclusion "
            "about the evidence this is too strong (studies can show only that an effect is small or uncertain); as "
            "a report of one study's own words it may be fine, so a person should look.",
            "If it states a conclusion, write 'little to no difference' or say there is no evidence of an effect; "
            "if it quotes a study, say whose words they are.", excerpt=excerpt, **kw)


def expressed_level(sl):
    # (level, [marker texts]) of a sentence by the table's precedence; "likely" counts as moderate. Month "May",
    #   "more likely" and similar are removed first (polysemy exceptions).
    t = MAY_MONTH_RE.sub(lambda m: " " * len(m.group(0)), sl)
    t = LIKELY_NOT_AFTER_RE.sub(lambda m: " " * len(m.group(0)), t)
    found = {}
    for lvl in ("very_low", "low", "moderate"):
        hits = [m.group(0) for r in LEVEL_MARKERS[lvl] for m in r.finditer(t)]
        if lvl == "moderate":
            hits += [m.group(0) for m in LIKELY_RE.finditer(t)]
        if hits:
            found[lvl] = hits
    level = next((lvl for lvl in CERTAINTY_LANGUAGE["expressed_level_precedence"] if lvl in found), "high")
    return level, found, t


def lint_certainty(add, f, fid, sl, ln, excerpt, compare=True):
    level, found, t = expressed_level(sl)
    label = {k: v["label"] for k, v in CERTAINTY_LANGUAGE["levels"].items()}
    scheme = f.get("certainty_scheme")
    kw = {"finding_id": fid, "excerpt": excerpt}
    lint_global(add, sl, ln, **kw)
    # report-lint-v2 (M-B1): the paired absence statement ("no evidence of an effect, which is not evidence of no
    #   effect") goes with any level, so its sentence is not compared with the finding's level
    compare = compare and not PAIRED_ABSENCE_RE.search(t)
    if GLOBAL["SIGNIFICANCE_LABEL"].search(t):
        add("sentence", "SIGNIFICANCE_LABEL", ln, f"Line {ln} describes finding {fid} as statistically significant "
            "or not. Significance says little about how large or how certain an effect is.",
            "Describe the size and direction of the effect and the certainty of the finding instead.", **kw)
    if f.get("moderator_status") == "post_hoc" and not EXPLORATORY_RE.search(t):
        add("sentence", "POST_HOC_UNLABELED", ln, f"Line {ln} states finding {fid}, a pattern noticed after looking "
            "at the results, without calling it exploratory.", "Say that the pattern is exploratory.", **kw)
    if scheme == "not_rated":
        reason_words = NOT_RATED_WORDS.get(f.get("not_rated_reason"), "certainty not rated")
        bad = next((m.group(0) for r in NOT_RATED_FORBIDDEN for m in r.finditer(t)), None)
        if bad:
            add("sentence", "NOT_RATED_WITH_HEDGE", ln, f"Line {ln} uses a certainty word ('{bad}') for finding {fid}, "
                "whose certainty was not rated. The word suggests a rating that does not exist.",
                f"Remove the word and add '{reason_words}'.", **kw)
        if not NOT_RATED_RE.search(t):
            add("sentence", "NOT_RATED_UNSTATED", ln, f"Line {ln} states finding {fid}, whose certainty was not "
                "rated, without saying so.", f"Add '{reason_words}'.", **kw)
        return
    stated = f.get("certainty")
    if stated not in LEVEL_RANK or not compare:
        return
    markers = [x for v in found.values() for x in v]
    levels_present = set(found)
    if "very_low" in levels_present:
        levels_present.discard("low")            # "may ..., but the evidence is very uncertain" is the table's variant
    if len(levels_present) > 1 or sum(len(found[x]) for x in ("low", "moderate") if x in found
                                      and x in levels_present) > 1:
        add("sentence", "CERTAINTY_STACKED_HEDGE", ln, f"Line {ln} uses more than one certainty word "
            f"('{', '.join(markers)}'). Two hedges blur which level is meant.",
            f"Keep one: the wording for {label[stated]} certainty, {CANONICAL_WORDS[stated]}.", **kw)
    if LEVEL_RANK[level] > LEVEL_RANK[stated]:
        how = "as settled (no hedge)" if level == "high" else f"at {label[level]} certainty ('{found[level][0]}')"
        add("sentence", "CERTAINTY_STRONGER", ln, f"Line {ln} words finding {fid} {how}, but the finding's certainty "
            f"is {label[stated]}. Readers would take it as surer than the evidence allows.",
            f"Write {CANONICAL_WORDS[stated]} (the wording for {label[stated]} certainty), or revisit the finding's "
            "certainty and its reason.", **kw)
    elif LEVEL_RANK[level] < LEVEL_RANK[stated]:
        add("sentence", "CERTAINTY_WEAKER", ln, f"Line {ln} words finding {fid} more cautiously ({label[level]}, "
            f"'{found[level][0]}') than its certainty ({label[stated]}).",
            f"Use {CANONICAL_WORDS[stated]}, or, if the caution is intended, lower the finding's certainty and record "
            "why.", **kw)
    elif level == "moderate" and LIKELY_RE.search(t):
        add("sentence", "FORBIDDEN_HEDGE", ln, f"Line {ln} uses 'likely'. DAAF does not use it for findings because it "
            "also reads as a probability term.", "Write 'probably' (the wording for moderate certainty).", **kw)
    if stated == "very_low" and not any(r.search(t) for r in VERY_LOW_REQUIRED):
        add("sentence", "VERY_LOW_WITHOUT_UNCERTAIN", ln, f"Line {ln} states finding {fid}, rated very low certainty, "
            "without saying the evidence is very uncertain.", "Write 'the evidence is very uncertain about ...'.", **kw)
    # words outside the table: the global nonstandard hedges, and a level's forbidden words that are not another
    #   level's markers (those are judged by the comparison above)
    t2 = COULD_PASSIVE_RE.sub(lambda m: " " * len(m.group(0)), t)
    marker_words = {m.lower() for m in markers}
    odd = [m.group(0) for m in GLOBAL["NONSTANDARD_HEDGE"].finditer(t2)]
    for r in LEVEL_FORBIDDEN[stated]:
        for m in r.finditer(t2):
            w = m.group(0)
            if w.lower() not in marker_words and not any(w.lower() in mw for mw in marker_words) \
                    and not LIKELY_RE.fullmatch(w):
                odd.append(w)
    if odd:
        lv_of = WORD_LEVEL.get(odd[0].lower())
        if lv_of and lv_of != stated:
            # M-W13: the word is another level's wording, not a word outside the table
            add("sentence", "NONSTANDARD_HEDGE", ln, f"Line {ln} uses '{odd[0]}', a word for {label[lv_of]} certainty, "
                f"in a sentence stating finding {fid}, whose certainty is {label[stated]}. Two levels in one sentence "
                "blur which one is meant.", f"Keep one wording per finding sentence ({CANONICAL_WORDS[stated]} for "
                f"{label[stated]} certainty), or move the second point to a sentence of its own.", **kw)
        else:
            add("sentence", "NONSTANDARD_HEDGE", ln, f"Line {ln} uses '{odd[0]}', which is not one of the certainty "
                "words this review uses, so readers cannot tell which level it means.",
                f"Use the wording for {label[stated]} certainty: {CANONICAL_WORDS[stated]}.", **kw)


def verdict_of(items):
    sev = {it["severity"] for it in items}
    return "FAIL" if "fail" in sev else ("NEEDS_REVIEW" if "review" in sev else "PASS")
