# 01 · 同版本重建真實研究、獨立核對與復原

**Parent:** [M1～M6 對應的原 backlog ID 與完成條件](../../private-research-ready/completion.md) · [規格](../spec.md)

**What to build:** 在固定候選以兩市場真實來源做一次可追溯、可獨立還原的完整私有研究，交付逐項驗收清單與當前限制。

**Blocked by:** M1～M5 必需功能與實證。可先準備索引和核對既有原件，完整結案依賴同候選實測、行情單位獨立抽檢，以及 Linux／NAS 實際獨立復原。

**Status:** ready-for-agent

- [ ] 依固定設定完成擷取、正規化、SQLite、模型、提醒、研究版本、audit、瀏覽器及歷史／事件描述，記錄來源、股票、期間與每階段結果。
- [ ] 核對每個必要 backlog ID 的完成條件、證據及限制。原始快照與參考來源的版本、時間、定義及獨立性均可追查。
- [ ] 復原至新目的地，驗證原始快照、SQLite、ledger、設定、研究引用、歷史、audit 與舊成功版本。macOS 實跑與 Linux／NAS 獨立演練分別記錄。
- [ ] 更新交接、驗證索引、去敏摘要及對應原待辦，附提交與 push 位置。任一必需驗收缺少證據時保留整體未完成並列明恢復條件。

## Comments

2026-11-19 在乾淨開發候選 `ccb4a44` 先唯讀核對既有輸入。驗證前後各重算同一份清單的 924 個檔案，包含公開示範與私有原件，雜湊全部一致。兩市場的正式 `local.bundle_audit` 皆 exit 0，各三個版本與 latest 均 valid。另重讀 09 正式行情抽檢報告，兩市場仍為 `compared_fields=0`、`needs_review=true`。這次檢查保留了六個既有版本的基準；上方同候選完整重建與跨主機復原均待實測。

在候選 checkout 使用鎖定 Python 執行既有私有證據目錄下的 `m6-preflight/check.py <新的私有輸出目錄>`。程式會重新驗證每個初始檔案、實際執行兩次 audit，並保存兩庫、事件檔與最新指標的雜湊。首次產物在 `local/private/m6-preflight/ccb4a44/`。

### 兩市場原件重建與瀏覽器預演

2026-11-19 在 `610e4b3` 使用已封存、當次重核雜湊的公司、月營收、11/17 與 11/18 行情原件。每個市場另核對一份月營收單位證據，共定位 10 個檔案。兩市場各兩檔股票。從空目錄實際執行 16 次 CLI，包含重新正規化、分日匯入行情、以固定模型及兩類提醒建立兩個研究版本、audit、歷史比較與事件報告，全部 exit 0。新行情庫使用本次本地重讀時間，原行情來源及當日首次留存的歷史另存。

固定權重在 CPU 離線使用。第一次研究每市場編碼 2 篇、評估 1 對；第二次各為 0 篇與 0 對。另以 `local.model_check --offline` 通過固定合成語料的四個快取情境。Chromium 以原生 HTTP 讀取兩市場新生成的圖譜、歷史與事件六頁，桌面與手機寬度均通過。兩次 Cytoscape CDN 回應均為 HTTP 200，內容 SHA256 均為 `1bb5340e549511e111b31e5684872c949ad33d40ea5dba0ad8e7d90c62c7b3b9`。重驗後 924 份原始基準檔逐一相符。

以下在產品候選目錄操作，`packet` 為主要工作區的 `local/private/m6-preflight`。使用新的私有目的目錄。

```bash
uv run --locked python "$packet/index-restore-inputs.py" "$packet/restore-inputs-verify.json"
uv run --locked python "$packet/rebuild.py" "$packet/live-new"
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/skg-tools/playwright /private/tmp/skg-browser-venv/bin/python "$packet/browser.py" "$packet/live-new" "$packet/browser-new"
uv run --locked python "$packet/check.py" "$packet/post-new"
```

私有重建摘要在 `live-610e4b3/summary.json`，瀏覽器證據在 `browser-610e4b3/browser.json`。這次預演涵蓋公司、月營收及兩日行情。季報、籌碼、其他文件、維運與還原仍須在最終整合候選一併驗收。09／10 仍為 `needs-info`。

文件提交 `c429270` 沿用同一產品程式，再對上述新建研究執行兩組獨立檢查。

- 以 `financial-reviews.py <新建研究根目錄> <新目的地>` 經四次 `local.financial_review` 核對兩市場各兩檔，4 筆月營收金額完全相符，8 筆增率在已確認的 0.01 個百分點以內。私有輸出為 `financial-c429270/`。
- 以 `check-sqlite-restore.py <新建研究根目錄> <新目的地>` 逐一對兩個市場的價格庫和正規化 ledger 執行 `local.backup create/verify/restore`，12 次命令 exit 0。四個還原庫均通過 SQLite `integrity_check`，來源與還原庫的完整邏輯匯出雜湊各自相符。私有輸出為 `sqlite-c429270/`。此項只驗四個 SQLite，本地整組證據封存與實體異機復原另列 P0-03。
