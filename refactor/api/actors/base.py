"""
Base Actor class for action execution.

Actors are the execution units that process assignments (tasks).
They receive messages from the Agent and send events back.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from . import messages

if TYPE_CHECKING:
    from .agent import Agent

logger = logging.getLogger(__name__)


class ActorBuilder(Protocol):
    """Protocol for actor builder functions."""

    def __call__(self, agent: "Agent") -> "Actor":
        """Create an actor for the given agent."""
        ...


class Actor(BaseModel):
    """
    Base class for all actors.

    Actors are the main execution units that process assignments.
    They are managed by an Agent and communicate via messages.

    An actor is responsible for:
    - Processing Assign messages and executing the corresponding action
    - Sending events back to the agent (Done, Error, Log, Progress, etc.)
    - Handling cancellation and interruption
    """

    agent: Any = Field(..., description="The agent managing this actor")
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique actor ID",
    )
    action: str = Field(..., description="The action this actor handles")
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Track running assignments
    running_assignments: Dict[str, messages.Assign] = Field(default_factory=dict)

    # Private asyncio tasks
    _running_tasks: Dict[str, asyncio.Task] = PrivateAttr(default_factory=dict)

    async def asend(self, message: messages.FromActorMessage) -> None:
        """
        Send a message to the agent.

        Args:
            message: Event message to send
        """
        await self.agent.asend(self, message)

    async def apass(self, message: messages.ToActorMessage) -> None:
        """
        Receive a message from the agent.

        Routes the message to the appropriate handler.
        """
        await self.aprocess(message)

    async def aprocess(self, message: messages.ToActorMessage) -> None:
        """
        Process an incoming message.

        Routes to specific handlers based on message type.
        """
        logger.debug(f"Actor {self.id} processing: {message.type}")

        if isinstance(message, messages.Assign):
            # Track the assignment
            self.running_assignments[message.assignation] = message

            # Create a task to run the assignment
            task = asyncio.create_task(self._run_assignment(message))
            self._running_tasks[message.assignation] = task
            task.add_done_callback(lambda t: self._on_task_done(message.assignation, t))

        elif isinstance(message, messages.Cancel):
            await self._handle_cancel(message)

        elif isinstance(message, messages.Interrupt):
            await self._handle_interrupt(message)

        elif isinstance(message, messages.Pause):
            await self._handle_pause(message)

        elif isinstance(message, messages.Resume):
            await self._handle_resume(message)

        else:
            logger.warning(f"Unknown message type: {type(message)}")

    async def _run_assignment(self, assignment: messages.Assign) -> None:
        """
        Run an assignment.

        This is the wrapper that calls on_assign and handles errors.
        """
        try:
            # Notify that we've accepted the assignment
            await self.asend(messages.AssignedEvent(assignation=assignment.assignation))

            # Execute the actual work
            await self.on_assign(assignment)

        except asyncio.CancelledError:
            logger.info(f"Assignment {assignment.assignation} was cancelled")
            await self.asend(messages.CancelledEvent(assignation=assignment.assignation))

        except Exception as e:
            logger.exception(f"Assignment {assignment.assignation} failed")
            await self.asend(
                messages.CriticalEvent(
                    assignation=assignment.assignation,
                    error=str(e),
                )
            )

    def _on_task_done(self, assignation_id: str, task: asyncio.Task) -> None:
        """Cleanup when a task completes."""
        self._running_tasks.pop(assignation_id, None)
        self.running_assignments.pop(assignation_id, None)

        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Task {assignation_id} failed: {e}")

    @abstractmethod
    async def on_assign(self, assignment: messages.Assign) -> None:
        """
        Handle an assignment.

        Subclasses must implement this to perform the actual work.
        Should call self.asend() with DoneEvent or YieldEvent when complete.

        Args:
            assignment: The assignment to process
        """
        raise NotImplementedError("Subclasses must implement on_assign")

    async def _handle_cancel(self, cancel: messages.Cancel) -> None:
        """Handle cancellation request."""
        task = self._running_tasks.get(cancel.assignation)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        else:
            # Already done or not found
            await self.asend(messages.CancelledEvent(assignation=cancel.assignation))

    async def _handle_interrupt(self, interrupt: messages.Interrupt) -> None:
        """Handle interrupt request (force stop)."""
        task = self._running_tasks.get(interrupt.assignation)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self.asend(messages.InterruptedEvent(assignation=interrupt.assignation))

    async def _handle_pause(self, pause: messages.Pause) -> None:
        """Handle pause request."""
        # Default: no-op, subclasses can implement
        await self.asend(messages.PausedEvent(assignation=pause.assignation))

    async def _handle_resume(self, resume: messages.Resume) -> None:
        """Handle resume request."""
        # Default: no-op, subclasses can implement
        await self.asend(messages.ResumedEvent(assignation=resume.assignation))

    async def acheck_assignation(self, assignation_id: str) -> bool:
        """Check if an assignation is still running."""
        return assignation_id in self._running_tasks

    async def acancel(self) -> None:
        """Cancel all running assignments."""
        for assignation_id, task in list(self._running_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
