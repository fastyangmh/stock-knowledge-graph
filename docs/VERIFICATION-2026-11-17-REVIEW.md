# 最終審查、修復與重驗｜2026-11-17

審查找到 **3 個不同的產品缺陷及 1 項共用化建議**，已修復並完成候選重驗。Standards 的 3 項硬性 finding／1 項 heuristic 與 Spec 的 2 項 P1 有重疊，不能相加成 5 個缺陷。**09／10 維持 needs-info，M1 未全過**；行情來源定義與獨立參考仍不足。

## 固定範圍與候選

- 兩軸原始審查 diff：`8adf7f68fdbb4b221686bcf45c2c83b596902795...3834c19bce622dccc85a127119d77663c595a5c2`。
- 修復起點：整合分支 `dev/private-research-ready` 的 `0b21300349311695ac3f4cbadac65bdb3045a957`。
- 修復及實測候選：`ecd176b3069a62aaa98c7a641496af45b8c415f2`，分支 `task/pr-review-fixes`。完整 check 與圖譜／歷史／事件瀏覽器回歸記錄 `dirty=false`；其後只更新驗證文件。
- macOS Darwin arm64、Python 3.11.11、uv 0.6.13、Node v22.16.0；獨立工具環境 Playwright 1.65.2／Chromium 159.0.8154.6。
- `uv.lock` SHA256：`13259ea6ed35f56419de780e995041682df6ca535f3eac198a1c9616c1c9a865`，與公開 `data/` 均未修改。

下列兩軸保留原本順序、優先級及判斷。原始 review／reproduction 全文另存私有 `local/private/m1/review-fixes/reviews/`；審查本身只跑合成重現，與後續候選全套／真實驗收分開。

## Standards 原始結果

1. **P1 — `local/official_import.py:34`（原候選行號）：** `--output` 可等於 `--unit-evidence` 或其 reference；合成 CLI 重現兩者均遭覆寫。違反 [FINANCIAL_REVIEW](FINANCIAL_REVIEW.md) 的可重讀參考 bytes／raw bytes 不改寫要求。寫入前應拒絕所有輸入／證據路徑碰撞。
2. **P1 — `local/event_study.py:168–171`（原候選行號）：** `_definition` 忽略新單位版本／交易範圍／財務 scope/basis；兩版 12 次觸發被壓成 6 事件，錯併研究定義。違反 [MARKET_PRICES](MARKET_PRICES.md) 的正規化版本比較鍵及 [FINANCIAL_REVIEW](FINANCIAL_REVIEW.md) 的版本／scope/basis 分離要求。應共同定義完整比較鍵。
3. **P2 — `local/check.py:31`（原候選行號）：** 既存 `"private" not in p.parts` 在 `/private/tmp` 排除全部來源；公開報告介面重現 `passed=true, source_sha256={}`。違反 [HANDOFF §5.1](HANDOFF.md) 的來源雜湊保存要求；應只檢查 repo 相對路徑。
4. **啟發式：可能 Duplicated Code —** `collect_official` 與 `market_prices` 重複 HTTP 失敗回應 bounded capture，可能隨修改產生規則漂移。建議抽小型共用 helper；不是硬性違規。

## Spec 原始結果

1. **P1 — 不同研究定義仍被合併成同一事件：** 規格第 6 項要求所有讀者的 event 可比較鍵同步尊重版本，第 15 項要求首次保存事件保持原義。新增提醒證據已有 `normalization_version`、幣別及報表／交易範圍，但事件去重鍵只取舊行情欄位，財務定義未納入。同日合法提醒改 `trading_scope` 仍只有 2 個價量事件、各 `repeated_captures=1`；改財務 scope／版本仍只有 4 個營收事件。事件及分母消失，混合 cohort 可能錯誤排除。
2. **P1 — 正規化輸出能毀掉新增單位證據輸入：** 規格要求原始證據／研究產物私有及第 6 項保留轉換依據。`--output` 未排除 `--unit-evidence` 或 references；合成官方快照 CLI 成功卻覆寫 manifest，下次不能重驗。應在寫入前拒絕碰撞並檢查原始 bytes 保全，正常獨立輸出仍須通過。

Spec review 另明示 09 真實獨立同日參考／交易範圍及 10 gate 尚缺，屬已揭露待辦；沒有另列成新缺陷、scope creep 或 Linux blocker。

## 修復與 TDD 證據

