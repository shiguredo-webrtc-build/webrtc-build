# パッチ解説

## 4k.patch


## add_dep_zlib.patch


## android_fixsegv.patch


## android_onremovetrack.patch


## android_simulcast.patch


## android_webrtc_version.patch


## ios_manual_audio_input.patch


## ios_simulcast.patch


## macos_av1.patch


## macos_h264_encoder.patch


## macos_screen_capture.patch


## macos_simulcast.patch


## macos_statistics.patch


## nacl_armv6_2.patch


## ubuntu_nolibcxx.patch


## windows_add_deps.patch


## ssl_verify_callback_with_native_handle.patch

WebRTC は Let's Encrypt のルート証明書を入れていないため、検証コールバックで検証する必要がある。
しかし WebRTC の検証コールバックから渡される `BoringSSLCertificate` には、検証に失敗した証明書だけが渡され、証明書チェーンが一切含まれていないため、正しく検証ができない。
なので BoringSSL のネイティブハンドル `SSL*` を `BoringSSLCertificate` に含めるようにする。

WebRTC は Let's Encrypt を含めていないので、Let's Encrypt の検証がうまくできないという点から本家に取り込んでもらうのは難しいと思われる。
証明書チェーンが利用できない、という話を起点にすれば取り込んでもらえるかもしれない。
ただし `SSL*` を渡すのは `OpenSSLCertificate` との兼ね合いを考えると筋が悪いので、本家用のパッチを書くのであれば清書する必要がある。
