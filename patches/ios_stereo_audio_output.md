# ios_stereo_audio_output.patch の解説

iOS 向け libwebrtc の Audio Device Module (ADM) にステレオ playout 経路を追加するパッチ `ios_stereo_audio_output.patch` の解説である。

## 目的

- iOS 向け libwebrtc の playout をステレオ (2ch) で再生できるようにする
- SDK 利用側から `RTCAudioDeviceModule` 経由でステレオ出力を有効化する API を公開する

recording (入力) 側のステレオ化は本パッチの対象外である。別 issue で扱う。

## 背景

upstream の `AudioDeviceIOS` はステレオ playout API がスタブになっている。

- `StereoPlayoutIsAvailable` は常に `available = false`
- `SetStereoPlayout` は `-1` を返す
- `StereoPlayout` は常に `enabled = false`

また、AudioUnit として `kAudioUnitSubType_VoiceProcessingIO` を使う設計になっており、AVAudioSession の mode も `AVAudioSessionModeVoiceChat` に固定されている。この組み合わせでは playout の `mChannelsPerFrame` が 1 に張り付いてしまい、ステレオを通せない。

## 変更点の概要

- `sdk/objc/native/src/audio/audio_device_ios.mm`
  - `StereoPlayoutIsAvailable` / `SetStereoPlayout` / `StereoPlayout` を実装。`playout_parameters_.channels()` を単一の source of truth として参照する
  - `UpdateAudioDeviceBuffer` の playout チャンネル数 `RTC_DCHECK_EQ(playout_parameters_.channels(), 1)` を削除
  - `OnGetPlayoutData` の `RTC_DCHECK_EQ(1, audio_buffer->mNumberChannels)` を `playout_parameters_.channels()` との比較に置き換える。silence 出力時の byte サイズ計算とサンプル取得 (`fine_audio_buffer_->GetPlayoutData`) にもチャンネル数を反映
  - `CreateAudioUnit` は `playout_parameters_.channels() == 2` の場合のみ新設の `RemoteIOAudioUnit` を使い、それ以外は従来通り `VoiceProcessingAudioUnit` を使う
  - `ConfigureAudioSession` / `ConfigureAudioSessionLocked` はステレオ playout 有効時のみ共有設定の mode を一時的に `AVAudioSessionModeDefault` に差し替えて `configureWebRTCSession:` を呼び、直後に元へ戻す。既定 (モノラル) では `VoiceChat` を維持する
- `sdk/objc/native/src/audio/voice_processing_audio_unit.h`
  - デストラクタ、`Init`、`Initialize` を `virtual` 化 (`RemoteIOAudioUnit` がオーバーライドするため)。`GetFormat` は派生側で異なるシグネチャの新規メソッドを追加するだけなので virtual にはしない (名前隠蔽を避ける)
  - private セクション全体 (`OnGetPlayoutData` / `OnDeliverRecordedData` の static コールバック、`Notify*` インスタンスメソッド、`GetFormat`、`DisposeAudioUnit`、`vpio_unit_` / `state_` などのメンバ) を `protected` に格上げし、`RemoteIOAudioUnit` からアクセスできるようにする
- `sdk/objc/native/src/audio/remote_io_audio_unit.h` / `.mm` (新規)
  - `VoiceProcessingAudioUnit` を継承し `componentSubType` に `kAudioUnitSubType_RemoteIO` を用いる AudioUnit ラッパー
  - コンストラクタで `play_channels_` / `rec_channels_` を確定させ、`Initialize` で入力/出力それぞれの stream format に反映する
  - `Init` では出力 bus (`kAudioOutputUnitProperty_EnableIO`, `kAudioUnitScope_Output`, `kOutputBus`) と入力 bus (`kAudioOutputUnitProperty_EnableIO`, `kAudioUnitScope_Input`, `kInputBus`) の両方を有効化し、`OnGetPlayoutData` と `OnDeliverRecordedData` の両方のコールバックを登録する。入力側コールバックを忘れると recording が空回りするため必ず設定している
  - デストラクタ本体を `.mm` 側に明示的に定義し、未定義シンボルによるリンクエラーを防ぐ
