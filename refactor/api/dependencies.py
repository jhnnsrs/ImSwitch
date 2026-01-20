"""
FastAPI dependency injection for the Experiment Processing API.

This module provides typed dependency functions for accessing managers
with proper type safety.
"""

from typing import Annotated
from fastapi import Depends, Request

from .managers import ConnectionManager, EngineManager
from .state import StateProxy
from .registry import ActionRegistry


def get_connection_manager(request: Request) -> ConnectionManager:
    """Get the ConnectionManager from app state with proper typing."""
    return request.app.state.manager


def get_engine_manager(request: Request) -> EngineManager:
    """Get the EngineManager from app state with proper typing."""
    return request.app.state.engine


def get_state_proxy(request: Request) -> StateProxy:
    """Get the StateProxy from app state with proper typing."""
    return request.app.state.state_proxy


def get_action_registry(request: Request) -> ActionRegistry:
    """Get the ActionRegistry from app state with proper typing."""
    return request.app.state.action_registry


# Type aliases for dependency injection
ConnectionManagerDep = Annotated[ConnectionManager, Depends(get_connection_manager)]
EngineManagerDep = Annotated[EngineManager, Depends(get_engine_manager)]
StateProxyDep = Annotated[StateProxy, Depends(get_state_proxy)]
ActionRegistryDep = Annotated[ActionRegistry, Depends(get_action_registry)]
