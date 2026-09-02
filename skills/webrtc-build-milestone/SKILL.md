---
name: webrtc-build-milestone
description: webrtc-build の WebRTC メジャーブランチ feature/mNNN.BBBB が新規作成された後の初動、差分調査、安定化、タグ作成、master への昇格判断を行う。個別パッチの追加・再生成・適用失敗修正には webrtc-build-patch を使う。
---

# webrtc-build milestone

`feature/mNNN.BBBB` の誕生から、そのブランチを安定させて `master` へ昇格できると判断するまでを扱う。
このリポジトリのメジャーブランチは長期保守ブランチであり、通常の短命な feature ブランチとして扱わない。

## 最初に確認すること

- リポジトリの作業指示と、存在する場合はリポジトリ固有設定を読む。
- リポジトリに残る成果物を作る前に `shiguredo-no-secrets` を読む。
- git 操作前に `shiguredo-git` を読む。
- GitHub Actions を確認・変更するときは `shiguredo-github-actions` を読む。
- 変更履歴を変更するときは `shiguredo-changelog` と、このリポジトリ固有の変更履歴形式を読む。
- リポジトリ概要のタグ・ブランチ運用、開発者用ドキュメント、version 設定、version update script、version update workflow、build workflow を現行 checkout で読む。
- 作業ツリー、現在ブランチ、remote、対象ブランチ、対象 milestone を確認する。対象を一意に決められなければ停止して確認する。

コマンド例の `BUILD_SCRIPT` と `PATCH_FILE` は、現行 checkout で解決した実値を実行時だけ task-specific 変数へ設定して使う。実値をリポジトリに残る成果物へ記録しない。

## 責務

このスキルは次を扱う。

- 日次処理で新しい `feature/mNNN.BBBB` が作成された後の初動確認
- 直前の milestone、`master`、対象ブランチ間の差分調査
- 対象ブランチへの `master` 取り込み可否の判定
- 対象ブランチの安定化状況とリリース準備状況の確認
- タグ作成の準備と、`master` へマージできるかの判定
- 明示承認後のタグ、merge、push と CI 確認

個別パッチの作成、編集、削除、適用失敗修正は `webrtc-build-patch` を使う。

## Chromium Dash で branch detail を確認する

milestone と upstream branch の対応は Chromium Dash の Branches を一次情報として確認する。

- 画面: `https://chromiumdash.appspot.com/branches`
- 公開 JSON: `https://chromiumdash.appspot.com/fetch_milestones?only_branched=true`
- JSON から対象 `milestone` と完全一致する要素を選び、少なくとも `chromium_branch`、`webrtc_branch`、`chromium_main_branch_position`、`schedule_phase`、`schedule_active` を記録する。
- `feature/mNNN.BBBB` の `NNN` が `milestone`、`BBBB` が `webrtc_branch` と一致することを確認する。
- `chromium_main_branch_hash` と `chromium_main_branch_position` は Chromium 側の値であり、version 設定の `WEBRTC_COMMIT` や WebRTC branch 上の commit position と混同しない。
- WebRTC branch の履歴が必要なら `https://webrtc.googlesource.com/src.git/+log/refs/branch-heads/<webrtc_branch>` を確認する。
- `schedule_phase` は Chromium のリリース段階を表す参考情報であり、webrtc-build のビルド成功や安定性を証明するものではない。

取得結果が version 設定、ブランチ名、`python3 "$BUILD_SCRIPT" version_list` の結果と食い違う場合は、推測で直さず、取得日時と差異を報告して停止する。

## 新しい milestone ブランチが作成されたとき

1. remote を更新し、対象ブランチの先頭、作成コミット、派生元を確認する。
2. 自動作成コミットが原則として version 設定だけを変更していることを確認する。
3. version 設定の次を Chromium Dash と WebRTC branch の現状に照合する。
   - `WEBRTC_BUILD_VERSION`
   - `WEBRTC_VERSION`
   - `WEBRTC_READABLE_VERSION`
   - `WEBRTC_COMMIT`
4. 直前 milestone の最新リリースタグと対象ブランチを、最初にファイル単位で比較する。

```bash
git diff --find-renames --stat <previous-tag>..<target-branch>
git diff --find-renames --name-status <previous-tag>..<target-branch>
```

5. version 設定、build script の `PATCHES`、変更されたパッチ、変更履歴、CI の差分を分けて調査する。
6. パッチ差分は変更されたものだけを十分な context 付きで確認する。

```bash
git diff --find-renames --unified=80 <previous-tag>..<target-branch> -- "$PATCH_FILE"
```

