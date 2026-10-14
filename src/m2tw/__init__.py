"""Magicka 2 台灣繁體中文化補丁（以遊俠 ALI213 簡體中文漢化為基礎）。"""

import sys
from pathlib import Path

__version__ = "1.0.1"

# 原始碼執行時是 repo 根目錄；打包成 exe 後是 PyInstaller 解壓出來的暫存資料夾
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
TRANSLATION_DIR = ROOT / "translation"
ASSETS_DIR = ROOT / "assets"
