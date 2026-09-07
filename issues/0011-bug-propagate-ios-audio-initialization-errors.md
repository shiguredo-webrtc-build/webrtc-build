# iOS 音声の初期化失敗を呼び出し元へ伝播する

- Created: 2026-09-07
- Completed: {YYYY-MM-DD}
- Branch: feature/m150.7871
- Polished: {YYYY-MM-DD}

## 目的

AudioSession または AudioUnit の初期化に失敗した場合に、初期化済みとして処理が継続し、利用者が成功と判断する状態を防ぐ。

## 現状

調査対象は `m150.7871.3.2` と stereo パッチ導入コミット `ff4271c9c62ff70c257aeac4d694f0abab7a76e7` である。

- `ios_manual_audio_input.patch` が変更する `AudioDeviceIOS::InitPlayOrRecord` は、`audio_unit_->Initialize(...)` の戻り値を確認せず、`audio_is_initialized_` を true にして成功を返す。
- `ios_stereo_audio_output.patch` の `RemoteIOAudioUnit::Initialize` は、ストリーム形式の設定や `AudioUnitInitialize` の失敗時に false を返す。この失敗が上記の呼び出し元で失われる。
- `ios_manual_audio_input.patch` は `RTCAudioSession+Configuration.mm` の最終的なエラー判定を `return YES` に変更している。どのエラーを許容する目的だったのかを確認する必要がある。
- `setStereoPlayoutEnabled:` の成功は設定の受付を示すものであり、後で実行する AudioUnit の初期化成功は保証しない。

以上はコード上で確認した問題である。特定の端末で無音になる条件や発生頻度は未検証である。

## 設計方針

- AudioUnit の初期化結果を確認し、失敗した場合は成功時の状態へ進めない。`InitPlayout` や `StartPlayout` を含む呼び出し経路も確認する。
- AudioSession の設定失敗は、動作を継続できないエラーと、OS が希望値を採用しなかった場合を区別する。既存パッチの意図を確認せずに、すべての希望値の不一致を致命的エラーへ変更しない。
- 失敗時は AudioUnit、delegate、AudioSession の利用開始と終了、初期化・再生状態の整合を保ち、再試行や破棄ができるようにする。
- 戻り値だけでは上位まで届かない非同期の失敗は、対象の ADM と対応付けて利用側が検知できる経路を設ける。共有 AudioSession の通知だけで失敗した接続を推測させない。
- VoiceProcessingIO と RemoteIO の両方で、正常時の挙動を維持する。

## 対応ブランチと依存関係

ユーザー指定の例外として、個別ブランチを作成せず `feature/m150.7871` で対応する。
Sora iOS SDK の PR #381 に含める issue 0130 の前提とし、本 issue を先に対応する。
設定の保持を扱う issue 0012、共有設定を扱う issue 0013、入力不要化を扱う issue 0014 とは目的を分ける。

## テスト方針

実際の ADM と AudioUnit を使って成功、失敗後の破棄、再初期化を確認する。
実機でしか発生させられない失敗は手順と観測結果を残し、モックやスタブは使用しない。
実行できなかった失敗条件を、検証済みとして扱わない。

## 完了条件

- 初期化に失敗した ADM が初期化済み・再生中として成功を返さない。
- 継続不能な AudioSession の設定・有効化エラーが握りつぶされない。
- 呼び出し元が、失敗した ADM と失敗段階を識別できる。
- 失敗後に再試行または破棄しても、利用数やリソースが残らない。
- 変更したパッチの適用対象を確認し、該当するビルドと VoiceProcessingIO / RemoteIO の動作を検証している。
- 検証した条件と未検証の条件を記録している。

## 解決方法
