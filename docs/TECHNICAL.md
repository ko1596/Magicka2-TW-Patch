# 技術說明

給想維護、改進這個專案的人。開發過程與決策背景請看 [DEVLOG.md](DEVLOG.md)。

## 專案結構

```
src/m2tw/
  translate.py   字典解析、簡轉繁、斷行、寫回 ali213.d12；也包含翻譯編輯器（PySide6）
  patches.py     三項修改（繁中文本、中文標題、CPU 優化）的套用／還原與備份管理
  game.py        尋找 Steam 裡的遊戲、檢查遊俠補丁是否生效
  gui.py         安裝程式視窗（tkinter Canvas）
  art.py         安裝程式的美術：背景合成、面板、勾選框、按鈕（依螢幕縮放比例繪製）
  crowdin.py     與 Crowdin 交換譯文（m2tw-crowdin export／import）
translation/
  zh_tw.json     本專案的譯文與轉換設定（見下方），也是安裝程式用的資料
  keys.json      字串 ID → 遊戲內部名稱
  i18n/          給 Crowdin 的 Chrome JSON（en.json 原文、zh-TW.json 譯文），由 m2tw-crowdin 產生
  crowdin_glossary.csv  由 GLOSSARY.md 產生、可匯入 Crowdin 的詞彙表
assets/          打包進安裝程式的素材：logo_zh.png、icon.ico、installer_bg.jpg
art/             原始美術（AI 生成），由 scripts/make_assets.py 轉成 assets/
scripts/
  build_exe.py   打包安裝程式
  make_assets.py 由 art/ 產生圖示與背景
```

## 開發環境

