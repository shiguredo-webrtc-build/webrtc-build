# Windows のビルドを libwebrtc の既定 (libc++) に合わせる

- Created: 2026-10-09
- Completed: 2026-10-14
- Branch: feature/change-windows-libcxx-build
- Polished: {YYYY-MM-DD}

## 目的

Windows のビルドを MSVC への依存から外し、libwebrtc の既定と同じ clang + libc++ に合わせる。

Windows のビルドは `use_custom_libcxx=false` を指定して MSVC の標準ライブラリに合わせているが、この指定は upstream が非推奨としており、いずれ削除される。削除された時点で Windows のアーカイブは libc++ で作られるか、ビルドが失敗する。前者の場合、MSVC と静的 CRT を前提にしている下流 (sora-cpp-sdk / webrtc-rs) はそのアーカイブをリンクできなくなる。upstream の既定に合わせて libc++ でビルドし、下流も libwebrtc と同じ clang + libc++ に移行できる状態にしておく。

外す依存は次の 4 つ。

- MSVC の C++ 標準ライブラリ (STL) への依存
- ビルドのコンパイラとリンカ (cl.exe / link.exe) への依存
- Visual Studio 同梱の LLVM ツール (llvm-ar / llvm-objcopy) への依存
- 下流の MSVC 前提

MSVC のヘッダ (`vcruntime.h` / `corecrt.h`) と Windows SDK、CRT (`ucrt` / `vcruntime` / `libcmt`) は対象外とする。clang-cl でも必ず要るもので、upstream の Windows 手順も Visual Studio のインストールを必須にしている。

## 現状

### Windows だけが upstream の既定を倒している

`run.py` の `build_webrtc` の Windows 分岐が `use_custom_libcxx=false` と `use_custom_libcxx_for_host=false` を指定している。`use_custom_libcxx_for_host` は 2025-05-31 の "libcxx が有効になってることがあったのを修正" で追加されたもので、ホストツールチェーン側に libc++ が入るのを防いでいる。

upstream の `build/config/c++/c++.gni` の `use_custom_libcxx` は既定が true (libc++) で、コメントに次のように書かれている。

```text
WARNING: Bringing your own C++ standard library is deprecated and will not be
supported in the future. This flag will be removed.
```

### 配布中のアーカイブは MSVC STL で作られている

`_build/windows_x86_64/release/webrtc/webrtc.lib` を走査すると、MSVC STL のシンボル (`@std@@`) が 563,861 件、libc++ のシンボル (`@__Cr@std@@`) が 0 件で、MSVC STL が使われている。libc++ の名前空間は `buildtools/third_party/libc++/__config_site` の `_LIBCPP_ABI_NAMESPACE` が `__Cr` にしているため、libc++ のシンボルは `@__1@std@@` ではなく `@__Cr@std@@` として現れる。

CI の `build.yml` も `run.py build` を素で呼ぶだけで gn の引数を上書きしないため、配布物にもこの設定が効いている。

### 下流は MSVC 前提

- webrtc-rs の `webrtc/CMakeLists.txt` は `WEBRTC_USE_WEBRTC_LIBCXX` と `WEBRTC_USE_WEBRTC_CLANG` を既定で true にし、"WebRTC との ABI 互換性のため" と "Windows 以外は WebRTC の Clang を使う" と書いたうえで、`WEBRTC_C_TARGET` が `windows_x86_64` のときだけ両方を false にしている
- sora-cpp-sdk の `CMakeLists.txt` は `MSVC_RUNTIME_LIBRARY "MultiThreaded..."` を指定しており、MSVC と静的 CRT でビルドする。提供する SDK の利用者 (Unity / Python / アプリ) も同じ前提でビルドすることになる

### Visual Studio 同梱の LLVM からツールを拾っている

`run.py` の `find_llvm_tool_windows` が `VCToolsInstallDir` から `<VS>/VC/Tools/Llvm/bin` を組み立て、無ければ PATH から `llvm-ar` と `llvm-objcopy` を探す。`merge_rust_objects_windows` が Rust の rlib を配布アーカイブに取り込むためにこの 2 つを使っており、Visual Studio の「C++ Clang Compiler for Windows」コンポーネントが無い環境ではビルドが失敗する。

この 2 つは upstream の手順にも同梱物にも無い。

- Chromium の Windows 手順 (`docs/windows_build_instructions.md`) が明示するコンポーネントは `Microsoft.VisualStudio.Workload.NativeDesktop` と `Microsoft.VisualStudio.Component.VC.ATLMFC` で、LLVM は挙げられていない。WebRTC の `docs/native-code/development/prerequisite-sw/README.md` はこの手順を参照している
- depot_tools の packaged toolchain の対象一覧 (`depot_tools/win_toolchain/package_from_installed.py` の `BuildFileList`) に `VC/Tools/Llvm` は無い
- Chromium の `third_party/llvm-build/Release+Asserts/bin` にも `llvm-ar` と `llvm-objcopy` は無い

