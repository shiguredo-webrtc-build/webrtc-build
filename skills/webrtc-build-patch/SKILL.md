---
name: webrtc-build-patch
description: webrtc-build の libwebrtc パッチを追加、編集、削除、または新しい WebRTC milestone の適用失敗に追従させ、build script の適用順と対象ターゲットを横断して検証する。milestone ブランチの安定化や master 昇格判断には webrtc-build-milestone を使う。
---

# webrtc-build patch

libwebrtc のソースを正しい最終状態へ編集し、build script の `diff` から再現可能なパッチを生成する。
パッチファイルの hunk を場当たり的に合わせることを目的にしない。

## 最初に確認すること

- リポジトリの作業指示と、存在する場合はリポジトリ固有設定を読む。
- リポジトリに残る成果物を作る前に `shiguredo-no-secrets` を読む。
- git 操作前に `shiguredo-git` を読む。
- Python コードを変更するときは `shiguredo-python` を読む。
- GitHub Actions を確認・変更するときは `shiguredo-github-actions` を読む。
- 変更履歴を変更するときは `shiguredo-changelog` と、このリポジトリ固有の変更履歴形式を読む。
- 開発者用ドキュメントのパッチ作成・編集・エラー修正手順、パッチ解説、build script の現行 `PATCHES` とパッチ処理を読む。
- milestone 全体の初動または `master` 昇格も扱う場合は `webrtc-build-milestone` を使う。

## 対象を確定する

開始前に次を確定する。

- 操作: 新規追加、既存編集、適用失敗修正、削除のどれか
- パッチファイル
- WebRTC milestone と version 設定の `WEBRTC_COMMIT`
- 失敗した target とコマンド
- build script の `PATCHES` でそのパッチを使う全 target と適用位置
- ソースディレクトリとビルドディレクトリ
- 比較元にする直前 milestone のリリースタグ

対象パッチが複数 target に含まれる場合、最初に一つだけ直して完了扱いにしない。
OS、SDK、適用前パッチ列が異なる target は別の検証対象として扱う。
コマンド例の `BUILD_SCRIPT`、`PATCH_FILE`、`PATCH_NAME`、`PREVIOUS_PATCH` は、現行 checkout で解決した実値を実行時だけ task-specific 変数へ設定して使う。実値をリポジトリに残る成果物へ記録しない。

## 破壊的なソース操作の前提

build script の `fetch` と `revert` は、対象 target の WebRTC source tree と依存リポジトリに対して checkout、reset、clean を行い、手編集や未追跡ファイルを失わせる。

実行前に必ず次を行う。

1. 展開後の source path を表示する。
2. 対象 source tree と配下リポジトリに、残すべき手編集や未追跡ファイルがないか確認する。
3. 失われる変更がある、または確認できない場合は停止する。
4. ユーザーが指定した別の source directory がある場合は、それを優先する。

プロジェクト本体への `git reset` や `git clean` と混同しない。リポジトリ本体の履歴を巻き戻さない。

## 調査の順序

適用失敗では、まず失敗をそのまま再現し、最初に失敗したパッチと hunk を確定する。

```bash
python3 "$BUILD_SCRIPT" fetch <target>
```

次を分けて調べる。

- 単なる行移動や周辺 context の変化
- ファイルの rename、移動、分割、削除
- target 名や依存関係の変更
- パッチ相当の変更が upstream に取り込まれた
- upstream の API・動作変更により、パッチの設計変更が必要になった
- 先に適用される別パッチとの競合

比較は最初にファイル単位で絞り、その後に必要なパッチだけを広い context で読む。

```bash
git diff --find-renames --stat <previous-tag>..<current-branch>
git diff --find-renames --name-status <previous-tag>..<current-branch>
git diff --find-renames --unified=80 <previous-tag>..<current-branch> -- "$PATCH_FILE"
```

旧パッチ、旧 milestone の upstream ソース、現 milestone の upstream ソース、reject artifact、ビルドエラーを照合する。
upstream の根拠には WebRTC Gitiles、WebRTC Gerrit、Chromium Source などの一次資料を使い、変更 commit または branch を記録する。

パッチ相当が upstream に入った可能性がある場合は、refresh と削除の両方を検討する。
公開 API や挙動の意図が不明なら、もっともらしい実装を作らず停止して確認する。

## 既存パッチを編集する

1. 対象パッチまでの状態を作る。

```bash
python3 "$BUILD_SCRIPT" revert <target> --patch "$PATCH_NAME"
```

壊れたパッチでは、このコマンド自体の失敗は想定内である。失敗位置と reject artifact を確認してから進む。

2. libwebrtc のソースを、パッチ適用後にあるべき正しい最終状態へ編集する。
3. 差分に対象外ファイル、生成物、backup artifact、reject artifact、ログ断片が混ざっていないことを確認する。

```bash
python3 "$BUILD_SCRIPT" diff <target>
```

