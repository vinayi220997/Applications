"""Engine unit tests: options, palette, fitting, pipeline and every exporter."""

from __future__ import annotations

import io
import math
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import cv2
import ezdxf
import numpy as np
import pytest

from vectorforge.engine import errors
from vectorforge.engine.color import parse_palette
from vectorforge.engine.export import export
from vectorforge.engine.fit import FitSettings, fit_closed
from vectorforge.engine.geometry import flatten_ring
from vectorforge.engine.options import parse_options
from vectorforge.engine.pipeline import vectorize


def png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


@pytest.fixture(scope="module")
def logo() -> bytes:
    img = np.full((300, 400, 3), 255, np.uint8)
    cv2.circle(img, (120, 150), 80, (70, 57, 230), -1, cv2.LINE_AA)
    cv2.rectangle(img, (220, 70), (360, 210), (87, 53, 29), -1)
    pts = np.array([[290, 90], [350, 200], [230, 200]], np.int32)
    cv2.fillPoly(img, [pts], (15, 196, 241), cv2.LINE_AA)
    return png(img)


@pytest.fixture(scope="module")
def logo_result(logo):
    opts = parse_options({})
    return vectorize(logo, opts), opts


# ----------------------------------------------------------------- options
def test_defaults_and_types():
    o = parse_options({"processing.max_colors": "8", "output.gap_filler.enabled": "false"})
    assert o["processing.max_colors"] == 8
    assert o["output.gap_filler.enabled"] is False
    assert o["output.file_format"] == "svg"


@pytest.mark.parametrize("raw", [
    {"processing.max_colors": "999"},
    {"output.file_format": "gif"},
    {"processing.nope": "1"},
    {"output.strokes.override_color": "red"},
])
def test_bad_options_raise_1019(raw):
    with pytest.raises(errors.VectorizeError) as e:
        parse_options(raw)
    assert e.value.code == 1019 and e.value.status == 400


def test_palette_parsing():
    e = parse_palette("#ff0000 -> #00ff00 ~ 10; #0000ff; #fff -> none;")
    assert e[0].color == (255, 0, 0) and e[0].remap == (0, 255, 0) and e[0].tolerance == 10
    assert e[1].remap is None and e[1].tolerance is None
    assert e[2].color == (255, 255, 255) and e[2].transparent


# ----------------------------------------------------------------- input validation
def test_unreadable_image():
    with pytest.raises(errors.VectorizeError) as e:
        vectorize(b"not an image", parse_options({}))
    assert e.value.code == 1006


def test_empty_image():
    with pytest.raises(errors.VectorizeError) as e:
        vectorize(b"", parse_options({}))
    assert e.value.code == 1005


def test_large_image_is_downscaled_to_pixel_cap():
    img = np.full((1600, 2000, 3), 255, np.uint8)
    cv2.circle(img, (1000, 800), 500, (0, 0, 255), -1, cv2.LINE_AA)
    res = vectorize(png(img), parse_options({"input.max_pixels": "500000"}))
    w, h = res.stats["processing_size"]
    assert w * h <= 500_000 * 1.01
    assert (res.width, res.height) == (2000, 1600)  # output in original pixel units
    circ = [s for s in res.shapes if s.primitive and s.primitive.kind == "circle"]
    assert circ and abs(circ[0].primitive.params["r"] - 500) < 3


# ----------------------------------------------------------------- fitting
def _circle_pts(cx, cy, r, n=400):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.stack([cx + r * np.cos(t), cy + r * np.sin(t)], 1)


def test_fit_detects_circle():
    ring, prim = fit_closed(_circle_pts(50, 60, 30), FitSettings())
    assert prim is not None and prim.kind == "circle"
    assert abs(prim.params["r"] - 30) < 0.05 and abs(prim.params["cx"] - 50) < 0.05


def test_fit_detects_rotated_rectangle():
    box = cv2.boxPoints(((100.0, 80.0), (120.0, 50.0), 25.0))
    pts = np.vstack([np.linspace(box[i], box[(i + 1) % 4], 60, endpoint=False) for i in range(4)])
    ring, prim = fit_closed(pts, FitSettings())
    assert prim is not None and prim.kind == "rect"
    q = prim.params
    assert abs(max(q["w"], q["h"]) - 120) < 0.5 and abs(min(q["w"], q["h"]) - 50) < 0.5


def test_fit_smooth_blob_uses_curves_within_tolerance():
    t = np.linspace(0, 2 * math.pi, 600, endpoint=False)
    r = 60 + 12 * np.sin(3 * t) + 5 * np.cos(5 * t)
    pts = np.stack([100 + r * np.cos(t), 100 + r * np.sin(t)], 1)
    st = FitSettings(tolerance=0.5)
    ring, prim = fit_closed(pts, st)
    assert prim is None
    kinds = {s[0] for s in ring.segs}
    assert kinds & {"C", "Q", "A"}
    assert len(ring.segs) < 40  # far fewer nodes than input points
    flat = flatten_ring(ring, 0.02).astype(np.float32).reshape(-1, 1, 2)
    # every input point is close to the fitted outline (point-to-polyline distance)
    d = np.array([abs(cv2.pointPolygonTest(flat, (float(x), float(y)), True)) for x, y in pts])
    assert d.max() < 0.6


def test_fit_keeps_sharp_corners_on_lshape():
    poly = np.array([[0, 0], [80, 0], [80, 30], [30, 30], [30, 80], [0, 80]], float) + 10
    pts = np.vstack([np.linspace(poly[i], poly[(i + 1) % 6], 50, endpoint=False) for i in range(6)])
    ring, _ = fit_closed(pts, FitSettings())
    assert all(s[0] == "L" for s in ring.segs)
    assert len(ring.segs) == 6


