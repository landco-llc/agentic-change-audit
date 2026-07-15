# 監査失効

## ステータス

- バージョン: Draft 0.1
- 言語: 日本語
- 正本: いいえ
- 対応英語版: Draft 0.1
- 最終更新日: 2026-07-12

## 1. 目的

本書は、監査結果が有効性を失う条件、および新規監査またはfocused re-auditが必要となる条件を定義します。

## 2. Binding Model

監査結果は次に結び付きます。

```text
Repository
+ Base
+ Target HEAD
+ Requirements
+ Required evidence
```

結果は、監査結果に記録された組み合わせに対してのみ有効です。

## 3. 必須失効イベント

次のいずれかが発生した場合、監査結果を失効扱いにします。

- target HEADが変わった
- commitの追加、削除、amend、rebase、force-pushが行われた
- baseが変わり、effective diffが実質的に変化した
- requirementsまたはacceptance criteriaが実質的に変わった
- requested scopeが拡大または縮小した
- review済みfileが変わった
- 必須configuration、dependency resolution、generated outputが変わった
- evidenceが別targetに属すると判明した
- 必須evidenceが訂正または撤回された
- 必須human checkが実質的に異なる結果を示した
- 監査手順がcorruptedまたはuntrusted evidenceに依存していたと判明した
- 記録したrepositoryまたはPull Request identityが誤っていた

以前の結果を現行結果として提示してはなりません。

## 4. 自動失効しないイベント

target identity、diff、requirements、required evidenceを変えない場合、次は自動的な失効要因ではありません。

- label追加
- reviewer assignment
- 規範的でないPull Request文言の編集
- discussion comment追加
- project board state変更
- 監査対象外の無関係なrepository content更新

実質的影響がないことを確認すべきです。

## 5. Base変更

base branch更新時は、少なくともdiff比較が必要です。

effective diff、merge result、dependency resolution、generated output、required checksが変わる場合、監査は失効します。

baseは変わったが、監査対象変更とrequired evidenceが同一の場合、full auditの代わりにbase-refresh verificationを記録できます。

## 6. Re-auditの種類

### 6.1 Full Re-audit

次の場合にfull re-auditを使用します。

- 以前のidentityが無効
- requirementsが変わった
- change setが実質的に拡大した
- architecture、security、data、dependencies、operationsが変わった
- 複数findingを広範囲で修正した
- 以前のevidenceへの信頼が失われた

### 6.2 Focused Re-audit

次を満たす場合、focused re-auditを使用できます。

- 以前のaudit targetとfindingsが明確
- 新targetが固定
- 変更が明確なremediationへ限定
- unrelated diff changeがない
- relevant checksを再実行
- focus外のregression riskを評価

focused re-auditでも次を実施します。

- 新target identityを確認
- 旧diffと新diffを比較
- unrelated changeがないことを確認
- 各blocking findingを再確認
- 実質的に影響するtest・checkを実行
- 新HEADに結び付く新しいverdictを発行

## 7. Status用語

推奨するstatus:

- `VALID`: 記録targetに結果が適用される
- `INVALIDATED`: binding inputが変わった
- `SUPERSEDED`: 後続監査が結果を置き換えた
- `EXPIRED`: 組織固有の期間方針で有効性が終了
- `UNKNOWN`: 有効性を確立できない

時間によるexpirationは任意であり、組織固有です。

## 8. 必須記載

すべての監査結果に、次と同等の記載を含めます。

> この結果は、base `<base>` に対するtarget HEAD `<sha>` にのみ有効です。target、effective diff、requirements、required evidenceの実質的変更は、この結果を失効させます。

## 9. Merge・Release時の使用

mergeまたはrelease判断時に、現在のtargetが監査対象と一致することを確認します。

HEADまたはeffective diffが変わっている場合、「以前監査済み」であることだけでは不十分です。
