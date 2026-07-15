# Agentic Change Audit 標準

## ステータス

- バージョン: Draft 0.1
- 言語: 日本語
- 正本: いいえ
- 対応英語版: Draft 0.1
- 最終更新日: 2026-07-12

## 1. 目的

Agentic Change Auditは、ソフトウェア変更を受け入れ、マージし、デプロイし、またはリリースする次工程へ進められる状態かを判断するための、ベンダー非依存かつEvidence-firstな監査方法を定義します。

本標準は、個々のコード行の品質だけでなく、変更全体を評価します。

## 2. 規範用語

**MUST**、**MUST NOT**、**SHOULD**、**SHOULD NOT**、**MAY**を規範用語として使用します。

- **MUST / MUST NOT**: 適合のために必須。
- **SHOULD / SHOULD NOT**: 文書化された合理的理由がない限り推奨。
- **MAY**: 任意。

判定名、Severity名、schema上の値は英語表記を正とします。

## 3. 適用対象

本標準は次に適用できます。

- Pull Request
- ローカルworking treeの変更
- リリース候補
- ドキュメントのみの変更
- アプリケーションコード
- 設定
- インフラ
- データベースおよびmigration
- 人間が作成した変更
- AIが生成した変更
- 人間とAIによる混合作業

## 4. 監査契約

監査は、以下をすべて特定できる場合にのみ有効です。

1. repositoryの同一性
2. base参照
3. target branchまたは変更セット
4. target commit SHAまたは同等の不変識別子
5. 変更指示、要件、または承認済みの意図
6. 期待される変更範囲
7. 実際のdiff
8. 必須検証
9. 利用可能な証跡
10. 人間確認要件

結果を変え得る不足情報を、監査者が推測で補ってはなりません。

## 5. 中核原則

### 5.1 Evidence First

主張は、確認可能な証跡によって裏付けられなければなりません。確信、慣れ、AIエージェント自身の申告は証跡の代替になりません。

### 5.2 Agent Neutral

本標準は、異なるAIエージェントおよび人間のレビュー担当者が利用できる状態を維持します。エージェント固有の指示は統合層に置き、規範となるコア仕様へ混在させません。

### 5.3 Fixed Target Identity

すべての監査結果を特定の対象へ結び付けます。Pull Request番号だけでは不十分です。

### 5.4 Explicit Scope Control

依頼された変更と実際のdiffを比較し、未実施、範囲外変更、不要ファイル、過剰実装を識別します。

### 5.5 Audit Invalidation

固定したtarget、base依存のdiff、要件、必須証跡が実質的に変わった場合、監査結果を失効扱いにします。

### 5.6 Explicit Stop Conditions

監査対象または証跡を信頼できる形で確立できない場合、無理に判定せず停止します。

### 5.7 Human Responsibility

本標準は意思決定を支援します。マージ、デプロイ、リリース、セキュリティ、法務、運用の最終責任を移転するものではありません。

## 6. 必須監査フェーズ

### Phase 1: 対象同一性の確立

次を確認します。

- repository
- base
- target branch
- target HEAD
- 該当する場合はPull Requestの同一性
- working treeがcleanかdirtyか
- 取得したdiffが意図した対象と一致するか

対象同一性を確立できない場合は`NOT AUDITABLE`です。

### Phase 2: 要求範囲の確立

次を特定します。

- 要件の出典
- 要求されたファイル、挙動、制約
- 禁止された変更
- 必須チェック
- 必須の人間確認
- 明示された停止条件

信頼できる要件または承認済みの意図が存在しない場合は`NOT AUDITABLE`です。

### Phase 3: 実変更の確認

diff全体を確認し、影響領域を分類します。

- アプリケーション挙動
- 公開インターフェース
- 認証・認可
- データ・migration
- 依存関係
- 設定
- インフラ・デプロイ
- テスト
- ドキュメント
- 生成ファイル・機密ファイル

### Phase 4: チェックの実行または確認

変更種別に必要なチェックを実行または確認します。

