#!/usr/bin/env python3
"""
generate_log_viewer.py — DAAF Session Log Manifest Builder

Standalone CLI tool that parses DAAF session JSONL logs and produces a
session_manifest.json for the HTML viewer.

Usage:
    python3 generate_log_viewer.py <project_path>
    python3 generate_log_viewer.py --logs-dir <logs_directory>

Arguments:
    project_path: Absolute path to a DAAF research project
                  (e.g., /daaf/research/2026-03-29_College_...)
    --logs-dir:   Direct path to a directory containing JSONL files
                  (e.g., /daaf/.claude/logs/sessions for archive mode)

Output:
    {logs_dir}/session_manifest.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from glob import glob


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAAF_ROOT = "/daaf/"

SKIP_RECORD_TYPES = {"file-history-snapshot", "queue-operation"}

TOOL_CATEGORY_MAP = {
    "Read": "read",
    "Write": "write",
    "Edit": "write",
    "Bash": "execute",
    "Glob": "read",
    "Grep": "read",
    "Skill": "skill",
    "Agent": "delegate",
    "WebSearch": "search",
    "WebFetch": "search",
    "TaskCreate": "track",
    "TaskUpdate": "track",
    "NotebookEdit": "write",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def strip_daaf_prefix(path):
    """Strip /daaf/ prefix to make paths relative to DAAF root."""
    if path and path.startswith(DAAF_ROOT):
        return path[len(DAAF_ROOT):]
    return path


def safe_json_loads(line, line_num, filepath):
    """Parse a JSON line, returning None on failure."""
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        print(f"  WARNING: Malformed JSON at line {line_num} in {os.path.basename(filepath)}, skipping")
        return None


def iso_timestamp():
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def duration_between(start_iso, end_iso):
    """Compute seconds between two ISO timestamps. Returns 0.0 on error."""
    try:
        fmt_options = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
        ]
        t_start = None
        t_end = None
        for fmt in fmt_options:
            if t_start is None:
                try:
                    t_start = datetime.strptime(start_iso, fmt)
                except ValueError:
                    pass
            if t_end is None:
                try:
                    t_end = datetime.strptime(end_iso, fmt)
                except ValueError:
                    pass
        if t_start and t_end:
            return round((t_end - t_start).total_seconds(), 1)
    except Exception:
        pass
    return 0.0


def truncate(text, max_len):
    """Truncate text to max_len characters with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def extract_bash_file_paths(command):
    """Extract file paths from a Bash command string."""
    import re
    paths = []
    # Match absolute paths (starting with /)
    for match in re.finditer(r'(?:^|\s)(/\S+)', command):
        p = match.group(1).rstrip(';,|&)')
        # Skip common non-file arguments
        if p in ('/', '/dev/null') or p.startswith('/proc/') or p.startswith('/sys/'):
            continue
        # Must look like a real file path (has at least one directory separator beyond root)
        if '/' in p[1:]:
            paths.append(strip_daaf_prefix(p))
    return paths


def tool_description(tool_name, tool_input):
    """Build human-readable description for a tool call."""
    inp = tool_input or {}

    if tool_name == "Read":
        path = strip_daaf_prefix(inp.get('file_path', ''))
        desc = f"Read {path}"
        offset = inp.get('offset')
        limit = inp.get('limit')
        if offset and limit:
            end_line = offset + limit - 1
            desc += f" (lines {offset}-{end_line})"
        elif offset:
            desc += f" (from line {offset})"
        elif limit:
            desc += f" (first {limit} lines)"
        return desc
    elif tool_name == "Write":
        path = strip_daaf_prefix(inp.get('file_path', ''))
        return f"Wrote {path}"
    elif tool_name == "Edit":
        path = strip_daaf_prefix(inp.get('file_path', ''))
        return f"Edited {path}"
    elif tool_name == "Bash":
        cmd = inp.get("command", "")
        desc = inp.get("description", "")
        if desc:
            return f"Ran command: {desc}"
        return f"Ran: {cmd}"
    elif tool_name == "Glob":
        pattern = inp.get('pattern', '')
        path = inp.get('path', '')
        desc = f"Searched for files matching {pattern}"
        if path:
            desc += f" in {strip_daaf_prefix(path)}"
        return desc
    elif tool_name == "Grep":
        pattern = inp.get('pattern', '')
        desc = f"Searched file contents for '{pattern}'"
        if inp.get("path"):
            desc += f" in {strip_daaf_prefix(inp['path'])}"
        mode = inp.get("output_mode", "")
        if mode == "content":
            desc += " (showing matches)"
        elif mode == "count":
            desc += " (counting matches)"
        return desc
    elif tool_name == "Skill":
        skill_name = inp.get('skill', '')
        return f"Loaded skill: {skill_name}"
    elif tool_name == "Agent":
        agent_type = inp.get("subagent_type", "agent")
        description = inp.get("description", "")
        return f"Dispatched {agent_type} specialist: {description}"
    elif tool_name == "WebSearch":
        return f"Web search: '{inp.get('query', '')}'"
    elif tool_name == "WebFetch":
        return f"Fetched URL: {inp.get('url', '')}"
    elif tool_name == "TaskCreate":
        return f"Created task: {inp.get('subject', '')}"
    elif tool_name == "TaskUpdate":
        return f"Updated task #{inp.get('taskId', '')}"
    elif tool_name == "NotebookEdit":
        return "Edited notebook cell"
    else:
        return f"Tool: {tool_name}"


