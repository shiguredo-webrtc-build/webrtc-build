# パッチ解説

## 4k.patch


## add_dep_zlib.patch


## android_fixsegv.patch

Android にて映像フレームの処理時にクラッシュするいくつかの現象を修正するパッチ。

同等の機能が本家に実装されるか、 PR を出して取り込まれたら削除する。

## android_simulcast.patch

Android でのサイマルキャストのサポートを追加するパッチ。この実装は C++ の `SimulcastEncoderAdapter` の簡単なラッパーであり、既存の仕様に破壊的変更も行わない。

以下の API を追加する。

- `SimulcastVideoEncoder`
- `SimulcastVideoEncoderFactory`

同等の機能が本家に実装されるか、 PR を出して取り込まれたら削除する。

## android_webrtc_version.patch

Android API に libwebrtc のビルド時のバージョンを取得する API を追加する。

以下の API を追加する。

- `WebrtcBuildVersion`

同等の機能が本家に実装されるか、 PR を出して取り込まれたら削除する。

## android_hardware_video_encoder.patch

解像度が16の倍数でない場合、 HardwareVideoEncoder 初期化時などのチェックでエラーが発生するようになった。  
Android CTS では解像度が16の倍数のケースしかテストされておらず、かつ、解像度が16の倍数でない映像を受信した際に問題が発生する端末があったことが理由で、上記のチェックが実装された。

参照: https://webrtc-review.googlesource.com/c/src/+/229460

このパッチでは、 Sora Android SDK 側でチェックを無効化する選択肢を提供するために、 libwebrtc に実装されたチェックを無効化している。  
チェックを無効化するオプションがメインストリームに実装された場合、このパッチは削除できる。  
https://bugs.chromium.org/p/webrtc/issues/detail?id=13973

## ios_bitcode.patch

現在は xcode の clang でなくても bitcode に対応したため xcode の clang 対応が落とされたが、その変更に伴う bitcode がらみのビルドエラーが生じているために、これを回避するパッチ。
関連する問題として xcode 13.0 縛りが[入っている](https://source.chromium.org/chromium/chromium/src/+/main:build/config/ios/BUILD.gn;l=130)ために build.yml でも xcode 13.0 指定をおこなっている。様子を見て解除すること。

## ios_manual_audio_input.patch

iOS でのマイク不使用時のパーミッション要求を抑制するパッチ。詳細は `docs/patch_ios_manual_audio_input.md` を参照すること。

同等の機能が本家に実装されるか PR を出して取り込まれたら削除するが、デフォルトの仕様の破壊的変更を含むので難しいと思われる。

## ios_simulcast.patch

iOS でのサイマルキャストのサポートを追加するパッチ。この実装は C++ の `SimulcastEncoderAdapter` の簡単なラッパーであり、既存の仕様に破壊的変更も行わない。

以下の API を追加する。

- `RTCVideoEncoderFactorySimulcast`
- `RTCVideoEncoderSimulcast`

同等の機能が本家に実装されるか、 PR を出して取り込まれたら削除する。

## macos_av1.patch


## macos_h264_encoder.patch


## macos_screen_capture.patch


## macos_simulcast.patch


## nacl_armv6_2.patch


## ubuntu_nolibcxx.patch


## windows_build_gn.patch

C++17 で deprecated されているコードを多数含むために _SILENCE_ALL_CXX17_DEPRECATION_WARNINGS を追加している。

## ssl_verify_callback_with_native_handle.patch

WebRTC は Let's Encrypt のルート証明書を入れていないため、検証コールバックで検証する必要がある。
しかし WebRTC の検証コールバックから渡される `BoringSSLCertificate` には、検証に失敗した証明書だけが渡され、証明書チェーンが一切含まれていないため、正しく検証ができない。
なので BoringSSL のネイティブハンドル `SSL*` を `BoringSSLCertificate` に含めるようにする。

WebRTC は Let's Encrypt を含めていないので、Let's Encrypt の検証がうまくできないという点から本家に取り込んでもらうのは難しいと思われる。
証明書チェーンが利用できない、という話を起点にすれば取り込んでもらえるかもしれない。
ただし `SSL*` を渡すのは `OpenSSLCertificate` との兼ね合いを考えると筋が悪いので、本家用のパッチを書くのであれば清書する必要がある。
