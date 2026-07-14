# Release Checklist

[English](RELEASE_CHECKLIST.md)

manualでpre-releaseまたはstable releaseを公開する際に使用します。

最初の公開releaseは、外部利用者による導入・監査動作の確認が蓄積するまでpre-releaseを維持する想定です。

## 1. Release identityを固定

- [ ] `v` prefixなしのSemVerを決定する。例: `0.1.0-rc.1`
- [ ] 正確な`main`のfull commit SHAを記録する
- [ ] working treeがcleanで、`main`が`origin/main`と一致する
- [ ] PRおよび`main`のvalidation workflowが成功している
- [ ] 未監査commitが含まれない

## 2. Sourceを検証

```bash
python -m pip install --disable-pip-version-check \
  -r requirements-validation.txt

python scripts/validate-skill.py .
python -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] Skill validationがPASS
- [ ] validatorおよびdistribution testがすべてPASS
- [ ] `git diff --check`がPASS
- [ ] cache、secret、local archive、temporary fileがtrackingされていない

## 3. 固定artifactを生成

指定versionで`Package` workflowをmanual実行するか、正確なrelease commitからlocal buildします。

local buildではbuilderが`source identity: verified_git_clean`を出力する必要があります。`--test-only-unverified-source`は使用しません。`unverified_test_fixture`と記録されたpackageはtest dataであり、release candidateではありません。

```bash
python scripts/build-distribution.py \
  --version <version> \
  --source-ref <full-source-sha> \
  --output-dir dist/release
```

- [ ] ZIP、external manifest、SHA256SUMSを生成
- [ ] manifestに`source_identity: verified_git_clean`を記録
- [ ] 同一入力による2回目のbuildとbyte単位で一致
- [ ] ZIP rootが正確に`agentic-change-audit/`
- [ ] allowlistのruntime fileと`PACKAGE-MANIFEST.json`だけを含む
- [ ] `.github`、`release`、`scripts`、`tests`、cache、secretを含まない

## 4. 独立検証

```bash
python scripts/verify-distribution.py \
  dist/release/agentic-change-audit-<version>.zip \
  --manifest dist/release/agentic-change-audit-<version>.manifest.json \
  --checksums dist/release/agentic-change-audit-<version>.SHA256SUMS \
  --expected-version <version> \
  --expected-source-ref <full-source-sha>
```

- [ ] ZIP内外のmanifestがbyte-identical
- [ ] 全package fileのsizeとSHA-256が一致
- [ ] external checksumがZIPとmanifestに一致
- [ ] source repository、source SHA、version、rootが正しい
- [ ] 独立監査で固定artifact hashを記録
- [ ] 必要な人間release承認をpackage外で記録

## 5. Tagとdraft releaseを準備

固定artifactのreview完了後にannotated tagを作成します。

```bash
git tag -a "v<version>" <full-source-sha> \
  -m "Agentic Change Audit v<version>"

git push origin "v<version>"
```

[RELEASE_NOTES_TEMPLATE.ja.md](RELEASE_NOTES_TEMPLATE.ja.md)からrelease noteを作成します。

GitHub Actions artifactをdownloadした場合、最初に外側のtransport ZIPを展開します。外側のtransport ZIPはGitHub Release assetには使用しないでください。review済みの内側3assetだけを添付してdraft releaseを作成します。

```bash
gh release create "v<version>" \
  dist/release/agentic-change-audit-<version>.zip \
  dist/release/agentic-change-audit-<version>.manifest.json \
  dist/release/agentic-change-audit-<version>.SHA256SUMS \
  --verify-tag \
  --draft \
  --prerelease \
  --notes-file <release-notes-file>
```

stable releaseでは、stability判断が明示承認された後にだけ`--prerelease`を外します。

- [ ] tagが監査済みsource SHAを指す
- [ ] asset確認中はreleaseをdraft維持
- [ ] 添付assetは内側の正確な3件だけで、外側のActions transport ZIPを添付していない
- [ ] release noteへpre-release/stable statusと既知制限を記載
- [ ] この処理外のsource ZIPをSkill runtime archiveとして表示しない
- [ ] downloadしたGitHub Actions transport ZIPをSkill runtime archiveまたはrelease assetとして表示しない

## 6. Upload済みassetを検証

draft assetを新しい空directoryへdownloadします。

- [ ] filenameがreview済みfilenameと一致
- [ ] SHA256SUMSがdownload済みZIPとmanifestに一致
- [ ] download済みassetへ`verify-distribution.py`がPASS
- [ ] 展開すると`agentic-change-audit/SKILL.md`が存在
- [ ] rootに余分なversion suffixがない
- [ ] 可能な範囲でClaude CodeとCodexのlocal installation smoke checkを実施

## 7. 公開

- [ ] draft releaseが監査済みtagとsource SHAを維持
- [ ] 独立監査後にassetが変更されていない
- [ ] maintainer approvalが明示されている
- [ ] GitHub Releaseをmanual公開
- [ ] material変更が必要な場合、assetを黙って置換せず再監査する

## 8. 公開後

- [ ] public release URL、tag、source SHA、3asset hashを記録
- [ ] 承認どおりpre-releaseまたはstable表示
- [ ] repositoryがclean
- [ ] 無償導入支援、回答期限、保守を保証しない
