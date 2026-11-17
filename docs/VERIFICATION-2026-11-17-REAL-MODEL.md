# 真實模型增量驗證（ticket 02）

日期：2026-11-17。這是 macOS 補充驗證；ticket 01 的 Linux gate 尚未通過，ticket 02 維持 `needs-info`。

新增 `local.model_check`，以核准的 research／semantic／encoder-loader seam 量測，使用真實 SQLite、不可變 bundle 與 audit。
入口是 opt-in，`local.check` 只跑合成 encoder 回歸，不下載模型。操作見[私有研究](PRIVATE_RESEARCH.md)。

## TDD 與本機真實結果

- 原 research／semantic 基準：25 passed，exit 0。
- 新測試 red：缺 `local.model_check`，ModuleNotFoundError，pytest collection error（外層 shell 因 zsh 唯讀 `status` 變數回傳 1，未另捕捉 pytest exit code；原始 pytest 錯誤保留）。
- green：四情境合成 encoder 回歸 1 passed；連同既有回歸 26 passed，exit 0。
- 真實初次擷取與四情境：exit 0；完整離線 local.check exit 0。
- 乾淨實作 Commit `5a4065069389e715a00ffa881d362eda09b371b8`：離線真實四情境 exit 0；完整 local.check exit 0，413 passed、154 subtests passed。
- 合併 integration `82edd78` 後，乾淨 Commit `0fb3f08d917c5ac286f4037a65c719d2417a28af`：離線真實四情境 exit 0；完整 local.check exit 0，422 passed、163 subtests passed。
- 明確缺少已驗證快取的離線 CLI：exit 1，保存 FileNotFoundError 與 passed=false，未載入模型。
- `git diff --check` exit 0；本票未更動公開示範、uv.lock 或既有私有研究。

| 情境 | encoded | pairs_evaluated | loader 次數 | graph_reused | stock_pairs |
| --- | --- | --- | --- | --- | --- |
| 首次 | 3 | 3 | 1 | false | 3 |
| 相同輸入 | 0 | 0 | 0 | true | 3 |
| 單篇文本修改 | 1 | 3 | 1 | false | 3 |
| 只改股票映射 | 0 | 3 | 0 | false | 1 |

三篇中／英／日文本及三檔股票皆為合成資料。真實模型為
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，完整 revision
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`。由 Hugging Face metadata 確定完整 revision 後，
所有下載均固定該 commit。一般 sandbox DNS 失敗（curl exit 6）；依正常 require_escalated 取得 metadata 與權重成功。
以 Hub 回應 commit／ETag 校驗 11 個模型／tokenizer／設定檔，再記錄 SHA256。未使用未知權重或浮動 tag 執行。

環境：Darwin arm64、CPython 3.11.11、CPU、PyTorch 單執行緒；uv 0.6.13、Node v22.16.0。
套件：sentence-transformers 5.7.0、torch 2.15.0、transformers 5.23.0、huggingface-hub 2.4.0、numpy 2.4.6。
`uv.lock` SHA256：`13259ea6ed35f56419de780e995041682df6ca535f3eac198a1c9616c1c9a865`，未變更依賴。

四份 audit 通過；全快取匯出語意邊相同，單篇修改只變動 `doc:d1` 向量，映射修改保持所有向量不變，
匯出股票關係／evidence 對應新映射。loader 邊界在兩個免載入情境直接拒絕被呼叫；不是只觀察 encoded=0。
編碼文本逐篇核對；合成 numeric 欄位未加入。每次確認舊 bundle 所有檔案 bytes 未變。
舊 pointer 失敗保全／損毀 DB 拒絕與數值排除仍由既有 research 測試及完整 local.check 驗證。

## 私有證據與重跑

私有執行根目錄：`/private/tmp/skg-worktrees/02/local/private/m1/02/`；已將原始報告、輸入、SQLite、模型 provenance 與完整已校驗 snapshot 複製至主工作區 `local/private/m1/02/`。Hub 中間下載快取不重複複製，主工作區仍可直接執行 `--offline`。
`model-cache/model-provenance.json` 包含來源、revision、ETag／SHA256／bytes；`live-01/report.json`
與 `exercise/scenarios.json` 包含四份 run、audit、向量 hash、關係與 loader 測量；原始輸入與 SQLite 同目錄保存。
最終整合證據為 `integrated/report.json` 與 `check-integrated.json`；兩份報告記錄乾淨 Commit，所有檢查 exit 0。

| 私有檔案 | SHA256 |
| --- | --- |
| `integrated/report.json` | `b031a50426a886dead87b7f64b4d48689fcd79545356567219579740f6b04fcd` |
| `check-integrated.json` | `f2b25bbaebff322c0e7c3ab4aff9f2786b7b4aad13b590c31add6cd2a79cf810` |
| `model-cache/model-provenance.json` | `2419e6d6ae941f784bd40a8da105b2aae5112044f41ae6d1b083c7affc5e74b4` |
| `model-cache/snapshot/model.safetensors`（470641600 bytes） | `eaa086f0ffee582aeb45b36e34cdd1fe2d6de2bef61f8a559a1bbc9bd955917b` |

模型、DB、原始報告不提交，公開 `data/` 未被覆寫。

```bash
export TMPDIR=/private/tmp
export UV_CACHE_DIR=/private/tmp/skg-uv-cache
export UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv
export PATH=/private/tmp/skg-tools/node-v22.16.0-darwin-arm64/bin:$PATH
uv run --locked python -m local.model_check --offline \
  --model-cache local/private/m1/02/model-cache \
  --output local/private/m1/02/offline-verified-001
uv run --locked python -m local.check --report local/private/m1/02/check.json
```

`--offline` 只接受先前已驗證 provenance 與完整檔案。首次擷取移除該旗標。`--output` 必須不存在，失敗後使用新目錄重跑。
此驗收不測語意品質、金融正確性、正式來源、GPU、Linux 或生產瀏覽器；沒有前端變更，本票未重跑前端／瀏覽器。
