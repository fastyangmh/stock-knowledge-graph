# 私有研究流程：公司／月營收＋行情＋觀察歷史

[文件中心](README.md) · [行情模組](MARKET_PRICES.md) · [資料來源](DATA_SOURCES.md)

## 完成範圍

本流程不需要臺灣50或009816名單，以使用者明確指定的普通股代碼做**私有**研究。股票代碼不是投資建議，也不推定指數／ETF歸屬。既有雙來源功能保留；暫緩名單權利確認不影響本流程。

已串接：經審核官方公司與月營收快照 → 自選股票正規化 → 追加式觀察紀錄 → 隔離 SQLite／可選語意分析 → 財務數值及盤後行情節點 → 驗證圖譜 → 新的私有研究版本。**不自動下載名單、不下單、不執行 Git、不改公開 data/、不安裝排程。**

正式來源全檔、數值尺度與最新版真實模型仍須實測；離線 fixture 通過不代表這些項目已驗收。

## 手動操作

從 repo 根目錄執行，使用 `uv sync --locked --extra dev` 安裝環境。以下股票代碼僅示範指令格式，不代表選股建議或成分股名單。`YYYY-MM-DD` 必須換成**實際快照／交易日期**，不能把昨天資料標為今天。

```bash
# 1. 原有核准官方 CSV → 私有公司／月營收快照（實際網路請求）
uv run --locked python -m local.collect_official

# 2. 新增：不用 index CSV，按明確代碼匯入公司／月營收
uv run --locked python -m local.official_import \
  --symbols 2330 2317 \
  --as-of YYYY-MM-DD \
  --output local/private/normalized-watchlist.json

# 3. 選用：盤後價格 → 私有觀察資料庫與原始快照（實際網路請求）
uv run --locked python -m local.market_prices \
  --market twse --symbols 2330 2317 --expected-date YYYY-MM-DD

# 4. 整合：只讀取上述本地資料，產生新的私有研究版本
uv run --locked python -m local.research \
  --input local/private/normalized-watchlist.json \
  --symbols 2330 2317 \
  --prices-db local/private/market-prices.db \
  --price-snapshots local/private/market-prices \
  --trade-date YYYY-MM-DD --price-market twse \
  --analysis none
```

省略 `--prices-db`、`--price-snapshots`、`--trade-date` 三個參數可只處理財務。三者必須一起提供，避免讀到沒有日期或無原始快照可核對的行情。原始 CSV、DB 紀錄、交易日、來源、OHLC 與 SHA256 都須一致；`--input` 匯入的市場 CSV 仍標成 `local_file_unverified`，不冒稱官方下載成功。

`--analysis none` 不產生文本相似邊；`--analysis lexical` 是測試基準；`--analysis semantic` 使用既有本地多語模型，首次使用可能下載權重。正式重現應另帶 `--revision <模型commit>`。`--top-k`、`--threshold`、`--lookback-days`、`--max-pairs` 可控制語意範圍與運算預算。數值行情與財務指標節點**不加入文字 Embedding**。

## 輸出與預覽

預設輸出在 `local/private/research-runs/<run-id>/`：

```text
<run-id>/
├── graph.db       # 當次隔離的衍生圖譜資料庫，不是原始資料庫
├── data/          # 完整可驗證的靜態圖譜（仍在 private 路徑）
└── report.json    # 資料來源、截止時間、快照、統計、警告、SHA256
```

同層 `latest.json` 指向最後成功的版本；它是普通 JSON，不是 symlink。將命令輸出中的實際 run-id 代入：

```bash
uv run --locked python -m local.preview \
  --data-dir local/private/research-runs/RUN-ID/data --port 8765
```

只在本機瀏覽 `http://127.0.0.1:8765/`。不要把整個 repo 或 private 目錄作為通用網頁根目錄。

新關係 `has_market_price`／`has_financial_metric` 是**數值觀察**，不是 cosine。價格用十進位文字保留精度；`source_reported` 仍表示未確認倍率，不自行轉成元／千元或計算投資報酬。生命週期原有100個資訊節點上限不變，其中最多10席優先留給主股票最新1個行情及9個財務數值節點，避免數值節點因沒有相似度分數而全部被排除。

## 修訂與時間界線

`local/private/research-history.db` 新增 `research_snapshots`：

- `sha256`：正規化 JSON 的 canonical SHA256。
- `observed_at`：輸入宣告的來源觀察時間。
- `recorded_at`：**本系統實際首次登錄**時間。
- `payload_json`：不可變的正規化輸入快照。

同一快照重跑不重複登錄；修訂追加新快照，不覆寫舊值。`--known-at` 是具時區的「本系統已知截止時間」，同時檢查 observed、recorded 與資料 available 時間。今天補匯入的舊檔不會變成系統昨天已知的證據。它不是完整市場歷史還原、退市資料庫或可直接宣稱無偏誤的回測引擎。

同一時間互相矛盾的修訂、同一指標的多來源衝突會停止，需明確校對。檔案缺少紀錄不被解釋成刪除；目前 ledger 是 upsert 型觀察紀錄，尚未定義刪除／撤回事件。財務資料量以最多5000個快照、128 MiB replay 文字作防護，超限明確停止；尚未自動封存或清理。

## 快取、失敗與保存

每次成功產生新 bundle，舊 bundle 不變；有相同模型身分時，從上一個通過 SHA256 的圖譜 DB 複製適用向量及語意狀態。資料與關係未變時可達 `encoded=0`、`graph_reused=true`，但仍會重建私有展示版本與報告。

匯出失敗不更新 `latest.json`。已通過驗證的輸入快照可能已進 ledger，作為失敗前取得的證據；這**不是**全部 SQLite／檔案系統的單一跨檔交易。若最後更新指標檔失敗，可能留下一個完整但未被 latest 指向的 bundle，應人工查核，不能當作新發布成功。

預設保留所有 bundle 與備份，不自動刪資料；正式長期排程前要決定磁碟預算與保存策略。公開發布仍需獨立審查，不因私有 bundle 可看就自動推送 GitHub。

## 私有 SQLite 備份／還原

```bash
uv run --locked python -m local.backup create \
  --db local/private/research-history.db
uv run --locked python -m local.backup verify \
  --bundle local/private/backups/BACKUP-ID
uv run --locked python -m local.backup restore \
  --bundle local/private/backups/BACKUP-ID \
  --db local/private/restored-history.db
```

使用 SQLite backup API 建立一致性單檔備份，含已提交 WAL 內容；驗證 SHA256、大小及 SQLite integrity。還原目標**必須不存在**，不提供覆寫／force。Linux/NAS 若不支援同檔案系統 hard link，還原會失敗，不降級成不安全覆寫。這個工具只備份 SQLite，**原始 CSV 快照、模型及憑證要另行備份**；未宣稱實測 NAS 斷電或異地復原。

## 價量及月營收研究提醒

加入 `--alerts` 可在同一私有版本產生兩類獨立提醒；設定使用 `--alerts-config`。提醒與語意模型獨立，不自動下載或發布，不合成交易分數。詳見[規則與驗收範圍](RESEARCH_ALERTS.md)。
