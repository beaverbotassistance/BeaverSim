"""Visual theme for BeaverSim figures: palette tokens, typography and media presets.

Figures never use colour or size literals. Colours come from a ``Palette`` (which a designer
can replace by editing a JSON file, see ``Palette.from_json``) and sizes from a ``Medium``
preset (book chapter, paper, slides).
"""
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap


@dataclass(frozen=True)
class SeriesStyle:
    """Encoding of one compared series (e.g. one Monte Carlo condition)."""
    hue: str                    # line and label colour
    tint: str                   # pattern colour of the spread band
    pattern: str                # matplotlib hatch of the spread band
    linestyle: Union[str, Tuple] = "solid"


@dataclass(frozen=True)
class Palette:
    """All colours used by the figures, as named tokens."""
    # Neutrals
    ink: str = "#111111"          # titles, axes
    mid: str = "#7a7a7a"          # labels, ticks, subtitles
    faint: str = "#d9d9d9"        # context shapes (e.g. water outline under traffic)
    background: str = "#ffffff"

    # Agent roles (kept from the published figures; swap here to restyle every figure)
    explorer: str = "#1f77b4"
    builder: str = "#d62728"
    neutral: str = "#f8f9fa"      # midpoint of the role traffic and change colormaps
    home: str = "#2ca02c"         # lodge / home-base markers

    # Landscape change (final - initial)
    loss: str = "#8c510a"         # vegetation removed / terrain lowered
    gain: str = "#24733f"         # vegetation regrown / stored

    # Compared series, cycled in order
    series: Tuple[SeriesStyle, ...] = (
        SeriesStyle("#24733f", "#b3d3bb", "////////////", "solid"),          # forest green, hatch
        SeriesStyle("#c99a3c", "#e8cd94", "............", (0, (0.1, 2.2))),  # ochre, stipple
        SeriesStyle("#2f6f9f", "#c3d7e6", "\\\\\\\\\\\\\\\\\\\\\\\\", (0, (4, 2))),  # blue, back-hatch
        SeriesStyle("#555555", "#cccccc", "xxxxxx", (0, (6, 2, 1, 2))),      # grey, cross
    )

    # Landscape colormap stops over [water min, vegetation max] (fraction, colour); 0.5 = value 0
    landscape: Tuple[Tuple[float, str], ...] = (
        (0.00, "#2c7da0"), (0.10, "#468faf"), (0.20, "#61a5c2"), (0.30, "#89c2d9"),
        (0.40, "#a9d6e5"), (0.499, "#f8f9fa"), (0.501, "#f8f9fa"), (0.60, "#cfe1b9"),
        (0.70, "#b5c99a"), (0.85, "#87986a"), (0.95, "#718355"), (1.00, "#a98b5e"),
    )

    font_family: Tuple[str, ...] = ("Inter", "DejaVu Sans")
    font_weight: int = 300        # body text (Inter Light)
    title_weight: int = 500       # figure titles (Inter Medium)

    def role(self, name: str) -> str:
        """Colour of an agent role."""
        return {"explorer": self.explorer, "builder": self.builder}[name]

    def series_style(self, index: int) -> SeriesStyle:
        return self.series[index % len(self.series)]

    def landscape_cmap(self) -> LinearSegmentedColormap:
        return LinearSegmentedColormap.from_list("landscape", list(self.landscape))

    def traffic_cmap(self) -> LinearSegmentedColormap:
        """Signed role traffic: explorers (negative) -> neutral -> builders (positive)."""
        stops = [(0.0, self.explorer), (0.40, self.explorer), (0.499, self.neutral),
                 (0.501, self.neutral), (0.60, self.builder), (1.0, self.builder)]
        return LinearSegmentedColormap.from_list("traffic", stops)

    def change_cmap(self) -> LinearSegmentedColormap:
        """Signed change: loss -> neutral -> gain."""
        return LinearSegmentedColormap.from_list("change", [(0.0, self.loss), (0.5, self.neutral), (1.0, self.gain)])

    def to_json(self, path: Union[str, Path]) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "Palette":
        """Load a palette; keys missing from the file keep their default value."""
        def as_tuple(v):
            """JSON turns nested tuples (dash patterns) into lists; convert them back recursively."""
            return tuple(as_tuple(x) for x in v) if isinstance(v, list) else v

        data = json.loads(Path(path).read_text())
        if "series" in data:
            data["series"] = tuple(
                SeriesStyle(s["hue"], s["tint"], s["pattern"], as_tuple(s.get("linestyle", "solid")))
                for s in data["series"])
        if "landscape" in data:
            data["landscape"] = tuple(tuple(stop) for stop in data["landscape"])
        if "font_family" in data:
            data["font_family"] = tuple(data["font_family"])
        return cls(**data)


