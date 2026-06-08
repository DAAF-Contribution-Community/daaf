"""Shared model loading and filtering for benchmark runners.

Loads ModelConfig entries from models.yaml, resolves provider-specific
environment overrides at load time, and provides CLI-friendly filtering
by model key and provider.
"""

import os
import sys
from pathlib import Path

import yaml

from benchmarks.harness.models import ModelConfig


# --- Provider environment wiring ---

# Maps provider names to the environment variable overrides needed for
# claude -p to route API calls to that provider's endpoint.
#
# Values that reference an env var name (e.g. "OPENROUTER_BASE_URL") are
# resolved at load time from os.environ. Empty strings are passed as-is.
PROVIDER_ENV_SPEC = {
    "openrouter": {
        "ANTHROPIC_BASE_URL": "OPENROUTER_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN": "OPENROUTER_AUTH_TOKEN",
        "ANTHROPIC_API_KEY": "",  # blank to prevent X-Api-Key from overriding Bearer
    },
    "anthropic": {
        # Placeholder: when CLAUDE_CODE_OAUTH_TOKEN is available in the
        # environment, inject it so -p mode uses subscription auth explicitly.
        "CLAUDE_CODE_OAUTH_TOKEN": "CLAUDE_CODE_OAUTH_TOKEN",
    },
}


def _resolve_provider_env(provider: str) -> dict[str, str]:
    """Resolve provider env spec to concrete key=value pairs from os.environ.

    Returns the resolved dict. Entries whose source env var is missing are
    silently omitted (the caller decides whether to warn/skip).
    """
    spec = PROVIDER_ENV_SPEC.get(provider, {})
    resolved = {}
    missing = []

    for target_var, source in spec.items():
        if source == "":
            resolved[target_var] = ""
        else:
            value = os.environ.get(source)
            if value is not None:
                resolved[target_var] = value
            else:
                missing.append(source)

    return resolved, missing


def load_models(path: Path) -> dict[str, ModelConfig]:
    """Load model configurations from models.yaml with provider env injection.

    For each model entry, if provider != 'anthropic' (default), resolves
    the provider's env overrides from the current environment and merges
    them into the model's env_overrides dict. YAML-level env_overrides
    take precedence over provider-level ones (more specific wins).

    Returns an ordered dict of key -> ModelConfig.
    Models whose required provider env vars are missing are skipped with a warning.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    models = {}
    skipped_providers = set()

    for m in data.get("models", []):
        config = ModelConfig.from_dict(m)
        provider = config.provider

        if provider in PROVIDER_ENV_SPEC:
            resolved, missing = _resolve_provider_env(provider)

            # For non-default providers, missing critical env vars means skip
            if missing and provider != "anthropic":
                if provider not in skipped_providers:
                    print(
                        f"WARNING: Skipping {provider} models — missing env vars: "
                        f"{', '.join(missing)}",
                        file=sys.stderr,
                    )
                    skipped_providers.add(provider)
                continue

            # Merge: provider env is the base, YAML env_overrides layer on top
            merged = {**resolved, **config.env_overrides}
            config.env_overrides = merged

        key = config.name.lower().replace(" ", "-").replace(".", "")
        models[key] = config

    return models


def filter_models(
    all_models: dict[str, ModelConfig],
    model_keys: list[str] | None = None,
    provider: str | None = None,
) -> list[ModelConfig]:
    """Filter models by key names and/or provider.

    Args:
        all_models: Full dict from load_models().
        model_keys: If set, comma-split list of keys to include.
        provider: If set, one of 'anthropic', 'openrouter', or 'all'.
                  Defaults to 'all' if None.

    Returns list of matching ModelConfig objects.
    """
    candidates = all_models

    # Filter by provider
    if provider and provider != "all":
        candidates = {
            k: v for k, v in candidates.items()
            if v.provider == provider
        }

    # Filter by specific keys
    if model_keys:
        result = []
        for k in model_keys:
            k = k.strip()
            if k in candidates:
                result.append(candidates[k])
            elif k in all_models:
                print(
                    f"WARNING: Model '{k}' exists but excluded by --provider filter",
                    file=sys.stderr,
                )
            else:
                print(
                    f"WARNING: Unknown model key '{k}'. "
                    f"Available: {', '.join(candidates.keys())}",
                    file=sys.stderr,
                )
        return result

    return list(candidates.values())


def add_model_args(parser) -> None:
    """Add --models and --provider arguments to an argparse parser."""
    parser.add_argument(
        "--models", type=str, default=None,
        help="Comma-separated model keys from models.yaml (default: all)",
    )
    parser.add_argument(
        "--provider", type=str, default="all",
        choices=["anthropic", "openrouter", "all"],
        help="Filter models by provider (default: all)",
    )
