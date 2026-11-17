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

2026-11-17 已完成 TWSE 固定端點的真實全檔與兩檔私有研究驗收，詳見[驗證紀錄](VERIFICATION-2026-11-17-TWSE-MARKET.md)。TPEx 真實驗收另由 ticket 07 負責；一次成功不代表每日穩定服務。重新導向、403、欄位異動仍會停止。

## 操作（手動，僅私有輸出）

在專案根目錄使用已鎖定的環境。下面的 `YYYY-MM-DD` 須換成來源資料實際交易日；股票代碼只是明確選取的例子，不代表任何指數或投資建議。

```bash
uv run --locked python -m local.market_prices \
  --market twse --symbols 2330 2317 \
  --expected-date YYYY-MM-DD
```

`--market tpex` 選擇上櫃來源。程式只接受明確的四碼代碼，不根據代碼格式聲稱普通股類別或指數歸屬。交易市場需由呼叫者選定，不把上市與上櫃的同代碼紀錄互相覆蓋。

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

TWSE 全檔至研究串接已驗證；接續完成單位與交易範圍核查（ticket 09），再擴充官方財務指標與原始公告抽檢。雙來源歷史名單、對外展示、付費服務或簽約各自評估，不阻塞與名單無關的模組。仍維持手動執行，不啟用排程或發布。
