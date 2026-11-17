# 專案交接｜Handoff

[文件中心](README.md) · [待開發與驗收清單](DEVELOPMENT_BACKLOG.md) · [路線圖](ROADMAP.md)

整理日期：**2026-11-17（Asia/Taipei）**。核對的程式基準：`115bd7c09afc8d8ec65fb0a6e6cf033c399443ac`（事件後描述統計）。這是交接時的基準，不保證永遠等於最新 `main`；接手前先查看遠端與本地差異。

## 1. 接手時先知道的事

專案已有可運作、經合成資料驗證的本地金融研究流程：**資料快照 → SQLite → 文字／數值圖譜 → 兩類研究提醒 → 版本比較 → 事件後描述統計**。公開網站仍是示範資料，**不能將工程測試通過稱為正式金融資料上線或整個專案完成**。

目前最重要的缺口不是再增加示範頁，而是：**正式來源下載與尺度核對、目標環境重現、未裁剪的研究資料契約，以及尚未實作的資料適配器**。可直接從待辦 `P0-01`、`P1-01`、`P1-02` 開始，不需重問使用者架構或名單選擇。

Repository：`fastyangmh/stock-knowledge-graph`；工作分支沿用 `main`。本次交接只整理文件，**沒有新增產品功能或重新執行產品測試**；以下測試數字引用既有驗證紀錄。

## 2. 已確認決策，不要重新詢問

| 主題 | 已確認的方向 |
| --- | --- |
| 目標 | D：分階段整合金融知識探索、異常訊號發掘與量化研究 |
| 運算與儲存 | Linux／NAS／Server 本地運算、SQLite 主資料庫、JSON 靜態展示 |
| Python 環境 | uv 與 `uv.lock`；使用者曾以 Linux x86_64／Python 3.11.18／uv 0.13.6 測試較早版本 |
| 語意模型 | 本地開源多語 Sentence Transformers；既有預設為 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| 網站 | Cytoscape.js 與 GitHub Pages；保持 `main / root` 分支式部署，不擅自改部署方式 |
| 更新與驗收 | 盤後先手動執行；以本地 CI／單元測試為主，不要求 GitHub CI 作為本次開發的驗收依據 |
| 股票池 | TW50 成分股與009816 ETF普通股持股取聯集、去重、保留各自來源與日期，不混成同一指數 |
| 名單依賴 | **先暫緩，不阻塞其他開發、不要求現在寄信**；可用 `--symbols` 自選股票做私有研究，不推定指數歸屬 |
| 研究提醒 | C：價量與月營收都做，分開呈現，不合併總分、不產生買賣指令 |
| 量化方向 | A：事件後描述統計；B正式策略回測未選定，不先詢問交易規則或成本 |
| 文件方式 | 根目錄 README 保持簡介與目錄，詳細說明在 `docs/` |
| 自主開發範圍 | 例行修復、測試、既定範圍整合可繼續；付費、簽約、擴大資料使用範圍、正式公開、排程或重大研究定義變更才停下確認 |

名單來源URL不等於取得使用許可；但已有適用開放授權的資料集，也不應一律要求另外寄信。逐來源核對，依實際條件使用；參考[資料來源](DATA_SOURCES.md)、[候選來源評估](SOURCE_REVIEW_2026-11-16.md)與[安全規範](SECURITY_AND_LICENSING.md)。

## 3. 已實作能力與主要入口

