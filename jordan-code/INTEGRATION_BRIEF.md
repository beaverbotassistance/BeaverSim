# BeaverSim × Landlab — Integration Brief and Plan

**Status as of 2026-09-03.** Written as a handoff document: it is self-contained, so a
future session (human or Claude) can pick the work up without the originating conversation.

Companion visual version: <https://claude.ai/code/artifact/29e9a242-e538-487e-897e-33148c7ba324>

---

## 1. Context

Two codebases that diverged months ago are being recombined:

- **BeaverSim** (this repo, `main` / `dev-rumneymarsh` / `dev_metric`) — Federico's
  agent-based beaver simulator.
- **Jordan Kennedy's pipeline** (`dev-jordan`) — a GIS + hydrology data pipeline.

The goal for the coming month is to integrate Jordan's terrain/hydrology work **into**
BeaverSim, and to run parameter studies on this machine (24 cores / 125 GB) rather than
on Jordan's.

`dev-jordan` is merged locally at **`d3fe4b8`** (fast-forward, 2 commits, +1.9 GB LFS).

---

## 2. What Jordan actually contributed

Two commits: a 7,218-line notebook (`0Building a digital world_crs_fixed_v2.ipynb`,
104 cells / 82 code) and ~1.9 GB of GIS data under `Datasets/`. No README, no
requirements file.

**It contains no agent-based model.** Mesa is imported in four places but no `Agent` or
`Model` subclass is ever defined — those imports are vestigial. The notebook builds and
characterises *terrain*. The beaver behaviour in the collaboration is entirely
BeaverSim's; Jordan's contribution is the world it runs on.

The hydrology tool is **Landlab** (not ANUGA).

### Pipeline stages

1. **Ingest** a USGS 1 m DEM GeoTIFF; detect CRS, bounds, resolution, nodata.
2. **Crop** to a study bbox, streaming the CSV in 1M-row chunks. Her run kept 180,456
   points — a 438 × 412 grid at 1 m (~44.6 acres) out of a 10 km × 10 km tile.
3. **Hydrology (Landlab).** `RasterModelGrid` in real metres, then
   `FlowAccumulator(flow_director="D8", depression_finder="DepressionFinderAndRouter")`
   to fill sinks and route flow. Produces `drainage_area` in m² (max 169,033 m² on her
   site); a percentile threshold turns it into a stream network.
   *Note: this is steady-state flow routing, not dynamic shallow-water.*
4. **Slope** via plane fit over each point's 12 nearest neighbours → `slope_degrees`,
   plus a `traversable` flag cut at 65°.
5. **Topographic maps.** USGS GeoPDFs warped to the DEM grid; pale-blue pixels detected
   in HSV → water mask → skeletonised → GeoJSON streamlines.
6. **NAIP aerial imagery.** 4-band (R, G, B, NIR) aligned to the DEM grid and sampled
   per point → NDVI, EVI, GNDVI, NormG.
7. **Provenance.** Per-dataset metadata JSON + site summary CSV.

### The master CSV schema (the real integration surface)

```
x, y, x_m, y_m, proj_epsg                  position, in a declared CRS
elevation                                  metres above datum
slope_degrees, traversable                 terrain cost / passability
drainage_area_m2, drainage_area_km2, percentile   routed water
label                                      stream / land classification
naip_R, naip_G, naip_B, naip_NIR           measured reflectance
veg_NDVI, veg_EVI, veg_GNDVI, veg_NormG    vegetation indices
```

---

## 3. Capability comparison

| Dimension | Jordan's pipeline | BeaverSim | Better |
|---|---|---|---|
| Terrain representation | Separate layers (elevation, slope, water, 4 veg indices) | One composite scalar `_map` (elevation + vegetation + river depth) | **Jordan** — the key gap |
| Units & georeferencing | Real metres, EPSG tracked end-to-end | Rescaled to `[-1,1]` on save; per-frame bounds not persisted | **Jordan** |
| Water | D8 flow routing + depression filling, physically derived | `grow_rivers()` decrements a scalar at fixed rate | **Jordan** |
| Vegetation | Measured from NAIP multispectral | Synthesised (seasonal skew-normal + mean reversion) | Split — hers real, ours dynamic |
| Agent behaviour | None | FSM tasks, explorer/builder roles, stigmergic visit maps, PID control, adaptive eta | **BeaverSim**, entirely |
| Time | Static snapshot | Multi-year evolution with feedback | **BeaverSim** |
| Software structure | One linear 7,218-line notebook | Layered package (`ral/`: backend, environment, robot, algorithms) | **BeaverSim** |
| Provenance | Metadata JSON + summary CSV | Bare `.npy`, no config snapshot | **Jordan** |
| Reproducibility | Deterministic | Seeded but broken (§4) | Neither |
| Tests / parallelism | None / none | None / none | Neither |

