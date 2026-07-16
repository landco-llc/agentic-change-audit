# Agentic Change Audit — Codex Plugin（development preview）

[English](README.md) | [日本語](README.ja.md)

## 狀態

**Development preview。** 這是 Agentic Change Audit 第一個可安裝的 Codex Plugin 基礎版本。它是一個 **skills-only Plugin**：內含既有的 Agentic Change Audit Skill，讓使用者除了 direct Skill folder 之外，也能透過 repository 範圍的 local marketplace 進行安裝。

這個 development Plugin 尚未提交、列入或公開於 OpenAI 的公開 Plugins Directory。

## 申請狀態

- **Desktop gate：通過（僅就 development foundation 而言）。** 已在 ChatGPT desktop 應用程式中驗證：可透過 CLI marketplace 註冊，於 **L&Co.LLC Open Source** marketplace 下顯示並安裝，可回應 `$agentic-change-audit` 明確呼叫，且稽核執行後 Git working tree 未變更。此 gate 僅涵蓋此 development foundation。
- **尚未完成向 OpenAI 的正式申請。** OpenAI submission portal 中沒有 draft，也未提交任何內容。
- **公開政策 URL 已備妥。** [支援](https://github.com/landco-llc/agentic-change-audit/blob/main/SUPPORT.md)與[隱私](https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md)已由本 repository 公開。publisher identity verification、logo 核准與申請本身，均仍待人工決定。
- **不主張任何公開 Directory 上架。** 本 Plugin 未在 OpenAI 公開 Plugins Directory 上架、提供或取得核准。請僅由本 repository 的 local marketplace 安裝。

repository 端的準備資料位於[申請套件](https://github.com/landco-llc/agentic-change-audit/tree/main/submission/codex-plugin)。這是準備資料，並非申請。

## 這個 Plugin 提供什麼

- 一個 **skills-only** 套件：`.codex-plugin/plugin.json`，以及 `skills/agentic-change-audit/` 下內含的 Skill。
- 內含的 Skill 與建置當下 commit 的 repository root 正本 Skill 來源逐位元組（byte-identical）一致。
- 稽核 workflow 本身沒有變更：Evidence-first、agent-neutral，預設為 read-only。

## 這個 Plugin 不提供什麼

- **沒有 MCP server。** 沒有 `.mcp.json`，也沒有 `mcpServers` 項目。
- **沒有 ChatGPT app 或 connector。** 沒有 `.app.json`，也沒有 `apps` 項目。
- **沒有 lifecycle hooks。** 沒有 `hooks/` 目錄，也沒有 `hooks` 項目。
- **沒有 authentication flow。** manifest 未宣告任何登入或 token 交換流程。
- **沒有 telemetry。** 這個 Plugin 不會向任何地方回傳使用狀況、analytics 或 event。
- **沒有具寫入能力的 tool。** manifest 宣告的 capability 僅有 `Read`。

將 repository copy 或 symlink 到 `~/.claude/skills/` 或 `~/.agents/skills/` 的 direct Skill installation 方式，不會被這個 Plugin 取代，仍完整支援。此方式請參閱[安裝指南](https://github.com/landco-llc/agentic-change-audit/tree/main/guides)。

## Local marketplace 測試

Clone repository，並將其註冊為 local Plugin marketplace source：

```bash
git clone \
  https://github.com/landco-llc/agentic-change-audit.git

cd agentic-change-audit

codex plugin marketplace add .
codex plugin marketplace list
```

`codex plugin marketplace add .` 會將目前 repository 的 `.agents/plugins/marketplace.json` 註冊為名為 `landco-llc-open-source` 的 local marketplace source。這個指令本身不會安裝 Plugin，也不會連線至任何外部 service。

## 在 ChatGPT desktop 安裝與測試

1. 新增或更新 marketplace 後，請重新啟動 ChatGPT desktop app，讓它讀取新的 source。
2. 開啟 **Plugins**。
3. 選擇 **L&Co.LLC Open Source** marketplace。
4. 安裝 **Agentic Change Audit**。
5. 開啟一個新的 task 並呼叫此 Plugin 進行測試。

以上步驟在 ChatGPT desktop UI 中的實際操作屬於 **PENDING HUMAN CHECK**，本 repository 無法自動執行或保證其結果。

## 此分支 merge 後直接從 GitHub 註冊

這個 Plugin 基礎版本 merge 進 `main` 之後，也可以不透過 local clone，直接從 GitHub 新增 marketplace：

```bash
codex plugin marketplace add \
  landco-llc/agentic-change-audit \
  --ref main
```

在此之前，請針對此分支的 checkout 使用上方的 local `codex plugin marketplace add .` 指令。

## 呼叫範例

```text
$agentic-change-audit

稽核目前 repository 的變更。
將稽核固定於目前的 base 與 target HEAD。
不要修改任何 file。
以 Markdown 回覆。
```

```text
使用 Agentic Change Audit 將這個由 AI 建置的 application 視為 release candidate 進行稽核。

記錄缺少的 evidence、finding、human check、一個 Verdict，
以及下一步允許的 action。
不要修改、deploy 或 release 任何內容。
```

## Read-only 稽核邊界

內含的 Skill 只進行稽核，不會執行動作。這個 Plugin 宣告的 capability 僅有 `Read`，稽核 workflow 本身也明確指示在稽核 phase 中不得修改 file、commit、push、核准、merge、deploy 或 release。使用者在稽核之後要求的任何狀態變更 action，都視為稽核以外、另行明確授權的步驟。

## 不授予組織性權限

安裝這個 Plugin 並不會授予 agent 或 Plugin 本身 approval、merge、deployment 或 release 的權限。PASS 判定是決策輔助，不能取代擁有該權限的人員。

## 不提供資安、法律或正式上線的保證

透過這個 Plugin 產生的稽核結果，並非資訊安全認證、法律意見、法規合規認證，也不是正式上線安全性的保證。涉及視覺確認、業務判斷、個人資料、付款、法務、破壞性操作、deploy 與最終核准等事項時，仍需人員確認。

## 版本

這個 Plugin 使用 development version 識別碼 `0.1.0-dev.1`。這不是公開 release 或穩定版 Plugin，也不對應任何已標記 tag 的 Skill release。

## 相關文件

- [Repository README](https://github.com/landco-llc/agentic-change-audit/blob/main/README.md)
- [安裝指南](https://github.com/landco-llc/agentic-change-audit/tree/main/guides)
- [正本 Skill（`SKILL.md`）](https://github.com/landco-llc/agentic-change-audit/blob/main/SKILL.md)
- [支援](https://github.com/landco-llc/agentic-change-audit/blob/main/SUPPORT.md)
- [隱私](https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md)
- [申請套件](https://github.com/landco-llc/agentic-change-audit/tree/main/submission/codex-plugin)
- [License](https://github.com/landco-llc/agentic-change-audit/blob/main/LICENSE)
