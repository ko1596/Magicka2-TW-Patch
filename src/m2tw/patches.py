"""三項修改：繁中文本、中文標題標誌、CPU 使用率優化。每項都能套用與還原。

遊戲原檔在第一次修改前備份到 <遊戲>/m2tw_backup/。之後每次套用都從備份重新產生，
所以重複套用不會疊加。如果 Steam 更新或驗證檔案把檔案換掉了（內容既不是備份也不是
我們上次寫入的版本），就把新的檔案當成原檔重新備份。
"""

import hashlib
import json
import shutil
import struct
import zlib
from pathlib import Path

from . import ASSETS_DIR

BACKUP_DIR = "m2tw_backup"
STATE_FILE = "state.json"


def _sha(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


class Backups:
    def __init__(self, game: Path):
        self.game = Path(game)
        self.dir = self.game / BACKUP_DIR
        self.state_path = self.dir / STATE_FILE
        try:
            self.state = json.loads(self.state_path.read_text("utf-8"))
        except (OSError, ValueError):
            self.state = {}

    def _save(self):
        self.dir.mkdir(exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), "utf-8")

    def original(self, rel: str) -> bytes:
        """取得遊戲原檔內容（必要時建立或更新備份）。"""
        cur = (self.game / rel).read_bytes()
        backup = self.dir / Path(rel).name
        if backup.exists():
            orig = backup.read_bytes()
            if _sha(cur) in (_sha(orig), self.state.get(rel)):
                return orig
        self.dir.mkdir(exist_ok=True)
        backup.write_bytes(cur)
        return cur

    def write(self, rel: str, data: bytes):
        (self.game / rel).write_bytes(data)
        self.state[rel] = _sha(data)
        self._save()

    def restore(self, rel: str) -> bool:
        backup = self.dir / Path(rel).name
        if rel not in self.state or not backup.exists():
            return False
        cur = (self.game / rel).read_bytes()
        if _sha(cur) == self.state[rel]:  # 只還原我們寫入的檔案，不動被 Steam 換過的
            shutil.copy2(backup, self.game / rel)
        del self.state[rel]
        self._save()
        return True

    def applied(self, rel: str) -> bool:
        target = self.game / rel
        return rel in self.state and target.exists() and _sha(target.read_bytes()) == self.state[rel]


# ---------------------------------------------------------------- 資源包讀寫

CHUNK = 0x10000


def _patch_bundle(raw: bytes, edits: list[tuple[int, bytes]], check) -> bytes:
    """資源包：12 位元組檔頭 + 一連串「4 位元組長度 + zlib 區塊」，每塊解壓後 64 KB。
    edits 是 [(解壓後位移, 新資料)]；只重新壓縮被改到的區塊。"""
    header, pos, chunks = raw[:12], 12, []
    while pos < len(raw):
        n = struct.unpack_from("<I", raw, pos)[0]
        chunks.append(raw[pos + 4:pos + 4 + n])
        pos += 4 + n
    plain = {}

    def block(i):
        if i not in plain:
            plain[i] = bytearray(zlib.decompress(chunks[i]))
        return plain[i]

    def read(at, n):
        out = bytearray()
        while len(out) < n:
            b, off = divmod(at + len(out), CHUNK)
            out += block(b)[off:off + n - len(out)]
        return bytes(out)

    for at, data in edits:
        check(read, at)
        pos, end = at, at + len(data)
        while pos < end:
            b, off = divmod(pos, CHUNK)
            take = min(CHUNK - off, end - pos)
            block(b)[off:off + take] = data[pos - at:pos - at + take]
            pos += take
    for i, data in plain.items():
        chunks[i] = zlib.compress(bytes(data), 9)
    out = bytearray(header)
    for c in chunks:
        out += struct.pack("<I", len(c)) + c
    return bytes(out)


# ---------------------------------------------------------------- 中文標題標誌

LOGO_W, LOGO_H = 660, 168
# 標題標誌（660×168 BGRA DDS）所在的資源包與 DDS 檔頭位移
LOGO_TARGETS = {
    "data/3b1335d6d0425964": (0x25584C, 0x301E1C),   # 開機時載入，標題畫面讀這份
    "data/ec181385e7000cf1": (0xA326C3C, 0xBA368FC),  # 介面資源包裡的副本
}


