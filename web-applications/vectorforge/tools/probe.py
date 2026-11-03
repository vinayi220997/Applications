"""Vectorize the same synthetic logo that was sent to vectorizer.ai during the investigation."""
import sys, time
import cv2, numpy as np
sys.path.insert(0, '.')
from vectorforge.engine.options import parse_options
from vectorforge.engine.pipeline import vectorize
from vectorforge.engine.export.svg import write_svg
img = np.full((300, 400, 3), 255, np.uint8)
cv2.circle(img, (120, 150), 80, (70, 57, 230), -1, cv2.LINE_AA)
cv2.rectangle(img, (220, 70), (360, 210), (87, 53, 29), -1)
cv2.fillPoly(img, [np.array([[290, 90], [350, 200], [230, 200]], np.int32)], (15, 196, 241), cv2.LINE_AA)
ok, buf = cv2.imencode('.png', img)
o = parse_options({})
t = time.time(); r = vectorize(buf.tobytes(), o); print('time', round(time.time() - t, 2))
print(r.stats)
print(r.palette)
svg = write_svg(r, o)
open(sys.argv[1], 'wb').write(svg)
print(svg.decode()[:3000])
