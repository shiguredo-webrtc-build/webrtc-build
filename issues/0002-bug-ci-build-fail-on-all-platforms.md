# CI ビルドが m153 の更新で全プラットフォーム失敗する

- Created: 2026-08-19
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-m153.8010
- Polished: 2026-08-19

## 目的

CI の全プラットフォーム (Linux / macOS / ios / android / windows) のビルドが失敗しているため、ビルドを通るようにする。

## 現状

対象バージョン: m153 (feature/m153.8010 ブランチ)

2026-08-19 の CI で 15 ジョブ全部が失敗している。

失敗した CI: https://github.com/shiguredo-webrtc-build/webrtc-build/actions/runs/32203010950

原因は WebRTC リビジョン更新 (WEBRTC_COMMIT=9ea5afc) に伴うもので、以下の 3 つの問題に分かれる。

### sframe ライセンスエラー (Linux / macOS、11 ジョブ)

Linux 8 ジョブ + macOS 3 ジョブが、パッケージング時に失敗する。エラーは `tools_webrtc/libs/generate_licenses.py` が「Missing licenses for third_party targets: sframe」を出す。

原因は、`generate_licenses.py` の `LIB_TO_LICENSES_DICT` に `third_party/sframe` のライセンスエントリが登録されていないこと。ライセンスファイル (`third_party/sframe/src/LICENSE`) 自体は存在する。

`third_party/sframe` の追加は upstream の chromium コミット 8ceb47263b18fed0a573187024faa1a5ed4dee6e (Include SFrame library to Chromium third party) によるものである。参照: https://source.chromium.org/chromium/chromium/src/+/8ceb47263b18fed0a573187024faa1a5ed4dee6e

sframe がビルド対象に加わったのは m153 (webrtc コミット 42995c384b、2026-08-13) のため、このエラーは m153 から発生する。

### android の jni_zero API 廃止による gn gen 失敗 (2 ジョブ)

android / android_sdk ジョブが `gn gen` で失敗する。エラーは `sdk/android/BUILD.gn` で `generate_jni_registration` が Unknown function。

原因は、パッチ `patches/android_jni_zero_generated_java.patch` が `sdk/android/BUILD.gn` に `generate_jni_registration("libwebrtc_jni_registration")` を追加していること。このテンプレートは jni_zero の `jni_zero.gni` で定義されるが、WebRTC が参照する jni_zero の更新で `generate_final_jni` にリネームされた (chromium のリネームコミット 78a5ecddd742853edfb420ab4a89bd6894ce4240、2026-07-30)。参照: https://source.chromium.org/chromium/chromium/src/+/78a5ecddd742853edfb420ab4a89bd6894ce4240

### windows の SDK バージョン不一致による toolchain 失敗 (2 ジョブ)

windows_x86_64 / windows_arm64 ジョブが `gn gen` で失敗する。エラーは `build/toolchain/win/setup_toolchain.py` が「include 環境変数内の `10.0.28000.0` のパスが存在しない」と出す。

原因は、WebRTC が参照する chromium build の `SDK_VERSION` が `10.0.28000.0` に更新されたが、GitHub Actions の windows runner には `10.0.28000.0` がインストールされていないこと (CI ログで確認済み)。

この `SDK_VERSION` の更新は upstream の chromium コミット 5e7ea61dd227b6521dcbc299be43fa92d37e42ae (Update Win toolchain to SDK 10.0.28000.2270) によるものである。参照: https://source.chromium.org/chromium/chromium/src/+/5e7ea61dd227b6521dcbc299be43fa92d37e42ae

## 設計方針

3 つの問題それぞれを個別に対応する。

### sframe ライセンスエラー

`patches/add_license_sframe.patch` を新規作成する (`patches/add_license_dav1d.patch` と同様の方式で、`generate_licenses.py` の `LIB_TO_LICENSES_DICT` に `'sframe': ['third_party/sframe/src/LICENSE']` を追加する)

- このパッチは全 15 ターゲットの `run.py` の `PATCHES` リストに登録する。`add_license_dav1d.patch` が全ターゲットに登録されているのと同様に、android / windows も `gn gen` で早期失敗して sframe エラーに未到達のため、それらの修正後にパッケージングへ到達した際の再発を防ぐ

### android の gn gen 失敗

`patches/android_jni_zero_generated_java.patch` の `generate_jni_registration` を `generate_final_jni` に置き換える (引数は互換)

