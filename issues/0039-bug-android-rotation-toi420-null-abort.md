# Android で端末回転時に SIGABRT する（テクスチャから I420 への変換失敗時に null を検査していない）

- Created: 2026-10-20
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-android-toi420-null-abort
- Polished: {YYYY-MM-DD}

## 目的

Sora Android SDK を利用したアプリで、 Pixel 8a / Android 17 の端末回転時に SIGABRT でクラッシュする問題を解消する。

クラッシュ地点は libwebrtc の `AndroidVideoTrackSource::OnFrameCaptured` で、 `VideoFrameBuffer::ToI420()` が返した nullptr を検査せずに `VideoFrame::Builder::build()` へ渡しているため。 `build()` 内の `RTC_CHECK(video_frame_buffer_ != nullptr)` でプロセスが落ちる。

`ToI420()` が nullptr を返すことはインターフェースの契約として明記されており、 Android の JNI 層だけがその契約を守っていない。 webrtc-build 側でパッチを当てて解消する。

## 現状

### 症状

- Pixel 8a / Android 17 で、 音声・映像の送受信中に端末を回転させると SIGABRT でクラッシュする。
- 同じ Android 17 の Pixel 10 では再現しない。他の Android OS バージョンでも再現しない。
- 回転で Activity は再生成されるが、接続は ViewModel 側で維持しており、回転を契機にした disconnect などのアプリ側処理は行っていない。
- 回転を契機にクラッシュするため、回転時のフレーム経路に原因があると考えている。

### コード上の事実

以下はすべて webrtc-checkout のソースで確認済み。

- `api/video/video_frame_buffer.h` の `VideoFrameBuffer::ToI420()` には「Conversion may fail, for example if reading the pixel data from a texture fails. If the conversion fails, nullptr is returned.」と明記されている。つまり nullptr は仕様上の戻り値。
- `sdk/android/src/jni/android_video_track_source.cc` の `AndroidVideoTrackSource::OnFrameCaptured` は次のとおりで、 nullptr を検査していない。
  ```cpp
  if (apply_rotation() && rotation != kVideoRotation_0)
    buffer = buffer->ToI420();
  ```
- `api/video/video_frame.cc` の `VideoFrame::Builder::build()` は `RTC_CHECK(video_frame_buffer_ != nullptr)` を持つ。したがって上記で nullptr になると SIGABRT する。 abort message は `Check failed: video_frame_buffer_ != nullptr.` になる。
- `sdk/android/src/jni/video_frame.cc` の `AndroidVideoBuffer::ToI420()` は、 Java 側の変換が失敗すると nullptr を返す（コメントに「In case I420 conversion fails, we propagate the nullptr.」とある）。
- `sdk/android/api/org/webrtc/TextureBufferImpl.java` の `toI420()` は `ThreadUtils.invokeAtFrontUninterruptibly(toI420Handler, () -> yuvConverter.convert(this))` を呼ぶ。
- `sdk/android/api/org/webrtc/YuvConverter.java` の `convert()` は `GLException` を catch して警告ログ（`Failed to convert TextureBuffer`）を出し、 nullptr を返す。したがって GL の失敗は例外にならず、 上記の nullptr 経路に流れる。
- 同じ nullptr を、 `modules/video_coding/codecs/vp8/libvpx_vp8_encoder.cc` の `LibvpxVp8Encoder::Encode` と `sdk/android/src/jni/video_frame.cc` の `NativeToJavaVideoFrame` はきちんと処理している（前者はフレーム破棄、後者は nullptr を返す）。考慮漏れは `AndroidVideoTrackSource::OnFrameCaptured` の 1 箇所だけ。
- `api/video/adapted_video_track_source.cc` の `AdaptedVideoTrackSource::apply_rotation()` は `broadcaster_.wants().rotation_applied` を返す。
- `api/video/video_broadcaster.cc` の `VideoBroadcaster::UpdateWants()` は各 sink の `rotation_applied` を ANY で集約する。
- `video/video_send_stream_impl.cc` の `VideoSendStreamImpl` は、 交渉済み RTP ヘッダ拡張に `RtpExtension::kVideoRotationUri` が無い場合にのみ `rotation_applied` を true にする（`urn:3gpp:video-orientation` 未交渉時のみ true）。
- **Sora は `urn:3gpp:video-orientation` をアドバタイズしない。** そのため Sora 接続ではこの拡張が交渉されず、 `apply_rotation()` は常に true になる。したがってこの abort 経路は Sora 接続では常に有効であり、特定のサーバー設定や SDP の書き換えで回避することはできない。
- `rotation != 0` になるのは、 `Camera2Session::getFrameOrientation()` の計算上、 背面カメラの縦持ち（`rotation == 90`）・前面カメラの縦持ち（`rotation == 270`）などが該当する。横持ちの片方向は `rotation == 0` になるため、その向きではこの分岐に入らず、変換は libvpx 側で行われる（失敗してもフレーム破棄でクラッシュしない）。つまり縦持ちのあいだは常にこの分岐が有効で、回転の瞬間に変換が失敗するとクラッシュする。
- CVO が交渉される構成（同一 libwebrtc 同士のループバック接続など）では `apply_rotation()` が false になり、変換失敗は libvpx 側のフレーム破棄になる。この差が比較検証に使える。

