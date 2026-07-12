# 07. FAQ: Technical Support

Operational questions with concrete answers. If you're stuck, troubleshooting, or curious about a technical choice -- check here first.

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Table of Contents
- [**Key Concepts Explained**](#key-concepts-explained)
- [**Installation Troubleshooting**](#installation-troubleshooting)
- [**Working with DAAF**](#working-with-daaf)
- [**Setup and Settings**](#setup-and-settings)
- [**Packages and Environment**](#packages-and-environment)
- [**R and Language Support**](#r-and-language-support)
- [**Session Logs and Diagnostics**](#session-logs-and-diagnostics)
- [**Technology Choices**](#technology-choices)
- [**Performance and Configuration**](#performance-and-configuration)
- [**Data Access Issues**](#data-access-issues)
- [**Common Error Messages**](#common-error-messages)
- [**Recommended Next Steps**](#recommended-next-steps)
- [**Community Resources**](#community-resources)

---

## Key Concepts Explained

If you're new to some of the technical vocabulary, here's a quick reference:

| Term | What it means |
|------|---------------|
| **Terminal** | A text-based interface for typing commands to your computer (also called Command Prompt on Windows or shell on Linux/Mac) |
| **Docker / Docker Desktop** | Software that creates isolated, reproducible environments (containers) on your computer |
| **Container** | A lightweight, isolated environment that runs programs without affecting the rest of your system |
| **Volume** | A persistent storage area attached to a Docker container -- your files live here and survive container restarts |
| **API Key** | A secret code that authenticates you with an external service (like Anthropic's Claude API) |
| **Environment Variable** | A named value your system stores in memory that programs can read (used for configuration and API keys) |
| **Port** | A numbered channel that allows programs to communicate over a network (DAAF uses ports 2718-2720) |
| **Claude Code** | Anthropic's command-line interface for Claude that DAAF runs inside -- it's the "brain" that powers all analysis |

---

## Installation Troubleshooting

### "docker: command not found" or "docker is not recognized"

Docker Desktop isn't installed or isn't in your system PATH. Download it from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/), install it, and make sure it's running (you should see the Docker whale icon in your system tray/menu bar). You may need to restart your terminal after installation.

### Malformed authentication URL when trying to log in to Claude Code

If you're trying to copy the URL authentication link, be careful to check it for erroneous line-breaks in the URL. Paste this into a simple notepad editor and remove any extra line-breaks, then try pasting the revised URL into your browser.

### "unable to get image" or build fails immediately

Make sure Docker Desktop is **running** (not just installed). Open Docker Desktop and wait for it to fully start before running the installer. If you're on a corporate network, check whether a VPN or firewall is blocking Docker Hub access.

### "service is not running" when trying to start DAAF

Run `docker compose up -d` from your `daaf-docker` folder first, then try `bash run_daaf.sh` again. If that doesn't work, open Docker Desktop and check if the container shows as "running."

### Port conflicts (2718, 2719, or 2720 already in use)

Another application is using one of DAAF's ports. Close the conflicting application, or edit `docker-compose.yml` in your `daaf-docker` folder to map different host ports (change the left side of the colon, e.g., `3718:2718`).

### Permission denied errors inside the container (macOS)

This usually happens when Docker Desktop's file sharing permissions haven't been configured. Open Docker Desktop → Settings → Resources → File Sharing, and ensure the relevant directories are shared.

### Claude Code asks me to log in again

This should be uncommon. Claude Code's login, session history, and plugins live in a dedicated Docker volume (`daaf-claude-config`), so they persist across container restarts, `docker compose down`, and even image rebuilds -- a routine restart or update should not sign you out. If you *do* get prompted after a normal restart, just run `/login` once for an Anthropic Max/Pro subscription (or paste your API key); it will persist from then on. Note that `docker compose down -v` (with the `-v` flag) or manually deleting the volume erases this state, so avoid `-v` unless you mean to wipe everything. If you'd rather never log in interactively, set your credentials in the `environment_settings.txt` file in the `daaf-docker/` folder -- it is read on every container start.

### OpenRouter: "model not found" or authentication errors

Check three things: (1) `ANTHROPIC_BASE_URL` must be exactly `https://openrouter.ai/api` with no `/v1` suffix, (2) your `ANTHROPIC_API_KEY` must be a valid OpenRouter API key (starts with `sk-or-`), and (3) the model you're requesting must be available on OpenRouter. Verify at [openrouter.ai/activity](https://openrouter.ai/activity).

### Container seems really slow to build the first time

The first build downloads and compiles 50+ Python packages including geospatial libraries (GDAL, GEOS, PROJ) that can take 5-15 minutes depending on your internet speed and hardware. This is normal and only happens once -- subsequent starts are fast because the image is cached.

### I can't find my research files on my computer

DAAF stores files inside a Docker volume, not directly on your filesystem. Three ways to access them:
- **Browser file manager:** Run `bash run_vscode.sh` (or `.\run_vscode.ps1` on Windows) and open `localhost:2720` in your browser
- **Backup script:** Run `bash backup_daaf.sh` (or `.\backup_daaf.ps1`) to copy everything to a folder on your computer
- **Single file:** `docker compose cp daaf-docker:/daaf/research/your-project/file.md ./`

### How do I update DAAF to the latest version?

From your `daaf-docker` folder on your host computer, run `bash update_daaf.sh` (macOS/Linux) or `.\update_daaf.ps1` (Windows). The script checks for available updates, shows you what's new, and handles the update safely -- including detecting and helping resolve any local edits you've made.

### How do I back up my research files?

From your `daaf-docker` folder: `bash backup_daaf.sh` (macOS/Linux) or `.\backup_daaf.ps1` (Windows). This copies your entire research directory to a timestamped folder on your computer. The backup folder also contains two hidden items you can safely ignore — a `.daaf-claude-config/` subfolder holding your Claude Code login and session history, and a small `.daaf-permissions` manifest that lets the restore put file permissions back correctly (see the quickstart's *Backing Up Your Work* section for details). You can also use the browser file manager (`bash run_vscode.sh`) to browse and download individual files.

---

## Working with DAAF

### What are engagement modes and how do I choose one?

DAAF has nine engagement modes, each designed for a different type of task. You don't need to memorize them -- just describe what you want to do and DAAF will suggest the right mode. But here's a quick overview:

- **Full Pipeline** — Complete research analysis from question to report ("Analyze how X relates to Y")
- **Data Onboarding** — Profile and register a new dataset ("I have this CSV I want to use")
- **Data Discovery** — Explore what data exists ("Is it possible to study X?")
- **Data Lookup** — Quick factual answers ("What are the coded values for variable X?")
- **Ad Hoc Collaboration** — Flexible working session ("Help me debug this" / "Think through this with me")
- **Revision and Extension** — Modify existing work ("Update the analysis to include 2024 data")
- **Reproducibility Verification** — Verify an analysis reproduces ("Re-run this and check the results match")
- **Framework Development** — Modify DAAF itself ("Create a new skill for survey methods")
- **User Support** — Questions about DAAF ("How does the validation system work?")

DAAF always confirms the mode with you before proceeding, so you can adjust if it picks wrong.

### What are the /config and /model commands I keep seeing referenced?

These are Claude Code slash commands you can type anytime during a session:

- `/config` — Opens the Claude Code settings menu. Key settings to check:
  - **Auto-compact:** Set to `false` (DAAF manages its own context)
  - **Verbose output:** Set to `true` (lets you see what agents are thinking)
- `/model` — Switch the active model (use arrow keys to select)
- `/clear` — Clear conversation history and start fresh (used when resuming from STATE.md)
- `/exit` — Exit Claude Code (first step in ending a session)
- `/status` — Check connection status and current model

### DAAF seems to be doing something I didn't ask for

You're always in control. If DAAF is heading in a direction you didn't intend:
- **Press ESC** to interrupt the current operation
- **Say "stop"** or "that's not what I meant" -- DAAF will pause and ask for clarification
- **Type `/clear`** to start completely fresh if things have gone off the rails

Remember: DAAF always presents a mode confirmation and research plan for your approval before doing substantial work. If something is happening you didn't approve, it's likely a continuation of a previously-approved step.

---

## Setup and Settings

### Q: Can I run DAAF without Docker?

Technically yes, but I really don't recommend it, and it's not something I will support. Docker provides security isolation (non-root, dropped capabilities), full reproducibility (pinned dependencies), and clean-slate recovery -- all critical when an AI agent is writing and executing code on your behalf. For the full rationale, see [**01. Installation -- Prerequisites: Docker Desktop**](01_installation_and_quickstart.md#3-docker-desktop).

If you want to go this route: be my guest, but you'll need to figure it out on your own. I would firmly posit that anyone who's ready and qualified to do this independently **already** knows how to do it without my help.

---

### Q: Should I use an API key or a Max subscription?

I strongly recommend the **Max subscription** ($100/mo or $200/mo). DAAF is extremely usage-intensive by design, and from my own testing I estimate I'd pay roughly **10x more** going with API billing versus my Max subscription. A single full-pipeline analysis can easily cost $50-100+ via the API; the Max plan covers that at a flat monthly rate.

| Factor | API Key | Max Subscription |
|--------|---------|------------------|
| **Cost model** | Pay per token (uncapped) | Flat monthly ($100-200/mo) |
| **Cost predictability** | Variable, can spike | Fixed |
| **Usage limits** | Unlimited (as long as you pay) | Subject to usage limits within your plan tier |
| **Rate limiting** | Minimal | May hit rate limits during very heavy sessions |
| **Best for** | Light/occasional use, or organizational API budgets | Regular DAAF usage (recommended) |

**Third option: OpenRouter.** Pay-per-token access via [OpenRouter](https://openrouter.ai/) with no monthly commitment (5.5% fee on credit purchases). OpenRouter provides access to Anthropic's Claude models and also to high-performing open-weight models like GLM 5.2, which [benchmarks competitively with the Opus line](https://daaf.openaugments.org/bench/) at roughly 33% of the cost. Good for testing DAAF or for cost-conscious sustained use. See [**01. Installation -- Configure authentication via environment_settings.txt**](01_installation_and_quickstart.md#configure-authentication-via-environment_settingstxt) for setup.

For the full comparison of all authentication options, see [**01. Installation -- Anthropic Account & Authentication**](01_installation_and_quickstart.md#1-anthropic-account--authentication).

One thing to note: the Max plan does have usage limits per time window. If you're running several DAAF analyses in parallel (which you absolutely can do!), you may occasionally hit a rate limit and need to wait a bit. The API key doesn't have that issue, but your wallet will feel it instead.

### Q: Which Claude model should I use?

DAAF defaults to **Opus 4.6**, and that remains a strong choice — but it's no longer the only good one. [Empirical benchmarking across 20 models](https://daaf.openaugments.org/bench/) (DAAFBench) has produced clear, data-backed guidance:

| Recommendation | Model | Why |
|---------------|-------|-----|
| **Default** | **Opus 4.6** | Strong orchestration performance with the deepest analytical reasoning. Best for complex methodology and nuanced judgment calls. |
| **Best value** | **Sonnet 4.6** | Ranked #2 overall on orchestration benchmarks — outperforms every Opus model on protocol conformance at ~66% of the cost. An excellent choice for most DAAF work. |
| **Best without Anthropic subscription** | **GLM 5.2** (via OpenRouter) | Ranked #4 overall, roughly on par with the Opus line on orchestration at ~33% of the cost. Makes DAAF accessible without any Anthropic subscription. |
| **Budget-friendly** | **DeepSeek V4 Flash** (via OpenRouter) | Solid mid-tier performance at ~3% of flagship cost. Worth exploring for less complex tasks. |
| **Not recommended** | **Haiku 4.5** | Adequate on basic tasks but struggles with DAAF's multi-step protocols and skill routing. |

**Important context:** These benchmarks test *orchestration behavioral conformance* — can the model follow DAAF's protocols, dispatch agents correctly, and load the right skills? They do not directly measure analytical reasoning depth or code quality. Opus may still have an edge on the hardest analytical work, but the gap between the top models is much smaller than previously assumed. See the [full DAAFBench results](https://daaf.openaugments.org/bench/) for detailed per-phase breakdowns.

Opus 4.6 also supports configurable "thinking levels" (toggle in the `/model` selector with left/right arrow keys). I recommend the **"High"** setting — quality matters more than speed for research work. Higher thinking levels do consume more of your usage allocation, so there's a legitimate tradeoff to explore. The DAAFBench results are a useful starting point for understanding where different models sit on the quality-cost frontier.

### Q: How do I change the Claude model during a session?

Type `/model` in the Claude Code chat window. You'll see a list of available models -- use the arrow keys to select one and press Enter. The change takes effect immediately for all subsequent interactions in that session.

You can also adjust the thinking level for Opus 4.6 by pressing the left and right arrow keys while Opus 4.6 is highlighted in the model selector.

### Q: Why does DAAF disable "background tasks" but specialists still run in the background?

These are two different Claude Code features that happen to share a name.

`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` (set in DAAF's `settings.json`) disables background *shell commands* — the option to run terminal commands in the background, automatic backgrounding of long-running commands, and the Ctrl+B shortcut. DAAF keeps this disabled deliberately: every analysis script must run to completion in the foreground so its full output is captured into the script's embedded audit log. A backgrounded script would decouple execution from capture and break the audit trail.

Separately, Claude Code runs *subagents* (the specialists DAAF dispatches for research, coding, and review work) in the background and notifies the session when each finishes. The official documentation says this setting disables background execution for subagent dispatches too, but on DAAF's pinned Claude Code version the observed behavior is that specialist dispatches still run in the background with the setting active. Either behavior is fine for DAAF: its workflows wait for all dispatched specialists to report back before making decisions, and the audit-trail concern applies to analysis scripts (which the setting reliably keeps in the foreground), not to specialist scheduling. If a future version update makes specialists run in the foreground instead, nothing in DAAF's workflows breaks — turns just complete sequentially.

(Related trivia: `DISABLE_AUTOUPDATER` in the same settings block is technically redundant — `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` subsumes it — but it's kept as an explicit standalone pin so the version-pinned container can never auto-update, even if the umbrella setting is temporarily lifted for diagnostics.)

### Q: Can I use DAAF with a different AI provider (OpenAI, Google, etc.)?

Yes -- partially. There are two different things this question might mean, so let me address both.

**Using different models through OpenRouter (supported and tested):** [OpenRouter](https://openrouter.ai/) is a model gateway that lets you route Claude Code through a single API key with pay-per-token billing. It's already configured as an authentication option in DAAF's `environment_settings_example.txt` template (Option C). Through OpenRouter, you can access Anthropic's Claude models without a Max subscription — and also access non-Anthropic models that perform well with DAAF. See [**01. Installation & Quick Start -- Configure authentication via environment_settings.txt**](01_installation_and_quickstart.md#configure-authentication-via-environment_settingstxt) for setup instructions (remember to run `/logout` first if you previously authenticated with Anthropic directly).

**Non-Anthropic models — what works:** [DAAFBench](https://daaf.openaugments.org/bench/) has tested multiple non-Anthropic models across 2,799 runs. The standout is **GLM 5.2**, which ranks #4 overall and performs roughly on par with the Opus line on orchestration benchmarks at ~33% of the cost. **DeepSeek V4 Flash** performs appreciably worse but at substantially lower price points (~3% of costs for Opus). Note that extended thinking (which DAAF uses extensively with Anthropic models) does not work with non-Anthropic models through OpenRouter — these models rely on their native reasoning capabilities instead. See the [full benchmark results](https://daaf.openaugments.org/bench/) for per-model breakdowns.

**Porting DAAF to a different CLI tool entirely:** This is also possible but requires more effort. DAAF is built on Claude Code, which is Anthropic's CLI agent tool. The vast majority of what DAAF actually *is* -- the agent protocols, skill documents, workflow definitions, validation checkpoints -- is just structured text in Markdown files. None of that is Anthropic-specific. What *is* specific to Claude Code are the hooks system (the safety guardrails that block dangerous commands, scan outputs for secrets, etc.) and some of the tool invocation patterns.

If you wanted to port DAAF to another agent harness (Gemini CLI, Codex, OpenCode, etc.), here's what would transfer immediately:
- All agent files (`.claude/agents/*.md`)
- All skill files (`.claude/skills/*/SKILL.md`)
- All reference documentation (`agent_reference/*.md`)
- The overall workflow design and validation philosophy

What would need adaptation:
- The hooks system (`.claude/hooks/`) -- these are shell scripts that hook into Claude Code's execution lifecycle
- The `.claude/settings.json` permission configuration
- Any Claude Code-specific invocation patterns (the `Task` tool, subagent types)

I would honestly be thrilled if someone forked DAAF and adapted it for another provider. The more researchers who have access to rigorous AI-assisted analysis tooling, the better. We've made significant progress testing open-source models via [DAAFBench](https://daaf.openaugments.org/bench/) — GLM 5.2 is already viable — but there's much more to explore, especially around analytical depth and domain-specific tasks. If you're running DAAF with non-default models, **please** share your experiences so we can continue refining this guidance!

### Q: Can I run DAAF on OpenAI GPT models?

Yes, and it's been validated live (2026-07-09). There are two ways in, both documented step-by-step in [**01. Installation & Quick Start**](01_installation_and_quickstart.md#gpt-openai-models-via-openrouter-option-c-extended):

- **Via OpenRouter (config-only, no rebuild):** point the existing "Option C" OpenRouter setup at GPT slugs like `openai/gpt-5.6-sol` (strong tier) and `openai/gpt-5.6-terra` (fast tier). GPT runs the full agentic stack — multi-tool loops, subagent dispatch, two-tier routing — with just environment variables.
- **Via the DAAF provider shim (direct OpenAI API):** set `DAAF_PROVIDER_SHIM=openai` and `OPENAI_API_KEY`, then point Claude Code at the local shim (`http://127.0.0.1:4141`). This one requires an image rebuild because the shim auto-starts from the container entrypoint.

GPT support is a power-user option offered with honest framing (see the limitation entries below). Anthropic does not officially support routing Claude Code to non-Claude models, and OpenRouter's Anthropic-compatible endpoint is officially scoped to Claude models — GPT works through it in practice, but it is unsupported territory a vendor could change.

If your session still starts on a Claude model after configuring, see [My GPT session starts on a Claude model](#q-my-gpt-session-starts-on-a-claude-model-instead-of-my-gpt-model).

### Q: My GPT session starts on a Claude model instead of my GPT model

Sessions open on the model named by `ANTHROPIC_MODEL` in the `env` block of DAAF's project `.claude/settings.json`, which ships as `claude-opus-4-8[1m]` — a deliberate Claude-first default, since most DAAF users run Claude. Importantly, that settings.json value **overrides** the container environment (verified empirically 2026-07-12: a process-environment `ANTHROPIC_MODEL` lost to the settings.json value on the wire), so setting `ANTHROPIC_MODEL` in `environment_settings.txt` does **not** work — don't use that route.

You have two options on a GPT setup:
- **Per session (default expectation):** just run `/model` after launch and pick your GPT model. If you forget, the very first message fails with a loud authentication/model error, so there's no silent wrong-model risk.
- **Standing default:** edit the `"ANTHROPIC_MODEL"` line in `/daaf/.claude/settings.json` to your GPT slug — bare with the window hint for the Option F shim lane (`"gpt-5.6-sol[1m]"`), prefixed for the Option C OpenRouter lane (`"openai/gpt-5.6-sol"`). This is a deliberate manual edit to a tracked framework file; expect to re-apply it after DAAF updates that touch settings.json.

### Q: On a GPT session, is the context bar accurate?

Not exactly — treat it as a close estimate. OpenRouter's Anthropic-compatible endpoint (and the provider shim) do not implement precise token counting, so Claude Code falls back to *estimating* context usage on GPT sessions. The context bar and the elevated/high/critical utilization warnings still work and are a good guide, but the percentages are approximations rather than exact counts. DAAF deliberately keeps its conservative context-quality thresholds (elevated/high/critical at 40/60/75%) on GPT models, since their long-context quality behavior isn't DAAF-validated yet.

### Q: The statusline shows the wrong context window on a GPT session (e.g. 200k when my model has more)

Claude Code assumes a 200k context window for any model it doesn't recognize, which is wrong for the 400k `gpt-5.2` / `gpt-5.4-mini` and the 1,050,000-token `gpt-5.4` / `gpt-5.5` / `gpt-5.6` family (Sol/Terra/Luna). Fix it by setting `CLAUDE_CODE_MAX_CONTEXT_TOKENS` in `environment_settings.txt` to your model's real window (e.g. `1050000` for `gpt-5.6-sol`), then restart the container. DAAF's statuslines carry a built-in GPT window map as a backstop, but the explicit variable is authoritative and is the recommended fix.

### Q: My GPT session says "Context limit reached" / "Prompt is too long" at low utilization

This is a *client-side* budget error — Claude Code decided the request is too big before it ever reached the model — and on a GPT session at genuinely low utilization it has two compounding causes. First, Claude Code assumes a small (~200K) window for a model slug it doesn't recognize, so it thinks the window is nearly full when it is not. Second, before shim v1.2.1 the provider shim (Option F) estimated a request's token count from its raw JSON byte length, which over-counted realistic Claude Code envelopes (large tool schemas plus JSON escaping) by roughly 1.6–1.9×, pushing the perceived size over the already-too-small window. The fix is two-part:

- **Append `[1m]` to your GPT slugs** in `environment_settings.txt` (e.g. `ANTHROPIC_DEFAULT_OPUS_MODEL=gpt-5.6-sol[1m]`). Claude Code reads `[1m]` as a 1M-window hint and budgets the full window, then strips the suffix before sending — the shim and OpenAI backend still see the bare `gpt-5.6-sol`. `CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000` is an equivalent env-var alternative if you prefer not to change the slugs. (`[1m]` also composes with a `#<effort>` reasoning-effort suffix — e.g. `gpt-5.6-sol[1m]#medium` — if you want to set both at once; see [How do I control GPT reasoning effort?](#q-how-do-i-control-gpt-reasoning-effort-option-f).)
- **Ensure the shim is v1.2.1 or newer** (check `curl -s http://127.0.0.1:4141/health` — the `version` field). v1.2.1 calibrates its token-count estimates against the backend's own reported counts and biases slightly low, so it no longer inflates the perceived request size.

Restart the container after editing `environment_settings.txt`.

### Q: The provider shim doesn't seem to be responding (Option F)

The shim auto-starts from the container entrypoint and is kept alive by a supervisor, so it should already be running. To diagnose:

```bash
bash /daaf/scripts/provider_shim/start_shim.sh --status   # is it running?
curl -s http://127.0.0.1:4141/health                       # health check
```

Its log is at `/daaf/scripts/provider_shim/logs/shim.log` — check there first. The manager script also accepts `--start`, `--stop`, and `--auto`. Remember that Option F requires the image to have been **rebuilt** after you set `DAAF_PROVIDER_SHIM=openai` (the auto-launch is baked into the entrypoint), so if nothing is running, confirm you rebuilt. If the shim *is* running but every request fails instantly with a 429, see the next entry.

### Q: My GPT session fails instantly with 429 errors on every request (Option F)

An immediate, deterministic 429 on *every* request — including the very first one after a restart — is almost never a real rate limit. Check the shim log (`/daaf/scripts/provider_shim/logs/shim.log`): since shim v1.1.1, every backend error line includes the OpenAI error body and rate-limit headers (credential-scrubbed), so the log names the cause directly. What to look for:

- **`"code": "insufficient_quota"`** — the key's platform.openai.com project has no credits, or hit its monthly spend cap. This is by far the most common cause: ChatGPT Plus/Pro does **not** include API credits, new API accounts get no free credits, and adding a payment card without completing the separate credit *purchase* step leaves the account unfunded. Retrying can never fix this — buy credits at platform.openai.com → Settings → Billing.
- **A rate-limit error with a `retry-after` header** — a genuine per-minute request/token limit for your usage tier. This clears on its own; current Tier 1 token-per-minute limits are generous (500K TPM for gpt-5/gpt-5-mini as of late 2025 — OpenAI has not published per-tier tables for the gpt-5.6 variants), but heavily parallel agentic sessions can still burst past request-per-minute caps. Sustained work may warrant a higher usage tier (tiers advance with cumulative spend).
- **401 `invalid_api_key`** — the key itself is wrong: check for truncation or stray whitespace in `environment_settings.txt`, and remember the container only picks up environment changes after `docker compose down` + `run_daaf.sh` (the shim reads its key at startup).

### Q: A scripted `claude -p` call on a GPT model returned an empty result

Occasionally a GPT turn ends with a reasoning-only block and no visible text, which can surface as an empty `result` field in scripted (non-interactive) `claude -p` usage. This is a GPT quirk, not a DAAF fault, and is only relevant to automated/batch tooling — interactive sessions are unaffected. If you hit it in a script, re-issue the call or add a follow-up turn that requests the answer explicitly.

### Q: How do I control GPT reasoning effort? (Option F)

On the direct-OpenAI shim lane (shim v1.2.2+), every request to OpenAI carries a `reasoning.effort` value, and the shim resolves it from a **four-tier precedence chain** — the first tier present wins:

1. **Per-request signal from Claude Code** — when Claude Code specifies an effort for a turn, that takes precedence over the tiers below. **Important caveat (shim v1.2.3+):** the `/model` reasoning-effort selector in the Claude Code UI does **not** work for GPT slugs. Claude Code gates that selector by model-ID pattern and, for an unrecognized (GPT) slug, pins the per-request signal to `high` on *every* request regardless of what you select — so the selector is inert. To keep it from masking your real preference, the shim treats an inbound `high` as that pin (i.e. as unset) and falls through to the tiers below; any *other* inbound value (`low`, `medium`, etc.) is still honored. The practical consequence: **steer GPT effort with tier 2 or tier 3 below, not the `/model` selector.**
2. **A `#<effort>` suffix on the model slug** — append it in `environment_settings.txt`, e.g. `ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-5.6-terra[1m]#medium`. This works *alongside* the `[1m]` window hint (Claude Code consumes `[1m]` locally and passes `#medium` through), and the shim strips the suffix before the request reaches OpenAI — the backend only ever sees the bare `gpt-5.6-terra`.
3. **The `SHIM_REASONING_EFFORT` env var** — a single default for the whole shim, applied when there is no usable per-request signal and no slug suffix.
4. **The built-in default, `high`** — used when none of the above is set, for posture parity with DAAF's Claude sessions.

Valid values are `none`, `low`, `medium`, `high`, `xhigh`, and `max` (`max` is gpt-5.6-only; `none` disables reasoning). An unrecognized value at any tier is ignored with a log warning and the next tier applies. You can confirm what the shim resolved by checking the shim log (`/daaf/scripts/provider_shim/logs/shim.log`): each request line ends with `effort=<value>:<source>`, where source is one of `inbound`, `slug`, `env`, or `default`. (Because of the v1.2.3 demotion, an inbound `high` with no slug/env override logs `effort=high:default`, not `effort=high:inbound`.) Most users need to set nothing — leaving everything unset gives `high` everywhere. Both the env var and slug suffixes are read at shim startup / request time; changes to `environment_settings.txt` require the usual container recreate. See also the Option F [reasoning-effort paragraph](01_installation_and_quickstart.md#option-f-openai-api-directly-daaf-provider-shim) in the installation guide. If GPT replies also feel *shorter* or *terser* than you expect, that is a separate knob — see [GPT responses feel terse compared to Claude](#q-gpt-responses-feel-terse-compared-to-claude-option-f) below.

### Q: GPT responses feel terse compared to Claude (Option F)

Two things are in play, and only one of them is tunable.

**Model personality (not fully fixable).** DAAF's prompts, agent protocols, and skill documents are written and tuned for Claude, whose default register is comparatively warm and explanatory. A GPT model running the same prompts brings its own default style, which tends to read as more clipped or matter-of-fact. No shim setting fully closes that gap — some of the difference is just the model, and the DAAF prompts can't override a model's underlying voice.

**Response verbosity (tunable).** On the direct-OpenAI shim lane, the shim (v1.2.4+) sends OpenAI's `text.verbosity` control on every request, and it defaults to **`high`** — chosen for parity with DAAF's warm, educational posture (the same rationale as the reasoning-effort default). `high` adds warmth and volume to responses; `low` makes them terse. So by default you are already getting the most expansive setting.

If responses still feel too brief, verbosity is already maxed and the remaining gap is model personality (above). If instead you find GPT responses too *long* or padded, dial verbosity down: set `SHIM_TEXT_VERBOSITY=low` (or `medium`) in `environment_settings.txt`. Valid values are `low`, `medium`, and `high`; the value is read once at shim startup, so a change requires the usual container recreate. You can confirm what the shim resolved via the `/health` endpoint's `text_verbosity` field, and the shim startup log line records it as `text_verbosity=<value>`. This is independent of reasoning effort — [that control](#q-how-do-i-control-gpt-reasoning-effort-option-f) governs how hard the model *thinks*, while verbosity governs how much it *writes*.

### Q: Is my data sent to Anthropic? What about privacy?

The answers are yes and no depending on exactly what we're talking about when we say, "data." Here's the complex picture:

1. **All data analysis and computation happens directly on your machine,** inside the Docker container. DAAF's hooks and safety rails prevent Claude from bulk-uploading or exfiltrating your data files themselves. You can verify this by reading the hook scripts in `.claude/hooks/`.

2. **The analytical output and diagnostics in scripts do transit through Anthropic's servers.** In the process of conducting analysis, DAAF runs diagnostics (like examining sample rows), statistical tests, data visualizations, and report summaries. Because of the way Claude Code works, these analytical outputs are explicitly included in the chats with Claude Code (so it can see what's happening when it runs the code) and inevitably sent to Anthropic as part of the conversation. There is no mechanism by which Claude Code sends entire datasets outside of your machine -- it's really just exposure in these small "chunks" of analytical output.

3. **Whether this exposure is a concern depends on your specific setup.** How Anthropic handles API data is governed by their privacy policy and terms of service. As of this writing, Anthropic states that API inputs and outputs are not used to train models, but you should verify their [current policies](https://www.anthropic.com/policies) yourself. Certain Enterprise agreements with Anthropic have stronger, more FERPA/HIPAA-compliant data handling guarantees, and specific model access protocols (like via AWS Bedrock or Google Vertex AI) offer additional data governance controls that keep data within your organization's cloud infrastructure. The specifics depend entirely on your license and agreement type. This is a main reason why I focused on public datasets for DAAF out-of-the-box.

4. **The container provides additional isolation.** Because DAAF runs inside Docker with dropped capabilities and no privilege escalation, the blast radius of any unexpected behavior is contained (i.e., files it can accidentally upload to the internet, or send via email, or etc. etc.).

5. **DAAF enforces credential safety.** The framework actively prevents reading, writing, or committing files that look like credentials (`.env`, `*.pem`, `*.key`, `environment_settings*`, etc.). It won't prevent everything, but it'll give you a good set of starting guardrails to help protect yourself.

6. **OpenRouter adds an additional hop.** If you use OpenRouter instead of a direct Anthropic connection, your analytical output transits through OpenRouter's servers *in addition to* the underlying model provider. Review [OpenRouter's privacy policy](https://openrouter.ai/privacy) alongside Anthropic's if you choose this route.

**Bottom line:** If you're working with private, proprietary, or otherwise protected non-public data, you need to fully understand the nuances of your specific Anthropic license, agreement type, and access method before using DAAF with that data. Talk to your IT team and legal counsel. Do not mess around here -- do your homework and be a good steward of your data.

---

### Q: Can Claude change its own safety hooks or settings? How do I edit them myself?

No — and that's by design. The hook scripts (`.claude/hooks/`), their logs (`.claude/logs/`), the benchmark harness hooks, and `.claude/settings.json`/`settings.local.json` are the framework's root of trust, so DAAF blocks Claude from modifying them through the shell (`cp`, `mv`, `tee`, output redirection, `sed -i`, `chmod`, etc.). If Claude could overwrite `settings.json` with a shell command, it could deregister every safety hook — so those writes are refused. Claude can still *read* these files (helpful when you ask it to explain a guardrail) and run git index commands like `git add` on them.

To change a hook or a setting yourself, edit the file from **outside** the agent's blocked path: use the browser-based code editor (or any host editor pointed at the Docker volume), or type the change as a `!`-prefixed command in the Claude Code prompt — `!` commands run directly in your shell and are **not** subject to the hooks, so they're your escape hatch for maintaining the safety system. Supported settings edits Claude makes through its `Edit`/`Write` tools still work (those changes are diff-visible for you to review); only opaque shell overwrites are blocked.

### Q: Why can't Claude just `pip install` a package it needs?

Because the container's environment is defined entirely by its Dockerfile, and anything installed at runtime disappears the next time the image is rebuilt — which makes analyses hard to reproduce. To keep the environment reproducible, DAAF blocks runtime package installs (`pip`/`pip3`/`pipx install`, `python -m pip install`, `uv`/`uvx`, `conda install`, etc.); read-only inspection like `pip list` and `pip show` still works. If you genuinely need a new package, add it to the Dockerfile and rebuild: exit the container, then run `bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1` on Windows) from your `daaf-docker` folder. See [Keeping DAAF Updated](01_installation_and_quickstart.md#keeping-daaf-updated) for the rebuild procedure.

---

### Q: Why are the notebook and log viewer ports bound to localhost only?

DAAF's `docker-compose.yml` binds ports 2718 (Marimo notebook), 2719 (session log viewer), and 2720 (code-server browser editor) to `127.0.0.1` — meaning only your local machine can access them. This is a deliberate security measure: Marimo notebooks and code-server are **interactive**, so an unauthenticated server exposed to your local network would allow anyone on that network to execute arbitrary code inside your container.

With localhost binding, the ports are only reachable from your own machine, not from other devices on your WiFi or LAN. code-server additionally requires a password for defense-in-depth.

**If you need to revert this** (e.g., WSL2 port forwarding issues, or you need to access from another device on a trusted network), edit the `ports:` section in `docker-compose.yml` to remove the `127.0.0.1:` prefix:

```yaml
# Localhost only (default, more secure):
- "127.0.0.1:2718:2718"
- "127.0.0.1:2719:2719"
- "127.0.0.1:2720:2720"

# All interfaces (less secure, use only if needed):
- "2718:2718"
- "2719:2719"
- "2720:2720"
```

After changing, rebuild the container — see [Keeping DAAF Updated](01_installation_and_quickstart.md#keeping-daaf-updated) for the procedure.

---

### Q: Is there a free way to use DAAF?

Not in a practical sense for full-pipeline analyses, unfortunately. The free and Pro tiers of Claude simply don't provide enough usage for the volume of work DAAF demands. You might be able to do some lightweight Data Discovery Mode queries (asking what data is available, looking up variable definitions), but a full analysis pipeline will exhaust a lower-tier plan very quickly.

**More flexible and affordable billing via OpenRouter:** [OpenRouter](https://openrouter.ai/) offers pay-per-token access with no monthly subscription commitment (5.5% fee on credit purchases). Critically, OpenRouter also provides access to high-performing open-weight models at a fraction of Anthropic's pricing. **GLM 5.2** [benchmarks competitively with the Opus line](https://daaf.openaugments.org/bench/) at roughly 33% of the cost, and **DeepSeek V4 Flash** offers passable mid-tier performance at roughly 3% of flagship cost. This makes DAAF substantially more accessible than it was even a few months ago — a full pipeline analysis that might cost $50+ with Opus via API could cost under $15 with GLM 5.2 through OpenRouter, or less than $1 with DeepSeek V4 Flash. See the [Installation Guide](01_installation_and_quickstart.md#configure-authentication-via-environment_settingstxt) for setup instructions.

Cost remains a meaningful barrier to entry for DAAF, but it's shrinking. As open-weight models continue to improve and inference costs continue to fall, accessibility will only get better. If you're running DAAF with non-default models, please share your experiences — community feedback on the quality-cost frontier directly informs the guidance here and in the [DAAFBench results](https://daaf.openaugments.org/bench/).

### Q: How much disk space does DAAF use?

The Docker image is roughly **8.61 GB** after building. It includes a Debian Bookworm base image, Python 3.12, 46 pinned Python packages (data science, geospatial, econometrics, visualization, ML), geospatial system libraries (GDAL/GEOS/PROJ), Claude Code, R, 60+ pinned R packages (tidyverse, fixest, survey, sf, and more), and the Quarto CLI. The R runtime, packages, and Quarto account for roughly **2.2 GB** of that total (measured: 8.61 GB with R vs. 6.4 GB without). Docker also keeps build cache layers, so total Docker disk usage may be somewhat higher.

Beyond the image, your Docker volume will grow as you create research projects. Each project accumulates scripts, parquet data files, session logs, and notebooks. A typical full-pipeline project might add 50-500 MB depending on how many datasets you fetch and how large they are.

**To check your Docker disk usage:**
- Open **Docker Desktop** and check the **Images** and **Volumes** sections for size information
- Or from the terminal: `docker system df` shows a breakdown of images, containers, and volumes

**To reclaim space:**
- `docker system prune` removes stopped containers, unused networks, and dangling images
- `docker builder prune` clears the build cache specifically
- Be careful not to remove your `daaf_daaf-data` volume -- that's where your research files live

### Q: Can I use DAAF offline?

No. DAAF requires an active internet connection for two reasons: Claude Code communicates with Anthropic's API for all AI inference (nothing runs locally), and data fetching requires access to data portals like the Urban Institute Education Data Portal. If you lose connectivity mid-session, Claude Code will fail on the next API call, but your work-in-progress files and session state are preserved in the Docker volume -- just reconnect and resume.

### Q: How do I get help understanding or using DAAF itself?

Just ask! DAAF has a dedicated **User Support** mode for questions about the framework itself and the tools it runs on (Docker, Git, Claude Code) -- what it is, how it works, which mode fits your needs, how to troubleshoot setup or tool issues, or how to get the most out of the system. Simply type a question like "What is DAAF?", "How do engagement modes work?", "Something's not working right," "How do I give Docker more memory?", or "Help me understand the pipeline" and DAAF will recognize it as a User Support request. It can also look up official documentation for Docker, Git, and Claude Code online when needed.

In User Support mode, DAAF loads its own documentation and responds conversationally -- no subagents, no formal outputs, no workspace creation. It's just a helpful conversation. When your questions naturally evolve into wanting to *do* something (run an analysis, look up data, debug a script), DAAF will suggest switching to the appropriate mode.

For self-guided reading, the full user documentation suite is in `user_reference/`:
- [**02. Understanding and Working with DAAF**](02_understanding_daaf.md) covers modes, architecture, and what to expect
- [**03. Best Practices**](03_best_practices.md) covers effective prompts, reviewing output, and managing sessions

---

## Packages and Environment

### Q: How do I install additional Python or R packages?

**Python:** The recommended approach is to ask DAAF to add the package to the `Dockerfile` and rebuild the container. For detailed step-by-step instructions, common scenarios, and examples, see [**04. Extending DAAF -- Customizing Your Python and R Environment**](04_extending_daaf.md#the-recommended-path-modify-the-dockerfile-python).

**R:** For quick, session-only use, run `install.packages("pkgname")` inside the container -- the package will be available for the rest of that session but will not survive a container restart. For permanent installation, add the package to the `Dockerfile`'s R package install block and rebuild the container. DAAF uses Posit Package Manager (P3M) with date-pinned snapshots for R package reproducibility, so permanent additions go through the Dockerfile just like Python packages. See [**04. Extending DAAF**](04_extending_daaf.md) for more details.

### Q: Can I use `apt-get` or `sudo` inside the container?

No. The DAAF container runs as a non-root user (`appuser`) with all Linux capabilities dropped and privilege escalation blocked. This is a deliberate security hardening measure -- `apt-get`, `sudo`, and other system-level commands are completely unavailable at runtime.

If you need system-level packages (for example, a C library that a Python package depends on), you'll want to ask DAAF to add them to the `apt-get install` block in the `Dockerfile`. See [**04. Extending DAAF -- Customizing Your Python and R Environment**](04_extending_daaf.md#adding-system-level-dependencies) for the full step-by-step process.

### Q: Will packages I install at runtime persist across restarts?

No. First, a note on *who* can run a runtime install: **DAAF's agents are blocked from runtime package installs** by the bash-safety hook and settings.json deny rules (`pip`/`pip3`/`pipx install`, `python -m pip install`, `uv`/`uvx`, `conda install`, and friends) — see [Why can't Claude just `pip install` a package it needs?](#q-why-cant-claude-just-pip-install-a-package-it-needs) above. *You* can still run a runtime install yourself: type it as a `!`-prefixed command in the Claude Code prompt, or run it from a host terminal into the container — `!` commands and host-shell commands are **not** subject to the hooks.

But even when you install one yourself, it is **ephemeral**. Runtime-installed packages (via `uv pip install --user` or `pip install --user`) are stored in the container's filesystem, which is **separate** from the Docker volume where your research data lives. Your research files, scripts, and outputs persist across restarts because they're in the named volume (`daaf_daaf-data`). But runtime-installed packages live in the container image layer, so they disappear whenever the container is rebuilt or recreated (e.g., after `docker compose down` + `docker compose up -d`, or after `docker compose up -d --build`).

The durable path — the only one that survives a rebuild and keeps your analysis reproducible — is to add the package to the `Dockerfile` and rebuild. See [**04. Extending DAAF -- Customizing Your Python and R Environment**](04_extending_daaf.md#the-recommended-path-modify-the-dockerfile-python) for the full process.

### Q: What package manager does DAAF use?

DAAF uses **[uv](https://docs.astral.sh/uv/)**, a fast Rust-based Python package manager by Astral (the makers of Ruff). It's fully compatible with pip -- it reads the same package index (PyPI) and supports the same package specifiers -- but it's significantly faster, often 10-50x for large installs.

In the `Dockerfile`, packages are installed with `uv pip install --system` (system-wide, during the root build phase) — this is where packages *should* go, since Dockerfile installs are the reproducible, rebuild-durable path.

Runtime installs are a different story. DAAF's agents are **blocked** from runtime installs by the safety hook and deny rules (see [Why can't Claude just `pip install` a package it needs?](#q-why-cant-claude-just-pip-install-a-package-it-needs)), so you cannot ask DAAF to run `uv pip install` for you. If *you* want an ad-hoc, throwaway install for quick testing, run it yourself via a `!`-prefixed command in the prompt or from a host terminal — `uv pip install --user <package>` or `pip install --user <package>` both work (user-local, since you're not root, and both read the same PyPI source). Just remember such installs are **ephemeral** and vanish on the next rebuild; anything you want to keep belongs in the `Dockerfile`.

---

## R and Language Support

### Q: How do I switch between R and Python?

Just tell DAAF. Say something like "I want to use R" or "set execution language to R" at the start of your session, and DAAF will configure itself to write R scripts, use tidyverse for data manipulation, validate with `stopifnot()` and `cat()`, and assemble Quarto notebooks instead of Marimo. This sets a preference in the project configuration that persists across sessions until you change it back.

To switch back, say "set execution language to Python" or "I want to use Python." The framework adjusts everything accordingly -- script templates, validation patterns, notebook format, and library choices.

### Q: Can I mix R and Python in one pipeline?

No. Each DAAF pipeline runs in a single language -- all scripts, validation, and notebooks within a given project use either Python or R, not both. This is by design: mixing languages within a pipeline would break the audit trail, complicate the code review process, and make reproducibility much harder to verify.

That said, parquet files are completely language-agnostic. Data saved by a Python pipeline can be read by an R pipeline and vice versa (R reads them with `arrow::read_parquet()`). So you can absolutely analyze the same dataset in both languages across different projects -- you just can't mix them within a single project's pipeline.

### Q: How do I add an R package?

For quick, session-only use, run `install.packages("pkgname")` inside the container. The package will be available for the rest of that session but will disappear when the container is rebuilt or recreated.

For permanent installation, add the package to the `Dockerfile`'s R package install block and rebuild the container. DAAF uses Posit Package Manager (P3M) with date-pinned snapshots for reproducibility, so all R packages are installed from a consistent, versioned repository. See [**04. Extending DAAF**](04_extending_daaf.md) for the full step-by-step process.

### Q: What R packages come pre-installed?

DAAF ships with 60+ pinned R packages covering the core data science stack: tidyverse (dplyr, tidyr, readr, purrr, stringr, forcats, lubridate), ggplot2, arrow (for parquet I/O), fixest (high-dimensional fixed effects), plm (panel data), survey (complex survey analysis), sf and terra (spatial data), tidymodels (machine learning), plotly, data.table, sandwich, lmtest, modelsummary, marginaleffects, and more. DAAF also includes 11 R library skills that provide curated guidance for using these packages effectively within the framework.

### Q: Are there any known differences between Python and R support?

Python and R are functional peers across the pipeline — the same file-first execution protocol, validation standards, QA review, and notebook assembly apply to both. In the interest of transparency, a few capability asymmetries are worth knowing about:

- **ML interpretation and fairness tooling is deeper on the Python side** (SHAP, fairlearn, LightGBM guidance). R ships iml and fairmodels with tidymodels interpretation/fairness references, but Python's coverage is more mature.
- **gt table export is HTML-first.** Exporting gt tables to PNG requires a headless browser that isn't shipped in the image; save tables as HTML instead.
- **Interactive plotly HTML from R needs internet access to view.** pandoc isn't on the PATH — Quarto bundles a private copy at `/opt/quarto/bin/tools`, but `htmlwidgets::saveWidget(selfcontained = TRUE)` only finds it if the `RSTUDIO_PANDOC` environment variable is exported, which DAAF does not do — so saved R plotly widgets are not self-contained and load their JavaScript from a CDN when opened in a browser.
- **PDF rendering uses Typst, not LaTeX.** Quarto's bundled Typst engine handles PDF output; LaTeX-specific features are not available.
- **Point-pattern spatial analysis is Python-only** (the spatstat package is not installed). Standard vector/raster spatial work is fully supported in R via sf and terra.

None of these affect the core pipeline (fetch, clean, transform, analyze, visualize, report) — they are edge-of-stack differences documented so you're never surprised by them mid-project.

---

## Session Logs and Diagnostics

### Q: Where are session logs stored?

Claude Code automatically archives a complete log of every session when it ends. These are stored locally in `.claude/logs/sessions/` in two formats:

| Format | File Pattern | Purpose |
|--------|-------------|---------|
| **Markdown** (`.md`) | `YYYY-MM-DD_HH-MM-SS_<session-id>_orchestrator.md` | Human-readable transcript with tool calls, timestamps, and token usage |
| **JSONL** (`.jsonl`) | `YYYY-MM-DD_HH-MM-SS_<session-id>_orchestrator.jsonl` | Raw machine-readable transcript (full API-level detail) |
| **Subagent JSONL** | `YYYY-MM-DD_HH-MM-SS_<session-id>_subagent_<agent-id>.jsonl` | Raw transcript for each subagent dispatched during the session |

The orchestrator Markdown archive includes a **Subagent Activity** summary table listing each subagent's type, duration, tool uses, and a final-message excerpt.

Additionally, `.claude/logs/activity.log` records a timestamped entry every time a session starts, giving you a quick overview of usage history.

**These logs are gitignored by default** (they may contain sensitive content or API details), so they stay on your local machine and are never pushed to the repository.

### Q: What happens to session logs if Claude Code crashes or I close the terminal unexpectedly?

They're preserved automatically. On the next session start, DAAF runs a background recovery scan that detects any un-archived transcripts from prior sessions and archives them retroactively. Recovered archives use the timestamp from when the original session last ran (not when recovery discovered them), so they sort chronologically alongside your other session logs.

You don't need to do anything -- just start a new session and recovery happens silently in the background. If you check `.claude/logs/activity.log`, you may occasionally see a line like `RECOVERY: archived 1 session(s)` -- that's the recovery hook doing its job.

### Q: How can I use session logs for debugging?

Session logs are invaluable when something goes wrong. The Markdown logs show you exactly what the assistant did, in order -- every tool call, every file read/write, every subagent invocation, and the full output at each step.

DAAF includes an interactive **DAAF Log Explorer** that renders your session transcripts as a visual timeline in your web browser. It shows the orchestrator's actions as a horizontal timeline bar, with subagent dispatches waterfalling downward. Click any block to see exactly what files were read, written, or executed -- with plain-language descriptions and clickable file references.

The quickest way to access this is from your host machine (no container shell needed):

```bash
cd daaf-docker
bash view_logs.sh            # macOS / Linux
.\view_logs.ps1              # Windows
```

This starts the container if needed, generates an activity manifest from all sessions, and starts the server. Open the URL it prints in the terminal into your browser.

For more specific per-project session log viewing and diagnostics, you can also run it from a terminal inside the container:

```bash
bash /daaf/scripts/collect_session_logs.sh /daaf/research/YYYY-MM-DD_Your_Project
bash /daaf/scripts/generate_log_viewer.sh /daaf/research/YYYY-MM-DD_Your_Project
```

**Note:** The server requires port 2719 to be mapped in your `docker-compose.yml`. If you set up DAAF after this feature was added, it's already there. If not, add `- "127.0.0.1:2719:2719"` under the `ports:` section and restart your container with `docker compose down && docker compose up -d`.

Alternatively, DAAF also processes every individual log transcript into a more intuitive markdown file showing the flow of the conversation alongside tool calling segments.

You can read these by finding the relevant `.md` session log in `.claude/logs/sessions/` (sorted by timestamp). The raw `.jsonl` file contains the complete raw transcript if deeper inspection is needed.


### Q: Are session logs shared or uploaded anywhere?

No. Session logs are gitignored and stay entirely on your local machine (specifically, inside the Docker volume). They are never pushed to the repository, never uploaded to Anthropic, and never shared with anyone. If you choose to file a bug report and include log excerpts, that's your choice -- but the system never does this automatically.

### Q: What about the STATE.md file? How is that different from session logs?

They serve very different purposes:

**Session logs** are a complete, raw transcript of everything that happened in a Claude Code session. They're automatically generated, stored in `.claude/logs/`, and are primarily useful for debugging after the fact. Think of these as a security camera recording -- comprehensive but not curated. You can browse them visually using the DAAF Log Explorer (`bash view_logs.sh` from your `daaf-docker` folder) rather than reading the raw files.

**STATE.md** is a structured progress tracker that DAAF creates during full-pipeline analyses. It lives inside your project folder (`research/[project]/STATE.md`) and tracks what stage the analysis is at, which checkpoints have passed, what decisions were made, and what needs to happen next. It also accumulates the QA Findings Summary (aggregated quality review results across all stages), the Final Review Log (from the data-verifier's end-of-pipeline check), and any Runtime Risks encountered during execution. Its primary purpose is enabling **session recovery** -- if your session runs out of context (the model's working memory fills up), you can start a fresh session and STATE.md tells the new session exactly where to pick up. Think of this as a bookmark with detailed notes.

---

## Technology Choices

### Q: Why Polars instead of Pandas?

A few reasons, and they're all about making AI-generated code more reliable.

**Clarity of intent.** Polars has a much more explicit code syntax. When you chain operations in Polars, what you're doing is unambiguous -- there's generally one obvious way to express a given transformation. Pandas, by contrast, has a lot of historical baggage and multiple ways to do the same thing (`.loc` vs `.iloc` vs `[]`, `apply` vs vectorized operations, etc.). When an AI is generating code, reducing ambiguity is extremely important because it reduces the surface area for subtle bugs. I just think it's way, way easier to skim and read.

**Better performance for the defaults.** Polars is faster than Pandas for most operations, especially on larger datasets, because it's built on Rust and uses lazy evaluation by default. This matters less for small datasets, but education data can get large -- millions of rows across years and states.

**Immutability.** Polars DataFrames are immutable by default -- operations return new DataFrames rather than modifying existing ones in place. This is a huge win for auditing and debugging AI-generated code, because you can always inspect the state before and after a transformation without worrying about hidden mutations.

**Type strictness.** Polars is stricter about types than Pandas, which means type-related bugs surface immediately rather than silently propagating through a pipeline.

That said, Pandas is still installed in the container and available if needed. If you're an R user, DAAF also supports R as a first-class execution language -- R pipelines use tidyverse (dplyr, tidyr, and friends) as their DataFrame library, with the same file-first execution protocol, parquet-based data pipeline, and inline validation standards. Polars syntax is intentionally similar to tidyverse, so the two ecosystems feel quite natural alongside each other. See the [R and Language Support](#r-and-language-support) FAQ section above for more on switching between languages.

### Q: Why Marimo instead of Jupyter?

This one's pretty straightforward: Jupyter notebooks and AI code editors are a terrible combination, and marimo solves nearly all the pain points.

**Version control.** Jupyter notebooks are JSON files with embedded outputs, base64-encoded images, and execution counts. They produce enormous, unreadable diffs in Git, and merge conflicts are essentially impossible to resolve by hand. Marimo notebooks are **plain Python files**. You can diff them, merge them, and read them in any text editor. For a project that's all about auditability and reproducibility, this matters enormously.

**Hidden state.** Jupyter's biggest footgun is that cells can be run out of order, creating hidden state that makes notebooks unreproducible. You can run cell 5, then cell 3, then cell 7, and get results that depend on that exact execution order -- but nothing in the notebook records that order. Marimo enforces a dependency graph between cells. If cell B uses a variable from cell A, marimo *knows* that and won't let you break that relationship. Run them in any order and you get the same result.

**AI editability.** Because marimo notebooks are plain Python, Claude can read and write them the same way it handles any other `.py` file. Editing a Jupyter `.ipynb` file requires manipulating JSON structure, cell metadata, kernel info, and output encodings -- it's fragile and error-prone for AI tools. Marimo is dramatically simpler and more reliable for this use case. Far, far, far easier.

**What about R projects?** R pipelines use **Quarto** (`.qmd` files) instead of Marimo. Quarto is R's native literate programming system -- it combines Markdown narrative with executable R code chunks, and renders to HTML, PDF, or other formats. Just as Marimo is the natural choice for Python (plain `.py` files, reactive execution, Git-friendly), Quarto is the natural choice for R (Markdown-based, knitr engine, first-class R support). The same principles apply: scripts are the primary artifact, and the Quarto document is assembled from completed scripts at the end for presentation.

### Q: Why Docker instead of a virtual environment?

A virtual environment (venv, conda, etc.) handles one thing well: Python package isolation. Docker handles that *plus* a whole lot more that matters for this project.

**Security isolation.** DAAF lets an AI agent write and execute arbitrary code on your behalf. That's inherently risky. Docker runs the entire environment as a non-root user with all Linux capabilities dropped and privilege escalation explicitly blocked. Even if Claude Code somehow tried to `rm -rf /` or `sudo` something malicious, the operating system kernel would stop it cold. A virtualenv gives you none of that -- Claude would run with your full user permissions.

**Complete reproducibility.** Docker pins *everything*: the OS (Debian Bookworm), Python version (3.12), system packages, Python libraries, and Claude Code itself. When I say DAAF works, I mean it works in that exact environment. Virtualenvs only manage Python packages, not system-level dependencies, OS differences, or tool versions.

**Clean recovery.** If something goes wrong -- a corrupted package, a broken state, whatever -- you can tear down the container and rebuild from scratch in minutes. Your research data persists in its Docker volume, and Claude Code's own login and session history persist in a second dedicated volume (`daaf-claude-config`), so both are completely unaffected by a rebuild. (Only an explicit `docker compose down -v` or `docker volume rm` deletes those volumes.) Try doing that with a corrupted virtualenv.

**Cross-platform consistency.** Docker runs the same way on Mac, Windows, and Linux. No more "it works on my machine" problems.

### Q: Why parquet for all data files?

DAAF saves all data exclusively as parquet files, never CSV. Here's why:

**Type preservation.** CSV files have no concept of data types -- everything is text, and your analysis tool has to guess what each column is. Integers, floats, dates, booleans -- it's all just strings in a CSV. Parquet preserves exact types, so a column that's an integer stays an integer, a date stays a date, and you never get bitten by implicit type coercion bugs. When AI is generating data pipelines, removing this entire category of potential errors is a significant win.

**Compression.** Parquet uses columnar compression, so files are dramatically smaller than equivalent CSVs -- often 5-10x smaller. Education datasets can be large, and storage adds up.

**Speed.** Polars (and Pandas, for that matter) reads parquet files much faster than CSV files, especially for large datasets. Parquet also supports reading specific columns without loading the entire file, which is useful for exploration.

**Metadata.** Parquet files carry schema information -- column names, types, and nullability -- right in the file. No more guessing at encodings, delimiters, or quoting rules.

### Q: Why are scripts the primary artifact instead of notebooks?

This is one of DAAF's most distinctive design choices, and it's worth understanding the reasoning.

In most data science workflows, the notebook *is* the work product -- you write code in cells, run them interactively, and the notebook captures both the code and its output. DAAF flips this: **scripts are the primary artifact**, and the notebook is assembled *from* those scripts at the end.

**Reproducibility.** Each script is a self-contained, executable Python or R file that can be run independently from the command line. You don't need a notebook server, you don't need to run cells in a specific order, and there's no hidden state. Run the script, get the output. Every time.

**Audit trail.** Each script includes its own execution log appended as a comment block at the bottom -- the exact output from when it was run, including timestamps, row counts, and validation results. This means the evidence of what happened is embedded directly in the artifact, not in a separate log file you might lose track of.

**Version control.** When a script needs revision (say, the code-reviewer finds a bug), the original script is preserved and a new version is created (`_a.py`/`_a.R`, `_b.py`/`_b.R`). The full history of attempts and fixes is visible in the file system. The notebook (marimo for Python, Quarto for R) only includes the final successful version, but the intermediate attempts remain available for audit.

**Separation of execution from presentation.** The notebook's job in DAAF is to *present* the completed work in an interactive, explorable format -- not to *do* the work. This separation means the notebook can't accidentally introduce bugs or hidden state, because it's literally just displaying what the scripts already produced.

---

## Performance and Configuration

### Q: The analysis seems to be taking a very long time. Is that normal?

Probably, yes. A full-pipeline DAAF analysis is not a quick process, and that's by design.

Here's what's happening under the hood: DAAF breaks every analysis into 12 stages across 5 phases. For the data-heavy stages (5 through 8), *every single script* goes through an execute-then-review cycle -- Claude writes the code, runs it, then a separate instance of Claude reviews it line by line. If the reviewer finds issues, the script gets revised and re-reviewed. This happens for every fetch script, every cleaning script, every transformation script, every analysis script, and every visualization script. It's a lot of work, and it takes time.

**Typical timelines for a full-pipeline analysis:**

| Phase | What's happening | Typical duration |
|-------|-----------------|------------------|
| Phase 1 (Discovery) | Exploring data sources, deep-diving into documentation | 5-15 minutes |
| Phase 2 (Planning) | Creating Plan.md and Plan_Tasks.md, validating them | 20-30 minutes |
| Phase 3 (Data Acquisition) | Fetching data, cleaning it, QA on each script | 30-45 minutes |
| Phase 4 (Analysis) | Transformations, statistical analysis, visualizations, QA on each | 60-90 minutes |
| Phase 5 (Synthesis) | Assembling notebook, writing report, final review | 20-30 minutes |

So a typical full run can easily exceed **2-3 hours of Claude's active processing time**, plus the time you spend reviewing and confirming at phase boundaries (the Phase Status Updates where it pauses and waits for your input).

**What makes things slower:**
- More data sources (each needs its own fetch/clean/QA cycle)
- Complex joins across multiple datasets
- QA revisions (when the code-reviewer catches issues)
- Rate limiting (if you're on a Max subscription and hit your usage window)
- Network latency when fetching data from the Urban Institute portal

**When to worry:** If a single stage seems stuck for more than 20-30 minutes with no progress updates or seeming changes to the window, something may have gone wrong. Check whether Claude is waiting for your input (it pauses at phase boundaries). If it genuinely seems stuck, you can interrupt it with Ctrl+C and ask it to check its STATE.md and resume.

### Q: Can I allocate more resources to the Docker container?

Yes, but it's probably not necessary. DAAF's Docker container is running Claude Code (which talks to Anthropic's servers for the AI part) and Python/R scripts (which run locally for data processing). The AI inference isn't happening on your machine -- it happens on Anthropic's infrastructure. The local compute is just for running Python or R data operations.

That said, if you're working with very large datasets and the Python or R scripts themselves are running slowly, you can adjust Docker Desktop's resource allocation:

1. Open **Docker Desktop**
2. Go to **Settings** (gear icon)
3. Select **Resources**
4. Increase **CPUs** and **Memory** as needed

For most DAAF analyses, the defaults are fine. If you're working with datasets in the tens of millions of rows, bumping memory up to 4-8 GB may help. But honestly, if your data is that large, the bottleneck will be Anthropic's API response time, not local computation.

### Q: Can I run DAAF analyses in parallel?

Yes! Because each Claude Code session runs independently with its own context, you can absolutely open multiple terminal windows, each running their own Claude Code session inside the same Docker container, each working on different research questions simultaneously.

This is one of the exciting aspects of the workflow -- you can kick off an analysis on school enrollment trends, then open a new terminal and start a completely separate analysis on college graduation rates, and they'll run side by side without interfering with each other. Each project gets its own folder in `research/`, its own Plan.md and Plan_Tasks.md, its own STATE.md, and its own set of scripts.

The practical constraint is your Anthropic usage allocation. Each parallel session consumes tokens independently, so running three analyses simultaneously will eat through your Max plan allocation roughly three times as fast. Plan accordingly.

---

## Data Access Issues

### Q: The assistant says data is unavailable or returns empty results

This usually means one of a few things:

**The data legitimately doesn't exist for your request.** Not every dataset covers every year, every state, or every variable combination. Education data has significant publication lags (see the next question), and some data collections simply don't include certain measures. DAAF should tell you what it looked for and why it came up empty.

**The data mirror is down or unreachable.** DAAF fetches data from the Urban Institute Education Data Portal's API. If the portal is experiencing downtime or maintenance, fetches will fail. You can check the portal's status at [educationdata.urban.org](https://educationdata.urban.org/). This is usually temporary -- wait and try again.

**The endpoint or filters are wrong.** Occasionally, the assistant may construct a query that doesn't quite match the API's expected parameters. If you suspect this, check the session logs to see the exact query that was attempted, and compare it against the [Education Data Portal documentation](https://educationdata.urban.org/documentation/).

**What you can do:**
1. Ask DAAF to try a broader query (fewer filters, wider year range) to see if any data is available at all
2. Use Data Discovery Mode to explore what data *is* available for your topic before committing to a full analysis
3. Check the Education Data Portal documentation directly to confirm the data you want actually exists
4. If the portal seems down, wait and try again later

### Q: I'm getting a "KeyError: HARVARD_DATAVERSE_API_KEY" error when fetching election data

Election data (county presidential returns) is hosted on Harvard Dataverse, which requires an API key — unlike the Urban Institute Education Data Portal, which is freely accessible with no authentication.

**To fix this:**

1. Create a free account at [dataverse.harvard.edu](https://dataverse.harvard.edu/)
2. Log in, click your account name (top-right) → **API Token** → **Create Token**
3. Add the key to the `environment_settings.txt` file in your `daaf-docker/` folder on the host:
   ```bash
   HARVARD_DATAVERSE_API_KEY=your_token_here
   ```
   If you don't have an `environment_settings.txt` file yet, copy the template first: `cp environment_settings_example.txt environment_settings.txt` (macOS/Linux) or `Copy-Item environment_settings_example.txt environment_settings.txt` (Windows).
4. Recreate the container: `docker compose down` then `bash run_daaf.sh` (or `.\run_daaf.ps1`)

Alternatively, you can set it manually inside the container before launching Claude Code: `export HARVARD_DATAVERSE_API_KEY="your_token_here"`

See also: [Installation Guide — Data Source API Keys](01_installation_and_quickstart.md#set-up-data-source-api-keys)

### Q: How current is the education data?

Education data has significant publication lags that vary by source. This is not a DAAF limitation -- it's how federal education data works. Agencies need time to collect, clean, validate, and publish data, so the most recent available data is typically 1-3 years behind the current date.

Some rough guidelines as of this writing:

| Data Source | Typical Lag | Example |
|-------------|-------------|---------|
| CCD (K-12 schools) | 1-2 years | In 2026, most recent may be 2023-24 |
| IPEDS (colleges) | 1-2 years | In 2026, most recent may be 2023-24 |
| CRDC (civil rights) | 2-3 years | Less frequent collection cycles |
| Scorecard (outcomes) | 1-2 years | Some earnings data lags further |
| EdFacts (assessments) | 1-2 years | In 2026, most recent may be 2023-24 |

DAAF knows about these lags -- during the Discovery phase (Stage 2), it will check what years are actually available for each data source before proposing an analysis plan. If you ask for data from the current year, it should proactively tell you that data isn't available yet and suggest the most recent available years instead.

### Q: Can I use my own data files instead of the built-in sources?

Yes, and DAAF has a built-in mode for exactly this -- **Data Onboarding Mode**.

Data Onboarding Mode helps you profile a new dataset and create the documentation artifacts (a "skill") that DAAF's other agents need to work with your data effectively. This includes cataloging variables, documenting types and distributions, identifying potential data quality issues, and creating the structured metadata that DAAF uses during analysis.

See [**04. Extending DAAF**](04_extending_daaf.md) for detailed guidance on this process.

**Important caveat:** If you're working with proprietary, sensitive, or regulated data, make sure you've done your due diligence on data governance *before* feeding it to any AI tool. Your data transits through Anthropic's infrastructure for inference. Talk to your IT and legal teams first. I cannot stress this enough.

---

## Common Error Messages

### Q: "STOP: Suppression rate >50%"

This means more than half of the data values in a critical column are suppressed (hidden/masked). Education data is frequently suppressed to protect student privacy -- for example, if a school has fewer than a certain number of students in a demographic group, the data for that group is replaced with a suppression code rather than the actual value.

When more than 50% of your data is suppressed, any statistical analysis on the remaining data would be unreliable at best and misleading at worst. DAAF is being cautious and responsible here by stopping rather than producing garbage results.

**What you can do:**
- **Broaden your scope.** Suppression is more common at granular levels (individual schools) than at aggregate levels (districts, states). Try analyzing at a higher aggregation level.
- **Reduce demographic disaggregation.** Suppression rates increase dramatically when you slice data into small subgroups. Broader demographic categories may have less suppression.
- **Try a different year or time range.** Some years have better coverage than others.
- **Accept the limitation and document it.** Sometimes the data simply isn't there for the analysis you want to do -- that's a genuine finding, not a failure.

### Q: The notebook won't render in my browser

The easiest way to view notebooks is with the convenience script — run `bash view_notebooks.sh` (or `.\view_notebooks.ps1` on Windows) from your `daaf-docker` folder. This handles container startup, port binding, and flag configuration automatically, and includes built-in port conflict detection.

If you're using the manual `marimo run` command and can't see anything at `http://localhost:2718`, check these things in order:

1. **Is the container running?** Check Docker Desktop's Containers panel. The `daaf` container should show as running.

2. **Did you include the right flags?** The command needs `--host 0.0.0.0 --port 2718 --headless` for Docker. The full command should look like:
   ```bash
   marimo run 'research/[your-project]/[notebook-name].py' --host 0.0.0.0 --port 2718 --headless
   ```

3. **Is the port mapped correctly?** Check your `docker-compose.yml` -- the line `"127.0.0.1:2718:2718"` under `ports:` maps the container's port to your host machine. If you changed this, use the host-side port in your browser.

4. **Is something else using port 2718?** See the port conflict question above. (The `view_notebooks` convenience script detects this automatically.)

5. **Try a different browser or incognito/private window.** Occasionally, browser extensions or cached state can interfere.

6. **Check for errors in the terminal.** If marimo itself hit an error (e.g., a missing dependency or a syntax error in the notebook), the error will appear in the terminal where you ran the `marimo run` command.

### Q: How do I view a Quarto notebook (R projects)?

Quarto notebooks (`.qmd`) render to a static HTML file rather than being served live like marimo. From inside the container, render the notebook:

```bash
quarto render research/YYYY-MM-DD_Your_Project/notebook.qmd
```

Then copy the resulting HTML file out to your host machine and open it in any browser:

```bash
# From your host terminal (not inside the container)
docker cp daaf-docker:/daaf/research/YYYY-MM-DD_Your_Project/notebook.html ./notebook.html
```

You can also read the `.qmd` source directly in the browser-based VS Code editor -- it's plain Markdown with R code chunks. See [Installation Guide — Viewing Quarto Documents](01_installation_and_quickstart.md#viewing-quarto-documents) for the full walkthrough.

### Q: "Context utilization CRITICAL" and the session seems to stop

This isn't an error -- it's DAAF being responsible about Claude's working memory.

Claude has a finite context window. As a session progresses and Claude processes more information, that window fills up. Even with large context windows (up to 1M tokens), quality can degrade well before the window is full, so DAAF enforces both percentage-based and absolute token thresholds — whichever fires first.

The exact trigger points depend on which model you are running. Newer models keep their quality across a larger share of their context window, so DAAF gives them higher thresholds; older or unrecognized models get a more conservative set so DAAF errs on the side of caution. DAAF detects the model automatically — nothing to configure. The four status levels and what DAAF does at each are the same for every model; only the trigger points differ:

| Status | What happens | Newer Claude Fable/Mythos models | Opus, Sonnet, and unrecognized models (conservative default) |
|--------|-------------|----------------------------------|--------------------------------------------------------------|
| NOMINAL | Normal operations | below 30% and below 300k tokens | below 40% and below 150k tokens |
| ELEVATED | Works normally but starts delegating more to subagents | ≥ 30% or ≥ 300k tokens | ≥ 40% or ≥ 150k tokens |
| HIGH | Finishes current work, prepares for session restart | ≥ 40% or ≥ 400k tokens | ≥ 60% or ≥ 200k tokens |
| CRITICAL | Stops new work, asks you to restart the session | ≥ 50% or ≥ 500k tokens | ≥ 75% or ≥ 250k tokens |

When you see CRITICAL, it means Claude's context window is nearly full and continuing would degrade the quality of its work. This is by design -- DAAF would rather stop and restart cleanly than continue with increasingly unreliable output.

**What to do:**
1. Claude should have already updated STATE.md with your current progress and provided a restart prompt
2. Copy the restart prompt it gives you
3. Type `/clear` to reset the session (this clears Claude's context but keeps all files intact)
4. Paste the restart prompt into the fresh session
5. Claude will read STATE.md and resume exactly where it left off, with a full fresh context window

This process is seamless when it works well -- the session state system was designed specifically for this scenario. Think of it like saving your game before the battery dies.

### Q: Claude seems to have forgotten earlier instructions or decisions

This is a symptom of **context degradation** -- Claude's working memory is getting full, and earlier information is effectively being crowded out by newer content. It doesn't mean the information is literally gone, but Claude's ability to attend to it decreases as the context fills up.

DAAF has several mechanisms to handle this:

1. **Context monitoring** catches this proactively. The system should flag elevated utilization before it gets this bad.
2. **STATE.md** records all key decisions, so even if Claude "forgets," the information is retrievable from the file.
3. **Plan.md** serves as the methodology specification; **STATE.md** tracks execution progress, QA findings, and runtime state.
4. **Session restart** via Session Recovery gives Claude a completely fresh context window while preserving all progress.

If you notice Claude asking questions it already asked, or making decisions that contradict earlier ones, the best course of action is to prompt it to check its STATE.md and Plan.md, or to restart the session with `/clear` and the restart prompt.

### Q: Claude seems to be making things up about data variables or endpoints

This is one of the most common -- and most important -- symptoms to recognize. If DAAF confidently references variable names, API endpoints, coded value schemes, or data structures that don't match reality, the most likely cause is a **skill or reference file that didn't load properly**.

DAAF has extensive curated knowledge about its supported data sources, stored in skill files. When these skills load correctly, agents have access to exact variable names, precise endpoint paths, correct coded values, and known caveats. When a skill *doesn't* load -- which can happen due to the non-deterministic nature of LLMs -- the agent falls back on its general training data and fills in the gaps with plausible-sounding but potentially incorrect details.

**What to do:**
1. Make sure **Verbose output** is set to **True** in `/config`. This is your primary tool for monitoring how agents are deciding to load or not to load certain reference files.
2. Ask DAAF to verify: "Can you double-check that variable name against the actual skill documentation?" or "Did the agent load the CCD data source skill before writing that script?"
3. If the issue persists, try restarting the session with `/clear` -- a fresh context often resolves loading issues. For Full Pipeline mode, DAAF's session recovery system will pick up where you left off.
4. Report persistent loading failures by [opening an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) -- patterns of failure help us improve DAAF's loading reliability.

For more detail, see [Best Practices — Monitoring DAAF's Internal Reference Loading](03_best_practices.md#monitoring-daafs-internal-reference-loading).

### Q: How can I tell whether a problem comes from DAAF or from Claude Code itself?

Claude Code ships a built-in diagnostic for exactly this question: **safe mode**. Launch it with:

```bash
claude --safe-mode
```

(or set `CLAUDE_CODE_SAFE_MODE=1` in the environment). Safe mode starts Claude Code with **all customizations disabled** — no CLAUDE.md instructions, no skills, no hooks, no MCP servers. (The one exception: settings deployed by an organization's admin policy stay active — not applicable to a standard DAAF install.) That gives you a clean baseline:

- If the problem **persists** in safe mode, it's a Claude Code or environment issue — check the [Claude Code documentation](https://code.claude.com/docs) or run `/doctor`
- If the problem **disappears** in safe mode, one of DAAF's customizations is involved — a good next step is filing an issue with the details

> **⚠️ Warning:** in safe mode, DAAF effectively does not exist. None of its safety guardrails, audit logging, or workflow protocols are active — the model runs with Claude Code's defaults only. Use safe mode strictly for quick diagnosis, never for real analysis work. Exit and restart normally when you're done.

---

## Recommended Next Steps

- [**00. README**](https://github.com/DAAF-Contribution-Community/daaf/tree/main?tab=readme-ov-file#summary-what-is-daaf) — Project overview, quick start, design philosophy, capabilities, and acknowledgments
- [**01. Installation & Quick Start**](01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step setup, day-to-day usage, and troubleshooting
- [**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Community Resources

- **GitHub Issues:** [Report bugs or request features](https://github.com/DAAF-Contribution-Community/daaf/issues)
- **GitHub Discussions:** [Ask questions and share findings](https://github.com/DAAF-Contribution-Community/daaf/discussions)
- **Email:** support@openaugments.org
- **Discord:** [Join the DAAF community](https://discord.gg/daaf) (link TBD)
- **YouTube:** [@brhkim](https://youtube.com/@brhkim) — Video tutorials and walkthroughs
- **Substack:** [DAAF Field Guide](https://daafguide.substack.com) — Deep dives on AI-assisted research
