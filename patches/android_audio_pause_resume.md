# android_audio_pause_resume.patch の解説

このドキュメントは、`android_audio_pause_resume.patch` の目的・変更点をまとめたものです。

## 目的

- Android 向け JavaAudioDeviceModule にマイク録音の一時停止／再開機能を追加し、アプリから pauseRecording() / resumeRecording() を呼び出せるようにしました。これにより実機でマイクインジケータを消灯するミュートが可能になります。

## 変更点の概要

### パブリック API の拡張

JavaAudioDeviceModule に pauseRecording() / resumeRecording() メソッドを追加しました。
ネイティブ ADM が生成済みで pause/resume をサポートしている場合は JNI 経由で実行します。未対応バックエンド(AAudio/OpenSLES)では即座に false を返します。

### WebRtcAudioRecord の内部状態管理

- RecordingState enum を導入しました。

```
- IDLE: 初期状態
- RECORDING: 録音中。 startRecording() での録音開始および、resumeRecording() による録音復帰
- PAUSED: pauseRecording() により録音一時停止
- STOPPED: stopRecording() により録音終了
```

- startRecording() / stopRecording() / pauseRecording() / resumeRecording() それぞれの実行時に内部状態のチェック・更新を行います。
- stopRecording() 内で実装されていた、stopAudioThread(...) を共通化し、pause/resume 失敗時にもスレッド停止・リソース解放を適切に行います。
pause/resume 失敗時はエラーログに加えて STOPPED へ状態遷移させます。

### JNI／ネイティブ層の更新

- AudioInput インターフェースに PauseRecording() / ResumeRecording() / SupportsPauseResume() を追加しました。
AndroidAudioDeviceModule が pause/resume を呼び出す際に SupportsPauseResume() により実行可否を判定します。
- AudioRecordJni で pause/resume を実装しました。ワーカースレッドからの呼び出しでも安全なように AttachCurrentThreadIfNeeded() を使用しています。
AAudioRecorder や OpenSLESRecorder では未対応として -1 が返ります。JavaAudioDeviceModule からの呼び出しには false を返し、ログで未対応を通知します。
- JNI ブリッジ（java_audio_device_module.cc）に PauseRecording() / ResumeRecording() / SupportsPauseResume() に対応するネイティブメソッドを追加しました。

### Android からの呼び出し経路

以下はpause の場合。resume においても同様の経路となります。

1. Java: JavaAudioDeviceModule.pauseRecording()
2. JNI: JNI_JavaAudioDeviceModule_nativePauseRecording(...)
3. C++: AndroidAudioDeviceModule::PauseRecording()
4. C++: AudioRecordJni::PauseRecording()
5. Java: WebRtcAudioRecord.pauseRecording()

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
```

- 両メソッドとも Boolean を返します。true なら成功、false なら未対応（AAudio, OpenSL ES など）または失敗となりますのでログを確認してください。
- 内部では録音スレッドの停止／再開を行うため、UI スレッドで直接呼ぶと join 待ちでブロックされる可能性が高いです