def tool_target(tool_name, tool_input):
    """Extract file path target from a tool call, if applicable."""
    inp = tool_input or {}
    if tool_name in ("Read", "Write", "Edit"):
        return strip_daaf_prefix(inp.get("file_path", ""))
    elif tool_name == "Glob":
        return inp.get("pattern", "")
    elif tool_name == "Grep":
        p = inp.get("path")
        if p:
            return strip_daaf_prefix(p)
    elif tool_name == "Skill":
        skill_name = inp.get("skill", "")
        if skill_name:
            return f".claude/skills/{skill_name}/SKILL.md"
    elif tool_name == "Bash":
        paths = extract_bash_file_paths(inp.get("command", ""))
        if paths:
            return paths[0]
    return None


def tool_extra_targets(tool_name, tool_input):
    """Extract additional file path targets beyond the primary one (e.g., multiple paths in Bash)."""
    inp = tool_input or {}
    if tool_name == "Bash":
        paths = extract_bash_file_paths(inp.get("command", ""))
        if len(paths) > 1:
            return paths[1:]
    return []


def tool_category(tool_name):
    """Map tool name to activity type category."""
    return TOOL_CATEGORY_MAP.get(tool_name, "other")


def extract_text_from_content(content):
    """Extract concatenated text from a content array or string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def extract_user_text(content):
    """Extract user-visible text from content, skipping tool results."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


# ---------------------------------------------------------------------------
# Agent Frontmatter Parsing
# ---------------------------------------------------------------------------


def extract_agent_frontmatter_skills(agent_type):
    """Extract skills list from an agent definition file's YAML frontmatter."""
    if not agent_type:
        return []
    agent_file = os.path.join(DAAF_ROOT, ".claude", "agents", f"{agent_type}.md")
    if not os.path.exists(agent_file):
        return []
    try:
        import yaml
        with open(agent_file, "r", encoding="utf-8") as f:
            content = f.read(4096)
        if not content.startswith("---"):
            return []
        end_idx = content.index("---", 3)
        frontmatter = content[3:end_idx]
        parsed = yaml.safe_load(frontmatter)
        if not isinstance(parsed, dict):
            return []
        skills = parsed.get("skills")
        if skills is None:
            return []
        if isinstance(skills, str):
            return [skills]
        if isinstance(skills, list):
            return [str(s) for s in skills if s]
        return []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# JSONL Loading
# ---------------------------------------------------------------------------


def load_jsonl(filepath):
    """Load a JSONL file, returning list of (line_number, record) tuples."""
    records = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                rec = safe_json_loads(line, i, filepath)
                if rec is not None:
                    rec["_line"] = i
                    rec["_file"] = filepath
                    records.append((i, rec))
    except Exception as e:
        print(f"  WARNING: Could not read {filepath}: {e}")
    return records


# ---------------------------------------------------------------------------
# Session Grouping
# ---------------------------------------------------------------------------


def group_files_by_session(logs_dir):
    """
    Group JSONL files by session prefix.
    Returns dict: session_prefix -> {"orchestrator": path, "subagents": {agent_short_id: path}}
    """
    jsonl_files = sorted(glob(os.path.join(logs_dir, "*.jsonl")))
    sessions = {}

    for fpath in jsonl_files:
        fname = os.path.basename(fpath)
        # Expected patterns:
        #   {date}_{time}_{sessionShort}_orchestrator.jsonl
        #   {date}_{time}_{sessionShort}_subagent_{agentShortId}.jsonl
        parts = fname.replace(".jsonl", "").split("_")

        # Find the session prefix: date_time_sessionShort
        # Format: YYYY-MM-DD_HH-MM-SS_XXXXXXXX
        if len(parts) < 4:
            continue

        # date = parts[0], time = parts[1], sessionShort = parts[2]
        session_prefix = f"{parts[0]}_{parts[1]}_{parts[2]}"

        if session_prefix not in sessions:
            sessions[session_prefix] = {"orchestrator": None, "subagents": {}}

        if "orchestrator" in fname:
            sessions[session_prefix]["orchestrator"] = fpath
        elif "subagent" in fname:
            # Extract agent short ID (the part after "subagent_")
            subagent_idx = fname.index("subagent_") + len("subagent_")
            agent_short = fname[subagent_idx:].replace(".jsonl", "")
            sessions[session_prefix]["subagents"][agent_short] = fpath

    return sessions


# ---------------------------------------------------------------------------
# Streaming Chunk Merging
# ---------------------------------------------------------------------------


