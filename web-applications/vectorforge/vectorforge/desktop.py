"""Desktop launcher: start the server on a free local port and open the browser.

This is the entry point of the packaged ``Vectorforge.exe``. Closing the
console window stops the app.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def _free_port(preferred: int = 8000) -> int:
    for port in [preferred, *range(8001, 8100)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(Path.home(), ".local", "share")
    d = Path(base) / "Vectorforge" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _open_when_ready(url: str):
    for _ in range(120):
        try:
            urllib.request.urlopen(url + "api/v1/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    print(f"\n  Vectorforge is running at {url}\n  Keep this window open while you use it. Close it to quit.\n")
    if os.environ.get("VF_NO_BROWSER") != "1":
        webbrowser.open(url)


def main() -> int:
    os.environ.setdefault("VF_DATA_DIR", str(_data_dir()))
    os.environ.setdefault("VF_RATE_LIMIT_PER_MIN", "0")
    port = int(os.environ.get("VF_PORT") or _free_port())
    url = f"http://127.0.0.1:{port}/"
    print("  Starting Vectorforge...")
    threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()

    import uvicorn

    from vectorforge.server.app import app  # import here so the exe bundles it

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        import multiprocessing

        multiprocessing.freeze_support()
    raise SystemExit(main())
