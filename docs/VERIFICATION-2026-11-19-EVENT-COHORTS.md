# 2026-11-19 事件分組、重疊與封存重播驗證

候選 `baaa437` 包含事件分組 `59a19e5` 及開發分支 `7c1cff4`。測試平台為 macOS arm64、Python 3.11.11 與 Node 22.16.0。術語與使用方式見[事件研究手冊](EVENT_STUDY.md)，工程完成範圍見[本地 ticket](../.scratch/m4-research-quality/issues/02-event-cohorts.md)。

## 工程與瀏覽器

- `uv run --locked python -m local.check --frontend` 在可用的本機 loopback 權限下 exit 0，607 個 Python 測試、341 個 subtests、56 個 Node 測試通過。原報告放在私有 `m4-quality/event-cohorts/acceptance/check-baaa437.json`。初次 sandbox 基準因 loopback 無法建立而失敗，改在正常權限重跑完整檢查。
- 合成 CSV 經行情匯入、SQLite、私有研究及 audit，再從事件入口讀取。五個日期的樣本中，同股兩個不同交易日期的事件在第 1 筆期間分開，在第 2 筆期間相交；後者同一分組有兩個事件、一個可計算、一個右設限。展示裁剪為 0 時仍能使用未裁剪數值。
- 其他案例涵蓋同時首次保存基準衝突、跨來源／基準與設定改變、晚登錄較早日期、缺基準、確切月份已過仍無資料、未到期、零納入、首次事件在另一 cohort、行情撤回與重發、舊版 scope 與既有分組重播。價格恰好減半的合成案例保持原值，拆併股覆蓋列未知；改成不同價格基準後無可比數值。
- 合成 Chromium 透過真實 loopback fetch 驗證新、舊、混合四種輸入情境與 390px 顯示，也從分組點選事件查看重疊與右設限。兩市場各自保存的舊報告與新報告另在桌機 1280px 與手機 390px 載入，共八個組合，通過且無頁面錯誤。私有結果分別為 `acceptance/smoke/browser.json` 與 `acceptance/browser.json`。

## 真實官方原件與兩市場短期樣本

每市場使用同一組三版 `with-prior/runs`，從既有私有報告讀取當時的 `analysis_at`，經正常 `local.event_study --root … --as-of … --output …` 另存新報告。表內每一列分別計算，行情採來源原值。原始名稱、代碼、數值、路徑索引、雜湊與報告均保留在私有目錄。

| 私有研究範圍 | 首次事件 | 重複保存 | 已觀察 | 報價筆數不足 | 營收目標月未結束 | 同股其他重疊事件 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 上市 | 1 | 2 | 2 | 4 | 6 | 0 |
| 上櫃 | 1 | 2 | 2 | 4 | 6 | 0 |

每市場唯一事件有 12 個指標與期間組合。兩個已觀察值是第 1 筆報價的收盤變化及成交股數倍數。獨立核對程式從各事件的基準與後續 SHA256 定位原始 CSV、重驗原件 bytes、選取來源列後以 Decimal 重算，兩市場共四個數值皆與報告小數六位一致。另核對每市場其餘十項右設限、重複版本、首次事件、基準及原來的各項衡量欄位。新版及原存報告逐一從稽核後的三個 bundle 重播，四份 canonical JSON 與保存 bytes 相同。

私有驗收位於 `local/private/m4-quality/event-cohorts/acceptance/`。其中 `verify.py`、`event-source-check.json` 沿用原件抽檢邏輯，`replay.py` 從目前 checkout 重算兩版本。從專案根目錄可用 `uv run --locked python local/private/m4-quality/event-cohorts/acceptance/verify.py` 與同目錄的 `replay.py` 重驗，兩者本輪均 exit 0。

下一批真實驗證需要每個事件後第 5／20 筆同基準行情、到期且保存的第 1／3／6 個確切營收月份、同股另一首次事件及相交區間。實際拆併股與正式行情撤回仍缺相應原件。P1-02 行情尺度、完整市場覆蓋及投資有效性均維持原有驗證範圍。
