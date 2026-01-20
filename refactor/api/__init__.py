"""
Experiment Processing API Package.

This package provides a FastAPI-based API for processing experimental data
with real-time WebSocket updates and task scheduling.
"""

from .app import create_app
from .models import (
    Task,
    TaskStatus,
    TaskCreateRequest,
    ExperimentParameters,
    ExperimentRequest,
    ProcessResult,
    StatusResponse,
    StateUpdateRequest,
    StateBatchUpdateRequest,
    StateResponse,
    ActionInfo,
    ActionExecuteRequest,
)
from .managers import ConnectionManager, EngineManager
from .state import StateProxy, StateUpdate, StateSnapshot
from .registry import ActionRegistry, register, action_registry
from . import actions  # Import to make actions available
from .dependencies import (
    get_connection_manager,
    get_engine_manager,
    get_state_proxy,
    get_action_registry,
    ConnectionManagerDep,
    EngineManagerDep,
    StateProxyDep,
    ActionRegistryDep,
)

__all__ = [
    # App factory
    "create_app",
    # Models
    "Task",
    "TaskStatus",
    "TaskCreateRequest",
    "ExperimentParameters",
    "ExperimentRequest",
    "ProcessResult",
    "StatusResponse",
    "StateUpdateRequest",
    "StateBatchUpdateRequest",
    "StateResponse",
    "ActionInfo",
    "ActionExecuteRequest",
    # Managers
    "ConnectionManager",
    "EngineManager",
    # State
    "StateProxy",
    "StateUpdate",
    "StateSnapshot",
    # Registry
    "ActionRegistry",
    "register",
    "action_registry",
    # Actions module
    "actions",
    # Dependencies
    "get_connection_manager",
    "get_engine_manager",
    "get_state_proxy",
    "get_action_registry",
    "ConnectionManagerDep",
    "EngineManagerDep",
    "StateProxyDep",
    "ActionRegistryDep",
]
