# stereo 用 AudioSession の設定時に共有設定を一時変更しない

- Created: 2026-09-07
- Completed: {YYYY-MM-DD}
- Branch: feature/m150.7871
- Polished: {YYYY-MM-DD}

## 目的

stereo 用の AudioSession 設定を適用するために共有設定オブジェクトを一時変更する処理をなくし、他の ADM やホストアプリとの設定競合を減らす。

## 現状

調査対象は `m150.7871.3.2` と `ios_stereo_audio_output.patch` である。

- `ConfigureAudioSession` と `ConfigureAudioSessionLocked` は、共有の `RTCAudioSessionConfiguration` の mode を保存し、stereo の場合だけ `AVAudioSessionModeDefault` に変更して `configureWebRTCSession` を呼ぶ。
- 呼び出し後に mode を戻すが、共有オブジェクト自体を一時変更している。通常の経路では共有設定と mode の取得が AudioSession の設定ロックより前にある。
- 共有設定の mode を戻すことと、OS に適用した AudioSession の mode を戻すことは別である。
- Sora iOS SDK の PR #381 は stereo 利用中の他の音声接続を拒否しているが、この制約ではホストアプリや他の SDK による共有設定への操作は制御できない。

## 設計方針

- 共有設定を読み取って作成した独立した設定を、対象の音声プロファイルに合わせて適用する経路を設ける。
- 共有設定の一時書き換えをなくし、設定取得・適用の同期範囲と、既にロックを保持する経路の責務を明確にする。
- AudioSession の利用数、delegate 通知、設定失敗の伝播、割り込み後の再設定を維持する。単純に既存の設定メソッドを迂回しない。
- ホストアプリによる設定オブジェクトの置換や mode の変更を、古い値で上書きして復元しない。
- AVAudioSession がプロセスで共有される制約は残る。共有オブジェクトを変更しなくなったことだけを根拠に、複数 ADM の同時動作を保証しない。
- VoiceProcessingIO と RemoteIO の独立した AudioUnit 実装は維持する。

## 対応ブランチと依存関係

ユーザー指定の例外として、`feature/m150.7871` で対応する。
Sora iOS SDK の PR #381 に含める issue 0132 の前提とする。
失敗処理は issue 0011、入力を無効にするプロファイルは issue 0014 と整合させる。

## テスト方針

実際の AudioSession と ADM を使い、通常の設定、設定失敗、再設定、ホストによる共有設定の置換を検証する。
実機では mono / stereo の逐次利用と同時利用を区別し、同時利用を保証できる条件を確認する。
モックやスタブは使用しない。

## 完了条件

- stereo の設定適用中も共有設定オブジェクトの mode を変更しない。
- 既存の利用数、通知、ロック、失敗処理の契約を維持する。
- ホストが変更した設定を終了処理で古い値に戻さない。
- 割り込みや経路変更後も、現在の音声プロファイルに対応する設定を適用する。
- 同時利用について保証できる範囲と残る制約が記録され、SDK 側が接続可否を判断できる。

## 解決方法
