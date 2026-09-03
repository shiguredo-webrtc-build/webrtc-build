# iOS のステレオ音声出力に対応する

- Created: 2026-09-03
- Completed:
- Branch: feature/add-ios-stereo-playout
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

## 試作から引き継ぐ AudioDeviceIOS 側の注意点

過去試作は `feature/ios-stereo-audio` ブランチの `patches/ios_stereo_audio.patch` にある。**本 issue では試作パッチのコードを直接流用しない** ことを設計方針 8 で決めている。RemoteIOAudioUnit も VP を継承せず独立実装するため、試作パッチが持っていた継承前提のバグ (`RemoteIOAudioUnit` デストラクタ未定義、`GetFormat` 2ch 固定、`play_channels_` と `playout_parameters_` の二系統管理など) は新実装では発生形自体が異なる。試作パッチのヘッダコメントや STEREO_LOG、m138 系ベースといった衛生上の未完項目も、コード非流用なので継承する必要はない。

一方、`AudioDeviceIOS` 側の実装は upstream をそのまま活かし、本 issue でステレオ playout API を新規実装する。試作パッチが `AudioDeviceIOS` 側で踏んでいた次の 2 つの誤りは、新実装でも同じ轍を踏まないよう明示的に避ける。

- `AudioDeviceIOS::StereoPlayoutIsAvailable` を「`record_parameters_.channels()` の値」で判定してはならない (試作パッチのコピペミス。playout 可否を recording 側の状態で判定することになる)。単一の source of truth である `playout_parameters_.channels()` で判定する
- `AudioDeviceIOS::OnGetPlayoutData` の `RTC_DCHECK_EQ(1, audio_buffer->mNumberChannels)` は残してはならない (試作パッチはこの DCHECK を残していたため、ステレオ playout 時に Debug ビルドが即死した)。設計方針 3 に沿い `playout_parameters_.channels()` との動的比較に置き換える

## 設計方針

1. **AudioUnit 種別を抽象化するため abstract class `AudioUnitInterface` を導入する**
   - `sdk/objc/native/src/audio/audio_unit_interface.h` に新規 abstract class を置く
   - **メソッド**: `AudioDeviceIOS` が `audio_unit_` 経由で呼び出す次を pure virtual メソッドとして並べる: `Init` / `Initialize(Float64 sample_rate)` / `Start` / `Stop` / `Uninitialize` / `SetMicrophoneMute(bool)` / `Render(...)` / `GetState() const`
   - **State enum**: `State { kInitRequired, kUninitialized, kInitialized, kStarted }` は `AudioUnitInterface` 側に移し、`VoiceProcessingAudioUnit` は自前定義を撤去して interface 継承経由で利用する。`AudioDeviceIOS.mm` に散在する `VoiceProcessingAudioUnit::kInitialized` / `kInitRequired` / `kUninitialized` / `kStarted` などの参照 (計 10 箇所以上) はすべて `AudioUnitInterface::kInitialized` 等に機械的に書き換える
   - **Observer**: コールバック観察側の interface (`VoiceProcessingAudioUnitObserver`) は既存のまま流用する。`AudioDeviceIOS` は既に `VoiceProcessingAudioUnitObserver` を継承しているため触らない。`RemoteIOAudioUnit` からも同 observer 型のポインタを保持し `OnGetPlayoutData` / `OnDeliverRecordedData` を経由して通知する。`OnReceivedMutedSpeechActivity` は VPIO 固有で RemoteIO からは発火しないが、observer 側の実装が呼ばれないだけで害はない (observer 型の名前が VP flavor である点は割り切り。名前変更まで踏み込まない)
   - **VoiceProcessingAudioUnit への upstream 変更**: `class VoiceProcessingAudioUnit : public AudioUnitInterface` に継承を追加し、既存メソッドに `override` を付け、自前 State enum を削除する。**private セクションの protected 昇格や既存メソッドへの virtual 後付けはしない**
   - **AudioDeviceIOS への変更**: `audio_unit_` の型を `std::unique_ptr<VoiceProcessingAudioUnit>` から `std::unique_ptr<AudioUnitInterface>` に変える。上記 State 参照の書き換えも含む
2. **`RemoteIOAudioUnit` は VoiceProcessingAudioUnit を継承しない**
   - `sdk/objc/native/src/audio/remote_io_audio_unit.h` / `.mm` に、`AudioUnitInterface` を直接実装する **完全に独立したクラス** として実装する
   - `componentSubType` は `kAudioUnitSubType_RemoteIO` を用いる
   - Init のプロパティ設定シーケンス (5 個の `AudioUnitSetProperty` 呼び出し) や Initialize の `AudioUnitInitialize` リトライループは `VoiceProcessingAudioUnit` と一部似た形になるが、**共有せず独立して持つ** ことを許容する。upstream 追従で片方だけ古くなるリスクは、独立実装であることを明示することで管理する
   - 内部フィールド名も VP-flavor から解放する (`vpio_unit_` ではなく `rio_unit_` 等、実態を反映した命名にする)
   - `Init` では入力 bus (`kAudioOutputUnitProperty_EnableIO` on `kAudioUnitScope_Input` + `SetInputCallback` で `OnDeliverRecordedData` 登録) と出力 bus (`EnableIO` on `kAudioUnitScope_Output` + `SetRenderCallback` で `OnGetPlayoutData` 登録) の両方を配線する。ステレオ playout 有効時に recording を壊さないため
