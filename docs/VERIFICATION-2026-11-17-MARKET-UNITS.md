# 行情單位抽檢與相容性驗證（2026-11-17）

本紀錄屬 ticket 09／P1-02。**工程驗證已執行，真實單位與交易範圍驗收未完成。** 公開 `data/`、既有06／07原始檔與研究版本未修改；未啟用交易、排程、付費或發布。

## 實作與測試範圍

開發基準 `34b707f`，獨立分支 `task/pr-09`；整合基準與最終 source hashes 記於私有 `local/private/m1/09/`。本次採使用者核准的 macOS arm64／Python 3.11 鎖定環境；不宣稱 Linux／NAS 已驗收。使用 `/private/tmp/skg-venv`、`/private/tmp/skg-uv-cache`，`TMPDIR=/private/tmp`。

新增 `local.market_review` 公共 CLI／私有報告、可選 snapshot-bound `market-unit-review-1.0` 審閱定義及 `market-units-2.0` record；舊預設保留。market_graph 的 raw 重建與完整事實 audit 讀取舊／新格式，提醒及事件隔離不同市場定義。

TDD 於已核准的 ingest／read_prices／research→audit／market_review CLI／提醒與事件 seams 執行。私有 red 日誌分別顯示缺少 unit_review 參數、缺少 market_review、跨幣別／股張／範圍／版本仍錯誤計算、symbol 未綁定、舊 facts 注入 currency 未拒絕、同 raw reference 被誤當相符；之後新增最小修復。合成回歸保留每股7欄、精確小數、差異、預設誤差0、零比較、未知單位、缺參考、參考檔篡改、原始綁定、舊新版讀回及完整 bundle audit。

初次完整 `uv run --locked python -m local.check --report local/private/m1/09/check.json`：exit 0，**470 passed、212 subtests passed**，包含 compileall、Python、示範資料驗證與 SQLite pipeline。網路下載及既有 loopback 測試經正常 sandbox escalation 執行；未改權限政策。最終整合後重驗見本節後續紀錄。未修改前端，本票未另跑瀏覽器；不將舊瀏覽器結果當本票驗證。

## 真實官方證據與未完成原因

實際取得 HTTPS bytes、時間、Content-Type／headers、SHA256 與URL，保存 `reference-manifest*.json`；原始引用不提交。以06的2330／2454、07的6488／8069及交易日2026-11-17作抽樣，產品讀者重驗各來源既存CSV hash。

| 查詢 | 已觀察事實 | 驗收界線 |
| --- | --- | --- |
| [TWSE STOCK_DAY 個股查詢](https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20261117&stockNo=2330) | 兩股當日7欄共14個原始數字和06相符；當次 JSON notes 僅含一般交易，排除零股、定價、鉅額、拍賣、標購 | bulk CSV 沒有同一範圍註記；數字相等不能證明其範圍。後取 HTML notes 已變成含一般／零股／定價，證明不可套用一個固定全天範圍 |
| [TPEx 個股日成交資訊](https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html) | 實際JSON兩股僅列到11/16；成交張數、成交仟元，不含鉅額的查詢註記 | 不能改成11/17、不能把張／仟元直接當股／元；也不是既有no1430的範圍證明 |
| [TPEx OpenAPI](https://www.tpex.org.tw/openapi/) 的 tpex_mainboard_quotes | 獨立下載回應日期也是1151116；原始Date保留 | 11/17正式report列 missing_reference，不補昨日 |
| [TPEx no1430 HTML](https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=htm&d=115/11/17&se=EW) | 明示不含定價、成交股數、成交金額(元)；兩股7欄共14數字和07相符 | 同一路徑的另一表示，不當成獨立驗收；尚未證明零股／鉅額涵蓋範圍與價格幣別 |

`numeric-diagnostics.json` 保存28個原始數字的零差額（誤差0），每筆均 `definition_verified: false`、`acceptance: not_passed`，**accepted_fields=0**。其中TPEx14欄只是同資料不同表示診斷，不算獨立核對。正式 `market_review` 產物為 TWSE `definition_unverified: 14`、TPEx `missing_reference: 14`，兩個命令 exit 2、`compared_fields: 0`、`needs_review: true`。這是如實呈現未完成，不能用拒絕比較本身宣稱P1-02通過。

尚需：取得TPEx同日且同no1430範圍的獨立官方參考，逐來源查明 bulk 的一般／盤後定價／盤中及盤後零股／鉅額範圍，並取得明確價格與成交值幣別證據。確認後才以當次 raw hash／日期／股票建立審閱定義，重新產生獨立新版DB、research與audit。未擷取歷史、公司行為還原及多日穩定性也未驗收。

私有證據路徑：`local/private/m1/09/`，含 capture/reconcile 程序、原始參考、兩市場 reference／review、診斷、red 日誌、完整 check 及 source/evidence hashes。`commands.json` 保存可重跑CLI與實際exit code；重抓官方網址可能得到不同時段bytes，應建立新快照，不覆寫本次證據。
