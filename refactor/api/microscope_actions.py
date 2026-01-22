"""
Microscope action definitions using the rekuest_next @register decorator.

This module contains all registered microscope actions. Import this module
to register the actions with the global DefinitionRegistry from rekuest_next.

Actions are defined as regular Python functions (async or sync) and are
automatically wrapped in actors for async execution.

The rekuest_next register decorator:
- Uses function name (title-cased) as the action name
- Uses docstring as the description
- Extracts parameter types and defaults from type annotations
- Supports collections for categorization
"""

import asyncio
from typing import Dict, Any, Optional, List
from uuid import uuid4
from rekuest_next.register import register
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.structures.registry import StructureRegistry


# Global registries - will be configured by app.py
definition_registry = DefinitionRegistry()
structure_registry = StructureRegistry()


# ============================================================================
# Imaging Actions
# ============================================================================


@register(
    definition_registry=definition_registry,
    structure_registry=structure_registry,
    collections=["imaging", "camera"],
)
async def capture_image(
    exposure_time: float = 0.1,
    resolution: Optional[List[int]] = None,
    channel: str = "default",
) -> Dict[str, Any]:
    """
    Capture an image from the microscope camera.

    Args:
        exposure_time: Exposure time in seconds
        resolution: Resolution [width, height]
        channel: Imaging channel

    Returns:
        Dictionary with image_id and capture parameters
    """
    await asyncio.sleep(0.1)  # Simulate camera capture
    return {
        "image_id": str(uuid4()),
        "exposure_time": exposure_time,
        "resolution": resolution or [1024, 1024],
        "channel": channel,
    }


@register(
    definition_registry=definition_registry,
    structure_registry=structure_registry,
    collections=["imaging", "z-stack", "3d"],
)
async def acquire_z_stack(
    z_start: float = 0,
    z_end: float = 10,
    z_step: float = 1,
    exposure_time: float = 0.1,
) -> Dict[str, Any]:
    """
    Acquire a Z-stack of images.

    Args:
        z_start: Start Z position
        z_end: End Z position
        z_step: Z step size
        exposure_time: Exposure per slice

    Returns:
        Dictionary with stack_id and acquisition parameters
    """
    num_slices = int(abs(z_end - z_start) / z_step) + 1
    await asyncio.sleep(0.1 * num_slices)  # Simulate acquisition

    return {
        "stack_id": str(uuid4()),
        "z_start": z_start,
        "z_end": z_end,
        "z_step": z_step,
        "num_slices": num_slices,
        "success": True,
    }


# ============================================================================
# Stage Actions
# ============================================================================


@register(
    definition_registry=definition_registry,
    structure_registry=structure_registry,
    collections=["stage", "motion"],
)
async def move_stage(
    x: Optional[float] = None,
    y: Optional[float] = None,
    z: Optional[float] = None,
    speed: float = 100.0,
    relative: bool = False,
) -> Dict[str, Any]:
    """
    Move the microscope stage to a position.

    Args:
        x: X position
        y: Y position
        z: Z position
        speed: Movement speed in µm/s
        relative: If True, move relative to current position

    Returns:
        Dictionary with new position and movement info
    """
    await asyncio.sleep(0.2)  # Simulate movement time

    position = [x or 0, y or 0, z or 0]
    return {
        "position": position,
        "speed": speed,
        "relative": relative,
        "success": True,
    }


@register(
    definition_registry=definition_registry,
    structure_registry=structure_registry,
    collections=["stage", "focus"],
)
async def adjust_focus(
    z_offset: float = 0.0,
    method: str = "manual",
) -> Dict[str, Any]:
    """
    Adjust the microscope focus.

    Args:
        z_offset: Z offset to apply
        method: Focus method ("manual", "auto", "continuous")

    Returns:
        Dictionary with focus info
    """
    await asyncio.sleep(0.15)  # Simulate focusing

    return {
        "z_offset": z_offset,
        "method": method,
        "success": True,
    }


# ============================================================================
# Laser/Illumination Actions
# ============================================================================


@register(
    definition_registry=definition_registry,
    structure_registry=structure_registry,
    collections=["laser", "illumination"],
)
async def set_laser_power(
    wavelength: int = 488,
    power: float = 50.0,
    enabled: bool = True,
) -> Dict[str, Any]:
    """
    Set the laser power for a specific laser line.

    Args:
        wavelength: Laser wavelength in nm
        power: Power level in mW
        enabled: Whether the laser is enabled

    Returns:
        Dictionary with laser state
    """
    await asyncio.sleep(0.05)  # Simulate setting

    return {
        "wavelength": wavelength,
        "power": power,
        "enabled": enabled,
        "success": True,
    }


@register(
    definition_registry=definition_registry,
    structure_registry=structure_registry,
    collections=["illumination"],
)
async def set_illumination(
    source: str = "brightfield",
    intensity: float = 50.0,
    enabled: bool = True,
) -> Dict[str, Any]:
    """
    Set the illumination settings.

    Args:
        source: Illumination source ("brightfield", "fluorescence", "led")
        intensity: Intensity level (0-100)
        enabled: Whether illumination is enabled

    Returns:
        Dictionary with illumination state
    """
    await asyncio.sleep(0.05)  # Simulate setting

    return {
        "source": source,
        "intensity": intensity,
        "enabled": enabled,
        "success": True,
    }


# ============================================================================
# Autofocus Actions
# ============================================================================


@register(
    definition_registry=definition_registry,
    structure_registry=structure_registry,
    collections=["focus", "autofocus"],
)
async def run_autofocus(
    method: str = "contrast",
    range_um: float = 10.0,
    steps: int = 20,
) -> Dict[str, Any]:
    """
    Run the autofocus routine.

    Args:
        method: Autofocus method ("contrast", "phase", "reflection")
        range_um: Focus search range in micrometers
        steps: Number of steps to search

    Returns:
        Dictionary with autofocus results
    """
    await asyncio.sleep(0.5)  # Simulate autofocus routine

    return {
        "method": method,
        "range_um": range_um,
        "steps": steps,
        "best_focus_z": 0.5,  # Simulated result
        "success": True,
    }


# ============================================================================
# Multi-step/Generator Actions (yield intermediate results)
# ============================================================================


@register(
    definition_registry=definition_registry,
    structure_registry=structure_registry,
    collections=["imaging", "time-lapse"],
)
async def time_lapse(
    num_frames: int = 10,
    interval: float = 1.0,
    exposure_time: float = 0.1,
):
    """
    Acquire time-lapse images, yielding each frame.

    This is a generator action that yields results incrementally.

    Args:
        num_frames: Number of frames to acquire
        interval: Interval between frames in seconds
        exposure_time: Exposure time per frame

    Yields:
        Dictionary with frame info for each captured frame
    """
    for frame_idx in range(num_frames):
        await asyncio.sleep(interval)  # Wait for interval

        yield {
            "frame_index": frame_idx,
            "image_id": str(uuid4()),
            "timestamp": frame_idx * interval,
            "exposure_time": exposure_time,
        }
