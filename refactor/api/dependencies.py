"""
FastAPI dependency injection for the Experiment Processing API.

This module provides typed dependency functions for accessing managers
with proper type safety.
"""

from typing import Annotated
from fastapi import Depends, Request

from .managers import ConnectionManager, EngineManager


def get_connection_manager(request: Request) -> ConnectionManager:
    """Get the ConnectionManager from app state with proper typing."""
    return request.app.state.manager


def get_engine_manager(request: Request) -> EngineManager:
    """Get the EngineManager from app state with proper typing."""
    return request.app.state.engine


# Type aliases for dependency injection
ConnectionManagerDep = Annotated[ConnectionManager, Depends(get_connection_manager)]
EngineManagerDep = Annotated[EngineManager, Depends(get_engine_manager)]
