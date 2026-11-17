# 2026-11-17 月營收單位與獨立抽檢

本票基於 `0de76c1`，於 `task/pr-08` 實作；實作 Commit 見本檔的 Git history。
本輪採使用者允許的 macOS arm64、Python 3.11.11／uv 鎖定環境；Linux 未執行。
私有證據存於 `local/private/m1/08/`，不提交官方 bytes、SQLite 或研究報告。
公開 `data/` 未變更，未設定排程／公開／交易。

## 結果

| 範圍 | 實際結果 |
| --- | --- |
| TWSE 2330、2454；2026-10 | 2 筆金額零差、4 筆增率在有證據的 0.01 百分點內 |
| TPEx 6488、8069；2026-10 | 2 筆金額零差、4 筆增率在有證據的 0.01 百分點內 |
| 企業 IR 補充 | 2454 金額／YoY／MoM、6488 金額、8069 金額共 5 筆通過各自尺度容差 |
| 原 CSV → 新單位 → 獨立 ledger → research/alerts → audit | 每市場 6 個完整 facts，兩個 bundle audit 通過；原擷取可得時間皆保留 |
| 零容差差異 | 8 筆官方 HTML 增率及 4 筆企業 IR 精度差異均保留 exit 2 原報告，未冒充零差 |
| 本地完整檢查 | `local.check`：471 passed、197 subtests passed；compileall、示範 import/similarity/export/validate 通過 |

初次 sandbox 檢查 449 passed、10 failed、12 errors，全為禁止 loopback bind；
以正常 escalation 重跑完整檢查 exit 0。`check-report.json` 保留失敗，
`check-escalated.json` 保留成功。未變更前端，未執行本票瀏覽器驗收。
`local.check` 的既知私有程式雜湊範圍問題未在本票修改，另存本票來源檔 SHA256。

## 獨立來源與單位結論

被測來源為 05 保存的上市 CSV 與 07 保存的上櫃 CSV；本票重新讀取其保留 bytes，
不從已正規化的數值建立 reference。Reference 另由獨立下載的官方 HTML 或企業 IR
原始檔整理。官方 HTML 與 CSV 共用公司申報上游，這是獨立取得／解析的官方參考，
不是兩套獨立會計查核。企業 IR 提供另外的交叉證據。

