# 判定基準

## ステータス

- バージョン: Draft 0.1
- 言語: 日本語
- 正本: いいえ
- 対応英語版: Draft 0.1
- 最終更新日: 2026-07-12

## 1. 目的

本書は、使用可能な5種類の監査判定と、それぞれを発行する条件を定義します。

VerdictとfindingのSeverityは別の概念です。

## 2. 使用可能な判定

### 2.1 PASS

次をすべて満たす場合にのみ`PASS`を使用します。

- 監査対象が有効かつ固定されている
- blocking findingがない
- 必須の非人間チェックが完了し、対象へ帰属できる
- 受入れ前に必須となる人間確認が完了している
- 判断へ影響する重大な証跡制限がない
- 変更が承認済みの範囲内である
- 承認された次工程へ進める

明確な`PASS`を避ける目的だけで、追跡不要な軽微所見を追加すべきではありません。

### 2.2 PASS WITH COMMENTS

次の場合に`PASS WITH COMMENTS`を使用します。

- 対象が有効
- blocking findingがない
- 受入れに必要なチェックが完了
- 残項目が非blocking
- 残項目が安全性または範囲を実質的に変えない
- コメントを記録した上で次工程へ進める

代表例:

- Low severityの保守性改善
- 任意のドキュメント改善
- 軽微な命名・一貫性上の所見
- 必須ではない人間フォローアップ

必須検証の未完了を隠すために使用してはなりません。

### 2.3 CHANGES REQUESTED

次の場合に`CHANGES REQUESTED`を使用します。

- 対象が有効で監査可能
- 受入れ前に修正が必要なfindingが1件以上ある

代表的な原因:

- 挙動の誤り
- 必須作業の不足
- 未許可または過剰な変更範囲
- 回帰
- セキュリティ上の弱点
- 安全でないmigration
- 必須test・buildの失敗
- 重大なドキュメント誤り
- HighまたはCritical finding

現在のtargetを受け入れてはなりません。修正後に新規監査またはfocused re-auditが必要です。

### 2.4 BLOCKED

次の場合に`BLOCKED`を使用します。

- 対象同一性と要求範囲は確立している
- 一部の監査は実施可能
- ただし、必須検証または判断依存関係を完了できない

代表的な原因:

- 必須CIを実行できない
- 必須外部システムが利用できない
- 必要なアクセス権がない
- 本番安全性を保った必須確認を実行できない
- 必須の人間確認が未完了
- 必須正本は存在するがアクセスできない

`BLOCKED`は、実装に欠陥があることを意味しません。

blockerが解消するまで、mergeまたはrelease可能とは判定できません。

### 2.5 NOT AUDITABLE

信頼できる監査対象または監査契約を確立できない場合に`NOT AUDITABLE`を使用します。

代表的な原因:

- repository、base、branch、HEADが不明
- diffを取得できない
- 要件または承認済みの意図が存在しない
- Pull Requestとbranchが一致しない
- 証跡が別targetに属する
- 監査中にtargetが変化した
- 正本が内部矛盾している
- 証跡の完全性を信頼できない

明確にpreliminary observationと表示した場合を除き、実装品質に関する結論を出してはなりません。

## 3. 判定順序

次の順序で適用します。

1. 対象同一性または監査契約が無効: `NOT AUDITABLE`
2. 対象は有効だが必須検証を完了できない: `BLOCKED`
3. 対象は有効で修正が必要: `CHANGES REQUESTED`
4. 非blocking項目を記録した上で受入れ可能: `PASS WITH COMMENTS`
5. 上記以外: `PASS`

複数条件に該当する場合は、この順序で最初に該当する判定を使用します。

## 4. Severityとの関係

推奨するfinding severity:

| Severity | 意味 | 標準的な判定影響 |
|---|---|---|
| Critical | データ損失、重大侵害、重大障害、権限突破 | `CHANGES REQUESTED` |
| High | 重大不具合、回帰、契約違反、安全でない変更 | `CHANGES REQUESTED` |
| Medium | 修正が必要な、意味のある限定的問題 | 原則`CHANGES REQUESTED` |
| Low | 非blockingの改善 | 原則`PASS WITH COMMENTS` |
| Comment | 情報、任意改善、人間確認メモ | `PASS`または`PASS WITH COMMENTS` |

例外は理由を説明します。

findingがなくても、`BLOCKED`または`NOT AUDITABLE`になる場合があります。

## 5. 人間確認

受入れ前に必須となる人間確認が未完了の場合、判定は`BLOCKED`です。

人間確認が明示的に任意、または後続の承認済みgateへ延期されている場合は、`PASS WITH COMMENTS`として記録できます。

## 6. 次に許可される行為

すべての結果に、次に許可される行為を1つ記載します。

例:

- `PASS`: 人間によるmerge承認へ進める
- `PASS WITH COMMENTS`: コメントを保持して人間によるmerge承認へ進める
- `CHANGES REQUESTED`: targetを修正し、再監査する
- `BLOCKED`: 指定依存関係を解消し、監査を再開または再実行する
- `NOT AUDITABLE`: 有効なtargetと要件を確立し、新規監査を開始する

## 7. 禁止する代替表現

次を判定の代わりに使用しません。

- confidence percentage
- 「問題なさそう」などの非公式表現
- GitHub上のreview state
- 全体判定の代わりとなるSeverity label
