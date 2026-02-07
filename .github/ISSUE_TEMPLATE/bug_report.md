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
- [ ] Stage 8: Visualization
- [ ] Stage 9-10: Notebook assembly / QA
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

- **OS:** <!-- e.g., Windows 11, macOS 14, Ubuntu 24.04 -->
- **Setup:** <!-- Docker (recommended) or native install -->
- **Auth method:** <!-- API key or Pro/Max subscription -->
- **Claude model:** <!-- e.g., Opus 4.6, Opus 4.5, Sonnet 4.5 — type /model in Claude Code to check -->
- **Claude Code version:** <!-- run `claude --version` inside the container -->

## Additional context

<!-- Anything else that might help — screenshots, data source involved, error messages, etc. -->