def _logo_pixels() -> bytes:
    from PIL import Image
    im = Image.open(ASSETS_DIR / "logo_zh.png").convert("RGBA")
    if bbox := im.getchannel("A").getbbox():  # 裁掉透明邊，讓標誌盡量放大
        im = im.crop(bbox)
    if im.size != (LOGO_W, LOGO_H):
        im.thumbnail((LOGO_W, LOGO_H), Image.LANCZOS)
        canvas = Image.new("RGBA", (LOGO_W, LOGO_H), (0, 0, 0, 0))
        canvas.paste(im, ((LOGO_W - im.width) // 2, (LOGO_H - im.height) // 2), im)
        im = canvas
    return im.tobytes("raw", "BGRA")


def _check_logo(read, dds):
    hdr = read(dds, 128)
    if hdr[:4] != b"DDS " or struct.unpack_from("<II", hdr, 12) != (LOGO_H, LOGO_W):
        raise RuntimeError("找不到標題標誌，遊戲版本可能不同")


def apply_logo(bk: Backups):
    pixels = _logo_pixels()
    for rel, offsets in LOGO_TARGETS.items():
        orig = bk.original(rel)
        bk.write(rel, _patch_bundle(orig, [(dds + 128, pixels) for dds in offsets],
                                    lambda read, at: _check_logo(read, at - 128)))


def restore_logo(bk: Backups):
    for rel in LOGO_TARGETS:
        bk.restore(rel)


def logo_applied(bk: Backups) -> bool:
    return all(bk.applied(rel) for rel in LOGO_TARGETS)


# ---------------------------------------------------------------- CPU 使用率優化

EXE_REL = "engine/Magicka2.exe"
IMAGE_BASE = 0x400000
SPIN_OLD = IMAGE_BASE + 0x3DDB38   # double 0.001：工作執行緒空轉 1 毫秒才休眠
SPIN_NEW = IMAGE_BASE + 0x3E24A0   # .rdata 裡被當 double 讀取的 0.0：沒工作就立刻休眠
# comisd xmm0, [門檻] 指令裡位址欄位的 RVA：工作迴圈、派工端（兩處必須一致，否則睡著的執行緒不會被叫醒）
SPIN_SITES = (0x2FB7D4, 0x2FB47F)


def _rva_to_offset(data: bytes, rva: int) -> int:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    sec = pe + 24 + struct.unpack_from("<H", data, pe + 20)[0]
    for i in range(nsec):
        size, va = struct.unpack_from("<II", data, sec + i * 40 + 8)
        raw = struct.unpack_from("<I", data, sec + i * 40 + 20)[0]
        if va <= rva < va + size:
            return rva - va + raw
    raise ValueError(hex(rva))


def apply_cpu(bk: Backups):
    data = bytearray(bk.original(EXE_REL))
    if struct.unpack_from("<d", data, _rva_to_offset(data, SPIN_NEW - IMAGE_BASE))[0] != 0.0:
        raise RuntimeError("Magicka2.exe 版本不同，無法套用 CPU 優化")
    for rva in SPIN_SITES:
        off = _rva_to_offset(data, rva)
        if data[off - 4:off] != b"\x66\x0f\x2f\x05" or struct.unpack_from("<I", data, off)[0] != SPIN_OLD:
            raise RuntimeError("Magicka2.exe 版本不同，無法套用 CPU 優化")
        struct.pack_into("<I", data, off, SPIN_NEW)
    bk.write(EXE_REL, bytes(data))


def restore_cpu(bk: Backups):
    bk.restore(EXE_REL)


def cpu_applied(bk: Backups) -> bool:
    return bk.applied(EXE_REL)


# ---------------------------------------------------------------- 繁中文本

SIMPLIFIED_ONLY = "们这说时会还发现们与为过对来经问应该关于"


def is_simplified(path: Path) -> bool:
    """遊俠原檔是簡體；我們寫出的繁體檔不會出現這些簡體專用字。"""
    text = path.read_text("utf-8-sig", errors="replace")
    return sum(text.count(c) for c in SIMPLIFIED_ONLY) > 50


def apply_text(game: Path) -> str:
    from .game import d12_path
    from .translate import Project, self_check
    d12 = d12_path(game)
    chs = d12.with_name(d12.name + ".chs")
    bk = Backups(game)
    if not chs.exists() and not is_simplified(d12):
        raise RuntimeError("ali213.d12 不是遊俠的簡體原檔，請重新安裝遊俠漢化補丁")
    # 遊俠補丁重新安裝過（d12 又變回簡體）→ 以新的簡體檔為準
    if chs.exists() and is_simplified(d12):
        shutil.copy2(d12, chs)
    p = Project(d12)
    self_check(p)
    results = p.convert_all()
    p.write(results)
    bk.state["text"] = _sha(d12.read_bytes())
    bk._save()
    stale = p.stale_overrides()
    msg = f"已寫入 {len(results)} 條繁體中文"
    if stale:
        msg += f"（{len(stale)} 條手動譯文對應的簡體原文和預期不同，遊俠補丁版本可能不一樣）"
    return msg


def restore_text(game: Path) -> bool:
    from .game import d12_path
    d12 = d12_path(game)
    chs = d12.with_name(d12.name + ".chs")
    if not chs.exists():
        return False
    shutil.copy2(chs, d12)
    bk = Backups(game)
    bk.state.pop("text", None)
    bk._save()
    return True


def text_applied(game: Path) -> bool:
    from .game import d12_path
    d12 = d12_path(game)
    return d12.exists() and Backups(game).state.get("text") == _sha(d12.read_bytes())
