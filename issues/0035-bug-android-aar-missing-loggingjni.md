# webrtc-build issue 草案

起票先: `shiguredo-webrtc-build/webrtc-build`

以下は `webrtc-build` に起票する issue 本文案です。このファイル自体は一時草案であり、Sora Android SDK の管理 issue ではありません。

---

# Android 向け AAR から LoggingJni.class が欠落する

- Created: 2026-10-06
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-android-logging-jni-packaging
- Polished: {YYYY-MM-DD}

## 目的

Android 向け AAR に `LoggingJni.class` を含め、 `libjingleEnabled` を有効にした Sora Android SDK のビデオチャット接続がタイムアウトする問題を解消する。

## 現状

- Sora Android SDK 2026.4.0-canary.0 ではビデオチャットに接続できるが、 2026.4.0-canary.1 では接続がタイムアウトする。 `libjingleEnabled` を `false` にすると接続できる。
- 手元で確認した `shiguredo-webrtc-android` 152.7977.0.4 / 155.8059.0.0 と webrtc-build m155.8059.1.1 の AAR では、 `classes.jar` に `Logging.class` と `Logging$Natives.class` はあるが `LoggingJni.class` がない。
- `patches/android_jni_zero_generated_java.patch` は `:generated_logging_jni_java` を `dist_jar("libwebrtc")` の依存に加えているが、 `../../rtc_base:base_java_jni_java` は直接依存に含めていない。 M155 と M156 の同パッチにもこの依存はない。

## 設計方針

- `patches/android_jni_zero_generated_java.patch` で `../../rtc_base:base_java_jni_java` を `dist_jar("libwebrtc")` の直接依存に加える。
- `android_sdk` の AAR を生成し、 `classes.jar` に `LoggingJni.class` が含まれることを確認する。

## 再現手順

1. Sora Android SDK 2026.4.0-canary.1 を使うビデオチャットサンプルを起動し、 `libjingleEnabled` を有効にした状態で接続する。
2. 接続がタイムアウトすることを確認する。
3. 同じ条件で `libjingleEnabled` を `false` にすると接続できることを確認する。

## 完了条件

- 修正後に生成した Android 向け AAR の `classes.jar` に `LoggingJni.class` が含まれる。
- Sora Android SDK 2026.4.0-canary.1 のビデオチャットサンプルが `libjingleEnabled` 有効時に接続できる。
