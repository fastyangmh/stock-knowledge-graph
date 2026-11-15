# 開發者指南｜Developer Guide

[文件中心](README.md) · [Architecture](ARCHITECTURE.md) · [資料模型](DATA_MODEL.md)

## 1. 開發環境

專案使用 Python、SQLite 與 `uv`；開發目標環境為 **Linux/NAS、Python 3.11**（`.python-version`），`pyproject.toml` 允許 Python 3.10–3.13。先安裝 Git 與 uv，然後在專案根目錄：

```bash
git clone https://github.com/fastyangmh/stock-knowledge-graph.git
cd stock-knowledge-graph
uv python install 3.11
uv sync --locked --extra dev
uv run --locked python -m local.check
```

`local.check` 依序執行語法檢查、pytest、隔離 SQLite→JSON smoke test 和完整 JSON 驗證，報告寫在 **不追蹤** 的 `local/private/check-report.json`。它不下載模型或官方金融資料，不修改公開 `data/`。

`pyproject.toml` 目前同時含有 `project.optional-dependencies.dev` 與 `dependency-groups.dev`；不要任意新增不同版本的重複測試套件規格，未來應在可重現環境中整理並更新 lockfile。

## 2. 日常開發迴圈

```bash
git status
uv run --locked python -m compileall -q local
uv run --locked pytest -q
uv run --locked python -m local.check
git diff --check
```

推薦在獨立分支修改程式。每次變更都應增加對應測試，並核對本地輸出是否落在 `local/private/` 或臨時目錄。開發指令預設可能帶有示範資料路徑；**不要把示範資料直接發布成真實金融資料**。

### 修改依賴

只有依賴真的有變化時才執行 `uv lock`，檢查 `pyproject.toml` 與 `uv.lock` 的 diff，再以 `uv sync --locked --extra dev` 和完整測試驗證。鎖定 Python 套件不等於鎖定 Hugging Face 遠端模型權重；正式重現時另指定 `--revision`（模型 commit SHA）。

## 3. 重要程式入口

| 入口 | 用途 |
| --- | --- |
| `python -m local.pipeline init` | 初始化 SQLite schema |
| `python -m local.pipeline import --input ...` | 匯入正規化 JSON |
| `python -m local.pipeline similarity` | 字元 bigram lexical baseline，不是 AI |
| `python -m local.pipeline semantic` | 本地 Sentence Transformers 語意關聯 |
| `python -m local.pipeline all` | 匯入、關聯計算、匯出 |
| `python -m local.pipeline validate --output ...` | 驗證既有匯出 JSON |
| `python -m local.check` | 本地離線驗收 |
| `python -m local.collect_official` | 從核准資料來源下載至私有快照 |
| `python -m local.official_import` | 官方快照 → 私有正規化 JSON |
| `python -m local.publish --dry-run` | 發布前查看候選變更；需已驗證公開資料 |

所有指令實際執行時，前面可加 `uv run --locked`。詳細步驟請看 [資料處理管線](DATA_PIPELINE.md)與[維運手冊](OPERATIONS.md)。

## 4. 修改模組的建議流程

**新增官方資料集：** 先核對資料集級授權 → 更新 `local/official_datasets.json` → 修改 `source_registry.py` 白名單與 adapter → 加入無網路 fixture 測試 → 用正式端點人工小範圍驗證 → 記錄 [資料來源](DATA_SOURCES.md)。

**新增節點／關聯：** 調整 `schema.sql`／`core.py` → 定義穩定 ID 與時間欄位 → 更新 `export_json.py`、`lifecycle.py` 與 `validate_release.py` → 加入圖完整性測試 → 更新 [資料模型](DATA_MODEL.md)。

**修改語意算法：** 對比模型身分、向量快取、`similarity_state` fingerprint 與邊證據，確保不同演算法版本不能錯誤重用舊邊；增加無變更／單文件變更／股票關係變更／異常向量／回復測試。

**修改前端：** 驗證網站仍能載入既有示範 JSON、切換股票、關聯類型與節點詳情；目前沒有自動化瀏覽器測試，需要人工驗證。

## 5. 測試範圍與提交流程

單元測試位於 [`local/tests/`](../local/tests/)；大部分使用虛構 fixture、fake encoder、臨時 SQLite 或本機 bare Git repo。不要讓單元測試自動對外下載模型、呼叫官方 API 或推送 `main`。最新一次已記錄的離線驗證結果見 [驗證紀錄](VERIFICATION-2026-11-15.md)，其「通過」**不代表**真實資料與網站正式驗收。

提交前核對：變更與測試一致、文檔更新、不包含 private data 或 token、不以未授權名單填補資料缺口。若涉及公開發布，遵守 [安全規範](SECURITY_AND_LICENSING.md)與[部署維運](OPERATIONS.md)。
