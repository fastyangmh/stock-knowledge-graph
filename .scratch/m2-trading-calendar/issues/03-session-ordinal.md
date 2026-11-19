# 03 · 並列觀察筆數與交易日序號

**Parent:** [P2-02｜交易日完整性](../../../docs/DEVELOPMENT_BACKLOG.md#p2-02交易日完整性) · [規格與一次確認範圍](../spec.md)

**What to build:** 研究者在同一完整性報告可核對事件後第 N 個已確認交易日，並與既有事件工具的第 N 筆報價比對。

**Blocked by:** [01 從已稽核行情列出逐日完整性](01-daily-coverage.md)

**Status:** resolved

**Review:** 2026-11-19 使用者已核准。合成資料開發。

## 完成條件

- [x] 以合成的首次保存事件為錨點，按 Asia/Taipei 排除事件當日。報告列出錨點事件／版本、交易日序號、保存報價序號、對應日期與可用性。
- [x] 重現規格週五至週二三種情境；開市缺週一報價時，週二為第 1 筆報價及第 2 個交易日。週一的行情欄位缺值，區間連續性未通過；中途日曆未知則交易日序號不可判。
- [x] 以完整合成序列及中途缺日測第 1／5／20 日的目標與區間狀態；包括年界及目標尚未到期。不得跳過缺值、日曆未知日或把未到期列作已漏抓。
- [x] 用原事件與提醒入口比對同一批 bundle。既有事件 ID、首次基準、首次後續值、horizon_unit、缺值理由及統計分母維持原契約；原價量提醒設定與結果一致。

## 驗證紀錄

2026-11-19 在 macOS arm64／Python 3.11.11 完成工程驗收。程式候選 `6754e80`，私有 CLI 與欄位見[日曆報告手冊](../../../docs/CALENDAR_COVERAGE.md)。合成 CSV 經行情匯入、SQLite、研究與提醒入口實際保存 bundle，日曆與事件 CLI 各自稽核同批版本。

- `uv run --locked python -m pytest -q local/tests/test_calendar_ordinals.py` 對應 7 個測試、6 個 subtests。先驗到未支援事件參數，隨後逐項驗到序號、未知日與目標明細缺失，再實作重跑。
- 週一缺列時第 1 個交易日缺觀察，週二為第 1 筆報價及第 2 個交易日。臨時休市、日曆未知或證據衝突各有獨立案例。跨年樣本第 1／5／20 日為 12/31、1/7、1/28；缺掉第 5 日後，第 5／20 筆保存報價移至 1/8、1/29，交易日目標仍在原位。
- 另以 UTC 週日晚間首次保存的週五提醒，驗到台北週一同日行情排除。週二首存缺收盤價，較晚修訂仍保留原事實 ID 與缺值理由。原報告的事件 ID、首次基準、首次後續、`quote_observations`、分母 1／可計算 0，及原價量提醒 20 筆設定／結果均經比對。
- 候選 `6754e80` 的 `uv run --locked python -m local.check` exit 0，507 個 pytest、266 個 subtests、SQLite 匯出與驗證通過。沙箱首次阻擋既有 HTTP 測試的本機 port，完整結果來自獲准使用 loopback 的重跑。JSON 保存於私有 `local/private/m2-calendar/03/check-6754e80.json`。
- 本票的研究版本使用合成行情與日曆。兩市場正式來源與行情的整合驗收見 [06 票](06-real-acceptance.md)。本票未執行前端或 Linux／NAS 驗收。

併入 02 與整合分支 `c1d5063` 後再驗證同一 CLI 的市場範圍與應到時點。合成 TPEx 週一報價沒有填入 TWSE 的週一缺口；TWSE 週二仍為第 1 筆，原事件工具的跨市場目標另列日期與不可比較原因。另以 02 的截止前應到證據驗到 `pending`，以首存缺收盤價驗到 `observation_continuity=complete`、`close_continuity=incomplete`。三份 CLI 測試 `test_calendar_ordinals.py`、`test_calendar_coverage.py`、`test_gap_evidence.py` 共 28 個測試、29 個 subtests 通過。
