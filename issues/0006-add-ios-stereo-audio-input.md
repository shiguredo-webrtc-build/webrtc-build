# iOS のステレオ音声入力に対応する

- Created: 2026-09-03
- Completed:
- Branch: feature/add-ios-stereo-audio-input
- Polished: 2026-09-03
- Updated: 2026-09-10

## 目的

libwebrtc の iOS 向け Audio Device Module (ADM) はステレオ recording が未実装のため、ステレオマイク等からのステレオ入力を送れない。本リポジトリに iOS 向けパッチを追加し、ステレオ入力（recording）を可能にする。

対象は iOS のネイティブマイク入力とする。macOS の入力対応は本 issue に含めない。
ステレオ出力 (playout) は `issues/closed/0005-add-ios-stereo-audio-output.md` で実装済みであり、本 issue はその AudioUnit 共通基盤を前提に録音側を拡張する。

## 現状

### upstream の iOS ADM はステレオ recording 未実装

確認対象は `VERSION` が指定する libwebrtc `154.8037.1`、upstream コミット `c2b761bb73f0b2ced096274abb415f6c7559a28b` と現在のパッチ群である。
`sdk/objc/native/src/audio/audio_device_ios.mm` の `AudioDeviceIOS` では、現在も次の通りステレオ recording API がスタブになっている。

- `StereoRecordingIsAvailable` は常に `available = false`
- `SetStereoRecording` は `"Not implemented"` で `-1` を返す
- `StereoRecording` は常に `enabled = false`

`sdk/objc/native/src/audio/audio_device_module_ios.mm` の `AudioDeviceModuleIOS::SetStereoRecording` は無条件で失敗を返す（下位の `AudioDeviceIOS` を呼ばない）。

`media/engine/adm_helpers.cc` の `adm_helpers::Init` は `StereoRecordingIsAvailable` の結果をそのまま `SetStereoRecording` に渡す。現在の iOS ADM では `false` を渡しても設定は失敗し、録音パラメーターは既定のモノラルのままとなる。

### 録音パラメーターとバッファは 1 ch 前提

入力経路がモノラル前提になっている。

- `sdk/objc/components/audio/RTCAudioSessionConfiguration.m` の `kRTCAudioSessionPreferredNumberOfChannels` は `1` で、入力チャンネル数の既定値も `1`
- `sdk/objc/native/src/audio/voice_processing_audio_unit.mm` の `VoiceProcessingAudioUnit::GetFormat` は `mChannelsPerFrame` に `kRTCAudioSessionPreferredNumberOfChannels` (= 1) を設定し、`RTC_DCHECK_EQ(1, kRTCAudioSessionPreferredNumberOfChannels)` を維持している
- `AudioDeviceIOS::UpdateAudioDeviceBuffer` の recording `channels() == 1` の `RTC_DCHECK` は、現在のステレオ出力パッチでも残っている
- `AudioDeviceIOS::OnDeliverRecordedData` は `record_audio_buffer_.SetSize(num_frames)` で録音バッファを確保する。チャンネル数を掛けておらず、2 ch 分のサンプルを格納して `FineAudioBuffer` へ渡す対応が必要
- 現行の `RemoteIOAudioUnit::Initialize` は入力に `GetFormat(sample_rate, rec_channels_)`、出力に `GetFormat(sample_rate, play_channels_)` を使用し、ASBD は入出力別のチャンネル数を扱える。ただし、`AudioDeviceIOS::CreateAudioUnit` が RemoteIO を選ぶ条件は `playout_parameters_.channels() == 2` のみで、録音パラメーターは既定の 1 ch のままである

入出力ともステレオ未指定の場合は、既定の `AVAudioSessionModeVoiceChat` と `kAudioUnitSubType_VoiceProcessingIO` を使う。既存のステレオ出力を有効にした場合は `AVAudioSessionModeDefault` と RemoteIO を使い、入力はモノラルのままである。

macOS の `AudioDeviceMac` は `_mixerManager` 経由でステレオ recording 可だが、iOS には相当機構がなく流用できない。

### Opus エンコード層は対応済み

`modules/audio_coding/codecs/opus/audio_encoder_opus.cc` の `GetChannelCount` は SDP fmtp の `stereo=1` で `2` を返す。ボトルネックは ADM から AudioUnit までの recording 経路である。マイクから 2 ch を取れなければ、エンコーダ側の `stereo=1` だけではステレオ送信にならない。

### 本リポジトリの現状