4. 内容を確認してから、同じコマンドの出力でパッチを再生成する。

```bash
python3 "$BUILD_SCRIPT" diff <target> > "$PATCH_FILE"
```

5. 再生成したパッチの file header、hunk header、追加・削除行、末尾改行を読む。
6. 対象パッチ以降も含めて全パッチを当て直す。

```bash
python3 "$BUILD_SCRIPT" revert <target>
```

hunk header の数値や空行 prefix を手だけで直すのは原則として避ける。直接修正が避けられない場合も、最終的に完全な再適用と `git diff --check` で検証する。

## 新しいパッチを追加する

最後に適用する場合は、clean な upstream ソースを編集し、build script の `diff` で生成してから、対象 target の `PATCHES` 末尾へ追加する。

途中へ追加する場合は、直前のパッチまで適用・commit した状態を作る。

```bash
python3 "$BUILD_SCRIPT" revert <target> --patch "$PREVIOUS_PATCH" --commit
```

その状態からソースを編集して新しいパッチを生成し、`PATCHES` の正しい位置へ追加する。
一つの target で順序を変えた場合は、同じパッチ列または関連するパッチ列を持つ全 target を確認する。

新規パッチでは次も確認する。

- パッチ名が目的を具体的に表す。
- 既存パッチへ含めるべき変更を不必要に分割していない。
- パッチ解説に利用者向けの目的、外せる条件、upstream の状況を記載する必要があるか。
- 追加ファイルのライセンスと license notice への影響。
- SDK、package、公開ヘッダー、生成物への影響。

## パッチを削除する

upstream 取り込みなどで不要になったことを一次資料と現行ソースで確認する。

- build script の全 `PATCHES` から削除する。
- パッチファイルを削除する。
- パッチ解説の該当説明と残存参照を確認する。
- パッチが補っていた依存、ライセンス、package 処理、生成物処理が build script などに残っていないか確認する。
- 削除後の全パッチ適用と関連 target のビルドを確認する。

パッチの一部だけが upstream に入った場合は、全削除せず残る責務を再定義する。

## 検証

検証は次の順で行う。

1. パッチ差分の目視確認
2. 対象パッチ以降を含む全パッチの再適用
3. そのパッチを使う各 target、または異なるパッチ列ごとの再適用
4. 変更に関係する gn gen、build、package
5. `git diff --check`
6. GitHub Actions の全 target matrix

ローカル OS で実行できない target は、未検証を明記して GitHub Actions で確認する。
別 target の成功を代用しない。モックやスタブでビルド成功を代替しない。

パッチが「適用できる」だけで完了にしない。次も確認する。

- 意図したソース差分になっている。
- upstream がすでに提供するものを重複していない。
- 追加した依存が過不足なく、不要な target を引き込んでいない。
- public API、ABI、SDK package、ライセンスへの影響を確認した。
- context だけの更新と意味上の変更を報告で区別できる。

## 変更履歴

version 設定だけの更新では変更履歴を変更しない。
パッチやビルド方法を変更した場合は、現行のタイムライン形式を維持し、最新項目を先頭へ追加する。

- 種別、日付、対象 milestone、変更理由、担当者を記載する。
- upstream の削除、rename、依存変更など、なぜ必要になったかを書く。
- context refresh だけか、動作・依存・公開 API が変わるかを区別する。
- 開発途中の失敗や中間修正ではなく、最終差分を記録する。
- 汎用 `shiguredo-changelog` 形式への移行をパッチ修正へ混ぜない。

## 承認境界と停止条件

- commit、tag、merge、push は明示承認後に行う。
- CI のために push が必要な場合は、ローカル検証結果と未検証 target を提示して承認を得る。
- 対象外の dirty file がある場合は、それを変更・stash・破棄せず停止する。
- source tree の reset・clean で失われる作業がある場合は停止する。
- パッチの維持、変更、分割、削除で設計判断が分かれる場合は停止する。
- 必要な OS のローカル検証ができず、CI も利用できない場合は未検証のまま完了にしない。
- upstream の一次資料と現行ソースが食い違う場合は、取得対象と commit を再確認する。

## 機密情報の確認

issue、コメント、変更履歴、commit message、tag message、PR 本文など、リポジトリに残る成果物へ次を記録しない。

- 機密情報の実値、認証情報、個人情報、社外秘情報
- 絶対パスまたは相対パス
- 内部 endpoint、LLM session URL、private repository 名

対象は component 名、skill 名、設定キー、`BUILD_SCRIPT` や `PATCH_FILE` のような変数名で表す。
commit、tag、push、PR 作成前に差分と message を再確認する。

## 終了報告

次を簡潔に報告する。

- 対象 milestone、patch、target
- 失敗原因または変更理由
- context 更新と意味上の変更の内訳
- 更新した `PATCHES`、ドキュメント、変更履歴
- ローカル再適用、build、package、CI の結果
- 未検証 target と残る判断
- commit、push、tag、merge の実施有無
