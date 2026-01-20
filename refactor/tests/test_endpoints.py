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
        assert data["version"] == "1.0.0"


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


class TestTaskEndpoints:
    """Tests for task management endpoints."""

    def test_create_task(self, client):
        """Test creating a new task."""
        response = client.post(
            "/tasks",
            json={
                "name": "capture_test",
                "action": "capture_image",
                "parameters": {"exposure_time": 0.1},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "capture_test"
        assert data["action"] == "capture_image"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_list_tasks(self, client):
        """Test listing all tasks."""
        # Create a few tasks
        client.post("/tasks", json={"name": "task1", "action": "capture_image"})
        client.post("/tasks", json={"name": "task2", "action": "move_stage"})

        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_tasks_filtered_by_status(self, client):
        """Test listing tasks filtered by status."""
        # Create a task
        create_response = client.post(
            "/tasks", json={"name": "pending_task", "action": "adjust_focus"}
        )
        assert create_response.status_code == 200
        task_data = create_response.json()

        # List all tasks first to see what we have
        all_tasks_response = client.get("/tasks")
        assert all_tasks_response.status_code == 200
        all_tasks = all_tasks_response.json()

        # Task should exist in all tasks
        task_ids = [t["id"] for t in all_tasks]
        assert task_data["id"] in task_ids

        # Find our task status
        our_task = next((t for t in all_tasks if t["id"] == task_data["id"]), None)
        assert our_task is not None
        task_status = our_task["status"]

        # Now test status filtering - filter by the actual status our task has
        filtered_response = client.get("/tasks", params={"status": task_status})
        assert filtered_response.status_code == 200
        filtered_data = filtered_response.json()
        assert isinstance(filtered_data, list)

        # Our task should be in the filtered results
        filtered_ids = [t["id"] for t in filtered_data]
        assert task_data["id"] in filtered_ids

    def test_get_task_by_id(self, client):
        """Test getting a specific task by ID."""
        # Create a task
        create_response = client.post(
            "/tasks", json={"name": "specific_task", "action": "capture_image"}
        )
        task_data = create_response.json()
        task_id = task_data["id"]

        # Get the task
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["name"] == "specific_task"

    def test_get_nonexistent_task(self, client):
        """Test getting a task that doesn't exist."""
        response = client.get("/tasks/nonexistent-id")
        assert response.status_code == 404

    def test_cancel_task(self, client):
        """Test cancelling a task."""
        # Create a task
        create_response = client.post("/tasks", json={"name": "cancel_me", "action": "move_stage"})
        task_id = create_response.json()["id"]

        # Cancel the task
        response = client.delete(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == task_id

    def test_task_execution(self, client):
        """Test that tasks are executed by the engine."""
        import time

        # Create a task
        create_response = client.post(
            "/tasks",
            json={
                "name": "execute_me",
                "action": "capture_image",
                "parameters": {"exposure_time": 0.1, "resolution": [512, 512]},
            },
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]

        # Wait a bit for task to be processed
        time.sleep(1.5)

        # Check task status
        response = client.get(f"/tasks/{task_id}")
        data = response.json()
        # Task should be completed or running
        assert data["status"] in ["completed", "running"]

    def test_task_with_parameters(self, client):
        """Test creating task with custom parameters."""
        response = client.post(
            "/tasks",
            json={
                "name": "parameterized_task",
                "action": "move_stage",
                "parameters": {"position": [10, 20, 30]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["parameters"]["position"] == [10, 20, 30]


class TestAPIDocumentation:
    """Tests for API documentation."""

    def test_openapi_schema_exists(self, client):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "Experiment Processing API"
        assert schema["info"]["version"] == "1.0.0"

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
