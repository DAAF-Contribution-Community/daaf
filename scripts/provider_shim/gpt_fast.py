#!/usr/bin/env python3
"""Strict persistent GPT service-tier policy and operator CLI.

The production policy path is fixed at
``~/.claude/provider_shim/gpt_fast_policy.json``.  Callers may inject an
explicit home directory through :class:`PolicyStore` for hermetic tests; there
is deliberately no production state-path environment variable.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

POLICY_VERSION = 1
SUPPORTED_BACKENDS = frozenset({"chatgpt", "openai"})
# Both exact GPT backends use the one canonical OpenAI Responses request value.
# ChatGPT presents it as Fast; OpenAI API presents it as Priority.
REQUEST_TIERS = {"chatgpt": "priority", "openai": "priority"}
MAX_STATE_BYTES = 256
STATE_FILENAME = "gpt_fast_policy.json"
LOCK_FILENAME = "gpt_fast_policy.lock"
HEALTH_SERVICE_ID = "daaf-anthropic-openai-shim"
HEALTH_TIMEOUT_SECONDS = 0.6
HEALTH_BODY_LIMIT = 16_384
REQUEST_SOURCES = frozenset({"none", "anthropic", "shim_global", "both"})
# Exact served `fast` is compatibility-only terminal parser vocabulary; it is never
# valid requested vocabulary or emitted by DAAF.
SERVED_TIERS = frozenset({"fast", "priority", "default", "flex", "scale", "auto"})
UTC_SECOND_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
LOOPBACK_HEALTH_RE = re.compile(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})/health")


class PolicyError(RuntimeError):
    """A bounded, user-safe policy operation failure."""


class PolicyDurabilityUncertain(PolicyError):
    """Atomic publication is visible, but directory durability is unconfirmed."""

    def __init__(self, backend_mode: str, enabled: bool) -> None:
        super().__init__(
            "the requested policy state is visible, but directory durability "
            "could not be confirmed"
        )
        self.backend_mode = backend_mode
        self.enabled = enabled


class _DuplicateKeyError(ValueError):
    pass


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Reject loopback health redirects rather than following their Location."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class PolicySnapshot:
    """One strict persisted-policy observation.

    ``enabled`` is the persisted boolean only when the state is valid.  A
    non-``ok`` status always has ``enabled=False`` and ``backend_mode=None``.
    ``effective`` additionally requires an exact match to the requested lane.
    """

    status: str
    backend_mode: Optional[str]
    enabled: bool
    effective: bool

    def health_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "backend_mode": self.backend_mode,
            "enabled": self.enabled,
            "effective": self.effective,
        }


@dataclass(frozen=True)
class NormalizationResult:
    status: str
    changed: bool
    snapshot: PolicySnapshot


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError("duplicate key")
        result[key] = value
    return result


def _strict_policy_object(raw: bytes) -> Optional[dict[str, Any]]:
    try:
        text = raw.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, ValueError, TypeError, _DuplicateKeyError):
        return None
    if not isinstance(value, dict):
        return None
    if set(value) != {"version", "backend_mode", "enabled"}:
        return None
    version = value.get("version")
    backend_mode = value.get("backend_mode")
    enabled = value.get("enabled")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        return None
    if type(backend_mode) is not str or backend_mode not in SUPPORTED_BACKENDS:
        return None
    if type(enabled) is not bool:
        return None
    return value


def _mode_bits(metadata: os.stat_result) -> int:
    return stat.S_IMODE(metadata.st_mode)


def _safe_parent_directory_metadata(metadata: os.stat_result) -> bool:
    return (
        stat.S_ISDIR(metadata.st_mode)
        and metadata.st_uid == os.getuid()
        and (_mode_bits(metadata) & 0o022) == 0
    )


def _safe_directory_metadata(metadata: os.stat_result) -> bool:
    return (
        _safe_parent_directory_metadata(metadata)
        and _mode_bits(metadata) == 0o700
    )


def _safe_file_metadata(metadata: os.stat_result) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_uid == os.getuid()
        and _mode_bits(metadata) == 0o600
        and metadata.st_nlink == 1
    )


class PolicyStore:
    """Lock-free strict reader plus serialized atomic writer."""

    def __init__(
        self,
        home: Optional[os.PathLike[str] | str] = None,
        *,
        fsync: Callable[[int], None] = os.fsync,
        replace: Callable[..., None] = os.replace,
    ) -> None:
        # Capture the home once.  Shim requests must not be redirected by a later
        # environment mutation, and production has no path override variable.
        resolved_home = Path(home) if home is not None else Path.home()
        self.home = resolved_home.expanduser().absolute()
        self.claude_dir = self.home / ".claude"
        self.state_dir = self.claude_dir / "provider_shim"
        self.state_path = self.state_dir / STATE_FILENAME
        self.lock_path = self.state_dir / LOCK_FILENAME
        self._fsync = fsync
        self._replace = replace

    def _open_safe_home(self) -> tuple[Optional[int], str]:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            before = os.lstat(self.home)
            home_fd = os.open(self.home, flags)
        except FileNotFoundError:
            return None, "missing"
        except PermissionError:
            return None, "unreadable"
        except OSError:
            return None, "unsafe"
        try:
            opened = os.fstat(home_fd)
            if (
                not _safe_parent_directory_metadata(opened)
                or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                os.close(home_fd)
                return None, "unsafe"
        except Exception:
            os.close(home_fd)
            return None, "unreadable"
        return home_fd, "ok"

    def _open_safe_directory(self) -> tuple[Optional[int], str]:
        # Traverse every security-relevant component by descriptor. O_NOFOLLOW on
        # each open forbids a symlink at HOME, .claude, or provider_shim, and no
        # validated pathname is reopened later.
        home_fd, status = self._open_safe_home()
        if home_fd is None:
            return None, status
        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            try:
                claude_fd = os.open(".claude", flags, dir_fd=home_fd)
            except FileNotFoundError:
                return None, "missing"
            except PermissionError:
                return None, "unreadable"
            except OSError:
                return None, "unsafe"
            try:
                if not _safe_parent_directory_metadata(os.fstat(claude_fd)):
                    return None, "unsafe"
                try:
                    directory_fd = os.open(
                        "provider_shim", flags, dir_fd=claude_fd
                    )
                except FileNotFoundError:
                    return None, "missing"
                except PermissionError:
                    return None, "unreadable"
                except OSError:
                    return None, "unsafe"
                try:
                    if not _safe_directory_metadata(os.fstat(directory_fd)):
                        os.close(directory_fd)
                        return None, "unsafe"
                except Exception:
                    os.close(directory_fd)
                    return None, "unreadable"
                return directory_fd, "ok"
            finally:
                os.close(claude_fd)
        finally:
            os.close(home_fd)

    def _read_from_open_directory(self, directory_fd: int, backend_mode: Optional[str]) -> PolicySnapshot:
        flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(STATE_FILENAME, flags, dir_fd=directory_fd)
        except FileNotFoundError:
            return PolicySnapshot("missing", None, False, False)
        except PermissionError:
            return PolicySnapshot("unreadable", None, False, False)
        except OSError:
            return PolicySnapshot("unsafe", None, False, False)
        try:
            metadata = os.fstat(fd)
            if not _safe_file_metadata(metadata):
                return PolicySnapshot("unsafe", None, False, False)
            if metadata.st_size > MAX_STATE_BYTES:
                return PolicySnapshot("invalid", None, False, False)
            raw = b""
            while len(raw) <= MAX_STATE_BYTES:
                chunk = os.read(fd, MAX_STATE_BYTES + 1 - len(raw))
                if not chunk:
                    break
                raw += chunk
            if len(raw) > MAX_STATE_BYTES:
                return PolicySnapshot("invalid", None, False, False)
        except PermissionError:
            return PolicySnapshot("unreadable", None, False, False)
        except OSError:
            return PolicySnapshot("unreadable", None, False, False)
        finally:
            os.close(fd)
        policy = _strict_policy_object(raw)
        if policy is None:
            return PolicySnapshot("invalid", None, False, False)
        bound_backend = policy["backend_mode"]
        enabled = policy["enabled"]
        effective = bool(enabled and backend_mode == bound_backend)
        return PolicySnapshot("ok", bound_backend, enabled, effective)

    def read(self, backend_mode: Optional[str] = None) -> PolicySnapshot:
        directory_fd, status = self._open_safe_directory()
        if directory_fd is None:
            return PolicySnapshot(status, None, False, False)
        try:
            return self._read_from_open_directory(directory_fd, backend_mode)
        finally:
            os.close(directory_fd)

    def _open_or_create_claude_parent(self) -> int:
        # Anchor creation at the captured HOME directory descriptor. Path-based
        # lstat-then-mkdir would permit a rename/symlink swap between validation and
        # creation of provider_shim. Every descendant operation below remains relative
        # to the opened, identity-checked descriptor.
        home_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            home_before = os.lstat(self.home)
            home_fd = os.open(self.home, home_flags)
        except OSError as error:
            raise PolicyError("cannot open the policy home directory safely") from error
        try:
            home_opened = os.fstat(home_fd)
            if (
                not _safe_parent_directory_metadata(home_opened)
                or (home_before.st_dev, home_before.st_ino)
                != (home_opened.st_dev, home_opened.st_ino)
            ):
                raise PolicyError("the policy home directory is unsafe")
            try:
                os.mkdir(".claude", 0o700, dir_fd=home_fd)
            except FileExistsError:
                pass
            except OSError as error:
                raise PolicyError(
                    "cannot create the private policy parent directory"
                ) from error
            claude_fd = os.open(".claude", home_flags, dir_fd=home_fd)
            try:
                if not _safe_parent_directory_metadata(os.fstat(claude_fd)):
                    raise PolicyError("the policy parent directory is unsafe")
            except Exception:
                os.close(claude_fd)
                raise
            return claude_fd
        except PolicyError:
            raise
        except OSError as error:
            raise PolicyError("cannot inspect the policy parent directory") from error
        finally:
            os.close(home_fd)

    def _ensure_private_directory(self) -> int:
        claude_fd = self._open_or_create_claude_parent()
        try:
            try:
                os.mkdir("provider_shim", 0o700, dir_fd=claude_fd)
            except FileExistsError:
                pass
            except OSError as error:
                raise PolicyError("cannot create the private policy directory") from error
            flags = (
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                directory_fd = os.open("provider_shim", flags, dir_fd=claude_fd)
            except OSError as error:
                raise PolicyError("cannot open the private policy directory") from error
            try:
                if not _safe_directory_metadata(os.fstat(directory_fd)):
                    raise PolicyError("the policy directory is unsafe")
            except Exception:
                os.close(directory_fd)
                raise
            return directory_fd
        finally:
            os.close(claude_fd)

    def _open_writer_lock(self, directory_fd: int) -> int:
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_NONBLOCK
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            lock_fd = os.open(LOCK_FILENAME, flags, 0o600, dir_fd=directory_fd)
        except OSError as error:
            raise PolicyError("cannot open the private policy writer lock") from error
        try:
            if not _safe_file_metadata(os.fstat(lock_fd)):
                raise PolicyError("the policy writer lock is unsafe")
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            if not _safe_file_metadata(os.fstat(lock_fd)):
                raise PolicyError("the policy writer lock became unsafe")
            return lock_fd
        except PolicyError:
            os.close(lock_fd)
            raise
        except OSError as error:
            os.close(lock_fd)
            raise PolicyError("cannot acquire the private policy writer lock") from error

    def _validate_replace_target(self, directory_fd: int) -> None:
        flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(STATE_FILENAME, flags, dir_fd=directory_fd)
        except FileNotFoundError:
            return
        except OSError as error:
            raise PolicyError("the existing policy state is unsafe") from error
        try:
            if not _safe_file_metadata(os.fstat(fd)):
                raise PolicyError("the existing policy state is unsafe")
        finally:
            os.close(fd)

    def _publish_locked(self, directory_fd: int, backend_mode: str, enabled: bool) -> None:
        self._validate_replace_target(directory_fd)
        payload = json.dumps(
            {"version": POLICY_VERSION, "backend_mode": backend_mode, "enabled": enabled},
            separators=(",", ":"),
            sort_keys=False,
        ).encode("utf-8")
        if len(payload) > MAX_STATE_BYTES:
            raise PolicyError("internal policy serialization exceeded its size bound")
        temp_name: Optional[str] = None
        try:
            # Create by directory descriptor, not a pathname traversal. The random
            # O_EXCL sibling is unique in exactly the opened/validated filesystem.
            for _attempt in range(8):
                candidate = f".gpt_fast_policy.{os.urandom(16).hex()}.tmp"
                try:
                    temp_fd = os.open(
                        candidate,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                        0o600,
                        dir_fd=directory_fd,
                    )
                    temp_name = candidate
                    break
                except FileExistsError:
                    continue
            else:
                raise PolicyError("could not allocate a unique policy temporary file")
            try:
                os.fchmod(temp_fd, 0o600)
                if not _safe_file_metadata(os.fstat(temp_fd)):
                    raise PolicyError("the policy temporary file is unsafe")
                with os.fdopen(temp_fd, "wb", closefd=True) as handle:
                    handle.write(payload)
                    handle.flush()
                    self._fsync(handle.fileno())
            except Exception:
                try:
                    os.close(temp_fd)
                except OSError:
                    pass
                raise
            # Re-check after the complete temp write so an unsafe pre-existing
            # target is never silently replaced. Both source and destination are
            # resolved relative to the same validated open directory descriptor.
            self._validate_replace_target(directory_fd)
            self._replace(
                temp_name,
                STATE_FILENAME,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            # os.replace() is the atomic visibility/commit point. Once it returns,
            # the destination already names the new complete state and the temporary
            # name no longer exists. A later directory-fsync failure is therefore not
            # a publication rollback and must be reported distinctly.
            temp_name = None
            try:
                self._fsync(directory_fd)
            except OSError as error:
                raise PolicyDurabilityUncertain(backend_mode, enabled) from error
        except PolicyError:
            raise
        except OSError as error:
            raise PolicyError("could not publish the policy atomically") from error
        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name, dir_fd=directory_fd)
                except OSError:
                    pass

    def write(self, backend_mode: str, enabled: bool) -> PolicySnapshot:
        if backend_mode not in SUPPORTED_BACKENDS:
            raise PolicyError("backend mode must be exactly chatgpt or openai")
        if type(enabled) is not bool:
            raise PolicyError("enabled must be a real boolean")
        directory_fd = self._ensure_private_directory()
        lock_fd: Optional[int] = None
        try:
            lock_fd = self._open_writer_lock(directory_fd)
            self._publish_locked(directory_fd, backend_mode, enabled)
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)
            os.close(directory_fd)
        return self.read(backend_mode)

    def normalize_backend(
        self,
        backend_mode: str,
        *,
        route_boundary_valid: bool = True,
        native_fast_disabled: bool = True,
    ) -> NormalizationResult:
        """Atomically reconcile route binding and global-policy boundaries.

        A valid other-route policy is reset to OFF for this route. A valid
        current-route ON policy is also reset when either the complete exact GPT
        provider/backend pair or the exact native-Fast disable boundary is absent.
        Missing/invalid/unsafe state remains effective OFF and is not replaced.
        The shared writer lock gives the operation compare-and-set semantics:
        whichever writer acquires the lock first publishes first, and the later
        operation re-observes that complete result. ``route_boundary_valid``
        defaults true so existing CLI/controller callers retain their exact-route
        behavior; the shim passes its separately computed raw-pair boundary.
        """

        if backend_mode not in SUPPORTED_BACKENDS:
            return NormalizationResult(
                "invalid_backend", False, PolicySnapshot("invalid", None, False, False)
            )
        try:
            directory_fd = self._ensure_private_directory()
            lock_fd: Optional[int] = None
            try:
                lock_fd = self._open_writer_lock(directory_fd)
                current = self._read_from_open_directory(directory_fd, backend_mode)
                route_changed = (
                    current.status == "ok" and current.backend_mode != backend_mode
                )
                current_route_on = (
                    current.status == "ok"
                    and current.backend_mode == backend_mode
                    and current.enabled
                )
                route_boundary_missing = (
                    current_route_on and route_boundary_valid is not True
                )
                native_boundary_missing = (
                    current_route_on and native_fast_disabled is not True
                )
                if route_changed or route_boundary_missing or native_boundary_missing:
                    self._publish_locked(directory_fd, backend_mode, False)
                    current = PolicySnapshot("ok", backend_mode, False, False)
                    if route_changed:
                        status = "reset"
                    elif route_boundary_missing:
                        status = "reset_route_boundary"
                    else:
                        status = "reset_native_boundary"
                    return NormalizationResult(status, True, current)
                return NormalizationResult(current.status, False, current)
            finally:
                if lock_fd is not None:
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    finally:
                        os.close(lock_fd)
                os.close(directory_fd)
        except PolicyDurabilityUncertain:
            # Publication crossed os.replace(): the reconciled state is visible even
            # though crash-durability could not be confirmed. Preserve that distinction
            # for startup diagnostics instead of misclassifying it as an unchanged read.
            snapshot = self.read(backend_mode)
            return NormalizationResult("durability_uncertain", True, snapshot)
        except PolicyError:
            snapshot = self.read(backend_mode)
            return NormalizationResult(snapshot.status, False, snapshot)


def resolve_exact_route(environment: Optional[dict[str, str]] = None) -> str:
    env = os.environ if environment is None else environment
    if env.get("DAAF_PROVIDER_SHIM") != "openai":
        raise PolicyError("DAAF_PROVIDER_SHIM must be exactly 'openai'")
    backend_mode = env.get("SHIM_BACKEND_MODE")
    if backend_mode not in SUPPORTED_BACKENDS:
        raise PolicyError("SHIM_BACKEND_MODE must be exactly 'chatgpt' or 'openai'")
    return backend_mode


def native_fast_is_disabled(environment: Optional[dict[str, str]] = None) -> bool:
    """Return true only for the exact supported native-Fast disable boundary."""

    env = os.environ if environment is None else environment
    return env.get("CLAUDE_CODE_DISABLE_FAST_MODE") == "1"


def _bounded_model(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value or len(value) > 160:
        return None
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        return None
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._/:")
    if any(character not in allowed for character in value):
        return None
    return value


def _configured_model(environment: dict[str, str]) -> tuple[Optional[str], Optional[str]]:
    for name in (
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "CLAUDE_CODE_SUBAGENT_MODEL",
    ):
        model = _bounded_model(environment.get(name))
        if model is not None:
            return model, name
    return None, None


def _canonical_utc_second(value: Any) -> bool:
    if not isinstance(value, str) or UTC_SECOND_RE.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, ValueError):
        return False
    return True


def _valid_latest_terminal(value: Any, backend: str) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "model",
        "requested_service_tier",
        "requested_source",
        "served_service_tier",
        "completed_at",
    }:
        return False
    model = value.get("model")
    if model is not None and _bounded_model(model) is None:
        return False
    requested = value.get("requested_service_tier")
    source = value.get("requested_source")
    served = value.get("served_service_tier")
    if requested is not None and requested != REQUEST_TIERS[backend]:
        return False
    if type(source) is not str or source not in REQUEST_SOURCES:
        return False
    if (source == "none") is not (requested is None):
        return False
    if served is not None and (
        type(served) is not str or served not in SERVED_TIERS
    ):
        return False
    return _canonical_utc_second(value.get("completed_at"))


def _bounded_health(url: str) -> Optional[dict[str, Any]]:
    target = LOOPBACK_HEALTH_RE.fullmatch(url)
    if target is None or int(target.group(1)) > 65_535:
        return None
    try:
        request = urllib.request.Request(url, method="GET")
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _RejectRedirects()
        )
        with opener.open(request, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return None
            raw = response.read(HEALTH_BODY_LIMIT + 1)
            if len(raw) > HEALTH_BODY_LIMIT:
                return None
        payload = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (
        OSError,
        ValueError,
        UnicodeDecodeError,
        _DuplicateKeyError,
        urllib.error.URLError,
    ):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("service") != HEALTH_SERVICE_ID:
        return None
    if _bounded_model(payload.get("version")) is None:
        return None
    if payload.get("backend_mode") not in SUPPORTED_BACKENDS:
        return None
    block = payload.get("gpt_service_tier")
    if not isinstance(block, dict):
        return None
    if set(block) != {
        "backend_mode",
        "requested_tier_vocabulary",
        "policy",
        "native_fast_disabled",
        "latest_terminal",
    }:
        return None
    backend = block.get("backend_mode")
    if backend not in SUPPORTED_BACKENDS or backend != payload.get("backend_mode"):
        return None
    if block.get("requested_tier_vocabulary") != REQUEST_TIERS[backend]:
        return None
    if type(block.get("native_fast_disabled")) is not bool:
        return None
    policy = block.get("policy")
    if not isinstance(policy, dict) or set(policy) != {
        "status", "backend_mode", "enabled", "effective"
    }:
        return None
    policy_status = policy.get("status")
    policy_backend = policy.get("backend_mode")
    policy_enabled = policy.get("enabled")
    policy_effective = policy.get("effective")
    if type(policy_status) is not str or policy_status not in {
        "ok", "missing", "invalid", "unreadable", "unsafe"
    }:
        return None
    if policy_backend is not None and (
        type(policy_backend) is not str or policy_backend not in SUPPORTED_BACKENDS
    ):
        return None
    if type(policy_enabled) is not bool or type(policy_effective) is not bool:
        return None
    if policy_status != "ok" and (
        policy_backend is not None or policy_enabled or policy_effective
    ):
        return None
    if policy_status == "ok" and policy_backend is None:
        return None
    if policy_effective and (not policy_enabled or policy_backend != backend):
        return None
    latest = block.get("latest_terminal")
    if latest is not None and not _valid_latest_terminal(latest, backend):
        return None
    # Return only the validated bounded projection consumed by status output. The
    # production health document also carries URLs and other unrelated fields; keeping
    # them out of this object prevents accidental future reflection by the CLI.
    return {
        "service": HEALTH_SERVICE_ID,
        "version": payload["version"],
        "backend_mode": payload["backend_mode"],
        "gpt_service_tier": {
            "backend_mode": backend,
            "requested_tier_vocabulary": block["requested_tier_vocabulary"],
            "policy": dict(policy),
            "native_fast_disabled": block["native_fast_disabled"],
            "latest_terminal": dict(latest) if latest is not None else None,
        },
    }


def _display_route(backend_mode: str) -> str:
    return "ChatGPT subscription" if backend_mode == "chatgpt" else "OpenAI API"


def _display_tier(backend_mode: str) -> str:
    return "Fast" if backend_mode == "chatgpt" else "Priority"


def _status_lines(
    store: PolicyStore,
    backend_mode: str,
    environment: dict[str, str],
) -> list[str]:
    snapshot = store.read(backend_mode)
    native_fast_disabled = native_fast_is_disabled(environment)
    effective = bool(snapshot.effective and native_fast_disabled)
    tier_label = _display_tier(backend_mode)
    tier_value = REQUEST_TIERS[backend_mode]
    tier_semantics = (
        "friendly ChatGPT Fast label; ChatGPT plan/credit semantics, not API Priority billing"
        if backend_mode == "chatgpt"
        else "OpenAI API Priority label; API Priority billing/cost semantics"
    )
    model, model_source = _configured_model(environment)
    port = environment.get("SHIM_PORT", "4141")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        port = "4141"
    health = _bounded_health(f"http://127.0.0.1:{port}/health")
    lines = [
        f"Route: {_display_route(backend_mode)} ({backend_mode})",
        "Scope: shim-wide; applies to newly accepted /v1/messages requests.",
        (
            f"Requested service vocabulary: {tier_label} ({tier_semantics}; "
            f"canonical wire service_tier={tier_value!r})."
        ),
        (
            f"Persisted requested policy: "
            f"{'ON' if snapshot.status == 'ok' and snapshot.enabled else 'OFF'} "
            f"(state={snapshot.status}, bound_backend={snapshot.backend_mode or 'unknown'})."
        ),
        (
            f"Effective requested policy: {'ON' if effective else 'OFF'} "
            "(requires persisted ON, exact route binding, and exact "
            "CLAUDE_CODE_DISABLE_FAST_MODE=1)."
        ),
        (
            "Native Claude Code Fast disabled: yes"
            if native_fast_disabled
            else "Native Claude Code Fast disabled: no (exact CLAUDE_CODE_DISABLE_FAST_MODE=1 is absent)."
        ),
    ]
    if model is None:
        lines.append("Configured model: unknown (no bounded model mapping found in environment).")
    else:
        lines.append(f"Configured model: {model} (from {model_source}).")
    if health is None or health.get("backend_mode") != backend_mode:
        lines.append("Shim: unavailable or identity/schema mismatch.")
        lines.append("Latest terminal: unknown.")
    else:
        lines.append(
            f"Shim: available, version={health.get('version', 'unknown')}, backend={health.get('backend_mode')}."
        )
        latest = health["gpt_service_tier"]["latest_terminal"]
        if latest is None:
            lines.append("Latest terminal: unknown (no completed upstream terminal in this process).")
        else:
            lines.append(
                "Latest terminal: model={model}; requested={requested}; source={source}; "
                "served={served}; completed_at={completed}.".format(
                    model=latest.get("model") or "unknown",
                    requested=latest.get("requested_service_tier") or "none",
                    source=latest.get("requested_source"),
                    served=latest.get("served_service_tier") or "unknown",
                    completed=latest.get("completed_at"),
                )
            )
    lines.append(
        f"Caution: requested {tier_label} service is not proof that the provider served {tier_label} service."
    )
    return lines


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gpt_fast.py",
        description="Control the shim-wide route-bound GPT service-tier request policy.",
    )
    parser.add_argument("command", choices=("on", "off", "status"))
    return parser


def main(argv: Optional[list[str]] = None, *, store: Optional[PolicyStore] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    environment = os.environ
    try:
        backend_mode = resolve_exact_route(environment)
    except PolicyError as error:
        print(f"ERROR: {error}.", file=sys.stderr)
        print("  Fix: run this command only inside an exact DAAF GPT provider-shim route.", file=sys.stderr)
        return 20
    policy_store = store or PolicyStore()
    tier_label = _display_tier(backend_mode)
    tier_value = REQUEST_TIERS[backend_mode]

    if args.command == "on":
        if not native_fast_is_disabled(environment):
            print(
                "ERROR: 'on' requires exact CLAUDE_CODE_DISABLE_FAST_MODE=1.",
                file=sys.stderr,
            )
            print(
                "  Fix: disable Claude Code native Fast mode for the GPT shim route before opting in.",
                file=sys.stderr,
            )
            return 20
        if backend_mode == "openai":
            print(
                "WARNING: OpenAI API Priority Processing can change API cost and depends on account/model eligibility.",
                file=sys.stderr,
            )
        try:
            snapshot = policy_store.write(backend_mode, True)
        except PolicyDurabilityUncertain:
            print(
                "ERROR: requested policy ON is visible, but durability is uncertain "
                "because the policy directory could not be synchronized.",
                file=sys.stderr,
            )
            print(
                "  The committed destination was not rolled back; inspect status and "
                "repair storage before retrying.",
                file=sys.stderr,
            )
            return 1
        except PolicyError as error:
            print(f"ERROR: could not enable the policy: {error}.", file=sys.stderr)
            print("  Fix: repair the private policy directory/state permissions, then retry.", file=sys.stderr)
            return 1
        if not snapshot.effective:
            print("ERROR: the enabled policy could not be verified safely.", file=sys.stderr)
            return 1
        print(
            f"Requested {tier_label} service is ON for all newly accepted shim requests "
            f"on {_display_route(backend_mode)} (service_tier={tier_value!r})."
        )
        print(f"Requested {tier_label} service is not proof that the provider served it.")
        return 0

    if args.command == "off":
        try:
            snapshot = policy_store.write(backend_mode, False)
        except PolicyDurabilityUncertain:
            print(
                "ERROR: requested policy OFF is visible, but durability is uncertain "
                "because the policy directory could not be synchronized.",
                file=sys.stderr,
            )
            print(
                "  The committed destination was not rolled back; inspect status and "
                "repair storage before retrying.",
                file=sys.stderr,
            )
            return 1
        except PolicyError as error:
            print(f"ERROR: could not disable the policy: {error}.", file=sys.stderr)
            print("  Fix: repair the private policy directory/state permissions, then retry.", file=sys.stderr)
            return 1
        if snapshot.status != "ok" or snapshot.enabled:
            print("ERROR: the disabled policy could not be verified safely.", file=sys.stderr)
            return 1
        print(
            f"Requested {tier_label} service is OFF for all newly accepted shim requests "
            f"on {_display_route(backend_mode)}; service_tier will be omitted unless valid inbound Anthropic Fast requests it."
        )
        return 0

    for line in _status_lines(policy_store, backend_mode, environment):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
