# Windows のビルドを libwebrtc の既定 (libc++) に合わせる

- Created: 2026-10-09
- Completed: {YYYY-MM-DD}
- Branch: feature/change-windows-libcxx-build
- Polished: {YYYY-MM-DD}

## 目的

Windows のビルドは `use_custom_libcxx=false` を指定して MSVC の標準ライブラリに合わせているが、この指定は upstream が非推奨としており、いずれ削除される。削除された時点で Windows のアーカイブは libc++ で作られるか、ビルドが失敗する。前者の場合、MSVC と静的 CRT を前提にしている下流 (sora-cpp-sdk / webrtc-rs) はそのアーカイブをリンクできなくなる。upstream の既定に合わせて libc++ でビルドし、下流も libwebrtc と同じ clang + libc++ に移行できる状態にしておく。

## 現状

### Windows だけが upstream の既定を倒している

`run.py` の `build_webrtc` の Windows 分岐が `use_custom_libcxx=false` と `use_custom_libcxx_for_host=false` を指定している。`use_custom_libcxx_for_host` は 2025-05-31 の "libcxx が有効になってることがあったのを修正" で追加されたもので、ホストツールチェーン側に libc++ が入るのを防いでいる。

upstream の `build/config/c++/c++.gni` の `use_custom_libcxx` は既定が true (libc++) で、コメントに次のように書かれている。

```text
WARNING: Bringing your own C++ standard library is deprecated and will not be
supported in the future. This flag will be removed.
```

### 配布中のアーカイブは MSVC STL で作られている

`_build/windows_x86_64/release/webrtc/obj/webrtc.lib` を走査すると、libc++ のシンボル (`@__1@std@@`) は 0 件、MSVC STL のシンボル (`@std@@`) は 563,867 件で、MSVC STL が使われている。CI の `build.yml` も `run.py build` を素で呼ぶだけで gn の引数を上書きしないため、配布物にもこの設定が効いている。

### 下流は MSVC 前提

- webrtc-rs の `webrtc/CMakeLists.txt` は `WEBRTC_USE_WEBRTC_LIBCXX` と `WEBRTC_USE_WEBRTC_CLANG` を既定で true にし、"WebRTC との ABI 互換性のため" と "Windows 以外は WebRTC の Clang を使う" と書いたうえで、`WEBRTC_C_TARGET` が `windows_x86_64` のときだけ両方を false にしている
- sora-cpp-sdk の `CMakeLists.txt` は `MSVC_RUNTIME_LIBRARY "MultiThreaded..."` を指定しており、MSVC と静的 CRT でビルドする。提供する SDK の利用者 (Unity / Python / アプリ) も同じ前提でビルドすることになる

### libc++ の Windows 対応は生きている

Windows 向けのビルドディレクトリで `use_custom_libcxx=true` にして `gn gen` を通すと成功し、`//buildtools/third_party/libc++:libc++` のビルド対象に `support/win32/locale_win32.cpp`、`support/win32/thread_win32.cpp`、`compiler_rt_shims.cpp` が含まれる。m156 の libc++ に Windows の実装があり、libc++ を選べる状態になっている (確認したのは gen とビルド対象の存在まで)。

## 設計方針

- `run.py` の `build_webrtc` から `use_custom_libcxx` と `use_custom_libcxx_for_host` の指定を外し、libwebrtc の既定に従う
  - Windows でも libc++ の実装を配布アーカイブに含める必要がある。今は `find_cxx_runtime_archives` が `libc++.a` と `libc++abi.a` を探し、`merge_rust_objects` が Linux と macOS のアーカイブに足している。Windows の `merge_rust_objects_windows` はこの処理を通っていないため、同じ扱いにする
  - compiler-rt の builtins の同梱 (`find_compiler_rt_builtins`) を残すかどうかは、Rust の MSVC ターゲット (rustc は link.exe でリンクする) の下流が残る限り必要かどうかを含めて決める
- 下流を libwebrtc と同じ clang + libc++ に移行する。webrtc-rs は `webrtc/CMakeLists.txt` の `windows_x86_64` の例外を外し、sora-cpp-sdk は CMake のコンパイラ指定と CI を変える。SDK の利用者に clang + libc++ を要求することになるため、案内も要る
- `run.py` の `test_link_in` の Windows 実装を MSVC から clang に変える。配布物を検証するテストは配布物の設定に合わせる。これに伴いフラグを MSVC 向けに翻訳している `MSVC_COMPILE_FLAGS` は不要になる
- 下流の移行が終わるまで `use_custom_libcxx=false` は外せない。webrtc-build のリリースと下流の追随の順序を決めてから着手する

## 完了条件

- `use_custom_libcxx` を指定せずに `python3 run.py build windows_x86_64` と `python3 run.py build windows_arm64` が成功する
- `python3 run.py test-link windows_x86_64` が clang でコンパイルし、アーカイブだけをリンクして実行まで成功する
- webrtc-rs が Chromium の clang + libc++ で m156 以降のアーカイブを使い、`cargo test --features source-build` のリンクまで通る
- sora-cpp-sdk が Chromium の clang + libc++ でビルドできる
- CHANGES.md に変更内容を記録する

## テスト戦略

- `run.py test-link` の Windows を clang に切り替え、`build.yml` の windows_x86_64 で実行まで確認する
- 下流の実際のビルド (webrtc-rs の `cargo test --features source-build` と sora-cpp-sdk の CI) でリンクを確認する。アーカイブが自己完結しているかは `test-link` が見る

## 未確認

- libc++ での Windows の WebRTC 全体のビルド (gen と libc++ のビルド対象の存在までは確認済み)
- libc++ で作ったアーカイブを下流の clang からリンクしたときの成否
- upstream が `use_custom_libcxx` を削除する時期。削除されると Windows のビルドがどうなるか (libc++ に切り替わるか、指定がエラーになるか)
