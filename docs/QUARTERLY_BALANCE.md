# 期末資產負債表的私有研究

`local.quarterly_import` 可從下列四個政府資料集選取股票、建立季度期末存量。每份來源各自固定 ID、CSV URL 和完整欄名。研究事實附原值、欄名、資料列位置、原件 SHA256、出表日及取得時間。期末按來源民國年度及季別換算曆季季末，`report_basis=point_in_time`。合併或個別範圍及金額單位須由發行人原始報表逐欄確認。每股參考淨值保留原欄，未自行推算。[季度 CLI 及核對檔契約](QUARTERLY_STATEMENTS.md)

## 市場、產業及使用範圍

四個目錄的提供機關均為金融監督管理委員會證券期貨局，個別列有政府資料開放授權條款第 1 版與免費 CSV。本專案將原件和研究結果保存在本機私有目錄並保留署名。公司財報另依發行人條件閱覽，保存核對所需的單項數值、範圍及頁碼。[政府資料開放授權條款](https://data.gov.tw/license) · [來源保存與使用邊界](SECURITY_AND_LICENSING.md)

| 官方目錄 | 已映射之六欄 | 2026 Q3 原件及範圍 |
| --- | --- | --- |
| [上市一般業 94831](https://data.gov.tw/dataset/94831) | 資產總計、負債總計、權益總計、歸屬於母公司業主之權益合計、每股參考淨值、流動資產 | 1,053 家有代號，26 欄。保留此來源的政府資料開放授權與取得紀錄。 |
| [上櫃一般業 91967](https://data.gov.tw/dataset/91967) | 同六欄 | 891 家，26 欄。以自己的資源 URL、授權與取得紀錄匯入。 |
| [上市金融業 94829](https://data.gov.tw/dataset/94829) | 同前五欄，另取貼現及放款－淨額 | 10 家，64 欄。僅採本金融業 CSV 所附條件與銀行業表頭。 |
| [上市保險業 94833](https://data.gov.tw/dataset/94833) | 同前五欄，另取保險合約資產 | 5 家，57 欄。僅採本保險業 CSV 所附條件與保險業表頭。 |
| [上櫃金融業 91965](https://data.gov.tw/dataset/91965) | 待驗 | 原件只有出表日及無代號空列，總額欄措辭與上市不同。CLI 拒絕該 ID。 |
| [上櫃保險業 91969](https://data.gov.tw/dataset/91969) | 待驗 | 先前正常取得資源回 403，缺原件及對應公司。CLI 拒絕該 ID。 |

金控、證券與其他業別留待取得相應原件和獨立財報。空格或缺值標記保存於 `metadata.missing_values`；研究版本只列當次可用的數值。獨立核對接受 `point_in_time`；累計與單季流量會在匯入時被拒絕。重跑用原件取得日排序，核對資訊依實際審閱時間加入；同時來源衝突須釐清，既有研究版本可繼續稽核。

## 2026-11-19 私有驗收

從四份原件選五家公司，重算原件 SHA256，經私有 CLI、SQLite ledger、研究版本與 bundle audit。展示節點上限設為零。30 個選取欄位共保存 28 筆數值、2 個原始缺值。以下為最後一次核對狀態。

| 來源 | 研究事實 | 與獨立財報零容差相符 | 未核對、缺值及保留紀錄 |
| --- | ---: | --- | --- |
| 上市一般 | 12 | 台積及聯發科兩份合併財報的期末流動資產、資產、負債、總權益與母公司權益，共 10 筆 | 兩家每股參考淨值待核。聯發科最初採用整數百萬元之業績發表資料，資產按倍率換算仍失配；另以正式合併財報仟元數覆核。原先的失配及後來的核對各有不可變研究版本。[台積公司 PDF 第 4 頁](https://investor.tsmc.com/sites/ir/financial-report/2026/TSMC%202026Q3%20Consolidated%20Financial%20Statements_E.pdf) · [聯發科合併財報印刷第 4～5 頁](https://www.mediatek.com/hubfs/MediaTek-Assets/Pdfs/Financial%20Reports/2026/Q3%20Consolidated%20Report.pdf) |
| 上櫃一般 | 6 | 環球晶合併財報期末資產 1 筆 | 其餘 5 筆待核。[環球晶合併財報第 4 頁](https://www.sas-globalwafers.com/wp-content/uploads/2026/05/GlobalWafers_2026Q3-consolidated-financial-statement_CN.pdf) |
| 上市金融 | 5 | 高雄銀行個別財報期末資產、負債、權益共 3 筆 | 2 筆待核，歸屬母公司權益欄空白。[銀行季報印刷第 4 頁](https://www.bok.com.tw/zh/-107?_com_khb_announcearea_AnnounceListN_INSTANCE_dsew_fileID=1301958&p_p_cacheability=cacheLevelPage&p_p_id=com_khb_announcearea_AnnounceListN_INSTANCE_dsew&p_p_lifecycle=2&p_p_mode=view&p_p_resource_id=download&p_p_state=normal) |
| 上市保險 | 5 | 旺旺友聯個別財報期末資產、負債、權益共 3 筆 | 2 筆待核，歸屬母公司權益欄空白。[保險公司季報印刷第 4 頁](https://www.wwunion.com/wp-content/uploads/2026/11/115Aud-Report-Q3.pdf) |

17 筆已核實為新台幣仟元，11 筆仍為 `source_reported`。每股欄雖可與金額欄區分，這次抽樣尚缺可直接核對的每股數值。兩份早期核對檔與原件索引見[歷次發行人抽檢](../.scratch/m3-evidence-sources/issuer-reference-2026-11-19.md)。其他期間、全體發行人與正式撤回紀錄尚待取得。

產品候選 `f458b81` 在 macOS arm64／Python 3.11.11 上執行 `uv run --locked python -m local.check`，544 個 pytest、301 個 subtests 通過，exit 0。相同候選重新跑四份原件及後續詳表，五個研究版本全數通過 audit；未支援的兩個 ID 均 exit 2，沒有建立輸出。完整檢查報告在 `local/private/m3-balance-2026-11-19/offline-check.json`，對應私有原件重播在同目錄的 `committed-run/`。本輪未另測前端或 Linux／NAS。

## 重播

原件及來源 manifest 位於 `local/private/source-review-2026-11-19/{official-resources,sectors-official}/`，發行人核對檔及重播程式位於 `local/private/m3-balance-2026-11-19/`。重播腳本的第一步建立全新目的地，第二步將上市一般業覆核加入同一 ledger，然後再次稽核兩個保存版本。

```bash
evidence=local/private/m3-balance-2026-11-19
destination=local/private/m3-balance-fresh
uv run --locked python "$evidence/replay.py" "$destination"
uv run --locked python "$evidence/review_detail.py" "$destination"
```

單一資料集可直接用標準入口。以下沿用上述首次重播產生的上櫃一般業核對檔。

```bash
archive=local/private/source-review-2026-11-19/sectors-official
run_dir=local/private/quarterly-balance-91967
uv run --locked python -m local.quarterly_import --manifest "$archive/manifest.json" \
  --dataset 91967 --symbols 6488 --review "$destination/91967/review.json" --output "$run_dir/input.json"
uv run --locked python -m local.research --input "$run_dir/input.json" --symbols 6488 \
  --history-db "$run_dir/ledger.db" --output-root "$run_dir/runs" --analysis none
uv run --locked python -m local.bundle_audit --root "$run_dir/runs"
```
