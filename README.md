# BeaverSim 🦫

An agent-based simulation framework for modeling beaver behavior and ecological engineering in realistic terrains. BeaverSim simulates beaver colonies interacting with Digital Elevation Model (DEM) data, including vegetation dynamics, resource harvesting, and environmental modifications.

## Overview

BeaverSim provides a modular simulation environment where autonomous beaver agents:
- Navigate realistic terrain based on real-world elevation data
- Harvest vegetation and manage resources
- Reinforce canals and and modify their environment
- Exhibit exploration and foraging behaviors

The framework is built on a flexible backend architecture supporting visualization, multi-agent coordination, and environmental dynamics.

## Installation

### Prerequisites

- Python 3.8+
- pip package manager
- (Recommended) Virtual environment manager (venv, conda, or virtualenv)
- **Git LFS** (Large File Storage) - Required for downloading example datasets
- (Optional but recommended) **Visual Studio Code** with Python and Jupyter extensions - for integrated notebook editing and visualization

### Recommended IDE Setup (Optional)

For the best development and visualization experience, we recommend using **Visual Studio Code**:

1. **Install VS Code**: Download from [code.visualstudio.com](https://code.visualstudio.com/)

2. **Install Required Extensions**:
   - **Python** (by Microsoft) - for Python language support
   - **Jupyter** (by Microsoft) - for notebook support with inline plots

3. **Benefits**:
   - Edit and run notebooks directly in the IDE
   - Inline visualization of plots and simulation results
   - Integrated terminal and debugging
   - Better code navigation and IntelliSense

**Alternative**: You can also use the classic Jupyter Notebook interface in your browser (instructions provided below).

### Setup

1. **Install Git LFS** (if not already installed):

**On Ubuntu/Debian:**
```bash
sudo apt-get install git-lfs
```

**On macOS:**
```bash
brew install git-lfs
```

**On Windows:**
Download and install from [git-lfs.github.com](https://git-lfs.github.com/)

**Initialize Git LFS:**
```bash
git lfs install
```

2. Clone the repository:
```bash
git clone https://github.com/beaverbotassistance/BeaverSim.git
cd BeaverSim
```

**Note**: The repository uses Git LFS for large CSV dataset files. After cloning, if you see pointer files instead of actual data in `beaversim/utils/example_datasets/`, run:
```bash
git lfs pull
```

3. Create and activate a Python virtual environment (recommended):

**Using venv:**
```bash
python -m venv beaversim_env
source beaversim_env/bin/activate  # On Windows: beaversim_env\Scripts\activate
```

**Using conda:**
```bash
conda create -n beaversim python=3.10
conda activate beaversim
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Test the installation:
```bash
python -c "import beaversim; print('BeaverSim successfully installed')"
```

## Quick Start

### 1. Interactive DEM Processing

Start by exploring how to process Digital Elevation Model data.

**Using VS Code (Recommended):**
- Open `beaversim/utils/dem_conversion_interactive.ipynb` in VS Code
- Click "Run All" or execute cells individually
- Plots will display inline within the editor

**Using Jupyter Notebook (Browser):**
```bash
jupyter notebook beaversim/utils/dem_conversion_interactive.ipynb
```

This interactive notebook teaches you how to:
- Load and process raw elevation data
- Configure coordinate systems
- Remove water bodies using stream thresholding
- Export data ready for simulation

### 2. Run Simulations

Each site has its own folder in `notebooks/simulations/` with two notebooks:

| Site | Folder | Data |
|---|---|---|
| Acadia National Park, Maine | `acadia/` | DEM, 0.5 m |
| Rumney Marsh, Boston | `rumney_marsh/` | DEM, 1 m |
| Rumney Ranch A2, Montana | `rumney_ranch/` | RGB, 1 m |

- **`run_simulation.ipynb`** runs one simulation with a **live dashboard** that refreshes while it runs
  (landscape now, change since start, trail traffic by role, swarm and environment metrics).
- **`run_montecarlo.ipynb`** runs several conditions × seeds in parallel; the comparison plot is redrawn
  each time a run finishes.

Every run is saved as a small **run record** (`run.json` + `series.npz` + `agents.npz` + `snapshots.npz`,
see `beaversim/records.py`) under `output/simulations/<site>/`.

Simulations can also be run from Python without notebooks:

```python
from beaversim.experiments import run, run_montecarlo
run(config, "output/simulations/my_run")
run_montecarlo(config, "output/simulations/my_experiment", seeds=range(1, 6),
               conditions={"visits": {"robot.exploration_map": ["vegetation_visits", "vegetation_visits"]}},
               processes=10)
```

### 3. Analyse Results

- **`notebooks/analysis/run_report.ipynb`**: report for one run (what was simulated, landscape change,
  trail traffic, evolution, environment and swarm metrics, agent diagnostics).
- **`notebooks/analysis/montecarlo_report.ipynb`**: conditions compared across seeds (mean ± 1σ).

Set the run or experiment folder at the top of the notebook and run all cells.

## DEM Data Processing

### Processing Your Own Elevation Data

After trying the demo notebooks, you can process your own DEM data using the interactive converter:

```bash
jupyter notebook beaversim/utils/dem_conversion_interactive.ipynb
```

The notebook provides a step-by-step workflow:
1. **Loading CSV data** with elevation coordinates
2. **Setting resolution** and resampling
3. **Normalizing elevation** to simulation ranges
4. **Stream threshold removal** to identify water bodies
5. **Coordinate transformation** between CRS systems
6. **Polygon masking** to select regions of interest
7. **Exporting processed data** ready for simulation

### Supported Data Formats

- **Geographic coordinates**: CSV with `x` (longitude), `y` (latitude), `elevation`
- **Projected coordinates**: CSV with `X_m`, `Y_m`, `elevation`
- **Output format**: NumPy arrays (.npy) with metadata JSON

### EPSG Coordinate Systems

The tool supports automatic conversion between coordinate reference systems:
- **WGS84** (EPSG:4326): Standard GPS coordinates
- **NAD83 State Plane**: Regional projected systems (feet or meters)
- Custom EPSG codes for any region

Example regions:
- **Massachusetts**: EPSG:6483 (meters) or EPSG:2249 (feet)
- **Maine**: EPSG:6484
- Find yours at [epsg.io](https://epsg.io/)

## Project Structure

```
BeaverSim/
├── beaversim/
│   ├── ral/                      # Simulator core
│   │   ├── backend/              # Mesa model and agent/environment adapters
│   │   ├── environment/          # Environment state and dynamics
│   │   ├── robot/                # Beaver agent behaviour, control and dynamics
│   │   └── algorithms/           # Neighbourhoods and gradients
│   ├── experiments.py            # Headless runners: run(), run_montecarlo()
│   ├── records.py                # Run record format (writer and loader)
│   ├── viz/                      # Figures: theme, primitives, single-run, Monte Carlo, live dashboard
│   └── constants.py
├── data_acquisition/             # DEM / RGB to simulation matrices
├── notebooks/
│   ├── notebooks_DEM/            # DEM conversion
│   ├── notebooks_RGB/            # RGB conversion
│   ├── simulations/<site>/       # run_simulation, run_montecarlo
│   └── analysis/                 # run_report, montecarlo_report
├── requirements.txt
└── README.md
```

## Visualization

All figures come from `beaversim.viz` and share one theme:

- **Media presets**: `viz.use_theme("chapter" | "paper" | "slides")` sets every size.
- **Palette**: every colour is a named token in `viz.Palette` (roles, landscape, change, compared series).
  Export with `viz.Palette().to_json("palette.json")`, edit, and load with `viz.use_theme(palette="palette.json")`
  to restyle every figure.
- **Saving**: `viz.save(fig, "output/figures/name")` writes PDF and PNG.

## Dependencies

Core dependencies:
- `numpy`: Numerical computing and array operations
- `scipy`: Scientific computing and optimization
- `matplotlib`: Visualization and plotting
- `mesa` (v1.2.0): Agent-based modeling framework
- `jupyter`: Interactive notebook environment (includes ipykernel, ipython, ipywidgets)

See `requirements.txt` for complete list.

## Contributing

Contributions are welcome! Areas for improvement:
- Additional agent behaviors
- Enhanced environmental dynamics
- Performance optimizations
- New visualization tools
- Documentation and examples

## Citation

If you use BeaverSim in your research, please cite:

```bibtex
@software{beaversim2025,
  title={BeaverSim: A Multi-Agent Emulator for Beaver-Mediated Landscapes},
  year={2025},
  url={https://github.com/beaverbotassistance/BeaverSim}
}
```

## License

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

## Contact

For questions, issues, or collaboration:
- Open an issue on GitHub

## Acknowledgments

This is a research tool developed for ecological engineering simulation.

---

**Note**: This is a research tool. Simulation results should be validated against real-world observations before drawing ecological conclusions.