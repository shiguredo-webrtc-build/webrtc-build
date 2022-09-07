# パッチ解説

## ライセンス

これらのパッチはすべて Apache License 2.0 です。これらのパッチを利用する場合にはライセンスを守ってご利用ください。

```
Copyright 2019-2022, Wandbox LLC (Original Author)
Copyright 2019-2022, tnoho (Original Author)
Copyright 2019-2022, Shiguredo Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## 4k.patch


## add_dep_zlib.patch


## android_fixsegv.patch

Android にて映像フレームの処理時にクラッシュするいくつかの現象を修正するパッチ。

同等の機能が本家に実装されるか、 PR を出して取り込まれたら削除する。

## android_simulcast.patch

Android でのサイマルキャストのサポートを追加するパッチ。この実装は C++ の `SimulcastEncoderAdapter` の簡単なラッパーであり、既存の仕様に破壊的変更も行わない。

以下の API を追加する。

- `SimulcastVideoEncoder`
- `SimulcastVideoEncoderFactory`

同等の機能が本家に実装されるか、 PR を出して取り込まれたら削除する。

## android_webrtc_version.patch

Android API に libwebrtc のビルド時のバージョンを取得する API を追加する。

以下の API を追加する。

- `WebrtcBuildVersion`

同等の機能が本家に実装されるか、 PR を出して取り込まれたら削除する。

## android_hardware_video_encoder.patch

解像度が16の倍数でない場合、 HardwareVideoEncoder 初期化時などのチェックでエラーが発生するようになった。  
Android CTS では解像度が16の倍数のケースしかテストされておらず、かつ、解像度が16の倍数でない映像を受信した際に問題が発生する端末があったことが理由で、上記のチェックが実装された。

参照: https://webrtc-review.googlesource.com/c/src/+/229460

このパッチでは、 Sora Android SDK 側でチェックを無効化する選択肢を提供するために、 libwebrtc に実装されたチェックを無効化している。  
チェックを無効化するオプションがメインストリームに実装された場合、このパッチは削除できる。  
https://bugs.chromium.org/p/webrtc/issues/detail?id=13973

## android_proxy.patch

Android に Proxy を設定する機能を入れるパッチ。
以下のように利用する。

```java
// Builder で setProxy を呼ぶことで Proxy を設定できる
PeerConnectionDependencies dependencies = PeerConnectionDependencies
    .builder(observer)
    .setProxy(ProxyType.HTTPS, "user-agent", "192.168.100.11", 3456, "username", "password");
    .createPeerConnectionDependencies();
// あとはいつも通り PeerConnection を生成する
PeerConnection pc = factory.createPeerConnection(rtcConfig, dependencies);
```

## ios_build.patch

iOS のビルドで発生した問題を修正するパッチ。  
以下の変更が含まれている。

- ビルドに Xcode に含まれる clang を使用する
  - libwebrtc で指定されている clang を使用した場合、 bitcode を有効にしてビルドしたアプリを App Store Connect にアップロードする際にエラーが発生する可能性がある
  - 参照: https://webrtchacks.com/the-webrtc-bitcode-soap-opera-saul-ibarra-corretge/
  - こちらの修正には https://github.com/jitsi/webrtc/releases/tag/v100.0.0 で公開されている 001-build.diff を参考にした
- bitcode を有効にした際に発生したビルド・エラーの修正

Xcode に含まれる clang を利用してビルドするオプションがメインストリームに実装された場合、このパッチは削除できる。  
https://bugs.chromium.org/p/webrtc/issues/detail?id=13925

## ios_manual_audio_input.patch

iOS でのマイク不使用時のパーミッション要求を抑制するパッチ。

同等の機能が本家に実装されるか PR を出して取り込まれたら削除するが、デフォルトの仕様の破壊的変更を含むので難しいと思われる。

以下に詳細を記載する。

### 内容

- 接続時のマイクのパーミッション要求を抑制する。

- マイクの初期化を明示的に行う API を追加する。
  パッチ適用後はマイクは自動的に初期化されない。

- ``AVAudioSession`` の初期化時に設定されるカテゴリを ``AVAudioSessionCategoryPlayAndRecord`` から ``AVAudioSessionCategoryAmbient`` に変更する。


### パッチ適用後の使い方

- マイクを使う場合は ``RTCAudioSession.initializeInput(completionHandler:)`` を実行してマイクを初期化する。
  - このメソッドはマイクが使用されるまで非同期で待ち、必要になったら初期化する。マイクの使用許可がなければユーザーにパーミッションを要求する。
  - 接続ごとに実行すること。接続が終了するとマイクは初期化前の状態に戻る。
  - 実行前に ``RTCAudioSessionConfiguration.webRTCConfiguration.category`` にマイクを使用可能なカテゴリをセットすること。 ``AVAudioSessionCategoryPlayAndRecord`` など。

- マイクを使わない場合は ``Info.plist`` にマイクの用途を記述する必要はない。


### `RTCAudioSession` のロックについて

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

## ios_simulcast.patch

iOS でのサイマルキャストのサポートを追加するパッチ。この実装は C++ の `SimulcastEncoderAdapter` の簡単なラッパーであり、既存の仕様に破壊的変更も行わない。

以下の API を追加する。

- `RTCVideoEncoderFactorySimulcast`
- `RTCVideoEncoderSimulcast`

同等の機能が本家に実装されるか、 PR を出して取り込まれたら削除する。

## macos_av1.patch


## macos_h264_encoder.patch


## macos_screen_capture.patch


## macos_simulcast.patch

## macos_use_xcode_clang.patch

大体 `ios_build.patch` と同じ内容のパッチ。

WebRTC が用意している clang でビルドすると、M1 Mac で実行時エラーが発生してしまう。
なので Xcode clang を利用してビルドするように修正する。

## nacl_armv6_2.patch


## ubuntu_nolibcxx.patch


## windows_build_gn.patch

C++17 で deprecated されているコードを多数含むために _SILENCE_ALL_CXX17_DEPRECATION_WARNINGS を追加している。

## ssl_verify_callback_with_native_handle.patch

WebRTC は Let's Encrypt のルート証明書を入れていないため、検証コールバックで検証する必要がある。
しかし WebRTC の検証コールバックから渡される `BoringSSLCertificate` には、検証に失敗した証明書だけが渡され、証明書チェーンが一切含まれていないため、正しく検証ができない。
なので BoringSSL のネイティブハンドル `SSL*` を `BoringSSLCertificate` に含めるようにする。

WebRTC は Let's Encrypt を含めていないので、Let's Encrypt の検証がうまくできないという点から本家に取り込んでもらうのは難しいと思われる。
証明書チェーンが利用できない、という話を起点にすれば取り込んでもらえるかもしれない。
ただし `SSL*` を渡すのは `OpenSSLCertificate` との兼ね合いを考えると筋が悪いので、本家用のパッチを書くのであれば清書する必要がある。
