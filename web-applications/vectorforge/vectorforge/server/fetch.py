"""Safe image download for ``image.url`` (blocks private addresses, limits size)."""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

from ..engine import errors
from ..engine.imageio import MAX_FILE_BYTES


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _check_host(url: str) -> None:
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise errors.VectorizeError(400, 1024, "Only http(s) URLs are supported.")
    if os.environ.get("VF_ALLOW_PRIVATE_URLS") == "1":
        return
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))
    except socket.gaierror as e:
        raise errors.url_fetch_failed(f"cannot resolve host: {e}") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise errors.VectorizeError(400, 1024, "URLs pointing to private networks are not allowed.")


def fetch_image(url: str, timeout: float = 20.0) -> bytes:
    for _ in range(4):
        _check_host(url)
        req = urllib.request.Request(url, headers={"User-Agent": "Vectorforge/1.0"})
        try:
            resp = _opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urllib.parse.urljoin(url, e.headers["Location"])
                continue
            raise errors.VectorizeError(400, 1020, f"The URL returned HTTP {e.code}.") from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise errors.url_fetch_failed(str(e)) from None
        ctype = resp.headers.get("Content-Type", "")
        if ctype and not ctype.startswith(("image/", "application/octet-stream")):
            raise errors.VectorizeError(400, 1021, f"The URL did not return an image ({ctype}).")
        data = resp.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise errors.file_too_large(len(data), MAX_FILE_BYTES)
        return data
    raise errors.url_fetch_failed("too many redirects")
