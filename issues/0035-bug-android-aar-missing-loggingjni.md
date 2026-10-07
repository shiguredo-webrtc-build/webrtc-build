# Android 向け AAR から LoggingJni.class が欠落する

- Created: 2026-10-06
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-android-logging-jni-packaging
- Polished: 2026-10-06

## 目的

Android 向け AAR に `LoggingJni.class` を含め、 `libjingleEnabled` を有効にした Sora Android SDK のビデオチャット接続がタイムアウトする問題を解消する。

## 背景

### `libjingleEnabled` とは何か

`libjingleEnabled` は Sora Android SDK の `SoraLogger` にある `Boolean` のフラグで、 libwebrtc のネイティブログ (`RTC_LOG()` の出力) を Android の Logcat に出力させるかどうかを切り替える。 有効にすると深刻度 `LS_INFO` 以上のログが対象になる。

名前の `libjingle` は libjingle ライブラリを指すものではない。 libwebrtc が生成するネイティブライブラリのファイル名 (`libjingle_peerconnection_so.so`) に由来する歴史的な名残であり、 現在の実体は libwebrtc のログ機能である。 実際にこのフラグが有効にするのは `org.webrtc.Logging` が提供する libwebrtc のログであり、 libjingle の機能は呼ばれない。

- 定義: `sora-android-sdk/src/main/kotlin/jp/shiguredo/sora/sdk/util/SoraLogger.kt` の `SoraLogger.Companion.libjingleEnabled` (既定値 `false`)
- 役割: `true` のときだけ `PeerConnectionFactory.initialize` の直後に `Logging.enableLogToDebugOutput(Logging.Severity.LS_INFO)` を呼ぶ。 既定値が `false` のため、 通常の接続ではこの呼び出しは発生しない
- 用途: 接続がうまくいかないときの原因調査用。 有効にすると libwebrtc 側の `RTC_LOG()` の出力が Logcat に流れる

### 呼ばれる libwebrtc の API とクラス

`libjingleEnabled` を有効にしてからログ出力が有効になるまでの経路は次のとおり。 途中に `LoggingJni` が入るため、 このクラスが AAR に無いと経路が途切れる。

| 段階 | 対象 | 内容 |
| --- | --- | --- |
| 1 | `SoraLogger.libjingleEnabled` (Sora Android SDK) | `true` のときだけ次の段階を呼ぶ |
| 2 | `org.webrtc.Logging.enableLogToDebugOutput(Severity)` (Java, libwebrtc) | `loggable` が未設定であることを確認し、 `LoggingJni.get().enableLogToDebugOutput(severity.ordinal())` に委譲する。 M152 以降はこの委譲が入る |
| 3 | `org.webrtc.LoggingJni` (Java, jni_zero 生成) | `@NativeMethods interface Natives` から jni_zero が生成するクラス。 `rtc_base/BUILD.gn` の `generate_jni("base_java_jni")` が `Logging.java` から生成する |
| 4 | `webrtc::jni::Logging_nativeEnableLogToDebugOutput` (C++, `sdk/android/src/jni/pc/logging.cc`) | 引数の深刻度を検証したうえで `LogMessage::LogToDebug(severity)` を呼ぶ |
| 5 | `webrtc::LogMessage::LogToDebug(LoggingSeverity)` (C++, `rtc_base/logging.h`) | 指定した深刻度以上のログを stderr などの標準の出力先へ流すように設定する |

`LoggingJni` は jni_zero が `Logging.java` の `@NativeMethods` を基に生成するクラスで、 生成先は `rtc_base` の `generate_jni("base_java_jni")` ターゲットが持つ `base_java_jni_java` である。 AAR の `classes.jar` は `direct_deps_only = true` の `dist_jar("libwebrtc")` が直接依存から集めるため、 `base_java_jni_java` を直接依存に含めない限り `LoggingJni.class` は同梱されない。

### タイムアウトに至る流れ

`LoggingJni.class` が欠落した AAR で `libjingleEnabled` を有効にすると、 上記の段階 3 で `LoggingJni` を解決できず `NoClassDefFoundError` になる。 この例外は `PeerConnectionFactory.initialize` の直後に送出されるため接続処理が完了せず、 接続タイマー (既定 10 秒) が満了して TIMEOUT として現れる。

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
