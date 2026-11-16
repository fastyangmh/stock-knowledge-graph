# 雙來源研究股票池：臺灣50＋009816

[文件中心](README.md) · [資料管線](DATA_PIPELINE.md) · [候選來源核對](SOURCE_REVIEW_2026-11-16.md) · [前端與預覽](FRONTEND_AND_PREVIEW.md)

## 決策與資料定義

第一階段採 **TW50 指數成分股與 009816 ETF 普通股持股的聯集**，不是合成新指數，也不能把 ETF 持股當成 TW50 歷史名單。

- 同一股票只保留一個 `stock_id`，可同時屬兩個來源；單一來源也納入。
- 歸屬為 `tw50_only`、`etf_009816_only`、`both`。沒有欄位的舊圖顯示「未標示」。
- TW50 按正式生效期間查詢並要求 50 檔；ETF 為 `snapshot_date` 當天觀察，**不強制 50 檔、不向前／向後補值**；聯集數量不固定。
- 輸入只接受四碼台股普通股 ID；現金、ETF 本身、衍生品不得冒充公司。基金原始資產明細另存私有快照。
- 不相加兩份權重、不平均來源分數、不推導「共同入選所以看多」。
- 網址是溯源欄位，不是適用的自動下載、歷史保存或公開展示授權證明。

其他文件的「50 檔」與只使用 `--universe` 的範例，仍可作為向後相容的 **TW50-only** 操作；雙來源依本頁操作。

## 私有輸入格式

TW50：`local/private/tw50.csv`

```csv
stock_id,effective_from,effective_to
```

必須有適用權利及真實生效日期；起訖日均含當日，空截止日依原規則處理。同股票區間不能重疊。以 `--universe-source` 指定該名單來源 HTTPS URL。

009816：`local/private/009816-holdings.csv`

```csv
stock_id,snapshot_date,source_url
```

`stock_id` 為 `TW:四碼`，`snapshot_date` 是持股日期而不是下載日期。同日只能有一份來源、不得重複股票；可保存多日紀錄，但只讀取指定日期，不沿用昨日。缺當日資料就停止。

## 私有匯入操作

**先取得兩份有權使用的名單及當日官方財務快照。** `YYYY-MM-DD` 與 `https://YOUR-REVIEWED-SOURCE/...` 為需替換的參數，不能原樣當成實際資料使用。

```bash
uv run --locked python -m local.official_import \
  --universe local/private/tw50.csv \
  --etf-holdings local/private/009816-holdings.csv \
  --universe-source 'https://YOUR-REVIEWED-SOURCE/tw50' \
  --as-of YYYY-MM-DD --output local/private/normalized-combined.json

uv run --locked python -m local.pipeline all --semantic \
  --input local/private/normalized-combined.json \
  --db local/private/combined-preview.db \
  --universe local/private/tw50.csv \
  --etf-holdings local/private/009816-holdings.csv \
  --universe-source 'https://YOUR-REVIEWED-SOURCE/tw50' \
  --as-of YYYY-MM-DD --lookback-days 90 --lifecycle \
  --output local/private/combined-preview

uv run --locked python -m local.pipeline validate --output local/private/combined-preview
uv run --locked python -m local.preview --data-dir local/private/combined-preview --port 8765
```

`local.run_after_close` 轉送 ETF 參數，仍拒絕 `--publish`，未安裝排程。`pipeline` 雙來源參數可用於 `import`、`all`、`export`；必須同時給 `--universe`、`--as-of`、`--universe-source`。舊操作保留相容性。

## 保存與展示

正規化輸入 `metadata.research_universe` 保存來源計數、交集／聯集、選定日期及輸入檔 SHA256。股票節點的 `graph_nodes.properties_json` 保存：

| 欄位 | 意義 |
| --- | --- |
| `universe_ids` | `TW50`／`ETF:009816`，可同時存在 |
| `universe_group` | 三種來源歸屬之一 |
| `universe_as_of` | 這次研究股票池選定日期 |
| `universe_memberships` | 各來源 URL、index_constituent／etf_holding、有效期間或快照日 |

**本次已完成前端股票池篩選、代號／名稱搜尋與來源詳情。** exporter 把經核對的歸屬摘要加入 manifest，使前端不必載入全部 graph.json。索引的來源計數只反映本次匯出主股票，不能拿來認定官方完整性或兩份名單今天仍相同。

圖內仍可出現研究池外的關聯鄰居；股票池參數限制主圖，不改寫資料庫所有文件的相似度範圍。建議用獨立 `combined-preview.db`。SQLite 節點屬性更新不是完整歷史版本資料庫；仍須保存原始名單快照。聯集不取消原有 lifecycle／配對預算限制。

## 權利與驗證界線

沒有加入新名單爬蟲、下載真實成分股、啟用券商 API 或發布真實資料；兩份名單的使用範圍仍各自確認。第三方網站只是候選來源，不自動變成核准下載來源。

原合併功能曾單獨驗證 28 項測試（8 子案例）；本次已重跑合併後的完整 Python 測試，並測試真實 SQLite→70 檔虛構聯集→manifest→graph 匯出，另有 Node 邏輯、本機 HTTP 及受限環境瀏覽器測試。**這不是正式名單或交易資料驗收。** 環境、數量及限制見 [本次驗證紀錄](VERIFICATION-2026-11-16-FRONTEND.md)。

相關測試：[雙來源](../local/tests/test_combined_universe.py)、[索引／歸屬契約](../local/tests/test_view_metadata.py)、[私有預覽](../local/tests/test_preview.py)。
