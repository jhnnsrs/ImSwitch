"""
Message types for actor communication.

This module defines all message types used for communication between
the Agent and Actors, inspired by rekuest-next patterns.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class AssignationStatus(str, Enum):
    """Status of an assignation (task assignment)."""

    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    YIELDED = "YIELDED"
    DONE = "DONE"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    CRITICAL = "CRITICAL"


class LogLevel(str, Enum):
    """Log levels for log events."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Base message class
class Message(BaseModel):
    """Base message class with auto-generated ID."""

    model_config = ConfigDict(use_enum_values=True, frozen=True)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# Messages TO actors (from Agent)
class Assign(Message):
    """
    Assignment message sent to an actor to start execution.

    Contains all information needed to execute an action.
    """

    type: Literal["ASSIGN"] = "ASSIGN"
    assignation: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique assignation ID for tracking this execution",
    )
    action: str = Field(..., description="The action/function to execute")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the action")
    user: Optional[str] = Field(None, description="User who initiated the action")
    reference: Optional[str] = Field(None, description="Client-provided reference")
    parent: Optional[str] = Field(None, description="Parent assignation ID for nested calls")


class Cancel(Message):
    """
    Cancellation request for a running assignation.
    """

    type: Literal["CANCEL"] = "CANCEL"
    assignation: str = Field(..., description="Assignation ID to cancel")


class Interrupt(Message):
    """
    Interrupt request (force stop) for a running assignation.
    """

    type: Literal["INTERRUPT"] = "INTERRUPT"
    assignation: str = Field(..., description="Assignation ID to interrupt")


class Step(Message):
    """
    Step message for debugging - advance one step.
    """

    type: Literal["STEP"] = "STEP"
    assignation: str = Field(..., description="Assignation ID to step")


class Pause(Message):
    """
    Pause message to suspend execution.
    """

    type: Literal["PAUSE"] = "PAUSE"
    assignation: str = Field(..., description="Assignation ID to pause")


class Resume(Message):
    """
    Resume message to continue paused execution.
    """

    type: Literal["RESUME"] = "RESUME"
    assignation: str = Field(..., description="Assignation ID to resume")


# Messages FROM actors (to Agent)
class AssignedEvent(Message):
    """
    Event sent when an actor has accepted an assignment.
    """

    type: Literal["ASSIGNED"] = "ASSIGNED"
    assignation: str = Field(..., description="Assignation ID that was accepted")


class YieldEvent(Message):
    """
    Event sent when an actor yields intermediate results.

    This is used for generator-style actions that produce multiple outputs.
    """

    type: Literal["YIELD"] = "YIELD"
    assignation: str = Field(..., description="Assignation ID")
    returns: Optional[Dict[str, Any]] = Field(None, description="Yielded values")


class DoneEvent(Message):
    """
    Event sent when an actor completes an assignation successfully.
    """

    type: Literal["DONE"] = "DONE"
    assignation: str = Field(..., description="Assignation ID that completed")
    returns: Optional[Dict[str, Any]] = Field(None, description="Final return values")


class ErrorEvent(Message):
    """
    Event sent when an actor encounters a recoverable error.
    """

    type: Literal["ERROR"] = "ERROR"
    assignation: str = Field(..., description="Assignation ID")
    error: str = Field(..., description="Error message")


class CriticalEvent(Message):
    """
    Event sent when an actor encounters a non-recoverable error.
    """

    type: Literal["CRITICAL"] = "CRITICAL"
    assignation: str = Field(..., description="Assignation ID")
    error: str = Field(..., description="Critical error message")


class LogEvent(Message):
    """
    Log message from an actor.
    """

    type: Literal["LOG"] = "LOG"
    assignation: str = Field(..., description="Assignation ID")
    message: str = Field(..., description="Log message")
    level: str = Field("INFO", description="Log level")


class ProgressEvent(Message):
    """
    Progress update from an actor.
    """

    type: Literal["PROGRESS"] = "PROGRESS"
    assignation: str = Field(..., description="Assignation ID")
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")
    message: Optional[str] = Field(None, description="Progress message")


class CancelledEvent(Message):
    """
    Event sent when an assignation is successfully cancelled.
    """

    type: Literal["CANCELLED"] = "CANCELLED"
    assignation: str = Field(..., description="Assignation ID that was cancelled")


class InterruptedEvent(Message):
    """
    Event sent when an assignation is interrupted.
    """

    type: Literal["INTERRUPTED"] = "INTERRUPTED"
    assignation: str = Field(..., description="Assignation ID that was interrupted")


class PausedEvent(Message):
    """
    Event sent when an assignation is paused.
    """

    type: Literal["PAUSED"] = "PAUSED"
    assignation: str = Field(..., description="Assignation ID that was paused")


class ResumedEvent(Message):
    """
    Event sent when a paused assignation is resumed.
    """

    type: Literal["RESUMED"] = "RESUMED"
    assignation: str = Field(..., description="Assignation ID that was resumed")


# Union types for message routing
ToActorMessage = Union[Assign, Cancel, Interrupt, Step, Pause, Resume]
FromActorMessage = Union[
    AssignedEvent,
    YieldEvent,
    DoneEvent,
    ErrorEvent,
    CriticalEvent,
    LogEvent,
    ProgressEvent,
    CancelledEvent,
    InterruptedEvent,
    PausedEvent,
    ResumedEvent,
]
