# 05 · 融資融券觀察

**Parent:** [P1-04](../../../docs/DEVELOPMENT_BACKLOG.md#p1-04籌碼資料) · [規格](../spec.md)

**What to build:** 將來源明載的日流量與餘額、資與券分開保存，產生可重讀的市場別研究事實。

**Blocked by:** 無其他 M3 子票。真實交付依賴逐來源可用性、範圍與使用條件；來源撤回的正式串接依賴 P2-04。

**Status:** needs-info

- [x] 不得把融券賣出當融資買進或把餘額當淨額。以零、缺值、同日修正、錯日期與股票不在來源覆蓋範圍驗證。
- [x] 私有 CLI 的合成輸入走 SQLite、研究版本與 audit，驗證缺失、格式改變、同時衝突及故障保全。數值保持為數值，文字保留來源與股票映射。
- [ ] 真實採用的每一組市場／產業均保存官方原件、欄位定位、取得時間、版本與獨立核對證據；清楚列出尚未支援的組合。每份資料的使用範圍分開記錄。
- [x] 儲存可重跑程序及去敏摘要，以原 backlog 條件評定整體狀態。只有工程通過時將真實證據另列待驗。

查證起點：[上市](https://data.gov.tw/dataset/11680) · [上櫃](https://data.gov.tw/dataset/11387)

## TWSE 交易日與來源表示的核對

政府目錄的 CSV 無日期欄。2026-11-19 另對同一 MI_MARGN 報表的官方日期查詢送出一次 `date=20261118`，回應根日期 20261118、資料表標題亦為 115 年 11 月 18 日。CSV 與日期查詢各有 1,311 檔、16 欄，按代號、欄組及數字千分位全列對照。17 檔在保留空值語意時完全相同。其餘差異共 6,725 格，皆為 CSV 空白、JSON 數字零；此結果提供日期與格式的查核線索。兩者同源，不納入獨立抽檢，不將所有空白擅自轉零。另核對金融商品單位、欄組與例外，並用獨立或來源明示的日期及尺度驗收。[政府資料集](https://data.gov.tw/dataset/11680) · [官方同日日期表示](https://www.twse.com.tw/exchangeReport/MI_MARGN?response=json&date=20261118&selectType=ALL)

私有根目錄 `local/private/source-review-2026-11-19/`，原 CSV 在 `official-resources/11680.response`，同範圍日期查詢在 `margin-date-representation/11680.response`，兩份 manifest 含 HTTP 狀態與 hash，核對計數見 `margin-date-match.json`。

## 2026-11-19 實作與驗收

已交付 TPEx 11387 的離線匯入、上櫃兩檔各 17 格的 SQLite／audit 逐格重播、錯日期及同時修訂等合成回歸。兩市場所用的收據各自保留。上市 CSV 的日期綁定、上櫃數量尺度、同日同範圍的獨立參考仍待查。候選、完整測試數、重跑方法與市場適用範圍見[融資融券驗收](../../../docs/MARGIN_TRADING.md)。

本票的審查修復與最新組合重驗見[四來源驗收](../../../docs/VERIFICATION-2026-11-19-M3-SOURCE-REVIEW.md)。待驗條件沿用上表。
