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
)
from .managers import ConnectionManager, EngineManager
from .dependencies import (
    get_connection_manager,
    get_engine_manager,
    ConnectionManagerDep,
    EngineManagerDep,
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
    # Managers
    "ConnectionManager",
    "EngineManager",
    # Dependencies
    "get_connection_manager",
    "get_engine_manager",
    "ConnectionManagerDep",
    "EngineManagerDep",
]
