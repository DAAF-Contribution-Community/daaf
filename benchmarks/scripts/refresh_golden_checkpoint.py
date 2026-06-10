"""Refresh embedded file payloads in a golden checkpoint JSONL.

Golden checkpoints replay recorded conversation history, which embeds
point-in-time snapshots of framework files (SKILL.md bodies, Read results).
When the framework files change, the recorded payloads go stale and models
resuming from the checkpoint see the OLD text in-context — masking framework
fixes. This tool rebuilds those payloads from the CURRENT on-disk files while
preserving every other byte of the recording.

Serialization formats (validated byte-for-byte against the Phase 3 golden
benchmarks/golden/dispatch_compliance/ad_hoc_initialized.jsonl, by
reconstructing payloads from the pre-fix git versions of the source files):

1. Skill tool_use -> paired tool_result content is the static string
   "Launching skill: {skill}" (NOT the skill body; left unchanged).
   The skill body lives in a SUBSEQUENT user record whose message.content
   is a list containing a text block of the form:
       "Base directory for this skill: /daaf/.claude/skills/{skill}\n"
       + <SKILL.md body with YAML frontmatter stripped>
   (the body retains its leading newline from after the closing "---").
   Any dynamic header lines between the base-directory line and the first
   markdown H1 (e.g., "ARGUMENTS: ...") are preserved verbatim; only the
   span from the first H1 onward is replaced.

2. Read tool_use -> paired tool_result content is a plain string:
       "\n".join(f"{i}\t{line}" for i, line in
                 enumerate(file_text.split("\n"), 1))
   i.e., 1-based line numbers, single tab, no padding, no system-reminder
   suffix, no truncation marker. A file ending in "\n" therefore yields a
   final numbered empty line with no trailing newline.

   The SAME record also duplicates the result in a top-level
   "toolUseResult" field: {"type": "text", "file": {"filePath": ...,
   "content": <RAW file text, un-numbered>, "numLines": N, "startLine": 1,
   "totalLines": N}} where N == len(file_text.split("\n")). Both copies
   must be refreshed together or stale text leaks into replay context.
   (Skill records also carry a toolUseResult, but it is only
   {"success": ..., "commandName": ...} — no embedded file body.)

3. JSONL lines round-trip exactly with
   json.dumps(rec, separators=(",", ":"), ensure_ascii=False).
   Unmodified lines are emitted verbatim from the source bytes regardless.

4. Skill-listing attachment records (validated against
   benchmarks/golden/bootstrap_template.jsonl line 5, where 36 of 37
   DAAF-skill descriptions matched the current on-disk frontmatter
   byte-for-byte; the 37th was the skill whose description had changed):
   a top-level record with "type":"attachment" whose "attachment" object is
       {"type": "skill_listing", "content": <listing>, "skillCount": N,
        "isInitial": ...}
   The listing string is "\n".join of one entry per skill:
       "- {name}: {description}"
   where {description} is the skill's frontmatter `description` field
   VERBATIM (yaml.safe_load semantics). Descriptions may contain literal
   newlines (e.g., the built-in claude-api skill); continuation lines do
   not start with "- {name}: " and belong to the preceding entry. Entries
   whose name has no SKILL.md under /daaf/.claude/skills (built-in or
   user-level skills, e.g. init, review, update-config) have no source to
   rebuild from and are preserved verbatim. Entry order, the entry name
   set, and skillCount are never changed — only description text is
   rebuilt. A frontmatter `when_to_use` field would be appended to the
   displayed listing in a serialization this tool has not validated, so
   encountering one raises an error rather than guessing.

Usage:
    python3 benchmarks/scripts/refresh_golden_checkpoint.py \
        --source benchmarks/golden/dispatch_compliance/ad_hoc_initialized.jsonl \
        --output benchmarks/golden/skill_routing/ad_hoc_initialized.jsonl
    python3 benchmarks/scripts/refresh_golden_checkpoint.py \
        --source <golden.jsonl> --output <golden.jsonl> --dry-run
"""

import argparse
import copy
import json
import re
from pathlib import Path

import yaml

SKILLS_DIR = Path("/daaf/.claude/skills")
BASE_DIR_PREFIX = "Base directory for this skill: "
# A skill-listing entry line: "- {name}: {description...}". Name charset per
# the Agent Skills spec (^[a-z0-9]+(-[a-z0-9]+)*$). Lines not matching are
# continuation lines of the previous entry's multi-line description.
LISTING_ENTRY_RE = re.compile(r"^- ([a-z0-9]+(?:-[a-z0-9]+)*): (.*)$")


