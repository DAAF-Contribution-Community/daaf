# Interpreting Deployment Smoke Results

Probe-by-probe interpretation for the DAAF deployment smoke suite: what each verdict means, which signals are expected mechanics rather than defects, route-conditional expectations, and how to route a real failure to its documented fix. Read this alongside a `report.md` from `scripts/deploy_smoke/reports/{timestamp}_{route}/`.

## Verdict Semantics

| Verdict | Meaning | Affects exit code? |
|---------|---------|--------------------|
| **PASS** | The probe's machinery worked as expected. | no |
| **FAIL** | A real defect for this route. Fix before trusting the deployment. | **yes** (nonzero) |
| **WARN** | Something worth a look, but not necessarily broken. Often expected on short headless runs (see below). | no |
| **SKIP** | Not applicable to the detected route (e.g. shim `/health` on a non-shim route). Correct behavior. | no |
| **INFO** | Informational context (e.g. the model-family/ceiling-hook posture), not a pass/fail signal. | no |

Only **FAIL** flips the overall verdict, matching the `run_all_smoke_tests.sh` contract. When triaging a report, read every FAIL first, then scan WARNs against the "expected mechanics" notes below before treating one as a defect.

The suite is **capability-structural**: Tier 1–2 probes check whether the machinery worked (did a subagent dispatch, did a script run, did a Skill load), *not* whether the model followed DAAF's protocols with high fidelity. Adherence quality is DAAFBench's job. A probe that PASSes confirms the plumbing is intact, not that the model behaves ideally.

---

## Tier 0 — Free Preflight (no LLM)

