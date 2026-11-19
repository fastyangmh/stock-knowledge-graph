# 01 · 盤點容量、增長與封存候選

**Parent:** [P2-06](../../../docs/DEVELOPMENT_BACKLOG.md#p2-06儲存預算與封存) · [規格](../spec.md)

**What to build:** 維護者指定私有根目錄、分類與預算，產生可重讀的盤點及封存 dry-run。

**Blocked by:** 無

**Status:** ready-for-agent

- [ ] 計入 DB（含 sidecars）、raw、研究 bundle、備份、模型與無法辨識檔案，各類及總量可逐檔回算。明確處理權限錯誤、hard link 與 symbolic link；拒絕沿連結掃描根外。
- [ ] 相對於上次盤點呈現新增／移除／大小差，按預算指出超限路徑與原因。封存計畫列明研究引用與依賴，未知引用保留；在已有私有資料上驗證全程唯讀。
- [ ] 以 fixture 及真實私有目錄實測，輸出設在掃描範圍外。封存後可還原及 audit 的跨票驗收由 02 記錄。
