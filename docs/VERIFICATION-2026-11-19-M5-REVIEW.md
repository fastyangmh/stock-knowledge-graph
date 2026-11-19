# M5 私有維運雙軸審查與復原驗收

審查範圍為開發基底 `1bb1bdc` 至 M5 產品 `d8a4692`。修復分支從含文件的 `12c7afd` 開始，納入 M4 事件讀者及開發分支 `b20fb50`。下列最終驗收使用乾淨產品 `1c36d3726e058ec1630b041cc0de38c67a884f4a`。macOS 27.2.1 arm64、Apple M4 Pro、Python 3.11.11、Node 22.16.0。

## 規格軸

| 原發現 | 修復與可觀察驗收 |
| --- | --- |
| 有效的籌碼快照在可攜稽核遭拒 | 研究寫入和封存重播採同一套籌碼與更正證據命名。重建的內容須符合 bundle 內對應檔的 hash，原收據及原件須能重播。真實組合 37 版全數有效，另以合成 22 筆法人事實驗證缺原收據會拒絕。 |
| 保存不完整 HTTP 回應時沒有完整內容雜湊 | 呼叫實際 `save_failure` 產生合成截斷收據，以 `captured_sha256`、長度和路徑驗證留存片段，保留完整 `sha256=null`。刪除片段即拒絕封存。完整失敗回應仍需符合完整雜湊。此次未遇真實線上回應截斷。 |
| 51 版有效歷史超出無法調整的預算 | create 支援 `--max-runs` 1–500、`--max-mib` 1–4096，預設 50、256。v2 將限制寫入封存，verify、restore 按同樣限制重驗。從真實 37 版還原複本用同一份既有月報另建 14 版，預設 exit 1，明示 51 後三步均 exit 0，共 595 檔、1,159 條引用、1 份原事件報告。 |
| 數值異常的月報過早釘選，無法重試 | 每個取得來源先核對選股所用數值與覆蓋才保存驗證指標。兩市場真實原檔各注入一個 `ERR`，使用模擬 HTTP 回應，首輪失敗於月報，重送同 job 各僅取月報一次，公司指標 bytes 相同。 |
| 只看候選指標就回報研究階段成功 | `--through research` 已檢查實際 bundle。破壞候選提醒時保留失敗候選並回報失敗，下次同 job 另建候選。兩個市場都從新的真實資料作業完成失敗、重建及提升；已提升的舊報告 bytes 一致。 |
| 以單一 run 作盤點根時，遺漏版本及來源 | 以真實組合 latest 所指版本直接作根，兩次掃描都保留 bundle、來源與未解析引用。9 檔合計 1,571,274 bytes，1,000,000 bytes 配額超出 571,274；內容與 mtime 指紋相同、增長零。 |

## 程式標準軸

| 原發現 | 修復與可觀察驗收 |
| --- | --- |
| 作業報告失敗前已將候選放入正式目錄，事件統計納入失敗版本 | 保存報告後才移入版本。提升標記原子取代 latest，在此之前 catalog 與直接 audit 排除該候選。兩市場故意阻斷新作業的報告寫入，舊指標、舊報告、catalog 與事件輸入均維持先前的一版；恢復後同 job 成功，正式目錄各兩版。合成測試在標記取代指標前中斷，再以同 job 繼續。 |
| 只封存 CSV 也能通過完整還原 | v2 以對應來源的收據、原件、實際使用的設定重播，結果須與 ledger 的 canonical 內容相符。兩市場月報缺取得清單或 registry 會被拒絕。舊封存依原契約核對並明列新增的來源重播缺口。 |
| 有效籌碼版本不能封存 | 已以真實 TPEx 法人與融資融券完整原收據、原 bytes、研究版本完成還原，兩個來源適配器獨立重建成功。 |
| 合法截斷收據使整組備份失敗 | 以保存片段的正式契約核對，仍拒絕遺失原件、路徑逸出和錯誤的完整內容宣稱。 |
| 判斷項 Duplicated Code | `local.research.archive_snapshot_evidence` 同時提供研究寫入與封存端的 payload／路徑轉換。封存端核對 ledger 重建內容及原件，bundle audit 另行檢查檔案集合與 checksum。 |

## 執行與結果

