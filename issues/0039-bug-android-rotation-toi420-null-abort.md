# Android で端末回転時に SIGABRT する（テクスチャから I420 への変換失敗時に null を検査していない）

- Created: 2026-10-20
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-android-toi420-null-abort
- Polished: 2026-10-20

## 目的

Sora Android SDK を利用したアプリで、 Pixel 8a / Android 17 の端末回転時に SIGABRT でクラッシュする問題を解消する。

クラッシュ地点は libwebrtc の `AndroidVideoTrackSource::OnFrameCaptured` と推定している。 `VideoFrameBuffer::ToI420()` が返した nullptr を検査せずに `VideoFrame::Builder::build()` へ渡すと、 `build()` 内の `RTC_CHECK(video_frame_buffer_ != nullptr)` でプロセスが落ちる。実際のクラッシュ経路は「残る未確定事項」の logcat で確定する。

`ToI420()` が nullptr を返すことはインターフェースの契約として明記されており、 Android の JNI 実装にはこの契約を守っていない呼び出し元がある。 また変換失敗時には direct ByteBuffer とテクスチャフレームが解放されず、 変換用の `GlTextureFrameBuffer` も失敗時の状態のまま残るため、 一度の失敗で以降のフレームが配信されなくなるか、 状態が回復しないまま映像が止まる。 webrtc-build 側でパッチを当てて、クラッシュ・リーク・配信停止をまとめて解消する。

## 現状

### 症状

- Pixel 8a / Android 17 で、 音声・映像の送受信中に端末を回転させると SIGABRT でクラッシュする。
- 同じ Android 17 の Pixel 10 では再現しない。他の Android OS バージョンでも再現しない。
- 回転で Activity は再生成されるが、接続は ViewModel 側で維持しており、回転を契機にした disconnect などのアプリ側処理は行っていない。
- 回転を契機にクラッシュするため、回転時のフレーム経路に原因があると考えている。

### コード上の事実

以下は libwebrtc M156 と Sora のソースおよび Sora のドキュメントで確認済み。 端末に依存する値は例示である。

- `api/video/video_frame_buffer.h` の `VideoFrameBuffer::ToI420()` には「Conversion may fail, for example if reading the pixel data from a texture fails. If the conversion fails, nullptr is returned.」と明記されている。つまり nullptr は仕様上の戻り値。
- `sdk/android/src/jni/android_video_track_source.cc` の `AndroidVideoTrackSource::OnFrameCaptured` は次のとおりで、 nullptr を検査していない。
  ```cpp
  if (apply_rotation() && rotation != kVideoRotation_0)
    buffer = buffer->ToI420();
  ```
