# 雙來源研究股票池：臺灣50＋009816

[文件中心](README.md) · [資料管線](DATA_PIPELINE.md) · [候選來源核對](SOURCE_REVIEW_2026-11-16.md)

## 決策與範圍

2026-11-16 使用者選擇「結合兩者」。第一階段研究目標改為 **TW50 指數成分股與 009816 ETF 普通股持股的聯集**，不是把兩個指數混成一個新指數，也不將 ETF 持股當作 TW50 歷史名單。

- 只在其中一份名單出現的股票也納入；兩份皆有的股票只保留一個 `stock_id`。
- 分別標示 `tw50_only`、`etf_009816_only`、`both`。
- 指數成分股依正式生效期間查詢；ETF 持股只視為 `snapshot_date` 當天的觀察，不向前／向後補值。缺少當日資料則停止。
- TW50 名單仍驗證恰好 50 檔；ETF 持股不強制 50 檔；聯集數量依當日重疊而定，不再要求總數為 50。
- 本階段只接受四碼台股普通股識別碼；現金、ETF本身、衍生品等不可冒充公司節點。基金原始資產明細應另存私有快照。
- 不相加兩份權重、不平均兩個來源的分數、不新增「共同入選所以看多」等投資訊號。

既有文件中「50 檔覆蓋」及只傳 `--universe` 的範例仍可作為向後相容的 **TW50-only** 操作；雙來源請依本頁操作。兩種資料定義差異與官方參考連結保留於[候選來源核對](SOURCE_REVIEW_2026-11-16.md)。

## 輸入檔案（私有，不提供真實成分股範例）

### TW50

`local/private/tw50.csv` 仍使用既有格式：

```csv
stock_id,effective_from,effective_to
```

每列需真實、具有適用權利的股票 ID 與生效起迄日期；空白截止日沿用原有規則。用 `--universe-source` 指定這份名單的來源 HTTPS URL。

### 009816

`local/private/009816-holdings.csv`：

```csv
stock_id,snapshot_date,source_url
```

`stock_id` 格式為 `TW:四碼`，`snapshot_date` 是實際持股資料日期，不是下載日期；同一日採同一來源快照，禁止重複股票。CSV 可保存多個歷史日期，但只讀取 `--as-of` 的那一天。來源 URL 是追溯資料，**不是授權證明**。

## 手動私有匯入

先有兩份有權使用的名單和對應當日官方財務快照，再執行。以下 `YYYY-MM-DD` 與 `https://YOUR-REVIEWED-SOURCE/...` 是需替換的參數，不是真實資料：

```bash
uv run --locked python -m local.official_import \
  --universe local/private/tw50.csv \
  --etf-holdings local/private/009816-holdings.csv \
  --universe-source 'https://YOUR-REVIEWED-SOURCE/tw50' \
  --as-of YYYY-MM-DD \
  --output local/private/normalized-combined.json

uv run --locked python -m local.pipeline all --semantic \
  --input local/private/normalized-combined.json \
  --db local/private/combined-preview.db \
  --universe local/private/tw50.csv \
  --etf-holdings local/private/009816-holdings.csv \
  --universe-source 'https://YOUR-REVIEWED-SOURCE/tw50' \
  --as-of YYYY-MM-DD \
  --lookback-days 90 --lifecycle \
  --output local/private/combined-preview

uv run --locked python -m local.pipeline validate \
  --output local/private/combined-preview
```

`local.run_after_close` 也會轉送 `--etf-holdings` 與 `--universe-source`；仍拒絕 `--publish`，未安裝排程。`pipeline` 的雙來源參數可用於 `import`、`all`、`export`；指定時必須同時給 `--universe`、`--as-of`、`--universe-source`。只用舊參數則維持原行為。

## 保留的資料

正規化 payload 的 `metadata.research_universe` 包含來源各自數量、交集／聯集數量、選定日期及兩個輸入檔案的 SHA256。股票節點新增：

| 欄位 | 意義 |
| --- | --- |
| `universe_ids` | 例如 `TW50`／`ETF:009816`，可同時存在 |
| `universe_group` | `tw50_only`、`etf_009816_only` 或 `both` |
| `universe_as_of` | 這次研究股票池的選定日期 |
| `universe_memberships` | 各自的來源 URL、`index_constituent`／`etf_holding` 類型、生效日或快照日 |

上述欄位保存在 SQLite `graph_nodes.properties_json`，沿用 exporter 的節點屬性輸出路徑。既有詳情面板可列出 JSON 屬性；**本次沒有新增專用的前端股票池切換／篩選介面**。使用者應保存原始名單快照；目前的資料庫屬性會更新，不是完整歷史成分股版本資料庫。

股票池限制匯出的主股票，沒有改寫既有全部文件的相似度範圍；舊研究資料庫可能包含其他關聯鄰居。建議使用獨立 `combined-preview.db`。匯出邊數與節點限制沿用 lifecycle，不因聯集擴大而移除原有防護。

## 權利與驗證界線

此功能只讀取使用者本地提供的名單，**沒有新增來源爬蟲、取得授權、下載真實名單、更新公開 `data/` 或改變 Pages 設定**。先前的第三方 ETF 網站仍是候選參考，未自動加入核准下載來源。TW50 與 ETF 持股的自動取得、歷史保存和公開展示權利仍各自確認。

本次在助手的 Linux／Python 3.13.5／pytest 9.0.2 本地環境執行新增測試：**28 passed（另有 8 subtests），unittest 28 tests OK，語法檢查通過**。測試用虛構 50 檔指數股票、30 檔 ETF 股票，交集 10 檔、聯集 70 檔；不是實際持股數量。SQLite 匯入與歸屬保存是真實執行；CLI wiring 的來源下載、模型、JSON exporter 和子程序使用注入測試物件隔離。沒有重跑全部既有 69 項測試，也沒有重驗 uv.lock、真實模型、官方 API、瀏覽器或整體正式發布。

新增測試檔：[`local/tests/test_combined_universe.py`](../local/tests/test_combined_universe.py)。
