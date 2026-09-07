# RemoteIO の SetMicrophoneMute でハードウェアミュートを実現する

- Created: 2026-09-07
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-ios-hard-mute-remote-io
- Polished: 2026-09-07

## 目的

ステレオ出力（RemoteIO）利用時、ネイティブの `RTCAudioDeviceModule.pauseRecording` がマイクのハードウェアミュートを実行しない。
ハードウェアミュートは、マイクの入力 bus を無効化してマイクデータの捕捉を止め、iOS のマイクインジケーターを消すことを指す。
現行実装は入力 bus を有効なまま維持し、再初期化に成功すると `pauseRecording` は成功を返す。
Sora iOS SDK の公開 API は、この制約に対してステレオ時のハードミュートをエラーで拒否している。
`RemoteIOAudioUnit::SetMicrophoneMute` を実装して、ネイティブ側でハードウェアミュートを成立させる。

## 現状

調査対象は `feature/m150.7871` の `3a098acb401f8493669ad6fcb77d24a3c426ffbc` にあるパッチである。

- ネイティブの呼び出し経路: `patches/ios_audio_pause_resume.patch` が追加する
  `RTCAudioDeviceModule.pauseRecording` / `resumeRecording` が `AudioDeviceModuleIOS::PauseRecording` / `ResumeRecording`、
  `AudioDeviceIOS::PauseRecording` / `ResumeRecording`、`ReinitAudioUnitForMicrophoneMute` を経由し、
  `AudioUnitInterface::SetMicrophoneMute` を呼ぶ。ここでは音声初期化済みかつ録音中からの pause と、その後の resume を対象とする。
- Sora iOS SDK の `Sora/AudioDeviceModuleWrapper.swift` にある `setAudioHardMute` はネイティブの戻り値が `0` なら成功扱いにする。
  ただし、現行の `Sora/MediaChannel.swift` にある公開 API `setAudioHardMute` は `audioStereoOutputEnabled == true` の場合に
  エラーを返すため、ステレオ時はラッパーへ到達しない。
- VPIO（モノラル）: `VoiceProcessingAudioUnit::SetMicrophoneMute` は `detect_mute_speech_ == false` のとき、
  入力 bus の `kAudioOutputUnitProperty_EnableIO`（`kAudioUnitScope_Input` / `kInputBus`）を `enable ? 0 : 1` でトグルし、
  入力 I/O を無効化する経路を使う。SDK は既定の `CreateAudioDeviceModule`（`muted_speech_event_handler = nullptr`）を
  使うため `detect_mute_speech_ = false` となり、この経路が選ばれる。
- RemoteIO（ステレオ）: `RemoteIOAudioUnit::SetMicrophoneMute` は no-op で `true` を返す。入力 bus は
  `RemoteIOAudioUnit::Init` で常に有効化されるため、mute しても入力 bus は有効なまま。
  `PauseRecording` は再初期化に成功すると `recording_` を無効にして録音データの転送を止めるが、入力 I/O は無効化しない。
  マイク捕捉とインジケーターの実機での変化は未検証であり、以下のテストで確認する。
- no-op にした経緯: stereo パッチで RemoteIO に VoiceProcessing 固有の `kAUVoiceIOProperty_MuteOutput` が無いことだけに
  着目し、`false` を返すと `ReinitAudioUnitForMicrophoneMute` がエラー扱いになるのを避けて no-op にした。
  ただし SDK が使うのは `MuteOutput` ではなく EnableIO トグル経路であり、これは RemoteIO にも存在する。

## 設計方針

