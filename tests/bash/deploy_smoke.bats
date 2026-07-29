#!/usr/bin/env bats
# ============================================================================
# Tests for deploy-smoke application helpers
# ============================================================================
# These are zero-network unit checks. They import the application module but do
# not run any deployment tier, provider request, or filesystem-writing probe.
# ============================================================================

load 'test_helper'

SMOKE_PROBES_DIR="${REPO_ROOT}/scripts/deploy_smoke"

setup() {
    common_setup
    export SMOKE_PROBES_DIR
}

teardown() {
    common_teardown
}

@test "wide-context classifier keeps GLM-5.2 matching exact and suffix-safe" {
    run env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${SMOKE_PROBES_DIR}:${REPO_ROOT}" python3 -c '
import smoke_probes

expected = {
    "z-ai/glm-5.2": True,
    "z-ai/glm-5.2-20260715": True,
    "z-ai/glm-5.2-air": False,
    "z-ai/glm-5.2-preview": False,
    "z-ai/glm-5.2-20260715-extra": False,
    "z-ai/glm-5.2-2026071": False,
    "gpt-5.6-sol": True,
    "claude-opus-4-8[1m]": True,
    "claude-sonnet-4-6": False,
}
for model_id, want in expected.items():
    got = smoke_probes._is_wide_context_model(model_id)
    assert got is want, (model_id, got, want)
print("wide-context classifier: 9/9 cases passed")
'
    assert_success
    assert_output "wide-context classifier: 9/9 cases passed"
}

