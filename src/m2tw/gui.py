"""安裝程式視窗（tkinter，打包後不需要另外安裝任何東西）。

勾選＝套用，取消勾選＝還原該項目；按「套用」讓遊戲狀態和勾選一致。
畫面是一張 Canvas：背景插畫與面板由 art.py 依螢幕縮放比例繪製，文字與按鈕疊在上面。
"""

import threading
import tkinter as tk
import traceback
import webbrowser
from pathlib import Path
from tkinter import filedialog

from PIL import ImageTk

from . import ASSETS_DIR, __version__, art, patches
from .game import check_ali213, find_game, game_running, is_game_dir

# 「一起來翻譯」按鈕的連結：Crowdin 翻譯專案
CONTRIBUTE_URL = "https://crowdin.com/project/magicka2-tw"
ALI213_HINT = "請先安裝遊俠網（ALI213）的《魔法對抗2》簡體中文漢化補丁，再執行本程式。"
FONT = "Microsoft JhengHei UI"
W, H = 760, 700  # 邏輯尺寸，實際像素會乘上螢幕縮放比例

C_TEXT = "#f6e7c1"
C_DIM = "#b8b0c8"
C_GOLD = "#e9b44c"
C_OK = "#7ee2a8"
C_ERR = "#ff8a7a"

OPTIONS = [
    ("text", "繁體中文文本", "約 2700 條台灣繁體中文，含全新潤飾的劇情對話"),
    ("logo", "中文標題標誌", "標題畫面換成「巫師2」中文標誌"),
    ("cpu", "CPU 使用率優化", "修正多核心 CPU 空轉吃滿的問題，會修改 Magicka2.exe"),
]


class ImageButton:
    def __init__(self, app, x, y, w, h, text, kind, command, size=12):
        self.app, self.command, self.enabled = app, command, True
        c, s = app.canvas, app.s
        self.imgs = {st: ImageTk.PhotoImage(art.button(app.px(w), app.px(h), kind, st))
                     for st in ("normal", "hover", "disabled")}
        self.tag = f"btn{id(self)}"
        self.img = c.create_image(app.px(x), app.px(y), image=self.imgs["normal"], anchor="nw", tags=self.tag)
        self.label = c.create_text(app.px(x + w / 2), app.px(y + h / 2 + 1), text=text, fill=C_TEXT,
                                   font=(FONT, size, "bold"), tags=self.tag)
        c.tag_bind(self.tag, "<Enter>", lambda e: self._show("hover"))
        c.tag_bind(self.tag, "<Leave>", lambda e: self._show("normal"))
        c.tag_bind(self.tag, "<Button-1>", lambda e: self.enabled and self.command())

    def _show(self, st):
        if self.enabled:
            self.app.canvas.itemconfigure(self.img, image=self.imgs[st])
            self.app.canvas.configure(cursor="hand2" if st == "hover" else "")

    def set_enabled(self, on: bool):
        self.enabled = on
        self.app.canvas.itemconfigure(self.img, image=self.imgs["normal" if on else "disabled"])
        self.app.canvas.itemconfigure(self.label, fill=C_TEXT if on else "#8a8494")


