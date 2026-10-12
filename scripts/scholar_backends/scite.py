# =============================================================================
# scholar_backends/scite.py - Scite adapter (keyless tallies + editorial
#                             notices; keyed Search behind a license ack)
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). Builds requests through the core's Http object, maps native
# JSON, parses nothing billable. Never writes files; never handles provenance.
#
# Documented behavior (docs.scite.ai, fetched 2026-10-11 into the S1
# workspace web_fetches/s2_research/; earlier copies 2026-10-02 in
# web_fetches/apis/):
#   - "Papers and Tallies are public and don't require an API key. All other
#     Scite endpoints require an API key" (authentication.md). Keys: Bearer
#     header, self-service keys need a Pro plan ("for evaluation").
#   - GET /papers/{doi} returns PaperResponse: metadata plus `retracted`,
#     `editorialNotices[{status,date,noticeDoi,doi,urls}]` AND `tally`
#     (Classifier Results). GET /tallies/{doi} returns {total, supporting,
#     contradicting, mentioning, unclassified, doi, citingPublications}.
#     POST /tallies (up to 500 DOIs) is the batch form; the guide shows a
#     {"dois": [...]} body, which measured 400 (see MEASURED below).
#   - GET /api_partner/search?term=&limit= needs a key; "Commercial or
#     research use of Search requires a separate license agreement"; snippets
#     are redacted on Pro keys (hits[].citations[].snippetHidden).
#   - Errors are JSON {"detail": …}: 401 no/invalid credential, 403 missing
#     scope, 404 unknown DOI, 422 validation, 429 rate limit.
#   - Terms: every endpoint, keyless included, is "subject to the Scite Terms
#     of Use"; §8(b) bars storing / redistributing content or derived
#     datasets for third parties; §4(iii) bars removing author or licensor
#     notices. No attribution clause. -> LICENSE_CLASS "restricted".
#   - REST says `contradicting`; Scite's product pages and MCP say
#     `contrasting`. This adapter keeps the REST word.
# MEASURED (2026-10-11, live CLI runs into research/2026-10-02_FrameworkDev_
# ScholarlySearch/smoke_s2/scite/, MANIFEST rows 1-6; references/scite.md):
#   - Keyless: RateLimit-Limit 60, X-RateLimit-Limit-Minute 60, one bucket
#     shared by /papers and /tallies (Remaining fell 59 -> 55 across both).
#     Keyed Search: RateLimit-Limit 13 (X-RateLimit-Limit-Second 13) and
#     X-RateLimit-Limit-Minute 60.
#   - Keyless /papers carried `retracted` and `editorialNotices` but NO
#     `tally` key (the schema lists it); notices had no `urls` field.
#     Notice statuses seen: "Retracted", "Has correction", "Has erratum",
#     "Has expression of concern", "Comment" (on a retracted 1998 paper).
#   - 404: {"detail": "Tally not found"}. Batch POST /tallies: bare-array
#     body (the documented {"dois": […]} got 400 {"message": "Invalid
#     request."}); answer {"tallies": {doi: tally}}.
#   - Search hits: titles carry <strong class="highlight"> markup; every
#     citation came back snippetHidden true with snippet "" on the Pro key.
# =============================================================================

import re

from ._common import BackendError, key_value, norm_doi, record, strip_tags

# §§ CONTRACT
NAME = "scite"
LABEL = "Scite"
KEY_ENV = "SCITE_API_KEY"
REQUIRED_KEY = False          # papers/tallies are keyless; only scite-search needs the key (exit 10 there)
LICENSE_CLASS = "restricted"  # Scite Terms of Use §8(b); user decision D-4 (2026-10-11)
RATE_LIMIT = {"scite": 1.1}   # one keyless bucket of 60/min shared by /papers and /tallies (measured)
RATE_LIMIT_NOTE = "keyless 60/min, one bucket for /papers + /tallies (measured 2026-10-11); gated 1.1 s"
CAPABILITIES = frozenset({"retraction", "stance"})   # Search stays its own subcommand, never in `find`
DEFAULT_IN_FIND = False
COST_NOTE = "papers/tallies free (keyless); Search needs a Pro key (evaluation) plus a separate research license"
ATTRIBUTION = ("Smart Citation tallies and editorial notices from Scite (https://scite.ai) under the Scite Terms "
               "of Use: no attribution clause, but never remove or alter author names or licensor notices; "
               "restricted (stored in restricted/, never shared)")
