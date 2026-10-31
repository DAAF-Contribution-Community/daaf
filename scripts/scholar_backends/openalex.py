# =============================================================================
# scholar_backends/openalex.py - OpenAlex adapter (the backbone backend)
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). Builds requests, maps native JSON to the common record schema,
# and parses cost headers. Never writes files; never handles provenance.
#
# Measured behavior this adapter is built around (2026-09-27, the user's
# original tool; re-measured items are dated 2026-10-02 in
# .claude/skills/scholarly-search/references/api-notes.md):
#   - `search=` also matches full text and drifts toward highly cited
#     off-topic papers, so keyword mode uses
#     filter=title_and_abstract.search + sort=relevance_score:desc.
#   - Semantic search: max 50 results, 1 request/second; year filters are
#     accepted (filter support re-measured 2026-10-02, see api-notes.md).
#   - Filter values are comma-separated, but a comma inside .search filter
#     text is text unless a filter name and ":" follow it directly
#     (re-measured 2026-10-31). filter_value() also neutralizes the spaced
#     forms (", type:", ",type :"), which were not measured. `?`/`*` are
#     wildcards the stemmed .search filters reject (a title ending in "?"
#     returned HTTP 400 on 2026-09-27; harmless on 2026-10-31).
#   - Open year ranges need comparisons (publication_year:>2014).
#   - Datasets ("Code for: …" ICPSR deposits) and paratext crowd out papers;
#     excluded unless --all-types. `find` also drops dissertations by default
#     (2026-09-27 cold test: 9 of the top 20 were theses).
#   - Per-second limits (docs, authentication page, fetched 2026-10-28; the
#     same page said 100 req/s on 2026-10-02): 10 req/s keyless, 30 with a
#     free key or prepaid usage, 50 on an annual plan; searches with more than
#     5 OR/AND/NOT operators 1 / 5 / 25 req/s; semantic search 1 req/s. Since
#     tool 1.6.0 (user decision 2026-10-30) every request is gated
#     container-wide by key tier (§§ RATE_LANES); since 1.6.1 the tier is the
#     OPENALEX_RATE_TIER setting, by default read from key presence
#     (§§ RATE_TIERS). Live re-measure 2026-10-30
#     (free single-work lookups, keyed): see api-notes.md § "Measured
#     behavior: OpenAlex per-second gate (2026-10-30)".
# =============================================================================

import difflib
import os
import re

from ._common import (VERIFY_CONFIDENT_MIN, VERIFY_MIN_TITLE_LETTERS, BackendError, arxiv_id_from, author_match,
                      key_value, norm_doi, numerals_differ, record, short_oa_id, title_letter_count,
                      verify_title_norm, year_within)

# §§ CONTRACT
NAME = "openalex"
LABEL = "OpenAlex"
KEY_ENV = "OPENALEX_API_KEY"
REQUIRED_KEY = False          # keyless works at $0.10/day (docs conflict; see api-notes.md)
LICENSE_CLASS = "open"        # data is CC0 (help.openalex.org)
# Rate lanes -> minimum spacing in seconds for the core's shared RateGate
# (scholar_search.py §§ SHARED_RATE_GATE). EVERY OpenAlex request books the
# main lane ("openalex"), so the main lane alone bounds the key's (or IP's)
# per-second total; a semantic or boolean-heavy search also books its own
# lane (lanes_for() below), in the same step as the main lane (core
# reserve_lanes()), so each lane's spacing holds for the time the request is
# sent. Documented limits: see the header.
# REASONING (user decision 2026-10-30): several DAAF agents may search at
#   once, so the per-second limit is enforced container-wide by the gate
#   rather than left to 429 retries.
# REASONING (user decision 2026-10-31, tool 1.6.1): the API does not tell a
#   key's plan (2026-10-30: no response header states it), so the tier is a
#   setting, OPENALEX_RATE_TIER, set host-side in environment_settings.txt
#   like the key. Unset, it is "free" with a key and "keyless" without one.
#   RATE_TIERS below is the ONE table of tiers: a vendor change to the
#   documented limits is a one-row edit there.
# ASSUMES: every scholar_search process in the container sees the same key
#   presence and the same OPENALEX_RATE_TIER (one environment, fixed at
#   container start), so every process books the shared gate files with the
#   same spacing. The tier is read once, when this module loads.
MAIN_LANE = NAME
SEMANTIC_LANE = "openalex-semantic"
BOOLEAN_LANE = "openalex-boolean"
SEMANTIC_INTERVAL = 1.1       # docs: semantic search is 1 request per second, on every plan
BOOLEAN_OPERATOR_MAX = 5      # docs: "more than 5 `OR`/`AND`/`NOT` operators" -> the lower limit
RATE_TIER_ENV = "OPENALEX_RATE_TIER"
# §§ RATE_TIERS
# tier: (documented req/s, documented req/s for a search with more than 5
#        operators, gate interval s for every request, gate interval s for such a search)
# Documented limits: help.openalex.org/api/authentication, fetched 2026-10-28
# and again 2026-10-30. Each interval keeps a margin under its limit:
#   keyless 0.11 s = ~9.1/s (limit 10)  and 1.1 s = ~0.9/s (limit 1);
#   free    0.04 s = 25/s (limit 30)    and 0.22 s = ~4.5/s (limit 5);
#   annual  0.024 s = ~41.7/s (limit 50) and 0.044 s = ~22.7/s (limit 25).
RATE_TIERS = {"keyless": (10, 1, 0.11, 1.1),
              "free": (30, 5, 0.04, 0.22),          # docs: "Free API key, or prepaid usage"
              "annual": (50, 25, 0.024, 0.044)}     # docs: "Annual plan"
