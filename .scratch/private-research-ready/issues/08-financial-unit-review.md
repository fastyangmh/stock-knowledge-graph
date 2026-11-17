# 08: 月營收單位版本與獨立抽檢

**What to build:** 讓研究者知道真實月營收數值的幣別、倍率與時間定義，透過獨立原始公告核對後才使用可比較金額。

**Parent:** [P1-02](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** [05：公司／月營收全檔到私有研究](05-official-financial-sources.md)
**Status:** ready-for-agent
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 逐採用財務來源查明原始金額尺度、幣別、合併／個別、月期別、公告／觀察時間；保留來源原始定位與版本證據，不請使用者猜尺度。
- [ ] 至少兩檔公司、來源實際可得期別，以及每個宣稱支援的金額／年增／月增欄位，具非由被測輸出產生的獨立 reference；沒有的欄位明示未驗收。
- [ ] financial_review 實際產生非零比較；預設誤差 0，有合理四捨五入例外才留依據；差異、未知單位／幣別、缺資料及 exit 2 都不能當成功。
- [ ] 若證據支持尺度轉換，新增明確正規化版本，原始值與依據可追溯；raw→新版→research／audit→財務比較與事件可比較性一致。舊 bundle／ledger 不就地改寫。
- [ ] 單位／幣別／statement_scope／report_basis 及事件既有定義欄位有一致映射，衝突拒絕；同數字不同尺度、未知／缺幣別不得誤判可比較。
- [ ] 季度／單季／累計等未由本票取得真實來源的範圍明示未涵蓋，留 P1-03；不以月營收抽檢宣布季度已驗收。

## Testing seam

官方輸入→新版正規化→research→audit，financial_review CLI 與 event 對可比較性的可見結果；沿用財務抽檢及 unknown-scale 事件測試。

## Demonstration

獨立公告與同定義數值相符時非零通過；改倍率／幣別或給未知定義時拒絕比較；舊版本仍可讀。

## Completion evidence

- [ ] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [ ] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

本票尚未實作或驗收。拆票與測試介面按使用者要求合併審閱；詳見[一次確認包](../README.md)。
