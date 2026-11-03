"""Editions (Admin / Public) and the admin PIN.

The edition is fixed when the installer is built: jobradar/edition.json says {"edition": "admin"} or
{"edition": "public"}. A missing or unreadable file means Public, so a build can never become Admin by accident.

Public:  the features in RESTRICTED are off.
Admin:   everything is on. If an admin PIN is set, the app starts locked (it behaves like Public) until the PIN
         is entered; it locks again after IDLE_MINUTES without activity, or when Lock is pressed.

To change what the Public version can do, edit RESTRICTED below and rebuild the installers.
Scheduled scans and emails don't go through the web app, so they work the same in both editions.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets as _secrets
import threading
import time
from pathlib import Path

EDITION_FILE = Path(__file__).parent / "edition.json"
IDLE_MINUTES = 30
MAX_TRIES, LOCKOUT_SECONDS = 5, 60

# key -> (name, what the Public version can't do)
RESTRICTED = {
    "mail.reveal":     ("Show saved passwords", "See the saved Gmail app passwords."),
    "mail.accounts":   ("Several Gmail accounts", "Add a second sending account, pause accounts, change the default sender, or choose senders per card. Public users set up one account."),
    "mail.advanced":   ("Advanced mail settings", "Default recipients, default sending rule, fallback, sender name and daily limit."),
    "mail.templates":  ("Email templates", "Create, edit, duplicate, switch or delete email templates. Public uses the default template (Preview still works)."),
    "mail.history":    ("Full email history", "Open sent messages and resend failed emails. Public still sees the list and statuses."),
    "settings.ai":     ("AI & OCR settings", "Turn AI on, change the AI/OCR provider, or enter an API key."),
    "settings.sources": ("Job sources", "Adzuna keys and adding company careers pages."),
    "cards.transfer":  ("Import / export cards", "Export cards to a file or import them."),
    "schedules.shared": ("Shared schedules", "Create or change schedules that run several cards. Each card can still have its own schedule."),
}

_lock = threading.Lock()
_tokens = {}          # token -> last activity (time.time())
_fails = {"n": 0, "until": 0.0}


def edition():
    try:
        e = json.loads(EDITION_FILE.read_text(encoding="utf-8")).get("edition")
    except (OSError, ValueError, AttributeError):
        e = None
    return "admin" if e == "admin" else "public"


# ---------------------------------------------------------------- PIN (stored hashed in config/secrets.json)
def _secrets_io():
    from . import mailer
    return mailer._load_secrets, mailer._save_secrets


def _hash(pin, salt, n=200_000):
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, n)


def pin_set():
    load, _ = _secrets_io()
    return bool(load().get("admin_pin"))


def check_pin_format(pin):
    pin = (pin or "").strip()
    if not (4 <= len(pin) <= 32):
        raise ValueError("The PIN must be 4 to 32 characters.")
    return pin


def _verify(pin):
    load, _ = _secrets_io()
    rec = load().get("admin_pin") or ""
    try:
        _, n, salt, h = rec.split("$")
        return hmac.compare_digest(_hash(pin or "", base64.b64decode(salt), int(n)), base64.b64decode(h))
    except ValueError:
        return False


def set_pin(new_pin, current_pin=None, token=None):
    """Set, change or (new_pin=None) remove the admin PIN. Changing or removing needs the current PIN
    or an unlocked admin session."""
    if edition() != "admin":
        raise PermissionError("The Public version has no admin PIN.")
    load, save = _secrets_io()
    if pin_set() and not (unlocked(token) or (current_pin and _verify(current_pin))):
        raise PermissionError("Enter the current PIN first.")
    d = load()
    if new_pin is None:
        d.pop("admin_pin", None)
    else:
        pin = check_pin_format(new_pin)
        salt = os.urandom(16)
        d["admin_pin"] = f"pbkdf2$200000${base64.b64encode(salt).decode()}${base64.b64encode(_hash(pin, salt)).decode()}"
    save(d)
    with _lock:
        _tokens.clear()


def unlock(pin):
    """Return a session token, or raise PermissionError."""
    if edition() != "admin":
        raise PermissionError("This is the Public version. Admin features aren't included.")
    now = time.time()
    with _lock:
        if _fails["until"] > now:
            raise PermissionError(f"Too many wrong PINs. Try again in {int(_fails['until'] - now) + 1} seconds.")
    if not pin_set() or not _verify(pin):
        with _lock:
            _fails["n"] += 1
            if _fails["n"] >= MAX_TRIES:
                _fails["n"], _fails["until"] = 0, now + LOCKOUT_SECONDS
        raise PermissionError("That PIN isn't right.")
    tok = _secrets.token_urlsafe(24)
    with _lock:
        _fails["n"] = 0
        _tokens[tok] = now
    return tok


def lock(token):
    with _lock:
        _tokens.pop(token or "", None)


def unlocked(token):
    """True when admin features are available for this request."""
    if edition() != "admin":
        return False
    if not pin_set():
        return True
    now = time.time()
    with _lock:
        t = _tokens.get(token or "")
        if t is None or now - t > IDLE_MINUTES * 60:
            _tokens.pop(token or "", None)
            return False
        _tokens[token] = now
        return True


def allowed(feature, token):
    return feature not in RESTRICTED or unlocked(token)


def info(token):
    ok = unlocked(token)
    return {"edition": edition(), "pin_set": edition() == "admin" and pin_set(), "unlocked": ok, "idle_minutes": IDLE_MINUTES,
            "features": {k: ok for k in RESTRICTED},
            "restricted": [{"key": k, "name": n, "detail": d} for k, (n, d) in RESTRICTED.items()]}
