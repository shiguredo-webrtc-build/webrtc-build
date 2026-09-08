# iOS のステレオ音声入力に対応する

- Created: 2026-09-03
- Completed:
- Branch: feature/add-ios-stereo-audio-input
- Polished: 2026-09-03

## 目的

libwebrtc の iOS 向け Audio Device Module (ADM) はステレオ recording が未実装のため、ステレオマイク等からのステレオ入力を送れない。本リポジトリに iOS 向けパッチを追加し、ステレオ入力（recording）を可能にする。

ステレオ出力（playout）は `0005-add-ios-stereo-audio-output` で別途扱う。

## 現状

### upstream の iOS ADM はステレオ recording 未実装

`AudioDeviceIOS` では次の通りステレオ recording API がスタブになっている。

- `StereoRecordingIsAvailable` は常に `available = false`
- `SetStereoRecording` は `"Not implemented"` で `-1` を返す
- `StereoRecording` は常に `enabled = false`

`AudioDeviceModuleIOS::SetStereoRecording` は無条件で失敗を返す（下位の `AudioDeviceIOS` を呼ばない）。

起動時の `adm_helpers::Init` は `StereoRecordingIsAvailable` の結果をそのまま `SetStereoRecording` に渡すため、iOS では常にモノラル recording で初期化される。

### AudioUnit / AVAudioSession も 1ch 固定

入力経路がモノラル前提になっている。

- `RTCAudioSessionConfiguration` の `kRTCAudioSessionPreferredNumberOfChannels` が `1`
- `VoiceProcessingAudioUnit::GetFormat` が `mChannelsPerFrame` に `kRTCAudioSessionPreferredNumberOfChannels`（= 1）を設定し、直前の `RTC_DCHECK_EQ(1, kRTCAudioSessionPreferredNumberOfChannels)` で 1 に固定されている
- `AudioDeviceIOS::UpdateAudioDeviceBuffer` が recording `channels() == 1` を `RTC_DCHECK`
- 録音コールバック側もモノラル前提のバッファ扱いになっている

既定は `AVAudioSessionModeVoiceChat` と `kAudioUnitSubType_VoiceProcessingIO`。VoIP 向けで、ステレオ収録向きではない。

macOS の `AudioDeviceMac` は `_mixerManager` 経由でステレオ recording 可だが、iOS には相当機構がなく流用できない。

### Opus エンコード層は対応済み

Opus エンコーダは SDP fmtp の `stereo=1` で 2ch にできる。ボトルネックは ADM から AudioUnit までの recording 経路である。マイクから 2ch を取れなければ、エンコーダ側の `stereo=1` だけではステレオ送信にならない。

### 本リポジトリの現状

- 対応ブランチは `feature/m150.7871`（m150.7871 系）
- `patches/` に iOS ステレオ向けパッチは存在しない
- `ios_audio_pause_resume.patch` が公開する `RTCAudioDeviceModule` は `pauseRecording` / `resumeRecording` のみで、stereo recording 制御 API は無い
- 過去に試作パッチと WIP PR があったが、未マージのまま閉じられている

### 試作で判明していること

過去の試作では、宣言 API だけを直してもステレオ入力にならなかった。実際に動かすには、OS の AudioUnit へ渡るデータ経路まで改修が必要だった。

到達した試作の方針は次の通り。

- `VoiceProcessingIO` ではステレオが成立しにくいため、`RemoteIO` へ切り替える
- `audio_device_buffer_` の recording チャンネル数、録音パス、`GetFormat` などモノラル前提の保護を外す
- 実機でステレオ送信を確認できた（端末の向きにより内蔵マイクがステレオになる条件がある）

一方で次の副作用・未解決がある。

- ハードウェアの AEC / AGC（VPIO 由来）が使えなくなる
- デフォルトの `AVAudioSessionModeVoiceChat` を一律 `Default` に変えると、通常の VoIP 挙動に悪影響がある。ステレオ利用時だけ切り替える必要がある（MUST）
- 内蔵マイクの L/R 役割設定、ステレオマイクの挿抜などデバイスハンドリングが未整備
- モノラルマイクしかない場合のフォールバックが未整理

## 過去試作パッチの既知バグと未完事項

過去試作は `feature/ios-stereo-audio` ブランチの `patches/ios_stereo_audio.patch` にある。新規パッチが試作を再利用する場合、少なくとも次は必ず対処すること。

### 致命的・重要な残存バグ（recording 経路）

