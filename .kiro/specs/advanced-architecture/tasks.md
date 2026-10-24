# Tasks – SceneForge AI Advanced Architecture Upgrade

Each task maps to a single, shippable unit of work. Tasks within the same phase can be
worked in parallel where noted. Dependent tasks list their blockers explicitly.

---

## Phase 1 – Foundation (no user-visible changes, enables everything else)

### Task 1.1 – Extend `config.json` with new keys
**Files:** `config.json`
**Depends on:** nothing

Add the following new keys to `config.json` while keeping all existing keys intact:

```json
{
  "seed": 42,
  "buildings": {
    "...existing keys...",
    "floor_height": 3.0,
    "bay_width": 4.0,
    "entryway_probability": 0.3,
    "use_geometry_nodes_windows": false
  }
}
```

Acceptance criteria:
- [ ] Existing `load_config()` does not break (new keys are additive).
- [ ] All new keys are present with the default values shown above.

---

### Task 1.2 – Extend `config_loader.py`
**Files:** `sceneforge/config_loader.py`
**Depends on:** Task 1.1

1. Add `floor_height`, `bay_width`, `entryway_probability`, `use_geometry_nodes_windows`
   to `REQUIRED_SECTION_KEYS["buildings"]`.
2. Add top-level optional key `seed` (use `config.setdefault("seed", 42)`).
3. Add range validation for new keys:
   - `floor_height` > 0
   - `bay_width` > 0
   - `entryway_probability` in [0, 1]
4. Implement `config_to_scene_props(config: dict, scene) -> None`.
5. Implement `scene_props_to_config(scene) -> dict`.
   - Both functions are no-ops if `scene.sceneforge` attribute does not exist (graceful
     degradation when running without the add-on registered).

Acceptance criteria:
- [ ] `load_config("config.json")` succeeds with the updated config file.
- [ ] Passing an out-of-range `entryway_probability` raises `ConfigError`.
- [ ] `scene_props_to_config(scene_props_to_config(…))` round-trips losslessly (pure
      Python test, no Blender context needed for the dict-level logic).

---

### Task 1.3 – Create `sceneforge/properties.py`
**Files:** `sceneforge/properties.py` (new)
**Depends on:** nothing

Define `SceneForgeProperties(bpy.types.PropertyGroup)` with all properties listed in
Design §2.2. Follow these conventions:
- Use `name` and `description` on every property.
- All float properties that represent physical lengths use `unit='LENGTH'`.
- `env_color` uses `subtype='COLOR', min=0.0, max=1.0, size=3`.
- No business logic in this file — only property declarations.

Acceptance criteria:
- [ ] File imports cleanly (`from sceneforge.properties import SceneForgeProperties`).
- [ ] All property names match the mapping table in Design §2.2 exactly.
- [ ] `bpy.utils.register_class(SceneForgeProperties)` succeeds inside Blender.

---

## Phase 2 – Geometry Engine Rewrite

### Task 2.1 – NumPy placement grid
**Files:** `sceneforge/buildings.py`
**Depends on:** Task 1.3 (for type hints only; can stub props as dict)

Replace the Python-loop placement strategy with a NumPy occupancy-grid approach.

Implementation steps:
1. Compute `cell_size = max_width + spacing`.
2. Build `grid = np.zeros((grid_w, grid_w), dtype=bool)`.
3. Use `np.random.default_rng(seed)` to shuffle candidate cells.
4. For each candidate cell `(i, j)`, compute world `(x, y)` centre; mark occupied and
   record if the cell is free.
5. Return `positions: np.ndarray` of shape `(N_placed, 2)` plus per-building
   `widths, depths, heights` arrays (all NumPy, float32).

Constraints:
- No `for` loop over `placed_footprints` for overlap testing.
- Function signature:
  ```python
  def _compute_placement_grid(
      ground_size: float,
      count: int,
      min_width: float, max_width: float,
      min_height: float, max_height: float,
      spacing: float,
      seed: int,
  ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
  # returns: positions(N,2), widths(N,), depths(N,), heights(N,)
  ```

Acceptance criteria:
- [ ] For `count=50`, `ground_size=100`, function runs in < 0.1 s (pure Python / NumPy,
      no Blender context).
- [ ] Output `positions` array has no two rows closer than `spacing` in both X and Y.
- [ ] Same `seed` always produces same output.

---

### Task 2.2 – BMesh box + floor/bay subdivision
**Files:** `sceneforge/buildings.py`
**Depends on:** Task 2.1

