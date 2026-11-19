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

### 私有容量、增長與封存規劃

以維護者選定的私有目錄為範圍，每次將報告存於範圍外的新檔案。例如盤點保存在 `local/private/collection` 的一批研究資料：

```bash
uv run --locked python -m local.storage_inventory \
  --root local/private/collection --class raw=downloaded \
  --budget total=10737418240 --budget raw=2147483648 \
  --output local/private/inventories/001.json

uv run --locked python -m local.storage_inventory \
  --root local/private/collection --class raw=downloaded \
  --budget total=10737418240 --budget raw=2147483648 \
  --previous local/private/inventories/001.json \
  --output local/private/inventories/002.json
```

- `files` 列出相對路徑。一般檔案的 `size_bytes` 是邏輯長度，`counted_bytes` 可逐檔加總。Hard link 依排序走訪的第一個名稱歸類、只計一次，其他名稱標記 `same_file_as`。Symlink 與特殊檔僅列型別，計入 0 bytes。目錄項目、壓縮、稀疏檔、APFS clone 等實體占用需由檔案系統工具另查。
- `--class` 可重複，採最深的相對路徑優先，適用整個子樹。預設先依備份、研究版本、原始快照和模型的已知目錄名稱歸類，再辨識 DB 副檔名與 WAL／SHM／journal，其餘列 `unknown`。可用類別為 `database`、`raw`、`bundle`、`backup`、`model`、`unknown`。`--budget` 接受上述類別或 `total`，以 bytes 為單位。`budget_exceeded` 列出限額、觀測值、差額與計量路徑。
- `growth` 比較同根目錄、同目錄身分及分類規則的兩次觀測，列出新增、移除、大小差與計量差。權限錯誤保存在 `scan_errors`，可觀測的部分仍會輸出，exit 2。兩次觀測中任一次不完整時，總增長為 null，讀不到的子樹標 `unobserved`。完整掃描即使超出配額仍 exit 0。
- `archive_plan.bundle_copies` 選出已辨識研究版本的整個目錄，列出從 latest、事件等文件可解析的引用者。`bundle_requirements` 保存報告宣告的來源、資料集與語意模型 revision。`references` 按包含引用的檔案列 SHA256、已知契約路徑及解析狀態，`content_paths` 連回同範圍內實際讀到相符 bytes 的檔案。相同內容可能保存在多處。只有路徑、無法在範圍內匹配、存在於 ledger 內、超出讀取預算的引用可維持 `unresolved`。JSON 解析失敗或未讀內容列於 `uninspected`。計畫一律保留原件，實際整組封存、還原及 audit 見 [M5-02](../.scratch/m5-private-operations/issues/02-restore.md)。
- 私有報告含路徑與來源雜湊。預設最多讀取 256 MiB 內容，可用 `--content-budget BYTES` 調整，0 適用僅盤點容量。單份 JSON 解析上限 8 MiB。最多走訪 100,000 個項目、深度 128、100,000 筆不同引用及 100,000 個版本連結，報告上限 64 MiB。超出硬限額 exit 2，報告以完整寫入後的獨佔建檔交付。需要一致的跨檔時間點時，應選擇停止寫入的資料或檔案系統快照。

## 私有研究整組備份與還原

`local.portable_backup` 以一個研究版本目錄和配對的 ledger 為單位。備份前保留各版本實際使用的正規化輸入原檔。正式來源的收據、CSV、單位核對檔及其引用文件須維持收據所寫的相對目錄結構。若各市場使用不同 ledger，分別建立封存。以下範例的私有路徑需換成實際位置。

```bash
uv run --locked python -m local.portable_backup create \
  --ledger local/private/history.db --runs local/private/research-runs \
  --input local/private/normalized.json --raw local/private/official \
  --prices-db local/private/prices.db --price-snapshots local/private/prices \
  --event local/private/events/report.json --config local/private/event-policy.json \
  --output local/private/backups/portfolio-001

uv run --locked python -m local.portable_backup verify \
  --bundle local/private/backups/portfolio-001

uv run --locked python -m local.portable_backup restore \
  --bundle local/private/backups/portfolio-001 --destination local/private/restored-001

uv run --locked python -m local.bundle_audit --root local/private/restored-001/runs
```

- 每個 `--input`、`--event`、`--config` 指定一個檔案，`--raw` 可指定檔案或目錄，各旗標皆可重複。同類輸入的末段名稱須唯一。有行情時同時提供行情庫和對應 CSV 目錄。設定隨版本報告保留，另有私有設定檔時可明示封存。只選本次用途所需的原件和設定。
- `manifest.json` 記錄相對目錄、逐檔路徑、類別、大小與 SHA256，以及研究版本所需來源和模型 revision。引用清單將 ledger、原始快照、收據、單位核對與事件對回封存內的檔案。模型權重不在這個介面的資料類別內。既有單一 SQLite 工作仍用 `local.backup`。
- 建立時使用 SQLite online backup 取得已提交的 WAL。不可變研究版本內的 `graph.db` 按原始 bytes 複製，維持舊報告的 hash。程式持有研究及所選來源目錄的協作鎖，檢查建檔前後的目錄、檔案身分、大小、時間戳，以及 SQLite WAL／journal。來源正在更新而導致拒絕時，待寫入者完成後再執行。
- 還原先檢查完整目錄與檔案清單，再於目的地同一檔案系統暫存、重播 ledger、按歷史 cutoff 重讀行情原件、稽核 graph 和重算列入的事件報告。目的檔案系統須支援排他目錄 rename。遇到檔案缺漏、引用不符、連結或既有目的地時會回傳非零。收到成功退出後再使用新目錄的 `runs/latest.json`。強制終止可能留有隱藏暫存目錄，舊成功版本仍可讀。
- 2026-11-19 的真實驗證使用 macOS 同一 APFS 裝置的不同目錄。移轉後須在 Linux／NAS 和獨立媒體上重跑建立、離線驗證與全新還原。實際停電後的耐久性需在目標設備另驗。[P0-03 演練紀錄](../.scratch/m5-private-operations/issues/02-restore.md)
