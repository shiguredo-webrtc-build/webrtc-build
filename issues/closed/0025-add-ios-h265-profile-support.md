# iOS の H.265 パッチで SDP のプロファイル（profile-id / tier-flag / level-id）を利用する

- Created: 2026-09-11
- Completed: 2026-09-11
- Branch: feature/add-ios-h265-profile-support
- Polished: {YYYY-MM-DD}

## 目的

`patches/h265_ios.patch` が追加する H.265 実装が、SDP でネゴシエーションしたプロファイル（`profile-id` / `tier-flag` / `level-id`）を VideoToolbox のエンコーダへ反映するようにする。

現在のパッチは WebKit 実装を元にしており、SDP のプロファイルを読まずに VideoToolbox のエンコーダを初期化している。offer/answer で通知したプロファイルと実際に送信するストリームが一致せず、RFC 7798 の SDP ネゴシエーションと実装が食い違う。upstream の H.265 SDP ネゴシエーションが決めた値をエンコーダ設定に反映できるようにする。

## 現状

確認対象は `VERSION` が指定する libwebrtc `154.8037.1`、upstream コミット `c2b761bb73f0b2ced096274abb415f6c7559a28b` と現在のパッチ群である。

- `patches/h265_ios.patch` の `RTCVideoEncoderH265.mm` は `_profile` を宣言しているが代入しておらず、`configureCompressionSession` の `kVTCompressionPropertyKey_ProfileLevel` 設定はコメントアウトされている
- `RTCVideoEncoderH265.mm` の `initWithCodecInfo:` は `codecInfo.name` だけを確認し、`codecInfo.parameters` の SDP fmtp を読んでいない
- `RTCH265ProfileLevelId.mm` の `kRTCLevel31Main` は `4d001f` で、`// TODO(jianjunz): This is value is not correct.` とコメントされている。H.264 の profile-level-id 形式であり、H.265 の `profile-id` / `tier-flag` / `level-id` とは表現が異なる。宣言と定義以外に使用箇所はない
- upstream には `api/video_codecs/h265_profile_tier_level.h` の `ParseSdpForH265ProfileTierLevel` があり、SDP fmtp からプロファイル・tier・レベルを取得できる
- `media/base/sdp_video_format_utils.cc` の `H265GenerateProfileTierLevelForAnswer` と `pc/codec_vendor.cc` により H.265 の SDP ネゴシエーションは有効になっている。`SdpVideoFormat::H265()` はパラメータなしのフォーマットを返すため、ローカル側は Main / Tier0 / Level 3.1 の既定値として扱われる
- 結果として、answer では Level 3.1 が上限として通知され得る一方、VideoToolbox のエンコーダはプロファイルもレベルも意識せずに動作する
- Android の `HardwareVideoEncoder` は H.264 の `profile-level-id` のみを MediaCodec に設定しており、H.265 のプロファイルを反映する実装は現行 libwebrtc にはない

## 設計方針

- `RTCVideoEncoderH265` の `initWithCodecInfo:` で `RTCVideoCodecInfo` の `nativeSdpVideoFormat` を取得し、`parameters` を `webrtc::ParseSdpForH265ProfileTierLevel` に渡してプロファイル・tier・レベルを取得する
- 取得したプロファイルを `configureCompressionSession` で `kVTCompressionPropertyKey_ProfileLevel` に設定する。Main は `kVTProfileLevel_HEVC_Main_AutoLevel`、Main10 は `kVTProfileLevel_HEVC_Main10_AutoLevel` を使う
- VideoToolbox の HEVC プロファイル定数は AutoLevel のみで、レベルを個別に指定できない。`level-id` は VideoToolbox の AutoLevel に任せ、レベルを反映できない制約をパッチ解説に残す
- `profile-id` が未指定、または Main / Main10 以外の場合は VideoToolbox の既定動作へフォールバックし、パッチ適用前の挙動を維持する
- 誤った H.264 形式の定数 `kRTCLevel31Main` は削除する
- プロファイルの解析結果を保持するだけで `RTCH265ProfileLevelId.h` / `RTCH265ProfileLevelId.mm` が不要になる場合は、削除も検討する

## 完了条件

- `profile-id=1` と `profile-id=2` を指定した SDP で H.265 をネゴシエーションしたとき、それぞれ `kVTProfileLevel_HEVC_Main_AutoLevel` と `kVTProfileLevel_HEVC_Main10_AutoLevel` が VideoToolbox に設定されること
- `profile-id` 未指定、または未対応のプロファイルを指定した場合は従来どおりのエンコード設定で動作すること
- `ios` / `ios_sdk` / `macos_arm64` のビルドが成功すること
- 実機で H.265 の送受信を確認し、SDP のプロファイルと実際のストリームが矛盾しないこと
- `patches/README.md` と `CHANGES.md` に変更内容が追記されていること

## 変更履歴案

- [ADD] iOS, macOS の H.265 パッチで SDP のプロファイルを利用する

## 解決方法

libwebrtc 側を確認し、iOS のパッチでは対応しない判断とした。

- H.265 の SDP ネゴシエーションは upstream 実装 (`pc/codec_vendor.cc` / `media/base/sdp_video_format_utils.cc` / `api/webrtc_sdp.cc`) で行われており、`profile-id` / `tier-flag` / `level-id` は SDP 層で解釈される
- パラメータ未指定時は RFC 7798 の既定値 (Main / Tier0 / Level 3.1) として扱われるため、Main プロファイルではエンコーダーが SDP を読まなくても SDP と実ストリームは矛盾しない
- iOS の H.265 エンコーダーは VideoToolbox の既定プロファイルが Main で、HEVC のプロファイル定数は AutoLevel のみであり、エンコーダー側で SDP のプロファイルを設定しても実質 no-op になる
- browser と同等の fmtp (`profile-id` / `tier-flag` の明示) は SDP 生成側の課題であり、必要なら sora-ios-sdk のコーデックファクトリー (`RTCVideoCodecInfo` の `parameters`) か H.265 登録箇所へのパラメータ追加で対応できる
