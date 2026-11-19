# M2 價格比較與修訂歷史雙軸審查

審查比較 `c916725..693f34e`，修復從 `d2af722` 開始。下列驗收使用產品候選 `bcafcb056bc556f2f1af16d7c17528372cc81f23`。範圍為[價格歷史兩票](../.scratch/m2-price-history/spec.md)。

| 審查軸 | 發現及修復 | 驗收行為 |
| --- | --- | --- |
| Standards | 文件的來源公告與可得時間可不同。一般文件與替代文件均以兩者較晚者判斷可得性。 | 未來才發布的替代文件尚未生效時，研究圖仍呈現原文。 |
| Standards | 報告與事實曾重複放入歷次通知全文。各份通知改存為以 SHA256 命名的獨立 JSON，保留原有單檔、整包及 ledger 預算；暫存包完成 audit 後才提交 ledger。 | 兩份各 17 MiB 的合成更正均通過 CLI 與 audit；另以過大的累計快照 metadata 觸發單檔超限，確認 ledger、成功指標及後續重試。 |
| Standards | 11633 補登記來源、授權與離線收據用途；維持下載停用。02 票補齊本地 tracker 格式。 | registry 測試核對資料與 URL、預設已啟用來源及再散布狀態。 |
| Standards | 登錄與封存稽核共用撤回、重新發布、公告先後及生效順序規則。 | 重送、錯誤父版本、亂序與同時有矛盾的輸入仍受驗證。 |
| Spec | 文件通知須先控制同一文件身分，再投影至本次選股；缺少 `stock_ids` 的舊文件採既有空範圍語意。 | 撤回後普通快照將同一文件改掛另一股票，只查後者仍看不到文件；指定股票撤回無連結舊文件會得到範圍錯誤。 |
| Spec | 稽核核對可見修訂節點的來源、標題、原文摘要、版本雜湊與時間。展示名額裁剪可使文件缺席。 | 把舊展示圖放回更正／撤回後的包、重新計算圖譜及清單雜湊後，獨立 audit 仍拒絕舊內容。 |
| Spec | 一般比較納入幣別、正規化、交易範圍等行情定義。提醒公式沿用既有版本。 | 實際 loopback `/api/compare` 核對兩版已觸發的價量提醒，兩版幣別不同時輸出 `definition_changed`、`comparable=false`。 |
| Spec | 比對普通目標來源前，先依可得時間篩選同鍵候選。 | 有效的來源 A 可登錄通知，另一份未來可得的來源 B 紀錄不會阻擋它。已知來源矛盾仍拒絕。 |

## 實際執行

macOS arm64、Python 3.11.11、Node v22.16.0。候選工作樹乾淨。完整 `uv run --locked python -m local.check --frontend` exit 0，550 個 pytest、286 個 subtests、55 個 Node 測試，以及隔離 SQLite pipeline 與匯出驗證均通過。第一次因沙箱限制無法開啟 loopback；第二次在開放 loopback 後完成 Python 與 pipeline，但未找到 Node。最後一次使用已保存的 Node 執行檔，從頭執行全套。

| 樣本 | 核對內容與結果 | 私有證據（相對主要工作區 `local/private/`） |
| --- | --- | --- |
| 上市、上櫃舊庫 | 遷移副本各保留 1 筆完整快照，原截止各重播相同 8 筆事實。每市場既有兩版及其各一個事件重讀一致。合成更正／撤回／再發布 8 版均可稽核。 | `m2-revisions/run-bcafcb0/results.json` |
| 兩家上櫃發行人的正式更正 | 原始、更正、早截止、重送各存一版，每家 4 版均通過 audit。早截止見原標題，晚截止見更正。 | `m2-revisions/source-notices-bcafcb0/result.json` |
| 兩個市場價格區間 | 各兩檔股票，2026-11-17 到 11-18，逐端比對保存的收盤與原件雜湊。11633 的 11-19 快照只有日期，四檔的三類公司行為涵蓋仍未知。 | `m2-history-fixes-intervals-bcafcb0/interval-check.json` |
| 舊格式與容量 | 先前內嵌通知的 8 份合成與 8 份真實公告研究版本皆通過唯讀 audit。兩份大型合成更正的個別 JSON 各 17,826,759 bytes；新包的報告 4,556 bytes、事實 2,790 bytes。 | `m2-revisions/legacy-inline-bcafcb0.json`、`m2-revisions/large-doc-smoke-bcafcb0.json` |
| 完整離線檢查 | 每項指令、退出碼、環境版本與來源雜湊保存在報告。 | `m2-revisions/check-bcafcb0-final.json` |

重跑時以候選工作樹為目前目錄並將其設為 `PYTHONPATH`。在主要工作區 `local/private/m2-revisions/` 執行 `verify.py <新輸出目錄>` 與 `real-notices.py <新子目錄名>`。價格驗收將原 `check-intervals.py` 複製到 `local/private/` 下新的同層資料夾執行，保留各輪結果。

本輪使用已保存的官方原件及研究版本。來源正式撤回、財務及籌碼真實更正、行情 ledger 的通知適配、Linux／NAS 與真實瀏覽器均未在本次驗收。價格區間與原件定位另見[價格操作與限制](PRICE_ACTION_REVIEW.md)及[公告逐列核對](../.scratch/m2-price-history/official-document-corrections-2026-11-19.md)。
