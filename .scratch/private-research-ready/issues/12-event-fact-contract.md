# 12: 事件統計改讀新契約並揭露舊版限制

**What to build:** 讓新事件統計使用已稽核的未裁剪數值，並在報告與頁面清楚區分舊版展示範圍。

**Parent:** [P2-01](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M2 預備線；不阻擋 M1
**Blocked by:** [11：未裁剪研究數值的保存與稽核](11-unpruned-facts.md)
**Status:** resolved
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [x] 事件工具經 audit 取得新事實，使用新分析版本與穩定事實引用；不直接開 SQLite、不靠展示 node 是否存在，也不重新抓來源。
- [x] 同一事實／提醒／固定時間以兩種展示上限產生 bundle，事件總數、各狀態分母與結果相同；僅忽略 run ID 等識別差異。
- [x] 維持首次實際保存事件基準、首次後續值與四種 outcome 狀態；晚到資料／更正不回填既有基準，仍稱第1／5／20筆觀察與1／3／6曆月。
- [x] 純舊 bundle 可用原版本讀取，JSON 與 UI 都標 display_graph_only；新契約缺漏／損壞不可偷偷退回 graph。
- [x] 混合目錄必須明確選定分析範圍並揭露新舊 cohort、納入／未納入數量與理由；不跨範圍合併分母，不以新契約假補舊事件基準，沒有靜默排除。
- [x] 事件與事實／訪問工作量／報告 bytes 預算仍有效；未知版本、無樣本、不可比較來源尺度、右設限與篡改有外部行為回歸。
- [x] 實際本機 HTTP／瀏覽器可看見分析版本、資料範圍及限制；server allowlist 不暴露完整事實／DB／raw。
- [x] local.check --frontend 與對應瀏覽器通過；記工程驗證與真實資料尚待結合範圍，不將此票當 P4A-01 全部完成。

## Testing seam

research→audit→event_study→本機事件頁；沿用 EventIntegrationTests、事件純規則及 browser 案例。

## Demonstration

裁剪前後圖不同、統計相同；舊版本限制明示，新檔篡改立即失敗，後續修訂不改首次基準。

## Completion evidence

- [x] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [x] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [x] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

2026-11-17 完成。功能提交 `4e59adc`，合併 integration 後以 `5b9913001f1ac5180ea3b02fb44df981af7f7b3e` 驗證：459 pytest／193 subtests、55 JS；真實 loopback HTTP／Chromium 專用 9 組通過。環境為使用者目前可用的 macOS arm64；Linux 未驗、不阻擋本輪工程交付。資料為合成，未宣稱真實金融品質或 P4A-01 完成。

驗證與重跑命令：[專用紀錄](../../../docs/VERIFICATION-2026-11-17-EVENT-FACTS.md)。私有證據 `local/private/m1/12/`；來源 hashes 有相對路徑補充。功能文件已更新；parent backlog／HANDOFF 由整合負責人同步，子票不關閉整個 parent。
