# Android 向け Java 成果物を JNI Zero の最終 registration に追従させる

- Created: 2026-09-02
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-android-jni-zero-final-registration
- Polished: {YYYY-MM-DD}

## 目的

WebRTC M149 以降の JNI Zero 構成変更に追従し、Android 向け Java 成果物 (webrtc.jar / AAR の classes.jar) に実行時に必要な JNI Zero 生成クラスを含める。R8 による静的解析で Missing class エラーが出ないようにする。

## 経緯

### 背景

JNI Zero は Chromium が Android の Java と native code を接続する JNI binding を生成する仕組みで、WebRTC も利用している。

WebRTC M149 では、class loader の初期化方法を変更した JNI Zero の commit が取り込まれた (https://chromium.googlesource.com/chromium/src/third_party/jni_zero/+/d3c7cd15e366abf83461e9c407368227bbe57168)。この変更により、JNI Zero の初期化後は `org.jni_zero.JniZero.setJniClassLoader()` が生成クラスの `JniZeroJni` を直接呼び出すようになった。

### 問題

変更前の Android 向け Java 成果物には、JNI Zero 関連のクラスとして `JniZero.class` と `JniZero$Natives.class` しか含まれず、`JniZeroJni.class` が欠落している。WebRTC M149 以降では `JniZero` から `JniZeroJni` への直接参照があるため、R8 が参照先を解析する構成では Missing class エラーになる。

`JniZeroJni.class` だけを追加しても、`generate_jni` が作る `GEN_JNI` は Java のコンパイル用であり、最終的な native library のハッシュ化 JNI symbol には対応していない。実行時に必要なクラスは揃わない。

### PR #159 の提案

https://github.com/shiguredo-webrtc-build/webrtc-build/pull/159 (`feature/m150.7871` 向け) で以下を提案した。

- `patches/android_jni_zero_final_registration.patch` を新規作成
  - `sdk/android/BUILD.gn` の `dist_jar("libwebrtc")` に `generate_jni_registration("libwebrtc_jni_registration")` ターゲットを追加
  - `third_party/jni_zero/BUILD.gn` の `generate_jni` ターゲットの visibility に `//sdk/android:*` を追加
  - `run.py` の `android` / `android_sdk` の PATCHES リストに登録
- `patches/README.md` と `CHANGES.md` に解説を追記

### master での別対応

PR #159 が `feature/m150.7871` に未マージのまま残っている間に、master では m151 対応 (2026-07-02) で `patches/android_jni_zero_generated_java.patch` が追加された。このパッチは `generated_*_jni_java` 依存の追加に加え、`generate_jni_registration` による最終 JNI registration クラスの生成も行う。PR #159 の `android_jni_zero_final_registration.patch` より広い対応であり、本 issue の目的は master 上では既に達成されている。

### 検討した代替案

R8 ルールに `-dontwarn org.jni_zero.**` を導入し、Missing class 警告を抑制する方法も検討した。Android 実機での webrtc 実行確認では問題が起きなかった。ただし master ではパッチ方式 (`android_jni_zero_generated_java.patch`) を採用している。

### 残作業

`generate_jni_registration` は jni_zero の更新で `generate_final_jni` にリネームされた (chromium コミット 78a5ecddd742853edfb420ab4a89bd6894ce4240)。この API 変更への追従は `issues/0002-bug-ci-build-fail-on-all-platforms.md` で扱う。
