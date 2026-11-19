# 2026-11-19 私有後續行情及新增來源樣本

候選 `71d3139`，macOS arm64。私有位置均相對於 repo。本文記錄輸入與適用範圍；原始檔、行情數值、公告內容及個別公司財報均保存在 `local/private/`。

## P2-03、P3-01、P4A-01 的真實後續觀察

11 月 19 日重新執行兩個既有已審來源的 `local.market_prices`，指定交易日 2026-11-18，沿用 TWSE 2330、2454 與 TPEx 6488、8069。兩個 sandbox 首次請求均因 DNS 失敗，failure report 已保存；經核准連線後兩市場命令各 exit 0、各保存兩筆。全檔 SHA256 與 HTTP metadata 可由各市場新的 `prices/latest-*.json` 查核。[TWSE 資料集](https://data.gov.tw/dataset/11549) · [TPEx 資料集](https://data.gov.tw/dataset/11371)

在各自的新位置複製 11 月 17 日的 M1 已稽核研究版本，以 SQLite backup 重建行情庫與 ledger，對 11 月 18 日原件重新正規化，逐欄比對同次擷取報告後併入該副本。沿用 11 月 17 日已審的月營收輸入與模型 revision，實際執行 research、bundle audit、event_study。11 月 18 日行情的來源觀察與首次進入研究版本時間均在 11 月 19 日，未回填至交易日。兩個原版本的 immutable 檔案逐 hash 核對相符。

- 重播腳本、各市場 CLI 擷取報告、兩日行情及研究輸出位於 `local/private/real-history-2026-11-19/`。從新目錄執行 `PYTHONPATH=. python local/private/real-history-2026-11-19/extend.py`，首次執行 exit 0。該腳本要求各市場目的地 `with-prior/` 尚未存在；重跑須在該來源目錄副本進行。已完成的研究版本時間與 ID 取自當次實際執行。
- 核對 `result.json`、各市場 `with-prior/events.json` 及其輸入。兩市場各一個既有事件、各兩檔股票、各四筆已保存日期事實。既有事件入口在每市場各判出一個第 1 筆收盤價變動與一個第 1 筆量比的 `observed`。第 5／20 筆均為 `insufficient_data`，三個營收曆月 horizon 均為 `pending`。
- 上述是首次保存口徑與原報告可重讀的證據。價量數值可比性仍待 P1-02，且不能由兩日樣本判定公司行為涵蓋、多日行情連續性或六條規則的研究品質。[09／10 的原始缺口](research-market-gaps-2026-11-18.md)

## P2-03、P1-03～05 的真實原始輸入

九個官方資料集均標有政府資料開放授權條款第 1 版及免費資源。目錄網頁採正常閱覽定位。本機 HTTP 用戶端抓取詮釋頁回 403 並保留原結果。另依目錄明列的 CSV 資源各讀取一次，九個資源均 HTTP 200。以 UTF-8 BOM 相容及嚴格 CSV 讀取，重新計算每份原件 SHA256，逐筆核對欄寬。這一步只確認已有可重用的輸入，市場範圍、單位、真實獨立財報或籌碼抽檢仍依各票執行。

| 資料集 | CSV 資料列 × 欄數 | 日期語意及用途 |
| --- | ---: | --- |
| [TPEx 除權除息計算結果](https://data.gov.tw/dataset/11633) | 1 × 21 | 日期 2026-11-19；逐欄覆核僅日期非空，可辨識個股事件 0 筆。另見[價格區間與真實個案](../../docs/PRICE_ACTION_REVIEW.md) |
| [上市一般業綜合損益](https://data.gov.tw/dataset/91998) | 1,053 × 33 | 出表 1151119、115 年第 3 季 |
| [上櫃一般業綜合損益](https://data.gov.tw/dataset/94853) | 891 × 33 | 同期；逐市場各自適配 |
| [上市一般業資產負債](https://data.gov.tw/dataset/94831) | 1,053 × 26 | 同期，與金融業 schema 分開 |
| [上市金融業資產負債](https://data.gov.tw/dataset/94829) | 10 × 64 | 同期，尚缺保險業、其他產業與報表的驗收 |
| [上櫃三大法人明細](https://data.gov.tw/dataset/11856) | 899 × 25 | 資料日 1151118；有買、賣、淨額欄，須逐欄檢查重疊群組 |
| [上市融資融券餘額](https://data.gov.tw/dataset/11680) | 1,311 × 16 | CSV 無交易日期欄，需取得能綁定同一快照的交易日期證據 |
| [上櫃融資融券餘額](https://data.gov.tw/dataset/11387) | 923 × 21 | 資料日 1151118，單位依欄位及來源逐項查證 |
| [上櫃每日重大訊息](https://data.gov.tw/dataset/18418) | 54 × 9 | 出表 1151119、發言 1151118，含引號內跨行文字，逐行切割會錯算列數 |

私有證據在 `local/private/source-review-2026-11-19/`。目錄讀取的 DNS 與 403 結果分存 `sandbox/manifest.json`、`official/manifest.json`。CSV 的首次 DNS 失敗與實際成功分存 `resource-sandbox/manifest.json`、`official-resources/manifest.json`，可依 ID 找來源 URL、擷取時間、HTTP 狀態、大小、原件及 SHA256。九份 CSV 存於 `official-resources/`，逐檔結構核對存於 `csv-audit.json`。各資料集的欄位定義、獨立參考及研究可比較性仍應在採用前逐票記錄。
