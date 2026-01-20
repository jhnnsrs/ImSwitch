"""
FastAPI application factory for the Experiment Processing API.

This module provides the application factory and lifespan management.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .managers import ConnectionManager, EngineManager
from .routes import (
    status_router,
    schema_router,
    tasks_router,
    process_router,
    ws_router,
)


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

    # Include routers
    app.include_router(status_router)
    app.include_router(schema_router)
    app.include_router(tasks_router)
    app.include_router(process_router)
    app.include_router(ws_router)

    return app
