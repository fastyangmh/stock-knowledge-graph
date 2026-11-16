# Stock Knowledge Graph｜股票金融知識圖譜

以股票為中心，整合可追溯的金融資料，透過本地 AI 語意分析與關聯計算，於 GitHub Pages 展示互動式知識圖譜。長期方向為 **知識探索 → 異常訊號 → 量化研究**。

**目前是研究原型：網站仍使用虛構示範資料，不是即時行情，也不構成投資建議。** 真實名單、授權與公開發布尚未完成。

[查看展示網站](https://fastyangmh.github.io/stock-knowledge-graph/) · [完整文件中心](docs/README.md) · [原始碼](https://github.com/fastyangmh/stock-knowledge-graph)

## 系統概覽

```text
經授權的官方資料 → Linux/NAS 本地 CSV/SQLite → Embedding/Top-K
       → 展示子圖 JSON → 人工驗證與 Git Push → GitHub Pages / Cytoscape.js
```

- **本地**：Python + uv、SQLite、Sentence Transformers；保留原始快照與必要歷史資料。
- **網站**：靜態 HTML／CSS／JS／JSON；從 GitHub `main / root` 分支部署。
- **研究股票池**：[臺灣50指數成分股＋009816 ETF普通股持股聯集](docs/RESEARCH_UNIVERSE.md)，去重且保留各自來源與日期，不合併指數定義。
- **更新**：盤後**手動**驗證；尚未啟用每日排程與真實資料發布。

## 快速開始（離線示範測試）

```bash
uv sync --locked --extra dev
uv run --locked python -m local.check
python -m http.server 8000
```

開啟 http://localhost:8000 預覽目前已提交的示範資料。測試不會自動下載官方資料或發布金融資訊。完整操作請看[使用者手冊](docs/USER_MANUAL.md)與[開發者指南](docs/DEVELOPER_GUIDE.md)。

## 文件目錄

**使用與入門**

- [文件中心（全部說明文件索引）](docs/README.md)
- [使用者手冊／網站操作](docs/USER_MANUAL.md)
- [常見問題與排錯](docs/TROUBLESHOOTING.md)
- [術語表](docs/GLOSSARY.md)

**系統設計與開發**

- [System Design｜系統設計與設計決策](docs/SYSTEM_DESIGN.md)
- [Architecture｜技術架構與元件資料流](docs/ARCHITECTURE.md)
- [雙來源研究股票池與操作](docs/RESEARCH_UNIVERSE.md)
- [資料模型與 JSON 格式](docs/DATA_MODEL.md)
- [開發者指南與本地測試](docs/DEVELOPER_GUIDE.md)
- [資料處理管線與語意關聯](docs/DATA_PIPELINE.md)
- [部署、手動更新與復原](docs/OPERATIONS.md)

**資料治理與開發計畫**

- [安全與資料授權](docs/SECURITY_AND_LICENSING.md)
- [官方資料來源與使用條件](docs/DATA_SOURCES.md)
- [台灣50成分股授權詢問](docs/TW50_LICENSE_INQUIRY.md)
- [驗證紀錄（2026-11-15）](docs/VERIFICATION-2026-11-15.md)
- [開發路線圖 P0–P4](docs/ROADMAP.md)

目前最大外部依賴是**有適用權利的兩份名單、ETF持股日期快照與實際官方資料端點驗證**。雙來源決策、參數與本次測試界線以[研究股票池文件](docs/RESEARCH_UNIVERSE.md)為準；其他完成度見[路線圖](docs/ROADMAP.md)及[既有驗證紀錄](docs/VERIFICATION-2026-11-15.md)。
