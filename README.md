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
- [x] Local CSV 正規化匯入介面（不含資料供應商 API）
- [ ] 真實金融資料來源、授權審查與自動蒐集器
- [x] 可讀取外部交易日曆 CSV 的交易日判斷器（缺資料時拒絕執行）
- [ ] 台灣交易日曆資料來源與本地排程安裝
- [ ] 發布完整原子性、增量索引與大型資料效能
- [ ] 異常訊號模型與量化研究／回測

本地資料庫與模型只在本地執行；GitHub Repository 內容不代表已在使用者電腦完成測試。

## 新增：金融資料匯入介面與交易日防護

可將經授權、已標準化的本地 CSV 放在 `local/inputs/`（已加入 .gitignore），使用以下指令轉成 SQLite Pipeline 所需 JSON：

```bash
uv run python -m local.ingest_csv --input-dir local/inputs --output local/private/normalized.json
uv run python -m local.pipeline all --semantic --input local/private/normalized.json --threshold 0.65
uv run python -m local.validate_release
```

CSV 檔名可為 `stocks.csv`、`sources.csv`、`documents.csv`、`financial_metrics.csv`、`chip_metrics.csv`。其中 stocks.csv 必填；documents.csv 的多檔股票關係使用 `stock_ids` 欄位，以分號分隔股票 ID。詳細欄位參考 [local/ingest_csv.py](local/ingest_csv.py)。目前僅支援本地匯入，**不會自動向台灣證交所或其他網站下載資料**。

交易日檢查採外部 `date,is_open` CSV（1/0），缺少日期時直接報錯，避免誤把休市日當交易日：

```bash
uv run python -m local.trading_calendar --calendar local/private/tw_calendar.csv --date 2026-11-16
```

這個交易日檢查尚未串入排程發布入口；正式排程前仍需確定權威行事曆來源、資料更新與作業系統。

## Linux/NAS 盤後排程與官方資料授權閘門

第一階段採用 **Linux/NAS/Server**，以台北時間 18:30 作為可調整的盤後執行門檻；此時間不是任何官方資料保證完成發布的時間。

- `local/source_registry.py`：資料集逐筆授權與公開再散布審查，預設全部停用。
- `local/official_datasets.json`：目前為空白白名單 `[]`，尚未核准任何 TWSE、TPEx、MOPS 端點。
- `local/collect_official.py`：只下載經白名單核准的 HTTPS 官方機器可讀資料，保存在本地私有目錄；不自動公開或轉成金融指標。
- `local/run_after_close.py`：台北時間、交易日與 cutoff 防護；沒有真實標準化輸入時拒絕使用測試資料替代。
- `local/trading_calendar.py`：要求明確的交易日曆 CSV；缺日期即停止，不以週一至週五猜測交易日。

```bash
# 授權資料集核准後，才可下載（目前白名單為空）
uv run python -m local.collect_official

# 需要提供外部交易日曆與真實、已標準化的本地輸入
uv run python -m local.run_after_close \
  --calendar local/private/tw_calendar.csv \
  --input local/private/normalized.json

# 確認驗證通過後，額外加 --publish 才會推送 GitHub
```

排程可使用 cron 或 systemd timer；目前尚未安裝任何實際排程，也未自動啟用 Git Push。Linux 主機須保持開機、網路連通，且預先配置 Git 寫入憑證。**正式上線前必須逐資料集確認 data.gov.tw 授權與署名條件，並提供官方交易日曆。**

### 官方資料授權注意事項

- TWSE 一般網站條款對未經同意的自動下載有限制；政府開放資料授權的例外需依資料集核對：https://wwwc.twse.com.tw/en/terms/use.html
- TPEx 部分資料集登錄政府開放資料平台，授權依個別資料集為準：https://data.gov.tw/
- TWSE/TPEx 即時、延遲行情及商業資訊產品可能另需契約或費用；本專案不預設有權下載或再散布。
- MOPS 重大訊息介接尚未啟用；不得使用未經確認的網站爬蟲替代正式授權介面。

**目前 collector 只負責安全下載已核准的資料集原始快照，尚未完成官方 API 欄位映射到 SQLite 的轉換器。**
