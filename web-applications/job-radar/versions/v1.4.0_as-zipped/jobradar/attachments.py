"""Attachments for the intake chat: resumes, job posts, screenshots and voice notes.

Files are stored only on this computer (data/attachments). Text is extracted so the agent can
pick up skills, experience, titles and locations:
  * PDF   -> bundled pypdf (vendor/)
  * DOCX  -> read directly from the Word XML
  * TXT/MD/RTF -> plain text
  * Images and screenshots -> Claude vision if an Anthropic API key is set, else Tesseract OCR if
    installed (pytesseract), else stored with a note asking for the key details as text.
  * Voice notes -> the transcript made by the browser while recording (Edge/Chrome dictation).
"""
import base64
import json
import re
import sys
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from .config import DATA_DIR, ROOT
from .intake import parse_description, SKILLS, _find_terms
from .normalize import iso, now_utc

ATT_DIR = DATA_DIR / "attachments"
MAX_BYTES = 15 * 1024 * 1024
DOC_EXT = {".pdf", ".docx", ".txt", ".md", ".rtf"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
AUD_EXT = {".webm", ".ogg", ".mp3", ".wav", ".m4a"}
MIME_EXT = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
            "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/wav": ".wav",
            "text/plain": ".txt",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx"}

SCHEMA = """CREATE TABLE IF NOT EXISTS attachments (
  id TEXT PRIMARY KEY, profile_id INTEGER, filename TEXT, mime TEXT, kind TEXT, size INTEGER,
  path TEXT, text TEXT, doc_type TEXT, extracted_json TEXT, note TEXT, created_at TEXT)"""


class AttachmentError(Exception):
    pass


def _ext(filename, mime):
    ext = Path(filename or "").suffix.lower()
    if ext in DOC_EXT | IMG_EXT | AUD_EXT:
        return ext
    base = (mime or "").split(";")[0].strip().lower()
    return MIME_EXT.get(base, ext)


def kind_of(ext):
    if ext in IMG_EXT:
        return "image"
    if ext in AUD_EXT:
        return "voice"
    if ext in DOC_EXT:
        return "document"
    return None


# ------------------------------------------------------------------ text extraction
def pdf_text(raw):
    vendor = str(ROOT / "vendor")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, "PDF reader not available."
    try:
        reader = PdfReader(BytesIO(raw))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:15])
    except Exception as e:
        return None, f"Couldn't read this PDF ({e.__class__.__name__})."
    if len(text.strip()) < 30:
        return None, "This PDF looks like a scanned image, so there's no text to read. Attach it as an image or type the key details."
    return text, None


def docx_text(raw):
    try:
        with zipfile.ZipFile(BytesIO(raw)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        return None, "Couldn't open this Word file. Save it as .docx or PDF and try again."
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ET.fromstring(xml)
    paras = []
    for p in root.iter(ns + "p"):
        paras.append("".join(t.text or "" for t in p.iter(ns + "t")))
    return "\n".join(paras), None


def rtf_text(raw):
    s = raw.decode("latin-1", "ignore")
    s = re.sub(r"\\par[d]?", "\n", s)
    s = re.sub(r"\\'[0-9a-f]{2}|\\[a-z]+-?\d* ?|[{}]", "", s)
    return s, None


def image_text(raw, mime, settings):
    key = ((settings or {}).get("anthropic") or {}).get("api_key")
    if key:
        import urllib.request
        body = json.dumps({
            "model": settings["anthropic"].get("model", "claude-haiku-4-5"), "max_tokens": 1500,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime if mime in ("image/png", "image/jpeg", "image/webp", "image/gif") else "image/png",
                                             "data": base64.b64encode(raw).decode()}},
                {"type": "text", "text": "Transcribe the text in this image (a resume, job post or job listing). "
                                         "Return only the text, keeping headings and bullet structure. If there is no readable text, return NONE."}]}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.loads(r.read().decode())
            txt = "".join(b.get("text", "") for b in out.get("content", []))
            if txt.strip() and txt.strip() != "NONE":
                return txt, None
            return None, "No readable text found in the image."
        except Exception as e:
            return None, f"Couldn't read the image with Claude ({e.__class__.__name__}). Check the API key in Settings."
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(BytesIO(raw))), None
    except Exception:
        return None, ("Saved the image, but reading text from images needs an Anthropic API key (Settings) "
                      "or Tesseract OCR. Type the key details from it in the chat.")


def extract(raw, ext, mime, settings, transcript=None):
    if ext == ".pdf":
        return pdf_text(raw)
    if ext == ".docx":
        return docx_text(raw)
    if ext == ".rtf":
        return rtf_text(raw)
    if ext in (".txt", ".md"):
        return raw.decode("utf-8", "replace"), None
    if ext in IMG_EXT:
        return image_text(raw, mime, settings)
    if ext in AUD_EXT:
        if transcript and transcript.strip():
            return transcript.strip(), None
        return None, "Voice note saved. Live transcription works in Microsoft Edge or Google Chrome; type the details if nothing was transcribed."
    return None, "Unsupported file type."


# ------------------------------------------------------------------ understanding
RESUME_HINTS = re.compile(r"\b(curriculum vitae|resume|education|work experience|professional experience|"
                          r"employment history|certifications|projects|skills|objective|profile summary)\b", re.I)
