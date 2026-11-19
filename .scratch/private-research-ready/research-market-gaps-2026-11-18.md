# 09／10 剩餘行情驗收缺口研究（2026-11-18）

本研究只調查官方一手來源；沿用既存 **2026-11-17** 交易日、TWSE 2330／2454、TPEx 6488／8069，不替換被測日期。**09／10 維持 `needs-info`：本研究不是正式行情驗收，沒有新增已通過欄位，沒有建立已確認的 unit-review。** 即使後續補足文件，也須另建 snapshot-bound、版本化審閱定義，重跑 09 與 10 受影響範圍；不能直接將研究筆記當作閉票證據。

對應 [P1-02 backlog](../../docs/DEVELOPMENT_BACKLOG.md#p1-02單位公告與人工抽檢)；程式核對基準為 `101ce8de6c9fe9de3553e910d28566419a68f1a6`。本輪變更限於本研究筆記及既有 `.scratch/` 入口連結。

## 已縮小的缺口

1. **確定：** 這次正常 HTTPS 取得的 TPEx `tradingStock` 兩股均已有 `115/11/17` 列，`tpex_mainboard_quotes` 快照的 `Date` 也全部為 `1151117`。昨日「參考缺同日資料」在這次觀察已解除；這不證明更新 SLA、未來每日穩定性或同交易範圍。[個股日成交資訊 API（6488）](https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code=6488&date=2026/11/17&response=json)、[8069](https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code=8069&date=2026/11/17&response=json)、[收盤行情 OpenAPI](https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes)。定位、時間與 SHA256 見下方私有 manifest。
2. **確定：** TWSE 同一 `STOCK_DAY` JSON URL／股票／日期的新舊快照，其 `notes[2]` 及量、額、筆數不同；不能拿較晚同日內容代替早期 raw。僅能確認不同取得時點的內容變動，不能僅據此認定變動原因。新下載的 `STOCK_DAY_ALL` 也與原 06 的量、額、筆數不同。[2330 同形態查詢](https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20261117&stockNo=2330)、[2454 同形態查詢](https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20261117&stockNo=2454)、[原 bulk 端點](https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data)。私有診斷為 `diagnostics.json`、`bulk-refresh-summary.json`，不覆寫舊結果。
3. **未知：** TWSE 原 bulk 的逐欄交易型態、明確幣別，以及 TPEx 原 no1430 與獨立同範圍參考的對應，仍缺官方直接證明。數字相等、名稱近似、不同 URL／hash／格式，都不足以證明來源獨立或 scope。[TWSE 資料集 11549](https://data.gov.tw/dataset/11549)、[TPEx 資料集 11371](https://data.gov.tw/dataset/11371)、[TPEx OpenAPI 定義](https://www.tpex.org.tw/openapi/swagger.json)。下一步須補端點與逐欄定義的官方對應，再決定是否適合進入正式 review。

## 證據保存與可重現界線

本次 bytes 全在 `local/private/research-market-gaps-2026-11-18/`（下文簡稱 `R/`）；行情值、全檔及報告不在本筆記重刊。既存證據簡稱 `O/ = local/private/m1/09/`。原 06／07 raw、DB、09 報告、ledger、bundle 與公開 `data/` 均未由研究代理更動。

- `R/manifest.json`：12 筆正常 HTTPS HTTP 200；`R/manifest-more.json`：7 筆 HTTP 200。每筆有精確 URL、UTC 請求時間、取得時間、HTTP status、curl exit、SHA256、bytes、來源日期與 locator；headers 在同名 `.headers`。`requested_at_utc` 是請求開始，`retrieved_at_utc` 以 raw 檔案最後寫入時間記錄，並註明依據，非聲稱來源發布時間。
- 正常下載集中於 **2026-11-18 01:56–01:57 UTC（09:56–09:57 Asia/Taipei）**。首次 sandbox DNS 失敗（curl exit 6／HTTP 000）另存 `manifest-sandbox-failed.json`，之後經正常權限 escalation 成功。未略過 TLS、未改 host／代理或偽造身份。
- Web 工具另開 TPEx 格式 PDF 與交易制度頁時回報 403；停止該路徑，不重試繞過。這兩份 raw 已於該 web 失敗前由正常 curl 取得 HTTP 200；使用既存正常取得 bytes 做離線閱讀。這不表示 403 已被解除。
- `capture.py`／`capture-more.py` 記錄本次 URL 與命令；有拒絕覆寫 body 檢查。重跑須使用新目錄／檔名，不覆寫本次 manifest。`annotate.py` 補日期與定位，`diagnose.py` 做研究診斷；都不是產品 CLI 或正式 review。
- `tpex-format-v1.33.txt` 以 macOS PDFKit (`extract.swift`) 從已下載 PDF 逐頁擷取，含 PDF 頁碼；`twse-a05-1150831.txt` 由 DOCX `word/document.xml` 擷取。文字定位可回原文件核對，沒有安裝依賴或改 lock。
- `R/parent-baseline.json` 由整合代理持有；本研究不改此檔。產品完整測試、正式 `market_review`、research／audit／瀏覽器驗收本輪研究均未執行，不沿用舊綠燈宣稱本輪通過。

## 獨立性分類

| 分類 | 含義 | 本次來源 |
| --- | --- | --- |
| A：同資料另一表示／同端點再抓 | 不算獨立驗收 | no1430 HTML 對原 no1430 CSV；TWSE bulk 再抓 |
| B：不同官方查詢產品，候選獨立參考 | 可以研究交叉查詢，但尚需證明 scope 與資料產製關係；不同 bytes 不是獨立證明 | TWSE `STOCK_DAY` 對 `STOCK_DAY_ALL`；TPEx `tradingStock` 對 no1430 |
| C：同官方 OpenAPI 的另一端點，產製關係未明 | 不能僅憑路徑、JSON／CSV或名稱改變計為獨立 | `tpex_mainboard_quotes`、`tpex_mainboard_daily_close_quotes` 對 no1430；前者與 dataset 11371 名稱／欄位一致，仍缺 lineage 文件 |
| D：官方定義／制度／產品格式文件 | 可支持其明示產品的定義，沒有逐日觀察，不能充當數值參考；也不能跨產品自動套用 | data.gov.tw metadata、Swagger、交易制度、TWSE A05、TPEx S37／S38 |

分類依官方 [TWSE 資料集資源 URL](https://data.gov.tw/dataset/11549)、[TPEx 資料集資源 URL](https://data.gov.tw/dataset/11371)、[TPEx Swagger 的 paths／schemas](https://www.tpex.org.tw/openapi/swagger.json)及實際請求 URL 做研究判讀；不是官方宣稱其後端相互獨立。**本次尚無可正式接受的同範圍獨立參考。**

## TWSE：原 bulk 與較晚同日內容不能混用

| 判定 | 官方來源／定位 | 私有證據／原證據 | 結論與可執行下一步 |
| --- | --- | --- | --- |
| 確定；D | [dataset 11549](https://data.gov.tw/dataset/11549)：主要欄位說明、資源 URL、更新頻率 | `R/twse-dataset.html`；原 06 `prices/latest-twse.json` | 確認原來源為 `STOCK_DAY_ALL?response=open_data`，欄名為成交股數／成交金額／成交筆數等；每日更新不等於最終日結或固定範圍。尚須取得該端點的發布階段與逐欄定義，不能由欄名推定 TWD／一般交易。 |
| 確定；B | [2330 STOCK_DAY](https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20261117&stockNo=2330)、[2454](https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20261117&stockNo=2454)：`data[日期=115/11/17]`、`fields`、`notes[2]` | `O/twse-2330.json`／`twse-2454.json` 與 `reference-manifest.json`；`R/` 同名新檔與 `manifest.json` | 原 JSON 統計註記為一般交易、排除其他型態；新 JSON 統計註記包含一般／零股／盤後定價／鉅額、排除拍賣標購。兩股 OHLC 共8欄相同，量／額／筆數共6欄不同。下一步要求與原 bulk hash 對應的官方說明；不把新 notes 回填原 raw。 |
| 確定；A | [bulk 再抓](https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data)：CSV 日期與2330／2454行 | 原 `local/private/m1/06/prices/latest-twse.json` 所綁 raw；`R/twse-bulk.csv`、`bulk-refresh-summary.json` | 新 bulk 的同一交易日兩股亦8欄相同、6欄不同。這是來源內容變動觀察，不是舊資料錯誤證明，也不證明納入哪類交易。後續若要改驗較晚版本，須明示新驗收範圍並保存舊報告。 |
| 確定；D／跨產品套用僅推論 | [TWSE 每日收盤行情商品](https://eshop.twse.com.tw/zh/product/detail/cfec9a1470e448ec91bfde006db361e8)：商品內容1／4 | `R/twse-eshop.html` | A05 商品列14:00、15:30、17:30三階段；對應一般、加入零股與定價、再加入鉅額，均排除拍賣標購。這支持「官方確有分階段商品」，**沒有證明免費 STOCK_DAY_ALL 與哪個檔案一一對應**。下一步找明確 crosswalk；不訂購商品。 |
| 確定；D／原 bulk 適用性未知 | [A05 格式（115/8/31 生效）](https://eshop.twse.com.tw/uploadFile/upload/8a82e9e69e2fb8c8019eb02ca23600d4.docx)：前言外幣註記、個股欄位表、說明2／3 | `R/twse-a05-1150831.docx`／`.txt` | 文件規定外幣商品按原幣揭露及部分匯總換匯；個股欄位有不同用途的幣別欄。不能把「幣別代碼」一律當所有普通股的報價幣別，不能從有些ETF外幣例外反推 bulk 每列均TWD。下一步需2330／2454普通股報價幣別及該CSV倍率的明確映射。 |
| 未知；D | [集中市場交易制度](https://www.twse.com.tw/zh/products/system/trading.html)：拾貳、交易方式彙總 | `R/twse-trading.html`；原06取得時間14:21:45 Asia/Taipei，原09 JSON約14:41:40 | 一般、盤後定價、零股、鉅額各有時段；原下載時間與完整盤後作業存在時間差只是疑點。不能用時間位置證明 bulk scope。下一步逐欄區分 OHLC 與量／額／筆數的產製規則。 |

**逐欄限制：** 新 `notes[2]` 用的是統計資訊層級描述，沒有逐一說明開／高／低／收是否也包含所有型態。本研究不將它擴張成7欄共同 scope；OHLC 數字一致不證明其涵蓋型態一致。量、額、筆數也須各自確認，不預設三欄一定同時更新。

## TPEx：同日已可取得，但同範圍及獨立性仍不成立

| 判定 | 官方來源／定位 | 私有證據／原證據 | 結論與可執行下一步 |
| --- | --- | --- | --- |
| 確定；A／D | [dataset 11371](https://data.gov.tw/dataset/11371)：資源 URL；[no1430 HTML](https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=htm&d=115/11/17&se=EW)：標題、日期、欄頭 | 原07 `prices/latest-tpex.json` 綁定 no1430 CSV；`O/tpex-no1430.html`；`R/tpex-no1430.html`、`tpex-dataset-11371.html` | 標題明示不含定價，欄頭明示股數及成交金額元；仍缺零股、鉅額、逐欄scope與幣別。HTML是同源另一表示，不計獨立。下一步釐清 no1430 是否只含一般、是否納入盤中或盤後零股。 |
| 確定；B | [tradingStock 6488](https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code=6488&date=2026/11/17&response=json)、[8069](https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code=8069&date=2026/11/17&response=json)：`tables[0].data`、`fields`、`notes[0]` | `O/tpex-6488.json`／`8069.json`僅到11/16；`R/`同名檔有11/17 | 同日兩列已到；根 `date=20261101` 是月查詢日期，不能拿來當個股列交易日。參考量／額欄為張／仟元；註記排除鉅額，未明確解決零股／定價及捨入規則。下一步查官方尺度、捨入及逐欄scope，不直接把張／仟元當股／元。 |
| 確定（數字）；C（獨立性未知） | [tpex_mainboard_quotes](https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes)：`Date=1151117`、`SecuritiesCompanyCode=6488/8069`；[Swagger](https://www.tpex.org.tw/openapi/swagger.json)：同名schema | `O/tpex-quotes.json`為1151116；`R/tpex-quotes.json`／`tpex-swagger.json` | 這次日期到11/17；兩股7欄共14個原始數字與原07相同。schema只列欄位名稱，沒有納入交易型態或產製獨立性說明。下一步確認是否只是no1430資料再發布；在取得證明前不把14相同稱為通過。 |
| 確定（差異）；C | [tpex_mainboard_daily_close_quotes](https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes)、[dataset 11370](https://data.gov.tw/dataset/11370)：上櫃股票行情；Swagger同名schema | `R/tpex-daily-close.json`、`tpex-dataset.html`、`tpex-swagger.json` | 這是相鄰資料集／另一端點，**不是原11371**。快照日期也是1151117，但與原07比較為OHLC共8欄相同、量／額／筆數共6欄不同。下一步取得11370、11371與各OpenAPI的官方scope對照；不得任選數字相同的端點湊過。 |
| 確定（文件本身）；D | [TPEx收市後格式v1.33](https://www.tpex.org.tw/storage/regular_system/%E6%96%B0%E7%89%88%E6%94%B6%E5%B8%82%E5%BE%8C%E4%BA%A4%E6%98%93%E8%B3%87%E8%A8%8A%E6%A0%BC%E5%BC%8F%E8%AA%AA%E6%98%8E%28V1.33%E7%89%88%29.pdf?t=20251127)：PDF20–23頁／印刷19–22頁，S37／S38 | `R/tpex-format-v1.33.pdf`／`.txt` | S37 `STKT1QUOTESN.TXT` 與S38 `STKT2QUOTESN.TXT`（含盤後）分開定義；OHLC與成交金額列元、成交股數列股（S38明列），但未找到與no1430／OpenAPI的直接對應，也不能將元直接視為TWD。下一步找免費端點crosswalk及逐欄型態；不採購收市後資料。 |
| 確定（制度）；D／API映射未知 | [上櫃有價證券交易系統簡介](https://www.tpex.org.tw/zh-tw/mainboard/trading/rules/system.html)：買賣單位與等價成交系統 | `R/tpex-system.html`／`.txt`；原07取得時間14:30:34 Asia/Taipei | 普通整股報價單位為1股、交易單位一般1000股，並有外幣ETF等例外。制度不是月查詢的捨入契約，也不是no1430的型態定義。下一步只在確認適用商品與欄位後使用單位證據。 |

`R/diagnostics.json` 對 TPEx 月查詢的張／仟元乘1000只作**研究假設診斷**，不宣稱可精確還原：兩股OHLC共8欄相同，量／額／筆數共6欄不同。原值與候選值、倍率、差額只存在私有檔；未知捨入與scope時，不擴大 tolerance 消除差異。該診斷及所有其他候選的 `accepted_fields` 皆為0。

## 後續工程／驗收的具體入口

1. 先補來源證據：取得 `STOCK_DAY_ALL` 的發布版本／時段、OHLC與量額筆數各自scope、2330／2454報價及成交值幣別／倍率；取得 no1430 與 TPEx 候選參考的逐欄scope及產製關係。官方商品格式與 metadata 只能作查詢定位；若必須新增付費／契約／憑證才停止請使用者決策。此次沒有寄信或購買。
2. 保留既存11/17 raw作被測樣本；任何新時點快照另存，不能用新終值替換原06／07後保留舊驗收名稱。若後續選新快照當另一輪驗收，明示範圍、日期、時間及hash，舊09失敗結果仍保留。
3. 證據充足後才建立新的 `market-unit-review-1.0` 與獨立reference；審查者需人工確認來源獨立，`market_review` 拒絕相同raw hash的工程保護，不能識別CSV／HTML不同hash其實同源。
4. 目前 `local/market_units.py` 的可確認 scope只有 `regular_only`、`regular_oddlot_afterhours`、`regular_oddlot_afterhours_block`。如果官方最後證明no1430包含零股卻排除盤後定價，或OHLC與量額scope不同，現有單一enum未必能誠實表示。先另做版本化契約修正及回歸，不挑最接近值。這是待證據決定的工程條件，不是本研究已確定no1430含零股。
5. `apply_review` 並非通用張／仟元轉換器；月查詢參考若需尺度轉換，須另存原始decimal、官方倍率及捨入規則、版本與定位。不能把診斷假設直接套入正式紀錄。
6. 再執行兩市場各兩股、非零獨立比較的正式09；保留日期／scope不符、缺參考、不同幣別及raw不一致的拒絕案例。只有真實定義確認與數值比較均通過，才建立全新DB／研究版本並重跑10受影響的research／alerts／audit／compare／event；舊ledger／bundle不靜默遷移。完整來源與金融品質未涵蓋部分仍留backlog。

程式契約定位：`local/market_units.py` 的 `apply_review` 內的 `trading_scope` 白名單、`local/market_review.py` reference與raw驗證；正式驗收入口與原失敗證據見 [2026-11-17行情驗證](../../docs/VERIFICATION-2026-11-17-MARKET-UNITS.md)、[ticket 09](issues/09-market-unit-review.md)、[ticket 10](issues/10-m1-acceptance.md)。上述是建議後續工作，本輪未修改產品或執行正式驗收。

## 可交給來源提供者核對的問題（尚未發送）

- TWSE：免費 `STOCK_DAY_ALL?response=open_data` 的11/17原始快照於14:21:45取得，與 `STOCK_DAY` 各發布階段、A05各檔案有何官方對應？OHLC、股數、金額、筆數分別納入一般、盤中／盤後零股、定價、鉅額哪些型態？價格與成交額如何標示幣別、倍率與修訂時間？
- TPEx：dataset11371/no1430、`tpex_mainboard_quotes`、dataset11370／`tpex_mainboard_daily_close_quotes`、`tradingStock` 是否共用同一資料產製結果？各欄的型態範圍與幣別為何？`tradingStock` 的張／仟元是截斷、四捨五入或精確小數，筆數又涵蓋哪些交易？哪個官方獨立報表可查11/17兩股並提供相同範圍的完整七欄？

這些問題由上述官方API、metadata與格式文件的缺口導出；不假定一般交易規則或付費格式能直接回答免費端點契約，也不要求使用者憑偏好決定金融定義。

## 本輪完成定義

完成官方來源閱讀、19次成功私有擷取、保留12筆sandbox DNS失敗、同日日期核對與私有數字差異診斷；未新增公開行情、名單、排程、交易、付費或聯絡他人。已執行19份manifest檔案hash／HTTP狀態／locator檢核、全部相對Markdown連結存在檢查及 `git diff --check`，均成功；整合代理另核查舊證據不變。**研究已交付，但09／10缺口尚未補足，繼續 `needs-info`。**

整合代理核對結果：870個既存私有證據／公開資料／lock檔案hash全部不變，19份新原始回應hash與bytes/status符合manifest，未追蹤私有檔案，產品程式無差異。四份變更Markdown的40個相對連結有效；私有驗證摘要為 `R/parent-verification.json`。本輪沒有執行產品測試或09／10正式驗收。
