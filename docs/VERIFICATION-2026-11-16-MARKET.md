# 官方盤後行情模組：離線驗證紀錄（2026-11-16）

[文件中心](README.md) · [功能及操作](MARKET_PRICES.md)

## 基準與範圍

遠端基準 `df87480c8ecc7895cc6c8671090c252ec6989715`。直接clone因DNS無法連線；使用GitHub連接器讀取相關來源，在本地重建新模組及必要的既有 `core.py`、`dates.py`、`safety.py`，比對Git blob SHA-1與遠端完全一致。這是新功能的局部測試副本，不是完整clone。

環境：Linux、Python 3.13.5、pytest 9.0.2、uv 0.10.0。使用已存在的套件／標準函式庫，沒有重建Python 3.11的uv.lock環境。

## 本次實際執行

| 檢查 | 結果 |
| --- | --- |
| 新模組及相依程式compileall | exit 0 |
| `pytest -q local/tests/test_market_prices.py` | **39 passed，41 subtests passed** |
| 獨立unittest runner | **Ran 39 tests，OK** |
| TWSE虛構CSV CLI → 真實SQLite／原始快照／結果報告 | 2檔、2筆新觀察 |
| TPEx虛構CSV CLI → 同一SQLite但獨立市場／來源 | 1檔、1筆新觀察 |
| 最新觀察view／更正保留／同時間衝突回復 | 測試通過 |

測試使用任意虛構代碼1000、1001及虛構2020-01-02報價，不代表真實股票資料或臺灣50／009816資格。HTTP使用注入回應；SQLite和檔案存取為真實執行。沒有Git push金融資料、啟用排程或修改公開網站行情。

涵蓋：上市／上櫃欄位映射、民國／西元日期、明確代碼覆蓋、空值與零、OHLC範圍、十進位精度、整數上限、非法CSV／HTML／重複欄位、未來及混合交易日、固定端點、限量讀取、403不重試、429有限重試、不追蹤重新導向、私有路徑／symlink防護、快照完整性、同一觀察冪等、修訂追加、倒序匯入與CLI離線無網路行為。

## 未驗證的事項

**沒有重跑既有116項Python或19項JavaScript測試**，也沒有重驗瀏覽器、模型、GitHub CI、正式TWSE／TPEx CSV全檔下載、官方歷史還原行情或真實網站發布。新模組不修改既有核心／圖譜處理程式與依賴，測試會被未來的 `local.check` 正常發現；但不可把本次39項通過當作全部系統驗收。

本次核對了政府資料集頁與所列CSV連結。web取得連結時返回不支援CSV內容型態，工作環境無直接網路；**沒有拿到正式回應bytes，因此無真實端點成功紀錄**。來源若變更會fail closed，不能據此假設live integration已完成。

## 重跑（非現在要求使用者重測）

```bash
uv run --locked pytest -q local/tests/test_market_prices.py
uv run --locked python -m unittest discover -s local/tests -p test_market_prices.py -v
```

完整回歸仍使用原本 `uv run --locked python -m local.check --frontend`，本輪未宣稱已執行。
