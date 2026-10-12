# =============================================================================
# scholar_backends - adapter registry for scripts/scholar_search.py
# =============================================================================
#
# Part of the scholar_search STANDALONE argparse CLI (CLAUDE.md § Code Style
# exception). One module per backend; this registry is the only list the core
# reads, so adding a backend = add a module + one entry in ADAPTERS (see
# .claude/skills/scholarly-search/references/adding-a-backend.md and
# _BACKEND_TEMPLATE.md).
#
# ADAPTER CONTRACT (validated at import by assert_valid() -> exit 1, and by
# the unit tests):
#   NAME, LABEL            str; NAME is the CLI/MANIFEST identifier (unique)
#   KEY_ENV                env var holding the key, or None (keyless); unique
#                          across adapters when not None
#   REQUIRED_KEY           bool; True -> missing key = exit 10 for that backend
#   LICENSE_CLASS          "open" | "cc-by-nc" | "restricted" (restricted
#                          artifacts are routed to DEST/restricted/ by the core)
#   RATE_LIMIT             {lane: min seconds between requests | None}; feeds
#                          the core's shared RateGate. Lane names are unique
#                          across adapters (a lane is one key's/IP's budget)
#   RATE_LIMIT_NOTE, COST_NOTE, ATTRIBUTION, GET_KEY_URL   str (docs/`backends`)
#   CAPABILITIES           frozenset subset of _common.CAPABILITY_VOCAB
#   DEFAULT_IN_FIND        bool; included in `find` when --backends is omitted
#   key_present(), auth_headers(), degraded_note(), parse_cost(headers)
#   to_record(native)      native JSON -> common record schema (_common.record)
#   FIND_LEGS + find_legs(http, a, keywords, ctx)   required when "search" in
#                          CAPABILITIES; FIND_LEGS names every ranked list
#                          find_legs() returns. Leg names are unique across
#                          adapters and feed `find --skip` choices
#   oa_locate(...)         when "oa_locate" (signature per backend; see core)
#   retraction_check(http, doi)        required when "retraction"
#   ID_KEY (optional)      the key this adapter uses in a record's `ids` map,
#                          when it differs from NAME (semantic_scholar: "s2");
#                          lets the core label IDs without naming backends
#
# Adapters NEVER write files and NEVER touch provenance: requests go through
# the core's Http object, which logs them, gates them, and applies the secret
# guard; the core writes every artifact and MANIFEST row. The exceptions an
# adapter may raise, and the exit code each maps to, are listed in
# references/adding-a-backend.md § "What an adapter may raise".
#
#   RETRY_POLICY (optional) {"penalize_429_s": seconds}: a 429 is never
#                          retried; the lane is paused that long for every
#                          process and the call fails "busy" (exit 12). For
#                          backends whose 429 is a timed block (Elicit).
#
# S2: Scite registered 2026-10-11 (keyless tallies + retraction notices,
# license_class "restricted"); Elicit registered 2026-10-11 (keyed search,
# usage and async reports, license_class "restricted", RETRY_POLICY 300 s,
# opt-in to `find` only). Any adapter declaring "retraction" joins
# `retractions` automatically.
# =============================================================================

import sys

from . import crossref, elicit, eric, openalex, scite, semantic_scholar, unpaywall
from ._common import CAPABILITY_VOCAB, LICENSE_ORDER

# Registration order is display order (`backends`, `--backends` help).
ADAPTERS = (openalex, semantic_scholar, eric, crossref, unpaywall, scite, elicit)
RETRY_POLICY_KEYS = frozenset({"penalize_429_s"})

REQUIRED_ATTRS = ("NAME", "LABEL", "KEY_ENV", "REQUIRED_KEY", "LICENSE_CLASS", "RATE_LIMIT",
                  "RATE_LIMIT_NOTE", "CAPABILITIES", "DEFAULT_IN_FIND", "COST_NOTE", "ATTRIBUTION",
                  "key_present", "auth_headers", "degraded_note", "parse_cost", "to_record")
CAPABILITY_FUNCS = {"search": "find_legs", "retraction": "retraction_check"}


