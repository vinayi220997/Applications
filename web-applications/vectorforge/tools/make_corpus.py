"""Generate the test corpus (tests/corpus/*.png|jpg).

Mix of synthetic images with known geometry and the public-domain sample
images bundled with scikit-image (astronaut, chelsea, coffee, logo, horse).
Usage: python tools/make_corpus.py [out_dir]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage import data

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/corpus")
OUT.mkdir(parents=True, exist_ok=True)
AA = cv2.LINE_AA


def bgr(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def save(name, img, quality=None):
    p = OUT / name
    if quality:
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    else:
        cv2.imwrite(str(p), img)
    print("wrote", p, img.shape)


def star_pts(cx, cy, R, r, n, rot=-math.pi / 2):
    return np.array([[cx + (R if i % 2 == 0 else r) * math.cos(rot + i * math.pi / n),
                      cy + (R if i % 2 == 0 else r) * math.sin(rot + i * math.pi / n)]
                     for i in range(2 * n)], np.float64)


def fill(img, pts, col):
    cv2.fillPoly(img, [np.rint(pts * 16).astype(np.int32)], col, AA, shift=4)


# 1. flat logo (same as the probe sent to vectorizer.ai)
img = np.full((300, 400, 3), 255, np.uint8)
cv2.circle(img, (120, 150), 80, bgr("#e63946"), -1, AA)
cv2.rectangle(img, (220, 70), (360, 210), bgr("#1d3557"), -1)
fill(img, np.array([[290, 90], [350, 200], [230, 200]], float), bgr("#f1c40f"))
save("logo_flat.png", img)

# 2. badge logo with text, ring, star, rounded rect
img = np.full((480, 640, 3), bgr("#fdf6e3"), np.uint8)
cv2.circle(img, (320, 240), 200, bgr("#264653"), -1, AA)
cv2.circle(img, (320, 240), 170, bgr("#fdf6e3"), -1, AA)
cv2.circle(img, (320, 240), 150, bgr("#2a9d8f"), -1, AA)
fill(img, star_pts(320, 225, 95, 40, 5), bgr("#e9c46a"))
cv2.rectangle(img, (190, 330), (450, 390), bgr("#e76f51"), -1, AA)
cv2.putText(img, "VECTOR", (215, 375), cv2.FONT_HERSHEY_DUPLEX, 1.6, bgr("#ffffff"), 3, AA)
save("logo_badge.png", img)

# 3. low-resolution icon (48x48) - house
img = np.full((48, 48, 3), 255, np.uint8)
fill(img, np.array([[6, 24], [24, 7], [42, 24]], float), bgr("#c0392b"))
cv2.rectangle(img, (11, 24), (37, 41), bgr("#2c3e50"), -1)
cv2.rectangle(img, (20, 30), (28, 41), bgr("#f39c12"), -1)
save("icon_lowres.png", img)

# 4. transparent icon (RGBA, anti-aliased alpha)
s = 256
rgba = np.zeros((s, s, 4), np.uint8)
cv2.circle(rgba, (128, 128), 110, (*bgr("#3a86ff"), 255), -1, AA)
cv2.circle(rgba, (128, 128), 60, (0, 0, 0, 0), -1, AA)
fill(rgba, star_pts(128, 128, 45, 20, 4, 0), (*bgr("#ffbe0b"), 255))
save("transparent_icon.png", rgba)

# 5. scikit-image logo (real RGBA logo with transparency)
lg = data.logo()  # RGBA
save("transparent_logo.png", cv2.cvtColor(lg, cv2.COLOR_RGBA2BGRA))

# 6. flat illustration: landscape with sun, hills (bezier-ish), tree, rotated ellipses
W, H = 800, 520
img = np.full((H, W, 3), bgr("#87ceeb"), np.uint8)
cv2.circle(img, (640, 110), 60, bgr("#ffd166"), -1, AA)
xs = np.linspace(0, W, 200)
for base, amp, ph, col in ((330, 40, 0.0, "#06d6a0"), (380, 30, 1.7, "#118ab2"), (430, 25, 3.1, "#073b4c")):
    ys = base + amp * np.sin(xs / 120 + ph)
    pts = np.vstack([np.stack([xs, ys], 1), [[W, H], [0, H]]])
    fill(img, pts, bgr(col))
cv2.rectangle(img, (150, 260), (170, 360), bgr("#6b4226"), -1)
cv2.circle(img, (160, 240), 45, bgr("#2d6a4f"), -1, AA)
cv2.ellipse(img, (420, 90), (70, 25), 15, 0, 360, bgr("#ffffff"), -1, AA)
cv2.ellipse(img, (480, 110), (50, 20), -10, 0, 360, bgr("#ffffff"), -1, AA)
save("illustration_flat.png", img)

# 7. complex multicolor pattern (12 colors)
pal = ["#ef476f", "#ffd166", "#06d6a0", "#118ab2", "#073b4c", "#8338ec",
       "#ff006e", "#fb5607", "#3a86ff", "#2ec4b6", "#e71d36", "#ff9f1c"]
img = np.full((600, 600, 3), 250, np.uint8)
rng = np.random.default_rng(3)
for i in range(40):
    cx, cy = rng.integers(40, 560, 2)
    col = bgr(pal[i % len(pal)])
    t = i % 4
    if t == 0:
        cv2.circle(img, (int(cx), int(cy)), int(rng.integers(15, 60)), col, -1, AA)
    elif t == 1:
        w, h = rng.integers(30, 120, 2)
        ang = float(rng.uniform(0, 90))
        box = cv2.boxPoints(((float(cx), float(cy)), (float(w), float(h)), ang))
        fill(img, box, col)
    elif t == 2:
        fill(img, star_pts(cx, cy, rng.integers(25, 55), rng.integers(10, 22), int(rng.integers(5, 7))), col)
    else:
        cv2.ellipse(img, (int(cx), int(cy)), (int(rng.integers(20, 70)), int(rng.integers(10, 35))),
                    float(rng.uniform(0, 180)), 0, 360, col, -1, AA)
save("multicolor_complex.png", img)

# 8. line drawing: pen strokes, text and a scikit-image horse silhouette
img = np.full((500, 700, 3), 255, np.uint8)
horse = (data.horse() == 0).astype(np.uint8)  # True = horse
horse = cv2.resize(horse * 255, (300, 300 * horse.shape[0] // horse.shape[1]), interpolation=cv2.INTER_AREA)
hy, hx = 150, 380
img[hy:hy + horse.shape[0], hx:hx + horse.shape[1]] = 255 - np.dstack([horse] * 3)
for i in range(6):
    pts = np.array([[40 + i * 50, 80 + 30 * math.sin(i + t / 6.0) + t * 3] for t in range(0, 100, 5)])
    pts[:, 0] += np.linspace(0, 40, len(pts))
    cv2.polylines(img, [np.rint(pts * 16).astype(np.int32)], False, (20, 20, 20), 3, AA, shift=4)
cv2.putText(img, "Line Art 42", (40, 450), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 0, 0), 4, AA)
save("line_drawing.png", img)

# 9. low-resolution JPEG of the illustration (64 px tall, quality 55)
small = cv2.resize(cv2.imread(str(OUT / "illustration_flat.png")), (160, 104), interpolation=cv2.INTER_AREA)
save("lowres_jpeg.jpg", small, quality=55)

# 10. gradient background + shapes
img = np.zeros((400, 600, 3), np.uint8)
g = np.linspace(0, 1, 600)[None, :, None]
img[:] = (np.array(bgr("#ff9a9e")) * (1 - g) + np.array(bgr("#fad0c4")) * g).astype(np.uint8)
cv2.circle(img, (200, 200), 100, bgr("#6a0572"), -1, AA)
cv2.rectangle(img, (350, 100), (520, 300), bgr("#ffffff"), -1, AA)
save("gradient.png", img)

# 11-13. photographs
save("photo_astronaut.jpg", cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR), quality=90)
save("photo_chelsea.jpg", cv2.cvtColor(data.chelsea(), cv2.COLOR_RGB2BGR), quality=90)
save("photo_coffee.jpg", cv2.cvtColor(data.coffee(), cv2.COLOR_RGB2BGR), quality=90)

# 14. large image (exercise downscaling to the pixel cap): illustration at 2400x1560
big = cv2.resize(cv2.imread(str(OUT / "illustration_flat.png")), (2400, 1560), interpolation=cv2.INTER_CUBIC)
save("large_illustration.png", big)
