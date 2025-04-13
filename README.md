# WebRTC-Build

[![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/shiguredo-webrtc-build/webrtc-build.svg)](https://github.com/shiguredo-webrtc-build/webrtc-build)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Actions Status](https://github.com/shiguredo-webrtc-build/webrtc-build/workflows/build/badge.svg)](https://github.com/shiguredo-webrtc-build/webrtc-build/actions)

## About Shiguredo's open source software

We will not respond to PRs or issues that have not been discussed on Discord. Also, Discord is only available in Japanese.

Please read <https://github.com/shiguredo/oss/blob/master/README.en.md> before use.

## 時雨堂のオープンソースソフトウェアについて

利用前に <https://github.com/shiguredo/oss> をお読みください。

## webrtc-build について

様々な環境向けの WebRTC のビルドを行って、そのバイナリを提供しています。

## ダウンロード

[リリース](https://github.com/melpon/webrtc-build/releases) からダウンロードしてください。

## パッケージに入っている内容

- WebRTC ライブラリ(webrtc.lib あるいは libwebrtc.a)
- WebRTC のインクルードヘッダ
- WebRTC のバージョン情報(コミットハッシュ)

## 現在提供しているビルド

- windows_x86_64
- windows_arm64
- macos_arm64
- raspberry-pi-os_armv6 (Raspberry Pi Zero, 1)
- raspberry-pi-os_armv7 (Raspberry Pi 2, 3, 4)
- raspberry-pi-os_armv8 (Raspberry Pi Zero 2, 3, 4)
- ubuntu-20.04_armv8
  - Jetson Xavier NX
  - Jetson AGX Xavier
  - Jetson Orin NX
  - Jetson AGX Orin
- ubuntu-22.04_armv8
  - Jetson AGX Orin
  - Jetson Orin Nano
- ubuntu-20.04_x86_64
- ubuntu-22.04_x86_64
- ubuntu-24.04_armv8
- ubuntu-24.04_x86_64
- android_arm64
- ios_arm64

### multi-codec-simulcast ビルドについて

- 対応ブランチは support/multi-codec-simulcast です
- 最新の libwebrtc 追従は有償で承っております
- バグ修正は有償で承っております

このブランチは libwebrtc への CL のバックポートを含んでいます。

### hololens2 ビルドについて

- 対応ブランチは support/hololens2 です
- 最新の libwebrtc 追従は有償で承っております
- バグ修正は有償で承っております

## 廃止

- macOS x86_64 廃止
  - 2022 年 6 月を持って廃止しました
- Ubuntu 18.04 x86_64 廃止
  - 2022 年 6 月を持って廃止しました
- Jetson 向け ARM 版 Ubuntu 18.04 廃止
  - 2023 年 4 月を持って廃止しました

## H.264 (AVC) と H.265 (HEVC) のライセンスについて

**時雨堂が提供する libwebrtc のビルド済みバイナリには H.264 と H.265 のコーデックは含まれていません**

### H.264

H.264 対応は [Via LA Licensing](https://www.via-la.com/) (旧 MPEG-LA) に連絡を取り、ロイヤリティの対象にならないことを確認しています。

> 時雨堂がエンドユーザーの PC /デバイスに既に存在する AVC / H.264 エンコーダー/デコーダーに依存する製品を提供する場合は、
> ソフトウェア製品は AVC ライセンスの対象外となり、ロイヤリティの対象にもなりません。

### H.265

H.265 対応は以下の二つの団体に連絡を取り、H.265 ハードウェアアクセラレーターのみを利用し、
H.265 が利用可能なバイナリを配布する事は、ライセンスが不要であることを確認しています。

また、H.265 のハードウェアアクセラレーターのみを利用した H.265 対応の SDK を OSS で公開し、
ビルド済みバイナリを配布する事は、ライセンスが不要であることも確認しています。

- [Access Advance](https://accessadvance.com/ja/)
- [Via LA Licensing](https://www.via-la.com/)

## ライセンス

Apache License 2.0

```
Copyright 2019-2025, Wandbox LLC (Original Author)
Copyright 2019-2025, tnoho (Original Author)
Copyright 2019-2025, Shiguredo Inc.

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

## タグやブランチ運用について

**かなり特殊なブランチ運用です**

- feature/m94.4606 のようにブランチを切ります
  - ブランチは削除してはいけません
  - 必ず feature 上でタグを打ちます
- feature ブランチがステーブルになったら master にマージします
- コミットポジションは右から 2 番目の値を変更します
- libwebrtc のコミットポジションは変更せずに何か変更がある場合は一番右の数値を増やします
  - m94.4606.0.0 から m94.4606.0.1 のようにする
- master ブランチは 同一または上位の feature ブランチにしかマージはしてはいけません
  - master が m94 なら m94 以上にだけマージして良い
- 下位へのマージは禁止しています
  - master が m94 なら m93 以下にマージはしていはいけない
- master ブランチへの変更を下位への反映したい場合は cherry-pick を利用します
- 下位へのみの反映は feature ブランチだけにします

### タグの読み方

`m124.6367.3.1` は m124 で、ブランチが `6367` で、コミットポジションが `3` で、
shiguredo/webrtc-build としてのリリース回数が `1` という意味です。

### コミットポジションについて

コミットポジションとは libwebrtc ブランチの [Cr-Commit-Position: refs/branch-heads/6367@{#3}](https://webrtc.googlesource.com/src.git/+/a55ff9e83e4592010969d428bee656bace8cbc3b) の `#3` の部分です。

たとえばこの 6367 は m124 のブランチ番号なのですが、libwebrtc にバックポートなどが入ってもブランチ番号は変更されません。
その代わりコミットポジションが +1 されていきます。

main だけでコミットポジションがない場合はコミットポジション 0 として扱います。

### support ブランチとタグ

大きめのパッチで、かつメインブランチにマージが難しい場合は support ブランチを利用します。
support ブランチでは `<webrtc-build>-<support-branch-name>.<release>` というタグを打ちます。

- 例: `m127.6533.1.1-simulcast-multi-codec.1`
- 例: `m127.6533.1.1-hololens2.0`

## パッチ運用について

- 最新版でパッチが動作しない場合はパッチ作成者が修正をしてください
- 何かしらの理由でパッチ修正が難しい場合はパッチを削除します
  - 時雨堂で必要と思ったパッチは時雨堂にて対応します
