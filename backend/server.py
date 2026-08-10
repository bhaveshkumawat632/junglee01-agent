"""
Autonomous AI Agent Platform - Backend Server v2
Real-time terminal streaming, ReAct execution, multi-model orchestration,
StateGraph-style task state management, self-evaluation, and AgentTool pattern.
"""

import asyncio
import json
import time
import uuid
import subprocess
import shutil
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Autonomous AI Agent Platform v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────
class TaskStatus(str, Enum):
    PENDING = "pending"
    REASONING = "reasoning"
    ACTING = "acting"
    OBSERVING = "observing"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class TaskRequest(BaseModel):
    task: str
    task_id: Optional[str] = None

class Step(BaseModel):
    step_id: str
    thought: str
    action: str
    observation: str
    status: TaskStatus
    timestamp: str
    metadata: Dict[str, Any] = {}

@dataclass
class TaskState:
    task_id: str
    original_task: str
    status: TaskStatus = TaskStatus.PENDING
    steps: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[str] = None
    score: float = 0.0
    model_used: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)

# ──────────────────────────────────────────────
# Model registry with capabilities
# ──────────────────────────────────────────────
MODELS = {
    "hermes": {
        "name": "Hermes",
        "capabilities": ["autonomous", "terminal", "multi-tool", "reasoning"],
        "cost": "low",
        "speed": "fast",
    },
    "gemini": {
        "name": "Gemini CLI",
        "capabilities": ["research", "coding", "analysis", "grounding"],
        "cost": "low",
        "speed": "fast",
    },
    "kiro": {
        "name": "Kiro CLI",
        "capabilities": ["orchestration", "workflow", "planning"],
        "cost": "low",
        "speed": "fast",
    },
    "aider": {
        "name": "Aider",
        "capabilities": ["code-editing", "git", "refactoring"],
        "cost": "low",
        "speed": "fast",
    },
    "ollama": {
        "name": "Ollama Local",
        "capabilities": ["local-llm", "offline", "privacy"],
        "cost": "free",
        "speed": "medium",
    },
}

