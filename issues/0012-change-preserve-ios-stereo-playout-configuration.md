# ADM の再初期化後も stereo 出力設定を保持する

- Created: 2026-09-07
- Completed: {YYYY-MM-DD}
- Branch: feature/m150.7871
- Polished: {YYYY-MM-DD}

## 目的

MediaEngine の終了と再初期化によって stereo 出力設定が失われることを防ぎ、利用側で未接続の PeerConnection を保持する回避策を不要にする。

## 現状

調査対象は `m150.7871.3.2` と `ios_stereo_audio_output.patch` である。

- `AudioDeviceIOS::SetStereoPlayout` は再生パラメーターのチャンネル数を変更する。
- `AudioDeviceIOS::Init` は共有設定の希望値からパラメーターを初期化するため、同じ ADM で `Terminate` と `Init` を実行すると stereo の指定が失われる。
- `ConnectionContext` は MediaEngine の利用数が 0 になると終了処理を実行する。PeerConnectionFactory を保持するだけでは設定を維持できない。
- Sora iOS SDK の PR #381 は、`stereoMediaEngineAnchor` として未接続の PeerConnection を保持してこの状態遷移を避けている。

## 設計方針

- 利用者が指定した stereo 出力設定を、AudioUnit の現在の形式や初期化状態とは分けて ADM の寿命まで保持する。
- 再初期化時には保持した設定を `AudioDeviceIOS` と `AudioDeviceBuffer` のチャンネル数へ一貫して反映する。
- 新しい ADM の既定値は mono とし、初期化前に stereo を無効化した場合も再初期化後に反映する。
- AudioUnit 初期化後の設定変更を拒否する既存の制約を維持する。終了後に変更できる条件は明文化する。
- 設定値の getter と利用可否の判定について、未初期化時を含む既存の契約との整合を確認する。OS の物理的な出力チャンネル数とは区別する。
- 現在の公開 API を維持する。音声制御 API 全体の統合設計は既存 issue 0010 で扱う。

## 対応ブランチと依存関係

ユーザー指定の例外として、`feature/m150.7871` で対応する。
Sora iOS SDK の PR #381 に含める issue 0131 は、本 issue を含むビルドの取り込み後に対応する。
エラー時の状態遷移は issue 0011 の修正と整合させる。

## テスト方針

実際の ADM と PeerConnection を使い、stereo 設定後の初期化・終了・再初期化と、PeerConnection の利用数が 0 になる遷移を検証する。
mono、stereo の無効化、複数回の再初期化を含め、モックやスタブは使用しない。

## 完了条件

- 同じ ADM の再初期化後も指定した stereo 出力設定が保持される。
- 新しい ADM の既定値と、明示的に mono を指定した場合の挙動が変わらない。
- ADM、AudioDeviceBuffer、AudioUnit のチャンネル数が整合する。
- 未接続の PeerConnection を保持せずに、MediaEngine の終了と再初期化を経ても stereo 出力を継続できる。
- 設定変更と getter のライフサイクル上の契約が説明され、検証結果が記録されている。

## 解決方法
