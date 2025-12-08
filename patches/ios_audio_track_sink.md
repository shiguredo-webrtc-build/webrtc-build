# ios_audio_track_sink.patch の解説

iOS SDK 向けに AudioTrackSink 機能を追加するパッチである、`ios_audio_track_sink.patch` についての説明です。

## 目的

- iOS SDK 向け libwebrtc で `RTCAudioTrack` から PCM データを取得できるようにする
- C++ `AudioTrackInterface::AddSink()` と同等の仕組みを Objective-C API に提供し、録音・波形表示などの用途に活用できるようにする

## 背景

- 標準の libwebrtc iOS SDK には、`RTCAudioTrack` の PCM データを読み出す公式手段が存在しない。
- C++ では `AudioTrackInterface` に `AddSink()` / `RemoveSink()` が用意されており、`webrtc::AudioTrackSinkInterface` を実装することで PCM コールバックを受け取ることができる。
- このパッチでは Objective-C から直接 PCM データを受け取るための `RTCAudioTrackSink` プロトコルと、その C++ ブリッジ実装を追加している。

## 変更点の概要

- `sdk/objc/api/peerconnection/RTCAudioTrackSink.h` を新規追加し、`didReceiveData` と `preferredNumberOfChannels`（任意）を持つ `RTCAudioTrackSink` プロトコルを公開する。
- `sdk/objc/api/peerconnection/RTCAudioTrack+Sink.{h,mm}` を追加し、`RTCAudioTrack` に対して `addSink:` / `removeSink:` を提供するカテゴリを実装する。
  - 内部では `AudioTrackSinkInterface` を実装した `AudioSinkAdapter` を生成し、`nativeAudioTrack->AddSink()` / `RemoveSink()` を呼び出して C++ 側へ登録する。
- `AudioSinkAdapter` は `didReceiveData` 内で PCM を `NSData` にコピーして渡し、必要に応じて `preferredNumberOfChannels` を C++ 側へ伝える。
- `SinkAdapterManager` で `RTCAudioTrackSink` とアダプターの対応を `std::map` + `std::mutex` で管理し、同一インスタンスの重複登録や未登録解除を防ぐ。
- `sdk/BUILD.gn` に iOS/macOS 向けビルドターゲットへ新規ファイルを追加する。

### パッチ実装のポイント

- `AudioSinkAdapter::OnData` は WebRTC のオーディオスレッドから 10–20ms 間隔で呼ばれるため、`didReceiveData` 実装側では重たい処理を別キューへディスパッチすることを推奨。
- `@autoreleasepool` を毎回張ることで、`NSData` 生成や `weak` → `strong` 取得時に発生する一時オブジェクトを即時解放し、オーディオスレッドでのメモリ膨張を防いでいる。
- `__weak` 参照で `RTCAudioTrackSink` / `RTCAudioTrack` を保持し、ライフサイクル管理を簡潔にしつつ循環参照を避けている。
- `SinkAdapterManager` が `RTCAudioTrackSink` ごとに単一アダプターを保持するため、`removeSink:` では登録時と同じポインタで確実に `RemoveSink()` を呼べる。

## AudioTrackSink 利用方法

```swift
let audioTrack: RTCAudioTrack = /* MediaStream などから取得 */

final class SampleAudioSink: NSObject, RTCAudioTrackSink {
  func didReceiveData(
    _ audioData: Data,
    bitsPerSample: Int,
    sampleRate: Int,
    numberOfChannels: Int,
    numberOfFrames: Int
  ) {
    // audioData は PCM16LE。重たい処理は別スレッドに渡すこと。
  }

  func preferredNumberOfChannels() -> Int {
    return 1 // 例: モノラルが欲しい場合。制約なしの場合は -1 を返す。
  }
}

let sink = SampleAudioSink()

// AudioTrack に AudioTrackSink を紐づける
audioTrack.addSink(sink)

// 不要になったら removeSink() で AudioTrack から AudioTrackSink を外す
audioTrack.removeSink(sink)
```

- `preferredNumberOfChannels()` が `-1` を返す場合は「制約なし」を意味し、既存のチャンネル数がそのまま渡される。

## AudioTrack と AudioTrackSink の紐づけについて

- AudioTrackSink と AudioTrack は 1:1 で紐づける必要があります。
- 実装上の制約として、一度 `addSink:` された AudioTrackSink インスタンスを、別の AudioTrack（または同じ AudioTrack）に再度登録しようとした場合、その操作は無視されます。
- 複数の AudioTrack のデータを扱いたい場合は、それぞれの Track に対して個別の AudioTrackSink インスタンスを生成して紐づけてください。

## 付録

### `RTC_OBJC_TYPE(RTCAudioTrackSink)` の `didReceiveData()` 呼び出しシーケンス

`AudioTrackSinkInterface`（C++ 側）を実装した場合に、C++ 側から Objective-C 側の `didReceiveData` へどのような経路で音声データが渡ってくるかをメモした内容です。

1. アプリ側で `RTCAudioTrack.addSink:` を呼ぶと、Objective-C 層から `AudioSinkAdapter` が生成され、C++ の `AudioTrackInterface::AddSink()` に登録される。
   - 参照: `sdk/objc/api/peerconnection/RTCAudioTrack+Sink.mm`, `sdk/objc/api/peerconnection/RTCAudioTrack+Private.h`
2. リモートトラックの場合、`AudioRtpReceiver` が内部で `RemoteAudioSource` を生成し、メディアチャネルへ `AudioDataProxy` を生 PCM 受信用シンクとして登録する。
   - 参照: `pc/audio_rtp_receiver.cc`, `pc/remote_audio_source.cc`
3. メディアチャネル (`WebRtcVoiceReceiveChannel`) は受信ストリーム (`WebRtcAudioReceiveStream`) の `SetRawAudioTrackSink()` を通じて、音声デコーダーチャネル (`ChannelReceive`) に `AudioTrackSinkInterface` を設定する。
   - 参照: `media/engine/webrtc_voice_engine.cc`, `audio/audio_receive_stream.cc`, `audio/channel_receive.cc`
4. ネットワークから復号されたフレームが `ChannelReceive::GetAudioFrameWithInfo()` に到達すると、設定済みの `AudioTrackSinkInterface` に `AudioTrackSinkInterface::Data` を渡す。
   - 参照: `audio/channel_receive.cc`
5. `AudioDataProxy::OnData()` が `RemoteAudioSource::OnData()` を呼び出し、登録されている各 `AudioTrackSinkInterface`（ここでは `AudioSinkAdapter`）へ PCM16 データをファンアウトする。
   - 参照: `pc/remote_audio_source.cc`
6. `AudioSinkAdapter::OnData()` が Objective-C の `didReceiveData()` を呼び、`NSData` にコピーした PCM データとメタ情報（ビット深度、サンプルレート、チャンネル数、フレーム数）を渡す。
   - 参照: `sdk/objc/api/peerconnection/RTCAudioTrack+Sink.mm`, `sdk/objc/api/peerconnection/RTCAudioTrackSink.h`