### 上流の Windows 手順は Visual Studio のインストールを前提にしている

Chromium の Windows 手順は Visual Studio 2026 と Windows 11 SDK 10.0.28000.2270 のインストールを要求し、clang-cl を使うが Visual Studio のヘッダ・ライブラリ・一部ツールが必要だと書いている。

`build/vs_toolchain.py` の `DEPOT_TOOLS_WIN_TOOLCHAIN` の既定は 1 で、`gclient sync` の `win_toolchain` フックが depot_tools の packaged toolchain を落とす。これは `gs://chrome-wintoolchain` から gsutil で取得する Visual Studio + Windows SDK のイメージで、資格情報が無い場合は `get_toolchain_if_necessary.py` が `DEPOT_TOOLS_WIN_TOOLCHAIN=0` を促して失敗する。`run.py` も `DEPOT_TOOLS_WIN_TOOLCHAIN=0` を設定してローカルの Visual Studio を使っている。

### libc++ の Windows 対応は生きている

Windows 向けのビルドディレクトリで `use_custom_libcxx=true` にして `gn gen` を通すと成功する。`//buildtools/third_party/libc++:libc++` は source_set で、51 個のオブジェクトが `obj/buildtools/third_party/libc++/libc++/` に作られ、Windows 向けの実装として `locale_win32`、`support`、`thread_win32` が含まれる (確認したのは gen とビルド対象の存在まで)。

### Windows の libc++ は配布アーカイブに入らない

`build/config/c++/c++.gni` の `libcxx_target_type` は `is_win` かつ共有でないとき `source_set` になる。`build/config/BUILD.gn` の `common_deps` は `:executable_deps` / `:loadable_module_deps` / `:shared_library_deps` にしか公開されておらず、静的ライブラリは libc++ に依存しない。したがって `use_custom_libcxx=true` にしても `obj/webrtc.lib` に libc++ のオブジェクトは入らない。

Windows では `libc++.a` と `libc++abi.a` が作られないため、Linux と macOS で `find_cxx_runtime_archives` が `libc++.a` を探して `merge_rust_objects` が足している方法はそのままでは使えない。

また `build/config/c++/BUILD.gn` の `runtime_library` は Windows で libc++abi を使わない。libc++abi が実装するのは Itanium C++ ABI だけで、Windows で使う Microsoft ABI と異なるため。

### libc++ にしても clang-cl は MSVC のヘッダと Windows SDK を使う

`use_custom_libcxx=true` で gen した `toolchain.ninja` の `cc` ルールにも、`build/toolchain/win/setup_toolchain.py` が `INCLUDE` から組み立てた `-imsvc` で MSVC の `include` と Windows Kits の ucrt / um / shared などが渡る。C++ の標準ヘッダは `build/config/c++/BUILD.gn` の `runtime_library` が `-I` で渡す libc++ が先に解決される (clang は `-I` を `-isystem` と `-imsvc` より先に探す)。Windows では `-nostdinc++` を付けない。

## 設計方針

- `run.py` の `build_webrtc` から `use_custom_libcxx` と `use_custom_libcxx_for_host` の指定を外し、libwebrtc の既定に従う
- Rust の rlib を扱う `llvm-ar` と `llvm-objcopy` は Visual Studio から拾うのをやめ、LLVM の公式リリースから固定バージョンをダウンロードして使う
  - `llvmorg-23.1.3` の `clang+llvm-23.1.3-x86_64-pc-windows-msvc.tar.xz` (859.5 MiB、sha256 `9ee6a2192fbb30c776415af529927f76ca6b5d1d55699bb1315f9878e610b5b8`) を使う
  - `run.py` の Windows 向け環境設定 (`vswhere.exe` を落としている箇所) と同じく `download()` でビルドディレクトリに落とし、既に取り出していれば飛ばす
  - アーカイブ全体は展開せず、`tarfile` で `bin/llvm-ar.exe` と `bin/llvm-objcopy.exe` だけを取り出す (合計 26 MiB、約 66 秒)
  - ダウンロード後に sha256 を検証し、一致しなければ削除してエラーにする
  - ツールはホストで動くので、`windows_x86_64` と `windows_arm64` のどちらのターゲットでも x64 版を使う
  - より小さい `tar.zst` (263.5 MiB) は Windows の `tar.exe` (bsdtar) が展開できないため使わない
  - `llvm-objcopy` は `lib.rmeta` を含むアーカイブを扱えず rlib を直接渡せない。`merge_rust_objects_windows` の流れ (`collect_archive_objects` でメンバーを取り出し、`rename_rust_symbols` で改名し、`llvm-ar -rc` で組み直して `lld-link /lib` に渡す) はそのままにし、道具の入手元だけを変える
  - `find_llvm_tool_windows` はダウンロードしたディレクトリを見るだけにし、`VCToolsInstallDir` と PATH を見ない
