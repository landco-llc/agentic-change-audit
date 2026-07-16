# 安裝、導入、設定與使用指南

[English](../en/installation.md) | [日本語](../ja/installation.md)

- 語言：繁體中文
- 最後確認日期：2026-07-15
- 適用公開版本：`v0.1.0-rc.1`
- 直接安裝對象：Claude Code、OpenAI Codex
- 套件名稱：`agentic-change-audit`
- 狀態：預發行版本

## 1. Agentic Change Audit 是什麼

Agentic Change Audit 是一個開源 Agent Skill，用於在人類決定 merge、release 或 deploy 之前，稽核 AI Agent 或人員所進行的軟體變更。

主要適用對象：

- Pull Request 與固定 commit
- 本機尚未 commit 的變更
- Release candidate
- AI 產生、人員撰寫或兩者混合的變更
- 應用程式、網站、業務自動化、設定、基礎設施、資料移轉、外部相依套件與文件

它不只接受 AI 所說的「已確認」或「沒有問題」，而是記錄稽核對象、已執行的檢查、未執行的檢查、剩餘問題、需要人工確認的事項，以及一個最終 Verdict。

本 Skill 用於協助判斷，不會取代人類的最終權限，也不是資訊安全、法律、法規或正式上線安全性的認證或保證。

## 2. 目前支援範圍

`v0.1.0-rc.1`提供下列環境的直接安裝說明：

- Claude Code
- OpenAI Codex

核心規範不綁定特定 AI 公司，但目前尚未提供：

- Claude Code Plugin package
- ChatGPT Web 一鍵安裝
- Custom GPT
- Gemini CLI 專用套件
- GitHub Copilot 專用套件

OpenAI 的 direct Skill folder 適合本機使用與 repository 範圍內的工作流程，此方式仍完整支援。此外，現在也可以從本 repository 的 local marketplace 取得**development skills-only Codex Plugin**。這個 Plugin 內含相同的正本 Skill 與稽核 workflow，未新增任何 MCP server、ChatGPT app、connector 或 lifecycle hooks，也不會授予 approval、merge、deploy 或 release 權限。OpenAI 公開 Plugins Directory 的申請尚未完成；這個 Plugin 僅能透過 repository 範圍的 local marketplace，或 merge 進 `main` 之後透過 Git-backed marketplace source 安裝，安裝與測試皆透過 ChatGPT desktop app 進行。

註冊 local marketplace：

```bash
codex plugin marketplace add .
```