- `sdk/objc/components/audio/RTCAudioDeviceModule.h` / `.mm`
  - `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を追加。内部で `AudioDeviceModule::SetStereoPlayout` / `StereoPlayout` を呼ぶ
  - `setStereoPlayoutEnabled:` は `CHECKinitialized_` を通すために ADM 未初期化なら `Init()` を先に呼ぶ (`Init` は冪等)
- `sdk/BUILD.gn`
  - `audio_device` ターゲットに `remote_io_audio_unit.h` / `.mm` を追加

## 適用順序と登録先

本パッチは `ios_audio_pause_resume.patch` が作成する `RTCAudioDeviceModule.h` / `.mm` に手を入れるため、`run.py` の `PATCHES["ios_sdk"]` では `ios_audio_pause_resume.patch` の後に本パッチを並べる。

`ios` ターゲットには `ios_audio_pause_resume.patch` が入っておらず、`RTCAudioDeviceModule` が存在しないため本パッチも `ios_sdk` にのみ登録している。issue 0005 の完了条件は「core を触る場合は `ios` と `ios_sdk` の両方に登録」と書いているが、本パッチは SDK 拡張 API (`RTCAudioDeviceModule` への追加) と一体で提供されるため、そちらの規則に従い `ios_sdk` のみに登録する判断とした。結果として raw `ios` ビルド (Sora C++ SDK 相当) には本機能は含まれない。

## SDK 側 API 呼び出し例

```swift
import WebRTC

// ADM を先に作り、PeerConnectionFactory 生成前にステレオを有効化する
let adm = RTCAudioDeviceModule()
let result = adm.setStereoPlayoutEnabled(true)
if result != 0 {
    // 有効化に失敗した (すでに InitPlayout 後、など)
}

let factory = RTCPeerConnectionFactory(
    encoderFactory: RTCDefaultVideoEncoderFactory(),
    decoderFactory: RTCDefaultVideoDecoderFactory(),
    audioDeviceModule: adm)

