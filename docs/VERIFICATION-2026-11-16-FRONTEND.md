# 本地整合驗證｜雙來源介面與私有預覽（2026-11-16）

[文件中心](README.md) · [功能及操作](FRONTEND_AND_PREVIEW.md) · [前次驗證](VERIFICATION-2026-11-15.md)

## 基準與環境

遠端基準 `e9f3bf77c1edd2a4d3edcc30c221c459e5712dd5`。GitHub 連接器讀取來源，在工作環境重建測試副本，修改前以 Git blob SHA-1 比對原始 Python 程式、全部既有測試及相關配置；**不是直接 clone 成功**。修改前完整跑出 97 passed、8 subtests passed（原有 69 加雙來源 28），補上上一輪未整合全套執行的驗證。

本次本地環境：Linux、Python 3.13.5、pytest 9.0.2、Node.js 22.16.0、Playwright 與系統 Chromium。使用既有環境套件，沒有重新執行 uv.lock 的 Python 3.11 安裝或真實模型下載。使用者先前的鎖定環境／模型成功紀錄仍是另一筆驗證。

## 實際結果

| 檢查 | 結果 |
| --- | --- |
| 修改前完整 pytest | 97 passed、8 subtests passed |
| 修改後 compileall | exit 0 |
| 修改後完整 pytest | **116 passed、12 subtests passed，6.15 秒** |
| 獨立 unittest runner | **Ran 116 tests，OK，6.083 秒** |
| 隔離 SQLite→lexical→lifecycle→JSON | 3 股票成功匯出，完整驗證通過 |
| Node 語法檢查與內建測試 runner | **19 tests，19 pass，0 fail** |
| Python 真實 loopback HTTP | allowlist、Host、HEAD、快照不可變、路徑與大小防護通過 |
| 虛構雙來源 SQLite→匯出 | 50 指數＋30 ETF、交集10、聯集70，圖檔／歸屬／checksum 驗證通過 |
| Chromium DOM／canvas 互動 | **9 組情境通過，page_errors=[]** |

## 瀏覽器測試的重要界線

此執行環境的 Chromium 導航政策阻擋 localhost（`ERR_BLOCKED_BY_ADMINISTRATOR`）。沒有更改或繞過政策；改以 about:blank 載入實際 HTML/CSS/JS，使用**純記憶體的虛構 fetch 回應**，阻擋所有真實瀏覽器網路請求。Python loopback HTTP 行為獨立測試。

本機僅有 Cytoscape **3.33.1** 可用，故瀏覽器使用該版本的本地資產；網站原有 CDN pin **3.30.4 沒有改動**。這不能算是已驗證生產 CDN 的逐 bytes 行為。測試本地資產 SHA256：

```text
38944c926eef34939819338782c1f5a9000e0f4c92208d73d6eb1c5b57cb2695
```

about:blank 沒有安全 context 的 WebCrypto，因此 in-memory 瀏覽器 fixture 移除可選 SHA 欄位；checksum 正確／錯誤分支已在 Node 真實 WebCrypto 與 Python 驗證。不能把它說成瀏覽器實際 HTTPS/SHA/CDN 整條路徑已驗收。

9 組情境：canvas 與初次只讀一張圖、六種來源篩選、無結果清除舊圖、代碼搜尋／日期／來源與文字安全、relation／fit、慢回應不覆蓋最後選擇、390px 手機版無水平溢出、壞圖清除及可恢復錯誤、既有公開 demo 仍可讀且不偽造歸屬。測試發現並修復手機 resize 的 grid 溢出及圖譜適配問題；已檢視手機截圖。

## 新增檢查重點

- 索引來自驗證後的主節點歸屬，不因股票名稱／數量推測 TW50。
- 來源期間／ETF同日快照、完整欄位、來源 HTTPS、歸屬一致性與重疊計數。
- SHA256 檢測混版圖檔，node/edge ID 不可碰撞，索引／圖檔股票與數量不一致即拒絕。
- 不合法來源連結／HTML 注入文字不被執行。
- 私有預覽僅127.0.0.1、不可列目錄、不能讀 DB／任意檔案；超額 JSON 在解析前拒絕。
- 無 staged financial files、沒有 GitHub CI 驗收、沒有正式金融資料 push。

## 可重跑入口

```bash
uv run --locked python -m local.check --frontend
uv run --locked python -m local.check --runner unittest
```

`--frontend` 要求 Node.js，沒有安裝會明確失敗，不靜默略過。報告含實際指令、exit code、Python/JS/HTML/CSS SHA256。選用瀏覽器 harness：`scripts/browser_smoke.py`；工具需求與參數見[介面文件](FRONTEND_AND_PREVIEW.md)。瀏覽器 harness 不在預設 Python 測試中自動安裝或下載。

## 仍未完成

指定 Python 3.11 locked 環境的新版完整重現、原 CDN 3.30.4／生產 HTTPS 路徑、真實官方 API／模型／兩份名單、正式部署的互動驗收、授權／單位核對、歷史回測與 NAS 斷電復原。沒有改動 `data/`、`pyproject.toml`、`uv.lock`、GitHub Actions、Pages Source 或排程。前端程式提交 main 後可由既有 Pages 分支流程更新介面，但內容仍是原本示範資料。
