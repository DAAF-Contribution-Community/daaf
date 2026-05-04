"""Checkpoint manager: prepares golden session checkpoints for benchmark runs.

Handles session ID cloning, project path normalization, and sandbox seeding
so that `claude -p --resume` can continue from a pre-recorded conversation state.

Golden checkpoints are truncated session JSONL files from known-good sessions.
Each benchmark run gets a fresh session ID to enable parallel execution.
"""

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path


PROJECTS_DIR = Path.home() / ".claude" / "projects" / "-daaf"

GOLDEN_DIR = Path("/daaf/benchmarks/golden")


def extract_session_id(golden_file: Path) -> str:
    """Extract the sessionId from a golden checkpoint JSONL."""
    with open(golden_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                sid = record.get("sessionId")
                if sid:
                    return sid
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No sessionId found in {golden_file}")


def extract_project_path(golden_file: Path) -> str:
    """Extract the cwd (project path) from a golden checkpoint JSONL."""
    with open(golden_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                cwd = record.get("cwd")
                if cwd:
                    return cwd
            except json.JSONDecodeError:
                continue
    return "/daaf"


def prepare_sandbox(
    golden_file: Path,
    sandbox_dir: Path,
    project_path: str | None = None,
) -> str:
    """Prepare a benchmark sandbox from a golden checkpoint.

    1. Cleans the sandbox directory
    2. Seeds it with files from the checkpoint's _seed/ directory (if exists)
    3. Clones the session JSONL with a fresh session ID and rewritten paths
    4. Places the cloned session in Claude Code's projects directory

    Args:
        golden_file: Path to the golden checkpoint JSONL.
        sandbox_dir: Path to the sandbox directory for this run.
        project_path: The DAAF project directory referenced in the golden
            session (e.g., "/daaf/research/2026-04-30_Analysis"). When provided,
            this specific path is replaced with sandbox_dir throughout the
            session JSONL. This is safe because project paths live under
            research/ and never collide with framework paths (.claude/skills/,
            agent_reference/). When None, no path replacement is performed —
            appropriate for golden sessions that don't reference project files.

    Returns the new session ID for use with --resume.
    """
    old_id = extract_session_id(golden_file)
    new_id = str(uuid.uuid4())

    # Clean and create sandbox
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    # Seed with expected filesystem state
    seed_dir = golden_file.with_suffix("").parent / (golden_file.stem + "_seed")
    if seed_dir.is_dir():
        shutil.copytree(seed_dir, sandbox_dir, dirs_exist_ok=True)

    session_content = golden_file.read_text()

    # Always replace session ID for parallel execution isolation
    session_content = session_content.replace(old_id, new_id)

    # Replace project-specific paths only when explicitly provided.
    # The project_path should be a directory under research/ (e.g.,
    # /daaf/research/2026-04-30_Analysis) — specific enough to never
    # match framework paths like /daaf/.claude/skills/....
    if project_path and project_path != str(sandbox_dir):
        session_content = session_content.replace(
            project_path, str(sandbox_dir)
        )

    # Ensure the projects directory exists
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    session_file = PROJECTS_DIR / f"{new_id}.jsonl"
    session_file.write_text(session_content)

    # Pre-create the orchestrator-loaded flag file so remind-orchestrator.sh
    # doesn't inject a "load the orchestrator" reminder on the resumed session.
    # The orchestrator was already loaded in the golden session's history.
    flag_file = Path(f"/tmp/claude-daaf-orchestrator-{new_id}")
    flag_file.touch()

    return new_id


def cleanup_sandbox(
    session_id: str,
    sandbox_dir: Path | None = None,
) -> None:
    """Clean up after a benchmark run.

    Removes the cloned session file and optionally the sandbox directory.
    """
    session_file = PROJECTS_DIR / f"{session_id}.jsonl"
    if session_file.exists():
        session_file.unlink()

    # Also clean up the session's subagent directory if it exists
    subagent_dir = PROJECTS_DIR / session_id
    if subagent_dir.exists():
        shutil.rmtree(subagent_dir)

    # Clean up the orchestrator flag file
    flag_file = Path(f"/tmp/claude-daaf-orchestrator-{session_id}")
    if flag_file.exists():
        flag_file.unlink()

    if sandbox_dir and sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)


def list_golden_checkpoints(mode: str | None = None) -> list[Path]:
    """List available golden checkpoint files, optionally filtered by mode."""
    if mode:
        mode_dir = GOLDEN_DIR / mode
        if not mode_dir.exists():
            return []
        return sorted(mode_dir.glob("*.jsonl"))
    return sorted(GOLDEN_DIR.rglob("*.jsonl"))


def validate_checkpoint(golden_file: Path) -> dict:
    """Validate that a golden checkpoint file is well-formed.

    Returns a dict with validation results.
    """
    result = {
        "valid": True,
        "line_count": 0,
        "session_id": None,
        "has_user_message": False,
        "has_assistant_message": False,
        "last_record_type": None,
        "errors": [],
    }

    try:
        with open(golden_file) as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                result["line_count"] = i
                try:
                    record = json.loads(line)
                    rtype = record.get("type", "unknown")
                    result["last_record_type"] = rtype

                    if rtype == "user" and record.get("message", {}).get("role") == "user":
                        content = record.get("message", {}).get("content", "")
                        if isinstance(content, str) and content.strip():
                            result["has_user_message"] = True

                    if rtype == "assistant":
                        result["has_assistant_message"] = True

                    sid = record.get("sessionId")
                    if sid and not result["session_id"]:
                        result["session_id"] = sid

                except json.JSONDecodeError as e:
                    result["errors"].append(f"Line {i}: invalid JSON: {e}")
                    result["valid"] = False

    except FileNotFoundError:
        result["valid"] = False
        result["errors"].append(f"File not found: {golden_file}")

    if not result["session_id"]:
        result["valid"] = False
        result["errors"].append("No sessionId found")

    if not result["has_user_message"]:
        result["valid"] = False
        result["errors"].append("No user message found")

    return result
