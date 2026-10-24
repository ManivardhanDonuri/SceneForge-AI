"""
lighting.py
===========
Lighting system for SceneForge AI.

Configures three light source types driven by the ``lighting`` section
of config.json:

  1. Sun light   – directional, simulates daylight
  2. Area light  – soft fill light above the scene
  3. Environment – world background colour / ambient light
"""

import bpy
import math
from typing import Any, Dict, List, Tuple


def setup_lighting(lighting_cfg: Dict[str, Any]) -> None:
    """
    Configure all lighting for the scene based on the config dictionary.

    Parameters
    ----------
    lighting_cfg : dict
        The ``"lighting"`` section of config.json, containing sub-keys:
        ``"sun"``, ``"area"``, and ``"environment"``.
    """
    created: List[str] = []

    if lighting_cfg.get("sun", {}).get("enabled", False):
        _setup_sun(lighting_cfg["sun"])
        created.append("Sun")

    if lighting_cfg.get("area", {}).get("enabled", False):
        _setup_area_light(lighting_cfg["area"])
        created.append("Area")

    if lighting_cfg.get("environment", {}).get("enabled", False):
        _setup_environment(lighting_cfg["environment"])
        created.append("Environment")

    if not created:
        print("[!] lighting.py: No lights enabled in config. Scene will be dark.")


# ─────────────────────────────────────────────────────────────────────────────
# Sun light
# ─────────────────────────────────────────────────────────────────────────────

def _setup_sun(sun_cfg: Dict[str, Any]) -> bpy.types.Object:
    """
    Create and configure a directional sun lamp.

    The sun is rotated on the X axis by ``angle_degrees`` so that it
    casts realistic shadows across the scene.

    Parameters
    ----------
    sun_cfg : dict
        Sub-config with keys: ``energy``, ``angle_degrees``.

    Returns
    -------
    bpy.types.Object
        The sun lamp object.
    """
    light_data = bpy.data.lights.new(name="Sun_Light", type="SUN")
    light_data.energy = float(sun_cfg.get("energy", 5.0))
    light_data.color = (1.0, 0.98, 0.92)  # Warm daylight tint
    light_data.angle = math.radians(0.53)  # Angular diameter of the sun

    sun_obj = bpy.data.objects.new("Sun_Light", light_data)
    bpy.context.scene.collection.objects.link(sun_obj)

    # Position high above the scene and rotate to simulate sun angle
    angle_deg = float(sun_cfg.get("angle_degrees", 45))
    sun_obj.location = (0.0, 0.0, 50.0)
    sun_obj.rotation_euler = (
        math.radians(angle_deg),
        0.0,
        math.radians(30.0),  # Slight azimuth offset
    )

    return sun_obj


# ─────────────────────────────────────────────────────────────────────────────
# Area light
# ─────────────────────────────────────────────────────────────────────────────

def _setup_area_light(area_cfg: Dict[str, Any]) -> bpy.types.Object:
    """
    Create and configure a soft area (fill) light above the scene.

    Parameters
    ----------
    area_cfg : dict
        Sub-config with keys: ``energy``, ``size``.

    Returns
    -------
    bpy.types.Object
        The area lamp object.
    """
    light_data = bpy.data.lights.new(name="Area_Light", type="AREA")
    light_data.energy = float(area_cfg.get("energy", 200.0))
    light_data.size = float(area_cfg.get("size", 10.0))
    light_data.color = (0.9, 0.95, 1.0)  # Cool sky-fill tint
    light_data.shape = "RECTANGLE"
    light_data.size_y = light_data.size

    area_obj = bpy.data.objects.new("Area_Light", light_data)
    bpy.context.scene.collection.objects.link(area_obj)

    # Place it above and slightly to the side for fill lighting
    area_obj.location = (-20.0, 20.0, 40.0)
    area_obj.rotation_euler = (math.radians(-45.0), 0.0, math.radians(-45.0))

    return area_obj


# ─────────────────────────────────────────────────────────────────────────────
# Environment / World lighting
# ─────────────────────────────────────────────────────────────────────────────

def _setup_environment(env_cfg: Dict[str, Any]) -> None:
    """
    Configure the Blender World background for ambient environment lighting.

    Uses a Background shader with a solid sky colour. Future versions
    can replace this with an HDRI texture node.

    Parameters
    ----------
    env_cfg : dict
        Sub-config with keys: ``strength``, ``color`` (RGB list 0–1).
    """
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Clear existing world nodes
    nodes.clear()

    # Background node
    bg_node = nodes.new("ShaderNodeBackground")
    color = env_cfg.get("color", [0.2, 0.3, 0.5])
    bg_node.inputs["Color"].default_value = (
        float(color[0]),
        float(color[1]),
        float(color[2]),
        1.0,
    )
    bg_node.inputs["Strength"].default_value = float(
        env_cfg.get("strength", 0.5)
    )

    # Output node
    output_node = nodes.new("ShaderNodeOutputWorld")

    links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])
