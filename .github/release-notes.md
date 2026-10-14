## 安裝

1. 先安裝遊俠網（ALI213）的《魔法對抗2》簡體中文漢化補丁，確認遊戲能顯示簡體中文。
2. 下載下方的 **Magicka2-TW-Patch.exe**。
3. 關閉遊戲，執行 `Magicka2-TW-Patch.exe`，勾選要套用的項目，按「套用」。

詳細說明請看 [README](https://github.com/{{REPO}}#readme)。

## 瀏覽器或 Windows 跳出警告？

這個安裝程式沒有付費的數位簽章，剛發布的版本下載的人還不多，所以 Edge 會顯示「不常下載」，Windows 會顯示「Windows 已保護您的電腦」。這是正常現象，不是病毒：

- **Edge**：在下載提示按「⋯」→「保留」→「顯示更多」→「仍要保留」。
- **Windows**：執行時按「其他資訊」→「仍要執行」。

## 確認檔案沒有被竄改

這個 exe 是由 GitHub Actions 依照本 repo 公開的原始碼自動打包的，不是在任何人的電腦上製作的。

**SHA-256**：`{{SHA256}}`

在 PowerShell 比對：

```powershell
Get-FileHash .\Magicka2-TW-Patch.exe -Algorithm SHA256
```

用 [GitHub CLI](https://cli.github.com/) 驗證建置來源證明（確認這個 exe 確實出自本 repo 的 GitHub Actions）：

```sh
gh attestation verify Magicka2-TW-Patch.exe -R {{REPO}}
```
