# 上市一般業季報原始參考核對

P1-03。2026-11-19 正常閱覽兩家公司分別公布的 2026 年第 3 季合併報表，對照政府開放資料 91998、94831 的同一股票與 2026 年第 3 季。兩份上市一般業 CSV 已取回、封存及驗證 SHA256。[官方快照索引](../private-research-ready/source-samples-2026-11-19.md)

| 公司與原始定位 | 零容差結果 | 限制 |
| --- | --- | --- |
| 台積公司合併財務報表英文版 PDF 第 4～6 頁，9 月 30 日資產總計、前九月營收與基本 EPS | 三欄皆與原 CSV 相符。報表的金額單位為新台幣仟元，EPS 為新台幣元／股 | 只確認此公司此份合併報表以上三個欄位，前三季累計營收與第三季單季營收有不同欄位。[公司合併財務報表](https://investor.tsmc.com/sites/ir/financial-report/2026/TSMC%202026Q3%20Consolidated%20Financial%20Statements_E.pdf) |
| 聯發科技第 3 季財務報表 PDF 第 2～3 頁，前九月營收、基本 EPS 與期末資產總計 | EPS 相符。兩個金額欄在套用報表明示之百萬元／仟元倍率後仍有非零差異，保留兩筆失配 | 公司公告表列整數百萬元，須取得可核至仟元的同一期間正式報表或明確捨入依據後再驗。[公司財務報表](https://www.mediatek.com/hubfs/MediaTek-Assets/Pdfs/Quarterly%20Earnings%20Release/2026/Quarterly%20Earnings%20Release-2026Q3/%E8%B2%A1%E5%8B%99%E5%A0%B1%E8%A1%A8.pdf) |

兩份公司原始報表均採閱覽及記錄必要核對值，保存的私有摘要包含原始定位與政府 CSV 雜湊。公司 PDF 未作為可再發布或可索引全文的來源。[台積公司使用條款](https://www.tsmc.com/chinese/legal_and_trademark) · [聯發科技使用條款](https://www.mediatek.com/terms-of-use)

私有核對程式與結果位於 `local/private/source-review-2026-11-19/issuer-sample.py`、`issuer-view-comparison.json`。六筆比較四筆完全相符、兩筆金額不相符。第一次以目錄欄名「資產總額」核對時，程式因原 CSV 欄名為「資產總計」而中止，改用原件精確欄名後完成。程式 exit 0 表示比較已執行。此抽樣未驗其他產業、其他欄位、現金流量表及上櫃樣本；公司原始 PDF 的封存權利亦須分別處理。[M3 規格與各來源票](spec.md)

## 兩市場的產業欄位與空列

另依政府目錄指向的七個 CSV，各請求一次。七個資源皆 HTTP 200；重算原件 SHA256，並用 CSV 讀者核對公司代號、期別及資料列。此次私有原件與 metadata 在 `local/private/source-review-2026-11-19/sectors-official/`，結構核對在 `sectors-audit.json`。下列數量為有公司代號者；產業 schema 不可互套。

| 來源與官方定位 | 有代號筆數 | 欄數 |
| --- | ---: | ---: |
| [上櫃一般業資產負債表](https://data.gov.tw/dataset/91967) | 891 | 26 |
| [上市金融業綜合損益表](https://data.gov.tw/dataset/91995) | 10 | 25 |
| [上市保險業綜合損益表](https://data.gov.tw/dataset/92000) | 5 | 26 |
| [上市保險業資產負債表](https://data.gov.tw/dataset/94833) | 5 | 57 |
| [上櫃金融業綜合損益表](https://data.gov.tw/dataset/94850) | 0 | 25 |
| [上櫃金融業資產負債表](https://data.gov.tw/dataset/91965) | 0 | 64 |
| [上櫃保險業綜合損益表](https://data.gov.tw/dataset/94855) | 0 | 26 |

有代號者均為民國 115 年第 3 季。最後三檔各有一列無公司代號、無季別，須保留原件並回報沒有可用觀察，不能以空列驗收產業。上櫃保險業資產負債表的官方資源回 403，本次未封存該資源。重新驗收條件是可依授權取得原件且有可核對公司與期別。[上櫃保險業資產負債表](https://data.gov.tw/dataset/91969)
