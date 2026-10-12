# Backend scaffold template

Copy-and-fill scaffolding for a new `scholar_search` backend: (1) the adapter
module, (2) the per-backend reference file, (3) the unit-test additions.
Follow `adding-a-backend.md` for the workflow; this file is only the
skeletons. Replace every `<…>` placeholder. The built-in adapters in
`scripts/scholar_backends/` are the working references: **`unpaywall.py` is
the worked example** to read first — the smallest complete adapter (one
endpoint, one capability, a contract block, a mapper, live-measured behavior
in its header, and a test against live-wire fixtures; a `restricted` source
commits synthetic fixtures instead, see § 3). semantic_scholar.py
is the smallest keyed, search-capable one (`FIND_LEGS`, `find_legs()`,
`ID_KEY`); crossref.py shows `retraction_check()`.

## 1. Adapter — `scripts/scholar_backends/<name>.py`

```python
# =============================================================================
# scholar_backends/<name>.py - <Label> adapter
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). Builds requests through the core's Http object, maps native
# JSON to the common record schema, parses cost headers. Never writes files;
# never handles provenance.
#
# Documented behavior (<doc URL>, fetched <YYYY-MM-DD>): <auth, limits, terms>
# Measured behavior (<YYYY-MM-DD>, smoke run <path>): <what the live call showed>
# =============================================================================

from ._common import BackendError, key_value, norm_doi, record

# §§ CONTRACT
NAME = "<name>"                      # CLI/MANIFEST identifier, lowercase_underscore
LABEL = "<Label>"
KEY_ENV = "<NAME>_API_KEY"           # or None for keyless; unique across adapters
REQUIRED_KEY = False                 # True only if the API refuses keyless calls (missing key -> exit 10)
LICENSE_CLASS = "open"               # open | cc-by-nc | restricted (restricted -> lit_search/restricted/)
RATE_LIMIT = {"<name>": 1.1}         # lane -> min seconds between requests (doc limit + margin); None = no gate;
                                     # lane names are unique across adapters
RATE_LIMIT_NOTE = "<documented limit, and the gate interval>"
CAPABILITIES = frozenset({"search"})  # subset of: search lookup cites refs oa_locate fulltext retraction stance
DEFAULT_IN_FIND = False              # new backends stay opt-in (find --backends) until reviewed
FIND_LEGS = ("<name>",)              # REQUIRED with "search": every leg name find_legs() returns;
                                     # unique across adapters; becomes a `find --skip` choice
# ID_KEY = "<key>"                   # optional: only if to_record() keys its native id under a
                                     # name other than NAME in `ids` (semantic_scholar uses "s2")
COST_NOTE = "<free | $ per call>"
ATTRIBUTION = "<citation or credit the terms require>"
GET_KEY_URL = "<https://… or None>"

API = "https://<host>/<base>"


# §§ AUTH_AND_COST
def key_present():
    return bool(key_value(KEY_ENV)) if KEY_ENV else True


def auth_headers():
    # HEADERS ONLY. A key in a URL or param is refused by the core's guard.
    key = key_value(KEY_ENV)
    return {"Authorization": f"Bearer {key}"} if key else {}


def degraded_note():
    # One line printed (and recorded) when running without the key, else None.
    return None if key_present() else "<Label>: <KEY_ENV> not set; <what degrades>"


def parse_cost(headers):
    # Return {"cost_usd": …, "remaining_usd": …, …} from response headers, or None.
    return None


# §§ MAPPER
def to_record(item):
    # Native object -> common record schema (see _common.record()). Do NOT
    # add provenance fields; the core adds them.
    return record(
        title=item.get("<title field>") or "",
        year=item.get("<year field>"),
        authors=[<author names>],
        venue=item.get("<venue field>") or "",
        doi=norm_doi(item.get("<doi field>")),
        cites=item.get("<citation count field>"),
        abstract=item.get("<abstract field>") or "",
        type=item.get("<type field>") or "",
        oa_url=<pdf url or None>,
        url=<landing page>,
        ids={NAME: item.get("<native id field>")},
        backend=NAME,
        license_class=LICENSE_CLASS,
    )


# §§ REQUESTS
def search(http, query, limit, years=None):
    parsed = http.get(NAME, f"{API}/<search path>", {"<q param>": query, "<limit param>": limit},
                      auth_headers())
    items = parsed.get("<results key>") or []
    return [to_record(i) for i in items if isinstance(i, dict)], parsed.get("<total key>")


def find_legs(http, a, keywords, ctx):
    # One (leg_name, thunk) per ranked list this backend adds to `find`.
    # Use `keywords` for keyword engines; `a.query` for semantic engines.
    return [(NAME, lambda: search(http, keywords, a.per_source, a.years))]


# Optional, per capability:
# def retraction_check(http, doi): -> {"source": NAME, "status": "retracted|expression of concern|corrected|updated|commented|none|unknown", "notices": [...], "title": ...}
#     ("updated" = a notice exists but of no harder kind; see crossref.md § Retraction status values;
#      "commented" (tool 1.4.0) = only published comments are on record: ranked WITH "none" in
#      `retractions`, so it never raises the combined status — see scite.md § Retraction status values;
#      a restricted backend returns facts only: its digest lines stay in the open folder — scite.py)
# POST: _, parsed = http.post(NAME, url, body, None, auth_headers(), ok_statuses=(200,), idempotent=False)
#     one attempt and no redirect followed (tool 1.5.0) unless idempotent=True (free reads only; a call that may
#     draw quota, like Elicit search, stays non-idempotent); RETRY_POLICY = {"penalize_429_s": N} for
#     a timed 429 block (see adding-a-backend.md § "What an adapter may raise")
# def oa_locate(http, doi): -> (candidates[{leg,url,is_pdf,license,version,host}], record, oa_status)
#
# Failures: raise only BackendError(NAME, kind, message) — see adding-a-backend.md
# § "What an adapter may raise" for the kinds and the exit code each maps to.
# If the backend can flag a work as retracted, set record(retracted=True); the
# core then tags it "[RETRACTED per <LABEL>]" with no core change.
```

