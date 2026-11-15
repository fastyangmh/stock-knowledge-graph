# Local Pipeline

現行架構、指令與限制見 [專案 README](../README.md)。本目錄使用 uv 管理的 Python 環境，不再把 requirements-embedding.txt 或直接 pip 指令當成主要安裝方式；舊 requirements 檔只為相容保留。

```bash
uv sync --locked --extra dev
uv run --locked python -m local.check
```

本地 CI 不下載模型或金融資料、不發布網站。正式資料採手動 `local.collect_official` → `local.official_import` → `local.pipeline all --semantic ... --output local/private/preview`。

官方資料來源、金額尺度、台灣 50 名單的尚待確認事項見 [DATA_SOURCES](../docs/DATA_SOURCES.md)。發布原則見 [UPDATE_AND_PUBLISH](UPDATE_AND_PUBLISH.md)。
