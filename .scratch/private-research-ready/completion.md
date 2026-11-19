# 私有研究交付清單

依原 backlog 的完成條件記錄功能、實測範圍及下一個可驗證的結果。M6 的完成條件見[里程碑與相依](README.md)。日期為 2026-11-19。

| M | 原待辦 | 可查核的進度 | 下一個驗收結果 |
| --- | --- | --- | --- |
| M1 | [P0-01](../../docs/DEVELOPMENT_BACKLOG.md#p0-01目標環境依賴與真實模型) | [已在指定 macOS 驗證鎖定環境與固定模型](../../docs/VERIFICATION-2026-11-17-M1.md) | Linux 移轉時另驗 |
| M1 | [P0-02](../../docs/DEVELOPMENT_BACKLOG.md#p0-02真實前端與cdn驗收) | [原 CDN、三頁瀏覽器、WebCrypto 與兩市場真實研究版本已驗](../../docs/VERIFICATION-2026-11-17-REVIEW.md) | 相關程式變更後重驗受影響路徑 |
| M1 | [P1-01](../../docs/DEVELOPMENT_BACKLOG.md#p1-01正式來源全檔驗收最高資料優先) | [兩市場公司、月營收及行情全檔已取得](../../docs/VERIFICATION-2026-11-17-M1.md) | 核定範圍限於記錄的來源與交易日 |
| M1 | [P1-02](../../docs/DEVELOPMENT_BACKLOG.md#p1-02單位公告與人工抽檢) | 月營收已驗，行情正式抽檢兩市場各比較 0 欄、exit 2。[後續官方來源研究](research-market-gaps-2026-11-18.md) | 取得符合原快照版本的逐欄定義與同範圍獨立參考，再重驗 09／10 |
| M2 | [P2-01](../../docs/DEVELOPMENT_BACKLOG.md#p2-01研究事實與展示裁剪分離優先) | [已保存未裁剪事實並驗證新舊讀者與分母](../../docs/VERIFICATION-2026-11-17-REVIEW.md) | 持續用既有首次保存口徑做相容性回歸 |
| M2 | [P2-02](../../docs/DEVELOPMENT_BACKLOG.md#p2-02交易日完整性) | [逐日、序號及兩市場真實驗收完成](../../docs/VERIFICATION-2026-11-19-CALENDAR-COVERAGE.md) | 整批審查提出未來截止、應到時間及同時首存衝突，待修復重驗 |
| M2 | [P2-03](../../docs/DEVELOPMENT_BACKLOG.md#p2-03公司行為與價格基準) | 現有提醒揭露未還原價格，事件拒絕不同價格基準 | 核對兩市場公司行為來源與適用範圍，對可比與未知情形留下案例 |
| M2 | [P2-04](../../docs/DEVELOPMENT_BACKLOG.md#p2-04修訂與撤回) | 歷史 ledger 保存快照及本地登錄時間，現行 replay 依 upsert | 明示更正／撤回證據、截止重建、舊版 migration 與 audit |
| M3 | [P1-03](../../docs/DEVELOPMENT_BACKLOG.md#p1-03季度財報) | 現有官方適配及單位實測涵蓋月營收 | 季度三表、產業差異、時間與單位逐源抽檢 |
| M3 | [P1-04](../../docs/DEVELOPMENT_BACKLOG.md#p1-04籌碼資料) | 有籌碼數值的保存與重播契約 | 核對官方法人／融資融券來源，驗證方向、尺度、修訂與冪等 |
| M3 | [P1-05](../../docs/DEVELOPMENT_BACKLOG.md#p1-05重大訊息新聞與產業證據) | 已支援文件、股票對應與文字語意 | 每來源確認使用條件，驗證版本、重複、撤回與報表變更 |
| M4 | [P3-01](../../docs/DEVELOPMENT_BACKLOG.md#p3-01提醒品質與可解釋性) | 六條提醒可算或顯示不足，已有合成驗證 | 按規則核對真實歷史分母及人工案例，揭露誤報或無法判讀的原因 |
| M4 | [P4A-01](../../docs/DEVELOPMENT_BACKLOG.md#p4a-01事件後描述統計擴充) | 已保存兩市場各一個事件的第 1 筆真實後續觀察，5／20 筆仍不足。[後續行情與原件](source-samples-2026-11-19.md) | 在可確認的資料範圍檢查右設限、分組、重疊及選樣偏誤 |
| M5 | [P0-03](../../docs/DEVELOPMENT_BACKLOG.md#p0-03復原與備份) | 現有一致性備份工具涵蓋 SQLite | 連同原始證據、設定和 bundle 在新位置還原，另待有 Linux／NAS 及獨立儲存實測 |
| M5 | [P2-05](../../docs/DEVELOPMENT_BACKLOG.md#p2-05容量量測與ann評估) | 有固定模型快取及精確 Top-K 工作預算 | 固定資料尺度，量測 CPU、記憶體、輸出與瀏覽器成本後決定索引需求 |
| M5 | [P2-06](../../docs/DEVELOPMENT_BACKLOG.md#p2-06儲存預算與封存) | 已有部分讀取與工作量上限 | 盤點各類實際路徑、增長與超限，驗證封存 dry-run、還原及事件引用 |
| M5 | [OPS-01](../../docs/DEVELOPMENT_BACKLOG.md#ops-01完整手動更新流程) | 個別 CLI 與私有一次性整合程序已運作 | 可重跑的分階段手動入口，驗部分失敗、健康報告及舊 pointer 保全 |
| M6 | M1～M5 | 待上述必要的功能及證據齊備 | 同候選版本用真實來源重建、抽檢、復原及 audit，逐項對照完成條件 |

## 後續規格與可執行票

| 批次 | 原待辦與驗收入口 |
| --- | --- |
| [M2 價格基準與歷史](../m2-price-history/spec.md) | P2-03 原始行情比較、P2-04 依截止重播明示更正或撤回 |
| [M3 新來源](../m3-evidence-sources/spec.md) | P1-03 季度三表、P1-04 法人及融資融券、P1-05 公告與新聞／產業來源，按來源、權利及產業逐票驗收 |
| [M4 研究品質](../m4-research-quality/spec.md) | P3-01 六條提醒的實際分母與人工案例、P4A-01 事件觀察期與樣本重疊 |
| [M5 私有維運](../m5-private-operations/spec.md) | P0-03 實際復原、P2-05 固定負載、P2-06 儲存與封存、OPS-01 手動更新與重試 |
| [M6 總驗收](../m6-private-acceptance/spec.md) | 同一候選、真實來源、獨立參考、整組還原及逐項簽核 |

[REL-01](../../docs/DEVELOPMENT_BACKLOG.md#rel-01正式公開)、[REL-02](../../docs/DEVELOPMENT_BACKLOG.md#rel-02每日排程) 分別待公開授權及排程決定。[HOLD-01](../../docs/DEVELOPMENT_BACKLOG.md#hold-01研究名單暫緩不阻塞) 名單暫緩，[HOLD-02](../../docs/DEVELOPMENT_BACKLOG.md#hold-02策略回測交易未選定) 策略 B 未選定。