- 変更対象は `patches/ios_stereo_audio_output.patch` が追加する `sdk/objc/native/src/audio/remote_io_audio_unit.mm` の
  `RemoteIOAudioUnit::SetMicrophoneMute(bool enable)` とする。VPIO の EnableIO 制御と同様に、
  `kAudioOutputUnitProperty_EnableIO`（`kAudioUnitScope_Input` / `kInputBus`）へ `UInt32` の `enable ? 0 : 1` を設定する。
  [Apple の EnableIO リファレンス](https://developer.apple.com/documentation/audiotoolbox/kaudiooutputunitproperty_enableio) にある
  入力 bus `1` の input scope を制御し、出力 bus `0` の output scope は変更しない。
- 適用タイミングは、開始済みの AudioUnit に対して `ReinitAudioUnitForMicrophoneMute` が Stop → Uninitialize →
  SetMicrophoneMute → SetupAudioBuffersForActiveAudioSession → Initialize → Start の順で行う既存フローを使う。
  Uninitialize の成功後に EnableIO を設定する。状態参照は `AudioUnitInterface::kStarted` 等へ書き換え済みである。
  `RemoteIOAudioUnit::Initialize` は EnableIO を設定し直さないため、この再初期化では指定値を上書きしない。
- 入力と出力の EnableIO は別々に設定できるが、切替時には AudioUnit 全体を停止して再初期化するため、再生の一時中断を許容する。
  mute / unmute に成功した後は stereo 再生が再開し、mute の継続中も再生できることを要件とする。
- `SetMicrophoneMute` 自身は `AudioUnitSetProperty` の成功時に `true`、失敗時に `false` を返し、失敗時は英語のログに
  mute / unmute の要求と `OSStatus` を記録する。再初期化全体は null / 不正状態、Stop、Uninitialize、SetMicrophoneMute、
  Initialize、Start の各失敗でもエラーを返す既存の契約を維持する。
- 現行の RemoteIO は recvonly でも入力 bus を有効にする。入力を最初から使わないプロファイルは 0014 の未実装機能であり、
  本 issue では追加しない。0014 導入後の共存条件は次節に示す。
- mono（VPIO）と `patches/ios_manual_audio_input.patch` が追加する `RTCAudioSession.setInitialMicrophoneMute` の挙動は変更しない。
  後者は共有の VPIO に対する初期入力設定であり、本 issue は RemoteIO の初期ハードミュート対応を追加するものではない。
- 本 issue はバグ修正に絞る。playout-only（入力不使用）は 0014、初期化失敗の伝播は 0011 で別扱い。

## 対応ブランチと依存関係

ユーザー指定により、0015 の対応ブランチをベースにした `feature/fix-ios-hard-mute-remote-io` で対応する。
`gh stack` で依存関係を管理し、本作業ではマージしない。

- 0014（playout-only RemoteIO）: 本 issue を先に適用できる。0014 の実装時に入力不要設定を優先し、mute / unmute で
  入力を有効化しない条件を組み込む。0014 が先に取り込まれた場合は、その入力不要設定を確認して本 issue の EnableIO 制御に反映する。
- 0011（初期化失敗の伝播）: `InitPlayOrRecord` の `Initialize` 戻り値確認に加え、AudioSession や非同期失敗の通知、
  失敗後の状態整合を扱う。本 issue は `SetMicrophoneMute` の実装と既存の失敗伝播の維持に絞る。
- Sora iOS SDK: SDK の 0010 は `issues/closed/0010-add-stereo-audio-output.md` にあり、ステレオ時の `setAudioHardMute` 拒否は
  実装済みである。本修正を含む WebRTC ビルドの取り込み後に、実行時のハードミュートを公開するか SDK 側で判断する。
  SDK の拒否処理の変更は本 issue に含めず、初期ハードミュートの制約も本修正だけを根拠に解除しない。

## テスト方針

モックやスタブは使用しない。

- `run.py` の `PATCHES["ios_sdk"]` で `ios_audio_pause_resume.patch` の後に修正済み stereo パッチを適用し、`ios_sdk` をビルドする。
  実機上で実際の `RTCAudioDeviceModule` を factory に渡す前に `setStereoPlayoutEnabled(true)` を呼ぶ。
  その ADM を使う sendrecv / sendonly の送信中に `pauseRecording` を直接呼び、戻り値が `0` で、
  入力 I/O とマイクの捕捉が停止し、インジケーターが消えることを確認する。
  この検証ではマイク権限を許可し、他の ADM やホストアプリ側の音声処理がマイクを使用していない状態にする。
- `resumeRecording` の戻り値が `0` で、捕捉とインジケーターが戻ることを確認する。
- sendrecv では左右を区別できる音声を再生し、切替による一時中断後に stereo 再生が再開することと、mute の継続中も再生できることを確認する。
- 現行 SDK の公開 `setAudioHardMute` はステレオ時に拒否されるため、上記のネイティブ検証と区別する。
  SDK 側で拒否処理を見直す際に、更新した WebRTC を使った公開 API の統合検証を行う。
- mono（VPIO）の既存ハードミュートを壊さないことを確認する。
- 0014 が適用済みの場合は、入力不要プロファイルで mute / unmute を呼んでも入力 I/O を有効化しないことを確認する。
  未適用の場合はこの条件を未検証として記録する。
- Bluetooth（A2DP / HFP）や割り込み後の挙動、マイク権限の有無を確認する。
- 失敗条件はログで切り分けられるようにし、検証した条件と未検証の条件を記録する。

現行の `sdk/objc/native/src/audio/audio_device_ios.mm` の `SetupAudioBuffersForActiveAudioSession` には、
playout と recording の `GetBytesPerBuffer()` が等しいことを要求する DCHECK が残っている。
同じフレーム数でも stereo 出力と mono 入力ではバイト数が異なるため、DCHECK が有効なビルドではミュート操作前の初期化でも停止する。
これは既存のステレオ初期化の問題であり、本 issue の変更対象には加えない。
実機検証は stereo 送信・再生を開始できるビルドで行い、ビルド設定と、この制約で検証できなかった条件を明記する。

## 完了条件

- `RemoteIOAudioUnit::SetMicrophoneMute` が入力 bus の EnableIO を要求に従って設定し、実際の成功 / 失敗を返す。
- ステレオ送信中にハードミュートでマイクインジケーターが消え、マイク捕捉が止まる。unmute で復帰する。
- 切替時の再初期化による一時中断後に stereo 再生が再開し、mute の継続中も再生できる。
- mono（VPIO）のハードミュートと既存の初期マイクミュートの挙動が変わらない。
  0014 が適用済みの場合は、入力不要設定が mute / unmute より優先される。
- 実機での検証条件と結果が記録されている。

## 対応状況

2026-09-07 時点で、`RemoteIOAudioUnit::SetMicrophoneMute` の no-op を入力 bus の EnableIO 制御に置き換えた。
mute で `0`、unmute で `1` を設定し、出力 bus の設定は変更しない。
`AudioUnitSetProperty` が失敗した場合は、mute / unmute の要求と OSStatus を英語のログに記録し、`false` を返す。
pause / resume の既存の再初期化フローと、VPIO の実装は変更していない。

`RTCStereoAudioOutputTests` に、実際の `AudioDeviceIOS` を observer とする RemoteIO の回帰テストを追加した。
Core Audio から入力と出力の EnableIO を読み戻し、同一要求の繰り返しと反転で入力 I/O が切り替わり、出力 I/O が有効なままであることを検査する。
I/O は開始しないテストであり、モックやスタブは使用していない。

確認済みの項目:

- upstream `1f975dfd761af6e5d76d28333191973b258d82a8` に、`ios_sdk` の全 24 パッチを既存の適用順と方法で適用できること
- Xcode 26.6 / iOS SDK 26.5 で、RemoteIO 実装と XCTest を実機向け・シミュレーター向けの debug / release 設定でコンパイルし、計 8 個のオブジェクトを生成できること
- 既存の Python テスト 15 件と差分の空白検査の成功
- 2 系統で 3 周の差分レビューを行い、致命的・重要な指摘が 0 件であること。軽微なコメントと説明の改善 3 件を反映した

ローカルで未検証の項目:

- `ios_sdk` のフルビルドと、新規 XCTest のリンク・実行
- 実機の sendrecv / sendonly での pause / resume の戻り値、マイク捕捉とインジケーターの停止・復帰、切替後とミュート中の stereo 再生
- mono（VPIO）、Bluetooth、割り込み、マイク権限の条件別の実機動作
- 未実装の 0014 が導入された後の入力不要設定との共存

既存のビルド設定は `rtc_include_tests=false` のため、CI のビルド成功だけでは追加した XCTest の実行成功を確認できない。
`rtc_include_tests=true` にした `sdk_unittests` での実行と、上記の実機検証が必要である。
接続可能な iOS 実機が確認できておらず、完了条件を満たしていないため、open のままとし `Completed:` は未設定とする。
ユーザー承認により、新規 XCTest の実行と実機検証を後続作業として残し、draft PR を作成してフルビルドを CI で確認する。
フルビルドの結果は draft PR に記録する。
