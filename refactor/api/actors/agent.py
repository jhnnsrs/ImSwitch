"""
Agent for managing actors and routing assignments.

The Agent acts as the coordinator between incoming HTTP/WebSocket requests
and the actors that execute actions. Unlike rekuest-next which connects
to a GraphQL backend, this agent exposes actions via FastAPI.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from . import messages
from .base import Actor
from .registry import DefinitionRegistry, get_default_definition_registry

if TYPE_CHECKING:
    from ..managers import ConnectionManager

logger = logging.getLogger(__name__)


class Assignation(BaseModel):
    """
    Represents an assignment (task execution) and its current state.

    Used to track the lifecycle of an action execution.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Assignation ID")
    action: str = Field(..., description="Action being executed")
    args: Dict[str, Any] = Field(default_factory=dict, description="Input arguments")
    status: messages.AssignationStatus = Field(
        default=messages.AssignationStatus.PENDING,
        description="Current status",
    )
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    returns: Optional[Dict[str, Any]] = Field(None, description="Return value(s)")
    yields: List[Dict[str, Any]] = Field(default_factory=list, description="Yielded values")
    error: Optional[str] = Field(None, description="Error message if failed")
    user: Optional[str] = Field(None, description="User who initiated")
    reference: Optional[str] = Field(None, description="Client-provided reference")
    logs: List[Dict[str, Any]] = Field(default_factory=list, description="Log messages")
    progress: Optional[int] = Field(None, description="Progress 0-100")


