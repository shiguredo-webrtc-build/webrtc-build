# Sora Android SDK の libwebrtc の依存座標を webrtc-build に移行する

- Created: 2026-09-25
- Completed: {YYYY-MM-DD}
- Branch: feature/change-libwebrtc-coordinate
- Polished: {YYYY-MM-DD}

## 目的

Sora Android SDK が参照する libwebrtc の AAR を、 `shiguredo-webrtc-android` から webrtc-build が公開する JitPack の座標に移行する。

JitPack の座標が `com.github.shiguredo:shiguredo-webrtc-android` から `com.github.shiguredo-webrtc-build:webrtc-build` に変わり、バージョンに `m` が付くため、 SDK 側の依存定義とドキュメントを追随させる。

対象リポジトリは `shiguredo/sora-android-sdk` である。

## 現状

- `gradle/libs.versions.toml` で `libwebrtc` の値を JitPack のバージョンに使い、 module に `com.github.shiguredo:shiguredo-webrtc-android` を指定している
- `skills/sora-android-sdk/SKILL.md` の依存ライブラリの記載も同じ座標を参照している
- 新しい座標で公開できるのは、 webrtc-build に `jitpack.yml` を追加した後に作られるタグからである。既存のタグ (`m150.7871.3.0` など) は `jitpack.yml` を持たないため新しい座標では公開されない

## 設計方針

- `gradle/libs.versions.toml` の module を `com.github.shiguredo-webrtc-build:webrtc-build` に変更し、バージョンを `m<version>` にする
  - エイリアス名も `webrtc-build` に変更するかは実装時に決める
- 移行は 0031 の完了後に作られる webrtc-build の Release に合わせて行う
- `skills/sora-android-sdk/SKILL.md` と Sora Android SDK のドキュメントの記載を追随させる
- Sora Android SDK の JitPack 座標 (`com.github.shiguredo:sora-android-sdk`) は変わらないため、 SDK の利用者は SDK のバージョンを上げるだけでよい
- 外部利用者 (`zztkm/ayame-android-sdk` など) への周知は本 issue の範囲外とする

## 完了条件

- `com.github.shiguredo-webrtc-build:webrtc-build:m<version>` を参照して Sora Android SDK がビルドできる
- `skills/sora-android-sdk/SKILL.md` とドキュメントが新しい座標とバージョンの形式になっている
- `CHANGES.md` に依存座標の変更が記録されている

## 解決方法

未着手