### windows の toolchain 失敗

CI の windows runner に SDK `10.0.28000.0` を明示的にインストールする。起票者のローカルビルドでは、SDK `10.0.28000.0` をインストールすればビルドが通ることを確認済み

- インストール処理は `scripts/` 配下に新規作成する PowerShell スクリプト (例: `scripts/install_windows_sdk.ps1`) に実装し、`.github/workflows/build.yml` の build-windows ジョブの Build ステップ前から呼び出す (Linux の `scripts/apt_install_*.sh` を build.yml から呼ぶ構成と同様の方式)
- インストール方法は winget を優先し、winget が利用できない、対象バージョンのパッケージが存在しない、またはインストール先が想定と異なる場合は winsdksetup.exe に切り替える。インストールの成否は `C:\Program Files (x86)\Windows Kits\10\Include\10.0.28000.0` の存在で判定する
  - winget: `winget install --id Microsoft.WindowsSDK.10.0.28000.0 --exact --accept-package-agreements --accept-source-agreements`。runner 上で winget が利用可能か、対象バージョンのパッケージが winget に存在するか、およびインストール先が `setup_toolchain.py` が参照する `C:\Program Files (x86)\Windows Kits\10\` 配下になるかを確認する必要がある
  - winsdksetup.exe: Microsoft のダウンロードセンターから `winsdksetup.exe` を取得して、Windows Desktop 向け SDK をサイレントインストールする (`winsdksetup.exe /features OptionId.WindowsDesktopSoftwareDevelopmentKit /quiet /norestart /ceip off`)

## 不採用とした設計案

検討したが実装しない方針。理由とともに記録しておく。

### sframe ライセンスエラー

- WebRTC 側のリビジョンで修正されるのを待つ案。m153.8010 はコミット固定 (WEBRTC_COMMIT=9ea5afc) のため、上流の修正を待ってもこのブランチには反映されない

### windows の toolchain 失敗

- `build/vs_toolchain.py` / `build/toolchain/win/setup_toolchain.py` の `SDK_VERSION` を m152 の値である `10.0.26100.0` に戻すパッチを当てる案。`10.0.28000.0` 前提の m153 のビルドが `10.0.26100.0` で通る保証がないため
- windows runner のバージョン更新 (例: `windows-2022` を新しい runner に変更する) で対応する案。2026-08-19 時点の runner (`windows-2022`) には `10.0.28000.0` がインストールされていないことは確認済みだが、runner の更新が来て `10.0.28000.0` がインストールされる保証がないため

## 完了条件

- CI の全ジョブ (15 ジョブ) が成功すること
- `patches/android_jni_zero_generated_java.patch` の `generate_jni_registration` を `generate_final_jni` に置き換えていること
- `scripts/` 配下に SDK インストール用の PowerShell スクリプトを新規作成し、`.github/workflows/build.yml` の build-windows ジョブから呼び出していること
- `CHANGES.md` に修正内容を記録すること
- `patches/README.md` に新規パッチ `add_license_sframe.patch` の解説を追記すること
- `patches/README.md` の `android_jni_zero_generated_java.patch` の解説にある `generate_jni_registration` への言及を `generate_final_jni` に更新すること

## 検証

- CI の全 15 ジョブが成功すること
- 本リポジトリのビルド成果物を sora-cpp-sdk でビルドし、送受信確認ができること
- 検証ケースはプラットフォームごとに以下とする
  - iOS: sora-cpp-sdk のテストを使用して接続ができること
  - Android: sora-cpp-sdk のテストを使用して接続ができること
  - それ以外のプラットフォーム (macOS / Windows / Ubuntu): sumomo の単純接続ができること

## m153 移行時の SDK 影響分析

CI 修正完了後、ビルド成果物を各 SDK へ持ち込む際に必要な対応を把握するため、m152 から m153 の libwebrtc 差分から影響分析を行った。

調査方法は、m152 の `WEBRTC_COMMIT=6f37672d` と m153 の `WEBRTC_COMMIT=9ea5afc` の間の差分を取得し、各 SDK が直接 `#include` する webrtc ヘッダと突き合わせる方法である。差分は 293 ファイル (+8272 / -5906) で、大半は libwebrtc 内部実装の変更 (mac オーディオのリングバッファリファクタ、ビデオトラック内部実装、ジッタバッファとデコードタイミングの field trial 整理、sframe 追加など) である。

