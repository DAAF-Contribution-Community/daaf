#!/usr/bin/env python3
"""Opt-in normal Auto acceptance, separate from bypass-permission smoke tiers.

Only action-ID-correlated normal classifier allow + exact digest + intact capture
can pass. The monitor is reactive, NOT a preexecution security boundary. Native
log support is deliberately limited to the observed Claude Code 2.1.281 contract.
Framework CLI tooling exception: ordinary functions/classes, stdlib only here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime


ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT), str(Path(__file__).resolve().parent)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
from route_detection import SHIM_ROUTES
from smoke_probes import collect_main_model, _read_local_health, EXPECTED_SHIM_SERVICE

SUPPORTED_VERSION = "2.1.281"
MAX_INVOCATIONS = 3
MAX_TURNS = 6
CHILD_SECONDS = 120
CLEANUP_SECONDS = 5
CAPTURE_LIMIT = 8 * 1024 * 1024  # per stream/file, not a provider request limit
LINE_LIMIT = 1024 * 1024
SAFE_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/\[\]#-]{0,159}")
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,160}")
DEBUG_LINE = re.compile(r"^\d{4}-\d\d-\d\dT\S+ \[(DEBUG|INFO|WARN|ERROR)\] (.*)$")
MANDATORY_SKILLS = frozenset({"daaf-orchestrator", "skill-authoring", "agent-authoring"})
FAILURES = frozenset({"MAIN_ROUTE_REJECTED", "ADMISSION_REJECTED", "POLICY_DENIED",
                      "TRANSPORT_PARSER_FAILURE", "UNEXPECTED_ACTION", "ACTION_FAILED"})


# INTENT: recognize only the verified 2.1.281 operational notice template.
# REASONING: ineligibility for the billing update is not Auto admission denial;
# the fixed continued-operation clause is mandatory, not inferred from keywords.
# ASSUMES: dynamic slots contain a host[:port] and an HTTPS documentation URL.
# No private captured host, endpoint, path or identifier is embedded here.
AUTO_BILLING_NOTICE = re.compile(
    r"We're changing auto mode to no longer charge for classifier requests in Claude Code\. "
    r"However, this session isn't eligible because your requests go through "
    r"(?P<host>[A-Za-z0-9][A-Za-z0-9.-]{0,252})(?::(?P<port>[0-9]{1,5}))?, "
    r"which isn't compatible with this update\. Nothing breaks: auto mode keeps working, "
    r"and its classifier requests are billed as before\. To fix it and access the new version "
    r"of auto mode, ask your gateway to implement: https://[A-Za-z0-9][A-Za-z0-9./_#?=&%:+~-]{0,1023}")
NATIVE_ANCILLARY = {
    "auxiliary_lock_contention": re.compile(
        r"NON-FATAL: Lock acquisition failed for /[A-Za-z0-9_./-]+ "
        r"\(expected in multi-process scenarios\): Lock already held by another process"),
    "optional_telemetry_file_missing": re.compile(
        r"\$\.fs\.read \(telemetry\): (?P<path>/[A-Za-z0-9_./-]+) failed: "
        r"ENOENT: no such file or directory, open '(?P=path)'"),
    "metrics_opt_out_check_unavailable": re.compile(re.escape(
        "[Anthropic telemetry] Failed to check metrics opt-out status: "
        "Auth error: no credential usable for the metrics opt-out check")),
}


def safe_diagnostic(source, severity, category, content):
    """Record explicit diagnostics without publishing content or its private slots."""
    try:
        raw = content.encode("utf-8")
    except UnicodeError:
        raise EvidenceError("invalid_diagnostic_encoding") from None
    return {"source": source, "severity": severity, "category": category,
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical_uuid4(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed) == value


def exit_code(status):
    return 0 if status == "CLASSIFIER_ALLOW_PASS" else (1 if status in FAILURES else 2)


class EvidenceError(ValueError):
    """Safe categorical error; never include provider-controlled raw text."""


def strict_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise EvidenceError("duplicate_json_key")
        obj[key] = value
    return obj


def reject_json_constant(value):
    raise EvidenceError("nonfinite_json_constant")


def decode_event(line):
    if not line or len(line) > LINE_LIMIT:
        raise EvidenceError("empty_or_oversized_event")
    try:
        obj = json.loads(line.decode("utf-8"), object_pairs_hook=strict_object, parse_constant=reject_json_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise EvidenceError("malformed_jsonl") from None
    if not isinstance(obj, dict):
        raise EvidenceError("unsupported_event_schema")
    return obj


def digest_command(root):
    root = Path(root).resolve()
    if not re.fullmatch(r"/[A-Za-z0-9_./ -]+", str(root)):
        raise EvidenceError("unsupported_repository_path")
    return "openssl dgst -sha256 " + shlex.quote(str(root / "CLAUDE.md"))


def public_instruction(target, root):
    if not isinstance(target, str) or not re.fullmatch(r"[A-Za-z0-9_./ -]+", target):
        return False
    p = Path(target)
    if ".." in p.parts or p.suffix != ".md":
        return False
    p = p if p.is_absolute() else root / p
    # Reject symlink components, not just a symlink leaf or escaping resolve().
    if any(q.is_symlink() for q in (p, *p.parents)):
        return False
    if not p.is_file():
        return False
    p = p.resolve()
    return (p == root / "CLAUDE.md" or p.is_relative_to(root / "agent_reference")
            or p.is_relative_to(root / ".claude/skills"))


@dataclass
class ActionLedger:
    root: Path
    seen: dict = field(default_factory=dict)
    digest_id: str = ""
    completed: bool = False

    def observe(self, block):
        identifier, name, payload = block.get("id"), block.get("name"), block.get("input")
        if not isinstance(identifier, str) or not SAFE_ID.fullmatch(identifier) or not isinstance(name, str) or not isinstance(payload, dict):
            raise EvidenceError("invalid_tool_schema")
        signature = json.dumps([name, payload], sort_keys=True)
        if identifier in self.seen:
            if self.seen[identifier] != signature:
                raise EvidenceError("conflicting_tool_id")
            return False
        self.seen[identifier] = signature
        if self.completed:
            raise EvidenceError("tool_after_digest")
        valid = False
        if name == "Skill":
            valid = (isinstance(payload.get("skill"), str) and payload["skill"] in MANDATORY_SKILLS and
                     payload.get("args", "") in ("", None) and
                     not (set(payload) - {"skill", "args"}))
        elif name == "Read":
            valid = (not (set(payload) - {"file_path", "offset", "limit", "pages"}) and
                     public_instruction(payload.get("file_path"), self.root) and
                     all(type(payload[k]) is int and payload[k] > 0
                         for k in ("offset", "limit") if k in payload) and
                     payload.get("pages", "") in ("", None))
        elif name == "Bash":
            command = payload.get("command")
            if command == digest_command(self.root):
                if self.digest_id:
                    raise EvidenceError("second_digest_action")
                # Attempt recorded BEFORE remaining validation. Never retry ambiguity.
                self.digest_id = identifier
                valid = True
            elif isinstance(command, str) and re.fullmatch(r"wc -l [A-Za-z0-9_./ '-]+", command):
                try:
                    words = shlex.split(command)
                    valid = len(words) > 2 and all(public_instruction(p, self.root) for p in words[2:])
                except ValueError:
                    valid = False
            valid = (valid and not (set(payload) - {"command", "description", "timeout", "dangerouslyDisableSandbox", "run_in_background"})
                     and payload.get("dangerouslyDisableSandbox", False) is False
                     and payload.get("run_in_background", False) is False
                     and ("timeout" not in payload or type(payload["timeout"]) is int and 0 < payload["timeout"] <= 120000)
                     and ("description" not in payload or isinstance(payload["description"], str)))
        if not valid:
            raise EvidenceError("unexpected_tool_or_action")
        return True


@dataclass
class StreamEvidence:
    ledger: ActionLedger
    expected_model: str
    expected_hash: str
    session_id: str = ""
    init: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    response_models: set = field(default_factory=set)
    results: dict = field(default_factory=dict)
    tool_ids: set = field(default_factory=set)
    digest_ok: bool = False
    assistant_text: str = ""
    assistant_message_id: str = ""
    assistant_completion_ambiguous: bool = False
    previous_was_assistant: bool = False
    event_count: int = 0
    diagnostics: list = field(default_factory=list)
    informational_seen: bool = False

    def observe_informational(self, event):
        # Exact schema first; "informational" is not a blanket severity exemption.
        if (set(event) != {"type", "subtype", "content", "isMeta", "timestamp", "uuid", "level", "session_id"}
                or not self.init or event.get("session_id") != self.session_id
                or not canonical_uuid4(event.get("session_id"))
                or not canonical_uuid4(event.get("uuid")) or event["uuid"] == self.session_id
                or event.get("isMeta") is not False or not isinstance(event.get("content"), str)
                or not isinstance(event.get("level"), str) or event["level"] not in {"info", "warning", "error"}
                or not isinstance(event.get("timestamp"), str)
                or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", event["timestamp"])):
            raise EvidenceError("unsupported_informational_schema")
        try:
            datetime.strptime(event["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            raise EvidenceError("invalid_informational_timestamp") from None
        if self.informational_seen:
            raise EvidenceError("duplicate_informational_notice")
        self.informational_seen = True
        match = AUTO_BILLING_NOTICE.fullmatch(event["content"])
        recognized = (event["level"] == "warning" and match is not None
                      and (match["port"] is None or 0 < int(match["port"]) <= 65535))
        category = "auto_billing_update_ineligible_continues" if recognized else "unknown_system_notice"
        self.diagnostics.append(safe_diagnostic("structured", event["level"], category, event["content"]))
        if not recognized:
            raise EvidenceError("unknown_system_notice")

    def observe(self, event):
        self.event_count += 1
        if self.result:
            raise EvidenceError("event_after_completion")
        kind = event.get("type")
        if not isinstance(kind, str) or ("subtype" in event and not isinstance(event["subtype"], str)):
            raise EvidenceError("unsupported_event_schema")
        if event.get("isApiErrorMessage") is True or event.get("api_error_status") is not None:
            raise EvidenceError("transport_failure")
        sid = event.get("session_id")
        if sid is not None and (not isinstance(sid, str) or
                                self.session_id and sid != self.session_id):
            raise EvidenceError("mixed_session")
        if kind == "system" and event.get("subtype") == "init":
            if self.init or not isinstance(sid, str):
                raise EvidenceError("ambiguous_initialization")
            try:
                uuid.UUID(sid)
            except ValueError:
                raise EvidenceError("invalid_session_identity") from None
            self.session_id = sid
            model = event.get("model")
            if not isinstance(model, str) or not SAFE_MODEL.fullmatch(model):
                raise EvidenceError("unknown_initialized_model")
            if model.removesuffix("[1m]") != self.expected_model.removesuffix("[1m]"):
                raise EvidenceError("initialized_model_mismatch")
            if event.get("permissionMode") != "auto":
                raise EvidenceError("not_normal_auto")
            if event.get("claude_code_version") != SUPPORTED_VERSION:
                raise EvidenceError("unsupported_client_version")
            self.init = event
            return
        if kind == "system":
            if event.get("subtype") == "informational":
                self.observe_informational(event)
                return
            if event.get("subtype") not in {"hook_started", "hook_progress", "hook_response"}:
                raise EvidenceError("unsupported_system_event")
            if event.get("subtype") == "hook_response":
                outcome, code = event.get("outcome"), event.get("exit_code")
                if outcome in ("error", "cancelled") or type(code) is int and code != 0:
                    raise EvidenceError("hook_failed")
                if outcome != "success" or type(code) is not int or code != 0:
                    raise EvidenceError("hook_outcome_unknown")
            return
        if not self.init:
            raise EvidenceError("missing_initialization")
        if sid != self.session_id:
            raise EvidenceError("missing_or_mixed_session")
        if kind == "result":
            if sid != self.session_id or event.get("subtype") != "success" or event.get("is_error") is not False:
                raise EvidenceError("cli_unsuccessful")
            denials = event.get("permission_denials")
            if not isinstance(denials, list) or any(
                    not isinstance(item, dict) or
                    not isinstance(item.get("tool_name"), str) or not item["tool_name"] or
                    not isinstance(item.get("tool_use_id"), str) or not SAFE_ID.fullmatch(item["tool_use_id"]) or
                    not isinstance(item.get("tool_input"), dict) for item in denials):
                raise EvidenceError("permission_denials_unknown")
            if denials:
                raise EvidenceError("policy_denied")
            if type(event.get("num_turns")) is not int or not 0 < event["num_turns"] <= MAX_TURNS:
                raise EvidenceError("turn_bound_or_schema")
            self.result = event
            return
        if kind not in {"assistant", "user"}:
            raise EvidenceError("unsupported_event_type")
        message = event.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            raise EvidenceError("unsupported_message_schema")
        if kind == "assistant":
            model = message.get("model")
            if not isinstance(model, str) or not SAFE_MODEL.fullmatch(model):
                raise EvidenceError("invalid_response_model")
            self.response_models.add(model)
            message_id = message.get("id", "")
            if not isinstance(message_id, str):
                raise EvidenceError("invalid_assistant_message_id")
            # Stream-json can emit several blocks sharing one completion ID.
            # Keep the entire final completion, never just its last text block.
            if self.previous_was_assistant and (not message_id or not self.assistant_message_id):
                # Without completion IDs, adjacent records may be separate blocks
                # of ONE completion; never approve by discarding the earlier one.
                self.assistant_completion_ambiguous = True
            elif message_id != self.assistant_message_id:
                self.assistant_completion_ambiguous = False
            if not message_id or message_id != self.assistant_message_id:
                self.assistant_text = ""
            self.assistant_message_id = message_id
            self.previous_was_assistant = True
        else:
            # A tool/user turn ends the prior completion; it cannot authorize a
            # later textless assistant completion by carrying an old question.
            self.assistant_text = ""
            self.assistant_message_id = ""
            self.assistant_completion_ambiguous = False
            self.previous_was_assistant = False
        for block in message["content"]:
            if not isinstance(block, dict):
                raise EvidenceError("unsupported_content_block")
            block_type = block.get("type")
            if not isinstance(block_type, str):
                raise EvidenceError("unsupported_content_type")
            if block_type == "tool_use" and kind == "assistant":
                self.ledger.observe(block)
                self.tool_ids.add(block["id"])
            elif block_type == "tool_result" and kind == "user":
                identifier = block.get("tool_use_id")
                if not isinstance(identifier, str) or identifier not in self.tool_ids:
                    raise EvidenceError("unmatched_tool_result")
                signature = json.dumps(block, sort_keys=True)
                if identifier in self.results:
                    if self.results[identifier] != signature:
                        raise EvidenceError("conflicting_tool_result")
                    continue
                self.results[identifier] = signature
                if block.get("is_error", False) is not False:
                    raise EvidenceError("tool_failed")
                if identifier == self.ledger.digest_id:
                    self.ledger.completed = True
                    content = block.get("content")
                    if isinstance(content, list) and all(isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str) for b in content):
                        content = "\n".join(b.get("text", "") for b in content)
                    expected = rf"SHA(?:2-)?256\({re.escape(str(self.ledger.root / 'CLAUDE.md'))}\)= {self.expected_hash}"
                    self.digest_ok = isinstance(content, str) and re.fullmatch(expected, content.strip()) is not None
                    if not self.digest_ok:
                        raise EvidenceError("digest_mismatch")
            elif block_type == "text" and isinstance(block.get("text"), str):
                if kind == "assistant":
                    self.assistant_text += ("\n" if self.assistant_text else "") + block["text"]
            elif block_type in {"thinking", "redacted_thinking"} and kind == "assistant":
                pass
            else:
                raise EvidenceError("unsupported_content_type")


def parse_stdout(raw, ledger, expected_model, expected_hash, session_id="", diagnostics=None):
    if len(raw) > CAPTURE_LIMIT or not raw.endswith(b"\n"):
        raise EvidenceError("truncated_or_oversized_stdout")
    stream = StreamEvidence(ledger, expected_model, expected_hash, session_id,
                            diagnostics=diagnostics if diagnostics is not None else [])
    for line in raw.splitlines():
        stream.observe(decode_event(line))
    if not stream.init or not stream.result or not stream.response_models:
        raise EvidenceError("incomplete_stdout")
    if stream.tool_ids != set(stream.results):
        raise EvidenceError("unresolved_tool_calls")
    return stream


def native_fields(text, required):
    """Parse whole whitespace-delimited key=value tokens, never substring joins.

    Unknown fields/quoting are unsupported. Duplicate keys, including identical
    duplicates, are ambiguous. Request IDs keep dots and all supported suffixes.
    """
    fields = {}
    for token in text.split():
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)=([A-Za-z0-9_.\[\]/#:-]+)", token)
        if not match or match[1] in fields:
            raise EvidenceError("ambiguous_native_fields")
        fields[match[1]] = match[2]
    if set(fields) != set(required):
        raise EvidenceError("unsupported_native_fields")
    # Closed ancillary grammar from the supported 2.1.281 event contract. These
    # fields are validated, not discarded by a permissive trailing-text match.
    for key, value in fields.items():
        if key in ("actionChars", "durationMs", "permissionDecisionMs"):
            pattern = r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?" if key != "actionChars" else r"(?:0|[1-9][0-9]*)"
            if not re.fullmatch(pattern, value):
                raise EvidenceError("unsupported_native_number")
        elif key == "promptTokensEst" and value != "[REDACTED]":
            raise EvidenceError("unsupported_prompt_estimate_marker")
        elif key in ("id", "toolUseId") and not SAFE_ID.fullmatch(value):
            raise EvidenceError("unsupported_native_action_id")
        elif key == "reqId" and not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", value):
            raise EvidenceError("unsupported_native_request_id")
        elif key == "tool" and value not in {"Bash", "Read", "Skill"}:
            raise EvidenceError("unsupported_native_tool")
    return fields


def native_events(raw, diagnostics=None):
    """Strict supported event grammar; unrelated timestamped debug is not proof."""
    if not raw or len(raw) > CAPTURE_LIMIT or not raw.endswith(b"\n"):
        raise EvidenceError("truncated_native_capture")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError:
        raise EvidenceError("malformed_native_encoding") from None
    events = []
    contracts = {
        "classifier_request_started": ("start", {"reqId", "stage", "model", "tool", "promptTokensEst"}),
        "classifier_request_finished": ("finish", {"reqId", "stage", "tool", "outcome", "durationMs"}),
        "tool_dispatch_start": ("dispatch_start", {"toolUseId", "tool", "permissionDecisionMs"}),
        "tool_dispatch_end": ("dispatch_end", {"toolUseId", "tool", "outcome", "durationMs"}),
    }
    for line in lines:
        match = DEBUG_LINE.fullmatch(line)
        if not match:
            raise EvidenceError("unsupported_native_line")
        body = match[2]
        if "verifyAutoModeGateAccess:" in body and "canEnterAuto=false" in body:
            events.append(("admission", {}))
        elif body.startswith(("Auto mode classifier blocked action:", "Auto mode classifier unavailable, denying")):
            events.append(("denial", {}))
        elif body.startswith("Auto mode classifier (XML) error:") or re.search(r"\b(authentication_error|invalid_api_key)\b", body):
            events.append(("failure", {}))
        elif match[1] in {"ERROR", "WARN"}:
            # INTENT: distinguish three exact ancillary subsystems from failures.
            # REASONING: ERROR severity alone is not evidence of transport failure.
            # ASSUMES: no added action/request fields or changed message suffixes;
            # fullmatch rejects those, including telemetry-shaped hook failures.
            category = next((name for name, pattern in NATIVE_ANCILLARY.items()
                             if match[1] == "ERROR" and pattern.fullmatch(body)), None)
            category = category or ("unknown_native_error" if match[1] == "ERROR" else "unknown_native_warning")
            fields = safe_diagnostic("native", match[1], category, body)
            if diagnostics is not None:
                diagnostics.append(fields)
            events.append(("unknown" if category.startswith("unknown_") else "ancillary", fields))
        elif body.startswith("Skipping auto mode classifier for Bash:"):
            events.append(("fast", {"tool": "Bash"}))
        elif body.startswith("[auto-mode] new action being classified:"):
            fields = native_fields(body.removeprefix("[auto-mode] new action being classified:"),
                                   {"tool", "actionChars", "id"})
            # Only the explicit id field identifies the classified action.
            fields["toolUseId"] = fields.pop("id")
            events.append(("classification", fields))
        elif body.startswith("[Stall] "):
            name, _, text = body.removeprefix("[Stall] ").partition(" ")
            if name in contracts:
                kind, required = contracts[name]
                fields = native_fields(text, required)
                if kind in ("start", "finish") and fields["stage"] != "xml_s1":
                    raise EvidenceError("unsupported_classifier_stage")
                if kind == "start" and not SAFE_MODEL.fullmatch(fields["model"]):
                    raise EvidenceError("unsupported_classifier_model")
                events.append((kind, fields))
            elif name.startswith(("tool_dispatch", "classifier_request")):
                raise EvidenceError("unsupported_native_event")
        elif re.search(r"(?i)\bpermission\]?\s+decision\b", body):
            # Observed fixed prefix and punctuation; no generic .+ tail or
            # substring field search that could accept a contradictory decision.
            decision = re.fullmatch(
                r"Slow permission decision: (?:0|[1-9][0-9]*)(?:\.[0-9]+)?ms for "
                r"(Bash|Read|Skill) \(mode=auto, behavior=(allow|deny|ask)\)", body)
            if not decision:
                raise EvidenceError("unsupported_permission_schema")
            fields = {"tool": decision[1], "mode": "auto", "behavior": decision[2]}
            events.append(("allow" if decision[2] == "allow" else "denial", fields))
    return events


def native_terminal(events):
    for kind, status in (("admission", "ADMISSION_REJECTED"), ("denial", "POLICY_DENIED"),
                         ("failure", "TRANSPORT_PARSER_FAILURE")):
        if any(event == kind for event, fields in events):
            return {"status": status, "reason": "native_" + kind}
    for kind, fields in events:
        if kind == "unknown":
            return {"status": "INCONCLUSIVE", "reason": fields["category"]}
    return None


def native_ownership(events, stream):
    """Every native activity must belong to this child's validated structured tools.

    Both digest success and no-action continuation require complete ownership.
    Completed mandatory Read/Skill/wc transactions are allowed, not discarded.
    Classifier request/permission events without IDs need one uniquely owned
    pending action. Return per-action brackets only after the full channel passes.
    """
    known = {identifier: json.loads(stream.ledger.seen[identifier])[0] for identifier in stream.tool_ids}
    started, ended = set(), set()
    brackets = {identifier: [] for identifier in known}
    pending = []
    classified, request, request_finished, permission = "", "", False, ""
    fast = False
    for kind, fields in events:
        tool, identifier = fields.get("tool"), fields.get("toolUseId")
        if kind in ("classification", "dispatch_start", "dispatch_end"):
            if identifier not in known or known[identifier] != tool:
                raise EvidenceError("native_structured_tool_disagreement")
        if kind == "classification":
            if classified or request or permission or fast:
                raise EvidenceError("interleaved_native_activity")
            classified = identifier
        elif kind == "start":
            if not classified or request or known[classified] != tool:
                raise EvidenceError("unowned_classifier_request")
            request = fields["reqId"]
        elif kind == "finish":
            if not request or fields["reqId"] != request or request_finished or known[classified] != tool or fields["outcome"] != "ok":
                raise EvidenceError("unmatched_classifier_finish")
            request_finished = True
        elif kind == "allow":
            if permission or tool not in known.values() or request and not request_finished:
                raise EvidenceError("unowned_native_permission")
            if classified and known[classified] != tool:
                raise EvidenceError("unowned_native_permission")
            permission = tool
        elif kind == "fast":
            if fast or classified or request or tool not in known.values():
                raise EvidenceError("unowned_fastpath")
            fast = True
        elif kind == "dispatch_start":
            if identifier in started or classified and classified != identifier or permission and permission != tool or fast and tool != "Bash":
                raise EvidenceError("ambiguous_native_dispatch")
            if classified and (not request_finished or not permission):
                raise EvidenceError("incomplete_native_classification")
            started.add(identifier)
            # Associate ID-less request/permission metadata only after the
            # unique pending transaction joins this validated structured ID.
            brackets[identifier].extend(pending + [(kind, fields)])
            pending = []
            classified, request, request_finished, permission, fast = "", "", False, "", False
        elif kind == "dispatch_end":
            if identifier not in started or identifier in ended or fields["outcome"] != "ok":
                raise EvidenceError("incomplete_native_dispatch")
            ended.add(identifier)
            brackets[identifier].append((kind, fields))
        if kind in ("classification", "start", "finish", "allow", "fast"):
            pending.append((kind, fields))
    if classified or request or permission or fast or pending or started != ended or ended != set(known):
        raise EvidenceError("incomplete_native_activity")
    return brackets


def native_proof(raw, identifier, parsed=None):
    """Require one uniquely ordered classifier bracket for the exact digest ID."""
    parsed = native_events(raw) if parsed is None else parsed
    terminal = native_terminal(parsed)
    if terminal:
        return terminal
    events, selected, request, fast = [], None, None, False
    for kind, fields in parsed:
        if kind == "fast":
            fast = True
        elif kind == "classification":
            if fields["toolUseId"] != identifier or fields["tool"] != "Bash":
                raise EvidenceError("competing_classification")
            events.append(kind)
        elif kind == "start":
            if request or fields["tool"] != "Bash":
                raise EvidenceError("ambiguous_classifier_start")
            request, selected = fields["reqId"], fields["model"]
            events.append(kind)
        elif kind == "finish":
            if fields["reqId"] != request or fields["tool"] != "Bash" or fields["outcome"] != "ok":
                raise EvidenceError("unmatched_classifier_finish")
            events.append(kind)
        elif kind == "allow":
            if fields["tool"] == "Bash":
                events.append(kind)
        elif kind in ("dispatch_start", "dispatch_end") and fields["tool"] == "Bash":
            if fields["toolUseId"] != identifier or kind == "dispatch_end" and fields["outcome"] != "ok":
                raise EvidenceError("competing_or_failed_dispatch")
            events.append(kind)
    complete = events == ["classification", "start", "finish", "allow", "dispatch_start", "dispatch_end"] and not fast
    return {"status": "CLASSIFIER_ALLOW_PASS" if complete else "FAST_PATH_ACTION_SUCCESS" if fast and not request else "INCONCLUSIVE",
            "reason": "ordered_classifier_chain" if complete else "classifier_chain_not_established",
            "classifier_selected_model": selected,
            "normal_parser_acceptance_via_client_decision": complete}


def adjudicate(stdout, debug, meta, ledger, expected_model, expected_hash, session_id=""):
    report = {"status": "INCONCLUSIVE", "reason": "incomplete_evidence",
              "classifier_provider_response_model": None, "classifier_request_route": None,
              "provider_request_starts": None, "provider_calls_total": None, "provider_retries_total": None,
              "raw_classifier_xml_independently_available": False, "diagnostics": []}
    try:
        # Collect safe diagnostics even when completion was interrupted. Neither
        # known warnings nor replay can override the original child exit metadata.
        activity = native_events(debug, report["diagnostics"])
        stream = parse_stdout(stdout, ledger, expected_model, expected_hash, session_id, report["diagnostics"])
        report.update(initialized_main_model=stream.init["model"],
                      assistant_response_models=sorted(stream.response_models),
                      digest_attempted=bool(ledger.digest_id), digest_success=stream.digest_ok)
        if not all(meta.get(k) is True for k in ("natural_completion", "child_reaped", "capture_drained", "capture_intact")) or meta.get("exit_code") != 0 or meta.get("stop_reason"):
            report["reason"] = "interrupted_or_incomplete_capture"
        else:
            terminal = native_terminal(activity)
            if terminal:
                report.update(terminal)
            else:
                # A successful stdout digest does not excuse unowned, failed or
                # unfinished native work elsewhere in the same child. Validate
                # the entire channel first, then prove only the digest's bracket.
                brackets = native_ownership(activity, stream)
                if not ledger.digest_id:
                    report.update(status="ACTION_NOT_REACHED", reason="clean_action_free_completion")
                elif stream.digest_ok:
                    report.update(native_proof(debug, ledger.digest_id, brackets[ledger.digest_id]))
                else:
                    report.update(status="ACTION_FAILED", reason="digest_not_successful")
        return report, stream
    except EvidenceError as exc:
        report["reason"] = str(exc)
        if str(exc) == "policy_denied":
            report["status"] = "POLICY_DENIED"
        elif str(exc) == "hook_failed":
            report["status"] = "TRANSPORT_PARSER_FAILURE"
        # Malformed/unsupported/mixed evidence is inconclusive, not fabricated failure.
        return report, None


# --- Private capture and bounded lifecycle --------------------------------

def private_write(path, data):
    """Exclusive no-follow creation; callers never reuse an owned run path."""
    raw = data if isinstance(data, bytes) else (json.dumps(data, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def read_capture(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise EvidenceError("nonregular_capture")
        data = stream.read(CAPTURE_LIMIT + 1)
    if len(data) > CAPTURE_LIMIT:
        raise EvidenceError("oversized_capture")
    return data


def make_run_dir(report_dir, root=ROOT):
    root = root.resolve()
    target = Path(report_dir) if report_dir else root / "scripts/deploy_smoke/reports" / ("auto_" + uuid.uuid4().hex)
    if not target.is_absolute():
        target = root / target
    if any(p.is_symlink() for p in (target, *target.parents)) or not target.resolve().is_relative_to(root):
        raise EvidenceError("report_directory_outside_repository")
    for part in target.relative_to(root).parts:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", part) or part.endswith('.') or part.upper().split('.')[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise EvidenceError("nonportable_report_directory")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.mkdir(mode=0o700, exist_ok=False)
    return target


def pointer_snapshot(paths):
    # lexists preserves broken prior pointers too. Never read their target files.
    return {p: os.path.lexists(p) for p in paths}


def cleanup_pointers(before, owned_debug):
    removed = 0
    for path, existed in before.items():
        if existed:
            continue
        try:
            initial = path.lstat()
            if stat.S_ISLNK(initial.st_mode):
                target = Path(os.readlink(path))
                target = target if target.is_absolute() else path.parent / target
                if target.absolute() == owned_debug.absolute():
                    current = path.lstat()
                    if (initial.st_dev, initial.st_ino) == (current.st_dev, current.st_ino):
                        path.unlink()
                        removed += 1
        except FileNotFoundError:
            pass
    return removed


def _child_private_umask():
    # Do not impose an inherited RLIMIT_FSIZE: it also breaks appends to existing
    # CLI/hook audit files outside our ownership. Bound only owned captures.
    os.umask(0o077)


def normal_argv(client, debug_path, prompt, model=None, session_id=""):
    args = [client, "--permission-mode", "auto", "--max-turns", str(MAX_TURNS),
            "--output-format", "stream-json", "--verbose", "--debug-file", str(debug_path)]
    if session_id:
        uuid.UUID(session_id)  # actual initialized UUID, never capture/run UUID
        args += ["--resume", session_id]
    if model is not None:
        args += ["--model", model]
    return args + ["-p", prompt]


def _interrupt_child_capture(signum, frame):
    raise KeyboardInterrupt


def capture_child(argv, out, env, stream, pointer_paths=(), timeout=CHILD_SECONDS):
    """One owned process group, nonblocking drains, five-second total cleanup.

    Persist bytes before parsing. No communicate(), reader threads, benchmark
    executor or unbounded wait. Limit failure discards overflow only after marking
    capture incomplete; evidence already saved is retained. Final drain is parsed
    offline by adjudicate(), so late events cannot silently escape validation.
    """
    proc = None
    selector = selectors.DefaultSelector()
    handles, sizes = {}, {"stdout": 0, "stderr": 0}
    pending = b""
    debug_offset = 0
    debug_pending = b""
    meta = {"natural_completion": False, "child_reaped": False, "capture_drained": False,
            "capture_intact": True, "exit_code": None, "stop_reason": None}
    before = pointer_snapshot(pointer_paths)
    started = time.monotonic()
    prior_term = signal.getsignal(signal.SIGTERM)
    debug = out / "native-debug.log"

    def drain(monitor):
        nonlocal pending
        for key, _ in selector.select(timeout=0.05):
            try:
                chunk = os.read(key.fileobj.fileno(), 65536)
            except BlockingIOError:
                continue
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            name = key.data
            remaining = max(0, CAPTURE_LIMIT - sizes[name])
            saved = chunk[:remaining]
            if handles[name].write(saved) != len(saved):
                raise OSError("short_capture_write")
            sizes[name] += len(saved)
            if len(saved) != len(chunk):
                meta["capture_intact"] = False
                meta["stop_reason"] = meta["stop_reason"] or "capture_limit"
            if name == "stdout" and monitor:
                pending += saved
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    stream.observe(decode_event(line))
                if len(pending) > LINE_LIMIT:
                    raise EvidenceError("event_buffer_limit")
            if name == "stderr" and monitor and re.search(rb"authentication_error|invalid_api_key|permission prompt", saved, re.I):
                raise EvidenceError("transport_or_interactive_permission")

    def poll_debug():
        nonlocal debug_offset, debug_pending
        if debug.stat().st_size >= CAPTURE_LIMIT:
            raise EvidenceError("native_capture_limit")
        fd = os.open(debug, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise EvidenceError("nonregular_native_capture")
            handle.seek(debug_offset)
            chunk = handle.read(65536)
        debug_offset += len(chunk)
        debug_pending += chunk
        while b"\n" in debug_pending:
            line, debug_pending = debug_pending.split(b"\n", 1)
            # Early stop only; offline native parser applies the stronger contract.
            if b"canEnterAuto=false" in line:
                raise EvidenceError("admission_rejected")
            if any(marker in line for marker in (b"Auto mode classifier blocked action:", b"Auto mode classifier unavailable, denying")):
                raise EvidenceError("policy_denied")
            if b"Auto mode classifier (XML) error:" in line:
                raise EvidenceError("classifier_parser_failure")
        if len(debug_pending) > LINE_LIMIT:
            raise EvidenceError("native_line_limit")

    try:
        signal.signal(signal.SIGTERM, _interrupt_child_capture)
        for name, filename in (("stdout", "stdout.jsonl"), ("stderr", "stderr.log")):
            fd = os.open(out / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            handles[name] = os.fdopen(fd, "wb", buffering=0)
        private_write(debug, b"")
        private_write(out / "launch_claim.json", {"claimed": True, "never_relaunch": True,
                                                  "resume_session_id": stream.session_id or None})
        proc = subprocess.Popen(argv, cwd=str(stream.ledger.root), env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, preexec_fn=_child_private_umask)
        for name, pipe in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        while proc.poll() is None or selector.get_map():
            if time.monotonic() - started >= timeout:
                meta["stop_reason"] = "deadline"
                break
            drain(True)
            poll_debug()
            if meta["stop_reason"]:
                break
        meta["natural_completion"] = meta["stop_reason"] is None and proc.poll() == 0
    except EvidenceError as exc:
        meta["stop_reason"] = str(exc)
    except (Exception, KeyboardInterrupt):
        meta["stop_reason"] = "supervisor_exception"
        meta["capture_intact"] = False
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if proc is not None:
            deadline = time.monotonic() + CLEANUP_SECONDS
            for sig, until in ((signal.SIGTERM, deadline - 0.5), (signal.SIGKILL, deadline)):
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    pass
                except OSError:
                    meta["capture_intact"] = False
                while time.monotonic() < until:
                    try:
                        drain(False)
                    except Exception:
                        meta["capture_intact"] = False
                        break
                    if proc.poll() is not None and not selector.get_map():
                        break
            try:
                proc.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                meta["stop_reason"] = meta["stop_reason"] or "cleanup_deadline"
            meta["child_reaped"] = proc.returncode is not None
            meta["capture_drained"] = not selector.get_map()
            meta["exit_code"] = proc.returncode
            for pipe in (proc.stdout, proc.stderr):
                if pipe is not None:
                    pipe.close()
        selector.close()
        # Direct CLI debug writes may overshoot between polls. Retain only the
        # bounded prefix AFTER group cleanup, flagging any loss before judgment.
        # This bounds retained owned bytes, not peak disk use or unowned logs.
        try:
            fd = os.open(debug, os.O_RDWR | os.O_NONBLOCK | os.O_NOFOLLOW)
            with os.fdopen(fd, "r+b") as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise OSError("nonregular_native_capture")
                if info.st_size >= CAPTURE_LIMIT:
                    meta["capture_intact"] = False
                    meta["stop_reason"] = meta["stop_reason"] or "native_capture_limit"
                    handle.truncate(CAPTURE_LIMIT)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            meta["capture_intact"] = False
        for handle in handles.values():
            try:
                handle.flush()
                os.fsync(handle.fileno())
            except OSError:
                meta["capture_intact"] = False
            finally:
                handle.close()
        try:
            meta["owned_new_pointers_removed"] = cleanup_pointers(before, debug)
        except OSError:
            meta["capture_intact"] = False
            meta["stop_reason"] = meta["stop_reason"] or "pointer_cleanup_error"
        meta["elapsed_seconds"] = round(time.monotonic() - started, 3)
        signal.signal(signal.SIGTERM, prior_term)
        private_write(out / "exit.json", meta)
    return meta


# --- Continuation policy --------------------------------------------------

def confirmation_questions(root):
    command = digest_command(root)
    scope = (f"the single read-only command `{command}` once, with mandatory skills and public instruction reads only; "
             "no edits, provider/configuration changes, permission changes, retries, or other actions")
    return (f"Confirm Framework Development mode for {scope}?",
            f"Confirm this bounded diagnostic plan: {scope}?")


def continuation_prompt(stream, consent):
    """Closed same-scope shapes, not a generic proceed/yes regex."""
    if not consent or not stream or not stream.result or stream.ledger.digest_id or stream.assistant_completion_ambiguous:
        return None
    if stream.assistant_text.strip() not in confirmation_questions(stream.ledger.root):
        return None
    return ("The operator explicitly delegated this same-scope confirmation to the diagnostic runner. "
            "I relay that authorization only for the read-only diagnostic scope you just restated. "
            "Keep normal safeguards and do not change scope or repeat an attempted action. "
            f"Perform exactly `{digest_command(stream.ledger.root)}` once and stop; if any gate denies it, stop.")


def initial_prompt(root):
    questions = confirmation_questions(root)
    return ("This is an approved Framework Development read-only deployment diagnostic, not a request to edit the framework. "
            "Follow normal required framework skill loads and public instruction reads. "
            f"Perform exactly `{digest_command(root)}` once, without extra arguments, chaining or redirection, then report and stop. "
            "No edits, other actions, configuration/permission/sandbox/model/auth changes, or retries. "
            "If a gate denies or an error occurs, stop. If the framework requires a confirmation, ask exactly one of these "
            "scope-preserving questions and stop for the reply (do not assume approval):\n" + "\n".join(questions))


def write_manifest(out):
    rows = {}
    for path in sorted(out.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            if stat.S_IMODE(path.stat().st_mode) != 0o700:
                raise EvidenceError("capture_directory_mode")
            continue
        raw = read_capture(path)
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise EvidenceError("capture_file_mode")
        rows[str(path.relative_to(out))] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "mode": "0600"}
    private_write(out / "capture_manifest.json", {"directory_mode": "0700", "files": rows})
    return rows


def preflight(env, root, model):
    resolution, states = collect_main_model(env, str(root), model)
    checks = {"development_image": env.get("DAAF_DEV") == "1",
              "no_benchmark_or_bypass": resolution.normal_execution_context and not any(env.get(k) not in (None, "", "0", "false") for k in (
                  "DAAF_BENCHMARK_RUN", "CLAUDE_CODE_BYPASS_PERMISSIONS", "CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS")),
              "no_alternate_provider": not any(env.get(k) not in (None, "", "0", "false") for k in (
                  "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")),
              "no_global_debug": not any(env.get(k) for k in ("DEBUG", "DEBUG_SDK", "ANTHROPIC_LOG")),
              "client_available": shutil.which("claude") is not None,
              "openssl_available": shutil.which("openssl") is not None}
    # The resolution already reflects user/project/local overlays. Do not mix
    # that model with ambient-only routing or expose the projected environment.
    route = resolution.effective_route
    if route in SHIM_ROUTES:
        checks["expected_loopback"] = resolution.endpoint_kind == "fixed_loopback_shim"
        checks["health_ready"] = False
        if checks["expected_loopback"]:
            try:
                health = _read_local_health(timeout=5)
                checks["health_ready"] = (isinstance(health, dict) and
                    health.get("service") == EXPECTED_SHIM_SERVICE and health.get("status") == "ok"
                    and health.get("backend_mode") == resolution.expected_backend)
            except Exception:
                pass
    target = root / "CLAUDE.md"
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise EvidenceError("digest_input_symlink")
    expected_hash = hashlib.sha256(read_capture(target)).hexdigest()
    # No CLI/version probe here: at most three CLI invocations TOTAL. Version is
    # verified from the actual normal child's structured initialization event.
    return resolution, expected_hash, {"checks": checks, "settings_states": states,
                                       "main_model": resolution.safe_metadata(), "route": route}


def run_acceptance(args, env=None, root=ROOT, capture=capture_child):
    env = dict(os.environ if env is None else env)
    root = Path(root).resolve()
    if args.model is not None and not SAFE_MODEL.fullmatch(args.model):
        raise EvidenceError("unsupported_explicit_model")
    out = make_run_dir(args.report_dir, root)
    resolution, expected_hash, pre = preflight(env, root, args.model)
    private_write(out / "preflight.json", pre)
    report = {"status": "INCONCLUSIVE", "reason": "preflight_unresolved", "preflight": pre,
              "requested_main_model": args.model, "explicit_override": args.model is not None,
              "as_configured_certification": False, "children_launched": 0, "diagnostics": [],
              "reactive_monitor_not_preexecution_guarantee": True,
              "retention": "Private owned captures plus ordinary CLI/hook records outside this directory; no universal sanitization guarantee."}
    if resolution.compatibility == "incompatible":
        report.update(status="MAIN_ROUTE_REJECTED", reason="incompatible_main_model")
    elif (resolution.compatibility != "compatible" or not resolution.resolved_model
          or not all(pre["checks"].values())):
        # An unmapped tier alias (e.g. the shipped ANTHROPIC_DEFAULT_MODEL=opus) is
        # family-compatible but has no exact model ID to verify the initialized
        # model against, so it stays preflight_unresolved; pass --model to test it.
        pass
    elif args.preflight_only:
        report.update(status="PREFLIGHT_ONLY", reason="no_live_requested")
    elif not args.yes or not args.retain_private_capture:
        report.update(status="CONSENT_NOT_GRANTED", reason="separate_live_and_private_capture_consent_required")
    else:
        ledger = ActionLedger(root)
        capture_hashes = {}
        sid, prompt = "", initial_prompt(root)
        private_write(out / "run_claim.json", {"maximum_children": MAX_INVOCATIONS, "never_relaunch": True})
        for sequence in range(MAX_INVOCATIONS):
            child = out / f"child_{sequence + 1}"
            child.mkdir(mode=0o700)
            private_write(child / "sequence.json", {"sequence": sequence + 1, "session_id": sid or None,
                                                    "digest_already_attempted": bool(ledger.digest_id)})
            argv = normal_argv(shutil.which("claude"), child / "native-debug.log", prompt, args.model, sid)
            config = Path(env.get("CLAUDE_CONFIG_DIR") or Path(env.get("HOME") or Path.home()) / ".claude")
            if not config.is_absolute():
                config = root / config
            monitor = StreamEvidence(ledger, resolution.resolved_model, expected_hash, sid)
            report["children_launched"] += 1
            meta = capture(argv, child, env, monitor, (child / "latest", config / "debug/latest", root / ".claude/debug/latest"))
            try:
                stdout, debug = read_capture(child / "stdout.jsonl"), read_capture(child / "native-debug.log")
                stderr = read_capture(child / "stderr.log")
                if re.search(rb"authentication_error|invalid_api_key|permission prompt|API Error|Traceback", stderr, re.I):
                    meta["stop_reason"] = meta["stop_reason"] or "transport_failure"
                for filename, content in (("stdout.jsonl", stdout), ("native-debug.log", debug), ("stderr.log", stderr)):
                    capture_hashes[str((child / filename).relative_to(out))] = hashlib.sha256(content).hexdigest()
                # Replay with the same cumulative ID ledger; identical events dedup.
                result, parsed = adjudicate(stdout, debug, meta, ledger, resolution.resolved_model, expected_hash, sid)
            except (OSError, EvidenceError):
                result, parsed = {"status": "INCONCLUSIVE", "reason": "capture_unreadable"}, None
            terminal = {"admission_rejected": "ADMISSION_REJECTED", "policy_denied": "POLICY_DENIED",
                        "classifier_parser_failure": "TRANSPORT_PARSER_FAILURE", "transport_or_interactive_permission": "TRANSPORT_PARSER_FAILURE",
                        "transport_failure": "TRANSPORT_PARSER_FAILURE", "hook_failed": "TRANSPORT_PARSER_FAILURE",
                        "unexpected_tool_or_action": "UNEXPECTED_ACTION", "second_digest_action": "UNEXPECTED_ACTION",
                        "tool_failed": "ACTION_FAILED", "digest_mismatch": "ACTION_FAILED"}
            if meta.get("stop_reason") in terminal:
                result.update(status=terminal[meta["stop_reason"]], reason=meta["stop_reason"])
            diagnostics = report["diagnostics"] + result.get("diagnostics", [])
            report.update(result)
            report["diagnostics"] = diagnostics
            private_write(child / "adjudication.json", result)
            if parsed:
                private_write(child / "owned_session.json", {"session_id": parsed.session_id})
            # Never resume after any action attempt, denial, error, ambiguity or timeout.
            if ledger.digest_id or result["status"] != "ACTION_NOT_REACHED":
                break
            next_prompt = continuation_prompt(parsed, args.allow_bounded_continuations)
            if not next_prompt:
                report["reason"] = "confirmation_not_delegated_or_unrecognized"
                break
            if sequence == MAX_INVOCATIONS - 1:
                report["reason"] = "continuation_budget_exhausted"
                break
            sid, prompt = parsed.session_id, next_prompt
        report["digest_attempted"] = bool(ledger.digest_id)
        report["as_configured_certification"] = args.model is None and report["status"] == "CLASSIFIER_ALLOW_PASS"
    # Verify current digest input has not changed during the run.
    if hashlib.sha256(read_capture(root / "CLAUDE.md")).hexdigest() != expected_hash:
        report.update(status="INCONCLUSIVE", reason="digest_input_changed")
    try:
        manifest = write_manifest(out)
        if report["children_launched"] and any(manifest[name]["sha256"] != digest for name, digest in capture_hashes.items()):
            report.update(status="INCONCLUSIVE", reason="capture_changed_after_adjudication")
    except (OSError, EvidenceError):
        report.update(status="INCONCLUSIVE", reason="capture_manifest_failure")
    report["as_configured_certification"] = args.model is None and report["status"] == "CLASSIFIER_ALLOW_PASS"
    report["proof_checks"] = {
        "main_configuration_compatible": resolution.compatibility == "compatible",
        "digest_success": report.get("digest_success", False),
        "normal_classifier_chain": report.get("normal_parser_acceptance_via_client_decision", False),
        "complete_acceptance": report["status"] == "CLASSIFIER_ALLOW_PASS",
    }
    private_write(out / "report.json", report)
    # Metadata only, not native prompts, policy or XML. Kept local/private.
    text = ("# Auto acceptance\n\n" + f"Status: {report['status']}\nReason: {report['reason']}\n"
            + f"CLI invocations: {report['children_launched']} (maximum 3; six turns/120 seconds each, five-second cleanup).\n"
            + f"Explicit model override: {report['explicit_override']}.\n"
            + "Only CLASSIFIER_ALLOW_PASS certifies this classifier transaction. Missing evidence is not a fast path.\n"
            + "Diagnostics (categories/hashes only; not billing eligibility or configuration changes):\n"
            + "".join(f"- {item['source']} {item['severity']}: {item['category']} (SHA256 {item['sha256']})\n"
                      for item in report["diagnostics"])
            + "See report.json for safe proof metadata and capture_manifest.json for private evidence hashes.\n"
            + report["retention"] + "\nThe monitor reacts after observation; normal CLI safeguards remain responsible for preexecution protection.\n")
    private_write(out / "report.md", text.encode())
    return report, out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None, help="Real invocation override, not as-configured certification.")
    parser.add_argument("--report-dir", default="", help="Fresh repository-contained directory (never reused).")
    parser.add_argument("--yes", action="store_true", help="Authorize bounded live cost; not capture or confirmations.")
    parser.add_argument("--retain-private-capture", action="store_true", help="Authorize private content-bearing capture and ordinary CLI/hook retention.")
    parser.add_argument("--allow-bounded-continuations", action="store_true", help="Delegate only recognized exact-scope framework confirmations.")
    parser.add_argument("--preflight-only", action="store_true", help="No CLI child or inference; health transport may be queried.")
    args = parser.parse_args(argv)
    try:
        report, out = run_acceptance(args)
    except (EvidenceError, OSError, ValueError):
        print(json.dumps({"status": "INCONCLUSIVE", "reason": "runner_preflight_or_persistence_error"}))
        return 2
    print(json.dumps({"status": report["status"], "reason": report["reason"], "report_directory": str(out)}))
    return exit_code(report["status"])


if __name__ == "__main__":
    sys.exit(main())