# ──────────────────────────────────────────────
# ReAct engine
# ──────────────────────────────────────────────
class ReActEngine:
    """Reason + Act + Observe loop with self-evaluation."""

    def __init__(self, broadcast: Callable):
        self.broadcast = broadcast
        self.max_steps = 5
        self.thought_patterns = [
            "I need to break this down into steps",
            "Let me analyze the requirements",
            "I should check what tools are available",
            "This requires a systematic approach",
            "Let me think about the best strategy",
        ]

    async def reason(self, task: str, context: Dict) -> tuple[str, str]:
        """Generate thought and action for current step."""
        step_num = len(context.get("steps", [])) + 1

        # Simulated reasoning patterns based on task content
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["code", "program", "script", "build"]):
            thought = f"Step {step_num}: This is a coding task. I'll write clean, efficient code following best practices."
            action = "Write implementation with proper error handling and documentation"
        elif any(kw in task_lower for kw in ["research", "find", "search", "analyze"]):
            thought = f"Step {step_num}: This requires research. I'll search multiple sources and synthesize findings."
            action = "Search and analyze relevant information from available sources"
        elif any(kw in task_lower for kw in ["deploy", "setup", "install", "configure"]):
            thought = f"Step {step_num}: This is a deployment task. I'll verify prerequisites and execute step by step."
            action = "Check environment and execute deployment steps"
        else:
            thought = f"Step {step_num}: Analyzing task requirements and planning execution strategy."
            action = "Execute task with systematic approach and monitoring"

        return thought, action

    async def act(self, action: str, task: str) -> str:
        """Execute action and return observation."""
        # Simulate action execution with realistic output
        await asyncio.sleep(0.3)

        if "code" in action.lower():
            observation = f"✓ Code written and validated. Output: implementation complete with tests passing."
        elif "search" in action.lower() or "research" in action.lower():
            observation = f"✓ Research complete. Found 3 relevant sources with actionable insights."
        elif "deploy" in action.lower() or "setup" in action.lower():
            observation = f"✓ Deployment successful. Service running and health checks passing."
        else:
            observation = f"✓ Action executed successfully. Result: task progressed as planned."

        return observation

    async def evaluate(self, task: str, steps: List[Dict]) -> tuple[float, str]:
        """Self-evaluate task execution quality."""
        if not steps:
            return 0.0, "No steps executed"

        # Scoring based on step count and completeness
        base_score = min(len(steps) * 0.25, 1.0)
        completeness = sum(1 for s in steps if s.get("observation", "").startswith("✓"))
        completeness_ratio = completeness / len(steps) if steps else 0

        final_score = (base_score * 0.6) + (completeness_ratio * 0.4)

        if final_score >= 0.8:
            verdict = "EXCELLENT - Task completed with high quality"
        elif final_score >= 0.6:
            verdict = "GOOD - Task completed satisfactorily"
        elif final_score >= 0.4:
            verdict = "PARTIAL - Task partially completed, may need retry"
        else:
            verdict = "POOR - Task failed or incomplete, retry recommended"

        return final_score, verdict

    async def execute(self, task_state: TaskState) -> TaskState:
        """Run full ReAct loop on a task."""
        task_state.status = TaskStatus.REASONING
        await self.broadcast({
            "type": "terminal_output",
            "task_id": task_state.task_id,
            "output": f"[REACT] Starting reasoning loop for: {task_state.original_task[:60]}...",
            "level": "system",
            "timestamp": datetime.now().isoformat()
        })

        for step_num in range(1, self.max_steps + 1):
            # Reason
            task_state.status = TaskStatus.REASONING
            thought, action = await self.reason(task_state.original_task, task_state.context)

            await self.broadcast({
                "type": "terminal_output",
                "task_id": task_state.task_id,
                "output": f"[REASON] {thought}",
                "level": "info",
                "timestamp": datetime.now().isoformat()
            })

            # Act
            task_state.status = TaskStatus.ACTING
            await self.broadcast({
                "type": "terminal_output",
                "task_id": task_state.task_id,
                "output": f"[ACTION] {action}",
                "level": "info",
                "timestamp": datetime.now().isoformat()
            })

            observation = await self.act(action, task_state.original_task)

            # Observe
            task_state.status = TaskStatus.OBSERVING
            step = {
                "step_id": f"step_{step_num}",
                "thought": thought,
                "action": action,
                "observation": observation,
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
            }
            task_state.steps.append(step)

            await self.broadcast({
                "type": "terminal_output",
                "task_id": task_state.task_id,
                "output": f"[OBSERVE] {observation}",
                "level": "output",
                "timestamp": datetime.now().isoformat()
            })

            # Check if task is complete
            if "complete" in observation.lower() or "successful" in observation.lower():
                break

        # Evaluate
        task_state.status = TaskStatus.EVALUATING
        score, verdict = await self.evaluate(task_state.original_task, task_state.steps)
        task_state.score = score
        task_state.result = verdict

        await self.broadcast({
            "type": "terminal_output",
            "task_id": task_state.task_id,
            "output": f"[EVALUATE] Score: {score:.2f} — {verdict}",
            "level": "system",
            "timestamp": datetime.now().isoformat()
        })

        if score >= 0.6:
            task_state.status = TaskStatus.COMPLETED
        else:
            task_state.status = TaskStatus.FAILED

        return task_state

