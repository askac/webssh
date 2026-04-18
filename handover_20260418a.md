# Handover 2026-04-18a

## Current Status

本輪在 `github/webssh` 完成 localhost SSH key auth 的 UI/流程修正，目標是讓 localhost 連線失敗時的提示更精準，並避免把顯示字串當成控制訊號。

目前工作樹中與本輪相關的程式修改只有：

- `app.py`
- `templates/index.html`

另有既有未追蹤檔，**不要直接 `git add .`**：

- `.codex`
- `AGENTS.md`
- `handover_20260417a.md`
- `handover_20260417a_prompt.txt`

## Work Completed

### 1. Fixed localhost auth flow semantics

- 有輸入 password 時，localhost 直接走 password auth
- 只有 localhost 且 password 空白時，才嘗試 local public key auth
- 不再把同一個欄位混用成 key passphrase / SSH password

### 2. Added typed localhost key setup hint

- 後端在 localhost key auth 失敗時，不再只回純字串錯誤
- 改成帶 `message_type` / `error_code` / `action_type` / `action_message` / `action_question`
- 只有在以下條件同時成立時才會提供自動 setup 提示：
  - localhost
  - password 空白
  - key auth 失敗
  - username 等於目前本機使用者
  - `~/.ssh/authorized_keys` 缺少本地 public key

### 3. Replaced browser confirm with in-page prompt

- 前端移除 `window.confirm(...)`
- 改成 login panel 內的獨立 action prompt
- 說明文字與最後問句分開顯示
- 按鈕改成 `Yes` / `No`
- `No` 為主按鈕高亮，且 prompt 出現時鍵盤焦點落在 `No`

### 4. Added localhost auto-setup and reconnect

- 使用者按 `Yes` 後，前端送獨立 `setup_localhost_key_access` 事件
- 後端只在目前本機使用者情況下 append 第一把缺少的 local public key 到 `~/.ssh/authorized_keys`
- setup 成功後，前端會立刻用同一組 host/port/username/password 自動重試連線
- `already_configured` 或 `failed` 不會自動重試

### 5. Added conservative Windows restriction

- 對 Windows 特殊情況先採保守策略
- 若偵測為 Windows administrator account，**不提供自動 setup**
- 改回傳手動提示，不顯示 `Yes` / `No`
- Windows hint 已補充：
  - `%USERPROFILE%\.ssh\authorized_keys`
  - `C:\ProgramData\ssh\administrators_authorized_keys`

## Fix / Implementation

### Backend

- `app.py`
  - 新增 local public key 掃描與 parse
  - 以 `(key_type, key_body)` 比對 `authorized_keys`
  - 新增 localhost setup availability 判斷
  - 新增 `setup_localhost_key_access` socket event
  - Windows admin 帳號回傳 manual hint，不進 auto-setup flow

### Frontend

- `templates/index.html`
  - password placeholder 改回 `Password (Optional)`
  - 新增 in-page `actionBox`
  - 依 typed metadata 顯示 action prompt
  - `No` 為高亮預設選項
  - `Yes` 成功 setup 後自動重試 localhost 連線

## Validation Done

實際完成的驗證：

1. 使用 repo 內 venv 執行：
   - `tools/.venv_wsl/bin/python -m py_compile app.py`
2. 使用者回報：
   - localhost setup prompt / button flow 測試可用
   - `Yes` 後可成功自動重試

尚未做的驗證：

- 本輪**沒有**重新做 `/debug/xterm-wrap` 與 `less/head/cut` 的前端重現調查
- Windows 環境僅做 code inspection / defensive handling，**未在實機 Windows server 上驗證**

## Files Changed

- [app.py](/mnt/d/workspace/github/webssh/app.py)
- [templates/index.html](/mnt/d/workspace/github/webssh/templates/index.html)

## Git State

- Branch: `main`
- Base HEAD before this round: `3c35a43 Add localhost SSH key auth support`
- Intended commit content:
  - `app.py`
  - `templates/index.html`
  - `handover_20260418a.md`
  - `handover_20260418a_prompt.txt`

## Remaining Risks

- Windows support仍是保守版；目前只明確阻擋 Windows administrator auto-setup，尚未完整處理所有 Windows OpenSSH 變體
- `setup_localhost_key_access` 目前只 append 第一把缺少的 local public key；若使用者想選擇特定 key，之後需再設計
- 本輪沒有補 README / docs，若要公開此功能，應補說明

## Next Steps

1. 若要完整支援 Windows，補平台分流與更細的 authorized_keys 路徑判斷
2. 若要延續先前 xterm wrap 調查，回到 `handover_20260417a.md` 的 `/debug/xterm-wrap` 重現流程
3. 視需要補 README 的 localhost key setup 說明與 Windows 限制

## Prompt Stub Location

- [handover_20260418a_prompt.txt](/mnt/d/workspace/github/webssh/handover_20260418a_prompt.txt)
