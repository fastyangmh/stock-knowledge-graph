# 財務資料抽檢與數值比對

[文件中心](README.md) · [資料來源](DATA_SOURCES.md) · [歷史版本稽核](RESEARCH_HISTORY.md)

## 本工具做什麼

`local.financial_review`比較兩份**分別準備的正規化金融快照**，產生逐股票／指標／期別差異與來源證據。它不自動認定其中一份是真的，不下載財報，不改寫SQLite，也不把抽檢當成完整財務審計。

`--reference`可由研究者將合法取得的官方公告／財報獨立對照整理為既有normalized JSON契約。它不是要求把目前待確認的官方季報API當成已驗收的來源，也不會從PDF自動辨識數字。

## 指令

```bash
uv run --locked python -m local.financial_review \
  --input local/private/normalized-watchlist.json \
  --reference local/private/independent-reference.json \
  --symbols 2330 2317 \
  --output local/private/financial-review.json
```

代碼只是參數格式示例，不是成分股證明或投資建議。兩份檔案均須符合既有`research_history.validate_payload`契約，包含stocks、sources、financial_metrics與metadata.observed_at；每筆指標需要source_id及available_at。只檢查指定股票，未指定範圍不能宣稱已抽檢。

## 比對規則

配對鍵是`stock_id,metric,period_end,period_type`。不同期別不湊在一起；同鍵有多來源時標記ambiguous_sources，不自行取平均或挑數值。

- **單位與幣別**：字串必須一致，金額必須有已確認的 currency。不在抽檢階段換算幣別、元／千元；`source_reported`、空值或unknown即使數字相同，也列為unit_unverified。
- **月／季度／年度定義**：需要`statement_scope`（consolidated或separate）與`report_basis`（single_period、cumulative或point_in_time）。不同合併範圍、累計／單期不得直接比較；缺欄位標記statement_definition_unverified。
- **數值精度**：使用Decimal比較已提供的數值，不用二進位浮點相減製造誤差；但無法還原上游曾經丟掉的精度。
- **容許誤差**：預設絕對與相對誤差均為0。選用`--absolute-tolerance`與`--relative-tolerance`時，門檻與公式會寫入報告；相對值以小數比例表示（0.01 = 1%），不是百分點。

公式：`abs(input-reference) <= max(absolute, relative * max(abs(input), abs(reference)))`。

## 結果分類

`equal`／`within_tolerance`表示在**已宣告相同定義**下數值相符；`value_mismatch`表示超過設定差距。其餘包含缺資料、來源不唯一、單位或幣別不一致、報表定義不明或不同等，不視為自動通過。

報告保留兩側數值、資料時間、來源URL、正規化內容及原始輸入bytes的SHA256。若某指定股票在兩檔都沒有金融紀錄，明確列入stocks_without_financial_records，不能用「比較0筆」冒充成功。

Exit code：**0** = 指定範圍都相符；**2** = 報告已生成但仍需人工審閱；其他非0／exception = 檔案或設定有錯。輸出必須在私有路徑，禁止覆寫任一來源；預設最多20,000個比較鍵，超限停止。

## 還沒完成的部分

此工具完成的是獨立抽檢的工程入口，**不是季度／年度財報API全量介接**。真實欄位、金額倍率、最新修訂與公告時間仍要以對應官方文件核對，並保存實際取得的快照。比對結果不能重建從未保存的歷史修訂，也不構成回測或投資有效性證明。

## 有證據的月營收單位版本（2026-11-17）

`official_import --unit-evidence <private.json>` 可選用 `official-monthly-twd-v1`。
預設匯入仍保留 `source_reported`；此選項只轉換 manifest 明列的來源、股票及月份。
每個決策綁定被測 CSV 的 SHA256，並要求可重讀且 SHA256 相符的獨立參考 bytes、
HTTPS URL 與定位文字。參考是人工核對的主張，雜湊不會自動證明金融正確性。

