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
)
from refactor.api.actors.fastapi_agent import AssignationState


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


class TestAssignationState:
    """Tests for AssignationState model."""

    def test_assignation_state_creation(self):
        """Test creating an assignation state."""
        state = AssignationState(id="test-id", interface="capture_image")
        assert state.interface == "capture_image"
        assert state.status == "pending"
        assert state.id == "test-id"

    def test_assignation_state_with_args(self):
        """Test assignation state with arguments."""
        state = AssignationState(
            id="test-id",
            interface="move_stage",
            args={"x": 10, "y": 20},
        )
        assert state.args == {"x": 10, "y": 20}

    def test_assignation_state_status_values(self):
        """Test AssignationState status values."""
        state = AssignationState(id="test-id", interface="test", status="pending")
        assert state.status == "pending"

        state.status = "running"
        assert state.status == "running"

        state.status = "done"
        assert state.status == "done"
