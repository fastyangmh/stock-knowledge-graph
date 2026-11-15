# Stock Knowledge Graph

股票金融知識圖譜：GitHub Pages + JSON + Cytoscape.js。

## 架構
- 本地 SQLite/PostgreSQL 保存原始資料。
- 本地計算 Embedding、cosine similarity、Top-K 關聯。
- 輸出 `data/manifest.json` 及 `data/stocks/<ticker>/graph.json`。
- GitHub Pages 僅載入 JSON 與顯示互動圖譜。

## 預覽
```bash
python -m http.server 8000
```
瀏覽 http://localhost:8000 。

## 啟用 GitHub Pages
Settings → Pages → Deploy from a branch → main → / (root) → Save。

預計網址：https://fastyangmh.github.io/stock-knowledge-graph/

## JSON 格式
每個 `graph.json` 包含 `nodes` 和 `edges`。
- node: `id`, `label`, `type`
- edge: `source`, `target`, `relation`；可附加 `score`, `method`, `as_of`, `evidence_ids`

目前內容是虛構示範資料，並非真實金融資訊或投資建議。請勿將私密資料庫、API 金鑰或受限制的金融原始資料推送到公開 repository。

## Local SQLite pipeline (implemented)

Python 3.10+; from repository root:

```bash
python -m local.pipeline all
python -m local.pipeline validate
python -m unittest discover -s local/tests -v
python -m http.server 8000
```

See [local/README.md](local/README.md) for import format, CLI options and limitations.

**Model warning:** Current default similarity is a zero-dependency lexical character-bigram cosine baseline, **not** a semantic embedding model. All sample financial content and scores are synthetic. Select and validate a production embedding model before treating relationships as research signals.
