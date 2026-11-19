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

### 混合財報庫整組復原預演

2026-11-19 在 M5 候選 `88e20e8`，以 `63e0f49` 實測時保存的七家公司研究庫及 26 個歷史版本執行 `local.portable_backup create`、`verify`、`restore`，並分別對原目錄與新目錄執行 `local.bundle_audit`。五次命令 exit 0。封存 327 個檔案、618 條引用、21 個正規化輸入。還原後 26 個版本均 valid，最新指標一致，SQLite integrity_check 回覆 ok。重算來源 ledger 及 55 個具名輸入檔案的 SHA256 均相符。

這次使用兩市場公司與月營收、17 個季報快照及兩份人工現金流筆記。財報獨立參考的涵蓋程度沿用 P1-03 的逐欄紀錄。原始資料與私有重演程式位於 `local/private/m6-preflight/portfolio-restore.py`，同層 `portable-financial-88e20e8-b/summary.json`、`commands.json` 和 `selected-sources.json` 可追查實際輸入與命令。本機同一裝置的新目錄已驗，完整多來源研究與異機復原待驗。

### 兩市場共用研究庫、行情庫與版本目錄

M3 候選 `c7db79c` 上的私有 `m6-preflight/full-portfolio.py` 從前述財報研究庫的一致副本開始，將 7 份籌碼、公告、產業與新聞輸入登錄在同一研究庫。從封存公司及月營收重新正規化，依原 SHA256 從兩市場各匯入兩天行情至同一行情庫，執行四次含固定模型與兩類提醒的研究。整個目錄共 37 個有效版本，兩市場的歷史比較、事件報告均 exit 0。第二日上市保有 32 筆財務事實及 4 筆行情，上櫃保有 22 筆財務、78 筆籌碼及 4 筆行情。兩市場各自的第一版實際編碼 9／11 篇，第二版皆為 0。原財報研究目錄逐檔雜湊一致。事件報告覆蓋 37 個版本，其中 33 個未帶提醒、2 個首次事件、2 次重複。這是本次重讀行情的取得時間；未回填原始研究的首次保存時間。

同一候選以 Chromium 在 localhost 測試兩組股票，各自讀取圖譜、37 版歷史及事件，原 CDN、瀏覽器原生 fetch、桌機與手機寬度均通過。為發現跨里程碑相容問題，另在隔離目錄組合該候選與 M5 `88e20e8` 的封存程式，從同一組研究建立 420 檔封存、驗證 829 條引用、還原後再稽核全部 37 版。這次是兩個固定程式樹的整合預演，正式單一候選需重跑。私有位置為 `m6-preflight/{portfolio-c7db79c,browser-portfolio-c7db79c,portable-source-diagnostic}/`。完整現金流 PDF、來源使用權、行情獨立抽檢及異機復原仍依原票追蹤。

合併後在 `2b03884` 已用重做的各家族輸入及新版籌碼收據重驗，詳[開發分支驗證紀錄](../../../docs/VERIFICATION-2026-11-19-M3-SOURCE-REVIEW.md)。`trade_date` 選擇本次研究的行情截止日，`known_at` 使用本次 11/19 重讀時點。因而選擇 11/17 行情時，研究保有截至 11/19 已知的 11/18 籌碼。若問題是「11/17 當時能看到什麼」，須另用已保存的 11/17 版本與其原始截止。
