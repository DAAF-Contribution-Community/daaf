#!/usr/bin/env python3
# =============================================================================
# render_codex_config.py — write $CODEX_HOME/config.toml from environment_settings.txt.
#
# Standalone CLI (argparse): the sanctioned exception to DAAF's no-functions rule.
# stdlib only. Called by start_shim.sh at every container start; failures there
# are non-fatal.
#
# Users edit ONLY environment_settings.txt on the host. Docker Compose turns each
# line into a container env var, and this tool turns the relevant ones into the
# Codex CLI's user-level config file:
#
#   DAAF_CODEX_CONFIG_<N>=dotted.key=VALUE
#     N is a positive integer (leading zeros allowed, so _01 is entry 1); entries
#     apply in numeric order and later entries override earlier ones. A variable
#     that starts with DAAF_CODEX_CONFIG but has no valid number is reported, not
#     silently ignored. The KEY is a TOML dotted key: bare parts (letters, digits,
#     _ and -) or quoted parts, e.g. projects."/daaf".trust_level. VALUE handling
#     follows `codex -c key=value`: it is parsed as a TOML value, and if it does
#     not parse it is used as a literal string. An empty VALUE is skipped (write
#     key="" for an empty string); nan/inf are refused.
#
#   Derived defaults (openai lane only): when SHIM_BACKEND_MODE=openai and
#   SHIM_BACKEND_BASE_URL points somewhere other than api.openai.com, a
#   `daaf_gateway` model provider is derived (base_url, env_key, wire_api) and
#   `model` is taken from ANTHROPIC_DEFAULT_OPUS_MODEL. Explicit entries win.
#   Nothing is derived on the chatgpt lane, so device login is unaffected.
#
# Secrets never go into the file. An entry is refused when (a) a key names a
# credential (api_key, token, secret, password, bearer, authorization, cookie,
# subscription key, or any part ending in "key"); (b) it puts a string value
# under http_headers or query_params, which Codex would send from the file in
# plain text (sole exception: query_params.api-version, a public version string
# Azure-style gateways require); or (c) any string value looks like a key or bearer credential
# ("sk-..." or "Bearer ..."). Pointers to environment variables are always
# allowed: env_key, *_env_var, and everything under env_http_headers (header
# name -> environment-variable NAME). Values are never printed or logged.
#
# File ownership: the rendered file starts with a DAAF marker line. A file
# without the marker is user-authored and is never overwritten (the result goes
# to config.toml.daaf-generated instead). A DAAF-managed file is removed when
# nothing is left to render, so deleting settings really deletes them.
#
# Run log: with --log-file, each run's warnings and a one-line summary (never
# values) are appended there, keeping the last LOG_KEEP_LINES lines, so a user
# can see the outcome later via `start_shim.sh --status`.
#
# Exit codes: 0 success or no-op; 2 one or more entries or variable names were
# invalid or refused (valid entries are still rendered); 1 the file could not be
# rendered/written.
# =============================================================================

import argparse
import datetime
import json
import math
import os
import re
import sys
import tempfile
import tomllib

MARKER = (
    "# Managed by DAAF: generated from environment_settings.txt at container start "
    "and overwritten every time. Delete this line to take manual control of this file."
)
MARKER_PREFIX = "# Managed by DAAF"
ENTRY_PREFIX = "DAAF_CODEX_CONFIG"
ENTRY_RE = re.compile(r"^DAAF_CODEX_CONFIG_([0-9]+)$")
SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
# A key part that ENDS with a credential word: refuses experimental_bearer_token,
# X-Api-Key, Ocp-Apim-Subscription-Key, Cookie or a bare `key`, but not
# model_auto_compact_token_limit or model_max_output_tokens. env_key, *_env_var
# and env_http_headers.* hold environment-variable NAMES and are exempt.
SECRET_KEY_RE = re.compile(
    r"(^|[_-])(api[_-]?key|apikey|token|secret|password|bearer|authorization"
    r"|cookie|subscription[_-]?key|key)$",
    re.IGNORECASE,
)
# A string that looks like a credential itself, wherever it appears.
SECRET_VALUE_RE = re.compile(r"^\s*(sk-|bearer\s)", re.IGNORECASE)
# Codex sends these maps' values from the file verbatim (plain text on disk).
PLAIN_TEXT_MAPS = {"http_headers", "query_params"}
ENV_POINTER_MAP = "env_http_headers"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
GATEWAY_ID = "daaf_gateway"
LOG_KEEP_LINES = 200
RUN_LOG = []  # (kind, text) records for --log-file; never contains values


def note(kind, text):
    RUN_LOG.append((kind, text))


