# 上櫃股票市場日曆核對｜2026 年 11 月 14 至 17 日

[05 證據票](../.scratch/m2-trading-calendar/issues/05-tpex-evidence.md) · [06 兩市場驗收](../.scratch/m2-trading-calendar/issues/06-real-acceptance.md)

以臺北日期計，上櫃股票市場 11 月 14、15 日休市，16、17 日開市。每週交易時段、年度例外及事後交易紀錄均來自適用於上櫃的來源。本次只判定該日有無股票交易，日內有無中斷、盤後時段及交割另需證據。

| 臺北日期 | 星期 | 人工預期 | 核對依據 |
| --- | --- | --- | --- |
| 2026-11-14 | 六 | 休市 | 上櫃一般交易制度限週一至五，115 年表未安排該日交易。櫃買中心 11/16 新聞稿指明前一交易日期為 11/13 |
| 2026-11-15 | 日 | 休市 | 同一週末，落在 11/13 與 11/16 兩個相鄰上櫃市場收盤日之間 |
| 2026-11-16 | 一 | 開市 | 年度表無假日；櫃買中心新聞稿記載當日收盤。兩份封存的上櫃個股日成交查詢均有當日正成交筆數 |
| 2026-11-17 | 二 | 開市 | 年度表無假日；兩份個股日成交查詢均有當日正成交筆數，且與 M1 私有研究保存的行情交易日期一致 |

## 年度安排與例外

