"""AI and OCR services: configuration, availability, honest status and connection tests.

OCR (reading text from images) and AI (understanding text) are separate:
  * OCR engines: Windows built-in OCR (Windows 10/11, offline), Tesseract (if installed), Claude vision (needs AI key).
  * AI: Anthropic Claude, used to understand descriptions, documents and screenshot text. Optional.
Without either, the chat keeps working with built-in rules (offline mode).
"""
import base64
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
SAMPLES = HERE / "static" / "samples"
OCR_ENGINES = {"windows": "Windows built-in OCR", "tesseract": "Tesseract OCR", "claude": "Claude vision (AI)"}
LAST = {"ai": None, "ocr": None}          # last test results while the app runs

WIN_OCR_PS = r"""
param([string]$Path)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$type) {
  $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
  $null = $t.Wait(-1)
  $t.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { [Console]::Error.WriteLine('NO_OCR_LANGUAGE'); exit 3 }
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$stream.Dispose()
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
foreach ($line in $result.Lines) { [Console]::WriteLine($line.Text) }
"""


# ------------------------------------------------------------------ settings helpers
def ai_cfg(settings):
    a = (settings or {}).get("anthropic") or {}
    enabled = ((settings or {}).get("ai") or {}).get("enabled", True)
    return {"enabled": bool(enabled), "key": a.get("api_key") or "", "model": a.get("model") or "claude-haiku-4-5"}


def ai_ready(settings):
    c = ai_cfg(settings)
    return c["enabled"] and bool(c["key"])


def ocr_cfg(settings):
    o = (settings or {}).get("ocr") or {}
    return {"enabled": bool(o.get("enabled", True)), "provider": o.get("provider") or "auto"}


# ------------------------------------------------------------------ OCR engines
def _powershell():
    if os.name != "nt":
        return None
    return shutil.which("powershell.exe") or shutil.which("powershell")


def windows_ocr_available():
    if os.name != "nt" or not _powershell():
        return False
    try:
        return int(platform.release() or 0) >= 10
    except ValueError:
        return True


def tesseract_available():
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:
        return False
    return bool(shutil.which("tesseract") or os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"))


def engines_available(settings):
    out = []
    if windows_ocr_available():
        out.append("windows")
    if tesseract_available():
        out.append("tesseract")
    if ai_ready(settings):
        out.append("claude")
    return out


def _ocr_windows(raw, ext):
    ps = _powershell()
    with tempfile.TemporaryDirectory() as d:
        img = Path(d) / ("image" + (ext if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff") else ".png"))
        if ext == ".webp":
            raise RuntimeError("Windows OCR can't open .webp images. Save the screenshot as PNG or JPG.")
        img.write_bytes(raw)
        script = Path(d) / "ocr.ps1"
        script.write_text(WIN_OCR_PS, encoding="utf-8-sig")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        p = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), str(img)],
                           capture_output=True, timeout=60, creationflags=flags)
        if p.returncode != 0:
            err = p.stderr.decode("utf-8", "replace")
            if "NO_OCR_LANGUAGE" in err:
                raise RuntimeError("Windows OCR has no language pack. Add English in Windows Settings → Time & language → Language.")
            raise RuntimeError("Windows OCR failed: " + (err.strip().splitlines() or ["unknown error"])[-1][:200])
        return p.stdout.decode("utf-8", "replace")


def _ocr_tesseract(raw):
    import pytesseract
    from io import BytesIO
    from PIL import Image
    if os.name == "nt" and not shutil.which("tesseract"):
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return pytesseract.image_to_string(Image.open(BytesIO(raw)))


def _ocr_claude(raw, mime, settings):
    c = ai_cfg(settings)
    media = mime if mime in ("image/png", "image/jpeg", "image/webp", "image/gif") else "image/png"
    out = claude_call(settings, [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": media, "data": base64.b64encode(raw).decode()}},
        {"type": "text", "text": "Transcribe all text in this image (a resume, job post or job listing). Return only the text, "
                                 "keeping headings and bullets. If there is no readable text, return NONE."}]}], 1500)
    txt = out.strip()
    return "" if txt == "NONE" else txt


def ocr_image(raw, ext, mime, settings):
    """Returns (text, engine_label, note). Never pretends: no text -> text is None with a reason."""
    cfg = ocr_cfg(settings)
    if not cfg["enabled"]:
        return None, None, "OCR is turned off in Settings → AI & OCR, so text in this image wasn't read. Type the key details, or turn OCR on."
    avail = engines_available(settings)
    order = [cfg["provider"]] if cfg["provider"] in OCR_ENGINES else ["windows", "tesseract", "claude"]
    order = [e for e in order if e in avail]
    if not order:
        if cfg["provider"] in OCR_ENGINES:
            why = {"windows": "Windows built-in OCR isn't available on this computer",
                   "tesseract": "Tesseract isn't installed",
                   "claude": "Claude vision needs AI turned on and an Anthropic API key"}[cfg["provider"]]
            return None, None, f"Image saved, but text wasn't read: {why}. Change the OCR provider in Settings → AI & OCR."
        return None, None, "Image saved, but no OCR engine is available. Set one up in Settings → AI & OCR, or type the key details."
    errors = []
    for e in order:
        try:
            if e == "windows":
                txt = _ocr_windows(raw, ext)
            elif e == "tesseract":
                txt = _ocr_tesseract(raw)
            else:
                txt = _ocr_claude(raw, mime, settings)
        except Exception as ex:
            errors.append(f"{OCR_ENGINES[e]}: {ex}")
            continue
        if txt and len(txt.strip()) >= 3:
            return txt.strip(), OCR_ENGINES[e], None
        errors.append(f"{OCR_ENGINES[e]}: no readable text found")
    return None, None, "Couldn't read text from the image. " + " | ".join(errors)[:400]


