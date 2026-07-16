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
