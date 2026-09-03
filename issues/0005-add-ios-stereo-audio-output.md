# iOS のステレオ音声出力に対応する

- Created: 2026-09-03
- Completed: 2026-09-03
- Branch: feature/add-ios-stereo-audio-output
- Polished: 2026-09-03

## 目的

libwebrtc の iOS 向け Audio Device Module (ADM) はステレオ playout が未実装のため、ステレオ音声をステレオのまま再生できない。本リポジトリに iOS 向けパッチを追加し、ステレオ出力（playout）を可能にする。

ステレオ入力（recording）は `0006-add-ios-stereo-audio-input` で別途扱う。

## 現状

### upstream の iOS ADM はステレオ playout 未実装

`AudioDeviceIOS` では次の通りステレオ playout API がスタブになっている。

- `StereoPlayoutIsAvailable` は常に `available = false`
- `SetStereoPlayout` は `"Not implemented"` で `-1` を返す
- `StereoPlayout` は常に `enabled = false`

`AudioDeviceModuleIOS::SetStereoPlayout` は下位が成功すれば `audio_device_buffer_` の playout チャンネルを 2 にする実装だが、`AudioDeviceIOS::SetStereoPlayout` が常に失敗するため到達しない。

起動時の `adm_helpers::Init` は `StereoPlayoutIsAvailable` の結果をそのまま `SetStereoPlayout` に渡すため、iOS では常にモノラル playout で初期化される。

### AudioUnit / AVAudioSession も 1ch 固定

出力経路がモノラル前提になっている。

- `RTCAudioSessionConfiguration` の `kRTCAudioSessionPreferredNumberOfChannels` が `1`（コメントに stereo 対応の TODO あり）
- `VoiceProcessingAudioUnit::GetFormat` が `mChannelsPerFrame` に `kRTCAudioSessionPreferredNumberOfChannels`（= 1）を設定し、直前の `RTC_DCHECK_EQ(1, kRTCAudioSessionPreferredNumberOfChannels)` で 1 に固定されている
- `AudioDeviceIOS::UpdateAudioDeviceBuffer` が playout `channels() == 1` を `RTC_DCHECK`
- `AudioDeviceIOS::OnGetPlayoutData` が `mNumberChannels == 1` を `RTC_DCHECK`

既定は `AVAudioSessionModeVoiceChat` と `kAudioUnitSubType_VoiceProcessingIO`。VoIP 向けで、ステレオ再生向きではない。

macOS の `AudioDeviceMac` は `_mixerManager` 経由でステレオ playout 可だが、iOS には相当機構がなく流用できない。

### Opus デコード層は対応済み

Opus デコーダは SDP fmtp の `stereo=1` で 2ch にできる。ボトルネックは ADM から AudioUnit までの playout 経路である。デコードまではステレオになり得ても、再生デバイスへ出す段でモノラルに潰される。

### 本リポジトリの現状

- 対応ブランチは `feature/m150.7871`（m150.7871 系）
- `patches/` に iOS ステレオ向けパッチは存在しない
- `ios_audio_pause_resume.patch` が公開する `RTCAudioDeviceModule` は `pauseRecording` / `resumeRecording` のみで、stereo playout 制御 API は無い
- 過去に試作パッチと WIP PR があったが、未マージのまま閉じられている

### 試作で判明していること

過去の試作では、宣言 API（`StereoPlayoutIsAvailable` 等）だけを直してもステレオ再生にならなかった。実際に動かすには、OS の AudioUnit へ渡るデータ経路まで改修が必要だった。

到達した試作の方針は次の通り。

- `VoiceProcessingIO` ではステレオが成立しにくいため、`RemoteIO` へ切り替える
- `audio_device_buffer_` の playout チャンネル数、`OnGetPlayoutData`、`GetFormat` などモノラル前提の保護を外す
- 実機でステレオ再生を確認できた

一方で次の副作用・未解決がある。

