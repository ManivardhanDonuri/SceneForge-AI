"""
materials.py
============
PBR material creation and assignment.

Provides reusable factory functions for four core material types:
  - Concrete  (diffuse grey, rough)
  - Glass     (transmission + slight tint)
  - Metal     (specular, low roughness)
  - Ground    (dark asphalt-like)
  - Road      (dark asphalt)

All materials use Blender's Principled BSDF shader.
"""

import bpy
import random
from typing import List, Tuple


# ── Type alias ───────────────────────────────────────────────────────────────
Color = Tuple[float, float, float, float]  # RGBA (0–1)


# ─────────────────────────────────────────────────────────────────────────────
# Material factories
# ─────────────────────────────────────────────────────────────────────────────

def make_concrete_material(name: str = "Mat_Concrete") -> bpy.types.Material:
    """
    Create a rough concrete PBR material.

    Parameters
    ----------
    name : str
        Blender data-block name for the material.

    Returns
    -------
    bpy.types.Material
    """
    mat = _get_or_create_material(name)
    bsdf = _get_principled_bsdf(mat)

    # Slightly varied grey for visual interest
    grey = random.uniform(0.35, 0.55)
    bsdf.inputs["Base Color"].default_value = (grey, grey, grey, 1.0)
    bsdf.inputs["Roughness"].default_value = random.uniform(0.75, 0.95)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.05

    return mat


def make_glass_material(name: str = "Mat_Glass") -> bpy.types.Material:
    """
    Create a glass transmission material.

    Parameters
    ----------
    name : str
        Blender data-block name for the material.

    Returns
    -------
    bpy.types.Material
    """
    mat = _get_or_create_material(name)
    mat.use_backface_culling = False
    mat.blend_method = "BLEND"

    bsdf = _get_principled_bsdf(mat)
    bsdf.inputs["Base Color"].default_value = (0.6, 0.8, 0.9, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.0
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Transmission Weight"].default_value = 0.95
    bsdf.inputs["IOR"].default_value = 1.45

    return mat


def make_metal_material(name: str = "Mat_Metal") -> bpy.types.Material:
    """
    Create a metallic (steel-like) PBR material.

    Parameters
    ----------
    name : str
        Blender data-block name for the material.

    Returns
    -------
    bpy.types.Material
    """
    mat = _get_or_create_material(name)
    bsdf = _get_principled_bsdf(mat)

    bsdf.inputs["Base Color"].default_value = (0.7, 0.72, 0.74, 1.0)
    bsdf.inputs["Roughness"].default_value = random.uniform(0.1, 0.35)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.5

    return mat


def make_ground_material(name: str = "Mat_Ground") -> bpy.types.Material:
    """
    Create a dark ground / soil material.

    Parameters
    ----------
    name : str
        Blender data-block name for the material.

    Returns
    -------
    bpy.types.Material
    """
    mat = _get_or_create_material(name)
    bsdf = _get_principled_bsdf(mat)

    bsdf.inputs["Base Color"].default_value = (0.12, 0.10, 0.08, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.90
    bsdf.inputs["Metallic"].default_value = 0.0

    return mat


def make_road_material(name: str = "Mat_Road") -> bpy.types.Material:
    """
    Create a dark asphalt road material.

    Parameters
    ----------
    name : str
        Blender data-block name for the material.

    Returns
    -------
    bpy.types.Material
    """
    mat = _get_or_create_material(name)
    bsdf = _get_principled_bsdf(mat)

    bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.08, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Metallic"].default_value = 0.0

    return mat


# ─────────────────────────────────────────────────────────────────────────────
# Scene-level assignment
# ─────────────────────────────────────────────────────────────────────────────

# Building material types available for random assignment
_BUILDING_MATERIAL_FACTORIES = [
    make_concrete_material,
    make_glass_material,
    make_metal_material,
]


def apply_scene_materials(
    ground_obj: bpy.types.Object,
    road_objects: List[bpy.types.Object],
    building_objects: List[bpy.types.Object],
    seed: int = 7,
) -> None:
    """
    Apply materials to all scene objects.

    - Ground receives the ground material.
    - Roads receive the road/asphalt material.
    - Buildings are randomly assigned concrete, glass, or metal.

    Parameters
    ----------
    ground_obj : bpy.types.Object
        The ground plane object.
    road_objects : list of bpy.types.Object
        All road segment objects.
    building_objects : list of bpy.types.Object
        All generated building objects.
    seed : int, optional
        Random seed for reproducible material assignment (default 7).
    """
    random.seed(seed)

    # Ground
    _assign_material(ground_obj, make_ground_material("Mat_Ground"))

    # Roads (shared single material for efficiency)
    road_mat = make_road_material("Mat_Road")
    for road in road_objects:
        _assign_material(road, road_mat)

    # Buildings – random type per building
    for building in building_objects:
        factory = random.choice(_BUILDING_MATERIAL_FACTORIES)
        unique_name = f"Mat_{building.name}"
        mat = factory(unique_name)
        _assign_material(building, mat)


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_material(name: str) -> bpy.types.Material:
    """
    Return an existing material by name, or create a new one.

    Parameters
    ----------
    name : str
        Material data-block name.

    Returns
    -------
    bpy.types.Material
    """
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    # Remove the default diffuse node tree to start clean
    mat.node_tree.nodes.clear()
    # Add Principled BSDF + Material Output
    output_node = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf_node = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    mat.node_tree.links.new(
        bsdf_node.outputs["BSDF"], output_node.inputs["Surface"]
    )
    return mat


def _get_principled_bsdf(mat: bpy.types.Material) -> bpy.types.Node:
    """
    Return the Principled BSDF node from a material's node tree.

    Parameters
    ----------
    mat : bpy.types.Material
        A material with ``use_nodes = True``.

    Returns
    -------
    bpy.types.Node
        The Principled BSDF shader node.

    Raises
    ------
    ValueError
        If no Principled BSDF node is found.
    """
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    raise ValueError(
        f"Material '{mat.name}' has no Principled BSDF node. "
        "Use _get_or_create_material() to create materials."
    )


def _assign_material(
    obj: bpy.types.Object,
    mat: bpy.types.Material,
) -> None:
    """
    Assign a material to slot 0 of an object, replacing any existing one.

    Parameters
    ----------
    obj : bpy.types.Object
        Target Blender object.
    mat : bpy.types.Material
        Material to assign.
    """
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
