"""Monte Carlo figures: metrics over time, mean ± 1σ across seeds, one series per condition."""
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

import matplotlib.pyplot as plt
import numpy as np

from beaversim.records import Experiment
from beaversim.viz import primitives as P
from beaversim.viz.theme import current


@dataclass(frozen=True)
class Metric:
    """A recorded series and how to present it."""
    key: str                      # series name; '{role}' is filled in for per-role metrics
    title: str
    ylabel: str
    per_role: bool = False
    smooth_hours: float = 0       # centred moving average applied to mean and σ
    skip_hours: float = 0         # hide the start-up transient
    floor: Optional[float] = 0.0  # lower clip of the σ band (None = no clip)
    scale: float = 1.0            # display multiplier (e.g. 100 for percentages)


METRICS: Dict[str, Metric] = {
    "diffusion": Metric("{role}_spatial_footprint", "spatial diffusion", "cells visited", per_role=True),
    "canalization": Metric("{role}_canalization_ratio", "canalization ratio", "share of traffic on top 5% cells",
                           per_role=True, smooth_hours=168, skip_hours=24),
    "water": Metric("water_pixel_density", "open water", "% of cells", scale=100.0),
    "vegetation": Metric("veg_mean", "vegetation", "mean vegetation quality"),
}


def _stack(runs, key: str) -> np.ndarray:
    n = min(len(r.series[key]) for r in runs)
    return np.vstack([r.series[key][:n] for r in runs])


def _draw(ax: plt.Axes, exp: Experiment, metric: Metric, key: str, labels: Dict[str, str]) -> None:
    pal, _ = current()
    items, x = [], None
    for i, (cond, runs) in enumerate(exp):
        style = pal.series_style(i)
        Y = _stack(runs, key) * metric.scale
        dt = runs[0].dt_hours
        t = (np.arange(Y.shape[1]) + 1) * dt
        unit, hours = P.time_unit(t[-1])
        window = max(1, int(round(metric.smooth_hours / dt)))
        keep = t >= metric.skip_hours
        mu = P.mean_band(ax, t[keep] / hours, Y[:, keep], style, window, metric.floor)
        x = t[keep] / hours
        items.append((mu[-1], f"{labels.get(cond, cond)}  n={len(runs)}", style.hue))
    ax.set_xlim(0, x[-1])
    ax.set_xlabel(unit)
    P.end_labels(ax, items, x[-1])


def over_time(exp: Experiment, metric: Union[str, Metric], roles: Sequence[str] = ("explorer", "builder"),
              labels: Optional[Dict[str, str]] = None, title: Optional[str] = None,
              subtitle: Optional[str] = None, width: Optional[str] = None) -> plt.Figure:
    """
    One metric over time for every condition (mean line + patterned ±1σ band, direct labels).
    Per-role metrics get one panel per role.
    """
    metric = METRICS[metric] if isinstance(metric, str) else metric
    labels = labels or {}
    panels = list(roles) if metric.per_role else [None]
    fig, axes = P.figure(len(panels), width=width)
    for ax, role in zip(axes, panels):
        _draw(ax, exp, metric, metric.key.format(role=role), labels)
        if role:
            P.panel_title(ax, role)
    axes[0].set_ylabel(metric.ylabel)
    P.figure_header(fig, title or metric.title, subtitle)
    P.finish(fig)
    return fig


def summary(exp: Experiment) -> List[Dict[str, object]]:
    """One row per condition: number of seeds, duration, and the config overrides that define it."""
    rows = []
    for cond, runs in exp:
        rows.append({
            "condition": cond,
            "seeds": [r.seed for r in runs],
            "days": round(len(runs[0].series["time_h"]) * runs[0].dt_hours / 24, 1),
            "agents": len(runs[0].roles),
            "overrides": exp.overrides.get(cond, {}),
        })
    return rows
