"""Live dashboard: watch a simulation while it runs.

    live = viz.live.LiveDashboard()
    experiments.run(config, run_dir, on_update=live, update_every_days=2)

In a notebook the dashboard is redrawn in place in the cell output; outside a notebook it is
written to ``save_to`` (PNG) if given. The panels reuse the same drawing code as the reports.
"""
import time
from pathlib import Path
from typing import Optional, Union

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

from beaversim.records import Run
from beaversim.viz import primitives as P
from beaversim.viz import single
from beaversim.viz.theme import current


def _role_lines(ax: plt.Axes, run: Run, key: str, ylabel: str, smooth_hours: float = 0) -> None:
    """One line per role for a per-role series (e.g. '{role}_spatial_footprint')."""
    pal, med = current()
    s = run.series
    unit, scale = P.time_unit(max(s["time_h"][-1], 24))
    t = s["time_h"] / scale
    window = max(1, int(round(smooth_hours / run.dt_hours)))
    for k, role in enumerate(sorted(set(run.roles))):
        y = P.smooth(s[key.format(role=role)], window)
        ax.plot(t, y, color=pal.role(role), lw=med.line_width * 0.8)
        # Role key inside the panel (end labels would collide with the next panel in this dense layout)
        ax.text(0.03, 0.97 - 0.11 * k, role, transform=ax.transAxes, va="top", fontsize=med.small_size, color=pal.role(role))
    ax.set_xlim(0, max(t[-1], 1e-9))
    ax.set_xlabel(unit)
    ax.set_ylabel(ylabel)


def dashboard(run: Run, total_days: Optional[float] = None, note: str = "") -> plt.Figure:
    """
    Six panels for a run in progress:
    landscape now | change since start | trail traffic
    spatial diffusion | canalization ratio | vegetation & water
    """
    pal, med = current()
    snaps, s = run.snapshots, run.series
    # Size rows from the map aspect so maps fill their cells: inches, then fractions
    pt = 1 / 72
    W = med.widths["full"]
    left, right, wgap = 0.07 * W, 0.10 * W, 0.08 * W
    col_w = (W - left - right - 2 * wgap) / 3
    nx, ny = run.meta["grid"]["shape"]
    map_h, line_h = col_w * ny / nx, col_w * 0.7
    title_band = 2.4 * med.panel_title_size * pt                 # panel title above each row
    xlab_band = (6 + 2.2 * med.small_size + 1.8 * med.label_size) * pt
    H = P.header_height() + 2 * title_band + map_h + line_h + 2 * xlab_band
    fig = plt.figure(figsize=(W, H))
    gs = fig.add_gridspec(2, 3, height_ratios=(map_h, line_h), wspace=wgap / col_w,
                          hspace=(title_band + xlab_band) / ((map_h + line_h) / 2),
                          top=1 - (P.header_height() + title_band) / H, bottom=xlab_band / H,
                          left=left / W, right=1 - right / W)
    maps = [fig.add_subplot(gs[0, i]) for i in range(3)]
    lines = [fig.add_subplot(gs[1, i]) for i in range(3)]

    # Maps
    single.draw_landscape(maps[0], run)
    P.panel_title(maps[0], "landscape now")
    delta = snaps["landscape"][-1] - snaps["landscape"][0]
    lim = max(float(np.abs(delta).max()), 1e-6)
    P.map_panel(maps[1], delta, run.resolution_m, pal.change_cmap(), TwoSlopeNorm(0.0, -lim, lim))
    P.home_markers(maps[1], run.meta["home_bases"], run.resolution_m)
    P.panel_title(maps[1], "change since start")
    single.draw_traffic(maps[2], run)
    P.panel_title(maps[2], "trail traffic")
    for ax in maps[1:]:
        ax.set_ylabel("")

    # Time series
    if len(s["time_h"]):
        _role_lines(lines[0], run, "{role}_spatial_footprint", "cells visited")
        P.panel_title(lines[0], "spatial diffusion")
        _role_lines(lines[1], run, "{role}_canalization_ratio", "top 5% traffic share", smooth_hours=24)
        P.panel_title(lines[1], "canalization")
        unit, scale = P.time_unit(max(s["time_h"][-1], 24))
        t = s["time_h"] / scale
        veg, water = pal.series_style(0), pal.series_style(2)
        lines[2].plot(t, s["veg_mean"], color=veg.hue, lw=med.line_width * 0.8)
        lines[2].set_ylabel("mean vegetation")
        twin = lines[2].twinx()
        twin.plot(t, 100 * s["water_pixel_density"], color=water.hue, lw=med.line_width * 0.8, ls=water.linestyle)
        twin.spines["right"].set_visible(True)
        twin.spines["top"].set_visible(False)
        twin.set_ylabel("% water", color=water.hue)
        twin.tick_params(axis="y", colors=water.hue)
        lines[2].set_xlim(0, max(t[-1], 1e-9))
        lines[2].set_xlabel(unit)
        P.panel_title(lines[2], "vegetation · water")

    day = s["time_h"][-1] / 24 if len(s["time_h"]) else 0.0
    progress = f"day {day:.0f}" + (f" of {total_days:g}" if total_days else "")
    P.figure_header(fig, "simulation", f"{progress} · {len(run.roles)} agents · seed {run.seed}{note}")
    return fig


