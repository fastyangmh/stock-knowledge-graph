# Stock Knowledge Graph｜股票金融知識圖譜

**網站：** https://fastyangmh.github.io/stock-knowledge-graph/  
**Repository：** https://github.com/fastyangmh/stock-knowledge-graph/

> 目前是研究原型；公開 JSON 含虛構示範資料，不構成投資建議。

## 專案目標與路線圖

分三階段發展：
1. **金融知識探索**：將股票、新聞、財報、籌碼、產業及事件建立可追溯的知識圖譜。
2. **異常訊號發掘**：辨識重要變化、共同事件、可能的跨股票關聯；訊號需附證據與時間。
3. **量化研究**：建立歷史快照、無未來資訊洩漏的回測與模型評估；不將語意相似度當作因果或投資建議。

## 系統架構

```text
Local collectors (尚未接入真實資料來源)
    ↓ 標準化、去重、保留來源及可得時間
Local SQLite (stock_graph.db；不提交 GitHub)
    ↓ Python / uv / Sentence Transformers
Embedding cache → Cosine Similarity → Top-K
    ↓
Local JSON exporter → validator → publisher
    ↓ 僅提交 data/ 到 main
GitHub Pages (Deploy from a branch: main / root)
    ↓
Cytoscape.js 瀏覽器互動關聯圖
```

SQLite 是資料主來源；JSON 是可公開的發布產物。GitHub Pages 不執行 Python、SQLite 或 Embedding。資料模型包含 stocks、documents、document_stocks、financial_metrics、chip_metrics、graph_nodes、graph_edges、embeddings、edge_evidence、pipeline_runs 等表。共享新聞可連結多檔股票。

**關聯類型須分開**：事實關聯、語意相似、財務與籌碼特徵、價格相關性、事件關聯不可混成單一未校準分數。語意相似度並不代表因果或價格預測。每條重要關係應保留來源、模型、計算時間及證據。

## 技術與環境

- Python 3.11，使用 **uv** 管理，設定於 `.python-version` 和 `pyproject.toml`
- SQLite 本地儲存；`local/schema.sql` 定義資料表
- Sentence Transformers 本地多語言模型：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `local/semantic.py` 使用文件雜湊與模型識別進行 Embedding 快取；新文件或修改文件才重算向量，但近鄰搜尋目前仍為 O(N²) 全量掃描
- `local/similarity.py` 為字元特徵測試基準，不是真正語意模型
- 前端：HTML / CSS / JavaScript / Cytoscape.js

## 首次安裝與測試

```bash
uv python install 3.11
uv sync --extra dev
uv run pytest -q
uv run python -m local.validate_release
```

尚未提交 `uv.lock`；在有套件索引存取的環境執行 `uv lock` 後應提交，以固定依賴版本。正式執行 Sentence Transformers 需要本地下載模型並驗證。CI 成功狀態仍須確認。

## Local 更新與發布工作流程

**採用已確認方案：Local 計算 + GitHub Pages 從 main/root 分支部署。** 不啟用 GitHub Actions Pages 發布模式；GitHub Actions 的 `test.yml` 用於測試，不是部署關卡。

1. 每個台灣交易日收盤後，等待所需資料來源完成公布；遇休市或延遲公告須略過或等待。
2. 本地資料蒐集器產生標準化 JSON（**真實來源蒐集器尚未實作**）。
3. 匯入 SQLite，更新文件與股票關聯；使用本地模型增量計算 Embedding，重算 Top-K。
4. 匯出 `data/manifest.json` 及 `data/stocks/<ticker>/graph.json`。
5. 執行 JSON 完整性驗證、測試及發布前檢查。
6. 僅將 `data/` 變更 commit / push 至 main；GitHub Pages 自動從分支發布。
7. 檢查網站更新時間與可視化結果，記錄失敗並保留舊版。

```bash
# 注意：sample_data.json 是虛構資料，僅供測試
uv run python -m local.pipeline all --semantic --input local/sample_data.json --threshold 0.65
uv run python -m local.validate_release
uv run python -m local.publish --dry-run
# 確認資料與變更內容後才執行：
uv run python -m local.publish
```

**不要將上述 sample_data.json 指令直接用於正式市場資料發布。** 正式作業需改用已驗證的來源與輸入檔案。

詳細說明：[local/README.md](local/README.md)、[local/UPDATE_AND_PUBLISH.md](local/UPDATE_AND_PUBLISH.md)。

## 更新準則

- **時間**：第一階段每交易日收盤後更新；不是即時交易系統。資料供應商可能延後公布，排程須有市場行事曆及資料可得性檢查。
- **增量**：使用來源 ID、內容雜湊與模型版本判斷變更；不可無故重新向量化全部文件。近鄰索引最佳化列為後續工作。
- **資料正確性**：保留 published_at、available_at、ingested_at、資料來源、單位與修訂資訊；歷史回測不得使用當時尚不可取得的資訊。
- **圖譜品質**：節點 ID 唯一、所有邊的兩端必須存在、相似度範圍在 [-1,1]、不得有未列於 manifest 的殘留 graph.json。
- **發布**：先本地驗證再 push。因 Pages 仍為 Deploy from a branch，GitHub 不會等待獨立 CI 成功才部署；直接推送 main 的其他人仍可能繞過本地驗證。
- **隱私與授權**：不可提交資料庫、密鑰、未授權新聞全文或受限制原始資料。公開 JSON 可被下載。
- **安全與復原**：驗證失敗禁止發布；有問題時使用 Git 回退資料 commit。重要更新應記錄時間、資料量、失敗原因與來源。
- **測試**：每次修改執行 pytest、CLI 冒煙測試與 JSON 驗證；CI 目前只提供獨立測試，不控制 Pages 發布。

## 目前狀態與待辦

- [x] GitHub Pages 與 Cytoscape.js 原型
- [x] SQLite schema、匯入、文件與股票節點
- [x] Sentence Transformers 整合、Embedding 快取、Top-K 與 JSON Export
- [x] 本地 JSON 驗證與手動發布工具
- [x] 移除與分支部署衝突的 Pages Actions workflow
- [ ] uv.lock、CI 成功結果、正式模型端到端測試
- [ ] 真實金融資料來源、授權審查與蒐集器
- [ ] 台灣交易日行事曆與本地排程安裝
- [ ] 發布完整原子性、增量索引與大型資料效能
- [ ] 異常訊號模型與量化研究／回測

本地資料庫與模型只在本地執行；GitHub Repository 內容不代表已在使用者電腦完成測試。
