# WebRTC-Build

[![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/shiguredo-webrtc-build/webrtc-build.svg)](https://github.com/shiguredo-webrtc-build/webrtc-build)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Actions Status](https://github.com/shiguredo-webrtc-build/webrtc-build/workflows/build/badge.svg)](https://github.com/shiguredo-webrtc-build/webrtc-build/actions)

## About Shiguredo's open source software

We will not respond to PRs or issues that have not been discussed on Discord. Also, Discord is only available in Japanese.

Please read https://github.com/shiguredo/oss/blob/master/README.en.md before use.

## 時雨堂のオープンソースソフトウェアについて

利用前に https://github.com/shiguredo/oss をお読みください。

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
- macos_x86_64
- raspberry-pi-os_armv6 (Raspberry Pi Zero)
- raspberry-pi-os_armv7 (Raspberry Pi 3, 4)
- raspberry-pi-os_armv8 (Raspberry Pi 3, 4)
- ubuntu-18.04_armv8
    - Jetson Nano
    - Jetson Xavier NX
    - Jetson AGX Xavier
- ubuntu-20.04_armv8
    - Jetson AGX Orin
- ubuntu-18.04_x86_64
- ubuntu-20.04_x86_64
- android_arm64
- ios_arm64

### hololens2 ビルドについて

- 対応ブランチは support/hololens2 です
- 最新の libwebrtc 追従は有償で承っております
- バグ修正は有償で承っております

## 今後の予定

- Ubuntu 22.04 x86_64 対応
    - リリースされ次第対応を検討します
- Jetson 向け ARM 版 Ubuntu 20.04 対応
    - リリースされ次第対応を検討します

### 廃止

- macOS x86_64 廃止
    - 2022 年 6 月を持って廃止します
- Ubuntu 18.04 x86_64 廃止
    - 2023 年 4 月を持って廃止します
- Jetson 向け ARM 版 Ubuntu 18.04 廃止
    - 2023 年 4 月を持って廃止します

## ライセンス

Apache License 2.0

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

### コントリビューター

- melpon - *Original Author*
    - Android サポート
    - iOS サポート
    - CentOS 8 サポート
- tnoho - *Original Author*
    - macOS 向け AV1 サポート
    - macOS 向け H.265 サポート
- hakobera
    - Ubuntu 20.04 x86_64 サポート
    - macOS 11 arm64 サポート
- enm10k
    - iOS 向けデバッグビルド追加
- soudegesu
    - macOS 向け ObjC ヘッダー追加

## タグやブランチ運用について

- feature/m94.4606 のようにブランチを切ります
    - branch-heads のブランチは削除してはいけません
    - 次のリリースブランチが決まるまでは feature 上でタグを打ちます
- 次のリリースブランチが確定したら master にマージします
    - ブランチから変更が無ければタグを打つ必要はありません
- libwebrtc のコミットポジションは変更せずに何か変更がある場合は一番右の数値を増やします
    - m94.4606.0.0 から m94.4606.0.1 のようにする

## パッチ運用について

- 最新版でパッチが動作しない場合はパッチ作成者が修正をしてください
- 何かしらの理由でパッチ修正が難しい場合はパッチを削除します
    - 時雨堂で必要と思ったパッチは時雨堂にて対応します

