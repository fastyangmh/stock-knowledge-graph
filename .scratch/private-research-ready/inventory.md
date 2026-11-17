# 程式與待辦核對紀錄

日期：2026-11-17；HEAD：`8adf7f68fdbb4b221686bcf45c2c83b596902795`。
這是靜態盤點，不是產品重驗。由 `115bd7c` 到 HEAD 的差異是文件、skills 與設定，核心功能版本未變。
目前沒有 ADR 目錄；遵守 HANDOFF 的較新決策。原碼／測試的存在不表示本輪跑過。

## 第一階段實際落差

| Backlog | 程式證據 | 現況與規劃影響 |
| --- | --- | --- |
| [P0-01](../../docs/DEVELOPMENT_BACKLOG.md) | [pyproject](../../pyproject.toml)、[check](../../local/check.py)、[semantic](../../local/semantic.py)、[research 測試](../../local/tests/test_research.py) | optional dev 是 pytest >=8,<10，dependency group 是 >=9.2.0；先重現 lock，不因重複就改依賴。check 不下載模型，未自帶完整 commit／uv／Node／模型身分記錄，驗收證據須補齊。已有 injected encoder 與 cache 測試；缺 Python 3.11＋固定真實模型的實測證據。 |
| [P0-02](../../docs/DEVELOPMENT_BACKLOG.md) | [首頁](../../index.html)、[圖譜 harness](../../scripts/browser_smoke.py)、[歷史 harness](../../scripts/history_browser_smoke.py)、[事件 harness](../../scripts/event_browser_smoke.py) | 首頁固定 3.30.4。圖譜即使 loopback 模式仍攔截 CDN 以本機 JS 代替；另兩頁使用 about:blank／替換 fetch。需補真實傳輸，不能把 Python HTTP＋記憶體 DOM 分開通過合稱整合通過。 |
| [P1-01 公司營收](../../docs/DEVELOPMENT_BACKLOG.md) | [registry](../../local/official_datasets.json)、[collector](../../local/collect_official.py)、[adapter](../../local/official_adapter.py)、[import](../../local/official_import.py) | 已啟用 TWSE 兩來源；TPEx 兩來源有 review 記錄但 disabled。collector 保存 bytes、hash、URL、時間，尚未保存完整 content-type／status／欄列日期輪廓與結構化失敗紀錄。adapter 在選股後才核對出表日，不能聲稱全檔混日期已驗證；月營收月份／出表日規則需依真實來源契約判斷。 |
| [P1-01 行情](../../docs/DEVELOPMENT_BACKLOG.md) | [market_prices](../../local/market_prices.py)、[market_graph](../../local/market_graph.py)、[行情測試](../../local/tests/test_market_prices.py) | TWSE／TPEx 各有固定 CSV 契約。全列交易日先核對，再篩選 symbols。fetch 只回傳 bytes，回應 metadata 未完整保留。DB／raw／private bundle 整合已有合成測試。read_prices 要指定單一 feed／交易日；research 亦為單市場入口。 |
| [P1-02](../../docs/DEVELOPMENT_BACKLOG.md) | [financial_review](../../local/financial_review.py)、[official_adapter](../../local/official_adapter.py)、[event_outcomes](../../local/event_outcomes.py) | 月營收金額、行情價格／成交額仍 source_reported。financial_review 已有 Decimal 比對、unknown unit 與零筆不成功、exit 2，但不負責行情；行情需獨立核對紀錄。季度欄位使用 statement_scope／report_basis，事件可比較鍵用 consolidation／value_basis；來源尺度版本化時須明確對應，避免欄位名稱不同而遺失定義。 |
| [P2-01](../../docs/DEVELOPMENT_BACKLOG.md) | [research](../../local/research.py)、[audit](../../local/bundle_audit.py)、[saved_facts](../../local/event_outcomes.py)、[event_study](../../local/event_study.py)、[archive](../../local/research_archive.py) | research 先 replay／attach 再 lifecycle export；未寫獨立完整事實檔。audit 的檔案 allowlist 目前不接受新契約檔；Bundle 只有 graphs 等。saved_facts 直接走主股 graph nodes。archive 又會預算所有 JSON，不能只擴 audit 卻忘記預覽的容量語意。 |
| [P2-04](../../docs/DEVELOPMENT_BACKLOG.md) | [research_history](../../local/research_history.py)、[market_prices schema](../../local/market_prices.py) | 財務 ledger 有 observed_at／recorded_at、hash／replay；不是完整撤回模型。行情觀察表沒有獨立本地 recorded_at；不能因財務 ledger 有此欄位就推論全系統已是雙時間。P2-01 只能忠實保存既有時間及明示缺口，完整遷移屬 P2-04。 |

