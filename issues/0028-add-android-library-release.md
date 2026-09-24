# Android 向け WebRTC ライブラリの公開先を webrtc-build に移行する

- Created: 2026-09-24
- Completed:
- Branch: feature/add-android-library-release
- Polished: {YYYY-MM-DD}

## 目的

Android 向け `libwebrtc.aar` の公開先を、[shiguredo-webrtc-android](https://github.com/shiguredo/shiguredo-webrtc-android) リポジトリから `webrtc-build` リポジトリの `master` ブランチで管理するリリースへ移行する。

現在は `webrtc-build` がビルドしたアーカイブを別リポジトリのワークフローが取得し、Android 向けの AAR と `NOTICE` を再公開している。
ビルド元と公開先が分離しているため、Android 向けライブラリを公開するために複数リポジトリのタグと GitHub Actions を管理しなければならない。
`webrtc-build` のリリースに他のプラットフォームと同じタイミングで Android 向け成果物を含め、`master` のリリースだけで公開を完了できるようにする。

## 現状

- `run.py` の `build_webrtc_android_sdk` 関数が `build_aar.py` を実行して `libwebrtc.aar` を生成している。
- `run.py` の `package_webrtc` 関数は `android_sdk` のパッケージに `aar/libwebrtc.aar` と `NOTICE` を含め、`webrtc.android_sdk.tar.gz` を生成している。
- `.github/workflows/build.yml` の `build-linux` ジョブは `android_sdk` をビルドしてアーティファクトとして保存し、`create-release` ジョブは `m` プレフィックスのタグで各プラットフォームのアーカイブを GitHub Release に登録している。
- `shiguredo/shiguredo-webrtc-android` の `.github/workflows/release.yml` は、`webrtc-build` の `m<バージョン>` タグの `webrtc.android_sdk.tar.gz` を取得し、`libwebrtc.aar` と `NOTICE` を別リポジトリの GitHub Release に再登録している。
- `shiguredo/shiguredo-webrtc-android` の `prepareAar.sh` と `jitpack.yml` は、同リポジトリのリリースを基準に JitPack で AAR を配布する構成になっている。

## 設計方針

- Android 向け AAR は既存の `android_sdk` ビルド成果物を利用し、リリースのために別のビルドを実行しない。
- `master` に付与する既存の `m<バージョン>` タグを Android 向け公開の基準にし、同じタグの GitHub Release に `libwebrtc.aar` と `NOTICE` を直接登録する。
- 既存の `webrtc.android_sdk.tar.gz` は、他の Android SDK 成果物とライセンス・バージョン情報をまとめて取得する利用者のために維持するか、削除時期を明確にしたうえで移行する。
- `shiguredo-webrtc-android` の GitHub Release と JitPack を利用している既存利用者が取得方法を失わないよう、継続する公開経路、移行先 URL、タグとバージョンの対応を README に明記する。
- GitHub Actions にはリリース作成に必要な最小限の `contents: write` 権限を設定し、同じタグで再実行しても成果物を一貫して更新できるようにする。

## 完了条件

- `master` の `m<バージョン>` タグを起点に GitHub Actions が `android_sdk` をビルドし、`webrtc-build` の GitHub Release を自動作成または更新すること。
- `webrtc-build` の Android 向け GitHub Release に `libwebrtc.aar`、`NOTICE`、`webrtc.android_sdk.tar.gz` が同じビルドから登録されること。
- `libwebrtc.aar` が現在の `android_sdk` パッケージに含まれる AAR と同一であり、`NOTICE` が欠落しないことを CI で検証できること。
- 新規リリースで `shiguredo-webrtc-android` 側のタグ作成、リリースワークフロー実行、成果物の再アップロードが不要になること。
- GitHub Release から Android 向け成果物を取得する方法、タグ形式、JitPack を含む既存利用者の移行方針が README に記載されていること。
- `CHANGES.md` に Android 向けライブラリの公開先変更と自動リリース対応を追記すること。

## 解決方法

- `.github/workflows/build.yml` の `create-release` ジョブで `android_sdk` のアーカイブから `libwebrtc.aar` と `NOTICE` を取り出し、GitHub Release の追加アセットとして登録する。
- 必要に応じて `.github/actions/download/action.yml` またはリリース用の補助処理を変更し、Android SDK アーカイブの展開結果とリリースアセットのパスを一元的に扱う。
- `README.md` の Android 向け提供物とダウンロード方法を更新し、`shiguredo-webrtc-android` の `.github/workflows/release.yml`、`prepareAar.sh`、`jitpack.yml` が担っていた処理の移行または終了を反映する。
- リリースタグを使った実 CI で AAR、`NOTICE`、`webrtc.android_sdk.tar.gz` の生成・登録を確認し、既存のプラットフォーム向けリリースを壊していないことを確認する。
