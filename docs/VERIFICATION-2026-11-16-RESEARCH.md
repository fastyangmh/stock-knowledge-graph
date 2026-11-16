# 本地整合驗證｜自選股票、修訂歷史與備份（2026-11-16）

[文件中心](README.md) · [功能與操作](PRIVATE_RESEARCH.md) · [前次行情模組](VERIFICATION-2026-11-16-MARKET.md)

## 來源基準與環境

基準 Commit：`81f96a1d52f5beb0a662cae976f566d39315b9ae`。容器直接連線 GitHub 仍受 DNS 限制；本次透過連接器下載該 Commit 已存在的 Pages artifact **作為檔案傳輸**，不採用其 CI 結果驗收。解包後逐目錄計算 Git tree SHA-1，`local/`、`js/`、`css/`、`scripts/`、`docs/`、`data/` 與遠端相同；必要配置另核對 blob。不是宣稱直接 clone 成功，也沒有重新觸發 GitHub CI。

本地環境為 Linux、Python 3.13.5、pytest 9.0.2、Node.js 22.16.0、Playwright／系統 Chromium；使用已有套件。未重建 Python 3.11 的 uv.lock 環境，未重新下載 Sentence Transformers 權重。

## 實際執行結果

| 檢查 | 結果 |
| --- | --- |
| 修改前完整本地驗收 | 155 項 Python、53 個子案例及19項 JavaScript測試通過 |
| 修改後 compileall | exit 0 |
| 修改後完整 pytest | **217 passed、74 subtests passed，9.33秒** |
| 獨立 unittest discovery | **Ran 217 tests，OK，7.724秒** |
| Node 語法與測試 | **20 tests、20 pass、0 fail** |
| 既有隔離 SQLite→lexical→lifecycle→JSON | 3股票匯出與完整驗證通過 |
| 新流程獨立CLI子程序 | 虛構CSV→行情DB→研究ledger→數值圖譜→驗證→備份→還原，全數exit 0 |
| 新CLI輸出 | 1股票、1財務數值節點、1行情節點；原始CSV校驗成立，未發布 |
| Chromium記憶體fixture互動 | **10組情境通過、page_errors=[]**，包含行情關係與中文數值詳情 |

本次新增62項Python測試，另增加前端邏輯及瀏覽器情境。以上是真實執行結果，不將測試數量當成功能正確性保證。

## 新增覆蓋範圍

- 不用指數／ETF名單的明確代碼匯入，原雙來源模式不變。
- 正規化快照追加、首次本地登錄時間、重跑冪等、資料修訂、晚到舊檔不覆蓋新版。
- 以本系統已知時間裁切；今天補匯入的舊檔不能偽裝成昨天已知。來源衝突／同時間矛盾修訂停止。
- 真實SQLite與CSV校驗：價格來源、原始bytes SHA256、數值型別、OHLC、日期、修訂選擇。
- 價格／財務數值節點不建立文字embedding，且在既有節點總上限內保留必要數值展示。
- 私有不可變run bundle、完整報告與latest指標；失敗不替換上一個成功版本。
- 同模型跨bundle快取重用，全部未變時不載模型、不重算關係；以測試encoder驗證，非真實權重。
- SQLite一致性備份含已提交WAL內容；獨立單檔驗證、SHA256、還原拒絕覆寫與競爭建立目標。
- 瀏覽器顯示行情來源尺度、股數、交易日與非語意關係；原有股票池篩選與手機版仍通過。

## 瀏覽器與現場驗證界線

瀏覽器測試以about:blank載入實際HTML/CSS/JS和記憶體虛構fetch，阻擋對外請求，並非導航到正式Pages。使用本機Cytoscape **3.33.1**，網站仍固定CDN **3.30.4**；沒有聲稱兩者逐bytes相同。記憶體瀏覽器情境不驗證WebCrypto真實傳輸雜湊，相關邏輯由Node測試、圖檔由Python驗證。

沒有執行真實官方CSV全檔下載、新版真實模型推論、公開金融資料push、排程安裝或NAS斷電演練。行情來源單位尚待核對，仍標記`source_reported`；模組不計算投資報酬、不提供交易建議。研究ledger是本系統登錄以後的觀察紀錄，不是完整市場歷史或正式回測引擎。

## 尚待決策／後續工作

P0–P2的這一批私有資料整合已驗證；完整季度報表、籌碼／新聞adapter、ANN及正式來源現場驗收仍未完成。P3的首批異常訊號應先由使用者選定研究範圍（價量、月營收或兩者），再制定明確的基準窗口、門檻與評估方式。不擅自推出買賣訊號、付費資料或公開發布。

## 重跑入口

```bash
uv run --locked python -m local.check --frontend
uv run --locked python -m local.check --runner unittest --frontend
```

本次不修改`uv.lock`、`pyproject.toml`、公開`data/`或GitHub workflow。新測試會被本地檢查入口自動發現；產出報告包含原始碼SHA256，後續程式修改必須重新驗證。
