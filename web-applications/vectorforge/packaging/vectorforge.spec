# PyInstaller spec for the Vectorforge desktop app.
# Build:  pyinstaller packaging/vectorforge.spec --noconfirm
# Output: dist/Vectorforge/Vectorforge(.exe) plus its support files.

import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("vectorforge")
    + collect_submodules("ezdxf")
    + ["skimage.measure", "skimage.measure._find_contours", "scipy.ndimage",
       "multipart", "python_multipart"]
)

a = Analysis(
    [os.path.join(ROOT, "vectorforge", "desktop.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "vectorforge", "web"), os.path.join("vectorforge", "web"))],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "playwright", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Vectorforge",
    console=True,  # the console window shows the address and closing it quits the app
    icon=os.path.join(ROOT, "packaging", "vectorforge.ico") if os.path.exists(
        os.path.join(ROOT, "packaging", "vectorforge.ico")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Vectorforge")
