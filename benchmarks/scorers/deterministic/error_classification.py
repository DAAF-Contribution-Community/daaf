"""Classify error-bearing tool results as hook/policy blocks vs genuine failures.

DAAFBench runs surface two very different kinds of ``is_error`` tool results, and
conflating them corrupts any read of model behavior:

* **hook_block** — the tool call was refused by a DAAF or benchmark PreToolUse
  hook, a permission deny, or a project tool-availability policy. This is the
  harness/framework acting AS DESIGNED (e.g. ``enforce-single-command`` refusing
  a chained command). It reflects the model attempting a disallowed action, not a
  broken environment.
* **tool_failure** — a genuine tool / API / environment error (file not found,
  input-validation error, API stall, non-zero exit, oversize file, etc.).

The discrimination patterns below were derived EMPIRICALLY from ~830 real
``is_error`` tool results across archived transcripts under
``benchmarks/results/*/runs/*/`` (catalogued 2026-07-28). Hook/permission
signatures observed include the ``PreToolUse:...hook error:``/``BLOCKED by``
family (enforce-single-command, bash-safety, block-git-writes), the
``Explore subagents are blocked in this project`` policy block, and permission
denials (``requested permissions to ... but you haven't granted``,
``Permission to use ... has been denied``).

Anything error-bearing that matches NEITHER a hook signature NOR a known
genuine-failure signature is counted as ``tool_failures_unclassified`` — it is
never silently folded into ``tool_failures``, so an unrecognized signature stays
visible for future pattern curation rather than inflating the failure count.

Import-light by design: stdlib ``json`` only, so the four runner scripts can
import it without pulling in scoring machinery.
"""

import json
from pathlib import Path

# Substrings (matched case-insensitively) that mark a hook / permission / policy
# block. Checked FIRST — a blocked call is never also a genuine tool failure.
HOOK_BLOCK_SIGNATURES = (
    "blocked by",              # bash-safety.sh / enforce-single-command / block-git-writes
    "hook error:",            # PreToolUse:/PostToolUse: hook stderr prefix
    "pretooluse:",
    "posttooluse:",
    "blocked in this project",  # Explore-subagent / policy blocks
    "requested permissions to",  # permission-deny (grant not yet given)
    "haven't granted",
    "has been denied",         # "Permission to use ... has been denied"
    "permissiondecision",      # deny-shaped hook JSON leaked into content
    "not permitted in this environment",  # bash-safety phrasing
)

# Substrings (case-insensitive) that mark a genuine tool / API / environment
# error. Checked SECOND (after hook signatures). Anything error-bearing that
# matches neither list is 'unclassified' and surfaced separately.
TOOL_FAILURE_SIGNATURES = (
    "does not exist",
    "no such file or directory",
    "exceeds maximum",
    "tool_use_error",
    "inputvalidationerror",
    "is missing",              # "The required parameter `x` is missing"
    "unexpected parameter",
    "api error",
    "terminated early",
    "prompt is too long",
    "backend server error",
    "stalled",
    "exit code",
    "no such tool available",
    "has not been read yet",
    "command not found",
    "directory does not exist",
    "traceback",
    "request interrupted",
    "syntax error",
    "too_small",
)


def classify_error_content(content: str) -> str:
    """Classify one error-bearing tool-result content string.

    Returns one of ``"hook_block"``, ``"tool_failure"``, or
    ``"tool_failure_unclassified"``. Hook/permission signatures win over
    genuine-failure signatures because a blocked call reports as an error but is
    the framework acting as designed.
    """
    if not content:
        return "tool_failure_unclassified"
    low = str(content).lower()
    for sig in HOOK_BLOCK_SIGNATURES:
        if sig in low:
            return "hook_block"
    for sig in TOOL_FAILURE_SIGNATURES:
        if sig in low:
            return "tool_failure"
    return "tool_failure_unclassified"


def _iter_transcript_error_contents(transcript_path, skip_lines=0):
    """Yield the content string of every ``is_error`` tool_result in a .jsonl
    transcript. Best-effort: malformed lines and unreadable files are skipped.

    ``skip_lines`` drops the first N physical lines before scanning, mirroring
    ``extract_new_tool_calls``'s ``lines[checkpoint_line_count:]`` slice. For a
    parent transcript that carries a prepended golden-checkpoint prefix, pass the
    golden line count so only the post-checkpoint benchmark run is classified;
    the prefix's tool_results (framework setup, not model behavior) are excluded.
    Subagent transcripts have no such prefix and are scanned in full (skip=0)."""
    p = Path(transcript_path)
    if not p.exists():
        return
    try:
        with open(p, "r") as f:
            for lineno, line in enumerate(f):
                if lineno < skip_lines:
                    continue
                line = line.strip()
                if not line or '"is_error"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if not isinstance(obj, dict):
                    continue
                msg = obj.get("message", {})
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_result" or not block.get("is_error"):
                        continue
                    c = block.get("content", "")
                    if isinstance(c, list):
                        c = " ".join(
                            x.get("text", "") for x in c if isinstance(x, dict)
                        )
                    yield str(c)
    except OSError:
        return


def compute_error_counts(
    tool_failures,
    subagent_transcripts=None,
    parent_transcript=None,
    parent_skip_lines=0,
) -> dict:
    """Aggregate error-bearing tool results into the three diagnostic buckets.

    ``tool_failures`` is the parent-transcript failure list already extracted by
    the harness (``executor._extract_tool_failures`` → each entry a dict with a
    ``content`` string). ``subagent_transcripts``, when given, is an iterable of
    transcript file paths whose ``is_error`` tool_results are scanned and
    classified too, so a run's counts cover its dispatched subagents as well as
    the parent. ``parent_transcript`` (single path) is scanned skipping its first
    ``parent_skip_lines`` lines — pass the run's golden-checkpoint line count so
    only post-checkpoint content is classified (the golden prefix is framework
    setup, not model behavior). Cold-start phases pass ``parent_skip_lines=0``.

    NOTE (2026-07-28, W1/I2): these transcript scans see the FULL, untruncated
    tool_result content and the WHOLE post-checkpoint transcript, unlike the
    legacy ``result.tool_failures`` path (executor-extracted, truncated to the
    first 500 chars). Bucket classifications can therefore differ from
    pre-2026-07-28 runs — a signature past char 500 that the legacy path missed
    is now seen, so a run may reclassify from ``unclassified`` to a named bucket.

    Returns ``{"hook_blocks": n, "tool_failures": n,
    "tool_failures_unclassified": n}`` — additive fields for result.json.
    """
    counts = {"hook_blocks": 0, "tool_failures": 0, "tool_failures_unclassified": 0}
    _bucket = {
        "hook_block": "hook_blocks",
        "tool_failure": "tool_failures",
        "tool_failure_unclassified": "tool_failures_unclassified",
    }
    for tf in tool_failures or []:
        content = tf.get("content", "") if isinstance(tf, dict) else str(tf)
        counts[_bucket[classify_error_content(content)]] += 1
    if parent_transcript:
        for content in _iter_transcript_error_contents(
            parent_transcript, skip_lines=parent_skip_lines
        ):
            counts[_bucket[classify_error_content(content)]] += 1
    for tp in subagent_transcripts or []:
        for content in _iter_transcript_error_contents(tp):
            counts[_bucket[classify_error_content(content)]] += 1
    return counts
