#!/usr/bin/env python3
"""Fake `codex` CLI stub for provider-shim auth-delegation tests.

The production shim (v1.3.0+) no longer refreshes ChatGPT OAuth tokens itself;
it DELEGATES refresh to the codex CLI by spawning ``codex login status`` and then
re-reading ``$CODEX_HOME/auth.json``. This stub stands in for that binary so the
tests can drive every delegated-refresh outcome deterministically, entirely
offline, with no real network or real credentials.

It is injected via the ``SHIM_CODEX_BIN`` environment variable and behaves per the
``FAKE_CODEX_MODE`` environment variable:

  refresh-success  Rewrite auth.json's access_token with a fresh (far-future exp)
                   fabricated JWT, preserving every other field; print the
                   logged-in banner; exit 0. Models codex performing the refresh.
  noop             Print the logged-in banner; leave auth.json untouched; exit 0.
                   Models codex deciding no refresh is needed (or being unable to
                   change the on-disk token). This is the default when unset.
  not-logged-in    Print "Not logged in"; exit 1. Models a logged-out store.
  hang             Sleep far longer than any test timeout. Exercises the shim's
                   SHIM_CODEX_TIMEOUT_S kill path.

Every invocation appends one line to ``$CODEX_HOME/.codex_calls`` so tests can
assert single-flight behavior (the delegated refresh spawns codex exactly once
under concurrency). All tokens/markers are transparently fabricated test-only
values — no real secret material is ever produced or read.
"""

import base64
import json
import os
import sys
import time


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _make_fresh_jwt(ttl_seconds):
    # Minimal JWT the shim's _jwt_exp() can decode: header.payload.signature with a
    # base64url payload carrying a future `exp`. Signature is inert fabricated bytes.
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
    payload = _b64url(
        json.dumps(
            {
                "exp": int(time.time()) + int(ttl_seconds),
                "marker": "FABRICATED_FAKE_CODEX_STUB_ONLY",
            }
        ).encode("utf-8")
    )
    signature = _b64url(b"fabricated-fake-codex-signature")
    return f"{header}.{payload}.{signature}"


codex_home = os.environ.get("CODEX_HOME", "")
mode = os.environ.get("FAKE_CODEX_MODE", "noop").strip() or "noop"

# Invocation counter (single-flight assertions). Best-effort; never fatal.
if codex_home:
    try:
        with open(os.path.join(codex_home, ".codex_calls"), "a", encoding="utf-8") as f:
            f.write(f"{mode}\n")
    except OSError:
        pass

if mode == "hang":
    time.sleep(3600)
    sys.exit(0)

if mode == "not-logged-in":
    sys.stderr.write("Not logged in\n")
    sys.exit(1)

if mode == "refresh-success":
    auth_path = os.path.join(codex_home, "auth.json")
    try:
        with open(auth_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        tokens = data.get("tokens")
        if not isinstance(tokens, dict):
            tokens = {}
            data["tokens"] = tokens
        tokens["access_token"] = _make_fresh_jwt(3600)
        # Codex writes atomically; a plain write is sufficient for the test store.
        with open(auth_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.chmod(auth_path, 0o600)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"fake-codex refresh-success failed: {type(exc).__name__}\n")
        sys.exit(1)
    sys.stdout.write("Logged in using ChatGPT\n")
    sys.exit(0)

# Default / "noop": codex reports logged-in but changes nothing on disk.
sys.stdout.write("Logged in using ChatGPT\n")
sys.exit(0)
