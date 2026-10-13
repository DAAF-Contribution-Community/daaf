"""Route detection, model-family classification, and env-coherence checks for
the DAAF deployment smoke-testing suite.

This is the foundational layer of the suite. It defines the shared result
vocabulary (Verdict, Evidence, ProbeResult) used by every tier and the pure,
no-LLM inspection logic that reads the *live* environment to determine which of
DAAF's five install routes is active — exactly as the user configured it.

The five routes (auto-detected from the live env, presence-only — no credential
value is ever read beyond empty-vs-set; smoke v2 design 2026-10-13 §2):

    DAAF_PROVIDER_SHIM=openai + SHIM_BACKEND_MODE=chatgpt  -> chatgpt-subscription
    DAAF_PROVIDER_SHIM=openai + SHIM_BACKEND_MODE=openai   -> openai-api
    ANTHROPIC_BASE_URL contains "openrouter.ai"            -> openrouter
    else, ANTHROPIC_API_KEY set (non-empty)                -> anthropic-api
    else                                                   -> anthropic-subscription

Env alone cannot tell an interactive Console login from a subscription login,
so Tier 1 confirms the credential from the stream-json init record (T1.8).

This module makes NO subprocess calls and NO LLM calls — it is pure environment
inspection so Tier 0 preflight can run for free. Its one file access is a
read-only text read of the installed enforce-model-ceiling.sh (T0.2 checks which
rule set that hook carries). It is framework tooling (like
benchmarks/), so it uses normal engineering style with functions, NOT the
sequential no-functions research-script style that CLAUDE.md mandates for
pipeline analysis scripts.

Dependency position: this module imports nothing from the rest of the suite, so
the internal import DAG is route_detection <- smoke_probes <- run_deploy_smoke.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


# --- Verdict vocabulary ---------------------------------------------------

class Verdict:
    """Per-probe verdicts. Deliberately a small string-constant holder rather
    than an Enum so the values serialize verbatim into report.json and read
    cleanly in report.md."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    WARN = "WARN"
    INFO = "INFO"

    # Verdicts that make the overall run fail (nonzero exit), matching the
    # run_all_smoke_tests.sh contract: any FAIL fails the run. WARN/SKIP/INFO
    # do not, so a route-appropriate SKIP (e.g. shim /health on a non-shim
    # route) or a tolerant WARN never breaks the exit code.
    FAILING = frozenset({FAIL})


# --- Install route constants ----------------------------------------------

ROUTE_ANTHROPIC = "anthropic-subscription"
ROUTE_ANTHROPIC_SUBSCRIPTION = ROUTE_ANTHROPIC   # explicit alias; ROUTE_ANTHROPIC kept for callers
ROUTE_ANTHROPIC_API = "anthropic-api"
ROUTE_OPENROUTER = "openrouter"
ROUTE_OPENAI_API = "openai-api"
ROUTE_CHATGPT = "chatgpt-subscription"

# Five routes, in the design's table order (smoke v2 §2). run_deploy_smoke uses
# this as the --route choice list.
ALL_ROUTES = (ROUTE_ANTHROPIC, ROUTE_ANTHROPIC_API, ROUTE_CHATGPT, ROUTE_OPENAI_API,
              ROUTE_OPENROUTER)

# The two native-Anthropic routes: same endpoint and model family, different
# credential (subscription login/OAuth token vs Console API key).
ANTHROPIC_ROUTES = frozenset({ROUTE_ANTHROPIC, ROUTE_ANTHROPIC_API})

# Routes that place the provider shim in the request path. For these, shim
# /health is a required Tier 0 probe and per-run env overlays (--profiles)
# cannot change daemon-level state (SHIM_SANITIZE_TOOLS, backend_mode).
SHIM_ROUTES = frozenset({ROUTE_OPENAI_API, ROUTE_CHATGPT})

# Every selector that can make Claude Code itself, a dispatched subagent, or a
# housekeeping call run a mapped (possibly GPT) model. T0.4 inspects all
# seven rather than treating ANTHROPIC_MODEL as a proxy for the effective model
# surface:
#   * ANTHROPIC_MODEL — hard session-start selector (outranks a saved `model`).
#   * ANTHROPIC_DEFAULT_MODEL — soft session-start default (Claude Code 2.1.236+),
#     applied only when no --model, ANTHROPIC_MODEL or settings `model` key
#     selects one; DAAF's shipped settings.json sets it.
#   * ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU,FABLE}_MODEL — what each tier alias
#     resolves to. HAIKU also drives Claude Code's housekeeping calls (naming
#     and summarizing the session); FABLE is the fable alias + Fable recognition.
#   * CLAUDE_CODE_SUBAGENT_MODEL — since Claude Code 2.1.251 only a FALLBACK for
#     subagents without their own model (every DAAF agent sets `model:`); it is
#     forced onto every subagent only with CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1.
MODEL_SELECTOR_VARS = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_FABLE_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
)

# ANTHROPIC_DEFAULT_MODEL values Claude Code ignores (model-config docs,
# fetched 2026-10-12): the session then starts on the account-type default.
# Compared case-insensitively, the same convention as _resolve_tier_alias (the
# docs do not say whether these values are case-sensitive).
_IGNORED_DEFAULT_MODEL_VALUES = frozenset({"default", "inherit", "opusplan", "haiku"})


def _subagent_force_enabled(env) -> bool:
    """CLAUDE_CODE_SUBAGENT_MODEL_FORCE (Claude Code 2.1.257+) is documented as
    "Set to 1". '1' and case-insensitive 'true' count as enabled, matching
    enforce-model-ceiling.sh rule (a) (hook updated and installed 2026-10-12);
    anything else is off."""
    value = env.get("CLAUDE_CODE_SUBAGENT_MODEL_FORCE")
    return isinstance(value, str) and (value == "1" or value.lower() == "true")


def _effective_default_model(env) -> str:
    """ANTHROPIC_DEFAULT_MODEL as Claude Code would honor it ('' when unset or
    set to a value Claude Code ignores)."""
    value = env.get("ANTHROPIC_DEFAULT_MODEL")
    if (not isinstance(value, str) or not value
            or value.lower() in _IGNORED_DEFAULT_MODEL_VALUES):
        return ""
    return value


# Substrings that mark a model name as Claude-family: the four tier names that
# enforce-model-ceiling.sh's rank_of() substring-matches (haiku, sonnet, opus,
# fable), plus claude and mythos.
_CLAUDE_FAMILY_KEYWORDS = ("claude", "opus", "sonnet", "haiku", "fable", "mythos")

# Sentinel for "a tier alias with no ANTHROPIC_DEFAULT_<ALIAS>_MODEL mapping":
# Claude Code then uses its built-in Claude model for that tier.
_BUILTIN_CLAUDE = "claude"


def _resolve_tier_alias(value, env) -> str:
    """Resolve a selector that may be a tier alias the way Claude Code would.

    "opus" / "sonnet" / "haiku" / "fable" (and "<alias>[1m]") resolve through
    their own ANTHROPIC_DEFAULT_<ALIAS>_MODEL mapping: the mapped slug when set,
    else _BUILTIN_CLAUDE (Claude Code's built-in Claude model for the tier). Any
    other value is returned unchanged ('' for unset/non-string values).

    Case handling: the alias match is case-insensitive ("Opus" resolves like
    "opus"). Claude Code's model-configuration docs (fetched 2026-10-12) do not
    say whether aliases are case-sensitive, so this is a chosen convention, not a
    documented fact. It is the safe direction for T0.4: read case-sensitively,
    "Opus" would count as a Claude name by keyword and could mask a non-Claude
    OPUS mapping that needs a context-window declaration.
    """
    if not isinstance(value, str) or not value:
        return ""
    alias = value[:-len("[1m]")] if value.lower().endswith("[1m]") else value
    alias = alias.lower()
    if alias in _MAIN_ALIASES:
        mapped = env.get(_MAIN_ALIASES[alias], "")
        return mapped if isinstance(mapped, str) and mapped else _BUILTIN_CLAUDE
    return value


def _is_claude_family_name(model) -> bool:
    """Keyword test on one (already resolved) model name."""
    text = (model or "").lower()
    return any(k in text for k in _CLAUDE_FAMILY_KEYWORDS)


# Selector values that name no model on their own, so they are skipped rather
# than classified as text (docs fetched 2026-10-12):
#   * "inherit" — environment-variables docs, CLAUDE_CODE_SUBAGENT_MODEL:
#     "Setting it to inherit is the same as leaving it unset."
#   * "default" — model-configuration docs, "default model setting": it
#     resolves to an organization default, an honored ANTHROPIC_DEFAULT_MODEL,
#     the model recorded on the account, or the account-type default (a Claude
#     model on every listed account type). The env-visible parts of that chain
#     are inspected as selectors of their own.
# The docs do not say what "inherit" means in ANTHROPIC_MODEL, or "default" in
# CLAUDE_CODE_SUBAGENT_MODEL; skipping them there too is inference, chosen as
# the non-failing direction for T0.4.
_NO_MODEL_SELECTOR_VALUES = frozenset({"inherit", "default"})

# Selector aliases that stand for one or more tier aliases:
#   * "opusplan" — environment-variables docs: ANTHROPIC_DEFAULT_OPUS_MODEL is
#     the model "that opusplan uses while Plan Mode is active", and
#     ANTHROPIC_DEFAULT_SONNET_MODEL the one it uses "when Plan Mode is not
#     active". Both mappings therefore apply.
#   * "best" — model-configuration docs: "...except in Claude apps gateway
#     sessions, where fable and best resolve to Fable 5." That is the docs' only
#     mention of best. Resolving it through the FABLE mapping in other sessions
#     is inference; it cannot add a T0.4 failure, because the FABLE mapping is
#     inspected as a selector of its own.
_COMPOUND_ALIASES = {"opusplan": ("opus", "sonnet"), "best": ("fable",)}


