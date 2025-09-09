# android_simulcast.patch の解説

このドキュメントは、`android_simulcast.patch` の目的・変更点をまとめたものです。

## 目的

- libwebrtc の Android ライブラリでサイマルキャストが実現できるようになること

## 背景

- 現在の libwebrtc の実装では Android からサイマルキャストができません。
- C++ の `webrtc::SimulcastEncoderAdapter` に相当する機能が libwebrtc の Android ライブラリに含まれていないからです。
- Android 版のサイマルキャストを実装するにあたって以下のことを考慮する必要があります。
  - `webrtc::SimulcastEncoderAdapter` の Android 版を実装すると同時に、このエンコーダーを生成するためのファクトリも実装する必要がある
  - `webrtc::RtpEncodingParameters` の `scalability_mode`, `scale_resolution_down_by`, `scale_resolution_down_to` のどれにも値が設定されていない場合、VP9 と AV1 ではサイマルキャストが無効化される
    - ref: https://source.chromium.org/chromium/chromium/src/+/main:third_party/webrtc/media/engine/webrtc_video_engine.cc;l=2255-2276;drc=de4667eb4f071c691cfe5304210480ee61a112b0
    - また、Android 側の `webrtc::RtpEncodingParameters` に相当する `RtpParameters.Encoding` には `scalabilityMode`, `scaleResolutionDownTo` の設定が存在しない。
  - ただし、例え `webrtc::RtpEncodingParameters` の `scalability_mode` に値を設定しても、`webrtc::VideoEncoderFactory::GetSupportedFormats()` が返す `webrtc::SdpVideoFormat` の一覧に、対応する scalability mode が存在しない場合には設定することが出来ない
    - ref: https://source.chromium.org/chromium/chromium/src/+/main:third_party/webrtc/media/base/media_engine.cc;l=117-154;drc=3bd6510e6f1a508b4042e4be266f126afaa18e8c
    - また、Android 側の `webrtc::SdpVideoFormat` に相当する `VideoCodecInfo` には scalability mode の設定が存在しない
    - Android の HWA を利用するエンコーダファクトリである `HardwareVideoEncoderFactory` が実装している `getSupportedCodecs()` 関数は（`VideoCodecInfo` が scalability mode に対応していないので当然）scalability mode の設定が存在しない
- これらのことを考慮してパッチを記述する必要があります。

## やること

上記のことを踏まえると、以下のことをやる必要があります。

- `webrtc::SimulcastEncoderAdapter` の Android 版と、このエンコーダーを生成するためのファクトリの実装
- `webrtc::RtpEncodingParameters` の `scalability_mode`, `scale_resolution_down_to` に相当する機能を Android 版に追加
- `webrtc::SdpVideoFormat` に相当する `VideoCodecInfo` に scalability mode の対応を入れる
- `HardwareVideoEncoderFactory` の `getSupportedCodecs()` 関数が返す `VideoCodecInfo` に scalability mode の設定を入れる

## 変更点の概要

- `webrtc::SimulcastEncoderAdapter` の Android 版と、このエンコーダーを生成するためのファクトリも実装するために、以下の変更をしています。
  - `sdk/android/api/org/webrtc/SimulcastVideoEncoder.java` の追加
  - `sdk/android/api/org/webrtc/SimulcastVideoEncoderFactory.java` の追加
  - `SimulcastVideoEncoder` の JNI として `sdk/android/src/jni/simulcast_video_encoder.cc` の追加
  - `BUILD.gn` に、これらの追加したファイルをそれぞれ `simulcast_java` と `simulcast_jni` という名前で生成して、最終的な成果物の依存に含める。
    - なお最終的な成果物である `dist_jar("libwebrtc")` には `direct_deps_only = true` が存在しているため、`simulcast_java` は必ずここに含める必要がある。含めない場合、実行時に .class ファイルが見つからずに実行時エラーとなる。
      - ref: https://source.chromium.org/chromium/chromium/src/+/main:third_party/webrtc/sdk/android/BUILD.gn;l=33;drc=dc0a35fe850060ed606107299ccd7ad3dcbd5809
- `webrtc::RtpEncodingParameters` の `scalability_mode`, `scale_resolution_down_to` に相当する機能を Android 版に追加するため、以下の変更を行っています。
  - `sdk/android/api/org/webrtc/RtpParameters.java` に `RtpParameters.ResolutionRestriction` クラスの追加。
    - これは C++ 側の `webrtc::Resolution` に相当する。
  - `RtpParameters.Encoding` に `scalabilityMode` と `scaleResolutionDownTo` フィールドを追加し、コンストラクタでこれらを指定して初期化できるように変更したり、取得するための関数を追加。
  - `RtpParameters` と C++ 実装の `webrtc::RtpParameters` を相互に変換する JNI 実装に、`scalablityMode` と `scaleResolutionDownTo` を含める
    - この JNI 実装は `sdk/android/src/jni/pc/rtp_parameters.cc` にある。
- Android 側の `webrtc::SdpVideoFormat` に相当する `VideoCodecInfo` に scalability mode の対応を入れるため、以下の変更を行っています。
  - `sdk/android/api/org/webrtc/VideoCodecInfo.java` に `scalabilityModes` フィールドと、これを指定可能なコンストラクタと、取得するための関数を追加
  - また、`hashCode()` や `equals()` で `scalabilityModes` も見るように変更
    - これは `webrtc::SdpVideoFormat` の実装でもそうなっていたので、同様の実装にした
- `HardwareVideoEncoderFactory` の `getSupportedCodecs()` 関数が返す `VideoCodecInfo` に scalability mode の設定を入れるため、以下の変更を行っています。
  - `sdk/android/api/org/webrtc/HardwareVideoEncoderFactory.java` の `getSupportedCodecs()` 関数内で生成している `VideoCodecInfo` に scalability mode の値を設定する
    - 本当にサポートしている値だけ入れるべきだが、とりあえず L1T1, L1T2, L1T3 だけ渡しておくことにする。
      - これは VP8, H264 などの、SVC に対応していないソフトウェア実装で渡している値と同じとなる
      - ref: https://source.chromium.org/chromium/chromium/src/+/main:third_party/webrtc/modules/video_coding/codecs/vp8/vp8_scalability.h;l=18-19;drc=845d2024791ea649a25c4074bf25263b1f648ff9
      - ref: https://source.chromium.org/chromium/chromium/src/+/main:third_party/webrtc/modules/video_coding/codecs/h264/h264.cc;l=54-55;drc=845d2024791ea649a25c4074bf25263b1f648ff9
- ついでに、統計情報に `scalabilityMode` が含まれていない問題を解消するために、`sdk/android/src/jni/video_encoder_wrapper.cc` のコーデック情報を設定する部分で `CodecSpecificInfo` の `scalability_mode` に L1T1 の値を設定しています。

## 利用方法

このパッチを当てた libwebrtc を使ってサイマルキャストを実現する場合、以下のように利用して下さい。

- まずビデオエンコーダファクトリとして `SimulcastVideoEncoderFactory` を利用して下さい
- その上で `RtpParameters.Encoding` を設定する時に、`scalabilityMode`, `scaleResolutionDownBy`, `scaleResolutionDownTo` のどれかを設定して下さい
- 送信パラメータ設定（例）
    ```kotlin
    sender.parameters = sender.parameters.apply {
      encodings.forEachIndexed { _, e ->
        e.scalabilityMode = "L1T1"
        e.scaleResolutionDownTo = RtpParameters.ResolutionRestriction(1280, 720)
      }
    }
    ```
