"""FastAPI REST and WebSocket Telemetry Server for Shanto Download Manager.
Runs on 127.0.0.1:48912.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..core.manager import DownloadManager
from ..core.models import TaskCategory
from ..core.stream_extractor import StreamExtractor

app = FastAPI(title="Shanto Download Manager API", version="1.0.0")

# Enable CORS for browser extensions and external UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global manager instance
manager = DownloadManager()

# WebSocket active client pool
active_connections: List[WebSocket] = []


def ws_broadcast(msg: Dict[str, Any]) -> None:
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    if loop and loop.is_running():
        for ws in list(active_connections):
            asyncio.create_task(_send_ws(ws, msg))


async def _send_ws(ws: WebSocket, msg: Dict[str, Any]) -> None:
    try:
        await ws.send_json(msg)
    except Exception:
        if ws in active_connections:
            active_connections.remove(ws)


manager.add_subscriber(ws_broadcast)


# Request schemas
class AddTaskRequest(BaseModel):
    url: str
    filename: Optional[str] = None
    category: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    auto_start: bool = True
    speed_limit_kbps: int = 0


class ExtractRequest(BaseModel):
    url: str


class SpeedLimitRequest(BaseModel):
    limit_kbps: int


# REST Endpoints
@app.get("/api/tasks")
async def list_tasks():
    return {"tasks": manager.get_all_tasks()}


@app.post("/api/tasks")
async def add_task(req: AddTaskRequest):
    cat = None
    if req.category:
        try:
            cat = TaskCategory(req.category)
        except ValueError:
            cat = TaskCategory.OTHER

    task = await manager.add_task(
        url=req.url,
        filename=req.filename,
        category=cat,
        headers=req.headers,
        auto_start=req.auto_start,
        speed_limit_kbps=req.speed_limit_kbps,
    )
    return {"status": "ok", "task": task.to_dict()}


@app.post("/api/tasks/{task_id}/start")
async def start_task(task_id: str):
    success = await manager.start_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    success = await manager.pause_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, delete_file: bool = False):
    success = await manager.delete_task(task_id, delete_file=delete_file)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@app.post("/api/extract")
async def extract_media(req: ExtractRequest):
    try:
        info = await StreamExtractor.extract_info(req.url)
        return {"status": "ok", "info": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/settings/speed-limit")
async def set_speed_limit(req: SpeedLimitRequest):
    manager.set_global_speed_limit(req.limit_kbps)
    return {"status": "ok", "limit_kbps": req.limit_kbps}


# WebSocket telemetry stream
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_connections.append(ws)
    # Send initial full state dump
    await ws.send_json({"event": "initial_state", "tasks": manager.get_all_tasks()})
    try:
        while True:
            data = await ws.receive_json()
            # Client can send commands over WS
            action = data.get("action")
            task_id = data.get("task_id")
            if action == "start" and task_id:
                await manager.start_task(task_id)
            elif action == "pause" and task_id:
                await manager.pause_task(task_id)
            elif action == "delete" and task_id:
                await manager.delete_task(task_id, delete_file=data.get("delete_file", False))
    except (WebSocketDisconnect, Exception):
        if ws in active_connections:
            active_connections.remove(ws)


# Serve Static UI
web_dir = Path(__file__).resolve().parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(web_dir / "index.html"))
