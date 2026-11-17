# Repository guidance

先讀 `docs/HANDOFF.md`、`docs/DEVELOPMENT_BACKLOG.md` 及本次修改相關文件。
沿用交接文件的已確認決策；用繁體中文溝通，保留程式識別字。

## Agent skills

本專案採用 `.agents/skills/` 的 Matt Pocock skills。來源、使用方式與更新規則見
`docs/agents/README.md`。使用某個 skill 時先讀其 `SKILL.md` 和所需參考檔。
上游標記為 user-invoked 的流程只在使用者指定時啟動；一般任務依適用範圍使用
TDD、除錯、設計等 model-invoked skills，不把每次小修都變成完整訪談。
若介面沒有 Skill 工具，直接讀取對應檔案執行，不臆造工具。

### Issue tracker

沿用本地 Markdown 待辦；總覽為 `docs/DEVELOPMENT_BACKLOG.md`，細部規格與 tickets
依 `docs/agents/issue-tracker.md` 存放。

### Triage labels

採用上游五種角色作為本地狀態值，見 `docs/agents/triage-labels.md`。

### Domain docs

單一領域文件布局；術語表為現有 `docs/GLOSSARY.md`，ADR 按需存於 `docs/adr/`。
讀取與寫入對應規則見 `docs/agents/domain.md`。

## Development and verification

- 實作前檢查工作區並保留既有修改，遵循 `docs/DEVELOPER_GUIDE.md`。
- 功能與錯誤修復採小步驟、可觀察行為的測試；TDD 先看到相關失敗，再做最小實作。
- Python 基準與完整驗收：`uv run --locked python -m local.check`。
- 涉及前端：`uv run --locked python -m local.check --frontend`；瀏覽器驗收另依前端文件。
- 初次環境安裝：`uv sync --locked --extra dev`。依賴未變更時保留 `uv.lock`。
- 文件／技能設定變更檢查路徑、來源與 `git diff --check`；不將未執行的產品測試報為通過。
- 完成時記錄實際驗證、未驗證範圍及相關文件更新。

## Project boundaries

沿用 `docs/HANDOFF.md` 與 `docs/SECURITY_AND_LICENSING.md` 的資料及發布規則。
公開 `data/` 維持示範資料；私有快照、SQLite、憑證及測試產物不可提交。
技能中的發布步驟依本地 tracker 設定解讀；啟用技能不代表授權金融資料公開、
排程、付費、交易或變更研究定義。名單確認仍暫緩，不阻塞獨立開發。
