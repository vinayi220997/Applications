"""Job store and background processing.

A job is identified by an image token. The original upload is kept on disk
(so the token survives result eviction and server restarts within its
retention period); results are kept in memory with an LRU bound and are
recomputed on demand.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..engine.errors import VectorizeError, token_not_found
from ..engine.geometry import VectorResult
from ..engine.options import parse_options, processing_key
from ..engine.pipeline import vectorize


@dataclass
class Job:
    token: str
    created: float
    expires: float
    filename: str
    options: dict[str, Any]
    status: str = "queued"  # queued | processing | done | error
    stage: str = "queued"
    progress: float = 0.0
    error: dict | None = None
    result: VectorResult | None = None
    result_key: tuple | None = None
    revision: int = 0
    cache: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def summary(self) -> dict:
        out = {
            "token": self.token,
            "status": self.status,
            "stage": self.stage,
            "progress": round(self.progress, 3),
            "revision": self.revision,
            "filename": self.filename,
            "expires": int(self.expires),
        }
        if self.error:
            out["error"] = self.error
        if self.result is not None and self.status == "done":
            r = self.result
            out.update(width=r.width, height=r.height, palette=r.palette, stats=r.stats)
        return out


class JobStore:
    def __init__(self, data_dir: str, workers: int, max_results: int, default_retention_h: float):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vf-worker")
        self.jobs: "OrderedDict[str, Job]" = OrderedDict()
        self.max_results = max_results
        self.default_retention_s = default_retention_h * 3600
        self.lock = threading.Lock()
        self._load_existing()
        t = threading.Thread(target=self._janitor, daemon=True)
        t.start()

    # -- persistence ---------------------------------------------------------------
    def _path(self, token: str) -> Path:
        return self.dir / token

    def _load_existing(self):
        now = time.time()
        for p in self.dir.iterdir() if self.dir.exists() else []:
            meta = p / "meta.json"
            if not meta.exists():
                continue
            try:
                m = json.loads(meta.read_text())
            except (OSError, ValueError):
                continue
            if m["expires"] < now:
                shutil.rmtree(p, ignore_errors=True)
                continue
            self.jobs[m["token"]] = Job(m["token"], m["created"], m["expires"], m["filename"],
                                        parse_options(m.get("options", {}), strict=False),
                                        status="queued", stage="restored")

    def _janitor(self):
        while True:
            time.sleep(300)
            self.purge_expired()

    def purge_expired(self):
        now = time.time()
        with self.lock:
            dead = [t for t, j in self.jobs.items() if j.expires < now]
            for t in dead:
                self.jobs.pop(t, None)
        for t in dead:
            shutil.rmtree(self._path(t), ignore_errors=True)

    # -- API ------------------------------------------------------------------------
    def create(self, data: bytes, filename: str, options: dict[str, Any],
               retention_s: float | None = None) -> Job:
        token = f"{int(time.time() * 1000)}-{secrets.token_hex(12)}"
        now = time.time()
        ret = self.default_retention_s if retention_s is None else retention_s
        job = Job(token, now, now + max(ret, 600), filename, options)
        p = self._path(token)
        p.mkdir(parents=True)
        (p / "input").write_bytes(data)
        self._save_meta(job)
        with self.lock:
            self.jobs[token] = job
        return job

    def _save_meta(self, job: Job):
        raw = {k: v for k, v in job.options.items()}
        (self._path(job.token) / "meta.json").write_text(json.dumps({
            "token": job.token, "created": job.created, "expires": job.expires,
            "filename": job.filename, "options": raw,
        }))

    def get(self, token: str) -> Job:
        with self.lock:
            job = self.jobs.get(token)
            if job is None or job.expires < time.time():
                raise token_not_found()
            self.jobs.move_to_end(token)
            return job

    def input_bytes(self, token: str) -> bytes:
        p = self._path(token) / "input"
        if not p.exists():
            raise token_not_found()
        return p.read_bytes()

    def delete(self, token: str):
        with self.lock:
            self.jobs.pop(token, None)
        shutil.rmtree(self._path(token), ignore_errors=True)

    def submit(self, job: Job, options: dict[str, Any] | None = None) -> None:
        """(Re)process ``job`` in the background with ``options``."""
        with job.lock:
            if options is not None:
                job.options = options
                self._save_meta(job)
            job.revision += 1
            rev = job.revision
            job.status, job.stage, job.progress, job.error = "queued", "queued", 0.0, None
        self.pool.submit(self._run, job, rev)

    def _run(self, job: Job, rev: int):
        def progress(stage: str, frac: float):
            if job.revision == rev:
                job.stage, job.progress = stage, frac

        if job.revision != rev:
            return  # superseded before it started
        job.status = "processing"
        try:
            key = processing_key(job.options)
            res = vectorize(self.input_bytes(job.token), job.options, progress, job.cache)
            if job.revision != rev:
                return
            job.result, job.result_key = res, key
            job.status, job.stage, job.progress = "done", "done", 1.0
        except VectorizeError as e:
            if job.revision == rev:
                job.status, job.error = "error", e.to_dict()["error"]
        except Exception as e:  # noqa: BLE001 - report unexpected failures to the client
            if job.revision == rev:
                job.status, job.error = "error", {"status": 500, "code": 2000,
                                                  "message": f"Internal error: {e}"}
        self._evict()

    def _evict(self):
        with self.lock:
            with_results = [j for j in self.jobs.values() if j.result is not None]
            for j in with_results[: max(0, len(with_results) - self.max_results)]:
                j.result, j.result_key, j.cache = None, None, {}

    def ensure_result(self, job: Job, options: dict[str, Any]) -> VectorResult:
        """Synchronously return a result matching the processing part of ``options``."""
        key = processing_key(options)
        if job.result is not None and job.result_key == key:
            return job.result
        res = vectorize(self.input_bytes(job.token), options, None, job.cache)
        job.result, job.result_key = res, key
        job.status, job.stage, job.progress = "done", "done", 1.0
        return res


def store_from_env() -> JobStore:
    return JobStore(
        data_dir=os.environ.get("VF_DATA_DIR", "./data/jobs"),
        workers=int(os.environ.get("VF_WORKERS", max(1, (os.cpu_count() or 2) // 2))),
        max_results=int(os.environ.get("VF_MAX_CACHED_RESULTS", "64")),
        default_retention_h=float(os.environ.get("VF_RETENTION_HOURS", "24")),
    )