- ハードウェアの AEC / AGC（VPIO 由来）が使えなくなる
- デフォルトの `AVAudioSessionModeVoiceChat` を一律 `Default` に変えると、通常の VoIP 挙動（音量など）に悪影響がある。ステレオ利用時だけ切り替える必要がある（MUST）
- ステレオイヤホンの挿抜などデバイスハンドリングが未整備
- Bluetooth は HFP だとモノラル、A2DP ならステレオ可。カテゴリオプションの扱いは影響範囲の整理とドキュメントが必要

## 過去試作パッチの既知バグと未完事項

過去試作は `feature/ios-stereo-audio` ブランチの `patches/ios_stereo_audio.patch` にある。新規パッチが試作を再利用する場合、少なくとも次は必ず対処すること。

### 致命的・重要な残存バグ（playout 経路）

- `AudioDeviceIOS::StereoPlayoutIsAvailable` が `record_parameters_.channels()` を参照している。`playout_parameters_` を参照すべきコピペミスで、playout 可否を recording 側の状態で判定してしまう
- `AudioDeviceIOS::OnGetPlayoutData` に `mNumberChannels == 1` の `RTC_DCHECK` が残ったままで、ステレオ playout 時に Debug ビルドが即死する。`play_channels_` と比較する形へ差し替える
- `RemoteIOAudioUnit` のデストラクタがヘッダ宣言のみで `.mm` に定義が無く、リンクエラーになり得る
- `RemoteIOAudioUnit::Initialize` の内部で `GetFormat(sample_rate, 2)` を 2 箇所で常に 2ch 固定で呼んでおり、`play_channels_` に連動していない。`GetFormat` の引数を動的に渡す
- チャンネル数を `play_channels_` と `playout_parameters_.channels()` の二系統で管理しているが同期していない。`AudioDeviceIOS::SetStereoPlayout` は `play_channels_` しか更新せず、`AudioDeviceIOS::CreateAudioUnit` は `playout_parameters_.channels() == 2` で RemoteIO を選ぶため、設定経路によって AudioUnit 種別と実チャンネル数が食い違う。単一の source of truth に統一する

### 品質・未完事項

- `STEREO_LOG:` の暫定デバッグログが本番パッチに残っているため削除する
- `RTCAudioSessionConfiguration.m` の hunk が空行追加のみで意味を持たない
- タブとスペースのインデントが混在している
- 対象ベースが m138 系のため、`feature/m150.7871` への再ベースが必須
- VPIO から RemoteIO へ切り替える結果として AEC / AGC が失われる点を、パッチのヘッダコメントまたは関連ドキュメントに必ず明記する
- 送受信共通で単一の RemoteIO を使う構成にする場合は、`0006-add-ios-stereo-audio-input` 側で扱う入力 bus の配線（`kAudioOutputUnitProperty_EnableIO` と `SetInputCallback`）を欠落させないよう整合を取ること

## 設計方針

1. **パッチで iOS ADM のステレオ playout 経路を実装する**
   - 対象の中心は `AudioDeviceIOS` / `AudioDeviceModuleIOS` / AudioUnit 実装（現行は `VoiceProcessingAudioUnit`）の playout 側
   - 宣言 API だけでなく、バッファ・コールバック・ASBD（`GetFormat`）まで 2ch を通す
   - 過去試作を踏まえ、ステレオ時は `RemoteIO` への切替を軸に検討する
2. **既定挙動はモノラルのまま維持する**
   - `AVAudioSessionModeVoiceChat` と VPIO を既定とし、ステレオ出力有効時のみ mode / AudioUnit / チャンネル数を切り替える
   - ステレオを常時有効にするパッチにしない
3. **公開 API は最小限**
   - SDK または利用側がステレオ出力を有効化できる経路を用意する
   - SDP の `stereo=1` やアプリ側 `AVAudioSession` 設定は Sora iOS SDK / アプリ側の責務とし、本 issue の完了条件に含めない
4. **入力側とは分離する**
   - recording 側の改修は `0006-add-ios-stereo-audio-input` の範囲とする
   - AudioUnit 切替など共通基盤が必要なら、本 issue で出力に必要な範囲に限り入れ、入力固有の扱いは 0006 に残す
