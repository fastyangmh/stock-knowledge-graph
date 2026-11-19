# 私有交易日曆完整性報告

`local.calendar_coverage` 將指定市場的台北曆日逐日展開，用封存日曆判斷開休市，並在指定研究版本中尋找每檔股票當天的行情。報告適用於核對已保存的資料。個股上市或下市期間、價格尺度及資料應到時點需有各自的證據。

## 產生報告

先準備研究版本目錄及已人工核對的日曆索引，將原始檔放在索引所在的私有目錄或其子目錄。日期區間含首尾，`--as-of` 必須帶時區。以下日期與代碼是命令格式的示例。

```bash
uv run --locked python -m local.calendar_coverage \
  --root local/private/research-runs \
  --calendar local/private/calendar/index.json \
  --market twse --symbols 1000 1001 \
  --start 2019-01-05 --end 2019-01-08 --as-of 2019-01-09T20:00:00+08:00 \
  --output local/private/calendar-reports/coverage-001.json
```

每次先稽核整個 `--root` 及其 latest 指標，只取截止時已完成的研究版本。私有檔案不接受 symlink。把報告放在研究輸入目錄外，重跑相同內容可沿用同一路徑，變更條件時使用新檔名。遭遇雜湊錯誤、無效契約或超額等錯誤時 CLI 以非零結束，保留舊檔。日曆未涵蓋、研究範圍不足等有效診斷可產生報告，exit 0 本身不證明行情連續。

## 日曆輸入

索引為 UTF-8 JSON。以下示意只包含一個單日明示的合成條目，執行前須將 `path` 指向實際封存檔、將 `sha256` 換成對該檔原始 bytes 計算的 64 位小寫十六進位 SHA256。

```json
{
  "schema_version": "market-calendar-1",
  "entries": [
    {
      "id": "synthetic-closure-v1",
      "market": "twse",
      "start": "2019-01-07",
      "end": "2019-01-07",
      "source_url": "https://example.org/calendar/closure",
      "date_semantics": "合成公告明示之台北市場交易日期",
      "retrieved_at": "2019-01-07T08:00:00+08:00",
      "saved_at": "2019-01-07T08:01:00+08:00",
      "path": "closure.txt",
      "sha256": "<封存檔的 SHA256>",
      "days": {"2019-01-07": "closed"}
    }
  ]
}
```

- 每版用唯一的 `id` 識別，`market` 為 `twse` 或 `tpex`。適用範圍必須有原始依據，結算日須另核對是否允許股票交易。索引由人工解讀官方來源；CLI 重算原檔 SHA256，研究者可依 `source_url`、`date_semantics`、封存檔及另存的授權紀錄複核該解讀。
- `days` 只接受區間內的日期及 `open`、`closed`。有適用且已核實的完整週期時才給 `open_weekdays`，例如平日開市為 `[0,1,2,3,4]`，週一為 0。同版 `days` 優先於週期。省略週期時，未明列日維持未知。
- `published_at` 可省略或為 null。已知時間應滿足發布 ≤ 取得 ≤ 本地保存。`saved_at` 要能證明版本在該時已保存。截止後才保存的一版，不參與較早判讀。
- 適用日期有更正公告時在新版填 `supersedes`，列出同市場舊版 ID。只在新版也提供判讀的日期取代舊版；保留各版原檔及 `saved_at`。互斥且無取代關係的版本列為衝突。

## 查讀逐日結果

`inputs` 記錄各版識別、報告 SHA256、完成／知悉時間、選股及行情範圍。`calendar.versions` 保存截止時可用的判讀條目。`days[].evidence_ids` 對應到實際採信或有爭議的版本。`market_counts` 按曆日計，`stock_counts` 每檔按日計，兩者都可以回到 `days` 核算。狀態計數只有出現時才列。

| 從報告看到的情況 | 如何判讀 |
| --- | --- |
| 市場 `open`、`closed`、`unknown` | 已確認開市、已確認休市、缺該日或該市場證據 |
| 市場 `conflict` | 有效日曆判讀矛盾，或休市卻有該市已保存行情。後者會列出衝突的行情識別及版本 |
| 個股 `observed` 或 `missing_close` | 有未裁剪行情，保存原有收盤價或 null 及交易量；同一期採首個可證實的 bundle 保存版本 |
| 個股 `missing_observation` | 日曆確認開市、範圍涵蓋、指定研究版本中無該筆。原因待查 |
| 個股 `insufficient_scope` | 看 `reason` 區分截止前沒有版本、未選該股、僅展示圖、市場不符、超過行情截止 |
| 個股 `closed`、`unknown_calendar` 或 `calendar_conflict` | 休市無行情、無行情且日曆未決、或存在日曆證據衝突；已保存列仍可由 `observation` 查回 |