Rewrite `_create_building_mesh` to use direct BMesh vertex construction:

1. Create 8 vertices of a box, 6 quads — no `bmesh.ops.create_cube`.
2. Call `_subdivide_floors(bm, height, floor_height)`:
   - Compute `n_floors = max(1, round(height / floor_height))`.
   - For each floor boundary Z: `bmesh.ops.bisect_plane(bm, geom=[all], plane_co=(0,0,z),
     plane_no=(0,0,1), clear_inner=False, clear_outer=False)`.
3. Call `_subdivide_bays(bm, width, depth, bay_width)`:
   - For X-facing facades: bisect with `plane_no=(1,0,0)` at each bay boundary.
   - For Y-facing facades: bisect with `plane_no=(0,1,0)`.
4. Call `bmesh.ops.recalc_face_normals(bm, faces=bm.faces)`.
5. Return the completed `bm` (caller does `bm.to_mesh(mesh); bm.free()`).

No `bpy.ops.*` calls anywhere in this function.

Acceptance criteria:
- [ ] A building of height=12, floor_height=3, width=8, bay_width=4 produces exactly
      4 floor slabs and 2 column bays on each facade (verifiable by face count).
- [ ] `bmesh.ops.recalc_face_normals` leaves zero flipped normals.
- [ ] No orphan vertices or edges after construction.

---

### Task 2.3 – Window frame inset & recess
**Files:** `sceneforge/buildings.py`
**Depends on:** Task 2.2

Implement `_add_windows(bm, floor_height, bay_width, frame_width, recess_depth)`:

1. Identify facade faces: faces whose normals are approximately `±X` or `±Y`
   (dot product with Z-axis < 0.1).
2. Skip ground-floor faces (Z centre < floor_height).
3. For each facade face:
   a. `result = bmesh.ops.inset_individual(bm, faces=[face], thickness=frame_width,
      use_even_offset=True)`
   b. inner_face = result["faces"][0]
   c. `ext = bmesh.ops.extrude_face_region(bm, geom=[inner_face])`
   d. Translate extruded verts by `face.normal * -recess_depth`.
   e. Set `inner_face.material_index = 1` (glass slot).
4. Ensure no zero-area faces are created (guard: skip faces with area < 0.01).

New config parameters (add to `SceneForgeProperties` and `config.json`):
- `window_frame_width` (default 0.15 m)
- `window_recess_depth` (default 0.2 m)

Acceptance criteria:
- [ ] Every non-ground facade cell has an inset + recessed inner face.
- [ ] All inner faces have `material_index == 1`.
- [ ] No zero-area faces in resulting mesh.
- [ ] No `bpy.ops.*` calls.

---

### Task 2.4 – Entryway generation
**Files:** `sceneforge/buildings.py`
**Depends on:** Task 2.3

Implement `_add_entryway(bm, width, depth, floor_height, rng)`:

1. Select the ground-floor centre-bay face on the building's front facade
   (facade with highest Y for a Y-facing building; use bounding-box heuristic).
2. With probability `entryway_probability` (from props/rng): proceed; else return.
3. `bmesh.ops.inset_individual(bm, faces=[entry_face], thickness=frame_width * 2)`
4. Select the inset inner face; extrude inward by `recess_depth * 2`.
5. On the top edge of the inner face, create a 3-point arc approximation:
   - Add a midpoint vertex at `(centre_x, y_recessed, floor_height * 0.85)`.
   - `bmesh.ops.bridge_loops` to form the arch.
6. `bmesh.ops.recalc_face_normals` on modified region.

Acceptance criteria:
- [ ] Buildings with entryway have a visually distinct recessed arch on the ground floor.
- [ ] No crash when `entryway_probability = 0.0` (no entryways generated).
- [ ] No crash when `entryway_probability = 1.0` (all buildings get entryways).

---

### Task 2.5 – Rooftop assets
**Files:** `sceneforge/buildings.py`
**Depends on:** Task 2.2

Implement `_add_rooftop_assets(bm, width, depth, height, rng)`:

**Parapet (always):**
1. Select top face; `bmesh.ops.inset_individual(thickness=0.3)`.
2. Select the border loop; extrude upward by 0.5 m.

**Water tower (30 % probability):**
1. `bmesh.ops.create_circle(bm, cap_ends=True, segments=8, radius=0.6)`.
2. Translate to rooftop position `(x_offset, y_offset, height + 0.5)`.
3. Extrude the top circle upward by 1.5 m.
4. Add a conical cap: scale top loop to 0.0, fill.

