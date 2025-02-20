# 変更履歴

- RELEASE
  - タグの追加
- UPDATE
  - 下位互換がある変更
- ADD
  - 下位互換がある追加
- CHANGE
  - 下位互換のない変更
- FIX
  - バグ修正

VERSION ファイルを上げただけの場合は変更履歴記録は不要。
パッチやビルドの変更、リリース時のみ記録すること。

## support/simulcast-multi-codec

### 126.6478.1.0-simulcast-multi-codec.0 (2024-08-05)

- [FIX] r0.active=false, r1.active=true の時に実行時エラーになってたのを修正
  - @melpon
- [FIX] Reconfigure が走った時に実行時エラーになってたのを修正
  - @melpon

### 126.6478.1.1 (2024-07-11)

- [FIX] サイマルキャストマルチコーデックで、r0 を H264、r1 を VP8 にすると落ちるのを修正
  - @melpon

### 122.6261.1.3 (2024-04-24)

- [FIX] サイマルキャストマルチコーデックでビットレートが低いと高いレイヤーにビットレートが割り当てられなくなるのを、無理やり出力するように修正する
  - @melpon

### 122.6261.1.2

- [FIX] rtx = false 時にエラーになってたのを修正
  - @melpon
- [FIX] エンコーダの実装によってエラーが起きてたのを修正
  - @melpon

### 122.6261.1.1

- [ADD] マルチコーデックサイマルキャスト対応のパッチを追加する

## 2024-09-20
- タイムライン型の変更履歴
- 必ず一番上に書く
- リリース時には [RELEASE] を追加する

## 例

- 2024-03-01 [RELEASE] m127.0.0.1
  - @voluntas
- 2023-02-01 [ADD] h266.patch を追加
  - @melpon
- 2022-01-01 [FIX] h265.patch のバグを修正
  - @melpon

## タイムライン

- 2025-02-07 [RELEASE] m132.6834.5.8
  - @melpon
- 2025-02-07 [CHANGE] RTCDefaultVideoEncoderFactory が返すフォーマットの一覧を scalability_mode に対応する
  - @melpon
- 2025-02-03 [RELEASE] m132.6834.5.7
  - @zztkm
- 2025-02-03 [RELEASE] m132.6834.5.6
  - @zztkm
- 2025-01-31 [UPDATE] iOS の scaleResolutionDownTo のプロパティの setter を assign から copy に変更する
  - @zztkm
- 2025-01-30 [RELEASE] m132.6834.5.5
  - @melpon
- 2025-01-30 [FIX] Windows のビルド依存に api:enable_media_with_defaults を追加し忘れていた
  - @melpon
- 2025-01-30 [RELEASE] m132.6834.5.4
  - @melpon
- 2025-01-30 [ADD] ビルド依存に api:enable_media_with_defaults を追加
  - @melpon
- 2025-01-27 [RELEASE] m132.6834.5.3
  - @torikizi
- 2025-01-25 [ADD] Android と iOS の RtpEncodingParameters に scaleResolutionDownTo を定義する
  - @melpon
- 2025-01-23 [RELEASE] m132.6834.5.2
  - @miosakuma
- 2025-01-23 [FIX] apt_install_x86_64.sh の `apt-get update` のコメントアウトを解除
  - apt-get install で vim のパッケージが 404 エラーになったため
  - @miosakuma
- 2025-01-22 [FIX] kVTVideoEncoderSpecification_RequiredLowLatency を h265_ios.patch から削除する
  - libwebrtc を組み込んだ iOS アプリを App Store Connect にアップロードが失敗する問題への対処
  - 非公開シンボルである kVTVideoEncoderSpecification_RequiredLowLatency を参照しているとのエラーメッセージであったため、参照している箇所を削除した
  - @miosakuma
- 2025-01-14 [RELEASE] m132.6834.5.1
  - @miosakuma
- 2024-12-20 [RELEASE] m132.6834.5.0
  - @melpon @torikizi
- 2024-12-20 [RELEASE] m132.6834.4.0
  - ios_proxy.patch を libwebrtc 側の処理変更に追従して修正する
  - @melpon
- 2025-01-10 [RELEASE] m130.6723.2.1
  - @miosakuma
- 2025-01-10 [CHANGE] libwebrtc の iOS Simulcast 対応が不十分だったので、`ios_simulcast.patch` パッチを復活させた。 scalabilityMode の型が変更になっている。詳細は[こちら](patches/README.md#ios_simulcastpatch)
  - @tnoho
- 2024-12-14 [RELEASE] m131.6778.4.0
  - apt_install_arm.sh の `apt update` のコメントアウトを解除
  - @torikizi
- 2024-11-25 [RELEASE] m131.6778.3.1
  - @melpon
- 2024-11-25 [FIX] `*.inc` ファイルもリリースに含める
  - @melpon
- 2024-11-25 [RELEASE] m131.6778.3.0
  - @torikizi
- 2024-11-24 [ADD] windows_add_optional.patch を追加
  - @tnoho
- 2024-11-24 [FIX] arm_neon_sve_bridge.patch を修正
  - m131 で libvpx 向けだった arm_neon_sve_bridge.patch と同様の対応が libaom にも必要になったため修正
  - @tnoho
- 2024-10-18 [RELEASE] m129.6668.1.1
  - @melpon
- 2024-10-18 [ADD] fix_moved_function_call.patch を追加
  - @melpon