def warn(message):
    note("warning", message)
    print(f"render_codex_config: WARNING: {message}", file=sys.stderr)


def error(message):
    note("error", message)
    print(f"render_codex_config: ERROR: {message}", file=sys.stderr)


def safe_name(name):
    # Env-var names come from the user's file; show them as one bounded token.
    return re.sub(r"[^A-Za-z0-9_]", "?", name)[:80]


def label_segment(segment):
    if SECRET_VALUE_RE.match(segment):
        return "<redacted>"
    return segment if SEGMENT_RE.match(segment) else json.dumps(segment)


def label(path):
    text = ".".join(label_segment(str(segment)) for segment in path)
    return text if len(text) <= 120 else text[:117] + "..."


def normalize_base_url(raw):
    # Mirrors the shim (v1.4.7): trim, drop trailing "/", drop a pasted /responses.
    url = (raw or "").strip().rstrip("/")
    if url.lower().endswith("/responses"):
        url = url[: -len("/responses")].rstrip("/")
    return url


def split_entry(entry):
    # Split at the first "=" that is not inside a quoted key part.
    quote = None
    escaped = False
    for index, char in enumerate(entry):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\" and quote == '"':
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "=":
            return entry[:index], entry[index + 1 :]
    return None


def parse_key(key):
    # TOML dotted-key grammar (bare or quoted parts), via tomllib itself.
    key = key.strip()
    if not key or any(ord(char) < 32 or ord(char) == 127 for char in key):
        return None
    try:
        parsed = tomllib.loads(f"{key} = 0")
    except tomllib.TOMLDecodeError:
        return None
    segments = []
    node = parsed
    while isinstance(node, dict) and len(node) == 1:
        ((name, node),) = node.items()
        segments.append(name)
    if not segments or isinstance(node, bool) or node != 0:
        return None
    return segments


def parse_value(text):
    # `codex -c` semantics: a TOML value if it parses as exactly one, else a string.
    try:
        parsed = tomllib.loads(f"v = {text}")
    except tomllib.TOMLDecodeError:
        return text
    return parsed["v"] if list(parsed) == ["v"] else text


def has_non_finite(value):
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(has_non_finite(inner) for inner in value.values())
    if isinstance(value, list):
        return any(has_non_finite(inner) for inner in value)
    return False


def name_is_credential(path):
    last = str(path[-1])
    if SECRET_VALUE_RE.match(last):
        return True
    lowered = last.lower()
    if lowered == "env_key" or lowered.endswith("_env_var"):
        return False
    if any(str(segment).lower() == ENV_POINTER_MAP for segment in path[:-1]):
        return False
    return bool(SECRET_KEY_RE.search(last))


def credential_findings(path, value, findings):
    # findings: {label: set of kinds}; kinds are "name", "value", "plain".
    if name_is_credential(path):
        findings.setdefault(label(path), set()).add("name")
    if isinstance(value, str):
        if SECRET_VALUE_RE.match(value):
            findings.setdefault(label(path), set()).add("value")
        lowered = [str(segment).lower() for segment in path]
        # Exception: Azure-style gateways need query_params.api-version, a public
        # API version string with no environment-variable route in Codex.
        version_param = lowered[-1] == "api-version" and "query_params" in lowered[:-1]
        if any(segment in PLAIN_TEXT_MAPS for segment in lowered) and not version_param:
            findings.setdefault(label(path), set()).add("plain")
    elif isinstance(value, dict):
        for key, inner in value.items():
            credential_findings(path + [str(key)], inner, findings)
    elif isinstance(value, list):
        for inner in value:
            credential_findings(path, inner, findings)


def set_path(config, segments, value):
    node = config
    for segment in segments[:-1]:
        if not isinstance(node.get(segment), dict):
            node[segment] = {}
        node = node[segment]
    node[segments[-1]] = value


def derived_defaults(env):
    if env.get("SHIM_BACKEND_MODE", "").strip().lower() != "openai":
        return {}
    base_url = normalize_base_url(env.get("SHIM_BACKEND_BASE_URL"))
    if not base_url or base_url == OPENAI_DEFAULT_BASE_URL:
        return {}
    # Same key precedence as the shim: SHIM_BACKEND_API_KEY, else OPENAI_API_KEY.
    # Only the variable NAME is written; its value never is.
    env_key = "SHIM_BACKEND_API_KEY" if env.get("SHIM_BACKEND_API_KEY") else "OPENAI_API_KEY"
    config = {
        "model_provider": GATEWAY_ID,
        "model_providers": {
            GATEWAY_ID: {
                "name": "DAAF gateway (SHIM_BACKEND_BASE_URL)",
                "base_url": base_url,
                "env_key": env_key,
                "wire_api": "responses",
            }
        },
    }
    model = env.get("ANTHROPIC_DEFAULT_OPUS_MODEL", "").strip()
    model = model.split("#", 1)[0].strip()
    model = re.sub(r"\[1m\]$", "", model, flags=re.IGNORECASE)
    model = model.rsplit("/", 1)[-1].strip()
    if model:
        config["model"] = model
    return config


