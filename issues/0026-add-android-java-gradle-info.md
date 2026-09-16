# Android 版 libwebrtc の Gradle バージョンと Java class file version を確認できるようにする

- Created: 2026-09-11
- Completed: {YYYY-MM-DD}
- Branch: feature/add-android-java-gradle-info
- Polished: {YYYY-MM-DD}

## 目的

Android 版の libwebrtc パッケージから、利用側が Java バイトコードと Gradle / D8 の互換性を判断できるようにする。

Unity などのアプリケーションのビルドツールは独自の Gradle を同梱しており、同梱された D8 が libwebrtc の class file version に対応していない場合は Android のビルドに失敗する。libwebrtc がどの Java ターゲットでコンパイルされ、どの Gradle を基準にしているかをパッケージから確認できるようにする。

## 現状

確認対象は `VERSION` が指定する libwebrtc `154.8037.1`、upstream コミット `c2b761bb73f0b2ced096274abb415f6c7559a28b`。

- Android の AAR は `tools_webrtc/android/build_aar.py` が GN と Ninja で生成しており、Gradle を使用しない。このため「libwebrtc の Gradle バージョン」という単一の値は存在しない
- libwebrtc の Java は `build/android/gyp/compile_java.py` と `build/android/gyp/turbine.py` の `--release 21` でコンパイルされる。jar の class file version は 65 相当になる
- ソースツリーには用途の異なる Gradle wrapper が複数ある
  - `examples/androidtests/third_party/gradle` は Gradle 6.6。`DEPS` で固定され、`tools_webrtc/android/test_aar.py` が AAR のテストに使う
  - `third_party/android_build_tools/gradle_wrapper` は Gradle 8.10。Chromium の Android Studio 連携用で、standalone の libwebrtc ビルドからは参照されない
  - `build/android/gradle/generate_gradle.py` の既定値は Gradle 9.1.0、AGP 9.2.0、Java 21
- `run.py` の `generate_version_info` は `VERSIONS` に `WEBRTC_SRC_*` の URL とコミットだけを記録し、Java や Gradle のバージョンは含まない
- `run.py` の `generate_deps_info` は `DEPS` に `IOS_DEPLOYMENT_TARGET` を追記しているが、Android 向けの同様の情報はない
- 利用側は実際にビルドを試すまで互換性を判断できない

## 設計方針

- `run.py` の `generate_version_info` または `generate_deps_info` で、`android` / `android_sdk` ターゲットのときだけ Android 向けの情報を追記する
- 記録する値
  - Java: AAR または `libwebrtc.jar` に含まれる class file の major version。ビルドに使う javac の `--release` 値を記録するより、実際の成果物から読み取る方がビルド設定の変更に追従できる
  - Gradle: AAR のビルドでは使われないため、値の用途が分かるキー名にする。AAR のテストに使う `examples/androidtests/third_party/gradle` の wrapper バージョンを `ANDROID_TEST_GRADLE_VERSION` のように記録する
- `IOS_DEPLOYMENT_TARGET` と同じく、利用側の `read_version_file` が `KEY=VALUE` として読める形式で `VERSIONS` または `DEPS` に追記する
- `android` は AAR を生成しないため、記録する情報の有無と対象を整理する
- 既存ターゲットの `VERSIONS` / `DEPS` の形式は変えない

## 完了条件

- Android パッケージの `VERSIONS` または `DEPS` から Java class file version と参照 Gradle バージョンが読み取れること
- 値の用途 (AAR のテスト用か、Android Studio 連携用か) がキー名または issue から判別できること
- `android` / `android_sdk` のパッケージ生成が成功すること
- 既存ターゲットの `VERSIONS` / `DEPS` に差分がないこと
- `CHANGES.md` に追記されていること

## 変更履歴案

- [ADD] Android パッケージに Java class file version と参照 Gradle バージョンを記録する

## 解決方法

未着手
