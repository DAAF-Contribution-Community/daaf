# Learning Signal Extraction

After verifying subagent output, extract any Learning Signal:

1. Check if subagent output contains a `**Learning Signal:**` field
2. If value is "None" → skip
3. If value is present → append to STATE.md "Pending Learning Signals" buffer:
   ```
   - [Stage N.step] [Category] — [Signal text]
   ```
4. Do NOT write to LEARNINGS.md on every signal — wait for flush triggers

**Flush Triggers** (write buffered signals to LEARNINGS.md):
- Phase boundary completion (end of Phase 1, 2, 3, or 4)
- After BLOCKER resolution
- After debugger session
- At utilization gates (40%, 60%)

**Flush is lightweight:** Read buffer → categorize into LEARNINGS.md sections → append → clear buffer. Not a subagent invocation.
