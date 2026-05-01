from __future__ import annotations

import logging
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("prometheus.pairing_manager")


@dataclass
class PairedDevice:
    id: str
    name: str
    device_type: str
    paired_at: float
    last_seen: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PairingRequest:
    id: str
    device_name: str
    device_type: str
    pairing_code: str
    created_at: float
    expires_at: float
    status: str = "pending"


class PairingManager:
    """设备配对管理器 - 管理多设备配对。

    支持生成配对码、接受/拒绝配对请求、列出已配对设备等功能。
    """

    _instance: PairingManager | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._devices: dict[str, PairedDevice] = {}
        self._pairing_requests: dict[str, PairingRequest] = {}
        self._pending_codes: dict[str, str] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> PairingManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def start_pairing(self, timeout: int = 60) -> str:
        """开始配对过程。

        Args:
            timeout: 超时时间（秒）

        Returns:
            配对码
        """
        with self._lock:
            pairing_code = secrets.token_hex(4).upper()
            request_id = str(uuid.uuid4())[:8]
            now = time.time()

            self._pairing_requests[request_id] = PairingRequest(
                id=request_id,
                device_name="Pending Device",
                device_type="unknown",
                pairing_code=pairing_code,
                created_at=now,
                expires_at=now + timeout,
            )
            self._pending_codes[pairing_code] = request_id

            logger.info(f"Started pairing with code: {pairing_code}")
            return pairing_code

    def accept_pairing(self, device_id: str, device_name: str = "Unknown Device") -> bool:
        """接受配对请求。

        Args:
            device_id: 设备ID
            device_name: 设备名称

        Returns:
            是否成功
        """
        with self._lock:
            if device_id not in self._pairing_requests:
                logger.warning(f"Pairing request not found: {device_id}")
                return False

            request = self._pairing_requests[device_id]
            if request.status != "pending":
                logger.warning(f"Pairing request not pending: {device_id}")
                return False

            if time.time() > request.expires_at:
                logger.warning(f"Pairing request expired: {device_id}")
                request.status = "expired"
                return False

            device = PairedDevice(
                id=device_id,
                name=device_name,
                device_type=request.device_type,
                paired_at=time.time(),
                last_seen=time.time(),
                metadata={},
            )
            self._devices[device_id] = device
            request.status = "accepted"

            logger.info(f"Accepted pairing for device: {device_name} ({device_id})")
            return True

    def reject_pairing(self, device_id: str) -> bool:
        """拒绝配对请求。

        Args:
            device_id: 设备ID

        Returns:
            是否成功
        """
        with self._lock:
            if device_id in self._pairing_requests:
                self._pairing_requests[device_id].status = "rejected"
                logger.info(f"Rejected pairing request: {device_id}")
                return True
            return False

    def list_devices(self) -> list[dict[str, Any]]:
        """列出所有已配对设备。"""
        with self._lock:
            now = time.time()
            devices = []
            for device in self._devices.values():
                time_since_seen = int(now - device.last_seen)
                devices.append(
                    {
                        "id": device.id,
                        "name": device.name,
                        "device_type": device.device_type,
                        "paired_at": device.paired_at,
                        "last_seen": f"{time_since_seen}s ago",
                        "online": time_since_seen < 300,
                    }
                )
            return devices

    def remove_device(self, device_id: str) -> bool:
        """移除配对设备。

        Args:
            device_id: 设备ID

        Returns:
            是否成功
        """
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                logger.info(f"Removed paired device: {device_id}")
                return True
            return False

    def get_device(self, device_id: str) -> PairedDevice | None:
        """获取设备信息。"""
        return self._devices.get(device_id)

    def update_last_seen(self, device_id: str) -> bool:
        """更新设备最后 seen 时间。"""
        with self._lock:
            if device_id in self._devices:
                self._devices[device_id].last_seen = time.time()
                return True
            return False

    def cleanup_expired_requests(self) -> int:
        """清理过期的配对请求。"""
        with self._lock:
            now = time.time()
            expired = []
            for req_id, request in self._pairing_requests.items():
                if now > request.expires_at and request.status == "pending":
                    request.status = "expired"
                    expired.append(req_id)
            return len(expired)


def get_pairing_manager() -> PairingManager:
    """获取PairingManager单例。"""
    return PairingManager.get_instance()
