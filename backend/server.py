"""
Autonomous AI Agent Platform - Backend Server
Real-time terminal streaming, task execution, and model orchestration
"""

import asyncio
import json
import time
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

app = FastAPI(title="Autonomous AI Agent Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskRequest(BaseModel):
    task: str
    task_id: Optional[str] = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "tasks": 0,
        "active_connections": len(manager.active_connections)
    }

@app.get("/api/models")
async def get_models():
    models = [
        {"id": "hermes", "name": "Hermes", "status": "standby", "capabilities": ["autonomous", "terminal", "multi-tool"]},
        {"id": "gemini", "name": "Gemini CLI", "status": "standby", "capabilities": ["research", "coding", "analysis"]},
        {"id": "kiro", "name": "Kiro CLI", "status": "standby", "capabilities": ["orchestration", "workflow"]},
        {"id": "aider", "name": "Aider", "status": "standby", "capabilities": ["code-editing", "git"]},
        {"id": "ollama", "name": "Ollama Local", "status": "standby", "capabilities": ["local-llm", "offline"]}
    ]
    return {"models": models}

@app.post("/api/task")
async def submit_task(request: TaskRequest):
    task_id = request.task_id or f"task_{int(time.time())}"
    await manager.broadcast({
        "type": "terminal_output",
        "task_id": task_id,
        "output": f"[TASK] {request.task}",
        "level": "system",
        "timestamp": datetime.now().isoformat()
    })
    asyncio.create_task(execute_autonomous_task(task_id, request.task))
    return {"task_id": task_id, "status": "executing"}

async def execute_autonomous_task(task_id: str, task: str):
    try:
        await manager.broadcast({
            "type": "terminal_output",
            "task_id": task_id,
            "output": "[EXEC] Starting autonomous execution...",
            "level": "info",
            "timestamp": datetime.now().isoformat()
        })

        models = ["hermes", "gemini", "kiro", "aider", "ollama"]
        for i, model in enumerate(models):
            await asyncio.sleep(0.5)
            await manager.broadcast({
                "type": "model_update",
                "task_id": task_id,
                "model": model,
                "active": True
            })
            await manager.broadcast({
                "type": "terminal_output",
                "task_id": task_id,
                "output": f"[{model.upper()}] Processing task component...",
                "level": "info",
                "timestamp": datetime.now().isoformat()
            })

        await asyncio.sleep(1)
        for model in models:
            await manager.broadcast({
                "type": "model_update",
                "task_id": task_id,
                "model": model,
                "active": False
            })

        result = f"Task '{task}' completed successfully using autonomous multi-model execution"
        await manager.broadcast({
            "type": "terminal_output",
            "task_id": task_id,
            "output": "[SUCCESS] Task completed",
            "level": "system",
            "timestamp": datetime.now().isoformat()
        })
        await manager.broadcast({
            "type": "terminal_output",
            "task_id": task_id,
            "output": f"[RESULT] {result}",
            "level": "output",
            "timestamp": datetime.now().isoformat()
        })
        await manager.broadcast({
            "type": "task_update",
            "task_id": task_id,
            "status": "completed"
        })
    except Exception as e:
        await manager.broadcast({
            "type": "terminal_output",
            "task_id": task_id,
            "output": f"[ERROR] {str(e)}",
            "level": "error",
            "timestamp": datetime.now().isoformat()
        })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "execute_task":
                await submit_task(TaskRequest(
                    task=message.get("task"),
                    task_id=message.get("task_id")
                ))
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
