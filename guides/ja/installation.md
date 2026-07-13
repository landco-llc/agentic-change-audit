# 導入・利用ガイド

- 言語: 日本語
- 最終確認日: 2026-07-13
- 初期対応エージェント: Claude Code、Codex
- パッケージ名: `agentic-change-audit`

## 重要な前提

このGitHub repository自体がSkillパッケージのディレクトリです。

有効な導入状態は次の形です。

```text
agentic-change-audit/
├── SKILL.md
├── standard/
├── templates/
└── ...
```

任意のフォルダへcloneしただけでは、Skillとして自動検出されません。repositoryフォルダ全体を、エージェントが対応する検出先へcopyまたはlinkする必要があります。

本ガイドは**local direct-folder installation**の手順です。Codexのdirect Skill folderはlocal authoringとdiscoveryを目的とします。単一repositoryを超えて再利用配布する場合、CodexはPluginを推奨しています。本repositoryは現時点でCodex Pluginを提供していません。

以下では、Claude CodeとCodexが同じファイルを利用できるように、共有source checkoutを使用します。

コマンド例はmacOSまたはLinuxのPOSIX shellを前提とします。他のOSでは同等のdirectory copyまたはdirectory linkを使用してください。

## 1. Sourceパッケージをcloneする

```bash
mkdir -p "$HOME/.local/share"

git clone \
  https://github.com/landco-llc/agentic-change-audit.git \
  "$HOME/.local/share/agentic-change-audit"
```

確認:

```bash
test -f "$HOME/.local/share/agentic-change-audit/SKILL.md"
```

第三者のSkillを有効化する前に、repositoryの内容を確認してください。

## Claude Code

Claude Codeの個人Skill配置先:

```text
~/.claude/skills/<skill-name>/SKILL.md
```

プロジェクトSkill配置先:

```text
<project>/.claude/skills/<skill-name>/SKILL.md
```

依頼内容がdescriptionと一致する場合は自動選択でき、`/skill-name`で明示呼出しもできます。

### 2A. Symlinkによる個人導入

全プロジェクトで使用する場合:

```bash
mkdir -p "$HOME/.claude/skills"

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  "$HOME/.claude/skills/agentic-change-audit"
```

Claude Code v2.1.203以降は、symlinkされたSkill directoryを読み取ります。それより古いversionでは、下記のcopy方式を使用するかClaude Codeを更新してください。

### 2B. Copyによる個人導入

環境上symlinkを使用できない場合:

```bash
mkdir -p "$HOME/.claude/skills"

destination="$HOME/.claude/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf '導入先がすでに存在します。copy前に移動または削除してください: %s\n' \
    "$destination" >&2
else
  cp -R \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

copyした導入先は、source checkoutを更新しても自動では更新されません。既存の導入先へ`cp -R`を再実行すると、入れ子のpackageが作られ、古いroot `SKILL.md`が残る可能性があります。管理された更新手順で既存copyを置き換えてください。

### 2C. プロジェクト限定導入

対象プロジェクトのルートで実行:

```bash
mkdir -p .claude/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .claude/skills/agentic-change-audit
```

絶対pathを含む端末固有のsymlinkを、共有repositoryへcommitしないでください。チーム共有の場合はパッケージをcopyするか、チームに適したrepository相対の配布方式を別途定義してください。

### 3. Claude Codeで確認する

Gitプロジェクト内でClaude Codeを起動:

```bash
claude
```

明示呼出し:

```text
/agentic-change-audit
```

または、descriptionに一致する依頼を行います。

```text
Agentic Change Auditで現在のPull Requestを監査してください。
live target HEADへ結果を固定し、PRは変更しないでください。
```

Claude Codeは既存Skill directoryの変更を監視します。新しく作成したtop-level Skill directoryが検出されない場合は、Claude Codeを再起動してください。

## Codex

CodexのユーザーSkill配置先:

```text
$HOME/.agents/skills/<skill-name>/SKILL.md
```

repository Skill配置先:

```text
<repository>/.agents/skills/<skill-name>/SKILL.md
```

Codexはcurrent working directoryからrepository rootまでの`.agents/skills`を走査し、symlinkされたSkill folderにも対応します。

### 4A. Symlinkによるユーザー導入

```bash
mkdir -p "$HOME/.agents/skills"

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  "$HOME/.agents/skills/agentic-change-audit"
```

### 4B. Copyによるユーザー導入

```bash
mkdir -p "$HOME/.agents/skills"

