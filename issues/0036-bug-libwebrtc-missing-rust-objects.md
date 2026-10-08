# m156 以降の libwebrtc.a が Rust の実装を含まずリンクに失敗する

- Created: 2026-10-08
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-libwebrtc-missing-rust-objects
- Polished: {YYYY-MM-DD}

## 目的

m156 で libwebrtc の corruption detection が Rust 実装になり、`rtc_rust=true` の既定のビルドで Rust のコードが libwebrtc 本体から呼ばれるようになった。しかし webrtc-build が生成する `libwebrtc.a` には Rust の実装が含まれないため、これをリンクした実行ファイルを作れない。下流 (webrtc-rs / Sora SDK など) が m156 に追随できないので、配布物を直す。

## 現状

### m156 で Rust が libwebrtc 本体に入った

m156 の `modules/rtp_rtcp/BUILD.gn` では、`rtc_rust` が true のとき corruption detection が Rust 実装になる。`rtc_rust_library("corruption_detection_extension")` と `rtc_rust_cxx_bridge("corruption_detection_extension_cxx")` が定義され `rtp_rtcp_format` から参照される。`modules/rtp_rtcp/source/rtp_sender_video.cc` と `modules/rtp_rtcp/source/rtp_video_stream_receiver2.cc` が `CorruptionDetectionExtension` のメソッドを呼ぶため、これらのオブジェクトを引くリンクでは Rust 側の実装が必要になる。

m155 では `rtc_rust=true` でも libwebrtc 本体に Rust は入っておらず、Rust のターゲットを参照するのは `rtc_include_tests` 配下のテストだけだった。m156 でこの前提が崩れた。実測でも m155 のビルドには rlib が 1 つも作られず、アーカイブに cxxbridge のシンボルの参照も無い。

### GN の完全な静的ライブラリには Rust が入らない

upstream の `BUILD.gn` には `complete_static_lib = true` を付けた `//:webrtc` があり、GN は `obj/libwebrtc.a` (Windows は `obj/webrtc.lib`) を作っている。しかし GN は rlib を **alink の暗黙入力** として宣言するだけで、alink のコマンドには明示入力しか渡さない。実際に `obj/webrtc.ninja` の `build obj/libwebrtc.a: alink <明示入力 3165 個> | <暗黙入力 96 個>` を調べると、rlib 31 個は暗黙入力の側にあり、アーカイブには 1 つも入らない。`BUILD.gn` の TODO (bugs.webrtc.org/430260876) はこの対応が済んでいないことを示している。

そのため `obj/libwebrtc.a` は C++ 側のオブジェクトは完全に含むが Rust の実装を含まず、これをリンクすると `webrtc$cxxbridge1$202$RustCorruptionDetectionExtension$parse` などの 12 個のシンボルが未定義になる。

### 上流のリンクテストでは検出できない

upstream の `webrtc_lib_link_test` は `deps = [":webrtc"]` でリンクする。GN の `link` / `solink` は `deps` の rlib をリンカへ直接渡すため、アーカイブに Rust が入っていなくてもリンクできてしまう。同じ形の検証用ターゲット (`deps = [":webrtc"]`) を m156 でビルドすると、Rust の入っていないアーカイブでもリンクと実行に成功する (リンク行に rlib が 31 個渡っている)。`deps = []` と `libs = [<アーカイブ>]` にした場合だけが失敗する。

### obj 配下の `*.o` を全部集める方式の問題

配布用アーカイブを作る処理は、以前は `obj` 配下の `*.o` を find で全部集めて `ar -rc` するだけだった。この方式には次の問題がある。

- ホストツール (nasm / protobuf / buildtools / perfetto) のオブジェクトが入る。`main` を定義するメンバーが 4 つ入るため `--whole-archive` でリンクできない。m155 では find 版 3181 メンバー 85.2 MB に対し GN 版は 2986 メンバー 63.5 MB で、find 版だけにある 195 メンバーはすべてホストツールだった
- 以前のビルドの残骸を拾う。ローカルの m156 ビルドディレクトリには古い `librate_tracker_ffi_*.rlib` などが残っており、これを展開すると Rust のクレートのハッシュ (crate disambiguator) が現在のビルドと食い違い、`<rate_tracker_rust_*::RustRateTracker>::new` などの未定義シンボルになる。実際に rlib を `obj` 配下から探す方式では、アーカイブを丸ごとリンクすると 8 個のシンボルが未定義になった