- 完整 `uv run --locked python -m local.check --frontend` exit 0，696 個 pytest、410 個 subtests、56 個 Node 測試。編譯、示範圖譜建立與驗證也通過。初次修復產品 `d8d0e29` 的受限沙盒結果保留；最終檢查使用允許 loopback 的環境。
- v2 實際 create、verify、restore、原版與還原版 catalog 均 exit 0。37 版有效、零 invalid、零 staging。469 個檔案、879 條引用、1 份保存事件，108 個原始檔與來源 ledger 前後雜湊相符。獨立使用各 CLI 僅讀還原資料，再產出兩份月報、17 份季度財報、兩份現金流筆記、法人及融資融券各一份、公告一份、產業與新聞各兩份；28 份 canonical SHA256 全與 ledger 相同。
- 已保存的事件報告使用 M4 的 `replay_report`，只取該報告明列的版本及原有 cohort 契約。實際 v1 封存內兩份早期事件報告與組合封存的一份報告均重播成功。合成測試同時涵蓋保存後新增 50 版與 M4 新、舊契約。
- 實際舊檔 `m5-restore-2026-11-19/c5d63d2/{twse,tpex}/archive` 各通過 verify、restore 與 bundle audit；每市場 3 版、44 檔、46 條引用，舊指標逐位元相同。CLI 回報 `legacy_v1` 並逐一列出月報缺少 registry。新封存預設使用 v2。
- 各市場的 11/17 私有手動作業使用既存 2026-10 月報及固定離線模型，分別重驗已保存官方原件、兩類提醒及新舊指標。各市場實際兩檔、8 筆事實，重試新增行情 0。另驗證已確認休市以及日曆尚未涵蓋的交易日。當日即時網路到件與每日穩定性仍待觀察。
- 32、128、512 份固定 seed 短文件，以相同 MiniLM revision 核對冷、熱快取。冷跑各計算 496、8,128、130,816 對；熱跑均 0。與獨立 NumPy 全排序對照三組 recall 均為 1，最大絕對分數誤差小於 0.0000005。Chromium 159.0.8154.6 實際經 loopback 與正常 CDN 完成九次圖譜載入，三組首開為 0.271、0.269、0.438 秒。此尺度沿用精確搜尋，超過負載另行量測。

## 私有重跑位置

命令在產品 checkout 執行。以下的 `private` 指主工作樹的 `local/private`，目的目錄須使用新的私有路徑。原始金融資料、SQLite、模型、瀏覽器輸出與測試報告均存放於私有區。

| 證據 | 重跑程式與保存結果 |
| --- | --- |
| 全套與 37 版復原 | `m6-preflight/m5-check-1c36d37.json`；`m6-preflight/portfolio-restore.py <新目的> <portfolio-2b03884/ledger.db> <portfolio-2b03884/runs> portfolio`；結果 `portfolio-restore-1c36d37/{commands,summary}.json` |
| 28 次重建、51 版及舊版 | `m6-preflight/regenerate-restored.py <restored> <新目的>`，見 `regenerated-1c36d37/results.json`；`m5-real-budget.py <restored> <新目的>`，見 `m5-51runs-1c36d37/*.log`；舊版 `m5-legacy-1c36d37/summary.json` |
| 來源與中斷重試 | `m5-manual-2026-11-19/ops01-v1/{exercise.py,replay-1c36d37/summary.json}`；`m6-preflight/{m5-real-input-retry.py,m5-retry-reviewed.py}` 各讀新的重播作業目錄，結果 `m5-source-retry-1c36d37/summary.json`、`m5-retry-1c36d37/summary.json` |
| 盤點與容量 | `m6-preflight/portfolio-restore-1c36d37/single-run-{inventory,delta}.json`；`m5-capacity-preflight/verified-1c36d37/{summary,browser}.json`。固定模型、CPU、記憶體與各階段秒數均在容量報告內。 |

此輪來源與還原目錄位於同一個 APFS 裝置。Linux／NAS、獨立媒體、實際斷電以及 M1 09／10 的行情獨立核對仍待外部證據。各來源抽檢、權利及真實撤回按各來源票維持原狀。

[維運操作](OPERATIONS.md) · [手動更新](MANUAL_UPDATE.md) · [M5 四票](../.scratch/m5-private-operations/spec.md)
