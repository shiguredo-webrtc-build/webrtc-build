# 変更履歴

- UPDATE
  - 下位互換がある変更
- ADD
  - 下位互換がある追加
- CHANGE
  - 下位互換のない変更
- FIX
  - バグ修正

VERSION ファイルを上げただけの場合は変更履歴記録は不要。
パッチやビルドの変更のみ記録すること。

## 2024-09-20

- [CHANGE] Ubuntu18.04 armv8 のビルドを削除
  - @torikizi

## 2024-09-19

- [ADD] Ubuntu 24.04 armv8 に対応
  - @melpon
- [FIX] Windows でビルドエラーが発生するのを `fix_windows_boringssl_string_util.patch` のパッチを当てて修正
  - これは m130 か m131 あたりで不要になるはず
  - @melpon

## 2024-08-19

- [UPDATE] GitHub Actions Android のビルド環境を Ubuntu 22.04 に上げる
  - @zztkm

## 2024-06-21

- [ADD] Ubuntu 24.04 に対応
  - @melpon
- [FIX] 生成した VERSIONS ファイルの指すコミットが shiguredo-patch パッチ適用後のコミットになっていたのを修正
  - @melpon

## 2024-05-20

- [CHANGE] --webrtc-fetch, --webrtc-fetch-force オプションを削除
  - 代わりに run.py fetch コマンドを利用する
  - @melpon
- [ADD] run.py に fetch コマンドと revert コマンドと diff コマンドを追加
  - @melpon

## 2024-05-06

- [ADD] run.py にバージョン操作系のコマンド `version_list` と `version_update` を追加
  - @melpon

## m124.6367.0.0

- [CHANGE] ios / macos_arm64 向けに `revert_asm_changes.patch` を追加
  - @torikizi

## m123.6312.3.5

- [FIX] H.265 の映像を受信した際に、最初の映像が描画されるまでに時間がかかることがある問題を修正する
  - @enm10k

## m123.6312.3.4

- [FIX] macOS で H.265 の受信が動作していなかった問題を修正する
  - @enm10k

## m123.6312.3.3

- [FIX] H.265 受信時にクラッシュする問題を修正する
  - @enm10k

## m123.6312.3.2

- [UPDATE] support/m122.6261 ブランチの変更を取り込む
  - ubuntu-20.04_x86_64, ubuntu-22.04_x86_64, windows_x86_64 のビルドに h265.patch を適用する
  - @enm10k
- [FIX] m122 のリリースのみに適用されていた fix_typo_in_deprecated_attribute.patch を m123 にも適用する
  - @enm10k

## 122.6261.0.2

- [UPDATE] ubuntu-20.04_x86_64, ubuntu-22.04_x86_64, windows_x86_64 のビルドに h265.patch を適用する
  - @enm10k

## 122.6261.0.1

- [FIX] リリース・バイナリを利用した Windows 向けのビルドが `error C3827: standard attribute 'deprecated' may have either no arguments or one string literal` というエラーになる問題を修正するパッチを追加する
  - @enm10k

## m120.6099.1.2

- [ADD] DEPS ファイルを追加して、依存するバージョンを明示する
  - @melpon

## m119.6045.2.1

- [ADD] H.265 パッチを追加する WebRTC 119.6045.2.0 / WebKit f92a593e ベース
  - @tnoho

## m114.5735.2.2

- [CHANGE] iOS を scalability mode に対応する
  - @szktty
- [FIX] iOS のサイマルキャストが VP9 と AV1 で動作しない問題を修正する
  - @szktty

## m114.5735.0.0

- [CHANGE] ビルド全体で例外を有効にする
  - @melpon

## m111.5563.4.3

- [ADD] Windows で rtc::FileRotatingLogSink が含まれなくなっていたので、依存に rtc_base:log_sinks を追加する
  - @melpon

## m110.5481.4.1

- [UPDATE] deprecated になった actions/create-release と actions/upload-release の利用をやめて softprops/action-gh-release を利用する
  - @melpon
- [UPDATE] GitHub Actions の各種バージョンを上げる
  - @melpon
- [CHANGE] macos_x86_64 のビルドを削除
  - @melpon
- [CHANGE] ubuntu-18.04_x86_64 のビルドを削除
  - @melpon
- [CHANGE] Docker でのビルドを削除
  - @melpon
- [ADD] Windows の高負荷環境で録音デバイスの初期化に失敗する問題を修正するパッチ windows_fix_audio_device.patch を追加
  - @melpon

## m111.5563.0.0

- [CHANGE] 不要になった macos_h264_encoder.patch を削除
  - @torikizi
- [CHANGE] 不要になった windows_fix_towupper.patch を削除
  - @torikizi

## m103.5060.5.0

- [ADD] iOS で Proxy を利用可能にする
  - @melpon

## m102.5005.7.6

- [FIX] Android の Proxy 対応で PeerConnectionFactoryProxy を使っていなかったのを修正
  - @melpon

## m102.5005.7.5

- [ADD] ubuntu-22.04_x86_64 追加
  - @melpon

## m102.5005.7.4

- [FIX] macOS のビルドでも Xcode Clang を利用する
  - @melpon

## m102.5005.7.3

- [ADD] Android で Proxy を利用可能にする
  - @melpon

## m102.5005.7.2

- [FIX] macOS はホストの libc++ を利用する
  - @melpon

## m102.5005.7.1

- [FIX] iOS のビルドに、 Xcode に含まれる clang を使用する
  - こちらのパッチを作成するにあたり、以下の記事とパッチを参考にしました
  - <https://webrtchacks.com/the-webrtc-bitcode-soap-opera-saul-ibarra-corretge/>
  - <https://github.com/jitsi/webrtc/releases/tag/v100.0.0>
  - @enm10k

