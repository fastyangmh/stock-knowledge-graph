# M3 季報雙軸審查與混合研究版本重驗

審查範圍固定為 `51c91fc...6b0f9a5`，涵蓋 M3-01～03。保留先前分表的[固定基準](VERIFICATION-2026-11-19-M3-FINANCIALS.md)。修正產品 `e7edc48` 已包含 `5a731f1` 的交易回滾；最終實測候選 `3c7f57c2623b543a924e4fe04938f92c8028b6e7` 同時包含 `1118b7f` 的原生行情通知。

## Standards 審查

| 工程標準 | 發現與處理 | 驗證 |
| --- | --- | --- |
| 每來源明列權利及取得方式 | 八份損益／資產負債資料集補入正式 registry，依指定資源與收據離線讀取，保留逐來源署名。 | 八項均排除於有效網路來源，偽造 URL、重複取得紀錄與變造原件會拒收。[登錄清單](DATA_SOURCES.md#季度財報的私有離線來源) |
| 離線 fixture 獨立於產品映射 | 先前部分產業測試從 adapter 取欄名。現從八份既存 CSV 各留一行表頭，配合成企業列；三個測試檔共用同一 research → audit 入口。 | 一般、金融、保險表頭分開驗；原欄消失、新欄及錯誤欄寬均有拒絕案例。 |
| 股票身分與原件定位 | 報表取得時間相同時，先前單因來源署名不同而拒收同一家公司。新輸入將報表來源留於文件與數值，既有 v1 快照在 replay 時按同樣方式讀身分。 | 同公司同時兩表可共存；相異名稱仍拒收。 |
| 交接及錯誤保全文件 | 補 ticket `## Comments` 與單一狀態值，更新 backlog、月營收尺度文件及現金流回滾說明。 | 重送上一版成功；失敗輸入與 latest 都有保全回歸。[現金流操作](QUARTERLY_CASHFLOW.md) |

## Spec 審查

| 規格行為 | 原問題與判定 | 驗證 |
| --- | --- | --- |
| 同時衝突、核對時序與晚到原件 | 兩份同來源、同取得時間的原件衝突可能由較晚的發行人核對勝出。現先按來源與取得時間核對證據雜湊，再依實際可得時間套用同原件的覆核。 | TDD 先重現兩份不同原件皆有覆核且覆核日不同的錯案。同一原件可由未核對進展為已核對，同秒覆核可用，較早截止維持首次狀態。未來覆核拒收；舊截止也無法讓同時矛盾的現金流筆記進庫。 |
| 修訂使某欄成為缺值 | 先前數字會在新原欄明示缺值時殘留。現由原欄、公司、期別與來源定位，隨取得時間讓該值失效；M2 仍可另行保存正式通知。 | CSV 和現金流均經 SQLite、research、audit 重播數值 → 缺值。原始空格與顯式標記仍在快照。整列全缺須有同來源、同公司與期別的先前數值；缺公司列拒絕匯入。來源沒觀察某股票或指標時保持原狀。 |
| 可與真實月營收共同研究 | 先前 ledger 對整庫要求一個版本，已驗月營收與季度無法同庫。現依 source 保存正規化及 adapter 政策，兩市場月營收另共用尺度版本檢查，舊通知仍可指向對應版本。 | 經單位證據轉換的月營收與季報可同庫；再加入舊尺度月營收會拒收。下表以逐次實際本地登錄重播五個截止。 |

## 真實私有重播

八份已存政府 CSV 重算原件 SHA256，依資料集執行正規化與逐版 audit；兩份現金流讀發行人中英版人工筆記。先以 `6b0f9a5` 的逐欄輸出核對原固定樣本，然後加入高雄銀行財報附註（八）的新覆核。另將既有兩市場 `official-monthly-twd-v1` 正規化輸入與三表依序送進一個全新 ledger。21 次登錄每次都建立研究版本並執行 bundle audit。

| 實際截止階段 | 覆蓋股票 | 累計正規化快照 | 未裁剪數值 | 其中損益／資產負債欄的狀態 |
| --- | ---: | ---: | ---: | --- |
| 兩市場月營收 | 4 | 2 | 12 | 此時尚無季報 |
| 加入八份未覆核原件 | 7 | 10 | 68 | 56 欄未核 |
| 加入八份同原件覆核 | 7 | 18 | 68 | 44 欄等值、12 欄未核 |
| 加入兩份現金流筆記 | 7 | 20 | 80 | 44 欄等值、12 欄未核 |
| 加入銀行附註同原件再覆核 | 7 | 21 | 80 | 45 欄等值、11 欄未核。損益 22/22、資產負債 23/34 等值。 |

所有登錄結束後，使用原股票集合與 `--known-at` 各重做上表五個階段。五份 `research-facts.json` 的 SHA256 分別與原先版本相同，五份重播版本均通過 audit。月營收加季報最終涵蓋 12 個數值來源；現金流的 12 欄另計，同一發行人的兩個語言版本等值。與另行發布文件的七欄零容差比較仍為一欄相符、六欄有差額。[現金流欄位與比較文件](QUARTERLY_CASHFLOW.md)

從候選工作樹重跑時，`private` 指向原 checkout 既存私有目錄，`out` 使用新路徑。以下指令均使用已存檔案。

```bash
private=/path/to/stock-knowledge-graph/local/private
out="$private/m3-fin-review-new"
uv run --locked python "$private/m3-income-issuer-expanded/replay.py" "$out/income"
uv run --locked python "$private/m3-balance-issuer-expanded/replay.py" "$out/balance"
uv run --locked python "$private/m3-cashflow-2026-11-19/reviewed/replay.py" "$out/cashflow"
uv run --locked python "$private/m3-balance-issuer-bank/replay.py" "$out/bank"
uv run --locked python "$private/m3-fin-review-3c7f57c/mixed_replay.py" "$private" "$out" "$out/mixed"
TMPDIR=/private/tmp uv run --locked python -m local.check --frontend --report "$out/full-check.json"
```

完整檢查於 macOS arm64、Python 3.11.11、uv 0.6.13、Node v22.16.0 執行。整合前 `e7edc48` 為 579 pytest、319 subtests、55 Node；整合後乾淨候選 `3c7f57c` 為 588 pytest、329 subtests、55 Node，編譯、SQLite／JSON smoke、圖譜驗證全部 exit 0。HTTP 測試以本機 loopback 權限執行。完整報告、逐版時間、SHA256、命令與來源核對都在 `local/private/m3-fin-review-3c7f57c/`。

本次未另驗瀏覽器或 Linux／NAS。現金流官方原件封存、其他產業／期間及正式季報撤回仍待證；合成缺值與通知案例限於工程語意驗證。M3-03 保持 `needs-info`。
