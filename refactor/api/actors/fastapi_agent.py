"""
FastAPI-specific Agent implementation.

This module provides a FastAPI-based Agent that implements the rekuest_next
agent pattern but exposes actions via HTTP/WebSocket instead of connecting
to the arkitekt backend.

The FastAPIAgent:
- Uses rekuest_next's DefinitionRegistry to get actor builders
- Uses rekuest_next's Actor classes (AsyncFuncActor, AsyncGenActor) directly
- Routes HTTP POST requests to actors via apass(Assign(...))
- Captures actor events and broadcasts via WebSocket
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.actors.base import Actor
from rekuest_next.actors.types import ActorBuilder
from rekuest_next import messages
from rekuest_next.structures.registry import StructureRegistry

logger = logging.getLogger(__name__)


class AssignationState(BaseModel):
    """State of an assignation (task execution)."""

    id: str = Field(..., description="Unique assignation ID")
    interface: str = Field(..., description="Interface/action name")
    status: str = Field(default="pending", description="Current status")
    args: Dict[str, Any] = Field(default_factory=dict)
    returns: Optional[Dict[str, Any]] = Field(default=None)
    error: Optional[str] = Field(default=None)
    progress: int = Field(default=0)
    progress_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    events: List[Dict[str, Any]] = Field(default_factory=list)


class AgentConnectionManager:
    """WebSocket connection manager for broadcasting events from the agent."""

    def __init__(self) -> None:
        self.active_connections: Set[Any] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: Any) -> None:
        """Add a new connection."""
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: Any) -> None:
        """Remove a connection."""
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        async with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                await self.disconnect(connection)


class FastAPIAgent:
    """
    FastAPI-based Agent that uses rekuest_next's actor system.

    This agent:
    - Uses rekuest_next.definition.registry.DefinitionRegistry
    - Uses rekuest_next.actors (AsyncFuncActor, etc.) directly
    - Routes HTTP requests to actors via rekuest_next.messages.Assign
    - Broadcasts actor events via WebSocket

    The agent implements the interface expected by rekuest_next Actors:
    - asend(actor, message): Called by actors to send events
    """

    def __init__(
        self,
        definition_registry: DefinitionRegistry,
        instance_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the FastAPI Agent.

        Args:
            definition_registry: The rekuest_next DefinitionRegistry containing
                                registered actions and their actor builders
            instance_id: Unique instance identifier
        """
        self.definition_registry = definition_registry
        self.instance_id = instance_id or str(uuid.uuid4())

        # Actor management (matches rekuest_next.agents.base.BaseAgent pattern)
        self.managed_actors: Dict[str, Actor] = {}
        self.managed_assignments: Dict[str, messages.Assign] = {}

        # Assignation state tracking
        self.assignation_states: Dict[str, AssignationState] = {}

        # WebSocket connection manager
        self.connection_manager = AgentConnectionManager()

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(f"FastAPIAgent initialized with instance_id: {self.instance_id}")

    @property
    def hook_registry(self) -> Any:
        """Stub for rekuest_next Agent protocol compatibility."""
        return None

    @property
    def extension_registry(self) -> Any:
        """Stub for rekuest_next Agent protocol compatibility."""
        return None

    @property
    def capture_condition(self) -> asyncio.Condition:
        """Stub for rekuest_next Agent protocol compatibility."""
        if not hasattr(self, "_capture_condition"):
            self._capture_condition = asyncio.Condition()
        return self._capture_condition

    @property
    def capture_active(self) -> bool:
        """Stub for rekuest_next Agent protocol compatibility."""
        return False

    async def asend(self, actor: Actor, message: messages.FromAgentMessage) -> None:
        """
        Handle messages from actors.

        This is called by Actor.asend() to forward events back to the agent.
        Instead of sending to a transport, we update state and broadcast via WebSocket.

        Args:
            actor: The actor sending the message
            message: The message from the actor
        """
        logger.debug(f"Agent received message from actor: {message}")

        assignation_id = getattr(message, "assignation", None)
        if not assignation_id:
            logger.warning(f"Message without assignation: {message}")
            return

        async with self._lock:
            state = self.assignation_states.get(assignation_id)
            if not state:
                logger.warning(f"Unknown assignation: {assignation_id}")
                return

        # Handle different message types
        event_data: Dict[str, Any] = {
            "type": message.type.value if hasattr(message.type, "value") else str(message.type),
            "assignation": assignation_id,
            "assignation_id": assignation_id,  # Alias for compatibility
            "timestamp": datetime.utcnow().isoformat(),
        }

        if isinstance(message, messages.ProgressEvent):
            state.status = "running"
            state.progress = getattr(message, "progress", 0)
            state.progress_message = getattr(message, "message", None)
            event_data["progress"] = state.progress
            event_data["message"] = state.progress_message

        elif isinstance(message, messages.YieldEvent):
            state.returns = message.returns
            event_data["returns"] = message.returns

        elif isinstance(message, messages.DoneEvent):
            state.status = "done"
            event_data["status"] = "done"
            # Also send application-level event
            await self.connection_manager.broadcast({
                "type": "assignation_done",
                "assignation_id": assignation_id,
                "action": state.interface,
                "returns": state.returns,
                "timestamp": datetime.utcnow().isoformat(),
            })

        elif isinstance(message, messages.ErrorEvent):
            state.status = "error"
            state.error = message.error
            event_data["error"] = message.error
            # Also send application-level event
            await self.connection_manager.broadcast({
                "type": "assignation_error",
                "assignation_id": assignation_id,
                "action": state.interface,
                "error": message.error,
                "timestamp": datetime.utcnow().isoformat(),
            })

        elif isinstance(message, messages.CriticalEvent):
            state.status = "critical"
            state.error = message.error
            event_data["error"] = message.error
            # Also send application-level event
            await self.connection_manager.broadcast({
                "type": "assignation_error",
                "assignation_id": assignation_id,
                "action": state.interface,
                "error": message.error,
                "timestamp": datetime.utcnow().isoformat(),
            })

        elif isinstance(message, messages.LogEvent):
            event_data["message"] = message.message
            event_data["level"] = getattr(message, "level", "INFO")

        state.updated_at = datetime.utcnow()
        state.events.append(event_data)

        # Broadcast via WebSocket
        await self.connection_manager.broadcast(event_data)

    async def aput_on_shelve(self, identifier: Any, value: Any) -> str:
        """Stub for rekuest_next Agent protocol - shelve storage."""
        return str(uuid.uuid4())

    async def aget_from_shelve(self, key: str) -> Any:
        """Stub for rekuest_next Agent protocol - shelve retrieval."""
        return None

    async def apublish_state(self, state: Any) -> None:
        """Stub for rekuest_next Agent protocol - state publishing."""
        pass

    async def aget_state(self, interface: str) -> Any:
        """Stub for rekuest_next Agent protocol - get state."""
        return None

    async def aget_context(self, context: str) -> Any:
        """Stub for rekuest_next Agent protocol - get context."""
        return None

    async def aprovide(self, instance_id: Optional[str] = None) -> None:
        """Stub for rekuest_next Agent protocol - provide."""
        pass

    async def atest(self, instance_id: Optional[str] = None) -> None:
        """Stub for rekuest_next Agent protocol - test."""
        pass

    async def assign(
        self,
        interface: str,
        args: Dict[str, Any],
        user: str = "anonymous",
        reference: Optional[str] = None,
    ) -> str:
        """
        Create and execute an assignment.

        This is the main entry point for HTTP requests to trigger actions.

        Args:
            interface: The action/interface name
            args: Arguments for the action
            user: User making the request
            reference: Optional reference ID

        Returns:
            The assignation ID for tracking
        """
        assignation_id = str(uuid.uuid4())

        # Get or create actor for this interface
        async with self._lock:
            actor = await self._get_or_create_actor(interface)

        # Create assignation state
        state = AssignationState(
            id=assignation_id,
            interface=interface,
            status="pending",
            args=args,
        )

        async with self._lock:
            self.assignation_states[assignation_id] = state

        # Broadcast assignation_created event
        await self.connection_manager.broadcast({
            "type": "assignation_created",
            "assignation_id": assignation_id,
            "action": interface,
            "args": args,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Create rekuest_next Assign message
        # Note: extension defaults to "default" for our use case
        assign_message = messages.Assign(
            interface=interface,
            extension="default",
            assignation=assignation_id,
            args=args,
            user=user,
            reference=reference or assignation_id,
        )

        async with self._lock:
            self.managed_assignments[assignation_id] = assign_message

        # Pass to actor for processing
        # This will call actor.on_assign() which executes the action
        # and sends events back via asend()
        await actor.apass(assign_message)

        return assignation_id

    async def cancel(self, assignation_id: str) -> bool:
        """
        Cancel an assignation.

        Args:
            assignation_id: The assignation to cancel

        Returns:
            True if cancel was sent, False if assignation not found
        """
        async with self._lock:
            if assignation_id not in self.managed_assignments:
                return False

            assign = self.managed_assignments[assignation_id]
            actor = self.managed_actors.get(f"default.{assign.interface}")

            if not actor:
                return False
            
            state = self.assignation_states.get(assignation_id)
            if state and state.status in ["done", "error", "critical"]:
                # Already completed, cannot cancel
                return False

        # Note: rekuest_next.messages.Cancel expects int assignation, but we use string UUIDs.
        # For FastAPI use case, most actions complete quickly anyway.
        # We'll just cancel the asyncio task if it's running.
        try:
            if hasattr(actor, '_running_asyncio_tasks') and assignation_id in actor._running_asyncio_tasks:
                task = actor._running_asyncio_tasks[assignation_id]
                task.cancel()
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to cancel assignation {assignation_id}: {e}")
            return False

    async def _get_or_create_actor(self, interface: str) -> Actor:
        """
        Get or create an actor for the given interface.

        Uses the rekuest_next DefinitionRegistry to get the actor builder.
        Starts the actor with arun() so it's ready to receive messages.

        Args:
            interface: The interface/action name

        Returns:
            The actor instance
        """
        actor_id = f"default.{interface}"

        if actor_id in self.managed_actors:
            return self.managed_actors[actor_id]

        # Get actor builder from registry
        try:
            actor_builder = self.definition_registry.get_builder_for_interface(interface)
        except KeyError:
            raise ValueError(f"No actor builder found for interface: {interface}")

        # Create actor with self as the agent
        actor = actor_builder(agent=self)
        
        # Start the actor's listening loop (creates _in_queue and starts alisten())
        await actor.arun()
        
        self.managed_actors[actor_id] = actor

        logger.info(f"Created and started actor for interface: {interface}")
        return actor

    def get_assignation(self, assignation_id: str) -> Optional[AssignationState]:
        """Get the state of an assignation."""
        return self.assignation_states.get(assignation_id)

    def get_all_assignations(self) -> List[AssignationState]:
        """Get all assignation states."""
        return list(self.assignation_states.values())

    def get_available_actions(self) -> Dict[str, Any]:
        """
        Get all available actions from the registry.

        Returns:
            Dictionary mapping interface names to their definitions
        """
        result = {}
        for interface, template in self.definition_registry.templates.items():
            result[interface] = {
                "name": template.definition.name,
                "description": template.definition.description,
                "args": [
                    {
                        "key": arg.key,
                        "kind": arg.kind.value if hasattr(arg.kind, "value") else str(arg.kind),
                        "description": arg.description,
                        "nullable": arg.nullable,
                        "default": arg.default,
                    }
                    for arg in template.definition.args
                ],
                "returns": [
                    {
                        "key": ret.key,
                        "kind": ret.kind.value if hasattr(ret.kind, "value") else str(ret.kind),
                        "description": ret.description,
                    }
                    for ret in template.definition.returns
                ],
                "collections": template.definition.collections,
            }
        return result
