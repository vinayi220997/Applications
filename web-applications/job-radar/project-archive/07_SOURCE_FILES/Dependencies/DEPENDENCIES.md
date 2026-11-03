# Dependencies

- Python 3.9+ standard library only.
- Bundled: pypdf 4.3.1 in `vendor/` (license in `06_RESOURCES_AND_ASSETS/Licenses_and_Attribution`).
- Optional at runtime: Tesseract + pytesseract + Pillow (OCR), an Anthropic API key (AI), Windows PowerShell (Windows OCR), Microsoft Edge/Chrome (voice transcription).
- Build: NSIS `makensis` (installer). Tests: `unittest`; browser tests use Playwright + Chromium.
