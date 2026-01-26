"""
FastAPI application routes for the Experiment Processing API.

This module contains all the HTTP and WebSocket endpoints.
Uses rekuest_next's actor system for async action execution.
"""

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel, Field

from .models import (
    ExperimentRequest,
    ProcessResult,
    StatusResponse,
    StateUpdateRequest,
    StateBatchUpdateRequest,
    StateResponse,
)
from .dependencies import (
    ConnectionManagerDep,
    StateProxyDep,
    DefinitionRegistryDep,
    AgentDep,
)


# =============================================================================
# Response Models
# =============================================================================


class ActionDefinitionResponse(BaseModel):
    """Response model for action definition."""

    name: str = Field(..., description="Action name")
    description: str = Field(..., description="Action description")
    args: List[dict] = Field(default_factory=list, description="Input parameters")
    returns: List[dict] = Field(default_factory=list, description="Return values")
    is_generator: bool = Field(False, description="Whether action yields multiple results")
    collections: List[str] = Field(default_factory=list, description="Tags/categories")


class AssignRequest(BaseModel):
    """Request to assign (execute) an action."""

    args: dict = Field(default_factory=dict, description="Arguments for the action")
    reference: Optional[str] = Field(None, description="Client reference for tracking")


class AssignationResponse(BaseModel):
    """Response containing assignation information."""

    id: str = Field(..., description="Assignation ID")
    action: str = Field(..., description="Action being executed")
    status: str = Field(..., description="Current status")
    args: dict = Field(default_factory=dict, description="Input arguments")
    returns: Optional[dict] = Field(None, description="Return value(s)")
    yields: List[dict] = Field(default_factory=list, description="Yielded values")
    error: Optional[str] = Field(None, description="Error message if failed")
    progress: Optional[int] = Field(None, description="Progress 0-100")
    created_at: str = Field(..., description="Creation timestamp")
    started_at: Optional[str] = Field(None, description="Start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    reference: Optional[str] = Field(None, description="Client reference")


# =============================================================================
# Create Routers
# =============================================================================

status_router = APIRouter(tags=["Status"])
schema_router = APIRouter(prefix="/schema", tags=["Schema"])
process_router = APIRouter(tags=["Processing"])
ws_router = APIRouter(tags=["WebSocket"])
state_router = APIRouter(prefix="/state", tags=["State"])
actions_router = APIRouter(prefix="/actions", tags=["Actions"])
assignations_router = APIRouter(prefix="/assignations", tags=["Assignations"])


# =============================================================================
# Status Endpoints
# =============================================================================


@status_router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Get API status."""
    return StatusResponse(status="ok", version="2.0.0")


# =============================================================================
# Schema Endpoints
# =============================================================================


@schema_router.get("/request")
async def get_request_schema() -> dict:
    """Get JSON schema for ExperimentRequest."""
    return ExperimentRequest.model_json_schema()


@schema_router.get("/response")
async def get_response_schema() -> dict:
    """Get JSON schema for ProcessResult."""
    return ProcessResult.model_json_schema()


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time updates.

    Clients connect here to receive assignation events:
    - assignation_created: When an action is queued
    - assignation_assigned: When an actor accepts the work
    - assignation_progress: Progress updates
    - assignation_yield: Intermediate results (for generators)
    - assignation_done: Completion with results
    - assignation_error: Error occurred
    - assignation_cancelled: Cancelled by user
    """
    manager = websocket.app.state.manager
    await manager.connect(websocket)
    try:
        # Send welcome message
        await manager.send_personal_message(
            json.dumps(
                {
                    "type": "connection",
                    "message": "Connected to microscope control API",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            websocket,
        )

        # Keep connection alive and handle client messages
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Handle ping/pong
                if msg.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}),
                        websocket,
                    )
            except json.JSONDecodeError:
                # Simple text ping
                await manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}),
                    websocket,
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# =============================================================================
# Process Endpoint (Legacy)
# =============================================================================


