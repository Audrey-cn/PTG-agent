"""SMS gateway adapter."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from prometheus.gateway.config import Platform, PlatformConfig
from prometheus.gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 160

CHECK_INTERVAL = 3

_ANDROID_SMS_CONTENT_URI = "content://sms"
_ANDROID_SMS_COLUMNS = [
    "_id",
    "address",
    "body",
    "date",
    "date_sent",
    "read",
    "type",
    "thread_id",
]

_ADB_LOCKFILE = Path("/tmp/adb-sms.lock")
_REPLY_TEMP_DIR = Path("/tmp/prometheus-sms")
_MAX_CACHED_IDS = 500

# ADB commands
_ADB_DEVICE_SERIAL_RE = re.compile(r"^([a-zA-Z0-9_-]+)\s+device\b")


def _run_adb(
    *args: str,
    timeout: float = 15.0,
    serial: str | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run an ADB command. ``serial`` can be a device serial or host:port."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


async def _run_adb_async(
    *args: str,
    timeout: float = 15.0,
    serial: str | None = None,
) -> tuple[int, str, str]:
    """Run an ADB command asynchronously and return (returncode, stdout, stderr)."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            proc.returncode,
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise


@dataclass
class _SMSEntry:
    id: int
    address: str
    body: str
    date_ms: int
    date_sent_ms: int
    read: bool
    msg_type: int
    thread_id: int


