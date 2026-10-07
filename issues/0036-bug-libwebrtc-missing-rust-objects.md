# m156 以降の libwebrtc.a が Rust の実装を含まずリンクに失敗する

- Created: 2026-10-08
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-libwebrtc-missing-rust-objects
- Polished: {YYYY-MM-DD}

## 目的

m156 で libwebrtc の corruption detection が Rust 実装になり、`rtc_rust=true` の既定のビルドで Rust のコードが libwebrtc 本体にリンクされるようになった。しかし webrtc-build が生成する `libwebrtc.a` には Rust の実装が含まれないため、これをリンクした実行ファイルを作れない。下流 (webrtc-rs / Sora SDK など) が m156 に追随できないので、配布物を直す。

## 現状

### m156 で Rust が libwebrtc 本体に入った

m156 の `modules/rtp_rtcp/BUILD.gn` では、`rtc_rust` が true のとき corruption detection が Rust 実装になる。`rtc_rust_library("corruption_detection_extension")` と `rtc_rust_cxx_bridge("corruption_detection_extension_cxx")` が定義され `rtp_rtcp_format` から参照される。`modules/rtp_rtcp/source/rtp_sender_video.cc` と `modules/rtp_rtcp/source/rtp_video_stream_receiver2.cc` が `CorruptionDetectionExtension` のメソッドを呼ぶため、これらのオブジェクトを引くリンクでは Rust 側の実装が必要になる。

m155 では `rtc_rust=true` でも libwebrtc 本体に Rust は入っておらず、Rust のターゲットを参照するのは `rtc_include_tests` 配下のテストだけだった (0027 の調査時点の認識)。m156 でこの前提が崩れた。

### `archive_objects` が `*.o` しか集めていない

`run.py` の `archive_objects` は、ビルドディレクトリ配下の `*.o` を `find` して `ar -rc` でまとめるだけなので、`.rlib` (`obj/modules/rtp_rtcp/libcorruption_detection_extension_*.rlib` や `local_rustc_sysroot` 配下の std など) が入らない。`libwebrtc.a` には C++ 側の bridge のオブジェクトは入るが Rust 側の実装が無いため、`webrtc$cxxbridge1$202$RustCorruptionDetectionExtension$parse` などのシンボルが未定義になる。

### GN の完全な静的ライブラリもそのままでは使えない

upstream の `BUILD.gn` には `complete_static_lib = true` を付けた `//:webrtc` があり、GN は `obj/libwebrtc.a` を作っている (Windows では `run.py` がこれを `webrtc.lib` としてコピーしている)。しかし GN は rlib を `llvm-ar -r` の入力にそのまま渡すため、rlib は入れ子のメンバーとしてアーカイブに入り、リンカから中身が見えない。`BUILD.gn` の TODO (bugs.webrtc.org/430260876) はこの対応が済んでいないことを示している。upstream の `webrtc_lib_link_test` が通るのは `rule link` / `rule solink` が `${rlibs}` として rlib をリンカに直接渡しているためで、`obj/libwebrtc.a` 単体でリンクできるわけではない。

したがって「GN の完全な静的ライブラリをそのまま配布する」では解決しない。

### 再現手順

1. m156.8078.2.1 以降で `python3 run.py build ubuntu-24.04_x86_64` を実行する
2. 生成した `_build/ubuntu-24.04_x86_64/release/webrtc/libwebrtc.a` を `nm` で調べると `webrtc$cxxbridge1$202$RustCorruptionDetectionExtension$parse` は参照 (U) だけがあって定義 (T) が無い
3. これをリンクする実行ファイル (webrtc-rs なら `cargo test --features source-build`) が `undefined symbol: webrtc$cxxbridge1$202$RustCorruptionDetectionExtension$parse` で失敗する

## 設計方針

`archive_objects` で `*.o` に加えて `*.rlib` の中身を展開して `libwebrtc.a` に含める。

- rlib は通常の `ar` アーカイブなので、rlib ごとに一時ディレクトリへ `ar x` で展開し、出てきた `*.o` を `find` の結果に加えてから `ar rc` でまとめる。POSIX の `ar x` / `ar rc` だけで済むため GNU ar / llvm-ar / Apple の ar のどれでも動く
- rlib ごとに別のディレクトリへ展開する。rlib のメンバー名は crate 名とハッシュを含むため衝突しない見込みだが、`lib.rmeta` のような拡張子を持たないメンバーが複数の rlib に存在するため同一ディレクトリに展開しない
- `ar` の MRI モード (`ar -M` の `ADDLIB`) でも同じことができるが、macOS / iOS は `/usr/bin/ar` (Apple の ar) を使っており MRI に対応しているか不明なため第一候補にしない
- Windows は `archive_objects` を通らず GN の `obj/webrtc.lib` をコピーしているため同じ問題を抱えている。MSVC の `lib.exe` が入れ子の rlib を展開するかは未確認で、別途対応が要る可能性が高い (展開が要るなら llvm-ar は Windows 用も取得されているので同じ処理で対応できる見込み)
- upstream が bugs.webrtc.org/430260876 に対応したらこの処理は不要になる。そのとき GN の `obj/libwebrtc.a` をそのまま使う形に寄せられるかは別途判断する

## 完了条件

- すべてのターゲットで `python3 run.py build <target>` が成功し、GitHub Actions の CI が成功する
- 生成した `libwebrtc.a` (Windows は `webrtc.lib`) をリンクした実行ファイルが作れる
- そのリンクを確認するテストが CI で動く
- webrtc-rs を m156.8078.3.0 に上げた状態で `cargo test --features source-build` のリンクまで通る
- CHANGES.md に変更内容を記録する

## テスト戦略

配布物がリンク可能であることを確認するテストを追加する。m156 で実際に壊れたのは「実行ファイルを作るリンク」なので、アーカイブのメンバー数ではなくリンクの成否で判定する。

- `run.py` に、ビルド済みの `libwebrtc.a` (Windows は `webrtc.lib`) をリンクして実行ファイルを作るサブコマンドを追加する。プラットフォームごとのコンパイラ・sysroot・include の知識は `run.py` が既に持っているため、テスト側で再実装しない
- リンクするコードは Rust の実装を必要とするものにする。案として `modules/rtp_rtcp/source/corruption_detection_extension.h` の `CorruptionDetectionExtension` を呼ぶ小さな C++ ファイルを用意する
- GitHub Actions の `build.yml` で、各プラットフォームのビルド直後にこのテストを実行する
- クロスコンパイルのターゲット (armv8 / android など) はリンクまで、ネイティブで動くターゲット (ubuntu-24.04_x86_64 / macos_arm64 / windows_x86_64) は実行ファイルの起動まで確認する

## 解決方法

- `run.py` の `archive_objects` を、`*.o` に加えて `*.rlib` を展開した `*.o` も含めるように変更する
  - `find` で `*.rlib` を集め、rlib ごとに一時ディレクトリへ `ar x` で展開して `*.o` を集める
  - `*.o` と展開した `*.o` をまとめて `ar rc` で `libwebrtc.a` にする
- Windows 向けに、GN の `obj/webrtc.lib` をコピーする処理へ rlib の展開を組み込む。MSVC の `lib.exe` が展開するかを確認したうえで判断する
- `run.py` にリンクテストのサブコマンドを追加し、`build.yml` の各プラットフォームで実行する
- ローカルの ubuntu-24.04_x86_64 で `python3 run.py build` → リンクテスト → webrtc-rs の `cargo test --features source-build` まで確認する
- CHANGES.md に変更内容を記録する
