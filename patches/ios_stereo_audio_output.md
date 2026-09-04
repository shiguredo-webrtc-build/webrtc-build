# ios_stereo_audio_output.patch の解説

iOS SDK 向けにステレオ音声出力 (playout) を有効化するためのパッチである `ios_stereo_audio_output.patch` についての説明です。標準の libwebrtc iOS ADM ではステレオ playout がスタブ実装のままモノラルに潰されてしまうため、AudioUnit 種別を抽象化する層を導入したうえで、ステレオ有効時のみ RemoteIO 経路に切り替えて 2ch 出力を通します。

## SDK 利用者向け

### 目的

- iOS 向け libwebrtc で音声トラックをステレオのまま再生できるようにします
- `RTCAudioDeviceModule` から明示的な API 呼び出しでステレオ出力を切り替えられるようにします
- 既定の挙動は従来通りモノラル (`VoiceProcessingIO` + `AVAudioSessionModeVoiceChat`) を維持し、ステレオ有効時だけ挙動を切り替えます

### SDK 側 API 呼び出し例

Swift の場合:

```swift
import WebRTC

let adm = RTCAudioDeviceModule()

// ステレオ出力を有効化する。
// この呼び出しは RTCPeerConnectionFactory に adm を渡す前に行う。
let result = adm.setStereoPlayoutEnabled(true)
if result != 0 {
    // 失敗。ADM 初期化に失敗している可能性がある。
}

// 現在の状態を取得する。
let enabled = adm.stereoPlayoutEnabled()

let factory = RTCPeerConnectionFactory(
    encoderFactory: nil,
    decoderFactory: nil,
    audioDeviceModule: adm)
```

Objective-C の場合:

```objc
#import <WebRTC/WebRTC.h>

RTCAudioDeviceModule *adm = [[RTCAudioDeviceModule alloc] init];

// ステレオ出力を有効化する。
NSInteger result = [adm setStereoPlayoutEnabled:YES];
if (result != 0) {
  // 失敗。ADM 初期化に失敗している可能性がある。
}

// 現在の状態を取得する。
BOOL enabled = [adm stereoPlayoutEnabled];

RTCPeerConnectionFactory *factory =
    [[RTCPeerConnectionFactory alloc] initWithEncoderFactory:nil
                                              decoderFactory:nil
                                           audioDeviceModule:adm];
```

### 利用上の注意

- **AEC / AGC が使えなくなる**: ステレオ出力を有効化すると内部的に AudioUnit を `VoiceProcessingIO` から `RemoteIO` に切り替えるため、iOS 標準のハードウェア AEC / AGC / マイクミュートは動作しなくなります。VoIP 用途で AEC / AGC が必須の場合はステレオ出力を有効化しないでください。
- **`pauseRecording` / `resumeRecording` が形骸化する**: 上記と関連。ステレオ有効時 (`RemoteIO` 経路) は `RemoteIOAudioUnit::SetMicrophoneMute` が no-op のため、`RTCAudioDeviceModule.pauseRecording` を呼んでも `Stop → Uninitialize → Initialize → Start` のフローだけ走ってミュート状態は切り替わりません (iOS のマイクインジケータも消えません)。ステレオ配信中に録音停止が必要なユースケースでは、ステレオ有効化と `pauseRecording` を組み合わせないでください。
- **`initWithBypassVoiceProcessing:YES` は無視される**: `RTCAudioDeviceModule` の bypass フラグは `VoiceProcessingIO` の内部音声処理をバイパスするための設定です。ステレオ有効時は `RemoteIO` を使うため VP 由来の音声処理はもともと無く、bypass 指定は事実上意味を持ちません (エラーにはならず単に無視されます)。
- **mode 切替**: ステレオ有効時のみ `AVAudioSession` の mode が `AVAudioSessionModeVoiceChat` から `AVAudioSessionModeDefault` に一時差し替えされます (WebRTC セッション構成時のみ)。モノラルに戻せば mode も戻ります。
- **Bluetooth 制約 + A2DP category option**: HFP はモノラルまでしか出せません。A2DP ではステレオが出せます。既定の `AVAudioSessionCategoryPlayAndRecord` は録音併用のため HFP が選ばれる場合があります。ステレオ出力を確実に狙うなら、アプリ側で category / options を A2DP を許容する構成に調整することを検討してください (本パッチは category の書き換えまでは踏み込みません)。
- **マイク権限**: `RTCAudioSessionCategoryPlayAndRecord` を用いる WebRTC の性質上、マイク権限は依然として必要です。
- **呼び出しタイミング + スレッド + Terminate 跨ぎ**: `setStereoPlayoutEnabled:` は `RTCPeerConnectionFactory` に `RTCAudioDeviceModule` を渡す前、かつ ADM 側の `InitPlayout` の前に呼んでください。呼び出しスレッドは ADM を生成したスレッドを守ってください。ADM を `Terminate` した後で再度使う場合は、再度 `setStereoPlayoutEnabled:` から設定し直してください。
- **実機検証**: シミュレータの Core Audio は挙動が実機と異なるため、ステレオ出力の確認は必ず実機で行ってください。

