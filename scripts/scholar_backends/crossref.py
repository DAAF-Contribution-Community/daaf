# =============================================================================
# scholar_backends/crossref.py - Crossref REST API adapter (keyless)
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). Never writes files; never handles provenance.
#
# Documented behavior (fetched 2026-10-02, web_fetches/apis/ in the S1
# workspace):
#   - No signup. Pools: public 5 req/s, 1 concurrent; polite (mailto param or
#     User-Agent) 10 req/s, 3 concurrent; Plus 150 req/s. 429 on excess; 403
#     on a manual block. Headers x-rate-limit-limit / x-rate-limit-interval /
#     x-concurrency-limit report the pool.
#   - "almost none of the metadata is subject to copyright … you may use it
#     for any purpose"; some abstracts may be copyrighted.
#   - Retraction Watch data (acquired 2023) is in the REST API: update
#     notices carry `update-to` with source "publisher" or "retraction-watch";
#     filter=update-type:retraction lists retraction notices.
#   - The polite pool needs a contact email. This adapter uses
#     SCHOLARLY_CONTACT_EMAIL when the user set it, else the public pool.
#     No address is ever hard-coded.
# =============================================================================

from ._common import (BackendError, contact_email, norm_doi, record, strip_tags)

# §§ CONTRACT
NAME = "crossref"
LABEL = "Crossref"
KEY_ENV = None                # Metadata Plus key not supported in v1
REQUIRED_KEY = False
LICENSE_CLASS = "open"
# Public pool is 5 req/s with ONE concurrent request; 0.25 s spacing keeps a
# container of concurrent agents inside it (the gate serializes slots).
RATE_LIMIT = {"crossref": 0.25}
RATE_LIMIT_NOTE = "public 5 req/s, 1 concurrent (gated 0.25 s); polite pool 10 req/s with SCHOLARLY_CONTACT_EMAIL"
CAPABILITIES = frozenset({"search", "lookup", "retraction"})
DEFAULT_IN_FIND = False       # topical relevance is weak; enable with --backends
FIND_LEGS = ("crossref",)
COST_NOTE = "free"
ATTRIBUTION = "Metadata from Crossref (https://www.crossref.org); no attribution required"
GET_KEY_URL = None

API = "https://api.crossref.org"
SELECT = ("DOI,title,author,issued,container-title,is-referenced-by-count,abstract,type,URL,"
          "license,update-to,updated-by,relation")
UPDATE_KINDS = {"retraction": "retracted", "withdrawal": "retracted", "removal": "retracted",
                "expression_of_concern": "expression of concern", "correction": "corrected",
                "erratum": "corrected", "corrigendum": "corrected"}


# §§ AUTH_AND_COST
def key_present():
    return True   # keyless backend


def auth_headers():
    return {}


def polite_params():
    email = contact_email()
    return {"mailto": email} if email else {}


def degraded_note():
    if contact_email():
        return None
    return ("Crossref: SCHOLARLY_CONTACT_EMAIL is not set, so requests use the public pool "
            "(5 req/s, 1 concurrent) instead of the polite pool.")


def parse_cost(headers):
    out = {k.replace("-", "_"): headers.get(k) for k in ("x-rate-limit-limit", "x-rate-limit-interval",
                                                          "x-concurrency-limit", "x-api-pool")
           if headers.get(k) is not None}
    return out or None