| 能力 | 程式／文件 | 已完成與剩餘界線 |
| --- | --- | --- |
| 公司／月營收快照與正規化 | `local.collect_official`、`local.official_import`；[資料管線](DATA_PIPELINE.md) | 已有CSV適配與私有快照；正式全檔下載及單位尚待實測 |
| 盤後行情 | `local.market_prices`、`local.market_graph`；[行情](MARKET_PRICES.md) | 明確股票代碼、OHLC／成交股數、原始快照與修訂；不是還原價格歷史服務 |
| SQLite／語意／展示子圖 | `core.py`、`semantic.py`、`neighbors.py`、`lifecycle.py`、`export_json.py` | 向量與關聯快取、精確Top-K、裁剪、JSON校驗；不是ANN |
| 私有研究版本 | `local.research`、`research_history.py`；[私有研究](PRIVATE_RESEARCH.md) | 觀察ledger、獨立bundle、latest指標與跨版本快取；不是完整市場雙時間資料庫 |
| 獨立研究提醒 | `alerts.py`、`alert_inputs.py`；[提醒規則](RESEARCH_ALERTS.md) | 2條價量、4條營收規則；未經真實績效校準 |
| 歷史稽核與比較 | `local.bundle_audit`、`local.research_compare`、`local.research_archive`；[研究歷史](RESEARCH_HISTORY.md) | 比較已保存版本，明確區分缺漏／定義改變；非策略回測 |
| 財務抽檢與備份 | `local.financial_review`、`local.backup`；[抽檢](FINANCIAL_REVIEW.md) | 已有精確差異與一致性備份工具；未完成真實財報抽檢／NAS復原演練 |
| 事件後描述統計 | `local.event_study`、`event_outcomes.py`；[事件統計](EVENT_STUDY.md) | 凍結首次保存事件基準、分組分母與證據；目前只用展示圖內保存的數值 |
| 網頁／私有預覽 | `index.html`、`history.html`、`event-study.html`、`js/`；[使用手冊](USER_MANUAL.md) | 股票池／搜尋／來源、兩類提醒、歷史及事件頁；私有頁由本機工具供應，不是公開後端 |

最近功能里程碑：`690d3f3` 私有研究整合 → `665a489` 研究提醒 → `c56b985` 歷史比較／抽檢 → `115bd7c` 事件後描述統計。更舊的「尚未選A/C」「缺uv.lock」或「只有69項測試」不是目前狀態。

## 4. 測試證據與限制

依[最新驗證紀錄](VERIFICATION-2026-11-16-EVENTS.md)，上一輪實際執行結果為：

| 檢查 | 已記錄結果 |
| --- | --- |
| Python完整pytest | 410 passed、154 subtests passed |
| unittest | 同一套410項測試通過；不能和pytest相加 |
| JavaScript | 53項通過 |
| 瀏覽器 | 圖譜13組＋歷史9組＋事件頁11組，共33組 |
| 整合 | 虛構CSV→真實本機SQLite→研究版本→稽核→事件統計；HTTP防護另有本機實測 |

上一輪環境為 Linux、Python 3.13.5、pytest 9.0.2、Node.js 22.16.0及Playwright／Chromium；**不是新版Python 3.11鎖定環境重驗**。模型／HTTP測試大量使用fixture及測試編碼器，沒有重新下載真實模型或官方金融資料。瀏覽器用記憶體fetch與本地Cytoscape 3.33.1，網站仍固定CDN 3.30.4；不等於正式Pages、原CDN及真實WebCrypto傳輸驗收。

既往助手環境曾無法直接解析GitHub主機，透過連接器取得既存Pages封裝作原始檔傳輸並比對Git tree，**不是採用GitHub CI成功狀態來驗收**。接手環境須重新檢查自己的網路能力，不假定永遠能或永遠不能clone。舊聊天的沙盒日誌／截圖可能不在新環境；以repo驗證文件與重新產生的本地報告作可攜交接依據。

## 5. 接手操作

### 5.1 先記錄版本，再跑本地基準

在已clone的repo根目錄，先檢查工作區；有未提交變更時先保留並核對，不做reset或force push：

```bash
git status --short
git rev-parse HEAD
# 確認沒有未處理的本地修改，再更新：
git pull --ff-only
uv sync --locked --extra dev
uv run --locked python -m local.check --frontend
```

`--frontend`需要Node.js；未安裝時先執行不帶該旗標的 `local.check`，將前端列為未驗證，不宣稱全套通過。要另外檢查同一測試集的unittest runner：

```bash
uv run --locked python -m local.check --runner unittest --frontend
```

報告預設在 `local/private/check-report.json`，應保存對應Commit、環境、exit code與原始檔雜湊。瀏覽器腳本是另外的測試，不包含在單純Node測試通過的含義中。Playwright／Chromium需求見[開發指南](DEVELOPER_GUIDE.md)及各驗證紀錄。

### 5.2 有私有資料後的安全入口

以下要求相關資料／版本已存在，不會自行補出真實資料。財務與行情下載／匯入步驟依[私有研究手冊](PRIVATE_RESEARCH.md)；先核對日期、來源和單位。

```bash
# 僅為命令格式：2330須換成實際輸入內的研究股票，不代表選股建議。
uv run --locked python -m local.research \
  --input local/private/normalized-watchlist.json \
  --symbols 2330 --analysis none --alerts

uv run --locked python -m local.bundle_audit --root local/private/research-runs
uv run --locked python -m local.research_archive --root local/private/research-runs --port 8766
```

