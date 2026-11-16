# 本地整合驗證｜研究歷史、版本比較及財務抽檢（2026-11-16）

[文件中心](README.md) · [研究歷史](RESEARCH_HISTORY.md) · [財務抽檢](FINANCIAL_REVIEW.md)

## 基準與環境

基準Commit：`665a489d9a921bec86437aefa53f6fbe27b2ed9d`。直接git連線仍無法解析GitHub主機；透過連接器下載該Commit既有Pages artifact作**原始檔傳輸**，沒有重新觸發CI，也不採用GitHub CI結果作驗收。解包後逐目錄計算Git tree SHA-1，local/js/css/scripts/docs/data與遠端完全相同，才開始本地測試。

環境：Linux、Python 3.13.5、pytest 9.0.2、Node.js 22.16.0、Playwright與系統Chromium。使用既有環境，未重建Python 3.11的uv.lock環境，沒有下載真實模型或官方金融資料；未改動pyproject.toml或uv.lock。

## 實際執行結果

| 驗證 | 結果 |
| --- | --- |
| 修改前完整本地驗收 | 256項Python、98個子案例、27項JavaScript通過 |
| 修改後compileall | exit 0 |
| 修改後完整pytest | **344 passed、127 subtests passed，11.14秒** |
| 獨立unittest discovery | **Ran 344 tests，OK，11.971秒** |
| Node語法與測試 | **39 tests，39 pass，0 fail** |
| 既有隔離SQLite→lexical→lifecycle→JSON | 3股票成功匯出、完整驗證通過 |
| 新CLI獨立子程序 | 整包audit exit 0；兩版本compare exit 0；已知數值差異的financial_review exit 2（預期） |
| 既有圖譜瀏覽器情境 | **13組通過，page_errors=[]**，含指定版本路由及非法run-ID拒絕 |
| 新歷史頁瀏覽器情境 | **9組通過，page_errors=[]** |

Python新增88項，JavaScript新增12項；pytest與unittest跑的是同一套測試，不加總成688項。秒數只是本機當次結果，不是效能保證。

## 新增覆蓋範圍

整包檢查SQLite bytes、report/latest錨點、manifest、圖檔checksum及股票覆蓋、提醒內容與統計；拒絕缺檔、路徑穿越、symlink、未知檔案、過量／變動中的檔案。最新版本毀損時不重用向量快取，不修改舊pointer。根目錄容量含invalid版本，不以失敗檔案繞過總預算；不自動修復或刪除。

版本比較涵蓋新達／未再達門檻、無法評估、首次可評估、設定／來源／價格基準改變、舊版本基準未知、股票加入／移出、時間倒序拒絕、決定性比較ID與來源不被修改。展示節點變化不當成完整資料庫刪除。

HTTP測試使用真實Python loopback server，驗證只提供allowlist資產與已驗證圖譜、Host防護、GET/HEAD、非法比較參數、SQLite/report/原始檔不可下載、POST拒絕及記憶體快照不隨磁碟變動。預覽JSON大小在解析前檢查；比對只對兩個已捕捉版本運算。

財務抽檢涵蓋精確十進位差異、誤差邊界、未知金額尺度不自動換算、不同幣別／單位／合併範圍／累計與單期拒比、缺資料、相同鍵多來源不擅自選擇、零筆比較不是成功、禁止覆寫來源，以及exit 2仍產生供人工審閱的報告。

## 瀏覽器界線

使用about:blank與記憶體合成fetch；測試不導航到正式Pages或外部主機。新歷史頁無外部JS依賴；既有圖譜仍以本地Cytoscape **3.33.1**測試，網站CDN固定 **3.30.4**未改動，不能宣稱原CDN版本／WebCrypto實際傳輸已驗證。圖檔雜湊由Python與Node另行測試，HTTP行為另用真實loopback測試。

瀏覽器檢查有效／invalid版本清單、獨立提醒類別、設定變更、缺資料、證據展開、安全文字DOM、快速切換晚到回應、時間倒序錯誤及恢復、390px手機布局。完整原有圖譜／搜尋／股票池／提醒場景亦重跑。

## 未完成／不包含

官方來源全檔與財報原文抽檢、季度／籌碼／新聞adapter、還原股價與公司行為、完整歷史回測、門檻投資有效性、正式金融資料發布、排程安裝或NAS斷電演練。財務review是可重跑的抽檢入口，不是假稱已核對真實財報。歷史頁只比較本系統已保存的研究版本；雜湊一致不代表來源真實或法律許可。

本次公開`data/`、Python依賴、GitHub workflow與Pages設定皆不變；新增功能只作私有資料讀取、摘要／比較與本機展示。

## 重跑

```bash
uv run --locked python -m local.check --frontend
uv run --locked python -m local.check --runner unittest --frontend
```

需另備Playwright／Chromium時可使用`scripts/history_browser_smoke.py`；詳細CLI、預算及限制見功能文件。測試報告保存原始檔SHA256，對應此次程式碼而不是所有未來Commit。
