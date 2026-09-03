# RemoteIOAudioUnit の親クラスとの重複を整理する

- Created: 2026-09-03
- Completed: 2026-09-03
- Branch: feature/refactor-remote-io-audio-unit-duplication
- Polished:

## 目的

`patches/ios_stereo_audio_output.patch` で新設した `RemoteIOAudioUnit` は、親クラス `VoiceProcessingAudioUnit` と大部分のコードが重複している。将来 upstream の libwebrtc が `VoiceProcessingAudioUnit` を更新した際に派生側だけ古くなる保守リスクがあるため、親クラス側に共通処理を集約して重複を減らす。

## 現状

過去のレビュー (`review-diff-code` Round 2 / Round 3) で次の重複が指摘されている。0005 の実装スコープでは動作優先で許容したが、独立の作業として整理する。

- `RemoteIOAudioUnit::Init` (`sdk/objc/native/src/audio/remote_io_audio_unit.mm`) は `VoiceProcessingAudioUnit::Init` (`sdk/objc/native/src/audio/voice_processing_audio_unit.mm`) と、`componentSubType` (`kAudioUnitSubType_RemoteIO` vs `kAudioUnitSubType_VoiceProcessingIO`) と各所ログ文字列以外はほぼ同一。5 個の `AudioUnitSetProperty` 呼び出しシーケンスが両方に展開されている
- `RemoteIOAudioUnit::Initialize` の `AudioUnitInitialize` リトライループも親と派生で重複
- `static const` 定数 `kInputBus` / `kOutputBus` / `kMaxNumberOfAudioUnitInitializeAttempts` が `voice_processing_audio_unit.mm` と `remote_io_audio_unit.mm` の両方で同一値で定義されている (file-local static のためリンク衝突はしないが片方だけ変わるリスクがある)
- `RemoteIOAudioUnit::~RemoteIOAudioUnit` は空実装として `.mm` に置いてあるが、`= default` で置換すれば `.mm` 側 6 行を削れる

## 設計方針

- `VoiceProcessingAudioUnit` 側に protected な仮想 hook を追加し、派生から `componentSubType` などの差分値を返せるようにする
- 集約後は `RemoteIOAudioUnit::Init` / `Initialize` はコンストラクタ以外の実装がほぼ空 (親呼び出し + hook 差分の反映) になる想定
- 定数は親クラスの protected constexpr として公開し、派生から参照できるようにする
- `~RemoteIOAudioUnit()` を `= default;` に変更し、`.mm` 側の空実装を削除する
- 挙動 (現在動く経路) を一切変えない範囲でリファクタする。実機での 2ch playout 挙動が本作業前後で同一であることを維持する

## 完了条件

- `remote_io_audio_unit.mm` の `Init` / `Initialize` から親と重複するプロパティ設定シーケンス・リトライループが削除されている
- 定数 `kInputBus` / `kOutputBus` / `kMaxNumberOfAudioUnitInitializeAttempts` の重複定義が解消されている (片方だけの定義になる)
- `~RemoteIOAudioUnit()` を `= default;` に変更し、`.mm` 側の空実装が削除されている
- CI (`.github/workflows/build.yml`) の `ios` / `ios_sdk` ビルドが通る
- 実機で `setStereoPlayoutEnabled:YES` 経路のステレオ playout 動作が 0005 マージ後と同一であることが確認できている
- `CHANGES.md` に `[UPDATE]` エントリが追加されている

## 変更履歴案

- [UPDATE] RemoteIOAudioUnit の親クラスとの重複を整理する

## 解決方法

本 issue は着手せず closed にする。上位の設計判断で issue の前提そのものが崩れたため。

- 0005 (`iOS のステレオ音声出力に対応する`) の PR #171 は「継承前提の設計が upstream の `VoiceProcessingAudioUnit` を無理やり派生用に改変しており品質上マージできない」との判断で close された
- 0005 の設計方針を **AudioUnitInterface 抽象クラスを導入し、`VoiceProcessingAudioUnit` と `RemoteIOAudioUnit` はそれぞれ独立に interface を実装する** 方式に転換した (`0005-add-ios-stereo-audio-output.md` の「## 設計方針」参照)
- 新方針では `RemoteIOAudioUnit` は最初から `VoiceProcessingAudioUnit` を継承しない。したがって「派生クラスと親クラスの重複を整理する」という本 issue の前提自体が発生しない
- Init のプロパティ設定シーケンスと Initialize のリトライループは新方針でも VP と RIO で似た形になるが、これは **共有せず独立に持つことを許容する** と 0005 の設計方針で明示している (upstream 追従で片方だけ古くなるリスクは独立性で管理する)
- 定数 (`kInputBus` / `kOutputBus` / `kMaxNumberOfAudioUnitInitializeAttempts`) の重複、`~RemoteIOAudioUnit()` の空実装の話も、新実装の中で自然な形で決まる (`= default` にするかどうかは実装時判断) ので独立 issue で追跡する必要がない

新実装で同種の重複整理を後追いで整理したくなった場合は、その時点で別 issue を立てる。