class Agent(BaseModel):
    """
    Agent that manages actors and routes assignments.

    The Agent is the main coordinator that:
    - Creates actors for registered actions
    - Routes assign messages to appropriate actors
    - Collects events from actors and broadcasts via WebSocket
    - Tracks assignation state for polling
    """

    definition_registry: DefinitionRegistry = Field(
        default_factory=get_default_definition_registry,
        description="Registry of action definitions",
    )
    connection_manager: Optional[Any] = Field(
        None, description="WebSocket connection manager for broadcasting"
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Actor management
    actors: Dict[str, Actor] = Field(default_factory=dict, exclude=True)

    # Assignation tracking
    assignations: Dict[str, Assignation] = Field(default_factory=dict)

    # Private state
    _is_running: bool = PrivateAttr(default=False)
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def start(self) -> None:
        """Start the agent and create actors for all registered actions."""
        logger.info("Starting agent...")
        self._is_running = True

        # Create an actor for each registered action
        for action_name, builder in self.definition_registry.actor_builders.items():
            actor = builder(self)
            self.actors[action_name] = actor
            logger.debug(f"Created actor for action: {action_name}")

        logger.info(f"Agent started with {len(self.actors)} actors")

    async def stop(self) -> None:
        """Stop the agent and all actors."""
        logger.info("Stopping agent...")
        self._is_running = False

        # Cancel all running assignments
        for actor in self.actors.values():
            await actor.acancel()

        self.actors.clear()
        logger.info("Agent stopped")

    async def assign(
        self,
        action: str,
        args: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
        reference: Optional[str] = None,
    ) -> Assignation:
        """
        Create a new assignation and dispatch to the appropriate actor.

        This is the main entry point for executing an action.

        Args:
            action: Name of the action to execute
            args: Arguments to pass to the action
            user: User initiating the action
            reference: Client-provided reference for tracking

        Returns:
            Assignation with ID for tracking

        Raises:
            ValueError: If action is not registered
        """
        if action not in self.actors:
            raise ValueError(f"Action '{action}' is not registered")

        # Create assignation
        assignation = Assignation(
            action=action,
            args=args or {},
            user=user,
            reference=reference,
            status=messages.AssignationStatus.PENDING,
        )
        self.assignations[assignation.id] = assignation

        # Create assign message
        assign_msg = messages.Assign(
            assignation=assignation.id,
            action=action,
            args=args or {},
            user=user,
            reference=reference,
        )

        # Broadcast that we're starting
        await self._broadcast(
            {
                "type": "assignation_created",
                "assignation_id": assignation.id,
                "action": action,
                "status": assignation.status.value,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Dispatch to actor (async, returns immediately)
        actor = self.actors[action]
        asyncio.create_task(actor.apass(assign_msg))

        return assignation

    async def cancel(self, assignation_id: str) -> bool:
        """
        Cancel a running assignation.

        Args:
            assignation_id: ID of the assignation to cancel

        Returns:
            True if cancellation was sent
        """
        assignation = self.assignations.get(assignation_id)
        if not assignation:
            return False

        if assignation.status not in (
            messages.AssignationStatus.PENDING,
            messages.AssignationStatus.ASSIGNED,
            messages.AssignationStatus.RUNNING,
        ):
            return False

        actor = self.actors.get(assignation.action)
        if actor:
            cancel_msg = messages.Cancel(assignation=assignation_id)
            await actor.apass(cancel_msg)
            return True

        return False

    async def get_assignation(self, assignation_id: str) -> Optional[Assignation]:
        """Get assignation by ID."""
        return self.assignations.get(assignation_id)

    async def list_assignations(
        self,
        status: Optional[messages.AssignationStatus] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Assignation]:
        """
        List assignations with optional filters.

        Args:
            status: Filter by status
            action: Filter by action name
            limit: Maximum number to return

        Returns:
            List of assignations
        """
        results = list(self.assignations.values())

        if status:
            results = [a for a in results if a.status == status]
        if action:
            results = [a for a in results if a.action == action]

        # Sort by created_at descending
        results.sort(key=lambda a: a.created_at, reverse=True)

        return results[:limit]

    async def asend(self, actor: Actor, message: messages.FromActorMessage) -> None:
        """
        Receive a message from an actor and update state.

        This is called by actors to report events.
        """
        logger.debug(f"Agent received from actor {actor.id}: {message.type}")

        assignation_id = getattr(message, "assignation", None)
        assignation = self.assignations.get(assignation_id) if assignation_id else None

        if isinstance(message, messages.AssignedEvent):
            if assignation:
                assignation.status = messages.AssignationStatus.ASSIGNED
                assignation.started_at = datetime.now()
            await self._broadcast(
                {
                    "type": "assignation_assigned",
                    "assignation_id": assignation_id,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        elif isinstance(message, messages.YieldEvent):
            if assignation:
                assignation.status = messages.AssignationStatus.YIELDED
                if message.returns:
                    assignation.yields.append(message.returns)
            await self._broadcast(
                {
                    "type": "assignation_yield",
                    "assignation_id": assignation_id,
                    "returns": message.returns,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        elif isinstance(message, messages.DoneEvent):
            if assignation:
                assignation.status = messages.AssignationStatus.DONE
                assignation.completed_at = datetime.now()
                assignation.returns = message.returns
            await self._broadcast(
                {
                    "type": "assignation_done",
                    "assignation_id": assignation_id,
                    "returns": message.returns,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        elif isinstance(message, messages.ErrorEvent):
            if assignation:
                assignation.status = messages.AssignationStatus.ERROR
                assignation.completed_at = datetime.now()
                assignation.error = message.error
            await self._broadcast(
                {
                    "type": "assignation_error",
                    "assignation_id": assignation_id,
                    "error": message.error,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        elif isinstance(message, messages.CriticalEvent):
            if assignation:
                assignation.status = messages.AssignationStatus.CRITICAL
                assignation.completed_at = datetime.now()
                assignation.error = message.error
            await self._broadcast(
                {
                    "type": "assignation_critical",
                    "assignation_id": assignation_id,
                    "error": message.error,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        elif isinstance(message, messages.LogEvent):
            if assignation:
                assignation.logs.append(
                    {
                        "message": message.message,
                        "level": message.level,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            await self._broadcast(
                {
                    "type": "assignation_log",
                    "assignation_id": assignation_id,
                    "message": message.message,
                    "level": message.level,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        elif isinstance(message, messages.ProgressEvent):
            if assignation:
                assignation.progress = message.progress
                assignation.status = messages.AssignationStatus.RUNNING
            await self._broadcast(
                {
                    "type": "assignation_progress",
                    "assignation_id": assignation_id,
                    "progress": message.progress,
                    "message": message.message,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        elif isinstance(message, messages.CancelledEvent):
            if assignation:
                assignation.status = messages.AssignationStatus.CANCELLED
                assignation.completed_at = datetime.now()
            await self._broadcast(
                {
                    "type": "assignation_cancelled",
                    "assignation_id": assignation_id,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    async def _broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected WebSocket clients."""
        if self.connection_manager:
            await self.connection_manager.broadcast(message)