RATE_TIER_ALIASES = {"prepaid": "free"}             # prepaid usage shares the free-key limits


def resolve_rate_tier(keyed, requested):
    # Returns (tier, source, warning or None). `requested` is the raw
    # OPENALEX_RATE_TIER value (None or "" when unset; case and surrounding
    # spaces ignored).
    # REASONING: an unknown value falls back to the default for the key state,
    #   the conservative tier. A keyed tier without a key falls back to
    #   "keyless", because keyless requests get the keyless limit whatever the
    #   setting says. "keyless" with a key set is allowed (slowest spacing; the
    #   key is still sent).
    default = "free" if keyed else "keyless"
    raw = (requested or "").strip()
    if not raw:
        return default, f"{'key set' if keyed else 'no key'}, {RATE_TIER_ENV} not set", None
    tier = RATE_TIER_ALIASES.get(raw.lower(), raw.lower())
    if tier not in RATE_TIERS:
        # REASONING (Phase 4 review W2, 2026-10-31): the value is echoed only
        #   when it looks like a typo of a tier name: letters, "-" or "_", at
        #   most 12, AND difflib finds a tier name or alias close to it
        #   ("anual" -> "annual"). Anything else, such as a key pasted into the
        #   wrong variable ("sk-ABCDEFGHI", "oa_test_key"), shows as "(value
        #   not shown)". The core also passes this text through the secret
        #   redactor on stdout, stderr, the digest and the row.
        names = list(RATE_TIERS) + list(RATE_TIER_ALIASES)
        near = difflib.get_close_matches(raw.lower(), names, n=1, cutoff=0.6)
        shown = repr(raw) if (re.fullmatch(r"[A-Za-z_-]{1,12}", raw) and near) else "(value not shown)"
        known = ", ".join(names)
        return default, f"fallback: unknown {RATE_TIER_ENV}", (
            f"{RATE_TIER_ENV}={shown} is not a known tier ({known}); using the {default} tier")
    if not keyed and tier != "keyless":
        # The user's own spelling is shown (`prepaid`, not its alias target
        # `free`); it is a known tier name here, so it is safe to print.
        return "keyless", f"fallback: {RATE_TIER_ENV}={raw} but no key", (
            f"{RATE_TIER_ENV}={raw} needs {KEY_ENV}, which is not set; using the keyless tier")
    return tier, f"from {RATE_TIER_ENV}", None


def rate_limit(tier):
    # The RATE_LIMIT map for a tier name (a RATE_TIERS key).
    _, _, main, boolean = RATE_TIERS[tier]
    return {MAIN_LANE: main, SEMANTIC_LANE: SEMANTIC_INTERVAL, BOOLEAN_LANE: boolean}