有關 local marketplace 測試、ChatGPT desktop 安裝與呼叫範例，請參閱[Codex Plugin README](https://github.com/landco-llc/agentic-change-audit/tree/main/plugins/agentic-change-audit)。

## 3. 正確的套件結構

有效的安裝必須在套件根目錄直接包含`SKILL.md`。

```text
agentic-change-audit/
├── SKILL.md
├── README.md
├── README.ja.md
├── docs/
├── guides/
├── standard/
└── templates/
```

請勿在根目錄名稱加入版本號。

```text
正確：
agentic-change-audit/

錯誤：
agentic-change-audit-0.1.0-rc.1/
```

也請避免形成巢狀套件。

```text
agentic-change-audit/
└── agentic-change-audit/
    └── SKILL.md
```

## 4. 公開原始碼與 Release

Repository：

```text
https://github.com/landco-llc/agentic-change-audit
```

Release：

```text
https://github.com/landco-llc/agentic-change-audit/releases/tag/v0.1.0-rc.1
```

已公開的 asset：

```text
agentic-change-audit-0.1.0-rc.1.zip
agentic-change-audit-0.1.0-rc.1.manifest.json
agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

已公開的 SHA-256：

```text
0e9fe576b2db43e29817df0a15d5e1eea2c07eeb8a0843c0b88117d81ac270ac  agentic-change-audit-0.1.0-rc.1.zip
df12de142bc2e6207d3325902043a81563e6429bd783405cde8749c62a6edffe  agentic-change-audit-0.1.0-rc.1.manifest.json
57327a19cecfc01ce5da924b0d02735b046dbddcffc2673fc70da50ea0e2c6bb  agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

GitHub 自動產生的`Source code (zip)`與`Source code (tar.gz)`不是 runtime Skill archive。請使用上述三個 Release asset。

## 5. 建議的共用 source 配置

以下配置便於 Codex 與 Claude Code 使用同一份套件，並降低版本不一致的風險。

```text
共用套件：
~/.local/share/agentic-change-audit/

Codex：
~/.agents/skills/agentic-change-audit
    -> ~/.local/share/agentic-change-audit/

Claude Code：
~/.claude/skills/agentic-change-audit
    -> ~/.local/share/agentic-change-audit/
```

## 6. 使用 Git 安裝固定 Release

適合可以使用 Git，並希望固定使用公開 Tag 原始碼的情況。

先確認目的地不存在：

```bash
test ! -e "$HOME/.local/share/agentic-change-audit" \
  && test ! -L "$HOME/.local/share/agentic-change-audit"
```

Clone 固定 Tag：

```bash
mkdir -p "$HOME/.local/share"

git clone \
  --branch v0.1.0-rc.1 \
  --depth 1 \
  https://github.com/landco-llc/agentic-change-audit.git \
  "$HOME/.local/share/agentic-change-audit"
```

確認 identity：

```bash
cd "$HOME/.local/share/agentic-change-audit"

git describe --tags --exact-match
git rev-parse HEAD
git status --short
```

預期值：

```text
Tag：
v0.1.0-rc.1

Commit：
f421571f25d090cbd7b5e387e82db86a688cd229

Working tree：
clean
```

確認 Skill entrypoint：

```bash
test -f "$HOME/.local/share/agentic-change-audit/SKILL.md" \
  && echo "Agentic Change Audit package: OK"
```

## 7. 從 Release ZIP 安裝

適合希望固定使用已稽核發行檔案的情況。

可從 Release 頁面下載三個 asset，或使用 GitHub CLI：

```bash
mkdir -p "$HOME/Downloads/agentic-change-audit-v0.1.0-rc.1"
cd "$HOME/Downloads/agentic-change-audit-v0.1.0-rc.1"

gh release download v0.1.0-rc.1 \
  --repo landco-llc/agentic-change-audit \
  --pattern 'agentic-change-audit-0.1.0-rc.1.zip' \
  --pattern 'agentic-change-audit-0.1.0-rc.1.manifest.json' \
  --pattern 'agentic-change-audit-0.1.0-rc.1.SHA256SUMS'
```

確認 checksum。

macOS：

```bash
shasum -a 256 -c agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

Linux：

```bash
sha256sum -c agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

列出的兩個檔案都必須顯示`OK`。

解壓縮並確認 entrypoint：

```bash
unzip agentic-change-audit-0.1.0-rc.1.zip

test -f agentic-change-audit/SKILL.md \
  && echo "Skill package: OK"
```

確認共用目的地尚未使用後移動：

```bash
mkdir -p "$HOME/.local/share"

mv agentic-change-audit \
  "$HOME/.local/share/agentic-change-audit"
```

## 8. 安裝至 Codex

### 8.1 所有專案都可使用

```bash
mkdir -p "$HOME/.agents/skills"

destination="$HOME/.agents/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf '安裝位置已存在：%s\n' "$destination" >&2
else
  ln -s \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

確認：

```bash
test -f "$HOME/.agents/skills/agentic-change-audit/SKILL.md" \
  && echo "Codex Skill: OK"
```

### 8.2 僅在特定 repository 使用

在目標 repository 的 root 執行：

```bash
mkdir -p .agents/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .agents/skills/agentic-change-audit
```

請勿將包含特定電腦絕對路徑的 symlink commit 到共享 repository。團隊共享時，請使用 repository 相對配置或受控的完整複製方式。

### 8.3 在 Codex 中呼叫

請在要稽核的 repository 中啟動 Codex。

明確呼叫：

```text
$agentic-change-audit

請稽核目前的專案。
請將稽核固定至目前的 commit 與 effective diff。
請勿修改檔案、commit、push、merge、deploy 或 release。
請以 Markdown 回傳結果。
```

其他方式：

- 執行`/skills`
- 輸入`$`後選擇`agentic-change-audit`
- 在 prompt 中直接指定 Skill 名稱
- 當需求符合 description 時，由 Codex 自動選擇

若新安裝的 Skill 沒有出現，請重新啟動 Codex。

### 8.4 在 Codex 暫時停用

在`~/.codex/config.toml`加入：

```toml
[[skills.config]]
path = "/absolute/path/to/.agents/skills/agentic-change-audit/SKILL.md"
enabled = false
```

修改設定後請重新啟動 Codex。

## 9. 安裝至 Claude Code

### 9.1 確認版本

使用 symlink Skill directory 需要 Claude Code `v2.1.203`以上版本。

```bash
claude --version
```

版本較舊時，請更新 Claude Code 或使用完整複製方式。

### 9.2 以 symlink 安裝為個人 Skill

```bash
mkdir -p "$HOME/.claude/skills"

destination="$HOME/.claude/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf '安裝位置已存在：%s\n' "$destination" >&2
else
  ln -s \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

確認：

```bash
test -f "$HOME/.claude/skills/agentic-change-audit/SKILL.md" \
  && echo "Claude Code Skill: OK"
```

### 9.3 無法使用 symlink 時

```bash
mkdir -p "$HOME/.claude/skills"

destination="$HOME/.claude/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf '安裝位置已存在：%s\n' "$destination" >&2
else
  cp -R \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

請勿對已存在的目的地重複執行`cp -R`，否則可能保留舊檔案或產生巢狀套件。更新時應完整替換整個 directory。

### 9.4 僅在特定 project 使用

在目標 project 的 root 執行：

```bash
mkdir -p .claude/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .claude/skills/agentic-change-audit
```

請勿將包含特定電腦絕對路徑的 symlink commit 到共享 repository。

### 9.5 在 Claude Code 中呼叫

```bash
cd /path/to/project
claude
```

明確呼叫：

```text
/agentic-change-audit

請將此專案視為 Release candidate 進行稽核。
請將稽核固定至目前的 commit。
請勿修改檔案、commit、push、deploy 或 release。
請以 Markdown 回傳結果。
```

當需求符合 description 時，Claude Code 也可能自動載入 Skill。

Claude Code 會監看既有 Skill directory 中的`SKILL.md`變更。若 session 啟動時 top-level Skills directory 尚不存在，請重新啟動 Claude Code。

## 10. ChatGPT 桌面版與 ChatGPT Web

OpenAI Skills 可用於 ChatGPT 桌面版、Codex CLI 與 Codex IDE extension。桌面版可從側邊欄的 Skills 畫面查看在各 project 中發現的 Skill。

目前版本不是公開 ChatGPT Plugin，因此無法在一般 ChatGPT Web 中一鍵安裝。

若需要在一般 Web 對話中暫時使用，可上傳`SKILL.md`與必要的 standard file，並要求 ChatGPT 將其視為稽核依據。

範例：

```text
請將附件中的 Agentic Change Audit SKILL.md 與 standard 視為本次稽核的正式依據。

請在不修改檔案的情況下稽核目前變更。
請記錄固定對象、已執行檢查、未執行檢查、finding、人工確認、一個 Verdict，以及下一個允許的動作。
```

這是暫時讀取文件的使用方式，不等同於已安裝 Skill 的自動偵測。

## 11. 建議的第一次測試

請先使用低風險的文件變更測試，不要直接從重要應用程式開始。

Codex：

```text
$agentic-change-audit

請使用 DOCS_ONLY 模式。
請稽核目前 branch 相對於 main 的變更。
請記錄 repository、base SHA、target HEAD 與變更檔案。
只執行相關且 read-only 的文件與 Git 檢查。
請勿修改檔案，並回傳 Markdown 稽核結果。
```

Claude Code：

```text
/agentic-change-audit

請使用 DOCS_ONLY 模式。
請稽核目前 branch 相對於 main 的變更。
請記錄 repository、base SHA、target HEAD 與變更檔案。
只執行相關且 read-only 的文件與 Git 檢查。
請勿修改檔案，並回傳 Markdown 稽核結果。
```

結果應確認：

- base 與 target identity 已固定
- 已記錄 review 的檔案
- 已記錄執行與未執行的檢查
- 已記錄 evidence limitation
- 僅使用一個允許的 Verdict
- 已記錄下一個允許的動作
- 已記錄稽核失效條件

## 12. 稽核模式

```text
FULL
依需求稽核完整變更

FOCUSED_REAUDIT
針對前次 finding 所授權的修正進行重新稽核

RELEASE
稽核固定的 Release candidate

DOCS_ONLY
只稽核文件變更，不要求無關的應用程式檢查
```

若應用程式是由 AI 快速製作，且開發過程沒有獨立稽核，通常應先固定目前狀態，再使用`RELEASE`模式。

## 13. Verdict

Agentic Change Audit 必須只回傳下列其中一個：

```text
PASS
必要檢查已完成，沒有剩餘的 blocking issue

PASS WITH COMMENTS
只剩不影響繼續進行的注意事項

CHANGES REQUESTED
接受前必須修改

BLOCKED
對象已固定，但無法完成必要檢查

NOT AUDITABLE
無法可靠固定對象或最低稽核條件
```

passing verdict 不是認證或保證。畫面、業務、privacy、付款、法律、破壞性操作、正式上線與最終核准等事項，仍需人工確認。

## 14. 權限邊界

稽核應從最低必要權限開始。

建議指示：

```text
稽核期間請以 read-only 方式工作。

請勿修改檔案、commit、push、approve、merge、deploy、release、
修改 database、執行真實付款或通知真實使用者。

請勿顯示秘密資訊的值，只回報可能存在的位置與類型。
```

稽核後的修正、merge、deploy 與 release，應視為另一個明確授權的步驟。

## 15. 更新

若使用固定的已稽核版本，請優先確認新的 Tag 或 Release asset，再替換目前套件，不要默默追蹤`main`。

Git 方式應先在另一個 directory 安裝並確認新版本，再替換共用套件。

copy 方式應完整替換整個 directory，避免新舊檔案混合。

只有在明確要追蹤開發版時才執行：

```bash
cd "$HOME/.local/share/agentic-change-audit"
git switch main
git pull --ff-only origin main
```

開發 branch 可能與已公開 Release candidate 不同。

## 16. 移除 Skill

移除 Codex symlink：

```bash
rm "$HOME/.agents/skills/agentic-change-audit"
```

移除 Claude Code symlink：

```bash
rm "$HOME/.claude/skills/agentic-change-audit"
```

這些指令只會移除 link。

刪除共用套件前，請先確認完整路徑：

```bash
printf '%s\n' "$HOME/.local/share/agentic-change-audit"
```

## 17. 疑難排解

### Skill 沒有顯示

```bash
test -f "$HOME/.agents/skills/agentic-change-audit/SKILL.md"
test -f "$HOME/.claude/skills/agentic-change-audit/SKILL.md"
```

請確認：

- directory 名稱為`agentic-change-audit`
- root 直接包含`SKILL.md`
- 套件沒有巢狀
- symlink 目標存在
- current user 有讀取權限
- 必要時已重新啟動 agent
- 在正確的 project 中啟動

查看 link：

```bash
ls -la "$HOME/.agents/skills/agentic-change-audit"
ls -la "$HOME/.claude/skills/agentic-change-audit"
```

### 沒有自動呼叫

請明確呼叫：

```text
Codex：
$agentic-change-audit

Claude Code：
/agentic-change-audit
```

### 顯示`Destination already exists`

請勿立即覆寫或刪除，先確認目前狀態。

```bash
ls -la "$HOME/.local/share/agentic-change-audit"
ls -la "$HOME/.agents/skills/agentic-change-audit"
ls -la "$HOME/.claude/skills/agentic-change-audit"
```

確認是舊版 copy、symlink 或其他安裝後，再進行受控替換。

## 18. 安全性與支援

安裝 Skill 等同於讓 AI Agent 載入新的操作指示。

啟用第三方 Skill 前：

- 檢查`SKILL.md`與參照檔案
- 確認 repository owner
- 確認版本、Tag、commit
- 限制 tool 權限
- 不要只因 JSON Schema 通過就判定稽核結果正確

本指南的固定公開 identity：

```text
Version：
v0.1.0-rc.1

Source commit：
f421571f25d090cbd7b5e387e82db86a688cd229

Tag object：
b81907105e477d50bfc35d8b723a6614916fa868
```

本專案以 as-is 方式提供，不承諾免費安裝支援、疑難排解、維護或回覆時限。專業導入與組織整合可能依另外的付費契約提供。

## 19. 官方參考資料

- [Agentic Change Audit repository](https://github.com/landco-llc/agentic-change-audit)
- [Agentic Change Audit v0.1.0-rc.1](https://github.com/landco-llc/agentic-change-audit/releases/tag/v0.1.0-rc.1)
- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code: Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Agent Skills specification](https://agentskills.io/specification)
