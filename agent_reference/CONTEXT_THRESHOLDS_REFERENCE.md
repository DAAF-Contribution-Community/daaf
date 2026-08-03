# Context Threshold Profile-Selection Reference

This document is the **canonical home for the context-threshold profile-selection
mechanics** — the version-specific rules that determine which Context Quality Curve
threshold profile the `context-reporter` hook (and the statusline scripts) apply to
a given agent, keyed off that agent's own exact model ID. CLAUDE.md § Context &
Session Health carries the operational summary and the four severity levels; this
reference carries the full selection prose (Sol slug rules, provider prefixes,
malformed-boundary examples, the physical-window-vs-profile separation, the
Codex ~370k lane cap, and the `claude-opus-4-8[1m]` example) so the mechanics live
in one place and CLAUDE.md stays lean.

The `context-reporter` hook computes severity on each agent's behalf — agents act
on the reported severity level, never on their own profile inference. This
reference documents *how* that selection is made, for transparency and maintenance.

## Profile Selection

The hook selects among three profiles from each agent's own exact model ID: Claude Fable/Mythos, exact terminal GPT 5.6 Sol, and the conservative default used by Opus, Sonnet, unknown model IDs, every other GPT variant, GLM models, and all other alternative-provider models unless individually validated and registered.

Profile selection is deliberately version-specific and independent of physical context-window mapping. The validated extended-horizon profile recognizes the registered Claude Fable/Mythos identifiers (currently the `fable-5` and `mythos-5` generations). Exact GPT 5.6 Sol has a separate validated profile: it shares the standard 40%/60%/75% percentage boundaries (also used by the conservative default) while retaining higher validated absolute gates (300k/400k/500k). For this exact-Sol profile, the terminal model slug must be exactly `gpt-5.6-sol` or `gpt-5.6-sol[1m]`; the identifier may be bare or may contain one or more provider path prefixes ending in `/`. Malformed left-boundary strings such as `xgpt-5.6-sol`, `foo-gpt-5.6-sol`, and `vendor/notgpt-5.6-sol` remain conservative, as do right-side suffix or trailing variants. GPT is not part of the Claude Fable/Mythos model family. Terra, Luna, Pro, mini, chat, date snapshots, future variants, and identifiers with any other trailing modifier remain conservative unless separately validated and registered. Physical capacity remains a separate lookup: GPT models in the wider mapped family may map to a 1,050,000-token physical window on API/OpenRouter routes, while the ChatGPT-subscription (Codex) lane is backend-capped at approximately 370,000 tokens (measured for Sol on 2026-07-16 and lane-gated by the hooks through `DAAF_PROVIDER_SHIM` + `SHIM_BACKEND_MODE`). At that approximately 370,000-token cap, exact Sol's 40%/60%/75% percentage boundaries are 148k, 222k, and 277.5k tokens, respectively, and therefore fire before its 300k/400k/500k absolute gates. Likewise, `claude-opus-4-8[1m]` has a 1M-token physical window but remains conservative because physical capacity and quality-threshold profile are separate lookups.

## Trigger Points by Threshold Profile

Reproduced here for self-containedness (this table is also maintained in
CLAUDE.md § Context Quality Curve). Percentage OR absolute tokens, whichever fires
first:

| Threshold Profile | Membership | ELEVATED at | HIGH at | CRITICAL at |
|-------------------|------------|-------------|---------|-------------|
| **Claude Fable/Mythos validated extended-horizon** | Registered Claude Fable/Mythos models | ≥ 30% or ≥ 300k tokens | ≥ 40% or ≥ 400k tokens | ≥ 50% or ≥ 500k tokens |
| **Exact GPT 5.6 Sol validated** | Exact terminal model slugs, bare or provider-prefixed: `gpt-5.6-sol` or `gpt-5.6-sol[1m]` | ≥ 40% or ≥ 300k tokens | ≥ 60% or ≥ 400k tokens | ≥ 75% or ≥ 500k tokens |
| **Conservative-default** | Opus, Sonnet, unknown model IDs, every other GPT variant, GLM models, and all other alternative-provider models unless individually validated and registered | ≥ 40% or ≥ 150k tokens | ≥ 60% or ≥ 200k tokens | ≥ 75% or ≥ 250k tokens |

The four severity **levels and their required actions are identical** across all
three profiles — only the trigger points differ. For the level definitions and
required actions (NOMINAL / ELEVATED / HIGH / CRITICAL), see CLAUDE.md § Context
Quality Curve.
