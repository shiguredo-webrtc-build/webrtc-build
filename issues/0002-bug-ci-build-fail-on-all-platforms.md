# CI ビルドが m153 の更新で全プラットフォーム失敗する

- Created: 2026-08-19
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-m153.8010.0.0
- Polished: {YYYY-MM-DD}

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

対応の選択肢:
- `generate_licenses.py` に sframe のライセンスエントリを追加するパッチを当てる (`patches/add_license_dav1d.patch` と同様の方式)
- WebRTC 側のリビジョンで修正されるのを待つ

### android の jni_zero API 廃止による gn gen 失敗 (2 ジョブ)

android / android_sdk ジョブが `gn gen` で失敗する。エラーは `sdk/android/BUILD.gn` で `generate_jni_registration` が Unknown function。

原因は、パッチ `patches/android_jni_zero_generated_java.patch` が `sdk/android/BUILD.gn` に `generate_jni_registration("libwebrtc_jni_registration")` を追加していること。このテンプレートは jni_zero の `jni_zero.gni` で定義されるが、WebRTC が参照する jni_zero の更新で `generate_final_jni` にリネームされた (chromium のリネームコミット 78a5ecddd742、2026-07-30)。

対応の選択肢:
- パッチの `generate_jni_registration` を `generate_final_jni` に置き換える (引数は互換)

### windows の SDK バージョン不一致による toolchain 失敗 (2 ジョブ)

windows_x86_64 / windows_arm64 ジョブが `gn gen` で失敗する。エラーは `build/toolchain/win/setup_toolchain.py` が「include 環境変数内の `10.0.28000.0` のパスが存在しない」と出す。

原因は、WebRTC が参照する chromium build の `SDK_VERSION` が `10.0.28000.0` に更新されたが、GitHub Actions の windows runner には最大 `10.0.26100.0` までしかインストールされていないこと。ローカルビルドでは `10.0.28000.0` をインストールすればビルドが通ることを確認済み。

対応の選択肢 (未定):
- CI の windows runner に SDK `10.0.28000.0` をインストールする
- `build/vs_toolchain.py` / `build/toolchain/win/setup_toolchain.py` の `SDK_VERSION` を `10.0.26100.0` に戻すパッチを当てる

## 設計方針

3 つの問題それぞれを個別に対応する。

- sframe ライセンスエラー: `generate_licenses.py` に sframe のライセンスエントリを追加するパッチを当てるか、WebRTC 側のリビジョンで修正されるのを待つかを決定する
- android の gn gen 失敗: `patches/android_jni_zero_generated_java.patch` の `generate_jni_registration` を `generate_final_jni` に置き換える
- windows の toolchain 失敗: CI の runner に SDK `10.0.28000.0` をインストールするか、`SDK_VERSION` を `10.0.26100.0` に戻すパッチを当てるかを決定する

## 完了条件

CI の全ジョブが成功すること。

## 解決方法

未着手
