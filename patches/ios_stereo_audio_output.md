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
    // factory への受け渡し後は設定を変更できない。
}

// 受け付けた設定値を取得する。ADM はまだ初期化されていない。
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
  // factory への受け渡し後は設定を変更できない。
}

// 受け付けた設定値を取得する。ADM はまだ初期化されていない。
BOOL enabled = [adm stereoPlayoutEnabled];

RTCPeerConnectionFactory *factory =
    [[RTCPeerConnectionFactory alloc] initWithEncoderFactory:nil
                                              decoderFactory:nil
                                           audioDeviceModule:adm];
```

### マイク入力の初期化

ステレオの有無と送受信の判断は独立しています。
SDK がすでに持つ送信側の判断を使い、マイクを送信する場合だけ、既存の `setInitialMicrophoneMute` と `initializeInput` を呼びます。
AudioUnit の生成前の要求は生成後まで待機し、再生開始後の要求は worker で停止、入力接続、再初期化を経て、AudioUnit が開始済みだった場合だけ再開します。
完了通知はメインキューで一度だけ行い、終了で待機要求が取り消された場合はエラーを返します。
入力初期化前のミュート解除は拒否します。

`RTCAudioSession` は既存どおり共有インスタンスで、公開 `initializeInput` は ADM の識別子を受け取りません。
入力要求は利用する ADM を初期化してから行い、複数の ADM が同時に独立した入力要求を持つ使い方はできません。
入力を使わない再生では、アプリが再生用の category と options を設定します。
本パッチは stereo 設定から category や送受信の要否を決めません。

### 利用上の注意

- **AEC / AGC が使えなくなる**: ステレオ出力を有効化すると内部的に AudioUnit を `VoiceProcessingIO` から `RemoteIO` に切り替えるため、iOS 標準のハードウェア AEC / AGC は動作しなくなります。VoIP 用途で AEC / AGC が必須の場合はステレオ出力を有効化しないでください。
- **`pauseRecording` / `resumeRecording`**: ネイティブの `RTCAudioDeviceModule` は、ステレオ有効時も入力 bus の EnableIO を切り替えてマイクの入力 I/O を停止 / 再開します。切り替えは AudioUnit 全体の停止と再初期化を伴うため、再生が一時中断します。出力 bus の EnableIO は変更せず、再初期化に成功すると再生を再開します。失敗時はエラーを返します。マイクインジケーターの消灯と再点灯、ミュート中の stereo 再生は実機で確認してください
- **SDK のハードミュート制約**: Sora iOS SDK の公開 API `setAudioHardMute` がステレオ時のハードミュートを拒否する制約の解除は、SDK 側で対応する必要があります。ネイティブの初期ミュートは、既存の `setInitialMicrophoneMute` と `initializeInput` で指定できます
- **`initWithBypassVoiceProcessing:YES` は無視される**: `RTCAudioDeviceModule` の bypass フラグは `VoiceProcessingIO` の内部音声処理をバイパスするための設定です。ステレオ有効時は `RemoteIO` を使うため VP 由来の音声処理はもともと無く、bypass 指定は事実上意味を持ちません (エラーにはならず単に無視されます)。
- **mode 切替**: ステレオ有効時のみ `AVAudioSession` の mode が `AVAudioSessionModeVoiceChat` から `AVAudioSessionModeDefault` に一時差し替えされます (WebRTC セッション構成時のみ)。モノラルに戻せば mode も戻ります。
- **Bluetooth 制約 + A2DP category option**: HFP はモノラルまでしか出せません。A2DP ではステレオが出せます。`AVAudioSessionCategoryPlayAndRecord` を指定すると録音併用のため HFP が選ばれる場合があります。ステレオ出力を確実に狙うなら、アプリ側で category / options を A2DP を許容する構成に調整することを検討してください (本パッチは category の書き換えまでは踏み込みません)。
- **マイク入力と権限**: ステレオ再生自体はマイク入力を必要としません。RemoteIO も既存の `RTCAudioSession.initializeInput` が呼ばれるまで入力 I/O を無効にします。受信専用では呼び出さず、マイクを送信する場合だけ録音可能な category とマイク権限を用意して呼び出してください。stereo を理由に入力初期化を省略していた SDK は、依存更新と同時に既存の呼び出しを戻す必要があります。
- **呼び出しタイミングと初期化**: `setStereoPlayoutEnabled:` は `RTCPeerConnectionFactory` に `RTCAudioDeviceModule` を渡す前に呼んでください。設定値だけを保持し、ADM の初期化と設定の適用は factory の worker スレッドで行います。戻り値 `0` は設定の受け付け成功を示し、音声デバイスの初期化成功を保証するものではありません。factory への受け渡し後は設定変更を拒否します
- **設定値の取得と再初期化**: `stereoPlayoutEnabled` は受け付けた設定値を返し、初期化前と factory への受け渡し後も取得できます。実際の出力経路のチャンネル数を示すものではありません。ADM を `Terminate` して再初期化した場合も、最初に受け付けた設定を再適用します
- **実機検証**: シミュレータの Core Audio は挙動が実機と異なるため、ステレオ出力の確認は必ず実機で行ってください。

## 開発者向け

### 背景

- 標準の libwebrtc iOS ADM (`AudioDeviceIOS`) は `StereoPlayoutIsAvailable` / `SetStereoPlayout` / `StereoPlayout` が `Not implemented` のスタブ実装であり、実際に呼び出しても常にモノラルに潰される
- 出力経路の AudioUnit も `VoiceProcessingIO` + `mChannelsPerFrame = 1` 固定になっており、`OnGetPlayoutData` / `UpdateAudioDeviceBuffer` で `mNumberChannels == 1` を `RTC_DCHECK` している
- Opus デコーダは SDP fmtp `stereo=1` で 2ch を出せるため、ボトルネックは ADM から AudioUnit までの playout 経路である

### 変更点の概要

- `sdk/objc/native/src/audio/audio_unit_interface.h` を新規追加し、`AudioUnitInterface` abstract class を定義。`State { kInitRequired, kUninitialized, kInitialized, kStarted }` enum と `kBytesPerSample` 定数を interface 側に集約し、`Init` / `Initialize` / `InitializeInput` / `IsInputInitialized` / `Start` / `Stop` / `Uninitialize` / `SetMicrophoneMute` / `Render` / `GetState` を pure virtual として並べる
- `sdk/objc/native/src/audio/voice_processing_audio_unit.h` を更新。`class VoiceProcessingAudioUnit : public AudioUnitInterface` に継承を追加し、既存メソッドに `override` を付与、自前 State enum を削除。private セクションの protected 昇格や既存メソッドの virtual 後付けは行わない
- `VoiceProcessingAudioUnit` に直接接続されていた入力初期化を `AudioUnitInterface::InitializeInput` に移す。`RTCAudioSession` は従来の公開 API で要求を受け付け、`AudioDeviceIOS` の worker が入力の接続と AudioUnit の再初期化を行う。一時停止では入力状態を保持し、最終終了で待機要求を解除する
- `sdk/objc/native/src/audio/remote_io_audio_unit.h` / `.mm` を新規追加。`AudioUnitInterface` を直接実装した独立クラスとして `RemoteIOAudioUnit` を定義。`componentSubType = kAudioUnitSubType_RemoteIO`、生成時は出力バスを有効にし、入力バスと入力コールバックは `initializeInput` の要求後に接続する。`GetFormat(sample_rate, channels)` で playout / record 個別のチャンネル数を扱える。`AudioUnitInitialize` のリトライループも独立に持つ
- `sdk/objc/native/src/audio/audio_device_ios.h` の `audio_unit_` メンバ型を `std::unique_ptr<VoiceProcessingAudioUnit>` から `std::unique_ptr<AudioUnitInterface>` に変更
- `sdk/objc/native/src/audio/audio_device_ios.mm` 内の `VoiceProcessingAudioUnit::kInitialized` / `kUninitialized` / `kStarted` / `kInitRequired` / `kBytesPerSample` の参照をすべて `AudioUnitInterface::` に置換 (ios_sdk 専用の `ios_audio_pause_resume.patch` は本パッチ適用後に `AudioUnitInterface::` の参照で追加される)
- `AudioDeviceIOS::StereoPlayoutIsAvailable` / `SetStereoPlayout` / `StereoPlayout` を実装。`playout_parameters_.channels()` を単一の source of truth として参照し、`play_channels_` のような別メンバによる二重管理は作らない。3 関数に `RTC_DCHECK_RUN_ON(thread_)` を付与
- `AudioDeviceIOS::UpdateAudioDeviceBuffer` の `RTC_DCHECK_EQ(playout_parameters_.channels(), 1);` を削除。recording 側の DCHECK は残す
- `AudioDeviceIOS::OnGetPlayoutData` の `RTC_DCHECK_EQ(1, audio_buffer->mNumberChannels);` を `RTC_DCHECK_EQ(playout_parameters_.channels(), audio_buffer->mNumberChannels);` に置換。silence 出力時のバイト数計算と `fine_audio_buffer_->GetPlayoutData(...)` の要求サンプル数も `playout_parameters_.channels()` を掛けた値に修正
- `AudioDeviceIOS::CreateAudioUnit` で `playout_parameters_.channels() == 2` のとき `RemoteIOAudioUnit`、それ以外は既定の `VoiceProcessingAudioUnit` を生成する分岐を追加
- `AudioDeviceIOS::ConfigureAudioSession` / `ConfigureAudioSessionLocked` にステレオ有効時のみ `AVAudioSessionModeDefault` に一時差し替えするロジックを追加。復元は `@try/@finally` で保証する
- `sdk/objc/components/audio/RTCAudioDeviceModule.h` / `.mm` に `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を追加。setter は未初期化の ADM に設定値だけを渡し、getter は保存した設定値を返す。factory への受け渡しと設定変更を `@synchronized` で保護し、受け渡し後の設定変更を拒否する
- `AudioDeviceModuleIOS::SetStereoPlayout` は未初期化時に初期設定を保持する。通常の `Init()` が worker スレッドで `AudioDeviceIOS` を生成した後に設定を適用し、`AudioDeviceBuffer` のチャンネル数も揃える。これにより、アプリ側スレッドで `Thread::Current()` の `nullptr` を保存して音量変更通知時に参照する問題を防ぐ
- `sdk_unittests` に回帰テストを追加。WebRTC に登録されていないスレッドで設定し、実際の ADM の初期化が worker スレッドまで遅延されること、モノラル / ステレオの反映、受け渡し後の設定変更拒否、再初期化時の設定保持を検証する
- `sdk/BUILD.gn` の `audio_device` ターゲットに新規ファイル 3 本 (`audio_unit_interface.h`、`remote_io_audio_unit.h`、`remote_io_audio_unit.mm`) を追加

