"""
Action registry for microscope actions.

This module provides a decorator-based registry for registering
microscope actions that can be executed by the EngineManager.
"""

from __future__ import annotations

import asyncio
from typing import Dict, Any, Callable, Awaitable, Optional, TypeVar, ParamSpec
from functools import wraps
from dataclasses import dataclass, field

P = ParamSpec("P")
R = TypeVar("R")

# Type for action handler functions
ActionHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class ActionInfo:
    """Information about a registered action."""

    name: str
    handler: ActionHandler
    description: str = ""
    parameters_schema: Optional[Dict[str, Any]] = None
    tags: list[str] = field(default_factory=list)


class ActionRegistry:
    """
    Registry for microscope actions.

    Actions can be registered using the @register decorator and then
    executed by the EngineManager.
    """

    def __init__(self):
        self._actions: Dict[str, ActionInfo] = {}

    def register(
        self,
        name: Optional[str] = None,
        description: str = "",
        parameters_schema: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> Callable[[ActionHandler], ActionHandler]:
        """
        Decorator to register an action handler.

        Args:
            name: Action name (defaults to function name)
            description: Human-readable description
            parameters_schema: JSON schema for parameters
            tags: List of tags for categorization

        Returns:
            Decorator function

        Example:
            @registry.register(name="capture_image", description="Capture an image")
            async def capture_image(params: Dict[str, Any]) -> Dict[str, Any]:
                return {"image_id": "abc123"}
        """

        def decorator(func: ActionHandler) -> ActionHandler:
            action_name = name or func.__name__
            action_info = ActionInfo(
                name=action_name,
                handler=func,
                description=description or func.__doc__ or "",
                parameters_schema=parameters_schema,
                tags=tags or [],
            )
            self._actions[action_name] = action_info

            @wraps(func)
            async def wrapper(params: Dict[str, Any]) -> Dict[str, Any]:
                return await func(params)

            return wrapper

        return decorator

    def get(self, name: str) -> Optional[ActionInfo]:
        """Get action info by name."""
        return self._actions.get(name)

    def has(self, name: str) -> bool:
        """Check if action is registered."""
        return name in self._actions

    async def execute(self, name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a registered action.

        Args:
            name: Action name
            parameters: Action parameters

        Returns:
            Action result

        Raises:
            ValueError: If action is not registered
        """
        action_info = self._actions.get(name)
        if not action_info:
            raise ValueError(f"Action '{name}' is not registered")
        return await action_info.handler(parameters)

    def list_actions(self) -> list[ActionInfo]:
        """List all registered actions."""
        return list(self._actions.values())

    def get_actions_by_tag(self, tag: str) -> list[ActionInfo]:
        """Get actions by tag."""
        return [a for a in self._actions.values() if tag in a.tags]


# Global action registry instance
action_registry = ActionRegistry()


# Convenience decorator for the global registry
def register(
    name: Optional[str] = None,
    description: str = "",
    parameters_schema: Optional[Dict[str, Any]] = None,
    tags: Optional[list[str]] = None,
) -> Callable[[ActionHandler], ActionHandler]:
    """
    Decorator to register an action with the global registry.

    Example:
        @register(name="capture_image", description="Capture an image from camera")
        async def capture_image(params: Dict[str, Any]) -> Dict[str, Any]:
            exposure = params.get("exposure_time", 0.1)
            return {"image_id": "abc123", "exposure": exposure}
    """
    return action_registry.register(
        name=name,
        description=description,
        parameters_schema=parameters_schema,
        tags=tags,
    )
