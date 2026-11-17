# 10: M1 真實私有整合驗收與證據索引

**What to build:** 讓研究者在同一候選版本確認目標環境、真實來源、尺度抽檢與三頁私有使用流程共同成立，取得第一里程碑的可審閱證據。

**Parent:** [P0-01、P0-02、P1-01、P1-02](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** [02：真實模型與增量快取四情境](02-real-model-cache.md)、[03：圖譜真實瀏覽器與固定 CDN](03-graph-browser.md)、[04：歷史與事件頁真實 HTTP 瀏覽](04-history-event-browser.md)、[08：月營收單位版本與獨立抽檢](08-financial-unit-review.md)、[09：行情單位與交易範圍抽檢](09-market-unit-review.md)
**Status:** needs-info
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [x] 固定本票實測候選 Commit、lock、模型 revision 與來源契約版本；上游證據若不對應影響範圍，重跑相關驗收，不盲目引用舊綠燈。
- [x] 在使用者指定當前macOS，以明確代碼分市場重讀已保存真實下載快照→正規化→SQLite→research／alerts→audit→歷史比較→事件報告與三頁瀏覽；Linux移轉另驗。
- [x] 至少保存可比較的兩個成功版本並驗證同輸入重跑與部分失敗；資料來源日期如實記錄。真實事件／後續資料不足就顯示無事件／insufficient_data，不為驗收捏造提醒。
- [x] 兩市場公司／營收輸入都具來源與尺度核對證據；若 07 額外採用來源未被 08 涵蓋，補做同一抽檢準則，不能默認 TWSE 結論適用 TPEx。
- [ ] 01～09 必要條件都有成功證據；受阻／未執行不能用替代 fixture 結案。真實模型、來源、獨立抽檢、瀏覽器各自列出。
- [x] 整合失敗保留舊成功 pointer／bundle；公開示範內容 hash 不變，沒有自動 push／排程／交易。
- [x] 更新功能文件、現行術語／導覽、交接與原 backlog 的實際狀態／證據；保留歷史驗證紀錄，明示 M2～M6 未完成。

## Testing seam

現有使用者 CLI 與真實私有 server 端到端；只補驗收流程／證據索引，不提前實作 OPS-01 的通用手動協調器。

## Demonstration

由一份證據索引重跑到瀏覽器，能查出每個數字來源、尺度及未完成範圍，且四個優先 backlog 各有對應證據。

## Completion evidence

- [x] 記錄實測 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [x] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

同候選3834c19於使用者指定macOS完成全check --frontend（482 pytest／220 subtests／55 Node）、真實模型四情境、兩市場真實快照／財務新版與原始行情→各自全新ledger／兩個semantic+alerts版本→audit／compare／event與真實三頁桌機手機HTTP；原CDN、WebCrypto及合成故障回歸重跑通過。原快照／舊ledger、公開示範與lock未變。

每市場一個營收事件，無後續資料，結果insufficient_data/pending；未捏造事件或未來數值。財務4組review成功；行情兩市場仍exit2、compared_fields=0，09外部證據gate未過，所以本票維持needs-info，01～09全成功條件與resolved條件不勾選。工程完成不代表M1完成；M2～M6其餘項亦未關閉。

完整命令、環境、失敗／成功與私有證據hash見[整合索引](../../../docs/VERIFICATION-2026-11-17-M1.md)。最終code-review／修復／push由後續整合流程另記，本票未push。


Post-review：`ecd176b` 修復證據覆寫、事件完整定義 identity、check來源hash並重跑本票受影響串接；最新490 pytest／246 subtests／55 Node及兩市場真實三頁通過。原 `3834c19` 證據不覆寫；09行情仍兩次exit2，本票保持needs-info。詳見[審查修復驗證](../../../docs/VERIFICATION-2026-11-17-REVIEW.md)。
