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

Sora iOS SDK の issue 0133 で、既存の入力初期化呼び出しの復元と、ステレオの初期ミュート・公開ハードミュートの制約解除を扱う。
SDK 側で独自に持つミュート状態のキャッシュも除く。
本変更を含む依存ビルドへの更新と公開 API の統合検証が必要である。

## 設計方針

- `RemoteIOAudioUnit::SetMicrophoneMute` で、入力 bus `1` の `kAudioUnitScope_Input` にある `kAudioOutputUnitProperty_EnableIO` を制御する。mute は `0`、unmute は `1` とする。
- 出力 bus `0` の EnableIO は変更しない。[Apple の EnableIO リファレンス](https://developer.apple.com/documentation/audiotoolbox/kaudiooutputunitproperty_enableio) の入出力それぞれの設定を使う。
- 入力未初期化なら `false` を返す。0014 の `ReinitAudioUnitForMicrophoneMute` による事前確認も維持し、受信専用で拒否するときは再生を停止しない。
- 既存の Stop → Uninitialize → SetMicrophoneMute → バッファ設定 → Initialize の順序を使い、再生中または録音再開要求の場合だけ Start する。切り替え時は再生が一時中断し、成功すると再開する。送信専用の停止要求では AudioUnit を開始しない。
- `Initialize` では EnableIO を設定し直さず、指定した入力状態を維持する。
- `AudioUnitSetProperty` が失敗したら、要求と OSStatus を英語のログに記録して `false` を返す。既存の再初期化経路のエラー伝播を維持する。
- `ResumeRecording` は録音の論理状態だけでなく AudioUnit の実際のミュート状態を確認する。初期ミュートでは録音の論理状態が開始済みでも入力 I/O は無効なため、最初の解除を省略しない。
- `PauseRecording` も実際のミュート状態を確認し、解除が途中で失敗して入力 I/O だけ有効になった場合もミュートを反映する。
- 早期成功の条件には AudioUnit の開始状態も含める。直前のミュート・解除が途中で失敗して AudioUnit が停止していた場合は、次の解除で再初期化する。
- 手動音声停止や割り込み中は入力状態だけを反映し、AudioUnit の初期化・開始は既存の音声再開通知に任せる。
- VPIO のミュート音声検出が有効な場合も、初期ミュートからの解除で入力 I/O を戻す。音声検出時のミュートは従来の MuteOutput を使う。
- 公開 ObjC の pause / resume は factory の worker で同期実行する。factory を弱参照で登録し、呼び出し中は強参照で保持する。factory がない場合は失敗を返す。
- 同じ ADM を複数の factory に渡すことを拒否する。factory の初期化は nullable として公開し、SDK 側でも失敗を処理する。
- `Terminate` で worker 専用のデバイスとバッファを破棄し、ObjC ADM の最後の参照がアプリ側で解放されても worker を参照しない。終了後のネイティブ操作は初期化ガードで拒否する。

## テスト方針

モックやスタブは使用しない。

- 実際の RemoteIO の EnableIO を読み戻し、入力初期化前のミュート解除が拒否されることと、初期化後の同一要求の繰り返し・反転で入力だけが切り替わることを確認する。
- 実際の AudioDeviceIOS で再生と録音を開始し、既存 API で入力を初期化した後、pause / resume の戻り値、再初期化後の入力 I/O、録音の論理状態、AudioUnit の再開を確認する。
- 初期ミュートの後に pause を挟まず、最初の resume で入力 I/O が有効になることを確認する。
- 実際の factory / PC に渡した ObjC ADM で、アプリ側と同じ worker からの操作、同じ factory の再初期化、factory 終了後の拒否、二重受け渡しの拒否を確認する。
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

実機の完了条件が残るため、issue は open とする。ユーザーの指示に従い、既存 PR #174 の draft は解除済みである。

### 初期ミュート解除と SDK 統合に伴う追加修正

2026-09-07、初期ミュートでも `recording_=1` になるため最初の `ResumeRecording` が入力 I/O を有効にせず終了する不具合を、実際の AudioDeviceIOS を使うテストで再現した。
AudioUnit の実際のミュート状態を使う判定へ変更し、VPIO の音声検出時も初期ミュートの入力 I/O を戻すようにした。
また、SDK の GCD キューから worker 専用の録音処理を直接呼んでいた経路を、ObjC API 境界で worker に渡すようにした。
実際の factory を使う `RTCAudioDeviceModuleThreadingTests` を追加した。

- 追加した実装・XCTest の 10 ファイルは、実機向け・Simulator 向けの debug / release でコンパイルできた。
- 実際の AudioUnit の初期ミュート解除と EnableIO の読み戻し、ネイティブ ADM の終了後の拒否・再初期化を検査する `RTCStereoAudioOutputTests` の 7 件が成功した。
- 修正前の `testStereoInitiallyMutedInputCanResume` は、解除後の EnableIO が 0 のままであることを検出して失敗した。
- 修正後の実入出力テストは AudioUnitInitialize 内の既存の RPC タイムアウトで停止したため、通過を確認した結果として扱わない。
- factory / PC を使う新しい XCTest はコンパイル確認までであり、今回の最小構成の実行用プロジェクトでは未実行である。
- 追加修正前の HEAD `9fbb8c2` の全 CI ビルドは成功した。今回の追加修正の CI 成功とは区別する。

対応するネイティブビルドへの SDK の依存更新と、公開 API を通した実機検証が残る。
