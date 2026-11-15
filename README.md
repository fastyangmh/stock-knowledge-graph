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

## 每日更新的圖譜成長與生命週期管理（規劃中，尚未實作）

**核心原則：完整歷史留在 Local SQLite；公開的 GitHub Pages JSON 只包含當前需要展示的精簡子圖。** 每交易日更新不等於每天複製所有既有節點。使用穩定 ID、來源去重、內容雜湊和文件與多檔股票共用節點，可降低重複新增。

### 成長風險與容量估算

若追蹤 1,000 檔股票，每檔每交易日平均新增 8 個**不重複**資訊節點，按每年 250 個交易日估算，單年新增約 2,000,000 節點、五年約 10,000,000 節點（不含股票主節點及關聯線）。這只是上限情境示例；共享新聞、去重、資料來源與實際更新量會改變結果。

對 500 個資訊節點進行所有不重複兩兩配對，候選關聯數為 500×499÷2＝124,750。Embedding 快取只節省向量重算，**不會自動消除目前語意關聯演算法的 O(N²) 全配對成本**。資料規模增大時需引入候選篩選、分批計算或 ANN 索引。

### 三層資料生命週期

| 層級 | 保存內容 | 用途 |
| --- | --- | --- |
| 歷史資料層（Local SQLite） | 原始文件、股票、財務／籌碼指標、Embedding、來源與必要歷史關聯快照 | 稽核、重新計算、歷史研究、回測 |
| 活躍圖譜層（Local 計算） | 依時間、類型、證據、重要性、相似度、Top-K 選出的子圖 | 控制資訊密度及關聯品質 |
| 公開展示層（GitHub Pages JSON） | 各股票有限節點、有限邊及可追溯的必要中繼資料 | 快速載入、互動探索；不承載完整歷史 |

### 建議的初始展示政策（可設定；尚未套用至 exporter）

| 節點／關聯類型 | SQLite 保存政策 | 前端預設展示政策 |
| --- | --- | --- |
| 股票、公司、產業 | 長期保留，追蹤狀態變更 | 持續顯示有效節點 |
| 新聞與一般資訊 | 保存歷史及來源、可得時間 | 最近 90 天內，依相關性及重要性排序 |
| 重大事件、供應鏈事實 | 保存歷史與有效期間 | 重要事件及有效關係優先 |
| 財報 | 保存全部期別 | 最近 4–8 季 |
| 籌碼異常 | 保存歷史 | 最近 30–60 天 |
| 語意關聯 | 保存模型版本與必要快照 | 每資訊節點最多 Top-5 |
| 跨股票關聯 | 保存分數、證據及計算時間 | 每檔股票最多 Top-15 |

**每檔股票公開圖譜初始上限：100 個資訊節點**，另保留股票主節點及合理數量的相關股票節點。節點及邊的數量限制應一起執行；不應留下指向未輸出節點的邊。超過上限的資訊日後可提供「載入更多」或時間區間查詢，而不是直接從 SQLite 刪除。

### Graph Lifecycle Manager（初版已實作；後續仍需擴充）

1. 對文件使用穩定 ID 去重；同一新聞關聯多檔股票時共享文件節點。
2. 以交易日／可得時間作為資料篩選依據，避免使用未來資訊。
3. 對不同節點類型設定獨立的保留視窗、排序與重要性規則。
4. 以 Top-K 與股票上限縮減公開關聯線；保留事實關聯與語意關聯的類型差異。
5. 輸出前驗證節點／邊數量、唯一性、端點完整性與 JSON 大小。
6. 保留必要的歷史快照，讓日後可做時間切片比較與回測；制定資料庫備份、封存與清理策略。
7. 監控每日新增文件數、去重率、Embedding 快取命中率、邊數、輸出檔大小及頁面載入時間。

**實作狀態：** 初版展示層裁剪已在 `local/lifecycle.py` 實作並以 `--lifecycle` 選用；財報季數、籌碼事件視窗、歷史快照、輸出目錄原子替換及效能優化仍未完成。

## 第一階段已確認：台灣 50 + Linux 手動驗證

- **股票範圍**：台灣 50 成分股。成分股會調整，必須使用附有效起訖日期的權威名單，不能將固定 50 檔清單當作永遠不變的成分股。名單 CSV 格式為 `stock_id,effective_from,effective_to`（例如 `TW:2330,2026-01-01,`；此行僅為格式範例，不代表官方成分股資料）。
- **排程**：先在 Linux/NAS 手動執行、驗證成功後才安裝 cron 或 systemd timer。**目前沒有自動排程或自動推送。**
- **新功能**：`local/universe.py` 提供依指定日期篩選股票清單；`local/lifecycle.py` 提供展示層節點與邊的裁剪，不刪除 SQLite 歷史。匯出器與 CLI 已提供可選參數。

```bash
# 前提：準備已確認來源及日期的台灣 50 成分股 CSV，及經授權的標準化金融資料
uv run python -m local.pipeline all --semantic \
  --input local/private/normalized.json \
  --universe local/private/tw50.csv --as-of 2026-11-15 \
  --lifecycle --threshold 0.65 --output local/private/export-preview

# 預覽輸出與測試（尚未發布）
uv run pytest -q
```

