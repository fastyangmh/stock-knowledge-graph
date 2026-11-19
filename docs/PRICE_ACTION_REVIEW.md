# 私有價格區間與公司行為核對

從兩個已通過 bundle 稽核的研究版本讀取個股收盤價。每端取該版本指定的交易日，報告列出 `run`、事實 `id`、`observed_at`、原始快照 SHA256、來源、未還原基準、幣別與尺度。沒有當日事實或舊版只有展示圖時，該端為 null。可用 `run/research-facts.json` 與來源 CSV 逐筆複查。這項核對由本機比較 CLI 輸出；既有事件的首次保存結果仍依原有定義重讀。

```bash
uv run --locked python -m local.research_compare \
  --root local/private/research-runs --before BEFORE_RUN_ID --after AFTER_RUN_ID \
  --price-review --action-manifest local/private/source-review-2026-11-19/official-resources/manifest.json
```

只用 `--price-review` 也可執行。每個 `--action-manifest` 指向一次已保存的原始資源清單，可重複傳入至多 32 次。清單為 JSON 陣列，恰有一項 `id=11633`，內含官方 `catalog`、確切 `url`、`started_at`、`received_at`、`status="200"`、`exit=0`、`bytes` 與 `sha256`；原始 CSV 名為同目錄的 `11633.response`。每份清單上限 1 MiB、原件 2 MiB。工具檢查私有路徑、資源 URL、原件雜湊與表頭；收據及其觀察時間仍依本機保存的紀錄。資料集提供者為金管會證期局／櫃買中心，採政府資料開放授權條款第 1 版。[資料集 11633](https://data.gov.tw/dataset/11633)

`price_review` 只使用在較後版本 `known_at` 之前或同時已收到的快照。每一條事件證據按市場、股票與 **前收盤日 < 生效日 ≤ 後收盤日** 匹配。原件列號從表頭第 1 列起算。同一事件的不同快照可分別留有證據列，列數不能作事件次數。沒有取得的日期、沒有資料列的股票與其他類型均保留未知。只有日期的空白列列入 `date_only_rows`。

| 個股 status | 讀法 |
| --- | --- |
| `incomparable` | 區間跨已知事件、兩端價格定義不同，或指定交易日倒序。可查 warnings、definition_differences 及 actions。 |
| `coverage_unknown` | 有兩個收盤日，但公司行為區間涵蓋不足。尺度、幣別、交易範圍或正規化版本未核實時，另列 `price_definition_unknown`。 |
| `unavailable` | 至少一端缺當日事實或收盤價。 |
| `same_trade_date` | 同日版本重讀，兩個收盤之間沒有跨日區間。仍須檢查價格定義與來源版本。 |

`unknown_interval_coverage` 列出無法證實完整涵蓋的類型。即使認出一筆事件，其他日期或其他類型仍可能缺漏。本報告只列出原值，沒有轉換方法或還原因子。

## 2026-11-19 官方來源核對

| 市場與類型 | 商品、日期與本次使用範圍 |
| --- | --- |
| TWSE 除權息 | 上市股票等證券的計算結果表可按日查詢，說明載有股利資料起於 2003-05-05，排除除息併案退還股款減資或分割減資。開放資料 89748 是不定期更新的預告表，採 OGDL-1.0；預告不能單獨證實生效。此票沒有可匯入的上市生效日原件，區間涵蓋未知。[結果表及排除情形](https://www.twse.com.tw/zh/announcement/ex-right/twt49u.html) · [預告資料集](https://data.gov.tw/dataset/89748) |
| TPEx 除權息 | 11633 提供每日收盤後、次一營業日上櫃有價證券參考價；程式接受已保存的明示個別事件。官網計算結果查詢自 2008-01-02 提供，早期歷史另表。每日 CSV 與歷史查詢為不同資源，實測見下。興櫃、其他商品代號或其他日期的完整性皆不能由個別股票列推得。[資料集](https://data.gov.tw/dataset/11633) · [官網結果查詢](https://www.tpex.org.tw/zh-tw/announce/market/ex/cal.html) |
| TWSE 分割／併股 | 可查上市股票變更面額後的恢復買賣日，實際換股比率需核對公告。ETF 分割與反分割另有專表。未確認查詢期間起點或自選股票完整涵蓋。[股票面額恢復買賣](https://wwwc.twse.com.tw/zh/announcement/change/twtb8u.html) · [TWSE 市場公告分類](https://www.twse.com.tw/res/data/zh/menu-mega.html) |
| TPEx 分割／併股 | 變更面額恢復買賣表依恢復日、換股率定義參考價。僅適用該類上櫃股票面額事件，本次未查得完整可用期間或綁定研究區間的原件。[變更面額參考價](https://www.tpex.org.tw/zh-tw/announce/market/change/reference.html) |
| TWSE 減資 | 普通股減資恢復買賣參考價格自 2011-01-01 提供；退還股款、彌補虧損及減資併現增有不同處理。此票沒有研究區間可重播的減資原件。[TWSE 減資恢復表](https://www.twse.com.tw/zh/announcement/reduction/twtauu.html) |
| TPEx 減資 | 上櫃減資恢復交易參考價自 2013 年 1 月提供，以恢復買賣日定位。公司完成減資登記的日期不能直接代作市場生效日。本次區間涵蓋未知。[TPEx 減資恢復表](https://www.tpex.org.tw/zh-tw/announce/market/reduction/reference.html) |

表中官網查詢限來源定義和個案核對。兩家交易所的網站條款將已授權政府資料開放平臺提供的資料另列；這次只將 11633 明列的 CSV 資源納入可重複讀取的公司行為證據，官網歷史表的批量取得及再利用權利尚待確認。[TWSE 使用條款](https://www.twse.com.tw/zh/terms/use.html) · [TPEx 使用條款](https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html)

## 真實與合成驗收

- 真實兩市場各兩檔股票，前後交易日為 2026-11-17、11-18。以同一 CLI 指定兩版，逐端核對 bundle 事實的原始收盤值和快照雜湊。當時已收到的 11633 私有原件只有一列 11-19 日期，股票及事件欄位皆空白。四檔的三類區間涵蓋均未知，沒有當期可確認的公司行為。
- 另查同一研究池內一檔上櫃股票的真實除息案例。櫃買中心 2026-07-16 歷史查詢回覆單日 54 筆；以股票代號核對到一列除息，與發行人官網所列除息交易日一致。這個已生效的個案在十一月價格區間以外。單次人工核對的網址、回覆雜湊、定位與原件留在私有目錄。[櫃買中心結果表](https://www.tpex.org.tw/zh-tw/announce/market/ex/cal.html) · [發行人股利資訊](https://www.sas-globalwafers.com/investor-page/shareholder-service/)
- 私有紀錄在 `local/private/m2-price-actions-2026-11-19/`。在實作版本的工作樹，以 Python 執行該目錄的 `check-intervals.py` 即可重讀兩組既有 bundle、重建並核對報告。該目錄的 `interval-check.json` 保存完整 CLI、run ID、輸出雜湊；`historical-check.json` 保存七月個案的逐列核對位置。
- 合成 `local/tests/test_price_action_review.py` 以 research → audit → 比較 CLI 檢查次日生效、邊界日期、不同股票／市場／幣別、來源校驗、晚到證據、未知涵蓋、舊版與同日重讀。另在比較介面以假設的第二價格基準驗證拒比。這些情境不替代 P1-02 行情尺度驗收。

2026-11-19 macOS arm64／Python 3.11.11，實作 `10dee33` 合入已完成的日曆分支後，候選 `9630980` 的 `uv run --locked python -m local.check` exit 0，527 個 pytest、277 個 subtests，以及 SQLite 輸出與驗證通過。兩市場真實 CLI 在該候選重跑通過。完整離線報告為上述私有目錄內的 `full-check.json`。另保留沙箱未開放 loopback 時的測試失敗紀錄；最後一次使用正常 loopback 權限。本票未修改前端或執行瀏覽器驗收。

## 11 月 18 日至 19 日的實際價格區間

在 `67274f3`、macOS arm64，以前節的 `local.research_compare --price-review --action-manifest` 命令比較盤後新增版本與其前版，兩市場各自 exit 0。區間為 2026-11-18 收盤至 2026-11-19 收盤，上市與上櫃各兩檔股票均為 `coverage_unknown`。已核對 11633 原件 SHA256，該原件的 11 月 19 日資料只有日期，可辨識的個股事件為 0 筆。四檔的除權息、分割／併股、減資涵蓋均維持未知。原始收盤值及兩端版本可由私有目錄 `local/private/close-2026-11-19/live-1400/{twse,tpex}/price-review-18-19.json` 追查。[盤後版本與來源收據](VERIFICATION-2026-11-19-EVENT-COHORTS.md#11-月-19-日盤後的同股事件重疊)
