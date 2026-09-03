# Android のステレオ音声受信で libwebrtc パッチが必要になった場合の対応

- Created: 2026-09-03
- Completed:
- Branch: feature/add-android-stereo-audio-receive
- Polished: 2026-09-03

## 目的

Sora Android SDK での Android のステレオ音声受信を実機で成立させるために、上流の libwebrtc に手を入れる必要が生じた場合の受け皿を用意する。着手前提は sora-android-sdk 側の対応が完了しており、その状態でも実機イヤホンでステレオ再生が成立しないことが実機検証で確認された場合である。

Sora Android SDK 側の関連 issue は以下のとおり。

- shiguredo/sora-android-sdk 0022 (ステレオ音声受信の調査)
- shiguredo/sora-android-sdk 0081 (SoraAudioOption に AudioAttributes を追加する)
- shiguredo/sora-android-sdk 0082 (answer SDP の Opus fmtp に stereo=1 / sprop-stereo=1 を追記する)

ステレオ送信は対象外とする。送信は録音経路と Opus エンコーダで完結し、再生側の AudioAttributes を経由しないため、libwebrtc 標準の `JavaAudioDeviceModule.Builder#setUseStereoInput` + Sora 側の Opus `opus_params` 指定で成立する認識である。

## 現状

### libwebrtc の Android ADM は宣言 API までステレオ対応している

libwebrtc の Android ADM は Java 側の宣言 API までステレオ対応済みで、iOS の 0005 / 0006 で扱っているようなスタブ実装 (常に false 返し、Not implemented) は無い。以下は libwebrtc main 相当を対象に確認した事実である。

- `sdk/android/api/org/webrtc/audio/JavaAudioDeviceModule.java` の `Builder` に `setUseStereoInput(boolean)` / `setUseStereoOutput(boolean)` / `setAudioAttributes(AudioAttributes)` が存在する
- `sdk/android/src/java/org/webrtc/audio/WebRtcAudioTrack.java` の `channelCountToConfiguration(int channels)` は 2 の場合に `CHANNEL_OUT_STEREO` を返し、モノラル強制のコードは無い
- `sdk/android/src/jni/audio_device/audio_device_module.cc` の `AndroidAudioDeviceModule::StereoPlayoutIsAvailable` は生成時に受け取ったブール値をそのまま返す
- `sdk/android/src/jni/audio_device/aaudio_wrapper.cc` は `AAudioStreamBuilder_setChannelCount(builder, audio_parameters().channels())` でチャンネル数をそのまま渡す

### 受信経路で実機ステレオを潰す可能性がある箇所

Java 側 AudioTrack は生成時に固定の `AudioAttributes` を使う。`WebRtcAudioTrack.java` の以下がその起点である。

- `private static final int DEFAULT_USAGE = AudioAttributes.USAGE_VOICE_COMMUNICATION`
- `getAudioAttributes(AudioAttributes overrideAttributes)` はデフォルトで `setUsage(DEFAULT_USAGE)` と `setContentType(CONTENT_TYPE_SPEECH)` を組み立て、`overrideAttributes` が非 null のときのみ Usage / ContentType / Flags を上書きする
- `audioAttributes` フィールドは final でコンストラクタで固定され、実行時に差し替える API は無い

Android の AudioPolicy は `USAGE_VOICE_COMMUNICATION` + `CONTENT_TYPE_SPEECH` を通話音声として扱い、STREAM_VOICE_CALL 系のミキサへルーティングされる。この経路では出力デバイスや音源が 2ch であっても実質モノラルへダウンミックスされる可能性がある (実機検証未実施の推測)。この推測は sora-android-sdk 0022 の「SDP 書き換えで `WebRtcAudioTrackExternal.initPlayout` が `channels=2` を出すところまで到達しても実機イヤホンでステレオ受信できない」現象と整合する。

### AAudio 側 (本 issue のスコープ外)

`sdk/android/src/jni/audio_device/aaudio_wrapper.cc` は `AAudioStreamBuilder_setUsage` と `AAudioStreamBuilder_setContentType` を呼んでおらず、AAudio デフォルト (`USAGE_MEDIA` 相当) を使用する。AAudio 経路では USAGE 経由のダウンミックスの懸念は薄い。

Sora Android SDK は現状 `JavaAudioDeviceModule` を利用するため、通常は Java の `AudioTrack` 経路 (上記の USAGE_VOICE_COMMUNICATION 側) を通り、AAudio 経路は使わない。したがって本 issue のスコープは Java の `AudioTrack` 経路のみとし、AAudio 経路の挙動安定化 (`setUsage` / `setContentType` の明示指定など) が必要になった場合は別 issue を切る。

## 設計方針

1. **本 issue は前提条件が揃うまで着手しない**
   - shiguredo/sora-android-sdk 0081 (`SoraAudioOption` への `audioAttributes` 追加) と 0082 (answer SDP の Opus fmtp 書き換え) の実装が完了していること
   - `SoraAudioOption.audioAttributes` に `USAGE_MEDIA` + `CONTENT_TYPE_MUSIC` を渡した状態で実機検証が実施されていること
   - 実機検証で受信ステレオが成立するなら、本 issue は closed する
2. **受信ステレオが成立しなかった場合に選ぶパッチ案**
   - (a) `WebRtcAudioTrack.java` の `DEFAULT_USAGE` / デフォルト `CONTENT_TYPE` を切り替え可能にする。デフォルトは既存挙動のまま維持し、SDK 側から明示的に切り替えられる形が望ましい
   - (b) 実行時に `AudioAttributes` を差し替えられる公開 API を `JavaAudioDeviceModule` に追加する (`WebRtcAudioTrack` の再初期化を伴うため大がかりになる)
   - AAudio 経路 (`aaudio_wrapper.cc` の `setUsage` / `setContentType` 明示指定) は Sora Android SDK が通らないため本 issue の対象外とする
3. **既定挙動を破壊しないこと**
   - 通常の VoIP 用途 (モノラル VoIP、Bluetooth SCO ルーティング、通話音量) の挙動を壊さないパッチ形態にする
   - ステレオ有効時のみ挙動を変える形を優先する

## 完了条件

- shiguredo/sora-android-sdk 0081 / 0082 の対応後の実機検証結果が揃っていること
- 実機検証で libwebrtc パッチが不要と判明した場合は、その結果を本 issue に記録して closed にすること
- 必要と判明した場合は上記 (a) / (b) のいずれかを `patches/` に追加し、`run.py` の `PATCHES` dict の Android ビルドターゲットに登録すること。core 側 (`sdk/android/api/org/webrtc/audio/` や `sdk/android/src/java/org/webrtc/audio/` 配下) を触るため、`android` と `android_sdk` の両方に登録する
- 通常の VoIP 用途 (モノラル VoIP) の実機動作にレグレッションが無いこと
- 追加したパッチの解説を `patches/README.md` に記載すること
- CHANGES.md に追記があること

## 変更履歴案

- [ADD] Android のステレオ音声受信のために libwebrtc の Android AudioTrack の AudioAttributes を差し替えるパッチを追加する
