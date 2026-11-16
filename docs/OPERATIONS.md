# 部署與維運｜Operations Runbook

[文件中心](README.md) · [使用手冊](USER_MANUAL.md) · [資料管線](DATA_PIPELINE.md)

> **目前部署決策：** GitHub Pages = `Deploy from a branch`／`main`／根目錄；Linux/NAS **手動執行，不安裝排程**。GitHub Actions 測試不會阻止另一個直接 push 到 `main` 的行為。

目前另有 [不依賴指數名單的私有研究入口](PRIVATE_RESEARCH.md)。下方正式雙來源發布條件仍適用，但不再阻塞自選股票的私有處理。

## 1. 每次開始前

確認專案更新、依賴與本地測試：

```bash
git pull --ff-only
uv sync --locked --extra dev
uv run --locked python -m local.check
git status --short
```

- 本地測試報告：`local/private/check-report.json`（勿提交）。
- 若 `git status` 有不相關檔案，先自行檢查，不要讓發布工具代替你處理 Git 衝突。
- 保持真實金融來源快照、SQLite、模型快取、權利證明與 API 憑證在私有位置。

## 2. 盤後手動流程

**尚未具備的先決條件：** 可適用於本專案的台灣50日期有效名單、實際官方端點線上驗證、資料單位／署名核對。這些條件未滿足時，僅能跑虛構示範或授權範圍內的私人測試。

正式條件滿足後：

1. 確認台灣交易日；檢查資料集當日是否真的出表。**18:30 是可調整的人工門檻，不是資料到齊保證**。
2. 逐來源下載並驗證私有快照：`uv run --locked python -m local.collect_official`。
3. 將當日快照與當日有權名單交由 `local.official_import` 正規化。
4. 使用 `local.pipeline all --semantic --lifecycle ... --output local/private/preview` 生成**私有** JSON，並執行 `local.pipeline validate --output local/private/preview`。
5. 人工檢查股票覆蓋、來源與授權、公告／可得時間、單位、相似度與連線證據、圖檔大小。
6. 只有在**另行確認可公開**後，才準備公開 `data/` 的完整有效輸出，再走下節手動發布。

完整參數示例見 [資料處理管線](DATA_PIPELINE.md)。`local.run_after_close` 是**私有預覽入口**，其 `--publish` 明確拒絕。沒有 cron／systemd timer；請勿自行視為已啟用每日更新。

## 3. 人工發布（需額外確認）

在符合資料使用權利與完整驗證的前提下，才以受控匯出方式更新公開 `data/`（不是把未審查的私有文件直接複製上傳）。先檢視：

```bash
git diff -- data/
uv run --locked python -m local.validate_release
uv run --locked python -m local.publish --dry-run
```

人工檢查 dry-run 列出的 **僅有 `data/manifest.json` 和各股票 `graph.json`**，確認沒有 API key、私有文件、錯誤來源或不可散布資料後，才執行：

```bash
uv run --locked python -m local.publish
```

此工具要求在 `main`，先 `git fetch origin main` 並確認本地分支與遠端一致，拒絕既有 staged 變更、無關檔案和不完整 JSON；不 force push。它**不負責取得授權或替研究員判斷資料品質**。

## 4. 發布後檢查

- 確認網站 https://fastyangmh.github.io/stock-knowledge-graph/ 可載入，股票下拉選單與關聯篩選正確。
- 檢查頁面顯示的 JSON 版本與圖譜節點／邊數量，並開啟不同股票確認沒有 404。
- 檢查公開頁面是否充分揭露資料來源、署名、資料時間及限制（目前來源署名 UI 尚須正式驗收）。
- 留存發布 Commit、快照 SHA256、人工核准與錯誤紀錄，方便稽核。

## 5. 失敗、回復與備份

- **來源下載失敗：** 保留上一批成功的 manifest 與快照；不要以失敗或舊資料假裝當日成功。
- **SQLite／計算失敗：** 保存錯誤與私有測試檔；先釐清原因，不要自動更新公開資料。
- **JSON 驗證失敗：** 停止發布；重新產生或修復，勿手動繞過 `validate_release`。
- **Git Push 失敗：** 本地資料 Commit 可能已存在。先檢查 `git log`、`git status`、分支狀態；勿 force push。
- **已發布資料錯誤：** 以被核准的舊 JSON 版本或經審查的 Git revert 進行人工回復；回復後再驗證網站，不直接刪 SQLite。
- **備份：** 正式使用前定義 SQLite 一致性備份、私有原始快照的離線／異地備份、空間與留存週期，並測試還原。程式的檔案 rename／鎖定不等於 NAS 斷電原子性或完整災難復原。

## 6. 安全邊界

本專案沒有後端部署、沒有常駐任務服務，GitHub Pages 只讀取公開 JSON。**請勿把 `local/private/`、`*.db`、Token、未授權的新聞全文與模型私有檔案加入 Git**。Repository 為 public，任何被提交的內容可能被他人看到。

相關：[既有維運註記](../local/UPDATE_AND_PUBLISH.md) · [安全／授權](SECURITY_AND_LICENSING.md) · [常見問題](TROUBLESHOOTING.md)。

## 研究版本與備份入口

現行不等待名單的流程見 [PRIVATE_RESEARCH](PRIVATE_RESEARCH.md)。`local.research` 只建立私有不可變 bundle，不改公開 `data/`；最新成功版本由普通 `latest.json` 指向。`local.backup create/verify/restore` 提供手動 SQLite 備份與防覆寫還原，原始 CSV 必須另外保存。這些入口不會啟用排程、購買資料或執行 Git Push。

## 本機版本容量與完整性巡檢

`local.bundle_audit`預設只檢查50個版本／合計256MiB，超額明確停止；可人工調整預算，不會自動刪除舊版本。毀損bundle及暫存殘留列入報告。`local.research_archive`只以loopback提供已驗證圖譜和摘要，保留同機使用者可存取的警告。沒有新增排程或遠端服務。操作與exit code見[研究歷史](RESEARCH_HISTORY.md)。