5. **デバイスハンドリングは段階的に扱う**
   - まずは固定デバイスでのステレオ再生を成立させる
   - 挿抜・Bluetooth ルート切替は、完了条件を満たしたうえで残課題として切り出せるなら別 issue にする

## 完了条件

- iOS 向けパッチが `patches/` に追加され、`run.py` の `PATCHES` dict に登録されていること。core 側（`sdk/objc/native/src/audio/` 配下の `audio_device_ios.mm` 等）を触る場合は `ios` と `ios_sdk` の両方に、SDK 拡張 API のみを追加する場合は `ios_sdk` のみに登録する
- ステレオ出力有効時に `StereoPlayoutIsAvailable` / `SetStereoPlayout` が成功し、AudioUnit の playout 経路が 2ch で動作すること
- SDK または利用側から iOS のステレオ出力を有効化できる経路（`RTCAudioDeviceModule` 相当の Objective-C API 拡張、または他の内部設定手段）が `ios_sdk` ビルド側から呼び出せること
- 既定（ステレオ未指定）では従来どおりモノラル（VoiceChat / VPIO）の挙動を維持すること
- 実機でステレオ再生が確認できること
- ステレオ出力有効時に AEC / AGC が使えないこと、Bluetooth（HFP / A2DP）の制約など、利用上の注意がパッチ解説または関連ドキュメントに残っていること
- CHANGES.md に追記があること

## 変更履歴案

- [ADD] iOS のステレオ音声出力に対応する

## 解決方法

### 追加した成果物

- `patches/ios_stereo_audio_output.patch`: libwebrtc iOS ADM のステレオ playout 経路と SDK 公開 API を単一パッチで追加
- `patches/ios_stereo_audio_output.md`: パッチの解説と利用上の注意 (AEC/AGC 喪失、mode 切替、Bluetooth 制約、マイク権限、呼び出しタイミング、実機検証の必要性)
- `run.py` の `PATCHES["ios_sdk"]` に `ios_audio_pause_resume.patch` の直後として登録

### 実装した変更

- `AudioDeviceIOS`
  - `StereoPlayoutIsAvailable` / `SetStereoPlayout` / `StereoPlayout` を実装し、`playout_parameters_.channels()` を単一の source of truth として参照
  - `UpdateAudioDeviceBuffer` の playout モノラル DCHECK を削除
  - `OnGetPlayoutData` の `mNumberChannels == 1` ハードコード DCHECK を動的比較へ差し替え
  - `CreateAudioUnit` を stereo 有効時のみ `RemoteIOAudioUnit` を選ぶ形に分岐
  - `ConfigureAudioSession` / `ConfigureAudioSessionLocked` で stereo 有効時のみ AVAudioSession の mode を `AVAudioSessionModeDefault` に一時差し替え、`@try/@finally` で復元を保証
  - stereo 関連 3 関数 (`StereoPlayoutIsAvailable` / `SetStereoPlayout` / `StereoPlayout`) に `RTC_DCHECK_RUN_ON(thread_)` を付与
- `VoiceProcessingAudioUnit`
  - デストラクタ、`Init`、`Initialize` を virtual 化
  - private セクション全体を protected に格上げし、`RemoteIOAudioUnit` から static コールバック等にアクセス可能にする
- `RemoteIOAudioUnit` (新規)
  - `VoiceProcessingAudioUnit` を継承し `kAudioUnitSubType_RemoteIO` を使う
  - `Init` で入力/出力 bus を両方 EnableIO し、`OnGetPlayoutData` と `OnDeliverRecordedData` の両コールバックを登録 (入力配線を欠くと stereo playout 時に recording が壊れるため必ず配線)
  - `Initialize` で `play_channels_` / `rec_channels_` を反映した stream format を設定
  - デストラクタ実装を `.mm` に明示的に置く
- `RTCAudioDeviceModule` (SDK 公開 API)
  - `setStereoPlayoutEnabled:` と `stereoPlayoutEnabled` を追加。docstring に呼び出し順序・スレッド・副作用・戻り値を明記
