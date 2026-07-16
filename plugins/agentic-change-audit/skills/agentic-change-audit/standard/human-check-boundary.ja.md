# 人間確認境界

## ステータス

- バージョン: Draft 0.1
- 言語: 日本語
- 正本: いいえ
- 対応英語版: Draft 0.1
- 最終更新日: 2026-07-12

## 1. 目的

本書は、人間の責任または人間による確認が必要な判断・観測を定義します。

本標準は、人間が不要であるとは宣言しません。

## 2. 最終責任

関連プロジェクトまたは組織で権限を持つ人間が、次の最終判断に責任を持ちます。

- merge
- production deployment
- release
- 破壊的data operation
- security acceptance
- 法令・規制適合
- 契約上の義務
- privacy・personal data
- financial transaction・billing
- operational risk
- business acceptance

AIエージェントは判断を推奨できますが、組織権限を持つと主張してはなりません。

## 3. 必須の人間確認領域

次の領域へ実質的影響がある場合、原則として人間確認が必須です。

- production deployment
- data deletionまたは不可逆migration
- authentication・authorization behavior
- payment、billing、financial calculation
- personal information・confidential information
- 法令、規制、契約の解釈
- 重大security riskの受容
- 破壊的infrastructure action
- 外部公開されるbrand、copy、visual、accessibility品質
- safety-critical behavior
- 最終merge・release approval

組織は必須領域を追加できます。

## 4. 自動化が不十分となる条件

次に依存する場合、人間確認が必要です。

- 主観的visual judgment
- requirementsへ完全に符号化されていないbusiness intent
- legal authority
- production credentialまたはrestricted access
- customer-specific context
- ethicalまたはreputational judgment
- physical-world observation
- residual riskの受容
- irreversible action

## 5. 人間確認記録

各human checkには原則として次を記録します。

```text
Check:
Reason automation is insufficient:
Required role:
Status:
Evidence or observation:
Acceptance gate:
Owner:
```

使用可能なstatus:

- `COMPLETE`
- `PENDING`
- `NOT REQUIRED`
- `DEFERRED TO APPROVED GATE`

## 6. 判定への影響

- acceptance前に必須のcheckが`PENDING`の場合は`BLOCKED`
- `DEFERRED TO APPROVED GATE`は、現在のgateで不要な場合に限り`PASS WITH COMMENTS`を許容
- optional checkはblockせず記録可能
- 実装修正が必要なhuman check失敗は原則`CHANGES REQUESTED`

## 7. 禁止する主張

監査は次を主張してはなりません。

- 人間レビューが不要
- 法令適合が認証された
- securityが保証された
- 必須権限なしにproduction deploymentが安全
- 観測なしに主観的visual resultが正しい
- AIエージェントが組織riskを受容した

## 8. 役割分離

実務上可能な場合、重大変更の実装者だけを最終承認者とすべきではありません。

high-risk changeでは、次を分離することを推奨します。

- implementation
- audit
- business approval
- deployment authorization

この分離は推奨事項であり、OSSコアの必須要件ではありません。

## 9. 有償業務との境界

有償の実装支援またはconsultingを提供しても、書面契約で明示しない限り、顧客の最終権限・責任は移転しません。
