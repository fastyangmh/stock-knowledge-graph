# 09: 行情單位與交易範圍抽檢

**What to build:** 讓研究者辨識 TWSE／TPEx 價格、成交量及成交值的確切尺度與涵蓋範圍，並避免不同基準被當成同一數列。

**Parent:** [P1-02](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** [06：TWSE 行情全檔到私有研究](06-twse-market-source.md)、[07：TPEx 行情全檔到私有研究](07-tpex-market-source.md)
**Status:** needs-info
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [ ] 兩市場各至少兩檔、各一個真實來源交易日，以獨立官方頁／文件核對 OHLC、成交股數、成交值、筆數及交易範圍；每個欄位有來源定位與版本。
- [ ] 確認股／張、價格幣別／倍率、成交值尺度、零股／鉅額等是否納入；未確認項維持 unknown／source_reported 並使該驗收未完成。
- [x] 產出私有核對報告，列採樣數、原始與參考 hash、差異、誤差設定、日期／範圍及待解項；不把行情硬轉成財務指標來通過 financial_review。
- [x] 需要轉換時保留原始 decimal 精度與有版本定義；market_graph 重新驗證 raw 時可讀舊版並正確驗證新版，不因新增單位欄位破壞來源一致性檢查。
- [x] 提醒／事件不混來源、幣別／尺度或價格基準；舊資料不靜默轉換，不實作公司行為還原，source_unadjusted 的限制明示。
- [x] 同數字不同尺度、股張誤用、raw 不一致、跨版本比較與零筆抽檢有失敗回歸；真實數值核對與合成邊界分列。

## Testing seam

market_prices／market_graph／research／audit→私有核對報告與提醒／事件可比較性；沿用行情與事件的來源／尺度拒絕案例。

## Demonstration

兩市場各有非零獨立比較；故意把股改張或幣別／基準改掉時不能產生假相符結果。

## Completion evidence

- [x] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [x] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

工程實作與合成TDD已完成，產品提交1037fe1；[行情核對證據](../../../docs/VERIFICATION-2026-11-17-MARKET-UNITS.md)保留原始來源與限制。10於3834c19重跑兩市場正式market_review，仍各exit 2、compared_fields=0。TWSE bulk交易範圍未證明；TPEx同日獨立reference未取得。28欄數字診斷不構成已確認定義，不以同源不同表示或昨日資料結案。

未知項維持source_reported；舊bytes／ledger未改。需要真正取得並核對來源定義及TPEx參考後才可勾選前兩條與設resolved；10依賴gate維持未完成。Linux移轉不是本輪blocker。
