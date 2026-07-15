# インストール・導入・設定・利用ガイド

[English](../en/installation.md) | [繁體中文](../zh-Hant/installation.md)

- 言語: 日本語
- 最終確認日: 2026-07-15
- 対象公開版: `v0.1.0-rc.1`
- 直接導入の対象: Claude Code、OpenAI Codex
- パッケージ名: `agentic-change-audit`
- 状態: プレリリース

## 1. Agentic Change Auditとは

Agentic Change Auditは、人がmerge、release、deployを判断する前に、AIエージェントや人が行ったソフトウェア変更を監査するためのオープンソースAgent Skillです。

主な対象:

- Pull Requestと固定commit
- ローカルの未commit変更
- Release候補
- AI生成、人間作成、両者が混在する変更
- アプリ、Webサイト、業務自動化、設定、インフラ、データ移行、外部部品、文書

AIの「確認した」「問題ない」という説明だけに依存せず、監査対象、実行した確認、実行していない確認、残っている問題、人による確認事項、最終Verdictを記録します。

このSkillは判断を支援しますが、人の最終権限を置き換えません。また、セキュリティ、法令、本番安全性などの認証や保証ではありません。

## 2. 現段階の対応範囲

`v0.1.0-rc.1`では、次の環境向けに直接導入手順を用意しています。

- Claude Code
- OpenAI Codex

中核仕様は特定のAI会社に依存しませんが、現行版では次をまだ提供していません。

- Codex Plugin package
- Claude Code Plugin package
- ChatGPT Webへのワンクリック導入
- Custom GPT
- Gemini CLI専用package
- GitHub Copilot専用package

OpenAIのdirect Skill folderは、ローカル利用とrepository単位の利用に向く方式です。Workspaceへ再利用可能な形で配布する場合、OpenAIはPlugin化を推奨しています。Agentic Change Auditは現時点でPluginを同梱していません。

## 3. 正しいパッケージ構造

有効な導入状態では、root直下に`SKILL.md`があります。

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

root folderへVersionを付けないでください。

```text
正しい:
agentic-change-audit/

誤り:
agentic-change-audit-0.1.0-rc.1/
```

次のような入れ子も避けます。

```text
agentic-change-audit/
└── agentic-change-audit/
    └── SKILL.md
```

## 4. 公開sourceとRelease

Repository:

```text
https://github.com/landco-llc/agentic-change-audit
```

Release:

```text
https://github.com/landco-llc/agentic-change-audit/releases/tag/v0.1.0-rc.1
```

公開済みasset:

```text
agentic-change-audit-0.1.0-rc.1.zip
agentic-change-audit-0.1.0-rc.1.manifest.json
agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

公開済みSHA-256:

```text
0e9fe576b2db43e29817df0a15d5e1eea2c07eeb8a0843c0b88117d81ac270ac  agentic-change-audit-0.1.0-rc.1.zip
df12de142bc2e6207d3325902043a81563e6429bd783405cde8749c62a6edffe  agentic-change-audit-0.1.0-rc.1.manifest.json
57327a19cecfc01ce5da924b0d02735b046dbddcffc2673fc70da50ea0e2c6bb  agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

GitHubが自動生成する`Source code (zip)`と`Source code (tar.gz)`は、runtime Skill archiveではありません。上記3件のRelease assetを使用してください。

## 5. 推奨する共有source構成

次の構成が分かりやすく、CodexとClaude CodeのVersionずれを抑えられます。

```text
共有package:
~/.local/share/agentic-change-audit/

Codex:
~/.agents/skills/agentic-change-audit
    -> ~/.local/share/agentic-change-audit/

Claude Code:
~/.claude/skills/agentic-change-audit
    -> ~/.local/share/agentic-change-audit/
```

## 6. Gitで固定Releaseを導入する

Gitを利用でき、公開Tagのsourceを固定して使いたい場合の手順です。

既存の配置先がないことを確認します。

```bash
test ! -e "$HOME/.local/share/agentic-change-audit" \
  && test ! -L "$HOME/.local/share/agentic-change-audit"
```

固定Tagをcloneします。

