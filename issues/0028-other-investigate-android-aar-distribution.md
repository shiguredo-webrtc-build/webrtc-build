# Android 向け libwebrtc.aar の配布を webrtc-build にまとめられるか検討する

- Created: 2026-09-24
- Completed: {YYYY-MM-DD}
- Branch: feature/debug-android-aar-distribution
- Polished: {YYYY-MM-DD}

## 目的

Android 向け libwebrtc の配布を担う `shiguredo/shiguredo-webrtc-android` の役割を webrtc-build にまとめられるか検討する。

`shiguredo/shiguredo-webrtc-android` は webrtc-build がビルドした AAR を再配布しているだけで独自のソースコードを持たず、 libwebrtc を更新するたびに 2 リポジトリでタグ・リリース・手作業が発生する。配布経路を webrtc-build にまとめられれば、下流 SDK の libwebrtc 更新作業から `shiguredo/shiguredo-webrtc-android` 側の手作業をなくせる。

## 現状

### `shiguredo/shiguredo-webrtc-android` の役割

- リポジトリにあるのは配布用のラッパーだけで、ビルド対象のソースコードは無い
  - `README.md` / `CHANGES.md` / `LICENSE` / `LICENSE_WEBRTC` / `PATENTS_WEBRTC`
  - `prepareAar.sh`: JitPack 用に AAR をローカルの Maven リポジトリへ登録する
  - `jitpack.yml`: `before_install` で `prepareAar.sh` を実行する
  - `.github/workflows/release.yml`: タグ push で GitHub Release を作成する
- タグは webrtc-build のタグから `m` を除いた値 (例: webrtc-build `m155.8059.1.0` → `155.8059.1.0`)
- `.github/workflows/release.yml` はタグ push を契機に `https://github.com/shiguredo-webrtc-build/webrtc-build/releases/download/m${TAG}/webrtc.android_sdk.tar.gz` を取得し、 `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` を Release の成果物としてアップロードする
- JitPack は `jitpack.yml` の `before_install` で `prepareAar.sh` を実行する。 `prepareAar.sh` は自分の Release から AAR を取得して `mvn install:install-file` でローカルの Maven リポジトリへ登録し、 JitPack が `com.github.shiguredo:shiguredo-webrtc-android:<version>` として公開する
- libwebrtc を更新するときの手作業
  - `prepareAar.sh` の `VERSION` を更新する
  - `CHANGES.md` に追記する
  - タグを作成して push する (Release 作成と JitPack への反映は push 後に自動で進む)
  - JitPack に反映されたことを確認する
- 下流は JitPack 経由で `com.github.shiguredo:shiguredo-webrtc-android` を参照している
  - Sora Android SDK の `gradle/libs.versions.toml` は `libwebrtc` の値をそのまま JitPack のバージョンに使う
  - 他にも JitPack 経由で参照する公開リポジトリがある (例: zztkm/ayame-android-sdk)

### webrtc-build の現状

- `run.py` の `android_sdk` ターゲットが `tools_webrtc/android/build_aar.py` で AAR を生成し、 `webrtc.android_sdk.tar.gz` に `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` を含めてパッケージしている
- `.github/workflows/build.yml` の `create-release` ジョブは `tags/m` のときだけ Release を作成し、各プラットフォームのアーカイブだけをアップロードする。 AAR 単体は Release の成果物に含まれない
- JitPack 用の設定ファイルは無い
- `VERSION` は `WEBRTC_BUILD_VERSION=155.8059.1.0` のように `m` を含まず、 `m` が付くのはタグ名だけである

### 調査で確認した事実

- webrtc-build の `m79.5.0` 以降のタグと `shiguredo/shiguredo-webrtc-android` のタグは 1 対 1 で対応している
- `shiguredo/shiguredo-webrtc-android` には同一 AAR に別バージョンを付けるサフィックス付きのタグ (例: 68.10.1.1) があるが、いずれも webrtc-build から AAR を取得する以前のもので、 `m79.5.0` 以降は使われていない
- JitPack は `jitpack.yml` のカスタムコマンドで既存の AAR を公開できる。 JitPack がビルドするバージョンはタグ名そのものである
- JitPack はリポジトリを削除しても公開済みの成果物をホストし続ける
- 公開リポジトリを対象にしたコード検索では、 JitPack 経由以外に `shiguredo/shiguredo-webrtc-android` の Release 成果物を直接参照している例は見つかっていない

## 設計方針

次の案を比較して、統合の可否と方式を決める。

- 案 1: JitPack を webrtc-build へ移して完全に統合する
  - webrtc-build 直下に `jitpack.yml` と AAR を用意するスクリプトを置き、 `m` 付きタグで JitPack をビルドする
  - 座標は `com.github.shiguredo-webrtc-build:webrtc-build:m<version>` になり、下流は依存座標とバージョン表記 (先頭の `m`) の両方を変更する必要がある
  - `shiguredo/shiguredo-webrtc-android` を廃止できる
  - サフィックス付きの別バージョンを付ける逃げ道は無くなる (ただし `m79.5.0` 以降は未使用)
- 案 2: AAR を webrtc-build の Release 成果物にして、 JitPack の座標を維持するために `shiguredo/shiguredo-webrtc-android` を残す
  - `create-release` ジョブで AAR と NOTICE を Release にアップロードし、 `prepareAar.sh` の取得元を webrtc-build の Release にする
  - `shiguredo/shiguredo-webrtc-android` 側の Release 作成は不要になり、手作業は JitPack がビルドするためのタグ作成だけになる
  - 下流の依存座標とバージョンは変わらない
- 案 3: 統合せず、 `shiguredo/shiguredo-webrtc-android` を自動化する
  - `prepareAar.sh` の `VERSION` をタグから導出し、 `CHANGES.md` への追記を自動化し、 webrtc-build の Release 完了時に `shiguredo/shiguredo-webrtc-android` のタグ作成を自動化する
  - リポジトリは残るが、下流の依存座標とバージョンは変わらず、人手もゼロにできる見込み

いずれの案も、 JitPack が `m` 付きタグやカスタムコマンドを受け付けるかを実ビルドで確認する。下流 SDK の座標変更は本 issue では行わない。

## 完了条件

- どの案を採用するかを決め、判断根拠 (下流への影響、手作業の削減量、JitPack の制約) を本 issue に記載すること
- 採用する案に実装が必要な場合、実装 issue を別途起票すること
- 下流 SDK の依存座標の変更と `shiguredo/shiguredo-webrtc-android` の廃止判断は、本 issue の結論を前提に別 issue で扱うこと

## 解決方法

未着手