def rate_tier_note(tier, source):
    lanes = rate_limit(tier)
    return (f"{tier} ({source}): every request {lanes[MAIN_LANE]} s, boolean-heavy {lanes[BOOLEAN_LANE]} s, "
            f"semantic {SEMANTIC_INTERVAL} s")


def rate_limit_note(tier, source):
    docs = ", ".join(f"{limits[0]} {name}" for name, limits in RATE_TIERS.items())
    heavy = "/".join(str(limits[1]) for limits in RATE_TIERS.values())
    return (f"docs req/s: {docs}; >5 OR/AND/NOT operators {heavy}; semantic 1. Gated for this container, "
            f"tier {rate_tier_note(tier, source)}; daily $ budget")


RATE_TIER, RATE_TIER_SOURCE, CONFIG_WARNING = resolve_rate_tier(bool(key_value(KEY_ENV)),
                                                                os.environ.get(RATE_TIER_ENV))
RATE_LIMIT = rate_limit(RATE_TIER)
RATE_TIER_NOTE = rate_tier_note(RATE_TIER, RATE_TIER_SOURCE)     # shown by `backends`
RATE_LIMIT_NOTE = rate_limit_note(RATE_TIER, RATE_TIER_SOURCE)
CAPABILITIES = frozenset({"search", "lookup", "cites", "refs", "oa_locate", "fulltext", "retraction"})
DEFAULT_IN_FIND = True
FIND_LEGS = ("openalex_semantic", "openalex_keyword")   # leg names find_legs() returns
COST_NOTE = "search/semantic $0.001, list+filter $0.0001, single lookup free, content download $0.01"
ATTRIBUTION = ("Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of scholarly "
               "works, authors, venues, institutions, and concepts. arXiv:2205.01833")
GET_KEY_URL = "https://openalex.org/settings/api-key"   # authentication page, fetched 2026-10-28

API = "https://api.openalex.org"
CONTENT = "https://content.openalex.org"
SELECT = ("id,doi,display_name,publication_year,authorships,primary_location,"
          "cited_by_count,abstract_inverted_index,open_access,type,has_content,"
          "content_urls,ids,referenced_works_count,is_retracted")
OA_SELECT = ("id,doi,display_name,publication_year,open_access,best_oa_location,"
             "primary_location,locations,ids,is_retracted,type")
TYPE_EXCLUDE = "type:!dataset,type:!paratext"
DISSERTATION_EXCLUDE = "type:!dissertation"
SEMANTIC_MAX = 50
PER_PAGE_MAX = 100


# §§ AUTH_AND_COST
def key_present():
    return bool(key_value(KEY_ENV))


def auth_headers():
    # Bearer header, never ?api_key= (the key must not reach a URL, a log,
    # or the raw artifact). Verified to work on api. and content. hosts
    # (2026-09-27).
    key = key_value(KEY_ENV)
    return {"Authorization": f"Bearer {key}"} if key else {}


def degraded_note():
    if key_present():
        return None
    return ("DEGRADED MODE: OPENALEX_API_KEY is not set. Keyless OpenAlex is budgeted at $0.10/day "
            "(about 100 searches or 10 cached full texts), and OpenAlex's own docs conflict on whether "
            "keyless access continues (help.openalex.org/api/deprecations says all users need a key). "
            f"A free key gives $1/day: {GET_KEY_URL} (add it host-side in environment_settings.txt).")


def parse_cost(headers):
    # INTENT: record spend and remaining budget per call. OpenAlex documents
    #   X-RateLimit-{Limit,Remaining,Credits-Used,Reset}; the 2026-09-27
    #   measurement saw x-ratelimit-{cost,remaining,limit}-usd. Both families
    #   are read (header lookup is case-insensitive) so a rename on either
    #   side is visible in the manifest instead of silently dropping spend.
    out = {}
    for field, names in (("cost_usd", ("x-ratelimit-cost-usd",)),
                         ("remaining_usd", ("x-ratelimit-remaining-usd",)),
                         ("limit_usd", ("x-ratelimit-limit-usd",)),
                         ("credits_used", ("x-ratelimit-credits-used",)),
                         ("remaining", ("x-ratelimit-remaining",)),
                         ("limit", ("x-ratelimit-limit",)),
                         ("reset_s", ("x-ratelimit-reset",))):
        for n in names:
            v = headers.get(n)
            if v is None:
                continue
            try:
                out[field] = float(v)
            except ValueError:
                out[field] = v
    return out or None