### sora-cpp-sdk

sora-cpp-sdk が直接 include する webrtc ヘッダは約 140 本で、m152→m153 で変更されたのは以下の 8 本のみ。いずれも破壊的変更ではなく、コード修正は不要な見込みである。

- `api/rtp_parameters.h`: deprecated な `RtpExtension` / `RtpHeaderExtensionCapability` の `int` ID オーバーロードを削除。sora-cpp-sdk は `RtpEncodingParameters` / `RtpParameters` のみ使用しており影響なし
- `api/video/video_bitrate_allocator.h`: `VideoBitrateAllocationObserver` を削除。sora-cpp-sdk は `VideoBitrateAllocation` のみ使用しており影響なし
- `api/video_codecs/sdp_video_format.h`: move コンストラクタを追加 (追加のみ)
- `api/video_codecs/video_codec.h`: `PayloadStringToCodecType` の引数を `const std::string&` から `absl::string_view` に変更。暗黙変換により source compatible で、sora-cpp-sdk の使用箇所も影響なし
- `common_video/libyuv/include/webrtc_libyuv.h`: `ConvertToI420` を追加 (追加のみ。sora-cpp-sdk は libyuv 側の `ConvertToI420` を使用)
- `media/base/codec.h`: コンストラクタの引数を `absl::string_view` に変更し move コンストラクタを追加 (追加/互換のみ)
- `modules/video_capture/video_capture.h`: `VideoCaptureModule` に `SetStride` / `GetStride` を default 実装付きで追加 (追加のみ)
- `rtc_base/network.h`: `NetworkManager::Stats` と `MergeNetworkList` の Stats 付きオーバーロードを削除。sora-cpp-sdk は未使用のため影響なし

### sora-ios-sdk

`WebRTC.framework` の ObjC API (`sdk/objc/`) は m152→m153 で `OWNERS` メタデータのみの変更で、API 変更はゼロ。

### sora-android-sdk

`org.webrtc.*` の Java API (`sdk/android/api/`) は変更ゼロ。sdk/ 配下の変更は Android ネイティブ実装の `sdk/android/native_api/stacktrace/stacktrace.cc` のみで、Kotlin 層への影響はなし。

### sora-python-sdk

直接 include する webrtc ヘッダで変更されたのは `common_video/libyuv/include/webrtc_libyuv.h` の 1 本のみで、`ConvertToI420` の追加のみのため影響なし。

### 結論

4 つの SDK すべてでコンパイル/API 面のコード修正は不要な見込み。確認すべきは実行時の挙動 (mac オーディオのリングバッファリファクタ、ジッタバッファとデコードタイミングの field trial 整理、sframe 追加による動作影響など) のみとなる。

## 解決方法

CI の全 15 ジョブが成功した:
https://github.com/shiguredo-webrtc-build/webrtc-build/actions/runs/32393692712

3 つの問題それぞれに対応した。

### sframe ライセンスエラー

- `patches/add_license_sframe.patch` を新規作成し、`tools_webrtc/libs/generate_licenses.py` の `LIB_TO_LICENSES_DICT` に `'sframe': ['third_party/sframe/src/LICENSE']` を追加した
- `run.py` の全 15 ターゲットの `PATCHES` リストに `add_license_sframe.patch` を登録した
- `patches/README.md` に `add_license_sframe.patch` の解説を追記した
- CI で `corrupt patch` エラーが発生したため、パッチの `index` 行とハンクヘッダーを修正した

### android の gn gen 失敗

- `patches/android_jni_zero_generated_java.patch` の `generate_jni_registration("libwebrtc_jni_registration")` を `generate_final_jni("libwebrtc_jni_registration")` に置き換えた
- `patches/README.md` の `android_jni_zero_generated_java.patch` の解説にある `generate_jni_registration` への言及を `generate_final_jni` に更新した

### windows の toolchain 失敗

- `scripts/install_windows_sdk.ps1` を新規作成した
  - `winsdksetup.exe` (Microsoft 公式の fwlink から取得) で Windows SDK `10.0.28000.0` をサイレントインストールする
  - インストールの成否は `include` / `lib` 配下のパス存在で判定する
- `.github/workflows/build.yml` の build-windows ジョブに `Install Windows SDK` ステップを追加し、`scripts/install_windows_sdk.ps1` を呼び出すようにした
- `CHANGES.md` に修正内容を記録した
