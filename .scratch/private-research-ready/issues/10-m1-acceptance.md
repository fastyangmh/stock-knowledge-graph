# 10: M1 真實私有整合驗收與證據索引

**What to build:** 讓研究者在同一候選版本確認目標環境、真實來源、尺度抽檢與三頁私有使用流程共同成立，取得第一里程碑的可審閱證據。

**Parent:** [P0-01、P0-02、P1-01、P1-02](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** [02：真實模型與增量快取四情境](02-real-model-cache.md)、[03：圖譜真實瀏覽器與固定 CDN](03-graph-browser.md)、[04：歷史與事件頁真實 HTTP 瀏覽](04-history-event-browser.md)、[08：月營收單位版本與獨立抽檢](08-financial-unit-review.md)、[09：行情單位與交易範圍抽檢](09-market-unit-review.md)
**Status:** ready-for-agent
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 固定最終 Commit、lock、模型 revision 與來源契約版本；上游證據若不對應影響範圍，重跑相關驗收，不盲目引用舊綠燈。
- [ ] 在目標 Linux 以明確代碼分市場完成真實下載→正規化→SQLite→research／alerts→audit→歷史比較→事件報告與三頁瀏覽。
- [ ] 至少保存可比較的兩個成功版本並驗證同輸入重跑與部分失敗；資料來源日期如實記錄。真實事件／後續資料不足就顯示無事件／insufficient_data，不為驗收捏造提醒。
- [ ] 兩市場公司／營收輸入都具來源與尺度核對證據；若 07 額外採用來源未被 08 涵蓋，補做同一抽檢準則，不能默認 TWSE 結論適用 TPEx。
- [ ] 01～09 必要條件都有成功證據；受阻／未執行不能用替代 fixture 結案。真實模型、來源、獨立抽檢、瀏覽器各自列出。
- [ ] 整合失敗保留舊成功 pointer／bundle；公開示範內容 hash 不變，沒有自動 push／排程／交易。
- [ ] 更新功能文件、現行術語／導覽、交接與原 backlog 的實際狀態／證據；保留歷史驗證紀錄，明示 M2～M6 未完成。

## Testing seam

現有使用者 CLI 與真實私有 server 端到端；只補驗收流程／證據索引，不提前實作 OPS-01 的通用手動協調器。

## Demonstration

由一份證據索引重跑到瀏覽器，能查出每個數字來源、尺度及未完成範圍，且四個優先 backlog 各有對應證據。

## Completion evidence

- [ ] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [ ] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

本票尚未實作或驗收。拆票與測試介面按使用者要求合併審閱；詳見[一次確認包](../README.md)。