# ----------------------------------------------------------------- pipeline
def test_logo_is_exact(logo_result):
    res, _ = logo_result
    assert res.stats["colors"] == 4
    prims = res.stats["primitives"]
    assert prims.get("circle") == 1 and prims.get("triangle") == 1
    circle = next(s for s in res.shapes if s.primitive and s.primitive.kind == "circle")
    assert abs(circle.primitive.params["cx"] - 120.5) < 0.5
    assert abs(circle.primitive.params["r"] - 80.5) < 0.6
    hexes = {p["color"] for p in res.palette}
    assert {"#ffffff", "#e63946", "#f1c40f"} <= hexes


def test_transparent_input_stays_transparent():
    rgba = np.zeros((120, 120, 4), np.uint8)
    cv2.circle(rgba, (60, 60), 40, (255, 0, 0, 255), -1, cv2.LINE_AA)
    res = vectorize(png(rgba), parse_options({}))
    assert len(res.shapes) == 1 and res.shapes[0].primitive.kind == "circle"


def test_background_removal():
    img = np.full((200, 200, 3), 255, np.uint8)
    cv2.rectangle(img, (50, 50), (150, 150), (0, 0, 0), -1)
    res = vectorize(png(img), parse_options({"processing.background.remove": "true"}))
    assert [s.color for s in res.shapes] == [(0, 0, 0)]


def test_strict_palette_and_remap(logo):
    res = vectorize(logo, parse_options({
        "processing.palette": "#ffffff; #e63946 -> #00ff00; #1d3557; #f1c40f -> none;"}))
    cols = {s.color for s in res.shapes}
    assert (0, 255, 0) in cols and (230, 57, 70) not in cols
    assert (241, 196, 15) not in cols  # made transparent


def test_max_colors(logo):
    res = vectorize(logo, parse_options({"processing.max_colors": "2"}))
    assert res.stats["colors"] <= 2


def test_stacked_mode_has_no_holes(logo):
    res = vectorize(logo, parse_options({"output.shape_stacking": "stacked"}))
    assert res.stacked
    assert all(len(s.rings) == 1 for s in res.shapes)


# ----------------------------------------------------------------- exporters
def test_svg_valid_and_uses_primitives(logo_result):
    res, opts = logo_result
    body, mime = export(res, opts, "svg")
    root = ET.fromstring(body)
    assert mime == "image/svg+xml" and root.tag.endswith("svg")
    assert root.find("{http://www.w3.org/2000/svg}circle") is not None
    assert root.find("{http://www.w3.org/2000/svg}polygon") is not None


def test_svg_flatten_and_curve_restrictions(logo_result):
    res, _ = logo_result
    o = parse_options({"output.parameterized_shapes.flatten": "true",
                       "output.curves.allowed.circular_arc": "false",
                       "output.curves.allowed.cubic_bezier": "false",
                       "output.curves.allowed.quadratic_bezier": "false",
                       "output.group_by": "color"})
    body = export(res, o, "svg")[0].decode()
    ET.fromstring(body)
    assert "<circle" not in body and "A" not in "".join(
        e.get("d", "") for e in ET.fromstring(body).iter() if e.get("d"))
    assert " C" not in body and "C" not in "".join(
        e.get("d", "") for e in ET.fromstring(body).iter() if e.get("d"))


def test_svg_physical_size(logo_result):
    res, _ = logo_result
    o = parse_options({"output.size.width": "100", "output.size.unit": "mm"})
    root = ET.fromstring(export(res, o, "svg")[0])
    assert root.get("width") == "100mm" and root.get("height") == "75mm"


def test_pdf_structure(logo_result):
    res, opts = logo_result
    body, mime = export(res, opts, "pdf")
    assert body.startswith(b"%PDF-1.4") and body.rstrip().endswith(b"%%EOF")
    assert b"/MediaBox [0 0 400 300]" in body
    if shutil.which("pdftoppm"):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "t.pdf")
            open(src, "wb").write(body)
            subprocess.run(["pdftoppm", "-r", "72", "-png", "-singlefile", src, os.path.join(d, "t")],
                           check=True, capture_output=True)
            img = cv2.imread(os.path.join(d, "t.png"))
        assert img.shape[:2] == (300, 400)
        b, g, r = img[150, 120]  # circle centre is red
        assert r > 200 and g < 90


def test_eps_structure(logo_result):
    res, opts = logo_result
    body = export(res, opts, "eps")[0].decode()
    assert body.startswith("%!PS-Adobe-3.0 EPSF-3.0")
    assert "%%BoundingBox: 0 0 400 300" in body and "eofill" in body


@pytest.mark.parametrize("level", ["lines_only", "lines_and_arcs", "lines_arcs_and_splines"])
def test_dxf_levels(logo_result, level):
    res, _ = logo_result
    o = parse_options({"output.dxf.compatibility_level": level})
    body = export(res, o, "dxf")[0]
    doc = ezdxf.read(io.StringIO(body.decode()))
    types = {e.dxftype() for e in doc.modelspace()}
    assert types
    if level == "lines_arcs_and_splines":
        assert "ARC" in types
    else:
        assert types == {"LWPOLYLINE"}


def test_png_matches_svg_render(logo_result, logo):
    res, opts = logo_result
    body = export(res, opts, "png")[0]
    img = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_UNCHANGED)
    src = cv2.imdecode(np.frombuffer(logo, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[:2] == src.shape[:2]
    diff = np.abs(img[..., :3].astype(int) - src.astype(int)).mean()
    assert diff < 3.0


def test_png_output_too_large(logo_result):
    res, _ = logo_result
    o = parse_options({"output.size.scale": "50"})
    with pytest.raises(errors.VectorizeError) as e:
        export(res, o, "png")
    assert e.value.code == 1023
