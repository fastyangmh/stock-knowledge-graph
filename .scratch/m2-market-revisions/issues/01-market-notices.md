# 01 · 在行情庫重播可追溯的來源通知

**Parent:** [P2-04](../../../docs/DEVELOPMENT_BACKLOG.md#p2-04修訂與撤回) · [規格](../spec.md)

**What to build:** 研究者能從正式通知辨識原版、有效版與撤回狀態，在私有行情與研究入口按截止重讀。

**Blocked by:** 已有 P2-01 的未裁剪行情事實及 P2-04 的正常 ledger 通知契約。無須等待 09／10 即可驗證合成來源及舊資料相容；涉及真實尺度的結論仍依賴 P1-02。

**Status:** needs-info（工程與原行情重播已驗，真實交易所行情通知待驗）

- [x] 原始行情與通知各綁定來源／市場／股票／交易日／原件 hash。明示更正、撤回、重發與版本衝突可在正常入口重跑。
- [x] 驗證早晚 cutoff、同時衝突、缺列與遲到舊檔；失敗保全舊成功版本與可重跑狀態。舊資料未知本地時間如實呈現。
- [x] 串行情與研究事實、提醒及 audit。驗證新版本的採用與未採用原因，早期 immutable bundle 及首次事件不回寫。
- [x] 既有兩市場真實行情副本重讀成功。正式來源通知未能取證時，留下實際查核、缺少的原件及恢復條件，真實通知列待驗。

- [ ] 取得可對應受審資料集、個股、交易日與適用交易範圍的真實交易所行情通知，以及該筆原檔、撤回或替代原件。取得後按早、晚截止重跑研究與稽核。

2026-11-19 在 TWSE 與 TPEx 官網檢索 11/17、11/18 的行情更正與撤回。找到 TWSE 每日市場總量及個股月報、TPEx 不含定價查詢及另一交易範圍收盤報表。這些頁面沒有明示撤回或更正所存原件。兩市場各兩日的既有原件只支持原行情重播。重大訊息的發行人更正另屬文件來源。[TWSE 市場成交資訊](https://www.twse.com.tw/zh/trading/historical/fmtqik.html) · [TPEx 每日收盤行情（不含定價）](https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing/historical.html)

私有重播程序在 `local/private/m2-market-notices/replay.py`。從候選 checkout 設定 `PYTHONPATH=.`，使用已鎖定 Python 執行。每次建立新的 SQLite 副本與輸出目錄。四次行情 CLI 重驗完整原始 CSV，兩市各兩檔行情逐欄符合原研究事實。四份研究按相同 cutoff 重跑提醒及整包 audit，各市場兩日分別有 8、10 筆完整事實。每市場 21 個舊 bundle 檔案 SHA256 相同，既有一個事件的首次基準及後續結果均相同。未重跑語意模型，本票研究採 `--analysis none`。

**驗證版本**　實作 `bb611d0`，與正規化來源修復整合後的乾淨候選 `6c79abd`。macOS arm64、Python 3.11.11，既有 Node 22.16.0，`TMPDIR=/private/tmp uv run --locked python -m local.check --frontend` exit 0，559 pytest、296 subtests、55 Node tests。測試涵蓋兩市場通知輸入、明示撤回、重發、待生效、原件與來源錯配、同時衝突、一般日檔缺列及晚到舊檔、歸檔數值／報告錯配、提醒與事件首次保存。最初 sandbox 禁止 loopback；取得本機測試權限後，第一次完整檢查未找到 Node，加入專案既有的 Node 路徑後全套通過。瀏覽器、真實通知及語意模型不在這次重跑範圍。

主要工作區私有證據 `local/private/m2-market-notices/` 內，`full-6c79abd.json` SHA256 `5ffbbb632bb978b524c3c1d02fec25e5b60c69821453d826c719e9c680750b1c`，`replay-9hzf5tl1/result.json` SHA256 `085a28541f934c2fdd683992a2f9946cd89e594105d50e7848f9e4808bc1b9b1`。

**審查後重驗**　候選 `8175e97` 已補齊重抓舊檔、通知待生效時的一般行情、累計預算、跨股票撤回原因與圖譜／提醒引用。57 個聚焦測試及完整 `--frontend` 通過。上市、上櫃兩日再次重播，每市場 21 份原有檔案和首次事件核對相同。[Standards 與 Spec 逐條結果](../../../docs/VERIFICATION-2026-11-19-MARKET-NOTICE-REVIEW.md)
