# カスタム音声入力の inputData 経路で 2 ch の PCM が半分しか取り込まれない不具合を修正する

- Created: 2026-09-07
- Completed: 2026-09-07
- Branch: feature/fix-custom-audio-input-stereo-sample-count
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
起票時点で確認済みだったのはソースコード上のサンプル数の不整合であり、専用の再現テストによる欠落量の測定結果は「解決方法」に記録する。

## 設計方針

- `sdk/objc/native/src/objc_audio_device.mm` のカスタム音声入力を修正する独立したパッチを追加し、`run.py` の `PATCHES["macos_arm64"]`、`PATCHES["ios"]`、`PATCHES["ios_sdk"]` に登録する。対象版の `sdk/BUILD.gn` では、macOS と iOS の framework が `peerconnectionfactory_base_objc`、`objc_audio_device_module` を経由して `audio_device_objc` に依存し、いずれもこの処理を含む。ネイティブ stereo 出力パッチへ混在させない。
- `inputData` 経路が渡すサンプル数を `num_frames * record_parameters_.channels()` とする。必要バイト数はこのサンプル数に `sizeof(int16_t)` を掛け、オーバーフローを起こさない形で算出・検査する。
- 録音中の `inputData` は、`mNumberBuffers == 1`、録音設定のチャンネル数が 1 または 2、`mNumberChannels` が録音設定と一致することを確認する。`mDataByteSize` が必要バイト数以上であり、必要なサンプルがある場合は `mData != nullptr` であることも、データを読む前にリリースビルドで検査する。バッファが必要量より大きい場合も、指定されたフレーム数に対応するサンプルだけを渡す。
- 上記の検査に失敗した場合は `kAudio_ParamError` を返し、当該入力を `FineAudioBuffer` へ追加しない。既に蓄積している正常な PCM は保持する。録音停止中は従来どおり入力に触れず `noErr` を返す。正常な 1 ch と `renderBlock` の挙動は維持する。
- `FineAudioBuffer` による 10 ms 単位への分割を経た後も、サンプル数、左右の並び、フレームの連続性を検証する。
- SDK の `renderBlock` による回避を取り除くことは本 issue の完了条件にしない。upstream への修正提案は別途検討し、本 issue はパッチによる修正を成果とする。

## 対応ブランチと依存関係

ユーザー指定により、`feature/m150.7871` をベースに作成した `feature/fix-custom-audio-input-stereo-sample-count` で対応する。
PR のマージ先は `feature/m150.7871` とし、自動マージは行わない。
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

`objc_audio_device_input.patch` を追加し、`macos_arm64`、`ios`、`ios_sdk` に登録した。
`inputData` から `FineAudioBuffer` に渡す要素数をフレーム数 × 録音チャンネル数に修正した。
録音中はバッファ数、録音設定と入力のチャンネル数、バッファ長、データポインターを検査し、不正な入力には `kAudio_ParamError` を返す。
長さの検査には除算を用い、後続のサンプル数の乗算が桁あふれしないことも保証する。
エラー時と 0 フレーム入力時は、それまでの正常な PCM の蓄積を保持する。

実際のカスタム ADM を使う回帰テストと実行スクリプトを追加した。
音声デバイスと転送は、メモリー上で録音・再生する実装を使い、モック、スタブ、音声ハードウェアは使用していない。
macOS の CI では、ソースの差し替えを行わず、ビルドした配布ライブラリそのものを検証する。

- 修正前の `m150.7871.3.2` の配布ライブラリでは、48 kHz / 2 ch / 20 ms の入力が通知 1 回・960 サンプルになり、回帰テストが失敗することを再現した。
- 修正後は、1 ch / 2 ch と `inputData` / `renderBlock` の全組み合わせで、通知 2 回と PCM の完全一致を確認した。2 ch は全 1,920 サンプルが届く。
- 10 ms 境界をまたぐ分割入力、不正入力と 0 フレーム入力の前後での蓄積保持、余剰バッファ、未対応の録音チャンネル数も確認した。
- 修正後の ObjC ADM を直接コンパイルするローカル検証は、AddressSanitizer / UndefinedBehaviorSanitizer 有効で成功した。既存の配布ライブラリ部分は再コンパイルしていない。
- 既存 Python テスト 15 件、新規実行スクリプトの ruff / ty、差分の空白検査が成功した。既存の `run.py` と workflow に新しい lint 指摘はない。
- 2 系統で 3 周レビューし、指摘を修正して再確認した結果、致命的・重要な指摘は 0 件となった。

実装コミット `34727fc` の [CI](https://github.com/shiguredo-webrtc-build/webrtc-build/actions/runs/34074384867) で、ビルド 15 ジョブがすべて成功した。
`macos_arm64`、`ios`、`ios_sdk` の既存パッチを含む適用、フルビルド、パッケージ作成、および macOS の配布ライブラリを使う回帰テストの成功を確認した。
タグの push ではないため、リリース作成は実行されていない。

[PR #173](https://github.com/shiguredo-webrtc-build/webrtc-build/pull/173) のベースは `feature/m150.7871` とし、ユーザー指定によりマージは行わない。
Sora iOS SDK への依存更新と `renderBlock` による回避の除去は本対応に含めていない。
