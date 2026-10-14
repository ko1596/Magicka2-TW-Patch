"""與 Crowdin 交換譯文（Chrome JSON 格式：每條有 message 與 description，description 會成為譯者看到的說明）。

  uv run m2tw-crowdin export   由 translation/zh_tw.json 產生 translation/i18n/en.json 與 zh-TW.json
  uv run m2tw-crowdin import   把 Crowdin 上的譯文（i18n/zh-TW.json）寫回 translation/zh_tw.json

流程：export 後推上 GitHub → Crowdin 讀取 en.json（原文）與 zh-TW.json（現有譯文）→
譯者在 Crowdin 翻譯 → Crowdin 開 Pull Request 更新 zh-TW.json → 合併後在本機執行 import 與 m2tw-convert。

需要電腦上有遊戲與遊俠補丁（英文原文與自動轉換的譯文都從遊俠字典來）。
"""

import json
import re
import sys
from pathlib import Path

from . import TRANSLATION_DIR
from .translate import Project, category, unspace

I18N = TRANSLATION_DIR / "i18n"
CODE_HINT = "格式代碼（[P=…] [c] #…; [K=…] %s %d）不可增減，%s／%d 順序要和英文一致；不可使用「獨」字。"


def key_for(p: Project, e) -> str:
    """Crowdin 的字串代號：有遊戲內部名稱用內部名稱，沒有就用 ID。"""
    return p.key_of(e) or "id_" + e.eng[3:11]


def describe(p: Project, e) -> str:
    key = p.key_of(e)
    parts = [category(key, e.remark), f"ID {e.eng[3:11]}"]
    if key:
        parts.append(key)
        if key.endswith("SP"):
            parts.append("單人版（對一位玩家說）")
        elif key.endswith("MP"):
            parts.append("多人版（對多位玩家說）")
    if "[P=" in e.remark or "%" in e.remark or "#" in e.remark or "[K=" in e.remark:
        parts.append(CODE_HINT)
    return "｜".join(parts)


def _load_project() -> Project:
    from .game import d12_path, find_game
    game = find_game()
    if not game:
        raise SystemExit("找不到 Magicka 2")
    return Project(d12_path(game))


def export():
    p = _load_project()
    results = p.convert_all()
    en, zh = {}, {}
    for e, text in zip(p.entries, results):
        k = key_for(p, e)
        en[k] = {"message": e.remark.replace("\r", ""), "description": describe(p, e)}
        zh[k] = {"message": text.replace("\r", "")}
    I18N.mkdir(exist_ok=True)
    for name, data in (("en.json", en), ("zh-TW.json", zh)):
        (I18N / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"已匯出 {len(en)} 條到 {I18N}")


def import_():
    p = _load_project()
    zh = json.loads((I18N / "zh-TW.json").read_text("utf-8"))
    cur = dict(zip((e.eng for e in p.entries), p.convert_all()))
    code = re.compile(r"\[P=[^\]]*\]|\[[KI]=[^\]]+\]|\[/?c\]|#[A-Za-z0-9_]+;|%[-0-9.]*[sdif]")
    changed, rejected = 0, []
    for e in p.entries:
        item = zh.get(key_for(p, e))
        if not item:
            continue
        text = item["message"].replace("\r", "").strip()
        if not text or text == cur[e.eng]:
            continue
        if sorted(code.findall(text)) != sorted(code.findall(e.remark)) and \
                sorted(code.findall(text)) != sorted(code.findall(cur[e.eng])):
            rejected.append((key_for(p, e), "格式代碼和原文不一致"))
            continue
        if re.findall(r"%[-0-9.]*[sdif]", text) != re.findall(r"%[-0-9.]*[sdif]", e.remark):
            rejected.append((key_for(p, e), "%s／%d 順序和原文不一致"))
            continue
        p.set_override(e, unspace(text))
        changed += 1
    p.save_config()
    print(f"已匯入 {changed} 條譯文")
    for k, why in rejected:
        print(f"  略過 {k}：{why}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "export":
        export()
    elif cmd == "import":
        import_()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
