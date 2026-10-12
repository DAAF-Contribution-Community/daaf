# =============================================================================
# scholar_backends/elicit.py - Elicit API v2 adapter (paper search, usage,
#                              async research reports; restricted)
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). Builds requests through the core's Http object and maps native
# JSON. Never writes files; never handles provenance: the core persists the
# report sessionId (checkpoint row) BEFORE the first poll and owns the poll
# loop, the wall-clock cap and every artifact (scholar_search.py §§ ELICIT).
#
# Documented behavior (docs.elicit.com v2 reference + openapi.json, fetched
# 2026-10-11 into the S1 workspace web_fetches/s2_research/; API terms
# "Last updated: July 15, 2026"):
#   - Base https://elicit.com/api/v2; "Authorization: Bearer elk_live_…";
#     "API access requires a Pro plan or above." Keys: elicit.com/developer
#     (changelog: "generate a key at elicit.com/developer").
#   - "All endpoints share a burst limit of 100 requests per minute per IP
#     address, including polling requests. Exceeding it returns 429 and
#     blocks that IP for 5 minutes." The edge 429 body is FLAT
#     {"error":"Rate limit exceeded","message":…}, not the {"error":{code,
#     message}} envelope. -> RETRY_POLICY penalize 300 s, never retried (the
#     vendor sample skill's "wait 60 seconds before retrying" is wrong).
#   - 402 insufficient_quota "when starting work" (search can return 402
#     too); a running session can pause as "pausedForInsufficientQuota" and
#     "does not automatically resume" -> POST /sessions/{id}/resume (409
#     session_not_paused). GET /usage: hasUsageRemaining, percentUsed,
#     periodStart, periodEnd, extraUsage{limitUsdCents, spentUsdCents}|null;
#     409 not_credits_pricing / usage_unavailable is an answer, not a failure.
#   - POST /search/papers {query, maxResults (default 10), searchMode
#     semantic|keyword, corpus elicit|pubmed, filters{minYear, maxYear,
#     typeTags[Review, Meta-Analysis, Systematic Review, RCT, Longitudinal],
#     …}}: synchronous, no pagination; "Filters and searchMode: "keyword" are
#     mutually exclusive … Mixing them returns a 400." Response {papers[],
#     warnings[]} (warnings are response-level). Pro plan: 300 results max per
#     request (more -> 400). abstract may be null.
#   - POST /sessions/reports {researchQuestion (1-2000 chars),
#     maxSearchPapers 1-1000 (default 50), maxExtractPapers 1-80 (default
#     10), isPublic (default false)} -> 202 {type, sessionId, status
#     "processing", url, isPublic, links.self}. "Creation and message requests
#     are not guaranteed to be idempotent. A timeout does not prove that work
#     was not started." An error body may carry error.sessionId ("Recovery ID
#     … whose creation outcome is uncertain").
#   - GET /sessions/reports/{id}: status processing | pausedForInsufficientQuota
#     | completed | failed | unknown; "Poll every 30–60 seconds. Reports
#     typically complete in 5–15 minutes"; "Stop normal polling on completed,
#     failed, or unknown"; ?include=reportBody adds result.reportBody (markdown)
#     and result.abstract; pdfUrl/docxUrl/txtUrl/bibUrl/risUrl are presigned
#     and "expire after 7 days"; exportsStatus can be stale.
#   - Terms: §2 no Personal Data ("includes names"); §3.2(c) no systematic
#     corpus reconstruction; §3.5 store/reuse outputs but no standalone index;
#     §3.4 disclose AI generation; §4.2 non-deterministic; §12.3 delete cached
#     outputs within 30 days of termination -> LICENSE_CLASS "restricted".
# MEASURED (2026-10-11, live CLI runs into research/2026-10-02_FrameworkDev_
# ScholarlySearch/smoke_s2/elicit/ rows 1-6; api-notes.md § "Measured
# behavior: Elicit (2026-10-11)", references/elicit.md § Measured behavior):
#   - /usage 200; percentUsed is an integer and stayed 0 across a 1-result
#     search and a 10/5 report on 2026-10-11 (last read 18:55:41Z), then read
#     3 on 2026-10-12T15:44:52Z: usage accounting LAGS, and the two calls
#     together drew about 3% (assuming no other use of the account; the
#     per-call split is unknown).
#   - search 200 with every documented field (studyTypeTags, journalQuartile,
#     fullTextUrl, pmid null); warnings []; no usage or rate-limit headers.
#   - create 202 in 0.4 s {type, sessionId, status "processing", url,
#     isPublic false, links.self}; no executionStage in the 202.
#   - completed: the plain read carries result{title, summary}, 5 presigned
#     S3 export links (X-Amz-Expires=604800, minted per fetch) and
#     exportsStatus "ready"; ?include=reportBody adds reportBody + abstract.
#     No paper counts in the JSON. The body holds {<64-hex>_<n>} anchors.
#   - the host crashed mid-poll after the created checkpoint; elicit-resume
#     (no POST) recovered the completed report (core 1.3.1 crash recovery).
# =============================================================================

