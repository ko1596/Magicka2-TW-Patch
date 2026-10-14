"""Magicka 2 遊俠漢化（ali213.d12）簡轉繁工具與翻譯編輯器。

可重做的設計：
  * 第一次執行時把遊戲裡的遊俠簡體檔備份為 ali213.d12.chs，之後每次轉換都從這份備份重新產生，
    不會在繁體上再轉一次。
  * 轉換設定（OpenCC 模式、詞彙替換表、逐條手動修改）存在 translation/zh_tw.json，
    這份檔案就是本專案的譯文，不含遊俠的簡體原文（只存原文的雜湊值，用來偵測原文變動）。

用法（在 repo 根目錄）：
  uv run m2tw-editor [d12路徑]        開啟翻譯編輯器（需要 PySide6：uv sync --extra editor）
  uv run m2tw-convert [d12路徑]       不開視窗，直接照設定重新轉換並寫入遊戲
  沒有指定路徑時會自動尋找 Steam 裡的 Magicka 2。
"""

import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from opencc import OpenCC

from . import TRANSLATION_DIR

DEFAULT_CFG = TRANSLATION_DIR / "zh_tw.json"
DEFAULT_KEYS = TRANSLATION_DIR / "keys.json"

MODES = [
    ("s2twp", "台灣正體＋台灣用語（推薦）"),
    ("s2tw", "台灣正體（只轉字形）"),
    ("s2t", "OpenCC 標準繁體"),
    ("s2hk", "香港繁體"),
]

ENTRY_RE = re.compile(
    r"xfhsm_res_No\.(\d+)\r?\n"
    r"xfhsm_res_ENG_Start\r?\n(.*?)xfhsm_res_ENG_End\r?\n"
    r"xfhsm_res_CHI_Start\r?\n(.*?)xfhsm_res_CHI_End\r?\n"
    r"xfhsm_res_Remark00_Start\r?\n(.*?)xfhsm_res_Remark00_End",
    re.S,
)


# ---------------------------------------------------------------- 文字處理

def is_wide(c: str) -> bool:
    """漢化檔會在中文字與全形標點後面各插一個空格（讓引擎能斷行）。"""
    o = ord(c)
    return o >= 0x2E80 or 0x2010 <= o <= 0x2027


