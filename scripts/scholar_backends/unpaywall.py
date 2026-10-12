# =============================================================================
# scholar_backends/unpaywall.py - Unpaywall REST API adapter (keyless, email)
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). Never writes files; never handles provenance.
#
# Documented behavior (help.openalex.org/access/unpaywall, fetched
# 2026-10-02): since late 2025 Unpaywall runs on the OpenAlex database; its
# is_oa / oa_status / PDF link equal OpenAlex's open_access and
# best_oa_location. The REST API is api.unpaywall.org/v2/{DOI}?email=…, covers
# Crossref DOIs only (404 otherwise). The unpaywall.org API/data-format pages
# are JS-rendered and could not be extracted, so the daily-limit figure
# (100k/day, from search snippets) is UNVERIFIED.
#
# Measured behavior (2026-10-02, live `oa --all-legs`, smoke_s1/ MANIFEST line
# 15; details in references/unpaywall.md):
#   - z_authors carry raw_author_name (+ author_position, is_corresponding,
#     raw_affiliation_strings), not given/family; the mapper reads both.
#   - host_type is always set ("publisher" | "repository");
#     repository_institution names the repository when there is one.
#   - A closed paper is HTTP 200 with is_oa false, best_oa_location null and
#     oa_locations []; a DataCite DOI is HTTP 404 with an HTML (not JSON) body.
#   - The response does not echo the email; no rate-limit headers are sent.
#
# The email is REQUIRED by the API and is the user's own choice:
# SCHOLARLY_CONTACT_EMAIL. When it is unset this adapter reports itself
# unconfigured and the `oa` command skips the leg with a note — no address is
# hard-coded or inferred. The core scrubs the address out of logged params.
# =============================================================================

from ._common import CONTACT_ENV, BackendError, contact_email, norm_doi, record

# §§ CONTRACT
NAME = "unpaywall"
LABEL = "Unpaywall"
KEY_ENV = None
# CONTACT_ENV (imported above, one definition in _common) is re-exported as a
# module attribute: the core's `backends` report reads it to show presence.
REQUIRED_KEY = False
LICENSE_CLASS = "open"
RATE_LIMIT = {"unpaywall": 0.1}
RATE_LIMIT_NOTE = "100k calls/day (UNVERIFIED: docs page is JS-only); gated 0.1 s"
CAPABILITIES = frozenset({"oa_locate"})
DEFAULT_IN_FIND = False
COST_NOTE = "free"
ATTRIBUTION = "Open-access locations from Unpaywall (OurResearch/OpenAlex)"
GET_KEY_URL = None

API = "https://api.unpaywall.org/v2"


# §§ AUTH_AND_COST
def key_present():
    return contact_email() is not None


def auth_headers():
    return {}


def degraded_note():
    if contact_email():
        return None
    return (f"Unpaywall: {CONTACT_ENV} is not set; the Unpaywall leg is skipped "
            "(OpenAlex best_oa_location carries the same data).")


def parse_cost(headers):
    return None


# §§ MAPPER
def _host(loc):
    # host_type is always present live (2026-10-02), so an `or` fallback to
    # repository_institution never fired; show both: "repository: <name>".
    kind, inst = loc.get("host_type"), loc.get("repository_institution")
    return f"{kind}: {inst}" if kind and inst else (kind or inst)


def _candidate(loc, best):
    url = loc.get("url_for_pdf") or loc.get("url") or loc.get("url_for_landing_page")
    if not url:
        return None
    return {"leg": NAME, "url": url, "is_pdf": bool(loc.get("url_for_pdf")),
            "license": loc.get("license"), "version": loc.get("version"),
            "host": _host(loc), "best": best}


def to_record(d):
    best = d.get("best_oa_location") or {}
    authors = []
    for a in d.get("z_authors") or []:
        name = " ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("raw_author_name")
        if name:
            authors.append(name)
    return record(
        title=d.get("title") or "",
        year=d.get("year"),
        authors=authors,
        venue=d.get("journal_name") or "",
        doi=norm_doi(d.get("doi")),
        type=d.get("genre") or "",
        oa_url=best.get("url_for_pdf") or best.get("url"),
        oa={"is_oa": d.get("is_oa"), "license": best.get("license"), "version": best.get("version"),
            "host": _host(best)},
        url=d.get("doi_url"),
        ids={"doi": norm_doi(d.get("doi"))},
        backend=NAME,
        license_class=LICENSE_CLASS,
    )


# §§ OA_LOCATE
def oa_locate(http, doi):
    email = contact_email()
    if not email:
        raise BackendError(NAME, "not-configured", f"unpaywall: {CONTACT_ENV} unset; leg skipped")
    d = http.get(NAME, f"{API}/{doi}", {"email": email})
    best = d.get("best_oa_location") or {}
    cands = []
    first = _candidate(best, True) if best else None
    if first:
        cands.append(first)
    for loc in d.get("oa_locations") or []:
        c = _candidate(loc, False)
        if c and all(c["url"] != x["url"] for x in cands):
            cands.append(c)
    return cands, to_record(d), d.get("oa_status")