**HVAC unit (40 % probability):**
1. Create a small box `(1.2 × 0.8 × 0.6)` via direct vertex creation.
2. Translate to a corner of the rooftop.
3. Add 3 horizontal loop-cuts for vent slats using `bmesh.ops.bisect_plane`.

Use `rng.random()` (the NumPy RNG passed from the main layout function) for
probability rolls, ensuring rooftop variation is seeded and reproducible.

Acceptance criteria:
- [ ] Every building has a parapet after generation.
- [ ] Water tower and HVAC probabilities match within 5 % over 100 buildings with
      a fixed seed.
- [ ] No `bpy.ops.*` calls.

---

## Phase 3 – Instancing System

### Task 3.1 – Create `sceneforge/instancing.py`
**Files:** `sceneforge/instancing.py` (new)
**Depends on:** nothing (pure Blender API)

Implement `InstanceLibrary` as specified in Design §2.4:

1. `__init__`: create or retrieve `SF_Prototypes` collection; exclude it from render
   layer visibility (`bpy.context.view_layer.layer_collection` lookup).
2. `register_prototype(name, build_fn)`: call `build_fn()` → mesh; create object; link
   to `SF_Prototypes`; set `obj.hide_render = True`; store in `self._registry`.
3. `place_instance(proto_name, location, rotation, scale, parent)`:
   - Create `Empty` object, set `instance_type = 'COLLECTION'`,
     `instance_collection = SF_Prototypes`.
   - Apply location/rotation/scale.
   - Return the Empty.
4. `batch_place(proto_name, transforms)`:
   - `transforms` is `np.ndarray` shape `(N, 9)`.
   - Loop over rows (N is expected to be ≤ 1000; Python loop acceptable here since
     Blender object creation is the bottleneck, not the Python loop).
   - Return list of Empty objects.

Acceptance criteria:
- [ ] After registering 3 prototypes and placing 100 instances, `bpy.data.meshes`
      contains exactly 3 additional mesh data-blocks (one per prototype).
- [ ] `SF_Prototypes` collection exists in scene after first `register_prototype` call.
- [ ] Prototypes are not visible in rendered output.

---

### Task 3.2 – Integrate instancing into buildings pipeline
**Files:** `sceneforge/buildings.py`
**Depends on:** Task 3.1, Task 2.5

1. At the start of `generate_buildings`, create an `InstanceLibrary`.
2. Register rooftop asset prototypes (`water_tower`, `hvac_unit`) via
   `instance_lib.register_prototype(...)`.
3. Replace direct in-BMesh rooftop geometry (Task 2.5) with calls to
   `instance_lib.place_instance(...)` for water towers and HVAC units, parented to their
   building object.
4. The parapet remains as direct BMesh geometry (it is part of the building silhouette).

Trade-off note: window geometry stays as BMesh because each building's windows differ
in count; window instancing via Geometry Nodes is deferred to Task 3.3.

Acceptance criteria:
- [ ] 20 buildings with rooftop assets add ≤ 2 new mesh data-blocks for rooftops
      (one water tower proto, one HVAC proto).
- [ ] Rooftop instances are parented to their building and move with it.
- [ ] `bpy.data.meshes` total count satisfies NFR-4 from requirements.

---

### Task 3.3 – Geometry Nodes window grid (opt-in)
**Files:** `sceneforge/buildings.py`, `sceneforge/geonodes_windows.py` (new)
**Depends on:** Task 2.3, Task 3.1
**Condition:** Only implemented if `use_geometry_nodes_windows = true` in props

Create `sceneforge/geonodes_windows.py`:

```python
def add_window_grid_modifier(
    obj: bpy.types.Object,
    floor_height: float,
    bay_width: float,
    frame_width: float,
    recess_depth: float,
) -> None:
    """Add a Geometry Nodes modifier that tiles a window instance across the facade."""
```

Approach:
1. Create (or reuse) a `NodeGroup` named `SF_WindowGrid`.
2. Inside the node group: `Mesh Line` (count = floors) → `Instances on Points` with
   a window frame mesh input → `Realize Instances`.
3. Add modifier to `obj`; set inputs from parameters.

Guard: wrap entire function in `if bpy.app.version >= (4, 0, 0)` — GN API is stable
from Blender 4.0. For Blender 3.6, fall through to BMesh path.

In `buildings.py`, after BMesh construction:
```python
if props.use_geometry_nodes_windows and bpy.app.version >= (4, 0, 0):
    from .geonodes_windows import add_window_grid_modifier
    add_window_grid_modifier(obj, ...)
else:
    _add_windows(bm, ...)   # existing BMesh path
```

