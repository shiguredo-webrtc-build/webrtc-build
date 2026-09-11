# iOS と macOS の treat_warnings_as_errors=false を外す

- Created: 2026-09-11
- Completed: {YYYY-MM-DD}
- Branch: feature/remove-treat-warnings-as-errors
- Polished: {YYYY-MM-DD}

## 目的

iOS と macOS のビルドで指定している `treat_warnings_as_errors=false` を外し、コンパイラ警告をビルドエラーとして検出できるようにする。

以前は iOS と macOS のビルドに Xcode (システム) の clang を利用していたため、システム由来の警告を回避する目的で `treat_warnings_as_errors=false` を指定していた。現在は libwebrtc が提供する clang を利用するようになり、制御できないシステム由来の警告を避ける必要がなくなったため、この指定は不要になっている。

`treat_warnings_as_errors=false` を残したままだと、libwebrtc のバージョンアップで新たに発生した警告を見逃す。外しておくことで、今後のバージョンアップ時に警告を早期に検出できる。

## 現状

`run.py` の次の 2 箇所で `treat_warnings_as_errors=false` を指定している。

- `IOS_COMMON_GN_ARGS` (`ios` / `ios_sdk` ビルドで利用)
- `build_webrtc` の `macos_arm64` 向け GN 引数

iOS ビルドで `treat_warnings_as_errors=false` を外したところ、以下の警告がエラーとして検出された。いずれもパッチで作成・変更している Objective-C++ ファイルの警告である。

- 代入結果を条件式として使っている箇所の `-Widiomatic-parentheses`
  - `RTCVideoDecoderH265.mm` の `init` (`patches/h265_ios.patch` が新規作成)
  - `RTCVideoEncoderH265.mm` の `initWithCodecInfo:` (`patches/h265_ios.patch` が新規作成)
  - `RTCVideoEncoderFactorySimulcast.mm` の `initWithPrimary:fallback:` (`patches/ios_simulcast.patch` が新規作成)
- 未使用変数の `-Wunused-const-variable`
  - `RTCVideoEncoderH265.mm` の `ErrorCallbackDefaultValue` (`patches/h265_ios.patch` が新規作成)
- 廃止された `webrtc::BitrateAdjuster` の 2 引数コンストラクタを利用していることによる `-Wdeprecated-declarations`
  - `RTCVideoEncoderH265.mm` の `_bitrateAdjuster` の初期化 (`patches/h265_ios.patch` が新規作成)

## 設計方針

- `run.py` の `IOS_COMMON_GN_ARGS` と `macos_arm64` 向け GN 引数から `treat_warnings_as_errors=false` を削除する
- `patches/h265_ios.patch` を次のように修正する
  - `RTCVideoDecoderH265.mm` と `RTCVideoEncoderH265.mm` の `if (self = [super init])` を `if ((self = [super init]))` にする
  - `RTCVideoEncoderH265.mm` の未使用変数 `ErrorCallbackDefaultValue` を削除する
  - `RTCVideoEncoderH265.mm` の `webrtc::BitrateAdjuster(.5, .95)` を、`Clock` を引数に取る新しいコンストラクタ `webrtc::BitrateAdjuster(webrtc::Clock::GetRealTimeClock(), .5, .95)` に変更する
- `patches/ios_simulcast.patch` を次のように修正する
  - `RTCVideoEncoderFactorySimulcast.mm` の `if (self = [super init])` を `if ((self = [super init]))` にする
- 上記を修正したうえで、`ios` / `ios_sdk` / `macos_arm64` の各ビルドで `treat_warnings_as_errors=false` を外してもビルドが成功することを確認する
- 修正で新たに別の警告が検出された場合は、同じく警告を出している側を修正する

## 完了条件

- `run.py` に `treat_warnings_as_errors=false` が存在しないこと
- `ios` / `ios_sdk` / `macos_arm64` のビルドが `treat_warnings_as_errors=false` なしで成功すること
- CHANGES.md に変更履歴が追記されていること

## 変更履歴案

- [CHANGE] iOS, macOS の `treat_warnings_as_errors=false` を外す

## 解決方法

未着手