- 配布アーカイブに libc++ のオブジェクトを入れる
  - `WEBTC_BUILD_TARGETS` の Windows に `buildtools/third_party/libc++` を足してオブジェクトをビルドさせ、`obj/buildtools/third_party/libc++/libc++/*.obj` を集めて `merge_rust_objects_windows` の `lld-link /lib` に渡す
  - libc++abi は Windows では使わないので入れない
- `compiler-rt` の builtins の同梱 (`find_compiler_rt_builtins`) を残すかどうかは、Rust の MSVC ターゲットの下流が残る限り必要かどうかを含めて決める
- `run.py` の `test_link_in` の Windows 実装を MSVC から clang に変える。配布物を検証するテストは配布物の設定に合わせる。これに伴いフラグを MSVC 向けに翻訳している `MSVC_COMPILE_FLAGS` は不要になる
- 下流を libwebrtc と同じ clang + libc++ に移行する。webrtc-rs は `webrtc/CMakeLists.txt` の `windows_x86_64` の例外を外し、sora-cpp-sdk は CMake のコンパイラ指定と CI を変える。SDK の利用者に clang + libc++ を要求することになるため、案内も要る
- 下流の移行が終わるまで `use_custom_libcxx=false` は外せない。webrtc-build のリリースと下流の追随の順序を決めてから着手する

## 完了条件

- Visual Studio の「C++ Clang Compiler for Windows」コンポーネントが無い環境で `python3 run.py build windows_x86_64` と `python3 run.py package windows_x86_64` が成功する
- `use_custom_libcxx` を指定せずに `python3 run.py build windows_x86_64` と `python3 run.py build windows_arm64` が成功する
- 配布アーカイブに libc++ の実装が入っている。`webrtc.lib` に libc++ のシンボル (`@__Cr@std@@`) が入っていることで確認する
- `python3 run.py test-link windows_x86_64` が clang でコンパイルし、アーカイブだけをリンクして実行まで成功する
- `python3 run.py test-link-rust windows_x86_64` が成功する
- webrtc-rs が Chromium の clang + libc++ で m156 以降のアーカイブを使い、`cargo test --features source-build` のリンクまで通る
- sora-cpp-sdk が Chromium の clang + libc++ でビルドできる
- CHANGES.md に変更内容を記録する

## テスト戦略

- `run.py test-link` の Windows を clang に切り替え、`build.yml` の windows_x86_64 で実行まで確認する
- `webrtc.lib` を走査し、`@__Cr@std@@` が入り `@std@@` が減っていることを確認する
- ダウンロードした `llvm-ar` と `llvm-objcopy` で配布アーカイブが作れることを確認する。あわせて、Visual Studio の LLVM を PATH から外した状態で `run.py package` が成功することを確認する
- 下流の実際のビルド (webrtc-rs の `cargo test --features source-build` と sora-cpp-sdk の CI) でリンクを確認する。アーカイブが自己完結しているかは `test-link` が見る

## 解決方法

`run.py` の Windows のビルドを clang + libc++ に切り替え、配布する `webrtc.lib` を自己完結させた。

- Windows だけ `use_custom_libcxx=false` を指定する分岐を削除し、upstream の既定どおり clang + libc++ でビルドする
- GN の `source_set` では Windows に `libc++.a` が作られないため、libc++ のオブジェクトを GN の入力から集めて `webrtc.lib` に入れる。libc++abi は Windows では Microsoft ABI を使うため入れない
- Rust の rlib を取り込む `llvm-ar` と `llvm-objcopy` を、Visual Studio 同梱の LLVM から拾うのをやめ、LLVM の公式リリースの Windows 向けアーカイブをダウンロードして使う。sha256 を検証し、`bin/llvm-ar.exe` と `bin/llvm-objcopy.exe` だけを展開する。`find_llvm_tool_windows` は `VCToolsInstallDir` と PATH を見ない
- `run.py test-link` と `test-link-rust` の Windows を、配布物と同じ clang-cl と lld-link でコンパイルとリンクするように変更する。MSVC の cl.exe と link.exe を使わなくなり、フラグを翻訳していた `MSVC_COMPILE_FLAGS` も削除する
- `webrtc.lib` を走査して `@__Cr@std@@` が入ることを確認した
- `run.py test-link windows_x86_64` と `run.py test-link-rust windows_x86_64` が成功し、`link_test.exe` と `link_test_rust.exe` が実行まで通ることを確認した
- `CHANGES.md` に変更内容を記録した

## 未確認

- libc++ で作ったアーカイブを下流の clang からリンクしたときの成否 (webrtc-build の `test-link` は通っている)
- compiler-rt の builtins を同梱し続ける必要があるか (Rust の MSVC ターゲットの下流が残る間)
- upstream が `use_custom_libcxx` を削除する時期。削除されると Windows のビルドがどうなるか (libc++ に切り替わるか、指定がエラーになるか)
