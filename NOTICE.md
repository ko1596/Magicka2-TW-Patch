# 聲明與致謝

## 遊俠網（ALI213）

本專案以 **遊俠網（ALI213）漢化組** 製作的《魔法對抗2》簡體中文漢化補丁為基礎改作：

- 在遊戲中顯示中文的技術（修改過的 `PhysX3_x86.dll`、`ali213.dll`、字型圖集 `ali213.d02`）完全來自遊俠補丁。本專案沒有修改，也不散布這些檔案。
- 本專案的繁體中文譯文，最初是由遊俠的簡體中文譯文經 OpenCC 轉換而來，之後才逐條修改、重新翻譯。尚未手動修改的條目，仍是遊俠譯文的轉換結果。
- `translation/zh_tw.json` 不包含遊俠的簡體原文，只保存每條原文的雜湊值，用來偵測原文是否變動。

本專案使用的遊俠補丁取自 josida 在 Steam 分享的指南（https://steamcommunity.com/sharedfiles/filedetails/?id=2800301065），一併致謝。

感謝遊俠漢化組讓這款遊戲有了中文，沒有他們的成果就沒有這個專案。若遊俠網對本專案有任何疑慮，請透過 Issues 聯絡，我們會配合處理。

## 遊戲本身

《Magicka 2》© Paradox Interactive AB，由 Pieces Interactive 開發。本專案為非官方的粉絲翻譯，與 Paradox Interactive、Pieces Interactive 無任何關聯：

- 不散布任何遊戲檔案。標題標誌與 CPU 優化都是在玩家自己的電腦上，修改玩家自己合法擁有的遊戲檔案。
- 譯文僅供已購買遊戲的玩家使用，免費提供，禁止任何商業用途。
- `translation/keys.json` 是字串 ID 與遊戲內部名稱的對照，僅供翻譯對照之用。

## 授權

- `src/`、`scripts/` 的程式碼：MIT License（見 [LICENSE](LICENSE)）。
- `translation/` 的譯文：由於部分內容衍生自遊俠的翻譯與遊戲原文，無法以自由授權釋出。僅限非商業的個人使用與改作；改作時請保留本聲明，並註明遊俠網與本專案。
- `assets/logo_zh.png`：中文標題標誌，與譯文相同條件。

## 使用到的開源軟體

- [OpenCC](https://github.com/BYVoid/OpenCC)（opencc-python-reimplemented）：簡繁轉換
- [Pillow](https://python-pillow.org/)：圖片處理
- [PySide6](https://doc.qt.io/qtforpython/)：翻譯編輯器
- [PyInstaller](https://pyinstaller.org/)：打包安裝程式
