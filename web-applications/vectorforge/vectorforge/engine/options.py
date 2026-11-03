"""Option schema and parsing.

Options use flat dotted names (``processing.max_colors``, ``output.file_format``)
so that they can be sent as multipart form fields, query parameters or JSON.
Names and semantics follow the Vectorizer.AI API where an equivalent exists;
Vectorforge-only options are marked ``vf`` in their description.

``processing.*`` options change the geometry and require re-processing.
``output.*`` options only change how an existing result is exported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .errors import bad_parameter


@dataclass(frozen=True)
class Opt:
    name: str
    kind: str  # bool | int | float | enum | str | color
    default: Any
    lo: float | None = None
    hi: float | None = None
    choices: tuple[str, ...] = ()
    desc: str = ""


def _o(name, kind, default, lo=None, hi=None, choices=(), desc=""):
    return Opt(name, kind, default, lo, hi, tuple(choices), desc)


DEFAULT_MAX_PIXELS = 2_097_152
HARD_MAX_PIXELS = 3_145_728 * 2  # 6 MP: we allow more than VAI if the operator wants

SPEC: list[Opt] = [
    # ---- input ---------------------------------------------------------------------
    _o("input.max_pixels", "int", DEFAULT_MAX_PIXELS, 100, HARD_MAX_PIXELS,
       desc="Images larger than this (width x height) are downscaled before processing."),
    # ---- processing -----------------------------------------------------------------
    _o("processing.max_colors", "int", 0, 0, 256,
       desc="Maximum number of colors. 0 picks the count automatically."),
    _o("processing.palette", "str", "",
       desc="Palette control: '#RRGGBB[ -> #RRGGBB|none][ ~ tolerance];' entries. Without "
            "tolerances the palette is strict: every pixel snaps to the nearest entry. 'none' "
            "makes that color transparent."),
    _o("processing.image_type", "enum", "auto", choices=("auto", "art", "photo"),
       desc="vf: Treat input as flat artwork or as a photograph (changes smoothing and color "
            "selection)."),
    _o("processing.detail", "enum", "medium", choices=("low", "medium", "high"),
       desc="vf: Detail level: controls smoothing and the smallest region kept."),
    _o("processing.shapes.min_area_px", "float", 0.0, 0.0, 10_000.0,
       desc="Regions smaller than this many pixels are merged into a neighbor. 0 uses the "
            "detail level's default."),
    _o("processing.fit_tolerance", "float", 0.0, 0.0, 5.0,
       desc="vf: Maximum curve fitting error in pixels. 0 uses the detail level's default."),
    _o("processing.corner_threshold", "float", 50.0, 10.0, 170.0,
       desc="vf: Direction change (degrees) above which a point is treated as a sharp corner."),
    _o("processing.background.remove", "bool", False,
       desc="vf: Remove the background color(s) touching the image border."),
    _o("processing.background.tolerance", "float", 12.0, 1.0, 60.0,
       desc="vf: Color distance (CIELAB dE) for background detection."),
    _o("processing.parameterized_shapes.enabled", "bool", True,
       desc="Fit whole shapes (circles, ellipses, rectangles, triangles, quads, stars)."),
    _o("processing.parameterizedShapes.ellipse.circle.enabled", "bool", True),
    _o("processing.parameterizedShapes.ellipse.general.enabled", "bool", True),
    _o("processing.parameterizedShapes.quadrilateral.rectangle.enabled", "bool", True),
    _o("processing.parameterizedShapes.quadrilateral.general.enabled", "bool", True),
    _o("processing.parameterizedShapes.triangle.general.enabled", "bool", True),
    _o("processing.parameterizedShapes.star.enabled", "bool", True,
       desc="vf: Regular stars with 3 to 6 points (VAI exposes N3..N6 separately)."),
    # ---- output ----------------------------------------------------------------------
    _o("output.file_format", "enum", "svg", choices=("svg", "pdf", "eps", "dxf", "png")),
    _o("output.shape_stacking", "enum", "cutouts", choices=("cutouts", "stacked"),
       desc="Cutouts: shapes never overlap. Stacked: shapes are drawn on top of each other "
            "(processing-level: changes the geometry)."),
    _o("output.group_by", "enum", "none", choices=("none", "color")),
    _o("output.draw_style", "enum", "fill_shapes",
       choices=("fill_shapes", "stroke_shapes", "stroke_edges")),
    _o("output.strokes.stroke_width", "float", 1.0, 0.0, 20.0),
    _o("output.strokes.non_scaling_stroke", "bool", True),
    _o("output.strokes.use_override_color", "bool", False),
    _o("output.strokes.override_color", "color", "#000000"),
    _o("output.gap_filler.enabled", "bool", True,
       desc="Draw thin same-color strokes under the fills to hide anti-aliasing seams."),
    _o("output.gap_filler.stroke_width", "float", 1.5, 0.0, 5.0),
    _o("output.gap_filler.non_scaling_stroke", "bool", True),
    _o("output.parameterized_shapes.flatten", "bool", False,
       desc="Write circles, ellipses, rectangles and polygons as plain paths."),
    _o("output.curves.allowed.quadratic_bezier", "bool", True),
    _o("output.curves.allowed.cubic_bezier", "bool", True),
    _o("output.curves.allowed.circular_arc", "bool", True),
    _o("output.curves.line_fit_tolerance", "float", 0.1, 0.001, 2.0,
       desc="Maximum error when a disallowed curve type is approximated with lines."),
    _o("output.svg.version", "enum", "svg_1_1", choices=("svg_1_0", "svg_1_1", "svg_tiny_1_2")),
    _o("output.svg.fixed_size", "bool", False),
    _o("output.svg.adobe_compatibility_mode", "bool", False),
    _o("output.pdf.compression_mode", "enum", "Deflate", choices=("None", "Deflate")),
    _o("output.dxf.compatibility_level", "enum", "lines_and_arcs",
       choices=("lines_only", "lines_and_arcs", "lines_arcs_and_splines")),
    _o("output.bitmap.anti_aliasing_mode", "enum", "anti_aliased",
       choices=("anti_aliased", "aliased")),
    _o("output.size.scale", "float", 0.0, 0.0, 1000.0),
    _o("output.size.width", "float", 0.0, 0.0, 1e9),
    _o("output.size.height", "float", 0.0, 0.0, 1e9),
    _o("output.size.unit", "enum", "none", choices=("none", "px", "pt", "in", "cm", "mm")),
    _o("output.size.aspect_ratio", "enum", "preserve_inset",
       choices=("preserve_inset", "preserve_overflow", "stretch")),
    _o("output.size.align_x", "float", 0.5, 0.0, 1.0),
    _o("output.size.align_y", "float", 0.5, 0.0, 1.0),
    _o("output.size.input_dpi", "float", 0.0, 0.0, 1e6),
    _o("output.size.output_dpi", "float", 0.0, 0.0, 1e6),
]

SPEC_BY_NAME = {o.name: o for o in SPEC}
# Options that change geometry (need re-processing) even though named output.*
GEOMETRY_OUTPUT_OPTIONS = {"output.shape_stacking"}


def _parse_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off", ""):
        return False
    raise ValueError("expected true or false")


def _parse_color(v: Any) -> str:
    s = str(v).strip()
    if len(s) in (4, 7) and s.startswith("#"):
        int(s[1:], 16)
        if len(s) == 4:
            s = "#" + "".join(c * 2 for c in s[1:])
        return s.lower()
    raise ValueError("expected #RRGGBB")


_PARSERS: dict[str, Callable[[Any], Any]] = {
    "bool": _parse_bool,
    "int": lambda v: int(float(v)),
    "float": float,
    "str": str,
    "color": _parse_color,
}


def parse_options(raw: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    """Validate ``raw`` (strings or native values) against SPEC and fill defaults.

    Unknown keys raise a parameter error when ``strict`` (keys outside the
    ``input.``/``processing.``/``output.`` namespaces are ignored).
    """
    out = {o.name: o.default for o in SPEC}
    for key, val in raw.items():
        if not key.startswith(("input.", "processing.", "output.")):
            continue
        opt = SPEC_BY_NAME.get(key)
        if opt is None:
            if strict:
                raise bad_parameter(key, "unknown option")
            continue
        try:
            if opt.kind == "enum":
                v = str(val).strip()
                if v not in opt.choices:
                    raise ValueError("expected one of " + ", ".join(opt.choices))
            else:
                v = _PARSERS[opt.kind](val)
        except (TypeError, ValueError) as exc:
            raise bad_parameter(key, str(exc)) from None
        if opt.lo is not None and isinstance(v, (int, float)) and not isinstance(v, bool):
            if v < opt.lo or v > opt.hi:
                raise bad_parameter(key, f"must be between {opt.lo:g} and {opt.hi:g}")
        out[key] = v
    return out


def processing_key(opts: dict[str, Any]) -> tuple:
    """A hashable key of every option that affects geometry."""
    keys = sorted(
        k for k in opts
        if k.startswith(("input.", "processing.")) or k in GEOMETRY_OUTPUT_OPTIONS
    )
    return tuple((k, opts[k]) for k in keys)


def spec_as_json() -> list[dict]:
    return [
        {
            "name": o.name,
            "type": o.kind,
            "default": o.default,
            **({"min": o.lo, "max": o.hi} if o.lo is not None else {}),
            **({"choices": list(o.choices)} if o.choices else {}),
            **({"description": o.desc} if o.desc else {}),
        }
        for o in SPEC
    ]
