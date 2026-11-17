# M1 整合驗證與證據索引｜2026-11-17

**M1 尚未全過；09／10 保持 needs-info。** 本輪在使用者指定的目前 macOS 完成可獨立執行的工程、真實快照與瀏覽器整合。行情交易範圍與同日獨立參考的缺口未被工程通過取代。Linux／NAS 移轉未驗，但不是本輪 blocker。

## 固定候選與環境

- 實測候選 `3834c19bce622dccc85a127119d77663c595a5c2`，分支 `task/pr-10`，已確認包含 integration 基準；完整check與瀏覽器回歸記錄 `dirty=false`。
- macOS Darwin arm64、Python 3.11.11、uv 0.6.13、pytest 9.2.0、Node v22.16.0。Playwright 1.65.2／Chromium 159.0.8154.6為獨立既有工具環境，不改lock。
- `uv.lock` SHA256：`13259ea6ed35f56419de780e995041682df6ca535f3eac198a1c9616c1c9a865`。
- 真實模型 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`；重驗02已保存的11個Hub provenance檔，CPU、torch單執行緒、離線載入。沒有改成浮動revision。
- 財務使用 `official-monthly-twd-v1`；行情保留舊 `source_reported`／未知幣別及交易範圍，未以合成 `market-units-2.0` 冒充真實確認。
- 本票沒有產品修復，因此沒有虛構red→green。已讀TDD及tests/mocking參考，沿用已核准CLI→bundle→HTTP seam。後續最終code-review、必要修復、重驗與推送尚由整合流程處理；本文件結果只屬上述候選。

## 同候選實際結果

| 檢查 | exit code／結果 | 資料性質 |
| --- | --- | --- |
| `local.check --frontend` | 0；482 pytest、220 subtests、55 Node；compile、SQLite→JSON、release validation全過 | 合成、真實臨時SQLite／loopback；未另跑unittest |
| `local.model_check --offline` | 0；首次／全快取／改一篇／改映射四情境及4份audit全過 | 真實固定模型＋合成多語文本 |
| 兩市場重讀原CSV→official_import | 兩次0；新輸出與08核對輸入逐bytes相同 | 已保存真實公司／月營收及單位證據 |
| 兩市場research／alerts | 4次成功；每市場全新ledger、兩個不可變成功bundle，每版8 facts | 真實財務新版＋原始行情＋真實模型 |
| 同輸入重跑 | 每市場首次encoded=2、pairs=1、loader=1；重跑encoded=0、pairs=0、loader=0，graph_reused=true | 第二次loader如被呼叫即拒絕；非測試encoder |
| bundle_audit／research_compare／event_study CLI | 每市場各3命令，全部0 | 兩版可比較，兩類提醒獨立 |
| 故障保全 | 兩市場衍生快照故意損壞，research拒絕checksum mismatch；全部舊bundle及latest bytes不變 | 故障注入；不宣稱官方回傳壞資料 |
| financial_review | 4次0；每市場2筆金額零容差，4筆增率0.01百分點容差 | 08保存的獨立官方HTML參考；未重新製造reference |
| market_review | **兩次2**；TWSE definition_unverified=14，TPEx missing_reference=14；兩者compared_fields=0 | 真實參考缺口；不是成功驗收 |
| 圖譜／歷史／事件／facts瀏覽器回歸 | 4個命令皆0；12／9／7／9組通過；只讀Pages另通過 | 合成資料、真實HTTP／原CDN，成功路徑原生fetch |
| 真實來源兩市場三頁 | 0；六個頁面各桌機與390px手機、allowlist、原生fetch通過，無page errors | 本票四份真實研究bundle及事件報告 |

pytest及subtests分列，不與unittest重複相加。真實來源三頁驗收與合成故障案例分開，不將合成提醒誤稱為真實事件。初次私有browser腳本誤以單股分類數量斷言兩股畫面，exit 1；修正為兩股後同產品候選exit 0，失敗stderr仍保留。另一次編輯腳本語法錯誤未改到腳本，重跑仍失敗；修正後才記成功。這兩項不是產品修復或TDD紅燈。

### 真實資料與時間界線

沿用05／06／07保存的全檔下載證據，沒有把本輪重讀冒稱新的官方下載。TWSE使用2330／2454，TPEx使用6488／8069；公司出表日2026-11-16、月營收出表日2026-11-17、營收期別2026-10、行情交易日2026-11-17。資料取得、來源可得、ledger首次登錄與bundle保存時間各自保留。08參考逐市場核對，不把上市結論自動套到上櫃。

兩市場各保存一個營收事件；同輸入重跑的重複期別各抑制一次。每市場12個後續觀察結果為6個`insufficient_data`及6個`pending`，沒有`observed`結果。沒有補造未來行情／營收、沒有把1／5／20筆改稱交易日、沒有績效或金融有效性宣稱。未裁剪事實已串接真實來源，但單日行情與單期營收不等於完整市場歷史。

圖譜實際載入 `https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js`：HTTP200、373734 bytes、SHA256 `1bb5340e549511e111b31e5684872c949ad33d40ea5dba0ad8e7d90c62c7b3b9`；版本3.30.4、localhost secure context及原生WebCrypto可用。歷史頁兩版可比較；事件頁明示event-study-2.0。DB／raw／完整facts等非allowlist路徑404、錯Host403、寫入method501。沒有把真實資料送到Pages；Pages只讀原公開示範。

## 上游證據與未關閉gate

| 票／backlog | 可定位證據 | 本輪狀態 |
| --- | --- | --- |
| 01／02，P0-01 | [鎖定環境](VERIFICATION-2026-11-17-LOCKED-ENVIRONMENT.md)、[真實模型](VERIFICATION-2026-11-17-REAL-MODEL.md)及本輪重驗 | 使用者指定macOS範圍完成；Linux移轉另驗 |
| 03／04，P0-02 | [圖譜](VERIFICATION-2026-11-17-GRAPH-LIVE.md)、[歷史／事件](VERIFICATION-2026-11-17-HISTORY-EVENT-HTTP.md)及本輪全套真HTTP重驗 | 本輪範圍完成 |
| 05／06／07，P1-01 | [公司／營收](VERIFICATION-2026-11-17-OFFICIAL-FINANCIAL.md)、[TWSE](VERIFICATION-2026-11-17-TWSE-MARKET.md)、[TPEx](VERIFICATION-2026-11-17-TPEX-MARKET.md) | 真實來源全檔與本輪串接完成；不代表多日穩定 |
| 08，P1-02財務子範圍 | [財務單位與獨立抽檢](VERIFICATION-2026-11-17-FINANCIAL-UNITS.md)及本輪4次review | 月營收完成；季度／年度未涵蓋 |
| 09，P1-02行情子範圍 | [行情單位缺口](VERIFICATION-2026-11-17-MARKET-UNITS.md)及本輪exit2報告 | **needs-info**；TWSE bulk範圍未證明、TPEx同日獨立reference未到 |
| 10，M1 | 本索引與[票10](../.scratch/private-research-ready/issues/10-m1-acceptance.md) | 工程整合已驗，依賴09 gate，**needs-info** |
| 11／12，P2-01 | [未裁剪事實](VERIFICATION-2026-11-17-UNPRUNED-FACTS.md)、[事件讀者](VERIFICATION-2026-11-17-EVENT-FACTS.md)及本輪真實串接 | 工程完成；不關閉M2其他項或P4A-01 |

09仍需可定位的bulk交易範圍／幣別證據與TPEx同日、同範圍的獨立參考。數字相同、同來源的另一表示或前日參考不能解決該缺口。未知尺度保持原樣，未重新擷取相同數字來冒稱已確認。

其餘M2～M6、季度／籌碼／公告適配、權威日曆、公司行為、完整撤回／雙時間歷史、真實研究品質、大規模量測、NAS獨立復原仍未完成。名單暫緩、策略B未選定、公開／排程仍須各自核准。

## 重跑與私有證據

在候選worktree採以下既有環境，正常授權的loopback／browser網路權限未改安全政策：

```bash
export TMPDIR=/private/tmp
export UV_CACHE_DIR=/private/tmp/skg-uv-cache
export UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv
export PATH=/private/tmp/skg-tools/node-v22.16.0-darwin-arm64/bin:$PATH
uv run --locked python -m local.check --frontend \
  --report local/private/m1/10/check-candidate.json