def load_lines(source_path):
    """Load raw JSONL lines (without trailing newlines) and parsed records."""
    raw_lines = source_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in raw_lines]
    return raw_lines, records


def strip_frontmatter(text):
    """Return SKILL.md content after the closing '---' of YAML frontmatter.

    The recorded payloads contain the body exactly as it appears after the
    frontmatter terminator line, INCLUDING its leading newline.
    """
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md does not start with YAML frontmatter")
    end = text.index("\n---\n", 4) + len("\n---\n")
    return text[end:]


def format_read_payload(file_text):
    """Replicate the recorded Read tool_result serialization exactly."""
    return "\n".join(
        f"{i}\t{line}" for i, line in enumerate(file_text.split("\n"), 1)
    )


def find_tool_result(records, tool_use_id, start_index):
    """Locate (record_index, block) of the tool_result paired to tool_use_id."""
    for idx in range(start_index, len(records)):
        message = records[idx].get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and block.get("tool_use_id") == tool_use_id
            ):
                return idx, block
    raise ValueError(f"No tool_result found for tool_use_id {tool_use_id}")


def find_skill_payload_block(records, skill_name, start_index):
    """Locate (record_index, text_block) of the user text block carrying the
    skill body injected after a Skill tool_result."""
    expected_first_line = f"{BASE_DIR_PREFIX}{SKILLS_DIR}/{skill_name}"
    for idx in range(start_index, len(records)):
        record = records[idx]
        message = record.get("message")
        if record.get("type") != "user" or not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                first_line = block.get("text", "").partition("\n")[0]
                if first_line == expected_first_line:
                    return idx, block
    raise ValueError(f"No skill payload text block found for {skill_name}")


def rebuild_skill_payload(old_payload, skill_name):
    """Swap the file-body span of a skill payload for the current SKILL.md.

    Preserves the base-directory header line and any dynamic preamble lines
    verbatim; replaces only from the first markdown H1 onward.
    """
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    current_body = strip_frontmatter(skill_md.read_text(encoding="utf-8"))

    header, sep, old_rest = old_payload.partition("\n")
    if not sep:
        raise ValueError(f"Skill payload for {skill_name} has no body")

    old_h1 = re.search(r"^# ", old_rest, flags=re.MULTILINE)
    new_h1 = re.search(r"^# ", current_body, flags=re.MULTILINE)
    if not old_h1 or not new_h1:
        raise ValueError(f"Could not locate H1 boundary for {skill_name}")

    preamble = old_rest[: old_h1.start()]
    return header + "\n" + preamble + current_body[new_h1.start():], str(skill_md)


def load_frontmatter_description(skill_name):
    """Return the current frontmatter `description` for a DAAF skill, or
    None if the skill has no SKILL.md under SKILLS_DIR (built-in skill).

    Uses yaml.safe_load on the frontmatter block — the same parse that was
    validated to reproduce recorded listing entries byte-for-byte (see
    module docstring, serialization 4).
    """
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_md.exists():
        return None
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{skill_md} does not start with YAML frontmatter")
    frontmatter = yaml.safe_load(text[4:text.index("\n---\n", 4)])
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{skill_md} frontmatter did not parse to a mapping")
    if "when_to_use" in frontmatter:
        raise ValueError(
            f"{skill_md} has a when_to_use field; its listing serialization "
            "is unvalidated — extend serialization 4 before refreshing"
        )
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{skill_md} has no usable frontmatter description")
    return description


def parse_skill_listing(content):
    """Parse a skill_listing content string into [[name, description], ...].

    Continuation-aware: lines that do not match the entry pattern are
    appended (with their newline) to the previous entry's description.
    """
    entries = []
    for line in content.split("\n"):
        match = LISTING_ENTRY_RE.match(line)
        if match:
            entries.append([match.group(1), match.group(2)])
        elif entries:
            entries[-1][1] += "\n" + line
        else:
            raise ValueError(
                f"skill_listing content does not start with an entry line: "
                f"{line!r}"
            )
    return entries


