# 不依賴指數名單的官方盤後行情

[文件中心](README.md) · [資料管線](DATA_PIPELINE.md) · [本次驗證](VERIFICATION-2026-11-16-MARKET.md)

## 決策更新（2026-11-16）

使用者選擇：名單來源若仍有缺口就先略過，先做可以做的。**TW50＋009816仍是既定研究範圍，但名單確認不再是整個開發工作的前置閘門；現在不要求使用者先寄信。** 沒有名單時，不宣稱任何股票為指數成分股或ETF持股；仍可獨立處理公開行情與其他已核對的官方資料。

### 名單並非只有寄信一條途徑

- [LSEG／FTSE Russell 臺灣指數系列](https://www.lseg.com/en/ftse-russell/indices/twse-taiwan) 在 Constituents 區列有「FTSE TWSE 50」及[官方下載入口](https://research.ftserussell.com/analytics/factsheets/Home/DownloadConstituentsWeights/?indexdetails=TW50)。
- [公開成分股表說明](https://www.lseg.com/en/ftse-russell/index-resources/constituent-weights) 表示通常於最近定審後兩個月內發布。因此「能下載」不能直接推論為每天更新的完整歷史名單。本次確認入口，未取得／解析其二進位表格內容，未核定再散布使用範圍。
- [元大0050官方持股揭露](https://www.yuantaetfs.com/product/detail/0050/ratio) 可查ETF持股，**不把它冒稱為正式TW50歷史名單，也不自動替換原先009816研究池**。
- [data.gov.tw 11670](https://data.gov.tw/dataset/11670) 是指數值與報酬指數，不是成分股名單；首頁 https://data.gov.tw/en 本身只是資料目錄。

名單及公開使用範圍列為獨立待辦，保留原有雙來源程式，不啟用爬取或自動公開名單。

## 本輪可用入口

`local.market_prices` 是**私有盤後價格儲存模組**，不需要TW50／009816名單、券商帳號、API Token或Embedding模型。使用者明確選定股票代碼，僅在相對應市場資料集中取得所選股票。

| 市場 | 政府資料集 | 固定來源（由資料集頁連結取得） |
| --- | --- | --- |
| 上市 TWSE | [11549 個股日成交資訊](https://data.gov.tw/dataset/11549) | `https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data` |
| 上櫃 TPEx | [11371 上櫃股票收盤行情](https://data.gov.tw/dataset/11371) | `https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=data&se=EW` |

兩份資料集頁標示每日更新、免費及政府資料開放授權條款第1版。依[條款](https://data.gov.tw/license)符合條件使用無須逐次書面授權，但須履行顯名義務。此核對只針對這兩份開放資料，不擴及其他付費行情、網站頁面或指數名單。

2026-11-17 已分別完成 TWSE 與 TPEx 固定端點的真實全檔、各兩檔私有研究驗收，詳見 [TWSE 紀錄](VERIFICATION-2026-11-17-TWSE-MARKET.md)與 [TPEx 紀錄](VERIFICATION-2026-11-17-TPEX-MARKET.md)。TPEx 使用既有 `otc_quotes_no1430` 資源，沒有換用 `daily_close_quotes` 或 OpenAPI；交易範圍與尺度另由 ticket 09 核查。一次成功不代表每日穩定服務。重新導向、403、欄位異動仍會停止。

## 操作（手動，僅私有輸出）

在專案根目錄使用已鎖定的環境。下面的 `YYYY-MM-DD` 須換成來源資料實際交易日；股票代碼只是明確選取的例子，不代表任何指數或投資建議。

```bash
uv run --locked python -m local.market_prices \
  --market twse --symbols 2330 2317 \
  --expected-date YYYY-MM-DD
```

`--market tpex` 選擇上櫃來源。程式只接受明確的四碼代碼，不根據代碼格式聲稱普通股類別或指數歸屬。交易市場需由呼叫者選定，不把上市與上櫃的同代碼紀錄互相覆蓋。

串接 `local.research` 時，TPEx 必須明確帶 `--price-market tpex`（預設為 `twse`），並使用獨立核對的上櫃公司／月營收輸入。本次以 private registry 啟用既有 TPEx 公司／營收來源完成驗收，公開 registry 的預設啟用設定未變；準備與重跑程序見 [TPEx 驗證](VERIFICATION-2026-11-17-TPEX-MARKET.md)。

已有來源CSV時可完全離線匯入：

```bash
uv run --locked python -m local.market_prices \
  --market twse --symbols 2330 2317 \
  --expected-date YYYY-MM-DD \
  --input local/private/source-prices.csv
```

離線檔案會標記 `local_file_unverified`：欄位／數值校驗不證明檔案真為官方資料。HTTP取得標記 `https_download`；同樣不把擷取時間當作原始公開時間。

**日期不是查歷史參數：** `--expected-date` 用來核對回應日期，不會傳給端點要求歷史下載，也不會改寫資料日期。過期、混合日期或選定股票不完整會停止。程式未整合交易日行事曆，請勿以「週一到週五」推測來源日期。

## 保存內容與限制

- 預設資料庫：`local/private/market-prices.db`；獨立於圖譜資料庫。
- 私有輸出：`local/private/market-prices/<source_id>/<SHA256>.csv` 及 `latest-twse.json`／`latest-tpex.json`。
- 成功報告附 HTTP status、Content-Type（缺省明示 missing）、實際 response URL、觀察時間、bytes 與 raw SHA256。離線／注入 bytes 不虛構 HTTP metadata，保持 unavailable。
- `profile` 記錄全檔欄位、總列數、交易日分布、指定股票列數與缺漏。全列日期、欄列結構及重複代碼均檢查；OHLC／成交數值只驗證指定股票，以 `selected_value_validation` 分開揭露。
- CLI 失敗另存 `retrieval-failure-<id>.json` 與有界 `failures/<id>.bin`，重用官方採集器的 metadata／錯誤分類。超量或短讀標記 `body_truncated`，只給 captured SHA256、不宣稱完整回應 hash；失敗不更新 `latest-<market>.json`。直接呼叫 `ingest` 的既有介面仍以例外回報，不自動建立失敗檔案。
- SQLite表 `market_price_observations` 保存來源、市場、代碼、交易日、觀察時間、原始校驗碼、正規化行情JSON、來源條款和取得方式。主鍵為 `(source_id, symbol, trade_date, observed_at)`。
- `market_prices_latest` view 按**每來源／股票／交易日**選最新觀察，而非最後插入順序；舊觀察與更正值都不覆寫。同一時間的矛盾資料會拒絕，不默默決定哪個正確。
- 原始CSV不可變；只對完整成功批次更新結果報告。檔案與SQLite不是跨系統原子交易，失敗時可能留下未被報告引用的原始快照；不自動清除稽核證據。
- 開高低收／成交金額以十進位文字保存，避免binary float誤差；成交股數和筆數為非負整數。缺少價格保留null，不補0；缺少成交股數／成交金額／筆數則停止。
- 成交股數依來源欄位採「股」，不自行轉成張。價格及成交金額的幣別／倍率尚未完成實際來源核對，保留 `source_reported`；不擅自標註新台幣元。
- 這是來源原始未還原行情，不提供除權息還原、報酬計算或績效聲明。
- 不將每日價格轉成文本Embedding／新聞節點，不增加圖譜節點，不提交任何公開 `data/`。既有前端不會自動顯示這些行情；後續再做價格查詢與圖譜整合。

## 下一步（不要求先寄信）

TWSE 與 TPEx 全檔至各市場研究串接已驗證；接續完成單位與交易範圍核查（ticket 09），再擴充官方財務指標與原始公告抽檢。雙來源歷史名單、對外展示、付費服務或簽約各自評估，不阻塞與名單無關的模組。仍維持手動執行，不啟用排程或發布。

## 私有行情單位抽檢與版本

`local.market_review` 對行情做獨立核對，不把價格偽裝為營收。輸入從市場 DB 讀取，必須同時重驗原始 CSV；reference 是另行從官方查詢轉錄、保存原始 bytes 的 JSON。每股固定核對 open／high／low／close／volume_shares／turnover_raw／trades 七欄，預設絕對誤差0。報告列 input raw SHA256、reference evidence SHA256／URL／取得時間／欄位定位、兩側定義、差額、容許誤差與狀態。

```bash
uv run --locked python -m local.market_review \
  --db local/private/market-prices.db \
  --snapshots local/private/market-prices \
  --market twse --symbols 2330 2454 \
  --trade-date 2026-11-17 --known-at 2026-11-17T08:00:00Z \
  --reference local/private/review/reference.json \
  --output local/private/review/report.json
```

日期／代碼僅示範命令格式。`--known-at` 不會補下載缺失歷史。Reference 格式是 `market-reference-1.0`：`records` 每筆含 market、symbol、trade_date、上述七欄、下列定義欄位、`evidence_id` 與 `locator`；`evidence` 每筆含唯一 `id`、同目錄原始檔 `path`、SHA256、HTTPS `url`、`retrieved_at`。CLI 驗證原始參考檔 hash，拒絕 symlink／跳出目錄、重複同股同日、同一原始 input hash 作 reference、缺檔及超額。上限為20,000個抽檢欄位、100個參考檔、單檔20 MB／合計128 MiB及32 MiB報告。使用者仍須核對參考是否獨立；不同 hash 不足以證明獨立性或來源真實性。

定義包含 `price_unit`、`price_currency`、`volume_unit`、`turnover_unit`、`turnover_currency`、`trades_unit`、`price_basis`、`trading_scope`。未知幣別／尺度／範圍即 `definition_unverified`；不同定義即 `definition_mismatch`；未提供正確日期參考即 `missing_reference`。缺值、差異及零筆比較都使 `needs_review: true`，CLI exit 2；只有全部必要欄位相符或落在明訂容許誤差內才 exit 0。`--absolute-tolerance` 對本次各欄位共同適用，若參考有不同四捨五入口徑應分次核對，不設大額誤差掩蓋股數或筆數錯誤。

只有完成來源尺度審閱後，才提供 `market_prices --unit-review <private.json>`。這是有證據的明確選用入口，預設仍產生原來的 `source_reported`。審閱檔 `schema_version: market-unit-review-1.0` 必須綁定 `source_id`、實際 CSV `raw_sha256`、`trade_date`、明列 `symbols`，並附 evidence 的 HTTPS URL／SHA256／retrieved_at／locator。它宣告價格 `currency_per_share`、成交量 `share`、金額 `currency`、筆數 `trade`、明確 ISO 幣別、`source_unadjusted` 及已確認交易範圍；不執行股張、匯率、倍率或還原轉換。交易範圍可為 `regular_only`、`regular_oddlot_afterhours`、`regular_oddlot_afterhours_block`，不能從 URL 名稱或數字相等推定。

新 record 保存 `normalization_version: market-units-2.0`、`raw_values` 的原有十進位精度及完整 `unit_review`。建議以獨立 DB 重新產生新版研究；同 timestamp 的矛盾舊新 record 仍拒絕，不修改觀察時間以規避。舊 DB／bundle 不就地升級；market_graph 和完整事實 audit 依 record 宣告重建舊／新版本，未知版本、raw hash／原始數值不一致、未有版本卻注入新版單位都拒絕。提醒與事件比較鍵包括幣別、股數／金額／筆數單位、交易範圍與正規化版本；不能跨定義混成一條數列。舊版來源內的相對描述仍保留原讀取行為，不表示已完成單位驗收。

截至本次[真實抽檢紀錄](VERIFICATION-2026-11-17-MARKET-UNITS.md)，兩市場範圍／幣別證據尚未全部確認，因此**未將任何真實快照升級為已審閱單位，也未完成 ticket 09**。同一官方端點在不同發布時段的註記可能不同，審閱結論須綁當次 bytes，不適用全部日期。

## 行情來源明示更正、撤回與重發

以個股及交易日為單位審閱交易所原件，確認通知明列該筆行情、處置與適用範圍，再準備私有 `market-notice-1.0` JSON。使用原已審資料集 TWSE 11549 或 TPEx 11371。兩種市場分別核對 `www.twse.com.tw`、`www.tpex.org.tw` 的 HTTPS 來源網址與原件定位。這是人工審閱的來源聲明，檔案雜湊只能重驗保存的 bytes。

先執行讀取模式，從原有行情庫核對當時的 `raw_sha256` 與 `record_sha256`。後者涵蓋該股的標準化數字與單位定義。下面各日期、代碼與私有路徑應換成原件對應值。

```bash
uv run --locked python -m local.market_prices --market twse --symbols 2330 \
  --expected-date YYYY-MM-DD --known-at "<含時區的截止時間>"

uv run --locked python -m local.market_prices --market twse --symbols 2330 \
  --expected-date YYYY-MM-DD --notice local/private/notice.json \
  --notice-evidence local/private/official-notice.pdf --input local/private/corrected.csv
```

| Manifest 欄位 | 內容 |
| --- | --- |
| `schema_version`、`action` | `market-notice-1.0`，處置為 `correct`、`withdraw`、`republish` 之一 |
| `source_id`、`market`、`symbol`、`trade_date` | 對應 CLI 的行情來源、市場小寫識別字、四碼股票與 ISO 交易日 |
| `target_raw_sha256`、`target_record_sha256` | 前一版原始 CSV 與該股正規化紀錄各自的校驗碼。重發時引用撤回前的最後一筆 |
| `parent_notice_sha256` | 首次通知為 JSON `null`，後續引用 CLI 回報的前一份 manifest 雜湊 |
| `replacement_raw_sha256` | 更正或重發提供替代 CSV 的 SHA256。撤回填 `null`，並省略 `--input` |
| `evidence_url`、`evidence_sha256`、`locator` | 對應市場交易所通知網址、獨立通知原始 bytes SHA256、指出處置與資料範圍的位置 |
| `published_at`、`effective_at`、`observed_at` | 通知原始發布時間、來源明示生效時間、觀察該原件時間，均含時區 |
| `replacement_unit_review` | 僅於替代檔有獨立單位審閱時附上，綁定替代 CSV。原版與替代版須具相同單位、交易範圍及價格基準 |

成功後另存 `market_price_notices`，最初本地登錄時間由系統產生。完全相同的通知重跑保留首次登錄。本機提供的替代行情保留 `local_file_unverified`。原檔及替代 CSV 按 SHA256 留在來源目錄，正式通知 bytes 位於 `<source_id>/notices/<evidence_sha256>.bin`。日常蒐集的 `latest-<market>.json` 和 SQL 的 `market_prices_latest` 只代表一般觀察，研究採用版本由上述 `--known-at` 或 `local.research` 查詢。

截止在首次登錄之前仍見一般觀察。通知已登錄但尚待生效時，照常採用當時最新的一般版本。若其間另有一般更新，研究會保存該觀察的時間、原件與紀錄雜湊。相同原件與正規化紀錄在不同時間擷取仍保留歷史。已被較新版本取代的舊檔再次到達時，查詢繼續顯示較新版本。首次通知的目標必須在觀察通知當時已可得，而且至登錄時仍為有效的一般版本。

撤回生效時該股該日的有效觀察為空。普通行情缺列與再次匯入舊檔均保留當前明示處置。要恢復須用 `republish` 引用撤回通知及替代原件。各股／日最多 256 份通知、每個登錄項 64 KiB、各原件上限 20 MB。登錄前先把新通知、替代原件與現存歷史一起計入該股該日的重播預算，原件累計上限 128 MiB。跨股票、跨日期的研究另有整次查詢上限。實際驗收與仍缺的原件見[行情通知驗收](../.scratch/m2-market-revisions/issues/01-market-notices.md)。

### 升級、備份與回復

1. 使用通知前，先暫停該行情庫的寫入，保留既有程式版本、SQLite 一致性備份、行情來源目錄及已保存研究 bundle。在獨立目錄使用新版讀者核對早期截止。一般行情的本地登錄時間仍為未知。首次登錄通知時程式在交易內新增 `market_price_notices`。
2. 建立可攜備份時，用 SQLite backup API 或 `.backup` 取得包括通知表的資料庫，再複製完整行情快照樹。須包含原始及替代 `<source_id>/<sha256>.csv`、`<source_id>/notices/<evidence_sha256>.bin`、既有 `latest-<market>.json`，並另存人工審閱的 manifest JSON、定位及既有 SHA256 清單。需要重播研究時一併保存對應輸入、歷史 ledger、整個 runs 目錄及 latest 指標。保持寫入暫停直到檔案複製完並核對完成。
3. 還原到全新私有路徑，逐檔檢查清單與原有雜湊，用新版 `market_prices --known-at` 分別查登錄前、待生效及生效後，再用 `bundle_audit` 核對已保存研究。撤回生效後應同時見到有效觀察為空與該檔撤回通知。
4. 回退舊程式時，只讓它讀升級前的副本與相應歷史截止，另行保留含通知的新庫及完整原件。舊讀者忽略通知表，`market_prices_latest` 也只反映一般行情，會把已撤回報價重新顯示為有效。恢復日常研究前先切回可重播通知的讀者，查核最新截止及撤回原因。
