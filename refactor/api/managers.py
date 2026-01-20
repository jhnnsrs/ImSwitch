"""
Manager classes for the Experiment Processing API.

This module contains the ConnectionManager for WebSocket connections
and the EngineManager for task scheduling and execution.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from fastapi import WebSocket

from .models import Task, TaskStatus


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a message to a specific WebSocket."""
        await websocket.send_text(message)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected WebSockets."""
        message_str = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception:
                # Handle disconnected clients silently
                pass


class EngineManager:
    """Manages microscope engine tasks and scheduling."""

    def __init__(self, connection_manager: ConnectionManager):
        self.tasks: Dict[str, Task] = {}
        self.connection_manager = connection_manager
        self.is_running = False
        self._task_queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        """Start the engine manager worker."""
        if not self.is_running:
            self.is_running = True
            self._worker_task = asyncio.create_task(self._process_tasks())

    async def stop(self) -> None:
        """Stop the engine manager worker."""
        self.is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def schedule_task(self, task: Task) -> Task:
        """Schedule a new task for execution."""
        self.tasks[task.id] = task
        await self._task_queue.put(task.id)

        # Broadcast task scheduled
        await self.connection_manager.broadcast(
            {
                "type": "task_scheduled",
                "task_id": task.id,
                "task_name": task.name,
                "action": task.action,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return task

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()

                await self.connection_manager.broadcast(
                    {
                        "type": "task_cancelled",
                        "task_id": task_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                return True
        return False

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.tasks.get(task_id)

    async def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        if status:
            return [t for t in self.tasks.values() if t.status == status]
        return list(self.tasks.values())

    async def _process_tasks(self) -> None:
        """Worker that processes tasks from the queue."""
        while self.is_running:
            try:
                task_id = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                task = self.tasks.get(task_id)

                if task and task.status == TaskStatus.PENDING:
                    await self._execute_task(task)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error in task worker: {e}")

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task."""
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

            await self.connection_manager.broadcast(
                {
                    "type": "task_started",
                    "task_id": task.id,
                    "task_name": task.name,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Simulate microscope action execution
            result = await self._perform_microscope_action(task.action, task.parameters)

            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result

            await self.connection_manager.broadcast(
                {
                    "type": "task_completed",
                    "task_id": task.id,
                    "task_name": task.name,
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            # Task failed
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)

            await self.connection_manager.broadcast(
                {
                    "type": "task_failed",
                    "task_id": task.id,
                    "task_name": task.name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )

    async def _perform_microscope_action(
        self, action: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform the actual microscope action.

        This is a placeholder - in a real implementation, this would interface
        with actual microscope hardware/software.
        """
        # Simulate some processing time
        await asyncio.sleep(0.5)

        # Mock different microscope actions
        if action == "capture_image":
            return {
                "image_id": str(uuid4()),
                "exposure_time": parameters.get("exposure_time", 0.1),
                "resolution": parameters.get("resolution", [1024, 1024]),
            }
        elif action == "move_stage":
            return {
                "position": parameters.get("position", [0, 0, 0]),
                "success": True,
            }
        elif action == "adjust_focus":
            return {
                "focus_position": parameters.get("z_position", 0),
                "success": True,
            }
        else:
            return {"action": action, "parameters": parameters, "executed": True}
