from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Dict, List, Optional

from prometheus.config import get_prometheus_home


class GatewayAPIServer:
    def __init__(self):
        self._app = None
        self._server = None
        self._host = "127.0.0.1"
        self._port = 9091
        self._running = False
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._platforms: Dict[str, Dict[str, Any]] = {}
        self._message_handlers: List[Callable] = []
    
    def _create_app(self):
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
        
        app = FastAPI(title="Prometheus Gateway API", version="1.0.0")
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        class SendMessage(BaseModel):
            message: str
            session_id: Optional[str] = None
            platform: Optional[str] = None
        
        @app.get("/status")
        async def get_status():
            return {
                "status": "running" if self._running else "stopped",
                "host": self._host,
                "port": self._port,
                "sessions_count": len(self._sessions),
                "platforms_count": len(self._platforms)
            }
        
        @app.post("/send")
        async def send_message(msg: SendMessage):
            result = {"sent": True, "message": msg.message}
            for handler in self._message_handlers:
                try:
                    handler_result = handler(msg.message, msg.session_id, msg.platform)
                    if handler_result:
                        result["handler_result"] = handler_result
                except Exception:
                    pass
            return result
        
        @app.get("/sessions")
        async def list_sessions():
            return [
                {"id": sid, **data}
                for sid, data in self._sessions.items()
            ]
        
        @app.post("/sessions/{session_id}/close")
        async def close_session(session_id: str):
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            del self._sessions[session_id]
            return {"closed": True, "session_id": session_id}
        
        @app.get("/platforms")
        async def list_platforms():
            return [
                {"name": name, **data}
                for name, data in self._platforms.items()
            ]
        
        self._app = app
        return app
    
    def get_routes(self) -> List[Dict[str, Any]]:
        if not self._app:
            return []
        routes = []
        for route in self._app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods) if route.methods else []
                })
        return routes
    
    def start(self, host: str = "127.0.0.1", port: int = 9091):
        try:
            import uvicorn
        except ImportError:
            raise ImportError("uvicorn is required. Install with: pip install uvicorn fastapi")
        
        self._host = host
        self._port = port
        self._running = True
        self._create_app()
        
        config = uvicorn.Config(
            app=self._app,
            host=host,
            port=port,
            log_level="warning"
        )
        self._server = uvicorn.Server(config)
        
        def run():
            asyncio.run(self._server.serve())
        
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
    
    def stop(self):
        self._running = False
        if self._server:
            self._server.should_exit = True
    
    def register_session(self, session_id: str, metadata: Optional[Dict[str, Any]] = None):
        self._sessions[session_id] = metadata or {}
    
    def unregister_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
    
    def register_platform(self, name: str, config: Optional[Dict[str, Any]] = None):
        self._platforms[name] = config or {}
    
    def unregister_platform(self, name: str):
        if name in self._platforms:
            del self._platforms[name]
    
    def add_message_handler(self, handler: Callable):
        self._message_handlers.append(handler)
    
    def remove_message_handler(self, handler: Callable):
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)


gateway_api = GatewayAPIServer()
