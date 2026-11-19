# 文件中心｜Documentation Hub

[返回專案首頁](../README.md)

文件分開記錄已實作、離線驗證及尚待正式資料驗收的部分；程式碼／實測為實際行為依據。

## 接手與後續開發

| 文件 | 內容 |
| --- | --- |
| [專案交接](HANDOFF.md) | 程式基準、已確認決策、實作與驗證界線、操作入口、接手指令 |
| [最終審查與修復重驗](VERIFICATION-2026-11-17-REVIEW.md) | Standards／Spec、三項修復、490項Python及真實兩市場／三頁重驗；M1仍未全過 |
| [M1本輪整合證據](VERIFICATION-2026-11-17-M1.md) | 當前macOS、真實模型／來源／瀏覽器；09／10未完成、M1未全過 |
| [待開發與驗收清單](DEVELOPMENT_BACKLOG.md) | 優先級、相依項目、完成條件、外部依賴與必要決策 |
| [真實私有研究逐項完成清單](../.scratch/private-research-ready/completion.md) | M1～M6 各原待辦的實測範圍、證據位置與恢復條件 |
| [AI 開發技能](agents/README.md) | Matt Pocock skills、使用流程、本地工作追蹤與更新方式 |

## 使用者

| 文件 | 內容 |
| --- | --- |
| [User Manual](USER_MANUAL.md) | 股票池、搜尋、關聯圖、來源與日期 |
| [前端與私有預覽](FRONTEND_AND_PREVIEW.md) | 索引契約、SHA256、僅本機只讀預覽及限制 |
| [Troubleshooting](TROUBLESHOOTING.md) | 環境、來源、資料與發布排錯 |
| [Glossary](GLOSSARY.md) | 名詞定義 |

## 開發與維運

| 文件 | 內容 |
| --- | --- |
| [System Design](SYSTEM_DESIGN.md) | 需求、設計取捨與驗收 |
| [Architecture](ARCHITECTURE.md) | 元件與資料流 |
| [未裁剪研究事實](RESEARCH_FACTS.md) | 新版bundle保存／稽核及舊版範圍限制 |
| [事件後變化統計](EVENT_STUDY.md) | 價量與營收分開，已保存事件的描述統計，非策略回測 |
| [雙來源研究股票池](RESEARCH_UNIVERSE.md) | TW50＋009816 聯集定義與輸入契約 |
| [Data Model](DATA_MODEL.md) | SQLite 與 JSON |
| [Developer Guide](DEVELOPER_GUIDE.md) | uv、測試、提交流程 |
| [私有研究與觀察歷史](PRIVATE_RESEARCH.md) | 自選代碼、數值圖譜、版本、備份與還原 |
| [Data Pipeline](DATA_PIPELINE.md) | 官方快照、正規化與圖譜 |
| [官方盤後行情](MARKET_PRICES.md) | 不依賴指數名單的股價／成交量私有匯入、版本保存 |
| [交易日曆](CALENDAR_COVERAGE.md) · [公司行為與價格](PRICE_ACTION_REVIEW.md) | 查明休市、應開市但缺行情、日曆未知及跨期價格可比性 |
| [Operations](OPERATIONS.md) | 人工更新、驗證、發布與復原 |
| [Security & Licensing](SECURITY_AND_LICENSING.md) | 資料權利與私密資訊界線 |
| [研究歷史與整包稽核](RESEARCH_HISTORY.md) | 本機版本清單、價量／營收提醒差異與完整性檢查 |
| [財務抽檢](FINANCIAL_REVIEW.md) | 獨立快照數值核對、單位／期別／報表範圍防護 |
| [Roadmap](ROADMAP.md) | P0–P4 與未解依賴 |

## 來源與驗證紀錄

| 文件 | 內容 |
| --- | --- |
| [官方來源](DATA_SOURCES.md) | 逐資料集核對 |
| [季報匯入](QUARTERLY_STATEMENTS.md) · [資產負債](QUARTERLY_BALANCE.md) · [現金流](QUARTERLY_CASHFLOW.md) | 按報表、產業、期間及欄位查看已核對尺度與原始定位 |
| [法人](INSTITUTIONAL_TRADING.md) · [融資融券](MARGIN_TRADING.md) · [重大訊息](ANNOUNCEMENTS.md) | 來源條件、私有 CLI、實際市場與可查核的歷史版本 |
| [官方新聞與產業分類](NEWS_AND_INDUSTRY.md) | 私有新聞索引、兩市公司產業依據與逐來源使用範圍 |
| [候選來源評估](SOURCE_REVIEW_2026-11-16.md) | 009816／TW50、富邦、FinMind、Yahoo |
| [台灣50權利詢問（暫緩）](TW50_LICENSE_INQUIRY.md) | 保留未確認的使用範圍，不要求現在寄信 |
| [2026-11-15 本地驗證](VERIFICATION-2026-11-15.md) | 前次 69 項離線測試及界線 |
| [2026-11-16 前端整合驗證](VERIFICATION-2026-11-16-FRONTEND.md) | 全部 Python、前端、HTTP 與瀏覽器測試 |
| [2026-11-16 行情模組驗證](VERIFICATION-2026-11-16-MARKET.md) | 39項新測試及私有SQLite流程，不是正式端點驗收 |

新使用者先看手冊；新開發者先看設計、架構、研究股票池、開發指南；資料維護者先看來源與授權，再看管線及維運。舊的單一 TW50 指令仍有相容性，雙來源以研究股票池文件為準。

[本地程式入口](../local/README.md) · [既有發布註記](../local/UPDATE_AND_PUBLISH.md)

> 公開金融資料仍為示範；來源篩選可用不代表真實名單已核准或正式下載成功。名單先暫緩，不阻塞行情等獨立模組。沒有啟用排程／自動金融資料發布。

本輪驗證：[私有研究整合（2026-11-16）](VERIFICATION-2026-11-16-RESEARCH.md)。

## 新增：價量／月營收提醒

- [研究提醒規則、設定與操作](RESEARCH_ALERTS.md)
- [完整本地驗證紀錄（2026-11-16）](VERIFICATION-2026-11-16-ALERTS.md)

前一輪本地驗證：[歷史版本與品質檢查](VERIFICATION-2026-11-16-HISTORY.md)。

歷史驗證：[事件後描述統計（2026-11-16）](VERIFICATION-2026-11-16-EVENTS.md)。

2026-11-19 的開發分支已實測兩市場的[交易日曆](VERIFICATION-2026-11-19-CALENDAR-REVIEW.md)、[行情通知](VERIFICATION-2026-11-19-MARKET-NOTICE-REVIEW.md)、[季度三表](VERIFICATION-2026-11-19-M3-FINANCIALS-REVIEW.md)與[四個來源家族合併研究](VERIFICATION-2026-11-19-M3-SOURCE-REVIEW.md)。M1 行情逐欄定義與獨立參考仍缺，各里程碑的其餘驗收條件見[完成清單](../.scratch/private-research-ready/completion.md)。