行情 `observed_at` 記錄來源觀察時間。`captured_at` 是供應版本中首份包含該日該股事實的 bundle 完成時間；原行情的本地登錄時間未知時保留 `recorded_at_status=unknown`。讀者應一起檢查市場與個股欄位，即使日曆未知也可能有已保存行情。

預設整個研究目錄、索引與適用原檔合計預算 256 MiB、50 個版本及 50,000 個「股票 × 曆日」列，可用 `--max-mib`、`--max-runs`、`--max-rows` 調整。日曆索引上限 4 MiB、512 個條目，單份封存證據 32 MiB；另設日曆判讀工作量與報告大小上限。既有 `local.trading_calendar` 的 CSV 判讀入口仍用於原盤後流程。

01 的合成 SQLite／CLI 驗收見 [01 票](../.scratch/m2-trading-calendar/issues/01-daily-coverage.md)。事件後序號及分市場官方樣本依對應票驗收。

## 以證據說明個股缺口

於同一命令加上 `--gap-evidence local/private/calendar/gaps.json` 可提供已核對的個股公告、資料應到時點或擷取紀錄。使用 `market-gap-evidence-1` 的 UTF-8 JSON 索引。每筆 `source_id` 指向受診斷的行情資料集，上市為 `twse_daily_11549`，上櫃為 `tpex_daily_11371`。下例欄位及檔名均為合成範例。

```json
{
  "schema_version": "market-gap-evidence-1",
  "entries": [
    {
      "id": "synthetic-fetch-1",
      "market": "twse",
      "source_id": "twse_daily_11549",
      "date": "2019-01-07",
      "saved_at": "2019-01-07T19:00:00+08:00",
      "kind": "fetch_failed",
      "run_id": "attempt-1",
      "failure": "download failed",
      "locator": "執行紀錄內的 attempt-1",
      "path": "attempt-1.json",
      "sha256": "<封存檔的 SHA256>"
    }
  ]
}
```

每筆使用唯一 `id`，`date` 為台北交易日期。提供本地可證實的 `saved_at`、原始封存檔相對路徑、SHA256 與可回查的 `locator`。維護者先核對原始文件與逐筆解讀，程式檢查檔案雜湊並套用截止、行情來源、市場、交易日與個股範圍。每次只納入截止時已保存的證據。索引與封存檔也使用整體讀取預算。

| `kind` | 額外欄位與判讀 |
| --- | --- |
| `suspended`、`no_trade` | `stock_id` 如 `TW:1000`；`source_url` 指向對應交易所官方 HTTPS 來源。需有明示個股停牌或當日無成交的證據。僅存零量或缺收盤價者保留原值與未知狀態。有正成交量或成交筆數時遇到相反公告會列 `conflict`，兩份證據均保留。 |
| `fetch_failed` | `run_id` 與 `failure` 定位對應市場、行情來源與交易日的失敗執行紀錄。 |
| `due` | `due_at` 為該行情文件有依據的應到時點，必須帶時區。無法證實時點時可省略這筆證據。多份紀錄的時點相異會列 `due_conflict`。 |
| `missing_file` | 提供 `quote_file`、`expected_files`、`missing_files` 及帶時區的 `checked_at`。必須在預期及缺件清單均找到指定行情檔，且清點已達可判定的應到時點，才列缺檔。 |

逐股逐日的 `status` 與 `stock_counts` 仍回答有無保存行情。另讀 `diagnosis` 的 `stock_state`、`acquisition`、`timing` 與 `gap`；證據 ID 可對回 `gap_evidence.versions`。停牌、抓取失敗及缺檔可以同時存在。即使證據解釋缺列，該日仍計入 `missing_observation`。已存列會顯示原 `close`、`volume_shares`、`turnover_raw`、`turnover_unit`、`price_unit` 及 `trades`。完全無行情列時 `observation` 保持 null。

`diagnosis_counts` 按股分別統計各狀態。`gap.unresolved` 是範圍內已開市、缺觀察且原因待查的日數。`pending` 是已知應到時點尚未到；應到時間不明時 `timing=due_unknown`。取得狀態按每一種成立原因各計一天，同日有兩種原因會計入兩類。

`late_first_bundle` 表示該日行情首次出現在所提供且已稽核的研究版本時已過應到時點；依據是 `observation.captured_at` 與 `timing_evidence_ids`。行情來源的 `observed_at` 與供應端實際晚發是不同判斷。原始本地登錄時間未知時，`recorded_at` 保持 null。
