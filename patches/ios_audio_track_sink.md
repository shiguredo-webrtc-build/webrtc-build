# ios_audio_track_sink.patch の解説

iOS SDK 向けに AudioTrackSink 機能を追加するパッチである `ios_audio_track_sink.patch` についての説明です。ネイティブの `AudioTrackInterface::AddSink()` / `RemoveSink()` を Objective-C / Swift から扱えるようにしています。

## 目的

- iOS 向け libwebrtc で `RTCAudioTrack` から PCM データを取得できる API を追加する
- 既存の C++ `AudioTrackInterface::AddSink()` と同等の機構を Objc API として提供し、トラックごとの録音・音量可視化などの用途に活用できるようにする

## 背景

- 標準の iOS SDK には、`RTCAudioTrack` の PCM データを直接受け取る手段がない。
- C++ では `AudioTrackInterface` に `AddSink()` / `RemoveSink()` が用意され、`AudioTrackSinkInterface` 実装を介して PCM を取得できる。
- このパッチでは Objective-C で `AudioTrackSinkInterface` と同等の役割を担う `RTCAudioTrackSink` プロトコルと、そのブリッジ実装を追加している。

## 変更点の概要

- `sdk/objc/api/peerconnection/RTCAudioTrackSink.h` を新規追加し、`onData()` と任意の `preferredNumberOfChannels()` を公開する `RTCAudioTrackSink` プロトコルを定義。
- `sdk/objc/api/RTCAudioTrackSinkAdapter.{h,mm}` と `RTCAudioTrackSinkAdapter+Private.h` を追加し、ObjC の `RTCAudioTrackSink` と C++ の `AudioTrackSinkInterface` を橋渡しするアダプターを実装。
- `sdk/objc/api/peerconnection/RTCAudioTrack.h/mm` に `addSink:` / `removeSink:` を追加し、トラックごとに複数のシンクを登録・解除できるように変更。`dealloc` で全シンクをネイティブ側から解除する処理を追加。
- `sdk/BUILD.gn` に上記ファイルを登録。

### パッチ実装のポイント

- `RTCAudioTrackSinkAdapter` は `AudioTrackSinkInterface` を実装し、`OnData` で受け取った PCM を `NSData` にコピーして `RTCAudioTrackSink#onData` に渡す。コールバックはネイティブ音声スレッドで呼ばれるため、重い処理は別スレッドへ委譲する必要がある。
- `preferredNumberOfChannels` が実装されていれば `NumPreferredChannels` で値を返し、`-1` の場合は「指定なし」として既定のチャンネル数が渡される。
- RTCAudioTrack の `addSink:` は同一インスタンスの重複登録を防ぎ、`removeSink:` は登録済みシンクのみを解除して `AudioTrackSinkInterface` との紐づけを適切に管理する。`dealloc` では残存シンクをすべて解除し、ネイティブ側の参照リークを防ぐ。

## RTCAudioTrackSink の利用例

```swift
final class AudioLogger: NSObject, RTCAudioTrackSink {
  func onData(_ audioData: Data,
              bitsPerSample: Int,
              sampleRate: Int,
              numberOfChannels: Int,
              numberOfFrames: Int) {
    // audioData は PCM16LE。必要なら別キューへ渡す。
  }

  func preferredNumberOfChannels() -> Int {
    return 1 // 例: モノラルで受けたい場合。指定しなければ -1 を返す。
  }
}

let track: RTCAudioTrack = /* MediaStream などから取得 */
let sink = AudioLogger()
track.addSink(sink)

// 不要になったら
track.removeSink(sink)
```

- `RTCAudioTrackSink` と `RTCAudioTrack` は 1:1 で紐づける運用を推奨。`onData` にトラック識別子が含まれないため、1:N で共有すると呼び出し元トラックを判別できなくなる。

