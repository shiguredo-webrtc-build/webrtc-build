# android-simulcast

## 対象プラットフォーム

Android


## 概要

- サイマルキャスト機能を追加する
- scalability modes に対応する


## 変更内容

- `SimulcastVideoEncoder` を追加
- `SimulcastVideoEncoderFactory` を追加
- `RtpParameters` に `scalabilityMode` プロパティを追加
- `VideoCodecInfo` に `scalabilityModes` プロパティを追加


## ビルド時の注意

- 本パッチの適用前にビルド済みの libwebrtc がある場合 (`_build` が存在する) 、 `_build` を削除してからビルドすること
  - 本パッチでは `VideoCodecInfo.java`　にネイティブから呼ばれるメソッドを追加しており、 libwebrtc のビルド時にネイティブのソースコード (`VideoCodecInfo_jni.h`) が自動的に生成される。このファイルは `python3 run.py build android` で更新されないので、 `_build` を削除して一からビルドし直す必要がある
  - `VideoCodecInfo_jni.h` のパスは `_build/android/release/webrtc/arm64-v8a/gen/jni_headers/sdk/android/generated_video_jni/VideoCodecInfo_jni.h`


## メモ

- `VideoCodecInfo` に `scalabilityModes` プロパティを追加しているが、この値はネイティブからセッター (`setScalabilityModes()`) を呼んで設定する (このメソッドはプライベートなので外部からは利用できない) 。コンストラクタの引数にとらない理由は以下の通り
  - 既存のコンストラクタのシグネチャを変更すると、 `VideoCodecInfo` に依存する他のコードでエラーになる
  - 新しいコンストラクタを追加すると、自動生成されるソースコードの API の名前が変わってしまう (コンストラクタの区別をつけるために接尾辞が追加される)


## その他

### C++ ヘッダーファイルを生成する方法

`simulcast_video_encoder.h` は `make javah` で生成できる。 `SimulcastVideoEncoder` にネイティブメソッド (`static native`) を追加したら、 `simulcast_video_encoder.h` を再生成して `src/sdk/android/src/jni/` にコピーすること。
