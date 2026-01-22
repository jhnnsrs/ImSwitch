"""
Actor system for async action execution.

This module re-exports the rekuest_next actor system and provides
a FastAPI-specific Agent for HTTP/WebSocket exposure.

The rekuest_next library provides:
- DefinitionRegistry: Stores action definitions and actor builders
- register: Decorator for registering functions as actions
- Actor: Base class for actors that execute actions
- AsyncFuncActor/AsyncGenActor: Functional actors for functions/generators
- messages: Assign, Cancel, YieldEvent, DoneEvent, ErrorEvent, etc.

This module adds:
- FastAPIAgent: Agent that routes HTTP requests to actors and broadcasts
  events via WebSocket instead of connecting to the arkitekt backend.
"""

# Re-export from rekuest_next
from rekuest_next.register import register
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.actors.base import Actor
from rekuest_next.actors.functional import AsyncFuncActor, AsyncGenActor
from rekuest_next.actors.types import ActorBuilder
from rekuest_next import messages

# Our FastAPI-specific agent
from .fastapi_agent import FastAPIAgent, AssignationState, AgentConnectionManager

__all__ = [
    # rekuest_next exports
    "register",
    "DefinitionRegistry",
    "StructureRegistry",
    "Actor",
    "AsyncFuncActor",
    "AsyncGenActor",
    "ActorBuilder",
    "messages",
    # FastAPI-specific
    "FastAPIAgent",
    "AssignationState",
    "AgentConnectionManager",
]
