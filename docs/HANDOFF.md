# 專案交接｜Handoff

[文件中心](README.md) · [待開發與驗收清單](DEVELOPMENT_BACKLOG.md) · [路線圖](ROADMAP.md)

整理日期：**2026-11-19（Asia/Taipei）**。M1 審查修復實測候選：`ecd176b3069a62aaa98c7a641496af45b8c415f2`；證據見[審查與重驗](VERIFICATION-2026-11-17-REVIEW.md)。原 `3834c19` 的[整合驗證](VERIFICATION-2026-11-17-M1.md)保留為歷史；其後文件提交不代表重新執行產品測試，推送由整合流程處理。

## 1. 接手時先知道的事

P2-02 六票已交付合成 CLI 與兩市場 11/14～17 的官方日曆驗收。11/18 的實際報價超出已核對日曆，事件報告能顯示第 1 筆已保存觀察，交易日序號維持未知。候選 `f45a8ac` 已修復未來截止、當日待到與同時首存衝突，並通過完整套件及真實重播。P2-02 在已記錄的範圍完成。[雙軸審查及重驗](VERIFICATION-2026-11-19-CALENDAR-REVIEW.md) · [真實日曆驗收](VERIFICATION-2026-11-19-CALENDAR-COVERAGE.md) · [逐項清單與後續規格](../.scratch/private-research-ready/completion.md)

M2 價格基準與正規化來源通知已整合至 `9a0bce9`。兩市場四檔原始價格可查回原件，更正公告可按截止時間還原。已修補晚公告、跨選股撤回、舊格式文件、跨幣別比較與大通知的儲存及回滾。兩市場三版真實歷史與事件頁已在桌面及手機寬度複驗。獨立行情庫已支援明示更正、撤回與重發；兩市場兩日既有行情與研究按原截止重播一致。正式行情通知原件仍待驗。[行情通知實作及驗收](../.scratch/m2-market-revisions/issues/01-market-notices.md) [雙軸審查及整合驗證](VERIFICATION-2026-11-19-M2-HISTORY-REVIEW.md)

最新一期季報、籌碼與重大訊息已開始分來源核對。11/17 與 11/18 的兩市場真實研究版本可供後續品質驗證。[真實後續行情及官方原件索引](../.scratch/private-research-ready/source-samples-2026-11-19.md) · [兩市場發行人季報抽檢](../.scratch/m3-evidence-sources/issuer-reference-2026-11-19.md)

專案已以真實官方快照、固定真實模型，在使用者指定的當前 macOS arm64／Python 3.11 環境完成兩市場各兩版私有研究、提醒、audit、歷史比較、事件報告及三頁真實 HTTP 驗收。公開 `data/` 仍為示範；沒有啟用發布、排程或交易。

**M1 尚未全過。** 01～08、11／12 已完成各票範圍；09 的行情交易範圍／獨立同日參考仍不足，正式兩市場抽檢皆 exit 2、`compared_fields=0`，10 依賴 gate 保持 `needs-info`。財務月營收已核對的新版單位不代表行情尺度已確認。Linux／NAS 未驗證，但使用者已要求本輪在當前環境測試，因此不是本輪 blocker；將來移轉需重驗。

下一步補 09 的來源定義證據；不需等待外部即可推進 M2～M5 中獨立工程工作。P2-01 未裁剪事實與新版事件讀者已完成工程交付及本輪真實來源串接；公司行為、完整撤回／修訂歷史、其他資料適配、研究品質、容量與 NAS 復原仍在 backlog。

Repository：`fastyangmh/stock-knowledge-graph`；本輪工作整合於 `dev/private-research-ready`，尚不能把開發分支驗收視為 `main` 已更新。

## 2. 已確認決策，不要重新詢問