### The one structural change that matters

`_map` is a single array meaning three things at once. `grow_grass()` adds vegetation
growth into it and `grow_rivers()` subtracts channel depth from it, both in the same
numeric units as terrain height.

Treating vegetation as elevation is a *deliberate and defensible* modelling choice — but
it is what blocks integration, because Landlab needs an elevation field that means
elevation and nothing else in order to route water over it.

Splitting `_map` into named layers (elevation / vegetation / water) is the enabling
change for everything downstream. The composite view can survive as a derived property,
so agent logic need not change semantics.

---

## 4. CRITICAL: BeaverSim runs are not reproducible

**Do not run parameter sweeps before fixing this.**

`exploration_gradient_DN()` in `beaversim/ral/robot/modules/module_beaver.py` calls the
**unseeded global** NumPy RNG at three sites — lines **49, 84, 96** (`np.random.choice`).
`np.random.seed` is never set anywhere in the package or the notebooks, and the agent's
own seeded `self.rng` is never passed in.

Seeding *does* exist elsewhere (`beavers_visualizer_backend.py`): backend rng,
environment rng, and per-agent `default_rng(seed + i + 1)`. It simply never reaches this
function — which happens to drive the single most consequential stochastic decision
(where each beaver moves next).

### Evidence

```
# 8 calls, identical inputs, same function:
[(4,4), (3,2), (6,2), (2,4), (2,4), (5,6), (3,2), (2,5)]
distinct outcomes: 6 of 8

# two full runs, both seed=7, final environment map hash:
run1  b5fab67c31b68f1a
run2  de46c06669d6977b     DIVERGED
```

### Consequences

- The existing `output/simulations/**/montecarlo/seed_1…seed_5` outputs (2,450 `.npy`
  files) **cannot be regenerated**.
- In a sweep, every difference between two configs mixes the parameter change with
  uncontrolled noise, with no way to separate them afterwards.

### Fix (~4 lines)

Pass the agent's existing `self.rng` through the `exploration_gradient_DN` call at
`beaversim/ral/robot/robot_beavers_backend.py:724`, add an `rng` parameter to the
function, and replace the three `np.random.choice` calls with `rng.choice`.

Verify by running one config twice and diffing output hashes.

---

## 5. Blockers to running Jordan's pipeline here

1. **Five missing packages** in `beaversim_env`: `landlab`, `rasterio`, `geopandas`,
   `shapely`, `seaborn`.
   Already present: numpy 2.5.0, scipy 1.18.0, pandas 3.0.3, matplotlib 3.11.0,
   skimage 0.26.0, networkx 3.6.1, imageio 2.37.3, pyproj 3.7.2, mesa 1.2.0.
2. **One hardcoded path.** Everything hangs off
   `path = "/media/jordan/easystore/MultiAgent simulation/Datasets/Buford"` (her external
   drive). It is a single variable — repointing is a one-line change.
3. **The committed data is a different site than her results.** The notebook's saved
   outputs are all **Buford, Colorado** (EPSG:26913), which is *not* in the repo. What
   she committed is **Montana** — Hall Coulee, ~48.93°N / −113.13°W, elevation
   1263–1502 m. Her numbers cannot be reproduced from the repo; the Montana site would be
   run fresh.
4. **Latent Mesa conflict.** She uses Mesa 3.x idioms (`from mesa.agent import Agent`,
   `RandomActivation` commented out — removed in Mesa 3). BeaverSim pins `Mesa==1.2.0`
   and *uses* `RandomActivation`. Harmless today (she never instantiates Mesa), but a
   naive single-environment merge breaks one side. **Install her stack in a separate
   environment.**

---

## 6. Compute budget

Benchmarked on this machine: 40 agents, 332 × 334 Boston grid, excluding the plotting and
saving the scenario performs every `downsampling` steps.

| Quantity | Measured | Note |
|---|---|---|
| Per-step cost | 28.9 ms | 40 agents |
| Full 4-year run | ~17 min | 35,040 steps, single core |
| Machine | 24 cores / 125 GB | memory is not a constraint |
| Parallel headroom | ~22 concurrent runs | a 22-config sweep in ~one run's wall time |

Two implications:

- The simulator is **entirely sequential** (no multiprocessing anywhere). A faster
  machine buys nothing on a single run — the win is running many configs concurrently.
- The current Monte Carlo harness varies **only the seed**: it deep-copies the config and
  overwrites `config['simulation']['seed']`. A real sweep harness does not exist yet.