def rebuild_skill_listing(attachment):
    """Rebuild a skill_listing attachment's content from current frontmatter.

    Entry order, the entry name set, and skillCount are preserved; only
    description text is swapped. Entries without a DAAF SKILL.md source are
    kept verbatim. Returns (new_content, stats_dict).
    """
    old_content = attachment.get("content", "")
    entries = parse_skill_listing(old_content)
    skill_count = attachment.get("skillCount")
    if len(entries) != skill_count:
        raise ValueError(
            f"Parsed {len(entries)} listing entries but skillCount is "
            f"{skill_count}; a description may contain an entry-like line"
        )
    stats = {"rebuilt": 0, "changed": 0, "external": 0}
    new_entries = []
    for name, old_description in entries:
        current = load_frontmatter_description(name)
        if current is None:
            new_entries.append((name, old_description))
            stats["external"] += 1
        else:
            new_entries.append((name, current))
            stats["rebuilt"] += 1
            if current != old_description:
                stats["changed"] += 1
    new_content = "\n".join(f"- {name}: {desc}" for name, desc in new_entries)
    # Reparse guard: a current frontmatter description containing an
    # entry-like line ("\n- name: ...") would corrupt the listing in a way
    # only the NEXT refresh's pre-rebuild check would catch — fail now.
    if len(parse_skill_listing(new_content)) != skill_count:
        raise ValueError(
            "Rebuilt skill listing no longer parses back to skillCount "
            f"({skill_count}) entries; a current frontmatter description "
            "likely contains an entry-like line"
        )
    return new_content, stats


def rebuild_read_payload(tool_input):
    """Rebuild a Read tool_result payload from the current on-disk file.

    Returns (numbered_payload, raw_text, file_path_str). The raw text is
    needed for the record's toolUseResult.file duplicate.
    """
    unsupported = sorted(set(tool_input) - {"file_path"})
    if unsupported:
        raise ValueError(
            f"Read input has unsupported parameters {unsupported}; "
            "offset/limit replay is not implemented"
        )
    file_path = Path(tool_input["file_path"])
    raw_text = file_path.read_text(encoding="utf-8")
    return format_read_payload(raw_text), raw_text, str(file_path)


def refresh_tool_use_result_file(record, raw_text):
    """Refresh the top-level toolUseResult.file duplicate of a Read record.

    Returns (old_len, new_len) of the duplicated content, or None if the
    record has no toolUseResult.file (tolerated: some recordings omit it).
    """
    tool_use_result = record.get("toolUseResult")
    if not isinstance(tool_use_result, dict):
        return None
    file_info = tool_use_result.get("file")
    if not isinstance(file_info, dict):
        return None
    if file_info.get("startLine") != 1 or (
        file_info.get("numLines") != file_info.get("totalLines")
    ):
        raise ValueError(
            "toolUseResult.file records a partial read (offset/limit); "
            "replay is not implemented"
        )
    old_len = len(file_info.get("content", ""))
    line_count = len(raw_text.split("\n"))
    file_info["content"] = raw_text
    file_info["numLines"] = line_count
    file_info["totalLines"] = line_count
    return old_len, len(raw_text)


def replace_result_content(block, new_payload):
    """Replace the payload of a tool_result block (str or single-text-block
    list), returning the old payload string."""
    content = block.get("content")
    if isinstance(content, str):
        old_payload = content
        block["content"] = new_payload
    elif (
        isinstance(content, list)
        and len(content) == 1
        and isinstance(content[0], dict)
        and content[0].get("type") == "text"
    ):
        old_payload = content[0]["text"]
        content[0]["text"] = new_payload
    else:
        raise ValueError("Unsupported tool_result content shape")
    return old_payload


def null_payload_copy(record):
    """Deep-copy a record with every string payload field nulled, so two
    records can be compared structurally ignoring payload text."""
    clone = copy.deepcopy(record)
    content = clone.get("message", {}).get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                block["text"] = None
            elif block.get("type") == "tool_result":
                if isinstance(block.get("content"), str):
                    block["content"] = None
                elif isinstance(block.get("content"), list):
                    for sub in block["content"]:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            sub["text"] = None
    # toolUseResult.file duplicates the Read payload; its content and
    # derived line counts are payload-dependent, so null them too
    file_info = clone.get("toolUseResult", {})
    if isinstance(file_info, dict):
        file_info = file_info.get("file")
        if isinstance(file_info, dict):
            file_info["content"] = None
            file_info["numLines"] = None
            file_info["totalLines"] = None
    # skill_listing attachment content is the payload; skillCount is NOT
    # nulled — the refresh never adds or removes entries, so it must match
    attachment = clone.get("attachment")
    if isinstance(attachment, dict) and attachment.get("type") == "skill_listing":
        attachment["content"] = None
    return clone


