"""Focused contracts for the provider-shim lifecycle capability helper."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock


_REPO_ROOT = Path(__file__).resolve().parents[2]
_HELPER = _REPO_ROOT / "scripts" / "provider_shim" / "lifecycle_capability.py"
_SCRATCH_PARENT = Path(__file__).resolve().parent / ".lifecycle-capability-scratch"
_SPEC = importlib.util.spec_from_file_location("lifecycle_capability_under_test", _HELPER)
assert _SPEC is not None and _SPEC.loader is not None
_CAPABILITY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CAPABILITY)


class LifecycleCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        _SCRATCH_PARENT.mkdir(mode=0o700, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="case-", dir=_SCRATCH_PARENT))
        self.root.chmod(0o700)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
        try:
            _SCRATCH_PARENT.rmdir()
        except OSError:
            pass

    def run_helper(
        self,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        child_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.root),
            "LANG": "C",
            "LC_ALL": "C",
        }
        if env:
            child_env.update(env)
        return subprocess.run(
            ["python3", str(_HELPER), *args],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
            env=child_env,
        )

    def parse_record(self, result: subprocess.CompletedProcess[str]) -> list[str]:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        fields = result.stdout.rstrip("\n").split("\t")
        self.assertEqual(len(fields), 5, result.stdout)
        self.assertEqual(fields[0], "LCAP1")
        return fields

    def test_pid_read_fixed_schema_for_absent_valid_invalid_and_hostile(self) -> None:
        pid_path = self.root / "service.pid"

        fields = self.parse_record(self.run_helper("pid-read", str(pid_path)))
        self.assertEqual(fields[1:], ["PID_READ", "ABSENT", "absent", "-"])

        pid_path.write_bytes(b"12345\n")
        pid_path.chmod(0o600)
        fields = self.parse_record(self.run_helper("pid-read", str(pid_path)))
        self.assertEqual(fields[1:], ["PID_READ", "VALID", "valid", "12345"])

        pid_path.write_bytes(b"12\x003\n")
        fields = self.parse_record(self.run_helper("pid-read", str(pid_path)))
        self.assertEqual(fields[2], "INVALID_CONTENT")
        self.assertEqual(fields[3], "invalid_grammar")
        self.assertEqual(fields[4], "-")

        pid_path.unlink()
        target = self.root / "target.pid"
        target.write_bytes(b"12345\n")
        target.chmod(0o600)
        pid_path.symlink_to(target)
        fields = self.parse_record(self.run_helper("pid-read", str(pid_path)))
        self.assertEqual(fields[2], "HOSTILE_OBJECT")
        self.assertEqual(fields[3], "symlink")

    def test_pid_faults_are_typed_and_crash_is_observable(self) -> None:
        pid_path = self.root / "service.pid"
        pid_path.write_bytes(b"12345\n")
        pid_path.chmod(0o600)
        for fault in ("open", "fd_identity", "read"):
            with self.subTest(fault=fault):
                fields = self.parse_record(
                    self.run_helper(
                        "pid-read",
                        str(pid_path),
                        env={
                            "DAAF_SHIM_TEST_MODE": "1",
                            "DAAF_SHIM_TEST_PID_FAULT": fault,
                        },
                    )
                )
                self.assertEqual(fields[2], "INFRASTRUCTURE_ERROR")
                self.assertEqual(fields[4], "-")
        crashed = self.run_helper(
            "pid-read",
            str(pid_path),
            env={
                "DAAF_SHIM_TEST_MODE": "1",
                "DAAF_SHIM_TEST_PID_FAULT": "helper_crash",
            },
        )
        self.assertNotEqual(crashed.returncode, 0)
        self.assertEqual(crashed.stdout, "")

    def test_test_faults_are_inert_without_exact_test_mode(self) -> None:
        pid_path = self.root / "service.pid"
        pid_path.write_bytes(b"12345\n")
        pid_path.chmod(0o600)
        for test_mode in (None, "0", "true"):
            with self.subTest(test_mode=test_mode):
                env = {"DAAF_SHIM_TEST_PID_FAULT": "open"}
                if test_mode is not None:
                    env["DAAF_SHIM_TEST_MODE"] = test_mode
                fields = self.parse_record(
                    self.run_helper("pid-read", str(pid_path), env=env)
                )
                self.assertEqual(fields[1:], ["PID_READ", "VALID", "valid", "12345"])

    def test_workspace_cleanup_finds_renamed_original_and_preserves_replacement(self) -> None:
        log_parent = self.root / "logs"
        log_parent.mkdir(mode=0o700)
        created = self.parse_record(
            self.run_helper("workspace-create", str(log_parent))
        )
        self.assertEqual(created[1:4], ["WORKSPACE_CREATE", "READY", "created"])
        token = created[4]
        basename = token.split("|")[1]
        original = log_parent / basename
        # Regression 5: inode lookup must survive an arbitrary same-parent rename,
        # not only a rename that retains the shim.stream. prefix.
        renamed = log_parent / "quarantine"
        original.rename(renamed)

        replacement = log_parent / basename
        replacement.mkdir(mode=0o700)
        replacement_owner = replacement / ".owner"
        replacement_owner.write_text("replacement\n", encoding="ascii")
        replacement_owner.chmod(0o600)
        replacement_fifo = replacement / "output.fifo"
        os.mkfifo(replacement_fifo, 0o600)

        cleaned = self.parse_record(
            self.run_helper("workspace-clean", str(log_parent), token)
        )
        self.assertEqual(cleaned[1], "WORKSPACE_CLEAN")
        self.assertEqual(cleaned[2], "CLEANED")
        self.assertEqual(cleaned[3], "cleaned_replacement_preserved")
        self.assertFalse(renamed.exists())
        self.assertTrue(replacement.is_dir())
        self.assertTrue(stat.S_ISFIFO(replacement_fifo.lstat().st_mode))
        self.assertEqual(replacement_owner.read_text(encoding="ascii"), "replacement\n")

    def assert_member_substitution_is_not_deleted(self, member: str) -> None:
        log_parent = self.root / "logs"
        log_parent.mkdir(mode=0o700)
        created = self.parse_record(
            self.run_helper("workspace-create", str(log_parent))
        )
        token = created[4]
        workspace = log_parent / token.split("|")[1]
        member_path = workspace / member
        captured_identity = (member_path.lstat().st_dev, member_path.lstat().st_ino)
        captured_original = self.root / f"captured-{member.lstrip('.')}"
        replacement_identity: tuple[int, int] | None = None
        substituted = False
        real_rename = os.rename
        real_unlink = os.unlink

        def substitute_once(directory_fd: int) -> None:
            nonlocal replacement_identity, substituted
            if substituted:
                return
            substituted = True
            # Simulate one same-UID substitution at the helper's actual destructive
            # boundary. Move the validated inode aside and put a foreign object of the
            # same accepted type/mode at its mutable name.
            real_rename(member, captured_original, src_dir_fd=directory_fd)
            if member == ".owner":
                replacement_fd = os.open(
                    member,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                    0o600,
                    dir_fd=directory_fd,
                )
                try:
                    os.write(replacement_fd, b"foreign-replacement\n")
                finally:
                    os.close(replacement_fd)
            else:
                os.mkfifo(member, 0o600, dir_fd=directory_fd)
            replacement_st = os.stat(
                member,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            replacement_identity = (replacement_st.st_dev, replacement_st.st_ino)

        def rename_at_boundary(src: object, dst: object, *args: object, **kwargs: object) -> None:
            directory_fd = kwargs.get("src_dir_fd")
            if src == member and isinstance(directory_fd, int):
                substitute_once(directory_fd)
            real_rename(src, dst, *args, **kwargs)

        def unlink_at_boundary(path: object, *args: object, **kwargs: object) -> None:
            directory_fd = kwargs.get("dir_fd")
            if path == member and isinstance(directory_fd, int):
                substitute_once(directory_fd)
            real_unlink(path, *args, **kwargs)

        output = io.StringIO()
        with (
            mock.patch.object(_CAPABILITY.os, "rename", side_effect=rename_at_boundary),
            mock.patch.object(_CAPABILITY.os, "unlink", side_effect=unlink_at_boundary),
            redirect_stdout(output),
        ):
            _CAPABILITY.workspace_clean(str(log_parent), token)

        fields = output.getvalue().rstrip("\n").split("\t")
        self.assertTrue(substituted, "member substitution seam was not reached")
        self.assertEqual(fields[0:2], ["LCAP1", "WORKSPACE_CLEAN"])
        self.assertEqual(fields[2], "CONTAMINATED", output.getvalue())
        self.assertNotEqual(fields[2], "CLEANED")
        self.assertTrue(workspace.is_dir())
        self.assertTrue(member_path.exists())
        replacement_st = member_path.lstat()
        self.assertEqual(
            (replacement_st.st_dev, replacement_st.st_ino),
            replacement_identity,
        )
        self.assertNotEqual(
            (replacement_st.st_dev, replacement_st.st_ino),
            captured_identity,
        )
        self.assertTrue(captured_original.exists())
        captured_st = captured_original.lstat()
        self.assertEqual((captured_st.st_dev, captured_st.st_ino), captured_identity)
        if member == ".owner":
            self.assertEqual(
                member_path.read_text(encoding="ascii"),
                "foreign-replacement\n",
            )
            self.assertTrue(stat.S_ISREG(captured_st.st_mode))
        else:
            self.assertTrue(stat.S_ISFIFO(replacement_st.st_mode))
            self.assertTrue(stat.S_ISFIFO(captured_st.st_mode))

    def test_workspace_cleanup_does_not_delete_substituted_fifo_at_removal_boundary(self) -> None:
        self.assert_member_substitution_is_not_deleted("output.fifo")

    def test_workspace_cleanup_does_not_delete_substituted_owner_at_removal_boundary(self) -> None:
        self.assert_member_substitution_is_not_deleted(".owner")

    def test_workspace_seam_is_inert_without_test_mode(self) -> None:
        log_parent = self.root / "logs"
        log_parent.mkdir(mode=0o700)
        created = self.parse_record(
            self.run_helper(
                "workspace-create",
                str(log_parent),
                env={"DAAF_SHIM_TEST_WORKSPACE_FAULT": "create"},
            )
        )
        self.assertEqual(created[2], "READY")
        cleaned = self.parse_record(
            self.run_helper("workspace-clean", str(log_parent), created[4])
        )
        self.assertEqual(cleaned[2], "CLEANED")


if __name__ == "__main__":
    unittest.main()
