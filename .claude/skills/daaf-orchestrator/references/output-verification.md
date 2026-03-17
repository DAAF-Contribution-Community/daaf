# Subagent Output Verification Protocol

**CRITICAL:** Before integrating subagent findings into the Plan or proceeding to the next stage, verify that subagent output meets orchestrator expectations.

**Verification Checklist:**

| Check | What to Verify | Action if Failed |
|-------|----------------|------------------|
| **Size** | Output is under 1000 words | Extract only structured summary fields; discard verbose sections, raw logs, and data samples before integrating into context. If chronic, re-invoke with emphasis on the 1000-word hard cap. |
| **Completeness** | All required output sections present | Re-invoke with clarification |
| **Format** | Output matches specified OUTPUT FORMAT | Re-invoke with format emphasis |
| **Confidence** | No LOW confidence items without resolution | Request resolution or escalate |
| **Substantive** | Real findings, not template placeholders | Re-invoke with thoroughness emphasis |

**Verification Procedure:**

1. **After subagent returns findings:**
   - Review output against the OUTPUT FORMAT specification provided in the prompt
   - Check that all required sections contain substantive content
   - Verify any confidence assessments (HIGH/MEDIUM/LOW)
   - Confirm no placeholder text remains (e.g., "[add more]", "[description]")

2. **If verification fails (first time):**
   - Re-invoke subagent with clarification about what's missing
   - Provide more specific context or examples
   - Emphasize the missing elements

3. **If verification fails (second time):**
   - Re-invoke with simplified task scope
   - Break complex tasks into smaller subtasks
   - Consider if task is feasible with available skills

4. **If verification fails (third time):**
   - STOP execution
   - Escalate to user with explanation of what couldn't be completed
   - Propose alternative approaches

**Example Verification:**

```markdown
**Subagent Output Review: Stage 2 (Data Exploration)**

Checklist:
- [x] Recommended Data Level specified
- [x] Candidate Endpoints table complete (3 endpoints found)
- [x] Key Variables table complete (8 variables identified)
- [x] Variables Flagged for Deep-Dive (2 flagged with reasons)
- [x] Limitations Encountered documented
- [x] Completeness Assessment all items checked
- [x] Confidence: HIGH (multiple sources confirm)

Status: VERIFIED - Proceeding to Stage 3
```

**Code-Reviewer Output Verification (Additional):**

When verifying code-reviewer QA reports specifically, also check:
- [ ] cr1 includes at least 5 script-specific checks (one per Skeptical Lens) and 5 spot-checks
- [ ] cr1 includes data profiling section; if multiple iterations, each has documented trigger
- [ ] Report includes reasoning (WHY correct, not just WHAT was checked)
- [ ] Adversarial analysis section has substantive content (not boilerplate)
- [ ] If PASSED: report articulates basis for confidence, not just absence of failures
- [ ] Report includes Investigation Narrative synthesizing across all iterations
- [ ] If capped at 5 iterations: "Additional Strands of Inquiry" section present

If the QA report reads like a template with values filled in and no script-specific reasoning, it has not met the review depth expectation. Consider re-invoking with emphasis on adversarial analysis.
