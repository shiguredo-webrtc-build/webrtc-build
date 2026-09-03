# iOS のステレオ音声出力に対応する

- Created: 2026-09-03
- Completed:
- Branch: feature/m150.7871
- Polished:

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
- `VoiceProcessingAudioUnit::GetFormat` が `mChannelsPerFrame = 1` をハードコード
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
- `RemoteIOAudioUnit::CreateAudioUnit` から `GetFormat(sample_rate, 2)` と常に 2ch 固定で呼んでおり、`play_channels_` に連動していない。`GetFormat` の引数を動的に渡す
- チャンネル数を `play_channels_` と `playout_parameters_.channels()` の二系統で管理しているが同期していない。`SetStereoPlayout` は `play_channels_` しか更新せず、`CreateAudioUnit` は `playout_parameters_.channels() == 2` で RemoteIO を選ぶため、設定経路によって AudioUnit 種別と実チャンネル数が食い違う。単一の source of truth に統一する

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

- iOS 向けパッチが `patches/` に追加され、`feature/m150.7871` 上の iOS ビルドターゲットのパッチ適用リストに登録されていること
- ステレオ出力有効時に `StereoPlayoutIsAvailable` / `SetStereoPlayout` が成功し、AudioUnit の playout 経路が 2ch で動作すること
- 既定（ステレオ未指定）では従来どおりモノラル（VoiceChat / VPIO）の挙動を維持すること
- 実機でステレオ再生が確認できること
- AEC / AGC が使えないこと、Bluetooth（HFP / A2DP）の制約など、利用上の注意がパッチ解説または関連ドキュメントに残っていること
- CHANGES.md に追記があること

## 変更履歴案

- [ADD] iOS のステレオ音声出力に対応する