- formatting・diff check
- lint
- typecheck
- compile・build
- unit・integration・regression test
- schema validation
- migration safety check
- security関連check
- ドキュメントリンク・構造check

結果が存在し、監査対象へ帰属できる場合にのみ、チェックをPASSと報告できます。

### Phase 5: 指摘事項の評価

各findingには、原則として次を記録します。

- 識別子
- タイトル
- Severity
- 対象箇所
- 観測証跡
- 期待される状態
- 影響
- 必要な対応
- 受入れを止めるか

### Phase 6: 判定

以下のいずれかを使用します。

- `PASS`
- `PASS WITH COMMENTS`
- `CHANGES REQUESTED`
- `BLOCKED`
- `NOT AUDITABLE`

判定は`verdict-criteria.ja.md`に従います。

### Phase 7: 有効性の記録

結果に次を記録します。

- 監査対象HEAD
- base
- 監査日時
- 証跡上の制限
- 未完了の人間確認
- 失効条件
- 次に許可される行為

## 7. 監査領域

変更によって実質的に影響する領域を確認します。

| 領域 | 最低限の確認事項 |
|---|---|
| Identity | repository、base、branch、HEAD、Pull Request |
| Scope | 依頼内容と実変更 |
| Correctness | 要件と挙動 |
| Regression | 既存挙動と契約 |
| Security | 認証、認可、秘密情報、入力、trust boundary |
| Data | 整合性、migration、rollback、破壊的影響 |
| Dependencies | 追加・更新、lockfile、supply chain |
| Architecture | 責務、依存方向、既存設計 |
| Quality | 可読性、重複、例外、保守性 |
| Tests | 必須かつ関連するカバレッジ |
| Build | lint、typecheck、compile、package、build |
| Git hygiene | 未追跡、生成物、一時ファイル、binary、秘密情報 |
| Operations | deploy、設定、cache、停止時間、rollback |
| Documentation | 利用者、開発者、運用、変更文書 |
| Evidence | コマンド、出力、終了状態、制限 |
| Merge readiness | 残るblockerと人間承認 |

すべての領域を同じ深さで確認する必要はありませんが、重要な除外は説明します。

## 8. 必須停止条件

次の場合、監査を停止します。

- repositoryを特定できない
- baseまたはtargetを確立できない
- target HEADが不明、または監査中に変化した
- 実際のdiffを取得できない
- 変更指示または承認済みの意図がない
- Pull Requestとbranchが一致しない
- 必須正本を参照できない
- 必須証跡が別targetに属する
- 証跡の完全性を信頼できない
- 継続に危険または未許可のアクセスが必要

監査対象または監査契約を確立できない場合は`NOT AUDITABLE`です。

対象は確立しているが必須検証を完了できない場合は`BLOCKED`です。

## 9. 禁止事項

監査者は次を行ってはなりません。

- 未実行のチェックを実行済みと報告する
- Pull Request番号を不変の監査対象として扱う
- 範囲外変更を黙って無視する
- 秘密情報を公開し、または証跡へ秘密値を含める
- 証跡取得だけを目的に破壊的な本番操作を行う
- 本標準に基づいて自動merge・自動deployする
- 法令、規制、セキュリティ上の認証として結果を提示する
- 人間レビューが不要と表明する

## 10. 最小結果構造

すべての監査結果に次を含めます。

```text
Repository:
Base:
Target branch or change set:
Target HEAD:
Requirements source:
Reviewed files:
Commands executed:
Command results:
Exit codes:
Checks not executed:
Evidence limitations:
Findings:
Human verification required:
Audit validity:
Verdict:
Next permitted action:
```

## 11. 非保証

本標準への適合は、次を保証しません。

- 不具合が存在しないこと
- 脆弱性が存在しないこと
- 法令・規制・契約への適合
- 本番安全性
- 特定目的への適合性
- 外部システムまたは証跡の正確性

## 12. サポート境界

本OSSは現状有姿で提供します。無償の導入支援、実装支援、トラブルシューティング、回答期限保証は含みません。

専門的な導入支援、カスタム監査ポリシー、ワークフロー統合、組織導入は、別途有償業務として提供する場合があります。
