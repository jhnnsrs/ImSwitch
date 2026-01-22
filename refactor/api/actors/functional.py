"""
Functional Actor implementation.

This actor type wraps a Python function (sync or async) and executes it
when an assignment is received. Inspired by rekuest-next's FunctionalActor.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, Dict, Optional, Union

from pydantic import Field

from .base import Actor
from . import messages

logger = logging.getLogger(__name__)

# Type alias for action functions
ActionFunction = Callable[..., Any]


class FunctionalActor(Actor):
    """
    An actor that wraps a function for execution.

    Supports both sync and async functions. Sync functions are
    executed in a thread pool to avoid blocking.
    """

    func: Callable = Field(..., description="The function to execute")
    is_async: bool = Field(False, description="Whether the function is async")
    is_generator: bool = Field(False, description="Whether the function is a generator")
    executor: Optional[ThreadPoolExecutor] = Field(
        None, description="Thread pool for sync functions"
    )

    model_config = {"arbitrary_types_allowed": True}

    async def on_assign(self, assignment: messages.Assign) -> None:
        """
        Execute the wrapped function with the assignment args.
        """
        try:
            # Log start
            await self.asend(
                messages.LogEvent(
                    assignation=assignment.assignation,
                    message=f"Starting execution of {self.action}",
                    level="INFO",
                )
            )

            # Execute the function
            if self.is_generator:
                await self._execute_generator(assignment)
            else:
                await self._execute_function(assignment)

        except asyncio.CancelledError:
            raise  # Let the base class handle cancellation

        except Exception as e:
            logger.exception(f"Error executing {self.action}")
            await self.asend(
                messages.CriticalEvent(
                    assignation=assignment.assignation,
                    error=str(e),
                )
            )

    async def _execute_function(self, assignment: messages.Assign) -> None:
        """Execute a regular function."""
        if self.is_async:
            result = await self.func(**assignment.args)
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            executor = self.executor or ThreadPoolExecutor(max_workers=1)
            func_partial = partial(self.func, **assignment.args)
            result = await loop.run_in_executor(executor, func_partial)

        # Normalize result to dict
        if result is None:
            result = {}
        elif not isinstance(result, dict):
            result = {"value": result}

        # Send done event with result
        await self.asend(
            messages.DoneEvent(
                assignation=assignment.assignation,
                returns=result,
            )
        )

    async def _execute_generator(self, assignment: messages.Assign) -> None:
        """Execute a generator function, yielding results."""
        if self.is_async:
            # Async generator
            async for result in self.func(**assignment.args):
                if result is None:
                    result = {}
                elif not isinstance(result, dict):
                    result = {"value": result}

                await self.asend(
                    messages.YieldEvent(
                        assignation=assignment.assignation,
                        returns=result,
                    )
                )
        else:
            # Sync generator - run in thread pool
            loop = asyncio.get_event_loop()
            executor = self.executor or ThreadPoolExecutor(max_workers=1)

            # Collect from sync generator in thread
            def run_generator():
                return list(self.func(**assignment.args))

            results = await loop.run_in_executor(executor, run_generator)

            for result in results:
                if result is None:
                    result = {}
                elif not isinstance(result, dict):
                    result = {"value": result}

                await self.asend(
                    messages.YieldEvent(
                        assignation=assignment.assignation,
                        returns=result,
                    )
                )

        # Send done after all yields
        await self.asend(
            messages.DoneEvent(
                assignation=assignment.assignation,
                returns={},
            )
        )


def create_functional_actor_builder(
    func: ActionFunction,
    action_name: str,
) -> Callable:
    """
    Create an actor builder for a function.

    Args:
        func: The function to wrap
        action_name: Name of the action

    Returns:
        Actor builder function
    """
    is_async = asyncio.iscoroutinefunction(func)
    is_async_gen = inspect.isasyncgenfunction(func)
    is_gen = inspect.isgeneratorfunction(func)

    def builder(agent) -> FunctionalActor:
        return FunctionalActor(
            agent=agent,
            action=action_name,
            func=func,
            is_async=is_async or is_async_gen,
            is_generator=is_gen or is_async_gen,
        )

    return builder