# §§ MAPPER
def reconstruct_abstract(inverted):
    # OpenAlex ships abstracts as {word: [positions]} "for legal reasons".
    if not isinstance(inverted, dict) or not inverted:
        return ""
    slots = {}
    for word, positions in inverted.items():
        for p in positions or []:
            if isinstance(p, int):
                slots[p] = word
    return " ".join(slots[i] for i in sorted(slots))


def to_record(w):
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = w.get("open_access") or {}
    best = w.get("best_oa_location") or {}
    has = w.get("has_content") or {}
    authors = [((a.get("author") or {}).get("display_name") or "") for a in (w.get("authorships") or [])]
    wid = short_oa_id(w.get("id"))
    return record(
        title=w.get("display_name") or w.get("title") or "",
        year=w.get("publication_year"),
        authors=[a for a in authors if a],
        venue=src.get("display_name") or "",
        doi=norm_doi(w.get("doi")),
        cites=w.get("cited_by_count"),
        abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
        type=w.get("type") or "",
        oa_url=oa.get("oa_url"),
        oa={"is_oa": oa.get("is_oa"), "license": best.get("license") or loc.get("license"),
            "version": best.get("version"), "host": ((best.get("source") or {}).get("display_name"))},
        fulltext=bool(has.get("grobid_xml")),
        url=loc.get("landing_page_url"),
        ids={"openalex": wid},
        fulltext_id=wid if has.get("grobid_xml") else None,
        refs=w.get("referenced_works_count"),
        retracted=w.get("is_retracted"),
        backend=NAME,
        license_class=LICENSE_CLASS,
    )


# §§ RATE_LANES
# INTENT: pick the rate lanes a request books (RATE_LIMIT above). The docs'
#   only words on these limits are "A few heavy request types have lower
#   limits of their own: semantic search is 1 request per second, and
#   searches with more than 5 OR/AND/NOT operators are limited to 1 (no key),
#   5 (free key or prepaid usage) or 25 (annual plan) per second"
#   (help.openalex.org/api/authentication, fetched 2026-10-28 and again
#   2026-10-30). "Of their own" is read as a stricter limit that ADDS to the
#   main per-second limit, so such a search books its sub-lane AND the main
#   lane (the docs give no accounting rule beyond that phrase). They do not
#   say how operators are counted.
# Counting rule (DAAF's):
#   - an operator is the whole word AND, OR or NOT in UPPER CASE; lower-case
#     "and"/"or"/"not" are plain words. Docs: "Use AND, OR, NOT (uppercase)
#     for complex queries" (help.openalex.org/api/searching, fetched
#     2026-10-30);
#   - INFERENCE (the docs do not address it): words inside double-quoted
#     phrases ARE counted. The searching page treats a quoted phrase as text
#     matched as typed, so a quoted "AND" may well be exempt; counting it is
#     the conservative choice (over-counting only slows one request,
#     under-counting risks a 429);
#   - INFERENCE (the docs do not address it): the text counted is every
#     `search` / `search.*` parameter and every `filter` clause whose field
#     name contains ".search" (title_and_abstract.search, title.search,
#     fulltext.search, …), summed over the request. When any filter clause
#     is a .search clause, the WHOLE filter value is counted, because "A
#     comma in a search filter’s text is part of the text" (searching page,
#     2026-10-30), so splitting on commas could hide operators that follow a
#     comma. `|` alternation inside a filter value is not counted.
BOOLEAN_OPERATOR_RE = re.compile(r"\b(?:AND|OR|NOT)\b")


def search_texts(params):
    # The free-text parts of a request's params (see the counting rule above).
    out = []
    for key, value in (params or {}).items():
        if not isinstance(value, str):
            continue
        if key == "search" or key.startswith("search."):
            out.append(value)
        elif key == "filter":
            # Whole value when any clause is a .search clause (a comma there is
            # part of the text); non-search clauses add no operators in practice,
            # and any they do add are over-counted, the safe direction.
            if any(".search" in clause.partition(":")[0] for clause in value.split(",")):
                out.append(value)
    return out


def boolean_operator_count(params):
    return sum(len(BOOLEAN_OPERATOR_RE.findall(t)) for t in search_texts(params))


