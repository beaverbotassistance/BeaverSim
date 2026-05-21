# BeaverSim - Biomimicry at the landscape scale

BeaverSim is an open-source research platform that models how small, autonomous agents inspired by North American beavers interact with real terrain to produce adaptive, landscape-scale change. Rather than prescribing final forms, BeaverSim focuses on process-driven emergence: how simple local behaviors and environmental feedbacks combine to produce ponds, channels, trails, and vegetation dynamics using Digital Elevation Model (DEM) and RGB aerial imagery data.

## Overview

- **Goal:** Provide a modular, extensible ABM testbed to explore how biologically inspired behaviors produce landscape-scale features and networks.
- **Approach:** Multi-Agent Simulation that integrates DEMs and aerial imagery with biologically plausible beaver-like behavioral policies and environmental feedbacks.
- **Key features:**
   - DEM/RGB import, processing, and water-masking tools
   - Modular backends for visualization and simulation control
   - Pre-configured demo scenarios and notebooks for quick experimentation
   - Per-agent analytics and visualization tools for tracking emergent patterns

## Background & Motivation

Landscapes are Complex Adaptive Systems shaped by geology, hydrology, and continuous reciprocal interactions with living agents. BeaverSim brings biomimicry to the landscape scale by using Agent-Based Modeling (ABM) to study how individual behaviors aggregate into persistent landscape structures. The North American beaver is a compelling case study because its dam-building, canal-digging, and foraging behaviors exemplify emergent, process-driven landscape engineering.

## Scope and Contributions

This repository provides:
- An open-source simulation suite that couples DEM inputs and RGB imagery with multi-agent beaver teams.
- Biologically plausible behavioral rules that reproduce qualitative patterns such as ponds, trails, and persistent visit networks.
- Interactive notebooks and demo scenarios that support both data preparation and simulation analysis.
- A post-processing workflow for comparing simulated outputs with real-world imagery and terrain-derived baselines.

The codebase is designed as a research testbed to be extended with new behaviors, metrics, and validation experiments.

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

**Note**: The repository uses Git LFS for large CSV dataset files. After cloning, if you see pointer files instead of actual data in `data_acquisition/example_datasets/`, run:
```bash
git lfs pull
```

3. Create and activate a Python virtual environment (recommended):

**Using venv:**
```bash
python -m venv beaversim_env
```

**PowerShell:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\beaversim_env\Scripts\Activate.ps1
```

**Command Prompt:**
```bat
.\beaversim_env\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source beaversim_env/bin/activate
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

### 1. Start With Data-Preparation Notebooks

If you want to understand how terrain and imagery become simulation inputs, begin here:

- `notebooks/notebooks_DEM/dem_conversion_Acadia_interactive.ipynb` - Acadia DEM workflow for loading CSV elevation data, resampling, masking water, and exporting simulation-ready arrays
- `notebooks/notebooks_DEM/dem_conversion_RumneyMarsh_interactive.ipynb` - Rumney Marsh DEM workflow on a larger site with the same processing pipeline
- `notebooks/notebooks_RGB/rgb_conversion_RumneyRanch_A2_interactive.ipynb` - RGB workflow that converts aerial imagery into a vegetation-quality matrix
- `notebooks/notebooks_RGB/rgb_conversion_RumneyRanch_A2_iterative.ipynb` - iterative RGB workflow for revisiting the same site with alternative preprocessing choices

**Using VS Code (Recommended):**
- Open any notebook in VS Code and select the `beaversim_env` virtual environment
- Run cells individually or choose "Run All"
- Plots and intermediate results will render inline

These notebooks walk through loading raw elevation or imagery data, configuring coordinate systems, masking water bodies, and exporting simulation-ready outputs.

### 2. Run The Simulation Demos

The simulation notebooks live under `notebooks/simulations/` and show how processed inputs are used in the agent model:

- `notebooks/simulations/demo_csv_acadia.ipynb` - small DEM-based demo on Acadia data; best first run
- `notebooks/simulations/demo_csv_boston.ipynb` - larger DEM-based demo with heavier computation
- `notebooks/simulations/demo_rgb_montana.ipynb` - RGB-based simulation example derived from aerial imagery
- `notebooks/simulations/data_analysis.ipynb` - post-processing notebook for environment heatmaps, growth statistics, snapshots, and agent diagnostics

**Using VS Code (Recommended):**
- Open the notebook you want to explore
- Run cells to inspect simulation outputs and visualizations inline

Start with Acadia if you want the quickest introduction, then move to Boston or RGB Montana once you are comfortable with the workflow.

## DEM and RGB Data Processing

