# 02 · 可攜的私有研究封存與還原

**Parent:** [P0-03](../../../docs/DEVELOPMENT_BACKLOG.md#p0-03復原與備份) · [規格](../spec.md)

**What to build:** 從一致的 SQLite、來源證據、研究版本、設定及引用清單，還原至全新私有位置並立即 audit。

**Blocked by:** 無，02 可用明示的成套輸入開始

**Status:** ready-for-agent

- [ ] 重用 SQLite online backup 取得含已提交 WAL 的一致 DB。其餘證據以包含路徑、類別、大小、hash 的 manifest 封存；複製期間來源或 pointer 改變即拒絕完成。
- [ ] 驗證錯 hash、缺檔、路徑逃逸、中途失敗與已有還原目標；舊版 SQLite 備份入口持續可用。成功還原需重讀原始證據、研究歷史、事件引用並完成 bundle audit。
- [ ] 在 macOS 的獨立目的目錄對合成與已有真實研究各做一次 create/verify/restore；記錄設備、來源一致性範圍及驗證命令。Linux／NAS 與獨立媒體實測另列，取得環境才完成 P0-03。