def _expand_selector(value, env) -> tuple:
    """Resolve one alias-capable selector value to the model names it can run.

    Returns () for unset values and for _NO_MODEL_SELECTOR_VALUES, one name per
    tier alias for _COMPOUND_ALIASES, and otherwise the single
    _resolve_tier_alias result. Matching is case-insensitive and ignores a
    trailing "[1m]", the same convention as _resolve_tier_alias."""
    if not isinstance(value, str) or not value:
        return ()
    alias = value[:-len("[1m]")] if value.lower().endswith("[1m]") else value
    alias = alias.lower()
    if alias in _NO_MODEL_SELECTOR_VALUES:
        return ()
    if alias in _COMPOUND_ALIASES:
        return tuple(_resolve_tier_alias(tier, env) for tier in _COMPOUND_ALIASES[alias])
    return (_resolve_tier_alias(value, env),)


def _resolved_selectors(env) -> list:
    """(name, raw, resolved) for every set MODEL_SELECTOR_VARS entry.

    ANTHROPIC_MODEL, an honored ANTHROPIC_DEFAULT_MODEL and
    CLAUDE_CODE_SUBAGENT_MODEL can name an alias, so they are expanded through
    _expand_selector: "inherit"/"default" yield no entry, "opusplan" yields one
    entry per tier it uses, and a tier alias resolves through its mapping. The
    four ANTHROPIC_DEFAULT_<ALIAS>_MODEL mappings are taken as written (they are
    the alias targets)."""
    out = []
    for name in MODEL_SELECTOR_VARS:
        if name == "ANTHROPIC_DEFAULT_MODEL":
            raw = _effective_default_model(env)
        else:
            raw = env.get(name, "")
            raw = raw if isinstance(raw, str) else ""
        if not raw:
            continue
        if name in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
            for resolved in _expand_selector(raw, env):
                out.append((name, raw, resolved))
        else:
            out.append((name, raw, raw))
    return out


# The installed ceiling hook. T0.2 reads it (read-only) to tell the 2026-10-12
# rule set (stands down only for CLAUDE_CODE_SUBAGENT_MODEL_FORCE or an
# OPUS/SONNET remap) from an older install (stands down whenever
# CLAUDE_CODE_SUBAGENT_MODEL is set, and does not know the force flag).
CEILING_HOOK_PATH = (Path(__file__).resolve().parents[2]
                     / ".claude" / "hooks" / "enforce-model-ceiling.sh")
_FORCE_MARKER = "SUBAGENT_MODEL_FORCE"


def _ceiling_hook_recognizes_force(hook_path):
    """True when the hook text mentions CLAUDE_CODE_SUBAGENT_MODEL_FORCE (the
    2026-10-12 rule set), False when it does not (an older hook), None when the
    file cannot be read. Text inspection only; the hook is never executed."""
    try:
        text = Path(hook_path).read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError, ValueError):
        return None
    return _FORCE_MARKER in text

_MAX_SIGNED_64 = 9223372036854775807
_CANONICAL_POSITIVE_DECIMAL_RE = re.compile(r"^[1-9][0-9]*$")

# Closed-set GPT flagship grammar. The pattern text is byte-identical to
# GPT_FLAGSHIP_RE in .claude/hooks/context-reporter.sh and gpt_flagship_re in
# .claude/scripts/subagent-bar.sh and .claude/scripts/context-bar.sh; a lockstep
# test in tests/python/test_deploy_smoke.py compares them. Apply it with
# fullmatch (see _gpt_physical_window). The GPT-6 Sol/Luna and flagship -pro
# members come from a USER POLICY DECISION of 2026-09-29, and the GPT-6.1 Sol
# member (one exact alternative, no gpt-6.1-* wildcard) from one of 2026-10-12;
# neither is a validation.
_GPT_FLAGSHIP_RE = re.compile(
    r"^(gpt-5\.(4|5|6)(-(sol|terra|luna))?|gpt-6-(astra|sol|luna)|gpt-6\.1-sol)(-pro)?(\[1m\])?$"
)


# --- Shared result types --------------------------------------------------

@dataclass
class Evidence:
    """One quoted piece of evidence backing a probe verdict.

    Evidence-graded reporting is the whole point of this suite: every claim in
    the report is either an observed fact (a command was run and its output is
    quoted here) or explicitly labeled inference (command left empty, note
    carries the reasoning).
    """

    command: str            # the literal command / probe that was run ("" for inference)
    output: str = ""        # the relevant captured output (stdout/stderr/value)
    note: str = ""          # interpretation or, for inference, the reasoning
    is_inference: bool = False  # True only when the note is genuinely inferential
                                # (no command was run); observed interpretation of a
                                # captured value stays False so the report does not
                                # mislabel an observed note as inference.

    def to_dict(self) -> dict:
        return {"command": self.command, "output": self.output,
                "note": self.note, "is_inference": self.is_inference}


@dataclass
class ProbeResult:
    """The verdict for a single smoke probe, with its supporting evidence."""

    probe_id: str           # e.g. "T0.6", "T1.3", "T2.1"
    name: str               # short human title
    tier: str               # "0", "1", "2", "D"
    verdict: str = Verdict.INFO
    detail: str = ""        # one-line summary of the finding
    evidence: list = field(default_factory=list)   # list[Evidence]
    profile: str = ""       # profile name this result belongs to ("" = tier-once)
    # smoke v2 §13 contract fields (all optional; readers use getattr defaults):
    duration_s: float = None                       # wall time of the probe, when measured
    session_ids: list = field(default_factory=list)  # claude -p session ids this probe ran
    cost_usd: float = None                         # CLI-reported cost of this probe's run(s)
    hint: str = ""          # static remediation text (FAIL/WARN only; "" when none)

    def add_evidence(self, command: str, output: str = "", note: str = "",
                     is_inference: bool = False) -> None:
        # Cap captured output so a runaway command cannot bloat the report.
        # Full artifacts are snapshotted into the report's evidence/ dir.
        if output and len(output) > 4000:
            output = output[:4000] + "\n...[truncated]..."
        self.evidence.append(Evidence(command=command, output=output, note=note,
                                      is_inference=is_inference))

    def to_dict(self) -> dict:
        return {
            "probe_id": self.probe_id,
            "name": self.name,
            "tier": self.tier,
            "verdict": self.verdict,
            "detail": self.detail,
            "profile": self.profile,
            "evidence": [e.to_dict() for e in self.evidence],
            "duration_s": self.duration_s,
            "session_ids": list(self.session_ids),
            "cost_usd": self.cost_usd,
            "hint": self.hint,
        }


@dataclass
class RouteInfo:
    """The detected configuration surface for this installation."""

    detected_route: str
    asserted_route: str = ""        # from --route, "" if not asserted
    model_family: str = "unknown"   # claude | gpt | glm | unknown
    remap_active: bool = False      # OPUS/SONNET tier remap set, or forced subagent model
    session_model: str = ""         # env start selector: ANTHROPIC_MODEL, else an honored
                                    # ANTHROPIC_DEFAULT_MODEL (T0.14 adds settings `model`)
    route_match: bool = True        # False when asserted_route != detected_route
    shim_control: str = ""         # raw DAAF_PROVIDER_SHIM value (no normalization)
    backend_mode_control: str = "" # raw SHIM_BACKEND_MODE value (no normalization)
    lane_control_issues: tuple = () # exact-value mismatches surfaced by T0.1

    def to_dict(self) -> dict:
        return {
            "detected_route": self.detected_route,
            "asserted_route": self.asserted_route,
            "model_family": self.model_family,
            "remap_active": self.remap_active,
            "session_model": self.session_model,
            "route_match": self.route_match,
            "shim_control": _bounded_lane_control(self.shim_control, ("openai",)),
            "backend_mode_control": _bounded_lane_control(
                self.backend_mode_control, ("chatgpt", "openai")
            ),
            "lane_control_issues": list(self.lane_control_issues),
        }


# --- Secret redaction -----------------------------------------------------

# Any env var whose NAME contains one of these tokens carries a secret VALUE
# that must never be written to a report. Matched case-insensitively.
_SECRET_NAME_RE = re.compile(r"(KEY|TOKEN|SECRET|AUTH)", re.IGNORECASE)

# smoke v2 fingerprint fix: a *_TOKENS variable holding a plain decimal count
# (CLAUDE_CODE_MAX_CONTEXT_TOKENS=919000, a MAX_OUTPUT/THINKING_TOKENS budget)
# is a size, not a credential. Matching the TOKEN name pattern used to redact it
# in the fingerprint and rewrite "919000" anywhere in free text, while T0.4
# printed the same value in the clear — a self-contradicting report. Only an
# all-digit value of at most 20 characters qualifies; anything else stays
# redacted by name.
_NUMERIC_COUNT_RE = re.compile(r"[0-9]{1,20}")


def _is_numeric_token_count(name: str, value) -> bool:
    return (isinstance(name, str) and name.upper().endswith("_TOKENS")
            and isinstance(value, str) and _NUMERIC_COUNT_RE.fullmatch(value) is not None)