class Option:
    def __init__(self, app, key, name, desc, y):
        self.app, self.key = app, key
        self.var = tk.BooleanVar(value=key != "cpu")
        c, px = app.canvas, app.px
        size = px(24)
        self.imgs = {(on, hv): ImageTk.PhotoImage(art.checkbox(size, on, hv)) for on in (0, 1) for hv in (0, 1)}
        tag = f"opt{key}"
        self.box = c.create_image(px(66), px(y + 4), image=self.imgs[(1, 0)], anchor="nw", tags=tag)
        c.create_text(px(104), px(y + 2), text=name, fill=C_TEXT, anchor="nw", font=(FONT, 13, "bold"), tags=tag)
        c.create_text(px(104), px(y + 29), text=desc, fill=C_DIM, anchor="nw", font=(FONT, 10), tags=tag)
        c.create_rectangle(px(56), px(y - 4), px(704), px(y + 54), outline="", fill="", tags=tag)
        self.hover = False
        c.tag_bind(tag, "<Enter>", lambda e: self._hover(True))
        c.tag_bind(tag, "<Leave>", lambda e: self._hover(False))
        c.tag_bind(tag, "<Button-1>", lambda e: self.toggle())
        self.var.trace_add("write", lambda *_: self.draw())
        self.draw()

    def _hover(self, on):
        self.hover = on
        self.app.canvas.configure(cursor="hand2" if on else "")
        self.draw()

    def toggle(self):
        if self.app.busy:
            return
        self.var.set(not self.var.get())

    def draw(self):
        self.app.canvas.itemconfigure(self.box, image=self.imgs[(int(self.var.get()), int(self.hover))])


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Magicka 2 台灣繁體中文化 v{__version__}")
        self.resizable(False, False)
        try:
            self.iconbitmap(default=str(ASSETS_DIR / "icon.ico"))
        except tk.TclError:
            pass
        self.s = max(1.0, self.winfo_fpixels("1i") / 96)
        self.busy = False
        px = self.px

        self.canvas = c = tk.Canvas(self, width=px(W), height=px(H), highlightthickness=0, bd=0, bg="#0c0a18")
        c.pack()
        panels = [(40, 236, 720, 322), (40, 334, 720, 538), (40, 616, 720, 684)]
        self.bg = ImageTk.PhotoImage(art.background(px(W), px(H), [tuple(px(v) for v in p) for p in panels], self.s))
        c.create_image(0, 0, image=self.bg, anchor="nw")
        self.logo = ImageTk.PhotoImage(art.logo(px(430)))
        c.create_image(px(W / 2), px(104), image=self.logo)
        c.create_text(px(W / 2), px(199), text="台灣繁體中文化補丁", fill=C_GOLD, font=(FONT, 14, "bold"))
        c.create_text(px(W / 2), px(222), text=f"v{__version__}  ·  基於遊俠網 ALI213 簡體中文漢化改作",
                      fill=C_DIM, font=(FONT, 9))

        # 遊戲位置
        c.create_text(px(60), px(246), text="遊戲位置", fill=C_GOLD, anchor="nw", font=(FONT, 11, "bold"))
        self.path = tk.StringVar(value=str(find_game() or ""))
        entry = tk.Entry(self, textvariable=self.path, bg="#120f22", fg=C_TEXT, insertbackground=C_GOLD,
                         relief="flat", font=(FONT, 10), highlightthickness=1,
                         highlightbackground="#6e5426", highlightcolor=C_GOLD)
        c.create_window(px(60), px(270), window=entry, anchor="nw", width=px(520), height=px(28))
        self.browse_btn = ImageButton(self, 592, 269, 108, 30, "瀏覽", "secondary", self.browse, size=10)
        self.status = c.create_text(px(60), px(309), text="", fill=C_DIM, anchor="w", font=(FONT, 9),
                                    width=px(640))

        # 選項
        c.create_text(px(60), px(344), text="安裝項目", fill=C_GOLD, anchor="nw", font=(FONT, 11, "bold"))
        c.create_text(px(700), px(347), text="取消勾選後按「套用」，即可還原該項目", fill=C_DIM, anchor="ne",
                      font=(FONT, 9))
        self.options = {key: Option(self, key, name, desc, 372 + i * 54)
                        for i, (key, name, desc) in enumerate(OPTIONS)}

        # 按鈕
        self.restore_btn = ImageButton(self, 40, 552, 180, 48, "全部還原", "secondary", lambda: self.run(True))
        self.apply_btn = ImageButton(self, 500, 552, 220, 48, "套用", "primary", self.run, size=15)
        self.contrib_btn = ImageButton(self, 286, 556, 188, 40, "一起來翻譯 ↗", "secondary",
                                       lambda: webbrowser.open(CONTRIBUTE_URL), size=10)

        # 訊息
        self.log = tk.Text(self, bg="#0c0a18", fg=C_TEXT, relief="flat", font=(FONT, 9), wrap="word",
                           highlightthickness=0, state="disabled", padx=4, pady=2)
        c.create_window(px(54), px(624), window=self.log, anchor="nw", width=px(652), height=px(52))

        self.path.trace_add("write", lambda *_: self.refresh())
        self.refresh()
        self.say("準備就緒。勾選要套用的項目，再按「套用」。")

    def px(self, v) -> int:
        return round(v * self.s)

    # ---- 狀態
    def game(self) -> Path:
        return Path(self.path.get().strip().strip('"'))

    def set_status(self, text, color):
        self.canvas.itemconfigure(self.status, text=text, fill=color)

    def refresh(self):
        game = self.game()
        if not self.path.get() or not is_game_dir(game):
            self.set_status("找不到遊戲，請按「瀏覽…」選擇 Magicka 2 的資料夾。", C_ERR)
            self.apply_btn.set_enabled(False)
            return
        problems = check_ali213(game)
        if problems:
            self.set_status(ALI213_HINT + "（" + "；".join(problems) + "）", C_ERR)
            self.apply_btn.set_enabled(False)
            return
        bk = patches.Backups(game)
        self.options["text"].var.set(True)
        self.options["logo"].var.set(patches.logo_applied(bk) or not bk.state)
        self.options["cpu"].var.set(patches.cpu_applied(bk))
        now = [n for n, ok in (("繁中文本", patches.text_applied(game)), ("中文標題", patches.logo_applied(bk)),
                               ("CPU 優化", patches.cpu_applied(bk))) if ok]
        self.set_status("已偵測到遊俠漢化補丁" + (f"  ·  目前已套用：{'、'.join(now)}" if now else ""), C_OK)
        self.apply_btn.set_enabled(True)

    def browse(self):
        d = filedialog.askdirectory(title="選擇 Magicka 2 資料夾", initialdir=self.path.get() or None)
        if d:
            self.path.set(d)

    def say(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ---- 套用／還原
    def run(self, restore_all=False):
        if self.busy:
            return
        if game_running():
            self.say("請先關閉遊戲再操作。")
            return
        want = {k: False for k in self.options} if restore_all else {k: o.var.get() for k, o in self.options.items()}
        self.busy = True
        for b in (self.apply_btn, self.restore_btn, self.browse_btn):
            b.set_enabled(False)  # 「一起來翻譯」不受影響
        self.say("全部還原中……" if restore_all else "施法中……")
        threading.Thread(target=self.work, args=(self.game(), want), daemon=True).start()

    def work(self, game: Path, want: dict):
        say = lambda m: self.after(0, self.say, m)
        try:
            bk = patches.Backups(game)
            if want["text"]:
                say(patches.apply_text(game))
            elif patches.restore_text(game):
                say("已還原成遊俠簡體中文文本")
            if want["logo"]:
                patches.apply_logo(bk)
                say("已套用中文標題標誌")
            elif patches.logo_applied(bk):
                patches.restore_logo(bk)
                say("已還原原版標題標誌")
            if want["cpu"]:
                patches.apply_cpu(bk)
                say("已套用 CPU 使用率優化")
            elif patches.cpu_applied(bk):
                patches.restore_cpu(bk)
                say("已還原原版 Magicka2.exe")
            say("完成！啟動遊戲即可。")
        except Exception as ex:
            say(f"發生錯誤：{ex}")
            say(traceback.format_exc(limit=2))
        finally:
            self.after(0, self.finish)

    def finish(self):
        self.busy = False
        for b in (self.restore_btn, self.browse_btn):
            b.set_enabled(True)
        self.refresh()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 高解析度螢幕不模糊
    except Exception:
        pass
    App().mainloop()


if __name__ == "__main__":
    main()
