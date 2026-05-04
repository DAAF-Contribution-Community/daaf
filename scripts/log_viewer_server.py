#!/usr/bin/env python3
"""
log_viewer_server.py — Custom HTTP server for the DAAF Log Explorer

Serves static files from REPO_ROOT (same as http.server) and provides
a /api/refresh-manifest endpoint that recovers in-flight sessions and
regenerates the session manifest.

Usage:
    python3 log_viewer_server.py --port 2719 --root /daaf --archive --logs-dir /daaf/.claude/logs/sessions
    python3 log_viewer_server.py --port 2719 --root /daaf --project-path /daaf/research/2026-03-29_Analysis
"""

import argparse
import http.server
import json
import os
import socketserver
import subprocess
import sys

# --- Parse arguments ---

parser = argparse.ArgumentParser(description="DAAF Log Explorer HTTP server")
parser.add_argument("--port", type=int, default=2719, help="Port to listen on (default: 2719)")
parser.add_argument("--root", type=str, required=True, help="Root directory to serve files from")
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--project-path", type=str, help="Absolute path to a DAAF research project")
group.add_argument("--archive", action="store_true", help="Archive mode (use with --logs-dir)")
parser.add_argument("--logs-dir", type=str, help="Logs directory (required with --archive)")
args = parser.parse_args()

if args.archive and not args.logs_dir:
    print("ERROR: --archive requires --logs-dir", file=sys.stderr)
    sys.exit(1)

PORT = args.port
ROOT_DIR = os.path.abspath(args.root)
RECOVERY_SCRIPT = os.path.join(ROOT_DIR, ".claude", "hooks", "recover-session-logs.sh")
GENERATOR_SCRIPT = os.path.join(ROOT_DIR, "scripts", "generate_log_viewer.py")

# --- Change to serving root ---

os.chdir(ROOT_DIR)

# --- Build the manifest regeneration command ---

if args.archive:
    GENERATOR_CMD = [sys.executable, GENERATOR_SCRIPT, "--logs-dir", args.logs_dir]
else:
    GENERATOR_CMD = [sys.executable, GENERATOR_SCRIPT, args.project_path]

# --- Request handler ---

class LogViewerHandler(http.server.SimpleHTTPRequestHandler):
    """Extends SimpleHTTPRequestHandler with a /api/refresh-manifest endpoint."""

    def do_GET(self):
        if self.path == "/api/refresh-manifest":
            self.handle_refresh_manifest()
        else:
            super().do_GET()

    def handle_refresh_manifest(self):
        """Run recovery + manifest regeneration and return JSON status."""
        errors = []

        # Step 1: Run recover-session-logs.sh to capture in-flight sessions
        if os.path.isfile(RECOVERY_SCRIPT):
            recovery_input = json.dumps({
                "session_id": "recovery",
                "transcript_path": "/home/appuser/.claude/projects/-daaf/_.jsonl"
            })
            recovery_env = os.environ.copy()
            recovery_env["CLAUDE_PROJECT_DIR"] = "/daaf"
            recovery_env["DAAF_SYNC_RECOVERY"] = "1"
            try:
                subprocess.run(
                    ["bash", RECOVERY_SCRIPT],
                    input=recovery_input,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=recovery_env,
                )
            except subprocess.TimeoutExpired:
                errors.append("Recovery script timed out after 30s")
            except Exception as e:
                errors.append("Recovery script error: " + str(e))
        else:
            errors.append("Recovery script not found: " + RECOVERY_SCRIPT)

        # Step 2: Regenerate the manifest
        try:
            result = subprocess.run(
                GENERATOR_CMD,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                stderr_snippet = (result.stderr or "").strip()[:500]
                errors.append("Manifest generation failed (exit " + str(result.returncode) + "): " + stderr_snippet)
        except subprocess.TimeoutExpired:
            errors.append("Manifest generation timed out after 60s")
        except Exception as e:
            errors.append("Manifest generation error: " + str(e))

        # Step 3: Return JSON response
        if errors:
            response = {"status": "error", "message": "; ".join(errors)}
            status_code = 500
        else:
            response = {"status": "ok"}
            status_code = 200

        response_body = json.dumps(response).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format, *log_args):
        """Suppress noisy per-request logging for static files; log API calls."""
        if self.path.startswith("/api/"):
            super().log_message(format, *log_args)

# --- Start server ---

socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", PORT), LogViewerHandler)

# Startup messages are printed by the calling shell script (generate_log_viewer.sh),
# which knows the full viewer URL. Only print Ctrl+C reminder here.
print("  Press Ctrl+C to stop the server.")
print("")

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServer stopped.")
    httpd.server_close()
