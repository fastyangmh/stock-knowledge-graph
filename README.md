# Stock Knowledge Graph｜股票金融知識圖譜

[網站](https://fastyangmh.github.io/stock-knowledge-graph/) · [資料來源與授權](docs/DATA_SOURCES.md) · [本次本地驗證紀錄](docs/VERIFICATION-2026-11-15.md)

> 研究原型。網站仍是虛構示範資料，不構成投資建議；未啟用自動排程或真實金融資料發布。

## 目標與已確認決策

分階段完成 **金融知識探索 → 異常訊號發掘 → 量化研究**。目前工作集中於 P0 可靠性、P1 官方資料整合、P2 圖譜生命週期；尚不是交易、預測或完整歷史回測系統。

| 項目 | 決策 |
| --- | --- |
| 第一階段股票範圍 | 台灣 50；使用有來源、有效起訖日期且有權使用的成分股 CSV，不以 ETF 持股冒充 |
| 執行環境 | Linux / NAS / Server，先手動驗證；不安裝 cron/systemd timer |
| Python | uv；專案固定 Python 3.11；保留使用者已提交的 pyproject.toml 與 uv.lock |
| 主資料庫 | Local SQLite；不提交資料庫與原始金融檔案 |
| 模型 | 本地 Sentence Transformers，多語言 MiniLM 基準；正式重現應固定模型 revision |
| 網站 | Cytoscape.js + JSON + GitHub Pages，維持 **Deploy from a branch / main / root** |
| 驗收 | 本地 CI 與單元測試；不以 GitHub Actions 狀態取代驗收 |

## 系統架構

```text
經逐資料集核對的官方 CSV
  → Local 私有原始快照 + SHA256 + 擷取時間 + 授權署名
  → 官方欄位映射 + 台灣 50 日期篩選 + 完整覆蓋檢查
  → Local SQLite（股票、文件、財務、籌碼、向量、關聯證據）
  → 增量 Embedding + 有上限的精確 Top-K + 未變動關聯重用
  → Graph Lifecycle Manager（時間、節點與邊數量限制）
  → 暫存 JSON → 完整驗證 → 私有預覽
  → 人工確認資料授權、日期、單位、變更內容
  → 另行手動匯出 data/、驗證及 Git Push → Pages 分支部署
```

SQLite 是主資料來源，JSON 只是公開子圖。前端不執行 Python、SQLite 或模型。事實、語意、財務／籌碼及價格關係不可混為單一未校準分數；相似不等於因果或報酬預測。

## 本地 CI：一個指令，不必使用 GitHub CI

在專案根目錄執行：

```bash
uv sync --locked --extra dev
uv run --locked python -m local.check
```

此入口會依序執行語法檢查、全部 pytest、隔離 SQLite→JSON 測試及完整 JSON 驗證；報告寫入忽略追蹤的 `local/private/check-report.json`。測試不下載模型、不存取官方 API、不改動 `data/`；Git 發布測試只操作臨時的本機 bare repository。

也可使用標準函式庫測試 runner：

```bash
uv run --locked python -m local.check --runner unittest
```

**驗證界線：** 使用者已在 Linux/Python 3.11 以鎖定依賴跑過舊版 16 項測試、真實模型與快取；本次修改另在 Python 3.13.5 的現有執行環境實測。後者不是重新建立該 uv.lock 環境，也不是重新下載真實模型。詳細結果見驗證紀錄。GitHub 的既有測試 workflow 未更動；它不控制分支式 Pages 部署。

## 官方資料：第一批已實作

`local/official_datasets.json` 記錄政府資料開放平台的資料集頁、固定資源 URL、OGDL-1.0、署名與核對日期。手動 collector 目前啟用上市公司基本資料及上市月營收；上櫃對應資料列已記錄但預設停用。

```bash
# 只下載至 local/private/official，不公開，也不操作 Git
uv run --locked python -m local.collect_official
```

下載器有固定 HTTPS 主機／路徑、禁止重新導向、大小限制、有限重試、HTML/空 CSV 拒絕、內容定址快照、完整批次成功後才更新 manifest。403 不重試；不繞過存取控制。這裡已測試模擬 HTTP 回應，**尚未完成正式端點的線上下載驗證**。

### 成分股名單與私有匯入

準備 `local/private/tw50.csv`，欄位為 `stock_id,effective_from,effective_to`。日期必須是有效 ISO 日期；截止日含當日，空白表示無截止日。同一股票的有效區間不得重疊。正式官方匯入入口要求選定日期恰有 50 檔；缺少資料拒絕產生不完整發布。

**目前沒有取得可用於本專案的官方台灣 50 成分股名單及其使用範圍證明。** 程式不會猜測名單，也不會把今日名單回填歷史。公司／月營收資料的開放授權不等於指數成分股名單的授權，詳見資料來源文件。

取得適用名單、當日完整快照後，以實際台北日期取代下方範例日期：

```bash
uv run --locked python -m local.official_import \
  --universe local/private/tw50.csv --as-of 2026-11-15

uv run --locked python -m local.pipeline all --semantic \
  --input local/private/normalized.json \
  --db local/private/official-preview.db \
  --universe local/private/tw50.csv --as-of 2026-11-15 \
  --output local/private/preview --lifecycle \
  --lookback-days 90 --threshold 0.65

uv run --locked python -m local.pipeline validate --output local/private/preview
```

以上使用獨立的官方資料預覽 DB，請勿與 sample_data 的測試 DB 混用；只有手動私有處理，不推送網站。`--as-of` 在 pipeline CLI 控制**成分股選擇日期**，不代表可重建當時的整個資料庫。官方匯入必須使用同日擷取快照，不能以今日快照假裝歷史資料。

月營收 adapter 處理民國日期、千分位、零與缺值、月份期末日、來源欄位變化、股票覆蓋及 provenance。金額暫保留來源原始尺度 `source_reported`，**不猜測幣別或千元／元倍率**，不應直接用於跨來源金額比較。擷取時間標記為首次觀察時間，不冒稱原始公告時間。現有財報／文件修訂仍覆寫目前資料列，完整歷史版本與雙時間回測尚待開發。

## Embedding 與關聯計算

- 標題／內容雜湊未變且模型身份相同：重用 SQLite float32 向量。
- 全部有效文件命中快取：不建立 SentenceTransformer，不下載模型。
- 文件、股票對應、Top-K／門檻及演算法版本均未變，且邊／證據校驗相符：重用既有語意邊；`graph_reused=true`、`pairs_evaluated=0`。
- 新增或修改文件只重算該文件向量；新增／移除股票對應會重建關聯，無須重新向量化。
- 精確 Top-K 使用每節點有界 heap，候選記憶體 O(NK)；**運算仍是 O(N²×向量維度)，不是 ANN**。
- `--max-pairs` 預設 2,000,000，超過就明確停止；可用 `--lookback-days` 縮小語意候選範圍，不刪除歷史向量。
- 股票語意分數目前是「被選中的文件配對」最高值，可能放大單一事件；不是金融有效性已驗證的投資訊號。
- `--revision <模型 commit SHA>` 可隔離模型版本。套件 lockfile 不會固定遠端模型權重；未固定 revision 的模型名稱仍可能變動。

無向 Top-K 聯集不是嚴格 degree≤K；前端展示由 lifecycle 另作限制。無變更時仍會讀 SQLite、檢查 hash 並匯出 JSON，不等於零成本跳過整個 pipeline。

## 每日更新與圖譜生命週期

資料庫歷史會成長，公開圖譜不應跟著無限制成長。每交易日收盤後，須等待來源資料可得並確認有效交易日；目前仍手動執行。18:30 僅為可調門檻，不保證任何來源已完成發布。日曆缺日期就停止，不以週一至週五代替交易日曆。

啟用 `--lifecycle` 後，每檔股票上限為主股票 + 100 個資訊節點 + 15 個相關股票；資訊節點語意連線最多 5，新聞使用 90 天視窗。優先使用 `available_at` 過濾未來資訊，裁剪後移除無法從主股票到達的孤立節點；SQLite 不刪除原始資料。財報 4–8 季、籌碼 30–60 天等分型保留政策仍是後續工作，不是已完成規格。

JSON 先完整寫入同檔案系統的暫存目錄，驗證 manifest、唯一 ID、端點、分數、檔案集合後替換；股票範圍縮小時清除舊 JSON。替換失敗會回復舊目錄，拒絕覆寫無關檔案及 symlink；使用本地鎖避免合作程序同時寫入。**不保證斷電、NAS 檔案系統或非合作讀取程序下的全局原子性；SQLite commit 與目錄替換也不是單一分散式交易。**

`local.run_after_close` 保持私有預覽入口，必須提供交易日曆、標準化輸入及成分股名單；`--publish` 明確拒絕。沒有安裝任何系統排程。

## 發布安全

`local.publish` 是獨立的人工工具，先驗證，僅允許 `data/manifest.json` 與股票 `graph.json`。拒絕其他工作區變更、既有 staged 檔案或與 origin/main 分歧；dry-run 不動 index，推送失敗保留本地 commit，不強制推送。

**本次開發沒有執行真實資料發布。** 日後人工確認公開權利、單位、資料日期與預覽後，再另行匯出至 `data/` 並檢視 Git diff。SQLite、模型權重、原始快照及憑證不可提交。分支部署不等待本地檢查或獨立 GitHub CI，其他直接 push 仍可能繞過驗證。

## 目前完成與待辦

| 階段 | 本次成果 | 尚未完成 |
| --- | --- | --- |
| P0 | 本地 CI 入口、測試擴充、回復／交易／發布防護、保留使用者 lockfile | 新版在鎖定 Python 3.11 環境重現、瀏覽器端測試；不將既有 CI 狀態當作證據 |
| P1 | 四個官方開放資料集核對、CSV 下載快照與公司／月營收映射、50 檔覆蓋檢查 | 授權適用的台灣 50 名單、線上來源實測、金額倍率確認、股價／籌碼／季報／重大訊息 adapter |
| P2 | 懶載入模型、未變關聯重用、有界精確 Top-K、資訊時間與展示限制、證據匯出 | ANN、大規模真實資料、歷史修訂／快照查詢、前端時間軸與載入更多 |
| P3–P4 | 僅保留設計方向 | 異常訊號、策略評估、成本與存活偏誤處理、完整回測 |

此 README 為現行操作準則；先前逐次開發紀錄保留於 Git 歷史，不再把已過時的待辦或未驗證聲明當成現況。
