# 季度財報私有匯入

`local.quarterly_import` 讀取已封存的官方 CSV 與取得紀錄，以公司代號選取資料。季度 CSV 的年度、季別、出表日期及取得時間各自保存。財報涵蓋幾個月、合併或個別報表、金額尺度及幣別，依逐欄的發行人財報核對紀錄填入。每股數值標為 `per_share`，運用來源數值時可檢視對應原欄名與單位。核對失配保留在 `issuer_review.status`，缺值與原欄位置保存在 `metadata.missing_values`。各表的數值使用既有未裁剪研究事實和版本稽核。[私有研究](PRIVATE_RESEARCH.md)

資產負債表採同一入口，完整欄位、期末存量核對與兩市場限制見[資產負債表](QUARTERLY_BALANCE.md)。

另可匯入已核對的發行人現金流量表私有筆記。[報表範圍及重播](QUARTERLY_CASHFLOW.md)

## 支援範圍及 2026-11-19 抽樣

政府開放資料平臺列金融監督管理委員會證券期貨局為提供機關。下列各目錄分別列出本資料集、CSV 資源及政府資料開放授權條款第 1 版。程式逐 ID 固定目錄與精確資源 URL。只在私有研究入口取用。發行人財報以正常閱覽方式核對並保留必要欄位及頁碼。[授權條款](https://data.gov.tw/license)

| 115 年第 3 季綜合損益表 | 映射數值 | 私有原件與獨立抽樣結果 |
| --- | --- | --- |
| [上市一般業 91998](https://data.gov.tw/dataset/91998) | 營收、營業利益、本期淨利、基本 EPS | 1,053 家有代號。選兩家共 8 筆事實。兩家前九月基本 EPS、一家前九月營收零容差相符。另一家營收的發行人報表以整數百萬元揭露，換算後仍有差異。4 筆未核對。[發行人核對](../.scratch/m3-evidence-sources/issuer-reference-2026-11-19.md) |
| [上櫃一般業 94853](https://data.gov.tw/dataset/94853) | 同上，端點與快照獨立 | 891 家有代號。選一家共 4 筆；合併報表前九月營收及基本 EPS 零容差相符，餘 2 筆未核對。[環球晶財報第 5 頁](https://www.sas-globalwafers.com/wp-content/uploads/2026/05/GlobalWafers_2026Q3-consolidated-financial-statement_CN.pdf) |
| [上市金融業 91995](https://data.gov.tw/dataset/91995) | 利息淨收益、本期稅後淨利、基本 EPS | 10 家有代號。抽一家個別報表，前三季三欄均零容差相符。[高雄銀行季報第 5 頁](https://www.bok.com.tw/zh/-107?_com_khb_announcearea_AnnounceListN_INSTANCE_dsew_fileID=1301958&p_p_cacheability=cacheLevelPage&p_p_id=com_khb_announcearea_AnnounceListN_INSTANCE_dsew&p_p_lifecycle=2&p_p_mode=view&p_p_resource_id=download&p_p_state=normal) |
| [上市保險業 92000](https://data.gov.tw/dataset/92000) | 保險服務結果、本期淨利、基本 EPS | 5 家有代號。抽一家個別報表，前三季三欄均零容差相符，EPS 欄名無「元」字樣，單位來自發行人報表。[旺旺友聯季報印刷第 5 頁](https://www.wwunion.com/wp-content/uploads/2026/11/115Aud-Report-Q3.pdf) |
| [上櫃金融業 94850](https://data.gov.tw/dataset/94850)、[上櫃保險業 94855](https://data.gov.tw/dataset/94855) | 尚未啟用 | 原件各只有出表日期與一列空公司，待有公司、期別及相應獨立財報後覆核。其他業別與期別也不在本次抽樣範圍。 |

每個資料集驗證完整標頭集合，包括尚未映射的原始欄位。原件的數值記錄序號從 1 起算，不含表頭。每次匯入要求全檔公司資料同一報表日期與期別；同一選取公司出現兩列時必須釐清。缺欄、新欄、錯誤欄寬、重複欄名、未閉合引號、來源或雜湊不同均會中止。結果可重跑；輸出內容變更時使用新檔名。

## 本機重跑

民國年度、季別按曆季計算期末（例如 115 年第 3 季為 2026-09-30）；保留原始年度與季別。非曆年會計年度尚待另行適配。

每份原件放在取得紀錄旁的 `<政府 ID>.response`。UTF-8 的 `manifest.json` 為陣列，每一個選取的 ID 須有唯一一筆成功的紀錄。必要欄為整數 `id`、`catalog`、`url`、含時區的 `received_at`、HTTP `status` 字串 `"200"`、整數 `exit=0`、`bytes` 與原始 bytes 的 `sha256`。檔案存放於忽略版控的 `local/private/`。讀取舊快照時沿用原取得時間。

下例重讀本輪上市一般業原件。更換 `--dataset`、同一資料集的取得紀錄、`--symbols` 與抽檢檔，即可重讀其他已支援資料集。

```bash
archive=local/private/source-review-2026-11-19/official-resources
evidence=local/private/m3-income-2026-11-19
run_dir=local/private/quarterly-91998
uv run --locked python -m local.quarterly_import \
  --manifest "$archive/manifest.json" --dataset 91998 --symbols 2330 2454 \
  --review "$evidence/91998-review.json" --output "$run_dir/input.json"
uv run --locked python -m local.research --input "$run_dir/input.json" --symbols 2330 2454 \
  --history-db "$run_dir/ledger.db" --output-root "$run_dir/runs" --analysis none
uv run --locked python -m local.bundle_audit --root "$run_dir/runs"
```

`--review` 可省略，此時保留原值與未知定義。審閱人讀取發行人對應期間的原始報表，記錄表別、單位、範圍和資料欄位置。下列為合成格式範例；`raw_sha256` 需換成實際來源雜湊。

```json
{
  "schema_version": "quarterly-review-v1",
  "dataset": 91998,
  "raw_sha256": "<原件 SHA256>",
  "reviewed_at": "2020-11-12T02:00:00Z",
  "rows": [{
    "stock_id": "TW:1234", "period_end": "2020-09-30", "source_field": "營業收入",
    "raw_unit": "TWD_thousands", "reference_unit": "TWD_millions", "reference_value": "1.234",
    "report_basis": "cumulative", "statement_scope": "consolidated",
    "reference_url": "https://issuer.example/financial-report.pdf",
    "locator": "第 5 頁 1 至 9 月合併營收"
  }]
}
```

`reference_value` 用十進位字串。核對支援新台幣元、仟元、百萬元及元／股，用精確有理數按尺度比較；相符後仍保存 CSV 原始數值及尺度。綜合損益表接受 `cumulative` 或 `single_period`，使用者輸入應依同股票同期間的原始報表確認。比較不會將累計盈餘換算為單季值。核對時間進入該欄的可得時間，原始取得時間仍用於來源修訂排序；ledger 另存本地首次登錄時間。僅來源檔少一列不會撤回舊資料。抽檢檔是審閱紀錄，需與對應原件和私有稽核結果一起保存。

本輪四份 `normalized.json`、SQLite、研究版本與報告在 `local/private/m3-income-2026-11-19/`。完整重跑可從 repo 根目錄執行 `uv run --locked python local/private/m3-income-2026-11-19/replay.py local/private/m3-income-fresh`，目的地須為新目錄。四份原件各自重算 SHA256，展示節點上限為零時仍共保存 18 筆事實，四份 audit 均通過。獨立核對 12 欄中 11 欄精確相符、1 欄失配，另 6 欄保留原值待核。Linux／NAS 與其他期間留待重驗。


## 月營收與季報共用研究版本

以同一組 `--history-db`、`--output-root` 依序執行 `local.research`，每次的 `--input` 使用一份完整正規化檔，各自保留來源、觀察及本地首次登錄時間。先登錄兩市場自選股票的月營收，再依需要加入損益、資產負債、現金流。每次 `--symbols` 可選截至當時已有資料的股票。最後用已登錄的任一檔和 `--known-at` 可重播相同股票的較早截止。月營收 `official-monthly-twd-v1` 與舊原值版需分庫，兩市場同用這條尺度規則。季度來源逐資料集核對 adapter 與正規化版本。

同一份 CSV 可先不帶 `--review` 匯入，待完成核對，再將附覆核的檔案寫到新路徑並登錄。同來源、同取得時間的不同原件雜湊會拒收；覆核時間不能代為決定採用哪一份原件。較早截止仍可看到當時的未核對定義。沒有 `issuer_review` 的格子保留 `source_reported` 與已知的報表屬性，失配欄另保存 `value_mismatch`。尚在未來的覆核時間會拒絕登錄。

同一股票、期別、來源欄由數值改成明示缺值，較新截止會列入 `metadata.missing_values` 並移除該數值。較早截止仍有原值。新快照少一家公司或沒有該期資料時，先前觀察持續有效。來源明示整列缺值時可產生零值筆數的正規化檔；登錄這種修訂須有相同公司、期別、來源的先前數值。來源正式宣告撤回另存 `source_revision`。
