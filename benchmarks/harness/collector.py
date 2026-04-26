"""Collector module: reads DAAF artifacts after a benchmark run.

Extracts audit.jsonl entries, session transcripts, and created files
for a specific session_id. Runs OUTSIDE the execution environment
(or reads via volume mount) to maintain scoring isolation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


# Default paths within the DAAF container
DEFAULT_AUDIT_LOG = Path("/daaf/.claude/logs/audit.jsonl")
DEFAULT_SESSIONS_DIR = Path("/daaf/.claude/logs/sessions")


def collect_audit_entries(
    session_id: str,
    audit_log_path: Path = DEFAULT_AUDIT_LOG,
    after_timestamp: str | None = None,
) -> list[dict]:
    """Extract audit.jsonl entries for a specific session.

    Args:
        session_id: The Claude Code session ID to filter by.
        audit_log_path: Path to the audit.jsonl file.
        after_timestamp: ISO timestamp; only return entries after this time.
            Useful when the audit log contains entries from prior runs.

    Returns:
        List of audit entry dicts, chronologically ordered.
    """
    if not audit_log_path.exists():
        return []

    entries = []
    with open(audit_log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("session_id") != session_id:
                continue

            if after_timestamp and entry.get("timestamp", "") <= after_timestamp:
                continue

            entries.append(entry)

    return sorted(entries, key=lambda e: e.get("timestamp", ""))


def get_audit_log_position(audit_log_path: Path = DEFAULT_AUDIT_LOG) -> tuple[int, str]:
    """Snapshot the current audit log position before a run.

    Returns:
        Tuple of (line_count, last_timestamp) for filtering after the run.
    """
    if not audit_log_path.exists():
        return (0, "")

    line_count = 0
    last_timestamp = ""
    with open(audit_log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                line_count += 1
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "")
                    if ts > last_timestamp:
                        last_timestamp = ts
                except json.JSONDecodeError:
                    continue

    return (line_count, last_timestamp)


def collect_new_audit_entries(
    after_timestamp: str,
    audit_log_path: Path = DEFAULT_AUDIT_LOG,
) -> list[dict]:
    """Collect ALL audit entries added after a given timestamp.

    Useful when session_id is not yet known (we collect then filter).
    """
    if not audit_log_path.exists():
        return []

    entries = []
    with open(audit_log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("timestamp", "") > after_timestamp:
                entries.append(entry)

    return sorted(entries, key=lambda e: e.get("timestamp", ""))


def find_session_transcript(
    session_id: str,
    sessions_dir: Path = DEFAULT_SESSIONS_DIR,
) -> Path | None:
    """Find the archived session transcript for a given session ID.

    Session archives are named: {date}_{time}_{session-short}_orchestrator.jsonl
    The session-short is the first 8 chars of the session UUID.
    """
    if not sessions_dir.exists():
        return None

    session_short = session_id[:8] if len(session_id) >= 8 else session_id

    for p in sessions_dir.glob(f"*_{session_short}_orchestrator.jsonl"):
        return p

    # Fallback: try matching any file containing the short ID
    for p in sessions_dir.glob(f"*{session_short}*.jsonl"):
        return p

    return None


def find_session_markdown(
    session_id: str,
    sessions_dir: Path = DEFAULT_SESSIONS_DIR,
) -> Path | None:
    """Find the human-readable Markdown transcript for a session."""
    jsonl_path = find_session_transcript(session_id, sessions_dir)
    if jsonl_path is None:
        return None

    md_path = jsonl_path.with_suffix(".md")
    return md_path if md_path.exists() else None


def collect_created_files(
    sandbox_dir: Path,
    after_time: float,
) -> list[str]:
    """List files created in the sandbox directory after a given time.

    Args:
        sandbox_dir: Directory to scan for new files.
        after_time: Unix timestamp; only return files modified after this.

    Returns:
        List of absolute file paths as strings.
    """
    if not sandbox_dir.exists():
        return []

    created = []
    for p in sandbox_dir.rglob("*"):
        if p.is_file() and p.stat().st_mtime > after_time:
            created.append(str(p))

    return sorted(created)


def extract_tool_sequence(audit_entries: list[dict]) -> list[dict]:
    """Extract a simplified tool call sequence from audit entries.

    Returns a list of dicts with: tool, target, agent_type, timestamp.
    Useful for protocol adherence scoring.
    """
    return [
        {
            "tool": e.get("tool", "unknown"),
            "target": e.get("target", ""),
            "agent_type": e.get("agent_type", "orchestrator"),
            "agent_id": e.get("agent_id", ""),
            "timestamp": e.get("timestamp", ""),
        }
        for e in audit_entries
    ]


def extract_skill_loads(audit_entries: list[dict]) -> list[str]:
    """Extract the names of skills loaded during a session.

    Looks for Skill tool invocations in the audit entries.
    The target field for Skill calls contains the skill name.
    """
    skills = []
    for e in audit_entries:
        if e.get("tool") == "Skill":
            target = e.get("target", "").strip()
            if target:
                skills.append(target)
    return skills


def extract_read_targets(audit_entries: list[dict]) -> list[str]:
    """Extract file paths read during a session."""
    return [
        e.get("target", "")
        for e in audit_entries
        if e.get("tool") == "Read" and e.get("target")
    ]


def now_iso() -> str:
    """Return current UTC time as ISO string matching audit.jsonl format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