```bash
mkdir -p "$HOME/.local/share"

git clone \
  --branch v0.1.0-rc.1 \
  --depth 1 \
  https://github.com/landco-llc/agentic-change-audit.git \
  "$HOME/.local/share/agentic-change-audit"
```

identityを確認します。

```bash
cd "$HOME/.local/share/agentic-change-audit"

git describe --tags --exact-match
git rev-parse HEAD
git status --short
```

期待値:

```text
Tag:
v0.1.0-rc.1

Commit:
f421571f25d090cbd7b5e387e82db86a688cd229

Working tree:
clean
```

Skill entrypointを確認します。

```bash
test -f "$HOME/.local/share/agentic-change-audit/SKILL.md" \
  && echo "Agentic Change Audit package: OK"
```

## 7. Release ZIPから導入する

監査済み配布archiveを固定利用したい場合の方法です。

Releaseページから3件のassetをdownloadするか、GitHub CLIを使用します。

```bash
mkdir -p "$HOME/Downloads/agentic-change-audit-v0.1.0-rc.1"
cd "$HOME/Downloads/agentic-change-audit-v0.1.0-rc.1"

gh release download v0.1.0-rc.1 \
  --repo landco-llc/agentic-change-audit \
  --pattern 'agentic-change-audit-0.1.0-rc.1.zip' \
  --pattern 'agentic-change-audit-0.1.0-rc.1.manifest.json' \
  --pattern 'agentic-change-audit-0.1.0-rc.1.SHA256SUMS'
```

checksumを確認します。

macOS:

```bash
shasum -a 256 -c agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

Linux:

```bash
sha256sum -c agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

記載された2fileが`OK`になることを確認します。

展開とentrypoint確認:

```bash
unzip agentic-change-audit-0.1.0-rc.1.zip

test -f agentic-change-audit/SKILL.md \
  && echo "Skill package: OK"
```

共有配置先が未使用であることを確認してから移動します。

```bash
mkdir -p "$HOME/.local/share"

mv agentic-change-audit \
  "$HOME/.local/share/agentic-change-audit"
```

## 8. Codexへ導入する

### 8.1 全projectで使用する

```bash
mkdir -p "$HOME/.agents/skills"

destination="$HOME/.agents/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf '導入先がすでに存在します: %s\n' "$destination" >&2
else
  ln -s \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

確認:

```bash
test -f "$HOME/.agents/skills/agentic-change-audit/SKILL.md" \
  && echo "Codex Skill: OK"
```

### 8.2 特定repositoryだけで使用する

対象repositoryのrootで実行します。

```bash
mkdir -p .agents/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .agents/skills/agentic-change-audit
```

端末固有の絶対pathを持つsymlinkを、共有repositoryへcommitしないでください。チーム共有では、repository相対の構成または管理されたcopy方式を利用します。

### 8.3 Codexで呼び出す

監査対象repository内でCodexを起動します。

明示呼出し:

```text
$agentic-change-audit

現在のprojectを監査してください。
現在のcommitとeffective diffへ監査を固定してください。
file変更、commit、push、merge、deploy、releaseは行わないでください。
Markdownで結果を返してください。
```

ほかに次の方法があります。

- `/skills`を実行
- `$`を入力して`agentic-change-audit`を選択
- prompt内でSkill名を明示
- 依頼内容がdescriptionと一致した場合の自動選択

新規導入したSkillが表示されない場合はCodexを再起動します。

### 8.4 Codexで一時無効化する

`~/.codex/config.toml`へ追加します。

```toml
[[skills.config]]
path = "/absolute/path/to/.agents/skills/agentic-change-audit/SKILL.md"
enabled = false
```

設定変更後にCodexを再起動します。

## 9. Claude Codeへ導入する

### 9.1 Version確認

symlinkされたSkill directoryはClaude Code `v2.1.203`以降で利用できます。

```bash
claude --version
```

古いVersionではcopy方式を使うか、Claude Codeを更新します。

### 9.2 個人Skillとしてsymlink導入する

```bash
mkdir -p "$HOME/.claude/skills"

