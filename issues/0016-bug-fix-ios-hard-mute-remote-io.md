# RemoteIO の SetMicrophoneMute でハードウェアミュートを実現する

- Created: 2026-09-07
- Completed: {YYYY-MM-DD}
- Branch: feature/m150.7871
- Polished: {YYYY-MM-DD}

## 目的

ステレオ出力（RemoteIO）利用時、Sora iOS SDK のマイクのハードウェアミュートが機能しない。
ハードウェアミュートは、マイクの入力 bus を無効化してマイクデータの捕捉を止め、iOS のマイクインジケーターを消すことを指す。
現状の RemoteIO では mute してもマイクが捕捉を続け、インジケーターも点いたまま、SDK 側は成功と報告する。
`RemoteIOAudioUnit::SetMicrophoneMute` を実装して、ハードウェアミュートの約束を満たす。

## 現状

- ハードミュートの呼び出し経路: sora-ios-sdk の `AudioDeviceModuleWrapper.setAudioHardMute` が
  `RTCAudioDeviceModule.pauseRecording` / `resumeRecording` を呼び、`AudioDeviceIOS::ReinitAudioUnitForMicrophoneMute` 経由で
  `AudioUnitInterface::SetMicrophoneMute` を呼ぶ。
- VPIO（モノラル）: `VoiceProcessingAudioUnit::SetMicrophoneMute` は `detect_mute_speech_ == false` のとき、
  入力 bus の `kAudioOutputUnitProperty_EnableIO`（`kAudioUnitScope_Input` / `kInputBus`）を `enable ? 0 : 1` でトグルし、
  マイク捕捉を止めてインジケーターを消す。SDK は既定の `CreateAudioDeviceModule`（`muted_speech_event_handler = nullptr`）を
  使うため `detect_mute_speech_ = false` となり、この経路が選ばれる。
- RemoteIO（ステレオ）: `RemoteIOAudioUnit::SetMicrophoneMute` は no-op で `true` を返す。入力 bus は
  `RemoteIOAudioUnit::Init` で常に有効化されるため、mute しても入力 bus は有効なまま。マイクの捕捉とインジケーターは止まらず、
  `ReinitAudioUnitForMicrophoneMute` は成功するので SDK は成功と判断する（ハードミュートが機能しないのに成功を報告する）。
- no-op にした経緯: stereo パッチで RemoteIO に VoiceProcessing 固有の `kAUVoiceIOProperty_MuteOutput` が無いことだけに
  着目し、`false` を返すと `ReinitAudioUnitForMicrophoneMute` がエラー扱いになるのを避けて no-op にした。
  ただし SDK が使うのは `MuteOutput` ではなく EnableIO トグル経路であり、これは RemoteIO にも存在する。

## 設計方針

- `RemoteIOAudioUnit::SetMicrophoneMute(bool enable)` を、VPIO の EnableIO トグル経路と同様に
  `kAudioOutputUnitProperty_EnableIO`（`kAudioUnitScope_Input` / `kInputBus`）を `enable ? 0 : 1` で設定する実装にする。
- 適用タイミングは `ReinitAudioUnitForMicrophoneMute` が Stop → Uninitialize → SetMicrophoneMute →
  SetupAudioBuffersForActiveAudioSession → Initialize → Start の順で行うため、未初期化状態で EnableIO を設定できる。
  RemoteIO の状態参照も `AudioUnitInterface::kStarted` 等へ書き換え済みでそのまま通る。
- 出力 bus は入力 bus と独立しているため、mute 中も stereo の再生は維持される。
- `AudioUnitSetProperty` が失敗した場合のみ `false` を返す（`ReinitAudioUnitForMicrophoneMute` がエラー扱いするのはこの場合のみ）。
- playout-only（入力不使用）のときは入力が元々無効のため mute は実質無効（対象外）だが、成功を返す挙動は維持する。
  mono（VPIO）と既存のマイクミュート（`setInitialMicrophoneMute`）の挙動は変更しない。
- 本 issue はバグ修正に絞る。playout-only（入力不使用）は 0014、初期化失敗の伝播は 0011 で別扱い。

## 対応ブランチと依存関係

ユーザー指定の例外として、個別ブランチを作成せず `feature/m150.7871` で対応する。

- 0014（playout-only RemoteIO）: 同一の EnableIO 入力制御プリミティブ。本 issue は「入力が使われる場合」の mute、
  0014 は「入力を最初から使わない」ケース。実装は `RemoteIOAudioUnit` に局所化し共存する。
- 0011（初期化失敗の伝播）: 本 issue の変更は `SetMicrophoneMute` に局所で、0011 の対象（`InitPlayOrRecord` の
  `Initialize` 戻り値確認）とは別。
- Sora iOS SDK: ネイティブのハードミュートが成立すれば、sora-ios-sdk の 0010 が計画する「ステレオ時は
  `setAudioHardMute` をエラーにする」workaround は不要になる（SDK 側の省略可否は SDK 側で判断）。

## テスト方針

モックやスタブは使用しない。

- 実機で、ステレオ sendrecv / sendonly の送信中に `setAudioHardMute(true)` を呼び、マイクの捕捉が止まり、
  iOS のマイクインジケーターが消えることを確認する。
- unmute で捕捉とインジケーターが戻ることを確認する。
- mute / unmute の間、ステレオ出力（再生）が途切れず維持されることを確認する。
- mono（VPIO）の既存ハードミュートを壊さないことを確認する。
- 0014（playout-only / recvonly）に影響しないことを確認する。
- Bluetooth（A2DP / HFP）や割り込み後の挙動、マイク権限の有無を確認する。
- 失敗条件はログで切り分けられるようにし、検証した条件と未検証の条件を記録する。

## 完了条件

- `RemoteIOAudioUnit::SetMicrophoneMute` が入力 bus の EnableIO をトグルし、実際の成功 / 失敗を返す。
- ステレオ送信中にハードミュートでマイクインジケーターが消え、マイク捕捉が止まる。unmute で復帰する。
- mute / unmute 中もステレオ再生が維持される。
- mono（VPIO）のハードミュート、既存のマイクミュート、playout-only（0014）の挙動が変わらない。
- 実機での検証条件と結果が記録されている。
