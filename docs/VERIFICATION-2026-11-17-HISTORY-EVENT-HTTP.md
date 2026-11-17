# 歷史與事件頁真實 HTTP 驗證｜2026-11-17

本票新增 `history_browser_smoke.py --live-http` 與
`event_browser_smoke.py --live-http`，共用 `history_event_live_smoke.py`。
產品前端、server、安全政策與 CDN 未修改；保留記憶體模式。

實作基準：`8b91af671a245f170d410bb1146e9916d85d1927` 加本票修改；完整
實作 Commit 由 Git history 定位。私有證據：`local/private/m1/04/`，不提交。
報告各自記錄執行時 Commit、dirty 與相關來源 SHA256；不能只用基準 Commit
推定未提交程式內容。

## 實際環境與命令

使用者接受本輪 macOS／arm64 環境；未宣稱 Linux 重驗。
Python 3.11.11、uv 0.6.13、Node v22.16.0、Chromium 159.0.8154.6。
Playwright 版本、執行檔、完整命令與時間在私有 JSON。

```bash
# Chromium 與 Playwright 需預先安裝；BROWSER 為當地實際執行檔。
TMPDIR=/private/tmp python scripts/history_browser_smoke.py --live-http \
  --chromium "$BROWSER" --report local/private/m1/04/live-history.json
TMPDIR=/private/tmp python scripts/event_browser_smoke.py --live-http \
  --chromium "$BROWSER" --report local/private/m1/04/live-event.json
uv run --locked python -m local.check --frontend \
  --report local/private/m1/04/check-report.json
```

## Red → green 與結果

新增模式前，以 `history_browser_smoke.py --live-http` 實際得到 exit 2
（unrecognized arguments），存 `red-history.log`。新增模式後執行真實 HTTP
案例；先修正 harness 對既有安全邊界的預期，不更改產品來迎合測試。

| 驗證 | 實測結果 |
| --- | --- |
| 歷史真實 HTTP | 9組情境通過，exit 0，page errors 0 |
| 事件真實 HTTP | 7組情境通過，exit 0，page errors 0 |
| 保留記憶體 smoke | 歷史9組、事件11組，exit 0 |
| `local.check --frontend` | 447 passed、187 subtests passed；Node 53 passed，exit 0 |
| `git diff --check` | 通過 |

歷史成功路徑使用3份已稽核 SQLite bundle，加1份錯誤 identity 版本；比較價量／
營收兩類、activated／still_unavailable／definition_changed、來源證據、桌機及
390px手機。兩種尺寸都實際點選版本圖譜，再返回歷史頁。Cytoscape由原
`https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js` 傳輸，實際確認
`cytoscape.version === '3.30.4'`、secure context與WebCrypto、native fetch，
記錄回應 bytes／SHA256。沒有替換 CDN 或瀏覽器網路函式。

事件成功路徑使用合成 CSV → 真實 SQLite → research → audit → event report，
6個事件分為價量2個與營收4個。驗證四種狀態分母、已觀察10%範例、缺樣本不顯示
零平均、報價觀察與曆月標示、事件切換及凍結證據。兩頁均實際下載HTML／CSS／JS／JSON。

故障案例使用同一 production HTTP handler 的受控已捕捉 bytes：惡意文字以文字
呈現、404／非法 schema／壞 JSON／不一致分母拒絕、重新載入恢復。歷史比較的
真實延遲 HTTP 回應不覆蓋較新的選擇；倒序時間比較由 production API 回400，
修正選擇後恢復。空研究目錄、格式損壞 pointer拒絕啟動；缺 pointer則保留個別
有效版本、預設manifest回404。空摘要UI用合成HTTP回應測試；無事件報告由真實
無提醒bundle生成。

兩個 production server 均驗證DB、raw、report、完整facts、目錄／repository
路徑回404，錯誤Host回403，POST／PUT／DELETE／OPTIONS回501；HEAD正常且無body。
壞版本不供應圖檔，已稽核版本提供圖檔與摘要。

## 證據限制

所有金融資料為合成，未驗證正式金融來源、授權或市場統計有效性。這兩頁的
本機HTTP與原CDN證據不等於正式Pages部署；只讀Pages驗收屬票03。
未修改公開 `data/`、lockfile、排程、發布或研究定義。

`local.check` 在 `/private/tmp` worktree 的既有 `source_sha256` 掃描缺口另由
整合審查處理；本票另存 `supplemental-source-sha256.json` 補充來源識別，未將
空欄位冒稱完整。最新整合後若重驗，以下補充紀錄及私有報告以實際結果為準。
