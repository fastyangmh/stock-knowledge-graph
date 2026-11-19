# 季度現金流量表的私有核對筆記

`local.quarterly_cashflow` 讀取一份人工核對筆記，將營業、投資、籌資活動的現金淨額、現金及約當現金的期初、期末餘額及本期淨變動送入私有研究。兩份已覆核的季報都列一至九月合併累計數，單位為新台幣仟元。每一欄取自現金流量表，保留原數與正負號。期初與期末餘額標為 `point_in_time`，另存 `instant_date`；流量保留 `period_start`、`period_end` 與 `report_basis=cumulative`。兩日間的匯率變動亦會影響本期淨變動。[季報匯入](QUARTERLY_STATEMENTS.md)

## 來源與 2026-11-19 核對

| 市場及類別 | 核對報表 | 私有工程與數值結果 |
| --- | --- | --- |
| 上市一般業 | 台積公司 2026Q3，中文印刷頁 8～10、英文頁 7～9，當年度前九月欄。公司條款提供個人非商業閱覽。[中文原表](https://investor.tsmc.com/sites/ir/financial-report/2026/TSMC%202026Q3%20Consolidated%20Financial%20Statements_C.pdf) · [英文譯本](https://investor.tsmc.com/sites/ir/financial-report/2026/TSMC%202026Q3%20Consolidated%20Financial%20Statements_E.pdf) · [條款](https://www.tsmc.com/english/legal_and_trademark) | 兩個語言版本的 6 欄相符。另讀先前發布之簡明表的前九月新台幣百萬元欄，換算後以零容差比較，6 欄均有非零差異；保留各欄差額。該表另列第三季單季與美元欄。[簡明現金流量表](https://investor.tsmc.com/schinese/encrypt/files/encrypt_file/qr/phase4_reports/2026-10/e18db1d00f041c8d37a90dedbcb150518d8277d9/FS.pdf) |
| 上櫃一般業 | 環球晶圓 2025Q3，中文及英文印刷頁 7、7-1，前九月欄。發行人網站標示保留權利。[中文原表](https://www.sas-globalwafers.com/wp-content/uploads/2025/11/GlobalWafers_2025Q3-consolidated-financial-statement_CN.pdf) · [英文譯本](https://www.sas-globalwafers.com/wp-content/uploads/2025/11/GlobalWafers_2025Q3-consolidated-financial-statement_EN.pdf) · [來源頁](https://www.sas-globalwafers.com/en/investor/financial-information_en/) | 兩個語言版本的 6 欄相符。另用同年第二季報表現金流量表第 7-1 頁覆核同一年初餘額，1 欄零容差相符。2026Q3 中文原表在此次閱覽失敗，故有核對結果的期間為 2025Q3。[第二季原表](https://www.sas-globalwafers.com/wp-content/uploads/2025/05/GlobalWafers_2025Q2-consolidated-financial-statement_EN.pdf) |
| 上市金融／保險、上櫃金融／保險 | 各組均未完成現金流量表核對 | 尚缺每組具體公司、原件使用範圍、逐欄定位及另一份原始資料的覆核。其他業別、公司與期間也待查。 |

中英版是同一發行人的同一份財報，兩份筆記可檢出抄錄或欄位選錯。另行發布文件共比對 7 欄，1 欄完全相符、6 欄仍有差額。兩家各有 6 筆數值經 SQLite、展示裁剪上限 0、研究事實及 bundle audit 驗證。兩份報表的期末減期初也各與表列淨變動相符。

證交所說明自 2019Q1 起採 iXBRL，財務比較平台的現金流可呈現各季累計數。本次未核實可封存整批公司檔案的逐資源授權，保留為來源候選。另找到台積公司提交 SEC 的同季 6-K；SEC 說明允許重用 EDGAR 公開申報。自動核准審查拒絕本次下載，理由為未明確授權該筆金融原件的下載，未取得可驗雜湊的 SEC 原件。本次來源限於發行人原表的目視核對筆記；官方原件封存仍待驗。[證交所 iXBRL](https://www.twse.com.tw/zh/listed/xbrl.html) · [比較平台說明](https://mopsfin.twse.com.tw/terms) · [SEC 6-K 附件](https://www.sec.gov/Archives/edgar/data/1046179/000104617926000801/a2026q3consolidatedreport-.htm) · [SEC 再利用說明](https://www.sec.gov/about/webmaster-frequently-asked-questions)

## 私有筆記與重播

檔案格式 `issuer-cashflow-notes-v1` 必須含 `schema_version`、四碼字串 `symbol`、`period_end`、含時區的實際核對時間 `observed_at`，以及依中文、英文順序排列的兩個 `editions`。各版以 `url` 指定上述完整原始網址，在 `context` 獨立記錄該版的 `period_start`（當年 1 月 1 日）、`period_end`、`report_basis=cumulative`、`statement_scope=consolidated`、`unit=TWD_thousands`。在 `cells` 為每一個以下的鍵提供 `{"locator":"印刷頁、期間欄及科目","raw_value":"(1,234)"}`。這個數字僅示範括號負值。正式資料只保留在私有目錄。

| 欄位鍵 | 現金流量表項目 |
| --- | --- |
| `operating_cash_flow`、`investing_cash_flow`、`financing_cash_flow` | 三類活動各自的淨現金流入或流出 |
| `opening_cash_equivalents`、`closing_cash_equivalents` | 期初、期末現金及約當現金餘額 |
| `net_change_cash_equivalents` | 本期現金及約當現金淨增減 |

`-`、`--`、`N/A` 代表筆記中的缺值，兩次核對都缺時記入 `metadata.missing_values`，零會生成數值事實。遇到不同報表、不同數值、缺少定位、全欄無數或結構改變，匯入會中止。私有原始筆記應連同單獨保存的 SHA256 一起留存，重播時逐次驗證。數字的證據標記為 `manual_transcription`，`note_sha256` 指向筆記。發行人原表只正常閱覽；原表 bytes、全文或影像皆未保存。文件節點只含自行撰寫的筆記標題、來源及股票對應。

從專案根目錄重跑本輪兩家公司，目的地使用新目錄。

```bash
evidence=local/private/m3-cashflow-2026-11-19/reviewed
uv run --locked python "$evidence/replay.py" local/private/cashflow-recheck
```

個別重建一家公司時，使用筆記完成當時留存的 checksum。日期採筆記實際核對時間，研究 ledger 自行記錄首次登錄時間。CLI 會保全既有不同內容的輸出；兩份同時觀察衝突時，研究拒建新版本並保留上一份可稽核的 bundle。衝突觀察仍留在 ledger，需核對矛盾後以獨立 ledger 重建。本次未取得聲明更正或撤回的真實現金流報表。

```bash
evidence=local/private/m3-cashflow-2026-11-19/reviewed
run_dir=local/private/cashflow-2330
uv run --locked python -m local.quarterly_cashflow \
  --notes "$evidence/2330-notes.json" --sha256 "$(cat "$evidence/2330-notes.sha256")" \
  --output "$run_dir/normalized.json"
uv run --locked python -m local.research --input "$run_dir/normalized.json" --symbols 2330 \
  --history-db "$run_dir/ledger.db" --output-root "$run_dir/runs" --analysis none
uv run --locked python -m local.bundle_audit --root "$run_dir/runs"
```