def validate_adapter(mod, others=()):
    # Returns a list of contract violations (empty = valid). `others` are the
    # adapters registered before this one; the uniqueness checks compare
    # against them, because BACKENDS is keyed by NAME and a duplicate would
    # otherwise silently replace an adapter.
    problems = [f"missing {a}" for a in REQUIRED_ATTRS if not hasattr(mod, a)]
    if problems:
        return problems
    if mod.LICENSE_CLASS not in LICENSE_ORDER:
        problems.append(f"LICENSE_CLASS {mod.LICENSE_CLASS!r} not in {sorted(LICENSE_ORDER)}")
    extra = set(mod.CAPABILITIES) - CAPABILITY_VOCAB
    if extra:
        problems.append(f"unknown capabilities {sorted(extra)}")
    for cap, fn in CAPABILITY_FUNCS.items():
        if cap in mod.CAPABILITIES and not hasattr(mod, fn):
            problems.append(f"capability {cap!r} needs {fn}()")
    if "oa_locate" in mod.CAPABILITIES and not (hasattr(mod, "oa_locate") or hasattr(mod, "oa_locate_by_title")):
        problems.append("capability 'oa_locate' needs oa_locate() or oa_locate_by_title()")
    if mod.REQUIRED_KEY and not mod.KEY_ENV:
        problems.append("REQUIRED_KEY is True but KEY_ENV is None")
    if not isinstance(mod.RATE_LIMIT, dict):
        problems.append("RATE_LIMIT must be a {lane: seconds|None} dict")
    policy = getattr(mod, "RETRY_POLICY", None)
    if policy is not None:
        if not isinstance(policy, dict) or set(policy) - RETRY_POLICY_KEYS:
            problems.append(f"RETRY_POLICY must be a dict with keys from {sorted(RETRY_POLICY_KEYS)}")
        elif not all(isinstance(v, (int, float)) and v > 0 for v in policy.values()):
            problems.append("RETRY_POLICY values must be positive seconds")
    legs = getattr(mod, "FIND_LEGS", None)
    if "search" in mod.CAPABILITIES:
        if not (isinstance(legs, tuple) and legs and all(isinstance(x, str) and x for x in legs)):
            problems.append("capability 'search' needs FIND_LEGS, a non-empty tuple of leg names")
            legs = None
    # INTENT: cross-adapter uniqueness. A shared NAME would overwrite an
    #   adapter in BACKENDS; a shared KEY_ENV would make two backends report
    #   one key; a shared rate lane would merge two independent rate budgets
    #   into one gate file; a shared leg name would make `find` overwrite one
    #   backend's ranked list with another's and make `--skip` ambiguous.
    for other in others:
        if other is mod:
            continue
        if getattr(other, "NAME", None) == mod.NAME:
            problems.append(f"NAME {mod.NAME!r} already registered")
        if mod.KEY_ENV and getattr(other, "KEY_ENV", None) == mod.KEY_ENV:
            problems.append(f"KEY_ENV {mod.KEY_ENV!r} already used by {other.NAME!r}")
        if isinstance(mod.RATE_LIMIT, dict) and isinstance(getattr(other, "RATE_LIMIT", None), dict):
            shared = sorted(set(mod.RATE_LIMIT) & set(other.RATE_LIMIT))
            if shared:
                problems.append(f"rate lane(s) {shared} already used by {other.NAME!r}")
        mine = set(legs or ()) | {mod.NAME}
        theirs = set(getattr(other, "FIND_LEGS", None) or ()) | {getattr(other, "NAME", None)}
        same_name = {mod.NAME} if getattr(other, "NAME", None) == mod.NAME else set()
        clash = sorted((mine & theirs) - same_name)   # a shared NAME is reported above
        if clash:
            problems.append(f"FIND_LEGS {clash} collide with {other.NAME!r}")
    return problems


def validate_registry(adapters):
    # Returns ["<name>: <problem>", …] for every adapter, in order.
    out = []
    for i, mod in enumerate(adapters):
        label = getattr(mod, "NAME", None) or getattr(mod, "__name__", "?")
        out += [f"{label}: {p}" for p in validate_adapter(mod, adapters[:i])]
    return out


def assert_valid(adapters):
    # INTENT: a broken adapter is a hard error at import, before any request
    #   is built or any artifact written: stderr names every violation, exit 1
    #   (the usage-error code; nothing ran).
    problems = validate_registry(adapters)
    if problems:
        sys.stderr.write("scholar_search: EXIT 1: invalid backend adapter registry:\n"
                         + "".join(f"  - {p}\n" for p in problems))
        raise SystemExit(1)


assert_valid(ADAPTERS)
BACKENDS = {m.NAME: m for m in ADAPTERS}


def gate_intervals():
    # Merged {lane: seconds} for every gated lane across all adapters.
    out = {}
    for mod in BACKENDS.values():
        for lane, interval in mod.RATE_LIMIT.items():
            if interval:
                out[lane] = float(interval)
    return out


def with_capability(cap):
    return [m for m in BACKENDS.values() if cap in m.CAPABILITIES]


def find_skip_choices():
    # `find --skip` accepts a search backend's NAME (all its legs) or one leg
    # from its FIND_LEGS, in registration order:
    # openalex, openalex_semantic, openalex_keyword, semantic_scholar, eric, crossref, elicit.
    out = []
    for m in with_capability("search"):
        out += [m.NAME] + [leg for leg in m.FIND_LEGS if leg != m.NAME]
    return list(dict.fromkeys(out))


def id_labels():
    # {ids-map key: display label}, e.g. {"openalex": "OpenAlex", "s2": "Semantic Scholar"}.
    return {getattr(m, "ID_KEY", m.NAME): m.LABEL for m in BACKENDS.values()}


def most_restrictive(classes):
    classes = [c for c in classes if c]
    return max(classes, key=lambda c: LICENSE_ORDER.get(c, 0)) if classes else "open"
