# Agentic Change Audit — Codex Plugin（development preview）

[English](README.md) | [繁體中文](README.zh-Hant.md)

## ステータス

**Development preview。** これはAgentic Change Auditの最初のinstallable Codex Plugin基盤です。**skills-only Plugin**であり、既存のAgentic Change Audit Skillを同梱し、direct Skill folderだけでなく、repository限定のlocal marketplaceからもinstallできるようにします。

このdevelopment PluginはOpenAIの公開Plugins Directoryへ申請・登録・公開されていません。公開申請資料、publisher identity verification、Directory掲載は後続phaseであり、この基盤の対象外です。

## このPluginが提供するもの

- **skills-only**なpackage：`.codex-plugin/plugin.json`と、`skills/agentic-change-audit/`配下に同梱したSkill。
- 同梱Skillは、build元のcommit時点のrepository root正本Skillソースとbyte単位で一致します。
- 監査workflow自体は変更していません。Evidence-first、agent-neutral、既定でread-onlyです。

## このPluginが提供しないもの

- **MCP serverなし。** `.mcp.json`および`mcpServers`エントリはありません。
- **ChatGPT appまたはconnectorなし。** `.app.json`および`apps`エントリはありません。
- **lifecycle hooksなし。** `hooks/`ディレクトリおよび`hooks`エントリはありません。
- **authentication flowなし。** manifestはlogin・token交換を宣言していません。
- **telemetryなし。** このPluginはどこにも利用状況・analytics・eventを送信しません。
- **書き込み可能なtoolなし。** manifestが宣言するcapabilityは`Read`のみです。

`~/.claude/skills/`または`~/.agents/skills/`へrepositoryをcopyまたはsymlinkするdirect Skill installationは、このPluginによって置き換えられることなく、引き続き利用できます。この方式は[導入ガイド](https://github.com/landco-llc/agentic-change-audit/tree/main/guides)を参照してください。

## Local marketplaceでのテスト

repositoryをcloneし、local Plugin marketplace sourceとして登録します。

```bash
git clone \
  https://github.com/landco-llc/agentic-change-audit.git

cd agentic-change-audit

codex plugin marketplace add .
codex plugin marketplace list
```

`codex plugin marketplace add .`は、現在のrepositoryの`.agents/plugins/marketplace.json`を、`landco-llc-open-source`という名前のlocal marketplace sourceとして登録します。これだけではPluginはinstallされず、外部serviceへの通信も発生しません。

## ChatGPT desktopでのinstallとテスト

1. marketplaceを追加・更新した後は、ChatGPT desktop appを再起動して新しいsourceを反映させます。
2. **Plugins**を開きます。
3. **L&Co.LLC Open Source**のmarketplaceを選択します。
4. **Agentic Change Audit**をinstallします。
5. 新しいtaskを開始し、Pluginを呼び出してテストします。

これらの手順をChatGPT desktop UIで実際に再現することは**PENDING HUMAN CHECK**です。このrepository自体が自動的に実行・保証できるものではありません。

## このbranchがmerge後にGitHubから直接登録する

このPlugin基盤が`main`へmergeされた後は、local cloneなしでGitHubから直接marketplaceを追加することもできます。

```bash
codex plugin marketplace add \
  landco-llc/agentic-change-audit \
  --ref main
```

それまでは、このbranchのcheckoutに対して上記のlocal `codex plugin marketplace add .`コマンドを使用してください。

## 呼び出し例

```text
$agentic-change-audit

現在のrepositoryの変更を監査してください。
現在のbaseとtarget HEADへ監査を固定してください。
fileは変更しないでください。
Markdownで返してください。
```

```text
Agentic Change Auditを使用して、このAIが構築したapplicationをrelease candidateとして監査してください。

不足しているevidence、finding、human check、1つのVerdict、
次に許可されるactionを記録してください。
変更、deploy、releaseは行わないでください。
```

## Read-only監査境界

同梱Skillは監査を行いますが、actionは実行しません。Pluginが宣言するcapabilityは`Read`のみであり、監査workflow自体も、監査phase中にfileの変更、commit、push、承認、merge、deploy、releaseを行わないよう指示しています。監査後にユーザーが要求する状態変更actionは、監査とは別に明示的に承認された手順として扱います。

## 組織的な権限は付与しない

このPluginをinstallしても、agentやPluginにapproval、merge、deployment、release権限は付与されません。PASSという判定は判断支援であり、その権限を持つ人間の代替ではありません。

## セキュリティ・法務・本番の保証はない

このPlugin経由で生成される監査結果は、セキュリティ認証、法律意見、規制適合認証、本番安全性の保証ではありません。視覚確認、事業判断、個人情報、決済、法務、破壊操作、deploy、最終承認など、該当する場合は引き続き人間確認が必要です。

## Version

このPluginはdevelopment version識別子`0.1.0-dev.1`を使用します。公開releaseや安定版Pluginではなく、tag付けされたSkill releaseにも対応していません。

## 関連文書

- [Repository README](https://github.com/landco-llc/agentic-change-audit/blob/main/README.ja.md)
- [導入ガイド](https://github.com/landco-llc/agentic-change-audit/tree/main/guides)
- [正本Skill（`SKILL.md`）](https://github.com/landco-llc/agentic-change-audit/blob/main/SKILL.md)
- [License](https://github.com/landco-llc/agentic-change-audit/blob/main/LICENSE)