- `api/video/video_frame.cc` の `VideoFrame::Builder::build()` は `RTC_CHECK(video_frame_buffer_ != nullptr)` を持つ。したがって上記で nullptr になると SIGABRT する。 `RTC_CHECK` の失敗は logcat の `rtc` タグへ `# Check failed: video_frame_buffer_ != nullptr`（末尾ピリオドなし）を出してから `abort()` を呼ぶ。
- `sdk/android/src/jni/video_frame.cc` の `AndroidVideoBuffer::ToI420()` は、 Java 側の変換が失敗すると nullptr を返す（コメントに「In case I420 conversion fails, we propagate the nullptr.」とある）。
- `sdk/android/api/org/webrtc/TextureBufferImpl.java` の `toI420()` は `ThreadUtils.invokeAtFrontUninterruptibly(toI420Handler, () -> yuvConverter.convert(this))` を呼ぶ。
- `sdk/android/api/org/webrtc/YuvConverter.java` の `convert()` は `GLException` を catch して警告ログ（`Failed to convert TextureBuffer`）を出し、 nullptr を返す。したがって GL の失敗は例外にならず、 上記の nullptr 経路に流れる。
- 同じ nullptr を、 `modules/video_coding/codecs/vp8/libvpx_vp8_encoder.cc` の `LibvpxVp8Encoder`（`PrepareBuffers`）と `sdk/android/src/jni/video_frame.cc` の `NativeToJavaVideoFrame` はきちんと処理している（前者はフレーム破棄、後者は nullptr を返す）。 Android のテクスチャ経路で nullptr を検査していないのは `AndroidVideoTrackSource::OnFrameCaptured` の 1 箇所だけ。
- `api/video/adapted_video_track_source.cc` の `AdaptedVideoTrackSource::apply_rotation()` は `broadcaster_.wants().rotation_applied` を返す。
- `api/video/video_broadcaster.cc` の `VideoBroadcaster::UpdateWants()` は各 sink の `rotation_applied` を ANY で集約する。
- `video/video_send_stream_impl.cc` の `VideoSendStreamImpl` は、 交渉済み RTP ヘッダ拡張に `RtpExtension::kVideoRotationUri` が無い場合にのみ `rotation_applied` を true にする（`urn:3gpp:video-orientation` 未交渉時のみ true）。
- **Sora は既定設定では `urn:3gpp:video-orientation` をアドバタイズしない。** そのため既定構成の Sora 接続ではこの拡張が交渉されず、 `apply_rotation()` は true になる。したがってこの abort 経路は既定構成の Sora 接続では有効である。 サーバー設定 `rtp_hdrext_video_orientation` を true にすると交渉させられるが、 この設定の利用には事前のサポート連絡が必要で、 SDK 利用者が前提にできる回避策ではない。
- `rotation != 0` になるのは、 `Camera2Session::getFrameOrientation()` の計算上、 背面カメラの縦持ち（`rotation == 90`）・前面カメラの縦持ち（`rotation == 270`）などが該当する（具体的な値は端末の `SENSOR_ORIENTATION` に依存する）。横持ちの片方向は `rotation == 0` になるため、その向きではこの分岐に入らず、変換が起きるのはエンコーダー側になる（ソフトウェア VP8 では libvpx が変換に失敗してもフレームを破棄するだけでクラッシュしない）。つまり縦持ちのあいだは常にこの分岐が有効で、回転の瞬間に変換が失敗するとクラッシュする。
- CVO が交渉される構成（同一 libwebrtc 同士のループバック接続など）では `apply_rotation()` が false になり、変換失敗は libvpx 側のフレーム破棄になる。この差が比較検証に使える。

### 変換が失敗する引き金（未解明）

- 回転してもテクスチャバッファの幅と高さは変わらない。 `CameraSession.createTextureBufferWithModifiedTransformMatrix` は `buffer.applyTransformMatrix(transformMatrix, buffer.getWidth(), buffer.getHeight())` を呼び、 コメントにも「The width and height are not affected by rotation」とある。したがって「回転でサイズが入れ替わるので再確保が走る」という説明は根拠がない。
- サイズが変わり得るのは、 キャプチャフォーマットが変わるか、 `AdaptedVideoTrackSource::AdaptFrame` の crop / scale の結果が向きによって変わる場合である。この場合は `YuvConverter.convertInternal` の `i420TextureFrameBuffer.setSize` が再確保を行う。
- 引き金として残る候補は、回転に伴うカメラセッションの再生成と SurfaceTexture / EGL まわりの状態。たとえば EGL コンテキストのロスト（GL 呼び出しが無効になり `glGenTextures` が 0 を返す）、 `SurfaceTexture` のサイズ未設定、テクスチャ再確保の失敗など。
- どの候補が当たっているかは未解明。特定には失敗時の GL エラーコードとフレームバッファ状態の計測が要る（後述）。端末差が出るのは、タイミング依存のこの引き金を踏むかどうかの差になる。

### 変換失敗が 1 回で終わらず、連鎖する欠陥

引き金が何であれ、一度失敗すると回復しない構造になっている。以下は `sdk/android/api/org/webrtc/` と `sdk/android/src/java/org/webrtc/` の Java 実装、 および JNI 層の問題。