def lanes_for(params, sub_lane=None):
    # Returns the lanes a request books: its sub-lanes, if any, then the main
    # lane. The core books them all in one step (scholar_search.py
    # reserve_lanes()), so the order does not change the timing; the main lane
    # stays last so the tuple reads as "sub-lanes + main lane".
    lanes = [sub_lane] if sub_lane else []
    if boolean_operator_count(params) > BOOLEAN_OPERATOR_MAX:
        lanes.append(BOOLEAN_LANE)
    return tuple(lanes) + (MAIN_LANE,)


# §§ REQUEST_BUILDERS
def filter_value(text):
    # INTENT: free text made safe as a .search filter value.
    # REASONING (1.6.1, measured 2026-10-31): a comma stays part of the text.
    #   Docs (help.openalex.org/api/filtering, fetched 2026-10-31): "a comma in
    #   their text stays part of the text unless the next filter starts right
    #   after it (,type:)". Live (lit_search/2026-10-31_openalex_live, keyed):
    #   ", " mid-filter, "," with no space, ", word:" and the docs' own title
    #   all answered HTTP 200, each with the same meta.count as its comma-free
    #   pair where one was sent (475/475/475; 10/10). The 2026-09-27 premise
    #   ("commas break the filter") no longer holds, so commas are kept except
    #   where one could start a filter clause.
    # REASONING (Phase 4 review W1, 2026-10-31): a comma becomes a space when
    #   a field-name-shaped word and ":" follow it, with optional whitespace
    #   before the word and before the ":", in any case (", type:",
    #   ",TYPE:", ",type :"). Only the no-space form is documented as a
    #   clause; whether the server reads the spaced forms as clauses was not
    #   measured, so they are neutralized too, the conservative choice. The
    #   cost is a lost comma before "word:" in real text ("Gaps, race:
    #   evidence"), which the live counts show is harmless (475/475/475 with
    #   and without commas). Wildcards are removed FIRST, so a `?` or `*`
    #   cannot hide such a comma (",?type:", ",type?:"). Leading and trailing
    #   commas are dropped: a trailing one would meet the joining comma as
    #   ",,". Non-ASCII commas (U+FF0C, U+060C) pass through (inference: the
    #   server splits on the ASCII comma only).
    # REASONING: `?` and `*` are wildcards (inside a word; `?` also at the end
    #   of a one-word search), and the stemmed .search filters reject wildcards
    #   with HTTP 400 (searching docs, fetched 2026-10-30), so both become
    #   spaces. A "?" ending a multi-word title is now harmless (2026-10-31:
    #   HTTP 200, meta.count 4 with and without it; on 2026-09-27 it was a 400).
    text = re.sub(r"[?*]+", " ", text)
    text = re.sub(r",(?=\s*[A-Za-z_][A-Za-z0-9_.]*\s*:)", " ", text)
    return re.sub(r"^[\s,]+|[\s,]+$", "", text)


def year_filter(years):
    # OpenAlex takes closed ranges as-is but open ranges as > / < comparisons.
    if not years:
        return None
    if years.endswith("-"):
        return f"publication_year:>{int(years[:-1]) - 1}"
    if years.startswith("-"):
        return f"publication_year:<{int(years[1:]) + 1}"
    return f"publication_year:{years}"


def join_filters(*parts):
    return ",".join(p for p in parts if p)


def search(http, query, mode, limit, years=None, extra_filter=None, sort=None, all_types=False):
    params = {"select": SELECT}
    if not all_types:
        extra_filter = join_filters(extra_filter, TYPE_EXCLUDE)
    if mode == "semantic":
        params["search.semantic"] = query[:2000]
        params["per_page"] = min(limit, SEMANTIC_MAX)
        f = join_filters(year_filter(years), extra_filter)
        sub_lane = SEMANTIC_LANE
    elif mode == "keyword":
        f = join_filters(f"title_and_abstract.search:{filter_value(query)}",
                         year_filter(years), extra_filter)
        params["sort"] = sort or "relevance_score:desc"
        params["per_page"] = min(limit, PER_PAGE_MAX)
        sub_lane = None
    elif mode == "broad":
        params["search"] = query
        f = join_filters(year_filter(years), extra_filter)
        params["per_page"] = min(limit, PER_PAGE_MAX)
        sub_lane = None
    else:  # filter-only
        f = join_filters(year_filter(years), extra_filter)
        params["per_page"] = min(limit, PER_PAGE_MAX)
        sub_lane = None
    if f:
        params["filter"] = f
    if sort and mode != "keyword":
        params["sort"] = sort
    # 1.6.0: the lanes are chosen from the FINAL params, so a boolean-heavy
    # --filter on any mode is counted too.
    parsed = http.get(NAME, f"{API}/works", params, auth_headers(), lane=lanes_for(params, sub_lane))
    results = parsed.get("results") or []
    total = (parsed.get("meta") or {}).get("count")
    return [to_record(w) for w in results if isinstance(w, dict)], total


