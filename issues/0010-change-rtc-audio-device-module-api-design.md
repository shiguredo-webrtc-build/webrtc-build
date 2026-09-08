# RTCAudioDeviceModule の音声制御 API の統合設計を決める

- Created: 2026-09-03
- Completed:
- Branch: feature/change-rtc-audio-device-module-api-design
- Polished:

## 目的

0005 で `RTCAudioDeviceModule` に `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を追加した。0006 (`0006-add-ios-stereo-audio-input`) で `setStereoRecordingEnabled:` / `stereoRecordingEnabled` の追加が想定されている。この形で個別メソッドを増やし続けるか、`RTCAudioDeviceModuleConfiguration` 相当の設定オブジェクトに集約するかを 0006 実装前に判断し、必要に応じて 0005 の既存 API も再構成する。

## 現状

- 0005 で追加された API (`sdk/objc/components/audio/RTCAudioDeviceModule.h` に inject)
  - `- (NSInteger)setStereoPlayoutEnabled:(BOOL)enabled;`
  - `- (BOOL)stereoPlayoutEnabled;`
- 0006 が追加する予定の API
  - `- (NSInteger)setStereoRecordingEnabled:(BOOL)enabled;`
  - `- (BOOL)stereoRecordingEnabled;`
- 既存の `RTCAudioDeviceModule` 上の音声制御 API (`ios_audio_pause_resume.patch` 由来)
  - `- (NSInteger)pauseRecording;`
  - `- (NSInteger)resumeRecording;`
  - `- (instancetype)initWithBypassVoiceProcessing:(BOOL)enabled;`
- 音声関連の設定は他にも AVAudioSession の mode / category / preferredOutputNumberOfChannels 等があり、SDK 利用側からの制御ニーズが増えると `RTCAudioDeviceModule` が個別メソッドで肥大化する可能性がある

## 設計方針

以下 3 択で判断し、0006 実装前に方針を確定させる。

- **選択肢 A: 個別メソッドを増やし続ける (現状の延長)**
  - 0006 で `setStereoRecordingEnabled:` / `stereoRecordingEnabled` を追加
  - シンプルで既存パターンと一貫
  - 追加が増えるほど `RTCAudioDeviceModule` が肥大化する
- **選択肢 B: 設定オブジェクトに集約する**
  - `RTCAudioDeviceModuleConfiguration` を新設し `stereoPlayoutEnabled` / `stereoRecordingEnabled` / `bypassVoiceProcessing` 等を持たせる
  - `RTCAudioDeviceModule` の init または setter で config を受け取る
  - 拡張しやすいが、既存の `setStereoPlayoutEnabled:` を廃止するなら 0005 の API が後方互換のない変更になる
- **選択肢 C: init 引数として設定オブジェクトを渡す**
  - `- (instancetype)initWithConfiguration:(RTCAudioDeviceModuleConfiguration *)configuration;` を新設
  - 生成時に一括で設定を確定できる (ライフサイクル制約を型で表現できる)
  - `pauseRecording` / `resumeRecording` のような runtime 制御 API は残す必要がある

判断時に考慮すること。

- 既存 `pauseRecording` / `resumeRecording` は runtime 制御なので初期化時の設定オブジェクトに含めるべきではない (振る舞いが異なる)
- 選択肢 B / C を採る場合、既存 `setStereoPlayoutEnabled:` を残す (後方互換) か廃止する (API 整理) かの判断も必要
- Sora iOS SDK 側からどのように呼ばれるかの想定利用パターン

## 完了条件

- 選択肢 A / B / C のいずれかを採用し、その根拠が本 issue の「## 解決方法」に記録されている
- 0006 の実装がその方針で進められる状態になっている (0006 の `Branch:` 着手前に本 issue が closed か、方針が確定していること)
- 選択肢 B / C を採る場合は `RTCAudioDeviceModuleConfiguration` 相当のクラスが実装されている
- 選択肢 B / C を採り既存 `setStereoPlayoutEnabled:` を廃止する場合は、0005 で追加した API が新方針に沿った形に置換されている
- 選択肢 A を採る場合は本 issue はコード変更なしで closed してよい
- 決定に応じて必要なら CHANGES.md に追記される

## 変更履歴案

- 選択肢 A: なし (変更なし)
- 選択肢 B / C: `[CHANGE]` または `[ADD]` を採用する方針次第で選択
