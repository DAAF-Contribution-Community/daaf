# =============================================================================
# scholar_backends/eric.py - ERIC (IES, U.S. Department of Education) adapter
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). Never writes files; never handles provenance.
#
# Measured behavior (2026-09-27, the user's original tool):
#   - Endpoint https://api.ies.ed.gov/eric/, no key, JSON via format=json.
#   - Solr's default operator is OR: "school finance reform" returned 171,348
#     hits; AND-joined it returned 183. Plain words are AND-joined here;
#     quotes, boolean operators and field: syntax pass through untouched.
#   - Filters: peerreviewed:T, e_fulltextauth:1 (not T),
#     publicationdateyear:[2018 TO *]. No DOI field, no citation counts.
#   - Full-text PDFs live at https://files.eric.ed.gov/fulltext/{ED…}.pdf
#     when e_fulltextauth is 1.
# =============================================================================

import re

from ._common import record

# §§ CONTRACT
NAME = "eric"
LABEL = "ERIC"
KEY_ENV = None
REQUIRED_KEY = False
LICENSE_CLASS = "open"        # U.S. federal (IES) metadata; abstracts may carry publisher rights
RATE_LIMIT = {"eric": None}
RATE_LIMIT_NOTE = "undocumented; no gate (low call volume)"
CAPABILITIES = frozenset({"search", "lookup", "oa_locate"})
DEFAULT_IN_FIND = True
FIND_LEGS = ("eric",)
COST_NOTE = "free"
ATTRIBUTION = "Institute of Education Sciences, ERIC (https://eric.ed.gov)"
GET_KEY_URL = None

API = "https://api.ies.ed.gov/eric/"
FIELDS = ("id,title,author,publicationdateyear,source,peerreviewed,description,"
          "publicationtype,url,e_fulltextauth,subject")
FIELD_SYNTAX = re.compile(r'(\b(AND|OR|NOT)\b|"|\w+:)')


# §§ AUTH_AND_COST
def key_present():
    return True   # keyless backend


def auth_headers():
    return {}


def degraded_note():
    return None


def parse_cost(headers):
    return None


# §§ MAPPER
def _as_list(v):
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)] if v else []


def pdf_url(eid):
    return f"https://files.eric.ed.gov/fulltext/{eid}.pdf"


def to_record(d):
    eid = d.get("id")
    year = d.get("publicationdateyear")
    try:
        year = int(year) if year else None
    except (TypeError, ValueError):
        year = None
    has_ft = str(d.get("e_fulltextauth")) == "1"
    return record(
        title=d.get("title") or "",
        year=year,
        authors=_as_list(d.get("author")),
        venue=d.get("source") or "",
        abstract=d.get("description") or "",
        type="; ".join(_as_list(d.get("publicationtype"))),
        fulltext=has_ft,
        oa_url=pdf_url(eid) if eid and has_ft else None,
        oa={"is_oa": True if has_ft else None, "license": None, "version": None,
            "host": "ERIC" if has_ft else None},
        url=f"https://eric.ed.gov/?id={eid}" if eid else None,
        ids={"eric": eid},
        peer_reviewed=d.get("peerreviewed") == "T",
        backend=NAME,
        license_class=LICENSE_CLASS,
    )


# §§ REQUESTS
def build_query(query, peer_reviewed=False, fulltext=False, years=None, dissertations=True):
    q = query.strip()
    if not FIELD_SYNTAX.search(q):
        q = " AND ".join(q.split())
    parts = [f"({q})"]
    if peer_reviewed:
        parts.append("peerreviewed:T")
    if fulltext:
        parts.append("e_fulltextauth:1")
    if years:
        # "2020" is a single year (not "2020 onward"), as in crossref.search.
        a, _, b = years.partition("-") if "-" in years else (years, "", years)
        parts.append(f"publicationdateyear:[{a or '*'} TO {b or '*'}]")
    q = " AND ".join(parts)
    return q if dissertations else q + " AND NOT publicationtype:Dissertations*"


def search(http, query, limit, peer_reviewed=False, fulltext=False, years=None, dissertations=True):
    params = {"search": build_query(query, peer_reviewed, fulltext, years, dissertations),
              "format": "json", "rows": min(limit, 200), "fields": FIELDS}
    parsed = http.get(NAME, API, params)
    resp = parsed.get("response") or {}
    return [to_record(d) for d in (resp.get("docs") or []) if isinstance(d, dict)], resp.get("numFound")


def find_legs(http, a, keywords, ctx):
    return [("eric", lambda: search(http, keywords, a.per_source, a.peer_reviewed, False, a.years,
                                    a.include_dissertations))]


# §§ OA_LOCATE
def oa_locate_by_title(http, title, title_match, min_ratio):
    # INTENT: ERIC has no DOI field, so the `oa` leg searches ERIC-hosted
    #   full text by exact title phrase and accepts only a confident title
    #   match: title_match is the core's difflib scorer, min_ratio the core's
    #   version-sibling cutoff (TITLE_MATCH_MIN), passed in so no copy of the
    #   number lives here.
    if not title:
        return []
    phrase = re.sub(r'["\\:]+', " ", title).strip()
    recs, _ = search(http, f'title:"{phrase}"', 5, fulltext=True)
    out = []
    for r in recs:
        ratio = title_match(title, r["title"])
        if ratio >= min_ratio and r.get("oa_url"):
            out.append({"leg": NAME, "url": r["oa_url"], "is_pdf": True, "license": None,
                        "version": None, "host": "ERIC", "title_similarity": round(ratio, 3),
                        "eric_id": r["ids"].get("eric")})
    return out
