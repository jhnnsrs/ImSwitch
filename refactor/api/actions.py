"""
Microscope action definitions.

This module contains all registered microscope actions that can be
executed by the EngineManager. Import this module to register the actions.
"""

from __future__ import annotations

import asyncio
from typing import Dict, Any
from uuid import uuid4

from .registry import register


# ============================================================================
# Imaging Actions
# ============================================================================


@register(
    name="capture_image",
    description="Capture an image from the microscope camera",
    parameters_schema={
        "type": "object",
        "properties": {
            "exposure_time": {"type": "number", "description": "Exposure time in seconds"},
            "resolution": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Resolution [width, height]",
            },
            "channel": {"type": "string", "description": "Imaging channel"},
        },
    },
    tags=["imaging", "camera"],
)
async def capture_image(params: Dict[str, Any]) -> Dict[str, Any]:
    """Capture an image from the microscope camera."""
    await asyncio.sleep(0.1)
    return {
        "image_id": str(uuid4()),
        "exposure_time": params.get("exposure_time", 0.1),
        "resolution": params.get("resolution", [1024, 1024]),
        "channel": params.get("channel", "default"),
    }


@register(
    name="acquire_z_stack",
    description="Acquire a Z-stack of images",
    parameters_schema={
        "type": "object",
        "properties": {
            "z_start": {"type": "number", "description": "Start Z position"},
            "z_end": {"type": "number", "description": "End Z position"},
            "z_step": {"type": "number", "description": "Z step size"},
            "exposure_time": {"type": "number", "description": "Exposure per slice"},
        },
    },
    tags=["imaging", "z-stack", "3d"],
)
async def acquire_z_stack(params: Dict[str, Any]) -> Dict[str, Any]:
    """Acquire a Z-stack of images."""
    z_start = params.get("z_start", 0)
    z_end = params.get("z_end", 10)
    z_step = params.get("z_step", 1)

    num_slices = int(abs(z_end - z_start) / z_step) + 1
    await asyncio.sleep(0.1 * num_slices)

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
    name="move_stage",
    description="Move the microscope stage to a position",
    parameters_schema={
        "type": "object",
        "properties": {
            "position": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Target position [x, y, z]",
            },
            "speed": {"type": "number", "description": "Movement speed in µm/s"},
            "relative": {"type": "boolean", "description": "Relative movement"},
        },
    },
    tags=["stage", "movement"],
)
async def move_stage(params: Dict[str, Any]) -> Dict[str, Any]:
    """Move the microscope stage to a specified position."""
    await asyncio.sleep(0.2)
    return {
        "position": params.get("position", [0, 0, 0]),
        "speed": params.get("speed", 1000),
        "relative": params.get("relative", False),
        "success": True,
    }


# ============================================================================
# Focus Actions
# ============================================================================


@register(
    name="adjust_focus",
    description="Adjust the microscope focus",
    parameters_schema={
        "type": "object",
        "properties": {
            "z_position": {"type": "number", "description": "Z position in µm"},
            "speed": {"type": "number", "description": "Focus speed"},
            "auto": {"type": "boolean", "description": "Use autofocus"},
        },
    },
    tags=["focus", "z-axis"],
)
async def adjust_focus(params: Dict[str, Any]) -> Dict[str, Any]:
    """Adjust the microscope focus position."""
    await asyncio.sleep(0.1)
    return {
        "focus_position": params.get("z_position", 0),
        "speed": params.get("speed", 100),
        "auto": params.get("auto", False),
        "success": True,
    }


# ============================================================================
# Illumination Actions
# ============================================================================


@register(
    name="set_laser_power",
    description="Set the power of a laser",
    parameters_schema={
        "type": "object",
        "properties": {
            "laser_id": {"type": "string", "description": "Laser identifier"},
            "power": {"type": "number", "description": "Power in mW"},
            "enabled": {"type": "boolean", "description": "Enable/disable laser"},
        },
    },
    tags=["laser", "illumination"],
)
async def set_laser_power(params: Dict[str, Any]) -> Dict[str, Any]:
    """Set laser power level."""
    await asyncio.sleep(0.05)
    return {
        "laser_id": params.get("laser_id", "default"),
        "power": params.get("power", 0),
        "enabled": params.get("enabled", True),
        "success": True,
    }