uv run --locked python -m local.model_check --offline \
  --model-cache /Users/austin_yang/Desktop/stock-knowledge-graph/local/private/m1/02/model-cache \
  --output local/private/m1/10/model-four-scenarios
```

完整私有一次性程序為`acceptance.py`（原快照hash→新ledger/runs→audit/compare/event→故障保全）、`renormalize.py`、`reviews.py`、`browser.py`及`browser-regressions.py`，均存`local/private/m1/10/`。Python以`uv run --locked python -m local.private.m1.10.<module>`執行；browser程序用`/private/tmp/skg-browser-venv/bin/python`、`PLAYWRIGHT_BROWSERS_PATH=/private/tmp/skg-tools/playwright`。重跑須指定全新目的目錄；不覆寫舊版本或事件報告。這些私有腳本不是OPS-01通用更新協調器。

`renormalize.json`、`review-commands.json`、`acceptance.json`及`browser-regressions.json`保存實際CLI／參數／退出碼；research公共run／loader邊界另外量測真實模型。05/06/07/08/09/02所有原始證據逐檔hash前後一致；公開`data/`與lock未變。本輪snapshot、DB、報告、截圖不提交。check在`/private/tmp`的已知source_sha256過濾問題仍未修，另存Git tracked相對路徑hash，不把空map宣稱完整hash；後續由最終審查處理。

| 私有證據（相對`local/private/m1/10/`） | SHA256 |
| --- | --- |
| `check-candidate.json` | `4f2e3a36a5ae3f47506c44fbf2d20293fd90377cc0a801c8ab72b8dc53481273` |
| `acceptance.json` | `8e450b67fe25615bc9cdc30d132b9d37712a9515638e600c4e7b1da21a2268b1` |
| `model-four-scenarios/report.json` | `85135f57c4ebd6008715ac539f997ff5d324db728f731f869a229b3d01ce4d69` |
| `browser.json` | `88f23266aa42571589a111dfe64e6030d4904e5a1997846963ca55c292d94b7f` |
| `source-sha256.json` | `5e38007ef23063af2904ddaf02623a6d685598eef3afbaf3bdb3df68b4a7770d` |

文件／連結與`git diff --check`另於提交前檢查；不將文件檢查或本輪證據宣稱為最終審查完成。


## Post-review 候選追加（2026-11-17）

上述原 `3834c19` 的結果、命令及 hash 維持歷史證據。本次僅勘誤原「公司／營收出表日同為11/17」文字：兩市場公司出表日為11/16，月營收為11/17，來源 bytes 未修改。

最終兩軸審查發現3個不同缺陷及1個共用化建議，已於 `ecd176b3069a62aaa98c7a641496af45b8c415f2` 修復。新候選完整 check exit 0（490 pytest／246 subtests／55 Node），`source_sha256` 81個正確且排除private；原先空map問題已修正。兩市場原始CSV重新 official_import→全新ledger／四個semantic+alerts bundle→audit／compare／event與真實三頁、四組瀏覽器回歸均通過；財務四次0、行情仍兩次預期2。真實模型四情境引用本文件原證據，未宣稱新候選重跑全部四情境。

Standards／Spec分開的原finding、red→green、環境、命令、私有證據hash及未驗項見[審查修復驗證](VERIFICATION-2026-11-17-REVIEW.md)。新產物在 `local/private/m1/review-fixes/`，原02／05～10證據逐hash不變；09／10維持needs-info，M1不結案。
