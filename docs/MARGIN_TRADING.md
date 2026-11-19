# 上櫃融資融券的私有研究與核對

`local.margin_import` 從已保存的收據與 CSV 建立單日研究輸入。TPEx 11387 於 2026-11-19 取得的全檔列出 11 月 18 日的 923 筆證券。每檔有 17 個數值欄、名稱及次一營業日狀態備註。資料由證金公司及自辦信用證券商提供，櫃買中心彙總。個別券商的相同欄位僅涵蓋該券商，跨市場及跨機構的比較仍須確認母體。[上櫃資料集與授權](https://data.gov.tw/dataset/11387) · [TPEx 報表及備註說明](https://www.tpex.org.tw/zh-tw/mainboard/trading/margin-trading/transactions.html)

| 來源欄位 | 研究意義與單位 |
| --- | --- |
| 資買、資賣、現償 | 融資當日買進、賣出、現金償還。各存來源原數值 |
| 券賣、券買、券償 | 融券當日賣出、買進、現券償還。券賣增加餘額，券買及券償減少餘額 |
| 前資餘額、資餘額、前券餘額、券餘額 | 這一交易日報表所載的前日與本日餘額。前日欄保留在本報表的交易日，過去版本仍可重讀 |
| 資屬證金、券屬證金 | 兩方餘額中屬證金的部分，已包含於相應餘額 |
| 資限額、券限額、資券相抵 | 各自的額度及資券相抵數，分別保存 |
| 資使用率、券使用率 | `percent`，保留原公布的小數。限額非零時以餘額除以限額乘 100 比對，容許誤差小於 0.01 個百分點。限額為零時保留該格明示的使用率並略過除法 |

櫃買中心的 EDIS S23 規格第 38 頁區分仟股及百分比。11387 CSV 本身缺少數量單位與商品別欄位，且格式和 S23 不同。兩個使用率已依原欄名、S23 及單日全表的比例尺核對。其餘 15 欄以 `unit=source_reported` 保存，相關原數值可逐格稽核。換成股、張、貨幣或外推到其他商品，仍需資料集及商品的尺度證據。[TPEx 收市後交易資訊格式說明，S23](https://www.tpex.org.tw/storage/regular_system/%E6%96%B0%E7%89%88%E6%94%B6%E5%B8%82%E5%BE%8C%E4%BA%A4%E6%98%93%E8%B3%87%E8%A8%8A%E6%A0%BC%E5%BC%8F%E8%AA%AA%E6%98%8E%28V1.33%E7%89%88%29.pdf?t=20251127)

## 已驗收的範圍

| 來源與組合 | 實測與待查事項 |
| --- | --- |
| TPEx 11387，11/18 | 923 列、21 欄均通過，1,846 個融資／融券餘額算式吻合。1,684 個非零限額的使用率可核算，另外 162 格限額為零。這是同一原件的結構與算術檢查 |
| TPEx 私有研究 | 兩檔四位數自選股票各 17 格比對原 CSV、SQLite 及 audit 後的事實。相同收據重跑兩版，ledger 維持一個 normalized 快照。產業非原表分類，其他日期與商品尚未真實驗收 |
| 同日同範圍的獨立參考 | 目前可計入的獨立核對欄數為 0。單一證金公司、市場總計、同一來源的重編碼報表，各自的母體或產製來源與此要求有別 |
| TWSE 11680 | 目錄所列免費 CSV 適用政府資料開放授權第 1 版，但 1,311 檔、16 欄都沒有交易日期。目錄所連結的 OpenAPI 個股資料亦無日期欄。CLI 收到 `--market TWSE` 會拒絕產生研究資料 |
| TWSE 附日期 MI_MARGN 報表 | 11/18 日期可在 JSON 根及資料表標題定位。與 CSV 比對全部個股及 16 欄後只有 17 列完全相同，另有 6,725 處是 CSV 空白、JSON 明載零。兩者同源，沒有證據可把日期、零值及開放 CSV 的授權一律套到另一表示。報表亦區分交易單位、市場融資金額及次營業日限額 |

上市 CSV 的日期及個股尺度、指定日期 JSON 可否作為長期研究來源、上櫃同日獨立資料、真實修正及撤回均待驗。[上市開放資料](https://data.gov.tw/dataset/11680) · [上市日期報表](https://www.twse.com.tw/exchangeReport/MI_MARGN?response=json&date=20261118&selectType=ALL) · [證交所使用條款](https://www.twse.com.tw/zh/terms/use.html)

## 操作及故障時的狀態

選用實際出現在已存上櫃原件內的四位數代號，範例以 `1000` 示意。以政府開放資料條款授權的 CSV 為輸入，來源、提供者、署名、使用限制及市場隨研究版本保存。registry 僅登記已核對的離線原件。

```bash
uv run --locked python -m local.margin_import --market TPEX \
  --manifest local/private/source-review-2026-11-19/official-resources/manifest.json \
  --trade-date 2026-11-18 --symbols 1000 --output local/private/margin/example.json
uv run --locked python -m local.research --input local/private/margin/example.json \
  --symbols 1000 --history-db local/private/margin/ledger.db \
  --output-root local/private/margin/runs --analysis none
uv run --locked python -m local.bundle_audit --root local/private/margin/runs
```

收據 URI、HTTP 狀態、CSV 媒體型別、起訖時間、bytes 與 SHA256 均須相符。逐列檢查資料日期、欄名順序、欄數、代號唯一性與數值。若任何數值欄空白、格式漂移、算術失衡、指定日期不符或選股缺列，匯入失敗並保留上一個成功檔案。明載的零保留為數字。每筆數值事實附來源欄名、CSV 邏輯列號、雜湊與擷取時間。備註作為股票文件內容保存，來源發布時刻未知時以收據時間記錄其觀察依據。

對同一交易日的後續收據使用新的 normalized 檔名，再登錄原 ledger。較晚接收的修訂各有新的雜湊，較早版本可由 `--known-at` 重讀。同時相衝突的修訂會回滾；研究使用登錄時間與來源可得時間的較晚者。指定交易日只比對來源所載日期，不以收據日期推定。

## 重跑驗收

合成測試入口為 `uv run --locked pytest -q local/tests/test_margin_import.py`。候選 `701949c` 以 macOS arm64／Python 3.11 執行 `uv run --locked python -m local.check --frontend`，exit 0，569 個 Python tests、325 個 subtests、55 個 Node tests 通過。此票未變更前端，未另做瀏覽器驗收。

同候選已依下式重播 11/18 原件，兩份 bundle 均通過 audit。重跑使用新的目的目錄。私有 `candidate/summary.json` 記錄候選版、逐份收據時間及雜湊、比較計數；`candidate/cells.json` 逐檔列出原件列、欄、原始文字、研究數字與單位，便於人工複查。原件與個股讀數存於私有目錄。

```bash
uv run --locked python local/private/m3-margin-2026-11-19/replay.py \
  --source-root local/private/source-review-2026-11-19 \
  --dest local/private/m3-margin-2026-11-19/replay-new
```

## 收據與歷史重播

v2 私有輸入在 `source_csv_b64` 保存原始 CSV bytes。研究與 bundle audit 會核對收據並從原件重算所選投影，按 normalized SHA 保存於 bundle 的 `chips/`。舊 v1 可讀，會標示 `legacy_chip_projection_only`；原件逐格重算需重新執行來源匯入。[M3 04～07 雙軸審查與組合重播](VERIFICATION-2026-11-19-M3-SOURCE-REVIEW.md)
