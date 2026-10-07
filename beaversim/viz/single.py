"""Single-run report figures: what was simulated, what changed in the landscape, and how agents behaved."""
from typing import Dict, List, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize, TwoSlopeNorm

from beaversim.records import Experiment, Run
from beaversim.viz import montecarlo
from beaversim.viz import primitives as P
from beaversim.viz.theme import current


# ============================================================
# RUN CARD
# ============================================================

def run_card(run: Run) -> Dict[str, object]:
    """The essentials of a run, for a table at the top of a report."""
    cfg = run.config
    roles = run.roles
    days = len(run.series["time_h"]) * run.dt_hours / 24
    return {
        "site": cfg["environment"].get("elevation_file_path", "").split("/output/")[-1],
        "grid": f'{run.meta["grid"]["shape"][0]} x {run.meta["grid"]["shape"][1]} cells @ {run.resolution_m:g} m',
        "duration": f"{days:g} days (dt = {run.dt_hours:g} h)",
        "agents": f'{len(roles)} ({roles.count("explorer")} explorers, {roles.count("builder")} builders)',
        "seed": run.seed,
        "condition": run.condition,
        "code": f'{(run.meta["git"]["commit"] or "?")[:7]}{" (dirty)" if run.meta["git"]["dirty"] else ""}',
    }


# ============================================================
# MAPS
# ============================================================

def _snapshot_label(hours: float, span_hours: Optional[float] = None) -> str:
    """'start', 'day 3', 'month 2', ... using the unit that suits the whole run (``span_hours``)."""
    if hours <= 0:
        return "start"
    unit, scale = P.time_unit(span_hours or hours)
    return f"{unit[:-1]} {round(hours / scale, 1):g}"


def _landscape_norm(run: Run) -> Normalize:
    env = run.config["environment"]
    return TwoSlopeNorm(0.0, -float(env["flow_info"]["streams_depth"]), float(env["vegetation_quality_range"][1]))


def landscape_change(run: Run, title: str = "landscape", subtitle: Optional[str] = None) -> plt.Figure:
    """Initial state, final state and their difference."""
    pal, _ = current()
    snaps = run.snapshots
    first, last = snaps["landscape"][0], snaps["landscape"][-1]
    delta = last - first
    fig, axes, cbars = P.map_row(3, first.shape)
    norm = _landscape_norm(run)
    lim = max(float(np.abs(delta).max()), 1e-6)
    dnorm = TwoSlopeNorm(0.0, -lim, lim)

    panels = [(first, pal.landscape_cmap(), norm, "initial"),
              (last, pal.landscape_cmap(), norm, _snapshot_label(snaps["time_h"][-1])),
              (delta, pal.change_cmap(), dnorm, "change")]
    for i, (ax, (layer, cmap, n, name)) in enumerate(zip(axes, panels)):
        P.map_panel(ax, layer, run.resolution_m, cmap, n)
        P.home_markers(ax, run.meta["home_bases"], run.resolution_m)
        P.panel_title(ax, name)
        if i:
            ax.set_ylabel("")
            ax.tick_params(labelleft=False)
    P.colorbar_strip(fig, cbars[0], pal.landscape_cmap(), norm, "water depth  |  vegetation quality")
    P.colorbar_strip(fig, cbars[2], pal.change_cmap(), dnorm, "loss  |  gain")
    P.figure_header(fig, title, subtitle or f"{len(run.roles)} agents · seed {run.seed}")
    return fig


def cumulative_traffic(run: Run) -> np.ndarray:
    """
    Signed visit counts over the whole run from agent trajectories, [x, y]:
    builder visits minus explorer visits (positive = builder-dominated cell).
    """
    shape = tuple(run.meta["grid"]["shape"])
    counts = {"explorer": np.zeros(shape), "builder": np.zeros(shape)}
    for role, path in zip(run.roles, run.agents["position"]):
        np.add.at(counts[role], (path[:, 0], path[:, 1]), 1)
    return counts["builder"] - counts["explorer"]


def trail_traffic(run: Run, source: str = "trajectories", snapshot: int = -1, gamma: float = 0.35,
                  title: str = "trail traffic", subtitle: Optional[str] = None) -> plt.Figure:
    """
    Where agents travelled, by role (explorers vs builders), over a faint water outline.
    ``source='trajectories'``: cumulative visits over the whole run (default).
    ``source='ledger'``: the decaying stigmergic visit ledger at ``snapshot`` (what agents sense).
    """
    snaps = run.snapshots
    fig, axes, cbars = P.map_row(1, tuple(run.meta["grid"]["shape"]), width="half", panel_titles=False)
    draw_traffic(axes[0], run, source, snapshot, gamma)
    pal, _ = current()
    P.colorbar_strip(fig, cbars[0], pal.traffic_cmap(), Normalize(-1, 1), "visit frequency",
                     ticks=[-1, 0, 1], ticklabels=["explorers", "", "builders"])
    if subtitle is None:
        k = -1 if source == "trajectories" else snapshot
        kind = "cumulative" if source == "trajectories" else "visit ledger"
        subtitle = f"{kind} · {_snapshot_label(snaps['time_h'][k])}"
    P.figure_header(fig, title, subtitle)
    return fig


# ============================================================
# AXES-LEVEL DRAWING (shared by report figures and the live dashboard)
# ============================================================