# ──────────────────────────────────────────────
# AgentTool pattern
# ──────────────────────────────────────────────
class AgentTool:
    """Wrap a subagent/skill as a callable tool."""

    def __init__(self, name: str, description: str, handler: Callable):
        self.name = name
        self.description = description
        self.handler = handler

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute tool and return result."""
        try:
            result = await self.handler(**kwargs)
            return {"tool": self.name, "success": True, "result": result}
        except Exception as e:
            return {"tool": self.name, "success": False, "error": str(e)}

# ──────────────────────────────────────────────
# Task orchestrator
# ──────────────────────────────────────────────
class TaskOrchestrator:
    """Orchestrates multi-model task execution with retry logic."""

    def __init__(self, broadcast: Callable):
        self.broadcast = broadcast
        self.react_engine = ReActEngine(broadcast)
        self.tools: Dict[str, AgentTool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register built-in tools."""
        self.tools["terminal"] = AgentTool(
            "terminal",
            "Execute shell commands",
            self._execute_terminal
        )
        self.tools["file_read"] = AgentTool(
            "file_read",
            "Read file contents",
            self._read_file
        )
        self.tools["web_search"] = AgentTool(
            "web_search",
            "Search the web",
            self._web_search
        )

    async def _execute_terminal(self, command: str, timeout: int = 30) -> str:
        """Execute terminal command safely."""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=timeout
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""
            return output + error
        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error: {str(e)}"

    async def _read_file(self, path: str) -> str:
        """Read file contents."""
        try:
            with open(path, "r") as f:
                return f.read()[:5000]  # Limit to 5KB
        except Exception as e:
            return f"Error reading file: {str(e)}"

    async def _web_search(self, query: str) -> str:
        """Web search placeholder."""
        return f"Web search results for: {query}"

    def select_model(self, task: str) -> str:
        """Select best model for task based on capabilities."""
        task_lower = task.lower()
        scores = {}
        for model_id, info in MODELS.items():
            score = 0
            for cap in info["capabilities"]:
                if cap in task_lower:
                    score += 1
            scores[model_id] = score

        if scores:
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                return best
        return "hermes"  # Default

    async def execute_with_retry(self, task_state: TaskState) -> TaskState:
        """Execute task with self-healing retry logic."""
        while task_state.retry_count < task_state.max_retries:
            try:
                # Select model
                model = self.select_model(task_state.original_task)
                task_state.model_used = model
                task_state.context["selected_model"] = model

                await self.broadcast({
                    "type": "model_update",
                    "task_id": task_state.task_id,
                    "model": model,
                    "active": True
                })

                # Execute ReAct loop
                task_state = await self.react_engine.execute(task_state)

                # Self-evaluate
                if task_state.score >= 0.6:
                    break
                else:
                    task_state.retry_count += 1
                    task_state.status = TaskStatus.RETRYING
                    await self.broadcast({
                        "type": "terminal_output",
                        "task_id": task_state.task_id,
                        "output": f"[RETRY] Attempt {task_state.retry_count}/{task_state.max_retries} - Score {task_state.score:.2f} too low, retrying...",
                        "level": "warning",
                        "timestamp": datetime.now().isoformat()
                    })

            except Exception as e:
                task_state.retry_count += 1
                task_state.status = TaskStatus.RETRYING
                await self.broadcast({
                    "type": "terminal_output",
                    "task_id": task_state.task_id,
                    "output": f"[ERROR] {str(e)} - Retry {task_state.retry_count}/{task_state.max_retries}",
                    "level": "error",
                    "timestamp": datetime.now().isoformat()
                })

        if task_state.status not in [TaskStatus.COMPLETED]:
            task_state.status = TaskStatus.FAILED
            task_state.result = f"Failed after {task_state.retry_count} attempts"

        return task_state

# ──────────────────────────────────────────────
# Connection manager
# ──────────────────────────────────────────────
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
orchestrator = TaskOrchestrator(manager.broadcast)
task_store: Dict[str, TaskState] = {}

# ──────────────────────────────────────────────
# API endpoints
# ──────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "tasks": len(task_store),
        "active_connections": len(manager.active_connections),
        "patterns": ["ReAct", "StateGraph", "AgentTool", "Self-Eval", "Retry"]
    }

@app.get("/api/models")
async def get_models():
    return {"models": [
        {**v, "id": k} for k, v in MODELS.items()
    ]}

@app.get("/api/tasks")
async def list_tasks():
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "status": t.status.value,
                "score": t.score,
                "model": t.model_used,
                "steps": len(t.steps)
            }
            for t in task_store.values()
        ]
    }

@app.post("/api/task")
async def submit_task(request: TaskRequest):
    task_id = request.task_id or f"task_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    task_state = TaskState(
        task_id=task_id,
        original_task=request.task,
        status=TaskStatus.PENDING
    )
    task_store[task_id] = task_state

    await manager.broadcast({
        "type": "task_update",
        "task_id": task_id,
        "status": "pending"
    })

    asyncio.create_task(orchestrator.execute_with_retry(task_state))
    return {"task_id": task_id, "status": "executing"}

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
