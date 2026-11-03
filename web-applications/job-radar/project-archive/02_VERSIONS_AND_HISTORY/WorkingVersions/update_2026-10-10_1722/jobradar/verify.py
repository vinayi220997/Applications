"""Active-status checks for application links. HTTP 200 alone is never treated as proof.

ATS jobs are verified by their presence in the employer's live feed (done in the pipeline).
This module checks third-party listings' application pages. It never logs in, never solves
CAPTCHAs and never retries around a block: blocked pages are reported as 'unable to verify'.
"""
import re
import urllib.parse

from .http import fetch, FetchError

CLOSED_PHRASES = re.compile(
    r"(no longer (accepting|available|open)|position (has been|is) (filled|closed)|job (has )?expired|"
    r"this job (is|has been) (closed|removed)|posting (has )?(closed|expired)|vacancy (is )?closed|"
    r"applications? (are )?(now )?closed|job not found|page not found|this position is no longer)", re.I)


def check(url, title=None, timeout=15):
    """Return (status, apply_url_verified, note). status in verified_active|appears_active|closed|unable_to_verify."""
    if not url or not re.match(r"^https?://", url):
        return "unable_to_verify", False, "no application link"
    try:
        status, final, body = fetch(url, timeout=timeout, retries=0, headers={"Accept": "text/html,*/*"})
    except FetchError as e:
        if e.status in (404, 410):
            return "closed", False, f"application page returns HTTP {e.status}"
        if e.status in (401, 403):
            return "unable_to_verify", False, "site blocks automated checks"
        return "unable_to_verify", False, str(e)
    orig, fin = urllib.parse.urlparse(url), urllib.parse.urlparse(final)
    head = body[:200000]
    if CLOSED_PHRASES.search(re.sub(r"<[^>]+>", " ", head)[:60000]):
        return "closed", False, "page says the job is closed"
    path_depth = len([p for p in fin.path.split("/") if p])
    if (fin.netloc != orig.netloc or fin.path != orig.path) and path_depth <= 1:
        return "unable_to_verify", False, "link redirects to a general page, not the vacancy"
    if title:
        words = [w for w in re.findall(r"[a-z]{4,}", title.lower())][:4]
        page = head.lower()
        if words and sum(1 for w in words if w in page) == 0:
            return "unable_to_verify", False, "page doesn't mention the job title"
    return "appears_active", True, "application page loads and shows the vacancy"