未帶行情參數時只處理可取得的財務資料；價量提醒可能顯示資料不足，**不是完整價量驗收**。加入行情須一起提供 `--prices-db`、`--price-snapshots`、`--trade-date`；使用AI改為 `--analysis semantic` 並固定適當的 `--revision`。不要把所有numeric節點轉成文字Embedding。

已累積事件與後續版本時，可在另一終端執行事件統計（Bash）：

```bash
uv run --locked python -m local.event_study \
  --root local/private/research-runs \
  --as-of "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output local/private/event-studies/handoff-report-001.json \
  --serve --port 8767
```

不同內容不覆寫既有報告，重做時用新檔名。歷史頁／事件頁僅在同機loopback使用，沒有帳號驗證，不公開連接埠，也不要對repo根目錄開通用HTTP server來展示私有資料。詳細預算、輸入契約與錯誤處理以功能文件及 `--help` 為準。

## 6. 私有檔案與安全不變條件

| 路徑／資料 | 用途與交接規則 |
| --- | --- |
| `local/private/official/` | 原始公司／月營收快照與retrieval manifest；保持原始bytes |
| `local/private/market-prices.db`、`market-prices/` | 行情觀察與原始CSV；檔案校驗不等於來源已授權 |
| `local/private/research-history.db` | 本系統登錄之後的追加快照；來源觀察時間不替代本地首次登錄時間 |
| `local/private/research-runs/<run-id>/` | `graph.db`、`data/`、`report.json`、選用`alerts.json`；舊版不可偷偷改寫 |
| `local/private/research-runs/latest.json` | 最後成功指標；失效不能偷偷挑其他版充數 |
| `local/private/backups/`、`event-studies/` | 私有備份／統計；還原拒絕覆寫，報告保留定義與分母 |
| repo根目錄 `data/` | 公開示範，**不要用私有測試輸出覆蓋**；正式金融發布需獨立核准 |

- 資料庫、Token、憑證、未授權原文與原始快照不push；不以公開Git代替私有備份。
- 缺值不補零、來源日期不改標今天、昨日名單不冒稱今日、財報金額未知尺度不擅自換算。
- 未來資訊／較晚登錄資料不可回填成事件當時已知；語意相似不等於因果、報酬或共同入選的投資訊號。
- 現行精確Top-K仍有兩兩比較成本；快取命中不表示整條pipeline或JSON產生被略過。
- 研究提醒的前20筆報價不是已驗證的連續20交易日；事件後第1／5／20筆也不宣稱交易日。
- 事件分析凍結首次保存基準與後續首次保存值；不把最終修訂版偷偷代入，不把缺漏事件排除來美化平均。
- 哈希驗證證明檔案一致性，不是數位簽章、金融正確性、法律授權或備份演練的替代品。

## 7. 下一個人應做什麼

依[待開發清單](DEVELOPMENT_BACKLOG.md)執行：先重現目標環境，再驗證已登錄官方端點及來源尺度，同時補上未裁剪研究資料契約；接著做季報／籌碼／重大訊息適配、交易日完整性及真實資料觀察。網路失敗要記錄失敗，不繞過封鎖；可先完成離線適配和測試，不因名單等待而停掉其他工作。

沒有新的必要決策時不要每一步詢問。完成一項需留下變更、對應測試、範圍限制與文件；不能只用測試數量稱專案完成。進度細項維護在待開發清單，功能語意維護在各專章，驗證結果另外寫帶日期及Commit的紀錄。

### 交給下一位開發者／新對話的指令

> 請接手 `fastyangmh/stock-knowledge-graph`。先讀 `docs/HANDOFF.md`、`docs/DEVELOPMENT_BACKLOG.md` 與最新驗證紀錄，確認遠端HEAD和本地差異後跑本地基準。沿用Linux／uv／SQLite／GitHub Pages、雙來源名單暫緩、自選股票私有研究、價量與營收分開提醒、事件後描述統計A。先執行P0-01、P1-01、P1-02並處理P2-01，不以名單阻塞、不重問已決策事項；不改公開金融資料、不啟用排程／付費／交易。一般修復與驗證持續進行，只有待辦文件列明的實質決策才停下確認。每次提交前保護既有修改、驗證對應內容與連結，區分真實來源和合成測試結果。