7. 対象ブランチが古い `master` から作られている場合は、現在の `master` を取り込む必要性と安全性を判定する。
8. パッチ適用またはビルドが失敗したら、失敗ターゲット、失敗パッチ、最初のエラーを整理して `webrtc-build-patch` の手順へ移る。

version 設定の更新だけを理由に変更履歴を更新しない。パッチやビルド方法を変更した場合は、このリポジトリのタイムライン形式で変更理由と upstream の根拠を記録する。汎用形式への移行を同じ作業へ混ぜない。

## `master` を milestone ブランチへ取り込む判断

- `master` の milestone が対象ブランチと同じか、それより低い場合だけ検討する。
- `master` が対象ブランチより高い milestone なら merge してはならない。
- 下位 milestone に `master` の変更が必要な場合は、必要なコミットだけを cherry-pick する。ただし cherry-pick も明示承認後に行う。
- merge 前に両方向の固有コミット数、merge-base、変更ファイル、衝突候補を確認する。
- merge が必要でも、merge commit の作成と push はユーザーの明示承認を得てから行う。
- unrelated な変更や、対象 milestone に入れるべきでない新機能を便乗させない。

## タグ作成と安定性の判定

タグは必ず対象の `feature/mNNN.BBBB` 上に作成し、ブランチはタグ作成後も削除しない。

リリース候補は少なくとも次を満たす必要がある。

- version 設定と予定タグが一致する。
- 対象 commit で全ターゲットの GitHub Actions が成功している。
- 全パッチが対象ターゲットで適用できる。
- 既知の gn gen、コンパイル、package の失敗が残っていない。
- パッチまたはビルド変更が変更履歴に記録されている。
- リリースを妨げる open issue や未反映の修正が残っていない。
- 差分の意味と検証結果を説明できる。

ローカルで実行できない OS の結果を、別 OS の成功から推測しない。全 matrix の確認には GitHub Actions を使う。
タグ作成と push はリリースを発生させるため、予定タグ、対象 commit、検証結果を提示して明示承認を得る。

## `master` へ昇格する判断

「Chromium が stable」「タグがある」「一部ターゲットが成功」のどれか一つだけでは昇格させない。
次をすべて確認してから「マージ推奨」と判断する。

- 対象ブランチ上にリリース済みタグがある。
- そのタグまたは同等 commit の全ターゲット CI が成功している。
- タグ後に未リリースの修正がある場合、その修正を含む次のリリースが必要か判断済みである。
- パッチ適用失敗、既知のビルド失敗、リリースを妨げる issue が残っていない。
- `origin/master...origin/feature/mNNN.BBBB` の固有コミットと最終差分を説明できる。
- `master` がより高い milestone に進んでおらず、このリポジトリの merge 方向制約を満たす。
- ユーザーが対象ブランチと merge 方法を明示承認している。

実際に merge する前に、対象 commit、取り込まれる差分、CI、予定される merge commit を提示する。
直近履歴だけを理由に merge 方法を決めず、現行規約とユーザー指定を優先する。
merge 後も対象 feature ブランチは削除せず、`master` と remote の同期、タグの位置、CI を確認する。

## 停止条件

次の場合は勝手に補完せず停止して報告する。

- Chromium Dash、version 設定、ブランチ名、WebRTC branch の対応が一致しない。
- 対象 milestone または比較元タグを一意に決められない。
- `master` が対象より高い milestone に進んでいる。
- CI が失敗中、未実行、cancelled、または必要 job が欠けている。
- タグを打つ commit、リリース番号、merge 方法に判断の余地がある。
- unrelated な未コミット変更がある。
- merge、tag、commit、push の承認がない。
- upstream の変更意図が不明で、パッチを維持・変更・削除する判断が分かれる。

## 機密情報の確認

issue、コメント、変更履歴、commit message、tag message、PR 本文など、リポジトリに残る成果物へ次を記録しない。

- 機密情報の実値、認証情報、個人情報、社外秘情報
- 絶対パスまたは相対パス
- 内部 endpoint、LLM session URL、private repository 名

対象は component 名、skill 名、設定キー、`BUILD_SCRIPT` や `PATCH_FILE` のような変数名で表す。
commit、tag、push、PR 作成前に差分と message を再確認する。

## 終了報告

次を簡潔に報告する。

- 対象 milestone、Chromium branch、WebRTC branch、対象 commit
- 比較元と主要差分
- パッチ、ビルド、CI、タグの状態
- `master` 取り込みまたは昇格の可否と根拠
- 実行した変更と未実行の外部操作
- 残る問題と次の判断
