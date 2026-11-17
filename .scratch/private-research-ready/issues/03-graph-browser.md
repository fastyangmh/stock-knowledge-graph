# 03: 圖譜真實瀏覽器與固定 CDN

**What to build:** 讓桌機與手機使用者以實際 HTTP／HTTPS 開啟圖譜，能驗證正確版本並從載入錯誤恢復。

**Parent:** [P0-02](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** None (can start immediately；待整體方案確認後)
**Status:** ready-for-agent
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 沿用 Cytoscape 3.30.4，成功路徑實際載入原 CDN HTTPS 回應，記資產版本／hash、瀏覽器版本及回應結果；不得以本機 3.33.1 代稱通過。
- [ ] 透過既有 private preview 服務導航實際頁面，真實 WebCrypto 驗證正確 bytes；故意錯版／錯 hash 必須拒絕並清除舊圖。
- [ ] 驗證搜尋／股票池篩選、空結果後恢復、快速切換晚到回應、HTTP 失敗恢復、來源惡意文字與安全連結、手機適配。
- [ ] 另只讀驗收既存 Pages 示範與 HTTPS／CDN；不部署驗收資料或改變原部署方式。
- [ ] 記錄 HTTP 成功路徑及有意故障注入的差別；瀏覽器政策／CDN 不通保持受阻，不修改政策或偷換 CDN。
- [ ] 前端修復先有可見失敗案例，再執行 local.check --frontend 與實際瀏覽器；私有 DB／raw 路徑不可存取。

## Testing seam

既有 preview HTTP→實際首頁與 DOM／WebCrypto；沿用 graph smoke 案例，受控故障 server 可用，成功路徑不替換 fetch。

## Demonstration

正常載圖、hash mismatch 拒絕、重新選股恢復；手機可操作；附實際 CDN 與 Pages 只讀證據。

## Completion evidence

- [ ] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [ ] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

本票尚未實作或驗收。拆票與測試介面按使用者要求合併審閱；詳見[一次確認包](../README.md)。
