"""
renderer.py
===========
Cycles render engine configuration.

Applies all render settings from the ``"render"`` section of config.json
to the active Blender scene, including:
  - Render engine selection (Cycles / EEVEE)
  - Cycles device and sample count
  - Output resolution and pixel aspect ratio
  - Output directory and file format (PNG)
  - Colour management (Filmic tone-mapping)
"""

import bpy
import os
from typing import Any, Dict


def configure_renderer(render_cfg: Dict[str, Any]) -> None:
    """
    Apply render settings to the current Blender scene.

    Parameters
    ----------
    render_cfg : dict
        The ``"render"`` section of config.json.  Expected keys:

        ``engine``        – ``"CYCLES"`` or ``"BLENDER_EEVEE"``
        ``samples``       – integer path-tracing sample count
        ``resolution_x``  – output width in pixels
        ``resolution_y``  – output height in pixels
        ``output_dir``    – output path (``//`` = relative to .blend)
        ``file_format``   – ``"PNG"`` (other formats supported by Blender)
    """
    scene = bpy.context.scene
    render = scene.render

    # ── Engine ────────────────────────────────────────────────────────────
    engine = render_cfg.get("engine", "CYCLES").upper()
    render.engine = engine

    if engine == "CYCLES":
        _configure_cycles(scene, render_cfg)
    elif engine == "BLENDER_EEVEE":
        _configure_eevee(scene, render_cfg)

    # ── Resolution ────────────────────────────────────────────────────────
    render.resolution_x = int(render_cfg.get("resolution_x", 1920))
    render.resolution_y = int(render_cfg.get("resolution_y", 1080))
    render.resolution_percentage = 100
    render.pixel_aspect_x = 1.0
    render.pixel_aspect_y = 1.0

    # ── Output path ───────────────────────────────────────────────────────
    output_dir = render_cfg.get("output_dir", "//output/")
    render.filepath = output_dir

    # ── File format ───────────────────────────────────────────────────────
    file_format = render_cfg.get("file_format", "PNG").upper()
    render.image_settings.file_format = file_format

    if file_format == "PNG":
        render.image_settings.color_mode = "RGBA"
        render.image_settings.color_depth = "8"
        render.image_settings.compression = 15  # 0–100, lower = larger file

    # ── Colour management ─────────────────────────────────────────────────
    _configure_colour_management(scene)

    # ── Film (transparent background option) ──────────────────────────────
    render.film_transparent = False


# ─────────────────────────────────────────────────────────────────────────────
# Engine-specific helpers
# ─────────────────────────────────────────────────────────────────────────────

def _configure_cycles(
    scene: bpy.types.Scene,
    render_cfg: Dict[str, Any],
) -> None:
    """
    Apply Cycles-specific settings.

    Parameters
    ----------
    scene : bpy.types.Scene
    render_cfg : dict
    """
    cycles = scene.cycles

    # Sample count
    cycles.samples = int(render_cfg.get("samples", 128))
    cycles.use_adaptive_sampling = True
    cycles.adaptive_threshold = 0.01  # Stop when noise < 1 %

    # Denoising
    cycles.use_denoising = True

    # Device – attempt GPU, fall back to CPU silently
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.refresh_devices()
        if prefs.has_active_device():
            cycles.device = "GPU"
        else:
            cycles.device = "CPU"
    except Exception:
        cycles.device = "CPU"

    # Bounces (balanced quality / speed)
    cycles.max_bounces = 8
    cycles.diffuse_bounces = 4
    cycles.glossy_bounces = 4
    cycles.transmission_bounces = 8
    cycles.volume_bounces = 2
    cycles.transparent_max_bounces = 8

    # Tile size (CPU-optimised)
    scene.render.tile_x = 64
    scene.render.tile_y = 64


def _configure_eevee(
    scene: bpy.types.Scene,
    render_cfg: Dict[str, Any],
) -> None:
    """
    Apply EEVEE-specific settings.

    Parameters
    ----------
    scene : bpy.types.Scene
    render_cfg : dict
    """
    eevee = scene.eevee

    eevee.taa_render_samples = int(render_cfg.get("samples", 64))
    eevee.use_ssr = True              # Screen-space reflections
    eevee.use_ssr_refraction = True
    eevee.use_bloom = False
    eevee.use_volumetric_lights = False
    eevee.shadow_cube_size = "1024"
    eevee.shadow_cascade_size = "1024"


# ─────────────────────────────────────────────────────────────────────────────
# Colour management
# ─────────────────────────────────────────────────────────────────────────────

def _configure_colour_management(scene: bpy.types.Scene) -> None:
    """
    Apply Filmic colour management for photorealistic output.

    Parameters
    ----------
    scene : bpy.types.Scene
    """
    view_settings = scene.view_settings
    view_settings.view_transform = "Filmic"
    view_settings.look = "None"
    view_settings.exposure = 0.0
    view_settings.gamma = 1.0

    scene.display_settings.display_device = "sRGB"
    scene.sequencer_colorspace_settings.name = "sRGB"