| Probe | PASS means | FAIL means / how to fix |
|-------|-----------|-------------------------|
| **T0.0 DAAF_DEV assertion** | `DAAF_DEV=1`; development image active. | `DAAF_DEV` not `1`. The deployment smoke suite is intentionally restricted to development images as a contributor tool; the Tier 0 policy gate applies even to `--tiers 0`. Tier D additionally relies on development-only deterministic/test tooling, although an unavailable Tier-D tool can produce a probe-level SKIP. Codex itself ships in every image. Shim routing and `codex login` are separate explicit opt-ins and do not require a development image. Set `DAAF_DEV=1` in the `daaf-docker` `environment_settings.txt` and rebuild. |
| **T0.1 Route detection + assertion** | Detected route reported; matches `--route` if asserted. | `--route` asserted a route the live env does not produce. Detection is authoritative — the expectation is wrong or the env is misconfigured. Reconcile the env vars in the fingerprint against the intended route. |
| **T0.2 Model family** | INFO — reports family (claude/gpt/glm/unknown) and the expected ceiling-hook posture. | Never FAILs. Use it to confirm the ceiling-hook expectation matches intent (see route sections below). |
| **T0.3 Env coherence** | Required vars for the detected route are present and mutually coherent. | Route-specific missing/incoherent var. The `detail` names each problem; see the route sections below for the exact fix. |
| **T0.4 Context-window declaration** | The window resolves natively, or the applicable route-specific check passes. On the direct OpenAI API shim and OpenRouter routes, any valid canonical positive explicit `CLAUDE_CODE_MAX_CONTEXT_TOKENS` value satisfies T0.4; exact equality to `1050000` is not enforced. With no explicit declaration, a supported `[1m]` hint is sufficient only on the direct OpenAI API shim. OpenRouter requires a canonical explicit declaration when its wide window is not otherwise resolved natively; the recommended GPT configuration is a provider-prefixed bare slug such as `openai/gpt-5.6-sol` plus `CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000`, but T0.4 does not enforce that slug form when a valid explicit declaration is present. On the exact ChatGPT-subscription (Codex) shim lane, mapped GPT flagship configurations require a canonical positive explicit declaration no greater than `370000`. | A required declaration is absent, or an explicit declaration is invalid or non-canonical. This includes an unresolved OpenRouter wide-window model with no canonical explicit declaration (`[1m]` alone is insufficient), and an exact ChatGPT-subscription mapped GPT flagship with a missing, invalid, non-canonical, or greater-than-`370000` declaration. On the direct OpenAI API shim, an unresolved model fails only when it has neither a valid canonical explicit declaration nor a supported `[1m]` hint. Claude Code otherwise silently assumes ~200k and under-reports a wide API/OpenRouter window; `[1m]` cannot raise the measured ChatGPT-subscription backend ceiling near ~370k for `gpt-5.6-sol` (measured 2026-07-16). Recommended authoritative values remain `1050000` for the supported 1M GPT API/OpenRouter configuration and `1048576` for exact `z-ai/glm-5.2`. Physical capacity does not change DAAF's model-family quality thresholds. |
| **T0.5 CLI available** | `claude --version` responds. | CLI missing/broken in the container. Rebuild; verify the image. |
| **T0.6 Hook registration** | Every `.claude/hooks/*.sh` is registered in `settings.json` (or is a known per-agent-frontmatter hook like `enforce-file-first.sh`). | A hook script is present but unregistered. A shell overwrite of `settings.json`, or a partial deploy, dropped a registration. Restore the hook chain in `settings.json`. |
| **T0.7 Statusline rendering** | Both `context-bar.sh` and `subagent-bar.sh` render non-empty output against a synthetic payload. | A statusline crashes or emits nothing. These are fail-open scripts (a crash still exits 0), so empty output is the real signal — inspect the script against the synthetic payload schema. |
| **T0.8 Shim /health** | (shim routes) `backend_mode` matches the route; `codex_home_present`/`sanitize_tools`/`version` reported. SKIP on non-shim routes. | `/health` unreachable → shim daemon not running (`start_shim.sh`). `backend_mode` mismatch → wrong `SHIM_BACKEND_MODE`. `codex_home_present=false` (chatgpt) → `auth.json` missing (see T0.9). |
| **T0.9 ChatGPT auth.json** | (chatgpt route) `$CODEX_HOME/auth.json` exists and is readable — contents never read. SKIP otherwise. | Missing/unreadable → run `codex login --device-auth`. |
| **T0.10 Workspace invariants** | `check_workspace_invariants.sh -q` clean (no unauthorized symlinks / repo-root leak artifacts). | An invariant violation exists on the live filesystem. Run `bash /daaf/scripts/check_workspace_invariants.sh` (verbose) to see the offending path. |
| **T0.11 R UTF-8 locale** | `Rscript -e 'quit(status = !isTRUE(l10n_info()[["UTF-8"]]))'` exits 0 — R starts under a UTF-8 locale (codeset UTF-8, MBCS on). Confirms the image's `LANG`/`LC_ALL=C.UTF-8` is in effect, so R reads multibyte UTF-8 (e.g. `yaml::read_yaml()` on `mirrors.yaml`) correctly rather than silently returning NULL. Route-independent — an image property, not a provider one. Note: the harness strips the `LC_CTYPE` its own Python interpreter injects via PEP 538 coercion before spawning `Rscript` (when `LANG`/`LC_ALL` are unset), so the verdict reflects the true image env — an unsanitized child would false-PASS on a stale image. | FAIL = R's codeset is `ANSI_X3.4-1968`/`POSIX` — `LANG`/`LC_ALL` are unset in the running container (a stale or pre-v3.0.0 image), and R will silently corrupt UTF-8. Fix at the source: confirm the `ENV LANG=C.UTF-8` / `ENV LC_ALL=C.UTF-8` block near the top of the `Dockerfile` and rebuild (`bash rebuild_daaf.sh` from `daaf-docker`). Unlike Python, R has no PEP-538 startup coercion, so the image env is the only complete fix; the education-data-query skill's runtime `Sys.setlocale()` guard mitigates file reads but cannot repair parse-time literal mangling. SKIP = `Rscript` not on PATH; a hung `Rscript` (60s timeout) is a FAIL. |

> **Tier 0 limitation — ambient env only.** Tier 0 runs **once**, against the ambient (as-launched) environment, before any profile overlay is applied. Its route/env-coherence and context-window checks (T0.1–T0.4) therefore describe the base installation, **not** any `--profiles` overlay. A profile that, say, sets `ANTHROPIC_MODEL` to a GLM slug and declares its window via `CLAUDE_CODE_MAX_CONTEXT_TOKENS` is exercised only in that profile's Tier 1/2 runs — Tier 0 never re-validates per-profile overlays. When multi-profiling, read each profile's overlay in `profiles.yaml` directly to confirm its window/remap declarations; the Tier 0 verdict speaks to the ambient config alone.

---

## Tier 1 — One Live Round-Trip

A single cold-start `claude -p` call plus the plumbing checks around it. Two of these probes routinely emit non-PASS verdicts on short headless runs that are **expected mechanics, not install defects** — understanding them prevents false alarms.

