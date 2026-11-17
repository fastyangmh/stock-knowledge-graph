# 06: TWSE 行情全檔到私有研究

**What to build:** 讓研究者下載 TWSE 實際盤後全檔，將所選股票的原始行情連到私有研究並稽核。

**Parent:** [P1-01](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** None (can start immediately；待整體方案確認後)
**Status:** resolved
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [x] 保存已登錄端點當次 HTTP 與完整 raw 證據，含全檔欄位／列數／日期、所選股票覆蓋與 hash；expected-date 僅作來源日期斷言。
- [x] 至少兩檔股票完成 raw→market DB→research→audit；串接使用獨立合法財務輸入並記來源，不假定 05 已完成。
- [x] 回應全列交易日一致；缺股票、缺欄位、混日／舊日、重複股票、非有限或非法數值、HTML／403 停止且有失敗報告。
- [x] 同一觀察冪等、較晚修訂可追溯；失敗保留舊行情成功報告／研究 pointer，raw 改寫或 checksum 不符不可接受。
- [x] 回歸使用合成資料，真實全檔另驗收；價格／成交額維持未知尺度直到 09，不因欄位存在就確認幣別。
- [x] 若已有其他來源票完成可重用的證據紀錄實作，直接重用；不要依複製貼上建立第二套錯誤／metadata 語意。

## Testing seam

market_prices→market_graph→research→audit；沿用真實 SQLite、原始快照驗證與市場測試。

## Demonstration

兩檔 TWSE 股票可追溯到實際全檔 hash；將回應換成舊交易日即停止且舊成功結果保持。

## Completion evidence

- [x] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [x] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [x] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

2026-11-17：已實作 `7d1c753`，整合驗收基準 `02222d6`（含 11）。真實 TWSE HTTP 200，1,391 列全為 2026-11-17、2330／2454 各一列；合法財務輸入重用 05 的 `acceptance-1082584/normalized.json`，有獨立來源／hash 記錄。兩檔行情→SQLite→research→audit 成功；新 bundle 亦包含 8 筆未裁剪 facts。價格尺度留 09。

完整檢查 447 passed、187 subtests；定向 53 passed、52 subtests。沙盒 DNS／loopback 限制經正常 escalation 重跑成功。macOS 為本輪使用者接受環境，Linux 未驗證。見[專用驗證紀錄](../../../docs/VERIFICATION-2026-11-17-TWSE-MARKET.md)；私有完整產物在 `local/private/m1/06/`。本票不關閉 P1-01 的其他來源或 P1-02 尺度工作；parent backlog 由整合票同步。
