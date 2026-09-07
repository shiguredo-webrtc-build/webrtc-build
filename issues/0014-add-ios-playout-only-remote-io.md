# 既存の入力初期化を RemoteIO に適用する

- Created: 2026-09-07
- Completed: {YYYY-MM-DD}
- Branch: feature/add-ios-playout-only-remote-io
- Polished: {YYYY-MM-DD}

## 目的

既存の `RTCAudioSession.initializeInput` が呼ばれた場合だけマイク入力を初期化する契約を、stereo 再生用の RemoteIO にも適用する。
受信専用ではマイクを使用せず、マイクを送信する場合は既存の初期化要求によって入力を使用する。
新しい公開設定 API や、ADM の寿命中ずっと入力を禁止するプロファイルは追加しない。

## 現状

調査対象は `feature/m150.7871` の `7796ca165d9f14862154d00ce4b794b0043f0622` にあるパッチである。

- `RemoteIOAudioUnit` は入力側の `kAudioOutputUnitProperty_EnableIO` を有効にし、入力コールバックも設定する。
- `ios_manual_audio_input.patch` は VoiceProcessingIO の入力初期化を分離し、公開 `initializeInput` の要求を生成前なら待機し、生成後なら実行する。`setInitialMicrophoneMute` もこの経路で適用する。
- その実装は `VoiceProcessingAudioUnit`、`vpio_unit_`、VPIO のコールバックに直接依存している。独立して追加された RemoteIO はこの経路を通らない。
- Sora iOS SDK は送信側だけで `initializeAudioInput` を呼ぶ既存の判断を持つが、PR #381 は stereo の場合にその呼び出しをスキップする。受信専用でも `playAndRecord` を要求する分岐も追加されている。
- 録音データの転送を止める処理だけでは、AudioUnit の入力自体やマイク権限への依存を取り除けない。
- `ios_manual_audio_input.patch` は既定 category を `Ambient` に変更しているため、「PlayAndRecord を用いる WebRTC の性質上、再生にも権限が必要」という説明は不正確である。

## 設計方針

- `AudioUnitInterface` に内部の入力初期化操作を設け、VPIO の既存処理を移し、RemoteIO にも実装する。公開の `initializeInput` / `setInitialMicrophoneMute` は維持する。
- RemoteIO は入力を無効にして生成する。入力要求がない間は入力コールバックと入力ストリーム形式を設定しない。
- 入力の要否は SDK の既存の送信 / 受信の判断に従う。stereo 設定から入力の要否を推測しない。
- 入力初期化は AudioDeviceIOS の worker スレッドで実行する。生成前の要求を待機し、生成後の要求では必要な停止と再初期化を経て入力を接続する。
- 入力要求の重複、停止 / 破棄時のキャンセル、古い要求が次の AudioUnit を有効にする経路を防ぐ。完了コールバックは内部ロックの外で一度だけ呼ぶ。
- 一時停止、再初期化、割り込み、経路変更では、入力を要求したかとミュート状態を維持する。最終破棄では登録と待機要求を解除する。
- 入力未初期化の RemoteIO ではミュート解除だけで入力を有効にしない。初期ミュートは既存 setter の指定を入力初期化時に適用する。
- 入力未使用の再生は入力経路の有無を開始条件にしない。既存 category と手動音声制御を尊重し、受信専用を理由に公開 API や factory 再生成の制約を増やさない。
- 公開 API 全体の統合設計を扱う issue 0010、stereo 録音を扱う issue 0006、実行時のハードミュートを扱う issue 0016 は目的を分ける。

## 対応ブランチと依存関係

`feature/m150.7871` をベースに対応する。
ユーザー指定により、本 issue、issue 0015 の PR #173、issue 0016 の PR #174 の順で gh stack を構成する。
issue 0011 の失敗処理、issue 0012 の設定保持、issue 0013 の設定適用と整合させる。
Sora iOS SDK の PR #381 に含める issue 0133 の前提とする。SDK は依存更新と同時に stereo 時の入力初期化スキップを除き、`playAndRecord` の要否を送信の有無で判断する必要がある。
この SDK 側の変更なしでは、stereo の送信側が入力初期化を要求せず、マイク音声を取得できない。

## テスト方針