```json
{
  "schema_version": "financial-unit-evidence-1.0",
  "normalization_version": "official-monthly-twd-v1",
  "decisions": [{
    "source_id": "twse_monthly_revenue",
    "stock_id": "TW:1000",
    "period_end": "2026-10-31",
    "raw_snapshot_sha256": "<被核對原始CSV的64位SHA256>",
    "raw_unit": "TWD_thousands",
    "currency": "TWD",
    "statement_scope": "consolidated",
    "report_basis": "single_period",
    "references": [{
      "path": "independent-statement.pdf",
      "sha256": "<參考檔案的64位SHA256>",
      "url": "https://example.org/independent-statement.pdf",
      "locator": "頁碼、表名、公司與月份；此例為格式示意"
    }]
  }]
}
```

參考路徑相對 manifest，不能跳出其目錄；manifest 與參考總讀取預算 32 MiB，
最多 1,000 個決策、每個最多 10 個參考。不接受重複、未使用、錯誤 raw hash、
不支援的版本／幣別／尺度／期間，缺證據不換算。公司無子公司時官方採個別申報，
所以不得把整個市場預設為 consolidated。

金額要求來源為精確整數仟元，轉成整數元（`unit=TWD`、`currency=TWD`），
增率保留 percent 及原數字。每筆保留 `raw_value`、`raw_unit`、
`normalization_version`、倍率、raw CSV hash、manifest hash 與參考定位；
raw bytes 不改寫。`statement_scope` 與 `consolidation`、`report_basis` 與
`value_basis` 一一對應；兩名稱同時出現卻不同時，驗證／抽檢／研究即拒絕。

**遷移採獨立 ledger 與輸出目錄。** 新尺度 metadata 有版本；`record_snapshot`
按來源檢查正規化定義；兩市場月營收共用一份版本政策。換成不同的月營收尺度或無版本舊資料時，登錄會中止。其他來源（例如季度三表）可加入相同 ledger。[月營收與季報混合重播](QUARTERLY_STATEMENTS.md#月營收與季報共用研究版本)
使用新 `--history-db`、`--output-root` 重新產生研究；不要更改 observed_at 或
available_at 來迴避同時衝突，不修改原 ledger 或 bundle。
新版本記錄原擷取時間，本地首次登錄時間仍為現在，不能倒填為早已知道。

抽檢 `financial-review-1.1` 對金額要求已知幣別，對月／季／年都要求已知 scope/basis；
缺失或 unknown 定義不通過。兩側 normalization_version 必須相同，包含一側缺失的情況；
獨立 reference 只有在確實整理成同一定義時才可標同版，逐筆來源 hash 不充當版本鍵。
事件分析與營收趨勢提醒同樣區分版本／scope/basis，未知幣別金額不可計算。

### 容差必須按指標拆分

CLI 的絕對容差適用該次全部比較列。金額及百分比分別準備僅含對應 financial_metrics
的 input/reference，分次執行；不可用 500,000 元容差同時接受錯誤增率。
預設 0 的報告先保存；有顯示精度證據後才另產生容差報告，不覆蓋原差異。

本輪四檔、兩市場、2026-10 的原始 CSV 與獨立官方 HTML 查詢核對，金額 4 筆零差；
8 筆百分比因 HTML 截至小數二位，以 0.01 **百分點**容差核對。
企業 IR 補充比對另採其已顯示精度：整數百萬元為 500,000 元，百分比二位
四捨五入為 0.005 百分點，原始仟元精確值為 0。完整來源與限制見
[本輪驗證](VERIFICATION-2026-11-17-FINANCIAL-UNITS.md)。

`official_import --output` 必須與輸入分離：不得指向原始 snapshot 目錄內、registry、
universe／ETF holdings、`--unit-evidence` manifest 或任何已驗證 reference。
碰撞會在寫入前拒絕，原始證據 bytes 保留；正常正規化輸出另存私有檔案。
