# RemoteIO の SetMicrophoneMute でハードウェアミュートを実現する

- Created: 2026-09-07
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-ios-hard-mute-remote-io
- Polished: 2026-09-07

## 目的

ステレオ出力の RemoteIO でも、入力初期化後の `pauseRecording` / `resumeRecording` で入力 I/O を停止 / 再開できるようにする。
従来の `SetMicrophoneMute` は no-op であり、録音データの転送を止めてもマイクの入力 I/O は有効なままだった。
マイクの捕捉とインジケーターの停止・復帰は、入力 I/O の制御に加えて実機で確認する。

## 前提と依存関係

ユーザー指定により、`feature/m150.7871` をベースに `0014 → 0015 → 0016` の gh stack を構成する。
本 issue の直接のベースは、0015 の `feature/fix-custom-audio-input-stereo-sample-count` とする。

0014 により、RemoteIO も既存の `RTCAudioSession.initializeInput` を呼ぶまで入力 I/O が無効になり、`setInitialMicrophoneMute` の指定が適用される。
送信側は入力初期化を要求し、受信専用では要求しない。
本 issue は、その初期化後の実行時ミュートを実装する。
入力未初期化の状態でミュート解除を要求しても、入力を有効化しない。
新しい入力不要プロファイルは追加しない。

Sora iOS SDK は公開 API `setAudioHardMute` でステレオ時の操作を拒否している。
SDK 側での解除は、本変更を含む依存ビルドへの更新と公開 API の統合検証が必要である。
SDK の issue 0133 が扱う既存の入力初期化呼び出しの復元と、公開ハードミュートの制約解除は区別する。

## 設計方針

- `RemoteIOAudioUnit::SetMicrophoneMute` で、入力 bus `1` の `kAudioUnitScope_Input` にある `kAudioOutputUnitProperty_EnableIO` を制御する。mute は `0`、unmute は `1` とする。
- 出力 bus `0` の EnableIO は変更しない。[Apple の EnableIO リファレンス](https://developer.apple.com/documentation/audiotoolbox/kaudiooutputunitproperty_enableio) の入出力それぞれの設定を使う。
- 入力未初期化なら `false` を返す。0014 の `ReinitAudioUnitForMicrophoneMute` による事前確認も維持し、受信専用で拒否するときは再生を停止しない。
- 既存の Stop → Uninitialize → SetMicrophoneMute → バッファ設定 → Initialize → Start の順序を使う。切り替え時は再生が一時中断し、成功すると再開する。
- `Initialize` では EnableIO を設定し直さず、指定した入力状態を維持する。
- `AudioUnitSetProperty` が失敗したら、要求と OSStatus を英語のログに記録して `false` を返す。既存の再初期化経路のエラー伝播を維持する。
- VPIO のミュート機構、入力初期化と初期ミュート、SDK の role 判断は変更しない。

## テスト方針

モックやスタブは使用しない。

- 実際の RemoteIO の EnableIO を読み戻し、入力初期化前のミュート解除が拒否されることと、初期化後の同一要求の繰り返し・反転で入力だけが切り替わることを確認する。
- 実際の AudioDeviceIOS で再生と録音を開始し、既存 API で入力を初期化した後、pause / resume の戻り値、再初期化後の入力 I/O、録音の論理状態、AudioUnit の再開を確認する。
- 0014 の受信専用テストと入力初期化テストを再実行し、初期ミュートと入力未使用の契約を壊さないことを確認する。
- 実機で sendrecv / sendonly のマイク音声、インジケーター、ミュート中と切り替え後の左右の再生音、Bluetooth、割り込みと経路変更を確認する。

## 完了条件

- 入力初期化後の RemoteIO で、ハードミュートの要求に従って入力 I/O が切り替わり、実際の成功 / 失敗を返す。
- 入力未初期化の受信専用では、ミュート解除によって入力を接続せず、再生を停止しない。
- 実機でマイク捕捉とインジケーターが停止・復帰し、ミュート中と再初期化後にもステレオ再生ができる。
- 既存の mono のミュートと初期マイクミュートを維持する。
- 実機の検証条件と結果を記録する。

## 対応状況

2026-09-07、RemoteIO の no-op を入力 bus の EnableIO 制御に置き換えた。
0014 の入力未初期化ガードを維持して rebase し、既存の EnableIO テストも入力初期化を経るように修正した。
さらに、実際の AudioDeviceIOS の pause / resume を使う `testStereoHardMuteKeepsPlayback` を追加した。
0014 で stereo 出力と mono 入力のフレーム数による整合性検査が導入されたため、従来のバイト数一致 DCHECK による停止は解消している。

### 検証結果

- upstream `1f975dfd761af6e5d76d28333191973b258d82a8` に `ios_sdk` の全 24 パッチを順に適用できた。0014 / 0016 の対象ソースは検証用ソースと一致した。
- Xcode 26.6 / iOS SDK 26.5 で、関連実装と XCTest の 8 ファイルを実機向け・Simulator 向け、それぞれ debug / release でコンパイルできた。
- 実際の Objective-C ADM、AudioDeviceIOS、RemoteIO、VPIO と XCTest をリンクできた。入力未初期化ガードと EnableIO 切り替えを検査する `testRemoteIOMicrophoneMutePreservesOutputIO` を含む `RTCStereoAudioOutputTests` の 4 件は成功した。
- 0014 単体では iOS 26.2 Simulator の入力初期化テスト 12 件が成功した。権限未決定・拒否での受信専用テストも成功した。
- スタック全体の追試では、入力を開く 10 件が Core Audio 内部の RPC タイムアウトでクラッシュし、17 件中成功は 7 件だった。追加した `testStereoHardMuteKeepsPlayback` はミュート操作前の初回 AudioUnit 初期化で停止し、Simulator 再起動後の単独実行でも再現した。実際の pause / resume の通過を確認した結果としては扱わない。
- 既存の Python テスト 15 件と差分の空白検査が成功した。0014 との統合後のコードレビューでも、致命的・重要な指摘は 0 件だった。

### 残る確認

接続可能な iOS 実機がないため、マイク音声の送信、左右の再生音、インジケーター、Bluetooth、割り込みと経路変更の実機検証は未実施である。
配布用 `ios_sdk` のフルビルドは CI で確認する。
既存のビルド設定は `rtc_include_tests=false` のため、CI のビルド成功は XCTest の実行成功を意味しない。

0014 の検証では、iOS 26.5 Simulator の `AudioUnitInitialize` 内で RPC タイムアウトによるクラッシュが発生した。
変更前の native ソースでも再現し、iOS 26.2 では一度は変更前・変更後とも成功した。
その後の追試では iOS 26.2 でも同じタイムアウトが再現したため、特定ランタイムだけの問題とは断定しない。
Simulator の音声入力初期化が再実行時に不安定になる原因と対処は未確定であり、クラッシュを修正済みとは扱わない。
テスト実行ではメインの run loop を動かして worker を待ち、XCTest の実行タイムアウトを有効にする。

実機の完了条件が残るため、issue は open、既存 PR #174 は draft を維持する。
