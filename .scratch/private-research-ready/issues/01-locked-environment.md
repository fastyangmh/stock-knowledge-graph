# 01: Linux／Python 3.11 鎖定環境重現

**What to build:** 讓開發者在乾淨的目標 Linux 環境依既有 lock 重跑離線全套檢查，取得可追溯的環境與產物證據。

**Parent:** [P0-01](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** None (can start immediately；待整體方案確認後)
**Status:** ready-for-agent
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 記錄 Commit、dirty 狀態、OS／架構、Python 3.11 實際 patch、uv／Node 版本、lock hash 與每條命令 exit code；若無目標環境，記受阻而非以 macOS 代驗。
- [ ] 完成 uv sync --locked --extra dev 及 local.check --frontend，保留原始報告與摘要；缺 Node 或依賴不得靜默 skip。
- [ ] 核對 optional dev／dependency group 的解析結果；依賴未變時 uv.lock bytes 不變。若實際不相容才最小修改，列出理由與重新鎖定後驗證。
- [ ] 合成測試與 CLI smoke 在隔離 SQLite／JSON 執行；公開示範與私人既有資料未被改寫。
- [ ] 若修復環境相關程式，先留下相關失敗與修復後回歸；沒有修復時不新增鏡像測試。

## Testing seam

local.check 使用者入口、報告與退出碼；重用現有離線全套測試，不把此票當真實模型或官方來源驗收。

## Demonstration

同一 Commit 可在目標環境重跑成功，能由報告辨識實際 runner、版本與合成範圍。

## Completion evidence

- [ ] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [ ] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

本票尚未實作或驗收。拆票與測試介面按使用者要求合併審閱；詳見[一次確認包](../README.md)。
