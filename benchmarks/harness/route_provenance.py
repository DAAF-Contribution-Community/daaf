"""Fail-closed route provenance for DAAFBench ChatGPT-subscription runs.

The registry may construct child-process environment overrides without touching
the network. Health I/O occurs only when ``preflight_models`` or
``revalidate_route`` is called explicitly by a runner/executor.
"""

from __future__ import annotations

import json
import os
import re
import socket
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from benchmarks.harness.models import ModelConfig, RouteProvenance


DEFAULT_SHIM_PORT = 4141
HEALTH_BODY_LIMIT = 16_384
CHATGPT_PROVIDER = "chatgpt-subscription"
EXPECTED_CODEX_BACKEND = "https://chatgpt.com/backend-api/codex"
EXPECTED_SHIM_SERVICE = "daaf-anthropic-openai-shim"
LOCAL_AUTH_PLACEHOLDER = "daaf-shim-local"
GPT_REQUEST_TIERS = {"chatgpt": "priority", "openai": "priority"}
GPT_POLICY_STATUSES = frozenset({"ok", "missing", "invalid", "unreadable", "unsafe"})
GPT_REQUEST_SOURCES = frozenset({"none", "anthropic", "shim_global", "both"})
GPT_SERVED_TIERS = frozenset({"fast", "priority", "default", "flex", "scale", "auto"})
GPT_UTC_SECOND_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
GPT_SERVICE_TIER_KEYS = frozenset({
    "backend_mode",
    "requested_tier_vocabulary",
    "policy",
    "native_fast_disabled",
    "latest_terminal",
})
GPT_POLICY_KEYS = frozenset({"status", "backend_mode", "enabled", "effective"})
GPT_LATEST_TERMINAL_KEYS = frozenset({
    "model",
    "requested_service_tier",
    "requested_source",
    "served_service_tier",
    "completed_at",
})
# Deliberately explicit rather than derived from the dataclass: adding an
# internal field must not silently widen the serialization boundary.
PROVENANCE_ALLOWLIST = frozenset({
    "route_type",
    "provider",
    "endpoint_origin",
    "backend_mode",
    "backend",
    "shim_version",
    "sanitizer_enabled",
    "sanitizer_condition",
    "auth_store_readable",
    "reasoning_effort",
    "text_verbosity",
    "captured_at",
    "gpt_requested_tier_vocabulary",
    "gpt_policy_status",
    "gpt_policy_backend_mode",
    "gpt_policy_enabled",
    "gpt_policy_effective",
    "native_fast_disabled",
})


class RouteContractError(RuntimeError):
    """Raised when the declared ChatGPT-subscription route is not coherent."""


class _DuplicateHealthKeyError(ValueError):
    pass


