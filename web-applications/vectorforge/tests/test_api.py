"""HTTP API tests (FastAPI TestClient)."""

from __future__ import annotations

import base64
import os
import tempfile
import time

import cv2
import numpy as np
import pytest

os.environ.setdefault("VF_DATA_DIR", tempfile.mkdtemp(prefix="vf-test-"))
os.environ.setdefault("VF_RATE_LIMIT_PER_MIN", "0")

from fastapi.testclient import TestClient  # noqa: E402

from vectorforge.server.app import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def img() -> bytes:
    a = np.full((120, 160, 3), 255, np.uint8)
    cv2.circle(a, (60, 60), 40, (0, 0, 255), -1, cv2.LINE_AA)
    cv2.rectangle(a, (110, 20), (150, 100), (255, 0, 0), -1)
    return cv2.imencode(".png", a)[1].tobytes()


def test_health_and_options():
    assert client.get("/api/v1/health").json()["status"] == "ok"
    names = {o["name"] for o in client.get("/api/v1/options").json()["options"]}
    assert "output.file_format" in names and "processing.max_colors" in names


def test_vectorize_svg(img):
    r = client.post("/api/v1/vectorize", files={"image": ("t.png", img, "image/png")})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert 'filename="t.svg"' in r.headers["content-disposition"]
    assert b"<circle" in r.content and b"<rect" in r.content


def test_vectorize_base64_and_formats(img):
    b64 = base64.b64encode(img).decode()
    for fmt, magic in (("pdf", b"%PDF"), ("eps", b"%!PS"), ("png", b"\x89PNG"), ("dxf", b"  0")):
        r = client.post("/api/v1/vectorize", data={"image.base64": b64, "output.file_format": fmt})
        assert r.status_code == 200, r.text
        assert r.content.startswith(magic), fmt


def test_retention_token_and_download(img):
    r = client.post("/api/v1/vectorize", files={"image": ("t.png", img, "image/png")},
                    data={"policy.retention_days": "1"})
    token = r.headers["x-image-token"]
    r2 = client.post("/api/v1/download", data={"image.token": token, "output.file_format": "pdf"})
    assert r2.status_code == 200 and r2.content.startswith(b"%PDF")
    r3 = client.post("/api/v1/vectorize", data={"image.token": token, "processing.max_colors": "2"})
    assert r3.status_code == 200
    assert client.post("/api/v1/delete", data={"image.token": token}).json()["success"]
    r4 = client.post("/api/v1/download", data={"image.token": token})
    assert r4.status_code == 400 and r4.json()["error"]["code"] == 1027


def test_error_envelopes(img):
    r = client.post("/api/v1/vectorize", data={})
    assert r.status_code == 400 and r.json()["error"]["code"] == 1005
    r = client.post("/api/v1/vectorize", files={"image": ("x.png", b"garbage", "image/png")})
    assert r.status_code == 400 and r.json()["error"]["code"] == 1006
    r = client.post("/api/v1/vectorize", files={"image": ("t.png", img, "image/png")},
                    data={"processing.max_colors": "-3"})
    assert r.status_code == 400 and r.json()["error"]["code"] == 1019
    r = client.post("/api/v1/vectorize", data={"image": "file.png"})
    assert r.status_code == 400 and r.json()["error"]["code"] == 1016


def test_private_url_blocked():
    r = client.post("/api/v1/vectorize", data={"image.url": "http://127.0.0.1/a.png"})
    assert r.status_code == 400 and r.json()["error"]["code"] == 1024


def _wait(token):
    for _ in range(300):
        s = client.get(f"/api/jobs/{token}").json()
        if s["status"] in ("done", "error"):
            return s
        time.sleep(0.05)
    raise AssertionError("timeout")


def test_job_flow_with_sse_and_reprocess(img):
    r = client.post("/api/jobs", files={"image": ("t.png", img, "image/png")},
                    data={"options": '{"processing.detail": "high"}'})
    assert r.status_code == 202
    token = r.json()["token"]
    with client.stream("GET", f"/api/jobs/{token}/events") as s:
        text = "".join(s.iter_text())
    assert "event: done" in text
    s = _wait(token)
    assert s["status"] == "done" and len(s["palette"]) == 3
    res = client.get(f"/api/jobs/{token}/result", params={"output.file_format": "svg"})
    assert res.status_code == 200 and res.headers["content-disposition"].startswith("inline")
    dl = client.get(f"/api/jobs/{token}/result", params={"download": "1", "output.file_format": "eps"})
    assert dl.headers["content-disposition"].startswith("attachment") and dl.content.startswith(b"%!PS")
    # recolor the red circle via a strict palette
    pal = " ".join(f'{p["source"]} -> {"#00ff00" if p["source"].startswith("#f") and p["source"] != "#ffffff" else p["color"]};'
                   for p in s["palette"])
    client.post(f"/api/jobs/{token}/reprocess", json={"processing.palette": pal})
    s2 = _wait(token)
    assert s2["revision"] == 2 and s2["status"] == "done"
    assert client.get(f"/api/jobs/{token}/source").content == img
    assert client.delete(f"/api/jobs/{token}").json()["success"]


def test_frontend_served():
    assert "Drop an image to vectorize" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