## m101.4951.5.1

- [ADD] ubuntu-20.04_armv8 を追加
  - @tnoho
- [FIX] Android の HardwareVideoEncoder に実装された解像度の制限を回避するパッチを追加する
  - @enm10k

## m96.4664.2.1

- [FIX] android_simulcast.patch を修正して、 SimulcastVideoEncoderFactory の fallback に null を渡せるようにする
  - @enm10k

## m93.4577.8.1

- [FIX] third_party/libjpeg_turbo の jpeglibmangler.h が機能していない問題を修正するパッチを追加する
  - @enm10k

## m92.4515.9.1

- [CHANGE] libwebrtc_onremovetrack.aar を廃止して、 libwebrtc.aar に android_onremovetrack.patch を適用する
  - @enm10k

## m91.4472.9.3

- [ADD] 各環境のバイナリに zlib を追加
  - @melpon

## m91.4472.9.2

- [ADD] Windows のバイナリに zlib を追加
  - @melpon

## m90.4430.3.2

- [CHANGE] iOS にサイマルキャスト対応のパッチを追加
  - @szktty @enm10k

## m90.4430.3.1

- [FIX] iOS で発生したロックの競合を解消する
  - @melpon @enm10k

## m89.4389.5.6

- [CHANGE] Android にサイマルキャスト対応のパッチを追加
  - @szktty @enm10k

## m89.4389.5.5

- [FIX] Android で SEGV することがあるのを修正
  - @melpon

## m89.4389

- [CHANGE] ubuntu-18.04_armv8 向けに `libjpeg_mangle.patch` を追加
  - @tnoho @melpon

## m88.4324.3.1

- [ADD] Apple Silicon 用ビルド (macos_arm64) を追加
  - @hakobera
- [CHANGE] Apple Silicon 対応に伴い、既存の macos を macos_x86_64 に変更する
  - @hakobera

## m88.4324.0.0

- [CHANGE] Linux の x86_64 にも `rtc_use_pipewire=false` を設定
  - @melpon
- [FIX] armv6 用パッチの修正
  - @melpon

## m86.4240.1.2 (2020/8/31)

- [ADD] centos-8_x86_64 ビルドを追加

  - @melpon

- [FIX] macOS でサイマルキャストを行うとセグフォが起きていたのを修正
  - @melpon

## m84.4147.11.3 (2020/8/12)

- [FIX] Windows に NOTICE ファイルが入っていなかったのを修正
  - @melpon

## m84.4147.11.2 (2020/8/9)

- [ADD] iOS 用のパッチを追加
  - @melpon

## m84.4147.11.1 (2020/8/5)

- [ADD] iOS 用ビルドを追加
  - @melpon

## m84.4147.7.3 (2020/6/23)

- [FIX] macOS 版の .a 内のファイル名が 15 文字で切られていたのを修正
  - @melpon

## m84.4147.7.2 (2020/6/16)

- [ADD] raspberry-pi-os_armv8 を追加
  - @melpon

## m84.4147.7.0 (2020/6/15)

- [CHANGE] raspbian-buster を raspberry-pi-os に変更する
  - @melpon

## m83.4103.12.2 (2020/5/26)

- [ADD] AAR パッケージの削除処理を Revert して Android に AAR を追加する
  - @enm10k

## m83.4103.12.1 (2020/5/16)

- [ADD] Android 用ビルドを追加
  - @melpon

## m83.4103.9.0

- [UPDATE] WebRTC のバージョンを 4103@{#9} に上げる
  - @voluntas

## m83.4103.2.0

- [UPDATE] WebRTC のバージョンを 4103@{#2} に上げる
  - @voluntas

## m81.4044.13.2

m81.4044.13.0,1 はリリースミスのためスキップ。

- [UPDATE] ビルド時にライセンスの生成を行う
  - @melpon
- [UPDATE] WebRTC のバージョンを 4044@{#13} にもどす
  - @voluntas

## m81.4044.11.0

- [UPDATE] WebRTC のバージョンを 4044@{#11} に上げる
  - @voluntas

## m81.4044.10.0

- [FIX] enable_libaom_decoder=false にする
  - @tnoho @melpon
- [FIX] enable_libaom_decoder は deprecated なので enable_libaom=false にする
  - @melpon
- [FIX] ubuntu-18.04_armv8 の rootfs が Ubuntu 16.04 になっていたのを修正
  - @melpon
- [UPDATE] WebRTC のバージョンを 4044@{#10} に上げる
  - @voluntas

## m81.4044.9.0

- [UPDATE] WebRTC のバージョンを 4044@{#9} に上げた
  - @voluntas

## m81.4044.7.0

- [UPDATE] WebRTC のバージョンを 4044@{#7} に上げた

## m80.3987.6.0

- [UPDATE] WebRTC のバージョンを 3987@{#6} に上げた

## m80.3987.2.2

- [FIX] Windows 版に 4K パッチが適用されていなかったのを修正

## m80.3987.2.1

- [FIX] Windows 版の VERSIONS ファイルのフォーマットが UTF-8 になっていなかったのを修正

## m80.3987.2.0

- [UPDATE] WebRTC のバージョンを 3987@{#2} に上げた
- [UPDATE] WebRTC バージョンの命名ルールを変更

## m79.5.4

- [ADD] バイナリの `VERSIONS` にいくつかのバージョン情報を追加

## m79.5.3

- [ADD] ubuntu-16.04_x86_64 を追加
- [ADD] ubuntu-16.04_armv7 を追加

## m79.5.2

- [ADD] バイナリにライセンスファイルを追加

## m79.5.1

- [CHANGE] H264 を使わないようにする