@process_router.post("/process", response_model=ProcessResult)
async def process_experiment(
    experiment: ExperimentRequest, manager: ConnectionManagerDep
) -> ProcessResult:
    """
    Process experiment data (legacy endpoint).

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

    # Process parameters
    params = experiment.parameters
    processed_data = {}

    if params.exposure_time is not None:
        processed_data["exposure_time"] = params.exposure_time * 2
    if params.laser_power is not None:
        processed_data["laser_power"] = params.laser_power * 2
    if params.num_frames is not None:
        processed_data["num_frames"] = params.num_frames * 2

    for key, value in (params.custom_params or {}).items():
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

    # Broadcast completion
    await manager.broadcast(
        {
            "type": "processing_complete",
            "experiment_name": experiment.name,
            "result": result.model_dump(),
            "timestamp": datetime.now().isoformat(),
        }
    )

    return result


# =============================================================================
# State Endpoints
# =============================================================================


@state_router.get("", response_model=StateResponse)
async def get_state(state_proxy: StateProxyDep, key: Optional[str] = None) -> StateResponse:
    """Get current state."""
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
    """Update a single state value."""
    await state_proxy.set(request.key, request.value, immediate=request.immediate)
    snapshot = await state_proxy.get_snapshot()
    return StateResponse(
        state=snapshot.state, version=snapshot.version, timestamp=snapshot.timestamp
    )


@state_router.patch("", response_model=StateResponse)
async def batch_update_state(
    request: StateBatchUpdateRequest, state_proxy: StateProxyDep
) -> StateResponse:
    """Update multiple state values at once."""
    await state_proxy.set_many(request.updates, immediate=request.immediate)
    snapshot = await state_proxy.get_snapshot()
    return StateResponse(
        state=snapshot.state, version=snapshot.version, timestamp=snapshot.timestamp
    )


@state_router.delete("/{key:path}")
async def delete_state(key: str, state_proxy: StateProxyDep, immediate: bool = False) -> dict:
    """Delete a state key."""
    success = await state_proxy.delete(key, immediate=immediate)
    if not success:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    return {"success": True, "deleted_key": key}


# =============================================================================
# Actions Endpoints
# =============================================================================


@actions_router.get("", response_model=List[ActionDefinitionResponse])
async def list_actions(
    registry: DefinitionRegistryDep,
    collection: Optional[str] = None,
) -> List[ActionDefinitionResponse]:
    """
    List all registered actions.

    Args:
        registry: Injected DefinitionRegistry from rekuest_next
        collection: Optional collection/tag to filter by

    Returns:
        List of action definitions
    """
    result = []
    for interface, template in registry.implementations.items():
        defn = template.definition

        # Filter by collection if specified
        if collection and collection not in (defn.collections or []):
            continue

        result.append(
            ActionDefinitionResponse(
                name=interface,  # Use interface as name
                description=defn.description or "",
                args=[
                    {
                        "key": arg.key,
                        "kind": arg.kind.value if hasattr(arg.kind, "value") else str(arg.kind),
                        "description": arg.description or "",
                        "nullable": arg.nullable,
                        "default": arg.default,
                    }
                    for arg in defn.args
                ],
                returns=[
                    {
                        "key": ret.key,
                        "kind": ret.kind.value if hasattr(ret.kind, "value") else str(ret.kind),
                        "description": ret.description or "",
                    }
                    for ret in defn.returns
                ],
                is_generator=defn.kind.value == "GENERATOR"
                if hasattr(defn.kind, "value")
                else False,
                collections=list(defn.collections) if defn.collections else [],
            )
        )

    return result


@actions_router.get("/{action_name}", response_model=ActionDefinitionResponse)
async def get_action(action_name: str, registry: DefinitionRegistryDep) -> ActionDefinitionResponse:
    """
    Get details about a specific action.

    Args:
        action_name: Name/interface of the action
        registry: Injected DefinitionRegistry from rekuest_next

    Returns:
        Action definition
    """
    if action_name not in registry.templates:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")

    template = registry.templates[action_name]
    defn = template.definition

    return ActionDefinitionResponse(
        name=action_name,
        description=defn.description or "",
        args=[
            {
                "key": arg.key,
                "kind": arg.kind.value if hasattr(arg.kind, "value") else str(arg.kind),
                "description": arg.description or "",
                "nullable": arg.nullable,
                "default": arg.default,
            }
            for arg in defn.args
        ],
        returns=[
            {
                "key": ret.key,
                "kind": ret.kind.value if hasattr(ret.kind, "value") else str(ret.kind),
                "description": ret.description or "",
            }
            for ret in defn.returns
        ],
        is_generator=defn.kind.value == "GENERATOR" if hasattr(defn.kind, "value") else False,
        collections=list(defn.collections) if defn.collections else [],
    )


@actions_router.post("/{action_name}/assign", response_model=AssignationResponse)
async def assign_action(
    action_name: str,
    request: AssignRequest,
    agent: AgentDep,
) -> AssignationResponse:
    """
    Assign (execute) an action asynchronously.

    This returns immediately with an assignation ID. The actual execution
    happens asynchronously and results are delivered via WebSocket.

    Use GET /assignations/{id} to poll for status if WebSocket is unavailable.

    Args:
        action_name: Name of the action to execute
        request: Assignment request with arguments
        agent: Injected FastAPIAgent

    Returns:
        Assignation with ID for tracking

    WebSocket Events:
        - ProgressEvent: Progress updates
        - YieldEvent: Intermediate results (generators)
        - DoneEvent: Completion
        - ErrorEvent: On failure
    """
    if action_name not in agent.definition_registry.templates:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")

    try:
        assignation_id = await agent.assign(
            interface=action_name,
            args=request.args,
            reference=request.reference,
        )

        # Get the state we just created
        state = agent.get_assignation(assignation_id)

        return AssignationResponse(
            id=assignation_id,
            action=action_name,
            status=state.status if state else "pending",
            args=request.args,
            returns=state.returns if state else None,
            yields=[],  # Will be populated via WebSocket
            error=state.error if state else None,
            progress=state.progress if state else 0,
            created_at=state.created_at.isoformat() if state else datetime.utcnow().isoformat(),
            started_at=None,
            completed_at=None,
            reference=request.reference,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Assignations Endpoints (for polling status)
# =============================================================================


@assignations_router.get("", response_model=List[AssignationResponse])
async def list_assignations(
    agent: AgentDep,
    status: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> List[AssignationResponse]:
    """
    List assignations with optional filters.

    Args:
        agent: Injected FastAPIAgent
        status: Filter by status (pending, running, done, error, etc.)
        action: Filter by action name
        limit: Maximum number to return

    Returns:
        List of assignations
    """
    all_assignations = agent.get_all_assignations()

    # Apply filters
    filtered = []
    for state in all_assignations:
        if status and state.status != status:
            continue
        if action and state.interface != action:
            continue
        filtered.append(state)
        if len(filtered) >= limit:
            break

    return [
        AssignationResponse(
            id=state.id,
            action=state.interface,
            status=state.status,
            args=state.args,
            returns=state.returns,
            yields=[],  # Could be populated from events
            error=state.error,
            progress=state.progress,
            created_at=state.created_at.isoformat(),
            started_at=None,
            completed_at=state.updated_at.isoformat()
            if state.status in ["done", "error"]
            else None,
            reference=None,
        )
        for state in filtered
    ]


@assignations_router.get("/{assignation_id}", response_model=AssignationResponse)
async def get_assignation(assignation_id: str, agent: AgentDep) -> AssignationResponse:
    """
    Get assignation status by ID.

    Use this endpoint to poll for results when WebSocket is unavailable.

    Args:
        assignation_id: Assignation ID
        agent: Injected FastAPIAgent

    Returns:
        Assignation with current status and results
    """
    state = agent.get_assignation(assignation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Assignation not found")

    return AssignationResponse(
        id=state.id,
        action=state.interface,
        status=state.status,
        args=state.args,
        returns=state.returns,
        yields=[],  # Could be populated from events
        error=state.error,
        progress=state.progress,
        created_at=state.created_at.isoformat(),
        started_at=None,
        completed_at=state.updated_at.isoformat() if state.status in ["done", "error"] else None,
        reference=None,
    )


@assignations_router.delete("/{assignation_id}")
async def cancel_assignation(assignation_id: str, agent: AgentDep) -> dict:
    """
    Cancel a running assignation.

    Args:
        assignation_id: Assignation ID to cancel
        agent: Injected Agent

    Returns:
        Success status
    """
    success = await agent.cancel(assignation_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel assignation")
    return {"success": True, "assignation_id": assignation_id}
