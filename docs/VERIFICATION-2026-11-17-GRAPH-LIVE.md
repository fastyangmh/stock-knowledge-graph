# 圖譜真實 HTTP／CDN 驗證｜2026-11-17

[前端與預覽](FRONTEND_AND_PREVIEW.md) · [03 ticket](../.scratch/private-research-ready/issues/03-graph-browser.md)

實作及驗收 Commit：`03fa0761d68b61a12ca20b1b55f9bf357b99959e`，已整合
`d8c96bd` 的 private-research-ready 基準。驗收時工作區乾淨；本紀錄為其後文件更新。
本票完成圖譜部分，不能據此關閉包含歷史／事件頁的整個 P0-02。
之後已合併 `263089e` 的文件修訂：使用者接受當前 macOS 環境驗收，Linux 留待後續，
不阻擋本輪；該修訂未改產品程式。

## 實際環境與命令

- macOS／arm64；產品回歸 Python 3.11.11、uv 0.6.13、Node.js 22.16.0。
- 瀏覽器工具使用另備的 Playwright 1.65.2 與 Chromium 159.0.8154.6；未改 `uv.lock`。
- 完整回歸：`uv run --locked python -m local.check --frontend --report local/private/m1/03/check-integrated.json`，exit 0。
- 真實瀏覽器：`python scripts/browser_smoke.py --live-cdn --chromium <Chromium executable> --report local/private/m1/03/graph-live-integrated.json`，exit 0。
- macOS 暫存環境為 `TMPDIR=/private/tmp`；uv cache、Python environment 與 Chromium 位於既有私有工具目錄。原始報告保留實際可執行檔路徑。

完整回歸：**441 passed、180 subtests passed；Node 53 passed**。subtests 不與 pytest
主測試相加。本票未另跑 unittest。`git diff --check` 通過。

## 真實傳輸與瀏覽器結果

私有資料是合成股票／文件／提醒經真實 SQLite 與 exporter 生成；不是正式金融資料。
瀏覽器由現有 private preview allowlist HTTP 開啟首頁，使用原生 `fetch`、原生
WebCrypto 與既有 CSP。未使用 request routing、CDN 替換、憑證例外或安全政策變更。

| 驗證 | 結果 |
| --- | --- |
| 原 CDN | `https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js`，HTTP 200、`text/javascript; charset=utf-8`、373734 bytes |
| CDN SHA256 | `1bb5340e549511e111b31e5684872c949ad33d40ea5dba0ad8e7d90c62c7b3b9` |
| 執行版本 | `cytoscape.version === '3.30.4'`；實際 canvas 顯示 |
| WebCrypto | localhost secure context 正常驗證；錯 bytes 拒絕並清空舊 canvas |
| 圖譜 12 組 | 初次只載一圖、六種股票池篩選／搜尋／空結果恢復、來源文字及連結安全、提醒／關聯／fit、晚到 HTTP 回應、錯 hash、404、損壞 bytes、匹配 hash 但錯股票、匹配 hash 但非法 JSON、390px 操作、私有路徑拒絕 |
| 恢復 | 每種錯誤確認 canvas／提醒清空；移除故障後按重新載入可恢復 |
| Pages 1 組 | 只讀 `https://fastyangmh.github.io/stock-knowledge-graph/`，HTTPS 200、同一 CDN 版本／hash、正常 canvas、空結果恢復、390px 無橫向溢位 |
| 私有路徑 | DB、raw、`.git/config`、文件路徑皆 404 |

故障只注入測試 server 已捕捉的 bytes／404／延遲；不修改正式 preview 實作，正常圖檔
仍由相同 allowlist 供應。來源注入字串出現在來源 DOM 的文字中，未生成 `img` 或
`script` 元素；`javascript:` 和含帳密 HTTPS 連結未生成，安全連結保留
`noopener noreferrer` 與 `no-referrer`。

## Red → green 與證據

1. 原 harness 必須供應本地 Cytoscape，`--live-cdn` 命令 exit 2，不能驗證原 CDN。
2. 新增 live 模式後，首次真實執行在錯誤等待條件遇到 CSP `unsafe-eval` 拒絕；Pages
   部分已通過。修正 harness 的字串式 predicate 為函式 predicate，未放寬 CSP。
3. 重跑並補上匹配 hash 的錯股／非法 JSON 案例，在上述固定 Commit 全部通過；產品
   前端無需修正。既有 in-memory 與本地資產 loopback 模式仍保留，其證據範圍不變。

私有證據位於 `local/private/m1/03/`：

- `live-cli-red.json`、`graph-live-red-csp.json`：初始 red 與 CSP 失敗報告。
- `graph-live-integrated.json`、同名 log、`.private.png`／`.pages.png`：最終瀏覽器、各 HTTP 回應 bytes／hash／TLS、檢查與截圖。
- `check-integrated.json`、同名 log：完整回歸的命令、環境與 exit code。
- `source-hashes.json`：92 個 Git tracked 程式／設定檔的 SHA256。當時 `local.check`
  對 `/private/tmp` worktree 有來源路徑篩選缺陷；此獨立清單補足 provenance，瀏覽器
  報告亦自行保存相關來源 hashes，未將空來源清單冒稱完整。

原始回應／測試產物不提交。公開 `data/`、生產 CDN 與 main/root 部署方式均未變，
沒有發布、排程或傳送私有金融資料。此紀錄不是 Linux 目標環境、真實模型、金融來源、
歷史／事件頁、實體手機或其他瀏覽器驗收；手機部分為 Chromium 390px viewport。