沿用已核准的 `official_import.main`、公開 `evaluate → analyze`／`research → build`、`check.main` 報告 seam；測試沒有 mock 正規化、事件去重或寫檔。僅外部 HTTP、時間及 subprocess 邊界使用合成控制。TDD skill 與 tests／mocking 參考已讀。

| finding | 修復與可觀察行為 | red → green／回歸 |
| --- | --- | --- |
| Standards 1／Spec 2 | 寫入前拒絕 manifest、已驗證 reference、snapshot 目錄內、registry、universe／holdings 碰撞；全輸入 bytes 不變 | manifest 測試先 exit 1（未拋錯）後通過；reference／raw 分離 subtest 先 5 failures 後通過。財務單位＋adapter 25 tests／8 subtests，exit 0；既有正常輸出→research→audit 持續通過 |
| Standards 2／Spec 1 | 事件 identity 使用完整 market definition keys；財務與提醒共用 definition keys，包含版本、幣別、scope／basis。缺省／null 新欄位不加入舊 identity | 13 種新增欄位／alias 錯併先失敗；修後事件＋提醒 87 tests／64 subtests，exit 0。另驗 6 個舊事件及 definition 的既有 hash、同定義新 raw／觀察時間仍去重、跨 cohort 不錯排、真實 SQLite→audit→build 保留兩版共 8 個財務事件與獨立分母 |
| Standards 3 | `source_sha256` 依相對 ROOT 的 `local/private` 排除私有產物，不看絕對祖先 | `/private/.../checkout` 的公開報告測試先 exit 1（空 map），修後 exit 0；known source 的固定 SHA256 正確，secret artifact 不在報告。候選實跑 81 個來源逐檔校驗 |
| heuristic 4 | `http_evidence.capture_failure_response` 共用截取失敗回應；原 HTTPError、metadata、截斷及舊成功 pointer 語意保留 | 這是無行為變更重構，沒有宣稱新 red；既有 adapter／collection／market 73 tests／57 subtests 前後全通過 |

私有 red／green log 以 `import-*`、`event-definitions-*`、`check-provenance-red`、`check-and-event-green`、`http-*-refactor` 保存命令、exit code、當時 commit／dirty。首次 input 多 subtest 重現因首個 reference 被毀而連帶失敗，改為逐 case 還原 fixture 後取得上述 5 個獨立失敗；未拿連帶 checksum failure 冒充全部碰撞。追加 cohort 測試初版誤讀不存在的 `excluded_events.category`，已修正測試為公開 `rule_id`；此測試編寫錯誤不算產品 red。

## 同候選整合結果

| 實測 | 結果／exit code | 範圍 |
| --- | --- | --- |
| `local.check --frontend` | **0；490 pytest、246 subtests、55 Node** | compile、全部 Python、SQLite→JSON、validation、前端；未另跑 unittest |
| report provenance | 81 個非空 Python source hashes 逐檔相符；private scripts 不納入 | 候選在 `/private/tmp`，正面與負面條件均驗證 |
| 真實 `official_import` | 兩次 0；重讀原公司／月營收 CSV＋08 unit evidence | 先產生新 input，與08已核對輸入逐 bytes 相同，再交本輪 research |
| 兩市場 semantic research／alerts | 四次成功，每市場獨立新 ledger／兩個不可變 bundle，每版 8 facts | 真實固定模型；財務 `official-monthly-twd-v1`＋行情既有 source_reported |
| 首次／全快取 | 每市場首次 encoded=2、pairs=1、loader=1；重跑三者均 0 | 第二次 loader 若被呼叫即拒絕，非測試 encoder |
| bundle audit／compare／event | 每市場各三 CLI，全部 0 | 真實新 bundle；新 event identity 從完整定義生成 |
| 失敗保全 | 兩市場衍生 raw 故障均拒絕，全部舊 bundle／latest bytes 不變 | 故意破壞複本，不改原始 raw |
| financial_review | 四次 0 | 新正規化輸入按金額／百分比拆開；仍使用08獨立官方參考及原容差 |
| market_review | **兩次預期 2**；兩者 compared_fields=0 | TWSE definition_unverified=14；TPEx missing_reference=14；未改成成功 |
| 真實 HTTP 瀏覽器回歸 | 四命令 0；圖譜12／歷史9／事件7／facts9組，另只讀 Pages 通過 | 合成成功／故障案例、原 CDN；原生 fetch／WebCrypto |
| 真實研究三頁 | 0；兩市場六頁，桌機與390px手機通過，無 page error | 新研究與事件報告；私有 HTTP allowlist／Host／method 檢查 |

