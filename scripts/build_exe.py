"""打包安裝程式成單一 exe：uv run --group dev scripts/build_exe.py

輸出：dist/Magicka2-TW-Patch.exe
"""

import re
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
sep = ";" if sys.platform == "win32" else ":"

version = re.search(r'__version__ = "([^"]+)"', (ROOT / "src/m2tw/__init__.py").read_text("utf-8")).group(1)
nums = tuple(int(x) for x in (version.split(".") + ["0"] * 4)[:4])

# Windows 檔案內容裡看得到的版本資訊
BUILD.mkdir(exist_ok=True)
version_file = BUILD / "version_info.txt"
version_file.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040404b0', [
      StringStruct('CompanyName', 'Magicka2-TW-Patch contributors'),
      StringStruct('FileDescription', 'Magicka 2 台灣繁體中文化補丁安裝程式'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'Magicka2-TW-Patch'),
      StringStruct('LegalCopyright', 'MIT License (code). Fan translation based on ALI213. https://github.com/ko1596/Magicka2-TW-Patch'),
      StringStruct('OriginalFilename', 'Magicka2-TW-Patch.exe'),
      StringStruct('ProductName', 'Magicka 2 台灣繁體中文化補丁'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [0x0404, 1200])])
  ]
)
""", "utf-8")

PyInstaller.__main__.run([
    str(ROOT / "scripts" / "installer_entry.py"),
    "--name", "Magicka2-TW-Patch",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--noupx",
    "--version-file", str(version_file),
    "--icon", str(ROOT / "assets" / "icon.ico"),
    "--paths", str(ROOT / "src"),
    "--add-data", f"{ROOT / 'translation' / 'zh_tw.json'}{sep}translation",
    "--add-data", f"{ROOT / 'translation' / 'keys.json'}{sep}translation",
    "--add-data", f"{ROOT / 'assets'}{sep}assets",
    "--collect-data", "opencc",
    # 安裝程式用不到翻譯編輯器的 PySide6
    "--exclude-module", "PySide6",
    "--exclude-module", "numpy",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(BUILD),
    "--specpath", str(BUILD),
])
