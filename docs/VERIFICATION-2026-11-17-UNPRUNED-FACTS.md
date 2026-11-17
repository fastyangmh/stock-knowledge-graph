# 2026-11-17｜未裁剪研究事實契約驗證

對應 [ticket11](../.scratch/private-research-ready/issues/11-unpruned-facts.md)、[契約文件](RESEARCH_FACTS.md)。本紀錄只驗收 P2-01 的保存／稽核／archive 子票；ticket12 的事件讀者與前端揭露尚待接續，不關閉整個 P2-01。

## 版本與環境

- 功能 commit：`1b05985`；整合後測試 commit：`63edf535ee503aa448d3af53807656526ad1f9e4`，包含 integration `82edd78452c181995bd9f4e604e287cab3407eee`（01／05），測試時 `dirty=false`。
- macOS Darwin arm64、Python 3.11.11、uv 0.6.13、pytest 9.2.0、Node.js v22.16.0。這不是 Linux/NAS 驗收。
- `uv.lock` SHA256：`13259ea6ed35f56419de780e995041682df6ca535f3eac198a1c9616c1c9a865`；沒有依賴／lockfile 修改。
- 全部新增研究資料為合成 fixture；真實臨時 SQLite、私有 JSON、raw CSV 與本機 loopback HTTP。沒有下載官方金融資料／模型，沒有送出私有資料或發布公開金融圖譜。

## Red → green 證據

預先核准測試 seam 是 research → bundle_audit → research_archive；未建立 SQL 私有實作單元測試。主要逐步失敗及修復：

| 可觀察行為 | 修改前實際 red | 最小實作後 green |
| --- | --- | --- |
| 125筆財務＋1筆籌碼跨兩種展示上限完整保存 | `run()` 不接受 `max_information_nodes` | 上限2／100分別3／101個圖節點，126筆事實完全一致 |
| 全部已保存行情，不限20筆 | 25筆期望、實際0筆 | 2019-12-09～2020-01-02共25筆；展示上限0／100事實一致，圖只有當日行情 |
| 未知 schema 不退回圖譜 | 改寫並重算hash後 audit 沒有拒絕 | `facts_schema_unsupported` |
| 跨股／未來／錯來源／錯快照／假值／錯事實ID | 10個污染子案例未被拒絕 | 全部 fail closed |
| 筆數與索引大小／count | 低筆數政策下仍產生新版本，錯索引被接受 | 超額整批失敗，舊pointer與bundle不變 |
| 私有事實不占HTTP預覽預算 | 未提供HTTP的1 MiB metadata導致preview超額 | 完整資料受audit預算、服務資料受preview預算，兩者分開 |
| 歷史工作量 | 降低rows／raw／record預算後仍成功 | 共享預算明確失敗，無半份新產物；SQL VM預算另有真實SQLite測試 |
| 錯誤schema形狀不得中止整個catalog | scope／market為array時拋出未處理AttributeError | 壞版本標invalid，其他catalog流程保留 |
| 財務來源鏈 | provider篡改並重算hash後仍被接受 | source解析至供應該值的normalized snapshot，篡改拒絕 |

另外已測：原始舊行情CSV篡改、32 MiB JSON與整包bytes拒絕、缺新檔／hash／symlink、純舊bundle `display_graph_only`、零筆明確coverage、未來 availability 排除、較晚修訂不回填、raw／normalization metadata保留、行情recorded_at不能用observed_at假造。

## 實際命令與結果

初始預設macOS TMPDIR路徑經 `/var` symlink，既有安全gate拒絕；改用實體 `/private/tmp`，沒有降低安全檢查。初始 stdlib 基準 `TMPDIR=/private/tmp python3 -m unittest discover -s local/tests -p 'test_research.py' -q`：23 tests、exit0。共享鎖定環境就緒後採以下命令。

```bash
env TMPDIR=/private/tmp \
  UV_CACHE_DIR=/private/tmp/skg-uv-cache \
  UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv \
  PATH=/private/tmp/skg-tools/node-v22.16.0-darwin-arm64/bin:$PATH \
  uv run --locked python -m local.check --frontend
```

2026-11-17 06:15:04～06:15:16 UTC，exit **0**：

- Python完整 **440 passed、180 subtests passed**；含19個新增facts tests與其17個subtests。
- compileall、合成pipeline→SQLite→export→validate全部exit0。
- JavaScript語法檢查與Node測試 **53 passed**。
- 真實loopback HTTP測試在正常核准的執行權限下通過；`/versions/<run>/research-facts.json`、DB、raw／report路徑回應404，版本圖譜／catalog正常提供。最初沙盒內socket.bind被拒是環境失敗，不列產品通過；後續真實HTTP已執行成功。
- `git diff --check` exit0；公開`data/`無修改。

私有總報告：`local/private/check-report.json`，SHA256 `a97fcf33d519a7a66f17b43645f0dd094adc946b4b38a10e6fa6cc5753249fcc`。該檔不提交。

本次發現既有check的Python來源列舉用完整路徑排除名為`private`的component，因此 `/private/tmp` worktree 的 `source_sha256` 會是空object。已回報整合方，沒有把空map稱為完整源碼hash證據；本票另存相對repo路徑的72個Python檔hash於私有 `local/private/ticket11-source-hashes.json`，manifest SHA256 `6893c55ab10f291f3b8530f3622faf11c7b6e04fb8524c9633a773f4ed8e6a00`。主要檔案：

| 檔案 | SHA256 |
| --- | --- |
| `local/research_facts.py` | `4192d18e60e95fbd0433b5361ac92bdad3af29ffdc151603d23ae6932ba96ff0` |
| `local/tests/test_research_facts.py` | `721ae7652408729599a46e6e60d72ffb53ae36288d18ec396efa7cccf0dd22c9` |
| `local/research.py` | `4fd8a1052fbdd2e730b669f33226cdd94d14e213d93a490089d227d5012ecb9f` |
| `local/bundle_audit.py` | `cced3b5e2d062b060f4dd7b47b27d4e447ee1b0c691013b470c18b6f46aa1811` |
| `local/market_graph.py` | `37f5cbb9cb808038c5be8717dde7f0ebc41fbd6ed72c63761628fce1143bfdf1` |

## 未驗證與限制

沒有執行新版完整事實對真實金融來源的抽檢、Linux/NAS復原、真實模型或瀏覽器CDN驗收；Node通過不代表瀏覽器通過。本票不修改JS／DOM，真實瀏覽器與新舊cohort畫面留ticket12／09。沒有把行情觀察筆數當交易日，沒有補造未保存歷史或市場首次recorded_at。

容量測試用真實超大sparse JSON及低政策門檻證明fail-closed；沒有宣稱100,000筆／256 MiB是已量測的可用全市場效能。行情raw按每次驗證累計128 MiB，同日多股可能重讀；SQL回呼粒度1000步另有每個連線不足該粒度的固定餘量。完整JSON大小限制不保證Python峰值記憶體。完整事實由audit捕捉bytes驗證；不是防惡意本機管理員的簽章。
