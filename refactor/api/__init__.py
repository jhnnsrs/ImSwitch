"""
Experiment Processing API Package.

This package provides a FastAPI-based API for microscope control
with real-time WebSocket updates and actor-based async execution using rekuest_next.
"""

from .app import create_app
from .models import (
    ExperimentParameters,
    ExperimentRequest,
    ProcessResult,
    StatusResponse,
    StateUpdateRequest,
    StateBatchUpdateRequest,
    StateResponse,
)
from .managers import ConnectionManager
from .state import StateProxy, StateUpdate, StateSnapshot
from .actors import (
    FastAPIAgent,
    Actor,
    AsyncFuncActor,
    AsyncGenActor,
    DefinitionRegistry,
    StructureRegistry,
    register,
    messages,
)
from . import microscope_actions  # Import to make actions available
from .dependencies import (
    get_connection_manager,
    get_state_proxy,
    get_definition_registry,
    get_agent,
    ConnectionManagerDep,
    StateProxyDep,
    DefinitionRegistryDep,
    AgentDep,
)

__all__ = [
    # App factory
    "create_app",
    # Models
    "ExperimentParameters",
    "ExperimentRequest",
    "ProcessResult",
    "StatusResponse",
    "StateUpdateRequest",
    "StateBatchUpdateRequest",
    "StateResponse",
    # Managers
    "ConnectionManager",
    # State
    "StateProxy",
    "StateUpdate",
    "StateSnapshot",
    # Actor system (rekuest_next re-exports)
    "FastAPIAgent",
    "Actor",
    "AsyncFuncActor",
    "AsyncGenActor",
    "DefinitionRegistry",
    "StructureRegistry",
    "register",
    "messages",
    "get_state_proxy",
    "get_definition_registry",
    "get_agent",
    "ConnectionManagerDep",
    "StateProxyDep",
    "DefinitionRegistryDep",
    "AgentDep",
]
