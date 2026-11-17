# TWSE 公司／月營收真實全檔驗證（ticket 05）

日期：2026-11-17。實作及最終產品測試 Commit：`1082584b0801b967e68f35d43d4183f0c2a8329d`，
整合基準包含 `465481e`；完整 check 報告 `dirty=false`。本次完成 ticket 05 的 TWSE
公司／月營收來源與私有研究鏈，金額尺度抽檢仍由 ticket 08 負責，不關閉整個 P1-01 或 M1。

## 實作與 TDD

collector 保留原始 bytes、HTTP status／Content-Type／實際 URL、取得時間與完整 hash；
新增全檔欄名、列數、日期／月份分布與所選股票覆蓋。`--symbols` 使選中數值在整批
成功指標更新前驗證。來源／日期異常及 HTTP 失敗保存結構化報告與有界回應；超大及
Content-Length 短讀拒絕並將完整 hash 設為 null。既有 bytes `fetch_csv` seam 保持相容。

核准 seam 是 collector／import／research／audit CLI。新增測試以外部 urllib 邊界
提供合成回應，其餘使用真實臨時檔案、SQLite、研究 bundle 與 audit。逐步 red→green：

- 第一輪因 collector CLI 不接受 argv、manifest 缺 HTTP evidence 而失敗，再補實作。
- 第二來源403原本沒有失敗報告（預期1、實際0），新增私有失敗證據後通過。
- HTML／超限缺分類與有界 bytes 先失敗，再補保存與 CLI 大小參數。
- 全檔輪廓／兩檔 CLI 鏈先因未支援 `--symbols` 失敗，再完成 profile 與選中數值閘門。
- 未選中股票的未來日期、混出表日／月份原本未拒絕；新增全檔日期契約後通過。
- 缺股票原本只回泛用錯誤；新增 source_coverage 與 missing 清單。
- 合成 Content-Length 短讀原本可成功；補回應完整性檢查後拒絕。

最終新增9項測試；官方來源相關31項通過。原有403不重試、429最多三次、快照
checksum 與舊成功 manifest 保留等測試仍通過。全測的 pytest／subtests 不視為真實
金融資料驗收，真實鏈另列如下。

## 實際環境與結果

環境為 Darwin 27.2.0／arm64、CPython 3.11.11、uv 0.6.13、pytest 9.2.0。
本票未變依賴或 lock；`uv.lock` SHA256 為
`13259ea6ed35f56419de780e995041682df6ca535f3eac198a1c9616c1c9a865`。
不是 Linux 目標環境結案，也沒有測瀏覽器或真實模型。

| 執行 | exit code | 證據／結果 |
| --- | --- | --- |
| 初次官方 collector（沙盒） | 1 | DNS解析失敗，`live-initial/retrieval-failure-*.json` 保存 network_error |
| 同來源正常 require_escalated | 0 | 兩個官方資源均200；未更換 URL／繞過封鎖 |
| 第一次完整 check（沙盒） | 1 | 396 passed；10 failed＋12 errors 均為本機 loopback bind 權限 |
| 完整 check 正常 require_escalated | 0 | 先418 passed；加入短讀回歸及整合01後，最終421 passed、163 subtests passed |
| 最終 collector（1082584） | 0 | 兩個來源全檔、完整長度、兩檔覆蓋及選中值通過 |
| 最終 official_import | 0 | 兩檔、6筆財務指標；金額仍 source_reported |
| 最終 research，analysis none | 0 | 真實 SQLite、2 graphs、6 financial_metric_nodes |
| 最終 bundle_audit | 0 | valid=1、invalid=0、latest_valid=true |
| 真實已存資料＋合成第二來源403 | 預期拋 HTTPError | 成功manifest／latest／graph.db不變，舊bundle仍audit valid |

## 官方全檔證據

