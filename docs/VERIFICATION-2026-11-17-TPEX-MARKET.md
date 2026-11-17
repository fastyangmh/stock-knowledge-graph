# TPEx 全檔至私有研究驗證（2026-11-17）

對應 [ticket 07](../.scratch/private-research-ready/issues/07-tpex-market-source.md)。測試基準 `8b91af6`（已確認 ancestry），加上本票 `local/tests/test_tpex_research.py`；完整測試時的檔案 hash 另存私有 `execution.json`。本票重用 05／06 的採集、HTTP evidence、profile 與失敗報告，沒有修改產品邏輯、來源 URL 或正規化定義。

## 來源審核與實際全檔

[行情 11371](https://data.gov.tw/dataset/11371)、[公司 25036](https://data.gov.tw/dataset/25036)、[月營收 56510](https://data.gov.tw/dataset/56510) 的官方頁面均重新確認資源連結、提供機關、免費及 OGDL-1.0 標示；另讀[條款與顯名義務](https://data.gov.tw/license)。官方 HTML 原始 bytes、取得時間與 hash 存 `source-review/`。CSV 透過產品 collector 實際下載，沒有重新導向、登入或封鎖繞過。

TPEx 行情保留已登錄 `otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=data&se=EW`，沒有替換為不同交易範圍的 `daily_close_quotes` 或 OpenAPI。公司／營收使用已登錄的 `t187ap03_O.csv`、`t187ap05_O.csv`；只在 private registry 副本啟用並更新審核日期，公開預設仍停用。

| 來源 | HTTP／Content-Type | bytes／欄／列 | 日期及覆蓋 |
| --- | --- | --- | --- |
| TPEx 行情 | 200／`application/csv;charset=utf-8` | 141,707／16／1,022 | 全檔 2026-11-17；6488／8069 各一列 |
| TPEx 公司 | 200／`text/csv` | 554,352／33／898 | 出表日 2026-11-16；兩檔齊全 |
| TPEx 月營收 | 200／`text/csv` | 170,907／14／898 | 出表日 2026-11-17、資料年月 2026-10；兩檔齊全 |

完整欄名、日期分布及選股驗證存 retrieval manifest／`latest-tpex.json`。行情取得時間 `2026-11-17T06:30:34.390175+00:00`，公司 `06:31:14+00:00`，營收 `06:31:19+00:00`。沒有將出表日、期末日、擷取時間混為同一時間。

原始 SHA256：

- 行情：`a76870c5add6af51ce28f0d4cf3fde04402766439fa71adf7f9b260418416f2b`
- 公司：`21db83542776807708d23cf8a4433817eabc2885b6ddaba325a783c13df49254`
- 月營收：`2b6fcef220f58cbb475a00b573cf36eb04b6da64d0817193d6e6d6b95023c2de`
- 正規化輸入：`6952ca73d835584b151026c45efd8dff66b5c1a7e2ca9bed6ce6d9f94913d7c3`

## 真實串接與故障注入

6488／8069 公司／營收均來自 TPEx 的獨立快照。raw→official import→market SQLite→`price_market=tpex` research（`analysis none`、alerts）→audit 全部 exit 0。最後驗證 run `f396c177ec8540fea8eb820f86b71bca`，2 個股票圖、6 財務節點、2 行情節點、8 筆完整 facts；兩個保存版本皆 valid。

同一行情 bytes／觀察時間再次匯入新增 0 筆；重用原 HTTP metadata，不將重讀冒稱新下載。另對獨立衍生副本注入舊日與 raw 改寫，並以錯誤 `price_market=twse` 嘗試研究；分別拒絕 stale/mixed date、checksum mismatch、market coverage missing。行情 DB、行情成功報告、財務成功 manifest、研究 latest pointer 的 hash 均不變。這些是故障注入，不是官方來源送出了壞資料。

## 合成回歸與完整檢查

新增 `test_tpex_research.py` 使用字面 16 欄 TPEx 格式、虛構數值、受控 HTTP 邊界及真實 SQLite／bundle。4 tests、6 subtests 通過，涵蓋獨立公司／營收來源、缺欄／缺股、舊日／混日、HTML／403、錯市場、部分財務來源失敗、冪等／修訂及 raw checksum。既有產品已能處理這些案例，沒有需要 red→green 修復的產品缺陷；本票不把新增驗收測試誤稱為產品修復。

實際完整命令：

```bash
TMPDIR=/private/tmp UV_CACHE_DIR=/private/tmp/skg-uv-cache \
UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv \
uv run --locked python -m local.check --report local/private/m1/07/check.json
```

結果 exit 0：451 passed、193 subtests；compile、lexical CLI 與 JSON validation 通過。環境 macOS 27.2.1 arm64、Python 3.11.11、uv 0.6.13，使用既有 lock。使用者已指定本輪目前 macOS 驗收；Linux 未驗、不阻擋本票。完整檢查以正常 escalation 提供 loopback 權限，沒有略過測試。未修改前端；本票未重跑 frontend、瀏覽器或真實模型。

`local.check` 在 `/private/tmp` worktree 的 `source_sha256` 既有空值問題未在本票修改；`execution.json` 另列 repo 相對 Python 原碼 hash 與 `uv.lock` hash。

## 重跑與證據位置

私有證據保留主工作區 `local/private/m1/07/`：`source-review/`、`tpex-registry.json`、`official/`、`prices/`、`prices.db`、`normalized.json`、`history.db`、`runs/`、`check.json`、`commands.json`、`execution.json`、`acceptance.py` 及故障副本。以下日期是本次驗收值；下次執行須以來源實際日期確認，`expected-date` 不查歷史。

```bash
# 先逐來源確認並準備僅啟用 TPEx 兩筆的私有 registry 副本。
uv run --locked python -m local.collect_official \
  --registry local/private/m1/07/tpex-registry.json \
  --output-dir local/private/m1/07/official --symbols 6488 8069
uv run --locked python -m local.official_import \
  --registry local/private/m1/07/tpex-registry.json \
  --snapshot-dir local/private/m1/07/official --symbols 6488 8069 \
  --as-of 2026-11-17 --output local/private/m1/07/normalized.json
uv run --locked python -m local.market_prices --market tpex --symbols 6488 8069 \
  --expected-date 2026-11-17 --db local/private/m1/07/prices.db \
  --output local/private/m1/07/prices
uv run --locked python -m local.research --input local/private/m1/07/normalized.json \
  --symbols 6488 8069 --history-db local/private/m1/07/history.db \
  --output-root local/private/m1/07/runs --prices-db local/private/m1/07/prices.db \
  --price-snapshots local/private/m1/07/prices --trade-date 2026-11-17 \
  --price-market tpex --analysis none --alerts
uv run --locked python -m local.bundle_audit --root local/private/m1/07/runs
```

## 界線

本票是來源與工程串接驗收，不是交易範圍、單位、財務獨立抽檢或價格正確性驗收。價格／成交額／營收仍 `source_reported`；不猜幣別或股張換算，尺度交由 08／09。全檔結構與日期驗證不代表每列數值皆已驗證。沒有歷史連續交易日保證、每日穩定性或投資有效性結論。公開 `data/` 未變，未啟用排程、發布或交易。
