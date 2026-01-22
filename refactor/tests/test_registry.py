"""Tests for the rekuest_next DefinitionRegistry and @register decorator integration."""

import pytest
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.register import register


class TestDefinitionRegistry:
    """Tests for rekuest_next's DefinitionRegistry class."""

    def test_create_registry(self):
        """Test creating an empty registry."""
        registry = DefinitionRegistry()
        assert len(registry.templates) == 0

    def test_registry_has_templates_dict(self):
        """Test registry has templates attribute."""
        registry = DefinitionRegistry()
        assert hasattr(registry, "templates")
        assert hasattr(registry, "actor_builders")

    def test_registry_has_actor_builders(self):
        """Test registry stores actor builders."""
        registry = DefinitionRegistry()
        assert hasattr(registry, "actor_builders")
        assert isinstance(registry.actor_builders, dict)


class TestRegisterDecorator:
    """Tests for the rekuest_next @register decorator."""

    def test_decorator_registers_async_function(self):
        """Test that @register decorator registers async functions."""
        registry = DefinitionRegistry()
        struct_registry = StructureRegistry()

        @register(definition_registry=registry, structure_registry=struct_registry)
        async def my_async_action(value: float = 1.0) -> float:
            """Multiply by two."""
            return value * 2

        # Check function is registered
        assert "my_async_action" in registry.templates
        template = registry.templates["my_async_action"]
        assert template.definition.name == "My Async Action"  # Title-cased
        assert "Multiply by two." in template.definition.description

    def test_decorator_registers_with_collections(self):
        """Test that @register captures collections."""
        registry = DefinitionRegistry()
        struct_registry = StructureRegistry()

        @register(
            definition_registry=registry,
            structure_registry=struct_registry,
            collections=["test", "example"],
        )
        async def tagged_action() -> str:
            """A tagged action."""
            return "done"

        template = registry.templates["tagged_action"]
        assert "test" in template.definition.collections
        assert "example" in template.definition.collections

    def test_decorator_extracts_args_from_signature(self):
        """Test that @register extracts parameter info from signature."""
        registry = DefinitionRegistry()
        struct_registry = StructureRegistry()

        @register(definition_registry=registry, structure_registry=struct_registry)
        async def action_with_args(
            x: int = 0,
            name: str = "default",
            enabled: bool = True,
        ) -> dict:
            """An action with multiple arguments."""
            return {"x": x, "name": name, "enabled": enabled}

        template = registry.templates["action_with_args"]
        defn = template.definition

        # Check args are extracted
        assert len(defn.args) == 3
        arg_keys = [arg.key for arg in defn.args]
        assert "x" in arg_keys
        assert "name" in arg_keys
        assert "enabled" in arg_keys

    def test_decorator_creates_actor_builder(self):
        """Test that @register creates an actor builder."""
        registry = DefinitionRegistry()
        struct_registry = StructureRegistry()

        @register(definition_registry=registry, structure_registry=struct_registry)
        async def buildable_action() -> str:
            """An action with a builder."""
            return "built"

        # Check actor builder was created
        assert "buildable_action" in registry.actor_builders
        builder = registry.actor_builders["buildable_action"]
        assert callable(builder)

    def test_multiple_registrations(self):
        """Test registering multiple functions."""
        registry = DefinitionRegistry()
        struct_registry = StructureRegistry()

        @register(definition_registry=registry, structure_registry=struct_registry)
        async def action_one() -> str:
            """First action."""
            return "one"

        @register(definition_registry=registry, structure_registry=struct_registry)
        async def action_two() -> str:
            """Second action."""
            return "two"

        @register(definition_registry=registry, structure_registry=struct_registry)
        async def action_three() -> str:
            """Third action."""
            return "three"

        assert len(registry.templates) == 3
        assert "action_one" in registry.templates
        assert "action_two" in registry.templates
        assert "action_three" in registry.templates


class TestMicroscopeActionsRegistry:
    """Tests for the microscope_actions module registration."""

    def test_microscope_actions_registered(self):
        """Test that microscope actions are registered on import."""
        from refactor.api.microscope_actions import definition_registry

        # Check that actions are registered
        assert "capture_image" in definition_registry.templates
        assert "move_stage" in definition_registry.templates
        assert "set_laser_power" in definition_registry.templates

    def test_microscope_action_has_definition(self):
        """Test that registered microscope actions have proper definitions."""
        from refactor.api.microscope_actions import definition_registry

        template = definition_registry.templates["capture_image"]
        defn = template.definition

        assert defn.name == "Capture Image"  # Title-cased from function name
        assert "camera" in defn.collections or "imaging" in defn.collections

    def test_microscope_action_has_builder(self):
        """Test that registered microscope actions have actor builders."""
        from refactor.api.microscope_actions import definition_registry

        assert "capture_image" in definition_registry.actor_builders
        builder = definition_registry.actor_builders["capture_image"]
        assert callable(builder)
