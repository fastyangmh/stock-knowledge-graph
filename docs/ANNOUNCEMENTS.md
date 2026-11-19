# 上市與上櫃每日重大訊息

`local.announcement_import` 將已保存的 MOPS CSV 與擷取收據轉成私有研究輸入。支援 18415 上市及 18418 上櫃，限四碼公司代號。政府目錄列出九欄、提供機關與 OGDL-1.0。每份輸入帶來源網址、顯名、授權、原件 SHA256、bytes、擷取時間及邏輯列號。[上市資料集](https://data.gov.tw/dataset/18415) · [上櫃資料集](https://data.gov.tw/dataset/18418) · [授權條款](https://data.gov.tw/license)

| 資料／用途 | 本專案操作範圍 |
| --- | --- |
| 兩份 CSV | 私有保留原件與九欄定位。主旨、說明為純文字，允許帶來源的本地索引、摘錄及私人語意分析。此次重播採 `--analysis none`。 |
| 內文所引文章、網址、圖影音及附件 | CSV 內文字按原欄保存。外部資源的全文、摘要、下載及 embedding 另依各來源審核。介面只連至已審核的資料集或授權頁。 |
| 發行人網站、法院頁 | 人工核對事件或公告，不匯入這些頁面的原文、圖片或附件。 |
| 公開展示 | 維持示範資料。正式公告、摘錄及衍生輸出須另依專案公開程序核准。 |

## 匯入與回讀

```bash
uv run --locked python -m local.announcement_import \
  --dataset 18418 --manifest local/private/capture/manifest.json \
  --output local/private/announcements/day.json

uv run --locked python -m local.research \
  --input local/private/announcements/day.json --symbols 5310 6881 \
  --history-db local/private/announcements/history.db \
  --output-root local/private/announcements/runs --analysis none

uv run --locked python -m local.bundle_audit --root local/private/announcements/runs
```

收據與 `<dataset>.response` 同目錄，沿用已審核擷取的 URL、MIME、狀態、時間、長度與 SHA256。先檢查整檔，再輸出全檔或用 `--record 31` 選一筆。表頭算第 1 筆，引號中的換行屬同筆。不同內容需新的輸出路徑。資料集、公司代號、發言日與台北時間到秒構成文件身分。完全相同的重複列共用節點，保留各列號。同一身分有不同說明時拒絕整檔，跨發布者同標題保留各自來源。發言時間、出表日、事實發生日、收據取得時間與本地首次登錄各自保存；未來的事實發生日可出現在已發布公告。研究依本地登錄截止回讀。

### 已核對的多股連結

預設僅連結公司代號欄。另加 `--record N --review local/private/link.json` 可以明示關聯公司。一筆公告可同時出現在兩張股票圖；每個圖上的文件 ID 相同。以下合成範例的 `raw_sha256` 需換成該原件實際校驗值。

```json
{"raw_sha256":"<原件 SHA256>","record":2,"links":[
  {"name":"乙公司","ticker":"2000","evidence":"乙公司 普通股","company_record":3}
]}
```

`evidence` 必須逐字出現在選定公告的主旨或說明，並含公司名。`company_record` 指向同一已核驗檔案明列該公司名稱及代號的列；若引文已同時列明名稱與代號可省略。人工核對公司在引文中的身分及關係。未確認的簡稱、母子公司、新聞內容或語意相似不自動建立關聯。

### 明示更正、撤回及重發

要重播文件的各版，先在專用 ledger 匯入原公告的單筆輸入。全檔入口則把每次來源發言視為單獨公告；已將新通知作為獨立公告的全檔，不能直接當作該通知的原版。兩條程序各用一個 ledger。人工核對原公告與通知，將 `--record` 指向通知、`--parent` 指向上一版 normalized JSON、`--review` 指向下列私有 JSON。其格式只接受一項明示動作。

```json
{"raw_sha256":"<通知原件 SHA256>","record":3,"revision":{
  "action":"correct","target_document_id":"<原公告 document_id>",
  "target_snapshot_sha256":"<上一版 registered_snapshot.sha256>",
  "evidence":"<公告明示更正的原文片段>"
}}
```

動作接受 `correct`、`withdraw`、`republish`。核對有效時間採該次發言時刻的通知才適用此入口。有另一指定生效時刻須依既有通知契約個別處理。修訂沿用上一版已驗股票範圍，保留本次發言自己的原件定位。研究初次啟用時帶 `--enable-source-revisions`；舊版回讀帶原報告的 `--known-at`。通知關鍵字僅能協助找候選，不適合作為自動更正／撤回判斷。[既有修訂與遷移契約](PRIVATE_RESEARCH.md#來源明示更正撤回與重新發布)

## 2026-11-19 驗收

候選 `4f36d7e` 包含開發分支 `3fa9107`。在 macOS arm64 以兩份 11/19 擷取的原件重播 11/18 發言。分市場建立全檔研究，逐列將 SQLite 的主旨、說明、公司關聯對回原始 CSV。上市 94 篇／68 家，上櫃 54 篇／45 家；重送仍是原快照。兩市場全檔共四版，另有以下九版經 audit。

- 上市第 81 列明示標的證券名稱，第 3 列定位其代號與名稱。以人工 review 把同一公告連結 2323 與 6442，在兩張圖讀回同一 ID。另讀第 95 列 3045 的訴訟公告，對照法院自行發布的案號、法院、被告、裁判結果與判決日期。[臺北高等行政法院新聞稿](https://www.judicial.gov.tw/tw/cp-1888-1651861-21e8a-1.html)
- 上櫃 5310 第 31 → 32 列、6881 第 37 → 46 列各經原版、更正、原截止、重送四版。每組均從新建 ledger 回讀原主旨及修訂主旨，原報告 hash 不變。6881 另以發行人官網獨立比對發布日及兩個主旨；5310 的配對已人工讀回原檔，尚缺發行人網站交叉驗證。[潤德重大訊息](https://rd.ruentex.com.tw/zh/financial-information/press-center)
- `uv run --locked python -m local.check --frontend` exit 0，613 pytest、378 subtests、55 Node tests。合成案例含跨市場同文、惡意文字、明示多股連結、同時歧義、收據損壞、明示撤回與原截止重讀。本次未另執行瀏覽器。兩份單日原件未驗證正式撤回、逐日連續涵蓋、外部轉載及新聞權利；明示更正限上述上櫃兩組。

真實重播程式在主工作區 `local/private/m3-announcements-2026-11-19/replay.py`。從候選工作目錄以 `PYTHONPATH=. uv run --locked python /path/to/replay.py new-run-name` 建立新的私有輸出。正式結果在同一私有目錄的 `replay-4f36d7e/result.json`、`check-report.json`（該次重播子目錄）及 `reference-review.json`（上層）。[本地票單](../.scratch/m3-evidence-sources/issues/06-announcements.md)

## 收據與歷史重播

重新取得相同發言保留原收據時間及已審的跨股連結，明示撤回仍可按截止排除。缺公司主檔時，股票節點會附資料集、提供者、授權、署名與原件列欄；跨股公司可定位至同檔經人工核對的公司代號列。[M3 04～07 雙軸審查與組合重播](VERIFICATION-2026-11-19-M3-SOURCE-REVIEW.md)