class _Display:
    """Redraw a figure in place in a notebook cell; optionally also save it to a PNG."""

    def __init__(self, save_to: Optional[Union[str, Path]] = None) -> None:
        self.save_to = Path(save_to) if save_to else None
        self._handle = None

    def show(self, fig: plt.Figure) -> None:
        if self.save_to:
            self.save_to.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(self.save_to)
        try:
            from IPython import get_ipython
            from IPython.display import display
        except ImportError:
            return
        if get_ipython() is None:
            return
        if self._handle is None:
            self._handle = display(fig, display_id=True)
        else:
            self._handle.update(fig)


class MonteCarloMonitor:
    """
    Callable for ``experiments.run_montecarlo(on_done=...)``: after each finished run, redraws one
    metric for every condition from the runs completed so far.
    """

    def __init__(self, out_dir: Union[str, Path], metric: str = "diffusion", labels: Optional[dict] = None,
                 save_to: Optional[Union[str, Path]] = None) -> None:
        self.out_dir = Path(out_dir)
        self.metric = metric
        self.labels = labels or {}
        self._display = _Display(save_to)
        self._t0 = time.perf_counter()

    def __call__(self, run_dir: Path, done: int, total: int) -> None:
        from beaversim.records import load_experiment
        from beaversim.viz import montecarlo
        elapsed = time.perf_counter() - self._t0
        eta = elapsed / done * (total - done)
        exp = load_experiment(self.out_dir)
        fig = montecarlo.over_time(exp, self.metric, labels=self.labels,
                                   subtitle=f"{done} of {total} runs · ~{eta / 60:.0f} min left")
        self._display.show(fig)
        plt.close(fig)


class LiveDashboard:
    """Callable for ``experiments.run(on_update=...)`` that redraws the dashboard in place."""

    def __init__(self, total_days: Optional[float] = None, save_to: Optional[Union[str, Path]] = None) -> None:
        self.total_days = total_days
        self._display = _Display(save_to)
        self._t0 = None
        self._day0 = 0.0

    def __call__(self, run: Run) -> None:
        now = time.perf_counter()
        day = run.series["time_h"][-1] / 24 if len(run.series["time_h"]) else 0.0
        if self._t0 is None:
            self._t0, self._day0 = now, day
        total = self.total_days or run.config["simulation"]["number_of_steps"]
        rate = (now - self._t0) / max(day - self._day0, 1e-9)                # wall seconds per simulated day
        eta = rate * (total - day)
        note = f" · {rate:.1f} s/day · ~{eta / 60:.0f} min left" if day > self._day0 else ""
        fig = dashboard(run, total, note)
        self._display.show(fig)
        plt.close(fig)