import re

from ._common import BackendError, key_value, norm_doi, parse_year_range, record

# §§ CONTRACT
NAME = "elicit"
LABEL = "Elicit"
KEY_ENV = "ELICIT_API_KEY"
REQUIRED_KEY = True           # every v2 endpoint needs the Bearer key (missing -> exit 10)
LICENSE_CLASS = "restricted"  # API Terms §12.3 (delete cached outputs within 30 days of termination); spec D-4
RATE_LIMIT = {"elicit": 0.75}  # 80/min, under the 100/min per-IP limit; polling shares the lane
RATE_LIMIT_NOTE = ("100 req/min per IP across ALL endpoints incl. polling; a 429 blocks the IP 5 min "
                   "(gated 0.75 s; a 429 pauses the lane 300 s, never retried)")
RETRY_POLICY = {"penalize_429_s": 300}
CAPABILITIES = frozenset({"search"})   # opt-in `find --backends elicit`; reports are their own subcommands
DEFAULT_IN_FIND = False                # user decision (Checkpoint 1, 2026-10-11): never in default fusion
FIND_LEGS = ("elicit",)
COST_NOTE = ("Pro plan or higher; per-call cost undocumented (usage draws from the plan's credit pool, API "
             "Terms §1.4): measure with elicit-usage before/after; reports are paid (--confirm-spend)")
ATTRIBUTION = ("Search results and research reports from Elicit (https://elicit.com) under the Elicit API Terms: "
               "reports and summaries are AI-generated, so disclose AI generation wherever they are used (§3.4); "
               "outputs are non-deterministic (§4.2), so the archived raw response is the only record; never "
               "submit personal data, names included (§2); restricted (stored in restricted/, never shared, "
               "deleted within 30 days if API access ends, §12.3)")
GET_KEY_URL = "https://elicit.com/developer"

API = "https://elicit.com/api/v2"
SEARCH_DEFAULT_MAX = 10
POLL_ATTEMPTS = 3
TYPE_TAGS = ("Review", "Meta-Analysis", "Systematic Review", "RCT", "Longitudinal")
REPORT_SEARCH_BOUNDS = (1, 1000)   # openapi.json maxSearchPapers minimum/maximum
REPORT_EXTRACT_BOUNDS = (1, 80)    # openapi.json maxExtractPapers minimum/maximum
# researchQuestion / query maxLength is 2000 (openapi.json); the core's
# QUERY_MAX_LEN (1000) is stricter, so no separate Elicit cap is needed.
# Create answers accepted as "created" (1.4.0): openapi.json declares only
# 202 for POST /sessions/reports (research script 26, 2026-10-12); 201 Created
# means the same by HTTP semantics. Any other answer is an UNCERTAIN create
# (the core records it and refuses a same-question re-run).
CREATE_OK_STATUSES = (202, 201)
# Report statuses (openapi.json ReportSessionDetail.status). The docs say to
# stop on completed/failed/unknown and to handle the quota pause separately
# (it never resumes by itself). Since 1.4.0 the core keeps polling ANY other
# status (processing, or one the docs do not list, e.g. "queued") until the
# wall-clock cap, then exits 13 with the re-attach command.
STATUS_PROCESSING = "processing"
STATUS_PAUSED = "pausedForInsufficientQuota"
STATUS_TERMINAL = ("completed", "failed", "unknown", STATUS_PAUSED)
EXPORT_FIELDS = ("pdfUrl", "docxUrl", "txtUrl", "bibUrl", "risUrl")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
PERSONAL_DATA_NOTE = ("Elicit's API Terms (§2) prohibit submitting personal data, names included: keep people's "
                      "names out of the query or question.")


# §§ AUTH_AND_COST
def key_present():
    return bool(key_value(KEY_ENV))


