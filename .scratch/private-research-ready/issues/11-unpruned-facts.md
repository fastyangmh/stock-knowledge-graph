# 11: 未裁剪研究數值的保存與稽核

**What to build:** 讓每份新研究 bundle 保存獨立於展示圖大小的完整數值集合，且同一份 audit 能驗證它並保留舊版本可讀性。

**Parent:** [P2-01](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M2 預備線；不阻擋 M1
**Blocked by:** None (can start immediately；待整體方案確認後)
**Status:** ready-for-agent
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 以現有 research 高層入口產生新契約，包含所選股票在 cutoff 可得的全部 replay 財務／既有籌碼數值，以及指定市場截至 trade_date 的本地已保存行情歷史；不以提醒 20 筆或展示上限裁剪。
- [ ] 定義並驗證 schema、producer、選股／市場／日期範圍、事實識別、來源、單位、期間／報表基準、觀察／可得／登錄時間及 raw／正規化證據連結；未知時間明示 unknown，不以 observed_at 補行情 recorded_at。
- [ ] raw 驗證、既有時間 gate 與來源衝突規則保持；未下載的歷史不補齊。缺市場輸入明示未含行情；未知尺度仍原樣保存。
- [ ] 新事實檔納入 report hash 與 audit，從捕捉 bytes 驗證；宣告新契約卻缺檔／壞 hash／未知 schema、未來值、跨股污染、symlink 拒絕。
- [ ] 總 bytes、JSON bytes、筆數與歷史讀取工作量有界；超額明確失敗，不截掉尾端事實，且舊 pointer／bundle 不變。沿用既有限制直到有量測支持調整。
- [ ] 純舊 bundle 仍通過原有 audit 並標示 display_graph_only；新 bundle 在 private history 可正常列出，預覽容量檢查與實際服務範圍區分清楚；HTTP 不暴露 raw、DB 或新完整事實檔。
- [ ] 使用超過展示上限的合成數據，兩種展示政策的完整事實內容一致、圖譜仍有限；提供新／舊／損壞／超額與真實 loopback 回歸。

## Testing seam

research→bundle_audit→research_archive；只新增被 audit 承認的 bundle 契約，不新增公開查詢 API。

## Demonstration

小圖仍只含受限節點，但 audited 研究事實完整；調整展示上限不改事實，篡改新檔會拒絕，舊版仍能開啟。

## Completion evidence

- [ ] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [ ] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

本票尚未實作或驗收。拆票與測試介面按使用者要求合併審閱；詳見[一次確認包](../README.md)。