| Probe | PASS means | Non-PASS interpretation |
|-------|-----------|-------------------------|
| **T1.1 Live round-trip response** | The model returned a response. | FAIL = timeout or empty response. A real routing/auth failure surfaces here first — check the provider-specific failure modes below. |
| **T1.2 Transcript located** | The session transcript was found (archived or live). | FAIL = transcript missing in both locations; session logging may be broken. |
| **T1.3 Audit-log hook fired** | `audit.jsonl` has entries for the session. | FAIL = the audit-log hook did not fire; check its registration (T0.6). |
| **T1.4 Context-reporter injection** | The context-reporter injection was visible in the transcript. | **INFO when absent is EXPECTED for a short headless probe.** `context-reporter.sh` injects at most once per 60 seconds; a cold-start probe finishes in seconds. The hook still fires and falls back to a 200k window when its cache is unresolved. Absence is cadence-driven, not a defect. |
| **T1.5 /tmp coordination caches** | `/tmp/claude-model-*` and `/tmp/claude-ctx-window-*` are populated (bounded ~5s retry). | **PASS with `window=200000` on a wide-window model can be expected headless behavior.** A headless `claude -p` statusline payload may omit the real window, so `context-bar.sh` begins from 200000. Its static map corrects supported GPT slugs and exact `z-ai/glm-5.2` or terminal `-YYYYMMDD` snapshots; `z-ai/glm-5.2-air`, future GLM suffixes, and native Claude `[1m]` ids do not inherit the exact GLM constant. Dynamic OpenRouter metadata, when available, remains authoritative even when it reports exactly 200000. The meaningful signal is whether the caches are populated at all; an absent-after-retry cache is the real WARN. GLM's larger physical capacity does not relax its conservative quality thresholds. |
| **T1.6 Statusline against real session** | `context-bar.sh` renders non-empty against the real session payload. | WARN = no output; SKIP = no transcript to render against. |
| **T1.7 Token/cost parsing** | Token/turn/cost fields parsed from the JSON result. | WARN = all zero; the parse may have missed the result message (rarely a deployment issue). |

**Why the headless caveats matter.** T1.4 and T1.5 were the two WARN signals in the first live anthropic-subscription run. They are the price of testing headlessly: no interactive statusline renders to write the real window, and the cache writes are async relative to CLI exit. The suite now polls with a bounded backoff and quotes both the first and final read. Treat an **absent-after-retry** cache as the real signal. A populated `200000` cache can be valid headless mechanics when no applicable static or dynamic mapping resolves; supported GPT and exact/date-snapshot GLM-5.2 ids are mapped when their narrow patterns match.

---

## Tier 2 — Six-Probe Functional Battery

Each probe is a separate cold-start run. All checks are capability-structural and deliberately tolerant of stylistic/protocol variation.

Every Tier 2 run works inside its own **per-run, UUID-owned sandbox** — `scripts/deploy_smoke/_sandbox/run_<uuid>/`, created fresh at the start of the run and removed in a guaranteed cleanup path (scoped to exactly that directory — never a recursive wipe of `_sandbox/` and never a sibling). This is what makes the T2.1/T2.2 fixtures fresh *by construction*: a run directory left behind by a hard process kill carries a UUID no future run mints, so it is inert crash residue that cannot satisfy a later run. The two historical root-level fixtures (`_sandbox/t21_marker.txt`, `_sandbox/t22_probe.py`) predate this design and are non-authoritative; all of `_sandbox/` stays git-ignored.

