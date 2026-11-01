# =============================================================================
# scholar_backends/semantic_scholar.py - Semantic Scholar (Ai2) adapter
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). Never writes files; never handles provenance.
#
# Measured behavior (2026-09-27, the user's original tool):
#   - Key terms: 1 request per second per key across all endpoints (S2
#     tutorial, re-fetched 2026-10-28: "automatically gives a user a 1 request
#     per second rate across all endpoints"; the Ai2 key email's "cumulative"
#     wording is per the user's 2026-09-27 notes). The core's shared RateGate
#     spaces requests 1.2 s apart container-wide.
#   - Server-side throttling is heavy: ~30% of first attempts refused with a
#     key; later 5 of 6 searches spaced 5 s apart refused. Hence few attempts
#     inside `find` (S2 is an optional extra there) and more for dedicated
#     commands.
#   - /paper/search requesting `abstract` at limit >= 10 was refused (429) on
#     every attempt; without abstracts it succeeded. `find` fills abstracts
#     from OpenAlex.
#   - /paper/search is plain relevance text: quotes/parentheses/boolean
#     operators are not syntax and zeroed a test query (plain_terms strips
#     them). /paper/search/bulk documents boolean syntax but returns results
#     "without search relevance" (re-measured 2026-10-02, api-notes.md).
#   - DOI coverage gaps for economics/education journal versions
#     (10.1093/qje/qjv036 -> 404); resolve() falls back to a title match.
#   - Citation contexts (2026-10-31 probe, tool 1.7.0 `--s2-context`): a
#     `/references` call returned contexts on 2 of 10 rows; every `/citations`
#     attempt answered 429; see § CITATION_CONTEXTS.
#   - Citation contexts coverage (2026-11-01 coverage probe, tool 1.8.0;
#     scholarly-search api-notes.md, "Coverage versus OpenAlex"):
#     `/citations` lists the newest citing papers first; it sent no intents on
#     any of 300 rows (intents were seen only on `/references`); publishers
#     can elide `/references` (HTTP 200, "data": null, a notice), which
#     elision_notice() detects when the notice names the list asked for.
# =============================================================================

import re

from ._common import BackendError, key_value, norm_doi, record

# §§ CONTRACT
NAME = "semantic_scholar"
LABEL = "Semantic Scholar"
KEY_ENV = "SEMANTIC_SCHOLAR_API_KEY"
REQUIRED_KEY = False          # keyless = a pool shared by all unauthenticated users, which S2 may throttle further under heavy use
LICENSE_CLASS = "cc-by-nc"    # S2 Data Licenses: CC BY-NC or ODC-BY; attribution REQUIRED
RATE_LIMIT = {"semantic_scholar": 1.2}
RATE_LIMIT_NOTE = "1 req/s per key, all endpoints (gated 1.2 s container-wide)"
CAPABILITIES = frozenset({"search", "lookup"})
DEFAULT_IN_FIND = True
FIND_LEGS = ("semantic_scholar",)
ID_KEY = "s2"                 # key in a record's `ids` map (to_record below)
COST_NOTE = "free"
ATTRIBUTION = ("Credit 'Semantic Scholar' in published materials; cite Kinney et al. (2023), "
               "The Semantic Scholar Open Data Platform, arXiv:2301.10140")
GET_KEY_URL = "https://www.semanticscholar.org/product/api#api-key-form"

GRAPH = "https://api.semanticscholar.org/graph/v1"
FIELDS = ("paperId,title,year,venue,externalIds,citationCount,abstract,authors,"
          "openAccessPdf,publicationTypes")
SEARCH_FIELDS = FIELDS.replace("abstract,", "")
SEARCH_MAX = 20
QUERY_MAX_LEN = 1000
FIND_ATTEMPTS = 3
DEDICATED_ATTEMPTS = 8
FIND_MAX_WAIT = 20.0          # inside `find`, skip rather than queue long


# §§ AUTH_AND_COST
def key_present():
    return bool(key_value(KEY_ENV))


def auth_headers():
    key = key_value(KEY_ENV)
    return {"x-api-key": key} if key else {}


def degraded_note():
    if key_present():
        return None
    return ("Semantic Scholar: SEMANTIC_SCHOLAR_API_KEY is not set; using the pool shared by all "
            "unauthenticated users, which S2 may throttle further under heavy use (expect BACKEND FAILED / "
            "exit 12).")


def parse_cost(headers):
    return None   # S2 reports no spend


