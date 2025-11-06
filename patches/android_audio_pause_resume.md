# android_audio_pause_resume.patch の解説

このドキュメントは、`android_audio_pause_resume.patch` の目的・変更点をまとめたものです。
このパッチは WebRtcAudioRecord にマイク録音の一時停止/再開機能を追加します。

## 目的

- Android 向け JavaAudioDeviceModule にマイク録音の一時停止／再開機能を追加し、アプリから pauseRecording() / resumeRecording() を呼び出せるようにしました。これにより実機でマイクインジケータを消灯するミュートが可能になります。

## 変更点の概要

### パブリック API の拡張

JavaAudioDeviceModule に pauseRecording() / resumeRecording() メソッドを追加しました。
成功時に true、失敗時に false が返されます。

### WebRtcAudioRecord の内部状態管理

- RecordingState enum を導入しました。

```
- IDLE: 初期状態
- RECORDING: 録音中。 startRecording() での録音開始および、resumeRecording() による録音復帰
- PAUSED: pauseRecording() により録音一時停止
- STOPPED: stopRecording() により録音終了
```

状態遷移は以下のようになります。

```
IDLE → RECORDING (startRecording)
RECORDING → PAUSED (pauseRecording)
PAUSED → RECORDING (resumeRecording)
RECORDING → STOPPED (stopRecording)
PAUSED → STOPPED (stopRecording or エラー時)
```

- startRecording() では録音開始成功時、RECORDING への状態の更新を行います。
- stopRecording() ではリソース開放後、STOPPED への状態の更新を行います。
- pauseRecording() では stopRecording() の処理と同様に audioThread の停止、PAUSED への状態の更新を行います。リソース解放は行いません。
- resumeRecording() では startRecording() の処理と同様に、audioRecord.startRecording() の実行と、audioThread の生成と開始を行います。
  - audioRecord.startRecording() の失敗(IllegalStateException)、または audioRecord.getRecordingState() が意図しない値だった場合のエラーハンドリングを startRecording() と同様に行いますが、追加でリソースの解放と STOPPED への状態の更新を行います。

### Android からの呼び出し経路

以下は pause の場合。resume においても同様の経路となります。

1. Java: JavaAudioDeviceModule.pauseRecording()
2. Java: WebRtcAudioRecord.pauseRecording()

## 利用方法

PeerConnectionFactory を初期化時に JavaAudioDeviceModule を生成し、Factory に渡しておきます。
(既存で実装されている場合は変更の必要はありません)

JavaAudioDeviceModule のインスタンスをアプリ側で保持しておき、録音を一時停止したいタイミングで pauseRecording()、再開時に resumeRecording() を呼びます。

``` kotlin
// 初期化例
val adm = JavaAudioDeviceModule.builder(appContext)
    .createAudioDeviceModule()
val factory = PeerConnectionFactory.builder()
    .setAudioDeviceModule(adm)
    .createPeerConnectionFactory()

// pause/resume（UI スレッド以外で実行推奨）
val paused = adm.pauseRecording()
val resumed = adm.resumeRecording()

// エラーハンドリングの例
if (!paused) {
    // 未対応バックエンド、または既に一時停止済み、録音未開始などの場合
    Log.w(TAG, "pauseRecording failed. Check logcat for details.")
}
```

- 両メソッドとも Boolean を返します。true なら成功、false なら失敗となりますのでログを確認してください。
- 内部では録音スレッドの停止／再開を行うため、UI スレッドで直接呼ぶと join 待ちでブロックされる可能性が高いです
