# Design – SceneForge AI Advanced Architecture Upgrade

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Blender Add-on Entry Point  (sceneforge/__init__.py)               │
│  bl_info · register() · unregister()                                │
│                                                                     │
│  ┌──────────────────────┐   ┌──────────────────────────────────┐   │
│  │  SceneForgeProperties│   │  VIEW_3D_PT_SceneForgePanel (UI)  │   │
│  │  (PropertyGroup on   │◄──│  Environment / Buildings /        │   │
│  │   bpy.types.Scene)   │   │  Lighting / Render sub-panels     │   │
│  └──────────┬───────────┘   └──────────────┬───────────────────┘   │
│             │                              │                        │
│             ▼                              ▼                        │
│       SCENEFORGE_OT_GenerateScene   SCENEFORGE_OT_ExportConfig      │
│       SCENEFORGE_OT_ImportConfig                                    │
└─────────────────────┬───────────────────────────────────────────────┘
                      │  calls pipeline modules
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Pipeline (same as today, driven by props instead of config dict)   │
│                                                                     │
│  scene.py ──► ground.py ──► buildings.py ──► materials.py          │
│                                  │                                  │
│                         instancing.py (new)                         │
│                                                                     │
│  lighting.py ──► camera.py ──► renderer.py                         │
└─────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
              config_loader.py  (extended)
