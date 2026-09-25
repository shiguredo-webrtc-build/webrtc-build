# AAR の取得元を webrtc-build の Release に変更する

- Created: 2026-09-25
- Completed: {YYYY-MM-DD}
- Branch: feature/change-aar-release-source
- Polished: {YYYY-MM-DD}

## 目的

`shiguredo/shiguredo-webrtc-android` が AAR を再配布する経路をなくし、 AAR の取得元を webrtc-build の Release に一本化する。

現状は `shiguredo-webrtc-android` が自リポジトリの Release に AAR を保存し、 JitPack がその Release から AAR を取得している。 webrtc-build の Release には既に `webrtc.android_sdk.tar.gz` の中に `webrtc/aar/libwebrtc.aar` が含まれており、同じ AAR を 2 つのリポジトリの Release に保存している。取得元を webrtc-build に寄せて二重保存を解消する。

対象リポジトリは `shiguredo/shiguredo-webrtc-android` である。

## 現状

- `prepareAar.sh` は `https://github.com/shiguredo/shiguredo-webrtc-android/releases/download/${VERSION}/libwebrtc.aar` を取得し、 `mvn install:install-file` でローカルの Maven リポジトリに登録する
- `.github/workflows/release.yml` はタグ push を契機に webrtc-build の `webrtc.android_sdk.tar.gz` から `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` を取り出し、自リポジトリの Release にアップロードする
- `jitpack.yml` の `before_install` で `prepareAar.sh` を実行し、 JitPack が `com.github.shiguredo:shiguredo-webrtc-android` として公開する
- 下流は JitPack 経由で参照しており、 `shiguredo-webrtc-android` の Release 成果物を直接参照している例は確認されていない

## 設計方針

- `prepareAar.sh` の取得元を `https://github.com/shiguredo-webrtc-build/webrtc-build/releases/download/m${VERSION}/webrtc.android_sdk.tar.gz` に変更し、 展開して `webrtc/aar/libwebrtc.aar` を取り出す
  - `VERSION` はタグ名 (`m` 無し) のままとする。 webrtc-build 側のタグは `m` を付けて組み立てる
  - 取得失敗時にビルドを失敗させるため `curl` には `-fsSL` を付ける
- webrtc-build 側の変更は行わない。 AAR 単体を Release に追加せず、既存の `webrtc.android_sdk.tar.gz` を使う (同一 Release に AAR を二重に置かないため)
  - `webrtc.android_sdk.tar.gz` は約 105 MB で AAR 単体 (約 14 MB) より大きいが、 JitPack のビルドはリリースごとに 1 回だけなので許容する
- `.github/workflows/release.yml` は AAR のアップロードをやめる。 NOTICE はライセンス通知を配布点に残すためアップロードを続ける
- 下流の依存座標とバージョンは変更しない

## 完了条件

- `shiguredo-webrtc-android` の Release から AAR が消え、 AAR が webrtc-build の Release にのみ存在する
- JitPack から `com.github.shiguredo:shiguredo-webrtc-android:<version>` の AAR が取得でき、下流のビルドが通る
- 下流の依存座標とバージョンの変更が不要である

## 解決方法

未着手