| Probe | PASS means | FAIL/SKIP interpretation |
|-------|-----------|--------------------------|
| **T2.1 Subagent dispatch + search** | An `Agent`/`Task` tool_use occurred and a subagent transcript and/or the marker token was observed. | FAIL = no dispatch or marker not returned. On non-Claude routes, cross-check the ceiling-hook posture (T0.2) — a mis-set remap can block dispatch. |
| **T2.2 Coding agent write + execute** | `research-executor` wrote a script and ran it via `run_with_capture.sh`, and *this run's* execution left fresh captured evidence. PASS requires **all** of: this run's probe script exists; a fresh `# EXECUTION LOG` banner is present; a `# Exit code: 0` record appears **after** the banner; and this run's unique nonce appears in the captured output **after** the banner. The nonce (not just the script's presence) is what ties the PASS to freshly captured output rather than source text. | FAIL = any one of those is missing. A nonce that appears only in the script source, a stale banner from a prior run, or a recorded nonzero exit are each a **FAIL** — never a PASS-with-note. Confirms the file-first execution path and `enforce-file-first.sh` are intact *for this run*, not merely that a script file exists. |
| **T2.3 Web access (WebSearch)** | A `WebSearch`/`WebFetch` tool_use occurred in a subagent transcript. | FAIL = no web tool_use. May reflect a provider that does not surface the web tools, or a sandboxed network. |
| **T2.4 Skill loading** | A `Skill` tool_use is present (skill body arrived in the transcript). | FAIL = no Skill tool_use; progressive disclosure may not be firing. |
| **T2.5 Isolation-strip hook** | `block-remote-isolation.sh` stripped the `isolation` parameter (strip evidence in transcript). | **SKIP is tolerated** — if the model omitted/refused the `isolation` param there is nothing to strip (not a FAIL). WARN = isolation requested but no explicit strip evidence, yet the dispatch did not hang. |
| **T2.6 Nested-dispatch deny hook** | `block-nested-dispatch.sh` denied a nested Agent/Task dispatch attempted from *inside* a subagent: the probe subagent reports its one nested dispatch was BLOCKED and quotes a denial mentioning "nested subagents". No nested agent actually runs on PASS, so the probe costs only the two subagent invocations' overhead (~cents) — the outer probe subagent plus the denied inner attempt that never executes. | FAIL = the nested dispatch actually ran (a nested agent returned a result) — the deny path did not fire. Most likely the hook is unregistered or misregistered in `settings.json` (it must sit first in *both* the `Task` and `Agent` matcher chains), or the harness stopped sending the `agent_id`/`agent_type` caller-identifying fields the hook keys on. Diagnose with `tests/bash/block_nested_dispatch.bats` (deterministic Tier D coverage of the same hook) and re-check the hook's registration in `settings.json`. |

---

## Tier D — Deterministic Battery (opt-in, zero API cost)

Opt-in via `--tiers D` (with `--include-r-smoke` for TD.6). Every probe shells a repo test entry point and reports its exit code — no LLM, no cost. A missing tool is a **SKIP**, not a FAIL, so running Tier D outside the `DAAF_DEV=1` image degrades gracefully rather than failing spuriously.

**The harness self-tests itself first.** TD.0 runs the suite's own provider-free `unittest` module (`tests/python/test_deploy_smoke.py`) *before* the broader batteries, so an official Tier D run first validates its own harness (environment sanitization, failure-evidence capture, Pester/battery output routing, per-run Tier 2 cleanup, and the stricter T2.2 semantics). You can run it directly, no route or provider needed: `python3 -m unittest discover -s /daaf/tests/python -p 'test_deploy_smoke.py'`.

**Deterministic environment isolation.** All Tier D subprocesses run under a sanitized copy of the live environment with exactly two variables stripped — `CLAUDE_CODE_MAX_CONTEXT_TOKENS` and `DAAF_BRANCH` — because a fully-configured live install legitimately exports both, and both steer default-window / default-branch fixtures onto the live session's values. This is defense-in-depth *atop* each battery's own fixture isolation (bats `setup()` unset, Pester `BeforeEach` removal), **not** `env -i`: `PATH`, `HOME`, route credentials, and the developer toolchain are all preserved so the batteries can still find their interpreters. TD.0's evidence records which variables were actually removed.

**Two-level evidence policy.** On a **PASS**, a probe keeps only a concise final excerpt (the last several lines) in the report. On a **FAIL or timeout**, the report quotes a bounded head-and-tail excerpt (so both the earliest failure names and the final summary stay visible) *and* the COMPLETE scrubbed output is persisted to `evidence/tier_d/{probe_id}.log`, referenced from the probe's evidence. All captured output is scrubbed for secret env values before it is quoted or persisted.