def merge_streaming_chunks(records):
    """
    Merge consecutive assistant records sharing the same message.id.

    Returns a new list of (line_number, record) tuples with merged content.
    Non-assistant records pass through unchanged.
    """
    merged = []
    i = 0
    while i < len(records):
        line_num, rec = records[i]
        msg = rec.get("message", {})

        # Only merge assistant records with a message.id
        if rec.get("type") != "assistant" or not msg.get("id"):
            merged.append((line_num, rec))
            i += 1
            continue

        msg_id = msg["id"]
        chunk_group = [(line_num, rec)]

        # Collect consecutive assistant records with the same message.id
        j = i + 1
        while j < len(records):
            next_line, next_rec = records[j]
            next_msg = next_rec.get("message", {})
            if next_rec.get("type") == "assistant" and next_msg.get("id") == msg_id:
                chunk_group.append((next_line, next_rec))
                j += 1
            else:
                break

        if len(chunk_group) == 1:
            # No merging needed
            merged.append((line_num, rec))
            i += 1
            continue

        # Merge the chunks
        first_line, first_rec = chunk_group[0]
        last_line, last_rec = chunk_group[-1]

        # Build merged content by deduplicating blocks
        seen_tool_ids = set()
        seen_text_hashes = set()
        merged_content = []

        for _, chunk_rec in chunk_group:
            chunk_content = chunk_rec.get("message", {}).get("content", [])
            if isinstance(chunk_content, list):
                for block in chunk_content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")

                    if btype == "tool_use":
                        # Deduplicate by tool_use id
                        tid = block.get("id")
                        if tid and tid in seen_tool_ids:
                            continue
                        if tid:
                            seen_tool_ids.add(tid)
                        merged_content.append(block)

                    elif btype == "thinking":
                        # Keep last thinking block (later chunks supersede)
                        # Use signature as dedup key if present, otherwise hash
                        sig = block.get("signature", "")
                        key = f"thinking:{sig}" if sig else f"thinking:{hash(block.get('thinking', '')[:200])}"
                        if key not in seen_text_hashes:
                            seen_text_hashes.add(key)
                            merged_content.append(block)

                    elif btype == "text":
                        # Later text blocks may contain earlier text plus more.
                        # Keep only the last (longest) text block.
                        txt = block.get("text", "")
                        # Replace any earlier text blocks with this one
                        # by tracking and updating
                        merged_content = [
                            b for b in merged_content
                            if b.get("type") != "text" or b.get("text", "") not in txt
                        ]
                        merged_content.append(block)
                    else:
                        merged_content.append(block)

        # Find usage from the chunk with stop_reason != null
        final_usage = None
        final_stop_reason = None
        for _, chunk_rec in chunk_group:
            chunk_msg = chunk_rec.get("message", {})
            sr = chunk_msg.get("stop_reason")
            if sr is not None:
                final_usage = chunk_msg.get("usage")
                final_stop_reason = sr

        # Collect all UUIDs from merged chunks for cross-reference linking
        all_uuids = set()
        for _, chunk_rec in chunk_group:
            uid = chunk_rec.get("uuid")
            if uid:
                all_uuids.add(uid)

        # Build merged record
        merged_rec = dict(first_rec)
        merged_rec["message"] = dict(first_rec.get("message", {}))
        merged_rec["message"]["content"] = merged_content
        if final_usage:
            merged_rec["message"]["usage"] = final_usage
        if final_stop_reason:
            merged_rec["message"]["stop_reason"] = final_stop_reason
        merged_rec["_line"] = first_line
        merged_rec["_line_end"] = last_line
        merged_rec["_end_timestamp"] = last_rec.get("timestamp", first_rec.get("timestamp"))
        merged_rec["_file"] = first_rec.get("_file")
        merged_rec["_all_uuids"] = all_uuids

        merged.append((first_line, merged_rec))
        i = j

    return merged


# ---------------------------------------------------------------------------
# Activity Extraction
# ---------------------------------------------------------------------------


def extract_activities_from_content(content, line_num):
    """Extract activity entries from a message content array."""
    activities = []
    if not isinstance(content, list):
        return activities

    for block in content:
        if not isinstance(block, dict):
            continue

        btype = block.get("type")

        if btype == "text":
            text = block.get("text", "").strip()
            if text:
                activities.append({
                    "type": "text",
                    "tool": None,
                    "description": text,
                    "target": None,
                    "line": line_num,
                    "resultLine": None,
                    "error": None,
                })

        elif btype == "thinking":
            thinking_text = block.get("thinking", "").strip()
            if thinking_text:
                activities.append({
                    "type": "thinking",
                    "tool": None,
                    "description": thinking_text,
                    "target": None,
                    "line": line_num,
                    "resultLine": None,
                    "error": None,
                })

        elif btype == "tool_use":
            tname = block.get("name", "Unknown")
            tinput = block.get("input", {})
            cat = tool_category(tname)
            desc = tool_description(tname, tinput)
            target = tool_target(tname, tinput)

            extras = tool_extra_targets(tname, tinput)

            activity = {
                "type": cat,
                "tool": tname,
                "description": desc,
                "target": target,
                "extraTargets": extras if extras else None,
                "line": line_num,
                "resultLine": None,
                "error": None,
                "_tool_use_id": block.get("id"),
            }

            # For Agent tool calls, add subagent metadata
            if tname == "Agent":
                activity["subagentType"] = tinput.get("subagent_type", "")
                activity["subagentDescription"] = tinput.get("description", "")

            activities.append(activity)

    return activities


