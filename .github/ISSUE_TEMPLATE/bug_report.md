---
name: Bug Report
about: Something went wrong during an analysis or interaction
title: "[Bug] "
labels: bug
assignees: ''
---

## What happened?

<!-- A clear description of the bug. What did you observe? -->

## What did you ask the assistant to do?

<!-- Paste your prompt or describe the request. -->

## What did you expect to happen?

<!-- What should have happened instead? -->

## Which stage failed?

<!-- If you can tell, which part of the workflow broke? Check all that apply. -->

- [ ] Stage 1-3: Discovery / data exploration
- [ ] Stage 4: Planning
- [ ] Stage 5: Data fetch
- [ ] Stage 6: Data cleaning
- [ ] Stage 7: Transformation / analysis
- [ ] Stage 8: Analysis & Visualization
- [ ] Stage 9: Notebook assembly
- [ ] Stage 10: QA aggregation
- [ ] Stage 11-12: Report / final review
- [ ] Not sure / other

## Session log excerpt

<!--
Check .claude/logs/sessions/ for the Markdown (.md) log from this session.
Find the section where things went wrong and paste it below.
IMPORTANT: Redact any API keys, personal file paths, or sensitive data before posting.
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

<!-- Anything else that might help — screenshots, data source involved, error messages, etc. -->
