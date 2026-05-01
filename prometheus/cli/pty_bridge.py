from __future__ import annotations

import contextlib
import os
import select
import signal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess


class PTYBridge:
    def __init__(self):
        self._master_fd: int | None = None
        self._slave_fd: int | None = None
        self._process: subprocess.Popen | None = None
        self._pid: int | None = None

    def spawn(self, command: str, args: List[str] | None = None) -> int:
        if os.name == "nt":
            return self._spawn_winpty(command, args)
        return self._spawn_unix(command, args)

    def _spawn_unix(self, command: str, args: List[str] | None = None) -> int:
        import pty

        self._master_fd, self._slave_fd = pty.openpty()

        cmd = [command]
        if args:
            cmd.extend(args)

        self._pid = os.fork()

        if self._pid == 0:
            os.setsid()
            os.dup2(self._slave_fd, 0)
            os.dup2(self._slave_fd, 1)
            os.dup2(self._slave_fd, 2)
            os.close(self._master_fd)
            os.close(self._slave_fd)
            try:
                os.execvp(command, cmd)
            except Exception:
                os._exit(1)
        else:
            os.close(self._slave_fd)
            self._slave_fd = None
            return self._pid

    def _spawn_winpty(self, command: str, args: List[str] | None = None) -> int:
        try:
            import winpty
        except ImportError:
            raise RuntimeError("winpty is required on Windows. Install with: pip install winpty")

        cmd = [command]
        if args:
            cmd.extend(args)

        self._process = winpty.PTY(cols=80, rows=24)
        self._process.spawn(cmd)
        return self._process.pid

    def send_input(self, data: str | bytes) -> None:
        if isinstance(data, str):
            data = data.encode()

        if os.name == "nt":
            if self._process:
                self._process.write(data.decode())
        else:
            if self._master_fd is not None:
                os.write(self._master_fd, data)

    def read_output(self, timeout: float = 0.1) -> str:
        if os.name == "nt":
            if self._process:
                return self._process.read()
            return ""

        if self._master_fd is None:
            return ""

        output = b""
        while True:
            ready, _, _ = select.select([self._master_fd], [], [], timeout)
            if not ready:
                break
            try:
                chunk = os.read(self._master_fd, 4096)
                if not chunk:
                    break
                output += chunk
            except OSError:
                break

        return output.decode(errors="replace")

    def resize(self, rows: int, cols: int) -> None:
        if os.name == "nt":
            if self._process:
                self._process.set_size(cols, rows)
        else:
            if self._master_fd is not None:
                import fcntl
                import struct
                import termios

                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)

    def kill(self) -> None:
        if os.name == "nt":
            if self._process:
                self._process.close()
                self._process = None
        else:
            if self._pid:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(self._pid, signal.SIGTERM)
                self._pid = None

            if self._master_fd is not None:
                os.close(self._master_fd)
                self._master_fd = None

            if self._slave_fd is not None:
                os.close(self._slave_fd)
                self._slave_fd = None

    def is_alive(self) -> bool:
        if os.name == "nt":
            return self._process is not None and self._process.isalive()

        if self._pid is None:
            return False

        try:
            os.kill(self._pid, 0)
            return True
        except ProcessLookupError:
            return False