def find_legs(http, a, keywords, ctx):
    # The fused-search legs this backend contributes to `find`: the QUESTION
    # goes to semantic search (meaning), the KEYWORDS to title/abstract search.
    # `ctx` carries core helpers (e.g. derive_keywords); unused here.
    xf = None if a.include_dissertations else DISSERTATION_EXCLUDE
    return [("openalex_semantic", lambda: search(http, a.query, "semantic", a.per_source, a.years, xf)),
            ("openalex_keyword", lambda: search(http, keywords, "keyword", a.per_source, a.years, xf))]


def title_candidates(http, title, per_page=10, extra_select=""):
    params = {"filter": f"title.search:{filter_value(title)}", "per_page": per_page,
              "select": SELECT + extra_select}
    parsed = http.get(NAME, f"{API}/works", params, auth_headers(), lane=lanes_for(params))
    return parsed.get("results") or []


def title_score(want_title, got_title):
    # INTENT: THE full-title score of the citation gate (and of version-sibling
    #   matching): difflib SequenceMatcher on verify_title_norm, untruncated.
    #   0.0 when either side normalizes to "" (two empty titles must not score
    #   1.00). autojunk=False: difflib's default treats characters frequent in
    #   a string of 200+ characters as junk, which made a long title's score
    #   depend on its length (measured on the B2 probe pair: 0.802 with it,
    #   0.851 without), so the score would no longer mean the same thing once
    #   titles are compared untruncated.
    a, b = verify_title_norm(want_title), verify_title_norm(got_title)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def authors_of(w):
    # The author display names of an OpenAlex work JSON (as to_record lists them).
    return [n for n in (((a.get("author") or {}).get("display_name") or "") for a in (w.get("authorships") or [])) if n]


def best_title_match(want_title, candidates, title_key, year=None, year_key=None, author=None, authors_key=None,
                     first_author=False):
    # Returns (ratio, candidate) or (0.0, None). The ratio is title_score, the
    # FULL-title score (never the subtitle-aware one). Ties on it — identical
    # normalized titles, e.g. a Cochrane review and its update — go first
    # (cycle 3, I-C) to a candidate on which the cited `author` passes the
    # verify author check (verify --author / --first-author), then to one whose
    # year is within VERIFY_YEAR_TOLERANCE of `year` (verify --year, R4), then
    # to the most-cited.
    # REASONING (cycle 4): author ranks BEFORE year because the two failures
    #   cost differently: picking a candidate whose author fails grades
    #   MISMATCH (a hard block), while one whose year is off only grades WEAK.
    #   With year first, a genuine "Lee" cited with a slightly wrong year lost
    #   the tie to a same-titled "Hanushek" record of that year and was
    #   blocked; author first keeps Lee's record and lets the year gap show.
    scored = sorted(((title_score(want_title, title_key(c)),
                      int(author_match(author, authors_key(c), first_only=first_author)["status"] == "pass")
                      if (author and authors_key) else 0,
                      year_within(year, year_key(c)) if (year is not None and year_key) else 0,
                      c.get("cited_by_count") or c.get("is-referenced-by-count") or 0, i, c)
                     for i, c in enumerate(candidates)),
                    key=lambda t: (t[0], t[1], t[2], t[3], -t[4]), reverse=True)
    if not scored:
        return 0.0, None
    return scored[0][0], scored[0][5]