- `sdk/BUILD.gn` に `remote_io_audio_unit.h/.mm` を追加

### 設計判断

- **登録先は `ios_sdk` のみ**: 完了条件は「core を触る場合は `ios` と `ios_sdk` の両方」と書いているが、本パッチは `ios_audio_pause_resume.patch` が作る `RTCAudioDeviceModule` に依存する SDK 拡張と一体で提供されるため `ios_sdk` にのみ登録。raw `ios` ビルド (Sora C++ SDK 相当) には本機能は含まれない。パッチ md でこの割り切りを明記
- **SDK API はメソッド方式**: `RTCAudioSessionConfiguration` シングルトンを SDK 利用者が触る方式は捨て、`RTCAudioDeviceModule` にメソッド追加 (`setStereoPlayoutEnabled:` / `stereoPlayoutEnabled`) する形にした。既存 `pauseRecording` / `resumeRecording` と一貫し、意図が明示的で型が効く
- **単一の source of truth**: `AudioDeviceIOS` 側に `play_channels_` メンバは持たず、`playout_parameters_.channels()` に一本化。過去試作が持っていた二系統管理の食い違いバグを構造的に排除

### 実機検証

本パッチは iOS 実機での 2ch playout 動作を自動テストで確認できない。CI (`build.yml`) は `ios` / `ios_sdk` のビルド成功 (パッチ適用と compile pass) までカバーするが、実行時挙動 (`setStereoPlayoutEnabled:YES` 呼び出し後に AudioUnit の 2ch stream format が実際に L/R 別々の音として出るか、既定 mono パスに影響がないか) はマージ前に実機での聴感確認が必要。

### 保留した改善事項

以下は本パッチのスコープ外とし、必要になれば別 issue で扱う。

- `RemoteIOAudioUnit::Init` / `Initialize` の大部分が `VoiceProcessingAudioUnit` と重複している (Init のプロパティ設定シーケンス、Initialize の `AudioUnitInitialize` リトライループ)。upstream 追従保守のため hook 化する余地がある
- `kInputBus` / `kOutputBus` / `kMaxNumberOfAudioUnitInitializeAttempts` が親クラスの .mm と派生クラスの .mm で同一値の重複定義
- `~RemoteIOAudioUnit` を `= default` にすれば .mm 側の空実装を削れる
- SDK API を将来 recording 側 (0006) と足並みを揃える際、個別メソッドを増やすか `RTCAudioDeviceModuleConfiguration` 相当の設定オブジェクトに集約するかの判断
- md の読み順を SDK 利用者向けと開発者向けで節分けする再構成余地
- SDK 側 API 呼び出し例に Objective-C 版のスニペットも用意する余地

### review-diff-code ループ結果

3 周 (本審 + 深掘り 2 周) 実施。以下を反映して致命的 0 件・重要 0 件で終了。

- Round 1 致命的 1 件: `voice_processing_audio_unit.h` の `OnGetPlayoutData` / `OnDeliverRecordedData` が private のまま派生から参照されコンパイルエラー → private セクション全体を protected に格上げ
- Round 1 重要 3 件: `RTCAudioSessionConfiguration.mode` 一時書き換えを `@try/@finally` で保証、パッチ内コメントから `0006` 除去、`RemoteIOAudioUnit::CreateAudioUnit` という存在しないシンボル名の削除 (実際は `Initialize`)
- Round 2 重要 1 件: `setStereoPlayoutEnabled:` docstring にスレッド制約と `Init` 副作用を追記
- Round 2 重要 1 件: `AudioDeviceIOS` の stereo 3 関数に `RTC_DCHECK_RUN_ON(thread_)` を追加
- Round 3 重要 1 件: `stereoPlayoutEnabled` (getter) の docstring にスレッド制約を追記
- 副次: md の「呼び出し順序」「Terminate 跨ぎ」節を「呼び出しタイミングとスレッドの制約」に統合。マイク権限必須の注記と Bluetooth A2DP category option 未設定の注記を追加