### 再現手順

1. m156.8078.3.0 以降で `python3 run.py build ubuntu-24.04_x86_64` を実行する
2. 生成した `_build/ubuntu-24.04_x86_64/release/webrtc/libwebrtc.a` の元になっている `obj/libwebrtc.a` を調べると、`webrtc$cxxbridge1$202$RustCorruptionDetectionExtension$parse` が未定義のままになっている
3. これをリンクする実行ファイル (webrtc-rs なら `cargo test --features source-build`) が `undefined symbol: webrtc$cxxbridge1$202$RustCorruptionDetectionExtension$parse` で失敗する

## 設計方針

GN が作った完全な静的ライブラリを土台にし、GN が alink の入力として宣言している rlib の中身を足して配布用のアーカイブを作る。

- 土台に GN の完全な静的ライブラリを使う。GN はビルドグラフのオブジェクトだけを入れており、ホストツールや残骸を含まない。m155 では GN 版に含まれない WebRTC のオブジェクトは 0 個、m156 で足りないのは Rust のオブジェクトだけであることを実測で確認している
- rlib の一覧は `ninja -t query` で alink の入力を調べて取る。`obj` 配下を `*.rlib` で探すと残骸を拾ってクレートのハッシュが食い違うため、現在のビルドが実際に使う rlib だけを使う
- rlib をそのままアーカイブに加えると入れ子のアーカイブになり、リンカから中身が見えない。rlib を展開してオブジェクトだけを加える
- 土台のアーカイブを展開してから作り直すと、同名のメンバー (`splitting_filter.o` など) が上書きされて欠落する。土台をコピーしてから追加する
- Windows は ar を使わず `lld-link /lib` で合体する。`lld-link` はアーカイブの入力を展開して取り込むため入れ子にならず、GN の alink と同じツールで、Windows の llvm-build に llvm-ar が含まれない事情にも合う。Windows の Rust のオブジェクトは raw-dylib の import stub (`.dll` メンバー) を必要とするため、オブジェクトだけを抜き出す方式にはしない
- Windows で MSVC のリンカを使う下流のために compiler-rt の builtins を同梱する。Rust の std が f16 の変換関数 (`__truncsfhf2` / `__extendhfsf2`) を参照するため、x86_64 では builtins が無いとリンクできない。GN 自身のリンクは `//build/config/compiler:runtime_library` で足しているが、アーカイブだけを受け取る下流は足せない
- Rust のオブジェクトだけでなく、GN がアーカイブをリンクするときに渡している静的ライブラリとオブジェクトも足す。GN の完全な静的ライブラリは C++ のランタイムを含まず、libc++ の実装をアーカイブに期待する下流は未定義シンボルになる。Linux では `libc++.a` と `libc++abi.a`、`third_party/compiler-rt/atomic/atomic.o` が該当する
  - `rtc_include_tests=false` のビルドでは GN が実行ファイルをリンクしないため、リンク行から一覧を取ることができない。`find_runtime_libraries` がビルドディレクトリの中から `libc++.a` と `libc++abi.a` と compiler-rt の `atomic.o` を探す。sysroot / NDK / SDK の中のライブラリは下流が自分でリンクするため足さない
  - `libc++.a` と `libc++abi.a` は thin アーカイブで `ar x` が使えない。メンバーのパスを `ar t` で読んで実体のファイルを取る
  - 同じ名前のメンバーは中身を比べ、同じなら足さず、違うなら別名で足す。`charconv.o` (abseil) と `charconv.o` (libc++) のように別のライブラリが同じ名前を持つため、単純に追加すると既存のメンバーが置き換わって欠落する
