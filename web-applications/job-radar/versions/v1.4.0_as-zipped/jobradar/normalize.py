"""Text, date, location, salary and experience normalisation. Never guesses a date."""
import hashlib
import html
import re
from datetime import datetime, timezone

INDIA_CITIES = [
    "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "mumbai", "navi mumbai", "thane",
    "delhi", "new delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad", "ncr", "kolkata",
    "ahmedabad", "jaipur", "kochi", "cochin", "trivandrum", "thiruvananthapuram", "coimbatore",
    "indore", "chandigarh", "mohali", "bhubaneswar", "nagpur", "mysore", "mysuru", "vadodara",
    "surat", "lucknow", "visakhapatnam", "vizag", "goa", "mangalore", "mangaluru",
]
CITY_ALIASES = {"bangalore": "bengaluru", "gurgaon": "gurugram", "new delhi": "delhi", "cochin": "kochi",
                "mysore": "mysuru", "vizag": "visakhapatnam", "mangalore": "mangaluru",
                "trivandrum": "thiruvananthapuram"}
NCR = {"delhi", "gurugram", "noida", "ghaziabad", "faridabad", "ncr"}

GLOBAL_REMOTE = re.compile(r"\b(anywhere|worldwide|global(ly)?|international|any location|all countries|world)\b", re.I)
APAC_REMOTE = re.compile(r"\b(apac|asia|india|south asia|emea and apac|asia[- ]pacific)\b", re.I)
REMOTE_WORD = re.compile(r"\bremote\b|work from home|\bwfh\b|distributed|telecommut", re.I)
HYBRID_WORD = re.compile(r"\bhybrid\b", re.I)


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_date(value):
    """Parse a source timestamp. Returns aware UTC datetime or None. Never invents a date."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            v = float(value)
            if v > 1e12:  # milliseconds
                v /= 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        s = str(value).strip()
        if re.fullmatch(r"\d{10,13}", s):
            return parse_date(int(s))
        s = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr|section)[^>]*>", re.I)


def html_to_text(value, limit=None):
    if not value:
        return ""
    s = html.unescape(str(value))          # Greenhouse double-escapes HTML
    s = _BLOCK.sub("\n", s)
    s = re.sub(r"<li[^>]*>", "\n• ", s, flags=re.I)
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s).strip()
    return s[:limit] if limit else s


def norm_text(s):
    return re.sub(r"[^a-z0-9+#.]+", " ", (s or "").lower()).strip()


def norm_company(s):
    s = norm_text(s)
    s = re.sub(r"\b(inc|llc|ltd|limited|pvt|private|technologies|technology|labs|software|corp|corporation|co)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_title(s):
    s = norm_text(s)
    s = re.sub(r"\b(sr)\b", "senior", s)
    s = re.sub(r"\b(jr)\b", "junior", s)
    s = re.sub(r"\b(engg|engr)\b", "engineer", s)
    s = re.sub(r"\(.*?\)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def canonical_city(name):
    n = name.lower().strip()
    return CITY_ALIASES.get(n, n)


def india_cities_in(text):
    t = (text or "").lower()
    found = set()
    for c in INDIA_CITIES:
        if re.search(r"\b" + re.escape(c) + r"\b", t):
            found.add(canonical_city(c))
    return found


def location_facts(location, description="", remote_flag=None, workplace_type=None):
    """Return dict: in_india, cities, remote, hybrid, remote_scope ('global'|'apac'|'india'|'restricted'|'unknown')."""
    loc = location or ""
    text = f"{loc} {workplace_type or ''}"
    cities = india_cities_in(loc)
    in_india = bool(cities) or bool(re.search(r"\bindia\b", loc, re.I))
    wt = (workplace_type or "").lower()
    remote = bool(remote_flag) or "remote" in wt or bool(REMOTE_WORD.search(text))
    hybrid = "hybrid" in wt or bool(HYBRID_WORD.search(text))
    scope = "unknown"
    if remote:
        if re.search(r"\bindia\b", loc, re.I) or cities:
            scope = "india"
        elif GLOBAL_REMOTE.search(loc):
            scope = "global"
        elif APAC_REMOTE.search(loc):
            scope = "apac"
        elif re.search(r"\b(us|usa|united states|canada|uk|united kingdom|europe|eu|germany|latam|americas|"
                       r"north america|australia|brazil|mexico|france|spain|netherlands|poland|ireland|"
                       r"[A-Z]{2} only|est|pst|cet)\b", loc, re.I):
            scope = "restricted"
        else:
            # Location field silent: look for an explicit restriction in the description.
            d = (description or "")[:4000]
            if re.search(r"(must be (located|based) in|only (accept|consider)ing? candidates (from|in)|"
                         r"(us|u\.s\.|uk|eu)[- ]based (candidates|only)|authori[sz]ed to work in the (us|united states|uk))", d, re.I):
                scope = "restricted"
            elif GLOBAL_REMOTE.search(d[:1500]):
                scope = "global"
    onsite = "onsite" in wt or "on-site" in wt or bool(re.search(r"\b(on-?site|in[- ]office|work from office)\b", loc, re.I))
    arrangement = "remote" if remote and not hybrid else ("hybrid" if hybrid else ("onsite" if onsite else ""))
    return {"in_india": in_india, "cities": sorted(cities), "remote": remote, "hybrid": hybrid,
            "remote_scope": scope, "arrangement": arrangement}


_EXP = re.compile(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|—|to)\s*(\d{1,2})\s*)?\+?\s*(?:years?|yrs?)", re.I)


def experience_range(text):
    """Extract the required years of experience from a description. Returns (min, max) or (None, None)."""
    if not text:
        return None, None
    best = None
    for m in _EXP.finditer(text[:8000]):
        ctx = text[max(0, m.start() - 60): m.end() + 60].lower()
        if not re.search(r"experience|exp\b|background|working|industry|professional", ctx):
            continue
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else None
        if lo > 30 or (hi and hi > 40):
            continue
        if best is None or lo > best[0]:
            best = (lo, hi)
    return best if best else (None, None)


def parse_candidate_experience(s):
    """'3–5 years' -> (3,5); '8+ years' -> (8, 40); '4' -> (4,4)."""
    if not s:
        return None, None
    nums = [int(n) for n in re.findall(r"\d{1,2}", str(s))]
    if not nums:
        return None, None
    if "+" in str(s) and len(nums) == 1:
        return nums[0], 40
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums[:2]), max(nums[:2])


def parse_lpa(s):
    """Parse a salary floor written by a candidate: '18 LPA', '₹18 lakh', '1800000', '$60k' (-> LPA approx)."""
    if not s:
        return None
    t = str(s).lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    if not m:
        return None
    v = float(m.group(1))
    if "cr" in t:
        return v * 100
    if "lpa" in t or "lakh" in t or "lac" in t or "l " in t + " ":
        return v
    if "$" in t or "usd" in t:
        if "k" in t:
            v *= 1000
        return round(v * 83 / 100000, 1)
    if v >= 100000:
        return round(v / 100000, 1)
    return v  # assume LPA if small number


def salary_from_source(min_v, max_v, currency, period=None):
    """Normalise a source salary range to annual lakh INR (approx for USD/EUR/GBP)."""
    rates = {"INR": 1.0, "USD": 83.0, "EUR": 90.0, "GBP": 105.0, "CAD": 61.0, "AUD": 55.0, "SGD": 62.0}
    cur = (currency or "").upper()
    if cur not in rates or (min_v is None and max_v is None):
        return None, None
    mult = {"hour": 2080, "hourly": 2080, "month": 12, "monthly": 12}.get((period or "").lower(), 1)
    conv = lambda v: round(float(v) * mult * rates[cur] / 100000, 1) if v not in (None, "") else None
    return conv(min_v), conv(max_v)


def stable_hash(*parts):
    h = hashlib.sha1()
    for p in parts:
        h.update((p or "").encode("utf-8", "ignore"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]


def content_hash(job):
    return stable_hash(norm_title(job.get("title")), norm_text(job.get("location")),
                       norm_text((job.get("description") or "")[:3000]), str(job.get("salary_text") or ""))
