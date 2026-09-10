# iOS の入力初期化を「AudioUnit 生成前に 1 回」の契約に単純化する

- Created: 2026-09-10
- Completed: {YYYY-MM-DD}
- Branch: feature/refactor-simplify-ios-audio-input-initialization
- Polished: {YYYY-MM-DD}

## 目的

`ios_stereo_audio_output.patch` が持つ入力初期化の非同期機構 (generation / owner / `input_safety_` / `PostTask` / 生成後対応) を削除し、sora-ios-sdk の実際の使い方に合わせて「AudioUnit 生成前に 1 回だけ」の契約に単純化する。ステレオ対応で抱き合わせて導入した過剰な機構を削り、パッチを読みやすくする。

## 現状

- `AudioUnitInterface::InitializeInput(bool initial_mute)` が VPIO / RemoteIO の両方に実装されており、入力初期化の抽象化は行われている (この抽象化は維持する)。
- 一方で `RTCAudioSession.mm` に `_inputOwner` / `_inputGeneration` / `_inputInitializer` / `_isInitializingInput` / `_waitsInputInit` / `_isInputInited` / `_inputInitCompletionHandler` / `_initialMicrophoneMute` と、`prepareInputInitializationForOwner:` / `setInputInitializer:owner:` / `hasInputRequestForOwner:generation:` / `deferInputInitializationForOwner:` / `clearInputInitializationForOwner:` / `completeInputInitializationForOwner:generation:error:` / `scheduleInputInitialization` がある。
- `AudioDeviceIOS` に `input_safety_` (`PendingTaskSafetyFlag`) と `RegisterInputInitializer` / `InitializeAudioInput` があり、`thread_->PostTask` で worker に投稿する。`InitializeAudioInput` は停止 → 未初期化 → 入力有効化 → 再初期化 → 再開を行う。
- これらは issue 0014 の設計方針「生成前の要求を待機し、生成後の要求では必要な停止と再初期化を経て入力を接続する」「入力要求の重複、停止 / 破棄時のキャンセル、古い要求が次の AudioUnit を有効にする経路を防ぐ」に対応する。
- sora-ios-sdk は `Sora/PeerChannel.swift` の `initializeAudioInput()` を初回 offer の `setRemoteDescription` 完了時に 1 回だけ呼ぶ。この時点で AudioUnit は未生成であり、生成後の `initializeInput` は使われない。
- 入力の再初期化跨ぎの再適用は `AudioUnitInterface::input_initialized_` が既に担っている (`remote_io_audio_unit.mm` の `Initialize` が `input_initialized_` を見て入力フォーマットを再設定する)。

## 設計方針

- 公開契約を「`initializeInput` は AudioUnit 生成前に 1 回だけ呼ぶ」に限定する。生成後の呼び出しはエラーを返す。
- 古い要求は単純破棄する。generation / owner による照合は行わない。
- `AudioUnitInterface::InitializeInput` と `input_initialized_` による再初期化跨ぎの再適用は維持する。
- `InitPlayOrRecord` (worker 上) が最初の `Initialize()` の前に要求を消費して `InitializeInput(initial_mute)` を呼ぶ。要求が無ければ入力を初期化しない。
- `ShutdownPlayOrRecord` で保留中の要求をエラーで完了させる (元実装は完了を呼んでいなかったが、呼び出し側が待ち続けないようにする)。
- `RTCAudioSession` は要求フラグ・初期ミュート・完了ハンドラ程度に縮小し、`AudioDeviceIOS` から `input_safety_` / `PostTask` / `InitializeAudioInput` を削除する。
- `configureWebRTCSession` の `requiresInput` 判定 (受信専用では入力を要求しない) は維持する。

## 不採用とした設計案

- 生成後の `initializeInput` を維持する案。RemoteIO の `InitializeInput` は `kUninitialized` を要求し、生成後は停止・再初期化・再開が必要になる。この対応が generation / owner / `input_safety_` / `PostTask` の主因であり、sora-ios-sdk はこの経路を踏まないため採用しない。

## テスト方針

- `python3 run.py revert ios` / `revert ios_sdk` が成功することを確認する。
- `sdk_unittests` をビルドし、`iossim` で `RTCStereoAudioOutputTests` などを実行する。
- 生成後・取消・世代を検証する `RTCManualAudioInputTests` の該当テストは削除、または生成前ケースのみに縮小する。

## 完了条件

- generation / owner / `input_safety_` / `PostTask` / 生成後 stop-reinit-restart が削除されている。
- 入力初期化が AudioUnit 生成前に 1 回だけ行われ、受信専用では入力を初期化しない契約が維持されている。
- `revert ios` / `revert ios_sdk` と XCTest が通る。
- `CHANGES.md` に変更内容を追記している。

## 解決方法

未着手