注意：`--universe` 僅限制匯出的股票主圖，不會自動限制 SQLite 收錄範圍；`--lifecycle` 目前為選用，包含資訊節點 100、相關股票 15、語意邊每節點 5、新聞 90 天的展示限制。**目前尚未取得並驗證官方台灣 50 歷史成分股名單**；匯出目錄若已有舊股票檔案，需要清理／原子替換後才能通過完整發布驗證。現階段不應直接發布預覽輸出。

## 匯出一致性修復（2026-11）

`local/export_json.py` 已改為先在輸出目錄旁建立完整暫存樹，使用 `local.validate_release` 驗證所有股票 JSON 與 manifest，再替換原有輸出目錄。這會移除舊股票名單留下的過期 `graph.json`；SQLite 歷史不受影響。替換採同一檔案系統上的目錄 rename 與備份回復，但**不保證所有平台、斷電情境或讀取中的網站程序都具有完全原子性**。正式發布仍應先在獨立預覽路徑執行測試，並確認 Git 變更內容。

已新增回歸測試，涵蓋股票範圍縮小、過期檔案清理、缺少成分股時拒絕匯出。**這些測試已提交，尚未取得 CI 成功執行紀錄。**

## Linux 實機驗證紀錄（2026-11-15）

使用者在全新 clone 的 `main` commit `6a1f54b` 上執行，環境 Linux x86_64 / Python 3.11.18 / uv 0.13.6：

| 檢查 | 結果 |
| --- | --- |
| `uv sync --extra dev` | exit 0，101 packages resolved、67 installed |
| `uv run pytest -q` | **15 passed in 0.08s**，exit 0 |
| `uv run python -m local.pipeline all --db /tmp/stock-graph-test.db --input local/sample_data.json --output /tmp/stock-graph-preview --lifecycle` | 3 documents、3 document pairs、3 stock pairs、3 graphs exported，exit 0 |
| `uv run python -m local.pipeline validate --output /tmp/stock-graph-preview` | 3 stock graphs validated，exit 0 |

**驗證範圍限制：** 使用的是預設 lexical character-bigram baseline，不是 `--semantic` Sentence Transformers；輸入為虛構示範資料。未執行 Git Push、正式發布、官方來源下載或台灣 50 全量處理。此紀錄為使用者提供的實機測試結果，並非 CI 成功狀態聲明。

### 下一階段驗證

1. 使用**獨立的臨時 DB / JSON 路徑**執行 `--semantic`，首次執行可能下載模型。確認首次 encoded > 0，第二次同一 DB 與模型 cache_hits > 0。
2. 執行 `uv lock`，檢查 lockfile diff 後提交 `uv.lock`，再以 `uv sync --locked --extra dev` 驗證可重現環境。
3. 核對官方台灣 50 成分股名單的資料來源與生效日期；確認授權後建立標準化映射器。
4. 以真實但**不公開**的資料進行手動驗證；資料品質及公開授權確認前不啟用排程或發布。

## Linux 真實語意模型驗證紀錄（2026-11-15）

使用者在 Linux 測試環境成功執行 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，完成首次 `--semantic` 測試：`documents=3`、`encoded=3`、`cache_hits=0`、`document_pairs=2`、`stock_pairs=2`、匯出 3 檔股票圖譜，exit 0；隨後圖譜驗證通過，exit 0。此測試使用虛構資料，沒有發布正式網站。

測試環境透過 SOCKS 代理連線，第一次因缺少 `socksio` 失敗；在測試虛擬環境額外安裝後重跑成功。此為環境特定依賴，尚未加入預設專案依賴。Hugging Face 匿名下載限速提示不影響本次成功。程式已更新為優先使用新的 `get_embedding_dimension()` API，並保留舊版相容回退；這項程式修改仍須重新執行測試。

**尚待驗證：** 在同一 SQLite DB、相同模型與未變動輸入下第二次執行，應看到 `encoded=0`、`cache_hits=3`。此外仍需 `uv.lock`、官方台灣 50 資料、正式授權與端到端發布前測試。

## SQLite Embedding 快取第二次實機驗證（2026-11-15）

使用者在相同 Linux 測試環境、相同 SQLite DB、相同模型與參數下再次執行 `--semantic`：

```text
Semantic: {'model_id': 'st:1cfd264d04e3b6b6e5322922', 'documents': 3, 'cache_hits': 3, 'encoded': 0, 'document_pairs': 2, 'stock_pairs': 2}
Exported 3 stocks
EXIT_CODE=0
```

**結論：** 3/3 文件向量成功從 SQLite 快取重複使用，未重新計算 Embedding。此驗證只涵蓋 3 篇示範文件，不代表大規模效能測試；Pipeline 仍載入模型、重算相似度及匯出 JSON。後續應測試單篇文件修改、模型版本變更、歷史資料成長下的關聯計算成本，以及發布前端到端驗證。
