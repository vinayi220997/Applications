"""SVG writer."""

from __future__ import annotations

from typing import Any

from ..geometry import Shape, VectorResult
from .common import allowed_ops, fmt_factory, hexcolor, placement


def ring_d(ring, opts, f) -> str:
    parts = [f"M{f(ring.start[0])} {f(ring.start[1])}"]
    for s in allowed_ops(ring, opts):
        k = s[0]
        if k == "L":
            parts.append(f"L{f(s[1])} {f(s[2])}")
        elif k == "Q":
            parts.append(f"Q{f(s[1])} {f(s[2])} {f(s[3])} {f(s[4])}")
        elif k == "C":
            parts.append(f"C{f(s[1])} {f(s[2])} {f(s[3])} {f(s[4])} {f(s[5])} {f(s[6])}")
        elif k == "A":
            r = s[3]
            large = 1 if abs(s[5]) > 3.141592653589793 else 0
            sweep = 1 if s[5] > 0 else 0
            parts.append(f"A{f(r)} {f(r)} 0 {large} {sweep} {f(s[6])} {f(s[7])}")
    parts.append("Z")
    return "".join(parts)


def shape_d(shape: Shape, opts, f) -> str:
    return "".join(ring_d(r, opts, f) for r in shape.rings)


def _primitive_el(shape: Shape, f, attrs: str) -> str | None:
    p = shape.primitive
    if p is None or len(shape.rings) != 1:
        return None
    q = p.params
    if p.kind == "circle":
        return f'<circle cx="{f(q["cx"])}" cy="{f(q["cy"])}" r="{f(q["r"])}"{attrs}/>'
    if p.kind == "ellipse":
        rot = f' transform="rotate({f(q["angle"])} {f(q["cx"])} {f(q["cy"])})"' if abs(q["angle"]) > 1e-3 else ""
        return (f'<ellipse cx="{f(q["cx"])}" cy="{f(q["cy"])}" rx="{f(q["rx"])}" '
                f'ry="{f(q["ry"])}"{rot}{attrs}/>')
    if p.kind == "rect":
        x, y = q["cx"] - q["w"] / 2, q["cy"] - q["h"] / 2
        rot = f' transform="rotate({f(q["angle"])} {f(q["cx"])} {f(q["cy"])})"' if abs(q["angle"]) > 1e-3 else ""
        return (f'<rect x="{f(x)}" y="{f(y)}" width="{f(q["w"])}" height="{f(q["h"])}"'
                f'{rot}{attrs}/>')
    if p.kind == "polygon":
        pts = " ".join(f"{f(x)},{f(y)}" for x, y in q["points"])
        return f'<polygon points="{pts}"{attrs}/>'
    return None


def write_svg(res: VectorResult, opts: dict[str, Any]) -> bytes:
    pl = placement(res, opts)
    f = fmt_factory(res)
    version = opts["output.svg.version"]
    adobe = opts["output.svg.adobe_compatibility_mode"]
    style = opts["output.draw_style"]
    flatten = opts["output.parameterized_shapes.flatten"]
    group = opts["output.group_by"] == "color"
    non_scaling = opts["output.strokes.non_scaling_stroke"] and not adobe
    vattr = ' vector-effect="non-scaling-stroke"' if non_scaling else ""
    override = opts["output.strokes.override_color"] if opts["output.strokes.use_override_color"] else None
    sw = opts["output.strokes.stroke_width"]

    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    ver = {"svg_1_0": "1.0", "svg_1_1": "1.1", "svg_tiny_1_2": "1.2"}[version]
    base = 'baseProfile="tiny" ' if version == "svg_tiny_1_2" else ""
    W, H = res.width, res.height
    sized = opts["output.svg.fixed_size"] or opts["output.size.unit"] != "none" or \
        opts["output.size.scale"] or opts["output.size.width"] or opts["output.size.height"]
    size_attr = ""
    if sized:
        u = "" if pl.unit in ("none", "px") else pl.unit
        size_attr = f' width="{f(pl.page_w)}{u}" height="{f(pl.page_h)}{u}"'
    # viewBox in image pixels; when the page aspect differs, place the image like preserve_inset
    vb = f"0 0 {f(W)} {f(H)}"
    par = ""
    if sized and opts["output.size.aspect_ratio"] == "stretch":
        par = ' preserveAspectRatio="none"'
    elif sized and opts["output.size.width"] and opts["output.size.height"]:
        ax, ay = opts["output.size.align_x"], opts["output.size.align_y"]
        xa = "xMin" if ax < 0.25 else "xMax" if ax > 0.75 else "xMid"
        ya = "YMin" if ay < 0.25 else "YMax" if ay > 0.75 else "YMid"
        mode = "meet" if opts["output.size.aspect_ratio"] == "preserve_inset" else "slice"
        par = f' preserveAspectRatio="{xa}{ya} {mode}"'
    out = [head,
           f'<svg xmlns="http://www.w3.org/2000/svg" version="{ver}" {base}viewBox="{vb}"{size_attr}{par}>\n']

    shapes = sorted(res.shapes, key=lambda s: s.order) if res.stacked else list(res.shapes)

    if style == "fill_shapes":
        if opts["output.gap_filler.enabled"] and opts["output.gap_filler.stroke_width"] > 0 and not res.stacked:
            gw = opts["output.gap_filler.stroke_width"]
            gns = opts["output.gap_filler.non_scaling_stroke"] and not adobe
            gv = ' vector-effect="non-scaling-stroke"' if gns else ""
            if not gns:
                gw = gw * 0.5  # in image pixels: half a pixel each side
            out.append(f'<g id="gap-filler" fill="none" stroke-width="{f(gw)}" stroke-linejoin="round">\n')
            by_color: dict = {}
            for s in shapes:
                by_color.setdefault(s.color, []).append(s)
            for col, ss in by_color.items():
                d = "".join(shape_d(s, opts, f) for s in ss)
                out.append(f'<path stroke="{hexcolor(col)}"{gv} d="{d}"/>\n')
            out.append("</g>\n")
        _emit_shapes(out, shapes, opts, f, group, flatten,
                     lambda c: f' fill="{hexcolor(c)}"', 'fill-rule="evenodd"')
    else:
        out.append(f'<g fill="none" stroke-width="{f(sw)}" stroke-linejoin="round" stroke-linecap="round">\n')
        _emit_shapes(out, shapes, opts, f, group, flatten,
                     lambda c: f' stroke="{override or hexcolor(c)}"{vattr}', "")
        out.append("</g>\n")
    out.append("</svg>\n")
    return "".join(out).encode("utf-8")


def _emit_shapes(out, shapes, opts, f, group, flatten, paint, rule):
    rule_attr = f" {rule}" if rule else ""
    if group:
        by_color: dict = {}
        order = []
        for s in shapes:
            if s.color not in by_color:
                order.append(s.color)
            by_color.setdefault(s.color, []).append(s)
        for col in order:
            out.append(f"<g{paint(col)}{rule_attr}>\n")
            for s in by_color[col]:
                el = None if flatten else _primitive_el(s, f, "")
                out.append((el or f'<path d="{shape_d(s, opts, f)}"/>') + "\n")
            out.append("</g>\n")
        return
    for s in shapes:
        attrs = paint(s.color)
        el = None if flatten else _primitive_el(s, f, attrs)
        if el is None:
            el = f'<path{attrs}{rule_attr} d="{shape_d(s, opts, f)}"/>'
        out.append(el + "\n")
