# 本地開發驗證紀錄｜2026-11-15

## 基準與環境

遠端基準：`52e32651d1041a5d4cc7f811ead15c9e98d3bf88`。連接器核對原始檔與 Git blob 雜湊後在本地建立測試副本；並非直接 clone 成功。原始 16 項 pytest 已在此環境通過後才修改。

此次環境：Python 3.13.5、pytest 9.0.2、uv 0.10.0、Linux。執行環境無法直接下載 GitHub／官方 CSV／模型，因此使用既有 Python 套件、標準函式庫、離線 fixtures、注入 encoder 和本機 Git repositories 測試。**沒有在此重新執行 `uv sync --locked`；使用者先前 Python 3.11.18 / uv 0.13.6 的鎖定安裝成功屬另一筆驗證。** pyproject.toml 和 uv.lock 不變。

## 實際結果

| 檢查 | 結果 |
| --- | --- |
| 修改前 pytest | 16 passed |
| 修改後 compileall | exit 0 |
| 修改後 pytest | 69 passed；1.24 秒（最後一次記錄） |
| 獨立 unittest runner | Ran 69 tests，OK；1.185 秒 |
| 隔離 SQLite → lexical → lifecycle → JSON | 3 篇文件、3 檔股票匯出成功 |
| 完整 preview manifest／圖譜驗證 | Validated 3 stock graphs |
| 50 家虛構公司 adapter→SQLite→假 encoder→JSON | 通過；50 次向量化、第二次全快取且重用關聯、50 圖譜驗證 |
| 500 個虛構向量，32 維，K=5 | 124,750 次配對、2,500 個保留候選、1,547 條聯集邊，0.2816 秒 |

500 向量測試不是股票績效或真實新聞 benchmark；候選數不是整個程序 peak RAM。精確演算法仍為二次時間成本，僅把候選儲存改成 O(NK)。

## 新增檢查範圍

快取全命中不載模型、不掃配對；單篇變更；股票對應變更；模型維度／批次／NaN 拒絕與 refresh rollback；日期格式、區間重疊、未來 availability；新聞視窗、股票／資訊節點分別限額；股票清單縮小後移除舊 JSON；stage 失敗回復、禁止 symlink／路徑穿越／無關檔案；CLI 明確 threshold 不被預設覆寫；來源快照 checksum、有限重試、失敗保留上一批 manifest；官方 CSV 欄位與缺值／零／民國日期映射；Git dry-run 不改 index、拒絕既有 staged／無關工作、只推資料到臨時本地 bare repo。

特別修復：舊 test_pipeline.py 的 stale-graph assertions 原先因字面 `\n` 混入註解，測試雖綠燈但沒有執行那段驗證；現在是真正執行的回歸測試。

## 仍未驗證／尚未完成

真實官方 CSV 完整下載、新版真實 SentenceTransformer 權重推論、正式台灣 50 名單及歷史名單權利、金額尺度、真實資料覆蓋、瀏覽器互動、GitHub CI、正式資料 push、NAS 斷電復原、全面雙時間歷史回測。不把已通過的離線測試當成這些項目的驗收。

本次只提交程式與文件；不修改 data/、網站部署來源、GitHub Actions workflow、pyproject.toml 或 uv.lock。

## 可重跑入口

```bash
uv run --locked python -m local.check
uv run --locked python -m local.check --runner unittest
```

測試入口會產生 `local/private/check-report.json`，包含實際指令、exit codes、輸出與 Python 原始檔 SHA256。只有對應原始碼的紀錄才有效，後續修改應重新執行。
