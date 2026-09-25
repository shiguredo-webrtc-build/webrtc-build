# JitPack を webrtc-build に追加して Android の AAR を公開する

- Created: 2026-09-25
- Completed: {YYYY-MM-DD}
- Branch: feature/add-jitpack-aar-distribution
- Polished: {YYYY-MM-DD}

## 目的

Android 向け libwebrtc の配布を `shiguredo-webrtc-build/webrtc-build` に統合し、 JitPack から `com.github.shiguredo-webrtc-build:webrtc-build` として AAR を公開する。

`shiguredo/shiguredo-webrtc-android` は AAR を再配布しているだけのリポジトリであり、 libwebrtc を更新するたびにタグ、 Release、 `CHANGES.md` の更新が発生している。 webrtc-build で JitPack ビルドを行えるようにして、配布専用リポジトリを不要にする。

対象リポジトリは `shiguredo-webrtc-build/webrtc-build` である。

## 現状

- webrtc-build には JitPack 用の設定ファイルが無い
- `.github/workflows/build.yml` の `create-release` ジョブは `tags/m` のときだけ Release を作成し、各プラットフォームのアーカイブだけをアップロードする
  - `webrtc.android_sdk.tar.gz` の中に `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` が含まれているが、 AAR 単体は Release の成果物に含まれない
- `shiguredo/shiguredo-webrtc-android` の `jitpack.yml` と `prepareAar.sh` が AAR を JitPack に公開している
- JitPack は登録済みリポジトリの新しいバージョンを検知して自動ビルドする (タグ push から約 1〜15 分)
- webrtc-build の Release 成果物は全プラットフォームのビルド完了後に作られるため、タグ push から約 1 時間かかる

## 設計方針

- `jitpack.yml` を追加し、 `install` で AAR をローカルの Maven リポジトリに登録するスクリプトを実行する
  - スクリプトは JitPack が設定する環境変数 `VERSION` (タグ名) を使い、 `https://github.com/shiguredo-webrtc-build/webrtc-build/releases/download/${VERSION}/libwebrtc.aar` を取得して `mvn install:install-file` する
  - バージョンはタグ名そのものになり、下流は `m155.8059.1.0` のような `m` 付きのバージョンを指定する
- `create-release` ジョブで `webrtc.android_sdk.tar.gz` から `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` を取り出し、 Release の成果物として追加する
  - AAR 単体を追加することで取得が単純になり、ダウンロードも約 105 MB から約 14 MB に減る
- Release は draft として作成し、全成果物をアップロードしてから publish する
  - webrtc-build の Release はタグ push から約 1 時間後に作られるため、 JitPack が成果物のアップロード完了前に検知しないようにする
- publish 後に JitPack のビルドを起動して artifact の公開を確認する。 JitPack の自動検知の有無やタイミングに依存しないようにする
  - ビルドの起動方法 (artifact URL へのリクエストや API) は実ビルドで確認する
- README に Android 向け AAR の利用方法 (座標とバージョンの形式) を追記する
- jitpack.yml はタグのコミットに含まれる必要があるため、新しい座標で公開できるのは jitpack.yml をマージした後に作られるタグからである

## 完了条件

- `m` 付きタグに対して `com.github.shiguredo-webrtc-build:webrtc-build:m<version>` の AAR が JitPack から取得できる
- webrtc-build の Release に `libwebrtc.aar` と `NOTICE` が単体で含まれる
- Release 完了から人手を介さずに JitPack のビルドが完了する
- Sora Android SDK を新しい座標でビルドできる
- README に AAR の利用方法が記載されている

## 未検証の点

- `m` 付きタグが JitPack のバージョンとして通るかは実ビルドで確認する
- org 名にハイフンを含む groupId (`com.github.shiguredo-webrtc-build`) が通るかは実ビルドで確認する
- JitPack がタグと Release のどちらを契機にビルドを検知するかは実ビルドで確認する

## 解決方法

未着手