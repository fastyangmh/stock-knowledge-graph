# Local Pipeline｜本地 Python 資料處理

[返回主 README](../README.md) · [完整文件中心](../docs/README.md)

本目錄保存 SQLite、官方資料快照處理、語意向量、圖譜匯出與單元測試。主要運作環境是 Linux/NAS，使用 uv 管理 Python；`local/private/` 為私有輸入／報告目錄，不得發布。

```bash
uv sync --locked --extra dev
uv run --locked python -m local.check
```

- [開發者指南](../docs/DEVELOPER_GUIDE.md)：測試、開發流程、依賴管理。
- [資料處理管線](../docs/DATA_PIPELINE.md)：離線示範與核准資料的私有預覽。
- [資料模型](../docs/DATA_MODEL.md)：SQLite schema／圖譜 JSON。
- [手動更新與發布](../docs/OPERATIONS.md)：部署、人工核准、安全回復。
- [資料來源／授權](../docs/DATA_SOURCES.md)：官方資料集狀態與限制。
- [最新離線測試紀錄](../docs/VERIFICATION-2026-11-15.md)。

`local/requirements-embedding.txt` 是相容性遺留檔；正式安裝流程以 `pyproject.toml`／`uv.lock` 為主。**真實台灣50名單授權、官方來源全量線上驗證及每日排程仍未完成。**
