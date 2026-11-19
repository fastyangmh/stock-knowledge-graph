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

## 核對區間與事件後第幾日

每個 `days[].session_ordinal` 從 `--start` 起算，第一個開市日為 1。休市日的值為 null。任一日缺日曆或有證據衝突，從該日起的序號都為 null。各股的 `observation_continuity` 涵蓋區間起日到該列日期，讀末列可得整段判定。

| 區間判定 | 所用證據 |
| --- | --- |
| `complete` | 至少一天開市，且每個開市日都有該股的已保存行情列。缺收盤價仍保留位置，可用性另見 `missing_close` |
| `incomplete` | 已確認有範圍內的開市日缺該股行情列；同段其他日期仍可另有未決證據 |
| `unknown` | 有未決日曆或開市日超出研究範圍 |
| `pending` | 沒有已知缺口或未決證據，仍有截止時未到期的開市日 |
| `no_sessions` | 全段已知休市 |

若要核對首次保存事件，從同一目錄的[事件統計](EVENT_STUDY.md)取得 `categories.*.events[].event_id`。在上面命令增加 `--event-id <事件ID>`，將 `--output` 改為新檔。選取該股並使用事件基準行情的市場，日期區間須涵蓋事件台北日的次日起點。工具從稽核後的未裁剪 cohort 及同一截止重新辨識錨點，日曆判讀只讀截止時可用的版本。

報告的 `event_sequence.anchor` 列出事件 ID、首次觸發的版本、報告雜湊、完成時間與台北日期。`event_sequence.days` 從事件台北日期的次日起算，每列並列該市場的 `session_ordinal` 與原事件工具的 `quote_ordinal`。例如週一開市缺行情、週二才有該股第一筆報價，週二會列交易日 2、報價 1。首次保存的後續報價使用原有的市場、事實 ID、bundle 及數值；原本缺收盤價的一筆仍占其位置。

`event_sequence.horizons` 並列第 1、5、20 個市場交易日與第 1、5、20 筆報價的目標日期。未到的日期依截止時已保存的開市安排標示序號，可用性列 `pending`，無法確定日期列 `unknown_calendar`，區間太短列 `outside_report_range`。市場交易日的連續性與報價是否有足夠數值各自判讀。關於價格定義及來源能否比較，查原事件報告的 `status`、`reason` 與分母。[合成 CLI 驗收](../.scratch/m2-trading-calendar/issues/03-session-ordinal.md)

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

01 的合成 SQLite／CLI 驗收見 [01 票](../.scratch/m2-trading-calendar/issues/01-daily-coverage.md)。缺口原因與分市場官方樣本依各票驗收。