| 主題 | 已確認的方向 |
| --- | --- |
| 目標 | D：分階段整合金融知識探索、異常訊號發掘與量化研究 |
| 運算與儲存 | Linux／NAS／Server 本地運算、SQLite 主資料庫、JSON 靜態展示 |
| Python 環境 | uv 與 `uv.lock`；本輪使用者指定當前 macOS arm64／Python 3.11.11；Linux／NAS 移轉另驗 |
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
| 公司／月營收快照與正規化 | `local.collect_official`、`local.official_import`；[資料管線](DATA_PIPELINE.md) | 兩市場公司／月營收真實全檔與月營收單位抽檢完成；[季度三表](QUARTERLY_STATEMENTS.md)有逐來源私有適配及抽檢 |
| 盤後行情 | `local.market_prices`、`local.market_graph`；[行情](MARKET_PRICES.md) | 兩市場真實全檔及私有串接完成；單位／交易範圍抽檢未過，保留 source_reported |
| 行情交易日完整性 | `local.calendar_coverage`；[私有日曆 CLI](CALENDAR_COVERAGE.md) | 逐日查開休市與缺觀察、獨立序號、證據截止與時序衝突；官方日曆目前核至 11/14～17 |
| SQLite／語意／展示子圖 | `core.py`、`semantic.py`、`neighbors.py`、`lifecycle.py`、`export_json.py` | 向量與關聯快取、精確Top-K、裁剪、JSON校驗；不是ANN |
| 私有研究版本 | `local.research`、`research_history.py`；[私有研究](PRIVATE_RESEARCH.md) | 觀察ledger、獨立bundle、latest指標與跨版本快取；不是完整市場雙時間資料庫 |
| 獨立研究提醒 | `alerts.py`、`alert_inputs.py`；[提醒規則](RESEARCH_ALERTS.md) | 2條價量、4條營收規則；未經真實績效校準 |
| 歷史稽核與比較 | `local.bundle_audit`、`local.research_compare`、`local.research_archive`；[研究歷史](RESEARCH_HISTORY.md) | 比較已保存版本，明確區分缺漏／定義改變；非策略回測 |
| 財務抽檢與備份 | `local.financial_review`、`local.backup`；[抽檢](FINANCIAL_REVIEW.md) | 真實月營收獨立抽檢完成；季度抽檢限已記錄來源與欄位，NAS 復原演練待驗 |
| 事件後描述統計 | `local.event_study`、`event_outcomes.py`；[事件統計](EVENT_STUDY.md) | 新版讀未裁剪研究事實，舊版標 display_graph_only；凍結首次保存基準與後續值 |
| 網頁／私有預覽 | `index.html`、`history.html`、`event-study.html`、`js/`；[使用手冊](USER_MANUAL.md) | 股票池／搜尋／來源、兩類提醒、歷史及事件頁；私有頁由本機工具供應，不是公開後端 |

最近功能里程碑：`690d3f3` 私有研究整合 → `665a489` 研究提醒 → `c56b985` 歷史比較／抽檢 → `115bd7c` 事件後描述統計。更舊的「尚未選A/C」「缺uv.lock」或「只有69項測試」不是目前狀態。

## 4. 測試證據與限制

最新候選 `ecd176b` 的[審查修復重驗](VERIFICATION-2026-11-17-REVIEW.md)：完整 `local.check --frontend` exit 0，490 pytest、246 subtests、55 Node tests；未另跑 unittest。來源 hash 已修正，在 `/private/tmp` 留存81個正確來源雜湊且排除私有產物。真實模型四情境及四份 audit 引用未變模型模組於 `3834c19` 的驗證；本候選另重跑兩市場首次與全快取。既有合成瀏覽器回歸圖譜12、歷史9、事件7、新版事實9組通過，另完成只讀 Pages 與兩市場真實研究三頁的桌機／手機驗收。使用原 Cytoscape 3.30.4 CDN、原生 fetch／WebCrypto，沒有替換成功路徑。

05／06／07 的原始官方擷取證據仍保留。本輪重讀其 bytes、重新正規化財務且與08已核對輸入相同，在全新 ledger／runs 合併財務新版與未確認行情原值。每市場兩版、每版8筆完整 facts；首次編碼2文件／1配對，重跑 encoded=0、pairs=0、loader=0。各市場一個營收事件，後續數值均為 insufficient_data 或 pending，沒有真實 observed 結果。完整金融／模型 bytes、報告與截圖只留私有。

Linux／NAS、完整歷史、每日穩定性、其餘季度產業與期別、籌碼／公告適配及真實投資品質待驗。單次下載、hash、模型執行或工程綠燈都不能替代來源尺度、授權或金融有效性。較早[事件驗證](VERIFICATION-2026-11-16-EVENTS.md)保留為歷史，不冒稱本輪執行。

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

依[待開發清單](DEVELOPMENT_BACKLOG.md)執行：先補行情來源範圍與同日獨立參考，維持09／10未完成；接著依依賴推進季報／籌碼／重大訊息適配、交易日與修訂完整性、容量／復原及真實資料觀察。網路失敗要記錄失敗，不繞過封鎖；可先完成離線適配和測試，不因名單等待而停掉其他工作。

沒有新的必要決策時不要每一步詢問。完成一項需留下變更、對應測試、範圍限制與文件；不能只用測試數量稱專案完成。進度細項維護在待開發清單，功能語意維護在各專章，驗證結果另外寫帶日期及Commit的紀錄。

### 交給下一位開發者／新對話的指令

> 請接手 `fastyangmh/stock-knowledge-graph`。先讀 `docs/HANDOFF.md`、`docs/DEVELOPMENT_BACKLOG.md` 與最新驗證紀錄，確認遠端HEAD和本地差異後跑本地基準。沿用Linux／uv／SQLite／GitHub Pages、雙來源名單暫緩、自選股票私有研究、價量與營收分開提醒、事件後描述統計A。依最新整合證據補P1-02行情缺口；P0-01/P0-02/P1-01本輪範圍及P2-01工程已驗，後續依backlog推進，不以名單阻塞、不重問已決策事項；不改公開金融資料、不啟用排程／付費／交易。一般修復與驗證持續進行，只有待辦文件列明的實質決策才停下確認。每次提交前保護既有修改、驗證對應內容與連結，區分真實來源和合成測試結果。
