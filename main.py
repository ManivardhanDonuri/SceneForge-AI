"""
SceneForge AI – Main Entry Point
=================================
Orchestrates the full procedural scene generation pipeline:
  1. Load configuration from config.json
  2. Initialise / clear the Blender scene
  3. Generate ground and road network
  4. Generate buildings
  5. Apply materials
  6. Configure lighting
  7. Position the camera
  8. Configure the render engine and output
  9. Optionally trigger a render

Run from Blender's Script Editor or via the terminal:
    blender --background --python main.py
"""

import sys
import os

# ---------------------------------------------------------------------------
# Make sure the sceneforge package is importable when run via the terminal.
# Blender's sys.path doesn't always include the script's own directory.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import bpy  # noqa: E402  (must come after sys.path fix)

from sceneforge.config_loader import load_config, ConfigError
from sceneforge.scene import initialise_scene
from sceneforge.ground import generate_ground, generate_roads
from sceneforge.buildings import generate_buildings
from sceneforge.materials import apply_scene_materials
from sceneforge.lighting import setup_lighting
from sceneforge.camera import setup_camera
from sceneforge.renderer import configure_renderer


def main() -> None:
    """Run the full SceneForge AI pipeline."""

    print("\n========================================")
    print("  SceneForge AI – Procedural Scene Gen")
    print("========================================\n")

    # ── 1. Configuration ──────────────────────────────────────────────────
    config_path = os.path.join(SCRIPT_DIR, "config.json")
    try:
        config = load_config(config_path)
        print(f"[✓] Config loaded from: {config_path}")
    except ConfigError as exc:
        print(f"[✗] Configuration error: {exc}")
        sys.exit(1)

    # ── 2. Scene initialisation ───────────────────────────────────────────
    initialise_scene()
    print("[✓] Scene cleared and initialised")

    # ── 3. Ground + roads ─────────────────────────────────────────────────
    env_cfg = config["environment"]
    ground_obj = generate_ground(
        size=env_cfg["ground_size"]
    )
    road_objects = generate_roads(
        ground_size=env_cfg["ground_size"],
        road_width=env_cfg["road_width"],
    )
    print(f"[✓] Ground and {len(road_objects)} road segment(s) created")

    # ── 4. Buildings ──────────────────────────────────────────────────────
    b_cfg = config["buildings"]
    buildings = generate_buildings(
        count=b_cfg["count"],
        ground_size=env_cfg["ground_size"],
        min_height=b_cfg["min_height"],
        max_height=b_cfg["max_height"],
        min_width=b_cfg["min_width"],
        max_width=b_cfg["max_width"],
        spacing=b_cfg["spacing"],
    )
    print(f"[✓] {len(buildings)} building(s) generated")

    # ── 5. Materials ──────────────────────────────────────────────────────
    apply_scene_materials(
        ground_obj=ground_obj,
        road_objects=road_objects,
        building_objects=buildings,
    )
    print("[✓] Materials applied")

    # ── 6. Lighting ───────────────────────────────────────────────────────
    setup_lighting(config["lighting"])
    print("[✓] Lighting configured")

    # ── 7. Camera ─────────────────────────────────────────────────────────
    cam_cfg = config["camera"]
    setup_camera(
        ground_size=env_cfg["ground_size"],
        auto_frame=cam_cfg["auto_frame"],
        distance_factor=cam_cfg["distance_factor"],
        height=cam_cfg["height"],
        focal_length=cam_cfg["focal_length_mm"],
    )
    print("[✓] Camera positioned")

    # ── 8. Renderer ───────────────────────────────────────────────────────
    configure_renderer(config["render"])
    print("[✓] Render engine configured")

    print("\n========================================")
    print("  Scene generation complete!")
    print("  To render: Render → Render Image (F12)")
    print("  Or re-run with --render flag to auto-render.")
    print("========================================\n")

    # ── 9. Optional auto-render (pass --render as extra Blender arg) ───────
    if "--render" in sys.argv:
        print("[→] Starting render...")
        bpy.ops.render.render(write_still=True)
        print("[✓] Render complete. Check the output directory.")


if __name__ == "__main__":
    main()