# Non-secret controls recorded in the fingerprint with a closed value set, so an
# arbitrary value is classified rather than reflected into the report.
_BOUNDED_FINGERPRINT_VALUES = {
    "SHIM_PDF_MODE": ("file", "omit"),
    "CLAUDE_CODE_AUTO_MODE_SERVER": ("0", "1", "true", "false"),
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
# The same CSI colour codes written as TEXT escapes rather than raw ESC bytes.
# subagent-bar.sh emits one JSON line per task ({"id", "content"}), so jq encodes
# its ESC bytes as the six characters "\u001b"; T0.7 quoted that JSON verbatim and
# the report carried "\u001b[38;5;…m" noise even after raw ESC was stripped.
# Covers \u001b / \u001B, \x1b / \x1B, \033 and \e, each followed by a CSI body.
_ESCAPED_ANSI_RE = re.compile(r"\\(?:u001[bB]|x1[bB]|033|e)\[[0-9;?]*[ -/]*[@-~]")


def strip_ansi(text):
    """Remove ANSI CSI/OSC escape sequences (statusline colour codes) from text
    before it is quoted as evidence; report.md used to carry them raw. Both the
    raw ESC form and the textual escape form (JSON "\\u001b[…m", "\\x1b[", "\\033[",
    "\\e[") are removed."""
    if not text:
        return text
    return _ESCAPED_ANSI_RE.sub("", _ANSI_RE.sub("", text))


def redact_env_value(name: str, value):
    """Return a report-safe rendering of an env var value.

    For secret-named vars the *value* is never emitted, but the empty-vs-set
    distinction IS preserved because it is load-bearing for route coherence
    (e.g. OpenRouter needs ANTHROPIC_API_KEY present-and-empty, not unset).
    """
    if value is None:
        return "<unset>"
    if name == "CLAUDE_CODE_DISABLE_FAST_MODE":
        # This control is intentionally an exact-string contract.  Preserve the
        # useful success fact while bounding every near miss instead of reflecting
        # arbitrary environment text into a report.
        return "1" if value == "1" else "<invalid:not-exact-1>"
    if name == "DAAF_PROVIDER_SHIM":
        return _bounded_lane_control(value, ("openai",))
    if name == "SHIM_BACKEND_MODE":
        return _bounded_lane_control(value, ("chatgpt", "openai"))
    if name in _BOUNDED_FINGERPRINT_VALUES:
        return _bounded_lane_control(value, _BOUNDED_FINGERPRINT_VALUES[name])
    if _is_numeric_token_count(name, value):
        return value
    if _SECRET_NAME_RE.search(name):
        return "<redacted:empty>" if value == "" else "<redacted:set>"
    return value


def scrub_secret_values(text, env=None):
    """Scrub any secret env VALUE that appears verbatim inside free text before it
    enters a report.

    redact_env_value() redacts by var NAME for the structured fingerprint; this
    complements it for UNstructured channels (CLI stderr captured into
    result.error, a shim /health JSON dump) where a secret could appear as a bare
    substring the fingerprint machinery never sees. Any env var whose NAME matches
    KEY/TOKEN/SECRET/AUTH and whose value is a non-trivial string (>=6 chars, to
    avoid over-matching empty or flag-like values) has its value replaced by a
    <redacted:NAME> marker. The replacement introduces no quotes, so a scrubbed
    JSON blob remains parseable.
    """
    if not text:
        return text
    if env is None:
        import os
        env = os.environ
    scrubbed = text
    for name, value in env.items():
        if not value or len(value) < 6:
            continue
        if _is_numeric_token_count(name, value):
            continue
        if _SECRET_NAME_RE.search(name):
            scrubbed = scrubbed.replace(value, f"<redacted:{name}>")
    return scrubbed


# Curated set of route-relevant vars captured in the report env fingerprint.
# Every one is rendered through redact_env_value, so listing a secret-named var
# here is safe — only its presence/emptiness leaks, never its value.
FINGERPRINT_VARS = (
    "DAAF_DEV",
    "DAAF_PROVIDER_SHIM",
    "SHIM_BACKEND_MODE",
    "SHIM_SANITIZE_TOOLS",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_FABLE_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL_FORCE",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
    "CLAUDE_CODE_EFFORT_LEVEL",
    "CLAUDE_CODE_DISABLE_FAST_MODE",
    "CODEX_HOME",
    # smoke v2: PDF handling mode of the shim (file|omit) and the Auto-mode
    # server opt-out (F12); both bounded to a closed value set.
    "SHIM_PDF_MODE",
    "CLAUDE_CODE_AUTO_MODE_SERVER",
    # Secret-bearing (values redacted by name match; empty/set state preserved):
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    # DAAFBench-convention OpenRouter vars: the benchmark harness reads these
    # (model_loader.py), but a LIVE OpenRouter install wires ANTHROPIC_* directly
    # (base URL + AUTH_TOKEN per the provider-surface preliminary notes), so these
    # are normally <unset> in situ. Kept in the fingerprint because an
    # UNEXPECTEDLY-set value is a useful misconfig signal; redacted-by-name, so
    # only presence/emptiness ever shows — never the value.
    "OPENROUTER_BASE_URL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_AUTH_TOKEN",
    "OPENAI_API_KEY",
    "SHIM_BACKEND_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
)


def env_fingerprint(env) -> dict:
    """Build a redacted, ordered fingerprint of route-relevant env vars.

    Every FINGERPRINT_VARS entry is recorded (even when unset) so the
    empty-vs-unset distinction is always visible in the report.
    """
    fp = {}
    for name in FINGERPRINT_VARS:
        present = name in env
        fp[name] = redact_env_value(name, env.get(name)) if present else "<unset>"
    return fp


def _key_state(env, name: str) -> str:
    """Classify an env var as 'unset', 'empty', or 'set' — without emitting its
    value. The OpenRouter route hinges on this distinction for ANTHROPIC_API_KEY."""
    if name not in env:
        return "unset"
    return "empty" if env.get(name) == "" else "set"


# --- Route + family detection ---------------------------------------------

def _is_canonical_positive_decimal(value) -> bool:
    """Mirror the hardened Bash consumers' arithmetic-input contract.

    Only canonical positive base-10 text within signed 64-bit range is accepted.
    No normalization is performed: whitespace, signs, leading zeroes, decimal or
    exponent notation, empty values, and overflow all remain invalid.
    """
    if value is None:
        return False
    text = value if isinstance(value, str) else str(value)
    if not _CANONICAL_POSITIVE_DECIMAL_RE.fullmatch(text):
        return False
    max_text = str(_MAX_SIGNED_64)
    return len(text) < len(max_text) or (
        len(text) == len(max_text) and text <= max_text
    )


def _gpt_physical_window(model_id: str):
    """Return the runtime static-map window for a supported GPT identifier.

    Physical-family matching is deliberately separate from the runtime's GPT
    quality-tier grammar (GPT_EXTENDED_RE / gpt_extended_re in the Bash
    consumers); this module implements no quality-tier matching. It operates on
    the terminal provider-stripped slug. The gpt-5.4/5.5/5.6 arm requires a
    supported version at the left boundary and accepts end-of-slug, '-' or '['
    as the version boundary, so mini and chat variants keep their established
    smaller mappings. The GPT-6 flagships are matched by the closed-set flagship
    grammar _GPT_FLAGSHIP_RE, byte-identical to the Bash consumers' flagship
    ERE.
    """
    slug = (model_id or "").rsplit("/", 1)[-1]
    if re.match(r"^gpt-5\.(?:4|5|6)(?:$|[-\[])", slug):
        if "-mini" in slug:
            return 400000
        if "-chat" in slug:
            return 128000
        return 1050000
    # GPT-6 flagships: gpt-6-astra, gpt-6-sol, gpt-6-luna and gpt-6.1-sol, each
    # optionally followed by '-pro' and then '[1m]', are 1,050,000-token models
    # (gpt-6.1-sol per OpenRouter openai/gpt-6.1-sol, fetched 2026-10-12). They are
    # matched by the closed-set flagship grammar shared verbatim with
    # context-reporter.sh (GPT_FLAGSHIP_RE), subagent-bar.sh and context-bar.sh
    # (gpt_flagship_re); the grammar is used unmodified so the lockstep test can
    # compare it byte for byte. re.fullmatch reproduces the POSIX '$' (end of
    # string only) semantics of Bash '=~', so a trailing newline does not match.
    # One deliberate difference from the Bash consumers: everything from the
    # first '#' onward is removed before matching, as the provider shim does
    # (anthropic_openai_shim.py, model.partition("#")). Env selectors may carry
    # the shim's documented reasoning-effort suffix (e.g. 'gpt-6-astra[1m]#xhigh';
    # user_reference/01_installation_and_quickstart.md, 07_faq_technical.md), and
    # keeping it would drop the exact-ChatGPT-lane 919000 check below for those
    # configs without any warning. Side effect: effort-suffixed gpt-5.4/5.5/5.6
    # ids that the arm above rejects at the version boundary (e.g. 'gpt-5.6#high')
    # now reach this check and map to 1050000, which over-applies the cap (the
    # safe direction). The shim echoes the stripped id in its responses, so
    # context-reporter.sh (response .message.model) never sees the suffix;
    # whether context-bar.sh's requested .model.id can carry it is unverified.
    # Near misses fall through to None: bare 'gpt-6', 'gpt-6-terra' (retired),
    # GPT-6 mini/chat ('gpt-6-sol-mini', 'gpt-6-sol-chat'), right-boundary text
    # ('gpt-6-astra-pro-x', 'gpt-6-sol-pro[1m]x', 'gpt-6-astra[1m]x',
    # 'gpt-6-sol[1m]-pro') and left-boundary text ('xgpt-6-sol').
    # Returning the flagship window makes these ids take part in the exact-
    # ChatGPT-lane 919000 ceiling (keyed on window == 1050000 below). That
    # subscription-lane cap is MEASURED only for Astra and Sol as of 2026-09-05:
    # gpt-6-astra accepted 919,053 and rejected 922,552, and gpt-5.6-sol accepted
    # 910,827 and rejected 921,973 (previously 370,000, set 2026-07-16 and now
    # stale). gpt-6-sol, gpt-6-luna and the flagship '-pro' forms are covered by
    # USER POLICY DECISION 2026-09-29, not validation (session workspace
    # research/2026-09-29_FrameworkDev_OpenRouterDottedModelNames). Under that
    # decision gpt-6-sol reads as gpt-5.6-sol, gpt-6-luna reads as gpt-5.6-luna,
    # and every flagship '-pro' reads as its non-pro base. Their 1,050,000 window
    # matches the OpenRouter catalogue fetched 2026-09-29. Their 919000 lane cap
    # is INFERRED from the Sol/Astra measurements, not measured. gpt-6.1-sol
    # (USER POLICY DECISION 2026-10-12) reads as gpt-6-sol on the same terms;
    # its ChatGPT-lane ceiling was MEASURED 2026-10-13 (accepted 919,744, rejected
    # 921,973; probe_context_ceiling.py), matching the 919000 lane cap.
    if _GPT_FLAGSHIP_RE.fullmatch(slug.split("#", 1)[0]):
        return 1050000
    if re.match(r"^gpt-5(?:$|[-\[])|^gpt-5\.2(?:$|[-\[])", slug):
        if "-chat" in slug:
            return 128000
        return 400000
    return None


def _has_supported_1m_hint(model_id: str) -> bool:
    """Recognize the direct-shim [1m] hint, including a following effort suffix."""
    slug = (model_id or "").rsplit("/", 1)[-1]
    return bool(re.search(r"\[1m\](?:#[^/]*)?$", slug))


def _bounded_lane_control(value: str, exact_values: tuple) -> str:
    """Classify a lane control without reflecting arbitrary environment text."""
    if value in exact_values:
        return value
    if not value:
        return ""
    if value.strip().lower() in exact_values:
        return "<invalid:case-or-whitespace>"
    return "<invalid:unsupported>"


def _lane_control_issues(env) -> tuple:
    """Explain exact-value lane-control near misses without normalizing them."""
    shim = env.get("DAAF_PROVIDER_SHIM", "")
    backend = env.get("SHIM_BACKEND_MODE", "")
    problems = []

    # A clean native/OpenRouter environment is not attempting a shim lane. Once
    # either control is nonempty, require the complete exact pair fail-closed.
    if not shim and not backend:
        return ()

    if shim != "openai":
        if shim.strip().lower() == "openai":
            problems.append(
                "DAAF_PROVIDER_SHIM is a case/whitespace near miss; runtime requires "
                "exact DAAF_PROVIDER_SHIM='openai'."
            )
        elif shim:
            problems.append(
                "DAAF_PROVIDER_SHIM is not the exact supported shim value 'openai'; "
                "partial or alternate values do not activate a shim lane."
            )
    if backend not in ("chatgpt", "openai"):
        if backend.strip().lower() in ("chatgpt", "openai"):
            problems.append(
                "SHIM_BACKEND_MODE is a case/whitespace near miss; runtime requires "
                "exact SHIM_BACKEND_MODE='chatgpt' or 'openai'."
            )
        else:
            problems.append(
                "SHIM_BACKEND_MODE is not an exact supported lane value; use 'chatgpt' "
                "for the subscription lane or 'openai' for the direct API lane."
            )
    if backend in ("chatgpt", "openai") and shim != "openai":
        problems.append(
            "SHIM_BACKEND_MODE is set without the other exact lane signal: "
            "DAAF_PROVIDER_SHIM must equal 'openai'."
        )
    return tuple(problems)


def detect_route(env) -> str:
    """Detect the active install route from the live environment.

    Order matters: the shim gate (DAAF_PROVIDER_SHIM=openai) is checked before
    the OpenRouter base-URL test because a shim route sets ANTHROPIC_BASE_URL to
    the localhost shim, not to openrouter.ai.
    """
    # The two shim controls intentionally receive NO trimming or case folding.
    # Runtime activates the subscription cap only for this exact conjunction, so
    # diagnostics must not normalize a near miss into a false success.
    shim = env.get("DAAF_PROVIDER_SHIM", "")
    backend_mode = env.get("SHIM_BACKEND_MODE", "")
    base_url = (env.get("ANTHROPIC_BASE_URL") or "").strip().lower()

    if shim == "openai" and backend_mode == "chatgpt":
        return ROUTE_CHATGPT
    if shim == "openai" and backend_mode == "openai":
        return ROUTE_OPENAI_API
    if "openrouter.ai" in base_url:
        return ROUTE_OPENROUTER
    # Presence-only: a non-empty ANTHROPIC_API_KEY is what `claude -p` bills
    # (in print mode the key is always used when present), so it names the
    # Console API route. Empty or unset falls through to the subscription route.
    if _key_state(env, "ANTHROPIC_API_KEY") == "set":
        return ROUTE_ANTHROPIC_API
    return ROUTE_ANTHROPIC


def classify_model_family(env):
    """Classify the configured model family and whether a tier remap is active.

    Returns (family, remap_active). family is one of claude|gpt|glm|unknown and
    is a combined posture over every MODEL_SELECTOR_VARS value (an honored
    ANTHROPIC_DEFAULT_MODEL included); T0.14 resolves the main model separately.
    remap_active is True when ANTHROPIC_DEFAULT_OPUS_MODEL or
    ANTHROPIC_DEFAULT_SONNET_MODEL is set (the only tiers DAAF agents use), or
    when CLAUDE_CODE_SUBAGENT_MODEL_FORCE is enabled — the conditions under which
    enforce-model-ceiling.sh stands down (rules a/b; hook updated and installed
    2026-10-12). CLAUDE_CODE_SUBAGENT_MODEL alone no longer counts: since Claude
    Code 2.1.251 it is only a fallback for subagents without their own model, so
    it does not override DAAF agents' `model:` frontmatter. HAIKU/FABLE remaps
    alone do not count either: no DAAF agent dispatches on those tiers.
    Expectations differ by family: on a Claude-pure config the ceiling hook must
    actively rank; with an OPUS/SONNET remap or a forced subagent model it must
    stand down. (T0.2 also reports an older installed hook's different rule set.)

    Every selector that can name a tier alias — ANTHROPIC_MODEL, an honored
    ANTHROPIC_DEFAULT_MODEL (DAAF ships "opus") and CLAUDE_CODE_SUBAGENT_MODEL,
    each also as "<alias>[1m]", case-insensitively — is resolved through its own
    ANTHROPIC_DEFAULT_<ALIAS>_MODEL mapping before it joins the candidates: the
    mapped slug when the alias is remapped, or "claude" (Claude Code's built-in
    model for that tier) only when it is unmapped (see _resolve_tier_alias).
    Counting the raw alias text instead would classify a custom remap (e.g. OPUS
    -> a qwen slug on OpenRouter) as claude.
    """
    candidates = [resolved for _, _, resolved in _resolved_selectors(env)]
    joined = " ".join(c for c in candidates if c).lower()

    remap_active = bool(
        env.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
        or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        or _subagent_force_enabled(env)
    )

    if "gpt-" in joined or "openai/" in joined:
        family = "gpt"
    elif "glm" in joined:
        family = "glm"
    elif _is_claude_family_name(joined):
        family = "claude"
    else:
        family = "unknown"

    return family, remap_active


def build_route_info(env, asserted_route: str = "") -> RouteInfo:
    """Assemble the RouteInfo for this installation from the live env."""
    detected = detect_route(env)
    family, remap = classify_model_family(env)
    info = RouteInfo(
        detected_route=detected,
        asserted_route=asserted_route or "",
        model_family=family,
        remap_active=remap,
        session_model=env.get("ANTHROPIC_MODEL", "") or _effective_default_model(env),
        shim_control=env.get("DAAF_PROVIDER_SHIM", ""),
        backend_mode_control=env.get("SHIM_BACKEND_MODE", ""),
        lane_control_issues=_lane_control_issues(env),
    )
    if asserted_route:
        info.route_match = (asserted_route == detected)
    return info


# --- Main-model projection (separate from ceiling-hook family posture) -----

_MAIN_ALIASES = {name: f"ANTHROPIC_DEFAULT_{name.upper()}_MODEL"
                 for name in ("opus", "sonnet", "haiku", "fable")}
_MODEL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*(?:\[1m\])?(?:#[A-Za-z0-9_-]+)?")


def main_model_family(model):
    """Classify one explicit selector, never aliases or subagent candidates."""
    if not isinstance(model, str) or not _MODEL_ID_RE.fullmatch(model):
        return "unknown"
    slug = model.rsplit("/", 1)[-1]
    if slug.startswith("claude-"):
        return "claude"
    if re.match(r"gpt-[0-9]", slug):
        return "gpt"
    if re.match(r"glm-[0-9]", slug):
        return "glm"
    return "unknown"


@dataclass(frozen=True)
class MainModelResolution:
    # selector/resolved_model are internal comparison inputs, not report fields.
    selector: str = ""
    resolved_model: str = ""
    source: str = "unresolved"
    overridden: bool = False
    family: str = "unknown"
    compatibility: str = "unknown"
    uncertainty: tuple = ()
    effective_route: str = "unknown"
    endpoint_kind: str = "unknown"
    expected_backend: str = ""
    normal_execution_context: bool = True

    def safe_metadata(self):
        import hashlib
        return {
            "source": self.source, "explicit_override": self.overridden,
            "family": self.family, "compatibility": self.compatibility,
            "uncertainty": list(self.uncertainty),
            "effective_route": self.effective_route, "endpoint_kind": self.endpoint_kind,
            "expected_backend": self.expected_backend,
            "normal_execution_context": self.normal_execution_context,
            "selector_sha256": hashlib.sha256(self.selector.encode()).hexdigest() if self.selector else None,
            "resolved_sha256": hashlib.sha256(self.resolved_model.encode()).hexdigest() if self.resolved_model else None,
            "projection_only": True,
        }


def resolve_main_model(env, saved_model=None, explicit_model=None,
                       env_source="environment", saved_source="saved_model",
                       uncertainty=(), route=None,
                       default_source="environment_default_model"):
    """Pure bounded projection of Claude Code's main-model precedence:
    invocation (--model) > effective ANTHROPIC_MODEL > saved settings `model`
    key > honored ANTHROPIC_DEFAULT_MODEL > account-type default (unresolved).

    Caller supplies already-projected settings env (a settings-file `env` value
    overwrites the same process variable). ANTHROPIC_DEFAULT_MODEL (Claude Code
    2.1.236+) is ignored when set to default/inherit/opusplan/haiku, exactly as
    Claude Code ignores it; its account-availability rule is not emulated. No
    dynamic default or managed policy emulation. Only the short
    opus/sonnet/haiku/fable aliases expand, each through its OWN
    ANTHROPIC_DEFAULT_<ALIAS>_MODEL mapping; explicit IDs are not rewritten by
    default aliases or subagent model pins. An alias whose mapping is unset
    resolves to Claude Code's built-in Claude model for that tier: the family is
    claude, but the exact ID (resolved_model) stays unknown.
    Configuration-compatible does not establish provider availability/acceptance.
    """
    issues = list(uncertainty)
    overridden = explicit_model is not None
    default_model = _effective_default_model(env)
    if overridden:
        selector, source = explicit_model, "invocation"
    elif env.get("ANTHROPIC_MODEL"):
        selector, source = env["ANTHROPIC_MODEL"], env_source
    elif saved_model:
        selector, source = saved_model, saved_source
    elif default_model:
        selector, source = default_model, default_source
    else:
        selector, source = "", "unresolved"
        issues.append("dynamic_default_unresolved")
    if not isinstance(selector, str):
        selector = ""
        issues.append("invalid_selector")
    resolved = selector
    builtin_alias = False
    # "<alias>[1m]" (e.g. "opus[1m]", which /model saves to user settings) is the
    # same alias with the 1M-context hint, so it expands through the same mapping.
    # Case-insensitive ("Opus" expands like "opus"), the same chosen convention
    # as _resolve_tier_alias (the docs are silent on alias case).
    alias = selector[:-len("[1m]")] if selector.lower().endswith("[1m]") else selector
    alias = alias.lower()
    if alias in _MAIN_ALIASES:
        resolved = env.get(_MAIN_ALIASES[alias], "")
        if not isinstance(resolved, str) or not resolved:
            # Unmapped alias: Claude Code uses its built-in Claude model for the
            # tier. Family is known (claude); the exact ID is version-dependent,
            # so resolved_model stays "" and exact-ID consumers (normal-Auto
            # acceptance) must treat it as unresolved.
            resolved = ""
            builtin_alias = True
    family = "claude" if builtin_alias else main_model_family(resolved)
    if family == "unknown":
        issues.append("model_family_unresolved")
    route = route or detect_route(env)
    if _lane_control_issues(env):
        issues.append("route_controls_uncertain")
    if any(env.get(k) not in (None, "", "0", "false") for k in (
            "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")):
        issues.append("alternate_provider_unresolved")
    # Auto eligibility is independent of main-route compatibility. In particular,
    # benchmark smoke must still block a KNOWN Claude-on-GPT mismatch.
    normal_context = not any(env.get(k) not in (None, "", "0", "false") for k in (
        "DAAF_BENCHMARK_RUN", "CLAUDE_CODE_BYPASS_PERMISSIONS", "CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS"))
    base = env.get("ANTHROPIC_BASE_URL")
    endpoint = "unknown"
    backend = ""
    if route in SHIM_ROUTES:
        backend = "chatgpt" if route == ROUTE_CHATGPT else "openai"
        if base in ("http://127.0.0.1:4141", "http://127.0.0.1:4141/",
                    "http://localhost:4141", "http://localhost:4141/"):
            endpoint = "fixed_loopback_shim"
    elif route in ANTHROPIC_ROUTES and base in (None, "", "https://api.anthropic.com", "https://api.anthropic.com/"):
        endpoint = "native_anthropic"
    elif route == ROUTE_OPENROUTER and base in ("https://openrouter.ai/api", "https://openrouter.ai/api/"):
        endpoint = "openrouter_api"
    if endpoint == "unknown":
        issues.append("endpoint_provider_unresolved")
    compatibility = "unknown"
    if not issues:
        if route in SHIM_ROUTES:
            compatibility = "compatible" if family == "gpt" else "incompatible"
        elif route in ANTHROPIC_ROUTES:
            compatibility = "compatible" if family == "claude" else "incompatible"
        elif route == ROUTE_OPENROUTER:
            compatibility = "compatible"
    return MainModelResolution(selector, resolved, source, overridden, family,
                               compatibility, tuple(sorted(set(issues))),
                               route if endpoint != "unknown" and not _lane_control_issues(env) else "unknown",
                               endpoint, backend, normal_context)


def probe_main_model(resolution, profile="", tier="0"):
    """T0.14 safe metadata; preserve ordinary WARN/non-failing semantics."""
    import json
    r = ProbeResult("T0.14", "Main-model/route coherence", tier, profile=profile)
    r.verdict = {"compatible": Verdict.PASS, "incompatible": Verdict.FAIL,
                 "unknown": Verdict.WARN}[resolution.compatibility]
    r.detail = {
        "compatible": "Projected main model is configuration-compatible; provider acceptance is not established.",
        "incompatible": "Projected main model is incompatible with the configured route; paid launch blocked. No configuration changed.",
        "unknown": "Main model or settings precedence is unresolved; compatibility is unknown, not certified.",
    }[resolution.compatibility]
    r.add_evidence("bounded main-model settings projection",
                   output=json.dumps(resolution.safe_metadata(), sort_keys=True))
    return r


# --- Tier 0 route/env coherence probes ------------------------------------

def probe_daaf_dev(env) -> ProbeResult:
    """Tier 0 policy gate: the deployment smoke suite is intentionally restricted
    to DAAF_DEV=1 development images as contributor tooling. Tier D additionally
    uses development-only deterministic/test tools. Codex ships in every image;
    shim routing and Codex authentication are separate explicit opt-ins, and
    neither requires a development image."""
    r = ProbeResult(probe_id="T0.0", name="DAAF_DEV assertion", tier="0")
    val = env.get("DAAF_DEV")
    r.add_evidence("env: DAAF_DEV", output=str(val) if val is not None else "<unset>")
    if val == "1":
        r.verdict = Verdict.PASS
        r.detail = "DAAF_DEV=1 (development image active)."
    else:
        r.verdict = Verdict.FAIL
        r.detail = (
            "DAAF_DEV is not 1. The deployment smoke suite is intentionally restricted to "
            "DAAF_DEV=1 development images as a contributor tool, including for --tiers 0. "
            "Tier D additionally relies on development-only deterministic/test tooling; "
            "missing Tier-D tools can otherwise SKIP. Codex itself ships in every image. "
            "Shim routing and codex login are separate explicit opt-ins and do not require "
            "a development image. Rebuild with DAAF_DEV=1 or run inside the dev container."
        )
    return r


def probe_route_detection(route_info: RouteInfo) -> ProbeResult:
    """Tier 0: report the detected route and, if --route asserted an expectation,
    FAIL on mismatch rather than silently overriding the detection."""
    r = ProbeResult(probe_id="T0.1", name="Route detection + assertion", tier="0")
    r.add_evidence(
        "detect_route(os.environ)",
        output=f"detected={route_info.detected_route}",
        note="derived from exact DAAF_PROVIDER_SHIM / SHIM_BACKEND_MODE controls, then ANTHROPIC_BASE_URL",
    )
    r.add_evidence(
        "env: DAAF_PROVIDER_SHIM / SHIM_BACKEND_MODE",
        output=("DAAF_PROVIDER_SHIM="
                f"{_bounded_lane_control(route_info.shim_control, ('openai',))!r}; "
                "SHIM_BACKEND_MODE="
                f"{_bounded_lane_control(route_info.backend_mode_control, ('chatgpt', 'openai'))!r}"),
        note="exact values or bounded invalid classifications; no normalization into success",
    )
    if route_info.lane_control_issues:
        r.verdict = Verdict.FAIL
        r.detail = "Exact lane-control mismatch: " + " ".join(route_info.lane_control_issues)
        if route_info.asserted_route and not route_info.route_match:
            r.detail += (
                f" --route asserted '{route_info.asserted_route}', while exact-value "
                f"detection yields '{route_info.detected_route}'."
            )
            r.add_evidence("", note=f"asserted={route_info.asserted_route}")
    elif route_info.asserted_route and not route_info.route_match:
        r.verdict = Verdict.FAIL
        r.detail = (
            f"Route mismatch: --route asserted '{route_info.asserted_route}' but the "
            f"live environment detects '{route_info.detected_route}'. Detection is "
            f"authoritative; the asserted expectation is wrong or the env is misconfigured."
        )
        r.add_evidence("", note=f"asserted={route_info.asserted_route}")
    else:
        r.verdict = Verdict.PASS
        if (route_info.detected_route == ROUTE_OPENAI_API
                and route_info.shim_control == "openai"
                and route_info.backend_mode_control != "chatgpt"):
            backend_display = route_info.backend_mode_control or "<unset>"
            r.detail = (
                "Active route: openai-api. The exact ChatGPT-subscription lane is "
                "not selected because SHIM_BACKEND_MODE is "
                f"{backend_display!r}, not exact 'chatgpt'."
            )
        else:
            r.detail = f"Active route: {route_info.detected_route}" + (
                f" (matches asserted --route)." if route_info.asserted_route else "."
            )
    return r


def probe_model_family(route_info: RouteInfo, env, hook_path=None) -> ProbeResult:
    """Tier 0: classify the model family and note the expected ceiling-hook posture.

    The posture depends on which enforce-model-ceiling.sh is installed, so the
    hook file (CEILING_HOOK_PATH unless hook_path is given) is read, never run:
      * current hook (2026-10-12, mentions CLAUDE_CODE_SUBAGENT_MODEL_FORCE):
        stands down only for an enabled force flag (rule a) or an OPUS/SONNET
        remap (rule b); CLAUDE_CODE_SUBAGENT_MODEL alone does not stand it down.
      * older hook (no force flag in its text): stands down whenever
        CLAUDE_CODE_SUBAGENT_MODEL is set (its rule a) or for an OPUS/SONNET
        remap, and does not recognize the force flag.
      * unreadable hook: the current rule set is assumed and the evidence says so
        (T0.6 checks the hook's registration).
    """
    r = ProbeResult(probe_id="T0.2", name="Model family classification", tier="0")
    path = CEILING_HOOK_PATH if hook_path is None else hook_path
    force_aware = _ceiling_hook_recognizes_force(path)
    legacy = force_aware is False
    r.add_evidence(
        "classify_model_family(os.environ)",
        output=f"family={route_info.model_family} remap_active={route_info.remap_active}",
        note=("family: ANTHROPIC_MODEL / ANTHROPIC_DEFAULT_MODEL / "
              "ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU,FABLE}_MODEL / CLAUDE_CODE_SUBAGENT_MODEL, "
              "tier aliases resolved through their ANTHROPIC_DEFAULT_<ALIAS>_MODEL mapping; "
              "remap_active: ANTHROPIC_DEFAULT_{OPUS,SONNET}_MODEL or "
              "CLAUDE_CODE_SUBAGENT_MODEL_FORCE enabled (current hook's rules a/b)"),
    )
    r.add_evidence(
        f"read-only text search of {path} for {_FORCE_MARKER!r}",
        output={True: "found (current 2026-10-12 rule set)",
                False: "not found (older hook rule set)",
                None: "hook file unreadable"}[force_aware],
        note=("Older hooks stand down whenever CLAUDE_CODE_SUBAGENT_MODEL is set and do "
              "not recognize CLAUDE_CODE_SUBAGENT_MODEL_FORCE." if legacy else
              "Expectation below assumes the current rule set; T0.6 checks hook "
              "registration." if force_aware is None else
              "Hook stands down only for CLAUDE_CODE_SUBAGENT_MODEL_FORCE (rule a) or "
              "an OPUS/SONNET remap (rule b)."),
    )
    subagent_model = env.get("CLAUDE_CODE_SUBAGENT_MODEL")
    force = _subagent_force_enabled(env)
    if subagent_model and not force:
        r.add_evidence(
            "env: CLAUDE_CODE_SUBAGENT_MODEL / CLAUDE_CODE_SUBAGENT_MODEL_FORCE",
            output=(f"CLAUDE_CODE_SUBAGENT_MODEL={subagent_model!r}; "
                    f"CLAUDE_CODE_SUBAGENT_MODEL_FORCE="
                    f"{env.get('CLAUDE_CODE_SUBAGENT_MODEL_FORCE', '<unset>')!r}"),
            note=("Since Claude Code 2.1.251 CLAUDE_CODE_SUBAGENT_MODEL is only a fallback "
                  "for subagents without their own model; every DAAF agent sets `model:`, "
                  "so it does not reroute DAAF dispatches unless "
                  "CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1 is also set. "
                  + ("The installed older hook nevertheless stands down while it is set."
                     if legacy else
                     "It does not stand enforce-model-ceiling.sh down on its own.")),
        )
    opus_sonnet_remap = bool(env.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
                             or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL"))
    # Each stand-down reason carries its own rationale, so the explanation names
    # only the rules that actually apply.
    remap_reason = ("an OPUS/SONNET tier remap is set (rule b)",
                    "the hook cannot rank custom slugs")
    if legacy:
        stand_down = bool(subagent_model) or opus_sonnet_remap
        reasons = []
        if subagent_model:
            reasons.append(("CLAUDE_CODE_SUBAGENT_MODEL is set (older rule a)",
                            "the older hook assumes that variable overrides every "
                            "subagent's model, which held only before Claude Code 2.1.251"))
        if opus_sonnet_remap:
            reasons.append(remap_reason)
        prefix = ("Installed enforce-model-ceiling.sh predates the 2026-10-12 update "
                  "(no CLAUDE_CODE_SUBAGENT_MODEL_FORCE support). ")
    else:
        stand_down = route_info.remap_active
        reasons = []
        if force:
            reasons.append(("CLAUDE_CODE_SUBAGENT_MODEL_FORCE is enabled (rule a)",
                            "a forced subagent model makes the ceiling moot"))
        if opus_sonnet_remap:
            reasons.append(remap_reason)
        prefix = ""
    if stand_down:
        expectation = (prefix + "enforce-model-ceiling.sh must STAND DOWN because "
                       + " and ".join(reason for reason, _ in reasons) + " — "
                       + "; ".join(why for _, why in reasons) + ".")
    elif route_info.model_family == "claude":
        expectation = (prefix + "Claude-pure config: enforce-model-ceiling.sh must "
                       "actively RANK subagent dispatches (haiku<sonnet<opus<fable).")
    else:
        expectation = (prefix + "Non-Claude family without an OPUS/SONNET remap: a "
                       "Claude-tier subagent request would be DENIED with tier-alias "
                       "guidance (ceiling-hook rule f).")
    if legacy and force:
        expectation += (" CLAUDE_CODE_SUBAGENT_MODEL_FORCE is set, but this older hook "
                        "does not recognize it.")
    r.verdict = Verdict.INFO
    r.detail = expectation
    return r


def probe_env_coherence(route_info: RouteInfo, env) -> ProbeResult:
    """Tier 0: verify the env vars required by the detected route are present and
    mutually coherent. Route-specific: required vars, the ANTHROPIC_API_KEY
    empty-vs-unset distinction (OpenRouter), and shim endpoint wiring."""
    route = route_info.detected_route
    r = ProbeResult(probe_id="T0.3", name=f"Env coherence ({route})", tier="0")
    problems = []

    def note_var(name):
        r.add_evidence(f"env: {name}", output=redact_env_value(name, env.get(name)) if name in env else "<unset>")

    if route in ANTHROPIC_ROUTES:
        # Both start-model selectors: DAAF's shipped settings.json sets only the
        # soft ANTHROPIC_DEFAULT_MODEL, so ANTHROPIC_MODEL is normally <unset>.
        note_var("ANTHROPIC_MODEL")
        note_var("ANTHROPIC_DEFAULT_MODEL")
        note_var("CLAUDE_CODE_OAUTH_TOKEN")
        note_var("ANTHROPIC_API_KEY")
        # anthropic-api: the Console key is the credential (detection requires it
        # set). ANTHROPIC_AUTH_TOKEN outranks it in Claude Code's credential order
        # (environment_settings_example.txt), so a stray one silently replaces the
        # key on both Anthropic routes; T0.16 reports the billing consequence.
        if _key_state(env, "ANTHROPIC_AUTH_TOKEN") == "set":
            problems.append(
                "ANTHROPIC_AUTH_TOKEN is set on a native Anthropic route — it outranks "
                "ANTHROPIC_API_KEY and the subscription login, so requests use it instead."
            )
        # Native Claude Code auth is interactive OR CLAUDE_CODE_OAUTH_TOKEN.
        # We cannot verify interactive OAuth without an LLM call, so this is INFO
        # unless ANTHROPIC_BASE_URL is unexpectedly pointed elsewhere.
        base = env.get("ANTHROPIC_BASE_URL", "")
        if base and "anthropic.com" not in base.lower():
            problems.append(
                f"ANTHROPIC_BASE_URL is set to '{base}' but route detected as "
                f"{route} — unexpected for the native route."
            )

    elif route == ROUTE_OPENROUTER:
        note_var("ANTHROPIC_BASE_URL")
        note_var("ANTHROPIC_AUTH_TOKEN")
        note_var("ANTHROPIC_API_KEY")
        base = (env.get("ANTHROPIC_BASE_URL") or "").lower()
        if "openrouter.ai/api" not in base:
            problems.append("ANTHROPIC_BASE_URL should end with 'openrouter.ai/api' for the OpenRouter route.")
        if _key_state(env, "ANTHROPIC_AUTH_TOKEN") != "set":
            problems.append("ANTHROPIC_AUTH_TOKEN must be set (your OpenRouter key) for Bearer auth.")
        api_state = _key_state(env, "ANTHROPIC_API_KEY")
        if api_state == "unset":
            problems.append(
                "ANTHROPIC_API_KEY is UNSET — for OpenRouter it must be present-and-EMPTY "
                "(ANTHROPIC_API_KEY=) so the X-Api-Key header does not override Bearer auth."
            )
        elif api_state == "set":
            problems.append(
                "ANTHROPIC_API_KEY is non-empty — for OpenRouter it should be empty "
                "(present-and-blank) to avoid X-Api-Key interfering with Bearer auth."
            )

    elif route in SHIM_ROUTES:
        note_var("DAAF_PROVIDER_SHIM")
        note_var("ANTHROPIC_BASE_URL")
        note_var("ANTHROPIC_AUTH_TOKEN")
        note_var("CLAUDE_CODE_DISABLE_FAST_MODE")
        base = (env.get("ANTHROPIC_BASE_URL") or "").lower()
        if "127.0.0.1:4141" not in base and "localhost:4141" not in base:
            problems.append("ANTHROPIC_BASE_URL should point at the local shim (http://127.0.0.1:4141) for shim routes.")
        if env.get("CLAUDE_CODE_DISABLE_FAST_MODE") != "1":
            problems.append(
                "CLAUDE_CODE_DISABLE_FAST_MODE must be the exact string '1' for GPT "
                "shim routes. Run 'bash /daaf/scripts/provider_shim/gpt_fast.sh off' "
                "to keep the requested GPT service-tier policy safely OFF, set "
                "CLAUDE_CODE_DISABLE_FAST_MODE=1 in the host environment_settings.txt, "
                "recreate the container, and start a new Claude session."
            )
        if route == ROUTE_CHATGPT:
            note_var("SHIM_BACKEND_MODE")
            note_var("CODEX_HOME")
            if env.get("SHIM_BACKEND_MODE") != "chatgpt":
                problems.append("SHIM_BACKEND_MODE must equal exact value 'chatgpt' for the ChatGPT-subscription route.")
            if not env.get("CODEX_HOME"):
                problems.append("CODEX_HOME must be set (holds auth.json) for the ChatGPT route.")
        else:  # openai-api
            note_var("SHIM_BACKEND_MODE")
            note_var("OPENAI_API_KEY")
            note_var("SHIM_BACKEND_API_KEY")
            if env.get("SHIM_BACKEND_MODE") != "openai":
                problems.append("SHIM_BACKEND_MODE must equal exact value 'openai' for the OpenAI-API route.")
            if _key_state(env, "OPENAI_API_KEY") != "set" and _key_state(env, "SHIM_BACKEND_API_KEY") != "set":
                problems.append("OPENAI_API_KEY or SHIM_BACKEND_API_KEY must be set for the OpenAI-API route.")

    if problems:
        r.verdict = Verdict.FAIL
        r.detail = "; ".join(problems)
    else:
        r.verdict = Verdict.PASS
        r.detail = f"Required env vars for {route} are present and coherent."
    return r


def probe_context_window_coherence(route_info: RouteInfo, env) -> ProbeResult:
    """Tier 0: validate the declaration used by Claude Code and DAAF accounting.

    Every effective model selector is inspected. On the exact ChatGPT-subscription
    lane, any selector mapped to the runtime's anchored GPT flagship physical
    family makes the 919000 ceiling relevant. That family is gpt-5.4/5.5/5.6 plus
    gpt-6-astra, and also gpt-6-sol, gpt-6-luna and the flagship -pro forms under
    the 2026-09-29 user policy decision and gpt-6.1-sol under the 2026-10-12 one,
    where the cap is inferred rather than measured.
    Numeric declarations use the same canonical positive signed-64-bit contract
    as the Bash consumers.
    """
    r = ProbeResult(probe_id="T0.4", name="Context-window declaration", tier="0")
    selectors = [(name, env.get(name, "")) for name in MODEL_SELECTOR_VARS]
    max_ctx = env.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS")
    auto_compact = env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")

    for name, value in selectors:
        mapped = _gpt_physical_window(value)
        r.add_evidence(
            f"env: {name}",
            output=value or "<unset>",
            note=(f"runtime GPT physical mapping={mapped}" if mapped is not None
                  else "no supported GPT physical-family mapping"),
        )
    r.add_evidence(
        "env: CLAUDE_CODE_MAX_CONTEXT_TOKENS",
        output=str(max_ctx) if max_ctx is not None else "<unset>",
        note="must match ^[1-9][0-9]*$ and be <= 9223372036854775807",
    )
    r.add_evidence(
        "env: CLAUDE_CODE_AUTO_COMPACT_WINDOW",
        output=str(auto_compact) if auto_compact is not None else "<unset>",
    )

    # Any non-Claude family reached over a route Claude Code does not natively
    # recognize needs an explicit window declaration. Static runtime fallbacks do
    # not guarantee Claude Code's own dynamic/headless budgeting in every context.
    # The combined family alone is not enough on OpenRouter: one Claude-looking
    # selector (e.g. a Claude HAIKU slug) would make it "claude" and mask a
    # non-Claude OPUS/SONNET mapping. So each selector is also checked on its own,
    # tier aliases resolved first (_resolved_selectors; case-insensitive alias
    # match), and ANY non-Claude one requires the declaration.
    resolved = _resolved_selectors(env)
    non_claude = [(name, raw, res) for name, raw, res in resolved
                  if not _is_claude_family_name(res)]
    r.add_evidence(
        "resolved selectors (tier aliases expanded through ANTHROPIC_DEFAULT_<ALIAS>_MODEL)",
        output="; ".join(f"{name}={raw!r} -> {res!r}" for name, raw, res in resolved) or "<none set>",
        note=("non-Claude: " + ", ".join(name for name, _, _ in non_claude)
              if non_claude else "no non-Claude selector"),
    )
    needs_declaration = (
        route_info.detected_route in SHIM_ROUTES
        or route_info.model_family == "gpt"
        or (route_info.detected_route == ROUTE_OPENROUTER
            and (route_info.model_family != "claude" or bool(non_claude)))
    )
    non_claude_text = ", ".join(
        f"{name}={raw!r}" + (f" -> {res!r}" if res != raw else "")
        for name, raw, res in non_claude
    )

    max_is_present = max_ctx is not None
    has_max = _is_canonical_positive_decimal(max_ctx)
    auto_compact_active = _is_canonical_positive_decimal(auto_compact)
    gpt_selectors = [
        (name, value, _gpt_physical_window(value))
        for name, value in selectors
        if value and _gpt_physical_window(value) is not None
    ]
    flagship_selectors = [
        (name, value) for name, value, window in gpt_selectors
        if window == 1050000
    ]
    exact_chatgpt_flagship = (
        route_info.detected_route == ROUTE_CHATGPT
        and bool(flagship_selectors)
    )
    relevant_text = ", ".join(
        f"{name}={value!r}" for name, value in flagship_selectors
    )

    # [1m] is a supported Claude Code hint on the direct OpenAI-API shim route.
    # It is not generalized to OpenRouter, whose supported example uses the bare
    # provider-prefixed slug plus an explicit 1050000 declaration. A single global
    # declaration remains the safest contract when selectors differ.
    direct_api_1m_complete = (
        route_info.detected_route == ROUTE_OPENAI_API
        and bool(gpt_selectors)
        and all(_has_supported_1m_hint(value) for _, value, _ in gpt_selectors)
    )
    native_claude_1m = (
        route_info.model_family == "claude"
        and not non_claude
        and any(_has_supported_1m_hint(value) for _, value in selectors if value)
    )

    if exact_chatgpt_flagship and auto_compact_active:
        r.verdict = Verdict.FAIL
        r.detail = (
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW is set on the exact "
            "ChatGPT-subscription lane for mapped GPT flagship selector(s): "
            f"{relevant_text}. DAAF keeps automatic compaction disabled; remove "
            "this setting and declare CLAUDE_CODE_MAX_CONTEXT_TOKENS=919000 "
            "(or a lower verified canonical positive value)."
        )
    elif max_is_present and not has_max:
        r.verdict = Verdict.FAIL
        r.detail = (
            f"Invalid CLAUDE_CODE_MAX_CONTEXT_TOKENS={max_ctx!r}. Runtime accepts "
            "only canonical positive decimal text matching ^[1-9][0-9]*$ and no "
            "greater than 9223372036854775807; signs, whitespace, leading zeroes, "
            "decimals, exponent notation, empty values, and overflow are ignored."
        )
        if exact_chatgpt_flagship:
            r.detail += f" The exact-lane ceiling is relevant because of: {relevant_text}."
    elif exact_chatgpt_flagship and not has_max:
        r.verdict = Verdict.FAIL
        r.detail = (
            "ChatGPT-subscription/Codex mapped GPT flagship selector(s) require "
            "a canonical CLAUDE_CODE_MAX_CONTEXT_TOKENS declaration no greater "
            f"than 919000. Relevant selector(s): {relevant_text}. A [1m] suffix "
            "and CLAUDE_CODE_AUTO_COMPACT_WINDOW do not satisfy this lane policy."
        )
    elif exact_chatgpt_flagship and int(max_ctx) > 919000:
        r.verdict = Verdict.FAIL
        r.detail = (
            f"Unsafe ChatGPT-subscription context declaration: {max_ctx} exceeds "
            "the 919000-token Codex backend ceiling (measured for gpt-5.6-sol and "
            "gpt-6-astra; applied to the other mapped flagships by 2026-09-29 "
            "policy). The declaration is "
            f"relevant because of: {relevant_text}. Set "
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS=919000, recreate the container, and "
            "restart the Claude Code session."
        )
    elif exact_chatgpt_flagship:
        r.verdict = Verdict.PASS
        r.detail = (
            f"ChatGPT-subscription declaration {max_ctx} is canonical and aligned "
            "with the 919000-token backend ceiling (measured for gpt-5.6-sol and "
            "gpt-6-astra; policy-applied to the other mapped flagships); lower "
            "positive values "
            f"are preserved. Relevant selector(s): {relevant_text}."
        )
    elif not needs_declaration:
        r.verdict = Verdict.INFO
        r.detail = "Model window resolves natively for this family; explicit declaration not required."
    elif has_max:
        r.verdict = Verdict.PASS
        r.detail = (
            f"Context window explicitly declared with canonical "
            f"CLAUDE_CODE_MAX_CONTEXT_TOKENS={max_ctx}."
        )
    elif direct_api_1m_complete:
        variables = ", ".join(name for name, _, _ in gpt_selectors)
        r.verdict = Verdict.PASS
        r.detail = (
            "Direct OpenAI-API shim GPT selector(s) use the supported [1m] hint "
            f"({variables}); the shim/backend receive bare model slugs."
        )
    elif native_claude_1m:
        r.verdict = Verdict.PASS
        r.detail = "Native Claude model uses its recognized [1m] context hint."
    else:
        r.verdict = Verdict.FAIL
        selector_note = (f"; non-Claude selector(s): {non_claude_text}"
                         if non_claude_text else "")
        r.detail = (
            f"Non-Claude/shim model ({route_info.model_family} family, "
            f"{route_info.detected_route} route{selector_note}) lacks a route-supported context "
            "declaration. Use a canonical positive CLAUDE_CODE_MAX_CONTEXT_TOKENS; "
            "for OpenRouter keep provider-prefixed bare GPT slugs and declare the "
            "route window explicitly. The [1m] suffix is supported for the direct "
            "OpenAI-API shim, not generalized across routes. "
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW is not an accepted substitute."
        )
    return r


# --- smoke v2 Tier 0: credential overlap (T0.16) and alias completeness (T0.17)

def probe_credential_overlap(route_info: RouteInfo, env) -> ProbeResult:
    """T0.16 — presence-only credential overlap on the native Anthropic routes.

    The "stated" route is --route when given, else the detected route. Claude
    Code's credential order (environment_settings_example.txt): Bedrock/Vertex >
    ANTHROPIC_AUTH_TOKEN > ANTHROPIC_API_KEY > CLAUDE_CODE_OAUTH_TOKEN >
    interactive login, and in -p mode a present ANTHROPIC_API_KEY is always used
    (scoping note 04 §1, search summary of the authentication docs — not fetched).
      * ANTHROPIC_AUTH_TOKEN set on an Anthropic route -> FAIL (it outranks both);
      * stated subscription with ANTHROPIC_API_KEY set -> FAIL (every -p probe
        would silently test and bill the key);
      * stated API with CLAUDE_CODE_OAUTH_TOKEN set -> WARN (overlap; the key wins);
      * otherwise PASS. Non-Anthropic routes SKIP (OpenRouter's key rules are T0.3).
    Values are never read: only unset/empty/set."""
    r = ProbeResult(probe_id="T0.16", name="Credential overlap", tier="0")
    stated = route_info.asserted_route or route_info.detected_route
    states = {n: _key_state(env, n) for n in
              ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")}
    r.add_evidence("env presence (unset|empty|set): " + ", ".join(states),
                   output="; ".join(f"{n}={s}" for n, s in states.items()),
                   note=f"stated route={stated} (detected={route_info.detected_route})")
    if stated not in ANTHROPIC_ROUTES:
        r.verdict = Verdict.SKIP
        r.detail = f"Not a native Anthropic route ({stated}); credential precedence is checked by T0.3."
        return r
    problems, warnings = [], []
    if states["ANTHROPIC_AUTH_TOKEN"] == "set":
        problems.append("ANTHROPIC_AUTH_TOKEN is set: it outranks ANTHROPIC_API_KEY and the "
                        "subscription login, so every request uses that token instead")
    if stated == ROUTE_ANTHROPIC and states["ANTHROPIC_API_KEY"] == "set":
        problems.append("the stated route is anthropic-subscription but ANTHROPIC_API_KEY is set: "
                        "in -p mode the key is always used, so the paid probes would test and "
                        "bill the API key, not the subscription")
    if stated == ROUTE_ANTHROPIC_API and states["CLAUDE_CODE_OAUTH_TOKEN"] == "set":
        warnings.append("the stated route is anthropic-api but CLAUDE_CODE_OAUTH_TOKEN is also set; "
                        "the key wins, the token is unused overlap")
    if problems:
        r.verdict = Verdict.FAIL
        r.detail = "Credential overlap: " + "; ".join(problems + warnings) + "."
    elif warnings:
        r.verdict = Verdict.WARN
        r.detail = "Credential overlap: " + "; ".join(warnings) + "."
    else:
        r.verdict = Verdict.PASS
        r.detail = f"No credential overlap for {stated}."
    return r


_TIER_ALIAS_VARS = ("ANTHROPIC_DEFAULT_FABLE_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
                    "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL")


def probe_alias_completeness(route_info: RouteInfo, env, settings_overlay=None) -> ProbeResult:
    """T0.17 — on non-Anthropic routes every tier alias must be mapped (F2/F3:
    an unmapped HAIKU sends Claude Code's housekeeping calls — session naming,
    resume summaries — to a Claude model name the route cannot serve).

    settings_overlay: {alias var: (value, source label)} from the settings files'
    `env` blocks (smoke_probes.collect_alias_settings; user < project < local, the
    observed 2.1.281 precedence). A settings value overrides the process env, as
    in a real session. None means the settings files were not read: the verdict
    then judges the process env alone and the detail says so.

      * shim routes: all four ANTHROPIC_DEFAULT_{FABLE,OPUS,SONNET,HAIKU}_MODEL
        set and non-Claude, else FAIL (the ChatGPT lane fast-fails claude-*
        slugs; the API lane forwards them to a backend that rejects them);
      * OpenRouter with a non-Claude model family: an unset alias is WARN (the
        built-in Claude name may not resolve there); a Claude-family mapping is
        accepted, because OpenRouter can serve Claude slugs (billed per use);
      * Anthropic routes and Claude-family OpenRouter: SKIP.
    Model names are not secrets and are quoted as configured."""
    r = ProbeResult(probe_id="T0.17", name="Tier-alias completeness", tier="0")
    route = route_info.detected_route
    values = {n: (env.get(n) if isinstance(env.get(n), str) else "") for n in _TIER_ALIAS_VARS}
    sources = {n: ("process env" if values[n] else "unset") for n in _TIER_ALIAS_VARS}
    for name, entry in (settings_overlay or {}).items():
        if name in values and isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], str):
            values[name], sources[name] = entry[0], entry[1]
    r.add_evidence("env + settings `env` (user < project < local): " + ", ".join(_TIER_ALIAS_VARS),
                   output="; ".join(f"{n}={v or '<unset>'} ({sources[n]})" for n, v in values.items()),
                   note=("settings files read" if settings_overlay is not None
                         else "settings files NOT read: process env only"))
    scope_note = ("" if settings_overlay is not None
                  else " Settings `env` mappings were not checked (process env only).")
    if route in ANTHROPIC_ROUTES or (route == ROUTE_OPENROUTER and route_info.model_family == "claude"):
        r.verdict = Verdict.SKIP
        r.detail = f"Tier aliases resolve natively on {route} (family {route_info.model_family})."
        return r
    unset = [n for n, v in values.items() if not v]
    claude = [n for n, v in values.items() if v and _is_claude_family_name(v)]
    if route in SHIM_ROUTES:
        if unset or claude:
            r.verdict = Verdict.FAIL
            parts = []
            if unset:
                parts.append("unset: " + ", ".join(unset))
            if claude:
                parts.append("Claude-family: " + ", ".join(claude))
            r.detail = ("Every tier alias must map to a GPT model on shim routes (" + "; ".join(parts)
                        + "). Unmapped or Claude-named aliases reach the shim as claude-* requests."
                        + scope_note)
        else:
            r.verdict = Verdict.PASS
            r.detail = "All four tier aliases map to non-Claude models." + scope_note
        return r
    # OpenRouter, non-Claude family.
    if unset:
        r.verdict = Verdict.WARN
        r.detail = ("Non-Claude OpenRouter config leaves tier alias(es) unmapped: " + ", ".join(unset)
                    + ". Claude Code then requests its built-in Claude name for that tier." + scope_note)
    else:
        r.verdict = Verdict.PASS
        r.detail = "All four tier aliases are mapped" + (
            f" (Claude-family via OpenRouter: {', '.join(claude)})." if claude else ".") + scope_note
    return r


# --- Remediation hints (smoke v2 §4) ----------------------------------------
# Static text per probe, kept beside the probe definitions so hint and check
# change together. smoke_probes.PROBE_HINTS holds the other modules' probes and
# merges this dict; a probe may also set ProbeResult.hint for a specific shape.
ROUTE_PROBE_HINTS = {
    "T0.0": "Run inside the DAAF_DEV=1 dev image (set DAAF_DEV=1 in environment_settings.txt and recreate the container).",
    "T0.1": "Re-run with the --route that matches this container, or fix DAAF_PROVIDER_SHIM / SHIM_BACKEND_MODE / ANTHROPIC_BASE_URL / ANTHROPIC_API_KEY in environment_settings.txt; detection is authoritative.",
    "T0.3": "Set the route's required variables in environment_settings.txt (see the install guide for this route), recreate the container, and start a new session.",
    "T0.4": "Declare CLAUDE_CODE_MAX_CONTEXT_TOKENS (919000 on the ChatGPT lane; the model window elsewhere) and remove CLAUDE_CODE_AUTO_COMPACT_WINDOW.",
    "T0.14": "Remove the stale ANTHROPIC_MODEL pin, settings `model` key or /model choice so the route's GPT/Claude mapping applies; see FAQ 'main model route rejection'.",
    "T0.16": "Keep exactly one credential per install: unset ANTHROPIC_AUTH_TOKEN on Anthropic routes; on a subscription install remove ANTHROPIC_API_KEY (it is billed per use); on an API install drop CLAUDE_CODE_OAUTH_TOKEN.",
    "T0.17": "Map all four ANTHROPIC_DEFAULT_{FABLE,OPUS,SONNET,HAIKU}_MODEL to models this route serves (environment_settings_example.txt), recreate the container, start a new session.",
}
