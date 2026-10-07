"""Headless simulation runners that write run records (see ``beaversim.records``).

    run(config, run_dir)                                   one simulation -> one run directory
    run_montecarlo(config, out_dir, seeds, conditions)     conditions x seeds, optionally in parallel

Conditions are named config overrides with dotted keys, e.g.
``{"visits": {"robot.exploration_map": ["vegetation_visits", "vegetation_visits"]}}``.
The experiment layout is ``out_dir/<condition>/seed_<n>/`` plus ``out_dir/experiment.json``.
"""
import copy
import json
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Union

from beaversim.ral.backend.base_backend import BaseBackend
from beaversim.records import Run, RunRecorder


def apply_overrides(config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of ``config`` with dotted-key overrides applied."""
    config = copy.deepcopy(config)
    for dotted, value in overrides.items():
        node = config
        *parents, leaf = dotted.split(".")
        for key in parents:
            node = node[key]
        node[leaf] = copy.deepcopy(value)
    return config


def run(config: Dict[str, Any], run_dir: Union[str, Path], condition: Optional[str] = None,
        snapshot_every_days: Optional[float] = None,
        on_update: Optional[Callable[[Run], None]] = None, update_every_days: float = 1.0) -> Path:
    """
    Run one simulation and write its record.

    Duration is ``simulation.number_of_steps`` (days); snapshots are taken every
    ``snapshot_every_days`` (default ``simulation.downsampling``), plus the initial and final state.
    ``on_update`` (e.g. a live dashboard) is called every ``update_every_days`` and at the end with the run so far.
    """
    backend = BaseBackend().initiate_backend(**config)
    backend.generate_agents(**config)
    sim = config["simulation"]
    steps_per_day = 24 / backend._timedelta
    n_steps = int(sim["number_of_steps"] * steps_per_day)
    every = max(1, int((snapshot_every_days or sim["downsampling"]) * steps_per_day))
    update = max(1, int(update_every_days * steps_per_day))

    recorder = RunRecorder(run_dir, config, backend, condition)
    recorder.snapshot(0)
    for step in range(1, n_steps + 1):
        backend.step()
        if step % every == 0 or step == n_steps:
            recorder.snapshot(step)
        if on_update is not None and (step % update == 0 or step == n_steps):
            on_update(recorder.view(current_step=step))
    return recorder.finalize()


def _run_job(job):
    config, run_dir, condition, snapshot_every_days = job
    return str(run(config, run_dir, condition, snapshot_every_days))


def run_montecarlo(config: Dict[str, Any], out_dir: Union[str, Path], seeds: Iterable[int],
                   conditions: Optional[Dict[str, Dict[str, Any]]] = None, processes: int = 1,
                   snapshot_every_days: Optional[float] = None,
                   on_done: Optional[Callable[[Path, int, int], None]] = None) -> Path:
    """
    Run every condition with every seed; returns ``out_dir``.
    ``on_done(run_dir, n_done, n_total)`` is called in this process after each run finishes (e.g. to refresh plots).
    """
    on_done = on_done or (lambda path, done, total: print(f"[{done}/{total}] done: {path}"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    conditions = conditions or {"default": {}}
    seeds = list(seeds)
    (out_dir / "experiment.json").write_text(json.dumps(
        {"conditions": list(conditions), "overrides": conditions, "seeds": seeds}, indent=1))

    jobs = []
    for name, overrides in conditions.items():
        for seed in seeds:
            cfg = apply_overrides(config, {**overrides, "simulation.seed": seed})
            jobs.append((cfg, out_dir / name / f"seed_{seed}", name, snapshot_every_days))

    if processes > 1:
        with Pool(processes) as pool:
            for done, path in enumerate(pool.imap_unordered(_run_job, jobs), 1):
                on_done(Path(path), done, len(jobs))
    else:
        for done, job in enumerate(jobs, 1):
            on_done(Path(_run_job(job)), done, len(jobs))
    return out_dir