| 證據 | 用途／定位 | SHA256 |
| --- | --- | --- |
| [TWSE 月營收彙總](https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_115_10_0.html) | 115年10月；2330/2454列；金額千元、各增率二位小數 | `033a41f996c9a9aad44d8b24da753e6c7abd39b06bc21dbe079fd13daa58dd59` |
| [TPEx 月營收彙總](https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_115_10_0.html) | 115年10月；6488/8069列；金額千元、各增率二位小數 | `951e9417279aaf5d4e2ce940c70af2ddf1a9ef2af71d941d1c838fd405fae77c` |
| [MediaTek 2026-10 PDF](https://www.mediatek.com/hubfs/MediaTek-Assets/Pdfs/Monthly%20Reports/2026/Monthly%20Sales%20Revenue%20October%2C%202026.pdf) | 第1頁 consolidated；NT$ million；公告日期11月10日 | `cab829891338c0dbd088949b52055c6a141e1fa72fc37e27581431a9a72d6885` |
| [環球晶財務資訊](https://www.sas-globalwafers.com/investor-page/financial-information/) | tablepress-159 的2026年10月；新台幣百萬元 | `6ff4c3bc57550cae2f8cedebc004a39ae6de14d11a083ff427a10ca3dd5a6b81` |
| [E Ink Monthly Sales](https://www.eink.com/investor/finance?bookmark=monthlysales) | 2026 Oct；Thousands of New Taiwan Dollars | `c24afc940d676d8dc0ca4cf39976db12de10de2d41142a6524289895506d6e3e` |

額外保存 2330／6488／8069 的 MOPS `ajax_t05st10_ifrs` 個別查詢，皆明示新台幣仟元，
SHA256 及帶完整參數的 URL 在各 `mops-<code>.html.json`。合併範圍採以下證據：
2454 PDF 明示合併子公司；6488 企業 Q2 公告明示 consolidated；8069 公司 Q2 合併財報
封面及核閱報告明示公司及子公司；2330 官方 Q3 損益彙總列有非控制權益歸屬數值，
支持存在合併子公司的判讀。後三者再配合 MOPS 本期「有子公司採合併、無子公司採個別」
規則，判讀本期為 consolidated。此為有定位證據的範圍核對，不表示完成季度財報適配或抽檢。

官方 CSV 出表日、HTML 出表日是 2026-11-17，資料期末是 2026-10-31；取得時間另記 UTC。
只有 MediaTek 公告明載11月10日發布日期；不把表格出表日或財報期間冒稱公告時間。
標準輸入 available_at 沿用 05／07 原始擷取時間；新版 ledger recorded_at 為本票實際登錄時間。

### 顯示精度與容差

官方彙總 HTML 將原始高精度增率截至兩位小數，八筆均可由該 HTML 保存的當月、上月、
去年同月整數金額驗算，差值絕對值小於 0.01 百分點。保留零容差失敗報告，再以只含
百分比列的檔案指定 `--absolute-tolerance 0.01`；四筆金額獨立報告維持 0。

企業公告有不同顯示精度，分次比較：聯發科 NT$ million 整數金額差 344,000 元、
環球晶整數百萬元差 123,000 元，均在半個百萬元（500,000 元）內；
聯發科 YoY/MoM 二位小數分別採 0.005 百分點；元太仟元整數金額差 0。
該容差只用於列明的金額或百分比組，沒有整批共用大金額容差。

### 未成功取得的來源

Python HTTPS 對台積電 IR HTML/PDF 回 403，舊 `mops.twse.com.tw/nas/...` 回404；未繞過封鎖。
改用另行核對的現行官方 `mopsov.twse.com.tw` 查詢及上市損益彙總來源。
Python 憑證鏈無法驗證 E Ink；使用系統 curl 信任庫正常驗證 TLS 後取得原始頁與 PDF，
沒有關閉憑證驗證。完整失敗分類另存 `acquisition-limitations.json`。

## 工程契約與 TDD

公共 seams：official_import CLI → research → bundle audit、financial_review CLI/review、
提醒 evaluate、event build/analyze；已依本輪核准的 seams 測試。

紅燈先重現：未知幣別相同金額被當 equal、scope alias 衝突被忽略、月期別缺 scope
被當 equal、不同 normalization_version 被比較、缺少 unit-evidence CLI、版本混入舊
ledger、事件將 unknown currency 當成已確認、完整財務事件遺失 source_url、
營收趨勢混用不同尺度版本。逐項最小修改後綠燈。

`official-monthly-twd-v1` 只套用 manifest 明列來源／股票／月份；固定 raw CSV hash，
保留原值、原單位、倍率、參考 hash 及原始時間。沒有證據的資料維持 source_reported；
舊 bundle 可 audit，新的尺度不可共用舊 ledger。aliases 衝突於 normalized validation、
facts audit、review 與事件讀取拒絕；原始逐筆證據不當分組版本。

## 重跑

```bash
TMPDIR=/private/tmp UV_CACHE_DIR=/private/tmp/skg-uv-cache \
UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv \
uv run --locked python -m local.check --report local/private/m1/08/check-escalated.json

# 需保有上述私有 bytes、05/07 snapshot 和 registry；不重新下載、不公開資料。
uv run --locked python -m local.private.m1.08.acceptance
uv run --locked python -m local.private.m1.08.corporate_review
```

驗收腳本中的絕對工作目錄是本輪環境定位，搬移時須改為本機已校驗的私有路徑。
正式入口及 manifest 格式見[財務抽檢](FINANCIAL_REVIEW.md)。下載腳本只作本票一次性
參考核對，未加入排程器或對外資料適配器。

未涵蓋季度／年度金額抽檢、單季／累計季報適配、完整月度歷史、每日穩定性、Linux/NAS、
真實投資有效性或正式發布。此票完成不代表整個 P1-02 的所有財務類型已驗收。
