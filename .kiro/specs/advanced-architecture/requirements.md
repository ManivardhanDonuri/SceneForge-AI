# Requirements – SceneForge AI Advanced Architecture Upgrade

## Overview

SceneForge AI currently generates procedural 3D city scenes via a standalone Python script
executed inside Blender's background mode. The existing pipeline is functional but limited:
buildings are plain unit-cube boxes, there is no instancing, and the tool cannot be installed
or operated as a native Blender add-on.

This upgrade transforms SceneForge AI into a **production-grade procedural generation tool**
with a proper Blender Add-on architecture, a low-level BMesh geometry engine, a GPU-friendly
instancing pipeline, an interactive UI panel, and a clean public Python API.

---

## Stakeholders

| Role | Interest |
|---|---|
| TD / Pipeline Engineer | Clean Python API, deterministic output, no `bpy.ops` side-effects |
| Environment Artist | Rich building facades, controllable randomness, fast iteration |
| Render Wrangler | Low vertex count via instancing, predictable Cycles output |
| Studio Technical Lead | Installable add-on, version metadata, CI-testable modules |

---

## Functional Requirements

### FR-1 – Geometry Engine Refactor

**FR-1.1** The building generator (`sceneforge/buildings.py`) SHALL replace all
`bmesh.ops.create_cube` + `bpy.ops.object.transform_apply` calls with direct BMesh
vertex/face construction so that no operator context is required.

**FR-1.2** Each building mesh SHALL be subdivided into **floor slabs** and **column bays**
before any facade detail is applied. The number of floors SHALL be derived from
`floor_height` (config parameter, default 3 m). Column bay count SHALL be derived from
building width and a `bay_width` parameter (default 4 m).

**FR-1.3** The facade generator SHALL procedurally inset **window openings** into each
bay/floor cell using BMesh face-inset and extrude operations. Window depth (recess), frame
width, and sill protrusion SHALL be individually configurable.

**FR-1.4** A subset of buildings (controlled by `entryway_probability`) SHALL receive a
ground-floor entryway arch or recessed portal carved into the facade using BMesh boolean-
equivalent topology (bridge-edge-loops / fill operations — no `bpy.ops.boolean`).

**FR-1.5** Rooftop asset generation SHALL place one or more of the following on each
building's top face:
- Flat parapet wall (extruded border loop)
- Water tower (cylinder approximation via BMesh prim)
- HVAC unit (box extrusion with vent slats)

Rooftop asset selection and count SHALL be seeded from the building's own random state so
results are reproducible.

**FR-1.6** Building footprint placement SHALL use **NumPy vectorised AABB checks** instead
of the current Python-loop overlap test. A 2-D occupancy grid (cell size = `spacing`)
SHALL be used to reject candidates in O(1) per lookup.

**FR-1.7** All building meshes SHALL have correct face normals (outward-facing) and no
interior/duplicate geometry after construction.

---

### FR-2 – Performance & Instancing System

**FR-2.1** Repeated sub-assets (windows, rooftop units, street furniture) SHALL be
represented as **Blender Collection Instances** rather than individual mesh objects, so
that `n` copies share a single mesh data-block in GPU memory.

**FR-2.2** The instancing system SHALL expose a `InstanceLibrary` class that:
- Registers a named prototype mesh into a dedicated Blender collection (`SF_Prototypes`).
- Returns a lightweight Empty object linked to that collection at a given transform.
- Allows batch placement via a NumPy array of (position, rotation, scale) rows.

**FR-2.3** Where Blender 4.x Geometry Nodes are available, the window-grid pattern on a
building facade MAY be driven by a Geometry Nodes modifier as an alternative to
per-vertex BMesh construction, reducing object count further. This shall be
**opt-in** via a config flag `use_geometry_nodes_windows`.

**FR-2.4** The total unique mesh data-block count SHALL NOT exceed
`count + prototype_types + 3` (ground + 2 road types) regardless of the number of
instances placed in the scene.

---

### FR-3 – Blender Add-on Architecture

**FR-3.1** `sceneforge/__init__.py` SHALL be rewritten to comply with the Blender Add-on
specification:
- Define `bl_info` dict with `name`, `author`, `version` (tuple), `blender` (min version
  tuple), `location`, `description`, `category`.
- Implement `register()` and `unregister()` functions that call
  `bpy.utils.register_class` / `unregister_class` for all custom types.

**FR-3.2** All parameters from `config.json` SHALL be mirrored as native Blender
properties stored on `bpy.types.Scene` under a `PropertyGroup` named
`SceneForgeProperties`. The following property types SHALL be used:

| Config key | Blender prop type |
|---|---|
| `environment.ground_size` | `FloatProperty` |
| `environment.road_width` | `FloatProperty` |
| `buildings.count` | `IntProperty` |
| `buildings.min/max_height` | `FloatProperty` |
| `buildings.min/max_width` | `FloatProperty` |
| `buildings.spacing` | `FloatProperty` |
| `buildings.floor_height` | `FloatProperty` |
| `buildings.bay_width` | `FloatProperty` |
| `buildings.entryway_probability` | `FloatProperty` (0–1) |
| `buildings.use_geometry_nodes_windows` | `BoolProperty` |
| `render.engine` | `EnumProperty` |
| `render.samples` | `IntProperty` |
| `render.resolution_x/y` | `IntProperty` |
| `seed` (global) | `IntProperty` |

**FR-3.3** A **UI Panel** (`VIEW_3D_PT_SceneForgePanel`) SHALL be registered in the
3D Viewport's `N`-panel (sidebar), under a tab labelled `"SceneForge"`. It SHALL contain:
- Collapsible sub-panels: Environment, Buildings, Lighting, Render.
- A prominent **"Generate Scene"** operator button.
- A **"Export Config"** operator button that writes current property values to
  `config.json`.
- A **"Import Config"** operator button that reads `config.json` and populates
  properties.
- A live vertex/instance count readout (updated after each generation).

**FR-3.4** A `SCENEFORGE_OT_GenerateScene` operator SHALL replace the `main()` function
as the primary pipeline entry point. It SHALL:
- Read parameters from `SceneForgeProperties` (not from disk) when invoked from the UI.
- Accept an optional `config_path` string property for headless/CLI invocation.
- Report progress via `self.report()` and Blender's progress bar (`wm.progress_begin`).
- Be undoable (register with `bl_options = {'REGISTER', 'UNDO'}`).

**FR-3.5** The add-on SHALL remain executable in **headless mode** via:
```
blender --background --python main.py -- --config config.json [--render]
```
`main.py` SHALL be kept as a thin CLI shim that registers the add-on and invokes the
operator programmatically.

---

### FR-4 – Material System Enhancements

**FR-4.1** Window openings SHALL receive a dedicated glass material slot (slot index 1)
automatically during facade construction.

**FR-4.2** The concrete material factory SHALL accept an optional `variation_seed` so
that per-building colour variation is deterministic and not globally random.

**FR-4.3** A `make_emissive_material` factory SHALL be added for lit window variants
(night-mode toggle via `BoolProperty`).

---

### FR-5 – Configuration & Validation

**FR-5.1** `config_loader.py` SHALL be extended to validate the new keys introduced by
FR-1 and FR-3 (`floor_height`, `bay_width`, `entryway_probability`,
`use_geometry_nodes_windows`, `seed`).

**FR-5.2** `config_loader.py` SHALL provide a `config_to_scene_props(config, scene)`
helper and a `scene_props_to_config(scene)` helper to drive the Import/Export operators.

---

### FR-6 – Code Quality & Testability

**FR-6.1** All new public functions SHALL have NumPy-style docstrings with `Parameters`,
`Returns`, and `Raises` sections.

**FR-6.2** Pure-logic functions (overlap detection, floor/bay grid computation, NumPy
transforms) SHALL be importable without a live `bpy` context so they can be unit-tested
with `pytest` and `fake-bpy-module`.

**FR-6.3** `requirements.txt` SHALL be updated to pin `fake-bpy-module-4x` for Blender
4.x compatibility in CI.

---

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Generating 50 buildings SHALL complete in under 10 seconds on a modern CPU (single-threaded Blender Python). |
| NFR-2 | The installed add-on ZIP SHALL be under 500 KB. |
| NFR-3 | No `bpy.ops.*` calls inside geometry-generation code paths (operators are context-sensitive and break headless execution). Allowed only in `scene.py` for scene-clear. |
| NFR-4 | All code SHALL be compatible with Blender 3.6 LTS and Blender 4.x. |
| NFR-5 | Random seed control SHALL guarantee identical output for identical inputs across runs. |

---

## Constraints

- The project must remain a **pure Python** Blender add-on; no C extensions or compiled
  binaries.
- NumPy is available inside Blender's bundled Python — no install required.
- Geometry Nodes integration (FR-2.3) is strictly additive and must not break the BMesh
  fallback path.