@test "route detection enforces exact shim lane controls and explains near misses" {
    run env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${SMOKE_PROBES_DIR}:${REPO_ROOT}" python3 -c '
from route_detection import (
    ROUTE_ANTHROPIC,
    ROUTE_CHATGPT,
    ROUTE_OPENAI_API,
    ROUTE_OPENROUTER,
    Verdict,
    build_route_info,
    probe_route_detection,
)

cases = [
    ("clean native controls", {}, ROUTE_ANTHROPIC, Verdict.PASS),
    ("clean OpenRouter controls", {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api"}, ROUTE_OPENROUTER, Verdict.PASS),
    ("exact ChatGPT conjunction", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "chatgpt"}, ROUTE_CHATGPT, Verdict.PASS),
    ("exact OpenAI conjunction", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "openai"}, ROUTE_OPENAI_API, Verdict.PASS),
    ("uppercase shim", {"DAAF_PROVIDER_SHIM": "OPENAI", "SHIM_BACKEND_MODE": "chatgpt"}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("leading-space shim", {"DAAF_PROVIDER_SHIM": " openai", "SHIM_BACKEND_MODE": "chatgpt"}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("trailing-space shim", {"DAAF_PROVIDER_SHIM": "openai ", "SHIM_BACKEND_MODE": "chatgpt"}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("uppercase backend", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "CHATGPT"}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("leading-space backend", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": " chatgpt"}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("trailing-space backend", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "chatgpt "}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("partial shim", {"DAAF_PROVIDER_SHIM": "open"}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("partial backend", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "chat"}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("only shim signal", {"DAAF_PROVIDER_SHIM": "openai"}, ROUTE_ANTHROPIC, Verdict.FAIL),
    ("only backend signal", {"SHIM_BACKEND_MODE": "chatgpt"}, ROUTE_ANTHROPIC, Verdict.FAIL),
]
for label, env, route, verdict in cases:
    info = build_route_info(env)
    got = probe_route_detection(info)
    assert info.detected_route == route, (label, info.detected_route, route)
    assert got.verdict == verdict, (label, got.verdict, verdict, got.detail)
    if verdict == Verdict.FAIL:
        assert "exact" in got.detail.lower(), (label, got.detail)
print("exact lane controls: 14/14 cases passed")
'
    assert_success
    assert_output "exact lane controls: 14/14 cases passed"
}

@test "GPT physical-family classifier mirrors runtime boundaries and mappings" {
    run env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${SMOKE_PROBES_DIR}:${REPO_ROOT}" python3 -c '
from route_detection import _gpt_physical_window

expected = {
    "gpt-5": 400000,
    "gpt-5.2": 400000,
    "openai/gpt-5.2-20251211": 400000,
    "gpt-5-chat": 128000,
    "gpt-5.4": 1050000,
    "vendor/openai/gpt-5.5[1m]": 1050000,
    "gpt-5.6-sol": 1050000,
    "openai/gpt-5.6-terra": 1050000,
    "gpt-5.6-luna[1m]": 1050000,
    "gpt-5.6-sol-mini": 400000,
    "gpt-5.6-sol-chat": 128000,
    "gpt-5.6-sol-extra": 1050000,
    "vendor/notgpt-5.6-sol": None,
    "xgpt-5.6-sol": None,
    "foo-gpt-5.6-sol": None,
    "gpt-5.60": None,
    "gpt-5.6sol": None,
    "gpt-5.6+trailing": None,
}
for model_id, want in expected.items():
    got = _gpt_physical_window(model_id)
    assert got == want, (model_id, got, want)
print("GPT physical mapping: 18/18 cases passed")
'
    assert_success
    assert_output "GPT physical mapping: 18/18 cases passed"
}

@test "route diagnostic enforces canonical decimal and all four effective GPT selectors" {
    run env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${SMOKE_PROBES_DIR}:${REPO_ROOT}" python3 -c '
from route_detection import (
    MODEL_SELECTOR_VARS,
    Verdict,
    _is_canonical_positive_decimal,
    build_route_info,
    probe_context_window_coherence,
)

valid = ["1", "370000", "9223372036854775807"]
invalid = [None, "", "0", "+370000", "-1", " 370000", "370000 ", "0370000", "370000.0", "3.7e5", "9223372036854775808"]
for value in valid:
    assert _is_canonical_positive_decimal(value), value
for value in invalid:
    assert not _is_canonical_positive_decimal(value), value

base = {
    "DAAF_PROVIDER_SHIM": "openai",
    "SHIM_BACKEND_MODE": "chatgpt",
    "ANTHROPIC_MODEL": "claude-opus-4-8[1m]",
}
for selector in MODEL_SELECTOR_VARS:
    env = {**base, selector: "gpt-5.6-sol[1m]", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000"}
    got = probe_context_window_coherence(build_route_info(env), env)
    assert got.verdict == Verdict.FAIL, (selector, got.verdict, got.detail)
    assert selector in got.detail, (selector, got.detail)

    for declaration in ("370000", "250000", "1"):
        aligned = {**env, "CLAUDE_CODE_MAX_CONTEXT_TOKENS": declaration}
        got = probe_context_window_coherence(build_route_info(aligned), aligned)
        assert got.verdict == Verdict.PASS, (selector, declaration, got.verdict, got.detail)

all_mapped = {
    "DAAF_PROVIDER_SHIM": "openai",
    "SHIM_BACKEND_MODE": "chatgpt",
    "ANTHROPIC_MODEL": "gpt-5.4",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-5.5",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "gpt-5.6-terra",
    "CLAUDE_CODE_SUBAGENT_MODEL": "gpt-5.6-sol[1m]",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000",
}
got = probe_context_window_coherence(build_route_info(all_mapped), all_mapped)
assert got.verdict == Verdict.FAIL, got.detail
for selector in MODEL_SELECTOR_VARS:
    assert selector in got.detail, (selector, got.detail)

for declaration in invalid[1:]:
    env = {**base, "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-5.6-sol", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": declaration}
    got = probe_context_window_coherence(build_route_info(env), env)
    assert got.verdict == Verdict.FAIL, (declaration, got.verdict, got.detail)
    assert "canonical positive decimal" in got.detail, (declaration, got.detail)
print("canonical declarations and selector remaps: 41/41 cases passed")
'
    assert_success
    assert_output "canonical declarations and selector remaps: 41/41 cases passed"
}

@test "route diagnostic keeps wide routes and non-flagship controls separate" {
    run env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${SMOKE_PROBES_DIR}:${REPO_ROOT}" python3 -c '
from route_detection import Verdict, build_route_info, probe_context_window_coherence

base_chatgpt = {
    "DAAF_PROVIDER_SHIM": "openai",
    "SHIM_BACKEND_MODE": "chatgpt",
}
cases = [
    ("missing exact-lane explicit despite [1m]", {**base_chatgpt, "ANTHROPIC_MODEL": "gpt-5.6-sol[1m]"}, Verdict.FAIL),
    ("auto compact is not protection", {**base_chatgpt, "ANTHROPIC_MODEL": "gpt-5.6-sol", "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "370000"}, Verdict.FAIL),
    ("mini excluded from flagship cap", {**base_chatgpt, "ANTHROPIC_MODEL": "gpt-5.6-sol-mini", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "400000"}, Verdict.PASS),
    ("chat excluded from flagship cap", {**base_chatgpt, "ANTHROPIC_MODEL": "gpt-5.6-sol-chat", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "128000"}, Verdict.PASS),
    ("non-GPT control", {**base_chatgpt, "ANTHROPIC_MODEL": "claude-opus-4-8[1m]"}, Verdict.PASS),
    ("malformed left-boundary GPT is not capped", {**base_chatgpt, "ANTHROPIC_MODEL": "vendor/notgpt-5.6-sol", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000"}, Verdict.PASS),
    ("direct API [1m] hint is supported", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "openai", "ANTHROPIC_MODEL": "gpt-5.6-sol[1m]"}, Verdict.PASS),
    ("direct API bare GPT needs explicit declaration", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "openai", "ANTHROPIC_MODEL": "gpt-5.6-sol"}, Verdict.FAIL),
    ("API route keeps canonical 1.05M", {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "openai", "ANTHROPIC_MODEL": "gpt-5.6-sol[1m]", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000"}, Verdict.PASS),
    ("OpenRouter keeps canonical 1.05M", {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "ANTHROPIC_MODEL": "openai/gpt-5.6-sol", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000"}, Verdict.PASS),
    ("OpenRouter does not generalize [1m]", {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "ANTHROPIC_MODEL": "openai/gpt-5.6-sol[1m]"}, Verdict.FAIL),
    ("native route rejects an explicit overflow declaration", {"ANTHROPIC_MODEL": "claude-opus-4-8[1m]", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "9223372036854775808"}, Verdict.FAIL),
]
for label, env, want in cases:
    got = probe_context_window_coherence(build_route_info(env), env)
    assert got.verdict == want, (label, got.verdict, want, got.detail)
print("route and model controls: 12/12 cases passed")
'
    assert_success
    assert_output "route and model controls: 12/12 cases passed"
}
