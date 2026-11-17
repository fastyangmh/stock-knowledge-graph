# 未裁剪事件事實與 cohort 驗證｜2026-11-17

範圍：[ticket12](../.scratch/private-research-ready/issues/12-event-fact-contract.md)、[事件統計](EVENT_STUDY.md)、[研究事實契約](RESEARCH_FACTS.md)。本輪交付 P2-01 工程預備線，不代表完整市場事件研究或 P4A-01 全部完成。

## 版本與環境

- 功能提交：`4e59adc`；合併當時 integration 後的實測 Commit：`5b9913001f1ac5180ea3b02fb44df981af7f7b3e`，測試開始時工作區乾淨。後續本紀錄／ticket 狀態提交不改產品原始碼。
- macOS / Darwin arm64、Python 3.11.11、uv 0.6.13、Node.js 22.16.0；獨立 Playwright／Chromium 1255 安裝用於瀏覽器驗證。
- 本輪依使用者要求在目前可用的 macOS 驗證。Linux／NAS 未執行；不冒稱已完成該環境重現，也不以其未具備阻擋本輪工程驗收。
- 所有金融輸入為合成 CSV／JSON，經真實本機 SQLite、research、audit、event 流程；外部來源與真實模型未下載。

## 已執行結果

| 檢查 | 結果 |
| --- | --- |
| 修改前事件基準（排除 HTTP 一項） | 65 passed、27 subtests；HTTP 納入後續完整檢查 |
| TDD 紅燈 | 新分析版本／cap 獨立性、mixed cohort 參數、UI 版本／範圍、完整筆數預算均先出現相關失敗，再完成最小實作 |
| `local.check --frontend` | exit 0；compileall、459 pytest、193 subtests、SQLite→JSON smoke、release validation、JS syntax、55 Node tests 全通過 |
| `event_facts_browser_smoke.py` | exit 0；9 組通過，無 page errors |
| `git diff --check`／公開示範 | exit 0；本票未修改公開 `data/`、`uv.lock`、排程或發布設定 |

pytest／unittest 未重複相加；本輪沒有另跑 unittest runner。完整檢查包含真實 loopback HTTP 的 allowlist、Host、HEAD／POST 行為；相關權限依正常升權流程執行。

## 行為證據

- 固定合成事實／提醒／時間，以展示上限 0 與 100 產生不同圖譜；新版事件總數、各狀態分母與統計相同，cap 0 仍得到後第1筆價格變化 10%、後第2筆 -10%。新版引用 `fact_id`，不依賴展示 node。
- 移除中間一個合成研究版本，後來 bundle 的完整歷史仍提供該已保存行情；以後來 bundle 實際保存時間作 `captured_at`，不假造較早保存或登錄時間。
- 純舊維持 `event-study-1.0`／`display_graph_only`；新版使用 `event-study-2.0`／`unpruned_facts`。混合目錄未選 cohort 報錯，明選後列出納入／未納入及原因。後來重現的舊事件列 `first_trigger_saved_in_other_cohort`，不重建舊基準。
- 後續更正不取代首次後續值；缺基準不由晚到 facts 補值。未知登錄時間保留 unknown。來源、尺度、正規化版本變動不可比較；保留 pending、insufficient_data、not_comparable 與 observed 的獨立分母。
- 新事實缺漏／未知 schema／篡改不退回 graph，即使選舊 cohort 亦必須先通過整包 audit。測試禁止事件讀者開 SQLite 或外部 HTTP，真實 catalog 仍可完成分析。
- 完整數值（含非事件指標／籌碼）、事件識別、事件與事實訪問工作量、報告 bytes 上限均有行為回歸；不以截尾達成通過。
- 瀏覽器走實際 `local.event_study.make_server`、真實 HTTP response 與原生 fetch，沒有替換 `window.fetch`。完整新版、混合新版、混合舊版及純舊版各測桌機／390px 手機；版本、範圍、數量與排除理由可見。完整事實、report、DB、raw URL 均404。

## 重跑與私有證據

在專案根目錄，以已準備的鎖定 Python／Node 環境執行：

```bash
TMPDIR=/private/tmp UV_CACHE_DIR=/private/tmp/skg-uv-cache \
UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv \
PATH=/private/tmp/skg-tools/node-v22.16.0-darwin-arm64/bin:$PATH \
uv run --locked python -m local.check --frontend \
  --report local/private/m1/12/check-report.json

TMPDIR=/private/tmp PLAYWRIGHT_BROWSERS_PATH=/private/tmp/skg-tools/playwright \
/private/tmp/skg-browser-venv/bin/python scripts/event_facts_browser_smoke.py \
  --chromium '/private/tmp/skg-tools/playwright/chromium-1255/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing' \
  --report local/private/m1/12/browser.json
```

機器路徑是本次證據環境，可換成自己已安裝的 Python／Chromium。主要私有證據為 `local/private/m1/12/check-report.json`、`browser.json`、各 cohort 報告／手機截圖、TDD red/green 日誌及 `evidence.json`。`evidence.json` 另外保存以 repo 相對路徑列出的來源 SHA256，補足現行 check 在 `/private/tmp` worktree 的雜湊路徑過濾限制；本票未修改 check 工具。

上述產物保留於私有目錄，不提交合成 DB、報告或截圖。瀏覽器此項僅驗證事件範圍揭露；通用歷史／事件錯誤恢復驗證由 ticket04 另記。真實金融資料與新契約結合、權威交易日曆、還原價格、完整雙時間歷史與研究品質仍屬後續工作。
