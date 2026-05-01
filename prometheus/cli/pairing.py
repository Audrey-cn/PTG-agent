from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Optional

from prometheus.config import get_prometheus_home


class DevicePairing:
    def __init__(self):
        self._devices_file = get_prometheus_home() / "paired_devices.json"
        self._pending_pairings: dict[str, dict] = {}
    
    def _load_devices(self) -> list[dict]:
        if self._devices_file.exists():
            try:
                with open(self._devices_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []
    
    def _save_devices(self, devices: list[dict]) -> None:
        self._devices_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._devices_file, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2)
    
    def start_pairing(self, device_name: str) -> str:
        code = secrets.token_hex(4).upper()
        self._pending_pairings[code] = {
            "device_name": device_name,
            "started_at": time.time(),
            "expires_at": time.time() + 300,
        }
        return code
    
    def complete_pairing(self, code: str) -> bool:
        if code not in self._pending_pairings:
            return False
        
        pairing = self._pending_pairings[code]
        
        if time.time() > pairing["expires_at"]:
            del self._pending_pairings[code]
            return False
        
        devices = self._load_devices()
        
        new_device = {
            "id": secrets.token_hex(8),
            "name": pairing["device_name"],
            "paired_at": time.time(),
            "last_seen": time.time(),
        }
        
        devices.append(new_device)
        self._save_devices(devices)
        
        del self._pending_pairings[code]
        
        return True
    
    def list_paired_devices(self) -> list[dict]:
        return self._load_devices()
    
    def unpair(self, device_id: str) -> bool:
        devices = self._load_devices()
        original_count = len(devices)
        devices = [d for d in devices if d.get("id") != device_id]
        
        if len(devices) < original_count:
            self._save_devices(devices)
            return True
        
        return False
    
    def get_device(self, device_id: str) -> Optional[dict]:
        devices = self._load_devices()
        for device in devices:
            if device.get("id") == device_id:
                return device
        return None
    
    def update_last_seen(self, device_id: str) -> bool:
        devices = self._load_devices()
        for device in devices:
            if device.get("id") == device_id:
                device["last_seen"] = time.time()
                self._save_devices(devices)
                return True
        return False
    
    def cleanup_expired_pairings(self) -> int:
        current_time = time.time()
        expired_codes = [
            code for code, pairing in self._pending_pairings.items()
            if current_time > pairing["expires_at"]
        ]
        
        for code in expired_codes:
            del self._pending_pairings[code]
        
        return len(expired_codes)
