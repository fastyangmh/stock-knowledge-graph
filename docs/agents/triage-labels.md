# Triage labels

本地 ticket 的 `Status:` 使用以下上游角色名稱；不需要建立遠端標籤。

| 上游角色 | 本地值 | 用途 |
| --- | --- | --- |
| needs-triage | needs-triage | 尚待評估 |
| needs-info | needs-info | 尚缺必要資訊 |
| ready-for-agent | ready-for-agent | 規格完整，可由代理實作 |
| ready-for-human | ready-for-human | 需要人工執行 |
| wontfix | wontfix | 決定不處理 |

執行中的工作可用 `claimed`，完成用 `resolved`；這兩者是執行狀態，並非新的 triage 角色。
