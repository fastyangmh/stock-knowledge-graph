# 01 · 盤點容量、增長與封存候選

**Parent:** [P2-06](../../../docs/DEVELOPMENT_BACKLOG.md#p2-06儲存預算與封存) · [規格](../spec.md)

**What to build:** 維護者指定私有根目錄、分類與預算，產生可重讀的盤點及封存 dry-run。

**Blocked by:** 無

**Status:** resolved

- [x] 計入 DB（含 sidecars）、raw、研究 bundle、備份、模型與無法辨識檔案，各類及總量可逐檔回算。明確處理權限錯誤、hard link 與 symbolic link；拒絕沿連結掃描根外。
- [x] 相對於上次盤點呈現新增／移除／大小差，按預算指出超限路徑與原因。封存計畫列明研究引用與依賴，未知引用保留；在已有私有資料上驗證全程唯讀。
- [x] 以 fixture 及真實私有目錄實測，輸出設在掃描範圍外。封存後可還原及 audit 的跨票驗收由 02 記錄。

## 驗收紀錄（2026-11-19）

[CLI 操作](../../../docs/OPERATIONS.md#私有容量增長與封存規劃) · [整合測試](../../../local/tests/test_storage_inventory.py)。macOS arm64、Python 3.11.11 上使用 M1 既有的兩市場驗收資料。131 個檔案共 18,899,888 bytes，10 MiB 示範配額超出 8,414,128 bytes。兩次盤點均為 exit 0，包含 4 個研究版本，來源檔案內容、大小、時間（mtime）、權限及目錄結構指紋一致，規模變動 0 bytes。預估封存保留所有未找到之證據與路徑。私有報告存於 `local/private/m5-storage/`。整組還原、研究引用重讀及 audit 由 02 驗收。

## 雙軸重驗

單一有效 run 作根可保留版本與依賴，9 檔共 1,571,274 bytes，兩次掃描前後指紋及增長符合預期。[修復、操作與私有證據](../../../docs/VERIFICATION-2026-11-19-M5-REVIEW.md)
