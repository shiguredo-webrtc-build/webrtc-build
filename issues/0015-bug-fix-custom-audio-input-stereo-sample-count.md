# カスタム音声入力の inputData 経路で 2 ch の PCM が半分しか取り込まれない不具合を修正する

- Created: 2026-09-07
- Completed: {YYYY-MM-DD}
- Branch: feature/m150.7871
- Polished: 2026-09-07

## 目的

カスタム `RTCAudioDevice` の `inputData` 経路で、2 ch のインターリーブ PCM を欠落なく libwebrtc へ渡せるようにする。
upstream に存在する不具合に対し、webrtc-build の修正パッチで対応する。

## 現状

確認対象は `m150.7871.3.2`、対応する upstream コミットは `1f975dfd761af6e5d76d28333191973b258d82a8` である。

- `RTCAudioDeviceDelegate.deliverRecordedData` は、生成済みの PCM を `inputData` で渡す方法と、libwebrtc のバッファに `renderBlock` で書き込む方法を提供する。
- API は 16 bit 整数の PCM を要求し、2 ch の場合は `L0, R0, L1, R1, ...` のインターリーブ形式を要求する。1 フレームは 2 サンプルに相当する。
- `objc_audio_device.mm` の `ObjCAudioDeviceModule::OnDeliverRecordedData` は、`inputData` がある場合、`std::span<const int16_t>` の要素数として `num_frames` を指定している。チャンネル数の乗算が欠けている。
- `renderBlock` 経路は `num_frames * record_parameters_.channels()` のバッファ全体を `FineAudioBuffer::DeliverRecordedData` へ渡す。
- 当該リリースのパッチ群はこの処理を変更していない。本不具合は stereo 出力パッチによって混入したものではない。

48 kHz / 2 ch / 20 ms の PCM を 1 回渡す場合、コード上の取り込み量は次のようになる。

| 項目 | 本来の入力 | 現在の inputData 経路 |
| --- | --- | --- |
| サンプル数 | 1,920 | 960 |
| フレーム数 | 960 | 480 |
| 音声の長さ | 20 ms | 10 ms |

右チャンネルだけが消えるのではなく、左右を含むバッファの後半が渡されない。
1 ch ではフレーム数とサンプル数が一致するため、この乗算漏れによる欠落はない。
対象はカスタム音声デバイスの `inputData` 経路であり、ネイティブのマイク入力や stereo 入力全般の問題とは区別する。

Sora iOS SDK の PR #381 では、`DummyAudioDevice` が `renderBlock` を使って回避している。
この回避は本体の修正ではなく、既存の stereo E2E テストの成功も `inputData` 経路の正常性を示さない。
確認済みなのはソースコード上のサンプル数の不整合であり、専用の再現テストによる欠落量や受信音声への影響の測定は未実施である。

## 設計方針

- `sdk/objc/native/src/objc_audio_device.mm` のカスタム音声入力を修正する独立したパッチを追加し、`run.py` の `PATCHES["macos_arm64"]`、`PATCHES["ios"]`、`PATCHES["ios_sdk"]` に登録する。対象版の `sdk/BUILD.gn` では、macOS と iOS の framework が `peerconnectionfactory_base_objc`、`objc_audio_device_module` を経由して `audio_device_objc` に依存し、いずれもこの処理を含む。ネイティブ stereo 出力パッチへ混在させない。
- `inputData` 経路が渡すサンプル数を `num_frames * record_parameters_.channels()` とする。必要バイト数はこのサンプル数に `sizeof(int16_t)` を掛け、オーバーフローを起こさない形で算出・検査する。
- 録音中の `inputData` は、`mNumberBuffers == 1`、録音設定のチャンネル数が 1 または 2、`mNumberChannels` が録音設定と一致することを確認する。`mDataByteSize` が必要バイト数以上であり、必要なサンプルがある場合は `mData != nullptr` であることも、データを読む前にリリースビルドで検査する。バッファが必要量より大きい場合も、指定されたフレーム数に対応するサンプルだけを渡す。
- 上記の検査に失敗した場合は `kAudio_ParamError` を返し、当該入力を `FineAudioBuffer` へ追加しない。既に蓄積している正常な PCM は保持する。録音停止中は従来どおり入力に触れず `noErr` を返す。正常な 1 ch と `renderBlock` の挙動は維持する。
- `FineAudioBuffer` による 10 ms 単位への分割を経た後も、サンプル数、左右の並び、フレームの連続性を検証する。
- SDK の `renderBlock` による回避を取り除くことは本 issue の完了条件にしない。upstream への修正提案は別途検討し、本 issue はパッチによる修正を成果とする。

## 対応ブランチと依存関係

ユーザー指定により、`feature/m150.7871` で対応する。
issue 0011 から 0014 のネイティブ音声の改善とは独立して進める。
修正ビルドを Sora iOS SDK の PR #381 に取り込む場合は、SDK issue 0130 の依存更新と合わせてバージョン、checksum、`WebRTCInfo` を揃える。
ネイティブ stereo 録音を追加する既存 issue 0006 とは対象経路が異なる。

## テスト方針

実際の ADM に、サンプル位置と左右を識別できる合成 PCM を入力する回帰テストを追加する。
録音デバイスやマイク権限を必須とせず、実際のカスタム `RTCAudioDevice` のコールバック経路を使う。
モックやスタブは使用しない。

- 1 ch / 2 ch と `inputData` / `renderBlock` の組み合わせを検証する。
- 48 kHz / 2 ch / 20 ms で、1,920 サンプルが欠落せず、左右の順序を保って取り込まれることを確認する。
- 10 ms 単位への分割と、複数の入力コールバックをまたぐ蓄積を検証し、入力バッファの後半やコールバック境界で欠落・重複がないことを確認する。
- 入力バッファ数、チャンネル数、バッファ長、データポインターが上記の条件を満たさない場合に、`kAudio_ParamError` を返し、当該入力を取り込まず、範囲外読み取りが起きないことを検証する。エラー前に蓄積した正常な PCM が保持され、その後の正常入力で処理を継続できることも確認する。
- 修正前に失敗し、修正後に成功することを確認する。圧縮後の受信音声だけで正確なサンプル数を推測せず、実際の ADM が取り込んだ PCM を観測する。

## 完了条件

- 修正パッチが `macos_arm64`、`ios`、`ios_sdk` に登録され、各ターゲットの既存パッチ群と合わせて対象版へ適用でき、ビルドが成功する。
- 正常な 2 ch の `inputData` が全サンプルを取り込み、フレームの連続性を保つ。
- 正常な 1 ch と `renderBlock` の挙動が維持される。
- 録音中の `inputData` が設計方針の検査条件を満たさない場合は `kAudio_ParamError` を返し、当該入力を取り込まず、既に蓄積している正常な PCM を保持する。
- 実際の ADM を使う回帰テストで、修正前の失敗と修正後の成功を確認している。
- ビルド・検証結果とパッチの理由が記録され、upstream に由来する不具合であることが説明されている。

## 解決方法
