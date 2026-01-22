"""
FastAPI dependency injection for the Experiment Processing API.

This module provides typed dependency functions for accessing managers
with proper type safety.
"""

from typing import Annotated
from fastapi import Depends, Request

from .managers import ConnectionManager
from .state import StateProxy
from .actors import FastAPIAgent, DefinitionRegistry


def get_connection_manager(request: Request) -> ConnectionManager:
    """Get the ConnectionManager from app state with proper typing."""
    return request.app.state.manager


def get_state_proxy(request: Request) -> StateProxy:
    """Get the StateProxy from app state with proper typing."""
    return request.app.state.state_proxy


def get_definition_registry(request: Request) -> DefinitionRegistry:
    """Get the DefinitionRegistry from app state with proper typing."""
    return request.app.state.definition_registry


def get_agent(request: Request) -> FastAPIAgent:
    """Get the FastAPIAgent from app state with proper typing."""
    return request.app.state.agent


# Type aliases for dependency injection
ConnectionManagerDep = Annotated[ConnectionManager, Depends(get_connection_manager)]
StateProxyDep = Annotated[StateProxy, Depends(get_state_proxy)]
DefinitionRegistryDep = Annotated[DefinitionRegistry, Depends(get_definition_registry)]
AgentDep = Annotated[FastAPIAgent, Depends(get_agent)]
