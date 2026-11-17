# 02: 真實模型與增量快取四情境

**What to build:** 讓研究者使用固定真實模型建立可稽核的研究版本，並確認增量執行僅做必要工作。

**Parent:** [P0-01](../../../docs/DEVELOPMENT_BACKLOG.md)
**Spec:** [第一階段規格](../spec.md)
**Milestone:** M1
**Blocked by:** [01：Linux／Python 3.11 鎖定環境重現](01-locked-environment.md)
**Status:** needs-info
**Review:** 使用者於 2026-11-17 授權依本規格實作、TDD、整合與審查；執行驗收仍依實際證據判定。

## Acceptance criteria

- [x] 沿用既定模型，固定完整 revision，記錄取得方式、權重／設定識別、硬體與所用套件；網路不可用時只接受可校驗對應 revision 的快取。
- [x] 固定可重現的多語文本及股票映射，首次建立向量與關聯，bundle audit 通過。
- [x] 相同輸入第二次執行 encoded=0、pairs_evaluated=0、關聯重用；以 loader 邊界測量證明沒有載入模型，不能僅看 encoded=0。
- [x] 只改一篇文本時僅該篇重編；只改文件股票映射時不重編文本，但關聯與 evidence 反映新映射。
- [x] 真實模型四情境、合成 encoder 回歸分開記錄，保留舊 bundle／pointer 失敗保全與 numeric 不進文字 encoder 的驗證。
- [ ] 缺下載／權重或任何情境未執行則本票未完成；新增修復先 red 再 green，最後重跑必要 local.check。

## Testing seam

research／semantic 既有入口與報告，既有 encoder／loader 邊界只用於可觀測的載入／編碼測量；DB 與 bundle 使用真實實作。

## Demonstration

四次受控輸入變化產生四份可稽核私有版本，計數與向量／關聯結果符合增量契約。

## Completion evidence

- [x] 記錄實作 Commit、實際命令／環境／exit code、測試與資料屬性（合成／真實）、私有證據識別及未驗證範圍。
- [ ] 更新相關功能文件；完成後本票設 resolved 並同步 parent backlog 實際進度，不以單一子票關閉整個 parent。
- [x] 私有 bytes／DB／原始報告不提交；repo 僅留去敏感摘要與可重跑程序，公開示範未被改寫。

## Comments

2026-11-17：已新增 opt-in `local.model_check`，固定既定模型完整 revision，驗證下載權重／設定 hash，真實模型四情境已在 macOS arm64／Python 3.11.11 通過，四份 bundle audit 成功。詳見[驗證紀錄](../../../docs/VERIFICATION-2026-11-17-REAL-MODEL.md)。合成 encoder 回歸與真實模型分開記錄；公開示範與 uv.lock 未變。

依賴 gate：ticket 01 尚缺 Linux／Python 3.11 目標環境驗收，因此本票仍為 needs-info；本機成功不替代 Linux acceptance，不關閉 parent P0-01。私有原始證據與模型位於 `local/private/m1/02/`，不提交。
