"""
scene.py
========
Scene initialisation utilities.

Provides functions to clear the default Blender scene (cube, camera,
light) and prepare a clean slate for procedural generation.
"""

import bpy


def initialise_scene() -> None:
    """
    Clear the default Blender scene and prepare for generation.

    Actions performed
    -----------------
    - Deselect all objects
    - Delete all mesh, light, and camera objects
    - Remove all existing materials from the data-block
    - Set the unit system to Metric / Metres
    """
    # ── Deselect everything first ─────────────────────────────────────────
    bpy.ops.object.select_all(action="DESELECT")

    # ── Delete all existing scene objects ─────────────────────────────────
    deletable_types = {"MESH", "LIGHT", "CAMERA", "CURVE", "EMPTY"}
    for obj in list(bpy.data.objects):
        if obj.type in deletable_types:
            bpy.data.objects.remove(obj, do_unlink=True)

    # ── Remove orphaned mesh data ──────────────────────────────────────────
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)

    # ── Remove all existing materials ────────────────────────────────────
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)

    # ── Configure scene units ─────────────────────────────────────────────
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0

    # ── Set timeline frame range (useful for animations) ──────────────────
    scene.frame_start = 1
    scene.frame_end = 250


def get_scene_collection() -> bpy.types.Collection:
    """
    Return the active scene collection (root collection).

    Returns
    -------
    bpy.types.Collection
        The master collection for the current scene.
    """
    return bpy.context.scene.collection


def link_object_to_scene(obj: bpy.types.Object) -> None:
    """
    Link a Blender object to the active scene collection if not
    already linked.

    Parameters
    ----------
    obj : bpy.types.Object
        The Blender object to link.
    """
    collection = get_scene_collection()
    if obj.name not in collection.objects:
        collection.objects.link(obj)
