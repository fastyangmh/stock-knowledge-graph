# 研究歷史、版本比較與整包稽核

[文件中心](README.md) · [私有研究](PRIVATE_RESEARCH.md) · [研究提醒](RESEARCH_ALERTS.md)

## 目的與界線

比較 `local.research` **已儲存**的兩個研究版本，查看哪些股票／展示節點改變，以及價量、月營收提醒如何變化。不重建未保存的市場歷史，不計算投資績效，也不將兩類提醒合併成評分。TW50與009816名單仍是獨立的暫緩項目，並非此功能的先決條件。

本機版本目錄使用 `local/private/research-runs/<32位run-id>/`，包含 `report.json`、`graph.db`、`data/`，以及啟用提醒時的 `alerts.json`。新版報告另保存 `configuration`（計算模式、模型revision、Top-K、門檻、窗口及裁剪版本）。舊版未保存的設定標記為「unknown」，不得推測相同。

## 先稽核，不修復也不刪除

```bash
uv run --locked python -m local.bundle_audit --root local/private/research-runs
```

稽核報告檢查：run-ID、完成狀態、選定股票覆蓋、截止時間、SQLite原始bytes SHA256、manifest、圖檔端點／數量／checksum、獨立提醒與圖中提醒一致，以及提醒統計。SQLite只作bytes雜湊，不執行資料庫內的SQL。上一個版本不完整時，下一次研究執行也會拒絕重用快取。

- 預設最多 **50個研究版本**、全部bundle檔案合計 **256 MiB**；透過 `--max-runs`／`--max-mib` 明確調整。
- 過量停止，不默默忽略較早版本。未知檔案、symlink、非法路徑、檔案讀取中變動皆拒絕。
- 毀損版本標記為invalid，不提供其圖譜／比較；可用的其他版本保留。
- `latest.json`不見或失效時不自行挑另一版冒充最新；`.research-stage-*`只列出殘留數量，不自動清理。
- 稽核exit **0**表示本次檔案一致性檢查通過；exit **1**表示有invalid版本或latest無效。格式／預算錯誤也會失敗。

**這不是數位簽章。** 舊版report沒有外部可信錨點，latest只與本地pointer互相比對；有能力重寫所有檔案和雜湊的人仍可偽造一致內容。此處也不證明來源真實性、公開權利或金融數值正確。讀取防護與鎖不是對惡意本機管理員的完整檔案系統沙箱。

## 本機歷史瀏覽器

```bash
uv run --locked python -m local.research_archive --root local/private/research-runs --port 8766
```

同一台主機開啟 `http://127.0.0.1:8766/`。此頁可：

1. 列出版本的資料可得截止、產生時間、股票數與品質警告；檔案不完整的版本不提供連結。
2. 查看某一版的圖譜（`index.html?run=<id>`），仍保留原有股票池、搜尋、節點詳情及兩類提醒。
3. 選取較早／較晚可得截止的兩版，比較股票範圍、展示圖譜及提醒狀態。
4. 展開每條提醒查看前後兩版的公式、門檻、期別與來源證據。

只監聽loopback；同機其他使用者可能存取，**沒有帳號驗證**，請勿轉發到公開網路。只服務已驗證的記憶體快照、必要網站資產與摘要，不開放SQLite、原始CSV、完整report或目錄列舉。預覽JSON與網站資產有64 MiB序列化大小預算，解析前先拒絕過量JSON；不是整個Python程序的峰值記憶體保證。更新研究資料後須重啟以讀到新版本。

`history.html`雖在Repository，但公開Pages不提供本地歷史API，直接瀏覽只會提示需啟動本機工具；這不會將研究版本上傳到網站。沒有新增遠端後端、排程、Git Push或自動清理。

## 如何判斷提醒變化

| 狀態 | 含義 |
| --- | --- |
| activated | 兩版定義相同且皆可評估，由未達門檻變成達到門檻 |
| no_longer_triggered | 同定義下本次未再達門檻；**不是風險解除** |
| still_triggered / still_not_triggered | 仍達／仍未達門檻；數值或證據仍可能變動 |
| became_unavailable / still_unavailable | 資料不足或不可比較，不算提醒消失 |
| became_evaluable | 先前無法評估，現在可以；不是已證實的新訊號 |
| definition_changed | 相關規則參數、來源／尺度或公式改變，不直接作狀態轉變解讀 |
| definition_unknown | 舊價格提醒沒有保存市場／價格尺度／未還原基準，無法證實可比較 |
| not_computed | 至少一版未執行提醒，不等於沒有異常 |
| added_coverage / removed_coverage | 股票研究範圍改變，不算啟動或解除訊號 |

僅與該規則相關的設定會阻擋比較：例如改成交量倍數，不會把月營收提醒一併標成不可比。新價量證據保存market／price_unit／price_basis；既有alerts-1.0報告仍可讀，未保存的舊欄位不回填。

圖譜比較只針對**匯出的展示子圖**。節點可能因時間窗、裁剪名額、Top-K或模型改變而消失，不等於原始文件已刪除或公司關係已失效。每類差異詳情預設最多列50筆，保留完整差異計數和truncated標記；不以空畫面隱藏超量。

## 命令列比較

從稽核報告取得兩個實際run-ID後，取代以下佔位值：

```bash
uv run --locked python -m local.research_compare \
  --root local/private/research-runs \
  --before BEFORE_RUN_ID --after AFTER_RUN_ID
```

只讀取已驗證版本，輸出JSON到stdout；不覆寫來源。較早版本的known_at晚於較後版本時拒絕；同一截止時間可比較不同版本設定。同版自比不會捏造新事件。若需要保存輸出，請自行導向 `local/private/`，勿提交私有資料到公開Issue。
