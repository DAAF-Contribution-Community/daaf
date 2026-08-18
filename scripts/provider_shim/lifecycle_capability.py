#!/usr/bin/env python3
"""Typed filesystem capabilities for the provider-shim lifecycle manager."""

from __future__ import annotations

import errno
import os
from pathlib import Path
import secrets
import stat
import sys


_SCHEMA = "LCAP1"
_PREFIX = "shim.stream."
_OWNER = ".owner"
_FIFO = "output.fifo"
_MAX_PID = 2_147_483_647


def emit(operation: str, outcome: str, reason: str, value: str = "-") -> None:
    fields = (_SCHEMA, operation, outcome, reason, value)
    if any("\t" in field or "\n" in field or "\r" in field for field in fields):
        raise RuntimeError("capability record contains an unsafe field")
    sys.stdout.write("\t".join(fields) + "\n")


def test_fault(name: str) -> bool:
    return os.environ.get("DAAF_SHIM_TEST_MODE") == "1" and os.environ.get(
        "DAAF_SHIM_TEST_PID_FAULT"
    ) == name


def identity(st: os.stat_result) -> tuple[int, int]:
    return st.st_dev, st.st_ino


def pid_read(path_text: str) -> None:
    path = Path(path_text)
    if test_fault("helper_crash"):
        os._exit(97)
    if test_fault("malformed_output"):
        sys.stdout.write("MALFORMED\n")
        return

    try:
        before = os.lstat(path)
    except FileNotFoundError:
        emit("PID_READ", "ABSENT", "absent")
        return
    except OSError:
        emit("PID_READ", "INFRASTRUCTURE_ERROR", "lstat")
        return

    if stat.S_ISLNK(before.st_mode):
        emit("PID_READ", "HOSTILE_OBJECT", "symlink")
        return
    if not stat.S_ISREG(before.st_mode):
        emit("PID_READ", "HOSTILE_OBJECT", "non_regular")
        return
    if before.st_uid != os.geteuid():
        emit("PID_READ", "HOSTILE_OBJECT", "unsafe_owner")
        return
    if stat.S_IMODE(before.st_mode) & 0o077:
        emit("PID_READ", "HOSTILE_OBJECT", "unsafe_mode")
        return
    if test_fault("open"):
        emit("PID_READ", "INFRASTRUCTURE_ERROR", "open")
        return

    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENXIO):
            emit("PID_READ", "HOSTILE_OBJECT", "open_object_changed")
        else:
            emit("PID_READ", "INFRASTRUCTURE_ERROR", "open")
        return

    try:
        if test_fault("fd_identity"):
            emit("PID_READ", "INFRASTRUCTURE_ERROR", "fd_identity")
            return
        try:
            opened = os.fstat(fd)
        except OSError:
            emit("PID_READ", "INFRASTRUCTURE_ERROR", "fd_identity")
            return
        if not stat.S_ISREG(opened.st_mode) or identity(opened) != identity(before):
            emit("PID_READ", "HOSTILE_OBJECT", "identity_race")
            return
        if opened.st_uid != os.geteuid() or stat.S_IMODE(opened.st_mode) & 0o077:
            emit("PID_READ", "HOSTILE_OBJECT", "unsafe_metadata")
            return
        if test_fault("read"):
            emit("PID_READ", "INFRASTRUCTURE_ERROR", "read")
            return
        try:
            raw = os.read(fd, 66)
        except OSError:
            emit("PID_READ", "INFRASTRUCTURE_ERROR", "read")
            return
        try:
            after = os.lstat(path)
        except FileNotFoundError:
            emit("PID_READ", "HOSTILE_OBJECT", "path_disappeared")
            return
        except OSError:
            emit("PID_READ", "INFRASTRUCTURE_ERROR", "path_recheck")
            return
        if identity(after) != identity(opened) or not stat.S_ISREG(after.st_mode):
            emit("PID_READ", "HOSTILE_OBJECT", "identity_race")
            return
    finally:
        os.close(fd)

    if raw.endswith(b"\n"):
        digits = raw[:-1]
    else:
        digits = raw
    if not 1 <= len(digits) <= 10 or not digits.isascii() or not digits.isdigit():
        emit("PID_READ", "INVALID_CONTENT", "invalid_grammar")
        return
    value = int(digits)
    if value < 2 or value > _MAX_PID:
        emit("PID_READ", "INVALID_CONTENT", "unsupported_pid")
        return
    emit("PID_READ", "VALID", "valid", str(value))


