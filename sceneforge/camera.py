"""
camera.py
=========
Automatic camera placement and scene framing.

Positions a perspective camera so that the full ground plane is visible
from a natural three-quarter viewpoint, mimicking a cinematic city-wide
establishing shot.
"""

import bpy
import math
from typing import Tuple


def setup_camera(
    ground_size: float,
    auto_frame: bool = True,
    distance_factor: float = 1.5,
    height: float = 25.0,
    focal_length: float = 35.0,
) -> bpy.types.Object:
    """
    Create and position a camera to frame the entire scene.

    The camera is placed at a diagonal corner position, elevated to
    ``height`` Blender units, and pointed at the scene centre (world
    origin).

    Parameters
    ----------
    ground_size : float
        Side length of the ground plane; used to compute camera distance.
    auto_frame : bool, optional
        If True, calculate position automatically from ``ground_size``
        and ``distance_factor``. If False, use ``height`` only and place
        the camera at a fixed diagonal offset.
    distance_factor : float, optional
        Multiplier applied to ``ground_size / 2`` to determine how far
        from the centre the camera is placed (default 1.5).
    height : float, optional
        Camera height above the ground plane in Blender units (default 25).
    focal_length : float, optional
        Camera lens focal length in millimetres (default 35 mm).

    Returns
    -------
    bpy.types.Object
        The camera object. It is also set as the scene's active camera.
    """
    # ── Camera data ───────────────────────────────────────────────────────
    cam_data = bpy.data.cameras.new("SceneCamera")
    cam_data.lens = focal_length
    cam_data.clip_start = 0.1
    cam_data.clip_end = 1000.0
    cam_data.dof.use_dof = False  # Disable depth-of-field by default

    # ── Camera object ─────────────────────────────────────────────────────
    cam_obj = bpy.data.objects.new("SceneCamera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)

    # ── Position ──────────────────────────────────────────────────────────
    if auto_frame:
        distance = (ground_size / 2.0) * distance_factor
    else:
        distance = ground_size * 0.75

    # Place camera at a 45-degree diagonal for a classic isometric feel
    cam_x = distance
    cam_y = -distance
    cam_z = max(height, ground_size * 0.3)  # Never too low

    cam_obj.location = (cam_x, cam_y, cam_z)

    # ── Point at world origin (scene centre) ──────────────────────────────
    _point_camera_at(cam_obj, target=(0.0, 0.0, 0.0))

    # ── Register as active scene camera ──────────────────────────────────
    bpy.context.scene.camera = cam_obj

    return cam_obj


def _point_camera_at(
    cam_obj: bpy.types.Object,
    target: Tuple[float, float, float],
) -> None:
    """
    Rotate a camera object so it faces the given world-space target point.

    Uses the ``track_to`` constraint approach: temporarily sets rotation
    mode and computes the look-at direction analytically.

    Parameters
    ----------
    cam_obj : bpy.types.Object
        Camera object to rotate.
    target : tuple
        (x, y, z) world-space point to look at.
    """
    import mathutils

    cam_loc = cam_obj.location
    direction = mathutils.Vector(target) - mathutils.Vector(cam_loc)

    # Align –Z axis of the camera toward the target (Blender camera convention)
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()