Acceptance criteria:
- [ ] With `use_geometry_nodes_windows=False`, pipeline is identical to Task 2.3 output.
- [ ] With `use_geometry_nodes_windows=True` on Blender 4.x, building object has a GN
      modifier and window mesh data-block count does not grow with building count.
- [ ] On Blender 3.6, flag is silently ignored (BMesh fallback used).

---

## Phase 4 – Add-on Architecture

### Task 4.1 – Rewrite `sceneforge/__init__.py`
**Files:** `sceneforge/__init__.py`
**Depends on:** Task 1.3 (properties.py), Phase 2 tasks, Phase 3 tasks

1. Add `bl_info` dict (see Design §2.1).
2. Import all classes from `properties.py`, `operators.py`, `panels.py`.
3. Implement `register()` and `unregister()` using `_CLASSES` list.
4. Attach `SceneForgeProperties` to `bpy.types.Scene.sceneforge` in `register()`.
5. Keep `__version__` string synced with `bl_info["version"]`.
6. Remove old `__author__` and module docstring imports of pipeline modules
   (those now live in `operators.py`).

Acceptance criteria:
- [ ] `bpy.utils.register_class` succeeds for all 9 classes with no errors.
- [ ] `bpy.types.Scene.sceneforge` is accessible after `register()`.
- [ ] `unregister()` cleanly removes all classes and the scene property.
- [ ] Blender's Add-on preferences panel shows SceneForge AI with correct metadata.

---

### Task 4.2 – Create `sceneforge/operators.py`
**Files:** `sceneforge/operators.py` (new)
**Depends on:** Task 1.2, Task 4.1 (register order), all Phase 2+3 tasks

Implement the three operators specified in Design §2.5:

**`SCENEFORGE_OT_GenerateScene`:**
- `execute()` calls `run_pipeline(props)` from a new private `_pipeline.py` or inline.
- Progress bar: `wm.progress_begin(0, 7)`, increment at each pipeline stage.
- On success: `self.report({'INFO'}, "Scene generated.")`.
- On exception: `self.report({'ERROR'}, str(exc))`, return `{'CANCELLED'}`.
- `bl_options = {'REGISTER', 'UNDO'}`.

**`SCENEFORGE_OT_ExportConfig`:**
- `invoke()` opens a file browser (`context.window_manager.fileselect_add(self)`).
- `execute()` calls `scene_props_to_config(scene)` → `json.dump(...)`.

**`SCENEFORGE_OT_ImportConfig`:**
- `invoke()` opens a file browser.
- `execute()` calls `load_config(path)` → `config_to_scene_props(config, scene)`.

Acceptance criteria:
- [ ] `bpy.ops.sceneforge.generate_scene()` completes without error in a clean Blender
      session.
- [ ] Export writes valid JSON that can be re-imported without data loss.
- [ ] Operator supports Undo (Ctrl+Z) to revert scene to pre-generation state.

---

### Task 4.3 – Create `sceneforge/panels.py`
**Files:** `sceneforge/panels.py` (new)
**Depends on:** Task 1.3, Task 4.2

Implement all panel classes from Design §2.6:

- Root panel: `bl_space_type='VIEW_3D'`, `bl_region_type='UI'`, `bl_category='SceneForge'`.
- Sub-panels: `bl_parent_id = 'VIEW_3D_PT_SceneForgePanel'`, `bl_options={'DEFAULT_CLOSED'}`.
- Footer row in root `draw()`:
  ```python
  row = layout.row(align=True)
  row.scale_y = 1.4
  row.operator("sceneforge.generate_scene", icon='SCENE')
  row.operator("sceneforge.import_config", icon='IMPORT', text="")
  row.operator("sceneforge.export_config", icon='EXPORT', text="")
  ```
- Stats row: show `len(bpy.data.objects)`, `len(bpy.data.meshes)`, `props.seed`.

Acceptance criteria:
- [ ] Panel appears in `View3D → N-panel → SceneForge` tab after add-on registration.
- [ ] All properties are editable live; changes persist in scene data.
- [ ] Sub-panels collapse/expand independently.
- [ ] "Generate Scene" button triggers the operator with visible progress.

---

### Task 4.4 – Update `main.py` to CLI shim
**Files:** `main.py`
**Depends on:** Task 4.1, Task 4.2

