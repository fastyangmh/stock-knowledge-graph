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

## 前端與完整本地驗收

```bash
# 需要 Node.js；缺少時明確失敗，不靜默略過
uv run --locked python -m local.check --frontend
# 標準函式庫 runner 可另行交叉檢查
uv run --locked python -m local.check --runner unittest
```

`--frontend` 加入 JavaScript 語法與 Node 內建 runner 的 `js/tests/graph-utils.test.js`。瀏覽器 harness 是選用的 `scripts/browser_smoke.py`，需要環境已有 Playwright、Chromium 和本地經核對的 Cytoscape JS，未更動 lockfile 以自動安裝這些工具。模式、checksum／CDN 驗證界線與指令見[前端文件](FRONTEND_AND_PREVIEW.md)。最新版結果見[2026-11-16整合驗證](VERIFICATION-2026-11-16-FRONTEND.md)，舊測試紀錄不代表新版本自動通過。

## 日常開發流程

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
- **資料集：** 先逐資料集核對權利及欄位，再更新 registry、adapter 和離線 fixtures；不把能瀏覽推定成可自動取得或公開。
- **Schema：** 同步更改 schema/core/export/validation/tests/docs。既存 SQLite 的 migration 與備份需明確設計，不能僅修改 CREATE TABLE。
- **語意算法：** 檢查模型身分、向量 hash、`similarity_state` fingerprint、邊及證據；改變演算法需避免錯用舊邊快取。
- **前端：** 純邏輯放 `js/graph-utils.js`，DOM/請求放 `js/app.js`；測試舊 demo、缺少歸屬、搜尋、空狀態、失敗回復、晚到回應、來源文字與連結安全。
- **發布：** GitHub Pages 仍從 main/root 發布，GitHub CI 不是強制發布閘門；未經人工核准不要更新金融資料。

離線綠燈不代表官方 API、原生產 CDN、最新真實模型、資料授權或 NAS 災難復原已驗收。操作與回復見 [OPERATIONS](OPERATIONS.md)，安全界線見 [SECURITY_AND_LICENSING](SECURITY_AND_LICENSING.md)。