Then add the module to the `ADAPTERS` tuple in
`scripts/scholar_backends/__init__.py` (the registry validates it at import:
a contract violation exits 1) and, if keyed, to the env template and
user_reference key table.

## 2. Reference — `.claude/skills/scholarly-search/references/<name>.md`

```markdown
# <Label>

<One paragraph: what it covers, why it is in the toolkit (the coverage gap),
its adapter path, its docs URL and the fetch date.>

## Auth
<Key env var, where to get it, header form, keyless behavior.>

## Endpoints used
| Use | Request | Command |
|-----|---------|---------|

## Cost and limits
<Per-call cost, quotas, rate limit, the gate interval chosen.>

## Measured behavior
- **<finding>** (<YYYY-MM-DD>, <probe>): <observation>.

## Storage and ToS
<Quote the storage/redistribution terms; state LICENSE_CLASS and attribution.>

## Exit mapping
<Which HTTP statuses mean bad key / quota / not found, and the exit code each yields.>

## Minimal smoke test
    bash /daaf/scripts/scholar_search.sh find "<q>" {PROJECT_DIR}/lit_search --backends <name> --limit 2
```

## 3. Tests — additions to `tests/python/test_scholar_search.py`

1. Save a trimmed **live** response as
   `tests/python/fixtures/scholar_search/<name>_search.json` with a
   `"_fixture_source"` field naming the smoke run and date. **Exception, a
   `restricted` source** (its terms bar sharing content; the repository is
   published): commit a **synthetic** fixture instead, with the live
   response's exact shape (every key path, value types, nesting, status
   vocabularies) and invented values, and `"_fixture_source": "SYNTHETIC;
   shape from live response <MANIFEST row, date>; values invented"`; the live
   response stays in the smoke run's `restricted/` folder
   (`adding-a-backend.md` Step 4; checklist SB7).
2. Add to `MapperTests`:

```python
    def test_<name>(self):
        from scholar_backends import <name>
        recs = [<name>.to_record(i) for i in fixture("<name>_search.json")["<results key>"]]
        self.assertTrue(recs and all(r["title"] and r["backend"] == "<name>" for r in recs))
        self.assertEqual(recs[0]["license_class"], <name>.LICENSE_CLASS)
```

3. `test_registry_contract` already validates every registered adapter; if
   the backend is keyed, extend `BehaviorTests.test_backends_never_prints_key_values`
   with a sentinel value for its `KEY_ENV`.
4. Run `python3 -m unittest discover -s /daaf/tests/python -p "test_scholar_search.py"`
   file-first, from a captured script under the session's `scripts/`
   executed with `run_with_capture.sh` (checklist SB15), and quote the result
   line.
