# 官方新聞索引與季度公司產業分類

`local.news_industry` 讀取已保存的官方收據及原件。產業文件可以從個股私有研究圖重新定位到季表。兩份新聞來源提供全市場索引，研究報告的 `quality.news_indexes` 保存截止時各來源最後一次觀察到的完整清單。新聞標題出現公司名稱或代號並不會建立股票關聯。

## 各來源適用範圍

四份資料集的目錄均列政府資料開放授權條款第 1 版。每份研究來源保留提供機關、目錄、資源、署名、條款及 `permitted_use`。本輪的公開展示均待審，registry 僅開放本機收據模式。[授權條款](https://data.gov.tw/license)

| 已保存的來源 | 索引或公司分類 | 全文、摘要與 Embedding |
| --- | --- | --- |
| [證交所新聞 11546](https://data.gov.tw/dataset/11546) | 756 列。以原始連結識別文章，標題、日期、CSV 列號可查。750 個相異標題 | 連結目的地全文及其衍生用途待審。索引僅存原題與定位欄，沒有送入文字模型 |
| [金管會新聞稿 6040](https://data.gov.tw/dataset/6040) | 591 個 RSS item。以 GUID 識別，另存連結、原題、來源 GMT 發布時間、item 序位及 description 有無。589 個相異標題，12 篇缺 description | 完整 RSS 原件私存。description 的 HTML、連結正文與第三方引文均未進研究模型。自動摘要、Embedding 與公開顯示待審 |
| [上市季度產業 20756](https://data.gov.tw/dataset/20756) | 2026 Q3 公司代號、當期名稱、產業文字、出表日及期末日。1,076 家、與主檔配對的 32 種分類 | 產業文件以公開資料欄位生成署名敘述，供私有研究與選用的文字比較。沒有採用文章全文或財務數值 |
| [上櫃季度產業 20757](https://data.gov.tw/dataset/20757) | 同季度 898 家、與主檔配對的 28 種分類。市場與來源分開 | 採用相同的公司分類欄位與私有衍生用途。本輪實際研究使用 `analysis=none` |

原件欄位為「出表日期、年度、季別、公司代號、公司名稱、產業別」及六個公司財務欄。研究文件的 `relation_basis=source_reported_industry`、`source_column=產業別`、`row_number` 和 `raw_sha256` 可核回原列。公司沒有季度列時保留缺口。整表在正規化及 SQLite ledger 保留，`local.research --symbols` 才限制個股輸出。其他研究來源的公司名稱及產業代碼優先，季表的名稱仍留在當期文件。模型或研究者推測的供應鏈、關聯公司及獨立產業指數均不在原表分類中。

TWSE 新聞僅有發布日期。RSS 另有含時區的發布時間。兩者皆使用實際取得時間與 ledger 首次登錄時間決定何時可重播。季表的期末及出表日各自保留，`published_at` 相容欄使用取得時間並透過 `availability_basis` 註明來源原始公告時刻未知。股票文件的穩定 ID 取自來源、代號與期末，索引的穩定鍵為來源與連結或 GUID。清單中消失的文章可查回先前版本，正式撤回仍需來源明示通知。

## 重跑已保存的原件

以下從 repository 根目錄執行，示例使用本機私有目錄。收據的 `received_at`、HTTP 狀態、URL、byte count、SHA256 及實際原件需相符。後續擷取須存入另一個目錄，保留先前原件與收據。相同輸出可重跑，變動的原件須使用新輸出路徑。

```bash
set -e
raw=local/private/source-review-2026-11-19/news-official
out=local/private/m3/07-news-industry/verified
for dataset in 20756 20757 11546 6040
do
  uv run --locked python -m local.news_industry --dataset "$dataset" \
    --manifest "$raw/manifest.json" --output "$out/$dataset.json"
done

uv run --locked python -m local.research --input "$out/20756.json" \
  --symbols 2330 2317 --history-db "$out/ledger.db" --output-root "$out/runs"
for dataset in 20757 11546 6040
do
  uv run --locked python -m local.research --input "$out/$dataset.json" \
    --symbols 2330 2317 6488 8299 --history-db "$out/ledger.db" --output-root "$out/runs"
done
uv run --locked python -m local.bundle_audit --root "$out/runs"
```

第一次建立 ledger 時，先登錄所選股票的已保存觀察。無股票的新聞快照只供同一 ledger 的研究查詢。研究 report 可依 `quality.news_indexes[].snapshot_sha256` 連回 `quality.snapshots` 的來源、登錄時間及收據。audit 會從當期索引及來源 metadata 重算 normalized SHA256，並核對截止時的來源版本。歷史截止可用 `local.research --known-at` 指定先前 report 的 `known_at`。同來源同時收到不同內容時，CLI 留下錯誤，舊的成功指標可繼續使用。

## 2026-11-19 私有驗收

四份原件以另一支程式逐列重讀。兩份新聞的識別、標題、連結、日期及原件序位與索引一致。兩份季表和公司主檔以公司代號交叉比對；在本次樣本各市場的每個產業代碼都只對到一個中文季表分類。上市主檔另外有 23 家沒有季表列。上櫃有一個代號在兩份原件的公司全名不同，已分別保存並以該檔實跑主檔與季表混合研究，兩版 audit 均通過。不同全名的原因及歷史身分尚待獨立查證。

同一 SQLite ledger 保存四份原件的版本證據。測試重播四個首次登錄後的截止並核對來源、新聞條目、研究事實，以及股票圖節點和邊。每次產圖的時間會改變。私有證據在 `local/private/m3/07-news-industry/verified/`，含 `verify.py`、`verification.json`、`mixed-verification.json`、`check-report.json`。本機以 `uv run --locked python "$out/verify.py"` 可在四個初始版本上重新跑逐列比對、截止重播及 audit。原始 SHA256、下載時間及 URL 留在 `news-official/manifest.json`。

候選 `e2064c7`（整合開發分支 `21373fd`）在 macOS arm64、Python 3.11.11、Node 22.16.0 以 `uv run --locked python -m local.check --frontend` 完成。616 個 Python 測試、384 個 subtests、55 個 Node 測試及合成管線通過，exit 0。首次在受限環境執行時 loopback 被拒絕，已在一般權限重驗。本票另實測欄位漂移、重複鍵、空值、跨主機連結、原件遭修改、同時衝突、舊版重播及篡改索引的拒絕。

## 待補來源

- 兩份季表和公司主檔屬同源交叉比對。其他期別、跨來源的獨立產業分類、產業總量、EPS 或公司金額的尺度未驗證。本票僅採用上述公司分類。
- 經濟部新聞與兩個工業生產資源在先前核對時回 HTTP 403。待可用的官方資源或有權保存的副本，重新核對欄位、期間與用途。[經濟部新聞](https://data.gov.tw/dataset/10861) · [工業生產](https://data.gov.tw/dataset/6607) · [電子零組件業](https://data.gov.tw/dataset/146531)
- Yahoo RSS 入口先前回 HTTP 404，實際 feed 可用性與條款適用範圍待核。第三方文章全文、語意衍生、付費財經庫及來源撤回通知需各自驗收。[逐來源查證與條款](SOURCE_REVIEW_2026-11-16.md)
