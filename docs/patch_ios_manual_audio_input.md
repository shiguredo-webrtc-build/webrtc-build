# ios_manual_audio_input.patch

## 内容

- 接続時のマイクのパーミッション要求を抑制する。

- マイクの初期化を明示的に行う API を追加する。
  パッチ適用後はマイクは自動的に初期化されない。

- ``AVAudioSession`` の初期化時に設定されるカテゴリを ``AVAudioSessionCategoryPlayAndRecord`` から ``AVAudioSessionCategoryAmbient`` に変更する。


## パッチ適用後の使い方

- マイクを使う場合は ``RTCAudioSession.initializeInput(completionHandler:)`` を実行してマイクを初期化する。
  - このメソッドはマイクが使用されるまで非同期で待ち、必要になったら初期化する。マイクの使用許可がなければユーザーにパーミッションを要求する。
  - 接続ごとに実行すること。接続が終了するとマイクは初期化前の状態に戻る。
  - 実行前に ``RTCAudioSessionConfiguration.webRTCConfiguration.category`` にマイクを使用可能なカテゴリをセットすること。 ``AVAudioSessionCategoryPlayAndRecord`` など。

- マイクを使わない場合は ``Info.plist`` にマイクの用途を記述する必要はない。


## `RTCAudioSession` のロックについて

パッチに変更を加える際は `RTCAudioSession` をロックするタイミングに注意すること。
実行中に `RTCAudioSession` の設定を `configureWebRTCSession` などのメソッドで変更する場合はロックを行う必要がある。
ロックは `lockForConfiguration` で行い、 `unlockForConfiguration` で解除する。
たとえば `configureWebRTCSession` を適切にロックして実行するには、次のように前後を `lockForConfiguration` と `unlockForConfiguration` で囲む:

```
[session lockForConfiguration];
bool success = [session configureWebRTCSession:nil];
[session unlockForConfiguration];
```

`lockForConfiguration` はパッチ実装時は再帰的ロックで実装されていたが、現在は相互排他ロック (mutex) で実装されている。
複数の箇所 (他のスレッド含む) でロックした場合、最初のロックが `unlockForConfiguration` で解除されるまで他の箇所の実行が止まるので注意すべき。

パッチで追加する `-[RTCAudioSession startVoiceProcessingAudioUnit:]` は `RTCAudioSession` の設定を変更するためにロックを行う。
`startVoiceProcessingAudioUnit:` は `VoiceProcessingAudioUnit::Initialize()` (`sdk/objc/native/src/audio/voice_processing_audio_unit.mm`) から呼ばれる。
`VoiceProcessingAudioUnit::Initialize()` は次の複数の箇所から呼ばれている:

- `AudioDeviceIOS::InitPlayOrRecord()` (`sdk/objc/native/src/audio/audio_device_ios.mm`)
- `AudioDeviceIOS::HandleSampleRateChange()` (`sdk/objc/native/src/audio/audio_device_ios.mm`)
- `AudioDeviceIOS::UpdateAudioUnit()` (`sdk/objc/native/src/audio/audio_device_ios.mm`)

`AudioDeviceIOS::InitPlayOrRecord()` はロックした状態で `VoiceProcessingAudioUnit::Initialize()` を呼んでいるが、 `AudioDeviceIOS::HandleSampleRateChange()` は呼び出し元をたどってもロックされていない (と思われる) 。

また、 `AudioDeviceIOS::UpdateAudioUnit()` でもロックされていない。
メソッド内で `ConfigureAudioSession()` を呼んでいるが、 `ConfigureAudioSession()` 内でロックしている (`-[RTCAudioSession configureWebRTCSession:]` を呼んでいる) ので、もしこの時点でロックされていればデッドロックするはず。
したがって、この直後で呼ばれる `VoiceProcessingAudioUnit::Initialize()` はロックせずに呼ばれていることになる。

もしその実装が正しいのであれば、 `VoiceProcessingAudioUnit::Initialize()` の呼び出しはロック不要であり、 `AudioDeviceIOS::InitPlayOrRecord()` で行うロックは意味がない。
そこで、パッチでは `AudioDeviceIOS::InitPlayOrRecord()` 内で `VoiceProcessingAudioUnit::Initialize()` を呼ぶ前にロックを解除している。
次に該当のパッチを示す:

```
--- a/sdk/objc/native/src/audio/audio_device_ios.mm
+++ b/sdk/objc/native/src/audio/audio_device_ios.mm
@@ -913,8 +913,14 @@ bool AudioDeviceIOS::InitPlayOrRecord() {
       audio_unit_.reset();
       return false;
     }
+    // NOTE(enm10k): lockForConfiguration の実装が recursive lock から non-recursive lock に変更されたタイミングで、
+    // この関数内の lock と、 audio_unit_->Initialize 内で実行される startVoiceProcessingAudioUnit が取得しようとするロックが競合するようになった
+    // パッチ前の処理はロックの粒度を大きめに取っているが、以降の SetupAudioBuffersForActiveAudioSession や audio_unit_->Initialize は lock を必要としていないため、
+    // ここで unlockForConfiguration するように修正する
+    [session unlockForConfiguration];
     SetupAudioBuffersForActiveAudioSession();
     audio_unit_->Initialize(playout_parameters_.sample_rate());
+    return true;
   }
```