# §§ MAPPER
def to_record(p):
    ext = p.get("externalIds") or {}
    pdf = p.get("openAccessPdf") or {}
    return record(
        title=p.get("title") or "",
        year=p.get("year"),
        authors=[a.get("name") if isinstance(a, dict) else str(a) for a in (p.get("authors") or [])
                 if (a.get("name") if isinstance(a, dict) else a)],
        venue=p.get("venue") or "",
        doi=norm_doi(ext.get("DOI")),
        cites=p.get("citationCount"),
        abstract=p.get("abstract") or "",
        type=",".join(p.get("publicationTypes") or []),
        oa_url=pdf.get("url") or None,
        oa={"is_oa": bool(pdf.get("url")) or None, "license": pdf.get("license"),
            "version": None, "host": None},
        url=f"https://www.semanticscholar.org/paper/{p['paperId']}" if p.get("paperId") else None,
        ids={"s2": p.get("paperId")},
        backend=NAME,
        license_class=LICENSE_CLASS,
    )


# §§ REQUESTS
def plain_terms(query):
    q = re.sub(r"\b(AND|OR|NOT)\b|[\"()]", " ", query)
    return re.sub(r"\s+", " ", q).strip()


def search(http, query, limit, years=None, max_attempts=None, max_wait=None):
    params = {"query": plain_terms(query)[:QUERY_MAX_LEN], "limit": min(limit, SEARCH_MAX),
              "fields": SEARCH_FIELDS}
    if years:
        params["year"] = years
    kw = {"max_attempts": max_attempts or DEDICATED_ATTEMPTS}
    if max_wait is not None:
        kw["max_wait"] = max_wait
    parsed = http.get(NAME, f"{GRAPH}/paper/search", params, auth_headers(), **kw)
    return [to_record(p) for p in (parsed.get("data") or []) if isinstance(p, dict)], parsed.get("total")


def find_legs(http, a, keywords, ctx):
    # S2 gets the QUESTION's core terms (ctx["derive_keywords"]), not
    # --keywords: with boolean structure stripped, method words in --keywords
    # ("randomized") took over its ranking in the 2026-09-27 cold test.
    terms = ctx["derive_keywords"](a.query)
    return [("semantic_scholar", lambda: search(http, terms, a.per_source, a.years,
                                                FIND_ATTEMPTS, FIND_MAX_WAIT))]


def snippets(http, query, limit, years=None):
    params = {"query": query[:QUERY_MAX_LEN], "limit": min(limit, 1000)}
    if years:
        params["year"] = years
    parsed = http.get(NAME, f"{GRAPH}/snippet/search", params, auth_headers(),
                      max_attempts=DEDICATED_ATTEMPTS)
    return [d for d in (parsed.get("data") or []) if isinstance(d, dict)]


def bulk_search(http, query, limit, years=None):
    # /paper/search/bulk: documented boolean syntax (+ - | "phrase"), up to
    # 1,000 per call, NOT relevance-ranked. Backs the `s2-bulk` subcommand
    # (exhaustive pulls); not part of `find`.
    params = {"query": query[:QUERY_MAX_LEN], "fields": "paperId,title,year,externalIds,citationCount"}
    if years:
        params["year"] = years
    parsed = http.get(NAME, f"{GRAPH}/paper/search/bulk", params, auth_headers(),
                      max_attempts=DEDICATED_ATTEMPTS)
    data = [p for p in (parsed.get("data") or []) if isinstance(p, dict)][:limit]
    return [to_record(p) for p in data], parsed.get("total")


# §§ CITATION_CONTEXTS (scholar_search 1.7.0: `cites|refs --s2-context`)
# INTENT: one request for the citation sentences ("contexts"), citation
#   intents and the influential flag S2 holds for a seed paper's citations
#   (`cites`: GET /paper/DOI:{doi}/citations, each row's citingPaper) or
#   references (`refs`: /references, each row's citedPaper). The core matches
#   the rows to its OpenAlex list; this adapter only builds the request and
#   maps the rows.
# REASONING (live probe 2026-10-31, api-notes.md; OpenAPI spec fetched
#   2026-10-31): both endpoints document fields contexts, intents,
#   isInfluential; `limit` "Must be <= 1000" per call; the envelope is
#   {offset, next, data} with no total. Intent values seen live are lower
#   case: background, methodology, result. The FAQ: "citation intent data is
#   limited to papers for which we have access to the full text", and the
#   influential flag "relies on our access to the full-text of the citing
#   paper". An empty context list therefore means "unknown", never "no
#   substantive use". None of the three intents means disagreement.
# REASONING: `/citations` answered 429 three times in a row in the probe (a
#   key shared across the container), so this call makes CONTEXT_ATTEMPTS = 2
#   attempts (one retry with backoff) and waits at most CONTEXT_MAX_WAIT for
#   the shared 1.2 s lane; the core then keeps the OpenAlex result and
#   records the status instead of failing the command.
CONTEXT_FIELDS = "contexts,intents,isInfluential,externalIds,title,year,authors"
CONTEXT_PAGE_MAX = 1000
CONTEXT_ATTEMPTS = 2
CONTEXT_MAX_WAIT = 60.0
CONTEXT_DIRECTIONS = {"citing": ("citations", "citingPaper"), "cited": ("references", "citedPaper")}


