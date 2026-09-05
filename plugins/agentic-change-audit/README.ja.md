# Agentic Change Audit — Codex Plugin（development preview）

[English](README.md) | [繁體中文](README.zh-Hant.md)

## ステータス

**Development preview。** これはAgentic Change Auditの最初のinstallable Codex Plugin基盤です。**skills-only Plugin**であり、既存のAgentic Change Audit Skillを同梱し、direct Skill folderだけでなく、repository限定のlocal marketplaceからもinstallできるようにします。

この development preview は、neutral な **Agentic Change Audit marketplace** identity と Plugin version `0.1.0-dev.3` を使用します。

## Development ステータス

- **Phase C の desktop 証跡は保留中です。** 以前の desktop 証跡は履歴上のものであり、旧 marketplace identity と Plugin version を対象にしたため、neutral な **Agentic Change Audit marketplace** と Plugin version `0.1.0-dev.3` へ移転できません。この repository には Phase C の desktop 確認は記録されていません。保留中の証跡には marketplace 登録、発見、install、明示呼び出し、Git working tree 非変更確認が含まれます。
- **Human prerequisite は保留中です。** repository の資料は identity verification、logo 承認、その他の人間による判断を満たすことはできません。
- **Repository 側のテストには local marketplace を使用します。**
  [Support](https://github.com/landco-llc/agentic-change-audit/blob/main/SUPPORT.md) と
  [Privacy](https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md) は
  repository の境界を記載しています。

repository 側の準備資料は
[package directory](https://github.com/landco-llc/agentic-change-audit/tree/main/submission/codex-plugin) にあります。

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

`codex plugin marketplace add .`は、現在のrepositoryの`.agents/plugins/marketplace.json`を、`agentic-change-audit`という名前のlocal marketplace sourceとして登録します。これだけではPluginはinstallされず、外部serviceへの通信も発生しません。

## ChatGPT desktopでのinstallとテスト

1. marketplaceを追加・更新した後は、ChatGPT desktop appを再起動して新しいsourceを反映させます。
2. **Plugins**を開きます。
3. **Agentic Change Audit marketplace**を選択します。
4. **Agentic Change Audit**をinstallします。
5. 新しいtaskを開始し、Pluginを呼び出してテストします。

これらの手順をChatGPT desktop UIで実際に再現することは**PENDING HUMAN CHECK**です。このrepository自体が自動的に実行・保証できるものではありません。

## Phase A 後に GitHub から直接登録する

Phase A は merge 済みです。local clone なしで GitHub から marketplace を追加できます。

```bash
codex plugin marketplace add \
  landco-llc/agentic-change-audit \
  --ref main
```

Phase C の desktop 証跡はまだ保留中です。このcommand は別途行う確認の手順であり、確認済みであることを示すものではありません。

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

このPluginはdevelopment version識別子`0.1.0-dev.3`を使用します。公開releaseや安定版Pluginではなく、tag付けされたSkill releaseにも対応していません。

## 関連文書

- [Repository README](https://github.com/landco-llc/agentic-change-audit/blob/main/README.ja.md)
- [導入ガイド](https://github.com/landco-llc/agentic-change-audit/tree/main/guides)
- [正本Skill（`SKILL.md`）](https://github.com/landco-llc/agentic-change-audit/blob/main/SKILL.md)
- [サポート](https://github.com/landco-llc/agentic-change-audit/blob/main/SUPPORT.md)
- [プライバシー](https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md)
- [申請パッケージ](https://github.com/landco-llc/agentic-change-audit/tree/main/submission/codex-plugin)
- [License](https://github.com/landco-llc/agentic-change-audit/blob/main/LICENSE)
