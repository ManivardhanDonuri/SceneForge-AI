# SceneForge AI – Procedural 3D Scene Generator

A Blender Python application that automatically generates procedural 3D city environments and configures Cycles rendering through a JSON-driven configuration system.

---

## Features

- **Procedural City Generation** – Automatically places buildings, roads, and ground planes to form a complete city block layout
- **Building Generator** – Randomized multi-story buildings with configurable height, width, and density
- **Material System** – Reusable PBR materials: concrete, glass, metal, and ground
- **Lighting System** – Sun, area, and environment (HDRI) lighting configuration
- **Camera System** – Automatic camera positioning and scene framing based on environment size
- **Rendering Configuration** – Cycles engine setup, resolution, samples, and PNG output
- **JSON Configuration** – All scene parameters driven by a single `config.json` file
- **Modular Architecture** – Clean separation of concerns across focused Python modules

---

## Technologies

| Technology | Purpose |
|---|---|
| Python 3.10+ | Core scripting language |
| Blender Python API (`bpy`) | 3D scene manipulation and rendering |
| Blender Cycles | Path-tracing render engine |
| JSON | Scene configuration format |
| Git | Version control |

---

## Project Architecture

```
SceneForge-AI/
├── main.py                  # Entry point – orchestrates the full pipeline
├── config.json              # Scene configuration (edit this to customise output)
├── requirements.txt         # Python/Blender version requirements
├── README.md
├── LICENSE
├── .gitignore
└── sceneforge/
    ├── __init__.py
    ├── config_loader.py     # Loads and validates config.json
    ├── scene.py             # Scene initialisation and cleanup
    ├── buildings.py         # Procedural building mesh generation
    ├── ground.py            # Ground plane and road network generation
    ├── materials.py         # PBR material creation functions
    ├── lighting.py          # Sun, area, and environment lighting
    ├── camera.py            # Automatic camera placement and framing
    └── renderer.py          # Cycles render engine configuration
```

---

## Installation

### Prerequisites

- **Blender 3.6 LTS or 4.x** – [Download](https://www.blender.org/download/)
- Python is bundled with Blender; no separate install is needed for Blender scripts

### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/SceneForge-AI.git
   cd SceneForge-AI
   ```

2. Open Blender's **Scripting** workspace.

3. Open `main.py` in Blender's text editor.

4. Edit `config.json` to customise your scene (see Configuration section below).

5. Press **Run Script** inside Blender, or run from the terminal:
   ```bash
   blender --background --python main.py
   ```

---

## Usage

### Running from the terminal (headless / background mode)

```bash
blender --background --python main.py
```

Rendered PNG files are saved to the `output/` directory defined in `config.json`.

### Running inside Blender

1. Open Blender → switch to the **Scripting** workspace
2. Open `main.py`
3. Click **▶ Run Script**

---

## Configuration (`config.json`)

```json
{
  "environment": {
    "type": "city",
    "ground_size": 100,
    "road_width": 6
  },
  "buildings": {
    "count": 20,
    "min_height": 5,
    "max_height": 30,
    "min_width": 4,
    "max_width": 12,
    "spacing": 3
  },
  "lighting": {
    "sun": {
      "enabled": true,
      "energy": 5.0,
      "angle_degrees": 45
    },
    "area": {
      "enabled": true,
      "energy": 200,
      "size": 10
    },
    "environment": {
      "enabled": true,
      "strength": 0.5,
      "color": [0.2, 0.3, 0.5]
    }
  },
  "camera": {
    "auto_frame": true,
    "distance_factor": 1.5,
    "height": 25,
    "focal_length_mm": 35
  },
  "render": {
    "engine": "CYCLES",
    "samples": 128,
    "resolution_x": 1920,
    "resolution_y": 1080,
    "output_dir": "//output/",
    "file_format": "PNG"
  }
}
```

### Configuration Reference

| Key | Description |
|---|---|
| `environment.type` | Scene type – currently `"city"` |
| `environment.ground_size` | Size of the ground plane in Blender units |
| `buildings.count` | Number of buildings to generate |
| `buildings.min/max_height` | Building height range (Blender units) |
| `buildings.min/max_width` | Building footprint width range |
| `lighting.sun.energy` | Sun lamp intensity |
| `lighting.area.energy` | Area lamp intensity |
| `camera.auto_frame` | Automatically frame the full scene |
| `render.samples` | Cycles path-tracing samples |
| `render.resolution_x/y` | Output image resolution in pixels |
| `render.output_dir` | Output path (`//` = relative to .blend file) |

---

## Future Improvements

- Interior building details (windows, floors)
- Vegetation system (trees, grass)
- Multiple environment types: forest, desert, coastal
- HDRI sky loading from file
- Level-of-detail (LOD) system for large scenes
- Animation path generation for camera fly-throughs
- Blender add-on packaging for one-click install
- Export to glTF / FBX for use in game engines

---

## License

MIT License – see [LICENSE](LICENSE) for details.