ELISION_MARK = "elided by the publisher"
ELISION_FIELDS_RE = re.compile(r"elided by the publisher:\s*\{([^}]*)\}")


def citation_contexts(http, doi, direction, limit):
    # Returns (rows, more, elided): rows as context_row() maps them, in S2's
    # order; more = True when the envelope names a `next` offset (rows were
    # left); elided = S2's elision notice (a string) when it sent no rows
    # because the publisher withheld the list asked for, else None (1.8.0).
    endpoint, paper_key = CONTEXT_DIRECTIONS[direction]
    params = {"fields": CONTEXT_FIELDS, "limit": max(1, min(int(limit), CONTEXT_PAGE_MAX)), "offset": 0}
    parsed = http.get(NAME, f"{GRAPH}/paper/DOI:{doi}/{endpoint}", params, auth_headers(),
                      max_attempts=CONTEXT_ATTEMPTS, max_wait=CONTEXT_MAX_WAIT)
    rows = [context_row(item, item.get(paper_key)) for item in (parsed.get("data") or []) if isinstance(item, dict)]
    elided = None if rows else elision_notice({k: v for k, v in parsed.items() if k != "data"}, endpoint)
    return rows, parsed.get("next") is not None, elided


def elision_notice(value, field):
    # INTENT (1.8.0): find S2's publisher-elision notice for `field` (the
    #   list the call asked for: "references" or "citations") in a response
    #   that sent no rows, so "the publisher withheld the list" is never
    #   recorded as an ordinary empty answer.
    # REASONING (live, 2026-11-01 coverage probe, api-notes.md): for two
    #   papers `/references` answered HTTP 200 with "data": null and, under
    #   citingPaperInfo.openAccessPdf.disclaimer, "Notice: The following
    #   paper fields have been elided by the publisher: {'references'}. …".
    #   Where the notice sits is not documented, so every string outside
    #   `data` is searched; the first one carrying the mark is returned.
    # REASONING (1.8.0, review fix of 2026-11-01): a notice naming another
    #   field (e.g. {'abstract'}) says nothing about the list asked for, so it
    #   counts only when `field` is among the fields it names in braces (or,
    #   with no braces, appears in it as a word).
    if isinstance(value, str):
        low = value.lower()
        if ELISION_MARK not in low:
            return None
        listed = ELISION_FIELDS_RE.search(low)
        return value if field in re.findall(r"[a-z_]+", listed.group(1) if listed else low) else None
    items = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
    for v in items:
        found = elision_notice(v, field)
        if found:
            return found
    return None


def context_row(item, paper):
    # One citation: the other paper's identity (for matching) plus what S2
    # says about the citation. Empty strings and non-string values are
    # dropped; intents are lower-cased and de-duplicated in order.
    paper = paper if isinstance(paper, dict) else {}
    ext = paper.get("externalIds") or {}
    influential = item.get("isInfluential")
    return {"paper_id": paper.get("paperId"), "title": paper.get("title") or "", "year": paper.get("year"),
            "authors": [a.get("name") for a in (paper.get("authors") or [])
                        if isinstance(a, dict) and isinstance(a.get("name"), str) and a.get("name")],
            "doi": norm_doi(ext.get("DOI")) if isinstance(ext, dict) else None,
            "contexts": [c for c in (item.get("contexts") or []) if isinstance(c, str) and c.strip()],
            "intents": list(dict.fromkeys(i.strip().lower() for i in (item.get("intents") or [])
                                          if isinstance(i, str) and i.strip())),
            "is_influential": influential if isinstance(influential, bool) else None}


def resolve(http, ident, openalex_get_work):
    # Returns (S2 paper id, note). Kept for adapters/commands that need an
    # S2 id; falls back to an OpenAlex title when S2 lacks the DOI.
    ident = ident.strip()
    if ident.lower().startswith("title:"):
        title = ident[6:].strip().strip('"')
        parsed = http.get(NAME, f"{GRAPH}/paper/search/match",
                          {"query": title, "fields": "paperId,title,year"}, auth_headers())
        data = parsed.get("data") or []
        if not data:
            raise BackendError(NAME, "not-found", f"semantic_scholar: no match for {title!r}")
        return data[0]["paperId"], "S2 title match"
    doi = norm_doi(ident)
    try:
        parsed = http.get(NAME, f"{GRAPH}/paper/DOI:{doi}", {"fields": "paperId,title"}, auth_headers())
        return parsed["paperId"], "S2 DOI lookup"
    except BackendError as exc:
        if exc.kind != "not-found":
            raise
    w, _, _ = openalex_get_work(http, doi)
    pid, note = resolve(http, f'title:{w.get("display_name")}', openalex_get_work)
    return pid, f"{note} (DOI unknown to S2; matched by title)"
