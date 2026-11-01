# OpenAlex

The backbone backend: authoritative metadata, the citation graph, semantic and
keyword search, cached GROBID full text, OA locations (the same data Unpaywall
serves since late 2025) and an `is_retracted` flag. Adapter:
`scripts/scholar_backends/openalex.py`. Docs: https://help.openalex.org
(`llms.txt` index); pages fetched 2026-10-02 are in the S1 workspace
`research/2026-10-02_FrameworkDev_ScholarlySearch/web_fetches/apis/`.

## Auth

- Key: `OPENALEX_API_KEY` — optional but **strongly recommended**. Free from
  https://openalex.org/settings/api-key (authentication page, 2026-10-28).
- Sent as `Authorization: Bearer <key>` (works on `api.openalex.org` and
  `content.openalex.org`, verified 2026-09-27). The docs also show
  `?api_key=`; the tool never uses it, so the key never reaches a URL, a log
  or a raw artifact.
- **Keyless:** "you can make basic queries with no key at all" (authentication
  page) at $0.10/day, but the deprecations page says "All users need an API
  key (free)". The docs conflict; the tool prints a DEGRADED MODE banner and
  keeps working until OpenAlex refuses.
- The old `mailto` polite pool is gone ("The `mailto` parameter is ignored").

## Endpoints used

| Use | Request | Commands |
|-----|---------|----------|
| Keyword search | `GET /works?filter=title_and_abstract.search:<q>&sort=relevance_score:desc` | `find`, `openalex --mode keyword` |
| Semantic search | `GET /works?search.semantic=<≤2000 chars>` | `find`, `similar`, `openalex --mode semantic` |
| Broad search | `GET /works?search=<q>` (also matches full text) | `openalex --mode broad` |
| Filter list | `GET /works?filter=cites:W…` / `openalex:W1|W2…` | `cites`, `refs` |
| Title lookup | `GET /works?filter=title.search:<title>` (billed as a search) | `work`, `verify` |
| Single work | `GET /works/W…` or `/works/doi:<doi>` (free) | `work`, `verify`, `oa`, `retractions` |
| Full text | `GET content.openalex.org/works/W….grobid-xml` | `fulltext` |

`select=` trims every response to the fields the mapper needs.
`--corpus core|expansion|all` passes the `corpus=` parameter (added August
2026; replaces the deprecated `include_xpac`).

## Cost and limits

| Operation | Per call | Source |
|-----------|----------|--------|
| Single entity by ID/DOI | free | docs + measured |
| List + filter | $0.0001 | docs + measured |
| Search / semantic search / `title.search` filter | $0.001 | docs + measured 2026-10-02 |
| Content download (`fulltext`) | $0.01 | docs |
| HTTP 400 (rejected request) | $0 | measured 2026-10-02 |

Budget: $1/day with a free key, $0.10/day keyless. Per-second limits, per
OpenAlex docs (authentication page), fetched 2026-10-28: 10 req/s keyless,
30 with a free key or prepaid usage, 50 on an annual plan; searches with more
than 5 `OR`/`AND`/`NOT` operators 1 / 5 / 25 req/s; "A per-second 429 costs
nothing". The same page said 100 req/s on 2026-10-02. Semantic search 1 req/s
and max 50 results; `per_page` max 100; 100 OR values per filter.

**Gating (tool 1.6.0, user decision 2026-10-30).** Several agents may search
at once, so the tool enforces the per-second limits container-wide through
the shared rate gate instead of leaving them to 429 retries. Every OpenAlex
request books the main `openalex` lane, and a search with more than 5
upper-case operators also books `openalex-boolean`, at the intervals of the
container's **rate tier**:

| Tier (`OPENALEX_RATE_TIER`) | Documented limit (all / >5 operators) | Gate interval (all / >5 operators) |
|---|---|---|
| `keyless` | 10 / 1 req/s | 0.11 s (~9.1/s) / 1.1 s (~0.9/s) |
| `free` (alias `prepaid`) | 30 / 5 req/s | 0.04 s (25/s) / 0.22 s (~4.5/s) |
| `annual` | 50 / 25 req/s | 0.024 s (~41.7/s) / 0.044 s (~22.7/s) |

**The tier is a setting (tool 1.6.1, user decision 2026-10-31),** because
the API does not tell a key's plan (no response header states it,
2026-10-30). Set `OPENALEX_RATE_TIER=annual` host-side in
`environment_settings.txt` (next to the key; then recreate the container:
Control Panel → **Restart Container**) when the key is on an annual plan. Unset, the tier is `free` with a key and `keyless`
without one. An unknown value falls back to that default (the warning shows
the value only when it is close to a tier name, such as `anual`; otherwise
"(value not shown)", so a key pasted there is not printed), and a keyed tier
with no key set falls back to `keyless`; both print a warning on stderr for
every command that uses OpenAlex, add `config_warnings` to the MANIFEST row,
and show in `scholar_search.sh backends`, which also prints the effective
tier and intervals (`openalex rate tier: …`). `keyless` with a key set is
allowed (slowest spacing; the key is still sent). Every process reads the
same environment when the adapter loads, so every process books the shared
gate with the same spacing. The one table of tiers is `RATE_TIERS` in
`openalex.py`: a vendor change to the limits is a one-row edit there.