### 適用順序と登録先

- 本パッチは `ios` と `ios_sdk` の両方に登録される (raw `ios` ビルドにも本機能が含まれる)
- `run.py` の `PATCHES["ios"]` / `PATCHES["ios_sdk"]` では `ios_manual_audio_input.patch` より前に適用する
- 入力初期化の worker 化 (`AudioUnitInterface::InitializeInput` 化) と、`RTCAudioDeviceModule` の土台 (ファイル生成と `init` / `nativeAudioDeviceModule` / stereo API) を本パッチが持つ
- `ios_manual_audio_input.patch` は本パッチ適用後 (両ターゲット共通) に、公開 API 宣言 (`initializeInput:` / `setInitialMicrophoneMute:` / `setCategory:error:` / エラー定数) と既定 category (`Ambient`) および category 設定エラー抑止のみを追加する
- `ios_sdk` 専用の `ios_audio_track_sink.patch` / `ios_audio_pause_resume.patch` は末尾に配置する。`ios_audio_pause_resume.patch` は本パッチ適用後を前提に、`AudioUnitInterface::` の参照や `IsInputInitialized()` を使って `PauseRecording` / `ResumeRecording` / `ReinitAudioUnitForMicrophoneMute`、`RTCAudioDeviceModule` の録音操作 (factory への `bindToFactory:` と worker 実行) を追加する

