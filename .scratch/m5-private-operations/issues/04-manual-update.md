# 04 · 分階段手動更新到已稽核的私有研究版本

**Parent:** [OPS-01](../../../docs/DEVELOPMENT_BACKLOG.md#ops-01完整手動更新流程) · [規格](../spec.md)

**What to build:** 維護者執行一次手動更新，逐市場看到來源日期、當期完整性、磁碟水位、各階段狀態與最後成功版本。

**Blocked by:** 已有來源與已核准的市場日曆介面；01 報告可獨立使用

**Status:** resolved

- [x] 從已核准來源的取得、正規化、行情到 research／兩類提醒／audit 提供可選階段，允許用先前已驗 hash 的快照重跑。區分月報期別、取得日與交易日。
- [x] 以臨時 SQLite 及本機檔案驗證休市、外部來源失敗、安全重試、audit 失敗及同輸入重跑，任何部分失敗保全舊成功 pointer。端到端成功路徑使用既有真實研究入口。
- [x] 私有報告列成功、跳過、缺檔、不新鮮與失敗原因，預留退出碼供人工操作。以至少一次實際兩市場手動執行記錄資料來源與限制。

## 實作與驗收

候選 `5ce10565df5e0dce7204ff504ceb371b8a7490ca` 在 macOS arm64、Python 3.11.11 完成驗收。入口、設定與各階段的輸出見[私有手動更新手冊](../../../docs/MANUAL_UPDATE.md)。

- 合成 CLI 使用臨時 SQLite 與原始 CSV，10 個測試、5 個子情境通過。已測第二個財務來源連線失敗後只補抓缺的來源、舊營收期別補抓、缺行情檔、行情日錯誤、開休市證據衝突、日曆未知、磁碟閾值、輸入 hash 改變及相同 job 重送。候選提醒被改寫、作業報告無法寫入、其他 job 提前提升或行情庫出現不同原件時，原成功指標保持原 bytes。
- 真實重播從 `m6-preflight/restore-inputs.json` 和既有研究報告找出 11/17、18 的 TWSE 11549、TPEx 11371 原件；公司、月營收、單位核對附件與兩市場官方日曆各自重新核對 hash。兩市場均從空的獨立作業根目錄開始，沿用已保存、逐檔核對的 MiniLM revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`，使用離線快取。
- TWSE、TPEx 各選兩檔；公司報表日期 11/16，月營收出表日期與兩來源取得日 11/17，營收期別均為 2026-10。兩份正規化輸出與 M1 08 核對過的 v2 輸入逐位元相同。兩個新候選各實際編碼兩份文件、比較一對、保存八筆研究事實。價量與月營收分列，各市場本次為零個觸發價量、一個觸發營收。兩份外部 `local.bundle_audit` 都通過。
- 每市場先停在 `research`，證實正式指標尚不存在；續跑 audit 才出現指標，再送同一 job 時行情新增為 0、指標 bytes 相同。用正式日曆重播 11/15 休市、11/18 超出日曆已核對範圍，後者 exit 2、原指標保持。行情本輪標記本地重新觀察，日期仍取實際 CSV。
- 私有重跑工具及原始輸出留在 `local/private/m5-manual-2026-11-19/ops01-v1/`。該處 `exercise.py` 產生 `replay-5ce1056/`，其 `summary.json`、分市場的 `*-command.json`、報告、原件、SQLite 與 bundle 可用來重驗。各作業根位於 `replay-5ce1056/operations/<market>/`。
- 完整套件以 `uv run --locked python -m local.check --frontend` 驗證。第一次受限沙箱無法通過 loopback 情境，保留 `full-sandbox-5ce1056.json`。依環境權限重跑 exit 0，667 個 pytest、410 個 subtests、55 個 Node 測試通過，證據為 `full-5ce1056.json`。
- 本次網路取得與失敗重試使用合成 HTTP 邊界。實際兩市場使用既有官方原件，未測此次線上來源是否到件或每日穩定性。Linux／NAS 實機另驗，M1 09／10 仍為 `needs-info`；行情的官方尺度及交易範圍不因通過此票改變。

## 雙軸重驗

兩市場真實原檔在模擬 HTTP 邊界各注入一格錯值，只補抓月報。兩市場的候選提醒及報告寫入故障均維持舊 catalog、事件輸入與 latest，同 job 重試可完成。[修復、操作與私有證據](../../../docs/VERIFICATION-2026-11-19-M5-REVIEW.md)
