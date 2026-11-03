"""Quality / speed benchmark over the test corpus.

For each image: vectorize with default options, export SVG, render it back to
pixels with rsvg-convert, and compare against the input composited on white.

Metrics
  dE_mean   mean CIELAB dE76 between input and rendered SVG (lower is better)
  dE>10 %   share of pixels with a clearly visible color difference
  psnr      PSNR in dB on RGB
  nodes     path segments in the output; shapes = filled elements
  kb        SVG size; time_s = vectorize + export; peak_mb = peak traced memory

Usage: python tools/benchmark.py [corpus_dir] [out_dir] [--json results.json]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import tracemalloc
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vectorforge.engine.export import export  # noqa: E402
from vectorforge.engine.options import parse_options  # noqa: E402
from vectorforge.engine.pipeline import vectorize  # noqa: E402

corpus = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "tests/corpus")
outdir = Path(sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "tests/results")
outdir.mkdir(parents=True, exist_ok=True)
json_out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None


def over_white(img: np.ndarray) -> np.ndarray:
    if img.shape[2] == 4:
        a = img[..., 3:4].astype(np.float32) / 255.0
        return (img[..., :3].astype(np.float32) * a + 255.0 * (1 - a)).astype(np.uint8)
    return img


def lab(img):
    return cv2.cvtColor(img.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)


rows = []
for path in sorted(corpus.iterdir()):
    if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
        continue
    data = path.read_bytes()
    opts = parse_options({})
    t = time.perf_counter()
    res = vectorize(data, opts)
    svg, _ = export(res, opts, "svg")
    elapsed = time.perf_counter() - t
    tracemalloc.start()  # second run only for memory (tracing slows Python code down)
    vectorize(data, opts)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    svg_path = outdir / (path.stem + ".svg")
    svg_path.write_bytes(svg)
    ET.fromstring(svg)  # raises on invalid XML
    src = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if src.ndim == 2:
        src = cv2.cvtColor(src, cv2.COLOR_GRAY2BGR)
    h, w = src.shape[:2]
    png_path = outdir / (path.stem + ".render.png")
    subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), "-b", "white", "-o", str(png_path),
                    str(svg_path)], check=True)
    ren = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
    a, b = over_white(src), over_white(ren)
    dE = np.sqrt(((lab(a) - lab(b)) ** 2).sum(-1))
    mse = float(((a.astype(np.float32) - b.astype(np.float32)) ** 2).mean())
    psnr = 10 * np.log10(255 ** 2 / max(mse, 1e-9))
    st = res.stats
    row = {
        "image": path.name,
        "size": f"{w}x{h}",
        "type": st["image_type"],
        "colors": st["colors"],
        "shapes": st["shapes"],
        "nodes": st["nodes"],
        "primitives": st["primitives"],
        "dE_mean": round(float(dE.mean()), 2),
        "dE_gt10_pct": round(float((dE > 10).mean() * 100), 2),
        "psnr": round(float(psnr), 2),
        "kb": round(len(svg) / 1024, 1),
        "time_s": round(elapsed, 2),
        "peak_mb": round(peak / 1e6, 1),
    }
    rows.append(row)
    # side by side for visual review
    side = np.hstack([a, b])
    cv2.imwrite(str(outdir / (path.stem + ".compare.png")), side)
    print(f"{row['image']:24s} {row['size']:>9s} {row['type']:5s} col={row['colors']:3d} "
          f"shapes={row['shapes']:5d} nodes={row['nodes']:6d} dE={row['dE_mean']:5.2f} "
          f"bad%={row['dE_gt10_pct']:5.2f} psnr={row['psnr']:5.1f} kb={row['kb']:7.1f} "
          f"t={row['time_s']:5.2f}s mem={row['peak_mb']:6.1f}MB prim={row['primitives']}")

if json_out:
    Path(json_out).write_text(json.dumps(rows, indent=2))
