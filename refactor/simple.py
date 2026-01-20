"""
Simple API for experiment processing.
"""

from typing import Dict, Any, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel, Field
import uvicorn
import json
from datetime import datetime
from contextlib import asynccontextmanager
import asyncio
from enum import Enum
from uuid import uuid4


class TaskStatus(str, Enum):
    """Status of a scheduled task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """Represents a scheduled microscope task."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Name of the task")
    action: str = Field(..., description="Microscope action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status")
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EngineManager:
    """Manages microscope engine tasks and scheduling."""

    def __init__(self, connection_manager: "ConnectionManager"):
        self.tasks: Dict[str, Task] = {}
        self.connection_manager = connection_manager
        self.is_running = False
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the engine manager worker."""
        if not self.is_running:
            self.is_running = True
            self._worker_task = asyncio.create_task(self._process_tasks())

    async def stop(self):
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
        await self.connection_manager.broadcast({
            "type": "task_scheduled",
            "task_id": task.id,
            "task_name": task.name,
            "action": task.action,
            "timestamp": datetime.now().isoformat()
        })
        
        return task

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                
                await self.connection_manager.broadcast({
                    "type": "task_cancelled",
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat()
                })
                
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

    async def _process_tasks(self):
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

    async def _execute_task(self, task: Task):
        """Execute a single task."""
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            await self.connection_manager.broadcast({
                "type": "task_started",
                "task_id": task.id,
                "task_name": task.name,
                "timestamp": datetime.now().isoformat()
            })
            
            # Simulate microscope action execution
            result = await self._perform_microscope_action(task.action, task.parameters)
            
            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            await self.connection_manager.broadcast({
                "type": "task_completed",
                "task_id": task.id,
                "task_name": task.name,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            # Task failed
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            
            await self.connection_manager.broadcast({
                "type": "task_failed",
                "task_id": task.id,
                "task_name": task.name,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

    async def _perform_microscope_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
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
                "resolution": parameters.get("resolution", [1024, 1024])
            }
        elif action == "move_stage":
            return {
                "position": parameters.get("position", [0, 0, 0]),
                "success": True
            }
        elif action == "adjust_focus":
            return {
                "focus_position": parameters.get("z_position", 0),
                "success": True
            }
        else:
            return {
                "action": action,
                "parameters": parameters,
                "executed": True
            }


# WebSocket Connection Manager
class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        await websocket.send_text(message)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected WebSockets."""
        message_str = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception:
                # Handle disconnected clients silently
                pass


# Input/Output Models
class ExperimentParameters(BaseModel):
    """Parameters for an experiment."""

    exposure_time: Optional[float] = Field(None, description="Exposure time in seconds")
    laser_power: Optional[float] = Field(None, description="Laser power in mW")
    num_frames: Optional[int] = Field(None, description="Number of frames to acquire")
    custom_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional parameters"
    )


class ExperimentRequest(BaseModel):
    """Request model for experiment processing."""

    name: str = Field(..., description="Name of the experiment", min_length=1)
    parameters: ExperimentParameters = Field(..., description="Experiment parameters")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "test_experiment",
                "parameters": {"exposure_time": 0.1, "laser_power": 50.0, "num_frames": 100},
            }
        }


class ProcessResult(BaseModel):
    """Result model for processed experiments."""

    status: str = Field(..., description="Processing status")
    experiment_name: str = Field(..., description="Name of the processed experiment")
    processed_data: Dict[str, Any] = Field(..., description="Processed experiment data")


class StatusResponse(BaseModel):
    """API status response."""

    status: str
    version: str = "1.0.0"