- Rust の std が固定名で定義する `rust_eh_personality` は、利用者の Rust の std も同じ名前を定義するため重複定義になる。`llvm-objcopy --redefine-sym` でアーカイブの中だけで使う名前に変えて衝突を避ける。定義だけでなく同じオブジェクトの中の参照とリロケーションも一緒に張り替わるため、personality が参照される構成 (ARM の EHABI や `extern "C-unwind"`) でもリンクは壊れない。1 つのバイナリに libwebrtc.a を複数回リンクすることは無いので、固定名でも自分自身とは衝突しない
- upstream の GN には `complete_static_lib` の下流へ rlib を伝播させる修正が既に入っている (https://gn-review.googlesource.com/c/gn/+/22100、2026-05-08 にマージ)。これは GN のリンク行に rlib を渡す修正で、配布するアーカイブに Rust の実装を入れる修正ではない。したがってこの処理は upstream の対応を待っても不要にはならない
- GN の alink が rlib の中身をアーカイブに入れるようになったら、この処理は不要になる

## 完了条件

- すべてのターゲットで `python3 run.py build <target>` が成功し、GitHub Actions の CI が成功する
- 生成した `libwebrtc.a` (Windows は `webrtc.lib`) をリンクした実行ファイルが作れる
- そのリンクを確認するテストが CI で動く
- webrtc-rs を m156.8078.3.0 に上げた状態で `cargo test --features source-build` のリンクまで通る
- CHANGES.md に変更内容を記録する

## テスト戦略

配布物がリンク可能であることを確認するテストを追加する。m156 で実際に壊れたのは「実行ファイルを作るリンク」なので、アーカイブのメンバー数ではなくリンクの成否で判定する。

- `run.py` に、ビルド済みの `libwebrtc.a` (Windows は `webrtc.lib`) をリンクして実行ファイルを作るサブコマンドを追加する。プラットフォームごとのコンパイラ・sysroot・include の知識は `run.py` が既に持っているため、テスト側で再実装しない
- リンクするコードは Rust の実装を必要とするものにする。`CorruptionDetectionExtension` を呼ぶ小さな C++ ファイルを用意する
- GitHub Actions の `build.yml` で、各プラットフォームのビルド直後にこのテストを実行する
- クロスコンパイルのターゲット (armv8 / android など) はリンクまで、ネイティブで動くターゲット (ubuntu-24.04_x86_64 / macos_arm64 / windows_x86_64) は実行ファイルの起動まで確認する

## 解決方法

- `run.py` の `archive_objects` を `merge_rust_objects` に置き換え、GN の完全な静的ライブラリをコピーしてから、GN がリンクに渡す静的ライブラリ・オブジェクトと rlib の中身を `ar -rc` で追加する
  - rlib の一覧は `find_build_rlibs` が `ninja -t query` で `obj/libwebrtc.a` の alink の入力を調べて取る
  - C++ ランタイムの一覧は `find_runtime_libraries` がビルドディレクトリの中の `libc++.a` と `libc++abi.a` と compiler-rt の `atomic.o` を探して返す
  - `collect_archive_objects` がアーカイブごとに別のディレクトリへ `ar x` で展開し、`*.o` だけを集める。`lib.rmeta` と `lib.rmeta-link` はコードを含まないメタデータなので加えない。thin アーカイブは `ar t` のメンバーのパスをそのまま使う
  - `append_objects` が同名のメンバーを中身で比べ、同じなら足さず、違うなら `1_charconv.o` のように別名にして足す
  - `rename_rust_symbols` が Rust のオブジェクトの `rust_eh_personality` と `DW.ref.rust_eh_personality` を `llvm-objcopy --redefine-sym` で `webrtc_` を付けた名前に変える
  - `find_files` は `cmdcap(["find", ...])` ではなく Python で辿るようにした。Windows には POSIX の find が無いため
- Windows 向けに `merge_rust_objects_windows` を追加し、`lld-link /lib /machine:<arch>` に `obj/webrtc.lib`、rlib、compiler-rt の builtins を渡して `webrtc.lib` を作る
  - builtins は `llvm-build/Release+Asserts/lib/clang/<version>/lib/windows/clang_rt.builtins-<arch>.lib` を `find_compiler_rt_builtins` が探す
- `tests/link_test.cc` に、配布するアーカイブの関数を呼び出すプログラムを置く。`CorruptionDetectionExtension` の parse に加えて、スレッドとタスクキュー、`PeerConnectionFactory`、映像フレームを扱う
  - `run.py test-link <target>` が GN の ninja からコンパイルとリンクのフラグを読み、WebRTC と同じコンパイラで `tests/link_test.cc` をコンパイルし、アーカイブだけをリンクして実行ファイルを作る
  - GN のリンクは rlib や C++ のランタイムをリンカに直接渡すため、アーカイブが自己完結していなくてもリンクできてしまう。アーカイブだけを渡すことで、配布するアーカイブが単体で使えることを確かめる
  - パッチを当てて GN にテスト用のターゲットを足す方法は、パッチのメンテナンスコストに見合う利点が無いので使わない
- `run.py test-link <target>` でそのターゲットをビルドして実行する。ネイティブで動くターゲットだけ実行し、クロスコンパイルのターゲットはリンクまで確認する
- ローカルの ubuntu-24.04_x86_64 で `python3 run.py build` → `python3 run.py test-link` → webrtc-rs の `cargo test --workspace --features source-build` まで確認する
- `build.yml` の各プラットフォームのビルド直後に `python3 run.py test-link` を実行する
- CHANGES.md に変更内容を記録する

### 実測した結果

m156 の新しい配布用アーカイブ (ubuntu-24.04_x86_64) は 3517 メンバーで、GN の 3165 メンバーに libc++ などの 67 オブジェクトと Rust の 285 オブジェクトを足したものになる。土台のメンバーの欠落は 0、入れ子のアーカイブは 0 で、ホストツール (nasm / protobuf) は含まない。

| リンク方法 | 結果 |
| --- | --- |
| 通常リンク | 成功 (実行も成功) |
| `--whole-archive` | 成功 (実行も成功) |
| `--whole-archive` + `--no-gc-sections` | 未定義 56 個 (すべて X11)。Rust の未定義は 0 |
| GN の `obj/libwebrtc.a` (参考) | 未定義 12 個 (Rust) で失敗 |
| webrtc-rs の `cargo test --workspace --features source-build` | 成功 (テスト 201 件) |

- `--whole-archive` はアーカイブだけをリンクした場合の結果。GN のリンク行と同じように `libc++.a` を重ねてリンクすると、libc++ と libc++abi が同じシンボルを持つため重複定義になる
- webrtc-rs は `allow-multiple-definition` のようなリンカオプションを足さずにリンクできる。`rust_eh_personality` を `webrtc_rust_eh_personality` に改名しているため、利用者の Rust の std と衝突しない

m155 では GN 版 (2986 メンバー) が `--whole-archive` まで成功するのに対し、find 版 (3181 メンバー) はホストツールの `main` が重複して失敗する。Rust は不要なため、この変更は m155 ではアーカイブが小さくなる以外の影響が無い。

Windows は x86_64 と arm64 の両方で `webrtc.lib` を作り直し、x86_64 は `lld-link` と MSVC の `link.exe` の両方でリンクと実行に成功する。arm64 はリンカでのリンクまでを確認し、実行の確認は CI で行う。

### 確認したこと

- `ios_sdk` と `android_sdk` の配布物は静的ライブラリを含まない。`ios_sdk` の `WebRTC.xcframework` は GN の `shared_library` が作る dylib、`android_sdk` の `libwebrtc.aar` は GN の `shared_library` が作る `.so` で、どちらも GN のリンクに rlib が渡されるため Rust の実装が入っている。上流のスクリプトがソースディレクトリの `out` 以下に作る静的ライブラリは配布していない (`package_webrtc` がコピーするのは xcframework と aar だけ)。そのためこの 2 つはリンクテストの対象外にしている

### 残っている作業

- Windows の Rust の std も `rust_eh_personality` を定義するため、Windows の Rust の下流では重複定義になる可能性がある。Windows は `lld-link /lib` で合体しており `llvm-objcopy --redefine-sym` を通していない。COFF で改名するか `/FORCE:MULTIPLE` を案内するかを決める必要がある
- `llvm-objcopy --redefine-sym` が macOS (Mach-O) と Windows (COFF) で使えるかは未確認。今のローカルの確認は ubuntu-24.04_x86_64 (ELF) だけなので、他のプラットフォームで使えない場合は代替手段を検討する必要がある