- `YuvConverter.convertInternal` に例外安全がない。`JniCommon.nativeAllocateByteBuffer(stride * totalHeight)` でフレームごとに direct ByteBuffer を確保し、 `preparedBuffer.release()` を関数末尾で行い、 ByteBuffer も `JavaI420Buffer.wrap` の release callback に所有権を渡して解放する。そのため `i420TextureFrameBuffer.setSize` 以降で例外が出ると `preparedBuffer` の retain と ByteBuffer の両方が解放されない。 720p で 1 フレーム約 1.4 MB。 `VideoFrameDrawer.prepareBufferForViewportSize` は `buffer.retain()` して同一オブジェクトを返すため、 この retain が残ると `SurfaceTextureHelper.isTextureInUse` が true のままになり、 以降のフレームが配信されなくなる。
- `GlTextureFrameBuffer.setSize` が失敗を固定化する。早期 return の判定に使う `width` / `height` を確保処理より先に更新しているため、 `GlUtil.generateTexture` や `glTexImage2D` の検査で例外が出てもサイズは更新済みになる。次回以降は「サイズが同じ」と判断されて再確保されず、壊れたフレームバッファを使い続ける。別のサイズになるまで回復しない。
- `YuvConverter.convert` は `GLException` しか catch しない。 `IllegalStateException`（フレームバッファ不完全）や `IllegalArgumentException` は JNI 境界へ抜け、 `jni_zero::CheckException` 経由の `HandleException` で `RTC_CHECK(false)` になる。 `GLException` のほうは nullptr になり、 `AndroidVideoTrackSource::OnFrameCaptured` の null 未検査で `VideoFrame::Builder::build()` の `RTC_CHECK` になる。
- 結果として、回転直後に 1 回失敗すると、現行コードではどちらの経路でも即座に SIGABRT する。クラッシュを止めただけでは、 `preparedBuffer` の retain が残って以降のフレームが届かなくなるため、 映像が止まる。端末差が出るのは「最初の 1 回が起きるかどうか」の差になる。

### 検証したバージョンと上流の状況

- Sora Android SDK の `libs.versions.toml` は libwebrtc `m156.8078.3.1` を参照している。 これは webrtc-build の `m156.8078.3.1` タグに相当し、 libwebrtc の commit は `3987dfb7b9`（M156.8078@#3）。本 issue の分析は `6306c66dfc`（M156.8078@#2）で行ったが、 対象ファイルは両者で同一である。 main (`29ecea7e21`) との差分も、 本 issue が扱う `android_video_track_source.cc`、 `video_frame.cc`、 `adapted_video_track_source.cc`、 `YuvConverter.java`、 `GlTextureFrameBuffer.java`、 `jvm.cc` には無い。
- 上流には同じ欠陥クラスの修正実績がある。 `5b435032de`（2026-05-05、M156 に含まれる）は `NativeToJavaVideoFrame` など 3 箇所に「`VideoFrameBuffer::ToI420()` の結果の null チェック」を追加してクラッシュを防いでいる。 `AndroidVideoTrackSource::OnFrameCaptured` だけが同じ修正を受けていない。
- 2026-10-16 には `f7126d621e`（Bug: webrtc:574312303）と `ad255b4e05` が入り、 `ToI420()` / `CropAndScale()` の失敗を null で返す方向へ整理が進んでいる。 main では `api/video/video_frame_buffer.cc` の `CropAndScale` 既定実装にも null 検査が入った。 上流はプロデューサ側の null 返却を整備している段階で、 Android の呼び出し元の null 検査は別途必要である。
- `GlTextureFrameBuffer.java` と `YuvConverter.java` は長く変更されておらず、状態更新順と例外安全の問題は未修正のまま残っている。

### 確定事項と残る未確定事項

確定していること。

- Sora は既定設定では `urn:3gpp:video-orientation` をアドバタイズしないため、 既定構成の Sora 接続では `rotation_applied` が true になり、 `AndroidVideoTrackSource::OnFrameCaptured` の `ToI420()` 経路が有効になる。
- `ToI420()` の nullptr を検査していない箇所が libwebrtc に存在し、 nullptr は仕様上の戻り値である。

残る未確定事項。パッチ適用の判断はこの 2 点で行う。

- logcat の `rtc` タグに `# Check failed: video_frame_buffer_ != nullptr` が出ていること（null 経路）。
- クラッシュ直前の logcat に `YuvConverter: Failed to convert TextureBuffer` が出ていること。

`RTC_CHECK` は `__android_log_print` で logcat へ出力してから `abort()` を呼ぶだけで `android_set_abort_message()` を呼ばないため、 tombstone の abort message には残らない。 判定は logcat の `rtc` タグの fatal log 行で行い、 tombstone は落ちたスレッドとバックトレースの確認に使う。 logcat の `rtc` タグが `# Check failed: false` である場合は、 null 経路ではなく `GlTextureFrameBuffer.setSize` の例外経路（`IllegalArgumentException` / `IllegalStateException`）である。この場合も修正対象は同じパッチの catch 範囲と状態リセットであり、 本 issue のパッチで扱う。

パッチ適用後に変換失敗が続く場合は、引き金（EGL コンテキストのロストなど）が継続していることを示す。

## 設計方針

