"""
Tests for ConnectionManager and EngineManager.
"""

from refactor.api import ConnectionManager, EngineManager


class TestConnectionManager:
    """Tests for the ConnectionManager class."""

    def test_initialization(self):
        """Test ConnectionManager initialization."""
        manager = ConnectionManager()
        assert manager.active_connections == []

    def test_has_required_methods(self):
        """Test ConnectionManager has required methods."""
        manager = ConnectionManager()
        assert hasattr(manager, "connect")
        assert hasattr(manager, "disconnect")
        assert hasattr(manager, "broadcast")
        assert hasattr(manager, "send_personal_message")


class TestEngineManager:
    """Tests for the EngineManager class."""

    def test_initialization(self):
        """Test EngineManager initialization."""
        conn_manager = ConnectionManager()
        engine = EngineManager(conn_manager)
        assert engine.tasks == {}
        assert engine.connection_manager == conn_manager
        assert engine.is_running is False

    def test_has_required_methods(self):
        """Test EngineManager has required methods."""
        conn_manager = ConnectionManager()
        engine = EngineManager(conn_manager)
        assert hasattr(engine, "start")
        assert hasattr(engine, "stop")
        assert hasattr(engine, "schedule_task")
        assert hasattr(engine, "cancel_task")
        assert hasattr(engine, "get_task")
        assert hasattr(engine, "list_tasks")
