# android_audio_track_sink.patch の解説

Android SDK 向けに AudioTrackSink 機能を追加するパッチである、`android_audio_track_sink.patch` についての説明です。

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
  - これは VideoTrack.java の実装を真似している
- `sdk/android/src/jni/audio_track_sink.{h,cc}` を追加し、`AudioTrackSinkInterface` から Java の `AudioTrackSink` へ PCM データを転送する `AudioTrackSinkWrapper` を定義する。
- `sdk/android/src/jni/pc/audio_track.cc` に JNI 関数を追加し、Java 側の `AudioTrack` からネイティブブリッジを作成・破棄できるようにする。

### パッチ実装のポイント

- PCM データは `CreateDirectByteBuffer()` で作成したダイレクトバイトバッファ越しに Java に受け渡す。`onData()` の呼び出しはネイティブ音声スレッドから行われるため、Java 実装側では重たい処理を別スレッドへオフロードする必要がある。
- `AudioTrackSink#getPreferredNumberOfChannels` に設定した値は、JNI ラッパー AudioTrackSinkWrapper::NumPreferredChannels() から C++ 側へ渡され 、onData に入ってくる音声データのチャンネル数の決定に使用される。
- `AudioTrack.dispose()` は登録済みのすべてのネイティブブリッジを解放し、C++ 側の参照リークを防ぐ。
- `IdentityHashMap` を利用することで、`equals()` をオーバーライドした `AudioTrackSink` 実装でも同一インスタンスの重複登録/解除を正しく扱える。

## AudioTrackSink 利用方法

```kotlin
val audioTrack: AudioTrack = /* MediaStream などから取得 */
val sink = object : AudioTrackSink {
  override fun onData(
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

- `getPreferredNumberOfChannels()` が `-1` を返す場合は「制約なし」を意味し、既存のチャンネル数がそのまま渡される。

## AudioTrack と AudioTrackSink の紐づけについて

- AudioTrackSink と AudioTrack は 1:1 で紐づけるようにする
- 仮に AudioTrackSink と AudioTrack を 1:N で紐づけてしまうと AudioTrackSink::onData では AudioTrack を識別する情報を返さないため、どの AudioTrack のデータなのか判別できない

## 付録

### `org.webrtc.AudioTrackSink` の `onData()` 呼び出しシーケンス

AudioTrackSinkInterface (C++ 側) を実装した場合に、C++ 側から Java 側の AudioTrackSink::onData へどのような経路で音声データが渡ってくるかをメモした内容です。

1. アプリ側で `AudioTrack.addSink()` を呼ぶと、Java 層から JNI を経由して `AudioTrackSinkWrapper` が生成され、C++ の `AudioTrackInterface::AddSink()` に登録される。
   - 参照: `sdk/android/api/org/webrtc/AudioTrack.java`, `sdk/android/src/jni/pc/audio_track.cc`
2. リモートトラックの場合、`AudioRtpReceiver` が内部で `RemoteAudioSource` を生成し、メディアチャネルへ `AudioDataProxy` を生 PCM 受信用シンクとして登録する。
   - 参照: `pc/audio_rtp_receiver.cc`, `pc/remote_audio_source.cc`
3. メディアチャネル (`WebRtcVoiceReceiveChannel`) は受信ストリーム (`WebRtcAudioReceiveStream`) の `SetRawAudioTrackSink()` を通じて、音声デコーダーチャネル (`ChannelReceive`) に `AudioTrackSinkInterface` を設定する。
   - 参照: `media/engine/webrtc_voice_engine.cc`, `audio/audio_receive_stream.cc`, `audio/channel_receive.cc`
4. ネットワークから復号されたフレームが `ChannelReceive::GetAudioFrameWithInfo()` に到達すると、設定済みの `AudioTrackSinkInterface` に `AudioTrackSinkInterface::Data` を渡す。
   - 参照: `audio/channel_receive.cc`
5. `AudioDataProxy::OnData()` が `RemoteAudioSource::OnData()` を呼び出し、登録されている各 `AudioTrackSinkInterface`（ここでは `AudioTrackSinkWrapper`）へ PCM16 データをファンアウトする。
   - 参照: `pc/remote_audio_source.cc`
6. `AudioTrackSinkWrapper::OnData()` が JNI を通じて Java の `AudioTrackSink.onData()` を呼び、Direct ByteBuffer にコピーした PCM データとメタ情報（ビット深度、サンプルレート、チャンネル数、フレーム数）を渡す。
   - 参照: `sdk/android/src/jni/audio_track_sink.cc`, `sdk/android/api/org/webrtc/AudioTrackSink.java`
