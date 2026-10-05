# iOS シミュレーター (simulator:arm64) 向け libwebrtc.a を ios 成果物に追加する

- Created: 2026-10-05
- Completed: {YYYY-MM-DD}
- Branch: feature/add-ios-simulator-libwebrtc
- Polished: {YYYY-MM-DD}

## 目的

`webrtc.ios.tar.gz` に iOS シミュレーター (arm64) 向けの `libwebrtc.a` を含め、webrtc-rs が `aarch64-apple-ios-sim` 向け prebuilt (`libwebrtc_c-ios_sim_arm64.tar.gz`) を作れるようにする。

iOS シミュレーターで動作確認できる iOS 向けクライアントの需要があり、webrtc-rs の prebuilt に `aarch64-apple-ios-sim` を追加する必要がある。webrtc-rs の prebuilt は `webrtc.ios.tar.gz` の静的ライブラリを材料にするため、まず webrtc-build の `ios` 成果物にシミュレーター向け静的ライブラリが必要になる。

webrtc-rs 側にも対応する issue を起票しており、成果物レイアウト (`lib/simulator/libwebrtc.a`) は両リポジトリで一致させる必要がある。

## 現状

- `run.py` の `IOS_ARCHS = ["device:arm64"]` により、`ios` ターゲットは device:arm64 のみをビルドする
- `IOS_FRAMEWORK_ARCHS = ["simulator:arm64", "device:arm64"]` は `ios_sdk` ターゲット (`build_webrtc_ios_sdk`) だけが使い、`IOS_ARCHS` を使う `ios` ターゲット (`build_webrtc_ios`) はシミュレーターをビルドしない
- `build_webrtc_ios` は `IOS_ARCHS` の全ライブラリを最後に `lipo -create` で `webrtc_build_dir/libwebrtc.a` に結合する
- `package_webrtc` の `ios` 分岐は `webrtc_build_dir/libwebrtc.a` を `lib/libwebrtc.a` として同梱する。device:arm64 のスライスしか持たない
- device:arm64 と simulator:arm64 は同一アーキテクチャのため `lipo` で 1 つの fat ファイルにまとめられない (`lipo: same architectures (arm64) found` で失敗する)。個別の `libwebrtc.a` として成果物に含める必要がある
- `ios_sdk` ターゲットが生成する `WebRTC.xcframework` には simulator:arm64 が含まれるが、webrtc-rs が参照するのは `ios` ターゲットの `libwebrtc.a` であり、こちらには無い

## 設計方針

- `build_webrtc_ios` で device:arm64 に加えて simulator:arm64 をビルドする
  - device は既存の `IOS_ARCHS` ループと `lipo` をそのまま使い、`webrtc_build_dir/libwebrtc.a` を生成する (現行どおり)
  - シミュレーターはビルド対象のリストを追加し (例: `IOS_SIMULATOR_ARCHS = ["simulator:arm64"]`)、GN 引数の `target_environment` を `simulator` にしてビルドする。`ios_deployment_target` は per-device で `IOS_MINIMUM_DEPLOYMENT_TARGET` から取得する既存処理をそのまま使う
  - シミュレーターの GN ビルドディレクトリは device と同じ構造で `webrtc_build_dir/simulator/arm64` とし、生成された `libwebrtc.a` を配布物の `lib/simulator/libwebrtc.a` として同梱する
- `package_webrtc` の `ios` 分岐に `lib/simulator/libwebrtc.a` の同梱を追加する
- ライセンス生成 (`generate_licenses.py`) の走査対象にシミュレーターのビルドディレクトリ (`webrtc_build_dir/simulator/arm64`) を追加する
- device の `lib/libwebrtc.a` と `_build/ios/<profile>/webrtc/libwebrtc.a` は現行のまま変更しない (既存利用者に影響を与えない)
- 配布物の `lib/simulator/libwebrtc.a` が正本の契約であり、webrtc-rs 側からの参照方法 (配布物 / ローカルビルド) は webrtc-rs の issue で扱う
- `webrtc.ios_sim.tar.gz` のような別アーカイブに分ける案もあるが、同一ソース・同一パッチの成果物であり、webrtc-rs は既存の `webrtc.ios.tar.gz` の解決を流用できるため同一アーカイブに含める
- `ios_sdk` ターゲットは変更しない (別 SDK 向けであり、本 issue の対象外)
- `DEPS` の `IOS_DEPLOYMENT_TARGET` は device / simulator とも `14.0` で同じ値のため変更しない

## 完了条件

- `python3 run.py build ios && python3 run.py package ios` が成功する
- `webrtc.ios.tar.gz` に `lib/libwebrtc.a` (device:arm64) と `lib/simulator/libwebrtc.a` (simulator:arm64) が含まれる
- device 向け `lib/libwebrtc.a` が `lipo -info` で arm64、`otool -l` の LC_BUILD_VERSION で platform 2 (iOS) と確認できる
- simulator 向け `lib/simulator/libwebrtc.a` が `lipo -info` で arm64、`otool -l` の LC_BUILD_VERSION で platform 7 (iOS Simulator) と確認できる
- `ios_sdk` ターゲットの成果物に差分がない
- GitHub Actions の `build-macos` で `ios` / `ios_sdk` のビルドが成功する
- CHANGES.md に変更履歴が追記されている

## 変更履歴案

- [ADD] `webrtc.ios.tar.gz` に iOS シミュレーター (simulator:arm64) 向け `libwebrtc.a` を追加する

## 解決方法

未着手