沿用 registry 已啟用、已審核的
[公司資料集](https://data.gov.tw/dataset/18419) 與
[月營收資料集](https://data.gov.tw/dataset/18420)，沒有啟用 TPEx 或新增資源。
當次 CSV 的所有欄名與原始日期字串完整列於私有 manifest；必需欄位均存在。
公司必需 `出表日期／公司代號／公司名稱`，營收另需 `資料年月／營業收入-當月營收`。

| 項目 | 公司 | 月營收 |
| --- | --- | --- |
| resource | `https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv` | `https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv` |
| HTTP／Content-Type | 200／text/csv | 200／text/csv |
| 取得時間 UTC | 2026-11-17T06:09:23+00:00 | 2026-11-17T06:09:26+00:00 |
| bytes（與 Content-Length 一致） | 675725 | 207911 |
| 全檔列數／欄數 | 1099／33 | 1091／14 |
| 全檔出表日 | 2026-11-16：1099列 | 2026-11-17：1091列 |
| 資料月份 | 不適用 | 2026-10：1091列 |
| 指定股票 | 2330、2454 均存在 | 2330、2454 均存在 |

公司 SHA256：`22e14a9414f445440e770f8759c70131e0efc0dc20d8066fd40021fb5e20facc`。
營收 SHA256：`0e6a2cbfb78befd2c77415e57aadfdf7acc1038a48e9d815bedb113730b622f2`。

公司出表日早於取得日，是合法且保留的差異；月份不是取得日。當次每份表單一出表日、
營收單一月份，據此採保守匯入契約，混雜先停止等待來源契約核對。這不表示官方保證
永遠單一月份，也不把選中數值檢查宣稱為所有1,091列的金額正確性抽檢。

## 重跑與私有保存

```bash
export TMPDIR=/private/tmp
export UV_CACHE_DIR=/private/tmp/skg-uv-cache
export UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv
uv run --locked python -m local.check \
  --report local/private/m1/05/check.json
uv run --locked python -m local.collect_official --symbols 2330 2454 \
  --output-dir local/private/m1/05/snapshots
uv run --locked python -m local.official_import \
  --snapshot-dir local/private/m1/05/snapshots --symbols 2330 2454 \
  --as-of YYYY-MM-DD --output local/private/m1/05/normalized.json
uv run --locked python -m local.research \
  --input local/private/m1/05/normalized.json --symbols 2330 2454 --analysis none \
  --history-db local/private/m1/05/history.db --output-root local/private/m1/05/runs
uv run --locked python -m local.bundle_audit --root local/private/m1/05/runs
```

`YYYY-MM-DD` 必須取實際取得時間的台北日期，不可拿本次日期當歷史查詢。
實際執行使用共享venv的相同 Python；精確 CLI argv、退出碼與log hash保存在
`acceptance-1082584/execution.json`。正常外網及本機loopback權限是執行前提。

證據已複製到主repo不追蹤的 `local/private/m1/05/`：

- `live-1082584/`：最終不可變全檔、成功manifest、合成第二來源失敗證據。
- `acceptance-1082584/`：正規化輸入、SQLite、不可變研究bundle、三個CLI log與執行摘要。
- `acceptance-1082584/partial-failure.json`：真實已存資料＋合成403的保留檢查。
- `check-1082584.json`：最終clean Commit全測，SHA256
  `17c8d27da6a3ba295ee05fee9434774e3b041fdf3799951a68c05c476c495f2a`。
- 最終成功 manifest SHA256：`cd55a8fda4013ce91f0b8c39fa6c765713bb1c574a572c5b37a8653396136890`。
- 最終 audit stdout SHA256：`7ad2420dd31eb516c3944092a0dd22630ec9c46d3deaff5f679cbd315f467791`。

原始 CSV、公司資料、財務數值、DB及原始報告均不提交；公開 `data/` 未改寫。
本票無剩餘來源連線阻礙；單位尺度／獨立抽檢、TPEx、行情、真實模型、Linux、
瀏覽器、每日穩定性及公開發布均不由本票宣告完成。
