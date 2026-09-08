# iOS のステレオ音声出力に対応する

- Created: 2026-09-03
- Completed: 2026-09-03
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

## 解決方法

### 追加した成果物

- `patches/ios_stereo_audio_output.patch` (1128 行): AudioUnitInterface 抽象クラス導入 + `VoiceProcessingAudioUnit` への継承追加 + `RemoteIOAudioUnit` 独立実装 + `AudioDeviceIOS` の State 参照書き換え (17 箇所) + `RTCAudioDeviceModule` に stereo 制御メソッド追加を単一パッチで実現
- `patches/ios_stereo_audio_output.md` (113 行): パッチ解説 (SDK 利用者向け節と開発者向け節に分割)
- `run.py` の `PATCHES["ios_sdk"]` に `ios_audio_pause_resume.patch` の直後として登録

### 実装した設計

- **新規 abstract class `AudioUnitInterface`** (`sdk/objc/native/src/audio/audio_unit_interface.h`)
  - pure virtual メソッド: `Init` / `Initialize(sample_rate)` / `Start` / `Stop` / `Uninitialize` / `SetMicrophoneMute(bool)` / `Render(...)` / `GetState()`
  - `State { kInitRequired, kUninitialized, kInitialized, kStarted }` を interface 側に集約
  - `kBytesPerSample` も interface 側に集約
- **`VoiceProcessingAudioUnit` への upstream 変更は最小改造** (継承追加 + `override` + State enum 削除のみ)。private セクションの protected 昇格や既存メソッドの virtual 後付けはしない
- **`RemoteIOAudioUnit` は VoiceProcessingAudioUnit を継承せず、AudioUnitInterface を直接実装した完全独立クラス** として実装
  - `componentSubType = kAudioUnitSubType_RemoteIO`
  - 入力 bus / 出力 bus の両方に `EnableIO` と対応コールバック (`OnGetPlayoutData` / `OnDeliverRecordedData`) を配線
  - `GetFormat(sample_rate, channels)` で play / rec 個別のチャンネル数を扱う
  - `~RemoteIOAudioUnit()` は `= default` にせず `DisposeAudioUnit()` を明示的に呼ぶ (Core Audio 資源リーク回避)
- **`AudioDeviceIOS::audio_unit_` の型を `std::unique_ptr<AudioUnitInterface>` に変更**
  - `CreateAudioUnit` で stereo 有効時のみ `RemoteIOAudioUnit` を生成
  - `VoiceProcessingAudioUnit::kInitialized` 等の 17 箇所を `AudioUnitInterface::kInitialized` 等に機械的に書き換え
  - State ログのラベルを `VPAU state:` から `AudioUnit state:` に変更 (RemoteIO 使用時にも同じログが出るため汎化)
- **`AudioDeviceIOS::SetStereoPlayout` / `StereoPlayoutIsAvailable` / `StereoPlayout` を実装**
  - `playout_parameters_.channels()` を単一の source of truth
  - `SetStereoPlayout` に `audio_is_initialized_` チェック (状態遷移ガード)
  - 3 関数に `RTC_DCHECK_RUN_ON(thread_)` を付与
  - `UpdateAudioDeviceBuffer` の playout モノラル DCHECK 削除、`OnGetPlayoutData` の DCHECK を動的比較に置換
- **`ConfigureAudioSession` / `ConfigureAudioSessionLocked` で stereo 有効時のみ mode を `AVAudioSessionModeDefault` に一時差し替え**
  - 復元は `@try/@finally` で保証
  - setup を `lockForConfiguration` より前に置き、setup が例外を投げても未 lock 状態で抜ける形に整理
- **SDK 公開 API**: `RTCAudioDeviceModule` に `setStereoPlayoutEnabled:` と `stereoPlayoutEnabled` を追加。docstring に呼び出し順序・スレッド・副作用 (Init 冪等呼び出し / RemoteIO 切替 / AEC/AGC 喪失 / mode 切替) を明記

### 主な設計判断

- **VoiceProcessingAudioUnit を継承させず独立実装**: 前回 PR #171 の継承前提設計は upstream の VP を無理やり派生用に改造しており品質上マージ不可だった。今回は AudioUnitInterface 経由で独立実装することで upstream 変更を最小化 (継承 + override 追加のみ)
- **`RemoteIOAudioUnit::SetMicrophoneMute` は no-op で true を返す**: RemoteIO には VoiceProcessing 由来のマイクミュート機構がない。false 返却だと `ReinitAudioUnitForMicrophoneMute` がエラー扱いになるため no-op で true。組み合わせないでほしい旨は md 側に集約
- **登録先は `ios_sdk` のみ**: 依存する `ios_audio_pause_resume.patch` が `ios_sdk` のみ登録されている先例踏襲。raw `ios` ビルドには本機能は含まれない
- **`preferredOutputNumberOfChannels` は 1 のまま据え置き**: 実チャンネル数は RemoteIO の stream format で決まるためシングルトンを触らずに済ませる
- **mode 一時差し替えのみシングルトンを触る**: VoiceChat のままだと 1ch にクランプされるため mode 差し替えは避けられない。`@try/@finally` で復元保証し、書き換え窓を最小化

### 実機検証

CI (`build.yml`) は macOS runner で `ios` / `ios_sdk` のビルド成功 (パッチ適用と compile pass) までカバーする。実行時挙動 (2ch 出力が実際に L/R 別々の音として出るか、既定 mono パスに影響がないか、Bluetooth A2DP でのステレオ挙動、マイク権限有無での成否) はマージ前に iOS 実機での聴感確認が必要。詳細な検証項目は `patches/ios_stereo_audio_output.md` の「実機検証」節を参照。

### 保留した改善事項

以下はスコープ外とし、必要になれば別 issue で扱う。

- `ConfigureAudioSession` と `ConfigureAudioSessionLocked` のロジック重複 (ヘルパ関数化で解消可能)
- `AudioUnitInterface` に `SetMicrophoneMute` を含める設計 (Interface Segregation 観点では望ましくないが、既存 shape 維持のため現状維持)
- md の追加改善は `0009-doc-improve-ios-stereo-audio-output-md` で扱う予定

### review-diff-code ループ結果

3 周実施、致命的 0 件・重要 0 件で終了。

- Round 1 致命的 1 反映: `~RemoteIOAudioUnit() = default` による Core Audio 資源リークを実定義 + `DisposeAudioUnit()` 呼び出しに修正
- Round 1 重要 5 反映: SetStereoPlayout の状態遷移ガード、md 注記追加 3 件 (pauseRecording 形骸化 / bypass 無視 / mode 一時差し替え設計判断)、パッチ内「本 issue」除去
- Round 2 重要 1 反映: `ConfigureAudioSession` の lockForConfiguration を setup 後・@try 前に配置
- Round 3 重要 1 反映: `VPAU state:` ログラベルを `AudioUnit state:` に汎化
- 改善レベル数件を並行反映 (docstring 戻り値記述、SetMicrophoneMute コメント整理、md 表記統一等)