3. **AudioDeviceIOS のステレオ playout API を実装する**
   - `StereoPlayoutIsAvailable` / `SetStereoPlayout` / `StereoPlayout` を実装。`playout_parameters_.channels()` を **単一の source of truth** として参照し、`play_channels_` のような別メンバによる二重管理を作らない
   - `SetStereoPlayout(true)` で `playout_parameters_.reset(sample_rate, 2, frames_per_buffer)` を呼び出し、以降の `CreateAudioUnit` が `playout_parameters_.channels() == 2` を見て `RemoteIOAudioUnit` を選ぶ
   - `UpdateAudioDeviceBuffer` の playout モノラル DCHECK と `OnGetPlayoutData` の `mNumberChannels == 1` DCHECK を、`playout_parameters_.channels()` との動的比較に置き換える
   - 上記 stereo 系 3 関数に `RTC_DCHECK_RUN_ON(thread_)` を付ける
4. **既定挙動はモノラルのまま維持する**
   - `AVAudioSessionModeVoiceChat` と VPIO を既定とし、ステレオ出力有効時のみ mode / AudioUnit / チャンネル数を切り替える
   - ステレオを常時有効にするパッチにしない
   - `ConfigureAudioSession` / `ConfigureAudioSessionLocked` でステレオ有効時のみ `AVAudioSessionModeDefault` に一時差し替えする。復元は `@try/@finally` で保証する
5. **公開 API は最小限**
   - `RTCAudioDeviceModule` に `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を追加。既存 `pauseRecording` / `resumeRecording` と同じメソッド追加パターン
   - `RTCAudioSessionConfiguration` のシングルトンを SDK 利用者に触らせる方式は採らない
   - ヘッダコメントに呼び出し順序制約 (Factory 渡し前 / スレッド制約 / AEC/AGC 喪失 / Init 副作用) を明記する
   - SDP の `stereo=1` やアプリ側 `AVAudioSession` 設定は Sora iOS SDK / アプリ側の責務とし、本 issue の完了条件に含めない
   - 0006 で `setStereoRecordingEnabled:` を追加する際の API 統合設計は `0010-change-rtc-audio-device-module-api-design` で判断する。0010 の判断は 0006 着手前に確定させる。**0005 完了時点では 0010 は未確定でよく、本 issue は暫定の個別メソッド方式 (`setStereoPlayoutEnabled:` / `stereoPlayoutEnabled`) で先行実装する。もし 0010 で Config オブジェクト集約方式が採用された場合は、その時点で 0005 の API 側も追随の再構成が発生する (後続作業として別途扱う)**
6. **入力側とは分離する**
   - recording 側の改修は `0006-add-ios-stereo-audio-input` の範囲とする
   - AudioUnit 切替の共通基盤 (`AudioUnitInterface` と `RemoteIOAudioUnit`) は本 issue で作るため、0006 はそれを前提に recording 経路の 2ch 対応を追加する形になる
7. **デバイスハンドリングは段階的に扱う**
   - まずは固定デバイスでのステレオ再生を成立させる
   - 挿抜・Bluetooth ルート切替は、完了条件を満たしたうえで残課題として切り出せるなら別 issue にする
8. **試作パッチのコードは直接流用しない**
   - 過去試作 `patches/ios_stereo_audio.patch` の実装は継承前提であり、m138 系ベースでもある
   - 上記 1 と 2 の設計に沿って新規に書き起こす。試作からは AudioDeviceIOS 側の実装で回避すべき具体的なバグ (「## 試作から引き継ぐ AudioDeviceIOS 側の注意点」節参照) の情報だけを引き継ぐ

## 完了条件

- iOS 向けパッチが `patches/` に追加され、`run.py` の `PATCHES` dict に登録されていること。本パッチは `ios_audio_pause_resume.patch` が提供する `RTCAudioDeviceModule` に依存し (SDK 拡張 API と一体)、`ios_audio_pause_resume.patch` 自体が `ios_sdk` のみに登録されている先例に合わせて、本パッチも **`ios_sdk` のみに登録** する。raw `ios` ビルドには本機能は含まれない (0006 と登録先の基準が異なるが、本 issue は先例踏襲、0006 は 0006 側の判断)
- `AudioUnitInterface` (abstract class) が新規追加され、`VoiceProcessingAudioUnit` と `RemoteIOAudioUnit` が独立にこれを実装していること。`VoiceProcessingAudioUnit` に対する upstream 変更は「interface を継承して override を付ける」だけの最小改造にとどまっており、private セクションの protected 昇格や既存メソッドの virtual 後付けを含まないこと
- `AudioDeviceIOS::audio_unit_` が `std::unique_ptr<AudioUnitInterface>` になっており、`CreateAudioUnit` が stereo 有効時のみ `RemoteIOAudioUnit` を生成し、それ以外は `VoiceProcessingAudioUnit` を生成する分岐になっていること
- ステレオ出力有効時に `StereoPlayoutIsAvailable` / `SetStereoPlayout` が成功し、AudioUnit の playout 経路が 2ch で動作すること
- SDK または利用側から iOS のステレオ出力を有効化できる経路 (`RTCAudioDeviceModule` に `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を追加) が `ios_sdk` ビルド側から呼び出せること。0010 で Config オブジェクト集約方式が採用された場合の API 再構成は本 issue の完了条件外 (後続作業とする)
- 既定 (ステレオ未指定) では従来どおりモノラル (VoiceChat / VPIO) の挙動を維持すること
- 実機でステレオ再生が確認できること
- ステレオ出力有効時に AEC / AGC が使えないこと、Bluetooth (HFP / A2DP) の制約など、利用上の注意がパッチ解説または関連ドキュメントに残っていること
- CHANGES.md に追記があること

## 変更履歴案

- [ADD] iOS のステレオ音声出力に対応する
