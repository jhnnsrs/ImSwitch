"""Tests for the ActionRegistry functionality."""

import pytest
from refactor.api.registry import ActionRegistry, register, action_registry

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestActionRegistry:
    """Tests for ActionRegistry class."""

    def test_create_registry(self):
        """Test creating an empty registry."""
        registry = ActionRegistry()
        assert len(registry.list_actions()) == 0

    def test_register_action(self):
        """Test registering an action."""
        registry = ActionRegistry()

        @registry.register(
            name="my_action",
            description="A test action",
            parameters_schema={"type": "object"},
            tags=["test"],
        )
        async def my_action(params):
            return {"result": "success"}

        assert registry.has("my_action")
        info = registry.get("my_action")
        assert info.name == "my_action"
        assert info.description == "A test action"
        assert "test" in info.tags

    def test_has_action(self):
        """Test checking if action exists."""
        registry = ActionRegistry()

        @registry.register(name="exists")
        async def my_action(params):
            return {}

        assert registry.has("exists") is True
        assert registry.has("does_not_exist") is False

    def test_get_nonexistent_action(self):
        """Test getting a nonexistent action returns None."""
        registry = ActionRegistry()
        assert registry.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_execute_action(self):
        """Test executing a registered action."""
        registry = ActionRegistry()

        @registry.register(name="double")
        async def double_action(params):
            return {"doubled": params.get("value", 0) * 2}

        result = await registry.execute("double", {"value": 21})
        assert result == {"doubled": 42}

    @pytest.mark.asyncio
    async def test_execute_nonexistent_action(self):
        """Test executing nonexistent action raises error."""
        registry = ActionRegistry()

        with pytest.raises(ValueError, match="Action 'missing' is not registered"):
            await registry.execute("missing", {})

    def test_list_actions(self):
        """Test listing all actions."""
        registry = ActionRegistry()

        @registry.register(name="action1")
        async def action1(params):
            return {}

        @registry.register(name="action2")
        async def action2(params):
            return {}

        actions = registry.list_actions()
        names = [a.name for a in actions]
        assert "action1" in names
        assert "action2" in names
        assert len(actions) == 2

    def test_get_actions_by_tag(self):
        """Test filtering actions by tag."""
        registry = ActionRegistry()

        @registry.register(name="action1", tags=["camera", "acquisition"])
        async def action1(params):
            return {}

        @registry.register(name="action2", tags=["stage", "movement"])
        async def action2(params):
            return {}

        @registry.register(name="action3", tags=["camera", "settings"])
        async def action3(params):
            return {}

        camera_actions = registry.get_actions_by_tag("camera")
        names = [a.name for a in camera_actions]
        assert "action1" in names
        assert "action3" in names
        assert "action2" not in names
        assert len(camera_actions) == 2


class TestRegisterDecorator:
    """Tests for the @register decorator."""

    def test_decorator_registers_action(self):
        """Test that @register decorator registers action in global registry."""
        # The global registry should have built-in actions
        assert action_registry.has("capture_image")
        assert action_registry.has("move_stage")
        assert action_registry.has("adjust_focus")
        assert action_registry.has("set_laser_power")
        assert action_registry.has("acquire_z_stack")

    def test_custom_register_decorator(self):
        """Test creating a custom register decorator for a new registry."""
        custom_registry = ActionRegistry()

        @custom_registry.register(
            name="custom_action", description="A custom action", tags=["custom"]
        )
        async def custom_action(params):
            return {"custom": True}

        assert custom_registry.has("custom_action")
        info = custom_registry.get("custom_action")
        assert info.description == "A custom action"
        assert "custom" in info.tags


class TestBuiltInActions:
    """Tests for the built-in registered actions."""

    @pytest.mark.asyncio
    async def test_capture_image_action(self):
        """Test capture_image action execution."""
        result = await action_registry.execute(
            "capture_image", {"exposure_time": 0.2, "resolution": [2048, 2048]}
        )
        assert "image_id" in result
        assert result["exposure_time"] == 0.2
        assert result["resolution"] == [2048, 2048]

    @pytest.mark.asyncio
    async def test_move_stage_action(self):
        """Test move_stage action execution."""
        result = await action_registry.execute("move_stage", {"position": [10, 20, 5]})
        assert result["position"] == [10, 20, 5]
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_adjust_focus_action(self):
        """Test adjust_focus action execution."""
        result = await action_registry.execute("adjust_focus", {"z_position": 15.5})
        assert result["focus_position"] == 15.5
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_set_laser_power_action(self):
        """Test set_laser_power action execution."""
        result = await action_registry.execute(
            "set_laser_power", {"laser_id": "488nm", "power": 75.0}
        )
        assert result["laser_id"] == "488nm"
        assert result["power"] == 75.0
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_acquire_z_stack_action(self):
        """Test acquire_z_stack action execution."""
        result = await action_registry.execute(
            "acquire_z_stack", {"z_start": 0, "z_end": 10, "z_step": 1, "exposure_time": 0.1}
        )
        assert result["z_start"] == 0
        assert result["z_end"] == 10
        # (10 - 0) / 1 + 1 = 11 slices
        assert result["num_slices"] == 11
        assert "stack_id" in result


class TestActionsEndpoints:
    """Tests for actions API endpoints."""

    def test_list_actions(self, client):
        """Test listing all registered actions."""
        response = client.get("/actions")
        assert response.status_code == 200
        actions = response.json()
        assert isinstance(actions, list)

        # Should have built-in actions
        names = [a["name"] for a in actions]
        assert "capture_image" in names
        assert "move_stage" in names

    def test_list_actions_by_tag(self, client):
        """Test listing actions filtered by tag."""
        response = client.get("/actions?tag=camera")
        assert response.status_code == 200
        actions = response.json()

        # All returned actions should have the camera tag
        for action in actions:
            assert "camera" in action["tags"]

    def test_get_action_details(self, client):
        """Test getting details of a specific action."""
        response = client.get("/actions/capture_image")
        assert response.status_code == 200
        action = response.json()
        assert action["name"] == "capture_image"
        assert "description" in action
        assert "parameters_schema" in action

    def test_get_nonexistent_action(self, client):
        """Test getting a nonexistent action returns 404."""
        response = client.get("/actions/nonexistent_action")
        assert response.status_code == 404

    def test_execute_action(self, client):
        """Test executing an action directly."""
        response = client.post(
            "/actions/capture_image/execute",
            json={"action": "capture_image", "parameters": {"exposure_time": 0.5}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "capture_image"
        assert "result" in data

    def test_execute_nonexistent_action(self, client):
        """Test executing a nonexistent action returns 404."""
        response = client.post(
            "/actions/nonexistent/execute", json={"action": "nonexistent", "parameters": {}}
        )
        assert response.status_code == 404
