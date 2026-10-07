# Android 向け AAR から LoggingJni.class が欠落する

- Created: 2026-10-06
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-android-logging-jni-packaging
- Polished: 2026-10-06

## 目的

Android 向け AAR に `LoggingJni.class` を含め、 `libjingleEnabled` を有効にした Sora Android SDK のビデオチャット接続がタイムアウトする問題を解消する。

## 現状

- Sora Android SDK 2026.4.0-canary.0 (libwebrtc 151.7922.0.1 を参照) ではビデオチャットに接続できるが、 2026.4.0-canary.1 (libwebrtc 152.7977.0.4 を参照) では接続がタイムアウトする。 `libjingleEnabled` を `false` にすると接続できる。
- 手元で確認した `shiguredo-webrtc-android` 152.7977.0.4 / 155.8059.0.0 と webrtc-build m155.8059.1.1 の AAR では、 `classes.jar` に `Logging.class` と `Logging$Natives.class` はあるが `LoggingJni.class` がない。
- M152 以降の `Logging.class` は JNI 呼び出しを `LoggingJni.get()` に委譲する。 `LoggingJni.class` が欠落しているため `Logging.enableLogToDebugOutput` を呼ぶと `NoClassDefFoundError` になり、 接続処理が完了しないまま接続タイマー (既定 10 秒) が満了して TIMEOUT になる。
- `patches/android_jni_zero_generated_java.patch` は `:generated_logging_jni_java` を `dist_jar("libwebrtc")` の依存に加えているが、 `../../rtc_base:base_java_jni_java` は直接依存に含めていない。 `feature/m152.7977` / `feature/m153.8010` / `feature/m154.8037` / `feature/m155.8059` / `feature/m156.8078` と master の同パッチにもこの依存はない。 `feature/m151.7922` には `base_java_jni` ターゲット自体がなく `Logging.java` も `LoggingJni` を参照しないため、 この問題は発生しない。

## 設計方針

- `patches/android_jni_zero_generated_java.patch` で `../../rtc_base:base_java_jni_java` を `dist_jar("libwebrtc")` の直接依存に加える。
- 同じ欠落が `feature/m152.7977` / `feature/m153.8010` / `feature/m154.8037` / `feature/m155.8059` / `feature/m156.8078` と master のすべてにあるため、 各ブランチに同じ修正を適用する。 `feature/m151.7922` は対象外とする。
- `android_sdk` の AAR を生成し、 `classes.jar` に `LoggingJni.class` が含まれることを確認する。
- `CHANGES.md` に変更履歴を追記し、 `patches/README.md` の `android_jni_zero_generated_java.patch` の解説を更新する。

## 再現手順

1. Sora Android SDK 2026.4.0-canary.1 を使うビデオチャットサンプルで `SoraLogger.libjingleEnabled` を `true` にして起動し、 `libjingleEnabled` を有効にした状態で接続する。
2. 接続がタイムアウトすることを確認する。
3. 同じ条件で `libjingleEnabled` を `false` にすると接続できることを確認する。

## 完了条件

- 修正後に生成した Android 向け AAR の `classes.jar` に `LoggingJni.class` が含まれる。
- 修正が `feature/m152.7977` / `feature/m153.8010` / `feature/m154.8037` / `feature/m155.8059` / `feature/m156.8078` と master に適用される。
- 修正版 AAR を組み込んだ Sora Android SDK のビデオチャットサンプルが `libjingleEnabled` 有効時に接続できる。
  - 2026.4.0-canary.1 は 152.7977.0.4 を固定で参照しているため、 修正版 AAR を含むバージョンをリリースし、 Sora Android SDK の依存を更新した状態で確認する。
- `CHANGES.md` に修正内容が記録される。
- `patches/README.md` の `android_jni_zero_generated_java.patch` の解説が更新される。
