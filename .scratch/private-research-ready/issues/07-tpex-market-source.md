# 07: TPEx 行情全檔到私有研究

**What to build:** 讓研究者對 TPEx 股票完成獨立的真實行情與私有研究驗收，不誤用上市市場資料。

**Parent:** [P1-01](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** None (can start immediately；待整體方案確認後)
**Status:** ready-for-agent
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 驗證既有 TPEx 固定端點的實際全檔、HTTP metadata、欄位／列數、交易日期與至少兩檔上櫃股票覆蓋，保留原始 bytes 與 hash。
- [ ] 為所選上櫃股票準備有證據的獨立正規化公司／營收輸入；可驗證並啟用已登錄 TPEx 來源，但須另存其來源與欄位證據，不能借上市公司輸入冒充真實整合。
- [ ] 完成 TPEx raw→market DB→單市場 research→audit；不新增跨市場單一 run，也不依賴 05／06 的股票資料。
- [ ] 缺欄位、舊日／混日、缺股票、HTML／403、錯誤市場、部分來源失敗停止且留報告；重跑／修訂與 raw checksum 驗證通過。
- [ ] 若端點或必要上櫃財務輸入不可取得，保留受阻，不用合成資料標成真實驗收，也不繞過封鎖。
- [ ] 針對 TPEx 格式的必要修復加入合成失敗回歸；若重用下載證據元件，維持兩市場各自契約與成功指標。

## Testing seam

TPEx market_prices→research→audit，既有來源 registry／import 可按實際需要重用；沿用 TPEx schema 與市場隔離測試。

## Demonstration

至少兩檔上櫃股票的 private bundle 可追溯到 TPEx 真實證據；錯用 TWSE feed 明確失敗。

## Completion evidence

- [ ] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [ ] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

本票尚未實作或驗收。拆票與測試介面按使用者要求合併審閱；詳見[一次確認包](../README.md)。
