"""Route detection, model-family classification, and env-coherence checks for
the DAAF deployment smoke-testing suite.

This is the foundational layer of the suite. It defines the shared result
vocabulary (Verdict, Evidence, ProbeResult) used by every tier and the pure,
no-LLM inspection logic that reads the *live* environment to determine which of
DAAF's four install routes is active — exactly as the user configured it.

The four routes (auto-detected from the live env, per the approved design):

    DAAF_PROVIDER_SHIM=openai + SHIM_BACKEND_MODE=chatgpt  -> chatgpt-subscription
    DAAF_PROVIDER_SHIM=openai + SHIM_BACKEND_MODE=openai   -> openai-api
    ANTHROPIC_BASE_URL contains "openrouter.ai"            -> openrouter
    else                                                   -> anthropic-subscription

This module makes NO subprocess calls and NO LLM calls — it is pure environment
inspection so Tier 0 preflight can run for free. It is framework tooling (like
benchmarks/), so it uses normal engineering style with functions, NOT the
sequential no-functions research-script style that CLAUDE.md mandates for
pipeline analysis scripts.

Dependency position: this module imports nothing from the rest of the suite, so
the internal import DAG is route_detection <- smoke_probes <- run_deploy_smoke.
"""

import re
from dataclasses import dataclass, field


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
ROUTE_OPENROUTER = "openrouter"
ROUTE_OPENAI_API = "openai-api"
ROUTE_CHATGPT = "chatgpt-subscription"

ALL_ROUTES = (ROUTE_ANTHROPIC, ROUTE_OPENROUTER, ROUTE_OPENAI_API, ROUTE_CHATGPT)

# Routes that place the provider shim in the request path. For these, shim
# /health is a required Tier 0 probe and per-run env overlays (--profiles)
# cannot change daemon-level state (SHIM_SANITIZE_TOOLS, backend_mode).
SHIM_ROUTES = frozenset({ROUTE_OPENAI_API, ROUTE_CHATGPT})

# Every selector that can make Claude Code itself or a dispatched subagent run a
# mapped GPT model. T0.4 inspects all four rather than treating ANTHROPIC_MODEL as
# a proxy for the effective model surface.
MODEL_SELECTOR_VARS = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
)

_MAX_SIGNED_64 = 9223372036854775807
_CANONICAL_POSITIVE_DECIMAL_RE = re.compile(r"^[1-9][0-9]*$")


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
        }


