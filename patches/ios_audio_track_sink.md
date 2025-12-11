# ios_audio_track_sink.patch の解説

iOS SDK 向けに AudioTrackSink 機能を追加するパッチである `ios_audio_track_sink.patch` についての説明です。ネイティブの `AudioTrackInterface::AddSink()` / `RemoveSink()` を Objective-C / Swift から扱えるようにしています。

## 目的

- iOS 向け libwebrtc で `RTCAudioTrack` から PCM データを取得できる API を追加する
- 既存の C++ `AudioTrackInterface::AddSink()` と同等の機構を ObjC API として提供し、トラックごとの録音・音量可視化などの用途に活用できるようにする

## 背景

標準の Objective-C SDK では RTCAudioTrack から PCM データを直接取得する手段が用意されていない。一方、C++ では AudioTrackInterface に AddSink() / RemoveSink() が定義されており、AudioTrackSinkInterface を実装することで PCM データを受け取ることができる。そこでこのパッチでは、Objective-C 向けに AudioTrackSinkInterface と同等の役割を果たす RTCAudioTrackSink プロトコルと、C++ とのブリッジ実装を追加する。

## 変更点の概要

- `sdk/objc/api/peerconnection/RTCAudioTrackSink.h` を新規追加し、`onData()` と任意の `preferredNumberOfChannels()` を公開する `RTCAudioTrackSink` プロトコルを定義。
- `sdk/objc/api/RTCAudioTrackSinkAdapter.mm` と `RTCAudioTrackSinkAdapter+Private.h` を追加し、ObjC の `RTCAudioTrackSink` と C++ の `AudioTrackSinkInterface` を橋渡しするアダプターを実装。
- `sdk/objc/api/peerconnection/RTCAudioTrack.h/mm` に `addSink:` / `removeSink:` を追加し、トラックごとに複数のシンクを登録・解除できるように変更。`dealloc` で全シンクをネイティブ側から解除する処理を追加。
- `sdk/BUILD.gn` に上記ファイルを登録。

### パッチ実装のポイント

- `AudioTrackSinkAdapter` は `AudioTrackSinkInterface` を実装し、`OnData` で受け取った PCM を `NSData` にコピーして RTCAudioTrackSin の `onData:bitsPerSample:sampleRate:numberOfChannels:numberOfFrames:` に渡す。
- `RTCAudioTrackSink` に `preferredNumberOfChannels` が実装されていれば `AudioTrackSinkAdapter::NumPreferredChannels()` でその値を返す、実装されていない場合は「指定なし」として `-1` をデフォルトで返す。
- RTCAudioTrack の `addSink:` は同一の RTCAudioTrackSink インスタンスの重複登録を防ぎ、`removeSink:` は登録済みシンクのみを解除して `AudioTrackSinkInterface` との紐づけを適切に管理する。`dealloc` では残存シンクをすべて解除し、ネイティブ側の参照リークを防ぐ。

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
    // 例: モノラルで受けたい場合。実装しなければ -1 を返すデフォルト実装が使われる。
    return 1
  }
}

let track: RTCAudioTrack = /* MediaStream などから取得 */
let sink = AudioLogger()
track.addSink(sink)

// 不要になったら
track.removeSink(sink)
```

### RTCAudioTrackSink 利用時の注意点

- `RTCAudioTrackSink` と `RTCAudioTrack` は 1:1 で紐づける運用を推奨。`onData` にトラック識別子が含まれないため、1:N で共有すると呼び出し元トラックを判別できなくなる。
- コールバックはネイティブ音声スレッドで呼ばれるため、重い処理は別スレッドへ委譲する必要がある。