def parent_open(path: Path) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    opened = os.fstat(fd)
    current = os.lstat(path)
    if not stat.S_ISDIR(opened.st_mode) or identity(opened) != identity(current):
        os.close(fd)
        raise OSError(errno.ESTALE, "log parent identity changed")
    if opened.st_uid != os.geteuid() or stat.S_IMODE(opened.st_mode) & 0o077:
        os.close(fd)
        raise PermissionError("unsafe log parent metadata")
    return fd, opened


def encode_token(
    basename: str,
    nonce: str,
    parent_st: os.stat_result,
    directory_st: os.stat_result,
    fifo_st: os.stat_result,
    owner_st: os.stat_result,
) -> str:
    values = (
        "W1",
        basename,
        nonce,
        str(parent_st.st_dev),
        str(parent_st.st_ino),
        str(directory_st.st_dev),
        str(directory_st.st_ino),
        str(fifo_st.st_dev),
        str(fifo_st.st_ino),
        str(owner_st.st_dev),
        str(owner_st.st_ino),
    )
    return "|".join(values)


def decode_token(token: str) -> tuple[str, str, tuple[int, ...]]:
    parts = token.split("|")
    if len(parts) != 11 or parts[0] != "W1":
        raise ValueError("token_schema")
    basename, nonce = parts[1], parts[2]
    if not basename.startswith(_PREFIX) or "/" in basename or basename in (".", ".."):
        raise ValueError("token_basename")
    if len(nonce) != 32 or any(char not in "0123456789abcdef" for char in nonce):
        raise ValueError("token_nonce")
    numeric = tuple(int(part) for part in parts[3:])
    if any(value < 0 for value in numeric):
        raise ValueError("token_identity")
    return basename, nonce, numeric