# §§ MAPPER
def _year(item):
    for key in ("issued", "published", "published-print", "published-online", "created"):
        parts = ((item.get(key) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            return parts[0]
    return None


def to_record(item):
    authors = []
    for a in item.get("author") or []:
        name = " ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name")
        if name:
            authors.append(name)
    lic = (item.get("license") or [{}])[0] if item.get("license") else {}
    # A retraction-kind notice in the work's own `updated-by` list marks the
    # record retracted (the core tags it "[RETRACTED per Crossref]"). No such
    # notice -> None (unknown), never False: `retractions` is the full check.
    kinds = {UPDATE_KINDS.get((e.get("type") or "").lower().replace("-", "_")) for e in item.get("updated-by") or []}
    return record(
        title=" ".join(item.get("title") or []),
        year=_year(item),
        authors=authors,
        venue=" ".join((item.get("container-title") or [])[:1]),
        doi=norm_doi(item.get("DOI")),
        cites=item.get("is-referenced-by-count"),
        abstract=strip_tags(item.get("abstract")),
        type=item.get("type") or "",
        oa={"is_oa": None, "license": lic.get("URL"), "version": lic.get("content-version"), "host": None},
        url=item.get("URL"),
        ids={"crossref": norm_doi(item.get("DOI"))},
        retracted=True if "retracted" in kinds else None,
        backend=NAME,
        license_class=LICENSE_CLASS,
    )


# §§ REQUESTS
def get_work(http, doi):
    parsed = http.get(NAME, f"{API}/works/{doi}", polite_params())
    item = parsed.get("message")
    if not isinstance(item, dict):
        raise BackendError(NAME, "api", "crossref: response had no message object")
    return item


def title_lookup(http, title, rows=5):
    params = {"query.bibliographic": title, "rows": rows, "select": SELECT}
    params.update(polite_params())
    parsed = http.get(NAME, f"{API}/works", params)
    return (parsed.get("message") or {}).get("items") or []


def search(http, query, limit, years=None):
    params = {"query": query, "rows": min(limit, 100), "select": SELECT}
    if years:
        a, _, b = years.partition("-") if "-" in years else (years, "", years)
        f = ",".join(x for x in (f"from-pub-date:{a}" if a else "", f"until-pub-date:{b}" if b else "") if x)
        if f:
            params["filter"] = f
    params.update(polite_params())
    parsed = http.get(NAME, f"{API}/works", params)
    msg = parsed.get("message") or {}
    return [to_record(i) for i in (msg.get("items") or []) if isinstance(i, dict)], msg.get("total-results")


def find_legs(http, a, keywords, ctx):
    return [("crossref", lambda: search(http, keywords, a.per_source, a.years))]


# §§ RETRACTION
def _notice(entry, via):
    kind = (entry.get("type") or "").lower().replace("-", "_")
    return {"type": kind, "status": UPDATE_KINDS.get(kind, kind or "update"),
            "notice_doi": norm_doi(entry.get("DOI")), "source": entry.get("source") or via,
            "date": "-".join(str(x) for x in (((entry.get("updated") or {}).get("date-parts") or [[]])[0]))
            or None, "via": via}


def retraction_check(http, doi):
    # INTENT: two Crossref signals, because members deposit some notices and
    #   Retraction Watch supplies many others:
    #   (1) the work's own `updated-by` list (notices that update it);
    #   (2) works whose `update-to` points at this DOI (filter=updates:{doi}).
    #   Status is the most severe notice found; "none" means Crossref has no
    #   notice on record, not that the paper is sound.
    notices = []
    title = None
    try:
        item = get_work(http, doi)
        title = " ".join(item.get("title") or [])
        for e in item.get("updated-by") or []:
            notices.append(_notice(e, "updated-by"))
    except BackendError as exc:
        if exc.kind != "not-found":
            raise
    params = {"filter": f"updates:{doi}", "rows": 20, "select": "DOI,title,type,update-to"}
    params.update(polite_params())
    parsed = http.get(NAME, f"{API}/works", params)
    for item in (parsed.get("message") or {}).get("items") or []:
        for e in item.get("update-to") or []:
            if norm_doi(e.get("DOI")) == doi:
                n = _notice(e, "updates-filter")
                n["notice_doi"] = n["notice_doi"] if n["notice_doi"] != doi else norm_doi(item.get("DOI"))
                notices.append(n)
    # The two signals usually report the same notice; keep one entry per
    # (notice DOI, type) and record every path that surfaced it.
    merged = {}
    for n in notices:
        k = (n["notice_doi"], n["type"])
        if k in merged:
            if n["via"] not in merged[k]["via"]:
                merged[k]["via"] += "+" + n["via"]
        else:
            merged[k] = n
    notices = list(merged.values())
    severity = {"retracted": 3, "expression of concern": 2, "corrected": 1}
    status = "none"
    for n in notices:
        if severity.get(n["status"], 0) > severity.get(status, 0):
            status = n["status"]
    # "updated": Crossref holds at least one notice for this DOI, but none of
    #   a retraction / expression-of-concern / correction kind (e.g. an
    #   "addendum" or "new_version"). Worth reading, not a hard flag.
    if status == "none" and notices:
        status = "updated"
    return {"source": NAME, "status": status, "notices": notices, "title": title}
