# 配布とRelease準備

[English](README.md)

このdirectoryは、GitHub Releaseを作成する前に、Agentic Change AuditのportableなSkill archiveを生成する方法を定義します。

package生成とrelease公開は意図的に分離します。

- Pull Requestおよび`main`のbuildでは一時的なworkflow artifactだけを生成する
- workflowはtag、GitHub Release、承認、mergeを作成しない
- 固定source commitと生成artifactのhashを独立確認した後に、maintainerがreleaseを公開する

## Release出力

version `<version>`に対し、次を生成します。

```text
agentic-change-audit-<version>.zip
agentic-change-audit-<version>.manifest.json
agentic-change-audit-<version>.SHA256SUMS
```

ZIP内部のroot directoryは、versionを含めず次に固定します。

```text
agentic-change-audit/
```

rootへversionを付けてはいけません。Agent SkillsではSkillの`name`と親directory名が一致する必要があるため、`agentic-change-audit-0.1.0`のようなrootは不正です。

## Runtime限定package

[distribution-files.json](distribution-files.json)を正確なallowlistとして使用します。

公開archiveには、Skill、license、README、導入guide、正本standard、Schema、結果templateを含めます。

次のrepository保守用内容は意図的に除外します。

- `.github/`
- `release/`
- `scripts/`
- `tests/`
- `requirements-validation.txt`
- 生成cacheおよびbuild出力

validation toolingと変更履歴の正本はsource repositoryに保持します。

## 再現可能なbuild

builderは次を実施します。

- `v` prefixを付けないASCII SemVerを要求
- 正確な40文字のsource commit SHAを要求
- `--source-ref`がrepositoryの`HEAD`と一致することを検証
- allowlist、distribution config、runtime file、正本builderがtrackingされ、そのcommitのbytesと一致することを検証
- packageへ影響するdirtyまたはuntracked fileを拒否
- release可能なmanifestへ`source_identity: verified_git_clean`を記録
- file不足、symlink、hidden path、重複、path traversalを拒否
- archive entryをsort
- ZIP timestampとfile modeを固定
- compression runtime差を避けるため`ZIP_STORED`を使用
- ZIP内外へbyte-identicalなmanifestを作成
- 外部SHA-256 checksumを生成

source bytes、version、source SHA、allowlistが同じ場合、出力もbyte単位で一致する必要があります。

`--test-only-unverified-source`はsynthetic unit test fixture専用です。このoptionで生成したmanifestは`unverified_test_fixture`と記録され、通常のverifierは拒否します。releaseまたはrelease candidateへ使用してはいけません。

3つの出力は1つのversion setとして公開します。いずれかのfile公開に失敗した場合、古いfileと新しいfileが混在しないよう、そのversion set全体を削除します。

## Local command

```bash
python scripts/build-distribution.py \
  --version 0.1.0-rc.1 \
  --source-ref <full-40-character-commit-sha> \
  --output-dir dist/release
```

3つの出力を検証します。

```bash
python scripts/verify-distribution.py \
  dist/release/agentic-change-audit-0.1.0-rc.1.zip \
  --manifest dist/release/agentic-change-audit-0.1.0-rc.1.manifest.json \
  --checksums dist/release/agentic-change-audit-0.1.0-rc.1.SHA256SUMS \
  --expected-version 0.1.0-rc.1 \
  --expected-source-ref <full-40-character-commit-sha>
```

## Workflow artifact

`Package` workflowはPull Request、`main`へのpush、manual dispatchで実行します。

Pull Requestと通常pushでは、commit単位のdevelopment versionを使用します。

```text
0.0.0-dev.<12-character-source-sha>
```

manual runでは、release candidate準備用のSemVerを指定できます。

workflow artifactは一時的なreview evidenceです。GitHub Releaseではなく、公開可否を保証するものでもありません。

GitHubのweb interfaceまたはartifact APIからdownloadしたworkflow artifactは、3つのrelease candidate fileを格納した**外側のtransport ZIP**です。最初にこのwrapperを展開してください。外側のtransport ZIPはruntime Skill archiveではなく、GitHub Release assetには使用しません。release候補となるのは、内側のruntime ZIP、external manifest、`SHA256SUMS`だけです。

公開前に[Release Checklist](RELEASE_CHECKLIST.ja.md)を確認してください。
