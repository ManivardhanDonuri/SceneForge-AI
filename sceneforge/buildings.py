"""
buildings.py
============
Procedural building mesh generation.

Generates a configurable number of buildings with randomised:
- Footprint dimensions (width × depth)
- Height
- Position within the scene (avoiding road zones)

Each building is a simple extruded box. Future improvements could add
window geometry, rooftop details, and facade subdivisions.
"""

import bpy
import bmesh
import random
import math
from typing import List, Tuple


def generate_buildings(
    count: int,
    ground_size: float,
    min_height: float,
    max_height: float,
    min_width: float,
    max_width: float,
    spacing: float,
    seed: int = 42,
) -> List[bpy.types.Object]:
    """
    Generate ``count`` procedural buildings placed on the ground plane.

    Buildings are distributed on a randomised grid to avoid heavy
    overlap. Each building is a single mesh object with applied scale.

    Parameters
    ----------
    count : int
        Number of buildings to generate.
    ground_size : float
        Side length of the ground plane (buildings stay within bounds).
    min_height, max_height : float
        Height range for randomised building heights.
    min_width, max_width : float
        Width/depth range for randomised footprints.
    spacing : float
        Minimum gap between building footprints.
    seed : int, optional
        Random seed for reproducible layouts (default 42).

    Returns
    -------
    list of bpy.types.Object
        All created building objects.
    """
    random.seed(seed)

    buildings: List[bpy.types.Object] = []
    placed_footprints: List[Tuple[float, float, float, float]] = []

    half = ground_size / 2.0
    # Keep buildings a little away from the very edge
    margin = max_width + spacing
    placement_range = half - margin

    max_attempts = count * 20  # Prevent infinite loops on dense configs
    attempts = 0
    generated = 0

    while generated < count and attempts < max_attempts:
        attempts += 1

        # Randomise dimensions
        width = random.uniform(min_width, max_width)
        depth = random.uniform(min_width, max_width)
        height = random.uniform(min_height, max_height)

        # Random position within safe bounds
        x = random.uniform(-placement_range, placement_range)
        y = random.uniform(-placement_range, placement_range)

        # Check for overlap with already-placed buildings
        if _overlaps(x, y, width, depth, placed_footprints, spacing):
            continue

        # Create the building mesh
        obj = _create_building_mesh(
            name=f"Building_{generated + 1:03d}",
            width=width,
            depth=depth,
            height=height,
            location=(x, y, height / 2.0),  # Origin at base centre
        )

        buildings.append(obj)
        placed_footprints.append((x, y, width, depth))
        generated += 1

    if generated < count:
        print(
            f"[!] buildings.py: Could only place {generated}/{count} buildings "
            f"without overlap. Increase ground_size or reduce count/spacing."
        )

    return buildings


def _create_building_mesh(
    name: str,
    width: float,
    depth: float,
    height: float,
    location: Tuple[float, float, float],
) -> bpy.types.Object:
    """
    Create a single box building mesh.

    Parameters
    ----------
    name : str
        Object name.
    width, depth, height : float
        Building dimensions in Blender units.
    location : tuple
        (x, y, z) world-space position of the object origin.

    Returns
    -------
    bpy.types.Object
        The building object linked to the active scene.
    """
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    # Build box geometry
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()

    # Scale to desired dimensions (unit cube → building box)
    obj.scale = (width, depth, height)
    obj.location = location

    # Apply scale so the mesh data reflects real dimensions
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(scale=True)

    return obj


def _overlaps(
    x: float,
    y: float,
    width: float,
    depth: float,
    placed: List[Tuple[float, float, float, float]],
    spacing: float,
) -> bool:
    """
    Return True if the proposed building footprint overlaps any
    already-placed footprint (including the spacing gap).

    Parameters
    ----------
    x, y : float
        Centre position of the proposed building.
    width, depth : float
        Footprint dimensions of the proposed building.
    placed : list
        List of (cx, cy, w, d) tuples for already-placed buildings.
    spacing : float
        Minimum gap between footprints.

    Returns
    -------
    bool
    """
    half_w = width / 2.0 + spacing / 2.0
    half_d = depth / 2.0 + spacing / 2.0

    for cx, cy, pw, pd in placed:
        # AABB overlap test with spacing
        if (
            abs(x - cx) < half_w + pw / 2.0
            and abs(y - cy) < half_d + pd / 2.0
        ):
            return True

    return False
