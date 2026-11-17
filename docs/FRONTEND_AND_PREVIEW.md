# 雙來源介面、索引契約與私有預覽

[文件中心](README.md) · [研究股票池](RESEARCH_UNIVERSE.md) · [使用者手冊](USER_MANUAL.md)

## 1. 這一版完成的範圍

TW50 指數成分股與 009816 ETF 普通股持股仍是兩個獨立來源；後端取聯集、去重，前端依來源篩選主股票。研究股票池不是新指數，重疊不代表投資訊號。真實名單與公開使用權仍待確認。

網站支援：全部股票、臺灣50（含重疊）、009816（含重疊）、兩者皆有、僅臺灣50、僅009816、未標示；並可依股票代號／名稱搜尋。篩選**只作用於主股票清單**，所選圖譜仍可保留其他相關股票作為上下文。

缺少來源欄位的舊版 JSON 一律顯示「未標示」，不根據代碼、名稱或股票數量猜測歸屬。索引會顯示匯出主圖計數、重疊及觀察日期；多日期資料不會被稱為當日完整名單。ETF 日期仍不向前或向後補值。

## 2. 向後相容的 manifest 擴充

保留 `schema_version: 1.0`；新 exporter 在每個 `stocks[]` 項目加入以下可選欄位，舊資料仍能讀取：

| 欄位 | 說明 |
| --- | --- |
| `stock_id`、`ticker` | 穩定股票識別與搜尋欄位 |
| `universe_ids`、`universe_group`、`universe_as_of` | 從主股票節點驗證後輸出的歸屬摘要；沒有就不輸出 |
| `node_count`、`edge_count` | 對應圖譜實際大小 |
| `sha256` | 對應 graph.json **原始 bytes** 的 SHA256，包含換行與格式 |

頂層 `research_universe.counts` 為**本次匯出主圖**的總數、來源數、重疊與未標示數；不是完整官方指數認證。`as_of_dates` 列出本次匯出包含的歸屬日期。完整 `universe_memberships` 仍保留在股票節點以供追溯。

`local.view_metadata` 核對來源 ID、歸屬、日期、生效期間與同日 ETF 快照；`local.validate_release` 交叉比對索引／主節點／數量／雜湊。矛盾資料停止匯出或載入，不自動修正成「兩者都有」。SHA256 只能偵測圖檔與索引不一致，不是數位簽章，也不能防止兩者一起被改寫。

## 3. 前端行為與安全界線

- 初始化只讀索引及一個所選圖檔，不為股票池篩選一次下載全部圖譜。
- 新圖有 SHA256 時，以 WebCrypto 驗證；需要 HTTPS 或瀏覽器信任的 localhost 安全環境。
- 使用請求序號與 AbortController 防止舊回應蓋掉使用者最後選擇的股票。
- 沒有匹配結果、HTTP 錯誤、非法圖譜或校驗失敗會清除舊圖，顯示可恢復的錯誤／空狀態。
- 來源、條款、名單日期、模型與證據使用文字 DOM 顯示，只建立無憑證的 HTTPS 連結；不把輸入文字插成 HTML。
- 「資料來源與使用條款」整合 manifest 及已載入圖譜的來源署名；**顯示欄位不等於已取得授權或完成法律審查**。
- 語意邊無箭頭；`contains` 資訊關係可顯示箭頭。縮放或手機寬度改變後自動適配圖譜。
- Cytoscape 繼續使用原本 CDN 固定版本 `3.30.4`；本次不更動供應來源或 npm/Python 依賴。

## 4. 不覆寫公開 data/ 的私有預覽

先產生私有輸出並驗證，再啟動預覽：

```bash
uv run --locked python -m local.pipeline validate --output local/private/combined-preview
uv run --locked python -m local.preview --data-dir local/private/combined-preview --port 8765
```

在**同一台主機**的瀏覽器開啟 `http://127.0.0.1:8765/`；遠端 NAS 可使用你已有且獲授權的 SSH port forwarding，不要開放到網際網路。Ctrl-C 關閉。此工具只讀取一份已驗證、最多 64 MiB 的記憶體快照；更新匯出後須重啟以載入新版本。

僅允許首頁、CSS、必要 JS、manifest 與列出的 graph.json；沒有目錄列表，不服務 SQLite、原始快照、文件目錄或 Git 檔案。固定 bind `127.0.0.1`，並檢查 Host。這不是登入／權限系統：其他本機使用者仍可能讀取該埠。

**不要以 Repository 根目錄的 `python -m http.server` 預覽敏感資料**，那樣會讓 `local/private/` 也落在可存取根目錄。預覽仍會載入現有第三方 Cytoscape CDN；這不是完全離線或零信任隔離工具。授權要求完全離線時須另行取得、驗證並固定前端依賴，不能直接聲稱目前已符合。

## 5. 可重跑測試

```bash
# Python、本機 HTTP、隔離 SQLite/JSON 與 Node 內建測試；需要 Node.js
uv run --locked python -m local.check --frontend
# 不需要 Node 的 Python-only 驗收
uv run --locked python -m local.check
```

另外提供 `scripts/browser_smoke.py`：使用 Playwright、Chromium 與**由操作者提供的本地 Cytoscape JS**，不自動下載。這些是選用開發工具，未加入現有 lockfile。範例：

```bash
uv run --locked python scripts/browser_smoke.py \
  --chromium /path/to/chromium \
  --cytoscape-js /path/to/reviewed/cytoscape.min.js
```

需要先在執行環境具備 Playwright。受限環境可選 `--in-memory` 跑 about:blank DOM 與合成 fetch；它不測試真實 HTTP 導航，並因安全 context 限制略去 fixture 的可選 checksum。SHA256 分支由 Node 真實 WebCrypto 測試，HTTP 行為由 Python loopback 測試。不可把不同測試的通過合稱為已完成生產部署驗收。

完整實測範圍見 [本次驗證紀錄](VERIFICATION-2026-11-16-FRONTEND.md)。

### 真實 HTTP／CDN 驗收

`--live-cdn` 以現有 private preview allowlist 提供合成 SQLite 匯出的圖檔，瀏覽器
直接載入原本 `https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js`，並另外
只讀開啟現有 Pages 示範。成功路徑不替換 `window.fetch`、不攔截 CDN，也不變更
CSP、憑證檢查或瀏覽器安全政策；不需要 `--cytoscape-js`。

```bash
# 使用已備妥 Playwright 的 Python；macOS 暫存路徑使用 /private/tmp
TMPDIR=/private/tmp python scripts/browser_smoke.py \
  --live-cdn --chromium /path/to/chromium \
  --report local/private/graph-live.json
```

報告分列 private preview 與 Pages 結果，包含 Commit／dirty、程式檔 hash、環境、
瀏覽器版本、實際回應 URL／status／Content-Type／bytes／SHA256／TLS 與檢查項目。
原生 WebCrypto 正常載圖後，測試 server 才注入延遲、404、錯 hash、錯股票及損壞
JSON；每種失敗確認舊 canvas 清除與重新載入恢復。另測來源惡意文字、安全連結、
手機與 DB／raw／repository 路徑拒絕。故障資料不寫回公開 `data/`。

兩部分皆通過才 exit 0；網路／CDN／瀏覽器受阻或斷言失敗仍保存部分報告並 exit 1。
本模式不能和 `--in-memory`、`--cytoscape-js` 或 `--esm-symbol` 混用。原本提供本地
Cytoscape 的 loopback 模式仍會攔截 CDN，不算本模式的真實 CDN 證據。
結果見 [2026-11-17 圖譜驗證](VERIFICATION-2026-11-17-GRAPH-LIVE.md)。
