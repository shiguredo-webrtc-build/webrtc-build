# CI ビルドが m153 の更新で全プラットフォーム失敗する

- Created: 2026-08-19
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-m153.8010.0.0
- Polished: 2026-08-19

## 目的

CI の全プラットフォーム (Linux / macOS / android / windows) のビルドが失敗しているため、ビルドを通るようにする。

## 現状

対象バージョン: m153 (feature/m153.8010 ブランチ)

2026-08-19 の CI で 15 ジョブ全部が失敗している。

失敗した CI: https://github.com/shiguredo-webrtc-build/webrtc-build/actions/runs/32203010950

原因は WebRTC リビジョン更新 (2026-08-14 時点の 9ea5afc) に伴うもので、以下の 3 つの問題に分かれる。

### sframe ライセンスエラー (Linux / macOS、11 ジョブ)

Linux 8 ジョブ + macOS 3 ジョブが、パッケージング時に失敗する。エラーは `tools_webrtc/libs/generate_licenses.py` が「Missing licenses for third_party targets: sframe」を出す。

原因は、`generate_licenses.py` の `LIB_TO_LICENSES_DICT` に `third_party/sframe` のライセンスエントリが登録されていないこと。ライセンスファイル (`third_party/sframe/src/LICENSE`) 自体は存在する。

### android の jni_zero API 廃止による gn gen 失敗 (2 ジョブ)

android / android_sdk ジョブが `gn gen` で失敗する。エラーは `sdk/android/BUILD.gn` で `generate_jni_registration` が Unknown function。

原因は、パッチ `patches/android_jni_zero_generated_java.patch` が `sdk/android/BUILD.gn` に `generate_jni_registration("libwebrtc_jni_registration")` を追加していること。このテンプレートは jni_zero の `jni_zero.gni` で定義されるが、WebRTC が参照する jni_zero の更新で `generate_final_jni` にリネームされた (chromium のリネームコミット 78a5ecddd742、2026-07-30)。

### windows の SDK バージョン不一致による toolchain 失敗 (2 ジョブ)

windows_x86_64 / windows_arm64 ジョブが `gn gen` で失敗する。エラーは `build/toolchain/win/setup_toolchain.py` が「include 環境変数内の `10.0.28000.0` のパスが存在しない」と出す。

原因は、WebRTC が参照する chromium build の `SDK_VERSION` が `10.0.28000.0` に更新されたが、GitHub Actions の windows runner には `10.0.28000.0` がインストールされていないこと (CI ログで確認済み)。

## 設計方針

3 つの問題それぞれを個別に対応する。

- sframe ライセンスエラー: `patches/add_license_sframe.patch` を新規作成する (`patches/add_license_dav1d.patch` と同様の方式で、`generate_licenses.py` の `LIB_TO_LICENSES_DICT` に `'sframe': ['third_party/sframe/src/LICENSE']` を追加する)
  - WebRTC 側のリビジョンで修正されるのを待つ案は不採用とする。m153.8010 はコミット固定 (WEBRTC_COMMIT=9ea5afc) のため、上流の修正を待ってもこのブランチには反映されない
  - このパッチは全 15 ターゲットの `run.py` の `PATCHES` リストに登録する。`add_license_dav1d.patch` が全ターゲットに登録されているのと同様に、android / windows も `gn gen` で早期失敗して sframe エラーに未到達のため、それらの修正後にパッケージングへ到達した際の再発を防ぐ
- android の gn gen 失敗: `patches/android_jni_zero_generated_java.patch` の `generate_jni_registration` を `generate_final_jni` に置き換える (引数は互換)
- windows の toolchain 失敗: 以下の 2 案から実装時に検証して確定する
  - 案 1: CI の windows runner に SDK `10.0.28000.0` をインストールする (`.github/workflows/build.yml` の build-windows ジョブにインストールステップを追加する)。起票者のローカルビルドでは、SDK `10.0.28000.0` をインストールすればビルドが通ることを確認済み
  - 案 2: `build/vs_toolchain.py` / `build/toolchain/win/setup_toolchain.py` の `SDK_VERSION` を m152 の値である `10.0.26100.0` に戻すパッチを当てる。ただし runner に `10.0.26100.0` が存在することは未確認で、`10.0.28000.0` 前提のビルドが `10.0.26100.0` で通る保証はない

## 完了条件

- CI の全ジョブ (15 ジョブ) が成功すること
- `CHANGES.md` に修正内容を記録すること
- `patches/README.md` に新規パッチ `add_license_sframe.patch` の解説を追記すること
- `patches/README.md` の `android_jni_zero_generated_java.patch` の解説にある `generate_jni_registration` への言及を `generate_final_jni` に更新すること

## 解決方法

未着手