class _RejectRedirects(HTTPRedirectHandler):
    """Turn loopback redirects into HTTP errors instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _default_health_opener(url: str, *, timeout: float):
    request = Request(url, method="GET")
    opener = build_opener(ProxyHandler({}), _RejectRedirects())
    return opener.open(request, timeout=timeout)


def _reject_duplicate_health_keys(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateHealthKeyError(key)
        value[key] = item
    return value


def _canonical_port(raw_port: object) -> int:
    try:
        port = int(str(raw_port))
    except (TypeError, ValueError) as exc:
        raise RouteContractError(f"Invalid local shim port: {raw_port!r}") from exc
    if not 1 <= port <= 65535:
        raise RouteContractError(f"Local shim port is out of range: {port}")
    return port


def canonicalize_local_endpoint(
    endpoint: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Return a canonical HTTP origin for the loopback-only provider shim.

    Selection order is an explicit endpoint, ``SHIM_PORT``, an ambient local
    ``ANTHROPIC_BASE_URL`` port, then the documented default port 4141. The
    returned host is always ``127.0.0.1`` and never includes credentials, a
    path, query, or fragment.
    """
    env = os.environ if environ is None else environ
    candidate = endpoint
    if candidate is None and env.get("SHIM_PORT"):
        port = _canonical_port(env["SHIM_PORT"])
        return f"http://127.0.0.1:{port}"
    if candidate is None and env.get("ANTHROPIC_BASE_URL"):
        candidate = env["ANTHROPIC_BASE_URL"]
    if candidate is None:
        return f"http://127.0.0.1:{DEFAULT_SHIM_PORT}"

    parsed = urlsplit(candidate)
    if parsed.scheme.lower() != "http":
        raise RouteContractError("Local shim endpoint must use http")
    if parsed.username is not None or parsed.password is not None:
        raise RouteContractError("Local shim endpoint must not contain credentials")
    if (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise RouteContractError("ChatGPT-subscription endpoint must be loopback-only")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RouteContractError("Local shim endpoint must be an origin without path/query/fragment")
    try:
        port = parsed.port or DEFAULT_SHIM_PORT
    except ValueError as exc:
        raise RouteContractError("Local shim endpoint contains an invalid port") from exc
    return f"http://127.0.0.1:{_canonical_port(port)}"


def build_chatgpt_child_env(
    environ: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Build non-secret route overrides for the benchmark child process only.

    Registry loading must also work in non-shim deployments, so an unrelated
    ambient ``ANTHROPIC_BASE_URL`` is not adopted here. Only the documented
    ``SHIM_PORT`` control can change the local target; preflight later requires
    ambient route coherence before any process launch.
    """
    env = os.environ if environ is None else environ
    port = _canonical_port(env.get("SHIM_PORT", DEFAULT_SHIM_PORT))
    endpoint = f"http://127.0.0.1:{port}"
    return {
        "ANTHROPIC_BASE_URL": endpoint,
        "ANTHROPIC_AUTH_TOKEN": LOCAL_AUTH_PLACEHOLDER,
        "ANTHROPIC_API_KEY": "",
    }


def validate_ambient_route(
    environ: Optional[Mapping[str, str]] = None,
    endpoint: Optional[str] = None,
) -> str:
    """Require that ambient deployment state truthfully describes this route."""
    env = os.environ if environ is None else environ
    canonical = canonicalize_local_endpoint(endpoint=endpoint, environ=env)

    # This is the benchmark/provider execution boundary, not a user-input parser.
    # Exact ambient controls are required so case, whitespace, or an omitted backend
    # cannot be normalized into a privileged GPT provider-shim route.
    if env.get("DAAF_PROVIDER_SHIM") != "openai":
        raise RouteContractError("DAAF_PROVIDER_SHIM must be exactly 'openai'")
    if env.get("SHIM_BACKEND_MODE") != "chatgpt":
        raise RouteContractError("SHIM_BACKEND_MODE must be exactly 'chatgpt'")
    if env.get("CLAUDE_CODE_DISABLE_FAST_MODE") != "1":
        raise RouteContractError(
            "CLAUDE_CODE_DISABLE_FAST_MODE must be exactly '1' for GPT provider-shim benchmarking"
        )

    ambient_base = env.get("ANTHROPIC_BASE_URL")
    if ambient_base:
        ambient_canonical = canonicalize_local_endpoint(
            endpoint=ambient_base,
            environ=env,
        )
        if ambient_canonical != canonical:
            raise RouteContractError(
                "Ambient ANTHROPIC_BASE_URL disagrees with the configured local shim endpoint"
            )
    return canonical


def _read_health_response(response) -> dict:
    status = getattr(response, "status", None)
    if status is None and hasattr(response, "getcode"):
        status = response.getcode()
    if status is not None and status != 200:
        raise RouteContractError(f"Shim /health returned HTTP {status}")
    raw = response.read(HEALTH_BODY_LIMIT + 1)
    if len(raw) > HEALTH_BODY_LIMIT:
        raise RouteContractError("Shim /health response exceeded the 16 KiB limit")
    body = raw.decode("utf-8", "replace")
    try:
        payload = json.loads(body, object_pairs_hook=_reject_duplicate_health_keys)
    except (json.JSONDecodeError, _DuplicateHealthKeyError) as exc:
        raise RouteContractError("Shim /health returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RouteContractError("Shim /health JSON must be an object")
    return payload


def _bounded_terminal_model(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", value) is not None
    )


def _canonical_utc_second(value: object) -> bool:
    if not isinstance(value, str) or GPT_UTC_SECOND_RE.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, ValueError):
        return False
    return True


def _validate_latest_terminal(value: object, backend: str) -> None:
    if not isinstance(value, dict) or set(value) != GPT_LATEST_TERMINAL_KEYS:
        raise RouteContractError(
            "Shim /health latest_terminal must have the exact v1.3.9 key set"
        )
    model = value.get("model")
    if model is not None and not _bounded_terminal_model(model):
        raise RouteContractError("Shim /health latest_terminal model is invalid")
    requested = value.get("requested_service_tier")
    source = value.get("requested_source")
    served = value.get("served_service_tier")
    if requested is not None and requested != GPT_REQUEST_TIERS[backend]:
        raise RouteContractError(
            "Shim /health latest_terminal requested tier is invalid for the route"
        )
    if type(source) is not str or source not in GPT_REQUEST_SOURCES:
        raise RouteContractError(
            "Shim /health latest_terminal requested source is invalid"
        )
    if (source == "none") is not (requested is None):
        raise RouteContractError(
            "Shim /health latest_terminal requested source and tier are incoherent"
        )
    if served is not None and (
        type(served) is not str or served not in GPT_SERVED_TIERS
    ):
        raise RouteContractError("Shim /health latest_terminal served tier is invalid")
    if not _canonical_utc_second(value.get("completed_at")):
        raise RouteContractError(
            "Shim /health latest_terminal completion time is invalid"
        )


def _validate_gpt_service_tier_block(
    block: object,
    expected_backend_mode: str,
) -> dict[str, object]:
    """Validate the exact v1.3.9 tier block and return its safe projection.

    ``latest_terminal`` is validated because malformed shim-global history makes
    the health contract untrustworthy, but it is intentionally not returned. A
    prior process-global terminal cannot establish what served a benchmark run.
    """
    if expected_backend_mode not in GPT_REQUEST_TIERS:
        raise RouteContractError("Unsupported GPT service-tier backend mode")
    if not isinstance(block, dict) or set(block) != GPT_SERVICE_TIER_KEYS:
        raise RouteContractError(
            "Shim /health gpt_service_tier must have the exact v1.3.9 key set"
        )

    backend_mode = block.get("backend_mode")
    if backend_mode != expected_backend_mode:
        raise RouteContractError(
            "Shim /health gpt_service_tier backend_mode must match the route"
        )
    requested_vocabulary = block.get("requested_tier_vocabulary")
    if requested_vocabulary != GPT_REQUEST_TIERS[expected_backend_mode]:
        raise RouteContractError(
            "Shim /health gpt_service_tier requested vocabulary is invalid for the route"
        )
    native_fast_disabled = block.get("native_fast_disabled")
    if native_fast_disabled is not True:
        raise RouteContractError(
            "Shim /health gpt_service_tier native_fast_disabled must be JSON boolean true"
        )

    policy = block.get("policy")
    if not isinstance(policy, dict) or set(policy) != GPT_POLICY_KEYS:
        raise RouteContractError(
            "Shim /health gpt_service_tier policy must have the exact v1.3.9 key set"
        )
    policy_status = policy.get("status")
    policy_backend = policy.get("backend_mode")
    policy_enabled = policy.get("enabled")
    policy_effective = policy.get("effective")
    if type(policy_status) is not str or policy_status not in GPT_POLICY_STATUSES:
        raise RouteContractError("Shim /health gpt_service_tier policy status is invalid")
    if policy_backend is not None and (
        type(policy_backend) is not str
        or policy_backend not in GPT_REQUEST_TIERS
    ):
        raise RouteContractError("Shim /health gpt_service_tier policy backend is invalid")
    if type(policy_enabled) is not bool or type(policy_effective) is not bool:
        raise RouteContractError(
            "Shim /health gpt_service_tier policy flags must be booleans"
        )
    if policy_status != "ok":
        if policy_backend is not None or policy_enabled or policy_effective:
            raise RouteContractError(
                "Shim /health non-ok GPT tier policy must fail safely off"
            )
    else:
        if policy_backend is None:
            raise RouteContractError(
                "Shim /health ok GPT tier policy must name its bound backend"
            )
        expected_effective = bool(
            policy_enabled and policy_backend == expected_backend_mode
        )
        if policy_effective is not expected_effective:
            raise RouteContractError(
                "Shim /health GPT tier policy effective flag is incoherent"
            )

    latest = block.get("latest_terminal")
    if latest is not None:
        _validate_latest_terminal(latest, expected_backend_mode)

    return {
        "gpt_requested_tier_vocabulary": requested_vocabulary,
        "gpt_policy_status": policy_status,
        "gpt_policy_backend_mode": policy_backend,
        "gpt_policy_enabled": policy_enabled,
        "gpt_policy_effective": policy_effective,
        "native_fast_disabled": native_fast_disabled,
    }


def _validate_health_payload(health: Mapping[str, object], endpoint: str) -> RouteProvenance:
    problems = []
    if health.get("service") != EXPECTED_SHIM_SERVICE:
        problems.append(f"service must equal '{EXPECTED_SHIM_SERVICE}'")
    if health.get("status") != "ok":
        problems.append("status must equal 'ok'")
    if health.get("backend_mode") != "chatgpt":
        problems.append("backend_mode must equal 'chatgpt'")
    if health.get("sanitize_tools") is not True:
        problems.append("sanitize_tools must be boolean true")
    if health.get("codex_home_present") is not True:
        problems.append("codex_home_present must be boolean true")

    backend = health.get("backend")
    if not isinstance(backend, str) or backend.rstrip("/") != EXPECTED_CODEX_BACKEND:
        problems.append(f"backend must equal '{EXPECTED_CODEX_BACKEND}'")
    version = health.get("version")
    if (
        not isinstance(version, str)
        or not re.fullmatch(r"[A-Za-z0-9._+-]{1,64}", version.strip())
    ):
        problems.append("version must be a nonempty, safe version identifier")
    if problems:
        raise RouteContractError("Shim /health contract failed: " + "; ".join(problems))

    tier_provenance = _validate_gpt_service_tier_block(
        health.get("gpt_service_tier"), "chatgpt"
    )
    reasoning = health.get("reasoning_effort")
    if reasoning not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
        reasoning = None
    verbosity = health.get("text_verbosity")
    if verbosity not in {"low", "medium", "high"}:
        verbosity = None
    return RouteProvenance(
        route_type="chatgpt_subscription_shim",
        provider=CHATGPT_PROVIDER,
        endpoint_origin=endpoint,
        backend_mode="chatgpt",
        backend=backend.rstrip("/"),
        shim_version=version.strip(),
        sanitizer_enabled=True,
        sanitizer_condition="deployed_default",
        auth_store_readable=True,
        reasoning_effort=reasoning if isinstance(reasoning, str) else None,
        text_verbosity=verbosity if isinstance(verbosity, str) else None,
        captured_at=datetime.now(timezone.utc).isoformat(),
        **tier_provenance,
    )


def fetch_route_provenance(
    environ: Optional[Mapping[str, str]] = None,
    opener: Optional[Callable] = None,
    timeout: float = 10.0,
) -> RouteProvenance:
    """Validate ambient state and live health, returning allowlisted provenance."""
    endpoint = validate_ambient_route(environ=environ)
    health_url = endpoint + "/health"
    network_opener = opener or _default_health_opener
    try:
        response = network_opener(health_url, timeout=timeout)
        if hasattr(response, "__enter__"):
            with response as opened:
                health = _read_health_response(opened)
        else:
            health = _read_health_response(response)
    except RouteContractError:
        raise
    except (HTTPError, URLError, socket.timeout, OSError) as exc:
        raise RouteContractError(
            f"Local shim /health is unreachable: {type(exc).__name__}: {exc}"
        ) from exc
    return _validate_health_payload(health, endpoint)


def safe_provenance_dict(provenance: RouteProvenance) -> dict:
    """Serialize only the explicit provenance allowlist."""
    values = asdict(provenance)
    return {key: values[key] for key in PROVENANCE_ALLOWLIST}


def preflight_models(
    models: Iterable[ModelConfig],
    environ: Optional[Mapping[str, str]] = None,
    opener: Optional[Callable] = None,
    timeout: float = 10.0,
) -> dict[str, RouteProvenance]:
    """Run one zero-model-cost route preflight for selected ChatGPT models."""
    selected = [model for model in models if model.provider == CHATGPT_PROVIDER]
    if not selected:
        return {}
    provenance = fetch_route_provenance(environ=environ, opener=opener, timeout=timeout)
    return {(model.key or model.id): provenance for model in selected}


def revalidate_route(
    model: ModelConfig,
    environ: Optional[Mapping[str, str]] = None,
    opener: Optional[Callable] = None,
    timeout: float = 10.0,
) -> Optional[RouteProvenance]:
    """Revalidate a model route immediately before process launch."""
    if model.provider != CHATGPT_PROVIDER:
        return None
    return fetch_route_provenance(environ=environ, opener=opener, timeout=timeout)