def workspace_create(parent_text: str) -> None:
    parent = Path(parent_text)
    created_name = ""
    parent_fd = -1
    directory_fd = -1
    try:
        parent_fd, parent_st = parent_open(parent)
        if os.environ.get("DAAF_SHIM_TEST_MODE") == "1" and os.environ.get(
            "DAAF_SHIM_TEST_WORKSPACE_FAULT"
        ) == "create":
            emit("WORKSPACE_CREATE", "ERROR", "create_fault")
            return
        nonce = secrets.token_hex(16)
        created_name = _PREFIX + secrets.token_hex(12)
        os.mkdir(created_name, mode=0o700, dir_fd=parent_fd)
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        directory_flags |= getattr(os, "O_NOFOLLOW", 0)
        directory_fd = os.open(created_name, directory_flags, dir_fd=parent_fd)
        directory_st = os.fstat(directory_fd)
        owner_fd = os.open(
            _OWNER,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        try:
            payload = (nonce + "\n").encode("ascii")
            if os.write(owner_fd, payload) != len(payload):
                raise OSError(errno.EIO, "short owner write")
            owner_st = os.fstat(owner_fd)
        finally:
            os.close(owner_fd)
        os.mkfifo(_FIFO, 0o600, dir_fd=directory_fd)
        fifo_st = os.stat(_FIFO, dir_fd=directory_fd, follow_symlinks=False)
        token = encode_token(created_name, nonce, parent_st, directory_st, fifo_st, owner_st)
        emit("WORKSPACE_CREATE", "READY", "created", token)
    except OSError:
        if directory_fd >= 0:
            for name in (_FIFO, _OWNER):
                try:
                    os.unlink(name, dir_fd=directory_fd)
                except OSError:
                    pass
        if parent_fd >= 0 and created_name:
            try:
                os.rmdir(created_name, dir_fd=parent_fd)
            except OSError:
                pass
        emit("WORKSPACE_CREATE", "ERROR", "infrastructure")
    finally:
        if directory_fd >= 0:
            os.close(directory_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def restore_quarantined_member(
    directory_fd: int,
    quarantine_name: str,
    original_name: str,
) -> str:
    """Restore one quarantined foreign inode without overwriting another entry."""
    try:
        # linkat is an atomic no-replace restoration primitive here: if another
        # entry appeared at original_name, preserve both objects and fail closed.
        os.link(
            quarantine_name,
            original_name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
    except FileExistsError:
        return "restore_name_occupied"
    except OSError:
        return "restore_link"
    try:
        os.unlink(quarantine_name, dir_fd=directory_fd)
    except OSError:
        # The restored name already references this exact inode. Retaining the
        # private hard link is a bounded cleanup failure, never foreign deletion.
        return "restore_quarantine_unlink"
    return "restored"


def quarantine_remove_member(
    directory_fd: int,
    name: str,
    expected_identity: tuple[int, int],
    expected_kind: str,
) -> tuple[str, str]:
    """Atomically bind removal to the captured member or preserve a substitute."""
    quarantine_name = f".lcap-quarantine-{secrets.token_hex(16)}"
    try:
        os.rename(
            name,
            quarantine_name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
    except FileNotFoundError:
        return "CONTAMINATED", "member_disappeared"
    except OSError:
        return "ERROR", "quarantine_rename"

    try:
        quarantined_st = os.stat(
            quarantine_name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
    except OSError:
        return "ERROR", "quarantine_stat"

    kind_matches = (
        expected_kind == "fifo" and stat.S_ISFIFO(quarantined_st.st_mode)
    ) or (
        expected_kind == "owner" and stat.S_ISREG(quarantined_st.st_mode)
    )
    metadata_matches = (
        identity(quarantined_st) == expected_identity
        and kind_matches
        and quarantined_st.st_uid == os.geteuid()
        and stat.S_IMODE(quarantined_st.st_mode) == 0o600
    )
    if not metadata_matches:
        restoration = restore_quarantined_member(
            directory_fd,
            quarantine_name,
            name,
        )
        if restoration == "restored":
            return "CONTAMINATED", "substituted_restored"
        return "ERROR", restoration

    try:
        # Only the unpredictable private name whose inode was just matched to the
        # captured capability is destructively removed. The original mutable name
        # is never passed to unlink on the matching path. Linux offers no
        # inode-conditional unlink, so this final removal is pathname-based on the
        # unguessable quarantine name: best-effort hardening, not an absolute
        # identity-bound guarantee (documented threat-model boundary).
        os.unlink(quarantine_name, dir_fd=directory_fd)
    except OSError:
        return "ERROR", "quarantine_unlink"
    return "REMOVED", "removed"


def workspace_clean(parent_text: str, token: str) -> None:
    parent = Path(parent_text)
    try:
        basename, nonce, numeric = decode_token(token)
    except (ValueError, OverflowError):
        emit("WORKSPACE_CLEAN", "ERROR", "invalid_token")
        return
    expected_parent = numeric[0:2]
    expected_directory = numeric[2:4]
    expected_fifo = numeric[4:6]
    expected_owner = numeric[6:8]
    parent_fd = -1
    directory_fd = -1
    found_name = ""
    try:
        parent_fd, parent_st = parent_open(parent)
        if identity(parent_st) != expected_parent:
            emit("WORKSPACE_CLEAN", "ERROR", "parent_identity")
            return
        if os.environ.get("DAAF_SHIM_TEST_MODE") == "1" and os.environ.get(
            "DAAF_SHIM_TEST_WORKSPACE_FAULT"
        ) == "clean":
            emit("WORKSPACE_CLEAN", "ERROR", "clean_fault")
            return
        # Search only bounded direct children of the already identity-validated
        # parent. The captured inode, not a mutable basename prefix, identifies the
        # original workspace after an arbitrary same-parent rename.
        with os.scandir(parent_fd) as entries:
            for entry in entries:
                try:
                    child_st = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISDIR(child_st.st_mode) and identity(child_st) == expected_directory:
                    found_name = entry.name
                    break
        if not found_name:
            emit("WORKSPACE_CLEAN", "NOT_FOUND", "original_not_under_parent")
            return
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        directory_flags |= getattr(os, "O_NOFOLLOW", 0)
        directory_fd = os.open(found_name, directory_flags, dir_fd=parent_fd)
        directory_st = os.fstat(directory_fd)
        if identity(directory_st) != expected_directory or directory_st.st_uid != os.geteuid():
            emit("WORKSPACE_CLEAN", "CONTAMINATED", "directory_identity")
            return
        owner_st = os.stat(_OWNER, dir_fd=directory_fd, follow_symlinks=False)
        fifo_st = os.stat(_FIFO, dir_fd=directory_fd, follow_symlinks=False)
        if (
            identity(owner_st) != expected_owner
            or not stat.S_ISREG(owner_st.st_mode)
            or stat.S_IMODE(owner_st.st_mode) != 0o600
            or identity(fifo_st) != expected_fifo
            or not stat.S_ISFIFO(fifo_st.st_mode)
            or stat.S_IMODE(fifo_st.st_mode) != 0o600
        ):
            emit("WORKSPACE_CLEAN", "CONTAMINATED", "member_identity")
            return
        owner_fd = os.open(
            _OWNER,
            os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
        try:
            raw_nonce = os.read(owner_fd, 34)
        finally:
            os.close(owner_fd)
        if raw_nonce != (nonce + "\n").encode("ascii"):
            emit("WORKSPACE_CLEAN", "CONTAMINATED", "owner_nonce")
            return
        names = {entry.name for entry in os.scandir(directory_fd)}
        if names != {_OWNER, _FIFO}:
            emit("WORKSPACE_CLEAN", "CONTAMINATED", "unexpected_member")
            return
        fifo_outcome, fifo_reason = quarantine_remove_member(
            directory_fd,
            _FIFO,
            expected_fifo,
            "fifo",
        )
        if fifo_outcome != "REMOVED":
            emit(
                "WORKSPACE_CLEAN",
                fifo_outcome,
                f"fifo_{fifo_reason}",
            )
            return
        owner_outcome, owner_reason = quarantine_remove_member(
            directory_fd,
            _OWNER,
            expected_owner,
            "owner",
        )
        if owner_outcome != "REMOVED":
            # FIFO removal is already committed. Report partial cleanup explicitly;
            # never claim CLEANED when owner restoration or removal did not finish.
            emit(
                "WORKSPACE_CLEAN",
                owner_outcome,
                f"owner_{owner_reason}_fifo_removed",
            )
            return
        os.close(directory_fd)
        directory_fd = -1
        os.rmdir(found_name, dir_fd=parent_fd)
        reason = "cleaned"
        try:
            old_st = os.stat(basename, dir_fd=parent_fd, follow_symlinks=False)
            if identity(old_st) != expected_directory:
                reason = "cleaned_replacement_preserved"
        except FileNotFoundError:
            pass
        emit("WORKSPACE_CLEAN", "CLEANED", reason)
    except OSError:
        emit("WORKSPACE_CLEAN", "ERROR", "infrastructure")
    finally:
        if directory_fd >= 0:
            os.close(directory_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    action = sys.argv[1]
    if action == "pid-read" and len(sys.argv) == 3:
        pid_read(sys.argv[2])
        return 0
    if action == "workspace-create" and len(sys.argv) == 3:
        workspace_create(sys.argv[2])
        return 0
    if action == "workspace-clean" and len(sys.argv) == 4:
        workspace_clean(sys.argv[2], sys.argv[3])
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