- 実装前に再現手順 2 で logcat の `rtc` タグを取得し、 クラッシュ経路を確定する。 パッチを適用すると再現しなくなるため、 この確認はパッチ適用前に行う。 引き金（EGL コンテキストのロストか、テクスチャ再確保の失敗か）の特定はパッチ適用後に別途行う。 パッチの内容は引き金に依存しないため、 引き金の特定を待たない。
- `patches/android_toi420_failure_handling.patch` を新規追加し、 `run.py` の `PATCHES` の `android` と `android_sdk` の両方に登録する。 `sdk/android` 配下を触るため両ターゲットが必要。
- `patches/android_fixsegv.patch` は `video_encoder_wrapper.cc` の初期化だけを扱っており、 今回の変更ファイルと重ならないため別パッチにする。
- パッチは「テクスチャから I420 への変換失敗を致命的にしない」という 1 つの目的に対し、 次の 4 点をまとめて扱う。 どれか 1 つだけを直しても、 クラッシュ・リーク・配信停止・状態の固定化のいずれかが残る。
  1. `YuvConverter.convertInternal` を例外安全にする。 `preparedBuffer.release()` と ByteBuffer の解放を `try` / `finally` で保証し、 失敗時にもリソースを残さない。 これが無いと、 クラッシュを止めても `preparedBuffer` の retain が残って `isTextureInUse` が true のままになり、 以降のフレームが配信されない。
  2. `YuvConverter.convert` の catch 範囲を広げ、 フレームバッファ不完全などの実行時例外も nullptr に変換してフレーム破棄に倒す。 これが無いと、 `jni_zero` の `CheckException` 経由で `HandleException` の `RTC_CHECK(false)` になりクラッシュする。
  3. 変換に失敗したら `i420TextureFrameBuffer.release()` を呼び、 変換用のフレームバッファとテクスチャの状態を捨てる。 `release()` はサイズと GL リソースの ID を 0 に戻すため、 次のフレームで必ず再確保される。 これが無いと、 失敗時に入った中途半端な状態のまま以降のフレームも失敗し続ける。
  4. `AndroidVideoTrackSource::OnFrameCaptured` に null 検査を入れ、 変換できなかったフレームだけをログ出力して破棄する。 libvpx 経路と同じ扱いに揃える。
- クラッシュだけを止める最小構成は 4 の null 検査と 2 の catch 拡張の 2 点である。 ただしその状態では変換失敗のたびに `preparedBuffer` の retain が残り、 映像が止まる。 本 issue はクラッシュ・リーク・配信停止・固定化をまとめて直すため、 1〜4 の 4 点を採る。
- `GlTextureFrameBuffer.setSize` の状態更新順（`width` / `height` を確保より先に更新する）は本 issue では変更しない。 3 の `release()` が同じ固定化を解消できるうえ、 このクラスは `EglRenderer` からも使われる公開クラスで、 変更範囲を広げる利点が薄いため。 必要なら別パッチまたは上流送りにする。
- フレームを捨てるのではなく黒フレームやダミー I420 に差し替える案は採らない。解像度・タイムスタンプの整合が崩れるうえ、原因の可視化にならないため。
- `patches/README.md` に解説を追加する。同等の修正が上流に入ったら削除する旨を明記する。
- `CHANGES.md` に変更履歴を追記する。
- 上流へもバグ報告と修正案を提出する（単体テストを添える）。上流の取り込みは待たず、 webrtc-build のパッチを先にリリースする。取り込まれたらパッチを削除する。
- Sora は既定設定では `urn:3gpp:video-orientation` をアドバタイズしないため、 CVO を交渉させてこの経路を回避する方法は SDK 利用者側では取れない（サーバー設定 `rtp_hdrext_video_orientation` を有効にすれば交渉できるが、 事前のサポート連絡が必要で SDK の修正ではない）。パッチ以外の回避策は、回転時にカメラセッションを作り直さない、 あるいは SDK 側で `frame.rotation` を 0 にして I420 変換自体を避ける、 などが考えられるが、 いずれも SDK 利用者やアプリ側に依存し確実性が低い。パッチを本命とする。
- このパッチでクラッシュ・リーク・配信停止・固定化は解消するが、変換が失敗したこと自体の原因は残る。復帰するようになるので症状は「数フレーム落ちて戻る」に変わるが、頻発するなら引き金の調査を別 issue として行う。

## 再現手順