def _extract_sms_from_query_output(output: str) -> list[_SMSEntry]:
    """Parse output of Android content query --projection _id,address,body,...

    Output format per row:
        Row: 0 _id=42 address=+1234567890 body=Hello date=1700000000000 ...

    Values are URL-encoded (%XX for special chars including newlines).
    """
    entries: list[_SMSEntry] = []
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line.startswith("Row:"):
            continue
        fields: dict[str, str] = {}
        for match in re.finditer(r"(\w+)=([^\s]*)", line):
            fields[match.group(1)] = match.group(2)
        try:
            row_id = int(fields["_id"])
            address = fields.get("address", "").strip()
            body = fields.get("body", "")
            body = body.replace("%20", " ").replace("%25", "%")
            body = re.sub(r"%([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), body)
            date_ms = int(fields.get("date", "0"))
            date_sent_ms = int(fields.get("date_sent", "0"))
            read = fields.get("read", "1") == "1"
            msg_type = int(fields.get("type", "1"))
            thread_id = int(fields.get("thread_id", "0"))
            entries.append(
                _SMSEntry(
                    id=row_id,
                    address=address,
                    body=body,
                    date_ms=date_ms,
                    date_sent_ms=date_sent_ms,
                    read=read,
                    msg_type=msg_type,
                    thread_id=thread_id,
                )
            )
        except (KeyError, ValueError):
            continue
    return entries


def check_sms_requirements() -> bool:
    """Return True if adb is available."""
    try:
        result = subprocess.run(
            ["adb", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class SMSAdapter(BasePlatformAdapter):
    """SMS gateway adapter using ADB + Android Content Provider."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.SMS)

        self._serial: str = config.extra.get("device_serial", "") or os.getenv(
            "SMS_DEVICE_SERIAL", ""
        )
        self._skip_attachments: bool = config.extra.get("skip_attachments", False)

        self._seen_ids: set = set()
        self._seen_ids_max: int = _MAX_CACHED_IDS

        self._poll_task: asyncio.Task | None = None

        _REPLY_TEMP_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(
            "SMS adapter initialized (device: %s, skip_attachments: %s)",
            self._serial or "(auto)",
            self._skip_attachments,
        )

    # ------------------------------------------------------------------
    # Required overrides
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Verify ADB device is reachable."""
        try:
            if not self._serial:
                serial = await self._discover_device()
                if not serial:
                    return False
                self._serial = serial

            rc, out, err = await _run_adb_async(
                "shell",
                "echo",
                "connected",
                serial=self._serial,
                timeout=10,
            )
            if rc != 0 or "connected" not in out:
                logger.error("SMS: ADB device check failed: %s %s", out, err)
                return False

            logger.info("SMS: connected to device %s", self._serial)

            self._running = True
            self._poll_task = asyncio.create_task(self._poll_loop())
            return True
        except Exception as e:
            logger.error("SMS: connection failed: %s", e)
            return False

    async def disconnect(self) -> None:
        """Stop polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        logger.info("SMS: disconnected")

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        """Send an SMS via adb shell service call."""
        try:
            msg_id = await self._send_sms(chat_id, content)
            return SendResult(success=True, message_id=msg_id)
        except Exception as e:
            logger.error("SMS: send failed to %s: %s", chat_id, e)
            return SendResult(success=False, error=str(e))

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        return {
            "name": chat_id,
            "type": "dm",
            "chat_id": chat_id,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _discover_device(self) -> str | None:
        """Return the serial of the first connected ADB device."""
        try:
            rc, out, err = await _run_adb_async("devices")
            if rc != 0:
                logger.warning("SMS: adb devices failed: %s %s", out, err)
                return None
            for line in out.split("\n"):
                line = line.strip()
                if _ADB_DEVICE_SERIAL_RE.match(line):
                    return line.split()[0]
            logger.warning("SMS: no ADB devices found")
            return None
        except Exception as e:
            logger.warning("SMS: device discovery error: %s", e)
            return None

    async def _poll_loop(self) -> None:
        """Periodically check for new SMS messages."""
        while self._running:
            try:
                await self._check_inbox()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("SMS: poll error: %s", e)
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check_inbox(self) -> None:
        """Query Android SMS Content Provider for new messages."""
        columns = ",".join(_ANDROID_SMS_COLUMNS)
        uri = _ANDROID_SMS_CONTENT_URI

        query_cmd = [
            "shell",
            "content",
            "query",
            "--uri",
            uri,
            "--projection",
            columns,
            "--sort",
            "_id DESC",
        ]

        rc, out, err = await _run_adb_async(
            *query_cmd,
            serial=self._serial,
            timeout=15,
        )
        if rc != 0:
            logger.warning("SMS: content query failed: %s %s", out, err)
            return

        entries = _extract_sms_from_query_output(out)
        for entry in reversed(entries):
            if entry.id in self._seen_ids:
                continue
            self._seen_ids.add(entry.id)
            if len(self._seen_ids) > self._seen_ids_max:
                trimmed = sorted(self._seen_ids)[: self._seen_ids_max // 2]
                self._seen_ids = set(trimmed)

            # Only process incoming messages (type == 1)
            if entry.msg_type != 1:
                continue

            # Skip self-sent messages
            # Use date_sent if available; fall back to date for pre-ICS
            ts_ms = entry.date_sent_ms or entry.date_ms
            if entry.address == "NULL" or not entry.address:
                continue

            timestamp = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)

            # Build message text
            text = entry.body.strip()
            if not text:
                continue

            source = self.build_source(
                chat_id=entry.address,
                chat_name=entry.address,
                chat_type="dm",
                user_id=entry.address,
                user_name=entry.address,
            )

            msg_event = MessageEvent(
                text=text,
                message_type=MessageType.TEXT,
                source=source,
                timestamp=timestamp,
                raw_message={"id": entry.id, "thread_id": entry.thread_id},
            )
            await self.handle_message(msg_event)

    async def _send_sms(self, address: str, text: str) -> str:
        """Send an SMS using Android service call via ADB."""
        import urllib.parse

        urllib.parse.quote(address)
        urllib.parse.quote(text)

        escaped_text = text.replace("'", "'\"'\"'")
        escaped_addr = address.replace("'", "'\"'\"'")

        n = (len(text) + 50) // 51

        service_call = (
            "service call isms 5 i32 0 s16 com.android.shell.SMS",
            f"split({n})",
            f"s16 '{escaped_addr}'",
            f"s16 '{escaped_text}'",
        )
        cmd = " ".join(service_call)

        rc, out, err = await _run_adb_async(
            "shell",
            cmd,
            serial=self._serial,
            timeout=30,
        )
        if rc != 0:
            raise RuntimeError(f"service call failed: {err or out}")

        logger.info("SMS: sent to %s", address)
        return str(int(time.time() * 1000))
