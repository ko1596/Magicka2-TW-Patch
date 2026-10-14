"""安裝程式視窗（tkinter，打包後不需要另外安裝任何東西）。

勾選＝套用，取消勾選＝還原該項目；按「套用」讓遊戲狀態和勾選一致。
"""

import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, ttk

from . import __version__, patches
from .game import check_ali213, find_game, game_running, is_game_dir

ALI213_HINT = "請先安裝遊俠網（ALI213）的《魔法對抗2》簡體中文漢化補丁，再執行本程式。"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Magicka 2 台灣繁體中文化 v{__version__}")
        self.resizable(False, False)
        self.columnconfigure(0, weight=1)
        pad = {"padx": 12, "pady": 4}

        ttk.Label(self, text="Magicka 2 台灣繁體中文化", font=("Microsoft JhengHei UI", 15, "bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 0))
        ttk.Label(self, text="以遊俠網（ALI213）簡體中文漢化為基礎，轉換並重新潤飾為台灣繁體中文。",
                  foreground="#555").grid(row=1, column=0, sticky="w", **pad)

        box = ttk.LabelFrame(self, text="遊戲位置")
        box.grid(row=2, column=0, sticky="ew", **pad)
        box.columnconfigure(0, weight=1)
        self.path = tk.StringVar(value=str(find_game() or ""))
        ttk.Entry(box, textvariable=self.path, width=58).grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        ttk.Button(box, text="瀏覽…", command=self.browse).grid(row=0, column=1, padx=(0, 8))
        self.status = ttk.Label(box, text="", wraplength=470)
        self.status.grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))

        opts = ttk.LabelFrame(self, text="要套用的項目（取消勾選＝還原該項目）")
        opts.grid(row=3, column=0, sticky="ew", **pad)
        self.v_text = tk.BooleanVar(value=True)
        self.v_logo = tk.BooleanVar(value=True)
        self.v_cpu = tk.BooleanVar(value=False)
        items = [
            (self.v_text, "繁體中文文本", "把遊俠的簡體漢化換成台灣繁體中文（約 2700 條，含全新潤飾的劇情對話）。"),
            (self.v_logo, "中文標題標誌", "標題畫面的 MAGICKA 2 換成中文「巫師2」標誌。"),
            (self.v_cpu, "CPU 使用率優化", "修正遊戲在多核心 CPU 上空轉吃滿 CPU 的問題（會修改 Magicka2.exe）。"),
        ]
        for i, (var, name, desc) in enumerate(items):
            ttk.Checkbutton(opts, text=name, variable=var).grid(row=i * 2, column=0, sticky="w", padx=8, pady=(6, 0))
            ttk.Label(opts, text=desc, foreground="#555", wraplength=470).grid(row=i * 2 + 1, column=0, sticky="w",
                                                                              padx=28, pady=(0, 4))

        btns = ttk.Frame(self)
        btns.grid(row=4, column=0, sticky="ew", **pad)
        self.restore_btn = ttk.Button(btns, text="全部還原", command=lambda: self.run(restore_all=True))
        self.restore_btn.pack(side="left")
        self.apply_btn = ttk.Button(btns, text="套用", command=self.run)
        self.apply_btn.pack(side="right")

        self.log = tk.Text(self, height=8, width=70, state="disabled", relief="flat", background="#f4f4f4")
        self.log.grid(row=5, column=0, sticky="ew", padx=12, pady=(4, 12))

        self.path.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    # ---- 狀態
    def game(self) -> Path:
        return Path(self.path.get().strip().strip('"'))

    def refresh(self):
        game = self.game()
        if not self.path.get() or not is_game_dir(game):
            self.status.configure(text="找不到遊戲，請按「瀏覽…」選擇 Magicka 2 的資料夾。", foreground="#b3261e")
            self.apply_btn.state(["disabled"])
            return
        problems = check_ali213(game)
        if problems:
            self.status.configure(text=ALI213_HINT + "\n" + "；".join(problems), foreground="#b3261e")
            self.apply_btn.state(["disabled"])
            return
        bk = patches.Backups(game)
        self.v_text.set(True)
        self.v_logo.set(patches.logo_applied(bk) or not bk.state)
        self.v_cpu.set(patches.cpu_applied(bk))
        now = [n for n, ok in (("繁中文本", patches.text_applied(game)), ("中文標題", patches.logo_applied(bk)),
                               ("CPU 優化", patches.cpu_applied(bk))) if ok]
        self.status.configure(text="已偵測到遊俠漢化補丁。" + (f"目前已套用：{'、'.join(now)}" if now else ""),
                              foreground="#1b6e3a")
        self.apply_btn.state(["!disabled"])

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
        if game_running():
            self.say("請先關閉遊戲再操作。")
            return
        want = {"text": False, "logo": False, "cpu": False} if restore_all else \
            {"text": self.v_text.get(), "logo": self.v_logo.get(), "cpu": self.v_cpu.get()}
        for b in (self.apply_btn, self.restore_btn):
            b.state(["disabled"])
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
        self.restore_btn.state(["!disabled"])
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
