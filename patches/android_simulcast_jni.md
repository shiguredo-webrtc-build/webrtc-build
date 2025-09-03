# android_simulcast_jni.patch の解説

このドキュメントは、`android_simulcast_jni.patch` の目的・変更点・使い方をまとめたものです。パッチは以下の2点を、Android 側の最小変更で満たすことを狙っています。

- W3C 互換の `scalabilityMode` / `scaleResolutionDownTo` を Java ↔ C++ で正しく往復し、legacy 判定を外して VP9/AV1 のサイマルキャスト（複数 SSRC）を維持できるようにする
- SDK に独自 `.so` を同梱せず、libwebrtc 側の Java+JNI から `SimulcastEncoderAdapter` を直接利用できるようにする

---

## 背景・目的

- libwebrtc の送信側では、VP9/AV1 に対し旧来挙動（legacy）のゲートがあり、以下の条件を満たすとゲートが外れ、複数 SSRC のサイマルキャストが維持されます。
  - encodings のいずれかで `scalabilityMode` が指定されている
  - かつ `scaleResolutionDownBy` または `scaleResolutionDownTo` が指定されている
- また、`setParameters` 時の `scalabilityMode` は codec list の `scalability_modes` に含まれている必要があります（含まれない場合は INVALID_MODIFICATION）。
- 本パッチは、上記を Android（Java）→ C++ で確実に満たしつつ、Java から `SimulcastEncoderAdapter` を直接使える薄いファクトリを追加します。SDK 側に .so を持たせる必要はありません。

---

## 変更点（概要）

1) `RtpParameters`（Java）への最小追加
- 追加クラス: `ResolutionRestriction`（W3C の `RTCResolutionRestriction` 互換）
  - フィールド: `maxWidth`, `maxHeight`（いずれも `Integer` / nullable）
- 追加フィールド: `RtpParameters.Encoding`
  - `@Nullable String scalabilityMode`
  - `@Nullable ResolutionRestriction scaleResolutionDownTo`
- JNI コンストラクタ拡張（`@CalledByNative("Encoding")`）
  - 末尾に `scalabilityMode` と `scaleResolutionDownTo` の幅/高（`Integer`）を引数として追加
  - 幅/高がどちらも non-null の場合のみ `scaleResolutionDownTo` オブジェクトを生成
- ゲッター追加
  - `getScalabilityMode()`
  - `getScaleResolutionDownToWidth()` / `getScaleResolutionDownToHeight()`

2) JNI ブリッジ（Encoding のみ）
- `sdk/android/src/jni/pc/rtp_parameters.cc`
  - C++ → Java（`NativeToJavaRtpEncodingParameter`）で `scalability_mode` と `scale_resolution_down_to` を追加で渡す
  - Java → C++（`JavaToNativeRtpEncodingParameters`）で上記値を読み取り、`RtpEncodingParameters` に設定
  - `#include "api/video/resolution.h"` を追加（`Resolution` 構築のため）

3) codec list への最小広告（VP9/AV1 に L1T1）
- `sdk/android/src/jni/video_codec_info.cc`
  - `VideoCodecInfo` → `SdpVideoFormat` 変換時、VP9/AV1 の場合に限って `scalability_modes = { L1T1 }` を追加
  - `setParameters` の `CheckScalabilityModeValues` を確実に通すための最小広告

4) Simulcast を直接使う Java+JNI の最小追加
- Java 側（`video_java` に含める）
  - `api/org/webrtc/SimulcastVideoEncoder.java`
    - `WrappedNativeVideoEncoder` を継承、`createNative()` で JNI へ委譲
  - `api/org/webrtc/SimulcastVideoEncoderFactory.java`
    - `VideoEncoderFactory` 実装。`createEncoder()` で上記エンコーダを返す
    - `getSupportedCodecs()` は primary + fallback の和集合（重複除去）
- JNI 側
  - `src/jni/simulcast_video_encoder.cc/.h`
    - `Java_org_webrtc_SimulcastVideoEncoder_nativeCreateEncoder(...)`
      - `VideoCodecInfo` を `SdpVideoFormat` に変換
      - `JavaToNativeVideoEncoderFactory(...)` で factory をネイティブ化
      - `new SimulcastEncoderAdapter(env, primary, fallback, format)` を生成してポインタを返却
    - 備考: `SimulcastEncoderAdapter` は factory を所有しないため、JNI 側では工場ラッパを意図的にリーク（小規模）させて寿命を保ちます（従来パッチと同様の割り切り）

5) BUILD.gn の更新
- `sdk/android/BUILD.gn`
  - `video_java` の `sources` に Java 2 ファイルを追加
  - `rtc_library("simulcast_jni")` を追加（dep: `:base_jni`, `:video_jni`, `:native_api_codecs`, `../../media:rtc_simulcast_encoder_adapter`）
  - `rtc_shared_library("libjingle_peerconnection_so")` に `:simulcast_jni` を追加

---

## 期待する効果と挙動

1) Simulcast のゲート（legacy 判定）の解除
- encodings のいずれかで以下が成立すれば、legacy から脱し、複数 SSRC のサイマルキャストが維持されます。
  - `scalabilityMode` が指定されている
  - かつ `scaleResolutionDownBy` または `scaleResolutionDownTo` が指定されている

2) `setParameters` の検証
- `pc/rtp_sender.cc` → `media/base/media_engine.cc` の `CheckScalabilityModeValues` は、指定された `scalabilityMode` が codec list に存在する必要あり
- 本パッチで VP9/AV1 に L1T1 を最小広告するため、`scalabilityMode="L1T1"` は必ず受理され、値が消されません

