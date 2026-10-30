"""Loopback tests for the Host-header check in scripts/log_viewer_server.py.

log_viewer_server.py is a top-level script (it parses arguments, chdirs and
serves at import time), so it cannot be imported here. Each test class starts
the real script as a subprocess on a free loopback port, serving a temporary
root that holds one synthetic file, and sends raw HTTP requests with chosen
Host headers through http.client. The server refuses any Host that does not
name localhost, 127.0.0.1 or [::1] (DNS-rebinding guard), for every method.

Nothing leaves the machine: the server binds all interfaces as in production,
but the tests connect to 127.0.0.1 only. The served root lives under
scripts/scratch/ (NEVER /tmp) and is removed in tearDownClass; the refresh
endpoint finds no recovery or generator script there, so a request that gets
through it changes nothing on disk.
Standard library only (the CI unit venv holds only httpx).

Run (file-first: from a captured script, through subprocess):
  python3 -m unittest discover -s tests/python -p 'test_log_viewer_server.py'
"""

import http.client
import shutil
import socket
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_SERVER = _SCRIPTS / "log_viewer_server.py"
_BODY = b"synthetic viewer file\n"


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LogViewerHostCheckTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = _SCRIPTS / "scratch" / f"log_viewer_test_{uuid.uuid4().hex[:10]}"
        cls.root.mkdir(parents=True)
        root = cls.root
        (root / "hello.txt").write_bytes(_BODY)
        cls.port = _free_port()
        cls.proc = subprocess.Popen(
            [sys.executable, str(_SERVER), "--port", str(cls.port), "--root", str(root),
             "--project-path", str(root / "no_project")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 15
        while True:
            try:
                socket.create_connection(("127.0.0.1", cls.port), timeout=1).close()
                break
            except OSError:
                if cls.proc.poll() is not None or time.time() > deadline:
                    cls.proc.kill()
                    shutil.rmtree(cls.root, ignore_errors=True)
                    raise RuntimeError("log_viewer_server.py did not start listening")
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
            cls.proc.wait(timeout=10)
        shutil.rmtree(cls.root, ignore_errors=True)

    def request(self, method, path, hosts):
        """Send one request with exactly the given Host header values (none if empty)."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for value in hosts:
                conn.putheader("Host", value)
            conn.endheaders()
            resp = conn.getresponse()
            return resp.status, resp.getheader("Content-Type"), resp.read()
        finally:
            conn.close()

    # --- Loopback hosts are served (any port, any case) ---

    def test_loopback_hosts_are_served(self):
        p = self.port
        for host in (f"localhost:{p}", "localhost", f"127.0.0.1:{p}", "127.0.0.1",
                     f"[::1]:{p}", "[::1]", "::1", f"LocalHost:{p}", "localhost:3719"):
            with self.subTest(host=host):
                status, _, body = self.request("GET", "/hello.txt", [host])
                self.assertEqual(status, 200)
                self.assertEqual(body, _BODY)

    def test_head_with_loopback_host_is_served(self):
        status, _, body = self.request("HEAD", "/hello.txt", [f"localhost:{self.port}"])
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")

    # --- Anything else is refused with a short plain-text 403 ---

    def test_foreign_hosts_are_refused(self):
        p = self.port
        for host in (f"evil.example:{p}", "evil.example", f"localhost.evil.example:{p}",
                     f"127.0.0.1.nip.io:{p}", f"evil.example#@localhost:{p}", "0.0.0.0",
                     f"localhost:{p}x", "localhost:", f"[::1]x:{p}", "[::1", f"::1:{p}",
                     "127.0.0.2", f"[::ffff:127.0.0.1]:{p}", ""):
            with self.subTest(host=host):
                status, ctype, body = self.request("GET", "/hello.txt", [host])
                self.assertEqual(status, 403)
                self.assertTrue(ctype.startswith("text/plain"))
                self.assertIn(b"localhost", body)
                self.assertNotIn(_BODY, body)

    def test_missing_host_is_refused(self):
        status, _, body = self.request("GET", "/hello.txt", [])
        self.assertEqual(status, 403)
        self.assertNotIn(_BODY, body)

    def test_repeated_host_is_refused(self):
        status, _, _ = self.request("GET", "/hello.txt", [f"localhost:{self.port}", "evil.example"])
        self.assertEqual(status, 403)
        status, _, _ = self.request("GET", "/hello.txt", [f"localhost:{self.port}", f"localhost:{self.port}"])
        self.assertEqual(status, 403)

    def test_head_with_foreign_host_is_refused_without_body(self):
        status, _, body = self.request("HEAD", "/hello.txt", ["evil.example"])
        self.assertEqual(status, 403)
        self.assertEqual(body, b"")

    def test_refresh_endpoint_with_foreign_host_is_refused(self):
        # A loopback Host reaches the handler (which returns its JSON error,
        # since the temporary root has no recovery or generator script); a
        # foreign Host is stopped before the handler runs anything.
        status, ctype, _ = self.request("GET", "/api/refresh-manifest", [f"localhost:{self.port}"])
        self.assertEqual(ctype, "application/json")
        self.assertIn(status, (200, 500))
        status, ctype, _ = self.request("GET", "/api/refresh-manifest", ["evil.example"])
        self.assertEqual(status, 403)
        self.assertTrue(ctype.startswith("text/plain"))

    def test_other_methods_with_foreign_host_are_refused(self):
        # Unsupported methods normally get 501; the Host check answers first.
        for method in ("POST", "PUT", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                status, _, _ = self.request(method, "/hello.txt", ["evil.example"])
                self.assertEqual(status, 403)

    def test_malformed_request_line_gets_a_400(self):
        # Four words with a valid version: parse_request sets request_version,
        # then rejects the syntax before it sets self.path, and send_error logs
        # through log_message. A log_message that reads self.path directly
        # raised AttributeError there, so the client got no answer at all.
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as s:
            s.sendall(b"GET /hello.txt extra HTTP/1.0\r\n\r\n")
            reply = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                reply += chunk
        self.assertTrue(reply.startswith(b"HTTP/1.0 400"), reply[:80])
        self.assertNotIn(_BODY, reply)
        status, _, body = self.request("GET", "/hello.txt", [f"localhost:{self.port}"])
        self.assertEqual(status, 200)
        self.assertEqual(body, _BODY)

    def test_bind_address_is_unchanged(self):
        # Docker forwards the published port to the container's own address, so
        # the server must keep binding all interfaces.
        self.assertIn('socketserver.TCPServer(("", PORT), LogViewerHandler)',
                      _SERVER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
