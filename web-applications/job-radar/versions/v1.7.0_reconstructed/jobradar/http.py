"""Small stdlib HTTP client with timeouts, retries and per-host politeness."""
import gzip
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import USER_AGENT

_host_lock = threading.Lock()
_host_last = {}
MIN_HOST_GAP = 0.35  # seconds between requests to the same host


class FetchError(Exception):
    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status


def _wait_host(url):
    host = urllib.parse.urlparse(url).netloc
    with _host_lock:
        last = _host_last.get(host, 0)
        gap = MIN_HOST_GAP - (time.time() - last)
        _host_last[host] = time.time() + max(0, gap)
    if gap > 0:
        time.sleep(gap)


def fetch(url, timeout=20, retries=2, headers=None, method="GET"):
    """Return (status, final_url, body_text). Raises FetchError on network failure or 4xx/5xx after retries."""
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.5",
            "Accept-Encoding": "gzip"}
    hdrs.update(headers or {})
    last_err = None
    for attempt in range(retries + 1):
        _wait_host(url)
        req = urllib.request.Request(url, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                charset = r.headers.get_content_charset() or "utf-8"
                return r.status, r.geturl(), raw.decode(charset, "replace")
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location") if e.headers else None
            if e.code in (301, 302, 303, 307, 308) and loc and attempt < retries:
                url = urllib.parse.urljoin(url, loc.strip().replace(" ", "%20"))
                continue
            if e.code in (404, 410, 401, 403):
                raise FetchError(f"HTTP {e.code}", e.code)
            last_err = FetchError(f"HTTP {e.code}", e.code)
            if e.code == 429:
                time.sleep(min(30, 5 * (attempt + 1)))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = FetchError(f"network error: {getattr(e, 'reason', e)}")
        time.sleep(1.5 * (attempt + 1))
    raise last_err


def get_json(url, timeout=20, retries=2, headers=None):
    status, final, body = fetch(url, timeout=timeout, retries=retries, headers=headers)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise FetchError("response was not JSON", status)
