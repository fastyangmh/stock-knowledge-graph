# 未裁剪研究事實契約

[私有研究](PRIVATE_RESEARCH.md) · [整包稽核與歷史](RESEARCH_HISTORY.md)

`local.research` 新產生的私有 bundle 包含 `research-facts.json`。它在展示裁剪之前建立，保存本次 cutoff 的完整數值集合；既有 `data/` 仍只包含有限展示圖。此契約不補下載歷史、不建立交易日曆、不還原價格，也不補造市場資料的本地登錄時間。

## 保存範圍

- 財務與既有籌碼：所選股票在 `known_at` 範圍內，由 normalized ledger replay 選出的全部數值。沿用 availability／observation／local registration 三個 gate、修訂選擇與來源衝突拒絕規則；不是把所有修訂版本重複當作不同事實。
- 行情：指定 `price_market`、截至 `trade_date` 的本地已保存日期；每股每日選取 cutoff 當時可讀取的最新觀察。每筆重用既有來源、正規化及原始 CSV SHA256 驗證，不沿用提醒前20筆或展示名額。當日仍要求全部所選股票有有效行情或已明示撤回；較早各日缺少的股票不補值。
- 未提供完整行情三參數時，`scope.market` 明示 `included: false`、`market: null`、`trade_date: null`。空數值集合保留各股零筆 coverage，不捏造樣本。

`--max-information-nodes 0..100` 僅調整展示資訊節點上限，預設100；不改變完整事實內容、提醒門檻或資料來源。圖譜仍只附當日行情，歷史行情保存在獨立契約中。

## 讀者介面

本機下游工具只使用 `local.bundle_audit.audit_bundle(...)` 或 `catalog(...)` 回傳的 `Bundle.facts`；不自行讀 SQL 或重新下載來源。

| 欄位 | 意義 |
| --- | --- |
| `Bundle.facts` | 新契約解析後的 dict；純舊 bundle 為 `None` |
| `Bundle.summary().fact_scope` | 新版 `unpruned_facts`；舊版 `display_graph_only` |
| `schema_version` | `research-facts-1.0`，含可見行情通知時採 `research-facts-1.1` |
| `producer` | `private-research-1` |
| `scope` | `stock_ids`、`known_at`、`market {included, market, trade_date}` |
| `facts` | 依穩定 `id` 排序的完整 flat rows |
| `coverage` | 每股 `financial_metric`／`chip_metric`／`market_price` 筆數，包括零筆 |
| `normalized_snapshots` | 已使用 ledger 快照的 SHA256、observed／recorded 時間、原始 source 定義與 metadata，含已提供的 raw／normalization 證據引用 |
| `time_semantics` | 本版 availability／registration／bundle completion 的明確語意 |

每筆 `kind` 為 `financial_metric`、`chip_metric` 或 `market_price`，皆有 `stock_id`、`source_id`、完整 `source`、`id`、`available_at`、`observed_at`、`recorded_at`、`recorded_at_status`。`id` 是 kind／股票／來源／指標／期間鍵的 SHA256，與展示 node ID 或該節點是否存在無關；它不把修訂數值或展示政策混入事實身分。

財務／籌碼 row 保留 replay 的全部已知欄位，包括 value、period_end／trade_date、period_type、unit、currency、consolidation、value_basis，以及輸入原有的正規化版本、raw 數字／尺度與證據引用。未提供 unit／currency／consolidation／value_basis 時明示 `null`；`source_reported` 保留原值，不推定倍率。`source_available_at` 保存輸入原始 available_at；有效 `available_at` 是原始 available、觀察、首次本地登錄三者最大值。`input_snapshot_sha256` 解析至 `normalized_snapshots`，`registered_at` 與 `recorded_at` 相同。每筆 source 必須解析至供應該筆值的 normalized snapshot，不能用後來同 ID 的來源定義冒充當時 provenance。

行情 row 保留完整 normalized OHLC 十進位文字、成交股數、成交金額、成交筆數、來源價格單位與未還原基準。`raw_sha256` 加 `source_id` 可定位既有私有原始快照；`raw_snapshot_verified` 明示 producer 已驗證，`acquisition` 不將本地匯入冒稱 HTTPS 下載。普通行情觀察未保存首次本地登錄時間，因此 `recorded_at: null`、`recorded_at_status: unknown`、`source_available_at: null`，有效 `available_at` 沿用 `observed_at`；這不是完整雙時間市場資料庫。`report.completed_at` 僅是本次保存時間。

## 稽核與失敗

