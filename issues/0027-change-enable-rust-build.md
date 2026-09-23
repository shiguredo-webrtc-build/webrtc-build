# libwebrtc の Rust ビルドを有効化する

- Created: 2026-09-23
- Completed: {YYYY-MM-DD}
- Branch: feature/change-enable-rust-build
- Polished: {YYYY-MM-DD}

## 目的

libwebrtc の Rust ビルドを有効化し、upstream が既定としている GN 引数に合わせる。

libwebrtc は Rust 実装を段階的に取り込んでおり、今後 Rust の利用は避けられない。現状は m136 で発生したビルドエラーを回避するために Rust ビルドを無効化しているが、これは upstream が想定していない状態である。無効化を続けると、libwebrtc が Rust 前提に移行したときにビルドが通らなくなる。

m155 の時点で無効化の理由が解消しているかを確認したうえで、Rust ビルドを有効化する。

## 現状

`run.py` の `COMMON_GN_ARGS` に以下の 4 つを指定して Rust ビルドを無効化している。

- `enable_rust=false`
- `enable_rust_cxx=false`
- `enable_chromium_prelude=false`
- `rtc_rust=false`

無効化の経緯は CHANGES.md に記録されている。

- 2025-04-19: libwebrtc に Rust ビルドを有効化する GN オプションが追加されたため、`enable_rust` 系の 3 つを false にした
- 2026-06-03: m150 で `rate_tracker_rust` が追加され `rtc_rust=true` がデフォルトになったため、`enable_rust=false` と衝突して `gn gen` が停止する問題を `rtc_rust=false` の追加で回避した

一方、libwebrtc m155 の upstream は Rust を有効にする前提になっている。

- `.gn` で `enable_rust=true` / `enable_rust_cxx=true` / `enable_chromium_prelude=true` を指定している
- `build/config/rust.gni` の `enable_chromium_prelude` には、無効化をサポートしない旨が書かれている
- `webrtc.gni` の `rtc_rust` はデフォルト true
- `third_party/rust-toolchain` (Chromium 版 Rust toolchain) は gclient sync で取得される。CI に Rust のインストール手順は無い
- `third_party/rust` の crate も gclient の `src/third_party` 依存として取得される

`build_overrides/build.gni` で `build_with_chromium=false` となるため `build/config/rust.gni` の `enable_rust` のデフォルト値は false になるが、`.gn` の `default_args` が `enable_rust=true` / `enable_rust_cxx=true` / `enable_chromium_prelude=true` を設定しており、GN では `default_args` がデフォルト値より優先される。このため無効化の指定を削除するだけで有効になり、`enable_rust` の明示は不要である。

なお現時点の libwebrtc は `BUILD.gn` の TODO (bugs.webrtc.org/430260876) のとおり、Rust を libwebrtc 本体にリンクしていない。`rtc_rust=true` で生成される Rust ターゲット (`rtc_base:rate_tracker_rust` など) を参照するのは `rtc_include_tests` 配下のテストだけであり、run.py は `rtc_include_tests=false` を指定している。`rtc_library("rate_tracker")` の deps にも Rust 実装は含まれていない。

このため、Rust を有効化しても `:default` でビルドされる内容はほとんど変わらない。m155 の Linux x86_64 で Rust 有効・無効それぞれのビルドディレクトリを生成し `ninja -t commands :default` を比較したところ、どちらも 4111 コマンドで、差分は Rust 無効時のみ定義される `-DWEBRTC_WITHOUT_RUST` の有無だけで、rustc の呼び出しは 0 件だった。有効化の効果は、成果物の内容を変えることではなく、upstream が Rust を libwebrtc 本体にリンクしたときに run.py を変更せず追随できる状態にすることにある。

## 設計方針

`COMMON_GN_ARGS` から Rust 無効化の 4 つを削除する。`enable_rust` / `enable_rust_cxx` / `enable_chromium_prelude` は `.gn` の `default_args`、`rtc_rust` は `webrtc.gni` の既定値で true になるため、明示は不要である。

- `enable_rust_cxx` は WebRTC の Rust ターゲットが cxx による C++ 連携を使うため必須である。無効にすると `rtc_rust_cxx_bridge` の assert で `gn gen` が停止する
- `enable_chromium_prelude` は WebRTC の Rust コードが `webrtc::import!` マクロで crate を解決するため必須である。無効にすると `gn gen` は通るが、Rust のコンパイルが `cannot find chromium in the list of imported crates` で失敗する
- `rtc_rust` は `webrtc.gni` の既定値が true のため無効化指定を削除する
- Rust toolchain は libwebrtc が同梱するものを gclient sync で取得するため、CI やドキュメントへの追加インストール手順は不要
- sysroot (`sysroot/*.json`) の変更は不要の見込み。Rust の std は `build/rust/std` が `local_rustc_sysroot` にソースからビルドし、`target_sysroot` とは独立している

## 完了条件

- すべてのターゲットで `python3 run.py build <target>` が成功し、GitHub Actions の CI が成功する
- `run.py` の GN 引数から Rust 無効化の指定が無くなり、upstream の既定と一致する
- `rtc_rust=true` により `rtc_base:rate_tracker_rust` などの Rust ターゲットが生成される

## 解決方法

- `run.py` の `COMMON_GN_ARGS` から Rust 無効化の 4 つを削除する
- 各ターゲットで `python3 run.py build <target> --webrtc-gen` を実行し、ビルドが通ることを確認する
  - `args.gn` が既に存在するビルドディレクトリでは `gn gen` が再実行されないため、`--webrtc-gen` を付ける必要がある
- ビルドが通らないターゲットがある場合は、原因を調査して GN 引数の追加やパッチの追加で対応する
- CHANGES.md に変更内容を記録する