### Processing DEM Inputs

Use the DEM notebooks to prepare your own elevation data (e.g., ```notebooks/notebooks_DEM/dem_conversion_RumneyMarsh_interactive.ipynb```):

The DEM workflow provides a step-by-step pipeline:
1. **Loading CSV data** with elevation coordinates
2. **Setting resolution** and resampling
3. **Normalizing elevation** to simulation ranges
4. **Stream threshold removal** to identify water bodies
5. **Coordinate transformation** between CRS systems
6. **Polygon masking** to select regions of interest
7. **Exporting processed data** ready for simulation

### Processing RGB Inputs

Use the RGB notebooks to derive vegetation-quality maps from aerial imagery (e.g., ```notebooks/notebooks_RGB/rgb_conversion_RumneyRanch_A2_interactive.ipynb```):

The RGB workflow provides:
1. **Baseline aggregation** from multiple images of the same site
2. **Shadow correction** to stabilize illumination differences
3. **Vegetation indices** such as NDVI, VARI, ExG, and CWI
4. **Water detection** and mask post-processing
5. **Quality matrix export** for simulation initialization and later comparison with outputs

### Supported Data Formats

- **DEM inputs**: CSV with `x` (longitude), `y` (latitude), `elevation` or projected `X_m`, `Y_m`, `elevation`
- **RGB inputs**: Folders of aerial imagery for baseline aggregation and vegetation scoring
- **Output format**: NumPy arrays (.npy) and metadata JSON for DEM; vegetation-quality matrices and masks for RGB

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
├── beaversim/                    # Core simulation package
│   ├── ral/                      # Robot abstraction layer and backend utilities
│   ├── environment/              # Environment simulation logic
│   ├── robot/                    # Beaver agent behavior modules
│   ├── scenarios/                # Pre-defined simulation scenarios
├── data_acquisition/             # DEM/RGB conversion helpers and source data
│   ├── modules/
│   │   ├── dem_to_matrix.py
│   │   └── rgb_to_matrix.py
│   └── example_datasets/
│       ├── ACADIA_DEM/
│       ├── RUMNEY_MARSH_DEM/
│       └── RUMNEY_RANCH_RGB/
├── notebooks/                    # Interactive notebooks and demos
│   ├── notebooks_DEM/
│   ├── notebooks_RGB/
│   └── simulations/
├── requirements.txt
└── README.md
```

## Visualization

The framework provides comprehensive visualization through the same plotting helpers used in `notebooks/simulations/data_analysis.ipynb`.

### Environment Heatmaps

Three-panel visualizations showing:

1. **Initial Vegetation Quality**
   - Starting state of the environment or terrain input
   - Elevation / vegetation quality with a blue-brown-green colormap
   - Water bodies and other negative-value cells shown as muted overlays

2. **Current Vegetation Quality**
   - Real-time vegetation state during simulation
   - Shows vegetation depletion from harvesting and regrowth dynamics over time
   - Agent positions marked (red = explorers, black = expanders)
   - Home base locations (gray rectangles)
   - Optional agent trajectories and motion destination markers

3. **Agent Visit Frequency**
   - Heatmap showing exploration patterns and territorial behavior
   - Color-coded by visit intensity and role
   - Overlay shows water bodies for reference

### Simulation Analytics

The analysis notebook also tracks per-agent and landscape-level statistics:

1. **Distance from Initial Position**
   - Movement range over simulation
   - River crossing events marked in blue
   - Territory exploration patterns

2. **Load Variation**
   - Current load vs maximum capacity
   - Harvesting efficiency
   - Resource transport patterns

3. **Control Error Norm**
   - PID controller performance
   - Navigation accuracy
   - Behavioral stability metrics

4. **Exploration Parameters**
   - Exploration eta (resource quality threshold)
   - Harvest threshold boundaries (min/max)
   - Adaptive behavior indicators

### Analysis Notebook Plots

`notebooks/simulations/data_analysis.ipynb` combines these with post-processing plots that compare stored simulation artifacts:

- **Growth statistics**: vegetation mean/median or mean ± standard deviation, plus seasonal growth and stochastic components
- **Spatial snapshots**: selected `maps/` and `visits/` `.npy` snapshots from a run
- **Real vs simulated vegetation**: side-by-side comparison of RGB-derived vegetation matrices and simulation maps
- **Motion diagnostics**: per-agent control error norm and speed over time, with destination changes highlighted

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
- Formal comparison metrics between different emergent landscapes
- Additional agent behaviors
- Enhanced environmental dynamics
- Performance optimizations
- New visualization tools and analysis notebooks
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
