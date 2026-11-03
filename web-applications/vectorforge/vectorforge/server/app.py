"""Vectorforge HTTP server: REST API, web-app job API and static frontend."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..engine import errors
from ..engine.errors import VectorizeError
from ..engine.export import MIME, export
from ..engine.imageio import load_image
from ..engine.options import parse_options, processing_key, spec_as_json
from ..engine.pipeline import vectorize
from .fetch import fetch_image
from .jobs import JobStore, store_from_env

__version__ = "1.0.0"
WEB_DIR = Path(__file__).resolve().parents[1] / "web"

app = FastAPI(title="Vectorforge", version=__version__,
              description="Self-hosted raster-to-vector conversion.")
store: JobStore = store_from_env()

API_KEYS = {k.strip() for k in os.environ.get("VF_API_KEYS", "").split(",") if k.strip()}
RATE_PER_MIN = int(os.environ.get("VF_RATE_LIMIT_PER_MIN", "120"))
_buckets: dict[str, list[float]] = {}
_bucket_lock = threading.Lock()


# ------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------

@app.exception_handler(VectorizeError)
async def _vf_error(request: Request, exc: VectorizeError):
    return JSONResponse(exc.to_dict(), status_code=exc.status)


def _check_rate(request: Request):
    if RATE_PER_MIN <= 0:
        return
    ip = request.client.host if request.client else "?"
    now = time.time()
    with _bucket_lock:
        b = [t for t in _buckets.get(ip, []) if now - t < 60]
        if len(b) >= RATE_PER_MIN:
            raise VectorizeError(429, 1015, "Rate limit exceeded; retry in a minute.")
        b.append(now)
        _buckets[ip] = b


def _check_auth(request: Request):
    """Optional API-key auth for /api/v1: HTTP Basic (key as user or password) or X-API-Key."""
    if not API_KEYS:
        return
    key = request.headers.get("x-api-key")
    auth = request.headers.get("authorization", "")
    if not key and auth.lower().startswith("basic "):
        try:
            user, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
            key = pw if pw in API_KEYS else user
        except (binascii.Error, UnicodeDecodeError):
            key = None
    if not key or not any(secrets.compare_digest(key, k) for k in API_KEYS):
        raise VectorizeError(401, 1004, "Missing or invalid API key.")


async def _form_fields(request: Request) -> tuple[dict[str, Any], bytes | None, str]:
    """Collect fields from multipart/urlencoded form, JSON body and query string."""
    fields: dict[str, Any] = dict(request.query_params)
    data: bytes | None = None
    filename = "image"
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/json"):
        try:
            body = await request.json()
        except ValueError:
            raise errors.bad_parameter("body", "invalid JSON") from None
        if isinstance(body, dict):
            fields.update(body)
    elif ctype.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
        form = await request.form(max_part_size=32 * 1024 * 1024)
        for k, v in form.multi_items():
            if hasattr(v, "read"):
                if k == "image":
                    data = await v.read()
                    filename = v.filename or filename
            else:
                if k == "image":
                    raise VectorizeError(400, 1016, "Image file parameter is missing (got a string; "
                                                    "send the file contents, not its name).")
                fields[k] = v
    return fields, data, filename


def _resolve_image(fields: dict[str, Any], data: bytes | None, filename: str):
    if data is not None:
        return data, filename
    if fields.get("image.base64"):
        s = str(fields["image.base64"])
        if "," in s and s.startswith("data:"):
            s = s.split(",", 1)[1]
        try:
            return base64.b64decode(s, validate=False), "image"
        except (binascii.Error, ValueError):
            raise errors.unreadable_image("invalid base64") from None
    if fields.get("image.url"):
        url = str(fields["image.url"])
        name = url.rstrip("/").split("/")[-1].split("?")[0] or "image"
        return fetch_image(url), name
    raise errors.missing_image()


def _out_name(filename: str, fmt: str) -> str:
    stem = Path(filename).stem or "vectorized"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem)[:80]
    return f"{safe}.{fmt}"


def _file_response(body: bytes, mime: str, name: str, extra: dict | None = None, inline=False):
    disp = "inline" if inline else "attachment"
    headers = {"Content-Disposition": f'{disp}; filename="{name}"', "Cache-Control": "no-store"}
    headers.update(extra or {})
    return Response(body, media_type=mime, headers=headers)


def _retention_seconds(fields) -> float | None:
    if "policy.retention_days" not in fields:
        return None
    try:
        days = float(fields["policy.retention_days"])
    except ValueError:
        raise errors.bad_parameter("policy.retention_days", "expected a number") from None
    if not 0 <= days <= 30:
        raise errors.bad_parameter("policy.retention_days", "must be between 0 and 30")
    return days * 86400


# ------------------------------------------------------------------------------------
# REST API (Vectorizer.AI-compatible shape)
# ------------------------------------------------------------------------------------

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": __version__, "jobs": len(store.jobs)}


@app.get("/api/v1/options")
async def options_schema():
    return {"options": spec_as_json(), "formats": list(MIME)}


@app.post("/api/v1/vectorize")
async def api_vectorize(request: Request):
    _check_auth(request)
    _check_rate(request)
    fields, data, filename = await _form_fields(request)
    opts = parse_options(fields)
    token = fields.get("image.token")
    if token:
        job = store.get(str(token))
        res = await asyncio.to_thread(store.ensure_result, job, opts)
        filename = job.filename
    else:
        img, filename = await asyncio.to_thread(_resolve_image, fields, data, filename)
        retention = _retention_seconds(fields)
        res = await asyncio.to_thread(vectorize, img, opts)
        if retention:
            job = store.create(img, filename, opts, retention)
            job.result, job.status, job.stage, job.progress = res, "done", "done", 1.0
            job.result_key = processing_key(opts)
            token = job.token
    body, mime = await asyncio.to_thread(export, res, opts)
    fmt = opts["output.file_format"]
    extra = {"X-Vectorforge-Shapes": str(res.stats["shapes"]),
             "X-Vectorforge-Colors": str(res.stats["colors"])}
    if token:
        extra["X-Image-Token"] = str(token)
    return _file_response(body, mime, _out_name(filename, fmt), extra)


@app.post("/api/v1/download")
async def api_download(request: Request):
    _check_auth(request)
    _check_rate(request)
    fields, _, _ = await _form_fields(request)
    token = fields.get("image.token")
    if not token:
        raise errors.bad_parameter("image.token", "required")
    job = store.get(str(token))
    base = dict(job.options)
    base.update({k: v for k, v in fields.items() if k.startswith(("output.", "processing.", "input."))})
    opts = parse_options(base)
    res = await asyncio.to_thread(store.ensure_result, job, opts)
    body, mime = await asyncio.to_thread(export, res, opts)
    return _file_response(body, mime, _out_name(job.filename, opts["output.file_format"]),
                          {"X-Image-Token": job.token})


@app.post("/api/v1/delete")
async def api_delete(request: Request):
    _check_auth(request)
    fields, _, _ = await _form_fields(request)
    token = fields.get("image.token")
    if not token:
        raise errors.bad_parameter("image.token", "required")
    store.get(str(token))
    store.delete(str(token))
    return {"success": True}


# ------------------------------------------------------------------------------------
# Web-app job API: async processing with Server-Sent Events progress
# ------------------------------------------------------------------------------------

@app.post("/api/jobs", status_code=202)
async def create_job(request: Request):
    _check_rate(request)
    fields, data, filename = await _form_fields(request)
    if "options" in fields:  # JSON-encoded options from the web app
        try:
            extra = json.loads(fields.pop("options"))
        except ValueError:
            raise errors.bad_parameter("options", "invalid JSON") from None
        fields.update(extra)
    opts = parse_options(fields)
    img, filename = await asyncio.to_thread(_resolve_image, fields, data, filename)
    # validate early so the user gets an immediate error for broken files
    await asyncio.to_thread(load_image, img, opts["input.max_pixels"])
    job = store.create(img, filename, opts)
    store.submit(job)
    return job.summary()


@app.get("/api/jobs/{token}")
async def job_status(token: str):
    return store.get(token).summary()


@app.post("/api/jobs/{token}/reprocess", status_code=202)
async def reprocess(token: str, request: Request):
    _check_rate(request)
    job = store.get(token)
    fields, _, _ = await _form_fields(request)
    base = dict(job.options)
    base.update(fields)
    store.submit(job, parse_options(base))
    return job.summary()


@app.get("/api/jobs/{token}/events")
async def job_events(token: str, request: Request):
    job = store.get(token)

    async def gen():
        last = None
        deadline = time.time() + 600
        while time.time() < deadline:
            if await request.is_disconnected():
                return
            snap = (job.revision, job.status, job.stage, round(job.progress, 2))
            if snap != last:
                last = snap
                payload = job.summary()
                event = "progress"
                if job.status == "done":
                    event = "done"
                elif job.status == "error":
                    event = "error"
                yield f"event: {event}\ndata: {json.dumps(payload)}\n\n"
                if event in ("done", "error"):
                    return
            await asyncio.sleep(0.12)
        yield "event: error\ndata: {\"error\": {\"message\": \"timeout\"}}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/jobs/{token}/result")
async def job_result(token: str, request: Request):
    job = store.get(token)
    q = dict(request.query_params)
    download = q.pop("download", "0") == "1"
    base = dict(job.options)
    base.update(q)
    opts = parse_options(base)
    if job.status in ("queued", "processing"):
        raise VectorizeError(409, 2001, "The result is still being processed.")
    if job.status == "error" and job.result is None:
        raise VectorizeError(job.error.get("status", 500), job.error.get("code", 2000), job.error["message"])
    res = await asyncio.to_thread(store.ensure_result, job, opts)
    body, mime = await asyncio.to_thread(export, res, opts)
    return _file_response(body, mime, _out_name(job.filename, opts["output.file_format"]),
                          inline=not download)


@app.get("/api/jobs/{token}/source")
async def job_source(token: str):
    store.get(token)
    data = store.input_bytes(token)
    return Response(data, media_type="application/octet-stream", headers={"Cache-Control": "no-store"})


@app.delete("/api/jobs/{token}")
async def job_delete(token: str):
    store.get(token)
    store.delete(token)
    return {"success": True}


# ------------------------------------------------------------------------------------
# static frontend
# ------------------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