1. Sora Android SDK を利用したアプリで映像を送信し、端末を回転させる。
2. 以下のコマンドで logcat の `rtc` タグの fatal log 行と落ちたスレッドを確認する。 `RTC_CHECK` は abort message を設定しないため、 経路の判定は logcat で行う。
   ```
   adb logcat -d -b main -s rtc:V
   adb shell ls /data/tombstones
   ```
3. 比較検証として、同一 libwebrtc 同士のループバック接続（`urn:3gpp:video-orientation` が交渉される構成）では回転してもクラッシュしないことを確認する。交渉される場合 `apply_rotation()` が false になり、同じ変換失敗がフレーム破棄に変わるため。
4. 比較検証として映像エンコーダーをソフトウェア VP8 固定にしても再現することを確認する（VP8 のハードウェアエンコーダーが選ばれなければ libvpx が使われるため、この条件では機種差が出ないはず）。

## 完了条件

- logcat の `rtc` タグでクラッシュ経路が確定している。
- `patches/android_toi420_failure_handling.patch` が追加され、 `run.py` の `PATCHES` の `android` と `android_sdk` に登録されている。
- パッチ適用後の `android` と `android_sdk` のビルドが成功する。
- Pixel 8a / Android 17 で、 Sora 接続のまま縦横の回転を繰り返しても SIGABRT しない。
- 変換に失敗したフレームは `Failed to convert the frame to I420. Dropping it.` のログで確認でき、フレーム破棄として扱われている。
- 変換に失敗しても direct ByteBuffer とテクスチャフレームがリークしておらず、 `SurfaceTextureHelper.isTextureInUse()` が false に戻ることを確認している（検証用の一時ビルドで変換失敗を起こし、 sora-android-sdk の instrumented test で確認する。検証用の変更はパッチに含めない）。
- 変換に失敗した次のフレームで変換用フレームバッファが再確保され、変換が再試行されることを確認している（同じく検証用の一時ビルドで確認する）。
- パッチ適用後も、回転時に映像が数フレーム落ちるだけで接続は維持される。
- `patches/README.md` と `CHANGES.md` が更新されている。
- 上流へバグ報告と修正案を提出し、 URL を issue に記録している。

## 参考: 原因究明用の計測

引き金を特定するための計測。パッチを入れる前に、まず既存のログで分かる範囲を確認する。

- `YuvConverter.convert` の `Logging.w(TAG, "Failed to convert TextureBuffer", e)` は `GLException` のメッセージとスタックトレースをそのまま出す。 `GLException` のメッセージには失敗した呼び出し名と GL エラーコードが入る（例: `YuvConverter.convert: GLES20 error: 1282`、`GlTextureFrameBuffer setSize: GLES20 error: 1282`）。 logcat の `YuvConverter` タグを確認すれば、どの GL 呼び出しで失敗したかは既に判別できる。
- 判別したいのは次の 3 つ。
  - `GlTextureFrameBuffer setSize` で失敗している → テクスチャ確保かフレームバッファ完全性の問題
  - `glBindFramebuffer` 以降で失敗している → 直前の確保が失敗したまま使われている（固定化）
  - `IllegalStateException: Framebuffer not complete, status: N` が出ている → 確保は成功したが FBO が不完全（EGL コンテキストのロストを疑う）
- 上のログで足りない場合は、次の一時計測を入れる。
  - `GlTextureFrameBuffer.setSize` で `glCheckFramebufferStatus` の値、 `textureId`、 `frameBufferId` を常に出力する
  - `YuvConverter.convert` の catch で `GLES20.glGetError()`、 `preparedBuffer` の幅と高さ、 `Thread.currentThread().getName()` を出力する
  - `SurfaceTextureHelper` の生成と破棄、 `setTextureSize` の呼び出しを出力する（EGL コンテキストの作り直しが回転で起きているかの確認）
- あわせて、回転時にカメラセッションが作り直されているか（`Camera2Session` の `Stop internal` と `Camera device successfully started.` の出現）を確認する。作り直されていないなら、引き金はセッション再生成ではない。

## 参考: パッチ案

パッチは `DEVELOPMENT.md` の「パッチを作成する」手順で生成する。以下は M156 のソースに当てた場合の変更内容。

### JNI 層: null 検査

