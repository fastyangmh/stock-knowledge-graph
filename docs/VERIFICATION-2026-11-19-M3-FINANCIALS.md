# M3 季度財報三表整合驗收

2026-11-19 在同一個乾淨的整合候選 `6b0f9a51e4e0bf58b82eb1acdcc1e37fdc522b24` 重播三組私有證據。損益與資產負債使用官方 CSV、取得紀錄與發行人逐欄核對；現金流使用兩家發行人的人工核對筆記。[逐來源核對與樣本擴充](../.scratch/m3-evidence-sources/issuer-reference-2026-11-19.md)

| 報表 | 樣本與審核結果 | 仍待核對 |
| --- | --- | --- |
| 損益 | 四個資料集、六家公司；22 筆研究事實逐欄等值，四個版本通過 audit。 | 上櫃金融與保險來源缺可用觀察，其他期間及產業仍待驗。[損益欄位與來源](QUARTERLY_STATEMENTS.md) |
| 資產負債 | 四個資料集、同六家公司；34 筆研究事實中有 22 筆逐欄等值，四個版本通過 audit。 | 其餘 12 筆保留為待核。上櫃金融與保險來源仍缺可用樣本。[資產負債範圍](QUARTERLY_BALANCE.md) |
| 現金流 | 上市與上櫃一般業各一家、各 6 筆；兩個版本均通過 audit，兩家公司均符合期末減期初等於淨變動。 | 中英版為同一發行人同一報表。另行發布的文件共比對 7 欄，1 欄零容差等值、6 欄仍有差額。官方原件封存及其他產業仍待驗。[現金流筆記與差額](QUARTERLY_CASHFLOW.md) |

## 重播與完整檢查

從候選工作樹執行下列命令。`evidence` 指向原本存放私有資料的 checkout；`out` 換成全新目的地。各腳本分別執行正規化、全新 SQLite ledger、展示節點上限零的研究版本與 bundle audit，八個政府 CSV 另重算原件雜湊。原件、筆記、逐欄數值與報告留存於私有目錄。

```bash
evidence=/path/to/original-checkout/local/private
out="$evidence/m3-combined-new"
uv run --locked python "$evidence/m3-income-issuer-expanded/replay.py" "$out/income"
uv run --locked python "$evidence/m3-balance-issuer-expanded/replay.py" "$out/balance"
uv run --locked python "$evidence/m3-cashflow-2026-11-19/reviewed/replay.py" "$out/cashflow"
TMPDIR=/private/tmp uv run --locked python -m local.check --frontend --report "$out/full-check.json"
```

這次三組重播均 exit 0。完整檢查在 macOS arm64、Python 3.11.11、uv 0.6.13、Node v22.16.0 執行。第一次執行受 loopback 權限限制；取得本機 HTTP 權限後重跑，559 pytest、310 subtests、55 Node tests、編譯、SQLite／JSON smoke 與圖譜驗證均通過，exit 0。私有報告為 `local/private/m3-combined-6b0f9a5/full-check.json`。本次未驗瀏覽器、Linux／NAS、正式財報更正或撤回，其他產業與期間也仍待取得可用原件。

後續修正、兩市場月營收與三表同庫的逐版重播，以及銀行附註新增的覆核，見[雙軸審查與混合研究驗收](VERIFICATION-2026-11-19-M3-FINANCIALS-REVIEW.md)。