GET_KEY_URL = "https://scite.ai/users/me/api"

API = "https://api.scite.ai"
SEARCH_DEFAULT_LIMIT = 5
TALLY_FIELDS = ("supporting", "contradicting", "mentioning", "unclassified", "total", "citingPublications")
# Retraction-check status vocabulary (the template's): native notice statuses
# are matched by stem, most severe first, so a variant spelling ("Retraction
# Notice", "withdrawn") still maps to the severe class. A published comment
# ("Comment", measured 2026-10-11) maps to "commented" (1.4.0, user decision
# Checkpoint 2, 2026-10-12): it is not an editorial change to the paper, so
# it ranks with "none" (SEVERITY below and the core's `retractions`) and
# never raises a combined status. Anything else is the soft "updated" (a
# notice exists, of no harder kind). The native value is always kept
# verbatim in the notice ("native_status").
STATUS_STEMS = (("retracted", ("retract", "withdr", "remov")),
                ("expression of concern", ("concern",)),
                ("corrected", ("correct", "errat", "corrig")),
                ("commented", ("comment",)))
SEVERITY = {"retracted": 4, "expression of concern": 3, "corrected": 2, "updated": 1, "commented": 0}


# §§ AUTH_AND_COST
def key_present():
    return bool(key_value(KEY_ENV))


def auth_headers():
    # HEADERS ONLY (the core refuses a key in a URL/param/body). Sent only on
    # keyed endpoints (Search): the keyless papers/tallies calls go without
    # it, so keyless use is never charged to (or licensed under) the
    # evaluation key.
    key = key_value(KEY_ENV)
    return {"Authorization": f"Bearer {key}"} if key else {}


def degraded_note():
    # Keyless IS the intended mode for tallies and retraction notices, so no
    # banner; scite-search reports a missing key itself (exit 10).
    return None


def parse_cost(headers):
    return None   # Scite reports no spend; RateLimit-* headers are logged by the core


# §§ MAPPER
def _authors(p):
    out = []
    for a in p.get("authors") or []:
        if not isinstance(a, dict):
            continue
        name = a.get("authorName") or " ".join(x for x in (a.get("given"), a.get("family")) if x)
        if name:
            out.append(name)
    return out


def to_record(p):
    # A /papers response or a search hit -> common record. The tally is NOT
    # mapped into `cites` (tally counts are citation statements, and keeping
    # Classifier Results out of the record keeps them out of shared digests).
    # Search hits wrap matched words in <strong class="highlight"> (measured
    # 2026-10-11), so title and abstract are tag-stripped.
    slug = p.get("slug")
    return record(
        title=strip_tags(p.get("title")),
        year=p.get("year"),
        authors=_authors(p),
        venue=p.get("journal") or p.get("shortJournal") or "",
        doi=norm_doi(p.get("doi")),
        abstract=strip_tags(p.get("abstract")),
        type=p.get("type") or "",
        url=f"https://scite.ai/reports/{slug}" if slug else None,
        ids={NAME: slug},
        retracted=True if p.get("retracted") else None,
        backend=NAME,
        license_class=LICENSE_CLASS,
    )


def tally_of(t):
    # The six documented tally fields (REST names), None when absent.
    t = t if isinstance(t, dict) else {}
    return {k: t.get(k) for k in TALLY_FIELDS}