| Probe | PASS means | FAIL/SKIP interpretation |
|-------|-----------|--------------------------|
| **TD.0 harness self-test** | The deploy-smoke suite's own `unittest` module (`tests/python/test_deploy_smoke.py`) passes — the harness's env sanitization, evidence capture, output routing, Tier 2 cleanup, and T2.2 freshness logic are all intact. Runs first so the rest of Tier D is trustworthy. | FAIL = a harness regression: fix the harness before trusting any other Tier D verdict. SKIP is not expected (it only needs stdlib `python3`); a FAIL here means the suite's own contracts broke. |
| **TD.1 bats tests/bash** | `bats tests/bash/` exits 0 (all Bash unit tests pass). | FAIL = a Bash test failed. SKIP = `bats` not installed (needs the `DAAF_DEV=1` image). |
| **TD.2 Pester tests/powershell** | `Invoke-Pester -Path tests/powershell -CI` exits 0 **and** its NUnit `testResults.xml` is present in the report at `evidence/tier_d/testResults.xml`. Pester runs with its working directory set to that evidence dir, so the XML lands report-local rather than at the repository root (`/daaf/testResults.xml` is never created). | FAIL = a PowerShell test failed, **or** Pester exited 0 but the report-local `testResults.xml` is missing (an artifact-routing failure — a zero exit with no XML is a TD.2 FAIL by contract, not a PASS). SKIP = `pwsh` not installed (dev image only). |
| **TD.3 daaf-conventions lint** | `tests/lint/check-daaf-conventions.sh` exits 0. | FAIL = a convention violation. Read the tail evidence for the offending file. |
| **TD.4 safety-hook tests** | `scripts/test_safety_hooks.sh` exits 0 (the `bash-safety.sh` battery passes). | FAIL = a safety-hook regression — investigate before trusting the deployment's guardrails. |
| **TD.5 single-command hook tests** | `scripts/test_enforce_single_command.sh` exits 0. | FAIL = an `enforce-single-command.sh` regression. |
| **TD.6 R/Python skill smoke suite** | (opt-in) log-stripped copies of `scripts/smoke_tests/smoke_*` run clean via `SMOKE_DIR`. | FAIL = a library smoke failed. **SKIP by default** — pass `--include-r-smoke` to enable (it is slow). Mirrors the CI staging pattern; runs under `scripts/scratch/smoke_live/`, never `/tmp`. |

---

## Route-Conditional Expectations and Known Failure Modes

Each route has a distinct configuration surface. Below: what Tier 0 expects for the route, and the known failure modes (with their documented fixes) that a live-tier FAIL most likely maps to.

### Route 1 — anthropic-subscription (native, no shim)

- **Expected:** No `DAAF_PROVIDER_SHIM`, no OpenRouter base URL. Model resolves via `settings.json` `ANTHROPIC_MODEL`. `enforce-model-ceiling.sh` actively **ranks** subagent dispatches (haiku < sonnet < opus < fable). T0.2 should report family `claude`, `remap_active=false`.
- **Auth:** Interactive OAuth or `CLAUDE_CODE_OAUTH_TOKEN`. Tier 0 cannot verify interactive OAuth without an LLM call, so a genuine auth problem surfaces at **T1.1** (round-trip fails).
- **Known failure mode:** `ANTHROPIC_BASE_URL` unexpectedly set while the route detects as native — T0.3 flags it. Unset it for the native route.

### Route 2 — openrouter

- **Expected:** `ANTHROPIC_BASE_URL` ends with `openrouter.ai/api`; `ANTHROPIC_AUTH_TOKEN` set (your OpenRouter key, Bearer auth); `ANTHROPIC_API_KEY` **present-and-empty** (`ANTHROPIC_API_KEY=`) so the `X-Api-Key` header does not override Bearer auth. For non-Claude models, `ANTHROPIC_DEFAULT_OPUS_MODEL`/`SONNET_MODEL` remap keeps subagents pure and makes the ceiling hook **stand down**; `CLAUDE_CODE_MAX_CONTEXT_TOKENS` declares the real window.
- **Known failure modes (documented in `user_reference/01_installation_and_quickstart.md` § "Setup Troubleshooting", anchor `#setup-troubleshooting`):**
  - *"model not found" / auth errors* — three causes: wrong base-URL suffix, `ANTHROPIC_API_KEY` unset vs. empty, or a stale login needing `/logout`. T0.3 catches the base-URL and empty-key cases directly.
  - *`-pro` GPT slugs* — hard "Prompt is too long" failures at ~50k tokens with ~4x-inflated token accounting (`01_installation_and_quickstart.md` § "GPT (OpenAI) models via OpenRouter (Option C, extended)", anchor `#gpt-openai-models-via-openrouter-option-c-extended`). Avoid `-pro` slugs over OpenRouter; use a standard flagship slug.
  - *Ceiling-hook DENY on a non-Claude session* — if a non-Claude family is configured **without** a remap var, a Claude-tier subagent request is denied with remap guidance (`enforce-model-ceiling.sh:189-192`). Set the `ANTHROPIC_DEFAULT_*` remap vars. T0.2's INFO posture is the early warning.
  - *Context under-reporting* — a GPT/non-`[1m]` slug without a window declaration → T0.4 FAIL.

