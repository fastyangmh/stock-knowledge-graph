# P2-04 正式重大訊息更正重播

程式候選 `9e429cc` 在 macOS 從已校驗的 TPEx 每日重大訊息原件，分別存入兩組原公告及其同日明示的主旨更正。依 CSV parser 邏輯記錄編號（表頭為 1），5310 使用 31 → 32，6881 使用 37 → 46。以公司、發言日期與時間、原／更正的文字對應核對關係。第二組的原主旨與新主旨對同一事件採不同描述，不能用標題完全相等來確認關聯。[官方資料集](https://data.gov.tw/dataset/18418)

兩家公司皆於 11 月 18 日發布；本專案初次取得原件為 11 月 19 日。操作員在兩個新的私有 ledger 將已核對的 CSV 列對應到同一文件的原版本及更正版本，綁定原始檔 SHA256、列號、來源 URL 與上一版正規化快照。來源發言、取得及首次本地登錄時間分開保存。兩次登錄之間的 cutoff 是本機重播範例，不能用來宣稱 11 月 18 日研究者已保存原始版本。

- 兩股分別經 research 與 bundle audit 實際建立四版，檢查原始、更正、依原本地 cutoff 回讀原標題及重複送入更正。八次均通過；兩份原 bundle 的報告 SHA256 在最後重驗相同。
- 原始 bytes 及擷取 metadata 在 `local/private/source-review-2026-11-19/official-resources/`。重播腳本為 `local/private/m2-revisions/real-notices.py`，工作目錄需為相應候選的乾淨 worktree。驗證紀錄 `local/private/m2-revisions/source-notices-9e429cc/result.json` 保存程式候選、兩組原件定位、發布與登錄時間、研究版本及各版 SHA256；exit 0。早一次試跑 `source-notices-01/` 的程式匯入自候選，但記錄的 Git 目錄不同，正式驗收採後一次。
- 本次驗證正式文件更正與人工確認的關聯，尚待分開驗正式撤回、更正財務或籌碼欄位的公告及獨立行情庫的適用性。重大訊息自動適配仍由 P1-05 負責。[P2-04 票](issues/02-revision-ledger.md) · [M3 重大訊息](../m3-evidence-sources/issues/06-announcements.md)