def extract_activities_from_tool_results(content, line_num, tool_result_meta):
    """
    Extract tool result information from user records containing tool_result blocks.
    Returns a list of dicts with tool_use_id -> result info for back-patching.
    """
    results = []
    if not isinstance(content, list):
        return results

    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_result":
            tool_use_id = block.get("tool_use_id")
            is_error = block.get("is_error", False)
            results.append({
                "tool_use_id": tool_use_id,
                "line": line_num,
                "error": is_error,
            })

    return results


# ---------------------------------------------------------------------------
# Block Building
# ---------------------------------------------------------------------------


def build_blocks(records, session_idx, file_rel):
    """
    Build the blocks array from merged orchestrator records.

    Returns (blocks, agent_dispatches) where agent_dispatches maps
    tool_use_id -> dispatch info for linking subagents.
    """
    blocks = []
    agent_dispatches = {}  # tool_use_id -> {agentId, agentType, description, blockId, line}
    block_counter = 0

    # Index for back-patching tool result lines
    # tool_use_id -> {resultLine, error}
    tool_result_index = {}

    # First pass: collect all tool result locations
    for line_num, rec in records:
        rtype = rec.get("type")
        if rtype == "user":
            content = rec.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tuid = block.get("tool_use_id")
                        if tuid:
                            # Extract tool result content for search display
                            result_content = ""
                            raw_content = block.get("content", "")
                            if isinstance(raw_content, str):
                                result_content = raw_content
                            elif isinstance(raw_content, list):
                                rc_parts = []
                                for rc_block in raw_content:
                                    if isinstance(rc_block, dict) and rc_block.get("type") == "text":
                                        rc_parts.append(rc_block.get("text", ""))
                                    elif isinstance(rc_block, str):
                                        rc_parts.append(rc_block)
                                result_content = "\n".join(rc_parts)
                            tool_result_index[tuid] = {
                                "resultLine": line_num,
                                "error": block.get("is_error", False),
                                "content": result_content,
                            }

            # Also check for Agent tool results
            tur = rec.get("toolUseResult", {})
            if isinstance(tur, dict) and tur.get("agentId"):
                # This is an Agent return — store subagent metadata
                tool_result_index[f"_agent_{tur['agentId']}"] = {
                    "resultLine": line_num,
                    "status": tur.get("status"),
                    "totalDurationMs": tur.get("totalDurationMs"),
                    "totalTokens": tur.get("totalTokens"),
                    "totalToolUseCount": tur.get("totalToolUseCount"),
                    "agentType": tur.get("agentType", ""),
                    "prompt": tur.get("prompt", ""),
                }

    # Second pass: build blocks
    for line_num, rec in records:
        rtype = rec.get("type")

        if rtype in SKIP_RECORD_TYPES:
            continue
        if rtype == "system":
            continue

        # Skip isMeta user records
        if rtype == "user" and rec.get("isMeta"):
            continue

        # Skip user records that are pure tool results (no user text)
        if rtype == "user":
            content = rec.get("message", {}).get("content", [])
            if isinstance(content, list):
                has_text = any(
                    isinstance(b, dict) and b.get("type") == "text"
                    for b in content
                )
                has_tool_result = any(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in content
                )
                if has_tool_result and not has_text:
                    continue
            elif isinstance(content, str) and not content.strip():
                continue

        msg = rec.get("message", {})
        timestamp = rec.get("timestamp", "")
        end_timestamp = rec.get("_end_timestamp", timestamp)
        line_end = rec.get("_line_end", line_num)

        block_counter += 1
        block_id = f"s{session_idx}_b{block_counter:03d}"

        if rtype == "user":
            content = msg.get("content", "")
            summary = extract_user_text(content)

            blocks.append({
                "id": block_id,
                "type": "user",
                "startTime": timestamp,
                "endTime": end_timestamp,
                "durationSec": duration_between(timestamp, end_timestamp),
                "lineStart": line_num,
                "lineEnd": line_end,
                "file": file_rel,
                "summary": summary,
                "activities": [],
            })

        elif rtype == "assistant":
            content = msg.get("content", [])
            activities = extract_activities_from_content(content, line_num)

            # Back-patch tool result lines and errors
            for act in activities:
                if act["tool"] and act["tool"] != "Agent":
                    # Match by tool_use_id for precise linking
                    tuid = act.get("_tool_use_id")
                    if tuid and tuid in tool_result_index:
                        tri = tool_result_index[tuid]
                        act["resultLine"] = tri["resultLine"]
                        act["error"] = tri.get("error", False)
                        # Capture search result content for display
                        if act["tool"] in ("Glob", "Grep") and tri.get("content"):
                            act["resultContent"] = truncate(tri["content"], 3000)

                elif act["tool"] == "Agent":
                    # Use the activity's own tool_use_id for precise matching
                    tuid = act.get("_tool_use_id")
                    if tuid and tuid in tool_result_index:
                        tri = tool_result_index[tuid]
                        act["resultLine"] = tri["resultLine"]
                        act["error"] = tri.get("error", False)

            # Collect Agent dispatches for subagent linking
            for block_item in (content if isinstance(content, list) else []):
                if (isinstance(block_item, dict)
                        and block_item.get("type") == "tool_use"
                        and block_item.get("name") == "Agent"):
                    tuid = block_item.get("id")
                    tinput = block_item.get("input", {})
                    agent_dispatches[tuid] = {
                        "description": tinput.get("description", ""),
                        "agentType": tinput.get("subagent_type", ""),
                        "blockId": block_id,
                        "line": line_num,
                    }

            # Build summary from activities
            summary = build_assistant_summary(activities)

            # Extract token usage
            usage = msg.get("usage", {})
            token_usage = None
            if usage:
                token_usage = {
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                    "cacheRead": usage.get("cache_read_input_tokens", 0),
                    "cacheWrite": usage.get("cache_creation_input_tokens", 0),
                }

            block_data = {
                "id": block_id,
                "type": "assistant",
                "startTime": timestamp,
                "endTime": end_timestamp,
                "durationSec": duration_between(timestamp, end_timestamp),
                "lineStart": line_num,
                "lineEnd": line_end,
                "file": file_rel,
                "summary": summary,
                "activities": activities,
            }
            if token_usage:
                block_data["tokenUsage"] = token_usage

            blocks.append(block_data)

    return blocks, agent_dispatches


