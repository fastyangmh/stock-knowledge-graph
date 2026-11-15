# 手動更新與發布準則

**維持 GitHub Pages：Deploy from a branch / main / root。** 不改成 Actions 部署，不啟用 cron/systemd timer。以下指令應在專案根目錄使用 uv 執行；在官方資料與名單驗證前，不發布真實資料。

## 開發驗收

```bash
uv sync --locked --extra dev
uv run --locked python -m local.check
```

本地檢查包含語法、單元測試、隔離資料庫、完整 JSON 驗證。現有 GitHub Actions 不是本專案的發布閘門，不依賴其結果驗收。

## 真實資料的私有預覽

先依 [來源文件](../docs/DATA_SOURCES.md) 準備有權使用、含有效期間的台灣 50 名單；取得當日官方快照後，以 `local.official_import` 產生私有 normalized.json。再使用 `local.pipeline all --semantic`、`--universe`、`--lifecycle` 與 `--output local/private/preview`。完整範例見 [資料處理管線](../docs/DATA_PIPELINE.md)；維運準則見 [部署與維運](../docs/OPERATIONS.md)。

`local.run_after_close` 是手動盤後入口，需交易日曆與名單；只生成私有預覽，`--publish` 仍明確拒絕。不能用缺乏名單或舊資料的空輸入冒充成功更新。

## 後續人工發布

只有在人工確認署名、公開使用權、資料新鮮度、金額尺度、完整股票覆蓋及內容無私密資訊後，才能另行匯出至 `data/`。先檢視 `git diff -- data/`，再執行：

```bash
uv run --locked python -m local.publish --dry-run
# 人工審查且同意公開後才執行下一個指令：
uv run --locked python -m local.publish
```

Dry-run 不修改 index、工作區或 commit，但會 fetch origin 以確認分支狀態。預先 staged 檔案、其他未提交工作、分支分歧、無關檔案或不完整 JSON 都會停止發布；不 force push、不自動處理衝突。

本地 SQLite、原始資料快照、模型權重與密鑰禁止提交。分支式 Pages 不等待獨立 CI，因此其他直接推送仍能繞過本地防護；不能宣稱伺服器端已強制驗證。

## 復原範圍

JSON exporter 會在換目錄失敗時嘗試恢復前一版本，不會任意刪除既存的 `.previous` 目錄。這不是斷電或跨 SQLite／檔案系統的完整交易保證。Git push 失敗保留本地資料 commit，先檢查後人工重試；不要刪資料庫或 force push。