- 櫃買中心於 2025-11-03 以證櫃交字第 11400754581 號公布 **115 年有價證券櫃檯買賣市場**開休市表，依據為金管會函及櫃買中心業務規則第 41 條。附表第 1 頁分列各交易系統。股票交易系統春節前最後交易日為 2/11，2/12、13 僅給付結算。國際債券及債券處所議價另有日期。第 2 頁的 10/26 與 12/25 之間沒有 11 月的特別安排。[115 年公告](https://www.tpex.org.tw/storage/eb_data/11411/11400754581.html) · [115 年附表](https://dsp.tpex.org.tw/storage/eb_data/11411/114007545811-1.pdf)
- 上櫃交易系統簡介列週一至週五為交易時段。2026-11-09 起施行的業務規則版本，第 41 條明文採銀行休假日，櫃買中心如需變更，可報主管機關核定。可封存的年度依據為金管銀國字第 11402721521 號公報第 4 頁，適用西元 2026 年，未列此區間為銀行假日。銀行局開放資料集 119737 這次取得的 CSV 只有 2027、2028 年列，已排除於日曆判定。[上櫃交易制度](https://www.tpex.org.tw/zh-tw/mainboard/trading/rules/system.html) · [業務規則第 41 條](https://www.selaw.com.tw/Chinese/LawDetail/LawArticleReference?lawDataid=16866976) · [金管會年度公報](https://gazette.nat.gov.tw/EG_FileManager/eguploadpub/eg031125/ch04/type3/gov36/num7/Eg.pdf) · [銀行局資料集](https://data.gov.tw/dataset/119737)
- 第 42 條規範不可抗力停市及恢復交易的公告。天然災害措施壹、一另區分臺北市全體公教機關全日、上午與下午停班對股票交易系統的影響。人事總處歷次紀錄於 11/19 查得最新事件為 10/24，這只補充天然災害查核。另核對 11/16 櫃買中心新聞稿與兩檔成交日期。四日內無需取代原排定狀態。11/17 發文的新年度公告適用 116 年。此處未建立全年度的公告更正史。[業務規則第 42 條](https://www.selaw.com.tw/Chinese/LawDetail/LawArticleReference?lawDataid=16866978) · [天然災害措施](https://www.selaw.com.tw/SFIWebSeLaw/Chinese/LawDetail/LawArticleReference?lawDataid=15280592) · [人事總處歷次紀錄](https://www.dgpa.gov.tw/informationlist?uid=374) · [市場公告查詢](https://www.tpex.org.tw/zh-tw/announce/market/announce.html) · [11/16 櫃買市場新聞稿](https://www.tpex.org.tw/storage/about_otc_news/2026/11/1794822408819_1054_news.pdf) · [116 年公告](https://dsp.tpex.org.tw/web/announcement/announcement_detail.php?content_file=MTE1MDA4MDM4NzEuaHRtbA%3D%3D&content_number=MTE1MDA4MDM4NzE%3D)

## 可重播的證據與時間

私有資料夾 `local/private/m2-calendar/05/` 內的 `manifest.json` 記錄九份原件各自的版本／定位、URL、取得、首次保存、SHA256、大小與用途。另列僅供閱覽的 TPEx 來源。封存與讀取範圍如下。

| 來源 | 證據與使用範圍 |
| --- | --- |
| 金管會 115 年銀行假日公報、銀行局 CSV | 保存官方原件；公報提供公開下載，CSV 依資料集第 1 版政府資料開放授權及顯名條件。採用公報 PDF 第 4 頁 |
| 證基會法令查詢所載櫃買中心第 41、42 條與天然災害措施 | 保存三份版本化條文頁供私有覆核。頁尾列明轉載須有提供單位正式書面授權 |
| 人事總處歷次停班公告目錄 | 保存有序目錄第一頁與取得時間，依政府網站資料開放宣告註明出處。[使用條件](https://www.dgpa.gov.tw/archive?uid=75) |
| 櫃買中心交易制度與兩檔個股日成交查詢 | 校驗後複用 11/18 既有私有原件；此次未重新下載。個股日期僅佐證實際交易，未匯入研究版本。[原私有來源核對](../.scratch/private-research-ready/research-market-gaps-2026-11-18.md) |
| 櫃買中心 115 年附表、11/16 新聞稿、116 年公告 | 以官方頁面閱覽定位，未另存原始 bytes 或宣稱有對應 SHA256。主站使用條款第 5、7 節規範自動下載與轉載，未將開放行情的權利延伸至網站文件。Web 開啟主站公告 HTML、年度查詢頁、公告資料下載列表及開放指數 CSV 回報 403，已停止這些讀取。[TPEx 使用條款](https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html) |

11/19 經正常 HTTPS 保存六份原件，取得時間為 **01:55:55 至 01:55:58 UTC**。curl 返回後記為本地取得及保存時間。另三份既存原件保留 11/18 原始寫入時間及本次複製時間。發文有日期無時刻者僅記日期。六筆首次沙箱 DNS 失敗另存 `sandbox-attempt/retrieval.json`。

審閱版本為 `tpex-bounded-review-20261119-1`。`calendar.json` 的 `market-calendar-1` 綁定八份適用原件，限四個明列日期。每個條目的審閱保存時間為 **2026-11-19T01:59:27.678376Z**。主要交易制度條目含四日判定，另七份條目參與原件校驗並供定位。樣本未設定行情應到時刻。

| 私有檔 | SHA256 |
| --- | --- |
| `manifest.json` | `3b6d7472e784d1a0b55dfe942b717cbef1796773d695c67ac13f1633ec105ee1` |
| `expected.json`，逐日人工預期 | `86a14a2fd5e6b6adfa496302fb7475c0012de0d32488360714832a15d1d9d3e7` |
| `calendar.json`，四日報告輸入 | `42067a75f1baf42ce803690a20aa7e617cacc937e330db15fd809e9ee907898c` |
| `replay-01.json`，01 候選的報告 | `4cbc98f2f770c93591104ae64a40ca04a2250b2010a981fb79e68cf8f321fd52` |

## 離線驗證

2026-11-19 以 macOS、鎖定環境 Python 3.11.11，在 01 候選 `e7f50b8c14736e69ec30b2b071c194557352b2b6` 的獨立原始碼副本重播。以下為整合工作區在同版本的命令。私有驗證腳本以 macOS PDFKit 從已封存公報重新抽取第 4 頁，檢查法條、週規、兩檔實際成交日期和各原件雜湊。

```bash
packet=local/private/m2-calendar/05
.venv/bin/python -m local.calendar_coverage \
  --root local/private/m1/review-fixes/acceptance/tpex/runs \
  --market tpex --symbols 6488 8069 --calendar "$packet/calendar.json" \
  --start 2026-11-14 --end 2026-11-17 --as-of 2026-11-19T02:00:00Z \
  --output "$packet/replay-01.json"
.venv/bin/python "$packet/verify.py" "$packet/replay-01.json"
```

三個 CLI 情境皆 exit 0。四日報告與人工預期全數相符；外推至 11/13 和 11/18，兩個邊界日皆為未知；截止提早至 01:59:27Z，四日皆為未知。僅在暫存副本變更公報一個位元組後，原件校驗失敗，CLI exit 2 並保留舊報告。命令及 hash 見 `replay-verification.json`、`rejected.json`。初次執行來源檢核時 `calendar.json` 尚未建立，exit 1；封存後九份 hash 及人工預期檢核 exit 0。

本票完成 TPEx 四日日期證據。所選兩股在 M1 研究範圍只保存 11/17 一日，11/16 查詢中的成交紀錄僅供日曆佐證。個股停牌、無成交、延遲到檔及 5／20 日完整行情未經此真實樣本驗證。02、03 整合後由 06 另驗；本票未執行完整產品套件或行情單位審閱。