def collect_entries(env):
    """Return ([(number, name)], problems) for well-named entries, in apply order."""
    problems = 0
    numbered = []
    for name in env:
        if not name.upper().startswith(ENTRY_PREFIX):
            continue
        match = ENTRY_RE.match(name)
        if not match or int(match.group(1)) == 0:
            warn(
                f"{safe_name(name)} ignored: the name must be DAAF_CODEX_CONFIG_ followed by a "
                "number from 1 up (for example DAAF_CODEX_CONFIG_1). Rename that line in "
                "environment_settings.txt."
            )
            problems += 1
            continue
        numbered.append((int(match.group(1)), name))
    numbered.sort()
    by_number = {}
    for number, name in numbered:
        by_number.setdefault(number, []).append(name)
    for number, names in sorted(by_number.items()):
        if len(names) > 1:
            warn(
                f"{' and '.join(names)} all use number {number}; they apply in that order, so "
                "the last one wins where they overlap. Give each line its own number."
            )
            problems += 1
    return numbered, problems


def build_config(env):
    """Return (config, problems). problems counts invalid or refused entries."""
    config = derived_defaults(env)
    numbered, problems = collect_entries(env)
    for _, name in numbered:
        entry = env[name].strip()
        # Tolerate one layer of single quotes left by a loader that kept them.
        if len(entry) >= 2 and entry[0] == entry[-1] == "'":
            entry = entry[1:-1].strip()
        if not entry:
            continue  # an empty placeholder line is not an error
        parts = split_entry(entry)
        segments = parse_key(parts[0]) if parts else None
        if segments is None:
            warn(
                f"{name} skipped: expected dotted.key=VALUE, where each key part is letters, "
                'digits, _ or -, or is in double quotes (for example projects."/daaf".trust_level)'
            )
            problems += 1
            continue
        raw_value = parts[1].strip()
        if not raw_value:
            warn(f'{name} skipped: {label(segments)} has no value after "=" (write "" for an empty string)')
            problems += 1
            continue
        value = parse_value(raw_value)
        findings = {}
        for depth in range(1, len(segments)):
            if name_is_credential(segments[:depth]):
                findings.setdefault(label(segments[:depth]), set()).add("name")
        credential_findings(segments, value, findings)
        if findings:
            kinds = set().union(*findings.values())
            hints = []
            if "plain" in kinds:
                hints.append(
                    "Header and query-parameter values would sit in the file in plain text; use "
                    "env_http_headers instead (header name = the NAME of an environment variable "
                    "that holds the value)."
                )
            if kinds - {"plain"}:
                hints.append(
                    "Put the secret in an environment variable and point Codex at it with "
                    "env_key (or env_http_headers for a header)."
                )
            warn(
                f"{name} refused: {', '.join(sorted(findings))} could hold a credential, and "
                f"credentials are never written to config.toml. {' '.join(hints)}"
            )
            problems += 1
            continue
        if has_non_finite(value):
            warn(f"{name} refused: {label(segments)} uses nan or inf, which Codex settings do not accept")
            problems += 1
            continue
        set_path(config, segments, value)
    return config, problems


def toml_key(key):
    return key if SEGMENT_RE.match(key) else json.dumps(key)


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value).replace("\x7f", "\\u007f")
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{toml_key(k)} = {toml_value(v)}" for k, v in value.items()) + "}"
    raise TypeError(f"unsupported value type {type(value).__name__}")


def render_table(table, prefix, lines):
    # Plain keys first, then sub-tables as [a.b] sections (TOML ordering rule).
    for key, value in table.items():
        if not isinstance(value, dict):
            lines.append(f"{toml_key(key)} = {toml_value(value)}")
    for key, value in table.items():
        if isinstance(value, dict):
            path = prefix + [toml_key(key)]
            lines.append("")
            lines.append("[" + ".".join(path) + "]")
            render_table(value, path, lines)


def leaf_keys(table, prefix=None):
    keys = []
    for key, value in table.items():
        path = (prefix or []) + [key]
        keys.extend(leaf_keys(value, path) if isinstance(value, dict) else [label(path)])
    return keys