JOB_HINTS = re.compile(r"\b(responsibilities|requirements|qualifications|we are looking|you will|what you'll do|"
                       r"about the role|job description|apply now|who you are|nice to have)\b", re.I)
TITLE_LINE = re.compile(r"^\s*(senior |sr\.? |junior |lead |principal |staff )?[A-Za-z/&+.\- ]{3,50}"
                        r"(engineer|developer|analyst|scientist|manager|designer|architect|consultant|lead|specialist|executive|administrator)\b", re.I | re.M)


def resume_years(text):
    m = re.search(r"(\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:total\s+|professional\s+|industry\s+|work\s+)?experience", text, re.I)
    if m:
        return float(m.group(1))
    return None


def understand(text):
    """Classify the document and pull search fields out of it."""
    t = text or ""
    r_hits, j_hits = len(RESUME_HINTS.findall(t)), len(JOB_HINTS.findall(t))
    doc_type = "resume" if r_hits > j_hits else ("job_post" if j_hits else "notes")
    ex = parse_description(t[:20000])
    if doc_type == "resume":
        ex.pop("min_salary", None)
        ex.pop("exclude", None)
        ex.pop("employment_type", None)
        yrs = resume_years(t)
        if yrs is not None:
            lo = int(yrs)
            ex["experience"] = f"{lo}–{lo + 2} years" if lo else "0–1 years"
        else:
            ex.pop("experience", None)        # 'X years' in a resume often isn't total experience
        titles = []
        for m in TITLE_LINE.finditer(t[:6000]):
            s = re.sub(r"\s+", " ", m.group(0)).strip(" -|,")
            if 5 <= len(s) <= 60 and s.lower() not in [x.lower() for x in titles]:
                titles.append(s)
        if titles and not ex.get("roles"):
            ex["roles"] = [titles[0].lower()]
        ex["resume_titles"] = titles[:5]
    ex["skills"] = _find_terms(t[:20000], SKILLS)
    return doc_type, {k: v for k, v in ex.items() if v not in (None, "", [])}


def describe(doc_type, ex, kind):
    bits = []
    if ex.get("roles"):
        bits.append("role: " + ", ".join(ex["roles"][:3]))
    if ex.get("skills"):
        bits.append(f"{len(ex['skills'])} skills ({', '.join(ex['skills'][:6])}{'…' if len(ex['skills']) > 6 else ''})")
    if ex.get("experience"):
        bits.append("experience: " + ex["experience"])
    if ex.get("locations"):
        bits.append("location: " + ", ".join(ex["locations"]))
    label = {"resume": "your resume", "job_post": "the job post", "notes": {"voice": "your voice note", "image": "the image"}.get(kind, "your file")}[doc_type]
    return (f"From {label} I picked up " + "; ".join(bits) + ".") if bits else f"I read {label} but found nothing to add to the search."


# ------------------------------------------------------------------ storage
def save(conn, filename, mime, data_b64, settings, transcript=None):
    conn.execute(SCHEMA)
    try:
        raw = base64.b64decode(data_b64.split(",", 1)[-1], validate=False)
    except Exception:
        raise AttachmentError("The file couldn't be read. Try attaching it again.")
    if not raw:
        raise AttachmentError("The file is empty.")
    if len(raw) > MAX_BYTES:
        raise AttachmentError("That file is larger than 15 MB. Attach a smaller one.")
    ext = _ext(filename, mime)
    kind = kind_of(ext)
    if not kind:
        raise AttachmentError("Attach a PDF, Word (.docx), text file, image or voice note.")
    ATT_DIR.mkdir(parents=True, exist_ok=True)
    aid = uuid.uuid4().hex[:16]
    path = ATT_DIR / f"{aid}{ext}"
    path.write_bytes(raw)
    text, note = extract(raw, ext, mime, settings, transcript)
    doc_type, ex = understand(text) if text else ("notes", {})
    summary = describe(doc_type, ex, kind) if text else note
    safe_name = re.sub(r"[^\w.\- ()]+", "_", filename or f"attachment{ext}")[:120]
    conn.execute("INSERT INTO attachments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                 (aid, None, safe_name, mime, kind, len(raw), str(path), (text or "")[:50000], doc_type,
                  json.dumps(ex), summary, iso(now_utc())))
    return {"id": aid, "filename": safe_name, "kind": kind, "doc_type": doc_type, "extracted": ex,
            "note": summary, "has_text": bool(text), "url": f"/attachments/{aid}"}


def get(conn, aid):
    conn.execute(SCHEMA)
    r = conn.execute("SELECT * FROM attachments WHERE id=?", (aid,)).fetchone()
    if not r:
        return None
    d = {k: r[k] for k in r.keys()}
    d["extracted"] = json.loads(d.pop("extracted_json") or "{}")
    return d


def link(conn, ids, profile_id):
    conn.execute(SCHEMA)
    for aid in ids or []:
        conn.execute("UPDATE attachments SET profile_id=? WHERE id=?", (profile_id, aid))


def delete_for_profile(conn, profile_id):
    conn.execute(SCHEMA)
    for r in conn.execute("SELECT path FROM attachments WHERE profile_id=?", (profile_id,)).fetchall():
        try:
            Path(r["path"]).unlink()
        except OSError:
            pass
    conn.execute("DELETE FROM attachments WHERE profile_id=?", (profile_id,))
