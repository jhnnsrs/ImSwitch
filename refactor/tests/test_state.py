"""Tests for the StateProxy functionality."""

import pytest
from refactor.api.state import StateProxy, StateSnapshot
from refactor.api.managers import ConnectionManager

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestStateProxy:
    """Tests for StateProxy class."""

    @pytest.fixture
    def connection_manager(self):
        """Create a connection manager for testing."""
        return ConnectionManager()

    @pytest.fixture
    def state_proxy(self, connection_manager):
        """Create a state proxy for testing."""
        return StateProxy(connection_manager, broadcast_interval=0.01)

    async def test_set_and_get(self, state_proxy):
        """Test setting and getting state values."""
        await state_proxy.set("key1", "value1")
        result = await state_proxy.get("key1")
        assert result == "value1"

    async def test_set_nested_key(self, state_proxy):
        """Test setting nested keys with dot notation."""
        await state_proxy.set("level1.level2.key", "nested_value")
        result = await state_proxy.get("level1.level2.key")
        assert result == "nested_value"

        # Also check the full structure
        level1 = await state_proxy.get("level1")
        assert level1 == {"level2": {"key": "nested_value"}}

    async def test_get_entire_state(self, state_proxy):
        """Test getting the entire state."""
        await state_proxy.set("key1", "value1")
        await state_proxy.set("key2", "value2")
        state = await state_proxy.get()
        assert state == {"key1": "value1", "key2": "value2"}

    async def test_get_default_value(self, state_proxy):
        """Test getting default value for missing key."""
        result = await state_proxy.get("missing", default="default_value")
        assert result == "default_value"

    async def test_set_many(self, state_proxy):
        """Test setting multiple values at once."""
        await state_proxy.set_many({"key1": "value1", "key2": 42, "key3": True})
        assert await state_proxy.get("key1") == "value1"
        assert await state_proxy.get("key2") == 42
        assert await state_proxy.get("key3") is True

    async def test_delete(self, state_proxy):
        """Test deleting a state key."""
        await state_proxy.set("to_delete", "value")
        assert await state_proxy.get("to_delete") == "value"

        success = await state_proxy.delete("to_delete")
        assert success is True
        assert await state_proxy.get("to_delete") is None

    async def test_delete_nonexistent_key(self, state_proxy):
        """Test deleting a key that doesn't exist."""
        success = await state_proxy.delete("nonexistent")
        assert success is False

    async def test_delete_nested_key(self, state_proxy):
        """Test deleting a nested key."""
        await state_proxy.set("parent.child", "value")
        success = await state_proxy.delete("parent.child")
        assert success is True

        parent = await state_proxy.get("parent")
        assert parent == {}

    async def test_clear(self, state_proxy):
        """Test clearing all state."""
        await state_proxy.set("key1", "value1")
        await state_proxy.set("key2", "value2")
        await state_proxy.clear()
        state = await state_proxy.get()
        assert state == {}

    async def test_get_snapshot(self, state_proxy):
        """Test getting a state snapshot."""
        await state_proxy.set("key1", "value1")
        snapshot = await state_proxy.get_snapshot()

        assert isinstance(snapshot, StateSnapshot)
        assert snapshot.state == {"key1": "value1"}
        assert snapshot.version >= 1

    async def test_version_increments(self, state_proxy):
        """Test that version increments on updates."""
        initial_version = state_proxy.version
        await state_proxy.set("key1", "value1")
        assert state_proxy.version == initial_version + 1

        await state_proxy.set("key2", "value2")
        assert state_proxy.version == initial_version + 2

    async def test_start_and_stop(self, state_proxy):
        """Test starting and stopping the broadcast loop."""
        await state_proxy.start()
        assert state_proxy._is_running is True
        assert state_proxy._broadcast_task is not None

        await state_proxy.stop()
        assert state_proxy._is_running is False


class TestStateEndpoints:
    """Tests for state API endpoints."""

    def test_get_state_empty(self, client):
        """Test getting empty state."""
        response = client.get("/state")
        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert "version" in data
        assert "timestamp" in data

    def test_update_state(self, client):
        """Test updating state via PUT."""
        response = client.put(
            "/state", json={"key": "test_key", "value": "test_value", "immediate": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["test_key"] == "test_value"

    def test_update_nested_state(self, client):
        """Test updating nested state."""
        response = client.put(
            "/state", json={"key": "parent.child.value", "value": 42, "immediate": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["parent"]["child"]["value"] == 42

    def test_batch_update_state(self, client):
        """Test batch updating state via PATCH."""
        response = client.patch(
            "/state",
            json={
                "updates": {"key1": "value1", "key2": 100, "key3": ["a", "b", "c"]},
                "immediate": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["key1"] == "value1"
        assert data["state"]["key2"] == 100
        assert data["state"]["key3"] == ["a", "b", "c"]

    def test_get_state_with_key(self, client):
        """Test getting specific key from state."""
        # First set a value
        client.put("/state", json={"key": "specific_key", "value": "specific_value"})

        # Then get that specific key
        response = client.get("/state?key=specific_key")
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["specific_key"] == "specific_value"

    def test_delete_state(self, client):
        """Test deleting a state key."""
        # First set a value
        client.put("/state", json={"key": "to_delete", "value": "value"})

        # Then delete it
        response = client.delete("/state/to_delete")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_nonexistent_state(self, client):
        """Test deleting a nonexistent key returns 404."""
        response = client.delete("/state/definitely_does_not_exist_12345")
        assert response.status_code == 404