### Routes 3 & 4 — shim (chatgpt-subscription, openai-api)

- **Expected:** `DAAF_PROVIDER_SHIM=openai`; `ANTHROPIC_BASE_URL` → `http://127.0.0.1:4141`; `ANTHROPIC_AUTH_TOKEN=daaf-shim-local`. Route 3 additionally needs `SHIM_BACKEND_MODE=chatgpt` and `CODEX_HOME` (holds `auth.json`); Route 4 needs `OPENAI_API_KEY` or `SHIM_BACKEND_API_KEY`. T0.8 shim `/health` must report the matching `backend_mode`.
- **Daemon state is not per-run overridable.** `SHIM_SANITIZE_TOOLS` and `backend_mode` are fixed at shim startup; `--profiles` overlays reach only the CLI session, so the runner WARNs if `--profiles` is used on a shim route. Verify daemon state read-only via T0.8.
- **Known failure modes:**
  - *Route 3 auth* — `codex_home_present=false` or T0.9 FAIL → `auth.json` missing/unreadable; run `codex login --device-auth`. Token refresh is JWT-`exp`-based and lazy; a genuinely expired, un-refreshable token surfaces at T1.1.
  - *GPT tool-call quirks* — `isolation`-fill hangs and empty `Read.pages` are handled by the shim's `_sanitize_tools` (default on, Routes 3–4) and, for `isolation`, by `block-remote-isolation.sh` at the hook layer. T2.5 exercises the hook-layer strip. For DAAFBench raw-model runs `SHIM_SANITIZE_TOOLS=0` is required — but that is a benchmark concern, not a deployment-health one.
  - *Route 4 instant 429* — an unfunded OpenAI API key returns 429 immediately (distinct from a ChatGPT subscription); surfaces at T1.1. Fund the API account or switch to the chatgpt route (`07_faq_technical.md` § "Q: My GPT session fails instantly with 429 errors on every request (Option F)", anchor `#q-my-gpt-session-fails-instantly-with-429-errors-on-every-request-option-f`).
  - *ChatGPT lane is an unofficial dev lane* — explicitly flagged as not OpenAI-sanctioned and liable to break (`01_installation_and_quickstart.md` § "Option F, alternate lane: ChatGPT subscription (Codex backend)", anchor `#option-f-alternate-lane-chatgpt-subscription-codex-backend`); a sudden T1.1 failure here may be upstream, not a local misconfig.

---

## Where Evidence Lands (for manual follow-up)

When a probe FAILs and the report evidence is not enough, these live locations carry more detail:

| Signal | Location |
|--------|----------|
| Shim health/config | `curl http://127.0.0.1:4141/health` → `backend_mode`, `codex_home_present`, `sanitize_tools`, `reasoning_effort`, `version` |
| Shim structured logs | `scripts/provider_shim/logs/shim.log` (credential-scrubbed) |
| Session/subagent model | `/tmp/claude-model-{session}`, `/tmp/claude-subagent-model-{session}-{id}` |
| Context-window cache | `/tmp/claude-ctx-window-{session}`, `/tmp/claude-or-models-{session}` (OpenRouter models cache) |
| Ceiling-hook stand-down/deny reasons | stderr of `enforce-model-ceiling.sh` and its `permissionDecisionReason` JSON |
| Report artifacts | `scripts/deploy_smoke/reports/{timestamp}_{route}/report.md`, `report.json`, `evidence/` (`shim_health.json`, `env_fingerprint.json`) |
| Tier D failure logs | `scripts/deploy_smoke/reports/{timestamp}_{route}/evidence/tier_d/{probe_id}.log` — complete scrubbed output of any FAILed/timed-out battery |
| Pester NUnit results | `scripts/deploy_smoke/reports/{timestamp}_{route}/evidence/tier_d/testResults.xml` — report-local (never `/daaf/testResults.xml`) |

Reading these `/tmp` caches is the sanctioned pattern (reads allowed, writes blocked). The report's `evidence/` directory already snapshots the shim `/health` JSON and the redacted env fingerprint for offline audit.
