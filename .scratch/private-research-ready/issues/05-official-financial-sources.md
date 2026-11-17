# 05: 公司／月營收全檔到私有研究

**What to build:** 讓研究者使用已啟用的 TWSE 公司與月營收官方全檔，以明確股票代碼建立有下載證據的私有研究版本。

**Parent:** [P1-01](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** None (can start immediately；待整體方案確認後)
**Status:** ready-for-agent
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 逐一核對既有來源與當次欄位契約；保存實際全檔 bytes、取得時間、URL、HTTP status／Content-Type（缺少明示）、hash／大小、欄位／列數、出表日／資料年月分布與所選股票覆蓋。
- [ ] 補足全檔輪廓檢查，不只查所選列；公司出表日、營收月份、取得日分別處理，禁止把資料日改成今天。非允許混雜明確停止。
- [ ] 至少兩檔明確上市代碼完成 download→normalize→SQLite→research（analysis none 即可）→audit，不要求模型或名單。
- [ ] 403、HTML、缺欄位、日期錯誤、缺股票、部分來源失敗均產生可辨識失敗紀錄，不更新整批成功指標，舊成功版本仍可讀。
- [ ] 離線合成回歸先證明新增欄位／錯誤需求的失敗再修復；真實來源失敗不能用 fixture 替代結案。
- [ ] 單位未查清仍 source_reported，金額可比較性由 08 驗收；此票不將正常下載等同尺度已核對。

## Testing seam

collect_official／official_import／research／bundle_audit 的使用者入口；重用 official adapter 與 explicit symbols 整合測試。

## Demonstration

兩檔真實公司／月營收資料產生 audited bundle，另展示第二來源失敗時舊 manifest 與成功 bundle 不變。

## Completion evidence

- [ ] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [ ] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

本票尚未實作或驗收。拆票與測試介面按使用者要求合併審閱；詳見[一次確認包](../README.md)。
