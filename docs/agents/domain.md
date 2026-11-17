# Domain docs

本 repo 採單一領域文件布局，沿用現有 `docs/`，不新增根目錄的重複術語表。

探索及修改前讀取：

- `docs/GLOSSARY.md`：領域名詞唯一維護位置。技能寫到 `GLOSSARY.md` 時，讀寫此檔。
- `docs/HANDOFF.md`：已確認決策與限制。
- `docs/ARCHITECTURE.md`、`docs/DATA_MODEL.md` 及修改範圍相關的功能文件。
- `docs/adr/` 中相關 ADR（若存在）。目前未有 ADR 時繼續工作，真正有決策才建立。

技能中的預設根目錄 `GLOSSARY.md` 路徑統一映射至 `docs/GLOSSARY.md`。
規格、ticket、測試及對話使用該術語表的定義；實作細節仍放功能文件。
若新方案與既有決策衝突，指出具體衝突及影響，不默默改寫歷史。

需要記錄難以回復、涉及實際取捨的決策時，新增 `docs/adr/NNNN-<slug>.md`，
依 `domain-modeling/ADR-FORMAT.md` 的格式記錄；不為既有每項決策補造 ADR。
