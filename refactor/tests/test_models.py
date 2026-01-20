"""
Tests for Pydantic models.
"""

import pytest
from pydantic import ValidationError

from refactor.api import (
    ExperimentParameters,
    ExperimentRequest,
    ProcessResult,
    StatusResponse,
    Task,
    TaskStatus,
)


class TestStatusResponse:
    """Tests for StatusResponse model."""

    def test_status_response_model(self):
        """Test StatusResponse model."""
        status = StatusResponse(status="ok")
        assert status.status == "ok"
        assert status.version == "1.0.0"

    def test_status_response_custom_version(self):
        """Test StatusResponse with custom version."""
        status = StatusResponse(status="ok", version="2.0.0")
        assert status.version == "2.0.0"


class TestExperimentParameters:
    """Tests for ExperimentParameters model."""

    def test_all_fields(self):
        """Test ExperimentParameters with all fields."""
        params = ExperimentParameters(
            exposure_time=0.1,
            laser_power=50.0,
            num_frames=100,
            custom_params={"key": "value"},
        )
        assert params.exposure_time == 0.1
        assert params.laser_power == 50.0
        assert params.num_frames == 100
        assert params.custom_params == {"key": "value"}

    def test_optional_fields(self):
        """Test ExperimentParameters with optional fields."""
        params = ExperimentParameters()
        assert params.exposure_time is None
        assert params.laser_power is None
        assert params.num_frames is None
        assert params.custom_params == {}

    def test_partial_fields(self):
        """Test ExperimentParameters with some fields."""
        params = ExperimentParameters(exposure_time=0.5, num_frames=50)
        assert params.exposure_time == 0.5
        assert params.laser_power is None
        assert params.num_frames == 50


class TestExperimentRequest:
    """Tests for ExperimentRequest model."""

    def test_valid_request(self):
        """Test ExperimentRequest with valid data."""
        params = ExperimentParameters(exposure_time=0.1)
        request = ExperimentRequest(name="test_exp", parameters=params)
        assert request.name == "test_exp"
        assert request.parameters.exposure_time == 0.1

    def test_empty_name_fails(self):
        """Test ExperimentRequest fails with empty name."""
        params = ExperimentParameters()
        with pytest.raises(ValidationError):
            ExperimentRequest(name="", parameters=params)

    def test_missing_name_fails(self):
        """Test ExperimentRequest fails without name."""
        params = ExperimentParameters()
        with pytest.raises(ValidationError):
            ExperimentRequest(parameters=params)


class TestProcessResult:
    """Tests for ProcessResult model."""

    def test_process_result_model(self):
        """Test ProcessResult model."""
        result = ProcessResult(
            status="success",
            experiment_name="test",
            processed_data={"exposure_time": 0.2},
        )
        assert result.status == "success"
        assert result.experiment_name == "test"
        assert result.processed_data["exposure_time"] == 0.2


class TestTask:
    """Tests for Task model."""

    def test_task_creation(self):
        """Test creating a task."""
        task = Task(name="test_task", action="capture_image")
        assert task.name == "test_task"
        assert task.action == "capture_image"
        assert task.status == TaskStatus.PENDING
        assert task.id is not None

    def test_task_with_parameters(self):
        """Test task with parameters."""
        task = Task(
            name="parameterized",
            action="move_stage",
            parameters={"x": 10, "y": 20},
        )
        assert task.parameters == {"x": 10, "y": 20}

    def test_task_status_enum(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
