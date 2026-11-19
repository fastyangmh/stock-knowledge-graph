# 私有研究交付清單

依原 backlog 的完成條件記錄功能、實測範圍及下一個可驗證的結果。M6 的完成條件見[里程碑與相依](README.md)。日期為 2026-11-19。

| M | 原待辦 | 可查核的進度 | 下一個驗收結果 |
| --- | --- | --- | --- |
| M1 | [P0-01](../../docs/DEVELOPMENT_BACKLOG.md#p0-01目標環境依賴與真實模型) | [已在指定 macOS 驗證鎖定環境與固定模型](../../docs/VERIFICATION-2026-11-17-M1.md) | Linux 移轉時另驗 |
| M1 | [P0-02](../../docs/DEVELOPMENT_BACKLOG.md#p0-02真實前端與cdn驗收) | [原 CDN、三頁瀏覽器、WebCrypto 與兩市場真實研究版本已驗](../../docs/VERIFICATION-2026-11-17-REVIEW.md) | 相關程式變更後重驗受影響路徑 |
| M1 | [P1-01](../../docs/DEVELOPMENT_BACKLOG.md#p1-01正式來源全檔驗收最高資料優先) | [兩市場公司、月營收及行情全檔已取得](../../docs/VERIFICATION-2026-11-17-M1.md) | 核定範圍限於記錄的來源與交易日 |
| M1 | [P1-02](../../docs/DEVELOPMENT_BACKLOG.md#p1-02單位公告與人工抽檢) | 月營收已驗，行情正式抽檢兩市場各比較 0 欄、exit 2。[後續官方來源研究](research-market-gaps-2026-11-18.md) | 取得符合原快照版本的逐欄定義與同範圍獨立參考，再重驗 09／10 |
| M2 | [P2-01](../../docs/DEVELOPMENT_BACKLOG.md#p2-01研究事實與展示裁剪分離優先) | [已保存未裁剪事實並驗證新舊讀者與分母](../../docs/VERIFICATION-2026-11-17-REVIEW.md) | 持續用既有首次保存口徑做相容性回歸 |
| M2 | [P2-02](../../docs/DEVELOPMENT_BACKLOG.md#p2-02交易日完整性) | [逐日、序號及兩市場真實驗收完成](../../docs/VERIFICATION-2026-11-19-CALENDAR-COVERAGE.md) | [521 pytest／282 subtests／55 Node，修復後 16 次真實 CLI 重播](../../docs/VERIFICATION-2026-11-19-CALENDAR-REVIEW.md)。本輪完成，日曆期間外仍顯示未知 |
| M2 | [P2-03](../../docs/DEVELOPMENT_BACKLOG.md#p2-03公司行為與價格基準) | [兩市場真實區間與六類來源](../../docs/PRICE_ACTION_REVIEW.md)已核對，個別除權息證據與未知期間可讀 | 兩市場原始價格警告及跨幣別拒比已驗。較長歷史與其他公司行為的完整涵蓋仍未知。[修復驗收](../../docs/VERIFICATION-2026-11-19-M2-HISTORY-REVIEW.md) |
| M2 | [P2-04](../../docs/DEVELOPMENT_BACKLOG.md#p2-04修訂與撤回) | 已驗舊庫重播與[兩份正式重大訊息更正](../m2-price-history/official-document-corrections-2026-11-19.md)，已通過[原生行情通知雙軸審查](../../docs/VERIFICATION-2026-11-19-MARKET-NOTICE-REVIEW.md)，合成案例涵蓋撤回及重新發布 | 正式撤回、財務與籌碼的真實更正待驗。[行情 SQLite 通知的獨立票](../m2-market-revisions/issues/01-market-notices.md) |
| M3 | [P1-03](../../docs/DEVELOPMENT_BACKLOG.md#p1-03季度財報) | [兩市場六家公司季報抽樣](../m3-evidence-sources/issuer-reference-2026-11-19.md)已核對 22 筆損益與 23 筆資產負債，另 11 筆資產負債待核 | [三表與兩市場月營收已同庫](../../docs/VERIFICATION-2026-11-19-M3-FINANCIALS-REVIEW.md)。現金流私有筆記兩家 12 筆可重播，正式原件封存、獨立金額差額與其他產業仍待驗 |
| M3 | [P1-04](../../docs/DEVELOPMENT_BACKLOG.md#p1-04籌碼資料) | [已依上櫃原始 CSV 重建兩股 44 筆法人與 34 筆融資融券；新版 audit 會偵測改值與刪格](../../docs/VERIFICATION-2026-11-19-M3-SOURCE-REVIEW.md) | 待同日同範圍獨立抽檢、數量尺度與上市來源證據 |
| M3 | [P1-05](../../docs/DEVELOPMENT_BACKLOG.md#p1-05重大訊息新聞與產業證據) | [兩市場共 148 筆正式公告、跨兩股關聯、兩組更正、兩份新聞索引與產業季表已重播](../../docs/VERIFICATION-2026-11-19-M3-SOURCE-REVIEW.md) | 需可定位的真實撤回、第三方新聞權利及獨立產業分類 |
| M4 | [P3-01](../../docs/DEVELOPMENT_BACKLOG.md#p3-01提醒品質與可解釋性) | [四檔股票 32 個規則／期間組合已對照來源](../m4-research-quality/issues/01-alert-quality.md)，私有 CLI 的 72 筆保存與逐例核算相符 | 補 20 筆同來源較早行情、相鄰營收月份及 P1-02 行情定義，核對長窗與修訂等真實案例 |
| M4 | [P4A-01](../../docs/DEVELOPMENT_BACKLOG.md#p4a-01事件後描述統計擴充) | [兩市場三代事件報告及六規則雙軸重驗](../../docs/VERIFICATION-2026-11-19-M4-REVIEW.md)，各驗一個首次事件、兩次重複保存與兩個第 1 筆後續值 | [已驗上櫃同股不同事件重疊](../../docs/VERIFICATION-2026-11-19-EVENT-COHORTS.md#11-月-19-日盤後的同股事件重疊)。補第 5／20 筆行情、到期的 1／3／6 月營收及正式公司行為案例 |
| M5 | [P0-03](../../docs/DEVELOPMENT_BACKLOG.md#p0-03復原與備份) | [v2 還原 37 個版本、28 個來源快照，兩市場舊 v1 揭露月報 registry 缺件](../../docs/VERIFICATION-2026-11-19-M5-REVIEW.md) | Linux／NAS 與獨立儲存實測 |
| M5 | [P2-05](../../docs/DEVELOPMENT_BACKLOG.md#p2-05容量量測與ann評估) | [固定模型的 32／128／512 文件已量測冷熱快取、CPU、RSS、精確邊及九次 Chromium](../../docs/VERIFICATION-2026-11-19-M5-REVIEW.md) | 更大尺度或新主機時重測 |
| M5 | [P2-06](../../docs/DEVELOPMENT_BACKLOG.md#p2-06儲存預算與封存) | [完成分類、增長、唯讀盤點；單一 run 作根、組合封存與還原均已重驗](../../docs/VERIFICATION-2026-11-19-M5-REVIEW.md) | 實際刪除需保留期授權 |
| M5 | [OPS-01](../../docs/DEVELOPMENT_BACKLOG.md#ops-01完整手動更新流程) | [兩市場手動原件、來源重試、候選與作業報告故障均已驗證](../../docs/VERIFICATION-2026-11-19-M5-REVIEW.md) | 持續到件與實際線上穩定性待驗 |
| M6 | M1～M5 | [同候選重建 37 版，從還原原件重做 28 個輸入與兩市場更新，桌機／手機及 21 個原 ID 已核對](../../docs/VERIFICATION-2026-11-19-M6.md) | `needs-info`。補行情同範圍獨立抽檢、缺少的來源與長期樣本、Linux／NAS 獨立復原 |

## 後續規格與可執行票

| 批次 | 原待辦與驗收入口 |
| --- | --- |
| [M2 價格基準與歷史](../m2-price-history/spec.md) | P2-03 原始行情比較、P2-04 依截止重播明示更正或撤回 |
| [M3 新來源](../m3-evidence-sources/spec.md) | P1-03 季度三表、P1-04 法人及融資融券、P1-05 公告與新聞／產業來源，按來源、權利及產業逐票驗收 |
| [M4 研究品質](../m4-research-quality/spec.md) | P3-01 六條提醒的實際分母與人工案例、P4A-01 事件觀察期與樣本重疊 |
| [M5 私有維運](../m5-private-operations/spec.md) | P0-03 實際復原、P2-05 固定負載、P2-06 儲存與封存、OPS-01 手動更新與重試 |
| [M6 總驗收](../m6-private-acceptance/spec.md) | 同一候選、真實來源、獨立參考、整組還原及逐項簽核 |

[REL-01](../../docs/DEVELOPMENT_BACKLOG.md#rel-01正式公開)、[REL-02](../../docs/DEVELOPMENT_BACKLOG.md#rel-02每日排程) 分別待公開授權及排程決定。[HOLD-01](../../docs/DEVELOPMENT_BACKLOG.md#hold-01研究名單暫緩不阻塞) 名單暫緩，[HOLD-02](../../docs/DEVELOPMENT_BACKLOG.md#hold-02策略回測交易未選定) 策略 B 未選定。

## 外部證據與恢復條件

| 待辦 | 可使驗收繼續的具體輸入 |
| --- | --- |
| M1 P1-02／09、10 | 2026-11-17 的 TWSE 11549、TPEx 11371 原快照各七欄的適用交易型態、幣別、尺度與版本，及同一交易日、同一股票、同範圍的獨立原始參考。上市選股 2330／2454，上櫃 6488／8069。後到資料須證明可對應原先取得時點。[已查來源與逐欄限制](research-market-gaps-2026-11-18.md) |
| P2-03 | 較長比較期間內，需有可定位市場、股票與生效日的除權息、分割／併股及減資原件。逐類保留來源、取得時間和來源涵蓋的商品與日期，並備妥區間兩端的原始收盤價、幣別、尺度及交易範圍，以核對價格基準是否可比。[公司行為來源與價格基準](../../docs/PRICE_ACTION_REVIEW.md) |
| P2-04 | 指明受影響的來源、股票、交易日／期別、原件版本及更正／撤回動作的正式通知，連同可定位的前版原件。兩份同源格式、下載失敗、普通日檔缺列或只更正另一財報附註均不足。[已找到的更正及受影響項目](../m2-price-history/official-document-corrections-2026-11-19.md) |
| P1-03 | 可合法私有封存並校驗原件雜湊的現金流正式報表、可核至相同精度的獨立參考，以及非空的上櫃金融／保險產業樣本。可提供本地檔案位置及用途依據；台積公司特定 SEC 6-K 下載曾因缺少該筆檔案明確授權而遭自動核准審查拒絕。[已閱原表、抽檢差額與 SEC 附件定位](../../docs/QUARTERLY_CASHFLOW.md) |
| P1-04 | 上市法人／信用交易的逐來源私有保存依據、帶日期且可證明同交易範圍的原件、欄位單位，以及上櫃同日兩檔可獨立核對的原始值。上市融資券的兩種官方表示有 6,725 格空白／零的差異；上櫃原檔內部加總僅能核算術。[法人](../m3-evidence-sources/issues/04-institutional.md) · [融資融券](../m3-evidence-sources/issues/05-margin.md) |
| P1-05 | 可指明公告前版、撤回事由與來源時點的原件；網站准許使用第三方新聞的明確範圍；可依同季、公司與分類版本核對的另一份正式證據。[公告](../m3-evidence-sources/issues/06-announcements.md) · [新聞與產業](../m3-evidence-sources/issues/07-news-industry.md) |
| P3-01／P4A-01 | 保留原始來源日期與實際首次保存時間的連續行情、月營收及後續研究版本，以實測 20 筆量基準、跨月提醒及 5／20 筆、1／3／6 曆月事件結果。可用合成案例驗工程邊界，真正右設限樣本依日期繼續觀察。[已保存案例與分母](../m4-research-quality/spec.md) |
| P0-03／M6 | 可供測試的 Linux／NAS 目標與獨立儲存位置，用有權存放金融資料的備份在新目的地實際完整還原及 audit。可提供主機別名、允許的目錄、檔案系統及備份位置，憑證留在使用者自己的環境。[使用者已指定的 macOS 與後續移轉條件](../m5-private-operations/issues/02-restore.md) |