Parameters worth sweeping (already well factored in the config dict): `exploration_eta`,
`epsilon_greedy`, `harvest_interval`, `maximum_load`, `vegetation_removal`, `role` mix,
`grass_growth_rate`, `river_growth_velocity`, `visits_reset`, controller gains
(`Kp`/`Kd`/`Ki`, `beta_repulsive`).

---

## 7. Plan

Ordered by dependency. Each phase unblocks the next.

### W1 — Sep 3–9 · Make runs reproducible, make the environment real
Thread the seeded RNG into `exploration_gradient_DN` (§4) and verify by double-run hash
diff. In parallel, install the five missing packages into a **separate** environment from
`beaversim_env` so the Mesa 1.2 pin stays intact, and repoint Jordan's `path` variable at
the committed Montana data.

**Done when:** two runs at the same seed produce byte-identical maps, and her notebook
executes end to end on the Montana DEM.

### W2 — Sep 10–16 · Sweep harness, then run the study
Generalise the Monte Carlo loop from seed-only to an arbitrary parameter grid, snapshot
the full config as JSON beside every run's outputs, and drive it with a process pool
across the 24 cores. Then run the sweep, seeds crossed with parameters so the two effects
separate.

**Done when:** a sweep spec produces a directory tree of runs each carrying the exact
config that generated it.

### W3 — Sep 17–23 · Split the composite map into named layers
Decompose `_map` into distinct elevation / vegetation / water fields, keeping the combined
value as a derived property so agent logic is untouched. Persist real units and the
per-frame normalisation bounds currently only printed to console. Adopt Jordan's
master-CSV column names so both halves share one vocabulary.

**Done when:** a saved frame can be read back into physical elevation without needing the
run's console output.

### W4 — Sep 24–30 · Wire Landlab in as the water layer
One-way coupling first: her pipeline emits the master CSV, a loader turns those columns
into simulator layers, and `grow_rivers()` is replaced by routed drainage area. Validate
that agent behaviour on real Montana terrain stays sane before adding feedback.

**Done when:** a simulation runs on Landlab-derived water and NAIP-derived vegetation
instead of synthesised fields.

### Oct onward — Close the loop
Let dam construction modify the elevation layer, re-run flow accumulation, feed the new
drainage pattern back to the agents. The builder-role visit maps
(`_map_visits_roles_builder`) already track dam locations separately from terrain, so the
input side is ready.

**Open question:** how often to re-run routing. Every step is far too expensive at 1 m
resolution; a trigger on cumulative dam change is the obvious alternative.

---

## 8. Open questions for Jordan

- Which site is canonical going forward — Montana (committed) or Buford (her executed
  results)? The sweep target depends on it.
- Can she export the master CSV for the Montana site, or should this machine regenerate
  it? Regenerating needs only the 1.9 GB already in hand.
- A `requirements.txt` with her pinned versions (especially Landlab and Mesa) would
  settle the environment split quickly.
- Committing 1.9 GB of *source* rasters to LFS is worth discussing — the derived master
  CSV is tens of megabytes and is what the simulator actually consumes.

---

## 9. Operational notes (save future time)

**SSH.** `~/.ssh/config` pins `github.com` to `IdentityFile ~/.ssh/jerry_github` with
`IdentitiesOnly yes`, which blocks other keys. The key authorised for this repo is
`~/.ssh/beaverbot_jerry`. To use it, override the pin:

```bash
eval "$(ssh-agent -s)" && ssh-add ~/.ssh/beaverbot_jerry
GIT_SSH_COMMAND="ssh -o IdentitiesOnly=no -o IdentityFile=~/.ssh/beaverbot_jerry" \
  git fetch origin
```

**Git LFS.** `git-lfs` was missing from PATH for a while; it is installed now (3.4.1).
Important gotcha: `git lfs fetch origin <branch>` resolves to the **local** branch ref. If
the local branch is behind, it silently fetches nothing and still exits 0. Fetch by commit
SHA instead:

```bash
git lfs fetch origin <sha>
```

**Pre-existing LFS defect.** `data_acquisition/example_datasets/ACADIA_DEM/Acadia.csv` is
committed as a raw 16.6 MB blob rather than an LFS pointer, despite matching `*.csv` in
`.gitattributes` (it predates git-lfs being installed). `git lfs fsck` reports it. It is
already on `origin/main` and `origin/dev_metric`; fixing it means history rewriting, so it
has been left alone.

**Boston DEM note.** `output/RumneyMarsh_Boston/DEM/elevation.npy` is 332 × 334 and
already normalised to `[-1, 1]`. The `home_base_position` values in
`notebooks/simulations/demo_csv_boston.ipynb` (e.g. `[570, 450]`) are out of bounds for
it and raise `IndexError` in Mesa's `place_agent`.