# Application setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - setup and teardown."""
    # Startup: Initialize managers
    app.state.manager = ConnectionManager()
    app.state.engine = EngineManager(app.state.manager)
    await app.state.engine.start()
    
    yield
    
    # Shutdown: cleanup
    await app.state.engine.stop()
    app.state.manager.active_connections.clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Experiment Processing API",
        description="Simple API for processing experimental data",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/status", response_model=StatusResponse)
    async def get_status():
        """Get API status."""
        return StatusResponse(status="ok", version="1.0.0")

    @app.get("/schema/request")
    async def get_request_schema():
        """Get JSON schema for ExperimentRequest."""
        return ExperimentRequest.model_json_schema()

    @app.get("/schema/response")
    async def get_response_schema():
        """Get JSON schema for ProcessResult."""
        return ProcessResult.model_json_schema()

    # Engine/Task Management Endpoints
    class TaskCreateRequest(BaseModel):
        """Request model for creating a task."""
        name: str = Field(..., description="Task name")
        action: str = Field(..., description="Microscope action")
        parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")

    @app.post("/tasks", response_model=Task)
    async def create_task(task_request: TaskCreateRequest, request: Request) -> Task:
        """
        Schedule a new microscope task.
        
        Args:
            task_request: Task creation request
            request: FastAPI request object
            
        Returns:
            Scheduled task with ID and status
        """
        engine = request.app.state.engine
        task = Task(
            name=task_request.name,
            action=task_request.action,
            parameters=task_request.parameters
        )
        scheduled_task = await engine.schedule_task(task)
        return scheduled_task

    @app.get("/tasks", response_model=List[Task])
    async def list_tasks(
        status: Optional[TaskStatus] = None,
        request: Request = None
    ) -> List[Task]:
        """
        List all tasks, optionally filtered by status.
        
        Args:
            status: Filter by task status
            request: FastAPI request object
            
        Returns:
            List of tasks
        """
        engine = request.app.state.engine
        return await engine.list_tasks(status)

    @app.get("/tasks/{task_id}", response_model=Task)
    async def get_task(task_id: str, request: Request):
        """
        Get a specific task by ID.
        
        Args:
            task_id: Task ID
            request: FastAPI request object
            
        Returns:
            Task details
        """
        engine = request.app.state.engine
        task = await engine.get_task(task_id)
        if not task:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.delete("/tasks/{task_id}")
    async def cancel_task(task_id: str, request: Request):
        """
        Cancel a pending or running task.
        
        Args:
            task_id: Task ID
            request: FastAPI request object
            
        Returns:
            Success status
        """
        engine = request.app.state.engine
        success = await engine.cancel_task(task_id)
        if not success:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Task cannot be cancelled")
        return {"success": True, "task_id": task_id}

    @app.websocket("/ws")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """
        WebSocket endpoint for real-time updates.

        Clients can connect to receive notifications about processing events.
        """
        manager = websocket.app.state.manager
        await manager.connect(websocket)
        try:
            # Send welcome message
            await manager.send_personal_message(
                json.dumps(
                    {
                        "type": "connection",
                        "message": "Connected to experiment processing updates",
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                websocket,
            )

            # Keep connection alive and listen for messages
            while True:
                data = await websocket.receive_text()
                # Echo back for ping/pong
                await manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}), websocket
                )
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    @app.post("/process", response_model=ProcessResult)
    async def process_experiment(experiment: ExperimentRequest, request: Request) -> ProcessResult:
        """
        Process experiment data.

        Args:
            experiment: Experiment request with name and parameters
            request: FastAPI request object

        Returns:
            ProcessResult with processed data
        """
        manager = request.app.state.manager

        # Broadcast processing start
        await manager.broadcast(
            {
                "type": "processing_start",
                "experiment_name": experiment.name,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Extract parameters
        params = experiment.parameters

        # Process parameters (example: double numeric values)
        processed_data = {}

        if params.exposure_time is not None:
            processed_data["exposure_time"] = params.exposure_time * 2
        if params.laser_power is not None:
            processed_data["laser_power"] = params.laser_power * 2
        if params.num_frames is not None:
            processed_data["num_frames"] = params.num_frames * 2

        # Process custom parameters
        for key, value in (params.custom_params or {}).items():
            # Check for bool first since bool is a subclass of int in Python
            if isinstance(value, bool):
                processed_data[f"custom_{key}"] = value
            elif isinstance(value, (int, float)):
                processed_data[f"custom_{key}"] = value * 2
            else:
                processed_data[f"custom_{key}"] = value

        result = ProcessResult(
            status="success", experiment_name=experiment.name, processed_data=processed_data
        )

        # Broadcast processing complete
        await request.app.state.manager.broadcast(
            {
                "type": "processing_complete",
                "experiment_name": experiment.name,
                "result": result.model_dump(),
                "timestamp": datetime.now().isoformat(),
            }
        )

        return result

    return app


# Main function with simple API
def main(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    Run the experiment processing API server.

    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload for development
    """
    app = create_app()
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    main(reload=True)
