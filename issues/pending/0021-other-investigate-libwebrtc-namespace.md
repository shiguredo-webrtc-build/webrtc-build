# libwebrtc の名前空間を独自に設定できる仕組みを検討する

- Created: 2026-09-10
- Completed: {YYYY-MM-DD}
- Branch: feature/debug-libwebrtc-namespace
- Polished: {YYYY-MM-DD}

## 目的

libwebrtc の C++ 名前空間を独自の名前空間に差し替えてビルドできるようにし、他社の WebRTC SDK が内包する libwebrtc と同一プロセス上で共存できるようにする。共存できるようになると、他社 SDK からの移行時にアプリへ両方の SDK を組み込めるようになり、移行しやすくなる。

## 現状

- `run.py` の `apply_patches` が upstream の webrtc ソースに `patches/*.patch` を適用してビルドしており、名前空間を変更する仕組みは無い。
- libwebrtc の C++ API は `webrtc` 名前空間、基盤部分は `rtc` 名前空間を利用している。 `CHANGES.md` には upstream の `rtc::` から `webrtc::` への名前空間変更にパッチを追従させた記録があり、名前空間は upstream の都合で変わりうる。
- ビルド成果物は `libwebrtc.a` / `webrtc.lib` / `WebRTC.framework` / `WebRTC.xcframework` / Android の `libjingle_peerconnection_so.so` と AAR で、 Sora C++ SDK / Sora Python SDK / Sora Unity SDK など下流の SDK がリンクする。
- シンボルの可視性は `RTC_EXPORT` と GN 引数の `rtc_enable_symbol_export` / `rtc_enable_objc_symbol_export` で制御しており、 `run.py` は macOS で `rtc_enable_symbol_export=true`、 iOS で `rtc_enable_objc_symbol_export=true` を設定している。これはシンボルの可視性を制御するものであり、名前空間とシンボル名の衝突は避けられない。
- 他社 SDK が内包する libwebrtc と同一プロセスで共存する場合、 `webrtc::` / `rtc::` の C++ シンボルに加えて、 ObjC クラス名 (`RTC*`) と Java クラス名 (`org.webrtc.*`) も衝突する可能性がある。

## 設計方針

- まず upstream に名前空間を差し替えるビルド設定 (GN 引数など) が存在するかを調査する。
- 存在しない場合は、次の方式の実現性を比較検討する。
  - パッチで C++ 名前空間 (`webrtc` / `rtc`) を書き換える方式
  - ビルド後のシンボルリネーム (`objcopy` など) で衝突を避ける方式
  - 共有ライブラリ化とシンボル可視性の制御で衝突を避ける方式
- 各方式について、対応が必要なプラットフォーム (iOS / macOS / Android / Windows / Ubuntu) ごとの実現性と、 ObjC / Java API への影響、下流 SDK の変更量を整理する。
- 実装する場合は本 issue では行わず、方式を決定してから実装 issue を別途起票する。

## pending にする理由

名前空間を差し替える仕組みが upstream に存在するか、存在しない場合にどの方式で実現するかが未確定であり、実現可否の下調べが必要なため保留する。下調べが完了して方式が決まった時点で reopened にし、実装が必要なら実装 issue を起票する。

## 完了条件

- 名前空間を独自に設定する方法の実現可否と、実現する場合の方式が判明し、調査結果と判断根拠が本 issue に記載されていること。
- 実装が必要な場合、方式に応じた実装 issue が起票されていること。

## 解決方法

未着手
