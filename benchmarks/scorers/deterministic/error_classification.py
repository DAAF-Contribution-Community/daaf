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
import re
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


# --- C4: additive tool-failure sub-classification -------------------------
# classify_tool_failure_class() assigns an already-observed tool failure a finer
# operational CAUSE so failures can be triaged (transient infra vs capacity vs
# config vs model behavior) without changing any scoring. It is additive and
# non-scoring, operates on the stored (truncated) error string, and is
# precedence-ordered: the FIRST matching rule wins.

# Transient infrastructure signatures: the backend dropped or stalled the
# stream, or returned an empty HTTP 200. These are the candidates for a bounded
# retry (the retry itself is DEFERRED — not implemented here).
INFRA_TRANSIENT_SIGNATURES = (
    "stream closed",
    "stalled mid-stream",
    "empty response body",   # empty-200: HTTP 200 with no content
    "empty 200",
    "200 with no body",
)

# Backend capacity refusal: the request context exceeded the model's window.
CAPACITY_PROMPT_SIGNATURES = (
    "prompt is too long",
)

# ChatGPT / Codex lane routing refusal. Only an infra_config cause when the
# rejected model id equals the run's configured child model id; a refusal naming
# a DIFFERENT model id means the model tried to route elsewhere → model_error.
LANE_CONFIG_SIGNATURES = (
    "not available via the chatgpt",
    "(codex) lane",
)

# Quota / rate-limit capacity signatures (plain substrings).
CAPACITY_QUOTA_SIGNATURES = (
    "quota",
    "rate limit",
    "too many requests",
    "http 429",
    "status 429",
    "error 429",
    "429 too many requests",
)

# Standalone HTTP 429 status code. A bare "429" substring false-matches trace
# ids ("trace-84290fae") and token counts ("4293 tokens"), so the code is only
# a capacity signal when it stands alone as a number — a "429" not glued to an
# adjacent digit or word character. \b429\b requires non-word boundaries on both
# sides, so "84290" (surrounded by digits) and "4293" (trailing digit) do not
# match, while "HTTP 429 Too Many Requests" / "error: 429" / "code 429." do.
_STANDALONE_429_RE = re.compile(r"\b429\b")


# Characters that can continue a model id (letters, digits, and the id
# punctuation ``. _ - [ ]``). A configured id counts as "named by the error"
# only when it is NOT immediately preceded or followed by one of these — so an
# extension like ``[1m]`` glued to the id (``gpt-5.6-terra[1m]``) is treated as a
# DIFFERENT id, never a match for the bare ``gpt-5.6-terra``.
_ID_CONTINUATION = r"[A-Za-z0-9._\[\]-]"


def _error_names_model_id(low_error_text: str, configured_child_model_id) -> bool:
    """True when the (lowercased) error text names EXACTLY the configured id.

    Delimiter-aware, not bare-substring: the configured id matches only when it
    is not immediately adjacent to an id-continuation character on either side.
    This distinguishes ``gpt-5.6-terra`` (configured) from a rejected
    ``gpt-5.6-terra[1m]`` (a different id → NOT a match → model_error) and,
    symmetrically, a configured ``gpt-5.6-terra[1m]`` from a rejected bare
    ``gpt-5.6-terra``. An exact-id occurrence still matches.
    """
    esc = re.escape(str(configured_child_model_id).lower())
    pattern = rf"(?<!{_ID_CONTINUATION}){esc}(?!{_ID_CONTINUATION})"
    return re.search(pattern, low_error_text) is not None


def classify_tool_failure_class(error_text, configured_child_model_id=None) -> str:
    """Assign a tool failure a finer operational cause (additive, non-scoring).

    Returns one of:
      ``policy_hook``      — a DAAF/benchmark hook or permission block
      ``infra_transient``  — dropped/stalled stream or empty-200 (retry candidate)
      ``capacity_limit``   — prompt-too-long, or a quota / 429 refusal
      ``infra_config``     — ChatGPT/Codex lane refusal of the CONFIGURED child model
      ``model_error``      — everything else, including a lane refusal naming a
                             DIFFERENT model id than the configured child (the
                             model mis-routing itself, e.g. a model-authored
                             ``claude-fable-5`` on a Terra run)

    Precedence is first-match-wins in the order above. One consequence is
    intentional: when a quota / 429 capacity signal CO-OCCURS with a transient
    signal (e.g. ``"HTTP 429 rate limit; stream closed"``), the transient rule
    (2) is reached before the capacity rule (5), so the failure classifies
    ``infra_transient`` — a dropped/stalled stream is the actionable, retryable
    cause and takes priority over the co-reported rate-limit note.

    ``error_text`` is the stored error string passed by the caller (the executor
    supplies the extracted tool-result content). ``configured_child_model_id`` is
    the run's configured child model id
    (``result.model_identity.requested_model_id``); when it is None and the lane
    pattern matches, the cause falls back to ``infra_config`` because the
    mismatch branch cannot be evaluated without it.
    """
    if not error_text:
        return "model_error"
    low = str(error_text).lower()

    # 1. policy_hook — a blocked call is the framework acting as designed.
    for sig in HOOK_BLOCK_SIGNATURES:
        if sig in low:
            return "policy_hook"

    # 2. infra_transient — dropped/stalled stream or empty-200.
    for sig in INFRA_TRANSIENT_SIGNATURES:
        if sig in low:
            return "infra_transient"

    # 3. capacity_limit — prompt exceeds the model window.
    for sig in CAPACITY_PROMPT_SIGNATURES:
        if sig in low:
            return "capacity_limit"

    # 4. ChatGPT / Codex lane refusal. infra_config only when the rejected model
    #    id equals the configured child id; a refusal naming a DIFFERENT model is
    #    the model mis-routing itself → model_error. With no configured id to
    #    compare against, fall back to infra_config.
    if any(sig in low for sig in LANE_CONFIG_SIGNATURES):
        if configured_child_model_id is None:
            return "infra_config"
        if _error_names_model_id(low, configured_child_model_id):
            return "infra_config"
        return "model_error"

    # 5. capacity_limit — quota / rate-limit refusal, or a standalone HTTP 429.
    for sig in CAPACITY_QUOTA_SIGNATURES:
        if sig in low:
            return "capacity_limit"
    if _STANDALONE_429_RE.search(low):
        return "capacity_limit"

    # 6. default.
    return "model_error"


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