需要 [uv](https://docs.astral.sh/uv/)。

```sh
uv sync --extra editor --group dev   # 安裝全部（含編輯器、打包工具）
uv run m2tw-installer                # 執行安裝程式（不打包）
uv run m2tw-editor                   # 翻譯編輯器
uv run m2tw-convert                  # 不開視窗，直接重新轉換並寫入遊戲
uv run m2tw-crowdin export|import    # 與 Crowdin 交換譯文（見 CONTRIBUTING.md）
uv run --group dev scripts/build_exe.py   # 打包成 dist/Magicka2-TW-Patch.exe
```

`m2tw-editor`、`m2tw-convert` 沒給路徑時會自動找 Steam 裡的遊戲。執行前必須已安裝遊俠補丁。

## 遊俠補丁的運作方式

| 檔案 | 作用 |
|---|---|
| `engine/PhysX3_x86.dll` | 遊戲必載的物理引擎 DLL，被插入一段程式碼空間（RVA 0x2910B0，入口在 0x101F1624 的 jmp），用來 `LoadLibraryA(".\ali213\ali213.dll")` |
| `engine/ali213/ali213.dll` | 攔截 D3D11 `CreateTexture2D`，把中文字形換進遊戲的字型貼圖 |
| `engine/ali213/ali213.d02` | 字型圖集，GBK 字集順序，每格 42 px、每列 190 字 |
| `engine/ali213/ali213.d12` | 字典（UTF-8，CRLF） |

Steam「驗證遊戲檔案」會把 `PhysX3_x86.dll` 換回原版，漢化就失效。`game.py` 用原版的 SHA-1（`c769a1f4…`）偵測這個情況。

### d12 字典格式

```
xfhsm_res_No.00000123        ← 流水號，必須連續
xfhsm_res_ENG_Start
id=6E237DFFh                 ← 字串 ID
xfhsm_res_ENG_End
xfhsm_res_CHI_Start
公 羊                        ← 譯文：每個全形字後面都要加一個空格
xfhsm_res_CHI_End
xfhsm_res_Remark00_Start
Ram                          ← 英文原文（註解用）
xfhsm_res_Remark00_End
```

- `ali213.dll` 依 ID 排序做二分搜尋，所以整份必須**依 ID 由小到大排列**，新增條目要插在正確位置並重新編號。
- 全形字後面的空格是給引擎斷行用的，同時也負責撐開字距（拿掉會讓字疊在一起）。
- 字串 ID ＝ 遊戲內部名稱的 MurmurHash64A（seed 0）取高 32 位元。

### 格式代碼

| 代碼 | 意思 |
|---|---|
| `[P=0.5]` | 停頓 0.5 秒（逐字顯示時） |
| `[c]…[/c]` | 強調色 |
| `#joa_char_lok;` | 插入另一個字串（角色名、地名等） |
| `[K=fire]` | 按鍵圖示 |
| `[I=hud_element_cold,1]` | 圖示 |
| `%s`、`%d` | 程式填入的值，**順序必須和英文一致**，否則顯示錯亂甚至當掉 |

## translation/zh_tw.json

```jsonc
{
  "mode": "s2twp",            // OpenCC 模式
  "phrases": [["計程車兵", "…"]],   // OpenCC 轉完後的詞彙替換（長詞優先）
  "overrides": {               // 逐條手動譯文（優先於自動轉換）
    "id=6E237DFFh": {"src": "3f2a…", "text": "公羊"}
  },
  "additions": {               // 遊俠字典沒有、本專案新增的字串 {ID: 英文原文}
    "id=…": "Checking…"
  },
  "wrap": {"default": 40, "narrow": 26, "narrow_ids": [...], "nospace_ids": []}
}
```

- `overrides.*.src` 是遊俠簡體原文的 SHA-1 前 12 碼。本專案**不保存遊俠的簡體原文**，只存指紋。遊俠更新字典、原文改變時，工具會警告「這條手動譯文可能過時」。
- 每條最終譯文的產生順序：有 `overrides` 用手動譯文；沒有就用 OpenCC 轉換遊俠原文，再套用 `phrases`。
- 寫入時自動：斷行（`narrow_ids` 用 26 字，其餘 40 字，平均分配、斷在標點後）、英文字母和中文字之間補半形空格、全形字後補引擎空格。

## 中文標題標誌

標誌是 660×168 的 BGRA DDS 貼圖，在兩個資源包裡各有兩份：

| 資源包 | DDS 檔頭位移（解壓後） |
|---|---|
| `data/3b1335d6d0425964`（開機載入，標題畫面讀這份） | 0x25584C、0x301E1C |
| `data/ec181385e7000cf1` | 0xA326C3C、0xBA368FC |

資源包格式：12 位元組檔頭，接著是一連串「4 位元組長度＋zlib 區塊」，每塊解壓後 64 KB。只重新壓縮被改到的區塊。

## CPU 使用率優化

Bitsquid 引擎依邏輯處理器數量開工作執行緒。執行緒沒工作時，會在 `Magicka2.exe+0x2FB705` 開始的迴圈裡用 `pause` 輪詢，累積空等時間到門檻（`[0x7DDB38]` 的 double，0.001 秒）才 `WaitForSingleObject(INFINITE)`。派工端（`+0x2FB47B`）也用同一個門檻判斷要不要叫醒執行緒。

修改：把兩處 `comisd xmm0, [0x7DDB38]` 的位址改成 `[0x7E24A0]`（`.rdata` 裡一個被當 double 讀取的 0.0），讓執行緒沒事就立刻休眠。兩處必須一致，否則睡著的執行緒不會被叫醒。exe 沒有重定位表，載入位址固定是 0x400000，可以直接改絕對位址。

## 備份與還原

- 遊戲原檔第一次修改前備份到 `<遊戲>/m2tw_backup/`，`state.json` 記錄每個檔案最後一次寫入的 SHA-1。
- 每次套用都**從備份重新產生**，重複套用不會疊加。
- 如果目前的檔案既不是備份、也不是我們上次寫入的版本（Steam 更新或驗證過檔案），就把它當成新的原檔重新備份。
- 還原時只還原「仍是我們寫入版本」的檔案，不會覆蓋 Steam 換過的新檔。
- 文本：簡體字典備份在 `engine/ali213/ali213.d12.chs`。如果偵測到 `ali213.d12` 又變回簡體（重裝過遊俠補丁），就以新的為準。

## 已知限制

見 [DEVLOG.md 的「還沒解決的」](DEVLOG.md#14-還沒解決的)。
