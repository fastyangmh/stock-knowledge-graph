# Stock Knowledge Graph｜股票金融知識圖譜

整合可追溯的金融資料，以本地語意分析、關聯計算與 GitHub Pages 互動圖譜支援 **知識探索 → 異常訊號 → 量化研究**。

**研究原型，公開網站仍為虛構示範資料。** 不是即時行情或投資建議；真實名單、使用權利及公開發布尚未完成。

[展示網站](https://fastyangmh.github.io/stock-knowledge-graph/) · [文件中心](docs/README.md) · [事件後描述統計](docs/EVENT_STUDY.md)

## 系統概覽

```text
核准資料 → Linux/NAS 本地 SQLite → Embedding/Top-K → 有限子圖 JSON
        → 私有預覽／人工核准 → GitHub Pages（main / root）
```

研究股票池為 [臺灣50指數成分股＋009816 ETF 普通股持股聯集](docs/RESEARCH_UNIVERSE.md)，保留來源及日期；不混成同一指數。使用 Python/uv、本地 SQLite、Sentence Transformers 與 Cytoscape.js；目前只手動運行，不啟用每日排程。

**名單確認先暫緩，不阻塞其他開發。** 已新增[官方盤後行情私有匯入](docs/MARKET_PRICES.md)，可指定股票代碼獨立處理價格／成交量，不要求先寄授權詢問信，也不把代碼清單冒稱為正式指數名單。

## 開發驗收

```bash
uv sync --locked --extra dev
uv run --locked python -m local.check
# 安裝 Node.js 的開發環境可一起測前端：
uv run --locked python -m local.check --frontend
```

測試使用隔離的虛構資料，不下載真實名單或推送金融資料。[私有預覽工具](docs/FRONTEND_AND_PREVIEW.md)不會把整個 Repository 當成網站根目錄。

## 研究提醒（初版）

已加入[價量＋月營收獨立研究提醒](docs/RESEARCH_ALERTS.md)：在私有研究指令加 `--alerts`，分開顯示門檻、比較基準與來源證據；資料不足不補零，不合成總分，也不產生買賣指令。

## 本機研究歷史與品質檢查

[研究版本稽核／歷史比較](docs/RESEARCH_HISTORY.md)可查看已儲存版本、比較兩類提醒與展示圖譜；[財務抽檢](docs/FINANCIAL_REVIEW.md)可核對獨立正規化資料，拒絕混用未知尺度及不同報表定義。均為本機私有工具，不改公開資料。

## 文件目錄

接手開發先讀 [交接文件](docs/HANDOFF.md)；可執行任務、相依關係與完成條件見 [待開發與驗收清單](docs/DEVELOPMENT_BACKLOG.md)。

| 使用與設計 | 資料與維運 |
| --- | --- |
| [User Manual](docs/USER_MANUAL.md) | [資料模型](docs/DATA_MODEL.md) |
| [System Design](docs/SYSTEM_DESIGN.md) | [資料處理管線](docs/DATA_PIPELINE.md) |
| [Architecture](docs/ARCHITECTURE.md) | [來源／使用條件](docs/DATA_SOURCES.md) |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | [安全／資料授權](docs/SECURITY_AND_LICENSING.md) |
| [雙來源股票池](docs/RESEARCH_UNIVERSE.md) | [部署與維運](docs/OPERATIONS.md) |
| [前端篩選／私有預覽](docs/FRONTEND_AND_PREVIEW.md) | [台灣50授權詢問（暫緩）](docs/TW50_LICENSE_INQUIRY.md) |
| [常見問題](docs/TROUBLESHOOTING.md) | [Roadmap](docs/ROADMAP.md) |
| [術語表](docs/GLOSSARY.md) | [前端整合驗證](docs/VERIFICATION-2026-11-16-FRONTEND.md) |
| [不依賴名單的盤後行情](docs/MARKET_PRICES.md) | [行情模組驗證](docs/VERIFICATION-2026-11-16-MARKET.md) |

全部文件及歷史驗證紀錄見 [docs/README.md](docs/README.md)。真實雙來源名單及公開使用範圍保留為獨立待辦；技術測試通過不代表正式來源下載、資料品質或公開發布已驗收。

## 不等待名單的私有研究流程

[公司／月營收＋行情＋修訂歷史＋備份操作](docs/PRIVATE_RESEARCH.md)已提供 `local.official_import --symbols` 與 `local.research`。自選代碼不推定指數歸屬；只產生新私有研究版本，不改公開金融資料。價量與月營收提醒已依選定的雙類別方案實作；完整回測仍在後續規劃，不把研究提醒當成買賣訊號。
