# 新增候選資料來源核對｜2026-11-16

[文件中心](README.md) · [既有官方來源](DATA_SOURCES.md) · [資料使用規範](SECURITY_AND_LICENSING.md)

> 本次是來源文件與介面範圍核對，不是下載全量金融資料或完成 adapter 驗收。未更動研究股票池、來源白名單、依賴或公開 data/。法律適用範圍仍應依實際條款／權利人回覆確認，不能將可讀取視為全面可再散布。

## 1. 009816 ETF 持股不是原定 TW50 指數成分股

使用者提供的 [籌碼小宇 009816 頁面](https://xiaoyu-etf.pages.dev/etf/009816) 是第三方彙整的 **凱基台灣TOP50 ETF 持股快照**；查閱時持股資料日期為 2026-11-13。這不是有生效起訖日期的 TW50 歷史名單。

[凱基投信官方基金頁](https://www.kgifund.com.tw/Fund/Detail?fundID=J023) 及 [證交所 ETF 頁](https://www.twse.com.tw/zh/ETFortune/etfInfo/009816) 確認，009816 追蹤的是 **臺灣指數公司特選臺灣TOP 50指數**。[該指數頁](https://taiwanindex.com.tw/indexes/IX0230) 與原定 [臺灣50指數 TW50](https://taiwanindex.com.tw/indexes/TW50) 是不同的指數定義。即使某日持股重疊，也不能以一者代替另一者的完整歷史成分股。

**待使用者決策：維持 TW50，或改採「009816 ETF 持股研究池」。** 後者需要明確名稱與來源日期、持股快照留存及適用的自動取得／公開使用範圍，不能冒稱正式 TW50 名單。對第三方網站的自動擷取與再利用權利本次尚未確認，也不據此推論必然需付費。

## 2. 股價與成交量：官方盤後開放資料優先，富邦作選配

[政府資料集 11549：上市個股日成交資訊](https://data.gov.tw/dataset/11549) 列有每日開高低收、成交股數、成交金額、成交筆數等欄位，資料集標示免費及政府資料開放授權條款第1版。**建議先核對此資料集對應官方資源及實際回應**，符合本專案盤後手動更新目標；歷史範圍、交易量口徑與修訂仍需實測。本次沒有啟用下載器或新增白名單。

[富邦 Web API](https://www.fbs.com.tw/TradeAPI/docs/market-data/http-api/getting-started/) 可提供日內、快照及歷史行情；官方範例要求登入帳號、密碼及憑證後取得行情權限。[歷史 K 線文件](https://www.fbs.com.tw/TradeAPI/docs/market-data/http-api/historical/candles/) 與 [速率限制](https://www.fbs.com.tw/TradeAPI/docs/market-data/rate-limit/) 應按端點與方案核對，不假設有無限歷史資料。

[富邦使用規範](https://www.fbs.com.tw/TradeAPI/docs/market-data/intro/) 涉及向第三人傳送及交易資訊使用限制，並指出其成交值／成交量不含零股與鉅額交易。因此：**有行情帳號不等於能將數據或任意衍生內容放上公開 Pages**；先確認使用與展示權利、單位及成交範圍。富邦帳號僅是候選方案，不推定使用者已持有帳戶；不收集或提交帳號、憑證及 Token。

## 3. TWSE／TPEx 財務 API：按報表和產業拆分

使用者指定的兩個操作不是全市場所有財報的單一 API：

| 操作 | 官方定義 | 注意 |
| --- | --- | --- |
| TWSE `/opendata/t187ap06_L_ins` | 上市公司綜合損益表（保險業） | 不涵蓋一般業、銀行／金融業及金控業所有表格 |
| TPEx `/mopsfin_t187ap07_O_ci` | 上櫃公司資產負債表（一般業） | 不是上市損益表，也不是月營收端點 |

官方依據：[TWSE API 文件](https://openapi.twse.com.tw/)、[TWSE OpenAPI schema](https://openapi.twse.com.tw/v1/swagger.json)、[TPEx API 文件](https://www.tpex.org.tw/openapi/)、[保險業損益資料集 92000](https://data.gov.tw/dataset/92000)、[上櫃一般業資產負債資料集 91967](https://data.gov.tw/dataset/91967)。後兩筆資料集標示政府資料開放授權條款第1版；不能據此概括所有行情或其他介面的權利。

建議建立 `市場 × 報表種類 × 產業類別` 的 adapter 路由，財務指標保留合併／個體、期末／期間、當季／累計、幣別與倍率資訊。月營收保留既有專用來源；一般業、銀行、金控、保險等財報以各自 schema 適配。

可達性限制：本次直接開啟 TPEx Swagger UI 回應 403，官方搜尋索引仍能讀到上述操作名稱與資料集 metadata。這只能確認文件範圍，**不代表 API 請求或下載成功**；不得繞過存取限制。

## 4. FinMind：可列備援／交叉核對，不等同公開資料授權

[FinMind Repository](https://github.com/FinMind/FinMind) 提供股價、財務、籌碼等資料介面。此次核對 [LICENSE](https://github.com/FinMind/FinMind/blob/master/LICENSE) 為 **Apache-2.0 軟體授權**；它不等於 API 資料及原始財報文件可自由公開。

依 [FinMind 資料授權說明](https://finmind.github.io/Disclaimer/) 與 [方案說明](https://finmind.github.io/Pricing/)，服務使用、商業使用、對外展示與再散布要分別核對；原始資料轉售／鏡像、即時資料對外呈現及券商分點資料另有限制。**先作候選備援與私有品質核對，不預設公開 JSON 能輸出全部 FinMind 內容。** 未申請方案、付款、要求 Token 或新增專案依賴。

## 5. Yahoo：優先評估 RSS，不直接爬新聞全文

[使用者提供的 RSS 索引](https://tw.stock.yahoo.com/rss-index) 及 [RSS 說明](https://tw.stock.yahoo.com/rss-help) 的官方搜尋索引仍提供個股／分類訂閱資訊；本次直接開啟頁面得到 404，**尚未驗證實際 feed XML 可用**，不能據此斷言服務永久終止。

[Yahoo 服務條款 RSS 段落](https://legal.yahoo.com/tw/zh-hant/yahoo/terms/otos/index.html) 與 RSS 說明要求保留來源、文章連結及提供內容，不得擅自改寫提供的內容，並有非商業／產品特定條件。先評估保留原題、來源、原文連結與發布時間的新聞索引；**不要擷取全文或推定自動摘要、Embedding 衍生公開服務已取得權利**。RSS 文章不能取代公司重大訊息的官方公告來源。

## 6. 真實資料抽檢與修訂策略（開發計畫，尚未實作）

- 抽樣涵蓋不同產業及季度；以同公司、同報表、同期間、同合併範圍與相同版本的官方公告／財報核對。
- 核對數值、貨幣、元／千元倍率、零與空值、當季與年初累計、公告／擷取時間。價格資料另外核對還原／未還原及交易量口徑。
- 避免新值覆寫唯一歷史：保留原始快照 checksum、`retrieved_at`、`source_published_at`（未知保持未知）、`revision_id`、`supersedes` 等版本資訊。
- 抽檢可評估當次轉換正確性，不能重建之前未保存的修訂歷史；新版官方數值不能直接當作歷史回測當時已知數值。

上述版本欄位是後續 schema 設計建議，不表示目前 SQLite 已有完整雙時間版本功能。

## 7. 本次變更與下一步

本次只新增文件並更新文件索引：沒有下載金融資料全集、執行有憑證的 API、建立爬蟲、改變股票池或公開資料。建議先推進已可逐筆核對的官方盤後價格與財報介面；009816／TW50 股票池差異則先請使用者確認，再決定名單 adapter，避免沿用錯誤標籤與歷史。

使用者另提供的 ChatGPT 分享頁未能在本次工具中讀取，沒有把未讀內容當成實作證據或授權文件。
