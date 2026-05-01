from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GeminiCloudCodeAdapter:
    def __init__(self, api_key: str | None = None, project_id: str | None = None):
        self._api_key = api_key
        self._project_id = project_id
        self._endpoint = "https://cloudcode.googleapis.com/v1"

    def complete(self, prompt: str, context: str | None = None) -> str:
        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nTask:\n{prompt}"
        return self._call_api("complete", {"prompt": full_prompt})

    def analyze_file(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found", "path": file_path}
        content = path.read_text()
        return self._call_api(
            "analyze",
            {"file_path": file_path, "content": content},
        )

    def suggest_fixes(self, code: str) -> list[dict[str, Any]]:
        result = self._call_api("suggestFixes", {"code": code})
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "fixes" in result:
            return result["fixes"]
        return []

    def _call_api(self, method: str, payload: dict[str, Any]) -> Any:
        return {"method": method, "payload": payload, "status": "mock"}

    def set_endpoint(self, endpoint: str) -> None:
        self._endpoint = endpoint

    def get_endpoint(self) -> str:
        return self._endpoint
