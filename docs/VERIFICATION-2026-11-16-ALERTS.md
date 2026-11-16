# 本地驗證｜價量與月營收獨立提醒（2026-11-16）

[文件中心](README.md) · [規則與使用方式](RESEARCH_ALERTS.md) · [前次驗證](VERIFICATION-2026-11-16-RESEARCH.md)

## 基準與環境

基準為 `690d3f340a7cdc2e98a6aa13315b4bd57e256248`。容器無法直接解析GitHub主機，透過連接器下載該版本已存在的Pages archive作檔案傳輸；沒有重新執行GitHub CI、沒有以其結果驗收。修改前計算Git tree SHA-1，確認local、js、css、scripts、docs、data與遠端相同；不是直接clone成功。

本地Linux、Python 3.13.5、pytest 9.0.2、Node.js 22.16.0、Playwright／系統Chromium。使用現有環境套件；未重建Python 3.11的uv.lock環境、未下載真實模型或金融資料。

## 實際結果

| 檢查 | 結果 |
| --- | --- |
| 修改前完整本地驗收 | 217項Python、74個子案例、20項JavaScript通過 |
| 修改後compileall | exit 0 |
| 修改後完整pytest | **256 passed、98 subtests passed，10.23秒** |
| 獨立unittest | **Ran 256 tests，OK，8.285秒** |
| Node語法與測試 | **27 tests、27 pass、0 fail** |
| 既有SQLite→lexical→lifecycle→JSON | 3股票匯出與驗證通過 |
| 新獨立CLI流程 | 4個虛構CSV匯入→研究提醒→圖譜驗證，6個子程序exit 0 |
| CLI測試結果 | 1股票：2條價量、4條月營收規則觸發；各類分開，非真實金融結果 |
| Chromium DOM／canvas | **11組情境通過，page_errors=[]** |

新增39項Python及7項JavaScript測試。pytest與unittest是相同測試集的不同runner，不相加為512項。

## 新增涵蓋範圍

門檻邊界、下跌與上升、基準排除本筆、零量／零分母／缺失收盤、來源與價格基準差異、歷史樣本不足、長日期缺口、未來觀察、晚到登錄、修訂截止時間、最新期百分比缺漏、未知金額尺度不重算、連續月缺口、跨年閏月、負年增率連續改善、下降與平盤、無效設定、決定性內容ID、證據竄改、私有bundle與既有公開資料不變。

來源CSV與SQLite為真實本機讀寫；CLI以獨立Python子程序執行，未呼叫官方網路。新增價格歷史讀取逐筆校驗原始bytes與記錄，任一基準快照被修改會停止並保留上一版成功pointer。財務資料沿用現有as-recorded ledger；不偽造來源最初公告時間。

瀏覽器檢查兩個獨立顯示區、6條規則的明確狀態、證據展開介面、舊資料尚未計算提示、載入失敗清除舊提醒，以及既有搜尋／股票池／手機布局。仍使用about:blank與記憶體虛構fetch；沒有導航正式Pages。使用本地Cytoscape 3.33.1，網站CDN仍為3.30.4；此測試不驗證正式CDN或實際傳輸中的WebCrypto，JSON校驗另由Python及Node測試。

## 不在驗收範圍

真實官方端點全檔與歷史資料品質、真實模型推論、門檻的投資有效性、交易日完整性、公司行為還原、報酬回測、付費服務、正式金融資料發布與自動排程。合成測試通過不等於正式市場訊號有效。圖檔新增提醒欄位不代表來源資料公開權利自動取得。

本次不修改`data/`、`pyproject.toml`、`uv.lock`、GitHub workflow或部署設定。選用的`--alerts`只增加私有研究輸出和前端呈現；未加旗標保持原行為。

## 重跑入口

```bash
uv run --locked python -m local.check --frontend
uv run --locked python -m local.check --runner unittest --frontend
```

本地報告包含對應Python及JavaScript原始檔SHA256，後續變動需重新測試；驗證紀錄中的秒數只是本次執行結果，不是效能保證。
