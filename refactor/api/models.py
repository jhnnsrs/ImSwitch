"""
Pydantic models for the Experiment Processing API.

This module contains all data models used for request/response validation
and task management.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class TaskStatus(str, Enum):
    """Status of a scheduled task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """Represents a scheduled microscope task."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Name of the task")
    action: str = Field(..., description="Microscope action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status")
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TaskCreateRequest(BaseModel):
    """Request model for creating a task."""

    name: str = Field(..., description="Task name")
    action: str = Field(..., description="Microscope action")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")


class ExperimentParameters(BaseModel):
    """Parameters for an experiment."""

    exposure_time: Optional[float] = Field(None, description="Exposure time in seconds")
    laser_power: Optional[float] = Field(None, description="Laser power in mW")
    num_frames: Optional[int] = Field(None, description="Number of frames to acquire")
    custom_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional parameters"
    )


class ExperimentRequest(BaseModel):
    """Request model for experiment processing."""

    name: str = Field(..., description="Name of the experiment", min_length=1)
    parameters: ExperimentParameters = Field(..., description="Experiment parameters")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "test_experiment",
                "parameters": {
                    "exposure_time": 0.1,
                    "laser_power": 50.0,
                    "num_frames": 100,
                },
            }
        }


class ProcessResult(BaseModel):
    """Result model for processed experiments."""

    status: str = Field(..., description="Processing status")
    experiment_name: str = Field(..., description="Name of the processed experiment")
    processed_data: Dict[str, Any] = Field(..., description="Processed experiment data")


class StatusResponse(BaseModel):
    """API status response."""

    status: str
    version: str = "1.0.0"