Rewrite `main.py` per Design §2.9:
- Remove direct pipeline imports (scene, ground, buildings, etc.).
- Import `sceneforge` (which calls `register()` via `__init__.py` — note: in headless
  Blender, add-on registration must be triggered manually; call
  `sceneforge.register()` explicitly).
- Parse `--config` from `sys.argv`.
- Call `config_to_scene_props` then `bpy.ops.sceneforge.generate_scene()`.
- Handle `--render` flag.

Acceptance criteria:
- [ ] `blender --background --python main.py` runs without error.
- [ ] `blender --background --python main.py -- --config config.json --render` produces
      output image.
- [ ] No pipeline logic remains in `main.py` (all delegated to operator).

---

## Phase 5 – Material Enhancements

### Task 5.1 – Emissive material + seeded concrete
**Files:** `sceneforge/materials.py`
**Depends on:** nothing (pure material API)

1. Add `variation_seed: int = 0` parameter to `make_concrete_material`.
   Replace `random.uniform(...)` with `random.Random(variation_seed).uniform(...)`.

2. Implement `make_emissive_material(name, color, strength)` using an Emission shader
   node instead of Principled BSDF:
   ```python
   emission_node = mat.node_tree.nodes.new("ShaderNodeEmission")
   emission_node.inputs["Color"].default_value = (*color, 1.0)
   emission_node.inputs["Strength"].default_value = strength
   ```

3. Add `night_mode: bool = False` to `apply_scene_materials`. When `True`, replace
   glass material (slot 1) on all buildings with an emissive variant.

4. Add `night_mode` `BoolProperty` to `SceneForgeProperties` (update Task 1.3).
   Add to `VIEW_3D_PT_SF_Render` panel (update Task 4.3).

Acceptance criteria:
- [ ] Two calls to `make_concrete_material("Mat_A", variation_seed=7)` return identical
      colour values.
- [ ] `make_emissive_material` creates a material with `ShaderNodeEmission`, not BSDF.
- [ ] With `night_mode=True`, all window slots have emissive materials.
- [ ] With `night_mode=False`, behaviour is identical to current implementation.

---

## Phase 6 – Polish & Verification

### Task 6.1 – Update `requirements.txt`
**Files:** `requirements.txt`
**Depends on:** nothing

- Replace `fake-bpy-module-latest==20240917` with `fake-bpy-module-4x`.
- Add a comment explaining the Blender 3.6 / 4.x compatibility target.

---

### Task 6.2 – Update `README.md`
**Files:** `README.md`
**Depends on:** all prior tasks

Document:
1. Installation as a Blender Add-on (zip the `sceneforge/` directory, install via
   Blender Preferences → Add-ons → Install).
2. Using the N-panel UI.
3. Headless/CLI usage with `main.py`.
4. New `config.json` keys (`floor_height`, `bay_width`, `entryway_probability`, `seed`,
   `window_frame_width`, `window_recess_depth`, `use_geometry_nodes_windows`).
5. Blender version compatibility matrix.

---

### Task 6.3 – End-to-end smoke test (headless)
**Files:** No source changes; validation only
**Depends on:** all prior tasks

Run:
```
blender --background --python main.py -- --config config.json
```

Verify:
- [ ] Script exits with code 0.
- [ ] Blender console shows `[✓]` for all 8 pipeline stages.
- [ ] `bpy.data.objects` count > 0 after run.
- [ ] No `bpy.ops` calls appear in buildings.py, instancing.py, or materials.py stack
      traces (audit via grep).

---

## Task Dependency Graph

```
1.1 ──► 1.2
1.3 ──────────────────────────────────────────────────────────┐
                                                               ▼
2.1 ──► 2.2 ──► 2.3 ──► 2.4                              4.1, 4.2, 4.3
             └──► 2.5 ──► 3.2 ◄── 3.1
                        └──► 3.3

1.2 ──► 4.2
4.1 ──► 4.2 ──► 4.3 ──► 4.4

5.1 (independent, merge before 4.2)

6.1, 6.2, 6.3 (final, depend on all above)
```

---

## Completion Criteria

The upgrade is complete when:

1. `blender --background --python main.py` runs without error.
2. The add-on installs from a ZIP and the N-panel is visible in `View3D`.
3. "Generate Scene" operator completes with 20 buildings, each with floor/bay
   subdivision, window insets, and probabilistic entryways and rooftop assets.
4. `bpy.data.meshes` count ≤ `building_count + prototype_types + 3` (NFR-4).
5. No `bpy.ops.*` calls in `buildings.py`, `instancing.py`, or `materials.py`.
6. Same `seed` value produces byte-identical `.blend` scene data across two runs.