def build_assistant_summary(activities):
    """Auto-generate summary from activities list."""
    counts = {}
    for act in activities:
        atype = act.get("type", "other")
        tool = act.get("tool")

        if atype in ("text", "thinking"):
            continue  # Don't count text/thinking blocks in summary

        if tool == "Read":
            counts["read"] = counts.get("read", 0) + 1
        elif tool in ("Write", "Edit", "NotebookEdit"):
            counts["wrote"] = counts.get("wrote", 0) + 1
        elif tool == "Bash":
            counts["ran"] = counts.get("ran", 0) + 1
        elif tool == "Agent":
            counts["dispatched"] = counts.get("dispatched", 0) + 1
        elif tool == "Skill":
            counts["loaded skill"] = counts.get("loaded skill", 0) + 1
        elif tool in ("Glob", "Grep"):
            counts["searched"] = counts.get("searched", 0) + 1
        elif tool in ("WebSearch", "WebFetch"):
            counts["web"] = counts.get("web", 0) + 1
        elif tool in ("TaskCreate", "TaskUpdate"):
            counts["task"] = counts.get("task", 0) + 1
        else:
            counts["other"] = counts.get("other", 0) + 1

    if not counts:
        # Fallback: use first text activity
        for act in activities:
            if act.get("type") == "text":
                return act.get("description", "")
        return ""

    parts = []
    label_map = {
        "read": ("Read {} file", "Read {} files"),
        "wrote": ("Wrote {} file", "Wrote {} files"),
        "ran": ("Ran {} command", "Ran {} commands"),
        "dispatched": ("Dispatched {} agent", "Dispatched {} agents"),
        "loaded skill": ("Loaded {} skill", "Loaded {} skills"),
        "searched": ("{} search", "{} searches"),
        "web": ("{} web request", "{} web requests"),
        "task": ("{} task update", "{} task updates"),
        "other": ("{} other action", "{} other actions"),
    }

    for key in ["read", "wrote", "ran", "dispatched", "loaded skill", "searched", "web", "task", "other"]:
        if key in counts:
            n = counts[key]
            singular, plural = label_map[key]
            parts.append((singular if n == 1 else plural).format(n))

    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Subagent Processing
# ---------------------------------------------------------------------------


