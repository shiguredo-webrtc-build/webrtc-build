# webrtc-build

[![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/shiguredo-webrtc-build/webrtc-build.svg)](https://github.com/shiguredo/momo)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Actions Status](https://github.com/shiguredo-webrtc-build/webrtc-build/workflows/build/badge.svg)](https://github.com/shiguredo-webrtc-build/webrtc-build/actions)

## About Support

We check PRs or Issues only when written in JAPANESE.
In other languages, we won't be able to deal with them. Thank you for your understanding.

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

- windows x86_64
- macos_arm64
- macos_x86_64
- raspberry-pi-os_armv6 (Raspberry Pi Zero)
- raspberry-pi-os_armv7 (Raspberry Pi 3, 4)
- raspberry-pi-os_armv8 (Raspberry Pi 3, 4)
- ubuntu-18.04_armv8
- ubuntu-18.04_armv8_jetson_nano (Jetson Nano)
- ubuntu-18.04_armv8_jetson_xavier (Jetson Xavier NX, AGX Xavier)
- ubuntu-18.04_x86_64
- ubuntu-20.04_x86_64
- centos-8_x86_64 (そのうち削除します)
- android
- ios

## ライセンス

Apache License 2.0

```
Copyright 2019-2021, Wandbox LLC (Original Author)
Copyright 2019-2021, Shiguredo Inc.

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

### Contributing

- melpon - *Original Author*
    - Android support
    - iOS Support
    - CentOS 8 support
- tnoho - *Original Author*
    - AV1 support for macOS
    - H.265 Support for macOS
- hakobera
    - Ubuntu 20.04 x86_64 support
    - macOS 11 arm64 support
