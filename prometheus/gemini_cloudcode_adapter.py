from __future__ import annotations

from pathlib import Path
from typing import Any


class GeminiCloudCodeAdapter:
    def __init__(self, api_key: Optional[str] = None, project_id: Optional[str] = None):
        self._api_key = api_key
        self._project_id = project_id
        self._endpoint = "https://cloudcode.googleapis.com/v1"

    def complete(self, prompt: str, context: Optional[str] = None) -> str:
        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nTask:\n{prompt}"
        return self._call_api("complete", {"prompt": full_prompt})

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found", "path": file_path}
        content = path.read_text()
        return self._call_api(
            "analyze",
            {"file_path": file_path, "content": content},
        )

    def suggest_fixes(self, code: str) -> list[Dict[str, Any]]:
        result = self._call_api("suggestFixes", {"code": code})
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "fixes" in result:
            return result["fixes"]
        return []

    def _call_api(self, method: str, payload: Dict[str, Any]) -> Any:
        return {"method": method, "payload": payload, "status": "mock"}

    def set_endpoint(self, endpoint: str) -> None:
        self._endpoint = endpoint

    def get_endpoint(self) -> str:
        return self._endpoint