def process_subagent_file(filepath, file_rel, agent_short_id, orchestrator_dispatches,
                          orchestrator_file_rel):
    """
    Process a subagent JSONL file. Returns a subagent dict for the manifest,
    or None if the file is empty/invalid.
    """
    raw_records = load_jsonl(filepath)
    if not raw_records:
        return None

    records = merge_streaming_chunks(raw_records)

    # Extract metadata from first record
    first_line, first_rec = records[0]
    agent_full_id = first_rec.get("agentId", "")
    start_time = first_rec.get("timestamp", "")

    # Find the last assistant record (the final report)
    last_assistant_line = None
    last_assistant_rec = None
    end_time = start_time
    for line_num, rec in reversed(records):
        if rec.get("timestamp"):
            end_time = rec["timestamp"]
            break

    for line_num, rec in reversed(records):
        if rec.get("type") == "assistant":
            msg = rec.get("message", {})
            if msg.get("stop_reason") == "end_turn":
                last_assistant_line = line_num
                last_assistant_rec = rec
                break

    # Extract the dispatch prompt (first user record content) — full text, no truncation
    prompt_preview = ""
    if first_rec.get("type") == "user":
        content = first_rec.get("message", {}).get("content", "")
        prompt_text = extract_text_from_content(content)
        prompt_preview = prompt_text

    # Extract final report text — full text, no truncation
    report_preview = ""
    report_subagent_line = None
    if last_assistant_rec:
        content = last_assistant_rec.get("message", {}).get("content", [])
        report_text = extract_text_from_content(content)
        report_preview = report_text
        report_subagent_line = last_assistant_line or None

    # Build tool result index for subagent (mirrors build_blocks logic)
    sa_tool_result_index = {}
    for line_num, rec in records:
        if rec.get("type") != "user":
            continue
        content = rec.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                tuid = block.get("tool_use_id")
                if not tuid:
                    continue
                result_content = ""
                raw_content = block.get("content", "")
                if isinstance(raw_content, str):
                    result_content = raw_content
                elif isinstance(raw_content, list):
                    rc_parts = []
                    for rc_block in raw_content:
                        if isinstance(rc_block, dict) and rc_block.get("type") == "text":
                            rc_parts.append(rc_block.get("text", ""))
                        elif isinstance(rc_block, str):
                            rc_parts.append(rc_block)
                    result_content = "\n".join(rc_parts)
                sa_tool_result_index[tuid] = {
                    "resultLine": line_num,
                    "error": block.get("is_error", False),
                    "content": result_content,
                }

    # Build activities for subagent
    subagent_activities = []
    for line_num, rec in records:
        if rec.get("type") == "assistant":
            content = rec.get("message", {}).get("content", [])
            acts = extract_activities_from_content(content, line_num)
            # Back-patch tool result lines and search content
            for act in acts:
                tuid = act.get("_tool_use_id")
                if tuid and tuid in sa_tool_result_index:
                    tri = sa_tool_result_index[tuid]
                    act["resultLine"] = tri["resultLine"]
                    act["error"] = tri.get("error", False)
                    if act.get("tool") in ("Glob", "Grep") and tri.get("content"):
                        act["resultContent"] = truncate(tri["content"], 3000)
            subagent_activities.extend(acts)

    # Calculate totals from records
    total_tool_uses = 0
    total_tokens = 0
    for line_num, rec in records:
        if rec.get("type") == "assistant":
            content = rec.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        total_tool_uses += 1
            usage = rec.get("message", {}).get("usage", {})
            if usage:
                total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                total_tokens += usage.get("cache_read_input_tokens", 0)
                total_tokens += usage.get("cache_creation_input_tokens", 0)

    # Determine agentType from first record context or dispatch
    agent_type = ""
    label = ""

    subagent_data = {
        "id": agent_short_id,
        "fullId": agent_full_id,
        "agentType": agent_type,
        "label": label,
        "file": file_rel,
        "parentBlockId": None,
        "startTime": start_time,
        "endTime": end_time,
        "durationMs": int(duration_between(start_time, end_time) * 1000),
        "tokens": total_tokens,
        "toolUseCount": total_tool_uses,
        "invocation": {
            "promptPreview": prompt_preview,
            "orchestratorFile": orchestrator_file_rel,
            "orchestratorLine": None,
            "subagentFile": file_rel,
            "subagentLine": first_line,
        },
        "report": {
            "summaryPreview": report_preview,
            "orchestratorFile": orchestrator_file_rel,
            "orchestratorLine": None,
            "subagentFile": file_rel,
            "subagentLine": report_subagent_line,
        },
        "activities": subagent_activities,
    }

    return subagent_data