def plan_replacements(records):
    """Walk the records and compute all payload replacements.

    Mutates `records` in place. Returns a list of report dicts.
    """
    report = []
    for idx, record in enumerate(records):
        attachment = record.get("attachment")
        if (
            record.get("type") == "attachment"
            and isinstance(attachment, dict)
            and attachment.get("type") == "skill_listing"
        ):
            old_payload = attachment.get("content", "")
            new_payload, stats = rebuild_skill_listing(attachment)
            attachment["content"] = new_payload
            report.append(
                {
                    "tool": "SkillListing",
                    "target": f"{SKILLS_DIR}/*/SKILL.md frontmatter",
                    "record_line": idx + 1,
                    "old_len": len(old_payload),
                    "new_len": len(new_payload),
                    "entries": stats,
                }
            )
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_name = block.get("name")
            tool_id = block.get("id")

            if tool_name == "Read":
                result_idx, result_block = find_tool_result(records, tool_id, idx)
                new_payload, raw_text, target = rebuild_read_payload(
                    block.get("input", {})
                )
                old_payload = replace_result_content(result_block, new_payload)
                duplicate = refresh_tool_use_result_file(
                    records[result_idx], raw_text
                )
                report.append(
                    {
                        "tool": "Read",
                        "target": target,
                        "record_line": result_idx + 1,
                        "old_len": len(old_payload),
                        "new_len": len(new_payload),
                        "duplicate": duplicate,
                    }
                )

            elif tool_name == "Skill":
                skill_name = block.get("input", {}).get("skill")
                result_idx, result_block = find_tool_result(records, tool_id, idx)
                launch_msg = result_block.get("content")
                if launch_msg != f"Launching skill: {skill_name}":
                    raise ValueError(
                        f"Unexpected Skill tool_result content: {launch_msg!r}"
                    )
                payload_idx, text_block = find_skill_payload_block(
                    records, skill_name, result_idx + 1
                )
                old_payload = text_block["text"]
                new_payload, target = rebuild_skill_payload(old_payload, skill_name)
                text_block["text"] = new_payload
                report.append(
                    {
                        "tool": "Skill",
                        "target": target,
                        "record_line": payload_idx + 1,
                        "old_len": len(old_payload),
                        "new_len": len(new_payload),
                    }
                )
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Refresh embedded Skill/Read payloads in a golden "
        "checkpoint JSONL from current on-disk files"
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the source golden checkpoint JSONL (read-only)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the refreshed golden checkpoint JSONL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned replacements and length deltas without writing",
    )
    args = parser.parse_args()

    if not args.source.exists():
        raise FileNotFoundError(f"Source golden not found: {args.source}")
    if args.source.resolve() == args.output.resolve():
        raise ValueError("Refusing in-place refresh: --output must differ from --source")

    raw_lines, records = load_lines(args.source)
    originals = copy.deepcopy(records)
    print(f"Loaded source: {args.source} ({len(records)} records)")

    report = plan_replacements(records)

    # Per-replacement report
    print(f"\nPlanned replacements: {len(report)}")
    for item in report:
        delta = item["new_len"] - item["old_len"]
        print(
            f"  [{item['tool']}] line {item['record_line']}: {item['target']}\n"
            f"      payload {item['old_len']} -> {item['new_len']} chars "
            f"({delta:+d})"
        )
        duplicate = item.get("duplicate")
        if duplicate:
            dup_delta = duplicate[1] - duplicate[0]
            print(
                f"      toolUseResult.file duplicate {duplicate[0]} -> "
                f"{duplicate[1]} chars ({dup_delta:+d})"
            )
        entries = item.get("entries")
        if entries:
            print(
                f"      entries: {entries['rebuilt']} rebuilt from current "
                f"frontmatter ({entries['changed']} changed), "
                f"{entries['external']} non-DAAF preserved verbatim"
            )

    # Structural assertion: non-payload JSON unchanged for every record
    modified_lines = {item["record_line"] - 1 for item in report}
    for idx, (orig, new) in enumerate(zip(originals, records)):
        if idx in modified_lines:
            assert null_payload_copy(orig) == null_payload_copy(new), (
                f"Structural change detected in modified record {idx + 1}"
            )
        else:
            assert orig == new, f"Unmodified record {idx + 1} changed"
    print(
        f"\nStructural assertion passed: {len(modified_lines)} record(s) "
        f"payload-swapped, {len(records) - len(modified_lines)} record(s) "
        "byte-identical; non-payload JSON unchanged everywhere"
    )

    if args.dry_run:
        print("\nDry run: no file written.")
        return

    # Emit: unmodified lines verbatim from source bytes; modified lines
    # re-serialized with the verified exact round-trip settings
    out_lines = []
    for idx, record in enumerate(records):
        if idx in modified_lines:
            out_lines.append(
                json.dumps(record, separators=(",", ":"), ensure_ascii=False)
            )
        else:
            out_lines.append(raw_lines[idx])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"\nWrote refreshed golden: {args.output} ({len(out_lines)} records)")


if __name__ == "__main__":
    main()
