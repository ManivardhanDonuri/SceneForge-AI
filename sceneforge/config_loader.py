"""
config_loader.py
================
Loads and validates the JSON configuration file that drives the
entire SceneForge AI pipeline.

Usage
-----
    from sceneforge.config_loader import load_config, ConfigError

    config = load_config("config.json")
"""

import json
import os
from typing import Any, Dict


class ConfigError(Exception):
    """Raised when the configuration file is missing, malformed, or invalid."""


# Keys that must be present at the top level of config.json
REQUIRED_TOP_LEVEL_KEYS = {
    "environment",
    "buildings",
    "lighting",
    "camera",
    "render",
}

# Required keys within each section
REQUIRED_SECTION_KEYS: Dict[str, set] = {
    "environment": {"type", "ground_size", "road_width"},
    "buildings": {
        "count", "min_height", "max_height",
        "min_width", "max_width", "spacing",
    },
    "lighting": {"sun", "area", "environment"},
    "camera": {"auto_frame", "distance_factor", "height", "focal_length_mm"},
    "render": {
        "engine", "samples",
        "resolution_x", "resolution_y",
        "output_dir", "file_format",
    },
}


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate the JSON configuration file.

    Parameters
    ----------
    config_path : str
        Absolute or relative path to config.json.

    Returns
    -------
    dict
        Validated configuration dictionary.

    Raises
    ------
    ConfigError
        If the file is missing, contains invalid JSON, or is missing
        required keys.
    """
    # ── File existence check ──────────────────────────────────────────────
    if not os.path.isfile(config_path):
        raise ConfigError(
            f"Configuration file not found: '{config_path}'\n"
            "Make sure config.json is in the same directory as main.py."
        )

    # ── JSON parsing ──────────────────────────────────────────────────────
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config: Dict[str, Any] = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"config.json contains invalid JSON: {exc}"
        ) from exc

    # ── Top-level key validation ──────────────────────────────────────────
    missing_top = REQUIRED_TOP_LEVEL_KEYS - config.keys()
    if missing_top:
        raise ConfigError(
            f"config.json is missing top-level key(s): {sorted(missing_top)}"
        )

    # ── Section key validation ────────────────────────────────────────────
    for section, required_keys in REQUIRED_SECTION_KEYS.items():
        section_data = config.get(section, {})
        if not isinstance(section_data, dict):
            raise ConfigError(
                f"config.json: '{section}' must be a JSON object, "
                f"got {type(section_data).__name__}."
            )
        missing_keys = required_keys - section_data.keys()
        if missing_keys:
            raise ConfigError(
                f"config.json: section '{section}' is missing "
                f"key(s): {sorted(missing_keys)}"
            )

    # ── Value range validation ────────────────────────────────────────────
    _validate_ranges(config)

    return config


def _validate_ranges(config: Dict[str, Any]) -> None:
    """
    Validate that numeric values are within sensible ranges.

    Raises
    ------
    ConfigError
        If a value is out of range.
    """
    b = config["buildings"]
    if b["count"] < 1:
        raise ConfigError("buildings.count must be >= 1.")
    if b["min_height"] <= 0:
        raise ConfigError("buildings.min_height must be > 0.")
    if b["max_height"] < b["min_height"]:
        raise ConfigError(
            "buildings.max_height must be >= buildings.min_height."
        )
    if b["min_width"] <= 0:
        raise ConfigError("buildings.min_width must be > 0.")
    if b["max_width"] < b["min_width"]:
        raise ConfigError(
            "buildings.max_width must be >= buildings.min_width."
        )

    r = config["render"]
    if r["samples"] < 1:
        raise ConfigError("render.samples must be >= 1.")
    if r["resolution_x"] < 1 or r["resolution_y"] < 1:
        raise ConfigError(
            "render.resolution_x and render.resolution_y must be >= 1."
        )
    if r["engine"] not in ("CYCLES", "BLENDER_EEVEE"):
        raise ConfigError(
            "render.engine must be 'CYCLES' or 'BLENDER_EEVEE'."
        )

    e = config["environment"]
    if e["ground_size"] <= 0:
        raise ConfigError("environment.ground_size must be > 0.")
