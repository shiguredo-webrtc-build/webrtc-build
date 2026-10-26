# upstream の WebRTC issue 42221823 の対応状況を確認する

- Created: 2026-10-26
- Completed: {YYYY-MM-DD}
- Branch: feature/debug-check-upstream-os-trust-store
- Polished: {YYYY-MM-DD}

## 目的

upstream の WebRTC issue 42221823 が目指す「`ssl_roots.h` に埋め込んだ CA ではなく、OS の trust store で TURN/TLS の証明書を検証する」対応が libwebrtc に入っているかを確認する。

現在の libwebrtc は `rtc_base/ssl_roots.h` の組み込み CA で TURN/TLS の証明書を検証しており、この一覧には Let's Encrypt (ISRG Root X1/X2) が含まれない。そのため Let's Encrypt の証明書を使う TURN サーバーに接続できない。webrtc-build は `patches/android_ssl_certificate_verifier_chain.patch` と `patches/ios_ssl_certificate_verifier_chain.patch` で、アプリ側の検証器に証明書チェーン全体を渡せるようにして回避している。

upstream の対応状況を確認し、これらのパッチを削除できるか、OS trust store 対応を取り込む必要があるかを判断する材料にする。

## 現状

### upstream の issue と main の状態

- issue 42221823 は 2026-10-26 時点で Assigned (P2, S4) のまま open。assignee は solenberg@webrtc.org。直近の更新は 2026-10-23。
  https://issues.webrtc.org/issues/42221823
- 確認した upstream main の HEAD は `83de8057` (2026-10-25)。
- issue が本題にしている「OS の trust store を使う」実装は main に存在しない。`X509TrustManager`、`SecTrust`、`CertVerifyCertificateChainPolicy`、`SecPolicyCreateSSL` などをツリーから検索しても該当しない。
- standalone の libwebrtc は今も `rtc_base/ssl_roots.h` の組み込み CA で検証している。

### upstream に入った関連変更

- CL 416880 (2025-10-22, main@{#46013}, `c1835dc9ae82`): `webrtc::SSLCertificateVerifier` に `VerifyChain(const SSLCertChain&)` を追加。X509 と CRYPTO_BUFFER の両経路でチェーン全体が渡る。`Verify()` は残り、既定の `VerifyChain()` は leaf のみを `Verify()` に渡す。
  https://webrtc-review.googlesource.com/c/src/+/416880
- CL 510920 (2026-10-23, main@{#49033}, `8cb3d509a138`): `webrtc.gni` の `rtc_builtin_ssl_root_certificates` を `!build_with_chromium` に変更。Chromium ビルド時のみ built-in roots を無効化する。standalone は対象外。
  https://webrtc-review.googlesource.com/c/src/+/510920
- CL 510761 (2026-10-22, main@{#49017}, `7796203a9c9a`): 侵害された eMudhra 中間 CA の SPKI ハッシュを distrust リストに追加。
  https://webrtc-review.googlesource.com/c/src/+/510761
- CL 510080 (2026-10-20, main@{#48990}): `ssl_roots.h` を pki.goog から更新。main の roots は 21 個で、ISRG は含まない。
  https://webrtc-review.googlesource.com/c/src/+/510080
- CL 510260 (2026-10-20, main@{#48989}): `generate_sslroots.py` の整形。
  https://webrtc-review.googlesource.com/c/src/+/510260

### upstream に入っていないもの

- Android の `X509TrustManager` / iOS の `SecTrust` を使う検証。
- Java の `SSLCertificateVerifier` は `verify(byte[])` のまま。JNI wrapper (`sdk/android/src/jni/pc/ssl_certificate_verifier_wrapper.cc`) は `Verify()` だけを実装しており、C++ の `VerifyChain()` を Java に公開していない。
- ObjC の `RTCSSLCertificateVerifier` は `verify:` のみ。`sdk/objc/native/api/ssl_certificate_verifier.mm` の adapter も `Verify()` だけを実装している。
- standalone ビルドで `ssl_roots.h` を廃止する変更。

### このリポジトリのパッチとの関係

- `patches/android_ssl_certificate_verifier_chain.patch` と `patches/ios_ssl_certificate_verifier_chain.patch` は、upstream の C++ `VerifyChain()` を Java / ObjC に橋渡しするパッチ。upstream は C++ までしか対応していないため、これらのパッチはまだ必要。
- `patches/ssl_verify_callback_with_native_handle.patch` の削除は別 issue の対象であり、本 issue では扱わない。

### ビルド対象バージョン (M156) の状態

- `VERSION` の M156 (`refs/branch-heads/8078`) には、2026-10 の変更は入っていない。`webrtc.gni` の `rtc_builtin_ssl_root_certificates` は `true` で、`ssl_roots.h` は 36 roots。C++ の `VerifyChain()` は入っている。
- Java / ObjC が leaf のみという状態は main と同じ。

### 参考: downstream の実装

- webrtc-sdk fork の PR #277 (2026-08-13 merge, `m144_release` ベース) は、Apple / Windows / Android で OS の trust store にフォールバックする実装を持つ。issue のコメント #21 でも参照されているが、upstream には取り込まれていない。
  https://github.com/webrtc-sdk/webrtc/pull/277

## 設計方針

- 本 issue は調査のみとし、コード変更やパッチ削除は行わない。
- 確認する対象:
  - issue 42221823 の status とリンクされている CL (Gerrit の `message:42221823` 検索)
  - `rtc_base/ssl_certificate.h` の `SSLCertificateVerifier::VerifyChain`
  - `rtc_base/openssl_adapter.cc` の `SSLVerifyInternal` など、チェーン検証の呼び出し箇所
  - `webrtc.gni` の `rtc_builtin_ssl_root_certificates` と `rtc_base/BUILD.gn` の `ssl_roots.h`
  - `sdk/android/api/org/webrtc/SSLCertificateVerifier.java` と `sdk/android/src/jni/pc/ssl_certificate_verifier_wrapper.cc`
  - `sdk/objc/base/RTCSSLCertificateVerifier.h` と `sdk/objc/native/api/ssl_certificate_verifier.mm`
  - 実際にビルドするブランチ (M156 など) へのバックポートの有無
- 判定:
  - upstream に OS trust store 対応、または Java / ObjC へのチェーン公開が入った場合は、パッチ削除または置換の実装 issue を別途起票する。
  - 入っていない場合はパッチを維持し、libwebrtc の更新時に再確認する。
- 本 issue の結論は、パッチ削除の実施判断ではなく、次に何をするかの判断までとする。

## 完了条件

- 確認時点の upstream main の commit hash と issue の status が記録されていること。
- C++ / Java / ObjC のそれぞれについて、チェーンが渡るかどうかが記録されていること。
- OS trust store の実装が upstream にあるかどうかが記録されていること。
- ビルド対象のバージョン (M156 など) への反映状況が記録されていること。
- パッチの要否が判断され、必要なら削除・置換の実装 issue が起票されていること。
- パッチを維持する場合、次回の確認契機 (libwebrtc 更新時など) が記録されていること。

## 解決方法

未着手
