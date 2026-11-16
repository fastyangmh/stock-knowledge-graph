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

- **單位與幣別**：字串必須一致。不換算幣別、元／千元；`source_reported`、空值或unknown即使數字相同，也列為unit_unverified。
- **季度／年度定義**：還需要`statement_scope`（consolidated或separate）與`report_basis`（single_period、cumulative或point_in_time）。不同合併範圍、累計／單期不得直接比較；缺欄位標記statement_definition_unverified。
- **數值精度**：使用Decimal比較已提供的數值，不用二進位浮點相減製造誤差；但無法還原上游曾經丟掉的精度。
- **容許誤差**：預設絕對與相對誤差均為0。選用`--absolute-tolerance`與`--relative-tolerance`時，門檻與公式會寫入報告；相對值以小數比例表示（0.01 = 1%），不是百分點。

公式：`abs(input-reference) <= max(absolute, relative * max(abs(input), abs(reference)))`。

## 結果分類

`equal`／`within_tolerance`表示在**已宣告相同定義**下數值相符；`value_mismatch`表示超過設定差距。其餘包含缺資料、來源不唯一、單位或幣別不一致、報表定義不明或不同等，不視為自動通過。

報告保留兩側數值、資料時間、來源URL、正規化內容及原始輸入bytes的SHA256。若某指定股票在兩檔都沒有金融紀錄，明確列入stocks_without_financial_records，不能用「比較0筆」冒充成功。

Exit code：**0** = 指定範圍都相符；**2** = 報告已生成但仍需人工審閱；其他非0／exception = 檔案或設定有錯。輸出必須在私有路徑，禁止覆寫任一來源；預設最多20,000個比較鍵，超限停止。

## 還沒完成的部分

此工具完成的是獨立抽檢的工程入口，**不是季度／年度財報API全量介接**。真實欄位、金額倍率、最新修訂與公告時間仍要以對應官方文件核對，並保存實際取得的快照。比對結果不能重建從未保存的歷史修訂，也不構成回測或投資有效性證明。