```

---

## 2. Module Breakdown

### 2.1 `sceneforge/__init__.py` – Add-on Bootstrap

**Responsibilities:** Blender add-on registration; nothing else.

```python
bl_info = {
    "name": "SceneForge AI",
    "author": "SceneForge AI",
    "version": (2, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > SceneForge",
    "description": "Procedural city scene generation with advanced geometry engine",
    "category": "3D View",
}

# Classes registered in order (dependencies first)
_CLASSES = [
    SceneForgeProperties,          # PropertyGroup
    SCENEFORGE_OT_GenerateScene,   # Operator
    SCENEFORGE_OT_ExportConfig,    # Operator
    SCENEFORGE_OT_ImportConfig,    # Operator
    VIEW_3D_PT_SceneForgePanel,    # Panel (root)
    VIEW_3D_PT_SF_Environment,     # Sub-panel
    VIEW_3D_PT_SF_Buildings,       # Sub-panel
    VIEW_3D_PT_SF_Lighting,        # Sub-panel
    VIEW_3D_PT_SF_Render,          # Sub-panel
]

def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sceneforge = bpy.props.PointerProperty(
        type=SceneForgeProperties
    )

def unregister():
    del bpy.types.Scene.sceneforge
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
```

---

### 2.2 `sceneforge/properties.py` – Property Group (new file)

Holds all `bpy.props.*` declarations, separated from `__init__.py` for clarity.

```
SceneForgeProperties (PropertyGroup)
├── Environment
│   ├── ground_size         : FloatProperty  (min=10, max=500, default=100)
│   └── road_width          : FloatProperty  (min=1, max=20,  default=6)
├── Buildings
│   ├── count               : IntProperty    (min=1, max=200, default=20)
│   ├── min_height          : FloatProperty  (min=1, default=5)
│   ├── max_height          : FloatProperty  (min=1, default=30)
│   ├── min_width           : FloatProperty  (min=1, default=4)
│   ├── max_width           : FloatProperty  (min=1, default=12)
│   ├── spacing             : FloatProperty  (min=0, default=3)
│   ├── floor_height        : FloatProperty  (min=1, default=3)
│   ├── bay_width           : FloatProperty  (min=1, default=4)
│   ├── entryway_probability: FloatProperty  (min=0, max=1, default=0.3)
│   └── use_geonode_windows : BoolProperty   (default=False)
├── Lighting  (mirrors existing lighting sub-keys)
│   ├── sun_enabled         : BoolProperty
│   ├── sun_energy          : FloatProperty
│   ├── sun_angle           : FloatProperty
│   ├── area_enabled        : BoolProperty
│   ├── area_energy         : FloatProperty
│   ├── env_enabled         : BoolProperty
│   ├── env_strength        : FloatProperty
│   └── env_color           : FloatVectorProperty (subtype='COLOR')
├── Render
│   ├── engine              : EnumProperty   [('CYCLES','Cycles',''), ('BLENDER_EEVEE','EEVEE','')]
│   ├── samples             : IntProperty    (min=1, default=128)
│   ├── resolution_x        : IntProperty    (min=1, default=1920)
│   ├── resolution_y        : IntProperty    (min=1, default=1080)
│   └── output_dir          : StringProperty (subtype='DIR_PATH')
└── seed                    : IntProperty    (default=42)
```

The `PropertyGroup` is defined as a standalone class; `__init__.py` attaches it to
`bpy.types.Scene.sceneforge` during `register()`.

---

### 2.3 `sceneforge/buildings.py` – Geometry Engine (full rewrite)

#### 2.3.1 Public API

```python
def generate_buildings(props: SceneForgeProperties | dict) -> list[bpy.types.Object]
```

Accepts either a `SceneForgeProperties` reference or a plain dict (for headless mode).
Returns a list of top-level building objects.

#### 2.3.2 Layout Grid (NumPy)

```python
def _compute_placement_grid(
    ground_size: float,
    count: int,
    max_width: float,
    spacing: float,
    seed: int,
) -> np.ndarray  # shape (N, 2) – (x, y) centres
```

Uses `np.random.default_rng(seed)` for a self-contained RNG. Candidate positions are
generated as a NumPy array and AABB overlap is tested with vectorised subtraction and
`np.all()` — no Python loop per-candidate.

Occupancy grid approach:
```
cell_size = max_width + spacing
grid_w    = int(ground_size / cell_size)
occupied  = np.zeros((grid_w, grid_w), dtype=bool)   # O(1) lookup
```

#### 2.3.3 BMesh Building Construction

Each building is built in a single `bmesh.new()` context — no `bpy.ops` calls.

```
_build_facade(bm, width, depth, height, floor_height, bay_width)
│
├── Step 1 – Base extrusion
│   Create bottom face (width × depth), extrude upward to height.
│   Result: closed box, 6 faces.
│
├── Step 2 – Floor loops (loop-cut equivalent via BMesh)
│   Calculate floor Z positions from floor_height.
│   For each floor boundary Z: select horizontal edge loop, bmesh.ops.bisect_plane()
│   Result: horizontal edge rings at each floor.
│
├── Step 3 – Bay columns (vertical cuts)
│   For each facade normal direction (4 sides):
│       Calculate bay X positions from bay_width.
│       bmesh.ops.bisect_plane() on that facade's face set.
│   Result: facade subdivided into W×H cells.
│
├── Step 4 – Window inset (per cell, floors 1..N-1)
│   For each cell face on a facade:
│       bmesh.ops.inset_individual(faces=[cell], thickness=frame_width)
│       bmesh.ops.extrude_face_region on inner face, translate by -recess_depth
│   Result: recessed window opening per cell.
│
├── Step 5 – Entryway (ground floor centre cell, probabilistic)
│   Select centre bay, ground-floor face.
│   bmesh.ops.inset_individual with larger thickness.
│   Extrude arch (N-gon approximated as 3-segment arc bridged with bmesh.ops.bridge_loops)
│
└── Step 6 – Rooftop assets
    Delegated to _add_rooftop_assets(bm, width, depth, height, rng)
    ├── Parapet: extrude top border loop outward + upward
    ├── Water tower: bmesh.ops.create_circle + extrude (cylinder)
    └── HVAC: small box extrusion with vent slat loop-cuts
```

**Material slot assignment during construction:**
- Slot 0: concrete (assigned by `materials.py` after mesh creation)
- Slot 1: glass (assigned to window inner faces during Step 4 via `face.material_index = 1`)

#### 2.3.4 Key BMesh Operations Reference

| Goal | BMesh Op |
|---|---|
| Horizontal floor cuts | `bmesh.ops.bisect_plane(bm, geom=..., plane_co=co, plane_no=(0,0,1))` |
| Vertical bay cuts | `bmesh.ops.bisect_plane(bm, geom=..., plane_co=co, plane_no=(1,0,0) or (0,1,0))` |
| Window frame | `bmesh.ops.inset_individual(bm, faces=[f], thickness=t, depth=0)` |
| Window recess | `bmesh.ops.extrude_face_region` + `bmesh.ops.translate` |
| Cylinder asset | `bmesh.ops.create_circle` + `bmesh.ops.extrude_edge_only` |
| Cleanup | `bmesh.ops.remove_doubles` + `bmesh.ops.recalc_face_normals` |

---

### 2.4 `sceneforge/instancing.py` – Instance Library (new file)

```python
class InstanceLibrary:
    COLLECTION_NAME = "SF_Prototypes"

    def __init__(self):
        self._collection = _get_or_create_collection(self.COLLECTION_NAME)
        self._registry: dict[str, bpy.types.Object] = {}

    def register_prototype(
        self,
        name: str,
        build_fn: Callable[[], bpy.types.Mesh],
    ) -> bpy.types.Object:
        """Create mesh once, store in SF_Prototypes, hide from render."""

    def place_instance(
        self,
        proto_name: str,
        location: tuple,
        rotation: tuple = (0, 0, 0),
        scale: tuple = (1, 1, 1),
        parent: bpy.types.Object | None = None,
    ) -> bpy.types.Object:
        """Return an Empty linked to the prototype collection."""

    def batch_place(
        self,
        proto_name: str,
        transforms: np.ndarray,   # shape (N, 9): x,y,z, rx,ry,rz, sx,sy,sz
    ) -> list[bpy.types.Object]:
        """Vectorised batch placement from NumPy transform array."""
```

**Collection Instance pattern:**
```python
empty = bpy.data.objects.new(name, None)
empty.instance_type = 'COLLECTION'
empty.instance_collection = self._collection
empty.location = location
scene.collection.objects.link(empty)
```

This keeps the GPU vertex budget at `O(unique_prototypes)` regardless of instance count.

---

### 2.5 `sceneforge/operators.py` – Operators (new file)

#### `SCENEFORGE_OT_GenerateScene`

```python
class SCENEFORGE_OT_GenerateScene(bpy.types.Operator):
    bl_idname  = "sceneforge.generate_scene"
    bl_label   = "Generate Scene"
    bl_options = {'REGISTER', 'UNDO'}

    config_path: StringProperty(default="")  # CLI override

    def execute(self, context):
        wm = context.window_manager
        wm.progress_begin(0, 100)
        try:
            props = context.scene.sceneforge
            run_pipeline(props, progress_cb=lambda pct: wm.progress_update(pct))
            self.report({'INFO'}, "SceneForge: scene generated successfully.")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        finally:
            wm.progress_end()
```

#### `SCENEFORGE_OT_ExportConfig`

Serialises `scene.sceneforge` → `config.json` via `scene_props_to_config()` from
`config_loader.py`. Uses a `FileSelectParams`-style invoke for path picking.

#### `SCENEFORGE_OT_ImportConfig`

Reads `config.json` via `load_config()` and calls `config_to_scene_props(config, scene)`.

---

### 2.6 `sceneforge/panels.py` – UI Panels (new file)

```
VIEW_3D_PT_SceneForgePanel        (root, no draw body — acts as tab anchor)
├── VIEW_3D_PT_SF_Environment     (ground_size, road_width)
├── VIEW_3D_PT_SF_Buildings       (count, height range, width range, spacing,
│                                  floor_height, bay_width, entryway_prob,
│                                  use_geonode_windows)
├── VIEW_3D_PT_SF_Lighting        (sun, area, environment toggles + params)
└── VIEW_3D_PT_SF_Render          (engine, samples, resolution, output_dir)

Footer row (always visible):
  [Generate Scene]  [Import Config]  [Export Config]
  Verts: {n}   Instances: {m}   Seed: {s}
```

All sub-panels use `bl_parent_id` to nest under the root panel and
`bl_options = {'DEFAULT_CLOSED'}` so only the relevant section is open at a time.

---

### 2.7 `sceneforge/config_loader.py` – Extensions

Two new helpers added (existing `load_config` unchanged):

```python
def config_to_scene_props(config: dict, scene: bpy.types.Scene) -> None:
    """Write config dict values into scene.sceneforge properties."""

def scene_props_to_config(scene: bpy.types.Scene) -> dict:
    """Read scene.sceneforge properties into a config dict."""
```

New validated keys added to `REQUIRED_SECTION_KEYS["buildings"]`:
`floor_height`, `bay_width`, `entryway_probability`, `use_geometry_nodes_windows`

Top-level optional key: `seed` (default 42).

---

### 2.8 `sceneforge/materials.py` – Extensions

```python
def make_emissive_material(
    name: str = "Mat_Emissive",
    color: tuple = (1.0, 0.9, 0.7),
    strength: float = 2.0,
) -> bpy.types.Material:
    """Emission shader for lit windows (night mode)."""
```

`make_concrete_material` gains `variation_seed: int = 0` parameter;
`random.uniform` replaced with `random.Random(variation_seed).uniform(...)`.

`apply_scene_materials` gains `night_mode: bool = False` parameter;
window slots receive emissive material when `True`.

---

### 2.9 `main.py` – CLI Shim (minimal rewrite)

```python
import bpy
import sys, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import sceneforge  # triggers register() via bl_info path

def main():
    # Parse --config and --render from sys.argv
    config_path = _arg_value("--config", default=os.path.join(SCRIPT_DIR, "config.json"))

    # Load config → populate scene props
    from sceneforge.config_loader import load_config, config_to_scene_props
    config = load_config(config_path)
    config_to_scene_props(config, bpy.context.scene)

    # Invoke operator
    bpy.ops.sceneforge.generate_scene(config_path=config_path)

    if "--render" in sys.argv:
        bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    main()
```

---

## 3. Data Flow

```
config.json
    │  load_config()
    ▼
config dict
    │  config_to_scene_props()
    ▼
SceneForgeProperties (bpy.types.Scene.sceneforge)
    │  SCENEFORGE_OT_GenerateScene.execute()
    ▼
run_pipeline(props)
    ├── initialise_scene()
    ├── generate_ground(props.ground_size) → ground_obj
    ├── generate_roads(props.ground_size, props.road_width) → road_objs
    ├── generate_buildings(props) → building_objs
    │       ├── _compute_placement_grid(...)   [NumPy]
    │       ├── _build_facade(bm, ...)         [BMesh]
    │       └── instance_lib.batch_place(...)  [instancing.py]
    ├── apply_scene_materials(ground_obj, road_objs, building_objs, night_mode)
    ├── setup_lighting(props)
    ├── setup_camera(props.ground_size, ...)
    └── configure_renderer(props)
```

---

## 4. File Structure After Upgrade

```
SceneForge-AI/
├── main.py                      (CLI shim, minimal)
├── config.json                  (extended with new keys)
├── requirements.txt             (updated fake-bpy-module version)
├── README.md
├── LICENSE
└── sceneforge/
    ├── __init__.py              (bl_info, register/unregister)
    ├── properties.py            (NEW – SceneForgeProperties PropertyGroup)
    ├── operators.py             (NEW – GenerateScene, ExportConfig, ImportConfig)
    ├── panels.py                (NEW – UI panel classes)
    ├── instancing.py            (NEW – InstanceLibrary)
    ├── buildings.py             (REWRITE – BMesh geometry engine)
    ├── config_loader.py         (EXTENDED – new keys + prop helpers)
    ├── materials.py             (EXTENDED – emissive mat, seeded concrete)
    ├── scene.py                 (MINOR – remove bpy.ops.object.select_all)
    ├── ground.py                (UNCHANGED)
    ├── lighting.py              (UNCHANGED)
    ├── camera.py                (UNCHANGED)
    └── renderer.py              (UNCHANGED)
```

---

## 5. Key Design Decisions

### 5.1 No `bpy.ops` in Geometry Code
`bpy.ops.*` requires an active operator context that is absent in headless mode and during
unit tests. All mesh construction uses `bmesh` directly. Only `scene.py`'s initial clear
retains `bpy.ops.object.select_all` (acceptable since it runs once at pipeline start with
a known context).

### 5.2 Properties as Source of Truth
The UI writes to `SceneForgeProperties`; the operator reads from `SceneForgeProperties`.
`config.json` is only used for import/export, not as a runtime dependency. This makes the
tool fully usable without a file on disk.

### 5.3 NumPy for Layout, BMesh for Geometry
NumPy handles the 2-D spatial problem (placement grid, AABB checks, transform arrays).
BMesh handles the 3-D mesh problem (topology editing). The boundary is clean: NumPy
produces `(x, y)` positions; BMesh consumes them.

### 5.4 Instancing via Collection Instances, not Geometry Nodes (default)
Collection Instances work identically in Blender 3.6 LTS and 4.x and require no modifier
stack. Geometry Nodes window grids are an opt-in upgrade for Blender 4.x users who want
to push instance counts higher.

### 5.5 Backward-Compatible CLI
`main.py` remains a valid entry point. Users who previously ran
`blender --background --python main.py` can continue to do so unchanged.

---

## 6. Dependencies

| Package | Source | Purpose |
|---|---|---|
| `bpy` | Blender built-in | Blender Python API |
| `bmesh` | Blender built-in | Low-level mesh editing |
| `numpy` | Blender built-in (≥3.6) | Vectorised layout + transforms |
| `mathutils` | Blender built-in | Vector/matrix math in camera.py |
| `fake-bpy-module-4x` | pip (dev only) | IDE type stubs + CI |

No new runtime pip dependencies are introduced.