### 入力初期化の回帰テスト

`RTCManualAudioInputTests` は実際の `AudioDeviceIOS` と AudioUnit を使い、入力 I/O、初期ミュート、手動音声の停止と再開、入力要求の取り消し、再接続を確認します。
入力を使うテストは、検証用アプリのマイク権限を許可した状態で実行します。
受信専用の `testStereoPlaybackWithoutInput` は、権限が未決定の状態と拒否された状態でも個別に実行します。

worker 操作の待機はメインの run loop を動かし、完了前に終了処理へ進まないようにしています。
実行時は XCTest のテストタイムアウトを有効にしてください。
`xcodebuild` では `-test-timeouts-enabled YES -default-test-execution-time-allowance 60 -maximum-test-execution-time-allowance 60` を指定します。
Core Audio が応答しない場合は、同じプロセスで後続処理を続けず、XCTest に失敗と診断情報を記録させます。
このテストは実際のマイク音声の送信、左右の再生音、Bluetooth の経路変更を検証するものではなく、それらは実機で別途確認します。

### preferredOutputNumberOfChannels は 1 のままとする設計判断

- `RTCAudioSessionConfiguration` の `kRTCAudioSessionPreferredNumberOfChannels` は 1 のまま据え置く
- 実際の playout チャンネル数は `RemoteIOAudioUnit` の stream format 側で決まるため、hint 用の `preferred*` を 2 に上げる必要はない
- `AVAudioSession.preferredOutputNumberOfChannels` は要求であって保証ではないため、シングルトンの hint を触らずに RemoteIO 側 format で決着させたほうが影響範囲が閉じる

### mode の一時差し替えは限定的に許容する設計判断

- 上記 `preferredOutputNumberOfChannels` とは別扱い。`AVAudioSession` の mode だけは `ConfigureAudioSession` / `ConfigureAudioSessionLocked` の内側でステレオ有効時のみ `AVAudioSessionModeDefault` に一時差し替えする
- 理由: `AVAudioSessionModeVoiceChat` のままだと OS 側で 1ch にクランプされるため、mode を Default に切り替えないと RemoteIO の 2ch format が実効的に活きない
- 復元は `@try/@finally` で保証。差し替えは `configureWebRTCSession:` の呼び出し窓の中に閉じ込め、外部から観測される時間を最小化する
- シングルトンを書き換える点は preferred* と同じ懸念があるが、mode 差し替えなしにはステレオが機能しないため許容せざるを得ない (代替案として ADM 固有の `RTCAudioSessionConfiguration` インスタンスを別途持って `configureWebRTCSession:` に渡す方式もあるが、`RTCAudioSession` の public API がシングルトン前提なので影響範囲が大きくなる)
