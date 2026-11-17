# TWSE 全檔至私有研究驗證（2026-11-17）

本紀錄對應 [ticket 06](../.scratch/private-research-ready/issues/06-twse-market-source.md)。實作 `7d1c753`；整合 11 與環境決策後基準 `02222d6f32107df9042257a8fc21c232d94db4ab`。最後補強測試將重複的未選股票納入拒絕驗證，未修改產品邏輯。

## 實作及合成回歸

重用 `local.http_evidence.capture_response` 與 `local.collect_official.save_failure`，保留既有 `fetch` 的 bytes 相容性與 `ingest` 離線介面。成功報告新增 HTTP metadata、全檔 profile；CLI 失敗另留有界原始 bytes／hash 與階段／分類，不推進行情成功報告。

TDD 的四輪實際 red：`profile` KeyError、缺失敗報告（0 != 1）、bytes 無 metadata、非法選股數值失敗缺 profile。各輪最小實作後相應測試 green。最終定向命令：

```bash
uv run --locked python -m pytest local/tests/test_market_prices.py local/tests/test_market_graph.py -q
```

結果 exit 0：53 passed、52 subtests。涵蓋缺股票／欄位、混日／舊日、未選股票重複、非法／非有限數值、HTML／403、有界超量回應、冪等、較晚修訂、同時間衝突與 raw 改寫拒絕。全檔欄列／日期檢查與所選股票數值驗證分別呈現。

## 真實來源與串接

固定已登錄端點 `https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data`；無改 URL、無帶日期查歷史。`--expected-date 2026-11-17` 只是斷言。

- 取得時間：2026-11-17T06:21:45.827112+00:00；HTTP 200；`text/csv;charset=utf-8`。
- 完整回應：138,767 bytes、11 欄、1,391 列；全部交易日 2026-11-17；指定兩檔各一列，無缺漏。
- 原始 SHA256：`cdca533b9117e1400e35c581226d46357ea94a0b1e27cb789cd633ebc3d65bd5`。
- 財務輸入來源：05 的 `acceptance-1082584/normalized.json`，使用已審核 TWSE 公司／月營收來源；其原始快照與 manifest 在 `local/private/m1/05/live-1082584/`。
- 複製財務輸入 SHA256：`44f5bd6186b5fce85b30cea56d2432a6925736e2368bb3dc1fa204e1d7ff9b15`；有與原檔逐 bytes hash 核對。
- 真實行情→SQLite→research（`analysis none`、alerts）→audit exit 0。整合 11 後 run `15de89fd485743f68da59a2d03806ea7`，兩個股票圖、2 行情節點、6 財務節點、8 筆完整 facts；catalog 內 3 個保存版本均 valid。
- 同一原始回應／觀察時間再次匯入新增 0 筆。保留原本 HTTP metadata，未把重讀當成新的網路請求。
- 在獨立衍生檔改成舊交易日後 CLI 明確失敗；行情報告、market DB、研究 latest pointer 雜湊不變。獨立快照副本改寫後 research 拒絕 checksum mismatch，三者亦不變。兩項屬故障注入，不能當作官方提供了錯誤資料。

可重跑指令（預期日期須依實際回應核對；輸入、DB 與原始快照均留私有）：

```bash
uv run --locked python -m local.market_prices --market twse --symbols 2330 2454 \
  --expected-date 2026-11-17 --db local/private/m1/06/prices.db \
  --output local/private/m1/06/prices
uv run --locked python -m local.research --input local/private/m1/06/normalized.json \
  --symbols 2330 2454 --history-db local/private/m1/06/history.db \
  --output-root local/private/m1/06/runs --prices-db local/private/m1/06/prices.db \
  --price-snapshots local/private/m1/06/prices --trade-date 2026-11-17 --analysis none --alerts
uv run --locked python -m local.bundle_audit --root local/private/m1/06/runs
```

## 環境與完整檢查

macOS 27.2.1 arm64、Python 3.11.11、uv 0.6.13；使用既有 lock，未變更依賴。使用者已同意本輪在目前環境測試；Linux 未驗證。

共享環境參數：`TMPDIR=/private/tmp`、`UV_CACHE_DIR=/private/tmp/skg-uv-cache`、`UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv`。完整命令 `uv run --locked python -m local.check --report local/private/m1/06/check-escalated.json` exit 0：447 passed、187 subtests；compile／lexical CLI／JSON validation 亦通過。本票未改前端，未執行 frontend／瀏覽器／真實模型測試。

首次沙盒內下載 exit 1（DNS）；正常網路 escalation 後下載 exit 0。首次完整 check exit 1（loopback PermissionError，10 failed、12 errors）；正常 escalation 後同一套檢查通過，未略過測試。私有 acceptance 腳本最初因 PYTHONPATH、catalog tuple 解包失敗，修正腳本後 exit 0；未將兩次失敗當產品成功。

完整證據保留 `local/private/m1/06/`：`prices/`、`prices.db`、`normalized.json`、`history.db`、`runs/`、`execution.json`、`acceptance.py`、兩次 check 報告與故障注入副本。既有 `local.check` 在 `/private/tmp` worktree 的 `source_sha256` 為空；`execution.json` 另列 repo 相對原碼 hash，本票未修改 check 工具。

## 界線

價格／成交額仍為 `source_reported`，未核定幣別、倍率與交易範圍，交由 09；本票不宣告尺度正確、每日穩定或全市場數值皆已驗證。TPEx、Linux、原 CDN／瀏覽器、金融發布不在本次驗收內。公開 `data/` 未改，沒有排程、發布或交易。
