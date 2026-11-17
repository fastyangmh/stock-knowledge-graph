# Matt Pocock skills：本專案用法

[文件中心](../README.md) · [開發指南](../DEVELOPER_GUIDE.md)

本專案以可版本控制的檔案安裝 [mattpocock/skills](https://github.com/mattpocock/skills)，
27 個技能位於 `.agents/skills/`，包含工程技能與其協作／寫作技能。
來源固定為 `5863806dd4e15c63174bee4e7515a4256792ecfa`；安裝日期為 2026-11-17。
上游原始檔保持不變，MIT 授權存於 `.agents/skills/LICENSE.mattpocock`；
路徑與雜湊清單為 `.agents/skills/mattpocock-source.json`。

這次直接銜接 repo 已有文件慣例，未執行上游互動式 `setup-matt-pocock-skills` 訪談。
本地設定以 [AGENTS.md](../../AGENTS.md) 及本目錄為準。可編輯本目錄調整工作追蹤和
文件位置；未建立遠端 Issues 或標籤。

## 使用方式

下一回合可指定技能名稱，例如：

```text
用 $ask-matt 判斷 DEVELOPMENT_BACKLOG 的下一項工作適合哪個流程。
用 $grill-with-docs 釐清 P1-02 尚未確定的研究資料契約，沿用已確認決策。
用 $to-spec 將已討論的需求整理成本地規格。
用 $to-tickets 將規格拆成可獨立驗收的工作。
用 $implement 實作指定 ticket，依 repo 指令驗收。
```

典型新功能順序為需求釐清 → 規格 → tickets → 實作／TDD → review。
已有完整需求可直接實作；除錯可用 `diagnosing-bugs`，架構盤點可指定
`improve-codebase-architecture`。是否需要訪談、測試介面確認或拆票，依實際工作
與所選技能規則判斷，不重問交接文件已確認的決策。

上游 `implement` 包含提交目前分支，`implement-spec` 與 `code-review` 包含子代理
工作；明確選用前應知道這些流程行為，仍受當次授權與執行環境限制。

## 本專案設定

- [工作追蹤](issue-tracker.md)：既有 backlog 與本地細部 tickets。
- [狀態用語](triage-labels.md)：五種 triage 角色。
- [領域文件](domain.md)：沿用 `docs/GLOSSARY.md`，ADR 按需建立。
- 驗收依 [開發指南](../DEVELOPER_GUIDE.md)，不套用上游範例的 TypeScript 指令。

## 更新

這是固定版本的檔案安裝，不會自動更新。更新時先檢查上游 diff，選定新的完整
commit SHA，再用 skill-installer 的 `install-skill-from-github.py` 將清單內所有
`upstream_path` 安裝到暫存目錄（`--repo mattpocock/skills --ref <SHA> --dest <temp>`）。
比對後才替換本 repo 的技能，保留授權並更新來源／SHA-256 清單。
installer 會拒絕覆蓋既有技能目錄；不要先刪除現有安裝來碰運氣。
技能名稱與相互引用也需一起檢查。
