# ssl_verify_callback_with_native_handle.patch を削除する

- Created: 2026-09-11
- Completed: {YYYY-MM-DD}
- Branch: feature/remove-ssl-verify-native-handle-patch
- Polished: {YYYY-MM-DD}

## 目的

下流の Sora C++ SDK が `RTCSSLVerifier::Verify()` から `RTCSSLVerifier::VerifyChain(const webrtc::SSLCertChain&)` へ移行し、証明書チェーンを native handle 経由で取得する必要がなくなったため、`ssl_verify_callback_with_native_handle.patch` を削除する。パッチ無しの libwebrtc をビルドできるようにする。

## 現状

- `patches/ssl_verify_callback_with_native_handle.patch` は、`BoringSSLCertificate` に `SSL*` の native handle を持たせ、検証コールバックから `SSL_get_peer_cert_chain` で証明書チェーンを取得できるようにするパッチである
- 以前の WebRTC は検証コールバックに検証失敗した証明書だけを渡し、証明書チェーンを取得できなかったため、このパッチで native handle を渡す必要があった
- upstream の https://webrtc-review.googlesource.com/c/src/+/416880 で `SSLCertificateVerifier` に `VerifyChain(const SSLCertChain&)` が追加され、完全な証明書チェーンを取得できるようになった
- Sora C++ SDK は `include/sora/rtc_ssl_verifier.h` と `src/rtc_ssl_verifier.cpp` で `VerifyChain` を実装済みで、native handle (`.ssl()`) を利用していない。`CHANGES.md` に `[UPDATE] RTCSSLVerifier::Verify() を RTCSSLVerifier::VerifyChain() に変更する` のエントリがある
- パッチは `run.py` の全 15 ターゲットのパッチ一覧に登録されており、`patches/README.md` に解説がある

## 設計方針

- `patches/ssl_verify_callback_with_native_handle.patch` を削除する
- `run.py` の全 15 ターゲットのパッチ一覧から `ssl_verify_callback_with_native_handle.patch` を削除する
- `patches/README.md` の `ssl_verify_callback_with_native_handle.patch` の解説節を削除する
- 削除後、下流の Sora C++ SDK の `DEPS` の `WEBRTC_BUILD_VERSION` をパッチ無しでビルドした libwebrtc のバージョンに更新する
- `patches/ios_ssl_certificate_verifier_chain.patch` と `patches/android_ssl_certificate_verifier_chain.patch` は ObjC / JNI ブリッジに証明書チェーンを渡す別目的のパッチであり、本 issue では削除しない

## 実装時期

Sora C++ SDK の `VerifyChain` 移行が正式にリリースされ、しばらく問題が発生していないという運用実績が積まれてから実施する。それまでは本 issue は open のままにする。

## 完了条件

- `patches/ssl_verify_callback_with_native_handle.patch` が削除されていること
- `run.py` の全ターゲットのパッチ一覧に `ssl_verify_callback_with_native_handle.patch` が存在しないこと
- `patches/README.md` に `ssl_verify_callback_with_native_handle.patch` の解説が存在しないこと
- パッチ無しの libwebrtc をビルドでき、下流の Sora C++ SDK が `WEBRTC_BUILD_VERSION` を更新してビルド・接続できること

## 解決方法

未着手