def map_notice_status(native):
    # Native editorialNotices[].status -> template vocabulary (see STATUS_STEMS).
    s = re.sub(r"[\s_\-]+", " ", str(native or "")).strip().lower()
    for status, stems in STATUS_STEMS:
        if any(stem in s for stem in stems):
            return status
    return "updated"


# §§ REQUESTS
def get_paper(http, doi):
    return http.get(NAME, f"{API}/papers/{doi}", None, {})


def tally(http, doi):
    # Keyless GET /tallies/{doi}; 404 -> BackendError not-found (core).
    return http.get(NAME, f"{API}/tallies/{doi}", None, {})


def tallies(http, dois):
    # Keyless batch POST /tallies: a READ sent as POST, so it is declared
    # idempotent (retried on 429/5xx like a GET). Returns {doi: tally} keyed
    # by normalized DOI; a DOI Scite does not know is absent.
    # REASONING (measured 2026-10-11, smoke_s2/scite/): the body is a BARE
    #   JSON array of DOIs. The guide's {"dois": [...]} form got HTTP 400
    #   {"message":"Invalid request."} keyless; the bare array got 200
    #   {"tallies": {doi: tally}}.
    _, parsed = http.post(NAME, f"{API}/tallies", list(dois), None, {}, idempotent=True)
    return normalize_batch(parsed)


def normalize_batch(parsed):
    # Measured answer: {"tallies": {doi: tally}}. {doi: tally} and a list of
    # tallies carrying `doi` are accepted too, defensively.
    if isinstance(parsed, dict) and isinstance(parsed.get("tallies"), (dict, list)):
        parsed = parsed["tallies"]
    out = {}
    if isinstance(parsed, dict):
        for k, v in parsed.items():
            if isinstance(v, dict):
                out[norm_doi(v.get("doi") or k)] = v
    elif isinstance(parsed, list):
        for v in parsed:
            if isinstance(v, dict) and v.get("doi"):
                out[norm_doi(v["doi"])] = v
    return out


def search(http, term, limit):
    # Keyed GET /api_partner/search. The core checks the license ack and the
    # key before calling this; a missing key here is still not-configured.
    if not key_present():
        raise BackendError(NAME, "not-configured", f"scite: {KEY_ENV} is not set; scite-search needs a Scite "
                                                   "API key (Pro plan) in host-side environment_settings.txt")
    return http.get(NAME, f"{API}/api_partner/search", {"term": term, "limit": limit}, auth_headers())


# §§ RETRACTION
def retraction_check(http, doi):
    # INTENT: Scite's paper-level `retracted` flag plus its editorialNotices,
    #   which Scite curates from Crossref, PubMed and its own notice detection.
    #   Returns FACTS ONLY (status, notice DOIs, dates, native status): the
    #   `retractions` digest is stored in the open folder, while the raw
    #   /papers response (whose schema can embed a tally; none was present
    #   keyless on 2026-10-11) goes to restricted/ (core
    #   SPLIT_STORAGE_COMMANDS). Never put a tally field in this return value.
    p = get_paper(http, doi)
    notices = []
    for n in p.get("editorialNotices") or []:
        if not isinstance(n, dict):
            continue
        native = n.get("status")
        notices.append({"type": str(native) if native is not None else "notice", "native_status": native,
                        "status": map_notice_status(native), "notice_doi": norm_doi(n.get("noticeDoi")),
                        "source": NAME, "date": n.get("date"), "via": "papers.editorialNotices"})
    if p.get("retracted"):
        status = "retracted"
    elif notices:
        status = max((n["status"] for n in notices), key=lambda s: SEVERITY.get(s, 1))
    elif p.get("retracted") is False or "editorialNotices" in p:
        status = "none"
    else:
        status = "unknown"   # neither field present: Scite said nothing either way
    return {"source": NAME, "status": status, "notices": notices, "title": p.get("title")}