### 回転で変換が失敗しやすい理由

- `YuvConverter.convertInternal` は毎フレーム `i420TextureFrameBuffer.setSize(viewportWidth, totalHeight)` を呼ぶ。回転で幅と高さが入れ替わるとサイズが変わるため、 `glTexImage2D` による再確保と `glCheckFramebufferStatus` による完全性チェックが回転直後に走る。ここで失敗すると `IllegalArgumentException` / `IllegalStateException` になり、これらは `GLException` ではないので `YuvConverter.convert()` の catch をすり抜け、 Java 例外として JNI 境界へ抜ける。この場合の落ち方は `Check failed: false.`（`sdk/android/src/jni/jvm.cc` の `HandleException` 経由）か、 CaptureThread 上の `FATAL EXCEPTION` になる。つまり abort message 次第で経路が 2 通りある。
- 回転で Activity が再生成されるとカメラセッションも作り直される。古い SurfaceTexture / EGL コンテキストに紐づいたフレームが処理中のまま残りやすい。
- 以上はタイミング依存なので、同じコードでも端末・OS バージョンによって再現性が変わる。 Pixel 10 で再現しないことは、コード上の分岐差ではなく変換失敗の有無の差として説明できる。

### 確定事項と残る未確定事項

確定していること。

- Sora は `urn:3gpp:video-orientation` をアドバタイズしないため、 Sora 接続では `rotation_applied` が常に true になり、 `AndroidVideoTrackSource::OnFrameCaptured` の `ToI420()` 経路が常に有効になる。
- `ToI420()` の nullptr を検査していない箇所が libwebrtc に存在し、 nullptr は仕様上の戻り値である。

残る未確定事項。パッチ適用の判断はこの 2 点で行う。

- tombstone の abort message が `Check failed: video_frame_buffer_ != nullptr.` であること。
- クラッシュ直前の logcat に `YuvConverter: Failed to convert TextureBuffer` が出ていること。

abort message が `Check failed: false.` または CaptureThread の `FATAL EXCEPTION` である場合は、 nullptr 経路ではなく `GlTextureFrameBuffer.setSize` の例外経路（`IllegalArgumentException` / `IllegalStateException`）を疑う。この場合の修正対象は `YuvConverter.convert()` の catch 範囲になり、本 issue のパッチ案とは別になる。

## 設計方針

- `patches/android_toi420_null_check.patch` を新規追加し、 `run.py` の `PATCHES` の `android` と `android_sdk` の両方に登録する。 `sdk/android/src/jni` 配下を触るため両ターゲットが必要。
- パッチ内容は `AndroidVideoTrackSource::OnFrameCaptured` に null 検査を入れ、変換できなかったフレームだけをログ出力して破棄する。 libvpx 経路と同じ扱いに揃える。
- フレームを捨てるのではなく黒フレームやダミー I420 に差し替える案は採らない。解像度・タイムスタンプの整合が崩れるうえ、原因の可視化にならないため。
- `patches/README.md` に解説を追加する。同等の修正が上流に入ったら削除する旨を明記する。
- `CHANGES.md` に変更履歴を追記する。
- 上流にも報告する。 `VideoFrameBuffer::ToI420()` の契約に libwebrtc 自身の Android 実装が違反しているのは上流のバグであり、取り込まれればパッチを削除できる。
- Sora が `urn:3gpp:video-orientation` をアドバタイズしないため、 CVO を交渉させてこの経路を回避する方法は取れない。パッチ以外の回避策は、回転時にカメラセッションを作り直さないようにして変換失敗そのものを起こさないことだが、これは Sora Android SDK 側の変更になり確実性が低い。パッチを本命とする。
- このパッチが直すのはクラッシュのみで、テクスチャから I420 への変換が失敗していること自体は残る。変換失敗が頻発して映像が乱れる場合は、回転時のカメラセッション再生成と EGL の扱いを別 issue として調査する。

