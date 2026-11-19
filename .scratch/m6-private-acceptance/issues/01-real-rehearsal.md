# 01 · 同版本重建真實研究、獨立核對與復原

**Parent:** [M1～M6 對應的原 backlog ID 與完成條件](../../private-research-ready/completion.md) · [規格](../spec.md)

**What to build:** 在固定候選以兩市場真實來源做一次可追溯、可獨立還原的完整私有研究，交付逐項驗收清單與當前限制。

**Blocked by:** M1～M5 必需功能與實證。可先準備索引和核對既有原件，完整結案依賴同候選實測、行情單位獨立抽檢，以及 Linux／NAS 實際獨立復原。

**Status:** ready-for-agent

- [ ] 依固定設定完成擷取、正規化、SQLite、模型、提醒、研究版本、audit、瀏覽器及歷史／事件描述，記錄來源、股票、期間與每階段結果。
- [ ] 核對每個必要 backlog ID 的完成條件、證據及限制。原始快照與參考來源的版本、時間、定義及獨立性均可追查。
- [ ] 復原至新目的地，驗證原始快照、SQLite、ledger、設定、研究引用、歷史、audit 與舊成功版本。macOS 實跑與 Linux／NAS 獨立演練分別記錄。
- [ ] 更新交接、驗證索引、去敏摘要及對應原待辦，附提交與 push 位置。任一必需驗收缺少證據時保留整體未完成並列明恢復條件。

## Comments

2026-11-19 在乾淨開發候選 `ccb4a44` 先唯讀核對既有輸入。驗證前後各重算同一份清單的 924 個檔案，包含公開示範與私有原件，雜湊全部一致。兩市場的正式 `local.bundle_audit` 皆 exit 0，各三個版本與 latest 均 valid。另重讀 09 正式行情抽檢報告，兩市場仍為 `compared_fields=0`、`needs_review=true`。這次檢查保留了六個既有版本的基準；上方同候選完整重建與跨主機復原均待實測。

在候選 checkout 使用鎖定 Python 執行既有私有證據目錄下的 `m6-preflight/check.py <新的私有輸出目錄>`。程式會重新驗證每個初始檔案、實際執行兩次 audit，並保存兩庫、事件檔與最新指標的雜湊。首次產物在 `local/private/m6-preflight/ccb4a44/`。