The docs
say the heavy request types "have lower limits of their own", which the tool
reads as limits that add to the main one: a semantic search also books
`openalex-semantic` (1.1 s on every tier), and a search whose text carries
more than 5 upper-case `AND`/`OR`/`NOT` words also books `openalex-boolean`.
Such a request books all
its lanes in one step and leaves at a slot free on every one of them, so each
lane's spacing holds for send times (a review probe on 2026-10-30 showed
that booking them one after another let a main-lane backlog bunch sub-lane
requests). The price is some idle main-lane capacity while a sub-lane
request waits. Counting rule: whole upper-case words only, per the searching page
(fetched 2026-10-30): "Use AND, OR, NOT (uppercase) for complex queries", so
lower-case `and`/`or`/`not` are plain words. Two parts are DAAF's inference,
because the docs do not address them: words inside quoted phrases are
counted (conservative), and the text counted is the `search`/`search.*`
parameters plus the whole `filter` value when any clause is on a `.search`
field (the docs say "A comma in a search filter’s text is part of the text",
so a comma cannot hide operators). Code: `openalex.py` § CONTRACT, §
RATE_TIERS and § RATE_LANES.

Response headers (measured 2026-10-02 — **both** families are sent):
`x-ratelimit-cost-usd`, `x-ratelimit-remaining-usd`, `x-ratelimit-limit-usd`,
`x-ratelimit-prepaid-remaining-usd`, plus the documented credit family
`x-ratelimit-limit` (10000 = $1), `x-ratelimit-remaining`,
`x-ratelimit-credits-used` (10 per $0.001 search), `x-ratelimit-reset`
(seconds to midnight UTC), and an undocumented
`x-ratelimit-onetime-remaining` (sent, but not in the docs' header table). The response
`meta` also carries `cost_usd`. The adapter parses both families into the
MANIFEST row (`openalex_cost_usd`, `openalex_budget`).

## Measured behavior

- **Per-second gate** (re-measured 2026-10-30, tool 1.6.0, keyed; 7 free
  `work <DOI>` lookups): every response carried the same nine
  `x-ratelimit-*` headers as on 2026-10-02 (`-limit-usd 1`,
  `-prepaid-remaining-usd 0`, `-cost-usd 0`, …) and **none states a
  per-second limit or the plan tier**, so the gate cannot read the tier from
  the API (since 1.6.1 it is the `OPENALEX_RATE_TIER` setting, by default
  chosen from key presence). Three processes started together queued on the
  main lane (`rate_gate_wait_s` 0.0, 0.03, 0.07). Details: `api-notes.md` §
  "Measured behavior: OpenAlex per-second gate (2026-10-30)".
- **`search=` drifts** (2026-09-27): it matches full text and blends in
  citations; Chetty's teacher value-added paper ranked 4th for "school finance
  reform student outcomes". Hence keyword mode = `title_and_abstract.search` +
  `sort=relevance_score:desc`. Its terms are effectively ANDed, so pass
  `--keywords`, not a sentence.
- **Commas in `.search` filter text are text** (re-measured 2026-10-31,
  keyed, tool 1.6.1; this replaces the 2026-09-27 finding that a comma broke
  the filter). The filtering page (fetched 2026-10-31): "a comma in their
  text stays part of the text unless the next filter starts right after it
  (,type:)". Live, every shape answered HTTP 200: `reading, mathematics`,
  `reading,mathematics` and `reading mathematics` mid-filter, each followed by
  the type exclusions, all matched 475 works; the docs' `Music and British
  Culture, 1785` as the last clause matched 10, as did the comma-free form;
  `reading, mathematics: achievement` matched 141 (`mathematics` is not a
  filter name, so this does not show whether a space after the comma stops a
  clause). Since 1.6.1 `filter_value()` keeps commas, but turns into a space
  every comma followed by a field-name-shaped word and `:`, with optional
  whitespace before the word and before the `:`, in any case (`,type:`,
  `, type:`, `,TYPE:`, `,type :`). Only the no-space form is documented as a
  clause; the spaced forms were not measured and are neutralized as the
  conservative choice, at the cost of a comma before `word:` in real text
  (`Gaps, race:` → `Gaps  race:`), harmless per the counts above. Wildcards
  are removed first, so `,?type:` cannot slip through, and leading and
  trailing commas are dropped (a trailing one would meet the joining comma
  as `,,`).
- **`?` and `*` are wildcards** in search text (inside a word; `?` also at the
  end of a one-word search), and the stemmed `.search` filters reject
  wildcards with HTTP 400 (searching page), so `filter_value()` turns both
  into spaces. A `?` ending a multi-word title, a 400 on 2026-09-27, was
  harmless on 2026-10-31 (`Does Head Start Make a Difference?`: HTTP 200, 4
  works, the same as without the `?`).
- **Boolean-heavy lane, live** (2026-10-31, keyed, `free` tier): three
  keyword searches with 6–7 upper-case `OR`s and one with exactly 5, started
  together as four processes. The gate booked the boolean lane 0.22 s apart
  (markers +0.325, +0.545, +0.765 s) and the 5-operator search on the main
  lane only. The third boolean-heavy request was retried once (`attempts`
  2) and then answered HTTP 200. The tool did not yet log a retried attempt's
  status (it does since 1.6.2: `retried_attempts`). The retry slot came about 0.9 s after its first send, sooner
  than the tool's own backoff (1.6–2.4 s), so the server most likely sent a
  sub-second `Retry-After`, as with a per-second 429 (inference; n = 1).
  Details: `api-notes.md` § "Measured behavior: OpenAlex rate tier, live
  boolean lane, commas (2026-10-31)".
- **Semantic-search filters** (re-measured 2026-10-02): `has_content.grobid_xml`
  is rejected with HTTP 400 ("not supported with semantic search", listing the
  supported set: author.id, authorships.*, funders.id, has_abstract,
  has_fulltext, institution ids, is_oa, is_retracted, language,
  open_access.is_oa, primary_location.license, primary_location.source.id,
  publication_year, type); `is_oa:true` is accepted. The docs' "Most filters
  and the `select` parameter work as usual" is therefore too generous; their two named exclusions
  (`cited_by_count`, country codes) are not the only ones.
- **Relevance score on semantic search** (re-measured 2026-10-02): returned
  when requested in `select` (`--with-score`; scores 0.89–0.90 for the top 3 of
  a tutoring query). The 2026-09-27 "no score" observation reflected a select
  list without `relevance_score`.
- **`corpus=`** (measured 2026-10-02): `"high-dosage tutoring"` keyword search
  matched 47 works with `corpus=core` and 70 with `corpus=all`.
- **Open year ranges** need comparisons (`publication_year:>2014`).
- **Type negation** `type:!dataset,type:!paratext` works in both modes;
  without it ICPSR "Code for: …" deposits took 4 of the top 6 `similar` slots.
- **Versions:** NBER working papers and journal versions are separate works
  (3–4 records per paper is common); the core's `fuse()` merges them.
- **Abstract coverage:** about 75% in Education (subfield 3304), 2015–2025;
  abstracts arrive as an inverted index (`reconstruct_abstract()`).
- **`group_by=has_abstract`** returned a false 0 in testing; use filter counts.
- **OA `version`** is reported as OpenAlex holds it (a PLOS article came back
  `submittedVersion`, 2026-10-02) — treat it as metadata, not ground truth.

## Storage and ToS

Data is CC0 ("no 'personal use only' carve-out"); raw JSON may be stored and
shared. Cached PDFs/TEI keep the original copyright ("OpenAlex does not grant
any additional rights") — check the license per work. Requested citation:
Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of
scholarly works, authors, venues, institutions, and concepts. arXiv:2205.01833.
`LICENSE_CLASS = "open"`.

## Exit mapping

401/403 → 11 (check the key); 404 → 11 (`work`/`verify` record NOT FOUND);
400 → 11 (bad filter — the message names the supported filters); 429 after
retries → 11 (daily budget, or the per-second limit: 10/30/50 req/s by key
tier, lower for searches with more than 5 boolean operators; the gate spaces
this container's requests under the limits of its rate tier, so a
per-second 429 most likely means other traffic on the same key or IP, an
`OPENALEX_RATE_TIER` above the key's real plan, an operator count the gate
missed, or a server-side window stricter than even spacing, which the docs
do not describe);
gate queue too long → 12; network
→ 4; timeout → 6.

## Minimal smoke test

```
bash /daaf/scripts/scholar_search.sh verify 10.1093/qje/qjv036 {PROJECT_DIR}/lit_search --title "The Effects of School Spending on Educational and Economic Outcomes: Evidence from School Finance Reforms" --author Jackson --year 2016   # free; expect CONFIDENT
bash /daaf/scripts/scholar_search.sh openalex '"high-dosage tutoring"' {PROJECT_DIR}/lit_search --limit 2   # $0.001
```
