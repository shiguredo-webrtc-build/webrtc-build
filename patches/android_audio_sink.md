# android_audio_sink.patch の解説

Android SDK 向けに AudioSink 機能を追加するパッチである、`android_audio_sink.patch` についての説明です。

## 目的

- Android SDK 向け libwebrtc で `AudioTrack` から PCM データを取得できるようにする
- 既存の C++ `AudioTrackInterface::AddSink()` と同等の機構を Java API に提供し、録音・音量可視化などの用途に活用できるようにする

## 背景

- 標準の libwebrtc Android SDK には、`AudioTrack` の PCM データを読み出す公式手段が存在しない。
- C++ では `AudioTrackInterface` に `AddSink()` / `RemoveSink()` が用意されており、`webrtc::AudioTrackSinkInterface` を実装することで PCM コールバックを受け取ることができる。
- このパッチでは Java から直接 PCM データを受け取るための `AudioSink` インターフェースと、その JNI ブリッジ実装を追加している。

## 変更点の概要

- `sdk/android/api/org/webrtc/AudioSink.java` を新規追加し、`onData()` / `getPreferredNumberOfChannels()` を公開する。
- `sdk/android/api/org/webrtc/AudioTrack.java` に `addSink()` / `removeSink()` / `dispose()` の拡張を実装し、登録済み `AudioSink` を `IdentityHashMap` で管理する。
- ビルドルール (`sdk/android/BUILD.gn`) に Java / JNI ファイルを追加し、ネイティブ側で `webrtc::Mutex` を利用できるよう依存を拡張する。
- `sdk/android/src/jni/pc/audio_sink.{h,cc}` を追加し、`AudioTrackSinkInterface` から Java の `AudioSink` へ PCM データを転送する `AudioSinkBridge` を定義する。
- `sdk/android/src/jni/pc/audio_track.cc` に JNI 関数を追加し、Java 側の `AudioTrack` からネイティブブリッジを作成・破棄できるようにする。

## 実装のポイント

- `AudioSinkBridge` は音声スレッド上で呼ばれるため、`webrtc::Mutex` で内部バッファを保護しながら `std::unique_ptr<uint8_t[]>` を再利用する。
  - `EnsureBufferSize()` で必要なサイズに合わせて Direct ByteBuffer を確保し直し、毎フレームの確保コストを最小化する。
- PCM データは `JNIEnv::NewDirectByteBuffer()` で作成したダイレクトバッファ越しに Java に受け渡す。`onData()` の呼び出しはネイティブ音声スレッドから行われるため、Java 実装側では重たい処理を別スレッドへオフロードする必要がある。
- `AudioSink.getPreferredNumberOfChannels()` の戻り値は `AudioTrackInterface::AddSink()` に渡す `AudioTrackSinkInterface::NumPreferredChannels()` に接続され、サーバー側が選択可能なチャネル数を調整できる。
- `AudioTrack.dispose()` は登録済みのすべてのネイティブブリッジを解放し、C++ 側の参照リークを防ぐ。
- `IdentityHashMap` を利用することで、`equals()` をオーバーライドした `AudioSink` 実装でも同一インスタンスの重複登録/解除を正しく扱える。

## 利用方法

```kotlin
val audioTrack: AudioTrack = /* MediaStream などから取得 */
val sink = object : AudioSink {
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

audioTrack.addSink(sink)

// 不要になったら必ず removeSink() するか、audioTrack.dispose() 実行前に解除する。
audioTrack.removeSink(sink)
```

- `onData()` のコールバック中は PCM データの所有権が JNI 側にあるため、必要であればバッファ内容を別領域へコピーしてから非同期処理に渡す。
- `getPreferredNumberOfChannels()` が `-1` を返す場合は「制約なし」を意味し、既存のチャンネル数がそのまま渡される。

