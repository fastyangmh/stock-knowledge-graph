# 私有研究手動更新

每次工作指定一個市場、一組股票、一份帶原始證據的市場日曆、一個交易日與一個 job ID。使用新的私有作業根目錄，兩市場的行情庫、財務 ledger、已稽核版本及指標各自獨立。同一市場的標準研究讀者使用 `<root>/<market>/runs`。

## 準備私有設定

以下為上市合成格式範例。路徑使用絕對路徑，將兩個 SHA256 佔位字換為已保存收據核對的雜湊，存為私有的 `plan.json`。研究股票須在公司、營收與當日行情都有涵蓋。`as_of` 為公司、營收快照的台北取得日；`trade_date` 為要核對的行情交易日。可從私有報告分別查到出表日期與營收所屬月份。

```json
{
  "market": "twse",
  "symbols": ["1000"],
  "trade_date": "2020-01-02",
  "as_of": "2020-01-02",
  "calendar": "/private/research/calendar/calendar.json",
  "financial_dir": "/private/research/official",
  "financial_manifest_sha256": "<retrieval_manifest.json 的 SHA256>",
  "price_file": "/private/research/quotes/daily.csv",
  "price_sha256": "<官方原始 CSV 的 SHA256>",
  "expected_revenue_month": "2019-12",
  "min_free_bytes": 104857600,
  "analysis": "none"
}
```

- `calendar` 採用本地保存的 `market-calendar-1` 日曆及其相對原件。已確認休市時跳過取得、行情及研究。若明示供應的原件在該休市日確實有行情，會報衝突。未知或矛盾的日曆均保留原成功指標。[日曆格式](CALENDAR_COVERAGE.md)
- `financial_dir` 內須有原 `retrieval_manifest.json` 及其指向的原始公司與月營收 CSV。程式會逐一重算檔案雜湊、日期分布與選股覆蓋。若採經核對的月營收尺度，加入 `unit_evidence` 絕對路徑與 `unit_evidence_sha256`，並保留證據引用的附件。不同正規化定義沿用獨立 ledger，作業時使用另一個私有根目錄。
- 上市預設使用專案 registry。上櫃指定 `"market": "tpex"` 並以 `registry` 指向只啟用上櫃公司及月營收的既有審核登記。程式核對資料集 ID、資源網址、格式及授權欄位。
- 若當次要取得公司與月營收，把 `financial_dir` 和 `financial_manifest_sha256` 換為 `"download_financial": true`。若要下載當日行情，把 `price_file` 和 `price_sha256` 換為 `"download_prices": true`。兩組可獨立選擇。預設重播本地原件。已完整驗過的公司來源可用於同 job 補抓營收。新取得時點若跨過原選定取得日，請按實際取得日另開工作。
- `expected_revenue_month` 為可選的 YYYY-MM 期別檢查。未指定時列實際期別。指定後，若只看到其他期別，會列出實際月份並以非零結束。`min_free_bytes` 為可選的可用空間下限，預設 0，各次報告均記錄檔案系統總量及剩餘 bytes。
- `analysis` 預設 `none`，亦可指定 `lexical` 或 `semantic`。語意模式需提供固定模型的 40 位 `revision`。離線演練使用既有模型快取及 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。每個新 job 從獨立候選目錄啟動；同 job 已生成的候選可重驗。每個完整候選都含價量與月營收兩組提醒。

## 執行與重試

```bash
uv run --locked python -m local.manual_update \
  --root local/private/manual-operations --plan local/private/plan.json \
  --job twse-20200102 --through research

uv run --locked python -m local.manual_update \
  --root local/private/manual-operations --plan local/private/plan.json \
  --job twse-20200102

uv run --locked python -m local.bundle_audit --root local/private/manual-operations/twse/runs
```

`--through` 可選 `preflight`、`calendar`、`acquire`、`normalize`、`prices`、`research`、`audit`，預設到 `audit`。較早階段會再檢查依賴的收據。停在 `research` 時，候選留在 `jobs/<job>/candidate`。最後一次執行會稽核候選的金融輸入、指定行情觀察與兩類提醒；存好報告後才原子更新 `runs/latest.json`。

CLI 印出 `jobs/<job>/report.json` 路徑，每次紀錄另外留在 `jobs/<job>/attempts/`。exit 0 表示達到請求階段或已確認休市。exit 2 表示工作輸入或執行階段失敗，可查 `stage`、`stages`、來源與實際日期、`kind`、`reason`。路徑無法建立或其他程序正持鎖時，請依終端錯誤處理後重試。

用相同計畫與 job ID 重試可修復缺檔、沿用已核對來源及其觀察時間。同一原件在同一工作不會重複新增行情。修改計畫或需要新觀察時開新 job。候選若落後另一個已提升版本，須另開工作驗證目前資料。失敗仍可能留下已取得原件、已登錄行情或候選，正式讀者以 `runs/latest.json` 的版本與雜湊為準。行程若在寫入報告和更新指標之間中斷，使用同一 job 重試並核對指標。

取得來源會先檢查選股的值及覆蓋。當月報含錯值時，同 job 重試可保留已核對的公司原件，只重抓月報。已保存的候選若損壞，該次研究階段會失敗，作業目錄保留被拒絕的候選；同 job 可另建並稽核新候選。提升標記取代 latest 之前，歷史與事件讀者只使用已成功的版本。[兩市場故障與重試驗收](VERIFICATION-2026-11-19-M5-REVIEW.md)

操作範圍為本機手動私有研究。實際來源與驗證界線見 [OPS-01 票](../.scratch/m5-private-operations/issues/04-manual-update.md)。
