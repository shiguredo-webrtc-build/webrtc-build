# iOS ステレオ音声出力パッチ解説ドキュメントを SDK 利用者向けに再構成する

- Created: 2026-09-03
- Completed:
- Branch: feature/update-ios-stereo-audio-output-md
- Polished:

## 目的

`patches/ios_stereo_audio_output.md` は 0005 で追加したパッチの解説だが、SDK 利用者向けの情報と開発者向けの情報が混在した順序になっている。SDK 利用者が最短で使い方と制約を把握できるように節を再構成し、コード例に Objective-C 版を追加する。

## 現状

- 節の順序が「目的 → 背景 → 変更点の概要 → 適用順序と登録先 → SDK 側 API 呼び出し例 → 利用上の注意 → プロトタイプからの差分」
- 「変更点の概要」「適用順序と登録先」「プロトタイプからの差分」は本パッチをレビュー・改修する開発者向けの内容で、SDK 利用者は読む必要がない
- SDK 利用者は「使い方 → 制約 → 実機検証」を先に読みたいが、現状は開発者向け節に挟まれている
- SDK 側 API 呼び出し例は Swift のみ。Sora iOS SDK と組み合わせる利用者には Objective-C 版も必要

## 設計方針

- md を大きく「SDK 利用者向け」と「開発者向け」の 2 セクションに分ける
- SDK 利用者向けに置く節: 目的、SDK 側 API 呼び出し例 (Swift + Objective-C)、利用上の注意 (AEC/AGC、mode 切替、Bluetooth、マイク権限、呼び出しタイミング、実機検証)
- 開発者向けに置く節: 背景、変更点の概要、適用順序と登録先、preferredOutputNumberOfChannels の設計判断、プロトタイプからの差分
- SDK 側 API 呼び出し例に Objective-C 版のスニペットを追加する。Swift 版と並置し、既存の使い方を変更しない

## 完了条件

- `patches/ios_stereo_audio_output.md` が「SDK 利用者向け」と「開発者向け」の 2 セクションに分割されている
- SDK 側 API 呼び出し例に Swift 版と Objective-C 版が両方掲載されている
- 既存の技術的説明の内容は失われていない (節の並べ替えと Objective-C 例の追加のみ)
- CHANGES.md への追記は不要 (`.md` ファイルのみの変更は変更履歴の対象外)

## 変更履歴案

- なし (`.md` ファイルのみの変更のため)
