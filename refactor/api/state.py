"""
State proxy for buffered state updates.

This module provides a StateProxy class that allows asynchronous state updates
with periodic WebSocket broadcasting of buffered changes.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, Set, TYPE_CHECKING
from copy import deepcopy
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .managers import ConnectionManager


class StateUpdate(BaseModel):
    """Represents a state update."""

    key: str = Field(..., description="State key that was updated")
    value: Any = Field(..., description="New value")
    timestamp: datetime = Field(default_factory=datetime.now)
    source: Optional[str] = Field(None, description="Source of the update")


class StateSnapshot(BaseModel):
    """Snapshot of the current state."""

    state: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    version: int = Field(0, description="State version number")


class StateProxy:
    """
    Proxy for managing state with buffered WebSocket updates.

    The StateProxy allows asynchronous state updates and periodically
    broadcasts buffered changes to connected WebSocket clients.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        broadcast_interval: float = 0.1,
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the StateProxy.

        Args:
            connection_manager: WebSocket connection manager for broadcasting
            broadcast_interval: Interval in seconds between broadcasts
            initial_state: Initial state dictionary
        """
        self._connection_manager = connection_manager
        self._broadcast_interval = broadcast_interval
        self._state: Dict[str, Any] = initial_state or {}
        self._version: int = 0
        self._dirty_keys: Set[str] = set()
        self._lock = asyncio.Lock()
        self._broadcast_task: Optional[asyncio.Task[None]] = None
        self._is_running = False

    @property
    def version(self) -> int:
        """Get the current state version."""
        return self._version

    async def start(self) -> None:
        """Start the periodic broadcast task."""
        if not self._is_running:
            self._is_running = True
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def stop(self) -> None:
        """Stop the periodic broadcast task."""
        self._is_running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    async def set(
        self,
        key: str,
        value: Any,
        source: Optional[str] = None,
        immediate: bool = False,
    ) -> None:
        """
        Set a state value.

        Args:
            key: State key (supports dot notation for nested keys)
            value: Value to set
            source: Optional source identifier
            immediate: If True, broadcast immediately
        """
        async with self._lock:
            self._set_nested(self._state, key, value)
            self._version += 1
            self._dirty_keys.add(key)

        if immediate:
            await self._broadcast_updates()

    async def set_many(
        self,
        updates: Dict[str, Any],
        source: Optional[str] = None,
        immediate: bool = False,
    ) -> None:
        """
        Set multiple state values at once.

        Args:
            updates: Dictionary of key-value pairs to update
            source: Optional source identifier
            immediate: If True, broadcast immediately
        """
        async with self._lock:
            for key, value in updates.items():
                self._set_nested(self._state, key, value)
                self._dirty_keys.add(key)
            self._version += 1

        if immediate:
            await self._broadcast_updates()

    async def get(self, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Get a state value.

        Args:
            key: State key (supports dot notation), or None for entire state
            default: Default value if key doesn't exist

        Returns:
            The state value or default
        """
        async with self._lock:
            if key is None:
                return deepcopy(self._state)
            return self._get_nested(self._state, key, default)

    async def get_snapshot(self) -> StateSnapshot:
        """Get a snapshot of the current state."""
        async with self._lock:
            return StateSnapshot(
                state=deepcopy(self._state),
                timestamp=datetime.now(),
                version=self._version,
            )

    async def delete(self, key: str, immediate: bool = False) -> bool:
        """
        Delete a state key.

        Args:
            key: State key to delete
            immediate: If True, broadcast immediately

        Returns:
            True if key was deleted, False if it didn't exist
        """
        async with self._lock:
            if self._delete_nested(self._state, key):
                self._version += 1
                self._dirty_keys.add(key)
                if immediate:
                    await self._broadcast_updates()
                return True
            return False

    async def clear(self, immediate: bool = False) -> None:
        """Clear all state."""
        async with self._lock:
            old_keys = set(self._state.keys())
            self._state.clear()
            self._version += 1
            self._dirty_keys.update(old_keys)

        if immediate:
            await self._broadcast_updates()

    def _set_nested(self, d: Dict[str, Any], key: str, value: Any) -> None:
        """Set a nested value using dot notation."""
        keys = key.split(".")
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value

    def _get_nested(self, d: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Get a nested value using dot notation."""
        keys = key.split(".")
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return default
        return deepcopy(d)

    def _delete_nested(self, d: Dict[str, Any], key: str) -> bool:
        """Delete a nested key using dot notation."""
        keys = key.split(".")
        for k in keys[:-1]:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return False
        if isinstance(d, dict) and keys[-1] in d:
            del d[keys[-1]]
            return True
        return False

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast buffered state updates."""
        while self._is_running:
            try:
                await asyncio.sleep(self._broadcast_interval)
                await self._broadcast_updates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in state broadcast loop: {e}")

    async def _broadcast_updates(self) -> None:
        """Broadcast buffered state updates to WebSocket clients."""
        async with self._lock:
            if not self._dirty_keys:
                return

            # Collect dirty values
            updates: Dict[str, Any] = {}
            for key in self._dirty_keys:
                value = self._get_nested(self._state, key)
                updates[key] = value

            dirty_keys = list(self._dirty_keys)
            self._dirty_keys.clear()

        # Broadcast outside the lock
        await self._connection_manager.broadcast(
            {
                "type": "state_update",
                "updates": updates,
                "keys": dirty_keys,
                "version": self._version,
                "timestamp": datetime.now().isoformat(),
            }
        )