`report.research_facts` 固定指向 `research-facts.json`，含 schema、SHA256、byte size、筆數與市場範圍。Audit 從同一批捕捉 bytes 計算 hash 和解析內容，驗證 scope、coverage、事實身分、來源、快照連結、時間 gate、數值／期間、行情正規化及 replay 計數。新檔損壞、缺漏、缺 hash 或未知 schema 都失敗，不能退回展示圖。

producer 在暫存目錄執行完整 bundle audit，成功才搬成新版本並更新 `latest.json`。容量或契約失敗不修改舊 bundle／pointer；已登錄的 normalized input 仍可能留在 ledger，沿用原先跨檔非單一交易的界線。

| 預算 | 限制與超額行為 |
| --- | --- |
| 單一 JSON | 32 MiB；捕捉前與讀取中皆檢查，不先載入超大 JSON |
| 單一新 bundle | 256 MiB；包含 DB、report、完整事實與展示檔 |
| 目錄 entries | 每 bundle 最多2000，包括目錄；symlink／未知檔拒絕 |
| 事實筆數 | 100,000；包含三種 kind，不截尾 |
| 財務 replay | 沿用最多5000 snapshots、128 MiB JSON 文字 |
| 行情 discovery | 最多100,000 revision rows、5000個可得日期；不採20筆窗口 |
| 行情各日 revision | 沿用最多10,000筆，包含所選股票的修訂 |
| 行情 JSON 與 raw 工作量 | 累計 record/source JSON 128 MiB、raw 驗證讀取128 MiB；重複讀取亦計費 |
| 行情 SQL 工作量 | 共享500萬個已回報 VM steps；每1000 steps回呼，另有每個連線未達回呼粒度的固定餘量；超額明確失敗 |
| 歷史 catalog | 預設50版本、合計256 MiB；沿用 CLI 的明確預算設定 |
| HTTP preview | 實際服務的圖譜、摘要、網站資產合計64 MiB；不包含不提供HTTP的完整事實／report／DB |

這些是容量／序列化與工作量限制，不是 Python peak heap 或全市場規模效能保證。行情 raw 工作量保守計入每次驗證，同日多股可能重讀同份 CSV；量測前不擅自提高限制。超額整批失敗，不能靜默縮小研究範圍。

## 相容與安全界線

純舊 bundle 仍通過原有 audit，標明 `display_graph_only`；不就地補寫或偽稱完整歷史。私有歷史頁可列出新版 bundle，但 HTTP allowlist 不提供 `research-facts.json`、完整 report、raw 或 SQLite。完整事實由本機已稽核的 `Bundle` 交給分析工具，沒有新增公開完整事實 API。

事件讀者已透過 audit 的 `Bundle.facts` 使用 `event-study-2.0`；純舊維持 `event-study-1.0`／`display_graph_only`。混合目錄必須明確選 cohort，列出未納入版本及原因，不用新契約重建舊事件基準；詳見[事件統計](EVENT_STUDY.md)。SHA256 證明內部一致性，不能證明來源真實性、授權、數位簽章或無偏研究。真實來源結合、Linux/NAS 與大規模效能仍須各自驗收。

行情可明確附 `normalization_version: market-units-2.0`、`raw_values`、`unit_review` 及價格幣別／股數／金額／筆數單位／`trading_scope`；它們是來源快照綁定的審閱定義，不能自行替舊事實補值。Audit 依原有或新版契約重建行情欄位；未知版本或未有版本卻注入新單位拒絕。完整格式與目前未完成的真實尺度驗收見[行情單位抽檢](MARKET_PRICES.md#私有行情單位抽檢與版本)。

財務定義 aliases 由共同契約處理：`statement_scope` 對應 `consolidation`，
`report_basis` 對應 `value_basis`；兩側提供不同值即拒絕。新建完整 facts 同時保存
兩個名稱，舊 facts 缺值仍可讀。`official-monthly-twd-v1` 保存原始金額／單位、
轉換倍率及私有證據引用，採獨立 ledger 重建，詳見[財務抽檢](FINANCIAL_REVIEW.md)。

含行情通知的 1.1 版保存 `market_notices`，逐筆記錄已知的來源處置、目標及替代原件 SHA256、數值定義、本地登錄和原件定位；尚待生效的通知也可查回。通知衍生的有效事實帶 `notice_sha256` 和已知 `recorded_at`，`source_available_at` 為來源發布時間，`available_at` 取發布、生效、觀察及本地登錄時間中最晚者。已撤回當日允許有效行情數為零，提醒保留缺少目標的原因。Audit 依通知鏈核對數值、截止、撤回狀態、報告與提醒引用。既存 1.0 bundle 仍依原契約稽核，事件沿用實際首次保存值。[行情操作](MARKET_PRICES.md#行情來源明示更正撤回與重發)
