# 04: 歷史與事件頁真實 HTTP 瀏覽

**What to build:** 讓使用者經私有 HTTP 選擇已保存版本、比較兩類提醒並閱讀事件統計與分母。

**Parent:** [P0-02](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** None (can start immediately；待整體方案確認後)
**Status:** ready-for-agent
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 用固定合成資料產生真實 bundle／事件報告，啟動 research_archive 與 event_study，實際導航本機頁面，不使用 about:blank＋window.fetch 代替傳輸。
- [ ] 桌機／手機驗證歷史版本選擇、比較、返回圖譜、各類提醒獨立顯示與事件證據／分母；返回圖譜時使用固定 3.30.4。
- [ ] 驗證無版本／無事件、非法報告、404／壞 latest、損壞版本、快速切換、錯誤恢復及惡意文字。
- [ ] 實際 HTTP 只允許指定資產／報告與已稽核圖檔；Host、非允許方法／路徑拒絕，不能讀 DB／raw 或列目錄。
- [ ] 保留原有記憶體 smoke 供快速回歸，真實 HTTP 瀏覽器報告另存，記版本、情境、exit code 與 page errors。
- [ ] 若改前端或 server，相關失敗先重現，local.check --frontend 及這兩頁的實際 browser 驗收通過。

## Testing seam

research_archive／event_study 既有 server→實際 HTML／JS；沿用 history／event browser smoke 與 Python HTTP 測試案例。

## Demonstration

從兩份保存版本完成比較，再查看事件四狀態分母；一個錯誤案例後可恢復，敏感路徑始終拒絕。

## Completion evidence

- [ ] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [ ] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

本票尚未實作或驗收。拆票與測試介面按使用者要求合併審閱；詳見[一次確認包](../README.md)。
