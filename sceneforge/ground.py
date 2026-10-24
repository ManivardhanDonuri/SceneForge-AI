"""
ground.py
=========
Ground plane and road network generation.

Generates:
- A large flat ground plane that fills the environment footprint
- A simple grid of road segments laid on top of the ground
"""

import bpy
import bmesh
from typing import List


def generate_ground(size: float) -> bpy.types.Object:
    """
    Create a flat ground plane centred at the world origin.

    Parameters
    ----------
    size : float
        Side length of the square ground plane in Blender units (metres).

    Returns
    -------
    bpy.types.Object
        The created ground plane object.
    """
    mesh = bpy.data.meshes.new("Ground_Mesh")
    obj = bpy.data.objects.new("Ground", mesh)

    bpy.context.scene.collection.objects.link(obj)

    # Build the plane geometry with bmesh
    bm = bmesh.new()
    half = size / 2.0
    bmesh.ops.create_grid(
        bm,
        x_segments=1,
        y_segments=1,
        size=half,  # Blender's create_grid 'size' is half-extent
    )
    bm.to_mesh(mesh)
    bm.free()

    # Lay flat at Z = 0
    obj.location = (0.0, 0.0, 0.0)

    return obj


def generate_roads(
    ground_size: float,
    road_width: float,
    grid_divisions: int = 3,
) -> List[bpy.types.Object]:
    """
    Generate a simple grid road network on top of the ground plane.

    Creates horizontal and vertical road strips across the scene.

    Parameters
    ----------
    ground_size : float
        Side length of the scene ground in Blender units.
    road_width : float
        Width of each road strip in Blender units.
    grid_divisions : int, optional
        Number of roads in each direction (default 3).

    Returns
    -------
    list of bpy.types.Object
        All created road segment objects.
    """
    road_objects: List[bpy.types.Object] = []
    half_ground = ground_size / 2.0

    # Road thickness (sits just above the ground to avoid Z-fighting)
    road_thickness = 0.05
    road_z = road_thickness / 2.0

    # Distribute roads evenly across the ground plane
    spacing = ground_size / (grid_divisions + 1)

    for i in range(1, grid_divisions + 1):
        offset = -half_ground + i * spacing

        # ── Horizontal road (runs along X axis) ───────────────────────
        h_road = _create_road_segment(
            name=f"Road_H_{i}",
            length=ground_size,
            width=road_width,
            location=(0.0, offset, road_z),
            axis="X",
        )
        road_objects.append(h_road)

        # ── Vertical road (runs along Y axis) ─────────────────────────
        v_road = _create_road_segment(
            name=f"Road_V_{i}",
            length=ground_size,
            width=road_width,
            location=(offset, 0.0, road_z),
            axis="Y",
        )
        road_objects.append(v_road)

    return road_objects


def _create_road_segment(
    name: str,
    length: float,
    width: float,
    location: tuple,
    axis: str,
) -> bpy.types.Object:
    """
    Create a single flat road segment as a thin box.

    Parameters
    ----------
    name : str
        Object name.
    length : float
        Road length along its primary axis.
    width : float
        Road width.
    location : tuple
        (x, y, z) world position.
    axis : str
        Primary axis of the road: ``"X"`` or ``"Y"``.

    Returns
    -------
    bpy.types.Object
        The road object.
    """
    thickness = 0.05

    if axis == "X":
        dimensions = (length, width, thickness)
    else:
        dimensions = (width, length, thickness)

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()

    obj.scale = dimensions
    obj.location = location

    # Apply scale so modifiers behave predictably
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(scale=True)

    return obj
