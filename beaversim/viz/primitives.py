"""Drawing primitives shared by all BeaverSim figures (headers, spread bands, direct labels, maps)."""
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Colormap, Normalize

from beaversim.viz.theme import SeriesStyle, current

HOURS = {"days": 24.0, "months": 365 * 24 / 12, "years": 365 * 24.0}


# ============================================================
# TEXT
# ============================================================

def spaced(text: str) -> str:
    """Letter-spaced capitals used for titles and captions."""
    return "  ".join(" ".join(word) for word in text.upper().split())


def header_height(subtitle: bool = True) -> float:
    """Height in inches taken by the figure header (title + optional subtitle), scaled with the medium."""
    _, med = current()
    return (1.6 * med.title_size + (1.6 * med.panel_title_size if subtitle else 0) + 4) / 72


def figure_header(fig: plt.Figure, title: str, subtitle: Optional[str] = None) -> None:
    """Spaced-caps title (ink) and optional subtitle (mid grey) in the top-left corner."""
    pal, med = current()
    fig.text(0.01, 0.99, spaced(title), fontsize=med.title_size, color=pal.ink, weight=pal.title_weight, va="top")
    if subtitle:
        line = 1.6 * med.title_size / 72 / fig.get_figheight()       # one title line, in figure fraction
        fig.text(0.01, 0.99 - line, spaced(subtitle), fontsize=med.panel_title_size, color=pal.mid, va="top")


def panel_title(ax: plt.Axes, text: str) -> None:
    pal, med = current()
    ax.set_title(spaced(text), loc="left", fontsize=med.panel_title_size, color=pal.mid, pad=10)


# ============================================================
# LAYOUT
# ============================================================

def figure(n_panels: int = 1, width: Optional[str] = None, rows: int = 1,
           height: Optional[float] = None) -> Tuple[plt.Figure, np.ndarray]:
    """Figure sized for the active medium; ``width`` is 'full' or 'half' (default by panel count)."""
    _, med = current()
    width = width or ("half" if n_panels == 1 else "full")
    cols = int(np.ceil(n_panels / rows))
    fig, axes = plt.subplots(rows, cols, figsize=(med.widths[width], height or med.panel_height * rows), squeeze=False)
    return fig, axes.ravel()


def finish(fig: plt.Figure, has_header: bool = True, right_margin: float = 0.96) -> None:
    """Tight layout leaving room for the header and for direct labels on the right."""
    top = 1 - header_height() / fig.get_figheight() if has_header else 1
    fig.tight_layout(rect=(0, 0, right_margin, top), w_pad=4)