```diff
--- a/sdk/android/src/jni/android_video_track_source.cc
+++ b/sdk/android/src/jni/android_video_track_source.cc
@@ -186,8 +186,17 @@ void AndroidVideoTrackSource::OnFrameCaptured(
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

### Java 層: 変換処理の例外安全

`YuvConverter.convertInternal` の確保と解放を `try` / `finally` で対応させる。

```java
    final ByteBuffer i420ByteBuffer = JniCommon.nativeAllocateByteBuffer(stride * totalHeight);
    boolean bufferOwnershipTransferred = false;
    try {
      // 以降の描画・glReadPixels・I420Buffer の生成
      ...
      // wrap が所有権を受け取ってから初めて true にする。wrap 自体が失敗した場合は
      // finally 側で ByteBuffer を解放する必要があるため、順序を逆にしないこと。
      final I420Buffer buffer = JavaI420Buffer.wrap(frameWidth, frameHeight, dataY, stride, dataU,
          stride, dataV, stride, () -> { JniCommon.nativeFreeByteBuffer(i420ByteBuffer); });
      bufferOwnershipTransferred = true;
      return buffer;
    } finally {
      preparedBuffer.release();
      if (!bufferOwnershipTransferred) {
        JniCommon.nativeFreeByteBuffer(i420ByteBuffer);
      }
    }
```

### Java 層: catch 範囲と失敗時の状態リセット

`YuvConverter.convert` で `GLException` 以外の実行時例外も捕まえ、 nullptr を返してフレーム破棄に倒す。あわせて、失敗時には変換用のフレームバッファを解放して次のフレームで再確保させる。

```java
  public I420Buffer convert(TextureBuffer inputTextureBuffer) {
    try {
      return convertInternal(inputTextureBuffer);
    } catch (RuntimeException e) {
      // フレームバッファ不完全などの実行時例外を JNI 境界へ抜けさせない。
      // 抜けると jni_zero の CheckException でプロセスが落ちる。
      Logging.w(TAG, "Failed to convert TextureBuffer", e);
      // 中途半端な状態のまま次のフレームも失敗し続けるのを避けるため、
      // 変換用のフレームバッファを解放して次のフレームで再確保させる。
      i420TextureFrameBuffer.release();
    }
    return null;
  }
```

`RuntimeException` を広く捕まえるのは原因を隠す懸念があるが、ここではログを残したうえでフレーム破棄に倒すことを優先する。上流に取り込ませる場合は `IllegalStateException` など対象を限定する形に調整する。

## 参考: 上流報告の要旨

- 対象: `sdk/android/api/org/webrtc/YuvConverter.java`、 `sdk/android/api/org/webrtc/GlTextureFrameBuffer.java`、 `sdk/android/src/jni/android_video_track_source.cc`
- 内容 1: `VideoFrameBuffer::ToI420()` はテクスチャ読み出し失敗時に nullptr を返すと `api/video/video_frame_buffer.h` で明記されているが、 Android の JNI 実装では `AndroidVideoTrackSource::OnFrameCaptured` が nullptr を検査せず、 `VideoFrame::Builder::build()` の `RTC_CHECK(video_frame_buffer_ != nullptr)` で SIGABRT する。 `NativeToJavaVideoFrame` などは同じ検査を入れている。
- 内容 2: `YuvConverter.convertInternal` は `nativeAllocateByteBuffer` で確保した direct ByteBuffer と `preparedBuffer` の retain を例外時に解放しないため、両方がリークし、 `SurfaceTextureHelper` の `isTextureInUse` も true のまま残って以降のフレームが配信されなくなる。
- 内容 3: `YuvConverter.convert` は `GLException` しか捕まえないため、フレームバッファ不完全などの実行時例外が JNI 境界へ抜けてプロセスが落ちる。
- 内容 4: `GlTextureFrameBuffer.setSize` は `width` / `height` を確保より先に更新するため、一度失敗すると「サイズが同じ」と判定されて再確保されず、壊れたフレームバッファを使い続ける。 webrtc-build 側は `i420TextureFrameBuffer.release()` で回避するが、上流では `setSize` 側を直すのが望ましい。
- 再現条件: Android のテクスチャバッファ、 `urn:3gpp:video-orientation` 未交渉（`rotation_applied` が true）、 `rotation != 0`、かつ `YuvConverter` の変換が失敗する状況（EGL コンテキストのロストなど）。
- 期待する修正: 上記 4 点。クラッシュだけでなく、失敗の固定化とリソースリークも直す必要がある。
