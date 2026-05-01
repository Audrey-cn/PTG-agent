from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from prometheus.config import get_prometheus_home, PrometheusConfig


def _check_fastapi():
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        return True
    except ImportError:
        return False


def _create_app():
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    
    app = FastAPI(title="Prometheus Agent", version="1.0.0")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    class ConfigUpdate(BaseModel):
        key: str
        value: Any
    
    class ChatMessage(BaseModel):
        message: str
        session_id: Optional[str] = None
        stream: bool = False
    
    class ToolToggle(BaseModel):
        enabled: bool
    
    _config: Optional[PrometheusConfig] = None
    _sessions: Dict[str, Dict[str, Any]] = {}
    _active_websockets: List[WebSocket] = []
    
    def _get_config() -> PrometheusConfig:
        nonlocal _config
        if _config is None:
            _config = PrometheusConfig.load()
        return _config
    
    @app.get("/api/config")
    async def get_config():
        config = _get_config()
        return config.to_dict()
    
    @app.post("/api/config")
    async def update_config(update: ConfigUpdate):
        config = _get_config()
        config.set(update.key, update.value)
        config.save()
        return {"success": True, "key": update.key}
    
    @app.get("/api/models")
    async def list_models():
        config = _get_config()
        providers = config.get("providers", {})
        models = []
        for provider, data in providers.items():
            if isinstance(data, dict) and "models" in data:
                for model in data["models"]:
                    models.append({
                        "provider": provider,
                        "model": model,
                        "name": model
                    })
        return models
    
    @app.post("/api/chat")
    async def send_message(chat: ChatMessage):
        from prometheus.tools.registry import registry
        return {
            "response": "Message received",
            "session_id": chat.session_id or "default",
            "tools_available": len(registry.list_tools())
        }
    
    @app.get("/api/sessions")
    async def list_sessions():
        return [
            {"id": sid, "data": data}
            for sid, data in _sessions.items()
        ]
    
    @app.get("/api/tools")
    async def list_tools():
        from prometheus.tools.registry import registry
        tools = []
        for name in registry.list_tools():
            tool = registry.get(name)
            if tool:
                tools.append({
                    "name": name,
                    "toolset": tool.toolset,
                    "description": tool.description,
                    "emoji": tool.emoji
                })
        return tools
    
    @app.post("/api/tools/{name}/toggle")
    async def toggle_tool(name: str, toggle: ToolToggle):
        from prometheus.tools.registry import registry
        tool = registry.get(name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
        return {"name": name, "enabled": toggle.enabled}
    
    @app.get("/api/skills")
    async def list_skills():
        skills_dir = get_prometheus_home() / "skills"
        skills = []
        if skills_dir.exists():
            for skill_path in skills_dir.iterdir():
                if skill_path.is_dir():
                    skill_md = skill_path / "SKILL.md"
                    if skill_md.exists():
                        skills.append({
                            "name": skill_path.name,
                            "path": str(skill_path),
                            "has_skill_md": True
                        })
        return skills
    
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        await websocket.accept()
        _active_websockets.append(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    message = {"text": data}
                
                await websocket.send_json({
                    "type": "ack",
                    "message": "Received: " + message.get("text", str(message))
                })
        except WebSocketDisconnect:
            _active_websockets.remove(websocket)
    
    return app


def run_server(host: str = "127.0.0.1", port: int = 9119):
    if not _check_fastapi():
        raise ImportError("FastAPI and uvicorn are required. Install with: pip install fastapi uvicorn")
    
    import uvicorn
    app = _create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
