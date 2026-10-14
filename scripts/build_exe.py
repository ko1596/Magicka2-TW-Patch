"""打包安裝程式成單一 exe：uv run --group dev scripts/build_exe.py

輸出：dist/Magicka2-TW-Patch.exe
"""

import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
sep = ";" if sys.platform == "win32" else ":"

PyInstaller.__main__.run([
    str(ROOT / "scripts" / "installer_entry.py"),
    "--name", "Magicka2-TW-Patch",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--paths", str(ROOT / "src"),
    "--add-data", f"{ROOT / 'translation'}{sep}translation",
    "--add-data", f"{ROOT / 'assets'}{sep}assets",
    "--collect-data", "opencc",
    # 安裝程式用不到翻譯編輯器的 PySide6
    "--exclude-module", "PySide6",
    "--exclude-module", "numpy",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT / "build"),
])
