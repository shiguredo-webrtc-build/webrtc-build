# iOS の録音 pause/resume を factory の worker 実行に移し bindToFactory を削除する

- Created: 2026-09-10
- Completed: {YYYY-MM-DD}
- Branch: feature/refactor-remove-ios-adm-factory-binding
- Polished: {YYYY-MM-DD}

## 目的

`RTCAudioDeviceModule` の `pauseRecording` / `resumeRecording` が `bindToFactory` で factory と worker を後から受け取り、呼び出し中だけ factory を強参照する構造をやめる。worker を所有する `RTCPeerConnectionFactory` に worker 実行の入口を設け、sora-ios-sdk がそれを介して ADM を操作する形にして、結合と寿命管理の複雑さを削除する。

## 現状

- `ios_audio_pause_resume.patch` が `RTCAudioDeviceModule+Private.h` / `.h` / `.mm` に `bindToFactory:workerThread:` / `_factory` / `_workerThread` / `pauseRecording` / `resumeRecording` を追加している。
- `RTCPeerConnectionFactory.mm` が `initWith...audioDeviceModule:` の最後で `[audioDeviceModule bindToFactory:self workerThread:self.workerThread]` を呼ぶ。
- `RTCAudioDeviceModule.mm` の `setRecordingPaused:` は `_factory` を強参照で保持して worker 破棄を防ぎつつ、`worker->IsCurrent() ? op() : worker->BlockingCall(op)` を実行する。
- worker は factory が所有する `_workerThread` で、`AudioDeviceIOS::thread_` は ADM の `Init()` 時に `Thread::Current()` で拾った同じスレッドである。
- sora-ios-sdk の呼び出しは `MediaChannel.setAudioHardMute` → `AudioDeviceModuleWrapper.setAudioHardMute` → `audioDeviceModule.pauseRecording()` / `resumeRecording()` のみで、libwebrtc 内部からの呼び出しは無い。
- `AudioDeviceModuleWrapper` は初回のハードミュート機能で追加されたクラスだが、セッション操作と状態管理は後に ADM 側へ移り、現在は `DispatchQueue` による直列化と pause/resume の呼び出しだけが残っている。
- `RTCPeerConnectionFactory` の `workerThread` は `RTCPeerConnectionFactory+Private.h` にのみあり、C++ の `webrtc::Thread*` のため Swift からは直接利用できない。

## 設計方針

- `RTCPeerConnectionFactory` に worker で同期実行する入口 (例: `- (NSInteger)runOnWorker:(NSInteger (^)(void))block;`) を追加する。`_workerThread` を所有する factory 自身が dispatch するため、呼び出し中は worker の生存が保証される。worker 上から呼ばれた場合は `IsCurrent()` でそのまま実行し、デッドロックしない。
- `RTCAudioDeviceModule` から `bindToFactory` / `_factory` / `_workerThread` と factory 強参照ダンスを削除する。`pauseRecording` / `resumeRecording` は worker 上で呼ぶ薄いラッパーにする。
- `RTCPeerConnectionFactory.mm` の `[audioDeviceModule bindToFactory:...]` を削除する。
- sora-ios-sdk は `AudioDeviceModuleWrapper` を削除し、factory と ADM を既に保持している `NativePeerChannelFactory` に `setAudioHardMute` を集約する。

## テスト方針

- `python3 run.py revert ios_sdk` が成功することを確認する。
- `sdk_unittests` の `RTCAudioDeviceModuleThreadingTests` を `runOnWorker` ベースに更新して実行する。
- sora-ios-sdk 側の `AudioDeviceModuleWrapperTests` を `NativePeerChannelFactory` 向けに更新する。

## 完了条件

- `bindToFactory` が削除され、factory の worker 実行入口を介して pause/resume が実行される。
- sora-ios-sdk から `AudioDeviceModuleWrapper` が削除されている。
- `revert ios_sdk` と XCTest が通る。
- `CHANGES.md` に変更内容を追記している。

## 解決方法

未着手
