"""
Definition Registry for action definitions.

This module provides the registry for storing action definitions
and their corresponding actor builders.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, ParamSpec, TypeVar, Union, overload

from pydantic import BaseModel, Field

from .functional import create_functional_actor_builder, ActionFunction

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class PortInfo(BaseModel):
    """Information about an input/output port."""

    key: str = Field(..., description="Parameter name")
    type: str = Field("any", description="Type name")
    description: str = Field("", description="Parameter description")
    required: bool = Field(True, description="Whether parameter is required")
    default: Any = Field(None, description="Default value")


class DefinitionInput(BaseModel):
    """
    Definition of an action that can be executed.

    Contains all metadata needed to describe and validate the action.
    """

    name: str = Field(..., description="Action name/identifier")
    description: str = Field("", description="Human-readable description")
    args: List[PortInfo] = Field(default_factory=list, description="Input parameters")
    returns: List[PortInfo] = Field(default_factory=list, description="Output values")
    is_generator: bool = Field(False, description="Whether action yields multiple results")
    collections: List[str] = Field(default_factory=list, description="Tags/categories")


class DefinitionRegistry(BaseModel):
    """
    Registry for action definitions and their actor builders.

    Stores all registered actions and provides builders to create
    actors for executing them.
    """

    definitions: Dict[str, DefinitionInput] = Field(default_factory=dict)
    actor_builders: Dict[str, Callable] = Field(default_factory=dict, exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def register(
        self,
        name: str,
        definition: DefinitionInput,
        actor_builder: Callable,
    ) -> None:
        """
        Register an action definition with its actor builder.

        Args:
            name: Action name
            definition: Action definition metadata
            actor_builder: Function to create an actor for this action
        """
        self.definitions[name] = definition
        self.actor_builders[name] = actor_builder
        logger.debug(f"Registered action: {name}")

    def get_definition(self, name: str) -> Optional[DefinitionInput]:
        """Get definition by name."""
        return self.definitions.get(name)

    def get_builder(self, name: str) -> Optional[Callable]:
        """Get actor builder by action name."""
        return self.actor_builders.get(name)

    def has(self, name: str) -> bool:
        """Check if action is registered."""
        return name in self.definitions

    def list_definitions(self) -> List[DefinitionInput]:
        """List all registered definitions."""
        return list(self.definitions.values())

    def get_by_collection(self, collection: str) -> List[DefinitionInput]:
        """Get definitions by collection/tag."""
        return [d for d in self.definitions.values() if collection in d.collections]


# Global default registry
_default_registry: Optional[DefinitionRegistry] = None


def get_default_definition_registry() -> DefinitionRegistry:
    """Get the default global definition registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = DefinitionRegistry()
    return _default_registry


def _extract_definition(
    func: Callable,
    name: Optional[str] = None,
    description: Optional[str] = None,
    collections: Optional[List[str]] = None,
) -> DefinitionInput:
    """
    Extract definition metadata from a function.

    Inspects the function signature and docstring to build
    a DefinitionInput.
    """
    func_name = name or func.__name__
    func_doc = description or func.__doc__ or ""

    # Inspect signature for args
    sig = inspect.signature(func)
    args = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        # Get type annotation
        param_type = "any"
        if param.annotation != inspect.Parameter.empty:
            if hasattr(param.annotation, "__name__"):
                param_type = param.annotation.__name__
            else:
                param_type = str(param.annotation)

        # Check for default
        has_default = param.default != inspect.Parameter.empty
        default_val = param.default if has_default else None

        args.append(
            PortInfo(
                key=param_name,
                type=param_type,
                required=not has_default,
                default=default_val,
            )
        )

    # Check if generator
    is_gen = inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func)

    # Get return type
    returns = []
    if sig.return_annotation != inspect.Signature.empty:
        ret_type = sig.return_annotation
        if hasattr(ret_type, "__name__"):
            returns.append(PortInfo(key="value", type=ret_type.__name__))

    return DefinitionInput(
        name=func_name,
        description=func_doc.strip(),
        args=args,
        returns=returns,
        is_generator=is_gen,
        collections=collections or [],
    )


class WrappedFunction:
    """
    A wrapped function with its definition attached.

    Calling this directly calls the underlying function.
    """

    def __init__(
        self,
        func: Callable,
        name: str,
        definition: DefinitionInput,
    ):
        self.func = func
        self.name = name
        self.definition = definition

    def __call__(self, *args, **kwargs):
        """Call the underlying function directly."""
        return self.func(*args, **kwargs)

    async def acall(self, *args, **kwargs):
        """Call the underlying function (async)."""
        if inspect.iscoroutinefunction(self.func):
            return await self.func(*args, **kwargs)
        return self.func(*args, **kwargs)


@overload
def register(func: Callable[P, R]) -> WrappedFunction: ...


@overload
def register(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    collections: Optional[List[str]] = None,
    registry: Optional[DefinitionRegistry] = None,
) -> Callable[[Callable[P, R]], WrappedFunction]: ...


def register(
    func: Optional[Callable[P, R]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    collections: Optional[List[str]] = None,
    registry: Optional[DefinitionRegistry] = None,
) -> Union[WrappedFunction, Callable[[Callable[P, R]], WrappedFunction]]:
    """
    Decorator to register a function as an action.

    Can be used with or without arguments:

        @register
        async def my_action(x: int) -> dict:
            return {"result": x * 2}

        @register(name="custom_name", collections=["imaging"])
        async def capture_image(exposure: float = 0.1) -> dict:
            return {"image_id": "abc123"}

    Args:
        func: Function to register (when used without arguments)
        name: Action name (defaults to function name)
        description: Human-readable description
        collections: Tags/categories for the action
        registry: Registry to use (defaults to global)

    Returns:
        Wrapped function with definition attached
    """
    reg = registry or get_default_definition_registry()

    def decorator(fn: Callable[P, R]) -> WrappedFunction:
        action_name = name or fn.__name__

        # Extract definition from function
        definition = _extract_definition(
            fn,
            name=action_name,
            description=description,
            collections=collections,
        )

        # Create actor builder
        actor_builder = create_functional_actor_builder(fn, action_name)

        # Register
        reg.register(action_name, definition, actor_builder)

        # Return wrapped function
        return WrappedFunction(fn, action_name, definition)

    # Handle @register vs @register()
    if func is not None:
        return decorator(func)
    return decorator
