# android_audio_sink.patch の解説

Android SDK 向けに AudioTrackSink 機能を追加するパッチである、`android_audio_sink.patch` についての説明です。

## 目的

- Android SDK 向け libwebrtc で `AudioTrack` から PCM データを取得できるようにする
- 既存の C++ `AudioTrackInterface::AddSink()` と同等の機構を Java API に提供し、録音・音量可視化などの用途に活用できるようにする

## 背景

- 標準の libwebrtc Android SDK には、`AudioTrack` の PCM データを読み出す公式手段が存在しない。
- C++ では `AudioTrackInterface` に `AddSink()` / `RemoveSink()` が用意されており、`webrtc::AudioTrackSinkInterface` を実装することで PCM コールバックを受け取ることができる。
- このパッチでは Java から直接 PCM データを受け取るための `AudioTrackSink` インターフェースと、その JNI ブリッジ実装を追加している。

## 変更点の概要

- `sdk/android/api/org/webrtc/AudioTrackSink.java` を新規追加し、`onData()` / `getPreferredNumberOfChannels()` を公開する。
- `sdk/android/api/org/webrtc/AudioTrack.java` に `addSink()` / `removeSink()` / `dispose()` の拡張を実装し、登録済み `AudioTrackSink` を `IdentityHashMap` で管理する。
- ビルドルール (`sdk/android/BUILD.gn`) に Java / JNI ファイルを追加し、ネイティブ側で `webrtc::Mutex` を利用できるよう依存を拡張する。
- `sdk/android/src/jni/pc/audio_sink.{h,cc}` を追加し、`AudioTrackSinkInterface` から Java の `AudioTrackSink` へ PCM データを転送する `AudioTrackSinkBridge` を定義する。
- `sdk/android/src/jni/pc/audio_track.cc` に JNI 関数を追加し、Java 側の `AudioTrack` からネイティブブリッジを作成・破棄できるようにする。

### 実装のポイント

- `AudioTrackSinkBridge` は音声スレッド上で呼ばれるため、`webrtc::Mutex` で内部バッファを保護しながら `std::unique_ptr<uint8_t[]>` を再利用する。
  - `EnsureBufferSize()` で必要なサイズに合わせて Direct ByteBuffer を確保し直し、毎フレームの確保コストを最小化する。
- PCM データは `JNIEnv::NewDirectByteBuffer()` で作成したダイレクトバッファ越しに Java に受け渡す。`onData()` の呼び出しはネイティブ音声スレッドから行われるため、Java 実装側では重たい処理を別スレッドへオフロードする必要がある。
- `AudioTrackSink.getPreferredNumberOfChannels()` の戻り値は `AudioTrackInterface::AddSink()` に渡す `AudioTrackSinkInterface::NumPreferredChannels()` に接続され、サーバー側が選択可能なチャネル数を調整できる。
- `AudioTrack.dispose()` は登録済みのすべてのネイティブブリッジを解放し、C++ 側の参照リークを防ぐ。
- `IdentityHashMap` を利用することで、`equals()` をオーバーライドした `AudioTrackSink` 実装でも同一インスタンスの重複登録/解除を正しく扱える。

## AudioTrackSink 利用方法

```kotlin
val audioTrack: AudioTrack = /* MediaStream などから取得 */
val sink = object : AudioTrackSink {
  override fun onData(
    audioTrack: AudioTrack,
    audioData: ByteBuffer,
    bitsPerSample: Int,
    sampleRate: Int,
    numberOfChannels: Int,
    numberOfFrames: Int
  ) {
    // audioData は PCM16LE。重たい処理は別スレッドへ渡すこと。
  }

  override fun getPreferredNumberOfChannels(): Int = 1 // 例: モノラルが欲しい場合
}

// AudioTrack に AudioTrackSink を紐づける
audioTrack.addSink(sink)

// 不要になったら removeSink() で AudioTrack から AudioTrackSink を外す。
audioTrack.removeSink(sink)
```

- `onData()` のコールバック中は PCM データの所有権が JNI 側にあるため、必要であればバッファ内容を別領域へコピーしてから非同期処理に渡す。
- `getPreferredNumberOfChannels()` が `-1` を返す場合は「制約なし」を意味し、既存のチャンネル数がそのまま渡される。

## AudioTrack と AudioTrackSink の紐づけについて

- 同じ `AudioTrackSink` インスタンスを複数の `AudioTrack` に登録することも可能で、その場合はトラックごとに別の `AudioTrackSinkBridge` が生成され、それぞれ対応する `AudioTrackInterface` に紐づく。
- `onData()` には必ず送信元の `AudioTrack` が引数で渡されるため、共有シンクを使うときは `audioTrack == myTrack` や `audioTrack.id()` で送信元を判別可能。
- 1 つの `AudioTrackSink` を複数の `AudioTrack` に共有するとバッファをまとめて扱える反面、トラックごとの排他制御や状態管理を自前で持つ必要がある。
- 処理をトラック単位で分けたい、あるいはスレッド干渉を避けたい場合は各 `AudioTrack` 専用に `AudioTrackSink` を用意する方がシンプル。

## 付録

### `org.webrtc.AudioTrackSink` の `onData()` 呼び出しシーケンス

※ この処理シーケンスはパッチで追加されたものではなく、libwebrtc に元々実装されている AudioTrackSink の onData() 処理シーケンスを説明したもの

1. アプリ側で `AudioTrack.addSink()` を呼ぶと、Java 層から JNI を経由して `AudioTrackSinkBridge` が生成され、C++ の `AudioTrackInterface::AddSink()` に登録される。
   - 参照: `sdk/android/api/org/webrtc/AudioTrack.java`, `sdk/android/src/jni/pc/audio_track.cc`
2. リモートトラックの場合、`AudioRtpReceiver` が内部で `RemoteAudioSource` を生成し、メディアチャネルへ `AudioDataProxy` を生 PCM 受信用シンクとして登録する。
   - 参照: `pc/audio_rtp_receiver.cc`, `pc/remote_audio_source.cc`
3. メディアチャネル (`WebRtcVoiceReceiveChannel`) は受信ストリーム (`WebRtcAudioReceiveStream`) の `SetRawAudioTrackSink()` を通じて、音声デコーダーチャネル (`ChannelReceive`) に `AudioTrackSinkInterface` を設定する。
   - 参照: `media/engine/webrtc_voice_engine.cc`, `audio/audio_receive_stream.cc`, `audio/channel_receive.cc`
4. ネットワークから復号されたフレームが `ChannelReceive::GetAudioFrameWithInfo()` に到達すると、設定済みの `AudioTrackSinkInterface` に `AudioTrackSinkInterface::Data` を渡す。
   - 参照: `audio/channel_receive.cc`
5. `AudioDataProxy::OnData()` が `RemoteAudioSource::OnData()` を呼び出し、登録されている各 `AudioTrackSinkInterface`（ここでは `AudioTrackSinkBridge`）へ PCM16 データをファンアウトする。
   - 参照: `pc/remote_audio_source.cc`
6. `AudioTrackSinkBridge::OnData()` が JNI を通じて Java の `AudioTrackSink.onData()` を呼び、Direct ByteBuffer にコピーした PCM データとメタ情報（ビット深度、サンプルレート、チャンネル数、フレーム数）を渡す。
   - 参照: `sdk/android/src/jni/pc/audio_sink.cc`, `sdk/android/api/org/webrtc/AudioTrackSink.java`
