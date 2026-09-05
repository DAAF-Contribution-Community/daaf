# Context Threshold Profile-Selection Reference

This document is the **canonical home for the context-threshold profile-selection
mechanics** — the version-specific rules that determine which Context Quality Curve
threshold profile the `context-reporter` hook (and the statusline scripts) apply to
a given agent, keyed off that agent's own exact model ID. CLAUDE.md § Context &
Session Health carries the operational summary and the four severity levels; this
reference carries the full selection prose (Sol/Astra slug rules, provider prefixes,
malformed-boundary examples, the physical-window-vs-profile separation, the
Codex ~919k lane cap, and the `claude-opus-4-8[1m]` example) so the mechanics live
in one place and CLAUDE.md stays lean.

The `context-reporter` hook computes severity on each agent's behalf — agents act
on the reported severity level, never on their own profile inference. This
reference documents *how* that selection is made, for transparency and maintenance.

## Profile Selection

The hook selects among three profiles from each agent's own exact model ID: Claude Fable/Mythos, exact terminal GPT Sol/Astra, and the conservative default used by Opus, Sonnet, unknown model IDs, every other GPT variant, GLM models, and all other alternative-provider models unless individually validated and registered.

Profile selection is deliberately version-specific and independent of physical context-window mapping. The validated extended-horizon profile recognizes the registered Claude Fable/Mythos identifiers (currently the `fable-5` and `mythos-5` generations). Exact GPT 5.6 Sol and GPT-6 Astra share a separate validated profile with independent 60%/75%/90% percentage boundaries and higher validated absolute gates (300k/400k/500k); Astra joins this same extended-horizon profile at Sol parity, and Sol's own tier history is unchanged. For this exact-Sol/Astra profile, the terminal model slug must be exactly `gpt-5.6-sol`, `gpt-5.6-sol[1m]`, `gpt-6-astra`, or `gpt-6-astra[1m]`; the identifier may be bare or may contain one or more provider path prefixes ending in `/`. Malformed left-boundary strings such as `xgpt-5.6-sol`, `foo-gpt-5.6-sol`, and `vendor/notgpt-5.6-sol` remain conservative, as do right-side suffix or trailing variants (including near-misses such as `gpt-6-astra-pro`). GPT is not part of the Claude Fable/Mythos model family. Terra, Luna, Pro, mini, chat, date snapshots, future variants, and identifiers with any other trailing modifier remain conservative unless separately validated and registered. Physical capacity remains a separate lookup: GPT models in the wider mapped family may map to a 1,050,000-token physical window on API/OpenRouter routes (Astra's physical window is 1,050,000 tokens, with a 128,000-token max output), while the ChatGPT-subscription (Codex) lane is backend-capped at **919,000 tokens**, measured directly for both `gpt-6-astra` and `gpt-5.6-sol` on 2026-09-05 and lane-gated by the hooks through `DAAF_PROVIDER_SHIM` + `SHIM_BACKEND_MODE`. This lane-wide cap is measured, not provisional: the 2026-09-05 probes accepted 919,053 real input tokens on Astra and 910,827 on Sol while rejecting 922,552 and 921,973 respectively, which is consistent with Astra's documented 922,000-token maximum input (1,050,000 window − 128,000 max output). (An earlier 2026-07-16 Sol probe reported approximately 370,000 tokens; that figure is superseded and no longer describes the lane.) At the 919,000-token cap, the exact-Sol/Astra 60%/75%/90% percentage boundaries are 551.4k, 689.25k, and 827.1k tokens, respectively, so the 300k/400k/500k absolute gates fire first — the same ordering as on the full window. At a 1,050,000-token full window, the corresponding percentage boundaries are 630k, 787.5k, and 945k, so the unchanged 300k/400k/500k absolute gates likewise fire first and preserve full-window behavior. Likewise, `claude-opus-4-8[1m]` has a 1M-token physical window but remains conservative because physical capacity and quality-threshold profile are separate lookups. The same separation applies to **Opus 5**: `claude-opus-5` maps to a 1,000,000-token physical window in **both** its bare and `[1m]` forms — observed 2026-09-05 on Claude Code 2.1.261 via `/model` + `/context`, where bare `claude-opus-5` reported "42.8k/1m tokens" and `claude-opus-5[1m]` reported "48.2k/1m" — while its quality-threshold profile stays conservative-default per its Opus-class membership. The window map is registered in `.claude/scripts/subagent-bar.sh` and `.claude/hooks/context-reporter.sh`; the profile-selection globs (`*fable-5*|*mythos-5*`) are deliberately left untouched.

## Trigger Points by Threshold Profile

Reproduced here for self-containedness (this table is also maintained in
CLAUDE.md § Context Quality Curve). Percentage OR absolute tokens, whichever fires
first:

| Threshold Profile | Membership | ELEVATED at | HIGH at | CRITICAL at |
|-------------------|------------|-------------|---------|-------------|
| **Claude Fable/Mythos validated extended-horizon** | Registered Claude Fable/Mythos models | ≥ 30% or ≥ 300k tokens | ≥ 40% or ≥ 400k tokens | ≥ 50% or ≥ 500k tokens |
| **Exact GPT Sol/Astra validated** | Exact terminal model slugs, bare or provider-prefixed: `gpt-5.6-sol`, `gpt-5.6-sol[1m]`, `gpt-6-astra`, or `gpt-6-astra[1m]` | ≥ 60% or ≥ 300k tokens | ≥ 75% or ≥ 400k tokens | ≥ 90% or ≥ 500k tokens |
| **Conservative-default** | Opus, Sonnet, unknown model IDs, every other GPT variant, GLM models, and all other alternative-provider models unless individually validated and registered | ≥ 40% or ≥ 150k tokens | ≥ 60% or ≥ 200k tokens | ≥ 75% or ≥ 250k tokens |

The four severity **levels and their required actions are identical** across all
three profiles — only the trigger points differ. For the level definitions and
required actions (NOMINAL / ELEVATED / HIGH / CRITICAL), see CLAUDE.md § Context
Quality Curve.