兩市場各一個營收事件，同定義重跑各抑制一次；每市場後續狀態為 6 個 insufficient_data、6 個 pending，沒有 observed。不同定義的額外分母僅在合成回歸驗證，沒有為真實驗收捏造定義、事件或未來值。

沿用已保存真實全檔而未重新下載；公司出表日 **2026-11-16**、月營收出表日 **2026-11-17**、期別 **2026-10**、行情交易日 **2026-11-17** 各自保留。舊 M1 文件把兩種出表日合寫為11/17是報告文字錯誤，本次勘誤不修改任何來源 bytes。取得時間、首次登錄與 bundle 保存時間不互相替代。

真實模型固定 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`；重讀02核驗 cache、CPU、torch單執行緒、離線載入。模型模組未改，完整四情境／四份 audit 引用 [3834c19 的實測](VERIFICATION-2026-11-17-M1.md)，本次只重跑兩市場首次／快取，不宣稱本次重跑「改一篇／改映射」。原02／05／06／07／08／09／10共609個非pycache證據檔逐 hash 前後一致。

三頁圖譜仍載入 Cytoscape 3.30.4 原 CDN，373734 bytes，SHA256 `1bb5340e549511e111b31e5684872c949ad33d40ea5dba0ad8e7d90c62c7b3b9`。未把私有資料送到 Pages，未推送、發布、排程或交易。

## 重跑與私有證據

本候選使用下列環境；loopback／browser 依正常權限流程執行，未放寬產品私有服務界線：

```bash
export TMPDIR=/private/tmp
export UV_CACHE_DIR=/private/tmp/skg-uv-cache
export UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv
export PATH=/private/tmp/skg-tools/node-v22.16.0-darwin-arm64/bin:$PATH
uv run --locked python -m local.check --frontend \
  --report local/private/m1/review-fixes/check-candidate-report.json
```

五份一次性私有腳本存 `local/private/m1/review-fixes/acceptance/`，先完整讀取原10腳本再複製改寫目的路徑。順序為 `renormalize.py → acceptance.py → reviews.py → browser.py`，另跑 `browser-regressions.py`。前3份以 `uv run --locked python -m local.private.m1.review-fixes.acceptance.<module>` 執行；browser 以 `/private/tmp/skg-browser-venv/bin/python` 執行，設定 `PLAYWRIGHT_BROWSERS_PATH=/private/tmp/skg-tools/playwright`。重跑須另選全新目的目錄，不覆寫本輪證據。

`run-record.py` 與各 `<step>.json/.log` 保存實際命令／退出碼；`acceptance/renormalize.json`、`acceptance/review-commands.json`、`acceptance/acceptance.json` 列明子 CLI；`original-evidence-before/after.json`、`verification-integrity.json` 保留完整性驗證。所有私有產物另複製回主 repo 同名 `local/private/m1/review-fixes/`，逐檔 hash 校驗；raw／DB／模型／報告／截圖不加入 Git。

| 私有檔案（相對 `local/private/m1/review-fixes/`） | SHA256 |
| --- | --- |
| `check-candidate-report.json` | `f7b1b61cb8f6f72eac722a2d99f1fcc4cb2d6e11c4db933424faf330fd1f3f4d` |
| `acceptance/acceptance.json` | `cfadee01419e987d1d4c1a3b78672d085bf84990dfe4af0a1483db5f2a9eae41` |
| `acceptance/browser.json` | `637a9405870eeefcfc94fa5e6f22b8f95ebdc1dc50040bbd99da0b020cbc9751` |
| `acceptance/browser-regressions.json` | `22989d5dba58da944ce164249f11159cbc5ab8c3eee6337db14273bd58e09d10` |
| `verification-integrity.json` | `5844e9865f236f5ab95d65af7f6d5536b16a6b6b15fe79d9ff49d74b17a8e623` |

## 未驗範圍與狀態

09 的交易範圍／幣別及 TPEx 同日獨立參考未補齊，10 仍受其 gate 限制。Linux／NAS、獨立復原、完整市場／修訂歷史、每日穩定、季度／籌碼／公告、研究品質與容量未驗，仍見 [backlog](DEVELOPMENT_BACKLOG.md)。工程與單次真實串接通過不代表金融有效性或全里程碑完成；名單暫緩、策略B未選定，公開／排程需另行核准。

文件連結、公開資料／lock 差異及 `git diff --check` 另檢查；文件提交不冒稱另一輪產品測試。原 [3834c19 整合驗證](VERIFICATION-2026-11-17-M1.md) 的測試數量、命令及 hash 保留為歷史。