def is_managed(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.readline().startswith(MARKER_PREFIX)
    except (OSError, UnicodeDecodeError):
        return False


def atomic_write(path, text, prefix=".config.toml."):
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)  # replaces a symlink entry itself, never its target
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_run_log(path, exit_code):
    # Bounded, private, append-style log of this run (no values, ever). A missing
    # log is only created when the run has something to say.
    quiet = all(kind == "summary" and text.startswith("no Codex settings") for kind, text in RUN_LOG)
    if not RUN_LOG or (quiet and not os.path.lexists(path)):
        return
    directory = os.path.dirname(os.path.abspath(path))
    if os.path.islink(directory) or (os.path.lexists(directory) and not os.path.isdir(directory)):
        print(f"render_codex_config: WARNING: run log not written: {directory} is not a plain directory", file=sys.stderr)
        return
    if os.path.lexists(path) and (os.path.islink(path) or not os.path.isfile(path)):
        print(f"render_codex_config: WARNING: run log not written: {path} is not a regular file", file=sys.stderr)
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = []
    for kind, text in RUN_LOG:
        text = text + (f" (exit {exit_code})" if kind == "summary" else "")
        fresh.append(f"{stamp} {kind}: " + re.sub(r"[\x00-\x1f\x7f]", "?", text))
    try:
        os.makedirs(directory, mode=0o700, exist_ok=True)
        existing = []
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as handle:
                existing = handle.read().splitlines()
        kept = (existing + fresh)[-LOG_KEEP_LINES:]
        atomic_write(path, "\n".join(kept) + "\n", prefix=".codex_config.log.")
    except OSError as failure:
        print(f"render_codex_config: WARNING: run log not written: {failure.strerror}", file=sys.stderr)


def render(args):
    config, problems = build_config(os.environ)
    exit_code = 2 if problems else 0
    problem_note = f"; {problems} problem(s) - see the warnings" if problems else ""
    codex_home = args.codex_home or os.environ.get("CODEX_HOME", "").strip() or os.path.expanduser("~/.codex")
    target = os.path.join(codex_home, "config.toml")
    sidecar = target + ".daaf-generated"

    if not config:
        if args.dry_run:
            return exit_code
        # Nothing to render: remove only files DAAF itself wrote.
        removed = []
        for path in (target, sidecar):
            if os.path.isfile(path) and not os.path.islink(path) and is_managed(path):
                os.unlink(path)
                removed.append(path)
                print(f"render_codex_config: no Codex settings configured; removed {path}", file=sys.stderr)
        if removed:
            note("summary", f"no Codex settings configured; removed {', '.join(removed)}{problem_note}")
        else:
            note("summary", f"no Codex settings configured; nothing written{problem_note}")
        return exit_code

    lines = [MARKER, "# Credentials never belong here: Codex reads the API key from the env var named by env_key."]
    render_table(config, [], lines)
    text = "\n".join(lines) + "\n"
    if tomllib.loads(text) != config:
        error("rendered TOML did not round-trip; nothing written")
        note("summary", "ERROR: config.toml not written (render check failed)")
        return 1

    if args.dry_run:
        sys.stdout.write(text)
        return exit_code

    destination = target
    if os.path.lexists(target) and not (os.path.isfile(target) and not os.path.islink(target) and is_managed(target)):
        destination = sidecar
        warn(
            f"{target} was written by someone other than DAAF, so it was left alone. "
            f"The DAAF version is in {sidecar}; merge it by hand or delete your file to let DAAF manage it."
        )
    try:
        os.makedirs(codex_home, mode=0o700, exist_ok=True)
        atomic_write(destination, text)
    except OSError as failure:
        error(f"could not write {destination}: {failure.strerror}")
        note("summary", f"ERROR: could not write {destination}")
        return 1
    keys = leaf_keys(config)
    summary = f"wrote {len(keys)} setting(s) to {destination}: {', '.join(keys)}"
    print(f"render_codex_config: {summary}", file=sys.stderr)
    note("summary", summary + problem_note)
    return exit_code


def main():
    parser = argparse.ArgumentParser(
        description="Render $CODEX_HOME/config.toml from DAAF_CODEX_CONFIG_<N> env vars."
    )
    parser.add_argument("--dry-run", action="store_true", help="print the TOML; write nothing")
    parser.add_argument("--codex-home", help="target directory (default: $CODEX_HOME, else ~/.codex)")
    parser.add_argument("--log-file", help="append this run's summary and warnings (never values) here")
    args = parser.parse_args()
    exit_code = render(args)
    if args.log_file and not args.dry_run:
        write_run_log(args.log_file, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
