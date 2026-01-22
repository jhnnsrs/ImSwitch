"""
Tests for API endpoints.
"""

import json


class TestStatusEndpoint:
    """Tests for the /status endpoint."""

    def test_status_returns_ok(self, client):
        """Test that status endpoint returns ok."""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"


class TestSchemaEndpoints:
    """Tests for JSON schema endpoints."""

    def test_request_schema_endpoint(self, client):
        """Test that request schema endpoint returns valid JSON schema."""
        response = client.get("/schema/request")
        assert response.status_code == 200
        schema = response.json()
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "parameters" in schema["properties"]
        assert schema["title"] == "ExperimentRequest"

    def test_response_schema_endpoint(self, client):
        """Test that response schema endpoint returns valid JSON schema."""
        response = client.get("/schema/response")
        assert response.status_code == 200
        schema = response.json()
        assert "properties" in schema
        assert "status" in schema["properties"]
        assert "experiment_name" in schema["properties"]
        assert "processed_data" in schema["properties"]
        assert schema["title"] == "ProcessResult"

    def test_request_schema_structure(self, client):
        """Test detailed structure of request schema."""
        response = client.get("/schema/request")
        schema = response.json()

        # Check name field
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["name"]["minLength"] == 1

        # Check parameters field
        assert (
            "$ref" in schema["properties"]["parameters"]
            or "allOf" in schema["properties"]["parameters"]
        )

    def test_response_schema_structure(self, client):
        """Test detailed structure of response schema."""
        response = client.get("/schema/response")
        schema = response.json()

        # Check required fields
        assert "required" in schema
        assert "status" in schema["required"]
        assert "experiment_name" in schema["required"]
        assert "processed_data" in schema["required"]


class TestProcessEndpoint:
    """Tests for the /process endpoint."""

    def test_process_basic_experiment(self, client):
        """Test processing a basic experiment."""
        request_data = {
            "name": "test_experiment",
            "parameters": {
                "exposure_time": 0.1,
                "laser_power": 50.0,
                "num_frames": 100,
            },
        }
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["experiment_name"] == "test_experiment"
        assert data["processed_data"]["exposure_time"] == 0.2
        assert data["processed_data"]["laser_power"] == 100.0
        assert data["processed_data"]["num_frames"] == 200

    def test_process_with_custom_params(self, client):
        """Test processing experiment with custom parameters."""
        request_data = {
            "name": "custom_experiment",
            "parameters": {
                "exposure_time": 0.5,
                "custom_params": {"temperature": 25.0, "humidity": "high"},
            },
        }
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["processed_data"]["exposure_time"] == 1.0
        assert data["processed_data"]["custom_temperature"] == 50.0
        assert data["processed_data"]["custom_humidity"] == "high"

    def test_process_only_custom_params(self, client):
        """Test processing with only custom parameters."""
        request_data = {
            "name": "only_custom",
            "parameters": {"custom_params": {"value1": 10, "value2": 20}},
        }
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["processed_data"]["custom_value1"] == 20
        assert data["processed_data"]["custom_value2"] == 40

    def test_process_empty_parameters(self, client):
        """Test processing with empty parameters."""
        request_data = {"name": "empty_params", "parameters": {}}
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["processed_data"] == {}

    def test_process_partial_parameters(self, client):
        """Test processing with partial parameters."""
        request_data = {
            "name": "partial_params",
            "parameters": {"exposure_time": 0.3, "num_frames": 50},
        }
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["processed_data"]["exposure_time"] == 0.6
        assert data["processed_data"]["num_frames"] == 100
        assert "laser_power" not in data["processed_data"]

    def test_process_invalid_name(self, client):
        """Test processing fails with invalid name."""
        request_data = {"name": "", "parameters": {}}
        response = client.post("/process", json=request_data)
        assert response.status_code == 422

    def test_process_missing_name(self, client):
        """Test processing fails without name."""
        request_data = {"parameters": {}}
        response = client.post("/process", json=request_data)
        assert response.status_code == 422

    def test_process_missing_parameters(self, client):
        """Test processing fails without parameters."""
        request_data = {"name": "test"}
        response = client.post("/process", json=request_data)
        assert response.status_code == 422


