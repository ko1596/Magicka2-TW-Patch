"""尋找 Magicka 2 安裝位置，檢查遊俠漢化補丁是否已安裝。"""

import hashlib
import re
import subprocess
from pathlib import Path

# Steam 原版 PhysX3_x86.dll；遊俠補丁換成會載入 ali213.dll 的版本，被還原成這個就代表漢化失效
STEAM_PHYSX_SHA1 = "c769a1f4013ed16ff01368eb3ab31a1008d80275"
GAME_DIR_NAME = "Magicka 2"
EXE_REL = Path("engine/Magicka2.exe")
ALI213_DIR = Path("engine/ali213")
PHYSX_REL = Path("engine/PhysX3_x86.dll")


def _steam_roots() -> list[Path]:
    roots = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try:
                            roots.append(Path(winreg.QueryValueEx(k, name)[0]))
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:  # 非 Windows
        pass
    roots.append(Path(r"C:\Program Files (x86)\Steam"))
    return list(dict.fromkeys(r.resolve() for r in roots if r.exists()))


def _libraries(steam: Path) -> list[Path]:
    libs = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text("utf-8", errors="replace")):
            libs.append(Path(m.group(1).replace("\\\\", "\\")))
    return libs


def find_game() -> Path | None:
    for steam in _steam_roots():
        for lib in _libraries(steam):
            game = lib / "steamapps" / "common" / GAME_DIR_NAME
            if (game / EXE_REL).exists():
                return game
    return None


def is_game_dir(path: Path) -> bool:
    return (Path(path) / EXE_REL).exists()


def d12_path(game: Path) -> Path:
    return Path(game) / ALI213_DIR / "ali213.d12"


def check_ali213(game: Path) -> list[str]:
    """回傳缺少的項目；空清單代表遊俠漢化補丁已正確安裝。"""
    game = Path(game)
    problems = []
    for name in ("ali213.dll", "ali213.d02"):
        if not (game / ALI213_DIR / name).exists():
            problems.append(f"缺少 engine/ali213/{name}")
    d12 = d12_path(game)
    if not d12.exists() and not d12.with_name(d12.name + ".chs").exists():
        problems.append("缺少 engine/ali213/ali213.d12")
    physx = game / PHYSX_REL
    if not physx.exists() or hashlib.sha1(physx.read_bytes()).hexdigest() == STEAM_PHYSX_SHA1:
        problems.append("engine/PhysX3_x86.dll 是 Steam 原版，遊俠漢化補丁沒有生效（Steam 驗證檔案後會被還原）")
    return problems


def game_running() -> bool:
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Magicka2.exe"], capture_output=True,
                             text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return "magicka2.exe" in out.lower()
    except OSError:
        return False