// この後 PeerConnection を作成すると playout は 2ch で動く
```

## 利用上の注意

### AEC / AGC が無効になる

ステレオ playout 有効時は AudioUnit を `VoiceProcessingIO` から `RemoteIO` に切り替える。この結果、ハードウェア由来の以下の機能が使えなくなる。

- 音響エコーキャンセラ (AEC)
- 自動利得制御 (AGC)
- 音声品質調整 (voice processing)

双方向通話用途では、モノラル (既定) のままにしてハードウェア AEC / AGC を活かすことを推奨する。ステレオ配信主体で受信専用寄りの用途 (視聴中心) で本 API を有効化するとよい。

### AVAudioSession のモードが変わる

ステレオ playout 有効時のみ、`RTCAudioSession` に反映される mode が `AVAudioSessionModeVoiceChat` から `AVAudioSessionModeDefault` に切り替わる。切り替えは本パッチ内 (`ConfigureAudioSession` / `ConfigureAudioSessionLocked`) で自動的に行い、既定 (モノラル) 時は `VoiceChat` のまま変わらない。

### preferredOutputNumberOfChannels は 1 のまま

本パッチは AVAudioSession の `preferredOutputNumberOfChannels` (共有 `RTCAudioSessionConfiguration._outputNumberOfChannels` に由来) を書き換えない。理由は 2 つある。

1. `RTCAudioSession+Configuration.mm` の `setPreferredOutputNumberOfChannels:` 呼び出しは `mode == AVAudioSessionModeVoiceChat` のときだけガードを通る。本パッチは stereo 有効時に mode を Default に切り替えるため、そのガードを通らず結局反映されない
2. 実チャンネル数の決定要因は `RemoteIOAudioUnit::Initialize` が設定する出力 stream format の `mChannelsPerFrame = 2` である。Core Audio 上、AudioUnit stream format が優先される

過去試作でも同じ構造で実機ステレオ再生を確認済み。実機での挙動確認 (後述) が済んでいることを前提に本設計を採用している。将来的に Bluetooth ルート切替などで挙動差が出た場合は、共有設定側の `outputNumberOfChannels` も一時差し替えする方向で拡張余地がある。

### Bluetooth デバイスの制約

Bluetooth ヘッドセットの動作は接続プロファイルに依存する。

- HFP (Hands-Free Profile) 接続: モノラルまでしか扱えない。ステレオ設定でも実際には片チャンネルに畳まれる可能性がある
- A2DP 接続: ステレオが利用できる。ただし A2DP は入力に非対応なため、送信 (recording) は別経路になる

libwebrtc の既定 `RTCAudioSessionConfiguration` は `AVAudioSessionCategoryOptionAllowBluetoothHFP` のみを設定し `AllowBluetoothA2DP` を含まない。Bluetooth 経由のステレオ再生を得るには、アプリ側で `AllowBluetoothA2DP` を追加した config を `+[RTCAudioSessionConfiguration setWebRTCConfiguration:]` で流し込む必要がある。

### マイク権限は視聴専用でも必須

本パッチは `RemoteIOAudioUnit::Init` で入力 bus も必ず `EnableIO` し、`AudioUnitInitialize` の成立にマイクへのアクセスが必要となる。既存の `VoiceProcessingIO` 経路と同じ制約だが、ステレオ視聴専用のユースケースでも変わらない。`Info.plist` に `NSMicrophoneUsageDescription` を用意し、ユーザーからマイク許可を取得すること。許可が無いと `AudioUnitInitialize` が失敗し、リトライ後に stereo playout 自体が動かない。

### 呼び出しタイミングとスレッドの制約

`setStereoPlayoutEnabled:` は次の 3 条件をすべて満たすタイミングで呼ぶこと。

- **順序**: `RTCPeerConnectionFactory` の生成前 (= `InitPlayout` 前) に呼ぶ。`AudioDeviceModuleIOS::SetStereoPlayout` は `PlayoutIsInitialized()` が真の場合に `-1` を返す
- **スレッド**: 本 ADM を生成したスレッドから呼ぶ。別スレッドから呼ぶと `RTC_DCHECK_RUN_ON(thread_)` により Debug ビルドが停止する (`stereoPlayoutEnabled` の getter 側も同じ制約)
- **ライフサイクル**: `AudioDeviceModule::Terminate()` が実行されると次の `Init()` で `playout_parameters_.channels()` が既定 (`outputNumberOfChannels`、= 1) に戻る。ADM を再利用する場合は `setStereoPlayoutEnabled:YES` を再度呼ぶこと

### 実機での動作確認が必要

CoreAudio / AVAudioSession の挙動は Xcode / iOS シミュレータでは再現しにくく、また AudioUnit の実 2ch 動作は自動テストの範疇では確認できない。本パッチの検証時は必ず iOS 実機で `setStereoPlayoutEnabled:YES` を呼んだうえで、L/R の片チャンネルだけを鳴らすステレオコンテンツ等で 2ch 出力が成立していることを聴感で確認すること。

## プロトタイプからの差分

過去試作 (m138 系) に対して本パッチで意図的に取り除いた要素は次の通り。

- recording (入力) 側の変更 (`SetStereoRecording` / `StereoRecordingIsAvailable` / `StereoRecording` の実装、`OnDeliverRecordedData` のバッファサイズ計算変更、`AudioDeviceModuleIOS::SetStereoRecording` のエラーコード修正) は本パッチには含めない
- デバッグ用の `STEREO_LOG:` プレフィックス printf / `RTCLog` は本パッチには含めない
- `RTCAudioSessionConfiguration.m` への空行追加のみの hunk は本パッチには含めない
- `RTCAudioSession+Configuration.mm` の `AVAudioStereoOrientationLandscapeRight` 決め打ちは本パッチには含めない
- `AudioDeviceIOS` に `play_channels_` / `rec_channels_` の独立メンバを追加する二系統管理は本パッチには含めない。playout チャンネル数は `playout_parameters_.channels()` を単一の source of truth として扱う
