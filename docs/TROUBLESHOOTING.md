# 常見問題與排錯｜Troubleshooting

[文件中心](README.md) · [使用者手冊](USER_MANUAL.md) · [開發者指南](DEVELOPER_GUIDE.md)

## 網站使用問題

| 現象 | 檢查方式 |
| --- | --- |
| 網頁顯示「載入失敗」 | 檢查 `data/manifest.json` 是否存在、是否為合法 JSON、股票 `path` 對應檔案是否存在 |
| 下拉選單為空／圖上沒有節點 | 檢查 manifest 的 `stocks` 與各股 `graph.json`；不代表官方尚未產生資料 |
| 點選「語意相似」沒有線 | 該股票圖可能沒有 `semantic_similarity` 關係；切到「全部」再檢查 |
| 本地雙擊 HTML 無法讀取 JSON | 使用 `python -m http.server 8000`，改以 `http://localhost:8000` 開啟，不用 `file://` |
| 網站資料仍是示範 | 正常：目前尚未發布真實金融圖譜；先確認資料權利及正式驗收 |
| 只看到少量節點 | `--lifecycle` 會裁剪公開子圖；SQLite 內可能仍保存更多歷史資料 |

## Linux／uv 問題

| 現象 | 處理方向 |
| --- | --- |
| 找不到 `uv` | 先確認已安裝 uv 並在 PATH，或請維護者安裝 |
| `uv sync --locked --extra dev` 失敗 | 查看 uv 與 Python 版本、lockfile 是否與 `pyproject.toml` 一致、套件索引是否可用；勿擅自刪除 lockfile |
| `pytest` 找不到套件 | 從 Repository 根目錄執行 `uv sync --locked --extra dev`，再執行 `uv run --locked python -m local.check` |
| 出現 Hugging Face 匿名下載提示 | 通常是限速提醒，不代表失敗；首次載入真實模型可能需要網路 |
| SOCKS 代理回報缺 `socksio` | 屬代理環境相依套件問題；先核對代理配置，再於該虛擬環境按需安裝，不要將 token 放入指令或日誌 |
| `compileall` 或測試失敗 | 先記下 Commit、第一個 traceback、測試名稱及 Python 版本，避免在同一時間發佈 |

## 官方金融資料／台灣50

| 現象 | 處理方向 |
| --- | --- |
| 官方 CSV 下載 403／HTML／欄位變動 | **停止**，核對官方資料集及權限；不繞過存取控制、不以範例資料補缺 |
| `No reviewed enabled datasets` | 檢查 `local/official_datasets.json` 的核准來源；不要任意啟用未核對的網站端點 |
| `Expected 50 active constituents` | 有權的日期有效名單缺漏或多筆，先核對生效日、重疊區間與權利來源 |
| 快照日期和 `--as-of` 不一致 | 官方匯入要求同日快照，不能把今天下載的資料假裝為歷史當日的已知資訊 |
| `Company coverage incomplete` 或 `Revenue coverage incomplete` | 查看當日 50 檔是否都有對應紀錄；不以零替代缺值 |
| 月營收單位是 `source_reported` | 尚未核對金額倍率，不能當成已確認的元／千元或進行跨來源比較 |

## 圖譜、驗證與發布

- 相似度候選超過 `--max-pairs`：資料量超過安全預算；可在研究需要合理的情況下調整 `--lookback-days`，但不能因此宣稱完整歷史都被比較。
- `validate` 回報重複節點、缺失端點或 manifest 不一致：不要發布，檢查匯出結果與上游輸入。
- 匯出器拒絕覆寫目錄：可能含非預期檔案／symlink，**不要直接刪除重要內容**；改用乾淨的私有預覽目錄。
- `local.run_after_close --publish` 失敗：**預期的安全行為**，盤後入口只允許私有預覽。
- `local.publish` 拒絕 staged 變更、無關檔案或分支不一致：先使用 `git status` 查清工作區；不要 force push 或忽略檢查。
- GitHub Pages 版本未更新：先確認手動公開資料 Commit 是否成功推送與 Pages 是否完成從 `main / root` 部署；既有 GitHub CI 不構成強制發布關卡。

## 回報問題時請提供

```text
Repository Commit:
作業系統 / Python / uv 版本:
執行的命令（刪掉所有 token 與敏感路徑）:
第一個完整錯誤訊息:
使用的是 synthetic demo / 私有授權資料？:
是否已修改 data/ 或推送 Git？:
```

可附上 `local/private/check-report.json` 中**已刪除敏感內容**的測試摘要；切勿在公開 Issue 上傳私有來源快照、完整金融原始資料或憑證。