def unspace(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        out.append(s[i])
        i += 2 if is_wide(s[i]) and s[i + 1:i + 2] == " " else 1
    return "".join(out)


def respace(s: str) -> str:
    return "".join(c + " " if is_wide(c) else c for c in s)


LATIN_CJK = re.compile(r"(?<=[A-Za-z0-9®™%])(?=[㐀-鿿豈-﫿])")


def latin_gap(s: str) -> str:
    """英文字母／數字後面緊接中文字時，遊戲裡兩種字型會疊在一起（例如「Boss時間」），補一個半形空格。"""
    return LATIN_CJK.sub(" ", s)


WRAP_LIMIT = 26  # 字幕等元件不會自動換行，單行超過這個字數就在標點處斷行
WRAP_POINT = re.compile(r"(?<=[。！？；，、：…」』）])(?![。！？；，、：…」』）])")
MARKUP = re.compile(r"\[[^\]]*\]|#[A-Za-z0-9_]+;")


def visible_len(s: str) -> int:
    # 變數會被換成名字，抓個大約長度；其他標記不佔寬度
    return len(MARKUP.sub(lambda m: "名字" if m.group().startswith("#") else "", s))


NO_LINE_START = "。！？；，、：…」』）～.,!?;:)—·"  # 不能放在行首
NO_LINE_END = "「『（“‘《·"                          # 不能放在行尾


def _can_cut(line: str, i: int, spans) -> bool:
    """能否在 line[i] 之前換行：不在標記中間、旁邊至少一邊是中文（不切開英文和符號）、
    新行開頭不是標點。"""
    if i <= 0 or i >= len(line) or any(a < i < b for a, b in spans):
        return False
    a, b = line[i - 1], line[i]
    if not (is_wide(a) or is_wide(b) or a == " "):
        return False
    if "·" in line[max(0, i - 3):i + 3]:  # 不拆開「菲爾·嗝考克」這類外國人名
        return False
    return b not in NO_LINE_START and a not in NO_LINE_END


def _wrap_line(line: str, limit: int) -> list[str]:
    """算出要分幾行，再挑最接近平均長度的位置切，優先切在標點後，讓每行長短接近。"""
    spans = [m.span() for m in MARKUP.finditer(line)]
    ok = [i for i in range(1, len(line)) if _can_cut(line, i, spans)]
    punct = {m.start() for m in WRAP_POINT.finditer(line)} & set(ok)
    pos = {i: visible_len(line[:i]) for i in ok}
    parts, start, begin = [], 0, 0
    while visible_len(line[start:]) > limit:
        rest = visible_len(line[start:])
        target = begin + rest / -(-rest // limit)  # 剩下的平均分成幾行
        fits = [i for i in ok if i > start and 4 <= pos[i] - begin <= limit]
        if not fits:
            break
        # 不是標點的位置加重扣分，除非標點離得太遠，否則一律斷在標點後
        cut = min(fits, key=lambda i: abs(pos[i] - target) + (0 if i in punct else limit / 2))
        parts.append(line[start:cut])
        start, begin = cut, pos[cut]
    parts.append(line[start:])
    return parts


def auto_wrap(s: str, limit: int = WRAP_LIMIT) -> str:
    """把過長的單行平均斷成幾行；優先斷在標點後，不切開標記、英文單字或專有名詞。"""
    out = []
    for line in s.split("\n"):
        out.extend([line] if visible_len(line) <= limit else _wrap_line(line, limit))
    return "\n".join(out)


BROKEN_GLYPHS = "獨"  # 圖集裡有字，但 ali213.dll 的字形資料壞掉，遊戲裡會被拉寬、變糊


def missing_glyphs(s: str) -> str:
    """字型圖集 ali213.d02 是按 GBK 字集排的，GBK 以外的全形字很可能沒有字形；
    另外列出已知在遊戲裡顯示壞掉的字。"""
    bad = []
    for c in s:
        if c in BROKEN_GLYPHS:
            bad.append(c)
        elif is_wide(c):
            try:
                c.encode("gbk")
            except UnicodeEncodeError:
                bad.append(c)
    return "".join(dict.fromkeys(bad))


# 依遊戲內部字串名稱（ali213.d12.keys.json）的前綴分類，由上往下比對，先符合者為準
CATEGORY_RULES = [
    (r"^joa_(\d)_(\d)_", r"劇情 第\1章-\2"),
    (r"^joa_veteran", "老兵對話"),
    (r"^(joa_)?dlc\d", "DLC 劇本"),
    (r"^joa_dlc_pack|^dlc_bundles", "DLC 說明"),
    (r"^test_|^debug_|^ipsum|^NXD|^G3u", "測試字串（遊戲內不會出現）"),
    (r"^(joa_)?char_|^joa_unit_veteran", "人物名稱"),
    (r"^(joa_)?family_", "種族名稱"),
    (r"^joa_loc_|^joa_prison_orb|^troll_cave", "地名"),
    (r"^unit_|encounter_bar|_golem$|^goblin_miner", "敵人／單位"),
    (r"^navigation_|^pause$|^roof_zoom", "按鍵提示"),
    (r"^creator_", "挑戰"),
    (r"^damage_", "戰鬥提示"),
    (r"^(lock_all_elements|lock_element|stasis|focus|raise_dead|resurrect|self_shield|conflagration|flame_tornado|kebab)$",
     "魔法與教學"),
    (r"^legal_|^eula_|tos_hyperlink|^new_username", "帳號／連線"),
    (r"^joa_ui_robe_color", "法袍顏色"),
    (r"^joa_ui_robe", "法袍"),
    (r"^joa_ui_weapon", "武器"),
    (r"^joa_ui_staff", "法杖"),
    (r"^joa_ui_familiar", "使魔"),
    (r"artifact", "神器"),
    (r"magick|^joa_tutorial|^element", "魔法與教學"),
    (r"challenge|^joa_cha_", "挑戰"),
    (r"trial", "試煉"),
    (r"^joa_mission", "任務說明"),
    (r"^joa_ui_credits", "製作名單"),
    (r"settings|^joa_ui_voice|keybind|^joa_ui_input", "設定"),
    (r"login|^pops_|cloud|psn|^join_|lobby|serverlist|network|^joa_ui_chat|account|steam", "帳號／連線"),
    (r"^joa_ui_|^menu_|^player_", "其他介面"),
]


def category(key: str, eng: str) -> str:
    if not key:
        return "對話（無內部名稱）" if "[P=" in eng else "其他（無內部名稱）"
    for pattern, label in CATEGORY_RULES:
        if m := re.search(pattern, key):
            return m.expand(label)
    return "其他"


def make_converter(mode: str) -> OpenCC:
    try:
        return OpenCC(mode)
    except Exception:
        return OpenCC(mode + ".json")  # 官方 opencc 套件需要 .json 後綴


# ---------------------------------------------------------------- 檔案與專案

@dataclass
class Entry:
    no: str
    eng: str        # 其實是 id=XXXXXXXXh
    chs: str        # 簡體原文（含引擎用空格與結尾換行）
    remark: str     # 英文原文
    span: tuple     # CHI 內容在原始檔中的位置；新增條目為 None
    no_span: tuple = None   # 編號數字在原始檔中的位置
    block: tuple = None     # 整個區塊（含後面的空行）在原始檔中的位置


def entry_id(e: Entry) -> int:
    return int(e.eng[3:-1], 16)


NEW_BLOCK = (
    "xfhsm_res_No.{no:08d}\r\nxfhsm_res_ENG_Start\r\n{id}\r\nxfhsm_res_ENG_End\r\n"
    "xfhsm_res_CHI_Start\r\n{text}\r\nxfhsm_res_CHI_End\r\n"
    "xfhsm_res_Remark00_Start\r\n{eng}\r\nxfhsm_res_Remark00_End\r\n\r\n"
)


def src_hash(simplified: str) -> str:
    """簡體原文的指紋：用來偵測遊俠原文是否變動，譯文檔裡不保存簡體原文本身。"""
    return hashlib.sha1(simplified.encode("utf-8")).hexdigest()[:12]


class Project:
    def __init__(self, d12: Path, cfg_path: Path = DEFAULT_CFG, keys_path: Path = DEFAULT_KEYS):
        self.d12 = Path(d12)
        self.backup = self.d12.with_name(self.d12.name + ".chs")
        self.cfg_path = Path(cfg_path)
        self.created_backup = False
        if not self.backup.exists():
            shutil.copy2(self.d12, self.backup)
            self.created_backup = True

        raw = self.backup.read_bytes()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        self.source = raw.decode("utf-8-sig")  # 保留 CRLF/LF 原樣
        matches = list(ENTRY_RE.finditer(self.source))
        self.entries = []
        for k, m in enumerate(matches):
            # 區塊從編號行開始，到下一個區塊開頭為止；最後一塊只算到後面那個空行
            end = matches[k + 1].start() if k + 1 < len(matches) else m.end() + 4
            self.entries.append(Entry(m.group(1), m.group(2).strip(), m.group(3), m.group(4).rstrip("\r\n"),
                                      m.span(3), m.span(1), (m.start(), end)))
        self.tail_start = self.entries[-1].block[1]

        self.mode = "s2twp"
        self.phrases: list[list[str]] = []          # [[繁體輸出中的詞, 改成]]
        self.overrides: dict[str, dict] = {}        # {id: {"src": 簡體原文雜湊, "text": 繁體(無空格)}}
        self.additions: dict[str, str] = {}         # 原檔沒有的條目 {id: 英文原文}，譯文放在 overrides
        # 自動斷行：角色對話框比較窄，用 narrow；其他（過場字幕、說明框）用 default
        self.wrap: dict = {"default": 40, "narrow": WRAP_LIMIT, "narrow_ids": []}
        if self.cfg_path.exists():
            cfg = json.loads(self.cfg_path.read_text("utf-8"))
            self.mode = cfg.get("mode", self.mode)
            self.phrases = cfg.get("phrases", [])
            self.overrides = cfg.get("overrides", {})
            self.additions = cfg.get("additions", {})
            self.wrap.update(cfg.get("wrap", {}))

        # 遊戲內部字串名稱（從資源包反查），用來分類；沒有這個檔也能正常運作
        keys_path = Path(keys_path)
        self.keys: dict[str, str] = json.loads(keys_path.read_text("utf-8")) if keys_path.exists() else {}

        known = {e.eng for e in self.entries}
        for eid, eng in self.additions.items():
            if eid not in known:
                self.entries.append(Entry("新增", eid, "", eng, None))
        self.entries.sort(key=entry_id)

    def set_override(self, e: Entry, text: str):
        self.overrides[e.eng] = {"src": src_hash(unspace(e.chs).rstrip("\r\n")), "text": text}

    def key_of(self, e: Entry) -> str:
        return self.keys.get(e.eng[3:11], "")

    def save_config(self):
        cfg = {"mode": self.mode, "phrases": self.phrases, "overrides": self.overrides,
               "additions": self.additions, "wrap": self.wrap}
        self.cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")

    def auto_convert(self, cc: OpenCC, e: Entry) -> str:
        """回傳不含引擎空格的繁體文字（OpenCC + 詞彙替換表，不含手動修改）。"""
        text = cc.convert(unspace(e.chs).rstrip("\r\n"))
        for src, dst in sorted((p for p in self.phrases if p[0]), key=lambda p: -len(p[0])):
            text = text.replace(src, dst)
        return text

    def convert_all(self) -> list[str]:
        """回傳每條的最終繁體（不含引擎空格與結尾換行）。"""
        cc = make_converter(self.mode)
        out = []
        for e in self.entries:
            ov = self.overrides.get(e.eng)
            out.append(ov["text"] if ov else self.auto_convert(cc, e))
        return out

    def stale_overrides(self) -> set[str]:
        """手動修改時的簡體原文和目前備份不同（例如換了新版漢化檔）。"""
        cur = {e.eng: src_hash(unspace(e.chs).rstrip("\r\n")) for e in self.entries}
        return {k for k, v in self.overrides.items() if cur.get(k) != v.get("src")}

    def write(self, results: list[str]):
        # ali213.dll 依 ID 排序查表，所以整份依 ID 順序輸出並重新連續編號；
        # 原有區塊除了編號和 CHI 內容之外逐字保留
        src = self.source
        parts = [src[:min(e.block[0] for e in self.entries if e.block)]]  # 檔頭
        narrow = set(self.wrap["narrow_ids"])
        # 置中的單行短標籤：引擎會把斷行用的空格也算進寬度，造成置中偏移，所以不加
        nospace = set(self.wrap.get("nospace_ids", []))
        for no, (e, text) in enumerate(zip(self.entries, results)):
            limit = self.wrap["narrow"] if e.eng in narrow else self.wrap["default"]
            body = latin_gap(auto_wrap(text.rstrip("\r\n"), limit))
            if e.eng not in nospace:
                body = respace(body)
            if e.block is None:
                parts.append(NEW_BLOCK.format(no=no, id=e.eng, text=body, eng=e.remark))
                continue
            (b0, b1), (n0, n1), (c0, c1) = e.block, e.no_span, e.span
            tail = e.chs[len(e.chs.rstrip("\r\n")):]  # 保留 CHI 區塊結尾換行
            parts += [src[b0:n0], f"{no:0{n1 - n0}d}", src[n1:c0], body + tail, src[c1:b1]]
        parts.append(src[self.tail_start:])
        data = "".join(parts).encode("utf-8")
        self.d12.write_bytes((b"\xef\xbb\xbf" if self.bom else b"") + data)

    def restore(self):
        shutil.copy2(self.backup, self.d12)


def self_check(p: Project):
    """不轉換時，去空格再補空格必須和原檔逐字相同，否則格式規則有誤。"""
    for e in p.entries:
        body = e.chs.rstrip("\r\n")
        if respace(unspace(body)) != body:
            raise RuntimeError(f"空格規則無法還原第 {e.no} 條：{body!r}")


# ---------------------------------------------------------------- CLI

def run_cli(path: Path):
    sys.stdout.reconfigure(errors="replace")  # cp950 主控台印不出部分字
    p = Project(path)
    self_check(p)
    if p.created_backup:
        print(f"已備份簡體原檔：{p.backup}")
    results = p.convert_all()
    p.write(results)
    bad = {c for r in results for c in missing_glyphs(r)} - set(missing_glyphs(p.source))
    print(f"已寫入 {len(results)} 條（模式 {p.mode}、替換詞 {len(p.phrases)} 組、手動修改 {len(p.overrides)} 條、"
          f"新增 {len(p.additions)} 條）")
    if stale := p.stale_overrides():
        print(f"警告：{len(stale)} 條手動修改的簡體原文已變動：{', '.join(sorted(stale))}")
    if bad:
        print(f"警告：以下字可能不在字型圖集裡：{''.join(sorted(bad))}")


# ---------------------------------------------------------------- GUI

def run_gui(path: Path):
    from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
    from PySide6.QtGui import QBrush, QColor
    from PySide6.QtWidgets import (
        QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
        QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
        QPushButton, QSplitter, QTableView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    )

    COL_NO, COL_ID, COL_CAT, COL_ENG, COL_CHS, COL_CHT = range(6)
    HEADERS = ["#", "ID", "分類", "英文原文", "簡體", "繁體"]
    OVERRIDE_BG = QBrush(QColor(255, 200, 60, 70))
    WARN_FG = QBrush(QColor(220, 50, 47))

    def one_line(s: str) -> str:
        return s.replace("\r\n", " ⏎ ").replace("\n", " ⏎ ")

    class EntryModel(QAbstractTableModel):
        def __init__(self):
            super().__init__()
            self.project: Project | None = None
            self.results: list[str] = []
            self.rows: list[list[str]] = []
            self.stale: set[str] = set()
            self.warn: list[str] = []
            self.blobs: list[str] = []  # 給搜尋用的小寫字串

        def set_project(self, project: Project):
            self.beginResetModel()
            self.project = project
            self.keys = [project.key_of(e) for e in project.entries]
            self.cats = [category(k, e.remark) for k, e in zip(self.keys, project.entries)]
            self.rows = [[e.no, e.eng, c, e.remark, unspace(e.chs).rstrip("\r\n")]
                         for e, c in zip(project.entries, self.cats)]
            self.results = project.convert_all()
            self.refresh_cache()
            self.endResetModel()

        def reconvert(self):
            self.results = self.project.convert_all()
            self.refresh_cache()
            if self.rows:
                self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, COL_CHT))

        def refresh_cache(self):
            self.stale = self.project.stale_overrides()
            self.warn = [missing_glyphs(t) for t in self.results]
            self.blobs = ["\n".join(r + [k, t]).lower() for r, k, t in zip(self.rows, self.keys, self.results)]

        def is_override(self, r):
            return self.project.entries[r].eng in self.project.overrides

        def has_warning(self, r):
            return bool(self.warn[r]) or self.project.entries[r].eng in self.stale

        def rowCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(self.rows)

        def columnCount(self, parent=QModelIndex()):
            return 6

        def headerData(self, section, orientation, role=Qt.DisplayRole):
            if role == Qt.DisplayRole and orientation == Qt.Horizontal:
                return HEADERS[section]

        def data(self, index, role=Qt.DisplayRole):
            r, c = index.row(), index.column()
            full = self.results[r] if c == COL_CHT else self.rows[r][c]
            if role == Qt.DisplayRole:
                return one_line(full)
            if role == Qt.ToolTipRole and c >= COL_ENG:
                return full
            if role == Qt.ToolTipRole and c == COL_CAT:
                return self.keys[r] or "（沒有內部名稱）"
            if role == Qt.BackgroundRole and self.is_override(r):
                return OVERRIDE_BG
            if role == Qt.ForegroundRole and c == COL_CHT and self.has_warning(r):
                return WARN_FG
            return None

    class FilterProxy(QSortFilterProxyModel):
        def __init__(self, src: EntryModel):
            super().__init__()
            self.src = src
            self.setSourceModel(src)
            self.query = ""
            self.only_override = False
            self.only_warn = False
            self.cat = ""

        def filterAcceptsRow(self, row, parent):
            s = self.src
            if self.cat and s.cats[row] != self.cat:
                return False
            if self.only_override and not s.is_override(row):
                return False
            if self.only_warn and not s.has_warning(row):
                return False
            return not self.query or self.query in s.blobs[row]

        def refilter(self):
            if hasattr(self, "beginFilterChange"):  # Qt 6.10+ 起 invalidateFilter() 已棄用
                self.beginFilterChange()
                self.endFilterChange()
            else:
                self.invalidateFilter()

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Magicka 2 漢化 簡轉繁工具")
            self.resize(1400, 860)
            self.project: Project | None = None
            self.cc = None
            self.current_row = -1
            self.filling = False

            # 上方：檔案與模式
            self.path_edit = QLineEdit(str(path))
            browse = QPushButton("瀏覽…")
            browse.clicked.connect(self.browse)
            load = QPushButton("載入")
            load.clicked.connect(lambda: self.load(Path(self.path_edit.text())))
            self.mode_box = QComboBox()
            for key, label in MODES:
                self.mode_box.addItem(f"{label}  [{key}]", key)
            self.mode_box.currentIndexChanged.connect(self.on_mode)
            top = QHBoxLayout()
            top.addWidget(QLabel("ali213.d12："))
            top.addWidget(self.path_edit, 1)
            top.addWidget(browse)
            top.addWidget(load)
            top.addSpacing(16)
            top.addWidget(QLabel("轉換模式："))
            top.addWidget(self.mode_box)

            # 篩選
            self.search = QLineEdit()
            self.search.setPlaceholderText("搜尋 ID／英文／簡體／繁體…")
            self.search.textChanged.connect(self.apply_filter)
            self.only_override = QCheckBox("只看手動修改")
            self.only_warn = QCheckBox("只看警告（缺字／原文已變動）")
            for cb in (self.only_override, self.only_warn):
                cb.toggled.connect(self.apply_filter)
            self.cat_box = QComboBox()
            self.cat_box.setMinimumContentsLength(14)
            self.cat_box.currentIndexChanged.connect(self.apply_filter)
            filt = QHBoxLayout()
            filt.addWidget(QLabel("分類："))
            filt.addWidget(self.cat_box)
            filt.addWidget(self.search, 1)
            filt.addWidget(self.only_override)
            filt.addWidget(self.only_warn)

            # 主表格（每列一行，完整內容在下方面板）
            self.model = EntryModel()
            self.proxy = FilterProxy(self.model)
            self.view = QTableView()
            self.view.setModel(self.proxy)
            self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.view.setSelectionMode(QAbstractItemView.SingleSelection)
            self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.view.setWordWrap(False)
            self.view.verticalHeader().hide()
            self.view.verticalHeader().setDefaultSectionSize(24)
            hh = self.view.horizontalHeader()
            hh.setSectionResizeMode(COL_NO, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(COL_ID, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(COL_CAT, QHeaderView.ResizeToContents)
            for c in (COL_ENG, COL_CHS, COL_CHT):
                hh.setSectionResizeMode(c, QHeaderView.Stretch)
            self.view.selectionModel().currentRowChanged.connect(self.on_select)

            # 詳細／編輯面板
            self.eng_box = QPlainTextEdit(readOnly=True)
            self.chs_box = QPlainTextEdit(readOnly=True)
            self.auto_box = QPlainTextEdit(readOnly=True)
            self.cht_box = QPlainTextEdit()
            self.cht_box.setPlaceholderText("在這裡修改繁體譯文，不用打字間空格（寫入時會自動補上）")
            for box in (self.eng_box, self.chs_box, self.auto_box):
                box.setMaximumHeight(64)
            self.cht_box.setMaximumHeight(84)
            self.info = QLabel()
            self.info.setWordWrap(True)
            apply_btn = QPushButton("套用修改 (Ctrl+Enter)")
            apply_btn.setShortcut("Ctrl+Return")
            apply_btn.clicked.connect(self.apply_edit)
            revert_btn = QPushButton("恢復自動轉換")
            revert_btn.clicked.connect(self.revert_edit)
            ebtn = QHBoxLayout()
            ebtn.addWidget(self.info, 1)
            ebtn.addWidget(revert_btn)
            ebtn.addWidget(apply_btn)
            detail = QWidget()
            form = QFormLayout(detail)
            form.setContentsMargins(0, 0, 0, 0)
            form.addRow("英文原文", self.eng_box)
            form.addRow("簡體原文", self.chs_box)
            form.addRow("自動轉換", self.auto_box)
            form.addRow("最終繁體", self.cht_box)
            form.addRow(ebtn)

            left = QSplitter(Qt.Vertical)
            left.addWidget(self.view)
            left.addWidget(detail)
            left.setStretchFactor(0, 3)
            left.setStretchFactor(1, 1)

            # 詞彙替換表
            self.phrase_table = QTableWidget(0, 2)
            self.phrase_table.setHorizontalHeaderLabels(["繁體輸出中的詞", "改成"])
            self.phrase_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.phrase_table.verticalHeader().hide()
            self.phrase_table.itemChanged.connect(self.on_phrase_edit)
            add_p = QPushButton("新增")
            add_p.clicked.connect(self.add_phrase)
            del_p = QPushButton("刪除選取")
            del_p.clicked.connect(self.del_phrase)
            prow = QHBoxLayout()
            prow.addWidget(add_p)
            prow.addWidget(del_p)
            side = QWidget()
            sl = QVBoxLayout(side)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.addWidget(QLabel("詞彙替換表\nOpenCC 轉完之後套用，長詞優先；\n適合統一遊戲專有名詞。"))
            sl.addWidget(self.phrase_table, 1)
            sl.addLayout(prow)

            split = QSplitter()
            split.addWidget(left)
            split.addWidget(side)
            split.setStretchFactor(0, 4)
            split.setStretchFactor(1, 1)

            # 下方按鈕
            write = QPushButton("轉換並寫入 ali213.d12")
            write.setStyleSheet("font-weight: bold; padding: 6px 16px;")
            write.clicked.connect(self.write)
            restore = QPushButton("還原成簡體原檔")
            restore.clicked.connect(self.restore)
            bottom = QHBoxLayout()
            bottom.addStretch(1)
            bottom.addWidget(restore)
            bottom.addWidget(write)

            central = QWidget()
            lay = QVBoxLayout(central)
            lay.addLayout(top)
            lay.addLayout(filt)
            lay.addWidget(split, 1)
            lay.addLayout(bottom)
            self.setCentralWidget(central)

            if path.exists():
                self.load(path)

        # ---- 載入與轉換
        def browse(self):
            f, _ = QFileDialog.getOpenFileName(self, "選擇 ali213.d12", self.path_edit.text(), "ali213.d12 (*.d12);;所有檔案 (*)")
            if f:
                self.path_edit.setText(f)
                self.load(Path(f))

        def load(self, p: Path):
            try:
                proj = Project(p)
                self_check(proj)
            except Exception as ex:
                QMessageBox.critical(self, "載入失敗", str(ex))
                return
            self.project = proj
            if proj.created_backup:
                QMessageBox.information(
                    self, "已建立備份",
                    f"已把目前的檔案備份為：\n{proj.backup}\n\n之後所有轉換都從這份簡體備份重新產生。\n"
                    "（如果這個檔案已經是繁體，請先刪掉 .chs 備份並放回簡體原檔。）")
            self.mode_box.blockSignals(True)
            self.mode_box.setCurrentIndex(max(0, self.mode_box.findData(proj.mode)))
            self.mode_box.blockSignals(False)
            self.cc = make_converter(proj.mode)
            self.fill_phrases()
            self.model.set_project(proj)
            self.fill_categories()
            self.current_row = -1
            self.show_detail()
            self.apply_filter()

        def reconvert(self):
            if self.project:
                self.model.reconvert()
                self.proxy.refilter()
                self.show_detail()
                self.update_status()

        def on_mode(self):
            if self.project:
                self.project.mode = self.mode_box.currentData()
                self.cc = make_converter(self.project.mode)
                self.project.save_config()
                self.reconvert()

        # ---- 詳細面板
        def on_select(self, cur, _prev):
            self.current_row = self.proxy.mapToSource(cur).row() if cur.isValid() else -1
            self.show_detail()

        def show_detail(self):
            r = self.current_row
            if not self.project or r < 0:
                for b in (self.eng_box, self.chs_box, self.auto_box, self.cht_box):
                    b.setPlainText("")
                self.info.setText("")
                return
            e = self.project.entries[r]
            self.eng_box.setPlainText(e.remark)
            self.chs_box.setPlainText(unspace(e.chs).rstrip("\r\n"))
            self.auto_box.setPlainText(self.project.auto_convert(self.cc, e))
            self.cht_box.setPlainText(self.model.results[r])
            notes = [f"{e.eng}（第 {e.no} 條）", self.model.keys[r] or "沒有內部名稱"]
            if self.model.is_override(r):
                notes.append("手動修改")
            if e.eng in self.model.stale:
                notes.append("⚠ 簡體原文已變動，請確認這條手動修改")
            if self.model.warn[r]:
                notes.append(f"⚠ 可能缺字形（不在 GBK）：{self.model.warn[r]}")
            self.info.setText("｜".join(notes))

        def apply_edit(self):
            r = self.current_row
            if not self.project or r < 0:
                return
            e = self.project.entries[r]
            # 編輯框統一用 \n；原文多行時用的是哪種換行就沿用哪種
            eol = "\r\n" if "\r\n" in e.chs.rstrip("\r\n") else "\n"
            new = unspace(self.cht_box.toPlainText().strip("\r\n")).replace("\n", eol)
            if new == self.project.auto_convert(self.cc, e):
                self.project.overrides.pop(e.eng, None)
            else:
                self.project.set_override(e, new)
            self.project.save_config()
            self.reconvert()

        def revert_edit(self):
            if self.project and self.current_row >= 0:
                self.project.overrides.pop(self.project.entries[self.current_row].eng, None)
                self.project.save_config()
                self.reconvert()

        # ---- 詞彙表
        def fill_phrases(self):
            self.filling = True
            self.phrase_table.setRowCount(len(self.project.phrases))
            for r, (a, b) in enumerate(self.project.phrases):
                self.phrase_table.setItem(r, 0, QTableWidgetItem(a))
                self.phrase_table.setItem(r, 1, QTableWidgetItem(b))
            self.filling = False

        def read_phrases(self):
            out = []
            for r in range(self.phrase_table.rowCount()):
                a, b = (self.phrase_table.item(r, c) for c in (0, 1))
                out.append([a.text() if a else "", b.text() if b else ""])
            self.project.phrases = out
            self.project.save_config()

        def on_phrase_edit(self, _):
            if not self.filling and self.project:
                self.read_phrases()
                self.reconvert()

        def add_phrase(self):
            if not self.project:
                return
            r = self.phrase_table.rowCount()
            self.filling = True
            self.phrase_table.insertRow(r)
            self.phrase_table.setItem(r, 0, QTableWidgetItem(""))
            self.phrase_table.setItem(r, 1, QTableWidgetItem(""))
            self.filling = False
            self.phrase_table.setCurrentCell(r, 0)
            self.phrase_table.editItem(self.phrase_table.item(r, 0))

        def del_phrase(self):
            rows = sorted({i.row() for i in self.phrase_table.selectedIndexes()}, reverse=True)
            for r in rows:
                self.phrase_table.removeRow(r)
            if self.project:
                self.read_phrases()
                self.reconvert()

        # ---- 篩選與狀態
        def fill_categories(self):
            """分類下拉選單：依劇情章節排在前面，其餘依筆數多寡。"""
            counts = {}
            for c in self.model.cats:
                counts[c] = counts.get(c, 0) + 1
            order = sorted(counts, key=lambda c: (not c.startswith("劇情"), c if c.startswith("劇情") else -counts[c]))
            self.cat_box.blockSignals(True)
            self.cat_box.clear()
            self.cat_box.addItem(f"全部（{len(self.model.cats)}）", "")
            for c in order:
                self.cat_box.addItem(f"{c}（{counts[c]}）", c)
            self.cat_box.blockSignals(False)

        def apply_filter(self):
            self.proxy.cat = self.cat_box.currentData() or ""
            self.proxy.query = self.search.text().strip().lower()
            self.proxy.only_override = self.only_override.isChecked()
            self.proxy.only_warn = self.only_warn.isChecked()
            self.proxy.refilter()
            self.update_status()

        def update_status(self):
            p = self.project
            if not p:
                return
            warn = sum(1 for r in range(len(p.entries)) if self.model.has_warning(r))
            self.statusBar().showMessage(
                f"顯示 {self.proxy.rowCount()}／{len(p.entries)} 條｜手動修改 {len(p.overrides)} 條｜"
                f"替換詞 {sum(1 for x in p.phrases if x[0])} 組｜警告 {warn} 條｜"
                f"來源：{p.backup.name}｜設定：{p.cfg_path.name}")

        # ---- 寫入與還原
        def write(self):
            if not self.project:
                return
            self.project.write(self.project.convert_all())
            QMessageBox.information(self, "完成", f"已寫入繁體到：\n{self.project.d12}")

        def restore(self):
            if not self.project:
                return
            if QMessageBox.question(self, "還原", "把 ali213.d12 還原成簡體原檔？\n（設定與手動修改會保留，之後可再轉回繁體）") == QMessageBox.Yes:
                self.project.restore()
                QMessageBox.information(self, "完成", "已還原成簡體。")

    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec())


def _d12_from_args() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    from .game import find_game, d12_path
    game = find_game()
    if not game:
        raise SystemExit("找不到 Magicka 2，請指定 ali213.d12 的路徑")
    return d12_path(game)


def main_cli():
    run_cli(_d12_from_args())


def main_gui():
    run_gui(_d12_from_args())
