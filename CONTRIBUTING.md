# 參與翻譯

謝謝你願意幫忙！這個專案的目標是讓台灣玩家玩起來自然、好笑。

## 在 Crowdin 上翻譯（推薦）

**👉 https://crowdin.com/project/magicka2-tw**

不用懂程式，用瀏覽器就能翻譯：

1. 用 Crowdin 帳號登入（可以直接用 GitHub、Google 帳號登入）。
2. 進入專案，選「繁體中文」，就能看到所有字串。
3. 每條字串下方的說明會告訴你這句的**分類**（劇情第幾章、法袍、神器、設定……）和遊戲內部名稱，翻譯前先看一下。
4. 覺得哪句翻得不好，直接提出新的譯法，或對別人的建議投票。

審核通過的譯文會自動同步回這個 repo，下一個版本就會出現在遊戲裡。

## 回報翻譯問題

到 [Issues](../../issues) 開一則回報，附上：

1. 遊戲截圖（Steam 內建截圖 F12 最方便；一般截圖工具在全螢幕模式下常常是全黑的）。
2. 你覺得怪的地方，以及建議的譯法（如果有的話）。
3. 如果知道英文原文更好。

## 翻譯原則

請先看 [用語表](translation/GLOSSARY.md)，Crowdin 專案裡也有同一份詞彙表，翻到這些詞時會自動提示。最重要的幾點：

- **先看懂笑點再翻。** Magicka 的對白到處是梗：諺語亂拼、雙關、電影台詞、反諷。字面正確但不好笑，就等於沒翻。
- **看上下文。** 內部名稱會告訴你這句是誰說的、在哪一章（例如 `joa_3_1_4_outpost1_humanSP` 是第 3 章、前哨站、人類士兵、單人版）。結尾 `SP`／`MP` 是同一句台詞的單人版和多人版，兩版要一致，只差在「你／你們」。
- **格式代碼一個都不能少**（`[P=…]`、`[c]`、`#…;`、`[K=…]`），`%s`／`%d` 的順序也不能變。
- **不要用「獨」字**，遊戲裡會顯示壞掉。
- **用台灣用語**，標點用全形，引號用「」。

## 維護者：同步 Crowdin

Crowdin 透過 GitHub 整合讀寫 `translation/i18n/`（設定在 `crowdin.yml`）：

- `translation/i18n/en.json`：英文原文（Chrome JSON 格式，`description` 是給譯者看的說明）。
- `translation/i18n/zh-TW.json`：繁體中文譯文。

```sh
uv run m2tw-crowdin export   # 由 translation/zh_tw.json 產生 i18n 檔案，推上 GitHub 後 Crowdin 會讀取
uv run m2tw-crowdin import   # 合併 Crowdin 的 Pull Request 之後，把 i18n/zh-TW.json 寫回 zh_tw.json
uv run m2tw-convert          # 套用到遊戲裡測試
```

`import` 會自動略過格式代碼和原文不一致的譯文。這兩個指令都需要電腦上有遊戲和遊俠補丁。

`translation/crowdin_glossary.csv` 是由用語表產生的詞彙表，可以在 Crowdin 專案的 Glossary 匯入。

## 用翻譯編輯器修改

```sh
uv sync --extra editor
uv run m2tw-editor
```

可以依分類篩選、搜尋英文、譯文或內部名稱（例如搜 `vlad` 會列出弗拉德的所有台詞）。改完按「套用修改」，再按「轉換並寫入」，就能直接進遊戲看效果。

## 程式開發

請看 [技術說明](docs/TECHNICAL.md)。