def auth_headers():
    # HEADERS ONLY (the core refuses a key in a URL/param/body).
    key = key_value(KEY_ENV)
    return {"Authorization": f"Bearer {key}"} if key else {}


def degraded_note():
    return None   # no keyless mode: a missing key is exit 10 (REQUIRED_KEY)


def parse_cost(headers):
    return None   # Elicit reports no spend per call; usage is read from GET /usage


# §§ MAPPER
def to_record(p):
    # INTENT: an Elicit paper -> common record. Elicit-only fields that matter
    #   for screening (study-design tags, SJR quartile, best full-text link)
    #   ride in `elicit`, and a null abstract is labelled as withheld (the docs:
    #   null "for publishers whose abstracts Elicit cannot redistribute"), so
    #   "no abstract" is never read as "the paper has none".
    # REASONING: fullTextUrl is "best available full-text / PDF link" with no
    #   license, so it is NOT put in oa_url (which `oa` and the digest treat as
    #   a legal open-access copy); the digest shows it as Elicit's link.
    abstract = p.get("abstract")
    urls = [u for u in (p.get("urls") or []) if isinstance(u, str) and u]
    tags = [t for t in (p.get("studyTypeTags") or []) if isinstance(t, str)]
    doi = norm_doi(p.get("doi"))
    return record(
        title=p.get("title") or "",
        year=p.get("year"),
        authors=[a for a in (p.get("authors") or []) if isinstance(a, str) and a],
        venue=p.get("venue") or "",
        doi=doi,
        cites=p.get("citedByCount"),
        abstract=abstract or "",
        type=", ".join(tags),
        url=(f"https://doi.org/{doi}" if doi else (urls[0] if urls else None)),
        ids={NAME: p.get("elicitId"), "pmid": p.get("pmid")},
        elicit={"studyTypeTags": tags, "journalQuartile": p.get("journalQuartile"),
                "fullTextUrl": p.get("fullTextUrl"), "urls": urls,
                "abstract_withheld": abstract is None},
        backend=NAME,
        license_class=LICENSE_CLASS,
    )


def screening_tag(rec):
    # One digest line with the Elicit-only fields (render_entry extra_tag).
    e = rec.get("elicit") or {}
    parts = []
    if e.get("studyTypeTags"):
        parts.append("study types: " + ", ".join(e["studyTypeTags"]))
    if e.get("journalQuartile"):
        parts.append(f"journal quartile Q{e['journalQuartile']} (SJR)")
    if e.get("abstract_withheld"):
        parts.append("abstract: withheld by Elicit (publisher does not allow redistribution)")
    if e.get("fullTextUrl"):
        parts.append(f"full-text link (Elicit, license unknown): {e['fullTextUrl']}")
    return "; ".join(parts)


# §§ REQUESTS
def search_body(query, max_results, mode="semantic", corpus="elicit", years=None, type_tags=None):
    # The documented request body. The core validates the keyword-vs-filter
    # exclusion before calling (parser error, no request); this re-checks so
    # no caller can send the documented 400.
    filters = {}
    lo, hi = parse_year_range(years)
    if lo is not None:
        filters["minYear"] = lo
    if hi is not None:
        filters["maxYear"] = hi
    if type_tags:
        filters["typeTags"] = list(type_tags)
    if filters and mode == "keyword":
        raise BackendError(NAME, "api", "elicit: filters (--years/--type-tags) and --mode keyword are mutually "
                                        "exclusive (Elicit returns 400); put filter terms in the keyword query")
    body = {"query": query, "maxResults": int(max_results), "searchMode": mode, "corpus": corpus}
    if filters:
        body["filters"] = filters
    return body


def search(http, query, max_results, mode="semantic", corpus="elicit", years=None, type_tags=None, max_wait=None):
    # Synchronous POST /search/papers. Returns (records, parsed response).
    # REASONING (1.4.0, S2 review): a search starts no session, but it may
    #   draw quota (the docs declare 402 for it; percentUsed moved 0 -> 3
    #   after one 1-result search plus one 10/5 report, read 2026-10-12 with
    #   lagged accounting, per-call split unknown). A retried search could
    #   therefore be charged twice, so it is sent as a NON-idempotent POST:
    #   one attempt, a 5xx or timeout is not retried, and no 3xx is followed
    #   (1.5.0). A 429 is never retried either (RETRY_POLICY: lane paused 300 s).
    body = search_body(query, max_results, mode, corpus, years, type_tags)
    kw = {"max_wait": max_wait} if max_wait is not None else {}
    _, parsed = http.post(NAME, f"{API}/search/papers", body, None, auth_headers(), ok_statuses=(200,),
                          idempotent=False, **kw)
    parsed = parsed if isinstance(parsed, dict) else {}
    recs = [to_record(p) for p in (parsed.get("papers") or []) if isinstance(p, dict)]
    return recs, parsed


