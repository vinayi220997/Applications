"""Export every corpus image in every format and option combination; validate each file."""
import io, os, subprocess, sys, tempfile, time, xml.etree.ElementTree as ET
from pathlib import Path
import cv2, ezdxf, numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vectorforge.engine.export import export
from vectorforge.engine.options import parse_options
from vectorforge.engine.pipeline import vectorize

VARIANTS = [
    {},
    {"output.shape_stacking": "stacked"},
    {"output.draw_style": "stroke_shapes", "output.group_by": "color"},
    {"output.parameterized_shapes.flatten": "true", "output.curves.allowed.circular_arc": "false"},
    {"output.size.width": "210", "output.size.height": "297", "output.size.unit": "mm"},
]

def check(fmt, body):
    if fmt == "svg":
        ET.fromstring(body)
    elif fmt == "pdf":
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.pdf"); open(p, "wb").write(body)
            subprocess.run(["pdftoppm", "-r", "10", "-png", "-singlefile", p, os.path.join(d, "a")], check=True, capture_output=True)
    elif fmt == "eps":
        assert body.startswith(b"%!PS-Adobe-3.0 EPSF-3.0") and b"%%EOF" in body
    elif fmt == "dxf":
        ezdxf.read(io.StringIO(body.decode()))
    elif fmt == "png":
        assert cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_UNCHANGED) is not None

ok = fail = 0
for path in sorted(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/corpus").iterdir()):
    data = path.read_bytes()
    cache = {}
    for v in VARIANTS:
        o = parse_options(v)
        res = vectorize(data, o, cache=cache)
        for fmt in ("svg", "pdf", "eps", "dxf", "png"):
            for lvl in (["lines_only", "lines_and_arcs", "lines_arcs_and_splines"] if fmt == "dxf" else [None]):
                oo = dict(o)
                if lvl: oo["output.dxf.compatibility_level"] = lvl
                try:
                    body, _ = export(res, oo, fmt); check(fmt, body); ok += 1
                except Exception as e:  # noqa
                    fail += 1; print("FAIL", path.name, v, fmt, lvl, repr(e)[:200])
print(f"exports validated: {ok} ok, {fail} failed")