def draw_landscape(ax: plt.Axes, run: Run, snapshot: int = -1) -> None:
    """Landscape layer at ``snapshot`` with home bases."""
    pal, _ = current()
    P.map_panel(ax, run.snapshots["landscape"][snapshot], run.resolution_m, pal.landscape_cmap(), _landscape_norm(run))
    P.home_markers(ax, run.meta["home_bases"], run.resolution_m)


def draw_traffic(ax: plt.Axes, run: Run, source: str = "trajectories", snapshot: int = -1, gamma: float = 0.35) -> None:
    """Role traffic (see ``trail_traffic``) over a faint water outline, with home bases."""
    pal, _ = current()
    snaps = run.snapshots
    land = snaps["landscape"][snapshot if source == "ledger" else -1]
    visits = cumulative_traffic(run) if source == "trajectories" else snaps["visits_roles"][snapshot]
    vmax = max(float(np.abs(visits).max()), 1e-9)
    shown = np.sign(visits) * (np.abs(visits) / vmax) ** gamma          # compress the long tail
    shown = np.where(np.abs(visits) > 1e-6, shown, np.nan)
    water = np.where(land < 0, 1.0, np.nan)
    P.map_panel(ax, water, run.resolution_m, plt.matplotlib.colors.ListedColormap([pal.faint]), Normalize(0, 1))
    P.map_panel(ax, shown, run.resolution_m, pal.traffic_cmap(), Normalize(-1, 1))
    P.home_markers(ax, run.meta["home_bases"], run.resolution_m)


def snapshot_strip(run: Run, n: int = 5, layer: str = "landscape", title: str = "landscape over time") -> plt.Figure:
    """``n`` evenly spaced snapshots of one layer, sharing a colourbar."""
    pal, _ = current()
    snaps = run.snapshots
    idx = np.unique(np.linspace(0, len(snaps["time_h"]) - 1, n).round().astype(int))
    fig, axes, cbars = P.map_row(len(idx), snaps[layer][0].shape)
    norm = _landscape_norm(run)
    for i, (ax, k) in enumerate(zip(axes, idx)):
        P.map_panel(ax, snaps[layer][k], run.resolution_m, pal.landscape_cmap(), norm)
        P.panel_title(ax, _snapshot_label(snaps["time_h"][k], snaps["time_h"][-1]))
        if i:
            ax.set_ylabel("")
            ax.tick_params(labelleft=False)
    P.colorbar_strip(fig, cbars[0], pal.landscape_cmap(), norm, "water depth  |  vegetation quality")
    P.figure_header(fig, title, f"{len(run.roles)} agents · seed {run.seed}")
    return fig


# ============================================================
# TIME SERIES
# ============================================================

def environment_over_time(run: Run, title: str = "environment") -> plt.Figure:
    """Vegetation (median, 10-90% band) and open-water share over time."""
    pal, med = current()
    s = run.series
    unit, scale = P.time_unit(s["time_h"][-1])
    t = s["time_h"] / scale
    fig, axes = P.figure(2)
    veg, water = pal.series_style(0), pal.series_style(2)

    q = s["veg_quantiles"]
    axes[0].fill_between(t, q[:, 0], q[:, 2], facecolor="none", edgecolor=veg.tint, hatch=veg.pattern, linewidth=0)
    axes[0].plot(t, q[:, 1], color=veg.hue, lw=med.line_width)
    P.end_labels(axes[0], [(q[-1, 1], "median", veg.hue), (q[-1, 2], "90%", pal.mid), (q[-1, 0], "10%", pal.mid)], t[-1])
    axes[0].set_ylabel("vegetation quality")
    P.panel_title(axes[0], "vegetation")

    axes[1].plot(t, 100 * s["water_pixel_density"], color=water.hue, lw=med.line_width)
    axes[1].set_ylabel("% of cells")
    P.panel_title(axes[1], "open water")
    for ax in axes:
        ax.set_xlim(0, t[-1])
        ax.set_xlabel(unit)
    P.figure_header(fig, title)
    P.finish(fig)
    return fig


def swarm_over_time(run: Run, metric: str = "diffusion") -> plt.Figure:
    """Per-role swarm metric for one run (same figure as the Monte Carlo version, without a band)."""
    return montecarlo.over_time(Experiment(run.path, {run.condition: [run]}), metric,
                                labels={run.condition: f"seed {run.seed}"})


def agent_diagnostics(run: Run, title: str = "agents") -> plt.Figure:
    """Carried load and controller error per agent, coloured by role."""
    pal, med = current()
    a = run.agents
    t_h = (np.arange(a["load"].shape[1]) + 1) * run.dt_hours
    unit, scale = P.time_unit(t_h[-1])
    t = t_h / scale
    fig, axes = P.figure(2)
    for i, role in enumerate(run.roles):
        c = pal.role(role)
        axes[0].plot(t, a["load"][i], color=c, lw=med.line_width * 0.4, alpha=0.7)
        axes[1].plot(t, a["error_norm"][i] * run.resolution_m, color=c, lw=med.line_width * 0.4, alpha=0.7)
    axes[0].set_ylabel("load")
    axes[1].set_ylabel("distance to waypoint  [m]")
    P.panel_title(axes[0], "carried load")
    P.panel_title(axes[1], "motion error")
    for ax in axes:
        ax.set_xlim(0, t[-1])
        ax.set_xlabel(unit)
    present = sorted(set(run.roles))
    P.end_labels(axes[0], [(axes[0].get_ylim()[1] * (0.9 - 0.12 * k), r, pal.role(r)) for k, r in enumerate(present)], t[-1])
    P.figure_header(fig, title)
    P.finish(fig)
    return fig
