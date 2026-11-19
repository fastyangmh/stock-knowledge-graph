# P2-02 日曆審查與修復重驗

2026-11-19 在 macOS arm64 重驗候選 `f45a8ac890e9ec0a435b50326b4ef22c6bbb3605`。兩市場的六份日曆報告及四份事件報告均與 06 封存的原報告逐位元組相同。完整 `local.check --frontend` exit 0。修復的三種邊界情境以合成行情、實際 SQLite、經稽核的研究 bundle 及公開 CLI 驗證。[06 原始逐日預期與報告 SHA256](VERIFICATION-2026-11-19-CALENDAR-COVERAGE.md)

## 兩軸審查

下列行號以審查基準 `49fee88` 計。兩軸各自指出的重疊問題保留原歸屬。

| 審查軸 | 發現 | 處理 |
| --- | --- | --- |
| 專案標準 | `calendar_coverage.py:132` 遇同時首存相異行情，按 run 名取第一筆 | 比對同市場、同股、同日的最早完整事實。矛盾時 CLI exit 2 並列出市場、日期、股票。相同事實的重複留存仍可讀。 |
| 專案標準 | `calendar_gaps.py:72` 在行情截止後提前返回，隱去已知應到時點 | 從已選市場與股票的範圍判斷中保留 `after_market_trade_date`，另列期限和證據 ID。 |
| 專案標準 | `calendar_ordinals.py:57` 傳遞六項位置值，兩個讀者靠解包順序辨識欄位 | 改用 `RangePosition` 的具名欄位，用原 CLI 檢查區間與事件序號、收盤價連續性。 |
| 專案標準 | `DEVELOPMENT_BACKLOG.md:27,116` 與私有完成清單第 12 行的進度落後票據 | 交由整合分支同步總覽，產品候選範圍為程式、回歸測試與操作手冊。 |
| 規格符合度 | 規格第 58 行要求分開「研究範圍」與「尚未到期」 | 今日 09:00 可知應到 18:00 時，列的範圍仍不足，期限、缺口診斷與該日連續性均待到。跨至次日的期限也有測試。到期仍缺範圍時顯示 `due_passed_outside_scope` 及未知連續性。 |
| 規格符合度 | 規格第 60 行的截止回播，普通報告在 `calendar_coverage.py:167` 接受未來截止，且同時首存的矛盾行情缺乏先後依據 | 日曆與事件 CLI 共用截止驗證，未來時間直接 exit 2。互換最早行情值的 run 名順序，兩種順序都拒用。 |
| 規格符合度 | 06 票第 18 行要求產品驗收後回填 P2-02 | 06 重播與本候選重驗各自留存，交接、總覽與完成清單由整合分支更新。 |

## 合成回歸

先跑原日曆三組測試，28 pytest、29 subtests 通過。再逐項新增 CLI 案例，依序取得以下失敗與修復結果。

| 案例 | 修復前 | 修復後 |
| --- | --- | --- |
| 帶及不帶事件參數，各指定未來截止 | 普通報告生成成功，exit 0 | 兩種入口皆 exit 2，輸出路徑沒有新報告 |
| bundle 只涵蓋至昨日，今日開市且有期限 | 同日、跨日及已到期案例均缺少期限證據 ID | 未到期限為 `pending`；已到期限仍保留範圍不足，未列入未解缺口分母。其他市場期限被排除，未選股維持未知連續性 |
| 三份同時保存的 bundle，前兩份行情一致，第三份價格不同 | 兩種 run 名與價格順序都生成新報告，exit 0 | 相同行情仍可重播；出現相異行情後，兩種順序均 exit 2，保留舊輸出 |

修復及序號重構後重跑 `python -m pytest -q local/tests/test_calendar_coverage.py local/tests/test_gap_evidence.py local/tests/test_calendar_ordinals.py`，31 pytest、36 subtests 通過。[逐日報告狀態與應到時點](CALENDAR_COVERAGE.md)

## 真實來源與完整套件

從乾淨候選工作樹執行。將 `evidence_repo` 設為保存原始私有證據與鎖定環境的整合工作區根目錄。沿用原 06 的事前期望，SHA256 為 `c2ca078a933a5cf598b78e474ce69411b83665d09b8c24123880377820d442c0`。重播與核對腳本的副本只調整候選 commit 與完整檢查報告路徑，實際參數在 `execution.json`。

```bash
packet="$evidence_repo/local/private/m2-calendar/review-f45a8ac"
export TMPDIR=/private/tmp UV_CACHE_DIR=/private/tmp/skg-uv-cache
export UV_PROJECT_ENVIRONMENT="$evidence_repo/.venv"
export PATH="/private/tmp/skg-tools/node-v22.16.0-darwin-arm64/bin:$PATH"
uv run --locked python -m local.check --frontend --report "$packet/check.json"
"$evidence_repo/.venv/bin/python" "$packet/replay.py"
"$evidence_repo/.venv/bin/python" "$packet/../04/replay.py" "$packet/../04"
"$evidence_repo/.venv/bin/python" "$packet/../05/verify.py" "$packet/tpex-base.json"
"$evidence_repo/.venv/bin/python" "$packet/verify.py"
```

- TWSE 重新核對 6 個原件雜湊、27 筆年度日曆列、13 筆當月成交列及四日人工預期，exit 0。TPEx 重新核對 9 個原件、從 PDF 公報抽取第 4 頁、兩檔股票成交日期及四日 CLI 報告，exit 0。兩市場各為 11/14、15 休市，11/16、17 開市。[TWSE 來源](VERIFICATION-2026-11-19-TWSE-CALENDAR.md) · [TPEx 來源](VERIFICATION-2026-11-19-TPEX-CALENDAR.md)
- 06 核對腳本驗證 4 份官方行情 CSV 的雜湊、全檔日期及選股覆蓋，也驗證研究版本中的行情事實、日曆原件、事件首次保存基準及後續觀察。6 份日曆各執行兩次，另執行 4 次事件 CLI，共 16 次 exit 0；最終逐筆核對 exit 0。兩市場 11/18 於較晚截止皆有第 1 筆保存報價；該日未涵蓋在日曆內，市場交易日序號未知。兩市場 6 份日曆報告 SHA256 全數與原 06 表相符。[原 06 雜湊與截止](VERIFICATION-2026-11-19-CALENDAR-COVERAGE.md)
- 首次完整檢查的 PATH 沒有 Node，Python 521 pytest、282 subtests 已通過，前端檢查使整體 exit 1。以既有 Node v22.16.0 重跑；macOS 27.2.1 arm64、Python 3.11.11、uv 0.6.13，10 個檢查步驟全數 exit 0，521 pytest、282 subtests、55 Node tests 通過。`check-without-node.json` SHA256 為 `2db7ec850ae8b6d1bd501764638f5aba49bd28458d40c146639fdd98d3340a86`，成功的 `check.json` 為 `80e95cd0f7fbeb90648c05c4e791d11af194bced12b5827251acf2df4664185f`。兩份檔案均記錄候選工作樹乾淨。
- 私有 `hashes.json` 保存逐檔雜湊，本次 SHA256 為 `7308ad2aa67bec65b5cb124edea6920d6c7b2a2336ed14773640d217d47ae0b9`。以上使用封存的官方原件，未另行下載。真實樣本沒有帶已知發布期限的缺口、同時矛盾首存、停牌或 5／20 日完整行情；上述邊界證據來自合成回歸。真實瀏覽器、Linux／NAS、行情單位及獨立交易範圍另待驗證。