destination="$HOME/.agents/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf '導入先がすでに存在します。copy前に移動または削除してください: %s\n' \
    "$destination" >&2
else
  cp -R \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

既存の導入先へ`cp -R`を再実行しないでください。Skill rootへ古いfileが残ったり、入れ子の`agentic-change-audit/` directoryが作られたりしないよう、管理された置換を行ってください。

### 4C. Repository限定導入

対象repositoryのルートで実行:

```bash
mkdir -p .agents/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .agents/skills/agentic-change-audit
```

絶対pathを含む端末固有のsymlinkを、共有repositoryへcommitしないでください。

### 5. Codexで確認する

Git repository内でCodexを起動します。

`/skills`で利用可能なSkillを確認するか、`$`を入力して`agentic-change-audit`を選択します。

依頼例:

```text
$agentic-change-audit

issue #98を要件正本としてPR #123を監査してください。
liveのbase SHAとtarget HEADへ監査を固定してください。
repositoryやPRは変更せず、Markdownで結果を返してください。
```

依頼内容がdescriptionと一致する場合、Codexが自動選択することもあります。新しく導入したSkillが表示されない場合はCodexを再起動してください。

## 6. 最初のテスト方法

低リスクなドキュメントのみの変更で試してください。

```text
Agentic Change AuditをDOCS_ONLYモードで使用してください。

現在branchをmainに対して監査してください。
repository、base SHA、target HEAD、変更fileを記録してください。
関連するread-onlyのdocumentation checkとgit checkを実行してください。
fileは変更せず、Markdown監査テンプレートで返してください。
```

結果が次を満たすことを確認します。

- baseとtarget HEADが固定されている
- review対象fileが記録されている
- 実行commandと未実行checkが記録されている
- 証跡上の制限が記録されている
- 許可されたVerdictを1つだけ使用している
- 次に許可される行為が記録されている
- 監査失効条件が記録されている

## 7. 更新

共有source checkoutを更新:

```bash
cd "$HOME/.local/share/agentic-change-audit"

git pull --ff-only origin main
```

Symlink方式では、エージェントが再読込した後に更新内容が反映されます。

Copy方式では、通常の管理された更新手順でcopy先を置き換えてください。新旧fileを混在させないでください。

## 8. Skillを外す

Symlinkによる個人・ユーザー導入の場合:

### Claude Code

```bash
rm "$HOME/.claude/skills/agentic-change-audit"
```

### Codex

```bash
rm "$HOME/.agents/skills/agentic-change-audit"
```

これらはlinkだけを削除し、共有source checkoutは削除しません。

削除commandの実行前に、対象pathを確認してください。

## 9. トラブルシューティング

### Skillが一覧に表示されない

確認:

```bash
test -f "$HOME/.claude/skills/agentic-change-audit/SKILL.md"
test -f "$HOME/.agents/skills/agentic-change-audit/SKILL.md"
```

続いて確認します。

- directory名が`agentic-change-audit`か
- package rootに`SKILL.md`があるか
- エージェントを再起動したか
- 正しいユーザーとhome directoryを利用しているか
- link先が存在するか
- エージェントにread権限があるか

### 自動でSkillが選択されない

まず明示的に呼び出してください。

Claude Code:

```text
/agentic-change-audit
```

Codex:

```text
`$`を入力して`agentic-change-audit`を選択
```

自動選択は、依頼内容とSkill descriptionの一致に依存します。

### Repositoryをcloneしたが利用できない

対応する検出先以外へのcloneはsource checkoutです。フォルダ全体を適切なSkill配置先へlinkまたはcopyしてください。

## 10. セキュリティと権限

Skillの導入は、AIエージェントへ運用指示を読み込ませる行為です。

利用前に次を行ってください。

- `SKILL.md`と参照fileを確認する
- repository ownerと利用versionまたはcommitを確認する
- エージェントのtool権限を適切に制限する
- JSON Schemaへ適合しているだけで監査結果が正しいと判断しない

本Skillは、組織上のapprove、merge、deploy、release権限をAIへ付与しません。

## 11. サポート

本プロジェクトは現状有姿で提供します。

無償の導入支援、トラブルシューティング、回答期限保証、継続保守は提供しません。

専門的な導入支援および組織統合は、別途契約による有償業務として提供する場合があります。

## 公式資料

- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code skills documentation](https://code.claude.com/docs/en/skills)
- [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills)