def save(fig: plt.Figure, path: Union[str, Path], formats: Sequence[str] = ("pdf", "png")) -> List[Path]:
    """Save to every format (``path`` without extension); returns the written files."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = []
    for fmt in formats:
        out = path.with_suffix(f".{fmt}")
        fig.savefig(out)
        written.append(out)
    return written


# ============================================================
# TIME SERIES
# ============================================================

def time_unit(hours: float) -> Tuple[str, float]:
    """Readable unit for a duration: days below 2 months, months below 2 years, else years."""
    if hours < 2 * HOURS["months"]:
        return "days", HOURS["days"]
    if hours < 2 * HOURS["years"]:
        return "months", HOURS["months"]
    return "years", HOURS["years"]


def smooth(y: np.ndarray, window: int) -> np.ndarray:
    """Centred moving average over ``window`` samples (edges padded)."""
    if window <= 1:
        return y
    ypad = np.pad(y, (window // 2, window - 1 - window // 2), mode="edge")
    return np.convolve(ypad, np.ones(window) / window, mode="valid")


def mean_band(ax: plt.Axes, x: np.ndarray, Y: np.ndarray, style: SeriesStyle,
              smooth_window: int = 1, floor: Optional[float] = None) -> np.ndarray:
    """
    Mean line with a patterned ±1σ band across rows of ``Y`` (one row per seed).
    Returns the plotted mean.
    """
    _, med = current()
    mu, sd = smooth(Y.mean(axis=0), smooth_window), smooth(Y.std(axis=0), smooth_window)
    lo = mu - sd if floor is None else np.maximum(floor, mu - sd)
    if Y.shape[0] > 1:
        ax.fill_between(x, lo, mu + sd, facecolor="none", edgecolor=style.tint,
                        hatch=style.pattern, linewidth=0)
    ax.plot(x, mu, color=style.hue, lw=med.line_width, ls=style.linestyle)
    return mu


def end_labels(ax: plt.Axes, items: Iterable[Tuple[float, str, str]], x_end: float, min_gap: float = 0.07) -> None:
    """Label lines at their right end; labels closer than ``min_gap`` (axes fraction) are pushed apart."""
    _, med = current()
    lo, hi = ax.get_ylim()
    gap = min_gap * (hi - lo)
    labels = sorted([list(i) for i in items])
    for _ in range(len(labels)):
        for a, b in zip(labels, labels[1:]):
            if b[0] - a[0] < gap:
                mid = (a[0] + b[0]) / 2
                a[0], b[0] = mid - gap / 2, mid + gap / 2
    for y, text, color in labels:
        ax.annotate(text, (x_end, y), xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=med.small_size, color=color, annotation_clip=False)


# ============================================================
# MAPS
# ============================================================

def map_panel(ax: plt.Axes, layer_xy: np.ndarray, resolution_m: float, cmap: Colormap, norm: Normalize,
              alpha: float = 1.0) -> None:
    """Draw an [x, y] layer in metres, origin bottom-left, with outward spines."""
    nx, ny = layer_xy.shape
    ax.imshow(layer_xy.T, origin="lower", extent=(0, nx * resolution_m, 0, ny * resolution_m),
              cmap=cmap, norm=norm, alpha=alpha, interpolation="nearest")
    ax.set_xlabel("x  [m]")
    ax.set_ylabel("y  [m]")
    ax.spines["left"].set_position(("outward", 4))
    ax.spines["bottom"].set_position(("outward", 4))


def home_markers(ax: plt.Axes, home_bases: Sequence[Sequence[int]], resolution_m: float) -> None:
    pal, med = current()
    for hx, hy in home_bases:
        ax.plot((hx + 0.5) * resolution_m, (hy + 0.5) * resolution_m, "o", ms=med.font_size * 0.6,
                mfc=pal.home, mec=pal.background, mew=0.8, zorder=5)


def map_row(n_panels: int, shape_xy: Sequence[int], width: str = "full", header: bool = True,
            colorbar: bool = True, panel_titles: bool = True) -> Tuple[plt.Figure, List[plt.Axes], List[List[float]]]:
    """
    A row of equal-aspect map panels sized from the grid shape, so no space is wasted.
    Returns the figure, the map axes and, per panel, a colourbar rectangle (figure fractions) below it.
    """
    _, med = current()
    pt = 1 / 72                                              # one point, in inches
    W = med.widths[width]
    left = 5.5 * med.small_size * pt + 2 * med.label_size * pt   # y tick labels + y label
    right, gap = 2 * med.small_size * pt, 3 * med.small_size * pt
    head = (header_height() if header else 0) + (2.4 * med.panel_title_size if panel_titles else 6) * pt
    xlabels = 4 + 2.2 * med.small_size + 1.8 * med.label_size     # outward spine, x tick labels, x label (pt)
    strip = 0.6 * med.small_size                                   # colourbar thickness (pt)
    cbar_block = 1.8 * med.small_size + strip + 2.2 * med.small_size   # caption, strip, tick labels (pt)
    foot = (xlabels + (cbar_block if colorbar else 0) + 6) * pt
    pw = (W - left - right - gap * (n_panels - 1)) / n_panels
    ph = pw * shape_xy[1] / shape_xy[0]
    H = head + ph + foot
    fig = plt.figure(figsize=(W, H))
    axes, cbars = [], []
    strip_y = (2.2 * med.small_size + 2) * pt                     # leave room for tick labels below it
    for i in range(n_panels):
        x0 = (left + i * (pw + gap)) / W
        axes.append(fig.add_axes([x0, foot / H, pw / W, ph / H]))
        cbars.append([x0, strip_y / H, pw / W, strip * pt / H])
    return fig, axes, cbars


def colorbar_strip(fig: plt.Figure, rect: Sequence[float], cmap: Colormap, norm: Normalize, caption: str,
                   ticks: Optional[Sequence[float]] = None, ticklabels: Optional[Sequence[str]] = None) -> None:
    """Slim horizontal colourbar in ``rect`` (figure fractions) with a spaced caption and no outline."""
    pal, med = current()
    cax = fig.add_axes(rect)
    cb = fig.colorbar(ScalarMappable(norm, cmap), cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    if ticks is not None:
        cb.set_ticks(ticks)
    if ticklabels is not None:
        cb.set_ticklabels(ticklabels)
    cax.tick_params(length=2.5, width=0.5, labelsize=med.small_size, colors=pal.mid)
    cax.set_title(spaced(caption), loc="left", fontsize=med.small_size, color=pal.mid, pad=4)
