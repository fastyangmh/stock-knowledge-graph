# Stock Knowledge Graph｜股票金融知識圖譜

整合可追溯的金融資料，以本地語意分析、關聯計算與 GitHub Pages 互動圖譜支援 **知識探索 → 異常訊號 → 量化研究**。

**研究原型，公開網站仍為虛構示範資料。** 不是即時行情或投資建議；真實名單、使用權利及公開發布尚未完成。

[展示網站](https://fastyangmh.github.io/stock-knowledge-graph/) · [文件中心](docs/README.md)

## 系統概覽

```text
核准資料 → Linux/NAS 本地 SQLite → Embedding/Top-K → 有限子圖 JSON
        → 私有預覽／人工核准 → GitHub Pages（main / root）
```

研究股票池為 [臺灣50指數成分股＋009816 ETF 普通股持股聯集](docs/RESEARCH_UNIVERSE.md)，保留來源及日期；不混成同一指數。使用 Python/uv、本地 SQLite、Sentence Transformers 與 Cytoscape.js；目前只手動運行，不啟用每日排程。

## 開發驗收

```bash
uv sync --locked --extra dev
uv run --locked python -m local.check
# 安裝 Node.js 的開發環境可一起測前端：
uv run --locked python -m local.check --frontend
```

測試使用隔離的虛構資料，不下載真實名單或推送金融資料。[私有預覽工具](docs/FRONTEND_AND_PREVIEW.md)不會把整個 Repository 當成網站根目錄。

## 文件目錄

| 使用與設計 | 資料與維運 |
| --- | --- |
| [User Manual](docs/USER_MANUAL.md) | [資料模型](docs/DATA_MODEL.md) |
| [System Design](docs/SYSTEM_DESIGN.md) | [資料處理管線](docs/DATA_PIPELINE.md) |
| [Architecture](docs/ARCHITECTURE.md) | [來源／使用條件](docs/DATA_SOURCES.md) |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | [安全／資料授權](docs/SECURITY_AND_LICENSING.md) |
| [雙來源股票池](docs/RESEARCH_UNIVERSE.md) | [部署與維運](docs/OPERATIONS.md) |
| [前端篩選／私有預覽](docs/FRONTEND_AND_PREVIEW.md) | [台灣50授權詢問](docs/TW50_LICENSE_INQUIRY.md) |
| [常見問題](docs/TROUBLESHOOTING.md) | [Roadmap](docs/ROADMAP.md) |
| [術語表](docs/GLOSSARY.md) | [本次整合驗證](docs/VERIFICATION-2026-11-16-FRONTEND.md) |

全部文件及歷史驗證紀錄見 [docs/README.md](docs/README.md)。目前外部依賴為**具適用權利、同日的兩份名單與真實官方來源驗收**；技術測試通過不代表已完成此驗收。
