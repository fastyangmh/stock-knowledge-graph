# 05: 公司／月營收全檔到私有研究

**What to build:** 讓研究者使用已啟用的 TWSE 公司與月營收官方全檔，以明確股票代碼建立有下載證據的私有研究版本。

**Parent:** [P1-01](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** None（已核准並完成本票驗收）
**Status:** resolved
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [x] 逐一核對既有來源與當次欄位契約；保存實際全檔 bytes、取得時間、URL、HTTP status／Content-Type（缺少明示）、hash／大小、欄位／列數、出表日／資料年月分布與所選股票覆蓋。
- [x] 補足全檔輪廓檢查，不只查所選列；公司出表日、營收月份、取得日分別處理，禁止把資料日改成今天。非允許混雜明確停止。
- [x] 至少兩檔明確上市代碼完成 download→normalize→SQLite→research（analysis none 即可）→audit，不要求模型或名單。
- [x] 403、HTML、缺欄位、日期錯誤、缺股票、部分來源失敗均產生可辨識失敗紀錄，不更新整批成功指標，舊成功版本仍可讀。
- [x] 離線合成回歸先證明新增欄位／錯誤需求的失敗再修復；真實來源失敗不能用 fixture 替代結案。
- [x] 單位未查清仍 source_reported，金額可比較性由 08 驗收；此票不將正常下載等同尺度已核對。

## Testing seam

collect_official／official_import／research／bundle_audit 的使用者入口；重用 official adapter 與 explicit symbols 整合測試。

## Demonstration

兩檔真實公司／月營收資料產生 audited bundle，另展示第二來源失敗時舊 manifest 與成功 bundle 不變。

## Completion evidence

- [x] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [x] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [x] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

2026-11-17 完成。實作 Commit `1082584b0801b967e68f35d43d4183f0c2a8329d`，已整合
`465481e`。最終 clean-worktree `local.check`：421 passed、163 subtests passed、exit 0。
新增9項合成CLI回歸，逐步先red後green；來源相關31項通過。首次沙盒DNS與loopback
限制皆依正常 escalation 處理，未繞來源封鎖。

真實已啟用TWSE公司／營收全檔各1099／1091列，HTTP200、text/csv；公司出表日
2026-11-16、營收出表日2026-11-17／資料月份2026-10，保留不同日期維度。
2330／2454完成 download→normalize→SQLite→research(analysis none)→audit，
三個後續CLI均exit0，audit valid1/invalid0。真實已存資料加合成第二來源403證明
舊manifest/latest/DB不變且舊bundle仍可稽核。尺度保持source_reported，08另行驗收。

完整命令、環境、hash、TDD與範圍見
[獨立驗證紀錄](../../../docs/VERIFICATION-2026-11-17-OFFICIAL-FINANCIAL.md)，
功能契約更新於[管線](../../../docs/DATA_PIPELINE.md)及
[來源文件](../../../docs/DATA_SOURCES.md)。私有證據保存在主repo
`local/private/m1/05/`；原始bytes、DB、報告不提交，公開data未改。
本票無外部阻礙；P1-01其他市場／行情及整體M1不因此結案。
Parent backlog／HANDOFF由整合負責人同步，不由本票覆寫平行工作。
