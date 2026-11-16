# 文件中心｜Documentation Hub

[返回專案首頁](../README.md)

文件分開記錄已實作、離線驗證及尚待正式資料驗收的部分；程式碼／實測為實際行為依據。

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
| [雙來源研究股票池](RESEARCH_UNIVERSE.md) | TW50＋009816 聯集定義與輸入契約 |
| [Data Model](DATA_MODEL.md) | SQLite 與 JSON |
| [Developer Guide](DEVELOPER_GUIDE.md) | uv、測試、提交流程 |
| [Data Pipeline](DATA_PIPELINE.md) | 官方快照、正規化與圖譜 |
| [Operations](OPERATIONS.md) | 人工更新、驗證、發布與復原 |
| [Security & Licensing](SECURITY_AND_LICENSING.md) | 資料權利與私密資訊界線 |
| [Roadmap](ROADMAP.md) | P0–P4 與未解依賴 |

## 來源與驗證紀錄

| 文件 | 內容 |
| --- | --- |
| [官方來源](DATA_SOURCES.md) | 逐資料集核對 |
| [候選來源評估](SOURCE_REVIEW_2026-11-16.md) | 009816／TW50、富邦、FinMind、Yahoo |
| [台灣50權利詢問](TW50_LICENSE_INQUIRY.md) | 尚未取得的使用範圍 |
| [2026-11-15 本地驗證](VERIFICATION-2026-11-15.md) | 前次 69 項離線測試及界線 |
| [2026-11-16 前端整合驗證](VERIFICATION-2026-11-16-FRONTEND.md) | 全部 Python、前端、HTTP 與瀏覽器測試 |

新使用者先看手冊；新開發者先看設計、架構、研究股票池、開發指南；資料維護者先看來源與授權，再看管線及維運。舊的單一 TW50 指令仍有相容性，雙來源以研究股票池文件為準。

[本地程式入口](../local/README.md) · [既有發布註記](../local/UPDATE_AND_PUBLISH.md)

> 公開金融資料仍為示範；來源篩選可用不代表真實名單已核准或正式下載成功。沒有啟用排程／自動金融資料發布。