def find_legs(http, a, keywords, ctx):
    # Opt-in only (`find --backends …,elicit`; DEFAULT_IN_FIND False). Elicit
    # search is semantic, so it gets the QUESTION, with --years as a filter.
    # The whole `find` then becomes restricted (most restrictive class).
    return [(NAME, lambda: (search(http, a.query, a.per_source, "semantic", "elicit", a.years)[0], None))]


def usage(http):
    # GET /usage: free (starts no work). A 409 (usage reporting unavailable /
    # not ready) raises BackendError api 409; the core reads it as an answer.
    return http.get(NAME, f"{API}/usage", None, auth_headers(), max_attempts=POLL_ATTEMPTS)


def create_report(http, question, max_search, max_extract):
    # POST /sessions/reports, EXACTLY ONCE (idempotent=False: the core's Http
    # makes one attempt and follows no redirect at all, 1.5.0, so a
    # timeout/5xx/3xx is never turned into a second paid session or read as
    # "not started"). isPublic is sent explicitly
    # false. Returns (status, parsed); see CREATE_OK_STATUSES.
    body = {"researchQuestion": question, "maxSearchPapers": int(max_search),
            "maxExtractPapers": int(max_extract), "isPublic": False}
    return http.post(NAME, f"{API}/sessions/reports", body, None, auth_headers(), ok_statuses=CREATE_OK_STATUSES,
                     idempotent=False)


def get_report(http, session_id, include_body=False, max_wait=None):
    # GET /sessions/reports/{id} (a read; 5xx retried a little, 429 never).
    params = {"include": "reportBody"} if include_body else None
    kw = {"max_wait": max_wait} if max_wait is not None else {}
    return http.get(NAME, f"{API}/sessions/reports/{session_id}", params, auth_headers(),
                    max_attempts=POLL_ATTEMPTS, **kw)


def resume_session(http, session_id):
    # POST /sessions/{id}/resume (no body), once: it restarts paid work. 409 =
    # session_not_paused (raised as BackendError api 409; the core reports it).
    return http.post(NAME, f"{API}/sessions/{session_id}/resume", None, None, auth_headers(),
                     ok_statuses=(200,), idempotent=False)


SESSION_IN_PATH_RE = re.compile(r"/(?:sessions/reports|sessions|review)/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
                                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:[/?#]|$)")


def session_id_in(url):
    # 1.5.0 (S2 review cycle 2 Finding 1): the core refuses every redirect on
    # the create POST; if the refused Location names a session
    # (/sessions/reports/<uuid>, /sessions/<uuid>, or the web /review/<uuid>),
    # that UUID is the create's recovery sessionId. Returns it or None.
    m = SESSION_IN_PATH_RE.search(str(url or ""))
    return m.group(1) if m else None


def error_code(body):
    # Elicit errors: {"error": {"code", "message", "sessionId"?}}; the edge 429
    # is flat {"error": "Rate limit exceeded", "message": …}. Returns
    # (code, message, recovery sessionId) defensively for either shape.
    if not isinstance(body, dict):
        return None, None, None
    err = body.get("error")
    if isinstance(err, dict):
        return err.get("code"), err.get("message"), err.get("sessionId")
    if isinstance(err, str):
        return err, body.get("message"), None
    return None, None, None


def explain_status(http_status, code):
    # A plain-language reason for the HTTP statuses the docs define.
    return {400: "invalid request (check the query/question, limits and the keyword-vs-filter rule; the plan's "
                 "maxResults cap is 300 on Pro)",
            401: "authentication failed: ELICIT_API_KEY is missing, invalid, revoked or expired",
            402: "insufficient quota: the Elicit usage allowance is exhausted; check `elicit-usage`, resolve the "
                 "limit (top up, or wait for periodEnd), then retry",
            403: "API access is not available on this plan (Elicit API needs Pro or above)",
            404: "session not found, of another type, or owned by someone else",
            409: f"conflict ({code or 'see error.code'})"}.get(http_status, f"HTTP {http_status}")
