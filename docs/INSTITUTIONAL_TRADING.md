# 上櫃三大法人買賣明細的私有匯入

`local.institutional_import` 讀取已保存的 [TPEx 11856 官方資料集](https://data.gov.tw/dataset/11856) CSV 與同次收據，依指定交易日及股票代號產出研究輸入。資料集使用政府資料開放授權條款第 1 版。資料集網址、提供者、署名與授權連結隨來源寫入研究版本。registry 的 `usage` 是 `offline_saved_receipt_only`，下載器維持停用。

| 組合 | 適用範圍 |
| --- | --- |
| TPEx 11856，2026-11-18 | 11 月 19 日取得。全檔 899 列、25 欄通過結構及算術校驗；研究版本已實測兩個四位數自選代號。產業並非此資料集的分類欄位 |
| TPEx 其他日期及商品 | 相同契約可重播另存的單日收據；其他日期目前尚無私有驗收紀錄。驗收保留全檔原件，選股入口限現有四位數代號 |
| TWSE T86 | 日報有以股計的欄位；含／不含鉅額的商品範圍與可長期封存的權利仍待查。尚未啟用適配 |
| 同日獨立參考、真實修訂與撤回 | 待驗。來源內算術及同一原件回對只證明此次解析一致 |

## 操作

`manifest.json` 包含官方取得清單，同目錄需有 `11856.response`。命令中的 `1000` 是格式範例，實際使用時換成出現在該日原件的四位數代號。為不同修訂或選股保留各自的 normalized 檔，再交由同一個研究 ledger 登錄。

```bash
uv run --locked python -m local.institutional_import \
  --manifest local/private/source-review-2026-11-19/official-resources/manifest.json \
  --trade-date 2026-11-18 --symbols 1000 \
  --output local/private/chips/example.json
uv run --locked python -m local.research --input local/private/chips/example.json \
  --symbols 1000 --history-db local/private/chips/history.db \
  --output-root local/private/chips/runs --analysis none
uv run --locked python -m local.bundle_audit --root local/private/chips/runs
```

CLI 核對收據所載清單與資源 URL、HTTP 結果、時間順序、CSV 媒體型別、長度及 SHA256。欄名或欄數漂移、日期不一致、重複代號、買進／賣出負數、空白／非整數、缺少所選代號、分類算術錯誤，都會中止該檔匯入並保留既有輸出。純股數以整數保存，含逗號的數字須有正確的三位分組。CSV 中的任一列都有可能使整批不適用，錯誤訊息標示可定位的列或欄。

七組分類各有買進、賣出與買賣超，另存來源公布的三大法人買賣超合計，共 22 個 `chip_metrics`。同組買進減賣出應等於帶正負號的淨額。外資及陸資有排除外資自營商的組成項與外資自營商，自營商有自行買賣與避險兩個組成項；各成員已包含於其分類小計，不宜再次相加。三大法人總數直接保存來源欄位。本日外資自營商皆為零，尚缺可辨別總數納入規則的樣本。

每筆事實以股票、來源、交易日及指標識別，保存 `source_column`、`row_number`（表頭為第 1 列）、`raw_sha256` 與 `unit=shares`。來源發布時刻未知，使用收據 `received_at` 作觀察時間；`available_at` 依研究帳本首次登錄時間與來源可得時間取較晚者。數值保存在 `graph.db` 的 `chip_metrics` 與 `research-facts.json`，文字文件只記公司、資料集及股票關聯。一般觀察的較晚修訂可由研究 `--known-at` 重讀先前版本；同時矛盾的觀察拒絕登錄。

## 驗收紀錄

macOS arm64／Python 3.11 使用 2026-11-18 真實單日原件，逐列檢查全檔及分類小計。兩檔所選股票的 44 個來源儲存格逐一對回稽核版事實與 SQLite，重跑後兩份 bundle 均通過 audit，ledger 保有一個相同的 normalized 快照。每次執行的收據時間、雜湊、命令輸出與比較留在私有目錄。從候選 checkout 可用下式重跑，目的目錄須是新路徑。

```bash
uv run --locked python local/private/m3-institutional-2026-11-19/replay.py \
  --manifest local/private/source-review-2026-11-19/official-resources/manifest.json \
  --dest local/private/m3-institutional-2026-11-19/replay-new
```

公開 repo 可用 `uv run --locked pytest -q local/tests/test_institutional_import.py` 執行合成收據驗證。來源範圍、獨立抽檢與使用限制沿用[法人買賣票](../.scratch/m3-evidence-sources/issues/04-institutional.md)。
