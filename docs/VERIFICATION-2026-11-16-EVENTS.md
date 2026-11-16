# 本地驗證｜事件後描述統計（2026-11-16）

[文件中心](README.md) · [功能與操作](EVENT_STUDY.md) · [前次完整驗證](VERIFICATION-2026-11-16-HISTORY.md)

## 基準與環境

基準Commit為 `c56b985a59fc65c6259a9aa87f716c43e21d48e2`。容器直接git clone仍因DNS失敗，透過GitHub連接器下載該版本既有Pages artifact，只作原始檔傳輸，不以CI結果驗收、不重新觸發GitHub CI。解包後計算local/js/css/scripts/docs/data的Git tree SHA-1，與遠端完全一致。

使用現有Linux、Python 3.13.5、pytest 9.0.2、Node 22.16.0、Playwright／系統Chromium。未重建Python 3.11的uv.lock環境，未下載真實模型或官方金融資料。沒有修改依賴或公開data/。

## 實際執行

| 檢查 | 結果 |
| --- | --- |
| 修改前完整本地驗收 | 344項Python及39項JavaScript通過 |
| 修改後完整本地pytest | **410 passed、154 subtests passed，24.19秒** |
| 獨立unittest本地驗收 | **Ran 410 tests，OK，22.678秒** |
| Node語法及測試 | **53 tests、53 pass、0 fail** |
| 語法與既有SQLite→JSON smoke | exit 0，3股票匯出及驗證成功 |
| 新功能端到端 | 虛構官方欄位CSV→真實SQLite→研究bundle→整包audit→事件統計CLI→私有JSON，通過 |
| 真實本機HTTP | GET/HEAD、Host、allowlist、POST拒絕、記憶體快照不可變，通過 |
| 新事件頁Chromium | **11組情境通過，page_errors=[]** |
| 既有圖譜／歷史頁Chromium重跑 | **13組＋9組通過，page_errors=[]** |

本輪新增66項Python及14項JavaScript測試。pytest／unittest是同一套測試，不把兩個runner相加計數。數值是當次執行紀錄，不是效能保證。

## 覆蓋重點

固定首次保存事件基準；實際完成時間晚於歷史cutoff時不回填事件；同股票／規則／期別／定義／方向重跑去重；未來版本排除；同日報價不作後續期；首次保存值不被較晚修訂覆寫；同時衝突拒絕；相鄰報價缺口、零分母、缺收盤、來源／尺度變化與未知金額幣別分開處理。

月份比較涵蓋跨年、閏年、精確月份而非最近月份替代、月份未結束、較晚本地登錄、最新期缺年增率不退回舊期；負年增率改善不誤稱為轉正。事件、事實數量、工作量與報告預算均有明確失敗測試。

分組保留事件總數與可計算分母，資料不足／不可比較不變成0；平均、中位數與範圍只在同規則／定義／方向／來源／期間內計算。無有效樣本為null，不產生勝率／綜合分數。CLI拒絕覆寫不同報告、輸入目錄、設定檔及symlink。稽核失敗的版本不會默默被排除以形成較好結果。

## 瀏覽器界線

新頁面使用實際HTML/CSS/JS和about:blank記憶體虛構報告，不導航正式Pages或任何市場網站；沒有外部JavaScript依賴。檢查兩類獨立統計、分母、缺值、可展開證據、安全文字DOM、分批顯示、390px手機版，以及非法報告／404／無事件提示。

原圖譜仍使用本機Cytoscape 3.33.1測試，網站CDN3.30.4未更換，非正式CDN逐bytes驗收。本機HTTP以Python獨立實測，不以記憶體fetch代替網路存取檢查。

## 未完成／不宣稱

不驗證真實來源完整性、原始財報數值、官方交易日曆、公司行為還原、歷史樣本選擇偏誤、提醒投資有效性或完整策略回測。只讀已保存且通過稽核的展示數值，未重新執行每個原始CSV驗證，不把既有raw_verified旗標當新驗收。事件後描述統計不能推論交易獲利或因果關係。

本次不修改公開金融資料、Python套件、GitHub workflow或部署方式，不啟用排程或交易。新增測試自動納入 `local.check --frontend`；單獨事件頁可用 `scripts/event_browser_smoke.py --chromium <path> --report <private path>` 重跑。所有測試紀錄只適用對應來源版本。