## 其餘 backlog 核對

| 原 ID | 已有基礎／尚缺部分 | 里程碑 |
| --- | --- | --- |
| P0-03 | [backup](../../local/backup.py) 提供 SQLite create／verify／restore；外部 raw、ledger、bundle 與 NAS 整包演練未完成 | M5 |
| P1-03／04／05 | [schema](../../local/schema.sql) 有 financial_metrics、chip_metrics、documents；目前官方 adapter 僅 companies／monthly_revenue，通用資料表不能充當已完成季度／籌碼／公告來源適配 | M3 |
| P2-02 | [trading_calendar](../../local/trading_calendar.py) 只讀人工提供 CSV 的 date／is_open；沒有官方下載、臨時休市及停牌／缺檔分類 | M2 |
| P2-03 | 行情保留 source_unadjusted；無公司行為適配／還原因子／跨基準可比較性驗收 | M2 |
| P2-05 | [neighbors](../../local/neighbors.py) 精確 Top-K、semantic 有 max_pairs；尚無 ANN，也沒有代表性真實容量量測 | M5 |
| P2-06 | 各工具已有上限，沒有總儲存盤點與封存 dry-run／政策；保持不自動刪除 | M5 |
| P3-01 | [alerts](../../local/alerts.py)、[alert_inputs](../../local/alert_inputs.py) 已有 2＋4 規則與缺值／來源證據；尚無六規則真實品質評估 | M4 |
| P4A-01 | [event_study](../../local/event_study.py) 已有四狀態分母、首次保存基準；完整事實、真實日曆／修訂與樣本偏誤驗收仍缺 | M4 |
| OPS-01 | [run_after_close](../../local/run_after_close.py) 是 cutoff／日曆 gate 與既有預覽流程，並非來源到 research／audit 的完整手動協調器 | M5 |
| REL-01／REL-02 | [publish](../../local/publish.py) 有發布保護；維持公開示範、人工核准及不啟用排程 | 私有閘門外 |
| HOLD-01／HOLD-02 | [combined_universe](../../local/combined_universe.py) 已有聯集；名單暫緩、策略 B 未選定 | 不阻擋 |

所有 ID 的原規格見 [Development Backlog](../../docs/DEVELOPMENT_BACKLOG.md)。

## 文件落差的處置

Glossary 的 Universe 還寫第一階段台灣50；Architecture 等舊文仍有依賴名單／尚無歷史頁的描述；較早來源評估仍列 TW50 或 009816 為待選。
本方案以 HANDOFF 已確認的聯集、名單暫緩、自選股票與現有歷史頁為準，不重新提問。
本輪不改 parent 或歷史驗證紀錄；各實作票更新相關功能文件，10 統一修正現行導覽／術語的陳舊描述，保留歷史紀錄的當時事實。

## P2-01 可以獨立做到哪裡

11／12 可完全使用合成資料、真實本地 SQLite／bundle／HTTP 執行，不依賴官方端點、單位換算、權威日曆、真實模型或指數名單。它們驗收的是「已在本系統且截止前可得的事實不受展示裁剪影響」。

不能藉此聲稱已補完未下載的市場歷史、行情本地登錄時間、撤回事件、正確幣別或交易日連續性。實際金融意義在 M1／M2／M4 補驗；相容欄位未知就保持未知，不補今天或來源時間假裝本地登錄時間。