@dataclass
class RouteInfo:
    """The detected configuration surface for this installation."""

    detected_route: str
    asserted_route: str = ""        # from --route, "" if not asserted
    model_family: str = "unknown"   # claude | gpt | glm | unknown
    remap_active: bool = False      # tier-alias remap or subagent-model pin set
    session_model: str = ""         # ANTHROPIC_MODEL as configured
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
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
    "CLAUDE_CODE_EFFORT_LEVEL",
    "CLAUDE_CODE_DISABLE_FAST_MODE",
    "CODEX_HOME",
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

    Physical-family matching is deliberately separate from exact-Sol quality-tier
    matching. It operates on the terminal provider-stripped slug, requires a
    supported version at the left boundary, and accepts only end-of-slug, '-' or
    '[' as the version boundary. The ordering mirrors the Bash consumers so mini
    and chat variants keep their established smaller mappings.
    """
    slug = (model_id or "").rsplit("/", 1)[-1]
    if re.match(r"^gpt-5\.(?:4|5|6)(?:$|[-\[])", slug):
        if "-mini" in slug:
            return 400000
        if "-chat" in slug:
            return 128000
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
    return ROUTE_ANTHROPIC


def classify_model_family(env):
    """Classify the configured model family and whether a tier remap is active.

    Returns (family, remap_active). family is one of claude|gpt|glm|unknown.
    remap_active is True when any of the tier-alias remaps or the global
    subagent-model pin is set — the condition under which enforce-model-ceiling
    stands down (rules a/b of that hook). Expectations differ by family: on a
    Claude-pure config the ceiling hook must actively rank; with remaps set it
    must stand down.
    """
    candidates = [
        env.get("ANTHROPIC_MODEL", ""),
        env.get("ANTHROPIC_DEFAULT_OPUS_MODEL", ""),
        env.get("ANTHROPIC_DEFAULT_SONNET_MODEL", ""),
        env.get("CLAUDE_CODE_SUBAGENT_MODEL", ""),
    ]
    joined = " ".join(c for c in candidates if c).lower()

    remap_active = bool(
        env.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
        or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        or env.get("CLAUDE_CODE_SUBAGENT_MODEL")
    )

    if "gpt-" in joined or "openai/" in joined:
        family = "gpt"
    elif "glm" in joined:
        family = "glm"
    elif any(k in joined for k in ("claude", "opus", "sonnet", "haiku", "fable", "mythos")):
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
        session_model=env.get("ANTHROPIC_MODEL", ""),
        shim_control=env.get("DAAF_PROVIDER_SHIM", ""),
        backend_mode_control=env.get("SHIM_BACKEND_MODE", ""),
        lane_control_issues=_lane_control_issues(env),
    )
    if asserted_route:
        info.route_match = (asserted_route == detected)
    return info


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


def probe_model_family(route_info: RouteInfo, env) -> ProbeResult:
    """Tier 0: classify the model family and note the expected ceiling-hook posture."""
    r = ProbeResult(probe_id="T0.2", name="Model family classification", tier="0")
    r.add_evidence(
        "classify_model_family(os.environ)",
        output=f"family={route_info.model_family} remap_active={route_info.remap_active}",
        note="ANTHROPIC_MODEL / ANTHROPIC_DEFAULT_{OPUS,SONNET}_MODEL / CLAUDE_CODE_SUBAGENT_MODEL",
    )
    if route_info.model_family == "claude" and not route_info.remap_active:
        expectation = ("Claude-pure config: enforce-model-ceiling.sh must actively RANK "
                       "subagent dispatches (haiku<sonnet<opus<fable).")
    elif route_info.remap_active:
        expectation = ("Tier remap / subagent pin active: enforce-model-ceiling.sh must "
                       "STAND DOWN (rules a/b) — it cannot rank custom slugs.")
    else:
        expectation = ("Non-Claude family without remap: a Claude-tier subagent request "
                       "would be DENIED with remap guidance (ceiling-hook rule f).")
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

    if route == ROUTE_ANTHROPIC:
        note_var("ANTHROPIC_MODEL")
        note_var("CLAUDE_CODE_OAUTH_TOKEN")
        # Native Claude Code auth is interactive OR CLAUDE_CODE_OAUTH_TOKEN.
        # We cannot verify interactive OAuth without an LLM call, so this is INFO
        # unless ANTHROPIC_BASE_URL is unexpectedly pointed elsewhere.
        base = env.get("ANTHROPIC_BASE_URL", "")
        if base and "anthropic.com" not in base.lower():
            problems.append(
                f"ANTHROPIC_BASE_URL is set to '{base}' but route detected as "
                f"anthropic-subscription — unexpected for the native route."
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
    lane, any selector mapped to the runtime's anchored GPT 5.4/5.5/5.6 flagship
    physical family makes the 370000 ceiling relevant. Numeric declarations use
    the same canonical positive signed-64-bit contract as the Bash consumers.
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
    needs_declaration = (
        route_info.detected_route in SHIM_ROUTES
        or route_info.model_family == "gpt"
        or (route_info.detected_route == ROUTE_OPENROUTER
            and route_info.model_family != "claude")
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
        and any(_has_supported_1m_hint(value) for _, value in selectors if value)
    )

    if exact_chatgpt_flagship and auto_compact_active:
        r.verdict = Verdict.FAIL
        r.detail = (
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW is set on the exact "
            "ChatGPT-subscription lane for mapped GPT flagship selector(s): "
            f"{relevant_text}. DAAF keeps automatic compaction disabled; remove "
            "this setting and declare CLAUDE_CODE_MAX_CONTEXT_TOKENS=370000 "
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
            f"than 370000. Relevant selector(s): {relevant_text}. A [1m] suffix "
            "and CLAUDE_CODE_AUTO_COMPACT_WINDOW do not satisfy this lane policy."
        )
    elif exact_chatgpt_flagship and int(max_ctx) > 370000:
        r.verdict = Verdict.FAIL
        r.detail = (
            f"Unsafe ChatGPT-subscription context declaration: {max_ctx} exceeds "
            "the measured 370000-token Codex backend ceiling. The declaration is "
            f"relevant because of: {relevant_text}. Set "
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS=370000, recreate the container, and "
            "restart the Claude Code session."
        )
    elif exact_chatgpt_flagship:
        r.verdict = Verdict.PASS
        r.detail = (
            f"ChatGPT-subscription declaration {max_ctx} is canonical and aligned "
            "with the measured 370000-token backend ceiling; lower positive values "
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
        r.detail = (
            f"Non-Claude/shim model ({route_info.model_family} family, "
            f"{route_info.detected_route} route) lacks a route-supported context "
            "declaration. Use a canonical positive CLAUDE_CODE_MAX_CONTEXT_TOKENS; "
            "for OpenRouter keep provider-prefixed bare GPT slugs and declare the "
            "route window explicitly. The [1m] suffix is supported for the direct "
            "OpenAI-API shim, not generalized across routes. "
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW is not an accepted substitute."
        )
    return r
