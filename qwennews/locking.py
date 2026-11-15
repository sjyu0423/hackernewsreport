"""Single-instance run lock for orchestration (macOS-safe file lock)."""

from __future__ import annotations

import atexit
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix
    fcntl = None  # type: ignore[assignment]


class LockBusyError(RuntimeError):
    """Raised when another orchestration run holds the lock."""


@dataclass
class RunLock:
    """Exclusive advisory lock shared by hourly and daily orchestration."""

    path: Path
    _fh: object | None = None

    def acquire(self, *, blocking: bool = False, stale_seconds: int = 7200) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+", encoding="utf-8")
        if fcntl is None:
            # Best-effort fallback without fcntl
            if self.path.exists() and self.path.stat().st_size > 0:
                content = self.path.read_text(encoding="utf-8").strip()
                if content and _pid_alive(content.split("|", 1)[0]):
                    fh.close()
                    raise LockBusyError(f"Lock busy: {self.path}")
            self._fh = fh
            self._write_holder()
            atexit.register(self.release)
            return

        flags = fcntl.LOCK_EX
        if not blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(fh.fileno(), flags)
        except OSError as exc:
            # Stale lock recovery: if holder PID is dead, steal after age check
            fh.seek(0)
            raw = fh.read().strip()
            holder_pid = raw.split("|", 1)[0] if raw else ""
            age = time.time() - self.path.stat().st_mtime
            if holder_pid and not _pid_alive(holder_pid) and age > 30:
                logger.warning("Stealing stale lock from dead pid %s", holder_pid)
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc2:
                    fh.close()
                    raise LockBusyError(f"Lock busy: {self.path}") from exc2
            elif age > stale_seconds and not blocking:
                fh.close()
                raise LockBusyError(
                    f"Lock busy (possibly stale >{stale_seconds}s): {self.path}"
                ) from exc
            else:
                fh.close()
                raise LockBusyError(f"Lock busy: {self.path}") from exc

        self._fh = fh
        self._write_holder()
        atexit.register(self.release)

    def _write_holder(self) -> None:
        assert self._fh is not None
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(f"{os.getpid()}|{time.time():.3f}\n")
        self._fh.flush()

    def release(self) -> None:
        fh = self._fh
        if fh is None:
            return
        try:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            try:
                fh.close()
            except Exception:  # noqa: BLE001
                pass
            self._fh = None

    def __enter__(self) -> RunLock:
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


def _pid_alive(pid_text: str) -> bool:
    try:
        pid = int(pid_text)
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
