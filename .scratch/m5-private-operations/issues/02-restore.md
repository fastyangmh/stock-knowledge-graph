# 02 · 可攜的私有研究封存與還原

**Parent:** [P0-03](../../../docs/DEVELOPMENT_BACKLOG.md#p0-03復原與備份) · [規格](../spec.md)

**What to build:** 從一致的 SQLite、來源證據、研究版本、設定及引用清單，還原至全新私有位置並立即 audit。

**Blocked by:** 無，02 可用明示的成套輸入開始

**Status:** needs-info（本機與工程已驗，Linux／NAS 和獨立媒體待實機）

- [x] 重用 SQLite online backup 取得含已提交 WAL 的一致 DB。其餘證據以包含路徑、類別、大小、hash 的 manifest 封存；複製期間來源或 pointer 改變即拒絕完成。
- [x] 驗證錯 hash、缺檔、路徑逃逸、中途失敗與已有還原目標；舊版 SQLite 備份入口持續可用。成功還原需重讀原始證據、研究歷史、事件引用並完成 bundle audit。
- [x] 在 macOS 的獨立目的目錄對合成與已有真實研究各做一次 create/verify/restore；記錄設備、來源一致性範圍及驗證命令。Linux／NAS 與獨立媒體實測另列，取得環境才完成 P0-03。

## 2026-11-19 實測

候選 `c5d63d2` 已納入開發分支 `3fa9107` 的行情及季報讀者。macOS arm64、Python 3.11.11、uv 0.6.13、Node 22.16.0。本機來源、備份與各還原目錄位於同一個 APFS 裝置。操作命令與輸入契約見[維運手冊](../../../docs/OPERATIONS.md#私有研究整組備份與還原)。

| 既有真實研究 | 每市場有效版本 | 還原檔案 TWSE／TPEx | 核對引用 TWSE／TPEx | 同截止的事件重播 |
| --- | ---: | ---: | ---: | --- |
| 含前兩版的連續歷史 | 3 | 44／44 | 46／46 | 每市場 1 份，內容相同 |
| 兩交易日重新建庫的歷史 | 2 | 34／33 | 36／35 | 每市場 1 份，內容相同 |

- 四組分別執行 `local.portable_backup create/verify/restore`、`local.bundle_audit` 和 `local.event_study`，均 exit 0。每市場核對公司、月營收、單位原件、兩份價格 CSV 及單位檔引用的 HTML／PDF（TWSE 4 份、TPEx 5 份）。四組原始來源檔前後 SHA256 相同，財務及行情庫按各版歷史截止實際重讀。盤點與還原分別沿用 [01](01-storage.md) 的引用分類及[既有 SQLite 入口](../../../local/backup.py)。
- 在各市場複本破壞正規化輸入、重用既有還原目錄，命令均 exit 1。另在兩市場三版歷史還原過程，確認暫存檔已寫入 17 bytes 後以 SIGTERM 終止程序（returncode -15）。只留下未提升的私有暫存，目的地未出現，原指標 bytes 相同且原目錄再次 audit 成功。未對真實主資料做中斷或破壞。
- 合成 CLI 覆蓋持續開啟中的 WAL 交易、未變更指標的中途 I/O 失敗、複製中變動的 WAL／指標、事件來源雜湊、單位證明及收據的原件、檔案類別、路徑逃逸、symlink／hard link、缺檔、競爭建立空目錄與成功開啟還原資料。舊的 SQLite 備份測試持續通過。[測試](../../../local/tests/test_portable_backup.py)
- 完整 `uv run --locked python -m local.check --frontend` 在允許 loopback 的當前環境 exit 0，615 pytest、344 subtests、55 Node tests。先前沙盒內的 HTTP 測試因埠綁定失敗，保留兩份私有輸出。此次未另跑瀏覽器。實際參數、雜湊、故障、重播輸出與完整報告保存於 `local/private/m5-restore-2026-11-19/`。
- 待取得 Linux／NAS、獨立儲存媒體後，將封存搬到該裝置並在新位置重跑 verify／restore／audit；目前同機證據未涵蓋獨立裝置、實際斷電、異地故障或檔案系統不支援排他 rename 時的成功復原。

## 雙軸重驗

已在 macOS 完成 37 版／28 份原始輸入組合的還原及八類適配器重建。另重驗舊 v1、51 版與截斷失敗收據，Linux／NAS 和獨立媒體仍待實機。[修復、操作與私有證據](../../../docs/VERIFICATION-2026-11-19-M5-REVIEW.md)