def link_subagents_to_dispatches(subagents, agent_dispatches, orch_records, orch_file_rel):
    """
    Link subagent entries to their orchestrator dispatch points using
    the toolUseResult.agentId field in orchestrator user records.
    """
    # Build map: agentId (full or short) -> dispatch info from tool results
    agent_result_map = {}  # agentId -> {tool_use_id, line, agentType, ...}

    for line_num, rec in orch_records:
        if rec.get("type") != "user":
            continue
        tur = rec.get("toolUseResult", {})
        if not isinstance(tur, dict):
            continue
        aid = tur.get("agentId", "")
        if aid:
            source_tool_uuid = rec.get("sourceToolAssistantUUID", "")
            # Extract tool_use_id from the tool_result block for precise dispatch matching
            tool_use_id = None
            content = rec.get("message", {}).get("content", [])
            if isinstance(content, list):
                for cblock in content:
                    if isinstance(cblock, dict) and cblock.get("type") == "tool_result":
                        tool_use_id = cblock.get("tool_use_id")
                        break
            agent_result_map[aid] = {
                "line": line_num,
                "agentType": tur.get("agentType", ""),
                "totalDurationMs": tur.get("totalDurationMs"),
                "totalTokens": tur.get("totalTokens"),
                "totalToolUseCount": tur.get("totalToolUseCount"),
                "prompt": tur.get("prompt", ""),
                "sourceToolAssistantUUID": source_tool_uuid,
                "tool_use_id": tool_use_id,
            }

    # Also build a map from sourceToolAssistantUUID -> dispatch info
    # by finding which assistant record contained the Agent tool_use.
    # After streaming chunk merging, a merged record may have multiple UUIDs
    # stored in _all_uuids. The sourceToolAssistantUUID on the result record
    # may reference ANY of those chunk UUIDs, so we index all of them.
    uuid_to_dispatch = {}
    for line_num, rec in orch_records:
        if rec.get("type") != "assistant":
            continue
        content = rec.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if (isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") == "Agent"):
                tuid = block.get("id")
                tinput = block.get("input", {})
                dispatch_entry = {
                    "tool_use_id": tuid,
                    "description": tinput.get("description", ""),
                    "agentType": tinput.get("subagent_type", ""),
                    "line": line_num,
                }
                # Index by primary UUID
                rec_uuid = rec.get("uuid", "")
                if rec_uuid:
                    uuid_to_dispatch[rec_uuid] = dispatch_entry
                # Also index by all merged chunk UUIDs
                for uid in rec.get("_all_uuids", set()):
                    uuid_to_dispatch[uid] = dispatch_entry

    # Now link each subagent
    for sa in subagents:
        full_id = sa.get("fullId", "")
        short_id = sa.get("id", "")

        # Look up agent result by full ID
        result_info = agent_result_map.get(full_id)
        if result_info:
            sa["report"]["orchestratorLine"] = result_info["line"]

            # Use metadata from the result to enrich
            if result_info.get("totalDurationMs"):
                sa["durationMs"] = result_info["totalDurationMs"]
            if result_info.get("totalTokens"):
                sa["tokens"] = result_info["totalTokens"]
            if result_info.get("totalToolUseCount"):
                sa["toolUseCount"] = result_info["totalToolUseCount"]
            if result_info.get("agentType"):
                sa["agentType"] = result_info["agentType"]

            # Match dispatch by tool_use_id first (precise), then UUID (fallback)
            dispatch = None
            tuid = result_info.get("tool_use_id")
            if tuid and tuid in agent_dispatches:
                dispatch = agent_dispatches[tuid]
            else:
                source_uuid = result_info.get("sourceToolAssistantUUID", "")
                if source_uuid and source_uuid in uuid_to_dispatch:
                    dispatch = uuid_to_dispatch[source_uuid]
            if dispatch:
                sa["invocation"]["orchestratorLine"] = dispatch["line"]
                if not sa["agentType"]:
                    sa["agentType"] = dispatch.get("agentType", "")
                sa["label"] = dispatch.get("description", "")

                # Find parent block
                for tuid, dinfo in agent_dispatches.items():
                    if dinfo.get("line") == dispatch["line"]:
                        sa["parentBlockId"] = dinfo.get("blockId")
                        break

        # If we still don't have a label, try to extract from prompt
        if not sa["label"] and sa["invocation"]["promptPreview"]:
            # Use first line of prompt as label
            first_line_text = sa["invocation"]["promptPreview"].split("\n")[0]
            sa["label"] = first_line_text


# ---------------------------------------------------------------------------
# Session Processing
# ---------------------------------------------------------------------------


def process_session(session_idx, session_prefix, session_files):
    """Process a single session (orchestrator + subagents). Returns a session dict."""
    orch_path = session_files["orchestrator"]
    if not orch_path or not os.path.exists(orch_path):
        print(f"  WARNING: No orchestrator file for session {session_prefix}, skipping")
        return None

    orch_file_rel = strip_daaf_prefix(orch_path)
    print(f"  Processing session: {os.path.basename(orch_path)}")

    # Load and merge orchestrator records
    raw_records = load_jsonl(orch_path)
    if not raw_records:
        print(f"    No records found in orchestrator file")
        return None

    records = merge_streaming_chunks(raw_records)

    # Extract DAAF version from companion .md file
    daaf_version = ""
    md_path = orch_path.replace(".jsonl", ".md")
    if os.path.exists(md_path):
        try:
            with open(md_path, "r", encoding="utf-8", errors="replace") as f:
                for md_line in f:
                    if md_line.startswith("**DAAF Version:**"):
                        daaf_version = md_line.split("**DAAF Version:**")[1].strip()
                        break
                    if md_line.startswith("---"):
                        break
        except Exception:
            pass

    # Extract session metadata from first meaningful record
    full_session_id = ""
    cli_version = ""
    git_branch = ""
    model = ""
    start_time = ""
    end_time = ""

    for _, rec in records:
        if rec.get("sessionId"):
            full_session_id = rec["sessionId"]
        if rec.get("version") and not cli_version:
            cli_version = rec["version"]
        if rec.get("gitBranch") and not git_branch:
            git_branch = rec["gitBranch"]
        if not start_time and rec.get("timestamp"):
            start_time = rec["timestamp"]
        m = rec.get("message", {}).get("model")
        if m and not model:
            model = m

    # Get end time from last record
    for _, rec in reversed(records):
        if rec.get("timestamp"):
            end_time = rec["timestamp"]
            break

    session_short = full_session_id[:8] if full_session_id else session_prefix.split("_")[-1]

    # Build blocks and agent dispatches
    blocks, agent_dispatches = build_blocks(records, session_idx, orch_file_rel)

    # Process subagents
    subagents = []
    for agent_short, sa_path in sorted(session_files["subagents"].items()):
        sa_file_rel = strip_daaf_prefix(sa_path)
        sa_data = process_subagent_file(
            sa_path, sa_file_rel, agent_short,
            agent_dispatches, orch_file_rel
        )
        if sa_data:
            subagents.append(sa_data)

    # Link subagents to their orchestrator dispatches
    link_subagents_to_dispatches(subagents, agent_dispatches, records, orch_file_rel)

    # Enrich subagents with frontmatter skills from agent definitions
    for sa in subagents:
        agent_type = sa.get("agentType", "")
        sa["frontmatterSkills"] = extract_agent_frontmatter_skills(agent_type)

    # Also enrich agent-type activities in blocks with subagent IDs
    for block in blocks:
        for act in block.get("activities", []):
            if act.get("tool") == "Agent":
                # Find matching subagent by checking the line
                for sa in subagents:
                    if sa["invocation"].get("orchestratorLine") == act.get("line"):
                        act["subagentId"] = sa["id"]
                        act["subagentType"] = sa.get("agentType", "")
                        act["subagentLabel"] = sa.get("label", "")
                        break

    session_data = {
        "sessionId": session_short,
        "fullSessionId": full_session_id,
        "startTime": start_time,
        "endTime": end_time,
        "durationSec": duration_between(start_time, end_time),
        "model": model,
        "cliVersion": cli_version,
        "daafVersion": daaf_version,
        "gitBranch": git_branch,
        "orchestratorFile": orch_file_rel,
        "blocks": blocks,
        "subagents": subagents,
    }

    print(f"    Blocks: {len(blocks)}, Subagents: {len(subagents)}")
    return session_data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Parse DAAF session JSONL logs and produce a session_manifest.json"
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        help="Absolute path to a DAAF research project"
    )
    parser.add_argument(
        "--logs-dir",
        help="Direct path to directory containing JSONL files (overrides project_path/logs)"
    )
    args = parser.parse_args()

    if args.logs_dir:
        logs_dir = os.path.abspath(args.logs_dir)
        project_name = "DAAF Session Archive"
        project_rel = strip_daaf_prefix(os.path.dirname(logs_dir))
    elif args.project_path:
        project_path = os.path.abspath(args.project_path)
        logs_dir = os.path.join(project_path, "logs")
        project_name = os.path.basename(project_path)
        project_rel = strip_daaf_prefix(project_path)
    else:
        parser.error("Either project_path or --logs-dir is required")

    if not os.path.isdir(logs_dir):
        print(f"ERROR: Logs directory does not exist: {logs_dir}")
        sys.exit(1)

    print(f"DAAF Log Manifest Builder")
    print(f"Project: {project_name}")
    print(f"Logs dir: {logs_dir}")
    print()

    # Group files by session
    session_groups = group_files_by_session(logs_dir)

    if not session_groups:
        print("No JSONL session files found in logs/")
        sys.exit(1)

    print(f"Found {len(session_groups)} session(s)")
    print()

    # Process each session
    sessions = []
    total_subagents = 0

    for idx, (prefix, files) in enumerate(sorted(session_groups.items())):
        session_data = process_session(idx, prefix, files)
        if session_data:
            sessions.append(session_data)
            total_subagents += len(session_data.get("subagents", []))

    # Sort sessions chronologically
    sessions.sort(key=lambda s: s.get("startTime", ""))

    # Build manifest
    manifest = {
        "version": 1,
        "generated": iso_timestamp(),
        "project": {
            "name": project_name,
            "path": project_rel,
        },
        "sessions": sessions,
    }

    # Strip internal fields (prefixed with _) before writing
    def strip_internal(obj):
        if isinstance(obj, dict):
            return {k: strip_internal(v) for k, v in obj.items() if not k.startswith("_")}
        if isinstance(obj, list):
            return [strip_internal(item) for item in obj]
        if isinstance(obj, set):
            return list(obj)
        return obj

    manifest = strip_internal(manifest)

    # Write output
    output_path = os.path.join(logs_dir, "session_manifest.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print()
    print(f"Summary:")
    print(f"  Sessions: {len(sessions)}")
    print(f"  Subagents: {total_subagents}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
