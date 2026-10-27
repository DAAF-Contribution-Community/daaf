# =============================================================================
# scholar_backends/_common.py - shared types for scholar_search backend adapters
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception, as stated in scripts/web_fetch.py). Holds what every adapter
# needs and nothing that touches the filesystem:
#
#   BackendError        the one exception type adapters raise
#   record()            the COMMON RECORD SCHEMA every mapper returns
#   normalization       DOI / title / abstract / ID helpers
#   contact_email()     the optional SCHOLARLY_CONTACT_EMAIL (never hard-coded)
#
# Adapters never write files and never handle provenance; the core
# (scripts/scholar_search.py) owns argparse, guards, artifacts, MANIFEST,
# fusion and rate gating. See .claude/skills/scholarly-search/references/
# _BACKEND_TEMPLATE.md for the adapter contract.
# =============================================================================

import html
import os
import re
import unicodedata

LICENSE_ORDER = {"open": 0, "cc-by-nc": 1, "restricted": 2}
CAPABILITY_VOCAB = frozenset({"search", "lookup", "cites", "refs", "oa_locate",
                              "fulltext", "retraction", "stance"})
CONTACT_ENV = "SCHOLARLY_CONTACT_EMAIL"

# §§ VERIFY_CUTOFFS
# Title-similarity cutoffs of the citation gate (`scholar_search verify`),
# calibrated on 2026-10-02 against 84 labeled (DOI, claimed title, claimed
# author) items (83 title-separable) run through the live CLI. Method, set composition, confusion
# tables and margins: .claude/skills/scholarly-search/references/api-notes.md
# § "Measured behavior: verify cutoff calibration (2026-10-02)"; the labeled
# set is tests/python/fixtures/scholar_search/verify_calibration_set.json and
# a no-network regression test holds the CONFIDENT cutoff to it.
#   (The rationale below is the pre-R1 2026-10-02 one, measured on the
#   full-title score alone; R1-R4 and cycle 2 refine how the scores are used.)
#   CONFIDENT  similarity >= VERIFY_CONFIDENT_MIN (0.95): no title-separable
#              mismatch scored above 0.917, so 0.95 leaves a 0.033 margin;
#              0.95 through 0.98 grade the set identically.
#   MISMATCH   similarity <  VERIFY_MISMATCH_BELOW (0.45), --title on an ID:
#              halves the genuine citations hard-flagged by a dropped or
#              added subtitle (6 -> 3 of 44) vs the provisional 0.60.
#   WEAK       everything between: do not cite until confirmed another way.
# All of it is IN-SAMPLE (n = 84, the mismatches and garbles partly authored
# by the calibrating model); an independent held-out validation is scheduled
# before Literature Review mode depends on verify.
# These govern the verify gate only. Version-sibling matching (fulltext
# siblings, the ERIC `oa` leg) keeps the core's TITLE_MATCH_MIN.
VERIFY_CONFIDENT_MIN = 0.95
VERIFY_MISMATCH_BELOW = 0.45
VERIFY_CUTOFFS_CALIBRATED = "2026-10-02"
# Rules R1-R4 (user decisions 2026-10-03; evidence: api-notes.md § "Measured
# behavior: verify R1–R4 (2026-10-03)"):
#   R1 VERIFY_SCORER "hybrid-v1": CONFIDENT on the difflib FULL-title score
#      (>= VERIFY_CONFIDENT_MIN); MISMATCH on the subtitle-aware score
#      max(full, main titles before the first colon, both sides split)
#      < VERIFY_MISMATCH_BELOW. The subtitle-aware score never decides
#      CONFIDENT: a fabrication keeping the real main title scores 1.00 on it.
#   R2 VERIFY_TITLE_SEARCH_FLOOR: on `verify title:"…"`, a best candidate
#      (full-title score, OpenAlex then Crossref) below it is NOT FOUND; the
#      2026-10-02 sweep sent 5/11 fabricated and 0/11 genuine titles there.
#   R3 VERIFY_AUTHOR_RULE "contiguous-surname-v1": --author passes only when
#      every token of the cited surname appears, contiguously, inside ONE
#      listed author's name (author_match below).
#   R4 VERIFY_YEAR_TOLERANCE: --year passes within ±1 (online-first vs issue
#      year); a larger gap downgrades CONFIDENT to WEAK, never to MISMATCH.
# Review-fix cycle 2 (user decisions D1-D2 and review fixes, 2026-10-03;
# evidence: api-notes.md § "Measured behavior: verify cycle 2 (2026-10-03)"):
#   D1 EXISTS: an identifier lookup without a title check resolves the ID only
#      and is never citable; CONFIDENT requires a passing title check.
#   B1 VERIFY_TITLE_NORM "nfkc-casefold-v1": verify scoring has its own
#      normalization (verify_title_norm below; any script kept, Latin
#      diacritics folded, never truncated), and either title with fewer than
#      VERIFY_MIN_TITLE_LETTERS letters can never grade CONFIDENT. norm_title
#      stays the merge/fusion key.
#   D2 VERIFY_NUMERAL_GUARD "numerals-v1": standalone numbers (digits, Roman
#      II-XX, and I/V/X closing a title segment) must match exactly before
#      CONFIDENT; a difference gives WEAK, never MISMATCH (title_numerals).
#   W3 VERIFY_AUTHOR_RULE "contiguous-surname-v2": "et al." / co-author tails,
#      Jr/Sr/II-IV and Vancouver initials are stripped; an unreadable surname
#      or an author-less record is "not checked" (never MISMATCH); a surname
#      matching only a given or middle name part is "ambiguous" (caps WEAK).
# Review-fix cycle 3 (2026-10-03; evidence: api-notes.md § "Measured behavior:
# verify cycle 3 (2026-10-03)"):
#   W-A VERIFY_NUMERAL_GUARD "numerals-v2": also ordinals and decades read by
#      their number ("21st" = 21, "1980s" = 1980), decimal digits of any script
#      (Arabic-Indic "٢٠١٨" = 2018), and I/V/X right after Part / Volume / Vol /
#      Book / Chapter / Study anywhere in the title.
#   W-C, I-D VERIFY_AUTHOR_RULE "contiguous-surname-v3": record author names
#      with no Latin-script letters, and organizational cited authors that are
#      not on the record, are "not checked" (never MISMATCH); particles may be
#      spaced or joined ("de la Cruz" = "Dela Cruz"); a name cited in the
#      other order ("Di Wu" vs "Wu Di") is "ambiguous"; a trailing upper-case
#      token ("Xiaoming LI") is read as initials only when that leaves a
#      surname on the record.
# Review-fix cycle 4 (user-authorized extra round, 2026-10-05; evidence:
# api-notes.md § "Measured behavior: verify cycle 4 (2026-10-05)"):
#   VERIFY_NUMERAL_GUARD "numerals-v3": PART_WORDS gains Phase / Wave / Title /
#      Section / Stage / Round / Experiment / Grade / Level; a spelled-out
#      one-twenty or first-twentieth right after a part word counts ("Part
#      Two" = 2); a segment-closing "I" after an auxiliary verb ("Who Am I:")
#      is the pronoun, not a numeral.
#   VERIFY_AUTHOR_RULE "contiguous-surname-v4": all-digit tokens ("Smith
#      2019") and a trailing Ed./Eds. are dropped from the cited author; a
#      surname that matches only with hyphens removed ("Al-Hassan" =
#      "Alhassan") or with German umlauts spelled out ("Mueller" = "Müller")
#      passes; "Mc"/"Mac" join the next token ("Mc Donald" = "McDonald"); a
#      cited particle the record drops ("von Hippel" vs "Hippel") is
#      "ambiguous"; an all-caps 2-8 letter acronym equal to the initials of a
#      record organization passes ("OECD"); a cited author with fewer than two
#      words before its first comma is read as a person even when a word is an
#      ORG_WORDS word ("Board", "Board, Jane").
# Review-fix cycle 5 (user-authorized, 2026-10-06; evidence: api-notes.md §
# "Measured behavior: verify cycle 5 (2026-10-06)"):
#   VERIFY_AUTHOR_RULE "contiguous-surname-v5":
#   - M1 (fixes a cycle-4 regression): an acronym is read ONLY when the whole
#     cited name is that acronym ("OECD", "OECD (2019)"), never from a
#     parenthetical. A cited organization's full name that is not on the
#     record never passes: when only its parenthetical matches ("American
#     Psychological Association (APA)" on an "American Psychiatric
#     Association" record) it is "ambiguous", else "not checked"; a
#     parenthetical can only corroborate a full name that matched.
#   - L2: acronym matching needs 3-8 letters ("UN", "JB" never pass).
#   - M2: an all-caps 2-8 letter cited name that matched nothing is "not
#     checked", never a fail (the rule cannot read every acronym: "CDC");
#     ORG_WORDS gains plurals ("Centers", "Institutes", "Academies"); a
#     leading "U.S." / "United States" is also read without it for initials
#     ("U.S. Government Accountability Office" -> GAO, and still USDA).
#   - L1: a separate "Mc"/"Mac" that leaves no match is retried without it
#     ("Mac Hulbert" vs "M. Hulbert") -> "ambiguous" (it may be a given name).
#   - L3: "Mueller" vs "Muller" (an umlaut spelling on one side, no umlaut on
#     the other) -> "ambiguous": Mueller and Muller are also distinct names.
#   VERIFY_NUMERAL_GUARD "numerals-v4": PART_WORDS gains Year / Cohort ("Year
#     One" vs "Year Two" is WEAK, no longer CONFIDENT at 0.979).
# Review-fix cycle 6 (user decision 2026-10-06, "the step-aside decision" below;
# evidence: api-notes.md § "Measured behavior: verify cycle 6 (2026-10-06)"):
#   The decision splits the citation gate into a rule layer (this code: identity —
#   the record exists, exact or near-exact title, numbers, year, surname,
#   retraction — certain or it steps aside to WEAK), a forthcoming model
#   "citation adjudicator" for the WEAK band (semantic equivalence), and a
#   human for what the adjudicator marks uncertain. Heuristic patching of
#   semantic matching stops with this cycle.
#   VERIFY_AUTHOR_RULE "contiguous-surname-v6" (organization part
#   VERIFY_ORG_RULE "org-conservative-v1"):
#   - an ORGANIZATION author (cited or listed) passes only on an EXACT
#     whole-name match after normalization (case, punctuation, accents, a
#     leading "The", a leading "U.S." / "United States"). Bare acronyms,
#     acronym-to-initials matches, parenthetical or bracketed forms that
#     match only through the acronym, containment / substring and partial
#     names are "ambiguous" with name_part ORG_NOT_EXACT (caps at WEAK, for
#     the adjudicator); an organization with no such relation stays "not
#     checked" (cycle-3 I-D; a cited organization may be a sponsor the record
#     does not list as author, so it is never a fail). "ACR (Full)", "Full
#     [ACR]", "ACR, Full" and "Full, ACR" are read like "Full (ACR)": the
#     full-name part is compared, the acronym only corroborates (N1, N5).
#   - a surname found inside a listed ORGANIZATION's name ("Bank" in "World
#     Bank", "Association (APA)") is ORG_NOT_EXACT, not a pass (N2, N4).
#   - ORG_WORDS gains bank, union(s), clearinghouse(s), parliament(s),
#     forum(s), court(s), reserve(s), nations (N2); a single lead word
#     ("Bank", "Union, J.") is still a person.
#   - the dropped-umlaut fold fires only on consonant + ae/oe/ue + two more
#     letters ("Mueller", "Schroeder"; not "Xue", "Doe", "Bauer", "Goel") (N3).
# Review-fix cycle 7 (user-approved fix round K, 2026-10-06; evidence:
# api-notes.md § "Measured behavior: verify cycle 7 (2026-10-06)"). Under the
# step-aside decision every fix is a STEP-ASIDE (the rule
# layer cannot be sure, so it says "ambiguous", capping at WEAK), never a new
# word list:
#   VERIFY_AUTHOR_RULE "contiguous-surname-v7" (person path, H1: an
#   organization whose name holds no ORG_WORDS word was read as a person and
#   passed on its last word: "Health Canada" on "Statistics Canada"):
#   - rule 1, given-name compatibility: when the cited name carries given
#     words (full names or initials, before the surname, after a comma, or as
#     Vancouver initials), its first given word must equal one of the matched
#     author's given words, or be its initial (or the reverse), once the words
#     both names share right before the surname are read as part of the
#     surname ("García Márquez", "Kirabo Jackson", "Dela Cruz" = "de la
#     Cruz"). Else "ambiguous" ("Jane Smith" on "John Smith", "Health
#     Canada" on "Statistics Canada"): a different given name may be a
#     nickname, a transliteration or another person, a semantic question;
#   - rule 2: a cited name of 3+ words (particles not counted) with no
#     initial reads like an organization; it passes only when it reproduces
#     the listed name whole;
#   - rule 3: a listed name of 3+ words with no initial and a connective
#     ("of", "and", "for", "the", "on", "in"; ACRONYM_STOPWORDS) reads like an
#     organization ("Teach For America"); a match on it passes only when the
#     cited name reproduces it whole. A 3-word person ("Andre Joshua Nickow")
#     is NOT stepped aside: the rule does not try to recognize given names;
#   - L1: a cited name with an abbreviation (a non-final word ending in ".":
#     "Am. Psychiatric Assn.") or an organization shape (a connective between
#     its words, or rule 2's shape) that matches no one is "ambiguous"
#     (ORG_NOT_EXACT), never "fail": the rule does not expand abbreviations.
#   VERIFY_ORG_RULE "org-conservative-v2":
#   - M1: the national prefix ("U.S.", "US", "USA", "United States (of
#     America)") is set aside only when the LISTED name has it and the cited
#     name does not, and only when 2+ content words remain ("Department of
#     Education" passes on "U.S. Department of Education"; "U.S. Department
#     of Education" on a bare "Department of Education" record, and "Bank" /
#     "The Bank" on "US Bank", are ORG_NOT_EXACT);
#   - L2: "&" is read as "and" ("Bill & Melinda Gates Foundation" = "Bill and
#     Melinda Gates Foundation"). Spelling variants (Centre/Center,
#     Organisation/Organization) stay unmatched for the adjudicator.
# Review-fix cycle 8 (fix round L, the FINAL rule-layer round, user decision
# 2026-10-06; evidence: api-notes.md § "Measured behavior: verify cycle 8
# (2026-10-06)"). That decision makes the citation
# adjudicator's second check on EVERY CONFIDENT mandatory, so the remaining
# rule-layer false passes are documented residuals the model reviews:
#   VERIFY_AUTHOR_RULE "contiguous-surname-v8" (step-asides only):
#   - N-1: a 2+ word cited name ending in an abbreviated word whose stem
#     begins a listed author's word ("RAND Corp." on "RAND Corporation") is
#     "ambiguous" (ORG_NOT_EXACT), not a fail; "Fakeman." still fails;
#   - N-2: when both names carry 2+ given words or initials, the second must
#     agree too ("John Q. Smith" on "John A. Smith", "J.-M. Sartre" on
#     "Jean-Paul Sartre": GIVEN_NAME_DIFFERS);
#   - N-3: cited given words with nothing on the listed side to compare them
#     with ("Health Canada" on "Canada", "Jane Smith" on "Smith"):
#     GIVEN_NAME_DIFFERS;
#   - INFO: a hyphen-joined given name counts as one word for rule 2 (so
#     "Jean-Paul Sartre" is judged by rule 1, not read as an organization)
#     and must be listed whole ("Jean-Paul Smith" on "Jean Smith" steps aside).
#   Documented residuals (still pass; reviewed by the mandatory adjudicator
#   check): a bare or partial organization name that is the record's last
#   word(s) ("Canada" on "Statistics Canada", "Research" / "Policy Research" on
#   "Mathematica Policy Research"), first + last word with the middle dropped
#   ("Mathematica Research", "Public Associates" on "Public Policy
#   Associates"), and the "&" co-author split ("Johnson & Johnson" on "Mary
#   Johnson": "&" ends the first author).
# Cycle 8b (add-on to fix round L, 2026-10-06; reported by the Manuscript
# Preparation session; evidence: api-notes.md § "Measured behavior: verify
# cycle 8 (2026-10-06)" > "Add-on 8b"):
#   VERIFY_TRANSLIT "translit-v1": the ASCII fold DELETED Latin letters that
#   have no Unicode decomposition ("Sørensen" -> srensen, "Ærø" -> r,
#   "Đorđević" -> orevic), so an ASCII-transliterated citation ("Sorensen",
#   "Djordjevic") was a false MISMATCH, and deleted letters could collide.
#   LATIN_TRANSLITERATION spells them out first, on BOTH sides, in every fold
#   that deletes (name_tokens, norm_title, org_initials). A character table is
#   normalization, not a word list (the step-aside decision).
#   VERIFY_AUTHOR_RULE "contiguous-surname-v9" (a step-aside): a surname that
#   matches only under an ALTERNATIVE transliteration of such a letter
#   (TRANSLIT_ALTERNATIVES: đ as dj, ø as oe, æ as a — "Djordjevic",
#   "Aeroe", "Torsson"; "Soerensen" / "Sørensen" is also ambiguous, but
#   through the cycle-5 dropped-umlaut fold, which is tried first) is
#   "ambiguous", never a fail; a different surname ("Nielsen" on "Anne
#   Sørensen") still fails.
# Cycle 9 (the final S1 patch, user approval 2026-10-06;
# from review cycle 8's BLOCKER B-1 and FIX-NOW F-1, with the reviewer's
# tested sketches F1 and F2; evidence: api-notes.md § "Measured behavior:
# verify cycle 9 / final S1 patch (2026-10-06)"):
#   VERIFY_AUTHOR_RULE "contiguous-surname-v10" (B-1, a step-aside): the N-2
#   check compared only the SECOND given position, so "John Q. R. Smith"
#   passed on "John Q. S. Smith". Now every aligned given position after the
#   first must agree (equal, or one is the other's initial); the first is
#   rule 1's. "J. Q. Smith" on "John Quincy Adams Smith", "Smith JAB" on
#   "John A. Smith" and "C. K. Jackson" on "C. Kirabo Jackson" still pass
#   (zip stops at the shorter side).
#   VERIFY_TRANSLIT "translit-v2" (F-1): translit-v1 still DELETED 216 Latin
#   letters (the reviewer's enumeration, Latin-1 Supplement to IPA
#   Extensions plus Latin Extended Additional), so "Aliyev" on "İlham
#   Əliyev" and "Habib" on "Joe Ħabib" were false MISMATCHes and "Liyev" /
#   "Abib" collided into passes. The table now adds (a) the reviewer's
#   letters whose Unicode name carries no base letter (schwa ə→a, open e
#   ɛ→e, open o ɔ→o, ezh ʒ→z, both cases), and (b) every still-deleted
#   letter whose Unicode name is "LATIN SMALL|CAPITAL LETTER <X> WITH …"
#   (ħ, ŧ, ɓ, ɗ, ƙ, ƴ, ƒ, ǥ, ɨ, …), mapped to <X>, plus the case partner of
#   such a letter ("AFRICAN D" Ɖ, partner of ɖ "D WITH TAIL"). The rest
#   (IPA-only letters, clicks, tone letters, wynn / yogh, digraphs) are left
#   deleted and counted in api-notes: no principled single-letter mapping
#   exists for them.
#   VERIFY_RULES_VERSION changes with every rule change, so MANIFEST rows
#   graded under different rules are distinguishable.
VERIFY_SCORER = "hybrid-v1"
VERIFY_TITLE_SEARCH_FLOOR = 0.70
VERIFY_YEAR_TOLERANCE = 1
VERIFY_AUTHOR_RULE = "contiguous-surname-v10"
VERIFY_ORG_RULE = "org-conservative-v2"
VERIFY_RULES_UPDATED = "2026-10-06"
VERIFY_RULES_VERSION = "2026-10-06f"
VERIFY_TITLE_NORM = "nfkc-casefold-v1"
VERIFY_TRANSLIT = "translit-v2"
VERIFY_MIN_TITLE_LETTERS = 3
VERIFY_NUMERAL_GUARD = "numerals-v4"
# Cycle 5 (M1/L2/M2): a cited name read as an organization acronym, and the
# all-caps cited names M2 never fails.
ACRONYM_MIN_LETTERS = 3
ACRONYM_MAX_LETTERS = 8
# Cited-author tails and suffixes stripped before the surname is read (W3;
# cycle 4 adds the editor marks "Ed." / "Eds.", which a reference list prints
# after the name: "Smith Ed.").
SURNAME_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv"})
EDITOR_MARKS = frozenset({"ed", "eds"})
# Roman numerals counted wherever they stand as a token (D2), and the three
# single letters counted only when they close a title segment or follow a
# part word (see title_numerals: "Teachers I:" and "Part I of" are numerals,
# "What I Learned" a pronoun).
ROMAN_NUMERALS = {"ii": 2, "iii": 3, "iv": 4, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "xi": 11, "xii": 12,
                  "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19, "xx": 20}
ROMAN_SEGMENT_END = {"i": 1, "v": 5, "x": 10}
PART_WORDS = frozenset({"part", "volume", "vol", "book", "chapter", "study", "phase", "wave", "title", "section",
                        "stage", "round", "experiment", "grade", "level", "year", "cohort"})
# Spelled-out numbers counted ONLY when they directly follow a part word
# (numerals-v3): "Part Two", "Grade Three", "Wave First". Elsewhere "one" is
# usually a pronoun or article ("One School's Story").
SPELLED_NUMERALS = {w: i + 1 for i, w in enumerate(
    "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
SPELLED_NUMERALS.update({w: i + 1 for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth "
    "fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split())})
# A segment-closing "I" right after one of these is the pronoun of an
# inverted question ("Who Am I:", "What Should I: …"), not a part numeral
# ("Teachers I:" still counts).
PRONOUN_I_AFTER = frozenset("am was can could do did should would will shall may might must have had".split())
# A cited author containing one of these words is read as an ORGANIZATION
# (cycle 3, I-D): compared by its whole name, never by its last word, and
# "not checked" when that name is not on the record. Cycle 5 (M2) adds the
# plurals ("Centers for Disease Control", "National Institutes of Health").
ORG_WORDS = frozenset("""institute institution organization organisation department center centre council
association university college bureau agency ministry office foundation commission committee board society
consortium collaboration collaborative group network laboratory program programme administration academy
service services survey team project initiative corporation inc ltd trust fund alliance coalition federation
partnership authority panel secretariat
institutes institutions organizations organisations departments centers centres councils associations
universities colleges bureaus bureaux agencies ministries offices foundations commissions committees boards
societies consortia collaborations groups networks laboratories programs programmes administrations academies
surveys teams projects initiatives corporations trusts funds alliances coalitions federations partnerships
authorities panels
bank union unions clearinghouse clearinghouses parliament parliaments forum forums court courts reserve reserves
nations""".split())
# Cycle 6 (N2) adds the last two lines ("World Bank", "African Union", "What
# Works Clearinghouse", "European Parliament", "World Economic Forum",
# "Supreme Court", "Federal Reserve", "United Nations"). "banks" is left out:
# Banks is a common surname ("James A. Banks"), and a listed name with an
# ORG_WORDS word is read as an organization (is_org_name).
# Cycle 6 (step-aside decision): the name_part of an organization match that is not an exact
# whole-name match — the rows the forthcoming citation adjudicator selects.
ORG_NOT_EXACT = "organization: not an exact name match"
# A leading "The" is dropped from BOTH organization names before the exact
# comparison ("The World Bank" = "World Bank"). Cycle 7 (M1): a leading
# national prefix is NOT dropped; org_key spells every form of it as the one
# token ORG_PREFIX_MARK, and org_exact sets it aside only on the listed side
# (longest form first).
ORG_NATIONAL_PREFIXES = (("united", "states", "of", "america"), ("united", "states"), ("u", "s", "a"), ("u", "s"),
                         ("usa",), ("us",))
ORG_PREFIX_MARK = "us"
# Lowercase surname particles that start a multi-token surname in a cited
# "First van der Surname" form. Matched after stripping a trailing period.
NAME_PARTICLES = frozenset("van von der den de del della dei di da du des dos das le la lo ten ter "
                           "vander st bin ibn".split())
# Cycle 4: "Mc"/"Mac" written as a separate token start a multi-token surname
# like a particle ("Mc Donald" = "McDonald", compared joined), but unlike the
# particles below they are never dropped.
NAME_JOIN_PREFIXES = frozenset({"mc", "mac"})
# Particles a record may drop from a cited surname ("von Hippel" listed as
# "Paul T. Hippel"): such a match is "ambiguous", never a pass (cycle 4).
# "st" is not droppable ("St. John" is not "John").
DROPPABLE_PARTICLES = NAME_PARTICLES - {"st"}
# Words ignored when an organization's initials are read for an acronym
# ("Organisation for Economic Co-operation and Development" -> OECD).
ACRONYM_STOPWORDS = frozenset({"of", "and", "for", "the", "on", "in"})
# Cycle 5 (M2): a leading national prefix an acronym often omits ("U.S.
# Bureau of Labor Statistics" = BLS), read both with and without it (USDA).
ACRONYM_OPTIONAL_PREFIX = re.compile(r"^\s*(?:U\.?\s?S\.?(?:A\.?)?|United\s+States(?:\s+of\s+America)?)\s+", re.I)
GERMAN_TRANSLITERATION = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})
# Cycle 8b (VERIFY_TRANSLIT "translit-v1"): Latin letters with NO Unicode
# decomposition, which the NFKD ASCII fold would delete, spelled out first.
# Applied after NFKD, so a marked form ("ǿ" = ø + acute) is caught too. "ß"
# keeps its own earlier replacement in name_tokens (cycle 4) and is listed
# here too, so norm_title and org_initials no longer delete it either.
LATIN_TRANSLITERATION_V1 = {
    "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "đ": "d", "Đ": "D",
    "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th", "ı": "i", "ŋ": "ng", "Ŋ": "Ng", "ĸ": "k", "ß": "ss", "ẞ": "SS"}
# Cycle 9 (VERIFY_TRANSLIT "translit-v2", review-8 F-1 / sketch F2): the
# reviewer's letters whose Unicode name carries no base letter, so the
# name-derived rule below cannot read them (schwa: Azerbaijani "Əliyev" is
# romanized "Aliyev"; open e / open o: West African orthographies; ezh).
LATIN_TRANSLITERATION_EXPLICIT_V2 = {"ə": "a", "Ə": "A", "ɛ": "e", "Ɛ": "E", "ɔ": "o", "Ɔ": "O", "ʒ": "z",
                                     "Ʒ": "Z"}
# The code-point blocks the name-derived rule scans (the review-cycle-8
# reviewer's enumeration ranges: Latin-1 Supplement through IPA Extensions, and Latin
# Extended Additional). Fixed here so the table does not grow with the
# Unicode database of a future Python.
TRANSLIT_NAME_RANGES = ((0x00C0, 0x024F), (0x0250, 0x02AF), (0x1E00, 0x1EFF))
TRANSLIT_WITH_NAME = re.compile(r"^LATIN (SMALL|CAPITAL) LETTER ([A-Z]) WITH .+$")


def name_derived_transliteration():
    # INTENT (cycle 9, translit-v2): for every Latin letter in
    #   TRANSLIT_NAME_RANGES that the NFKD ASCII fold DELETES (no
    #   decomposition to an ASCII letter), the base letter its Unicode name
    #   states: "LATIN SMALL LETTER H WITH STROKE" (ħ) -> "h", "LATIN CAPITAL
    #   LETTER D WITH HOOK" (Ɗ) -> "D". A letter not of that shape whose case
    #   partner is ("LATIN CAPITAL LETTER AFRICAN D" Ɖ, partner of ɖ "D WITH
    #   TAIL") gets the partner's base letter in its own case.
    # REASONING: Unicode names are immutable, so the mapping is a fixed,
    #   reviewable function of the character, not a word list (step-aside
    #   decision). Letters
    #   with a decomposition never reach the table (NFKD runs first).
    # ASSUMES: a stroke, hook, bar, curl, tail or loop on a Latin letter is a
    #   diacritic-like modifier whose ASCII rendering is the base letter, as
    #   the NFKD fold already does for decomposable marks (ç -> c).
    derived = {}
    for lo, hi in TRANSLIT_NAME_RANGES:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            if not ch.isalpha() or unicodedata.normalize("NFKD", ch).encode("ascii", "ignore"):
                continue
            m = TRANSLIT_WITH_NAME.match(unicodedata.name(ch, ""))
            if m:
                derived[ch] = m.group(2).lower() if m.group(1) == "SMALL" else m.group(2)
    for lo, hi in TRANSLIT_NAME_RANGES:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            if ch in derived or not ch.isalpha() or unicodedata.normalize("NFKD", ch).encode("ascii", "ignore"):
                continue
            for partner in {ch.lower(), ch.upper()} - {ch}:
                if len(partner) == 1 and partner in derived:
                    derived[ch] = derived[partner].upper() if ch.isupper() else derived[partner].lower()
                    break
    return derived


# translit-v2 = the name-derived letters, then the explicit ones (which win:
# ø, ł, đ are also "… WITH STROKE" letters and keep their v1 spelling).
LATIN_TRANSLITERATION = str.maketrans({**name_derived_transliteration(), **LATIN_TRANSLITERATION_V1,
                                       **LATIN_TRANSLITERATION_EXPLICIT_V2})
# The other spellings each of those letters is commonly transliterated as
# (the first is the LATIN_TRANSLITERATION one). A surname that matches only
# under one of them is "ambiguous", never a pass and never a fail (cycle 8b):
# "Djordjevic" / "Đorđević", "Aeroe" / "Ærø", "Torsson" / "Þórsson".
# ("Soerensen" / "Sørensen" is also ambiguous, through the cycle-5
# dropped-umlaut fold, which author_match_person tries first.) Cycle 9 adds
# no alternatives for the translit-v2 letters.
TRANSLIT_ALTERNATIVES = {"ø": ("o", "oe"), "ł": ("l",), "æ": ("ae", "a", "e"), "œ": ("oe", "o", "e"),
                         "đ": ("d", "dj"), "ð": ("d", "dh", "th"), "þ": ("th", "t"), "ı": ("i",),
                         "ŋ": ("ng", "n"), "ĸ": ("k", "q")}
TRANSLIT_VARIANT_CAP = 64
HYPHENS = "-‐‑"
APOSTROPHES = "'’‘ʼ`´"


class BackendError(Exception):
    # kind: not-configured | refused | network | timeout | oversize | api |
    #       not-found | busy   (mapped to exit codes by the core)
    def __init__(self, backend, kind, message, http_status=None):
        super().__init__(message)
        self.backend = backend
        self.kind = kind
        self.http_status = http_status


def contact_email():
    # INTENT: the polite-pool / Unpaywall contact is the USER's explicit
    #   choice. Unset -> None (Crossref public pool; Unpaywall leg skipped).
    #   No address is ever hard-coded or inferred.
    v = (os.environ.get(CONTACT_ENV) or "").strip()
    return v if "@" in v and " " not in v else None


def key_value(env_name):
    # Returns the stripped key or "" (env files edited on Windows can carry a
    # trailing CR/space). Callers put it in a HEADER only, never a URL.
    if not env_name:
        return ""
    return (os.environ.get(env_name) or "").strip()


# §§ NORMALIZATION
def norm_doi(doi):
    if not doi:
        return None
    d = str(doi).strip().lower()
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", d)
    return d or None


def norm_title(title):
    # INTENT: a merge key that survives the cosmetic differences between a
    #   working-paper record and its journal version (case, punctuation,
    #   trailing asterisks, spaced colons, diacritics).
    if not title:
        return ""
    t = re.sub(r"<[^>]+>", " ", str(title))
    # Unicode punctuation (e.g. the U+2010 hyphen in "court‐mandated") must
    # become a space BEFORE the ASCII fold, which would otherwise delete it
    # and glue the neighboring words together.
    t = re.sub(r"[\W_]+", " ", t)
    # Cycle 8b: letters without a decomposition (ø, ł, æ, đ, þ, …) are spelled
    # out before the fold, which would otherwise delete them.
    t = unicodedata.normalize("NFKD", t).translate(LATIN_TRANSLITERATION)
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:160]


def verify_title_norm(title):
    # INTENT (B1, VERIFY_TITLE_NORM): the citation gate's own normalization.
    #   norm_title (above) folds to ASCII, so a CJK or Cyrillic title became ""
    #   and any two of them scored 1.00; and it truncates at 160 characters, so
    #   two long titles that differ only after character 160 scored 1.00.
    #   Here: markup dropped, NFKC (full-width forms, ligatures), casefold,
    #   Latin diacritics folded (a mark is dropped only when its base letter is
    #   Latin, so Cyrillic "й" survives), punctuation, symbols and separators
    #   (Unicode categories P, S, Z, C) become spaces, whitespace collapsed.
    #   Letters and digits of every script are kept; nothing is truncated.
    t = unicodedata.normalize("NFKC", re.sub(r"<[^>]+>", " ", str(title or ""))).casefold()
    out, base_latin = [], False
    for ch in unicodedata.normalize("NFD", t):
        if unicodedata.combining(ch):
            if not base_latin:
                out.append(ch)
            continue
        base_latin = unicodedata.name(ch, "").startswith("LATIN")
        out.append(" " if unicodedata.category(ch)[0] in "PSZC" else ch)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", "".join(out))).strip()


def title_letter_count(title):
    # Letters of any script in the verify-normalized title (B1 guard).
    return sum(1 for ch in verify_title_norm(title) if ch.isalpha())


def title_numerals(title):
    # INTENT (D2, VERIFY_NUMERAL_GUARD): the standalone numbers a title carries,
    #   as (token as written, value) in order. "Teachers I" vs "Teachers II",
    #   "Wave 3" vs "Wave 4" or "2018" vs "2019" differ by one token, which
    #   barely moves a character similarity yet names a different work.
    #   Counted (since numerals-v2; the v3 and v4 additions follow below):
    #   tokens of decimal digits in any script ("12" in
    #   "PreK-12", Arabic-Indic "٢٠١٨" = 2018; not "2D" or "w23001"); ordinals
    #   and decades by their number ("21st" = 21, "3rd" = 3, "1980s" = 1980);
    #   Roman II-XX wherever they stand as a token, any case; and the single
    #   letters I, V, X when they CLOSE a title segment — the last token, or
    #   followed by : ; , ( ) [ ] an en/em dash or a spaced hyphen — or
    #   directly follow a part word (PART_WORDS: "Part I of the …", "Vol. V").
    # REASONING: a standalone "I" is usually the English pronoun ("What I
    #   Learned", "Who Am I?") or an index glitch ("Intergenerational I
    #   ncome", a real record), and a numeral "I" in a title almost always
    #   ends a part name ("Teachers I: Evaluating Bias", "Mobility I:
    #   Childhood…") or follows a part word. "V" and "X" get the same rule
    #   because "Brown v. Board" and "X-ray" are common. Roman values compare
    #   equal to digits ("Part II" = "Part 2").
    # numerals-v3 (cycle 4): PART_WORDS also holds Phase / Wave / Title /
    #   Section / Stage / Round / Experiment / Grade / Level; a spelled-out
    #   one-twenty or first-twentieth counts when it follows a part word with
    #   only spaces between ("Part Two" = 2, "Grade three" = "Grade 3"; not
    #   "Grade, One Teacher"); and a segment-closing "I" right after an
    #   auxiliary verb (PRONOUN_I_AFTER: "Who Am I:") is the pronoun, so "Who
    #   Am I:" and "Who Am I?" carry the same (no) numbers. Spelled-out numbers
    #   elsewhere and digits glued to unspaced CJK text ("2018年") are not
    #   covered.
    # numerals-v4 (cycle 5): PART_WORDS also holds Year / Cohort ("Year One
    #   Report" vs "Year Two Report").
    t = unicodedata.normalize("NFKC", re.sub(r"<[^>]+>", " ", str(title or "")))
    found, prev, prev_end = [], "", 0
    for m in re.finditer(r"[^\W_]+", t):
        tok = m.group(0)
        low = tok.casefold()
        ordinal = re.fullmatch(r"(\d+)(?:st|nd|rd|th|s)", low)
        if tok.isdecimal():
            found.append((tok, int(tok)))
        elif ordinal and ordinal.group(1).isdecimal():
            found.append((tok, int(ordinal.group(1))))
        elif low in ROMAN_NUMERALS:
            found.append((tok, ROMAN_NUMERALS[low]))
        elif low in ROMAN_SEGMENT_END and (
                prev in PART_WORDS
                or (re.match(r"\s*(?:[:;,()\[\]–—]|\s-\s|$)", t[m.end():])
                    and not (low == "i" and prev in PRONOUN_I_AFTER))):
            found.append((tok, ROMAN_SEGMENT_END[low]))
        elif low in SPELLED_NUMERALS and prev in PART_WORDS and t[prev_end:m.start()].isspace():
            found.append((tok, SPELLED_NUMERALS[low]))
        prev, prev_end = low, m.end()
    return found


def numerals_differ(claimed_title, record_title):
    # Returns None when both titles carry the same numbers (as a multiset of
    # values), else (cited tokens, record tokens) for the WEAK note.
    a, b = title_numerals(claimed_title), title_numerals(record_title)
    if sorted(v for _, v in a) == sorted(v for _, v in b):
        return None
    return [t for t, _ in a], [t for t, _ in b]


def unescape(value):
    # ERIC and S2 strings carry HTML entities, sometimes double-escaped
    # ("&amp;quot;"); unescape until stable.
    if not isinstance(value, str):
        return value
    for _ in range(3):
        nxt = html.unescape(value)
        if nxt == value:
            break
        value = nxt
    return value


def strip_tags(value):
    # Crossref abstracts arrive as JATS XML (<jats:p>…); keep the text only.
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def short_oa_id(value):
    if not value:
        return None
    m = re.search(r"(W\d+)", str(value), re.IGNORECASE)
    return m.group(1).upper() if m else None


def arxiv_id_from(*values):
    # INTENT: derive an arXiv identifier from a DataCite arXiv DOI
    #   (10.48550/arXiv.2101.00001) or an arxiv.org abs/pdf URL. Used by the
    #   keyless `oa` arXiv leg, which needs no API call.
    for v in values:
        if not v:
            continue
        s = str(v)
        m = re.search(r"10\.48550/arxiv\.(\d{4}\.\d{4,5}(v\d+)?)", s, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(v\d+)?|[a-z\-]+(\.[A-Z]{2})?/\d{7})", s,
                      re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def record(**kw):
    # INTENT: the COMMON RECORD SCHEMA (from the 2026-10-02 scholarly-API
    #   design research, trimmed to what adapters can know). Provenance fields — raw_response_path,
    #   raw_sha256, fetched_at, query, rank — are added by the CORE, never by
    #   an adapter, so a new backend cannot misreport its own provenance.
    #   Field map to the design's field names: backend=source_backend, ids=backend_ids,
    #   cites=citation_count (per backend), oa={is_oa, oa_pdf_url(=oa_url),
    #   license, version, host}, fulltext=fulltext.available,
    #   retracted=retraction.status (True/False/None=unknown).
    for k in ("title", "venue", "abstract", "type"):
        kw[k] = unescape(kw.get(k, "")) or ""
    kw["authors"] = [unescape(x) for x in kw.get("authors") or [] if x]
    base = {"title": "", "year": None, "authors": [], "venue": "", "doi": None,
            "cites": None, "abstract": "", "type": "", "oa_url": None,
            "oa": {"is_oa": None, "license": None, "version": None, "host": None},
            "fulltext": False, "url": None, "ids": {}, "backend": "",
            "license_class": "open", "retracted": None}
    base.update(kw)
    return base


def first_surname(authors):
    # "Kraft, Matthew A." (ERIC) and "Matthew A. Kraft" (OpenAlex) -> "kraft"
    if not authors:
        return ""
    a = authors[0]
    name = a.split(",")[0] if "," in a else (a.split() or [""])[-1]
    return norm_title(name)


def name_tokens(name, fold="ascii"):
    # INTENT: ONE normalization for cited and record author names (R3):
    #   NFC first (a decomposed accent must not split a token), apostrophes
    #   deleted (O'Brien and OBrien both -> "obrien"), every other
    #   non-alphanumeric — hyphens, periods, commas — a token break
    #   ("Steenbergen-Hu" -> steenbergen hu on BOTH sides), then the NFKD ASCII
    #   fold norm_title uses ("Llargués" -> llargues). "ß" becomes "ss" first
    #   (cycle 4; the ASCII fold used to delete it: "Strauß" -> "strau").
    # Cycle 4 alternative folds, applied to BOTH sides by author_match when the
    #   default finds nothing:
    #   fold="joined"  hyphens deleted instead of splitting ("Al-Hassan" ->
    #                  alhassan, as "Alhassan");
    #   fold="german"  ä/ö/ü spelled ae/oe/ue before the ASCII fold ("Müller" ->
    #                  mueller, as "Mueller").
    # Cycle 5 (L3):
    #   fold="deumlaut" after the ASCII fold, ae/oe/ue become a/o/u
    #                  ("Mueller" -> muller, as a record that dropped the
    #                  umlaut, "Muller"). author_match grades such a hit
    #                  "ambiguous", never a pass: Mueller and Muller are also
    #                  two distinct surnames.
    # Cycle 6 (N3): only after a CONSONANT and before at least TWO more
    #   letters, so the fold reads the German spellings ("Mueller",
    #   "Schroeder", "Koehler", "Goetz") but leaves alone Xue / Yue / Hue / Doe /
    #   Lue (vowel pair at the end), Bauer (after a vowel) and Goel / Joel / Noel
    #   (one letter after: the review sketch's one-letter lookahead still
    #   folded Goel into Gol).
    # Cycle 8b (VERIFY_TRANSLIT): every fold spells out the letters the ASCII
    #   fold would delete (LATIN_TRANSLITERATION: "Sørensen" -> sorensen, not
    #   srensen; "Ærø" -> aero, not r; "Đorđević" -> dordevic), on both sides.
    #   Cycle 9 (translit-v2) widens the table ("Əliyev" -> aliyev, "Ħabib" ->
    #   habib, "Ɗanjuma" -> danjuma).
    t = unicodedata.normalize("NFC", str(name or ""))
    t = re.sub(f"[{APOSTROPHES}]", "", t)
    t = t.replace("ß", "ss").replace("ẞ", "SS")
    if fold == "joined":
        t = re.sub(f"(?<=\\w)[{HYPHENS}](?=\\w)", "", t)
    elif fold == "german":
        t = t.translate(GERMAN_TRANSLITERATION)
    t = re.sub(r"[\W_]+", " ", t)
    t = unicodedata.normalize("NFKD", t).translate(LATIN_TRANSLITERATION)
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    if fold == "deumlaut":
        t = re.sub(r"(?<=[b-df-hj-np-tv-z])([aou])e(?=[a-z]{2})", r"\1", t)
    return re.sub(r"[^a-z0-9]+", " ", t).split()


def cited_first_name(cited):
    # The first named author of a citation as written: parenthetical asides
    # dropped ("Smith (2019)", "Smith (Ed.)"), then everything from an
    # "et al." / "and others" / co-author tail on.
    s = unicodedata.normalize("NFC", str(cited or "")).strip()
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s)
    s = re.split(r"(?:^|\s+)(?:et\.?\s+al\b\.?|and\s+others\b)|\s*&\s*|\s+and\s+", s, maxsplit=1, flags=re.I)[0]
    return s.strip()


def cited_surname_tokens(cited, pop_initials=True, fold="ascii"):
    # INTENT: the surname a citation names, as name tokens. Accepted forms:
    #   "Surname", "Surname, First", "First Surname", "F. Surname",
    #   "F.M. Surname", particle-led multi-token surnames ("van der Klaauw",
    #   "Wilbert van der Klaauw"), hyphenated ones ("Steenbergen-Hu"), and (W3)
    #   the forms a reference list prints: "Smith et al." / "Smith et al" /
    #   "Smith and others", co-author tails ("Smith and Jones", "Smith &
    #   Jones": the FIRST named author is checked), name suffixes ("Fryer
    #   Jr.", "Smith III") and Vancouver initials ("Smith JA": a trailing
    #   all-uppercase token of 1-3 letters after the surname). With
    #   pop_initials=False that trailing token is kept as the surname: the
    #   second reading author_match tries for "Xiaoming LI" (cycle 3, I-D).
    # Cycle 4 (rule v4): all-digit tokens are dropped ("Smith 2019", "Smith
    #   2019a": a year printed without parentheses), and a trailing editor mark
    #   ("Smith Ed.", "Smith Eds.") is stripped like a suffix; "Mc"/"Mac"
    #   written apart start the surname like a particle ("John Mc Donald" ->
    #   mc donald). `fold` is the name_tokens fold of the returned tokens.
    # ASSUMES: without a comma or a particle, the LAST remaining word is the
    #   surname, so a two-word surname without a particle ("García Márquez")
    #   is checked on its last word only. Returns [] when no surname remains.
    s = cited_first_name(cited)
    if "," in s:
        s = s.split(",")[0]
    words = [w for w in s.split() if not re.fullmatch(r"(?:[^\W\d_]\.-?)+|[^\W\d_]", w)   # drop initials
             and not re.fullmatch(r"\d+[a-z]?[.,;:]?", w)]                                 # and years (v4)
    while len(words) > 1 and words[-1].lower().strip(".,") in SURNAME_SUFFIXES | EDITOR_MARKS:
        words.pop()
    if pop_initials and len(words) > 1 and words[-1].isalpha() and words[-1].isupper() and len(words[-1]) <= 3:
        words.pop()   # Vancouver initials: "Smith JA"
    for i, w in enumerate(words[:-1]):
        if w.lower().rstrip(".") in NAME_PARTICLES | NAME_JOIN_PREFIXES:
            return name_tokens(" ".join(words[i:]), fold)
    return name_tokens(words[-1], fold) if words else []


def surname_zone(name, fold="ascii"):
    # The tokens a record author's SURNAME can end on: the part before the
    # comma in "Kraft, Matthew A." (ERIC), else the whole "First Last" name
    # (OpenAlex), in both cases without a trailing Jr/Sr/II-IV.
    toks = name_tokens(name.split(",")[0] if "," in str(name) else name, fold)
    while len(toks) > 1 and toks[-1] in SURNAME_SUFFIXES:
        toks.pop()
    return toks


def surname_hits(want, authors, fold="ascii"):
    # (position, author, ends_surname) for every listed author whose name
    # contains the cited surname tokens `want` as a contiguous run. Cycle 3
    # (I-D): when a name particle is involved on either side, the run may also
    # be spaced differently — "de la cruz" is found in "Juan Dela Cruz" and
    # "dela cruz" in "Juan de la Cruz" — by comparing the tokens joined. Cycle 4:
    # "Mc"/"Mac" count as such a particle ("McDonald" in "John Mc Donald").
    # `fold` tokenizes the record names the way `want` was tokenized.
    n, joined = len(want), "".join(want)
    joiners = NAME_PARTICLES | NAME_JOIN_PREFIXES
    want_particle = any(w in joiners for w in want)
    hits = []
    for i, a in enumerate(authors):
        toks, zone = name_tokens(a, fold), surname_zone(a, fold)
        if any(toks[j:j + n] == want for j in range(len(toks) - n + 1)):
            hits.append((i, a, zone[-n:] == want))
            continue
        windows = [toks[j:k] for j in range(len(toks)) for k in range(j + 1, len(toks) + 1)]
        if any("".join(w) == joined and (want_particle or any(x in joiners for x in w)) for w in windows):
            hits.append((i, a, any("".join(zone[j:]) == joined for j in range(len(zone)))))
    return hits


def org_initials(name):
    # The acronym readings of an organization name (cycle 4): the first
    # letters of its words, ACRONYM_STOPWORDS skipped, with a hyphenated word
    # read both as ONE word ("Co-operation" -> C: OECD) and split ("Co" +
    # "operation" -> CO). Empty unless the name contains an ORG_WORDS word,
    # so a person's initials ("Oscar Ellis Carl Davis") never form one.
    # Cycle 5 (M2): ORG_WORDS holds plurals ("National Institutes of Health" ->
    # NIH), and a leading "U.S." / "United States" is read both with and
    # without it ("U.S. Bureau of Labor Statistics" -> BLS and USBLS; "U.S.
    # Department of Agriculture" -> DA and USDA).
    if not ORG_WORDS & set(name_tokens(name)):
        return set()
    # Cycle 8b: "Ørsted Institute" reads OI, not RI (LATIN_TRANSLITERATION).
    t = unicodedata.normalize("NFKD", unicodedata.normalize("NFC", str(name))).translate(LATIN_TRANSLITERATION)
    t = t.encode("ascii", "ignore").decode()
    out = set()
    for text in dict.fromkeys((t, ACRONYM_OPTIONAL_PREFIX.sub("", t, count=1))):
        for split in (False, True):
            words = re.findall(r"[A-Za-z]+" if split else r"[A-Za-z]+(?:-[A-Za-z]+)*", text)
            initials = "".join(w[0] for w in words if w.lower() not in ACRONYM_STOPWORDS)
            if len(initials) >= 2:
                out.add(initials.lower())
    return out


def is_bare_acronym(cited, min_letters=ACRONYM_MIN_LETTERS):
    # True when the WHOLE cited first-author name (a trailing period and any
    # parenthetical such as a year dropped) is one all-caps token of
    # min_letters-8 letters: "OECD", "OECD (2019)", "NIH."; not "Smith (APA)".
    first = cited_first_name(cited).strip().rstrip(".")
    return bool(re.fullmatch(rf"[A-Z]{{{min_letters},{ACRONYM_MAX_LETTERS}}}", first))


def cited_acronyms(cited):
    # The organization acronym a citation offers: cycle 5 (M1, L2) reads one
    # ONLY when the whole cited name is an all-caps 3-8 letter token ("OECD",
    # "OECD (2019)"). A parenthetical is never read as the cited author's
    # acronym: "Smith (APA)" and "American Psychological Association (APA)"
    # offer none (cycle 4 read them, so "(APA)" passed on any record whose
    # organization had the initials APA, whatever the name before it said).
    return {cited_first_name(cited).strip().rstrip(".").lower()} if is_bare_acronym(cited) else set()


def is_acronym(text, min_letters=2):
    # One all-caps token of min_letters-8 letters, a trailing period allowed
    # ("APA", "NBER.").
    return bool(re.fullmatch(rf"[A-Z]{{{min_letters},{ACRONYM_MAX_LETTERS}}}", str(text or "").strip().rstrip(".")))


def is_org_name(name):
    # INTENT (cycle 6): is this name (cited part or listed author) an
    #   ORGANIZATION? It must contain an ORG_WORDS word, and either have two or
    #   more words (initials not counted) before its first comma ("World Bank",
    #   "Jane Board") or carry the ORG_WORDS word after the comma ("ACT, Inc.",
    #   "APA, American Psychiatric Association"). "Bank", "Board, Jane" and
    #   "Union, J." stay persons.
    # ASSUMES: a person whose two-word name holds an ORG_WORDS word ("Jane
    #   Board") is read as an organization; a citation of that person by
    #   surname alone is then capped at WEAK (cost of the conservative rule).
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", str(name or ""))
    if not ORG_WORDS & set(name_tokens(s)):
        return False
    head, _, tail = s.partition(",")
    return len([w for w in name_tokens(head) if len(w) > 1]) >= 2 or bool(ORG_WORDS & set(name_tokens(tail)))


def org_key(name, fold="ascii"):
    # The exact-comparison key of an organization name: name_tokens with a
    # leading "The" dropped, as a tuple; a name that would become empty keeps
    # its tokens. fold="joined" deletes hyphens ("Co-operation" =
    # "Cooperation").
    # Cycle 7 (M1): a leading national prefix ("U.S.", "US", "USA", "United
    #   States (of America)", after any "The") is KEPT, spelled as the single
    #   token ORG_PREFIX_MARK, so its forms compare equal ("U.S. Department of
    #   Education" = "United States Department of Education") and org_exact
    #   decides when it may be set aside (the listed side only).
    # Cycle 7 (L2): "&" is read as "and" ("Bill & Melinda Gates Foundation" =
    #   "Bill and Melinda Gates Foundation"); name_tokens would delete it.
    toks = name_tokens(str(name or "").replace("&", " and "), fold)
    if toks[:1] == ["the"] and len(toks) > 1:
        toks = toks[1:]
    for lead in ORG_NATIONAL_PREFIXES:
        if tuple(toks[:len(lead)]) == lead and len(toks) > len(lead):
            toks = [ORG_PREFIX_MARK] + toks[len(lead):]
            break
    return tuple(toks)


def org_exact(cited, author):
    # INTENT (cycle 7, VERIFY_ORG_RULE "org-conservative-v2"): is the cited
    #   organization name the listed `author`'s WHOLE name? Equal org_keys
    #   (default or hyphen-"joined" fold), or the listed name carries the
    #   national prefix, the cited name does not, and the cited name equals the
    #   rest ("Department of Education" on "U.S. Department of Education").
    # REASONING (M1): set aside on the listed side only. A citation that ADDS
    #   the prefix to a bare listed name may name another country's body, and
    #   a prefix that leaves one content word ("US Bank" -> "Bank") is part of
    #   the name, so both stay ORG_NOT_EXACT for the adjudicator.
    for fold in ("ascii", "joined"):
        c, r = org_key(cited, fold), org_key(author, fold)
        if not c:
            continue
        if c == r:
            return True
        rest = r[1:]
        if r[:1] == (ORG_PREFIX_MARK,) and c == rest and len([t for t in rest if t not in ACRONYM_STOPWORDS]) >= 2:
            return True
    return False


def cited_org_parts(cited):
    # INTENT (cycle 6): the organization reading of a cited author, or None
    #   for a person (or a bare acronym, which author_match_person handles).
    #   Returns (full, acronyms, others):
    #     full      the cited FULL organization name — the only part that can
    #               pass, and only by an exact org_key match;
    #     acronyms  all-caps 2-8 letter parts, which can only corroborate a
    #               passed full name or make a non-exact match "ambiguous";
    #     others    any other parenthetical ("Jane Fakeman (National Bureau of
    #               Economic Research)"), which can only make it "ambiguous".
    #   Forms: "Full", "Full (ACR)", "Full [ACR]", "Full, ACR", and with the
    #   full name second, "ACR (Full)", "ACR [Full]", "ACR, Full" (N1, N5).
    # REASONING: the full name is the identity claim; an acronym maps to
    #   several organizations (APA = Psychological / Psychiatric), so reading
    #   it is a semantic judgment, left to the adjudicator (step-aside decision).
    raw = unicodedata.normalize("NFC", str(cited or "")).strip()
    raw = re.split(r"(?:^|\s+)(?:et\.?\s+al\b\.?|and\s+others\b)", raw, maxsplit=1, flags=re.I)[0]
    parens = [(a or b).strip() for a, b in re.findall(r"\(([^)]*)\)|\[([^\]]*)\]", raw)]
    parens = [p for p in parens if p and not re.fullmatch(r"\d{4}[a-z]?|n\.?\s?d\.?", p, re.I)]   # years
    main = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", raw).strip().strip(",;").strip()
    head, sep, tail = (x.strip() for x in main.partition(","))
    acr_parens = [p for p in parens if is_acronym(p)]
    long_parens = [p for p in parens if not is_acronym(p) and len([w for w in name_tokens(p) if len(w) > 1]) >= 2]
    if is_acronym(main):
        if not long_parens:
            return None   # a bare acronym ("APA", "OECD (2019)"): author_match_person
        return long_parens[0], [main] + acr_parens, long_parens[1:]                     # "ACR (Full)"
    if sep and is_acronym(head) and ORG_WORDS & set(name_tokens(tail)):
        return tail, [head] + acr_parens, long_parens                                  # "ACR, Full"
    if sep and is_acronym(tail) and is_org_name(head):
        return head, [tail] + acr_parens, long_parens                                  # "Full, ACR"
    lead = [w for w in name_tokens(head) if len(w) > 1]
    if (ORG_WORDS & set(name_tokens(raw)) and len(lead) >= 2) or is_org_name(main):
        return main, acr_parens, [p for p in parens if not is_acronym(p)]               # "Full (ACR)"
    return None


def org_relation(full, acronyms, others, author):
    # Why a NON-exact cited organization may still be the listed `author`
    # (cycle 6; each makes the match "ambiguous", never a pass), or None.
    a_key, f_key = org_key(author), org_key(full) if full else ()
    content = lambda k: {t for t in k if t not in ACRONYM_STOPWORDS}  # noqa: E731
    for x in acronyms:
        if len(x.strip().rstrip(".")) >= ACRONYM_MIN_LETTERS and x.strip().rstrip(".").lower() in org_initials(author):
            return f"the acronym '{x}' equals the initials of '{author}', and an acronym can name several organizations"
        if org_key(x) == a_key:
            return f"only the acronym '{x}' is listed, not the cited name"
    if f_key and len(a_key) == 1 and is_acronym(author, ACRONYM_MIN_LETTERS) and a_key[0] in org_initials(full):
        return f"the listed '{author}' is the acronym of the cited name"
    for p in others:
        if org_key(p) == a_key:
            return f"only the parenthetical '{p}' equals '{author}'"
    n, m = len(f_key), len(a_key)
    if f_key and (any(a_key[j:j + n] == f_key for j in range(m - n + 1))
                  or any(f_key[j:j + m] == a_key for j in range(n - m + 1))):
        return f"one name contains the other ('{full}' / '{author}'), which may be a different body"
    if f_key and content(f_key) and content(a_key) and (content(f_key) <= content(a_key)
                                                       or content(a_key) <= content(f_key)):
        return f"one name is a partial form of the other ('{full}' / '{author}')"
    return None


def org_not_exact(base, position, author, why):
    # The cycle-6 "ambiguous" organization outcome (name_part ORG_NOT_EXACT).
    return dict(base, found=True, position=position, matched_author=author, name_part=ORG_NOT_EXACT, ok=None,
                status="ambiguous", reason=f"{ORG_NOT_EXACT} (adjudicate): {why}")


# Cycle 7 (H1): the name_part of a person-path match whose given names do not
# agree (rule 1 in author_match_person).
GIVEN_NAME_DIFFERS = "surname; given name differs"
YEAR_TOKEN = re.compile(r"\d+[a-z]?[.,;:]?")
INITIAL_TOKEN = re.compile(r"(?:[^\W\d_]\.-?)+|[^\W\d_]")


def cited_given_tokens(cited, pop_initials=True, fold="ascii"):
    # INTENT (cycle 7, H1): the GIVEN part of a cited person name as name
    #   tokens — the words and initials before the surname that
    #   cited_surname_tokens reads ("C. Kirabo Jackson" -> c kirabo), the part
    #   after a comma ("Smith, J. A." -> j a), initials printed after the
    #   surname ("Smith J."), and, in the reading that takes them as initials
    #   (pop_initials), Vancouver initials split into letters ("Smith JA" ->
    #   j a). Years, suffixes and editor marks are dropped exactly as
    #   cited_surname_tokens drops them.
    s = cited_first_name(cited)
    if "," in s:
        return [t for t in name_tokens(s.split(",", 1)[1], fold)
                if not t.isdigit() and t not in SURNAME_SUFFIXES | EDITOR_MARKS]
    words = [w for w in s.split() if not YEAR_TOKEN.fullmatch(w)]
    initial = [bool(INITIAL_TOKEN.fullmatch(w)) for w in words]
    core = [i for i, w in enumerate(words) if not initial[i]]
    while len(core) > 1 and words[core[-1]].lower().strip(".,") in SURNAME_SUFFIXES | EDITOR_MARKS:
        core.pop()
    vanc = []
    last = words[core[-1]] if core else ""
    if pop_initials and len(core) > 1 and last.isalpha() and last.isupper() and len(last) <= 3:
        vanc = list(last.lower())
        core.pop()
    if not core:
        return []
    start = next((i for i in core[:-1] if words[i].lower().rstrip(".") in NAME_PARTICLES | NAME_JOIN_PREFIXES),
                 core[-1])
    given = [w for i, w in enumerate(words) if i < start or (i > core[-1] and initial[i])]
    return name_tokens(" ".join(given), fold) + vanc


def record_given_tokens(author, want, fold="ascii"):
    # The GIVEN part of a listed author whose surname ends with the cited
    # surname tokens `want`: after the comma in "Kraft, Matthew A." (ERIC),
    # else what precedes the surname in "Matthew A. Kraft" (the surname run
    # compared joined, so "Juan de la Cruz" / "Juan Dela Cruz" both work).
    if "," in str(author):
        return [t for t in name_tokens(str(author).split(",", 1)[1], fold) if t not in SURNAME_SUFFIXES]
    zone, joined = surname_zone(author, fold), "".join(want)
    for j in range(len(zone)):
        if "".join(zone[j:]) == joined:
            return zone[:j]
    return zone[:-len(want)] if len(zone) > len(want) else []


def given_extend(cited_given, record_given):
    # Words both names share right BEFORE the surname belong to the surname
    # (a two-word surname, "García Márquez" on "Gabriel García Márquez"; a
    # middle name used as the cited given name, "Kirabo Jackson" on "C. Kirabo
    # Jackson"; particles spaced or joined, "Dela Cruz" on "Juan de la Cruz"):
    # drop them from both ends, comparing joined, and return what is left.
    cg, rg = list(cited_given), list(record_given)
    while cg and rg:
        m = next((m for m in range(1, len(rg) + 1) if "".join(rg[-m:]) == cg[-1]), 0)
        if m:
            del rg[-m:]
            cg.pop()
            continue
        k = next((k for k in range(2, len(cg) + 1) if "".join(cg[-k:]) == rg[-1]), 0)
        if not k:
            break
        del cg[-k:]
        rg.pop()
    return cg, rg


def name_shape(tokens):
    # (counted words, has an initial): particles, Mc/Mac, suffixes, editor
    # marks and digits are not counted; a one-letter token is an initial.
    skip = NAME_PARTICLES | NAME_JOIN_PREFIXES | SURNAME_SUFFIXES | EDITOR_MARKS
    words = [t for t in tokens if t not in skip and not t.isdigit()]
    return len(words), any(len(t) == 1 for t in words)


def given_compatible(g, x):
    # One given word against another: equal, or one is the other's initial
    # ("j" = "john", either direction).
    return g == x or (len(x) == 1 and g[0] == x) or (len(g) == 1 and x[0] == g)


def cited_given_hyphenated(cited, pop_initials=True):
    # Cycle 8 (INFO): True when the cited given part holds a hyphen-joined
    # given name, full ("Jean-Paul") or as initials ("J.-P."): read with the
    # hyphens deleted (fold "joined", the period before a hyphen dropped first
    # so "J.-P." joins too) it has fewer tokens than read split.
    split = cited_given_tokens(cited, pop_initials, "ascii")
    joined = cited_given_tokens(re.sub(f"\\.(?=[{HYPHENS}])", "", str(cited or "")), pop_initials, "joined")
    return len(joined) < len(split)


def person_step_aside(cited, matched, want, pop_initials=True, fold="ascii"):
    # INTENT (cycle 7, H1; cycle 8 VERIFY_AUTHOR_RULE "contiguous-surname-v8"):
    #   why a person-path surname match must NOT pass, as (name_part, reason),
    #   or None when it may pass. Step-aside decision: the rule layer cannot tell a person
    #   from an organization whose name holds no ORG_WORDS word ("Health
    #   Canada"), or a nickname from another person ("Jane" / "John"), so it
    #   steps aside to "ambiguous" (WEAK) rather than guessing:
    #   rule 2  the cited name has 3+ counted words and no initial (likely an
    #           organization) and does not reproduce the listed name whole;
    #           cycle 8: a hyphen-joined given name counts as ONE word
    #           ("Jean-Paul Sartre" is two words, not an organization shape);
    #   rule 3  the listed name has 3+ counted words, no initial and a
    #           connective word (ACRONYM_STOPWORDS: "Teach For America"), and
    #           the cited name does not reproduce it whole;
    #   rule 1  the cited name carries given words and its first one equals
    #           none of the listed author's given words or their initials
    #           (after given_extend), in either direction ("J." = "John");
    #           cycle 8 (N-2): when BOTH sides carry 2+ given words or
    #           initials, the second must agree too ("John Q." vs "John A.",
    #           "J.-M." vs "Jean-Paul"); cycle 9 (B-1): so must every later
    #           aligned one ("John Q. R." vs "John Q. S."); and a hyphen-joined cited given name
    #           is one name, so the listed side must carry all its parts
    #           ("Jean-Paul Smith" on "Jean Smith");
    #   N-3     (cycle 8) the cited name carries given words but the listed
    #           name has none left to compare them with ("Health Canada" on a
    #           record listing just "Canada", "Jane Smith" on "Smith").
    # ASSUMES: a 3-word listed person without an initial or a connective
    #   ("Andre Joshua Nickow", "Gabriel García Márquez") is a person; the rule
    #   does not try to recognize given names (that would be a word list).
    cg0 = cited_given_tokens(cited, pop_initials, fold)
    rg0 = record_given_tokens(matched, want, fold)
    cg, rg = given_extend(cg0, rg0)
    whole = not cg and not rg
    who = cited_first_name(cited).strip()
    c_raw = name_tokens(who)
    c_words, c_init = name_shape(c_raw)
    # REASONING (cycle 8, INFO): a hyphenated given name split into two tokens
    #   made "Jean-Paul Sartre" a 3-word, initial-less name, so rule 2 stepped
    #   it aside as an organization (name_part ORG_NOT_EXACT on a person).
    #   Counted with hyphens deleted it is two words, and rule 1 judges it.
    if c_words >= 3 and not c_init and cited_given_hyphenated(cited, pop_initials):
        c_words = name_shape(name_tokens(who, "joined"))[0]
    c_init = c_init or any(w.isalpha() and w.isupper() and len(w) <= 3 for w in who.split()[1:])
    if c_words >= 3 and not c_init and not whole:
        return ORG_NOT_EXACT, (f"{ORG_NOT_EXACT} (adjudicate): the cited name '{who}' has three or more words and "
                               f"no initial, so it may be an organization's name, and it does not reproduce "
                               f"'{matched}' whole")
    r_toks = name_tokens(matched)
    r_words, r_init = name_shape(r_toks)
    if r_words >= 3 and not r_init and ACRONYM_STOPWORDS & set(r_toks) and not whole:
        return ORG_NOT_EXACT, (f"{ORG_NOT_EXACT} (adjudicate): the listed name '{matched}' has three or more words, "
                               f"no initial and a connective word, so it may be an organization's name, and "
                               f"'{who}' does not reproduce it whole")
    if cg and rg:
        g = cg[0]
        if not any(given_compatible(g, x) for x in rg):
            return GIVEN_NAME_DIFFERS, (f"the surname matches '{matched}' but the cited given name '{g}' is none of "
                                        f"its given names ({' '.join(rg)}) nor their initial: it may be another "
                                        "person, a nickname or transliteration, or an organization whose name has "
                                        "no organization word")
        # Cycle 8 (N-2): rule 1 read only the first cited given word, so "John
        #   Q. Smith" passed on "John A. Smith" and "J.-M. Sartre" on "Jean-Paul
        #   Sartre". With two or more on both sides, the second must agree too.
        # Cycle 9 (B-1, review-8 sketch F1): the cycle-8 check read only the
        #   SECOND position, so "John Q. R. Smith" passed on "John Q. S. Smith".
        #   Every aligned position after the first must agree; zip stops at the
        #   shorter side, so "J. Q. Smith" on "John Quincy Adams Smith" and
        #   "Smith JAB" on "John A. Smith" still pass.
        if len(cg) >= 2 and len(rg) >= 2 and not all(given_compatible(a, b) for a, b in zip(cg[1:], rg[1:])):
            pos = next(i for i, (a, b) in enumerate(zip(cg[1:], rg[1:]), 2) if not given_compatible(a, b))
            return GIVEN_NAME_DIFFERS, (f"the surname and first given name match '{matched}' but cited given word or "
                                        f"initial {pos} '{cg[pos - 1]}' is not its '{rg[pos - 1]}' nor its initial: "
                                        "it may be another person with the same first name and surname")
        if len(rg) < len(cg) and cited_given_hyphenated(cited, pop_initials):
            return GIVEN_NAME_DIFFERS, (f"the cited hyphenated given name ({' '.join(cg)}) is one name, and "
                                        f"'{matched}' lists only part of it ({' '.join(rg)})")
    if cg and not rg:
        # Cycle 8 (N-3): the cited given words have nothing to be compared
        #   with ("Health Canada" on a record listing just "Canada", "Jane
        #   Smith" on "Smith"), so the surname alone cannot confirm the name.
        return GIVEN_NAME_DIFFERS, (f"the surname matches '{matched}', which lists no given name to compare with "
                                    f"the cited '{' '.join(cg)}': the surname alone cannot confirm it is the same "
                                    "person, and the cited name may be an organization's")
    return None


def cited_org_shape(cited):
    # INTENT (cycle 7, L1): why a cited name that matched NO listed author may
    #   be an organization the rule layer cannot read, or None. Then it is
    #   "ambiguous" (ORG_NOT_EXACT), never a fail: the rule does not expand
    #   abbreviations ("Am. Psychiatric Assn." on "American Psychiatric
    #   Association" was a false MISMATCH, exit 11).
    #   - an abbreviation: a word of 2+ letters ending in "." that is NOT the
    #     name's last word (a final period is reference-list punctuation:
    #     "Fakeman." still fails); suffixes, editor marks and particles
    #     ("Jr.", "Ed.", "St.") are not abbreviations;
    #   - a connective word (ACRONYM_STOPWORDS) between its words ("Teach For
    #     All", "Dept of Ed");
    #   - 3+ counted words and no initial (person_step_aside rule 2).
    who = cited_first_name(cited).strip()
    words = [w for w in who.replace(",", " ").split() if not YEAR_TOKEN.fullmatch(w)]
    skip = SURNAME_SUFFIXES | EDITOR_MARKS | NAME_PARTICLES | NAME_JOIN_PREFIXES
    abbr = [w for w in words[:-1] if re.fullmatch(r"[^\W\d_]{2,}\.", w) and w.lower().rstrip(".") not in skip]
    if abbr:
        return f"the abbreviated word(s) {' '.join(abbr)}"
    toks = name_tokens(who)
    if len(toks) >= 3 and ACRONYM_STOPWORDS & set(toks[1:-1]):
        return "a connective word between its words"
    n, has_init = name_shape(toks)
    if n >= 3 and not has_init:
        return "three or more words and no initial"
    return None


def cited_final_abbreviation(cited, authors):
    # INTENT (cycle 8, N-1): the cited name's FINAL word when it may be an
    #   abbreviation of a listed author's word, else None. cited_org_shape
    #   reads a final period as reference-list punctuation ("Fakeman."), so
    #   "RAND Corp." and "Brookings Inst." failed (MISMATCH) on "RAND
    #   Corporation" / "Brookings Institution". Here: a name of 2+ words whose
    #   last word is 2+ letters plus "." (not a suffix or editor mark), and
    #   whose stem is a PROPER prefix of a word in a listed author's name.
    # REASONING: no word list — the listed name itself shows the expansion.
    #   "Fakeman." (one word), "Jane Fakeman." and "J. Fakeman." (no listed
    #   word begins "fakeman") still fail.
    words = cited_first_name(cited).split()
    last = words[-1] if words else ""
    stem = "".join(name_tokens(last))
    if (len(words) >= 2 and re.fullmatch(r"[^\W\d_]{2,}\.", last) and stem
            and stem not in SURNAME_SUFFIXES | EDITOR_MARKS
            and any(t.startswith(stem) and t != stem for a in authors or [] for t in name_tokens(a))):
        return last
    return None


# Cycle 8b: the name_part of a surname that matches only under an alternative
# transliteration (translit_alternative_hit).
TRANSLIT_ALTERNATIVE = "surname; alternative transliteration"


def translit_variants(text):
    # Every spelling of `text` with each TRANSLIT_ALTERNATIVES letter replaced
    # by one of its alternatives (NFD first, so "ǿ" is ø + acute), capped at
    # TRANSLIT_VARIANT_CAP; [text] when it has none of those letters.
    out = [""]
    for ch in unicodedata.normalize("NFD", str(text or "")):
        alts = TRANSLIT_ALTERNATIVES.get(ch.lower())
        if alts:
            alts = [a.upper() for a in alts] if ch.isupper() else alts
            out = [v + a for v in out for a in alts][:TRANSLIT_VARIANT_CAP]
        else:
            out = [v + ch for v in out]
    return out


def translit_alternative_hit(cited, authors):
    # INTENT (cycle 8b, VERIFY_AUTHOR_RULE "contiguous-surname-v9"): when the
    #   cited surname matched no one, (position, author) of the first listed
    #   author whose surname it matches under an ALTERNATIVE transliteration of
    #   a TRANSLIT_ALTERNATIVES letter on either side ("Djordjevic" /
    #   "Đorđević", "Aeroe" / "Ærø", "Torsson" / "Þórsson"), else None.
    #   ("Soerensen" / "Sørensen" never gets here: the dropped-umlaut fold,
    #   tried earlier, already grades it ambiguous.)
    # REASONING (step-aside decision): ø is written o or oe, đ d or dj, æ ae or a; which one a
    #   reference list used is a spelling convention the rule cannot settle,
    #   so such a hit steps aside to "ambiguous" (never a pass), while a
    #   surname that matches under no spelling ("Nielsen" on "Anne Sørensen")
    #   still fails. A character table, not a word list.
    who = cited_first_name(cited)
    both = unicodedata.normalize("NFD", who + " " + " ".join(authors or []))
    if not any(ch.lower() in TRANSLIT_ALTERNATIVES for ch in both):
        return None
    for cv in translit_variants(who):
        want = cited_surname_tokens(cv)
        if not want:
            continue
        for i, a in enumerate(authors or []):
            if any(h[2] for av in translit_variants(a) for h in surname_hits(want, [av])):
                return i, a
    return None


def author_match(cited, authors, first_only=False):
    # R3: the cited surname must appear as a CONTIGUOUS token sequence inside
    # one author's name — "steenbergen hu" is not found in "Xueyan Hu", which
    # the old last-token-anywhere rule accepted. `position` is the matching
    # author (0 = first author); with first_only, only 0 passes.
    # W3 (rule v2) adds two outcomes besides pass (ok True) / fail (ok False):
    #   unchecked (ok None): no surname could be read from the citation, or the
    #     record lists no authors. Nothing was compared, so it never yields
    #     MISMATCH; it caps a passing title check at WEAK.
    #   ambiguous (ok None): the surname matches only a given or middle part of
    #     the name ("Kirabo" in "C. Kirabo Jackson"), not where the surname
    #     ends. Also caps at WEAK: it may be the wrong person, and it may be an
    #     East Asian name order or the first of two Spanish surnames.
    # Cycle 3 (rule v3) turns four former "fail" outcomes — each a MISMATCH on
    #   a genuine citation — into what was actually established:
    #   - W-C: nothing matched and a record author's name has no Latin-script
    #     letters ("王 伟", "Иван Петров"): the Latin-script cited surname was
    #     never compared with that name, so "not checked";
    #   - I-D organization: a cited author containing an ORG_WORDS word is
    #     compared by its whole name (or a parenthetical acronym), never by its
    #     last word ("Sciences"); not on the record -> "not checked";
    #   - I-D particles spaced or joined (surname_hits);
    #   - I-D name order: the cited name's tokens equal a record author's in
    #     another order ("Di Wu" vs "Wu Di") -> "ambiguous";
    #   - I-D upper-case surname: "Xiaoming LI" first reads "LI" as Vancouver
    #     initials (surname "xiaoming"); when that reading does not end a
    #     record author's surname but "li" does, the second reading is used.
    # Cycle 4 (rule v4) turns more former "fail" outcomes on genuine forms into
    #   pass or ambiguous, tried in this order only when nothing matched:
    #   - fold="joined" / fold="german" (name_tokens): the same surname with
    #     hyphens removed ("Al-Hassan" = "Alhassan") or umlauts spelled out
    #     ("Mueller" = "Müller") on both sides; a hit ending a surname passes,
    #     since only the spelling convention differs;
    #   - acronym: an all-caps 2-8 letter cited name equal to the initials of
    #     a record ORGANIZATION name (org_initials: "OECD" = "Organisation for
    #     Economic Co-operation and Development") passes;
    #   - dropped particle: a cited surname led by a particle the record omits
    #     ("von Hippel" vs "Paul T. Hippel", "de Souza" vs "Maria Souza") is
    #     ambiguous, not a pass: "Souza" alone may be another person.
    #   A cited author with fewer than two words before its first comma is
    #   read as a person even when a word is an ORG_WORDS word ("Board",
    #   "Board, Jane"). A multi-word person name containing one ("Jane Board")
    #   is still read as an organization and is "not checked" unless found
    #   whole: a person-reading fallback was tried and rejected, because it let
    #   "National Academy of Sciences" pass on "Institute of … Sciences".
    # Cycle 5 (rule v5; M1 fixes a cycle-4 regression):
    #   - an acronym is read only from a bare cited name of 3-8 capitals
    #     (cited_acronyms), so "Smith (APA)" is the person Smith, and two-letter
    #     collisions ("UN" vs "University of Nebraska") never pass (L2);
    #   - an organization is passed only on its FULL cited name. A full name
    #     that is not on the record is never rescued by its parenthetical:
    #     when the parenthetical matches a record name or a record
    #     organization's initials the result is "ambiguous" (name_part
    #     "organization acronym only"), else "not checked". A parenthetical
    #     acronym beside a full name that DID match only corroborates it
    #     (acronym_corroborates True / False, informational);
    #   - M2: an all-caps 2-8 letter cited name that matched nothing is "not
    #     checked", never "fail" (the rule cannot read every acronym: CDC is
    #     not the initials of "Centers for Disease Control and Prevention");
    #   - L1: a separate "Mc"/"Mac" that leaves no match is retried without
    #     it ("Mac Hulbert" vs "M. Hulbert") -> "ambiguous";
    #   - L3: a surname that matches only with ae/oe/ue read as a/o/u on both
    #     sides ("Mueller" vs "H. Muller", fold "deumlaut") -> "ambiguous".
    # Cycle 8b (rule v9): letters without a decomposition are transliterated
    #   on both sides (name_tokens), and a surname that matches only under an
    #   alternative transliteration ("Djordjevic" vs "Ana Đorđević", fold
    #   "translit-alt") -> "ambiguous" (translit_alternative_hit).
    acronyms = cited_acronyms(cited)

    def acronym_hit():
        # (position, author) of the first record organization whose initials
        # equal a cited acronym, else None.
        for i, a in enumerate(authors or []):
            if acronyms & org_initials(a):
                return i, a
        return None

    # Cycle 6 (step-aside decision, VERIFY_ORG_RULE "org-conservative-v1"):
    #   - an organization (cited_org_parts; "Board", "Board, J." and "Board,
    #     Jane" stay persons, cycle 4) passes ONLY when its full-name part
    #     equals a listed author's whole name (org_exact: case, punctuation,
    #     accents, a leading "The" set aside; "&" read as "and"; a national
    #     prefix set aside on the LISTED side only, cycle 7 M1; the "joined"
    #     hyphen fold also accepted). An acronym beside a passed full
    #     name only corroborates it (acronym_corroborates, informational).
    #   - any weaker relation (org_relation: acronym = initials, acronym or
    #     parenthetical = a listed name, containment, partial name) is
    #     "ambiguous" with name_part ORG_NOT_EXACT, never a pass, whatever the
    #     form ("ACR (Full)" N1, "ACR, Full" N5, "Full [ACR]", substrings N4).
    #     It is a semantic question (is this the same body?), routed to the
    #     forthcoming citation adjudicator and, until it exists, a human.
    #   - no relation at all: "not checked" (cycle-3 I-D), not a fail: a cited
    #     organization may be the sponsor or publisher the record does not
    #     list, and the labeled set and existing tests pin "not checked".
    #   This replaces the cycle-4 contiguous-substring pass and the cycle-5
    #   "organization acronym only" outcome.
    parts = cited_org_parts(cited)
    if parts is not None:
        full, acr, others = parts
        base = {"cited": cited, "surname": " ".join(name_tokens(full)), "found": False, "position": None,
                "matched_author": None, "name_part": None, "first_author_required": bool(first_only)}
        if not authors:
            return dict(base, ok=None, status="unchecked", reason="the record lists no authors")
        for i, a in enumerate(authors):
            if org_exact(full, a):
                res = dict(base, found=True, position=i, matched_author=a, name_part="organization")
                acr3 = [x.strip().rstrip(".").lower() for x in acr if is_acronym(x, ACRONYM_MIN_LETTERS)]
                if acr3:
                    res["acronym_corroborates"] = any(x in org_initials(a) for x in acr3)
                if first_only and i != 0:
                    return dict(res, ok=False, status="fail", reason=f"found as author {i + 1}, not the first author")
                return dict(res, ok=True, status="pass", reason=None)
        for i, a in enumerate(authors):
            why = org_relation(full, acr, others, a)
            if why:
                return org_not_exact(base, i, a, why)
        return dict(base, ok=None, status="unchecked",
                    reason="the cited author reads as an organization and that name is not on the record's author "
                           "list (organizations are compared by their whole name only)")
    return author_match_person(cited, authors, first_only, acronym_hit)


def author_match_person(cited, authors, first_only=False, acronym_hit=None):
    # The person reading of author_match (its comment block documents the
    # rules); `acronym_hit` is author_match's organization-acronym probe.
    want = cited_surname_tokens(cited)
    base = {"cited": cited, "surname": " ".join(want), "found": False, "position": None, "matched_author": None,
            "name_part": None, "first_author_required": bool(first_only)}
    if not want or not authors:
        why = ("no surname could be read from the cited author" if not want else "the record lists no authors")
        return dict(base, ok=None, status="unchecked", reason=why)
    hits = surname_hits(want, authors)   # (position, author, ends_surname)
    # Cycle 7: the reading (Vancouver initials popped or not) and the fold
    #   that produced `hits`, so person_step_aside reads the given names the
    #   same way.
    reading, hit_fold = True, "ascii"
    alt = cited_surname_tokens(cited, pop_initials=False)
    if alt != want and not any(h[2] for h in hits):
        alt_hits = [h for h in surname_hits(alt, authors) if h[2]]
        if alt_hits:
            want, hits, reading = alt, alt_hits, False
            base["surname"] = " ".join(want)
    if not hits:
        # Cycle 4: the same surname under another spelling convention.
        for fold in ("joined", "german"):
            w2 = cited_surname_tokens(cited, fold=fold)
            h2 = [h for h in surname_hits(w2, authors, fold) if h[2]] if w2 else []
            if h2:
                hits, want, hit_fold = h2, w2, fold
                base["surname"] = " ".join(w2)
                base["fold"] = fold
                break
    if not hits:
        hit = acronym_hit() if acronym_hit else None
        if hit:
            # Cycle 6 (step-aside decision): a bare acronym equal to a listed organization's
            #   initials is ORG_NOT_EXACT ("ambiguous"), no longer a pass: APA,
            #   AERA or NBER can each name more than one organization. With
            #   --first-author a hit on a later author still fails (kept).
            if first_only and hit[0] != 0:
                return dict(base, found=True, position=hit[0], matched_author=hit[1], name_part=ORG_NOT_EXACT,
                            ok=False, status="fail", reason=f"found as author {hit[0] + 1}, not the first author")
            return org_not_exact(base, hit[0], hit[1], f"the bare acronym '{cited_first_name(cited).strip()}' equals "
                                                       f"the initials of '{hit[1]}', and an acronym can name several "
                                                       "organizations")
        # Cycle 5 (L1): a separate leading "Mc"/"Mac" is dropped like a
        #   particle when nothing else matched ("Mac Hulbert" vs "M. Hulbert":
        #   "Mac" may be a given name), with the same "ambiguous" outcome.
        lead = 0
        while lead < len(want) - 1 and want[lead] in DROPPABLE_PARTICLES | NAME_JOIN_PREFIXES:
            lead += 1
        core_hits = [h for h in surname_hits(want[lead:], authors) if h[2]] if lead else []
        if core_hits:
            pos, matched, _ = core_hits[0]
            mac = any(w in NAME_JOIN_PREFIXES for w in want[:lead])
            res = dict(base, found=True, position=pos, matched_author=matched,
                       name_part="surname without Mc/Mac" if mac else "surname without particle")
            if first_only and pos != 0:
                return dict(res, ok=False, status="fail", reason=f"found as author {pos + 1}, not the first author")
            return dict(res, ok=None, status="ambiguous",
                        reason=(f"'{base['surname']}' matches '{matched}' only without '{' '.join(want[:lead])}', "
                                "which may be a given name or part of another person's surname") if mac else
                               (f"'{base['surname']}' matches '{matched}' only without the particle "
                                f"'{' '.join(want[:lead])}', so it may be another person with that surname"))
        # Cycle 5 (L3): the record dropped an umlaut the citation spells out
        #   (or the reverse): "Mueller" vs "H. Muller". Ambiguous, not a pass:
        #   Mueller and Muller are also two distinct surnames.
        w3 = cited_surname_tokens(cited, fold="deumlaut")
        h3 = [h for h in surname_hits(w3, authors, "deumlaut") if h[2]] if w3 else []
        if h3:
            pos, matched, _ = h3[0]
            res = dict(base, found=True, position=pos, matched_author=matched, name_part="surname", fold="deumlaut")
            if first_only and pos != 0:
                return dict(res, ok=False, status="fail", reason=f"found as author {pos + 1}, not the first author")
            return dict(res, ok=None, status="ambiguous",
                        reason=f"'{base['surname']}' matches '{matched}' only with ae/oe/ue read as a/o/u (an "
                               "umlaut dropped on one side), and the two spellings are also distinct surnames")
        full = name_tokens(cited_first_name(cited))
        for i, a in enumerate(authors):
            toks = name_tokens(a)
            if len(full) > 1 and toks != full and sorted(toks) == sorted(full):
                res = dict(base, found=True, position=i, matched_author=a, name_part="other")
                if first_only and i != 0:
                    return dict(res, ok=False, status="fail", reason=f"found as author {i + 1}, not the first author")
                return dict(res, ok=None, status="ambiguous",
                            reason=f"the cited name matches '{a}' with its names in another order (given and family "
                                   "name swapped, e.g. an East Asian name order), so the surname is uncertain")
        # W-C: one record author name with no Latin-script letters is enough —
        #   the cited (Latin) surname may be that author's transliteration, so
        #   nothing that was comparable disproved it.
        if any(not name_tokens(a) for a in authors):
            return dict(base, ok=None, status="unchecked",
                        reason="a record author name has no Latin-script letters and the cited surname matched no "
                               "listed name")
        # Cycle 5 (M2): an all-caps 2-8 letter cited name is most likely an
        #   acronym, and the rule cannot read every acronym ("CDC", "UNICEF",
        #   "WWC"; two-letter ones never pass, L2), so a miss is not evidence
        #   of a different work: "not checked", never a fail. Cost: an all-caps
        #   person surname ("LI") that matches nobody is also only capped.
        if is_bare_acronym(cited, min_letters=2):
            return dict(base, ok=None, status="unchecked",
                        reason="the cited author is an all-caps name, read as an acronym, that matches no listed "
                               "name or organization's initials (an acronym the rule cannot read is not evidence "
                               "of a different work)")
        # Cycle 7 (L1): an abbreviated or organization-shaped cited name that
        #   matched no one is a name the rule cannot read, not evidence of a
        #   different work ("Am. Psychiatric Assn."): ambiguous, never a fail.
        shape = cited_org_shape(cited)
        if shape:
            return dict(base, ok=None, status="ambiguous", name_part=ORG_NOT_EXACT,
                        reason=f"{ORG_NOT_EXACT} (adjudicate): the cited name '{cited_first_name(cited).strip()}' "
                               f"has {shape}, so it may be an organization's name the rule layer cannot read (it "
                               "does not expand abbreviations); it matched no listed author word for word")
        # Cycle 8 (N-1): a final abbreviated word that begins a listed word
        #   ("RAND Corp." on "RAND Corporation") is ambiguous, never a fail.
        last = cited_final_abbreviation(cited, authors)
        if last:
            return dict(base, ok=None, status="ambiguous", name_part=ORG_NOT_EXACT,
                        reason=f"{ORG_NOT_EXACT} (adjudicate): the cited name '{cited_first_name(cited).strip()}' "
                               f"ends in the abbreviated word '{last}', which begins a listed author's word, so it "
                               "may be an abbreviated organization name the rule layer cannot expand")
        # Cycle 8b: a surname that matches only under an alternative
        #   transliteration ("Djordjevic" on "Ana Đorđević") is ambiguous.
        alt_hit = translit_alternative_hit(cited, authors)
        if alt_hit:
            pos, matched = alt_hit
            res = dict(base, found=True, position=pos, matched_author=matched, name_part=TRANSLIT_ALTERNATIVE,
                       fold="translit-alt")
            if first_only and pos != 0:
                return dict(res, ok=False, status="fail", reason=f"found as author {pos + 1}, not the first author")
            return dict(res, ok=None, status="ambiguous",
                        reason=f"'{base['surname']}' matches '{matched}' only under another transliteration of a "
                               "letter such as ø, æ or đ (o / oe, ae / a, d / dj): a spelling convention the rule "
                               "cannot settle, or another person")
        return dict(base, ok=False, status="fail", reason="the cited surname is not part of any listed author's name")
    # With --first-author: the first author when it matches at all. Otherwise
    # the first author whose SURNAME matches, else the first partial match.
    # Cycle 6: a person listed by that surname is preferred to an organization
    #   whose name merely contains it.
    # Cycle 7 (H1): among those, an author whose given names agree with the
    #   cited ones (person_step_aside finds nothing) is preferred ("Jane
    #   Smith" on ["John Smith", "Jane Smith"] passes on author 2).
    first = [h for h in hits if h[0] == 0] if first_only else []
    pool = (first or [h for h in hits if h[2] and not is_org_name(h[1])] or [h for h in hits if h[2]] or hits)
    pos, matched, ends = next((h for h in pool if h[2] and not is_org_name(h[1])
                               and person_step_aside(cited, h[1], want, reading, hit_fold) is None), pool[0])
    res = dict(base, found=True, position=pos, matched_author=matched, name_part="surname" if ends else "other")
    if first_only and pos != 0:
        return dict(res, ok=False, status="fail", reason=f"found as author {pos + 1}, not the first author")
    if is_org_name(matched) and not org_exact(cited_first_name(cited), matched):
        # Cycle 6 (step-aside decision; N2, N4): the cited name was read as a person but is
        #   only PART of a listed organization's name ("Bank" in "World Bank",
        #   "Association (APA)" on "American Psychiatric Association"): an
        #   organization passes on its exact whole name only (cycle 7:
        #   org_exact, so "Bank" on "US Bank" is not exact either).
        return org_not_exact(base, pos, matched, f"'{cited_first_name(cited).strip()}' is only part of the "
                                                 f"organization name '{matched}'")
    if not ends:
        return dict(res, ok=None, status="ambiguous",
                    reason=f"'{res['surname']}' matches a given or middle part of '{matched}', not its surname")
    # Cycle 7 (H1, step-aside decision): the surname alone does not make a pass when the
    #   given names disagree or either name reads like an organization's.
    step = person_step_aside(cited, matched, want, reading, hit_fold)
    if step:
        return dict(res, ok=None, status="ambiguous", name_part=step[0], reason=step[1])
    return dict(res, ok=True, status="pass", reason=None)


def year_within(cited_year, record_year):
    # 1 when both years are known and within VERIFY_YEAR_TOLERANCE, else 0
    # (a sort key for title-candidate tie-breaking as well as a test).
    try:
        return int(abs(int(cited_year) - int(record_year)) <= VERIFY_YEAR_TOLERANCE)
    except (TypeError, ValueError):
        return 0


def year_check(cited_year, record_year):
    # R4: ok=None when the record has no year (nothing to compare; no downgrade).
    if cited_year is None:
        return None
    try:
        rec_year = int(record_year)
    except (TypeError, ValueError):
        return {"cited": int(cited_year), "record": None, "diff": None,
                "tolerance": VERIFY_YEAR_TOLERANCE, "ok": None}
    return {"cited": int(cited_year), "record": rec_year, "diff": abs(int(cited_year) - rec_year),
            "tolerance": VERIFY_YEAR_TOLERANCE, "ok": bool(year_within(cited_year, rec_year))}


def parse_year_range(years):
    # "2010-2025" -> (2010, 2025); "2015-" -> (2015, None); "-2000" -> (None, 2000)
    if not years:
        return None, None
    if "-" not in years:
        return int(years), int(years)
    a, _, b = years.partition("-")
    return (int(a) if a else None), (int(b) if b else None)
