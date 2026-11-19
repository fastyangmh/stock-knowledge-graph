# 開發者指南｜Developer Guide

[文件中心](README.md) · [Architecture](ARCHITECTURE.md) · [資料模型](DATA_MODEL.md) · [前端與預覽](FRONTEND_AND_PREVIEW.md)

## 環境與開始方式

開發目標是 Linux/NAS、Python 3.11（`.python-version`）；`pyproject.toml` 允許 3.10–3.13。Python 套件以 uv 和使用者提交的 `uv.lock` 管理。從專案根目錄執行：

```bash
uv python install 3.11
uv sync --locked --extra dev
uv run --locked python -m local.check
```

首次需自行準備 Git/uv 和可用套件索引。`local.check` 在隔離 SQLite/臨時 JSON 上測試，不下載模型或官方資料，不更新公開 `data/`。報告存於 `local/private/check-report.json`，不提交。

報告記錄 Git Commit／dirty 狀態、實際 OS／架構、Python patch／執行檔、uv／Node 版本、runner、`uv.lock` SHA256，以及每項檢查的命令、退出碼與輸出。版本探測另存 `environment_probes`；工具不存在或探測失敗時，版本／Commit／dirty 記為 `null`，不冒稱乾淨或已知。`--frontend` 缺 Node 仍會失敗。`uv sync` 是檢查前的獨立步驟，須另外保留其命令、輸出與 exit code；報告不宣稱替你執行過同步。

使用者於2026-11-17指定本輪採目前macOS環境驗收；Linux／NAS移轉仍需另驗，不能把macOS結果稱為Linux通過。若暫存目錄含 `/var` → `/private/var` symlink，請用 `TMPDIR=/private/tmp` 避免私有路徑防護拒絕測試產物；保留防護本身。HTTP 整合測試需要允許 loopback socket，權限受限時記錄受阻，依執行環境的正常權限流程重跑。

## 前端與完整本地驗收

```bash
# 需要 Node.js；缺少時明確失敗，不靜默略過
uv run --locked python -m local.check --frontend
# 標準函式庫 runner 可另行交叉檢查
uv run --locked python -m local.check --runner unittest
```

`--frontend` 加入 JavaScript 語法與 Node 內建 runner 的 `js/tests/graph-utils.test.js`。瀏覽器 harness 是選用的 `scripts/browser_smoke.py`，需要環境已有 Playwright、Chromium 和本地經核對的 Cytoscape JS，未更動 lockfile 以自動安裝這些工具。模式、checksum／CDN 驗證界線與指令見[前端文件](FRONTEND_AND_PREVIEW.md)。最新版結果見[2026-11-16整合驗證](VERIFICATION-2026-11-16-FRONTEND.md)，舊測試紀錄不代表新版本自動通過。

## 日常開發流程

AI 協作採用 [Matt Pocock skills](agents/README.md)，專案入口為根目錄 `AGENTS.md`；
技能沿用既有 backlog、術語表與以下驗收規則。

1. 讀取最新分支／Commit，使用獨立開發分支；不覆寫其他人的變更。
2. 先跑基準測試，再修改程式和相對應的回歸測試。
3. 執行 `compileall`、完整 Python 測試；前端變更另測 Node 與適用的瀏覽器情境。
4. 更新 `docs/`，區分實作、離線測試和未完成的真實來源驗收。
5. 檢查 `git diff --check`、變更範圍與私密資料，再提交。不把 SQLite、原始快照、token、模型權重或測試產物提交。

## 重要入口

| 入口 | 工作 |
| --- | --- |
| `local.pipeline init/import` | 建立 schema／匯入正規化資料 |
| `local.pipeline similarity` | 字元 baseline；不是語意模型 |
| `local.pipeline semantic`、`all --semantic` | 本地語意模型與快取 |
| `local.pipeline export/validate` | 匯出／完整檢查圖譜 |
| `local.collect_official`、`local.official_import` | 已審核來源的私有快照與正規化 |
| `local.preview` | 只服務已驗證圖譜及必要資產的本機預覽 |
| `local.publish --dry-run` | 人工發布前檢查；仍需預先確認公開權利 |

執行時加 `uv run --locked python -m`。雙來源參數見[研究股票池](RESEARCH_UNIVERSE.md)，不沿用「聯集一定50檔」的假設。

## 修改規則

- **依賴：** 只有真的變更依賴才更新 lockfile。現在同時存在 optional dev extra 和 dev dependency group；整理時須驗證，不任意覆寫使用者 lockfile。模型 revision 另行固定，套件 lock 不固定遠端權重。
- **資料集：** 先逐資料集核對權利及欄位，再更新 registry、adapter 和離線 fixtures；不把能瀏覽推定成可自動取得或公開。11633 在 `local/official_datasets.json` 登記為 `offline_saved_receipt_only`，由價格比較讀取已保存收據及原件。
- **Schema：** 同步更改 schema/core/export/validation/tests/docs。既存 SQLite 的 migration 與備份需明確設計，不能僅修改 CREATE TABLE。
- **語意算法：** 檢查模型身分、向量 hash、`similarity_state` fingerprint、邊及證據；改變演算法需避免錯用舊邊快取。
- **前端：** 純邏輯放 `js/graph-utils.js`，DOM/請求放 `js/app.js`；測試舊 demo、缺少歸屬、搜尋、空狀態、失敗回復、晚到回應、來源文字與連結安全。
- **發布：** GitHub Pages 仍從 main/root 發布，GitHub CI 不是強制發布閘門；未經人工核准不要更新金融資料。

離線綠燈不代表官方 API、原生產 CDN、最新真實模型、資料授權或 NAS 災難復原已驗收。操作與回復見 [OPERATIONS](OPERATIONS.md)，安全界線見 [SECURITY_AND_LICENSING](SECURITY_AND_LICENSING.md)。

## 歷史與抽檢測試

本地`local.check --frontend`會發現所有`js/tests/*.test.js`，不再只執行單一JS檔。Python新增整包稽核、版本比較、真實loopback歷史HTTP及財務抽檢測試。瀏覽器另可用`python scripts/history_browser_smoke.py --chromium /path/to/chromium --report local/private/history-browser.json`執行純記憶體的合成DOM案例（需另備Playwright／Chromium）；不更動uv.lock或以瀏覽器測試代替正式來源驗收。
