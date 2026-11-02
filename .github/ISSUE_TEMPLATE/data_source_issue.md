---
name: Data Source Issue
about: Problem with a specific data source — wrong data, missing variables, data access/mirror errors
title: "[Data] "
labels: data
assignees: ''
---

## Which data source?

<!-- Check all that apply. -->

- [ ] CCD (Common Core of Data)
- [ ] CRDC (Civil Rights Data Collection)
- [ ] EDFacts
- [ ] IPEDS
- [ ] College Scorecard
- [ ] MEPS (Model Estimates of Poverty in Schools)
- [ ] SAIPE
- [ ] FSA (Federal Student Aid)
- [ ] PSEO
- [ ] NACUBO
- [ ] EADA
- [ ] Campus Safety
- [ ] NHGIS
- [ ] NCCS
- [ ] County Presidential Returns (MIT Election Data and Science Lab)
- [ ] Other: <!-- specify -->

## What went wrong?

<!-- Describe the issue — wrong values, missing columns, a download error, unexpected row counts, etc. -->

## What query or variables were involved?

<!-- If you can identify them — the data file (mirror path or download URL), variable names, filters used, year range, etc. -->

## What the data looked like vs. what you expected

<!-- e.g., "Got 0 rows when I expected ~5,000" or "enrollment column was all -1 for 2022" -->

## Session log excerpt

<!--
If available, paste the relevant section from .claude/logs/sessions/.
IMPORTANT: Redact any API keys or sensitive data.
-->

<details>
<summary>Session log</summary>

```
(paste relevant session log excerpt here)
```

</details>

## Environment

- **DAAF version:** <!-- see "DAAF Version" in your session log header (.claude/logs/sessions/*.md) -->
- **Claude Code version:** <!-- run `claude --version` inside the container (Control Panel option 6, Open Terminal in Container) -->
- **Model:** <!-- the exact model name: see "Model" in your session log header, or type /model in Claude Code -->
- **Provider route:** <!-- one of: Anthropic subscription (say which plan), Anthropic API key, ChatGPT subscription through DAAF's provider shim, OpenAI API key through the provider shim (or an institutional gateway), OpenRouter, AWS Bedrock, Google Vertex AI -->
- **Host OS:** <!-- the computer that runs Docker, e.g., Windows 11, macOS 15, Ubuntu 24.04 -->

## Additional context

<!-- Anything else — links to the data provider's documentation, screenshots, related issues, etc. -->