class TestActionsEndpoints:
    """Tests for action definition endpoints."""

    def test_list_actions(self, client):
        """Test listing all registered actions."""
        response = client.get("/actions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have registered actions from microscope_actions
        action_names = [a["name"] for a in data]
        assert "capture_image" in action_names
        assert "move_stage" in action_names

    def test_get_action_details(self, client):
        """Test getting details for a specific action."""
        response = client.get("/actions/capture_image")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "capture_image"
        assert "description" in data
        assert "args" in data
        assert "returns" in data

    def test_get_nonexistent_action(self, client):
        """Test getting an action that doesn't exist."""
        response = client.get("/actions/nonexistent_action")
        assert response.status_code == 404


class TestAssignationEndpoints:
    """Tests for action assignment and execution endpoints."""

    def test_assign_action(self, client):
        """Test assigning an action for execution."""
        response = client.post(
            "/actions/capture_image/assign",
            json={
                "args": {"exposure_time": 0.1, "resolution": [512, 512]},
                "reference": "test-ref-123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["action"] == "capture_image"
        assert data["status"] in ["pending", "assigned", "running", "done"]
        assert "created_at" in data
        assert data["reference"] == "test-ref-123"

    def test_assign_action_minimal(self, client):
        """Test assigning an action with minimal parameters."""
        response = client.post(
            "/actions/move_stage/assign",
            json={"args": {}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["action"] == "move_stage"

    def test_assign_nonexistent_action(self, client):
        """Test assigning an action that doesn't exist."""
        response = client.post(
            "/actions/nonexistent_action/assign",
            json={"args": {}},
        )
        assert response.status_code == 404

    def test_list_assignations(self, client):
        """Test listing all assignations."""
        # Create a few assignations first
        client.post("/actions/capture_image/assign", json={"args": {}})
        client.post("/actions/move_stage/assign", json={"args": {}})

        response = client.get("/assignations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_assignations_filtered_by_action(self, client):
        """Test listing assignations filtered by action name."""
        # Create an assignation
        create_response = client.post("/actions/adjust_focus/assign", json={"args": {}})
        assert create_response.status_code == 200
        assignation_id = create_response.json()["id"]

        # List filtered by action
        filtered_response = client.get("/assignations", params={"action": "adjust_focus"})
        assert filtered_response.status_code == 200
        filtered_data = filtered_response.json()
        assert isinstance(filtered_data, list)

        # Our assignation should be in the filtered results
        filtered_ids = [a["id"] for a in filtered_data]
        assert assignation_id in filtered_ids

    def test_get_assignation_by_id(self, client):
        """Test getting a specific assignation by ID."""
        # Create an assignation
        create_response = client.post(
            "/actions/capture_image/assign",
            json={"args": {"exposure_time": 0.5}},
        )
        assignation_id = create_response.json()["id"]

        # Get the assignation
        response = client.get(f"/assignations/{assignation_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == assignation_id
        assert data["action"] == "capture_image"

    def test_get_nonexistent_assignation(self, client):
        """Test getting an assignation that doesn't exist."""
        response = client.get("/assignations/nonexistent-id")
        assert response.status_code == 404

    def test_cancel_assignation(self, client):
        """Test cancelling an assignation."""
        # Create an assignation
        create_response = client.post("/actions/move_stage/assign", json={"args": {}})
        assignation_id = create_response.json()["id"]

        # Cancel the assignation
        response = client.delete(f"/assignations/{assignation_id}")
        # May succeed or fail depending on state
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert data["assignation_id"] == assignation_id

    def test_assignation_execution(self, client):
        """Test that assignations are executed by the agent."""
        import time

        # Create an assignation
        create_response = client.post(
            "/actions/capture_image/assign",
            json={"args": {"exposure_time": 0.1}},
        )
        assert create_response.status_code == 200
        assignation_id = create_response.json()["id"]

        # Wait a bit for execution
        time.sleep(1.5)

        # Check assignation status
        response = client.get(f"/assignations/{assignation_id}")
        data = response.json()
        # Assignation should be completed or running
        assert data["status"] in ["running", "done", "error"]

    def test_assignation_with_reference(self, client):
        """Test creating assignation with client reference."""
        response = client.post(
            "/actions/move_stage/assign",
            json={
                "args": {"x": 10, "y": 20, "z": 30},
                "reference": "my-custom-ref",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reference"] == "my-custom-ref"


class TestAPIDocumentation:
    """Tests for API documentation."""

    def test_openapi_schema_exists(self, client):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "Experiment Processing API"
        assert schema["info"]["version"] == "2.0.0"

    def test_docs_endpoint_exists(self, client):
        """Test that /docs endpoint is available."""
        response = client.get("/docs")
        assert response.status_code == 200


class TestEdgeCases:
    """Tests for edge cases."""

    def test_process_very_large_numbers(self, client):
        """Test processing with very large numbers."""
        request_data = {
            "name": "large_numbers",
            "parameters": {
                "exposure_time": 1e10,
                "laser_power": 1e15,
                "num_frames": 999999,
            },
        }
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["processed_data"]["exposure_time"] == 2e10
        assert data["processed_data"]["laser_power"] == 2e15
        assert data["processed_data"]["num_frames"] == 1999998

    def test_process_zero_values(self, client):
        """Test processing with zero values."""
        request_data = {
            "name": "zero_values",
            "parameters": {"exposure_time": 0, "laser_power": 0, "num_frames": 0},
        }
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["processed_data"]["exposure_time"] == 0
        assert data["processed_data"]["laser_power"] == 0
        assert data["processed_data"]["num_frames"] == 0

    def test_process_negative_values(self, client):
        """Test processing with negative values."""
        request_data = {
            "name": "negative_values",
            "parameters": {"exposure_time": -0.1, "num_frames": -100},
        }
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["processed_data"]["exposure_time"] == -0.2
        assert data["processed_data"]["num_frames"] == -200

    def test_process_mixed_custom_param_types(self, client):
        """Test processing with mixed types in custom params."""
        request_data = {
            "name": "mixed_types",
            "parameters": {
                "custom_params": {
                    "int_val": 10,
                    "float_val": 3.14,
                    "str_val": "hello",
                    "bool_val": True,
                    "list_val": [1, 2, 3],
                    "dict_val": {"nested": "value"},
                }
            },
        }
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["processed_data"]["custom_int_val"] == 20
        assert data["processed_data"]["custom_float_val"] == 6.28
        assert data["processed_data"]["custom_str_val"] == "hello"
        assert data["processed_data"]["custom_bool_val"] is True
        assert data["processed_data"]["custom_list_val"] == [1, 2, 3]
        assert data["processed_data"]["custom_dict_val"] == {"nested": "value"}

    def test_process_long_experiment_name(self, client):
        """Test processing with very long experiment name."""
        long_name = "a" * 1000
        request_data = {"name": long_name, "parameters": {}}
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["experiment_name"] == long_name

    def test_process_special_characters_in_name(self, client):
        """Test processing with special characters in name."""
        special_name = "test-exp_123!@#$%^&*()"
        request_data = {"name": special_name, "parameters": {}}
        response = client.post("/process", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["experiment_name"] == special_name
