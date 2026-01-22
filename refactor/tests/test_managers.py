"""
Tests for ConnectionManager and FastAPIAgent.
"""

from refactor.api import ConnectionManager, FastAPIAgent, DefinitionRegistry


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


class TestFastAPIAgent:
    """Tests for the FastAPIAgent class."""

    def test_initialization(self):
        """Test FastAPIAgent initialization."""
        registry = DefinitionRegistry()
        agent = FastAPIAgent(
            definition_registry=registry,
        )
        assert agent.managed_actors == {}
        assert agent.managed_assignments == {}
        assert agent.definition_registry == registry

    def test_has_required_methods(self):
        """Test FastAPIAgent has required methods."""
        registry = DefinitionRegistry()
        agent = FastAPIAgent(definition_registry=registry)
        assert hasattr(agent, "assign")
        assert hasattr(agent, "cancel")
        assert hasattr(agent, "get_assignation")
        assert hasattr(agent, "asend")