def get_work(http, ident, extra_select=",referenced_works", year=None, author=None, first_author=False):
    # Returns (openalex_work_json, match_note, ratio_or_None). `year` and
    # `author` only break similarity ties on a title: lookup (best_title_match).
    ident = ident.strip()
    if ident.lower().startswith("title:"):
        title = ident[6:].strip().strip('"')
        cands = title_candidates(http, title, extra_select=extra_select)
        if not cands:
            raise BackendError(NAME, "not-found", f"openalex: no work matches title {title!r}")
        ratio, best = best_title_match(title, cands, lambda c: c.get("display_name"), year=year,
                                       year_key=lambda c: c.get("publication_year"), author=author,
                                       authors_key=authors_of, first_author=first_author)
        # The lookup note uses the verify gate's calibrated cutoff and its title
        # guards (B1 letters, D2 numerals), so a "close title match" here never
        # contradicts a `verify` title check on the same title. Its label never
        # uses the verdict words (cycle 3, W-B): `verify` embeds this note, and
        # "CONFIDENT" must appear only on a CONFIDENT verdict.
        got = best.get("display_name") or ""
        close = (ratio >= VERIFY_CONFIDENT_MIN and numerals_differ(title, got) is None
                 and min(title_letter_count(title), title_letter_count(got)) >= VERIFY_MIN_TITLE_LETTERS)
        label = "close title match" if close else "not a close title match — check it manually"
        return best, f"title lookup: similarity {ratio:.2f} ({label}); {len(cands)} candidate(s)", ratio
    wid = short_oa_id(ident) if re.match(r"^(https?://openalex\.org/)?W\d+$", ident, re.I) else None
    if wid:
        path = wid
    else:
        doi = norm_doi(ident)
        if not doi or not doi.startswith("10."):
            raise BackendError(NAME, "api", f"unrecognized identifier {ident!r} "
                                            "(use W…, a DOI, or title:\"…\")")
        path = f"doi:{doi}"
    parsed = http.get(NAME, f"{API}/works/{path}", {"select": SELECT + extra_select}, auth_headers())
    return parsed, "exact identifier", None


def resolve_id(http, ident):
    if re.match(r"^(https?://openalex\.org/)?W\d+$", ident.strip(), re.I):
        return short_oa_id(ident), None
    w, note, _ = get_work(http, ident)
    return short_oa_id(w.get("id")), note


def fulltext_bytes(http, wid):
    return http.get(NAME, f"{CONTENT}/works/{wid}.grobid-xml", None, auth_headers(), want="bytes")


# §§ OA_LOCATE
def oa_locate(http, doi):
    # INTENT: OpenAlex's best_oa_location IS Unpaywall's data since late 2025
    #   (help.openalex.org/access/unpaywall), and a single-work lookup is
    #   free. Returns a list of candidate dicts (best first) plus the record.
    w = http.get(NAME, f"{API}/works/doi:{doi}", {"select": OA_SELECT}, auth_headers())
    rec = to_record(w)
    cands = []
    locs = [w.get("best_oa_location") or {}] + [l for l in (w.get("locations") or []) if l]
    seen = set()
    for loc in locs:
        if not loc:
            continue
        url = loc.get("pdf_url") or loc.get("landing_page_url")
        if not url or url in seen or not loc.get("is_oa", True):
            continue
        seen.add(url)
        cands.append({"leg": NAME, "url": url, "is_pdf": bool(loc.get("pdf_url")),
                      "license": loc.get("license"), "version": loc.get("version"),
                      "host": (loc.get("source") or {}).get("display_name"),
                      "best": loc is locs[0]})
    rec["arxiv_id"] = arxiv_id_from(w.get("doi"), *[(l or {}).get("landing_page_url")
                                                  for l in (w.get("locations") or [])])
    return cands, rec, (w.get("open_access") or {}).get("oa_status")


# §§ RETRACTION
def retraction_check(http, doi):
    # OpenAlex's is_retracted flag (free single-work lookup). A True here is
    # a hard flag; False only means OpenAlex has no retraction on record.
    w = http.get(NAME, f"{API}/works/doi:{doi}", {"select": "id,doi,display_name,is_retracted"},
                 auth_headers())
    flag = w.get("is_retracted")
    return {"source": NAME, "status": "retracted" if flag else ("none" if flag is False else "unknown"),
            "notices": [], "title": w.get("display_name")}
