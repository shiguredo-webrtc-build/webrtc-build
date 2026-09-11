# iOS の ObjC ブリッジで TURN-TLS のクライアント証明書を設定できるようにする

- Created: 2026-09-11
- Completed:
- Branch: feature/add-ios-turn-tls-client-certificate
- Polished:

## 目的

iOS SDK から TURN-TLS 接続でクライアント証明書（クライアント認証 / mTLS）を指定できるようにする。

libwebrtc (C++) 側は `turn_tls_client_certificate.patch` (https://github.com/shiguredo-webrtc-build/webrtc-build/pull/146) で `PeerConnectionInterface::IceServer::tls_client_identity` に対応済みだが、iOS の ObjC ブリッジ `RTCIceServer` にはクライアント証明書を渡す経路がなく、`WebRTC.xcframework` 経由では設定できない。本 issue では ObjC ブリッジを拡張するパッチを追加する。

iOS SDK が `libwebrtc_c.xcframework` (webrtc_c) へ移行すれば C++ API に直接アクセスできるため本パッチは不要になるが、移行は当面先のため現行 `WebRTC.xcframework` 向けに作成する。

## 現状

### C++ 側は対応済み

`turn_tls_client_certificate.patch` で `PacketSocketTcpOptions` / `RelayServerConfig` / `PeerConnectionInterface::IceServer` に `std::unique_ptr<SSLIdentity> tls_client_identity` が追加され、`IceServer` から `RelayServerConfig` / `TurnPort` / `SSLAdapter` まで伝搬する。

`patches/README.md` の `turn_tls_client_certificate.patch` の項には「このパッチには iOS / Android SDK の変更は含まれていない」と明記されている。

### iOS の ObjC ブリッジは未対応

`RTCIceServer` が公開するのは `urlStrings` / `username` / `credential` / `tlsCertPolicy` / `hostname` / `tlsAlpnProtocols` / `tlsEllipticCurves` のみで、クライアント証明書を受け取る初期化子やプロパティを持たない。

`RTCIceServer.mm` の `- (webrtc::PeerConnectionInterface::IceServer)nativeServer` が native の `IceServer` を構築するが `tls_client_identity` を設定していない。`RTCConfiguration.mm` は `iceServer.nativeServer` の結果を `nativeConfig->servers` に渡すため、TURN-TLS の TLS ハンドシェイクでクライアント証明書を提示できない。

### Android は対応済み

Android は `android_turn_tls_client_certificate.patch` (https://github.com/shiguredo-webrtc-build/webrtc-build/pull/149) で `PeerConnection.IceServer.Builder.setTlsClientCertificate(privateKeyPem, certificatePem)` を追加し、JNI 側で `SSLIdentity::CreateFromPEMChainStrings()` から `tls_client_identity` を生成している。iOS には相当するパッチが存在しない。

## 設計方針

- Android の `setTlsClientCertificate(privateKeyPem, certificatePem)` と揃え、`RTCIceServer` にクライアント秘密鍵・証明書 (PEM) を指定する API を追加する。
- `RTCIceServer.mm` の `nativeServer` で `SSLIdentity::CreateFromPEMChainStrings()` を使い `tls_client_identity` を設定する。`certificatePem` には単体証明書でも証明書チェーン (concatenated PEM) でも指定できるようにする。
- 単体証明書と証明書チェーンを呼び分けない。Android 実装と同じく `CreateFromPEMChainStrings()` に一本化する。
- 秘密鍵と証明書は対で指定必須とする。片方のみの指定はエラーにする。
- 秘密鍵・証明書の PEM は `description` やログに出力しない。
- `patches/ios_turn_tls_client_certificate.patch` として追加し、`run.py` の `PATCHES` の `ios` と `ios_sdk` に登録する。登録先は ObjC ブリッジに証明書チェーンを渡す `ios_ssl_certificate_verifier_chain.patch` と同じ扱いにする。
- `patches/README.md` にパッチ解説を追加する。
- sora-ios-sdk 側の公開 API と実機検証は本 issue の範囲外とする。sora-ios-sdk の `issues/pending/0064-add-turn-tls-client-certificate.md` で扱う。

## 完了条件

- `patches/ios_turn_tls_client_certificate.patch` が追加され、`run.py` の `PATCHES` の `ios` と `ios_sdk` に登録されていること
- `RTCIceServer` の ObjC API からクライアント秘密鍵・証明書 (PEM) を指定でき、native の `PeerConnectionInterface::IceServer::tls_client_identity` に反映されること
- 単体証明書と証明書チェーンの両方を指定できること
- 秘密鍵と証明書を片方だけ指定した場合はエラーになること
- パッチ適用後の `ios` / `ios_sdk` ビルドが成功すること
- `patches/README.md` にパッチ解説が追加されていること
- CHANGES.md に追記があること

## 変更履歴案

- [ADD] iOS の ObjC ブリッジで TURN-TLS のクライアント証明書を設定できるようにする

## 解決方法

未着手