@dataclass(frozen=True)
class Medium:
    """Sizes for one output medium. Widths are in inches."""
    name: str
    font_size: float        # body text, direct labels
    small_size: float       # ticks, colourbar labels
    label_size: float       # axis labels
    title_size: float       # figure title
    panel_title_size: float
    line_width: float       # data lines
    axis_width: float       # spines, ticks
    widths: Dict[str, float] = field(default_factory=dict)   # "full", "half"
    panel_height: float = 3.0


MEDIA: Dict[str, Medium] = {
    "chapter": Medium("chapter", 9, 7.5, 8, 8.5, 7.5, 1.8, 0.6, {"full": 8.5, "half": 4.2}, 3.0),
    "paper":   Medium("paper",   8, 6.5, 7, 8,   6.5, 1.4, 0.5, {"full": 7.0, "half": 3.4}, 2.4),
    "slides":  Medium("slides", 16, 13, 14, 18,  13,  3.0, 1.0, {"full": 12.0, "half": 6.0}, 5.0),
}

_current = {"palette": Palette(), "medium": MEDIA["chapter"]}


def use_theme(medium: str = "chapter", palette: Optional[Union[Palette, str, Path]] = None) -> None:
    """Apply the theme globally (rcParams) for the given medium and palette (object or JSON path)."""
    if isinstance(palette, (str, Path)):
        palette = Palette.from_json(palette)
    pal = palette or _current["palette"]
    med = MEDIA[medium]
    _current.update(palette=pal, medium=med)
    # First installed family only: listing a fallback that lacks the weights makes matplotlib warn
    installed = {f.name for f in font_manager.fontManager.ttflist}
    family = next((f for f in pal.font_family if f in installed), "DejaVu Sans")
    mpl.rcParams.update({
        "font.family": [family],
        "font.weight": pal.font_weight,
        "font.size": med.font_size,
        "mathtext.fontset": "cm",
        "figure.facecolor": pal.background,
        "axes.facecolor": pal.background,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": med.axis_width,
        "axes.edgecolor": pal.ink,
        "axes.labelcolor": pal.mid,
        "axes.labelsize": med.label_size,
        "axes.grid": False,
        "xtick.color": pal.mid, "ytick.color": pal.mid,
        "xtick.labelsize": med.small_size, "ytick.labelsize": med.small_size,
        "xtick.major.width": med.axis_width, "ytick.major.width": med.axis_width,
        "xtick.major.size": 3, "ytick.major.size": 3,
        "xtick.direction": "out", "ytick.direction": "out",
        "lines.linewidth": med.line_width,
        "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
        "lines.dash_capstyle": "round", "lines.dash_joinstyle": "round",
        "hatch.linewidth": 0.3,
        "legend.frameon": False,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })


def current() -> Tuple[Palette, Medium]:
    """The active (palette, medium)."""
    return _current["palette"], _current["medium"]


@contextmanager
def theme(medium: str = "chapter", palette: Optional[Union[Palette, str, Path]] = None):
    """Temporarily apply a theme, e.g. to export the same figure for slides."""
    saved_rc, saved = mpl.rcParams.copy(), dict(_current)
    use_theme(medium, palette)
    try:
        yield current()
    finally:
        mpl.rcParams.update(saved_rc)
        _current.update(saved)
