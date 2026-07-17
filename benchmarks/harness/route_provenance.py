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
from urllib.request import urlopen

from benchmarks.harness.models import ModelConfig, RouteProvenance


DEFAULT_SHIM_PORT = 4141
CHATGPT_PROVIDER = "chatgpt-subscription"
EXPECTED_CODEX_BACKEND = "https://chatgpt.com/backend-api/codex"
LOCAL_AUTH_PLACEHOLDER = "daaf-shim-local"
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
})


class RouteContractError(RuntimeError):
    """Raised when the declared ChatGPT-subscription route is not coherent."""


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

    if (env.get("DAAF_PROVIDER_SHIM") or "").strip().lower() != "openai":
        raise RouteContractError("DAAF_PROVIDER_SHIM must equal 'openai'")
    if (env.get("SHIM_BACKEND_MODE") or "").strip().lower() != "chatgpt":
        raise RouteContractError("SHIM_BACKEND_MODE must equal 'chatgpt'")

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
    body = response.read().decode("utf-8", "replace")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RouteContractError("Shim /health returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RouteContractError("Shim /health JSON must be an object")
    return payload


def _validate_health_payload(health: Mapping[str, object], endpoint: str) -> RouteProvenance:
    problems = []
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
    )


def fetch_route_provenance(
    environ: Optional[Mapping[str, str]] = None,
    opener: Optional[Callable] = None,
    timeout: float = 10.0,
) -> RouteProvenance:
    """Validate ambient state and live health, returning allowlisted provenance."""
    endpoint = validate_ambient_route(environ=environ)
    health_url = endpoint + "/health"
    network_opener = opener or urlopen
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
