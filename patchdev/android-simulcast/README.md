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
- `sdk/android/BUILD.gn` は他の Android のパッチの変更点を含まないので、ビルドに失敗したら `BUILD.gn` を編集して以下の変更点を追加すること。現在の `patchdev.py` の実装では `make build` を実行すると、オリジナルの `sdk/android/BUILD.gn` を単純に置き換えるので、他のパッチの変更点が消えてしまう。ただし、以下の変更点を追加したままパッチを作成すると、 `run.py` によるパッチ適用時にリジェクトされるので、コミットしないように注意すること。

```
@@ -156,7 +156,6 @@ if (is_android) {
     sources = [
       "api/org/webrtc/Predicate.java",
       "api/org/webrtc/RefCounted.java",
-      "api/org/webrtc/WebrtcBuildVersion.java",
       "src/java/org/webrtc/CalledByNative.java",
       "src/java/org/webrtc/CalledByNativeUnchecked.java",
       "src/java/org/webrtc/Histogram.java",
@@ -284,7 +283,6 @@ if (is_android) {
       "api/org/webrtc/PeerConnection.java",
       "api/org/webrtc/PeerConnectionDependencies.java",
       "api/org/webrtc/PeerConnectionFactory.java",
-      "api/org/webrtc/ProxyType.java",
       "api/org/webrtc/RTCStats.java",
       "api/org/webrtc/RTCStatsCollectorCallback.java",
       "api/org/webrtc/RTCStatsReport.java",
```



## メモ

- `VideoCodecInfo` に `scalabilityModes` プロパティを追加しているが、この値はネイティブからセッター (`setScalabilityModes()`) を呼んで設定する (このメソッドはプライベートなので外部からは利用できない) 。コンストラクタの引数にとらない理由は以下の通り
  - 既存のコンストラクタのシグネチャを変更すると、 `VideoCodecInfo` に依存する他のコードでエラーになる
  - 新しいコンストラクタを追加すると、自動生成されるソースコードの API の名前が変わってしまう (コンストラクタの区別をつけるために接尾辞が追加される)


## その他

### C++ ヘッダーファイルを生成する方法

`simulcast_video_encoder.h` は `make javah` で生成できる。 `SimulcastVideoEncoder` にネイティブメソッド (`static native`) を追加したら、 `simulcast_video_encoder.h` を再生成して `src/sdk/android/src/jni/` にコピーすること。