3) SDK 側は .so 追加不要
- Java から `SimulcastVideoEncoderFactory` を使うだけで、内部的に `SimulcastEncoderAdapter` を直接利用できます

---

## 使い方（SDK 側）

- 既存の `SimulcastVideoEncoderFactoryWrapper` などから、`org.webrtc.SimulcastVideoEncoderFactory` をこれまで通り利用してください（コード変更不要）
- 送信パラメータ設定（例）
  - encodings の各 `RtpParameters.Encoding` に対して最低限:
    - `scalabilityMode = "L1T1"`
    - `scaleResolutionDownBy` もしくは `scaleResolutionDownTo`（`ResolutionRestriction(maxWidth, maxHeight)`）
  - Kotlin 例（概念的）:
    ```kotlin
    sender.parameters = sender.parameters.apply {
      encodings.forEachIndexed { _, e ->
        e.scalabilityMode = "L1T1"
        e.scaleResolutionDownTo = RtpParameters.ResolutionRestriction(1280, 720)
      }
    }
    ```

---

## ビルド手順（webrtc-build の run.py を使用）

このパッチは shiguredo/webrtc-build の仕組みで自動適用・ビルドする想定です。手動で `gn gen`/`ninja` は不要です。

1) パッチの配置と run.py のパッチリスト変更（必須）
- 本ファイルと同じディレクトリに `android_simulcast_jni.patch` があることを確認
- `webrtc-build/run.py` の `PATCHES["android"]` を編集し、以下を反映
  - 削除: `android_simulcast.patch`, `android_add_scale_resolution_down_to.patch`
  - 追加: `android_simulcast_jni.patch`
  - 配置順: 既存の `android_simulcast.patch` があった位置に置き換える（他のパッチ順は維持）

  例（概念・抜粋）:
  ```python
  PATCHES = {
      "android": [
          "add_deps.patch",
          # ... 省略 ...
          "android_webrtc_version.patch",
          "android_fixsegv.patch",
          # "android_simulcast.patch",  # ← 削除
          # "android_add_scale_resolution_down_to.patch",  # ← 削除
          "android_simulcast_jni.patch",  # ← 追加（置き換え）
          "android_hardware_video_encoder.patch",
          # ... 省略 ...
      ],
  }
  ```

2) 取得（初回のみ）または再適用
- 初回やクリーン取得時は、build だけで自動的にフェッチ＋パッチ適用まで行われます
- 既にソースがあり、当該パッチだけを差し替えたい場合の例
  ```bash
  cd /Users/voluntas/shiguredo/webrtc-build
  python3 run.py revert android --patch android_simulcast_jni.patch
  ```

3) ビルド
```bash
cd /Users/voluntas/shiguredo/webrtc-build
# Release ビルド（デフォルト）で Android 用 libwebrtc をビルド
python3 run.py build android

# 必要に応じてオプション
# - デバッグビルド: --debug
# - AAR を作らない: --webrtc-nobuild-android-aar
# - GN を再生成: --webrtc-gen / 強制再生成: --webrtc-gen-force
```

4) 生成物
- `_build/android/release/webrtc/aar/libwebrtc.aar` と `_build/android/release/webrtc/aar/webrtc.jar`
- 各 ABI の `libwebrtc.a`: `_build/android/release/webrtc/<abi>/libwebrtc.a`

---

## 既知の注意点 / 制限

- 工場ラッパの寿命管理
  - `SimulcastEncoderAdapter` は factory を所有しないため、JNI で生成した工場ラッパを解放せず寿命を保つ実装（小規模リーク）になっています。必要であれば後続で解放機構を追加可能です
- `scalability_modes` の広告は最小（L1T1 のみ）
  - Simulcast のゲートを外す目的には十分です。L2/L3 を許可したい場合は codec list の広告を拡張してください
- 既定の Java 側 Factory（`DefaultVideoEncoderFactory` 等）との併用
  - 本パッチの `SimulcastVideoEncoderFactory` は primary/fallback を合成し、エンコーダ生成時に `SimulcastEncoderAdapter` を利用します
- 依存
  - 既存の `VideoEncoderFactoryWrapper`/`VideoCodecInfoToSdpVideoFormat` などの JNI/utility に依存しています

---

## 動作確認のヒント

- Offer/Answer の送受信後、送信側が複数 SSRC を持っていることを確認（Sender の stats、SDP、ログなど）
- `scalabilityMode`/`scaleResolutionDownTo` が `setParameters` 後に保持されていることを確認
- ログ上で `SimulcastEncoderAdapter` が利用されているか確認（実装名）

---

## 変更ファイル一覧（参考）

- Java
  - `sdk/android/api/org/webrtc/RtpParameters.java`
  - `sdk/android/api/org/webrtc/SimulcastVideoEncoder.java`
  - `sdk/android/api/org/webrtc/SimulcastVideoEncoderFactory.java`
- JNI/C++
  - `sdk/android/src/jni/pc/rtp_parameters.cc`
  - `sdk/android/src/jni/video_codec_info.cc`
  - `sdk/android/src/jni/simulcast_video_encoder.cc`
  - `sdk/android/src/jni/simulcast_video_encoder.h`
- GN
  - `sdk/android/BUILD.gn`

---

## まとめ

- 本パッチは、`scalabilityMode/scaleResolutionDownTo` の最小 JNI と、`SimulcastEncoderAdapter` を直接使う薄い Java+JNI を同時に導入します
- SDK 側に .so を追加せず、Android で VP9/AV1 の複数 SSRC サイマルキャストを実現することを目標としています
