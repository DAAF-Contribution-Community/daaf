"""Route detection, model-family classification, and env-coherence checks for
the DAAF deployment smoke-testing suite.

This is the foundational layer of the suite. It defines the shared result
vocabulary (Verdict, Evidence, ProbeResult) used by every tier and the pure,
no-LLM inspection logic that reads the *live* environment to determine which of
DAAF's four install routes is active — exactly as the user configured it.

The four routes (auto-detected from the live env, per the approved design):

    DAAF_PROVIDER_SHIM=openai + SHIM_BACKEND_MODE=chatgpt  -> chatgpt-subscription
    DAAF_PROVIDER_SHIM=openai (otherwise)                  -> openai-api
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

    def to_dict(self) -> dict:
        return {
            "detected_route": self.detected_route,
            "asserted_route": self.asserted_route,
            "model_family": self.model_family,
            "remap_active": self.remap_active,
            "session_model": self.session_model,
            "route_match": self.route_match,
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

def detect_route(env) -> str:
    """Detect the active install route from the live environment.

    Order matters: the shim gate (DAAF_PROVIDER_SHIM=openai) is checked before
    the OpenRouter base-URL test because a shim route sets ANTHROPIC_BASE_URL to
    the localhost shim, not to openrouter.ai.
    """
    shim = (env.get("DAAF_PROVIDER_SHIM") or "").strip().lower()
    backend_mode = (env.get("SHIM_BACKEND_MODE") or "").strip().lower()
    base_url = (env.get("ANTHROPIC_BASE_URL") or "").strip().lower()

    if shim == "openai":
        return ROUTE_CHATGPT if backend_mode == "chatgpt" else ROUTE_OPENAI_API
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
        note="derived from DAAF_PROVIDER_SHIM / SHIM_BACKEND_MODE / ANTHROPIC_BASE_URL",
    )
    if route_info.asserted_route and not route_info.route_match:
        r.verdict = Verdict.FAIL
        r.detail = (
            f"Route mismatch: --route asserted '{route_info.asserted_route}' but the "
            f"live environment detects '{route_info.detected_route}'. Detection is "
            f"authoritative; the asserted expectation is wrong or the env is misconfigured."
        )
        r.add_evidence("", note=f"asserted={route_info.asserted_route}")
    else:
        r.verdict = Verdict.PASS
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
        base = (env.get("ANTHROPIC_BASE_URL") or "").lower()
        if "127.0.0.1:4141" not in base and "localhost:4141" not in base:
            problems.append("ANTHROPIC_BASE_URL should point at the local shim (http://127.0.0.1:4141) for shim routes.")
        if route == ROUTE_CHATGPT:
            note_var("SHIM_BACKEND_MODE")
            note_var("CODEX_HOME")
            if (env.get("SHIM_BACKEND_MODE") or "").strip().lower() != "chatgpt":
                problems.append("SHIM_BACKEND_MODE must be 'chatgpt' for the ChatGPT-subscription route.")
            if not env.get("CODEX_HOME"):
                problems.append("CODEX_HOME must be set (holds auth.json) for the ChatGPT route.")
        else:  # openai-api
            note_var("OPENAI_API_KEY")
            note_var("SHIM_BACKEND_API_KEY")
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
    """Tier 0: for model slugs Claude Code does not recognize (GPT slugs; any
    non-[1m] flagship), the real context window must be declared via a [1m]
    suffix or CLAUDE_CODE_MAX_CONTEXT_TOKENS — otherwise the statusline/hook
    stack silently assumes ~200k, a known silent failure."""
    r = ProbeResult(probe_id="T0.4", name="Context-window declaration", tier="0")
    model = env.get("ANTHROPIC_MODEL", "")
    max_ctx = env.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS")
    auto_compact = env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    r.add_evidence("env: ANTHROPIC_MODEL", output=model or "<unset>")
    r.add_evidence("env: CLAUDE_CODE_MAX_CONTEXT_TOKENS", output=max_ctx or "<unset>")

    # Any non-Claude family reached over a route Claude Code does not natively
    # recognize needs an explicit window declaration. context-bar.sh has static
    # fallbacks for GPT plus exact z-ai/glm-5.2 and terminal date snapshots, but
    # T0.4 still requires explicit declarations for non-Claude routes because
    # dynamic/headless resolution is not guaranteed in every smoke-test context.
    # It is NOT enough to check family=="gpt": shim routes always need a
    # declaration, and on OpenRouter ANY non-Claude family (gpt, glm, unknown)
    # needs one. Native Claude [1m] slugs and Anthropic-recognized models resolve
    # natively.
    needs_declaration = (
        route_info.detected_route in SHIM_ROUTES
        or route_info.model_family == "gpt"
        or (route_info.detected_route == ROUTE_OPENROUTER
            and route_info.model_family != "claude")
    )

    has_1m = model.strip().endswith("[1m]")
    has_max = bool(max_ctx and str(max_ctx).strip().isdigit())
    has_auto = bool(auto_compact and str(auto_compact).strip().isdigit())

    if not needs_declaration:
        r.verdict = Verdict.INFO
        r.detail = "Model window resolves natively for this family; explicit declaration not required."
    elif has_1m or has_max or has_auto:
        r.verdict = Verdict.PASS
        r.detail = "Context window explicitly declared ([1m] suffix or CLAUDE_CODE_MAX_CONTEXT_TOKENS/AUTO_COMPACT_WINDOW)."
    else:
        r.verdict = Verdict.FAIL
        r.detail = (
            f"Non-Claude/shim model ({route_info.model_family} family, "
            f"{route_info.detected_route} route) configured without a [1m] slug suffix "
            "or CLAUDE_CODE_MAX_CONTEXT_TOKENS — Claude Code will silently assume ~200k, "
            "under-reporting the real window (known silent failure)."
        )
    return r