- `RemoteIOAudioUnit::Init` に入力側の配線が欠落している。upstream の `VoiceProcessingAudioUnit::Init` に相当する入力 bus の `kAudioOutputUnitProperty_EnableIO` 有効化と、`kAudioOutputUnitProperty_SetInputCallback` による `OnDeliverRecordedData` の登録を追加しないと、ステレオ以前に録音自体が成立しない
- `AudioDeviceIOS::SetStereoRecording` の失敗時エラー報告が `kStereoPlayoutFailed` になっている。`kStereoRecordingFailed` に修正する
- `RemoteIOAudioUnit` のデストラクタがヘッダ宣言のみで `.mm` に定義が無く、リンクエラーになり得る
- `RemoteIOAudioUnit::Initialize` の内部で `GetFormat(sample_rate, 2)` を 2 箇所で常に 2ch 固定で呼んでおり、`rec_channels_` に連動していない。`GetFormat` の引数を動的に渡す
- チャンネル数を `rec_channels_` と `record_parameters_.channels()` の二系統で管理しているが同期していない。`AudioDeviceIOS::SetStereoRecording` は `rec_channels_` しか更新せず、`AudioDeviceIOS::CreateAudioUnit` は `record_parameters_.channels() == 2` で RemoteIO を選ぶため、設定経路によって AudioUnit 種別と実チャンネル数が食い違う。単一の source of truth に統一する

### 品質・未完事項

- 内蔵マイクのステレオ向き設定が `AVAudioStereoOrientationLandscapeRight` 決め打ちになっており、端末の姿勢や利用側からの制御に追従できない
- `STEREO_LOG:` の暫定デバッグログが本番パッチに残っているため削除する
- `RTCAudioSessionConfiguration.m` の hunk が空行追加のみで意味を持たない
- タブとスペースのインデントが混在している
- 対象ベースが m138 系のため、`feature/m150.7871` への再ベースが必須
- VPIO から RemoteIO へ切り替える結果として AEC / AGC が失われる点を、パッチのヘッダコメントまたは関連ドキュメントに必ず明記する

## 設計方針

1. **パッチで iOS ADM のステレオ recording 経路を実装する**
   - 対象の中心は `AudioDeviceIOS` / `AudioDeviceModuleIOS` / AudioUnit 実装の recording 側
   - 宣言 API だけでなく、バッファ・コールバック・ASBD（`GetFormat`）まで 2ch を通す
   - 過去試作を踏まえ、ステレオ時は `RemoteIO` への切替を軸に検討する
2. **既定挙動はモノラルのまま維持する**
   - `AVAudioSessionModeVoiceChat` と VPIO を既定とし、ステレオ入力有効時のみ mode / AudioUnit / チャンネル数を切り替える
   - ステレオを常時有効にするパッチにしない
3. **公開 API は最小限**
   - SDK または利用側がステレオ入力を有効化できる経路を用意する
   - SDP の `stereo=1` やアプリ側 `AVAudioSession` 設定は Sora iOS SDK / アプリ側の責務とし、本 issue の完了条件に含めない
4. **出力側とは分離する**
   - playout 側の改修は `0005-add-ios-stereo-audio-output` の範囲とする
   - AudioUnit 切替など共通基盤が 0005 で入る場合はそれを前提にし、本 issue は recording 固有の経路と API に集中する
5. **デバイスハンドリングは段階的に扱う**
   - まずは固定デバイスでのステレオ録音を成立させる
   - 内蔵マイクの L/R・挿抜・モノラルデバイス時のフォールバックは、完了条件を満たしたうえで残課題として切り出せるなら別 issue にする

## 完了条件

- iOS 向けパッチが `patches/` に追加され、`run.py` の `PATCHES` dict に登録されていること。core 側（`sdk/objc/native/src/audio/` 配下の `audio_device_ios.mm` 等）を触る場合は `ios` と `ios_sdk` の両方に、SDK 拡張 API のみを追加する場合は `ios_sdk` のみに登録する
- ステレオ入力有効時に `StereoRecordingIsAvailable` / `SetStereoRecording` が成功し、AudioUnit の recording 経路が 2ch で動作すること
- SDK または利用側から iOS のステレオ入力を有効化できる経路（`RTCAudioDeviceModule` 相当の Objective-C API 拡張、または他の内部設定手段）が `ios_sdk` ビルド側から呼び出せること
- 既定（ステレオ未指定）では従来どおりモノラル（VoiceChat / VPIO）の挙動を維持すること
- 実機でステレオ録音（送信）が確認できること
- ステレオ入力有効時に AEC / AGC が使えないこと、モノラルマイク時の挙動など、利用上の注意がパッチ解説または関連ドキュメントに残っていること
- CHANGES.md に追記があること

## 変更履歴案

- [ADD] iOS のステレオ音声入力に対応する