## 開発者向け

### 背景

- 標準の libwebrtc iOS ADM (`AudioDeviceIOS`) は `StereoPlayoutIsAvailable` / `SetStereoPlayout` / `StereoPlayout` が `Not implemented` のスタブ実装であり、実際に呼び出しても常にモノラルに潰される
- 出力経路の AudioUnit も `VoiceProcessingIO` + `mChannelsPerFrame = 1` 固定になっており、`OnGetPlayoutData` / `UpdateAudioDeviceBuffer` で `mNumberChannels == 1` を `RTC_DCHECK` している
- Opus デコーダは SDP fmtp `stereo=1` で 2ch を出せるため、ボトルネックは ADM から AudioUnit までの playout 経路である

### 変更点の概要

- `sdk/objc/native/src/audio/audio_unit_interface.h` を新規追加し、`AudioUnitInterface` abstract class を定義。`State { kInitRequired, kUninitialized, kInitialized, kStarted }` enum と `kBytesPerSample` 定数を interface 側に集約し、`Init` / `Initialize` / `Start` / `Stop` / `Uninitialize` / `SetMicrophoneMute` / `Render` / `GetState` を pure virtual として並べる
- `sdk/objc/native/src/audio/voice_processing_audio_unit.h` を最小改造。`class VoiceProcessingAudioUnit : public AudioUnitInterface` に継承を追加し、既存メソッドに `override` を付与、自前 State enum を削除。private セクションの protected 昇格や既存メソッドの virtual 後付けは行わない
- `sdk/objc/native/src/audio/voice_processing_audio_unit.mm` は `kBytesPerSample` の定義を `AudioUnitInterface::kBytesPerSample` に、`GetState()` の戻り値型注記を `AudioUnitInterface::State` に更新するだけの最小追随
- `sdk/objc/native/src/audio/remote_io_audio_unit.h` / `.mm` を新規追加。`AudioUnitInterface` を直接実装した独立クラスとして `RemoteIOAudioUnit` を定義。`componentSubType = kAudioUnitSubType_RemoteIO`、入力バスと出力バスに `EnableIO` + コールバック配線を行い、`GetFormat(sample_rate, channels)` で playout / record 個別のチャンネル数を扱える。`AudioUnitInitialize` のリトライループも独立に持つ
- `sdk/objc/native/src/audio/audio_device_ios.h` の `audio_unit_` メンバ型を `std::unique_ptr<VoiceProcessingAudioUnit>` から `std::unique_ptr<AudioUnitInterface>` に変更
- `sdk/objc/native/src/audio/audio_device_ios.mm` 内の `VoiceProcessingAudioUnit::kInitialized` / `kUninitialized` / `kStarted` / `kInitRequired` / `kBytesPerSample` の参照をすべて `AudioUnitInterface::` に置換 (17 箇所)。`ios_audio_pause_resume.patch` が追加した `ReinitAudioUnitForMicrophoneMute` 内の 2 箇所も同時に置換
- `AudioDeviceIOS::StereoPlayoutIsAvailable` / `SetStereoPlayout` / `StereoPlayout` を実装。`playout_parameters_.channels()` を単一の source of truth として参照し、`play_channels_` のような別メンバによる二重管理は作らない。3 関数に `RTC_DCHECK_RUN_ON(thread_)` を付与
- `AudioDeviceIOS::UpdateAudioDeviceBuffer` の `RTC_DCHECK_EQ(playout_parameters_.channels(), 1);` を削除。recording 側の DCHECK は残す
- `AudioDeviceIOS::OnGetPlayoutData` の `RTC_DCHECK_EQ(1, audio_buffer->mNumberChannels);` を `RTC_DCHECK_EQ(playout_parameters_.channels(), audio_buffer->mNumberChannels);` に置換。silence 出力時のバイト数計算と `fine_audio_buffer_->GetPlayoutData(...)` の要求サンプル数も `playout_parameters_.channels()` を掛けた値に修正
- `AudioDeviceIOS::CreateAudioUnit` で `playout_parameters_.channels() == 2` のとき `RemoteIOAudioUnit`、それ以外は既定の `VoiceProcessingAudioUnit` を生成する分岐を追加
- `AudioDeviceIOS::ConfigureAudioSession` / `ConfigureAudioSessionLocked` にステレオ有効時のみ `AVAudioSessionModeDefault` に一時差し替えするロジックを追加。復元は `@try/@finally` で保証する
- `sdk/objc/components/audio/RTCAudioDeviceModule.h` / `.mm` に `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を追加。`setStereoPlayoutEnabled:` は ADM が未初期化なら先に `Init()` を呼ぶ冪等実装。`stereoPlayoutEnabled` は未初期化時は `NO` を返す
- `sdk/BUILD.gn` の `audio_device` ターゲットに新規ファイル 3 本 (`audio_unit_interface.h`、`remote_io_audio_unit.h`、`remote_io_audio_unit.mm`) を追加

### 適用順序と登録先

- 本パッチは `ios_sdk` にのみ登録される。raw `ios` ビルドには本機能は含まれない
- 依存する `ios_audio_pause_resume.patch` が同じく `ios_sdk` にのみ登録されている先例に合わせている
- `run.py` の `PATCHES["ios_sdk"]` では `ios_audio_pause_resume.patch` の直後に `ios_stereo_audio_output.patch` を配置する (pause_resume が追加する `ReinitAudioUnitForMicrophoneMute` の State 参照を本パッチが書き換えるため、順序は不可逆)

### preferredOutputNumberOfChannels は 1 のままとする設計判断

- `RTCAudioSessionConfiguration` の `kRTCAudioSessionPreferredNumberOfChannels` は 1 のまま据え置く
- 実際の playout チャンネル数は `RemoteIOAudioUnit` の stream format 側で決まるため、hint 用の `preferred*` を 2 に上げる必要はない
- `AVAudioSession.preferredOutputNumberOfChannels` は要求であって保証ではないため、シングルトンの hint を触らずに RemoteIO 側 format で決着させたほうが影響範囲が閉じる

### mode の一時差し替えは限定的に許容する設計判断

- 上記 `preferredOutputNumberOfChannels` とは別扱い。`AVAudioSession` の mode だけは `ConfigureAudioSession` / `ConfigureAudioSessionLocked` の内側でステレオ有効時のみ `AVAudioSessionModeDefault` に一時差し替えする
- 理由: `AVAudioSessionModeVoiceChat` のままだと OS 側で 1ch にクランプされるため、mode を Default に切り替えないと RemoteIO の 2ch format が実効的に活きない
- 復元は `@try/@finally` で保証。差し替えは `configureWebRTCSession:` の呼び出し窓の中に閉じ込め、外部から観測される時間を最小化する
- シングルトンを書き換える点は preferred* と同じ懸念があるが、mode 差し替えなしにはステレオが機能しないため許容せざるを得ない (代替案として ADM 固有の `RTCAudioSessionConfiguration` インスタンスを別途持って `configureWebRTCSession:` に渡す方式もあるが、`RTCAudioSession` の public API がシングルトン前提なので影響範囲が大きくなる)