destination="$HOME/.claude/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf '導入先がすでに存在します: %s\n' "$destination" >&2
else
  ln -s \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

確認:

```bash
test -f "$HOME/.claude/skills/agentic-change-audit/SKILL.md" \
  && echo "Claude Code Skill: OK"
```

### 9.3 symlinkを使えない場合

```bash
mkdir -p "$HOME/.claude/skills"

destination="$HOME/.claude/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf '導入先がすでに存在します: %s\n' "$destination" >&2
else
  cp -R \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

既存のcopy先へ`cp -R`を再実行しないでください。古いfileが残ったり、packageが入れ子になる可能性があります。更新時はdirectory全体を管理された手順で置換します。

### 9.4 特定projectだけで使用する

対象projectのrootで実行します。

```bash
mkdir -p .claude/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .claude/skills/agentic-change-audit
```

端末固有の絶対pathを含むsymlinkを共有repositoryへcommitしないでください。

### 9.5 Claude Codeで呼び出す

```bash
cd /path/to/project
claude
```

明示呼出し:

```text
/agentic-change-audit

このprojectをRelease候補として監査してください。
現在のcommitへ監査を固定してください。
file変更、commit、push、deploy、releaseは行わないでください。
Markdownで結果を返してください。
```

依頼内容がdescriptionと一致する場合、Claude Codeが自動でSkillを読み込むこともあります。

Claude Codeは既存Skill directory内の`SKILL.md`変更を監視します。session開始時にtop-level Skills directoryが存在しなかった場合は再起動してください。

## 10. ChatGPTデスクトップとChatGPT Web

OpenAI Skillsは、ChatGPTデスクトップアプリ、Codex CLI、Codex IDE extensionで利用できます。デスクトップアプリでは、sidebarのSkills画面からproject内などで検出されたSkillを確認できます。

現行版は公開ChatGPT Pluginではなく、通常のChatGPT Webへワンクリックで追加することはできません。

通常Webチャットで一時的に使う場合は、`SKILL.md`と必要なstandard fileを添付し、監査正本として使用するよう依頼します。

例:

```text
添付したAgentic Change AuditのSKILL.mdとstandardを監査正本として使用してください。

現在の変更を、fileを修正せずに監査してください。
固定対象、実行した確認、実行していない確認、finding、人による確認、1つのVerdict、次に許可される行為を記録してください。
```

これは文書を一時的に読ませる利用方法であり、導入済みSkillとしての自動検出とは異なります。

## 11. 最初の動作確認

重要なアプリではなく、低リスクな文書変更から試します。

Codex:

```text
$agentic-change-audit

DOCS_ONLYモードを使用してください。
現在branchをmainに対して監査してください。
repository、base SHA、target HEAD、変更fileを記録してください。
関連するread-onlyの文書確認とGit確認だけを実行してください。
fileは変更せず、Markdown監査結果を返してください。
```

Claude Code:

```text
/agentic-change-audit

DOCS_ONLYモードを使用してください。
現在branchをmainに対して監査してください。
repository、base SHA、target HEAD、変更fileを記録してください。
関連するread-onlyの文書確認とGit確認だけを実行してください。
fileは変更せず、Markdown監査結果を返してください。
```

結果で確認する項目:

- baseとtarget identityが固定されている
- review対象fileが記録されている
- 実行した確認と未実行確認が記録されている
- evidence limitationが記録されている
- 許可されたVerdictを1つだけ使っている
- 次に許可される行為が記録されている
- 監査失効条件が記録されている

## 12. 監査モード

```text
FULL
要件に対して変更全体を監査

FOCUSED_REAUDIT
前回監査の指摘に対する許可された修正を再監査

RELEASE
固定されたRelease候補を監査

DOCS_ONLY
文書変更だけを、無関係なapplication checkなしで監査
```

AIで途中監査なしに急いで作ったアプリは、現在状態を固定して`RELEASE`モードで監査する方法が基本です。

## 13. Verdict

必ず次のいずれか1つを返します。

```text
PASS
必要な確認が完了し、blocking issueが残っていない

PASS WITH COMMENTS
進行を止めない注意事項だけが残っている