# ------------------------------------------------------------------ AI
class AIError(Exception):
    pass


def claude_call(settings, messages, max_tokens=800, timeout=60):
    c = ai_cfg(settings)
    if not c["key"]:
        raise AIError("No Anthropic API key saved.")
    body = json.dumps({"model": c["model"], "max_tokens": max_tokens, "messages": messages}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": c["key"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            pass
        if e.code == 401:
            raise AIError("The API key was rejected (401). Check it at console.anthropic.com and save it again.")
        if e.code == 404:
            raise AIError(f"Model '{c['model']}' wasn't found (404). Pick another model in Settings.")
        if e.code == 429:
            raise AIError("Rate limit or credit limit reached (429). Try again later or check your Anthropic plan.")
        raise AIError(f"Anthropic API error {e.code}: {detail[:160]}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AIError(f"Couldn't reach api.anthropic.com ({e.__class__.__name__}). Check the internet connection.")
    return "".join(b.get("text", "") for b in out.get("content", []))


def test_ai(settings):
    c = ai_cfg(settings)
    t0 = time.time()
    if not c["key"]:
        res = {"ok": False, "message": "Add an Anthropic API key first."}
    else:
        try:
            claude_call(settings, [{"role": "user", "content": "Reply with the word OK."}], 5, timeout=20)
            res = {"ok": True, "message": f"Connected to Claude ({c['model']}) in {time.time() - t0:.1f}s."}
        except AIError as e:
            res = {"ok": False, "message": str(e)}
    res["at"] = time.strftime("%H:%M")
    LAST["ai"] = res
    return res


def test_ocr(settings):
    sample = SAMPLES / "sample-job-post.png"
    t0 = time.time()
    if not sample.exists():
        res = {"ok": False, "message": "The sample image is missing from the app folder; reinstall Job Radar."}
    else:
        txt, engine, note = ocr_image(sample.read_bytes(), ".png", "image/png", settings)
        if txt:
            first = next((l for l in txt.splitlines() if l.strip()), "")[:60]
            res = {"ok": True, "engine": engine,
                   "message": f"{engine} read the sample image in {time.time() - t0:.1f}s (first line: “{first}”)."}
        else:
            res = {"ok": False, "message": note}
    res["at"] = time.strftime("%H:%M")
    LAST["ocr"] = res
    return res


# ------------------------------------------------------------------ status for the chat
def status(settings):
    c, o = ai_cfg(settings), ocr_cfg(settings)
    if not c["enabled"]:
        ai = {"state": "disabled", "label": "AI Disabled", "detail": "Turned off in Settings"}
    elif not c["key"]:
        ai = {"state": "not_configured", "label": "AI Disabled", "detail": "Not configured (no API key)"}
    elif LAST["ai"] and not LAST["ai"]["ok"]:
        ai = {"state": "error", "label": "AI Error", "detail": LAST["ai"]["message"]}
    else:
        ai = {"state": "ready", "label": "AI Ready",
              "detail": f"Claude ({c['model']})" + (" · connection tested" if LAST["ai"] else " · not tested yet")}
    avail = engines_available(settings)
    if not o["enabled"]:
        ocr = {"state": "disabled", "label": "OCR Disabled", "detail": "Turned off in Settings"}
    elif not avail:
        ocr = {"state": "not_configured", "label": "OCR Disabled", "detail": "No OCR engine available"}
    elif o["provider"] in OCR_ENGINES and o["provider"] not in avail:
        ocr = {"state": "error", "label": "OCR Error", "detail": f"{OCR_ENGINES[o['provider']]} isn't available"}
    elif LAST["ocr"] and not LAST["ocr"]["ok"]:
        ocr = {"state": "error", "label": "OCR Error", "detail": LAST["ocr"]["message"]}
    else:
        use = o["provider"] if o["provider"] in OCR_ENGINES else avail[0]
        ocr = {"state": "ready", "label": "OCR Ready", "detail": OCR_ENGINES[use] + (" · tested" if LAST["ocr"] else "")}
    ai["enabled"], ai["model"], ai["key_saved"] = c["enabled"], c["model"], bool(c["key"])
    ai["key_hint"] = ("…" + c["key"][-4:]) if len(c["key"]) > 8 else ""
    ocr["enabled"], ocr["provider"], ocr["available"] = o["enabled"], o["provider"], [{"id": e, "label": OCR_ENGINES[e]} for e in avail]
    mode = "online" if ai["state"] == "ready" else "offline"
    return {"mode": mode, "ai": ai, "ocr": ocr, "last": LAST,
            "voice": {"detail": "Uses the browser's speech-to-text (Edge or Chrome, needs internet). The recording is always saved."}}
