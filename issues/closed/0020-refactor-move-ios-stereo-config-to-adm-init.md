# iOS の stereo 設定を ADM の init に渡し遅延フラグを削除する

- Created: 2026-09-10
- Completed: 2026-09-11
- Branch: feature/refactor-move-ios-stereo-config-to-adm-init
- Polished: {YYYY-MM-DD}

## 目的

stereo 設定を「factory へ渡す前の setter」ではなく `RTCAudioDeviceModule` の init 引数にし、`AudioDeviceModuleIOS` の可変遅延フラグ `stereo_playout_enabled_on_init_` と順序制約を削除する。構築時に確定させることで、`bypass_voice_processing_` と同じ扱いに揃える。

## 現状

- `ios_stereo_audio_output.patch` が `RTCAudioDeviceModule` に `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` と、受け渡し後の設定変更を拒む `_nativeAudioDeviceModuleRetrieved` ガードを追加している。
- `AudioDeviceModuleIOS` に可変の `stereo_playout_enabled_on_init_` があり、`SetStereoPlayout` が未初期化時にフラグへ保存し、`Init()` で適用する。`AudioDeviceModuleIOS::SetStereoPlayout` は未初期化ケースを特別扱いしている。
- `CreateAudioDeviceModule` は `bypass_voice_processing` のみを引数に取る。
- sora-ios-sdk は `RTCAudioDeviceModule(bypassVoiceProcessing:)` を生成した直後に `setStereoPlayoutEnabled(true)` を呼んでから factory に渡す。

## 設計方針

- `RTCAudioDeviceModule` の init を `initWithBypassVoiceProcessing:stereoPlayoutEnabled:` にする。
- `CreateAudioDeviceModule` / `AudioDeviceModuleIOS` のコンストラクタに stereo を追加し、構築時設定として保持する (`bypass_voice_processing_` と同じ形)。`stereo_playout_enabled_on_init_` は可変フラグでなく構築時設定にする。
- `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を削除する。SDK は自分で渡した値を知っているため getter も不要になる。
- 外部から未初期化の ADM に `SetStereoPlayout` を呼ぶ経路が無くなるため、`SetStereoPlayout` の未初期化特別扱いを削除する。
- `_nativeAudioDeviceModuleRetrieved` は「同じ ADM を複数 factory に渡さない」ガードとしてのみ残す (設定変更拒否の役割は削除する)。

## テスト方針

- `python3 run.py revert ios` / `revert ios_sdk` が成功することを確認する。
- `sdk_unittests` の `RTCStereoAudioOutputTests` を init 引数ベースに更新して実行する。
- sora-ios-sdk 側の `StereoAudioOutputTests` を更新する。

## 完了条件

- stereo が ADM の構築時に確定し、`stereo_playout_enabled_on_init_` が可変遅延フラグでなくなっている。
- `setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` が削除されている。sora-ios-sdk の呼び出し更新は別 issue で扱う。
- `revert ios` / `revert ios_sdk` と XCTest が通る。
- `CHANGES.md` に変更内容を追記している。

## 解決方法

stereo 設定を `RTCAudioDeviceModule` の init 引数にし、`AudioDeviceModuleIOS` の構築時設定にした。

- `RTCAudioDeviceModule` の init を `initWithBypassVoiceProcessing:stereoPlayoutEnabled:` にし、`setStereoPlayoutEnabled:` / `stereoPlayoutEnabled` を削除した。
- `CreateAudioDeviceModule` / `CreateMutedDetectAudioDeviceModule` / `AudioDeviceModuleIOS` のコンストラクタに stereo 引数を追加した。
- `AudioDeviceModuleIOS` の `stereo_playout_enabled_on_init_` (可変) を `stereo_playout_enabled_` (構築時) にし、`Init()` で適用するようにした。`SetStereoPlayout` の未初期化特別扱いを削除し、`CHECKinitialized_()` に置き換えた。
- `_nativeAudioDeviceModuleRetrieved` は「同じ ADM を複数 factory に渡さない」ガードとして残した。
- `RTCStereoAudioOutputTests` を新しい init に更新し、setter の変更可否を検証するテストを削除した。

検証結果:

- `python3 run.py revert ios` / `revert ios_sdk` が成功した。
- `sdk_unittests` を iPhone 16 Pro / iOS 18.1 Simulator で実行し、`RTCStereoAudioOutputTests` 6 件、`RTCManualAudioInputTests` 11 件、`RTCAudioDeviceModuleThreadingTests` がすべて成功した。

sora-ios-sdk 側の追従 (`RTCAudioDeviceModule(bypassVoiceProcessing:)` と `setStereoPlayoutEnabled` の init 引数化) は別 issue で扱う。