CHANGES REQUESTED
受け入れ前に修正が必要

BLOCKED
対象は固定できたが、必要な確認を完了できない

NOT AUDITABLE
対象または最低限の監査条件を確実に固定できない
```

passing verdictは認証や保証ではありません。画面、業務、privacy、決済、法務、破壊的操作、本番反映、最終承認などでは、人による確認が必要です。

## 14. 権限境界

監査は必要最小限の権限で開始してください。

推奨する指示:

```text
監査中はread-onlyで作業してください。

file変更、commit、push、approve、merge、deploy、release、
database変更、実決済、実在ユーザーへの通知を行わないでください。

秘密情報の値は表示せず、存在する可能性のある場所と種類だけ報告してください。
```

監査後の修正、merge、deploy、releaseは、別の明示された作業として扱います。

## 15. 更新

固定された監査済みVersionでは、`main`を自動追跡するより、新しいTagまたはRelease assetを別に確認してから置換してください。

Git方式では、次Versionを別directoryで導入・確認してから共有packageを置換します。

copy方式ではdirectory全体を置換し、新旧fileを混在させないでください。

開発版の`main`を意図的に追跡する場合のみ:

```bash
cd "$HOME/.local/share/agentic-change-audit"
git switch main
git pull --ff-only origin main
```

開発branchは公開Release候補と異なる可能性があります。

## 16. Skillを外す

Codexのsymlink:

```bash
rm "$HOME/.agents/skills/agentic-change-audit"
```

Claude Codeのsymlink:

```bash
rm "$HOME/.claude/skills/agentic-change-audit"
```

これらはlinkだけを削除します。

共有packageを削除する前に、正確なpathを確認します。

```bash
printf '%s\n' "$HOME/.local/share/agentic-change-audit"
```

## 17. トラブルシューティング

### Skillが表示されない

```bash
test -f "$HOME/.agents/skills/agentic-change-audit/SKILL.md"
test -f "$HOME/.claude/skills/agentic-change-audit/SKILL.md"
```

次を確認します。

- directory名が`agentic-change-audit`
- root直下に`SKILL.md`がある
- packageが入れ子ではない
- symlink先が存在する
- current userにread権限がある
- 必要に応じてagentを再起動した
- 正しいprojectで起動している

link確認:

```bash
ls -la "$HOME/.agents/skills/agentic-change-audit"
ls -la "$HOME/.claude/skills/agentic-change-audit"
```

### 自動で呼び出されない

明示的に呼び出します。

```text
Codex:
$agentic-change-audit

Claude Code:
/agentic-change-audit
```

### `Destination already exists`と表示される

すぐに上書きや削除をせず、現在状態を確認します。

```bash
ls -la "$HOME/.local/share/agentic-change-audit"
ls -la "$HOME/.agents/skills/agentic-change-audit"
ls -la "$HOME/.claude/skills/agentic-change-audit"
```

古いcopy、symlink、別導入のどれかを判断してから置換します。

## 18. セキュリティとサポート

Skillの導入は、AIエージェントへ運用指示を読み込ませる行為です。

第三者Skillを有効にする前に:

- `SKILL.md`と参照fileを確認
- repository ownerを確認
- Version、Tag、commitを確認
- tool権限を制限
- JSON Schemaに適合しただけで監査結果が正しいと判断しない

本ガイドの固定公開identity:

```text
Version:
v0.1.0-rc.1

Source commit:
f421571f25d090cbd7b5e387e82db86a688cd229

Tag object:
b81907105e477d50bfc35d8b723a6614916fa868
```

本projectはas-isで提供されます。無償の導入支援、troubleshooting、保守、回答期限は保証しません。専門的な導入支援や組織統合は、別契約の有償serviceとして提供される場合があります。

## 19. 公式参照先

- [Agentic Change Audit repository](https://github.com/landco-llc/agentic-change-audit)
- [Agentic Change Audit v0.1.0-rc.1](https://github.com/landco-llc/agentic-change-audit/releases/tag/v0.1.0-rc.1)
- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code: Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Agent Skills specification](https://agentskills.io/specification)