- 更新時点のブランチは `feature/m154.8037`、ビルド版は `m154.8037.1.1`。m150 系で導入されたステレオ出力と後続修正は現在のブランチにも取り込まれている
- `patches/ios_stereo_audio_output.patch` に `AudioUnitInterface`、独立した `VoiceProcessingAudioUnit` / `RemoteIOAudioUnit`、ステレオ出力の切り替えが実装済み。導入コミットは `ff4271c`
- `ios_audio_pause_resume.patch` が公開する `RTCAudioDeviceModule` は `initWithBypassVoiceProcessing:`、`pauseRecording` / `resumeRecording` を持ち、ステレオ出力パッチが `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を追加している。stereo recording の制御 API はまだ無い
- 出力設定は factory に ADM を渡す前に値だけを保持し、worker スレッドでの ADM 初期化時に適用する。受け渡し後の変更は拒否し、`AudioDeviceModuleIOS::Init` は `stereo_playout_enabled_on_init_` を再初期化時にも再適用する。これらは `418ce63` で実装済み
- `RTCAudioSession.initializeInput` の要求がある場合だけ、`AudioDeviceIOS` の worker から `AudioUnitInterface::InitializeInput` で入力を接続する。RemoteIO の入力初期化、初期ミュート、終了時の入力要求解除は `cd6ab6b` で実装済み
- `RemoteIOAudioUnit::SetMicrophoneMute` は入力 bus の EnableIO を切り替える。`pauseRecording` / `resumeRecording` の worker での同期実行と初期ミュート解除は `cd6bb70` で修正済み。ステレオ設定自体は入力初期化の要求を兼ねない
- `run.py` の `PATCHES["ios_sdk"]` には `ios_manual_audio_input.patch`、`ios_audio_pause_resume.patch`、`ios_stereo_audio_output.patch` の順に登録されている。raw `ios` には後者 2 つがなく、現在の RemoteIO 共通基盤は `ios_sdk` のみに含まれる
- 音声制御 API の統合設計は open の `0010-change-rtc-audio-device-module-api-design` で未決定。0006 の実装前に、個別メソッドの追加か設定オブジェクトへの集約かを確定させる必要がある
- 関連する 0011 から 0016 は現在のブランチでは open。0012 の設定再適用、0014 の入力初期化、0016 のハードミュートは上記のとおり実装が入っている。0011 の失敗伝播は `InitPlayOrRecord` の AudioUnit 初期化結果の確認が追加済みだが、AudioSession 設定の最終判定を `return YES` にする処理は残る。0013 の共有 mode の一時変更も残る。0015 はカスタム `RTCAudioDevice` の `inputData` 経路を扱い、本 issue のネイティブマイク入力とは別である

### 試作で判明していること

過去の試作では、宣言 API だけを直してもステレオ入力にならなかった。実際に動かすには、OS の AudioUnit へ渡るデータ経路まで改修が必要だった。
起票時の記録では試作の WIP PR は未マージのまま閉じられたとされている。今回の同期では PR の状態を再確認していない。

到達した試作の方針は次の通り。

- `VoiceProcessingIO` ではステレオが成立しにくいため、`RemoteIO` へ切り替える
- `audio_device_buffer_` の recording チャンネル数、録音パス、`GetFormat` などモノラル前提の保護を外す
- 過去の記録では実機でステレオ送信を確認できたとされている（端末の向きにより内蔵マイクがステレオになる条件がある）。これは現行 m154 系での検証結果ではなく、現在の実装による実機確認は完了条件として残る

一方で次の副作用・未解決がある。

- ハードウェアの AEC / AGC（VPIO 由来）が使えなくなる
- デフォルトの `AVAudioSessionModeVoiceChat` を一律 `Default` に変えると、通常の VoIP 挙動に悪影響がある。現行の出力側と同様、ステレオ利用時だけ切り替える必要がある
- 内蔵マイクの L/R 役割設定、ステレオマイクの挿抜などデバイスハンドリングが未整備
- モノラルマイクしかない場合のフォールバックが未整理

## 過去試作パッチの既知バグと未完事項

過去試作は `origin/feature/ios-stereo-audio` の `patches/ios_stereo_audio.patch` にあり、確認したコミットは `8ebe2aebad4fcef1c60e1a7b587637fb1b7ed4e8`、対象は m138.7204 系である。現在のパッチ群には含まれない。録音固有の処理を参考にする場合も、現在の独立した RemoteIO 実装と入力初期化経路を前提とする。

### 現行の共通基盤で対応済みの項目と、試作を参照する場合の注意

- 現行の `RemoteIOAudioUnit::Init` は意図的に入力を無効にし、`InitializeInput` が入力 bus の EnableIO と録音コールバックを設定する。`Init` に入力の有効化を追加する必要はない。旧試作にも `RTCAudioSession::finishInitializeInput` から入力を接続する経路があり、`Init` 単体から録音不能とは断定できない
- 現行の `RemoteIOAudioUnit` はデストラクタを定義済みで、`DisposeAudioUnit()` により AudioUnit を解放する。試作にあった定義漏れは現在の残存バグではない
- 現行の `RemoteIOAudioUnit::Initialize` は入力と出力のチャンネル数を別々に渡す実装であり、試作の常時 2 ch 固定の形式設定を流用しない
- 試作の `AudioDeviceModuleIOS::SetStereoRecording` は失敗時に `kStereoPlayoutFailed` を報告している。参考にする場合は `kStereoRecordingFailed` を使う。該当クラスは `AudioDeviceIOS` ではなく `AudioDeviceModuleIOS` である
- 試作では `AudioDeviceIOS::rec_channels_` と `record_parameters_.channels()` が同期していない。現行基盤は `record_parameters_.channels()` を RemoteIO のコンストラクタへ渡すため、この関係を前提に設定値、録音パラメーター、AudioDeviceBuffer、AudioUnit のチャンネル数を一致させる

### 品質・未完事項

- 内蔵マイクのステレオ向き設定が `AVAudioStereoOrientationLandscapeRight` 決め打ちになっており、端末の姿勢や利用側からの制御に追従できない
- `STEREO_LOG:` の暫定デバッグログ、空行追加だけの `RTCAudioSessionConfiguration.m` の hunk、タブとスペースの混在は旧試作に残っている。これらを新規パッチへ持ち込まない
- 対象ベースが m138 系のため、試作を参考にする場合も現在の m154 系のソースとパッチ適用順に合わせる必要がある
- RemoteIO 使用時にハードウェア AEC / AGC が使えない点は `patches/ios_stereo_audio_output.md` に記載済み。入力機能についても同じ制約を解説に反映する

## 設計方針

1. **パッチで iOS ADM のステレオ recording 経路を実装する**
   - 対象の中心は `AudioDeviceIOS` / `AudioDeviceModuleIOS` / AudioUnit 実装の recording 側
   - 宣言 API だけでなく、バッファ・コールバック・ASBD (`GetFormat`) まで 2 ch を通す
   - 実装済みの `RemoteIOAudioUnit` を利用し、現在は出力設定だけに依存する `CreateAudioUnit` と AudioSession の mode 切り替えを、入力のみステレオの場合にも対応させる
   - 既存の `RTCAudioSession.initializeInput` による明示的な入力接続、初期ミュート、`pauseRecording` / `resumeRecording`、終了時の入力要求解除を維持する
2. **既定挙動はモノラルのまま維持する**
   - 入出力ともステレオ未指定の場合は `AVAudioSessionModeVoiceChat` と VPIO を維持する。既存のステレオ出力指定時の RemoteIO とモノラル入力も維持し、ステレオ入力を明示的に有効化した場合だけ録音を 2 ch にする
   - ステレオを常時有効にするパッチにしない
3. **公開 API は最小限**
   - SDK または利用側がステレオ入力を有効化できる経路を用意する
   - API の形式は 0010 で確定させる。既存の出力設定と同様、設定の受け付けと worker スレッドでの適用を分け、ADM の再初期化でも指定した設定を維持する
   - SDP の `stereo=1` やアプリ側 `AVAudioSession` 設定は Sora iOS SDK / アプリ側の責務とし、本 issue の完了条件に含めない
4. **出力側とは分離する**
   - playout の 2 ch 対応と `AudioUnitInterface` / `RemoteIOAudioUnit` は 0005 で実装済みであり、本 issue は recording 固有の経路と API に集中する
   - AudioSession の共有設定を一時変更する処理の整理は 0013 で扱う。現在の `ConfigureAudioSession` / `ConfigureAudioSessionLocked` との整合を確認する
5. **デバイスハンドリングは段階的に扱う**
   - まずは固定デバイスでのステレオ録音を成立させる
   - 内蔵マイクの L/R・挿抜・モノラルデバイス時のフォールバックは、完了条件を満たしたうえで残課題として切り出せるなら別 issue にする

## 完了条件

- iOS 向けパッチが `patches/` に追加され、`run.py` の `PATCHES` dict に登録されていること。core 側（`sdk/objc/native/src/audio/` 配下の `audio_device_ios.mm` 等）を触る場合は `ios` と `ios_sdk` の両方に、SDK 拡張 API のみを追加する場合は `ios_sdk` のみに登録する
  - 現行の RemoteIO 共通基盤と `RTCAudioDeviceModule` は `ios_sdk` 専用のパッチに含まれる。`ios_sdk` ではこれらの適用後に入力側の変更を適用する。raw `ios` にも core の変更を登録するには、共通基盤と SDK 公開 API の分離など、依存するパッチの構成と適用順を整理する必要がある。入力パッチを両方へ登録するだけではこの条件を満たせない
- ステレオ入力有効時に `StereoRecordingIsAvailable` / `SetStereoRecording` が成功し、AudioUnit の recording 経路が 2 ch で動作すること
- SDK または利用側から iOS のステレオ入力を有効化できる経路（`RTCAudioDeviceModule` 相当の Objective-C API 拡張、または他の内部設定手段）が `ios_sdk` ビルド側から呼び出せること
- 既定（入出力ともステレオ未指定）では従来どおりモノラル（VoiceChat / VPIO）の挙動を維持すること。既存のステレオ出力とモノラル入力の組み合わせも維持すること
- 実機でステレオ録音（送信）が確認できること
- ステレオ入力有効時に AEC / AGC が使えないこと、モノラルマイク時の挙動など、利用上の注意がパッチ解説または関連ドキュメントに残っていること
- CHANGES.md に追記があること

## 変更履歴案

- [ADD] iOS のステレオ音声入力に対応する