実機で、マイク権限が未決定または拒否された状態から受信専用の再生を開始する。
権限ダイアログ、入力の使用状態、実際の左右の再生、再接続、経路変更を確認する。
入力が必要な送受信の動作も確認し、モックやスタブは使用しない。
生成前 / 生成後の入力要求、初期ミュート、重複要求、破棄時の完了通知、再初期化後の入力状態を実際の AudioSession と AudioUnit で確認する。

## 完了条件

- `initializeInput` を呼ばない受信専用では入力 I/O を使用せず、マイク権限を要求せずに再生できる。
- マイク権限が拒否されていても受信専用の再生を開始できる。
- 既存 `initializeInput` を呼ぶ送信側では入力を使用でき、初期ミュートの指定を反映する。
- 再初期化や経路変更後も入力の初期化状態とミュート状態が維持される。
- 従来の入力を使用する mono / stereo 出力の送受信が動作する。
- 新しい公開設定 API を必要とせず、SDK 側の既存判断と呼び出しを使用できる。
- 実装側と SDK 側の変更を対応付け、送信側の初期化スキップを残したまま利用可能と説明しない。
- 実機の検証条件と結果が記録されている。

## 解決方法

`AudioUnitInterface` に入力初期化を移し、既存の `RTCAudioSession.initializeInput` から VPIO と RemoteIO を共通に制御するようにした。
公開設定 API は増やしていない。
AudioDeviceIOS が worker で要求を処理し、一時停止時は入力状態を保持する。
最終終了では待機要求をエラーで完了し、世代と AudioUnit ごとの安全フラグで古い入力タスクの実行を防ぐ。
入力初期化前のミュート解除は、再生を停止する前に拒否する。
stereo 出力と mono 入力の整合性検査は、バイト数の一致からフレーム数の一致に修正した。

## 検証結果

2026-09-07、upstream `1f975dfd761af6e5d76d28333191973b258d82a8` を使って確認した。

- `ios_sdk` の既存 23 パッチを順に適用し、検証したソースと一致した。
- Xcode 26.6 / iOS SDK 26.5 で、変更に関係する実装と XCTest の 7 ファイルを実機向け・Simulator 向け、それぞれ debug / release でコンパイルできた。
- 実際の AudioDeviceIOS、AudioDeviceBuffer、AudioUnit をリンクした検証用 XCTest で、iOS 26.2 Simulator 上の 12 テストが成功した。生成前後の要求、mono / stereo、初期ミュート、送信専用、手動音声の停止と再開、重複要求、取り消し、再接続を含む。
- iOS 26.2 / 26.5 Simulator で、マイク権限が未決定・拒否のそれぞれで、受信専用の再生と再接続の単独テストが成功した。最終版の再確認は iOS 26.2 で行った。
- 既存の Python テスト 15 件が成功した。モックやスタブは使用していない。
- 2 系統で 3 周の差分レビューを行い、致命的・重要な指摘を修正した。後続のクラッシュ調査で見つけたテスト待機の問題も修正した。

### Simulator のクラッシュ

iOS 26.5 Simulator で入力を使うテストを再実行した際、`AudioUnitInitialize` から Core Audio 内部の RPC がタイムアウトし、検証用 `Host` が `SIGABRT` で終了した。
メインスレッドを `BlockingCall` で待たないテストに変更しても再現した。
変更前の native ソース全体で組んだ単独テストも、同じ初期化位置と RPC タイムアウトで失敗した。
同じ比較を iOS 26.2 Simulator で行うと、変更前・変更後とも成功し、変更後の 12 テストも成功した。
したがって、本変更に固有の回帰とは確認できていないが、iOS 26.5 での失敗は未解消である。
Xcode がクラッシュ後に実行した 0 件のテストの成功表示は、検証成功として数えていない。

worker 操作はメインの run loop を動かして完了を待ち、未完了のまま teardown に進まないようにした。
XCTest の実行タイムアウトを 60 秒で有効にして、停止したプロセスの失敗と診断情報を記録する。

### 残る確認

接続可能な iOS 実機がないため、実際のマイク音声の送信、左右の再生音、インジケーター、Bluetooth、割り込みと経路変更の実機検証は未実施である。
検証用 XCTest のリンクと実行は確認したが、配布用 `ios_sdk` のフルビルドは CI で確認する。
Sora iOS SDK の issue 0133 は、本変更を含む依存ビルドへの更新と同時に、送信側の `initializeAudioInput` の呼び出しと category の判断を修正する必要がある。
実機の完了条件が残るため、本 issue は open のまま、PR は draft とする。
