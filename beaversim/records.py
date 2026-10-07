"""Run records: the on-disk format shared by the simulator (writer) and the analysis/viz code (reader).

One run is one directory:

    run.json        schema version, full config, seed, condition label, git commit,
                    grid metadata (shape, resolution_m, dt_hours, array order), agent roles
    series.npz      environment metrics, one value per simulation step (+ ``time_h``)
    agents.npz      per-agent step logs: ``position`` (A, T, 2), ``load`` (A, T),
                    ``max_load`` (A, T), ``error_norm`` (A, T), ``destination`` (A, T, 2, NaN if none)
    snapshots.npz   ``time_h`` (K,) and one (K, X, Y) float32 array per environment layer

Layers are stored in the environment's native array order ``[x, y]`` and in simulation units
(no rescaling). An experiment is any directory tree containing run directories; runs are grouped
into conditions by their ``condition`` label.
"""
import datetime
import json
import subprocess
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

SCHEMA_VERSION = 1
RUN_FILE = "run.json"


# ============================================================
# WRITER
# ============================================================

def _git_state() -> Dict[str, Any]:
    root = Path(__file__).resolve().parent.parent
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "beaversim"], cwd=root,
                                    capture_output=True, text=True, check=True).stdout.strip())
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


class RunRecorder:
    """Collects snapshots during a run and writes the run directory at the end."""

    def __init__(self, run_dir: Union[str, Path], config: Dict[str, Any], backend: Any, condition: Optional[str] = None) -> None:
        self.run_dir = Path(run_dir)
        self.config = config
        self.backend = backend
        self.condition = condition
        self._snapshot_times: List[float] = []
        self._snapshots: Dict[str, List[np.ndarray]] = {}

    def snapshot(self, step: int) -> None:
        """Store the environment layers at simulation step ``step`` (0 = initial state)."""
        self._snapshot_times.append(step * self.backend._timedelta)
        for name, layer in self.backend._environment.layers().items():
            self._snapshots.setdefault(name, []).append(np.asarray(layer, dtype=np.float32).copy())

    def finalize(self) -> Path:
        backend, env = self.backend, self.backend._environment
        agents = sorted(backend._schedule.agents, key=lambda a: a.unique_id)
        dt = float(backend._timedelta)
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # 1. Metadata
        meta = {
            "schema": SCHEMA_VERSION,
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
            "git": _git_state(),
            "condition": self.condition,
            "seed": self.config["simulation"].get("seed"),
            "config": self.config,
            "grid": {
                "shape": list(env._map.shape),
                "resolution_m": float(env._resolution_m or 1.0),
                "array_order": "xy",
                "layers": sorted(self._snapshots),
            },
            "dt_hours": dt,
            "n_steps": len(env._plotting_stats.get("water_pixel_density", [])),
            "home_bases": [list(map(int, h)) for h in agents[0]._home_base_position_store] if agents else [],
            "roles": [a._role for a in agents],
        }
        (self.run_dir / RUN_FILE).write_text(json.dumps(meta, indent=1, default=_json_default))

        # 2. Environment series (one value per step)
        series = {k: np.asarray(v, dtype=float) for k, v in env._plotting_stats.items()}
        for k, v in env._growth_stats.items():
            if k != "day":
                series[k] = np.asarray(v, dtype=float)
        n = min(len(v) for v in series.values()) if series else 0
        series = {k: v[:n] for k, v in series.items()}
        series["time_h"] = (np.arange(n) + 1) * dt
        np.savez_compressed(self.run_dir / "series.npz", **series)

        # 3. Agent step logs
        def stack(rows):
            return np.stack(rows) if rows else np.empty((0,))
        np.savez_compressed(
            self.run_dir / "agents.npz",
            position=stack([np.asarray(a._position_store, dtype=np.int32) for a in agents]),
            load=stack([np.asarray(a._load_store, dtype=float) for a in agents]),
            max_load=stack([np.asarray(a._maximum_load_store, dtype=float) for a in agents]),
            error_norm=stack([np.array([np.linalg.norm(e) for e in a._error_store]) for a in agents]),
            destination=stack([np.array([d if d is not None else (np.nan, np.nan) for d in a._destination_store], dtype=float)
                               for a in agents]),
        )

        # 4. Snapshots
        np.savez_compressed(self.run_dir / "snapshots.npz", time_h=np.asarray(self._snapshot_times),
                            **{name: np.stack(frames) for name, frames in self._snapshots.items()})
        return self.run_dir


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Not JSON serializable: {type(obj).__name__}")


# ============================================================
# READER
# ============================================================

@dataclass
class Run:
    """One recorded run. Arrays are loaded lazily on first access."""
    path: Path
    meta: Dict[str, Any]

    @property
    def seed(self) -> Any:
        return self.meta.get("seed")

    @property
    def condition(self) -> str:
        return self.meta.get("condition") or "default"

    @property
    def dt_hours(self) -> float:
        return float(self.meta["dt_hours"])

    @property
    def resolution_m(self) -> float:
        return float(self.meta["grid"]["resolution_m"])

    @property
    def roles(self) -> List[str]:
        return list(self.meta["roles"])

    @property
    def config(self) -> Dict[str, Any]:
        return self.meta["config"]

    @cached_property
    def series(self) -> Dict[str, np.ndarray]:
        with np.load(self.path / "series.npz") as f:
            return {k: f[k] for k in f.files}

    @cached_property
    def agents(self) -> Dict[str, np.ndarray]:
        with np.load(self.path / "agents.npz") as f:
            return {k: f[k] for k in f.files}

    @cached_property
    def snapshots(self) -> Dict[str, np.ndarray]:
        with np.load(self.path / "snapshots.npz") as f:
            return {k: f[k] for k in f.files}


@dataclass
class Experiment:
    """Runs grouped by condition (in ``experiment.json`` order when present)."""
    path: Path
    conditions: Dict[str, List[Run]] = field(default_factory=dict)
    overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)   # condition -> config overrides

    def __iter__(self):
        return iter(self.conditions.items())

    def runs(self) -> List[Run]:
        return [r for runs in self.conditions.values() for r in runs]


def load_run(path: Union[str, Path]) -> Run:
    path = Path(path)
    meta = json.loads((path / RUN_FILE).read_text())
    if meta.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"{path}: schema {meta.get('schema')} != supported {SCHEMA_VERSION}")
    return Run(path, meta)


def load_experiment(path: Union[str, Path], order: Optional[List[str]] = None) -> Experiment:
    """Load every run below ``path``, grouped by condition (optionally in the given order)."""
    path = Path(path)
    runs = sorted((load_run(p.parent) for p in path.rglob(RUN_FILE)), key=lambda r: (str(r.condition), str(r.seed)))
    exp = Experiment(path)
    for r in runs:
        exp.conditions.setdefault(r.condition, []).append(r)
    manifest = path / "experiment.json"
    if manifest.exists():
        info = json.loads(manifest.read_text())
        exp.overrides = info.get("overrides", {})
        order = order or info.get("conditions")
    if order:
        exp.conditions = {c: exp.conditions[c] for c in order if c in exp.conditions}
    return exp
