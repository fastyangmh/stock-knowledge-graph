# 鎖定環境補充驗證（ticket 01）

日期：2026-11-17。實作與最終測試 Commit：`54773a094a9cf06294cc4e6b6bb9208ac0accbdc`，報告的 dirty 為 `false`。此為 **macOS 補充驗證**；尚無 Linux runtime，ticket 01 保留 `needs-info`，不宣稱完成目標環境驗收。

## 變更與 TDD

`local.check` 報告新增 Commit／dirty、OS／架構、Python patch／執行檔、uv／Node 版本、runner、frontend 請求及 lock SHA256。工具探測保留命令、退出碼、輸出；無法探測以 `null` 表示，不當成乾淨工作區。原有合成範圍與逐步退出碼保留。

核准 seam 為 `local.check` 入口、報告與退出碼。新增報告測試先因缺少 `repository` 產生 `KeyError`（exit 1），補實作後兩項 regression 通過（exit 0）；另一項驗證缺工具時未知狀態與 `--frontend` 失敗不被掩蓋。測試的 subprocess 邊界為合成結果，不等同真實工具驗收；以下全套則執行實際工具。

## 實際環境與命令

- OS：Darwin 27.2.0 / arm64；CPython 3.11.11。
- uv：0.6.13（Homebrew）；Node：v22.16.0（官方 darwin-arm64 tar，SHA256 經官方 SHASUMS 核對）。
- `uv.lock` SHA256：`13259ea6ed35f56419de780e995041682df6ca535f3eac198a1c9616c1c9a865`；bytes 未變。
- dev extra `pytest>=8,<10`、dev group `pytest>=9.2.0` 同時解析為 lock 中的 `pytest 9.2.0`，無需改依賴。
- 模型套件已安裝，這次沒有載入真實模型、下載權重或驗證真實來源。

可重跑命令（共享暫存環境路徑可換為本機路徑）：

```bash
export TMPDIR=/private/tmp
export UV_CACHE_DIR=/private/tmp/skg-uv-cache
export UV_PROJECT_ENVIRONMENT=/private/tmp/skg-venv
export PATH=/private/tmp/skg-tools/node-v22.16.0-darwin-arm64/bin:$PATH
uv sync --locked --extra dev
uv run --locked python -m local.check --frontend \
  --report local/private/m1/01/macos-54773a0-pytest.json
```

| 檢查 | exit code | 結果 |
| --- | --- | --- |
| 初次 sandbox `uv sync --locked --extra dev` | 1 | 套件主機 DNS 失敗；未改 lock |
| 同命令經正常 require_escalated | 0 | 安裝 48 packages；後續 cached repeat 亦為 0 |
| 初次 unittest check | 1 | macOS 預設 TMPDIR symlink 與 loopback 權限限制 |
| `TMPDIR=/private/tmp` unittest check | 1 | 剩下 loopback `PermissionError`，未略過 |
| 正常 require_escalated、unittest `--frontend` | 0 | 412 tests；Node 53 tests；隔離 SQLite→JSON smoke／validate 通過 |
| clean Commit 上 locked pytest `--frontend` | 0 | 412 passed、154 subtests passed；Node 53 tests；所有 10 個檢查退出碼皆 0 |

pytest 與 unittest 為同一測試集，不相加。Node 是離線邏輯測試，不是瀏覽器驗收。公開 `data/`、既有私有研究與 lock 未改寫。

## 私有證據與剩餘範圍

原始報告與 log 留於執行 worktree `/private/tmp/skg-worktrees/01/local/private/m1/01/`，不提交。包含 `execution-summary.json`、`sync.log`、失敗基準與後續成功報告。最終 `macos-54773a0-pytest.json` SHA256：`08e29a4f374fd7a88d83a9497301f855cd1187230938c46569debd7ee0ff9e66`。

`docker`、`podman`、`colima`、`lima` 均不在 PATH；現有主機為 macOS，無已提供 Linux 執行入口。仍需在乾淨 Linux／Python 3.11 上以同一候選 Commit 執行 sync 與 `local.check --frontend`，保留環境與原始報告。macOS 成功不解除此完成條件。真實模型四情境、正式來源及瀏覽器分屬其他 tickets，這次均未驗證。