## 再現手順

1. Sora Android SDK を利用したアプリで映像を送信し、端末を回転させる。
2. 以下のコマンドで abort message と落ちたスレッドを確認する。
   ```
   adb shell logcat -b crash -b main
   adb shell ls /data/tombstones
   ```
3. 比較検証として、同一 libwebrtc 同士のループバック接続（`urn:3gpp:video-orientation` が交渉される構成）では回転してもクラッシュしないことを確認する。交渉される場合 `apply_rotation()` が false になり、同じ変換失敗がフレーム破棄に変わるため。
4. 比較検証として映像エンコーダーをソフトウェア VP8 固定にしても再現することを確認する（Pixel 8a も Pixel 10 も Codec2 のため VP8 は libvpx になり、この条件では機種差が出ないはず）。

## 完了条件

- abort message と logcat で原因が確定している。
- `patches/android_toi420_null_check.patch` が追加され、 `run.py` の `PATCHES` の `android` と `android_sdk` に登録されている。
- パッチ適用後の `android` と `android_sdk` のビルドが成功する。
- Pixel 8a / Android 17 で、 Sora 接続のまま縦横の回転を繰り返しても SIGABRT しない。
- 変換に失敗したフレームは `Failed to convert the frame to I420. Dropping it.` のログで確認でき、フレーム破棄として扱われている。
- パッチ適用後も、回転時に映像が数フレーム落ちるだけで接続は維持される。
- `patches/README.md` と `CHANGES.md` が更新されている。
- 上流への報告が完了している。

## 参考: パッチ案

```diff
--- a/sdk/android/src/jni/android_video_track_source.cc
+++ b/sdk/android/src/jni/android_video_track_source.cc
@@ -185,8 +185,16 @@ void AndroidVideoTrackSource::OnFrameCaptured(
   const VideoRotation rotation = jintToVideoRotation(j_rotation);
 
   // AdaptedVideoTrackSource handles applying rotation for I420 frames.
-  if (apply_rotation() && rotation != kVideoRotation_0)
+  if (apply_rotation() && rotation != kVideoRotation_0) {
     buffer = buffer->ToI420();
+    // テクスチャからの読み出しに失敗すると ToI420() は nullptr を返す。
+    // そのまま VideoFrame::Builder::build() に渡すと
+    // RTC_CHECK(video_frame_buffer_ != nullptr) でプロセスが落ちるため、
+    // このフレームは破棄する。
+    if (buffer == nullptr) {
+      RTC_LOG(LS_ERROR) << "Failed to convert the frame to I420. Dropping it.";
+      return;
+    }
+  }
 
   OnFrame(VideoFrame::Builder()
               .set_video_frame_buffer(buffer)
```

`rtc_base/logging.h` は同ファイルで既に include されているため、追加の include は不要。

## 参考: 上流報告の要旨

- 対象: `sdk/android/src/jni/android_video_track_source.cc` の `AndroidVideoTrackSource::OnFrameCaptured`
- 内容: `VideoFrameBuffer::ToI420()` はテクスチャ読み出し失敗時に nullptr を返すと `api/video/video_frame_buffer.h` で明記されているが、この呼び出し元だけが nullptr を検査せず、 `VideoFrame::Builder::build()` の `RTC_CHECK(video_frame_buffer_ != nullptr)` で SIGABRT する。
- 再現条件: Android のテクスチャバッファ、 `urn:3gpp:video-orientation` 未交渉、 `rotation != 0`、かつ `YuvConverter` の変換が失敗する状況（回転時の再確保など）。
- 期待する修正: 上記パッチ案と同等の null 検査、または `build()` 前にフレームを破棄する処理。
