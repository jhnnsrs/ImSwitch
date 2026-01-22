"""
FastAPI application factory for the Experiment Processing API.

This module provides the application factory and lifespan management.
Uses rekuest_next's actor system for async action execution, with
a FastAPI-specific Agent for HTTP/WebSocket exposure.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .managers import ConnectionManager
from .state import StateProxy
from .actors import FastAPIAgent
from .microscope_actions import definition_registry, structure_registry
from . import microscope_actions  # noqa: F401 - Import to register actions
from .routes import (
    status_router,
    schema_router,
    process_router,
    ws_router,
    state_router,
    actions_router,
    assignations_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - setup and teardown."""
    # Startup: Initialize managers
    app.state.manager = ConnectionManager()
    app.state.state_proxy = StateProxy(app.state.manager)

    # Use the registries from microscope_actions (populated by @register)
    app.state.definition_registry = definition_registry
    app.state.structure_registry = structure_registry

    # Create the FastAPIAgent with the rekuest_next registry
    app.state.agent = FastAPIAgent(
        definition_registry=app.state.definition_registry,
    )

    # Share the connection manager with the agent
    app.state.agent.connection_manager = app.state.manager

    # Start background tasks
    await app.state.state_proxy.start()

    yield

    # Shutdown: cleanup
    await app.state.state_proxy.stop()
    app.state.manager.active_connections.clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Experiment Processing API",
        description="Actor-based async API for microscope control using rekuest_next",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(status_router)
    app.include_router(schema_router)
    app.include_router(process_router)
    app.include_router(ws_router)
    app.include_router(state_router)
    app.include_router(actions_router)
    app.include_router(assignations_router)

    return app
