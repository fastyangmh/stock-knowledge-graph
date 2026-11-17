# Issue tracker: Local Markdown

沿用既有 `docs/DEVELOPMENT_BACKLOG.md` 作為優先級、相依關係及驗收總覽。
現有 P0／P1／P2 編號保留，不自動搬移或重編；本地路徑或 backlog 編號都可作為工作引用。

需要詳細規格或拆票時才建立：

- `.scratch/<feature-slug>/spec.md`：規格，標註對應 backlog 編號。
- `.scratch/<feature-slug>/issues/<NN>-<slug>.md`：每張 ticket 一個檔案，自 `01` 編號。
- ticket 頂部記錄 `Status:`、`Blocked by:` 和可驗證的完成條件；依賴使用 ticket 路徑或編號。
- 討論附於 `## Comments`；完成後記錄驗證證據、設 `Status: resolved`，同步 backlog 進度。
- 細部 ticket 的執行狀態以該檔案為準，backlog 維持功能層級總覽並連結細部檔案。

技能中的「publish to issue tracker」代表寫入上述本地檔案。
「fetch ticket」代表讀取指定檔案或 backlog 對應段落。
GitHub remote 是程式碼儲存庫；本設定不要求將本地待辦同步為遠端 Issues。

`wayfinder` 的 map 放在 `.scratch/<effort>/map.md`；子票使用上述 issues 目錄，
以 `Type:` 記錄 research／prototype／grilling／task。所有 blockers resolved 後才可領取；
先存 `Status: claimed`，完成後附上 `## Answer`、設 `resolved` 並更新 map 的決策連結。

`.scratch/` 只放可提交的開發規格；私人金融資料與產物仍放 gitignored 的
`local/private/`，不可附入 tickets。
