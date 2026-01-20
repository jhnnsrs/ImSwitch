"""
FastAPI application routes for the Experiment Processing API.

This module contains all the HTTP and WebSocket endpoints.
"""

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from .models import (
    Task,
    TaskStatus,
    TaskCreateRequest,
    ExperimentRequest,
    ProcessResult,
    StatusResponse,
    StateUpdateRequest,
    StateBatchUpdateRequest,
    StateResponse,
    ActionInfo,
    ActionExecuteRequest,
)
from .dependencies import (
    ConnectionManagerDep,
    EngineManagerDep,
    StateProxyDep,
    ActionRegistryDep,
)


# Create routers
status_router = APIRouter(tags=["Status"])
schema_router = APIRouter(prefix="/schema", tags=["Schema"])
tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])
process_router = APIRouter(tags=["Processing"])
ws_router = APIRouter(tags=["WebSocket"])
state_router = APIRouter(prefix="/state", tags=["State"])
actions_router = APIRouter(prefix="/actions", tags=["Actions"])


# Status endpoints
@status_router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Get API status."""
    return StatusResponse(status="ok", version="1.0.0")


# Schema endpoints
@schema_router.get("/request")
async def get_request_schema() -> dict:
    """Get JSON schema for ExperimentRequest."""
    return ExperimentRequest.model_json_schema()


@schema_router.get("/response")
async def get_response_schema() -> dict:
    """Get JSON schema for ProcessResult."""
    return ProcessResult.model_json_schema()


# Task endpoints
@tasks_router.post("", response_model=Task)
async def create_task(task_request: TaskCreateRequest, engine: EngineManagerDep) -> Task:
    """
    Schedule a new microscope task.

    Args:
        task_request: Task creation request
        engine: Injected EngineManager

    Returns:
        Scheduled task with ID and status
    """
    task = Task(
        name=task_request.name,
        action=task_request.action,
        parameters=task_request.parameters,
    )
    scheduled_task = await engine.schedule_task(task)
    return scheduled_task


@tasks_router.get("", response_model=List[Task])
async def list_tasks(engine: EngineManagerDep, status: Optional[TaskStatus] = None) -> List[Task]:
    """
    List all tasks, optionally filtered by status.

    Args:
        engine: Injected EngineManager
        status: Filter by task status

    Returns:
        List of tasks
    """
    return await engine.list_tasks(status)


@tasks_router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str, engine: EngineManagerDep) -> Task:
    """
    Get a specific task by ID.

    Args:
        task_id: Task ID
        engine: Injected EngineManager

    Returns:
        Task details
    """
    task = await engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@tasks_router.delete("/{task_id}")
async def cancel_task(task_id: str, engine: EngineManagerDep) -> dict:
    """
    Cancel a pending or running task.

    Args:
        task_id: Task ID
        engine: Injected EngineManager

    Returns:
        Success status
    """
    success = await engine.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")
    return {"success": True, "task_id": task_id}


# WebSocket endpoint
@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
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
            await websocket.receive_text()
            # Echo back for ping/pong
            await manager.send_personal_message(
                json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}),
                websocket,
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Process endpoint
@process_router.post("/process", response_model=ProcessResult)
async def process_experiment(
    experiment: ExperimentRequest, manager: ConnectionManagerDep
) -> ProcessResult:
    """
    Process experiment data.

    Args:
        experiment: Experiment request with name and parameters
        manager: Injected ConnectionManager

    Returns:
        ProcessResult with processed data
    """
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
        status="success",
        experiment_name=experiment.name,
        processed_data=processed_data,
    )

    # Broadcast processing complete
    await manager.broadcast(
        {
            "type": "processing_complete",
            "experiment_name": experiment.name,
            "result": result.model_dump(),
            "timestamp": datetime.now().isoformat(),
        }
    )

    return result


# State endpoints
@state_router.get("", response_model=StateResponse)
async def get_state(state_proxy: StateProxyDep, key: Optional[str] = None) -> StateResponse:
    """
    Get current state.

    Args:
        state_proxy: Injected StateProxy
        key: Optional key to get specific value (supports dot notation)

    Returns:
        StateResponse with current state
    """
    snapshot = await state_proxy.get_snapshot()
    if key:
        value = await state_proxy.get(key)
        return StateResponse(
            state={key: value}, version=snapshot.version, timestamp=snapshot.timestamp
        )
    return StateResponse(
        state=snapshot.state, version=snapshot.version, timestamp=snapshot.timestamp
    )


@state_router.put("", response_model=StateResponse)
async def update_state(request: StateUpdateRequest, state_proxy: StateProxyDep) -> StateResponse:
    """
    Update a single state value.

    Args:
        request: State update request
        state_proxy: Injected StateProxy

    Returns:
        Updated StateResponse
    """
    await state_proxy.set(request.key, request.value, immediate=request.immediate)
    snapshot = await state_proxy.get_snapshot()
    return StateResponse(
        state=snapshot.state, version=snapshot.version, timestamp=snapshot.timestamp
    )


@state_router.patch("", response_model=StateResponse)
async def batch_update_state(
    request: StateBatchUpdateRequest, state_proxy: StateProxyDep
) -> StateResponse:
    """
    Update multiple state values at once.

    Args:
        request: Batch update request
        state_proxy: Injected StateProxy

    Returns:
        Updated StateResponse
    """
    await state_proxy.set_many(request.updates, immediate=request.immediate)
    snapshot = await state_proxy.get_snapshot()
    return StateResponse(
        state=snapshot.state, version=snapshot.version, timestamp=snapshot.timestamp
    )


@state_router.delete("/{key:path}")
async def delete_state(key: str, state_proxy: StateProxyDep, immediate: bool = False) -> dict:
    """
    Delete a state key.

    Args:
        key: State key to delete (supports dot notation via path)
        state_proxy: Injected StateProxy
        immediate: If True, broadcast immediately

    Returns:
        Success status
    """
    success = await state_proxy.delete(key, immediate=immediate)
    if not success:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    return {"success": True, "deleted_key": key}


# Actions endpoints
@actions_router.get("", response_model=List[ActionInfo])
async def list_actions(registry: ActionRegistryDep, tag: Optional[str] = None) -> List[ActionInfo]:
    """
    List all registered actions.

    Args:
        registry: Injected ActionRegistry
        tag: Optional tag to filter by

    Returns:
        List of ActionInfo
    """
    if tag:
        actions = registry.get_actions_by_tag(tag)
    else:
        actions = registry.list_actions()

    return [
        ActionInfo(
            name=info.name,
            description=info.description,
            parameters_schema=info.parameters_schema,
            tags=list(info.tags),
        )
        for info in actions
    ]


@actions_router.get("/{action_name}", response_model=ActionInfo)
async def get_action(action_name: str, registry: ActionRegistryDep) -> ActionInfo:
    """
    Get details about a specific action.

    Args:
        action_name: Name of the action
        registry: Injected ActionRegistry

    Returns:
        ActionInfo for the action
    """
    info = registry.get(action_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")
    return ActionInfo(
        name=info.name,
        description=info.description,
        parameters_schema=info.parameters_schema,
        tags=list(info.tags),
    )


@actions_router.post("/{action_name}/execute")
async def execute_action(
    action_name: str, request: ActionExecuteRequest, registry: ActionRegistryDep
) -> dict:
    """
    Execute an action directly (not as a scheduled task).

    Args:
        action_name: Name of the action
        request: Execution request with parameters
        registry: Injected ActionRegistry

    Returns:
        Action result
    """
    if not registry.has(action_name):
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")

    try:
        result = await registry.execute(action_name, request.parameters)
        return {"success": True, "action": action_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
