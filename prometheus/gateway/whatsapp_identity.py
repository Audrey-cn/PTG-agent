from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from prometheus.config import get_prometheus_home

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class Identity:
    id: str
    phone_number: str
    created_at: float
    name: str = ""
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)


class WhatsAppIdentity:
    def __init__(self) -> None:
        self._identities: Dict[str, Identity] = {}
        self._lock = threading.Lock()
        self._load_from_disk()

    def _storage_path(self) -> Path:
        return get_prometheus_home() / "whatsapp_identities.json"

    def _load_from_disk(self) -> None:
        path = self._storage_path()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("identities", []):
                    identity = Identity(
                        id=item["id"],
                        phone_number=item["phone_number"],
                        created_at=item.get("created_at", time.time()),
                        name=item.get("name", ""),
                        status=item.get("status", "active"),
                        metadata=item.get("metadata", {}),
                    )
                    self._identities[identity.id] = identity
            except Exception:
                pass

    def _save_to_disk(self) -> None:
        path = self._storage_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "identities": [
                {
                    "id": i.id,
                    "phone_number": i.phone_number,
                    "created_at": i.created_at,
                    "name": i.name,
                    "status": i.status,
                    "metadata": i.metadata,
                }
                for i in self._identities.values()
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def create_identity(self, phone_number: str) -> Dict[str, Any]:
        with self._lock:
            identity_id = str(uuid.uuid4())
            identity = Identity(
                id=identity_id,
                phone_number=phone_number,
                created_at=time.time(),
            )
            self._identities[identity_id] = identity
            self._save_to_disk()
            return {
                "id": identity.id,
                "phone_number": identity.phone_number,
                "created_at": identity.created_at,
                "name": identity.name,
                "status": identity.status,
            }

    def get_identity(self, identity_id: str) -> Dict[str, Any] | None:
        with self._lock:
            identity = self._identities.get(identity_id)
            if identity:
                return {
                    "id": identity.id,
                    "phone_number": identity.phone_number,
                    "created_at": identity.created_at,
                    "name": identity.name,
                    "status": identity.status,
                    "metadata": identity.metadata.copy(),
                }
            return None

    def list_identities(self) -> list[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": i.id,
                    "phone_number": i.phone_number,
                    "created_at": i.created_at,
                    "name": i.name,
                    "status": i.status,
                }
                for i in self._identities.values()
            ]

    def delete_identity(self, identity_id: str) -> bool:
        with self._lock:
            if identity_id in self._identities:
                del self._identities[identity_id]
                self._save_to_disk()
                return True
            return False

    def update_identity(
        self,
        identity_id: str,
        name: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        with self._lock:
            identity = self._identities.get(identity_id)
            if not identity:
                return False
            if name is not None:
                identity.name = name
            if status is not None:
                identity.status = status
            if metadata is not None:
                identity.metadata.update(metadata)
            self._save_to_disk()
            return True
