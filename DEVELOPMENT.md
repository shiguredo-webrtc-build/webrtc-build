# 開発者用ドキュメント

## ローカルでのビルド

`run.py` を利用すると、WebRTC をローカルでビルド可能になる。

以下のコマンドでビルドする

```
python3 run.py build <target>
```

`<target>` の部分には、`windows` や `ubuntu-20.04_x86_64` 等のターゲット名が入る。
詳細は `python3 run.py --help` や `python3 run.py build --help` 等を参照すること。

これで `_build` 以下のディレクトリに `libwebrtc.a` 等のライブラリが生成される。
WebRTC のソースやツール、パッチの適用は初回実行時に自動的に行われる。

この後、2回目の build コマンドの実行では **ビルドのみ行う**。
WebRTC ソースの更新や、gn gen の再実行は行わないため、取得した WebRTC のソースを任意に書き換えてビルドが楽に出来るようになっている。

もう少し細かく書くと、build コマンドをオプション引数無しで実行した場合、以下のことを行なっている。

- 必要な WebRTC のソースやツールが存在しなければ、ダウンロードしてから WebRTC ソースに時雨堂パッチを当てる
- まだ ninja ファイルが存在しなければ、gn gen コマンドで ninja ファイルを生成する
- ninja コマンドでビルドする

こうなっているため、2回目の実行では WebRTC のソースやツールや、ninja ファイルが存在しているため取得・生成されず、単にビルドだけが行われる。

WebRTC のソースを手で書き換えた場合は、単にもう一度 build コマンドを実行するだけで良い。

### --webrtc-fetch

WebRTC のソースをリポジトリから取得し直したい場合は `--webrtc-fetch` 引数を利用すれば良い。

```
python3 run.py build <target> --webrtc-fetch
```

これで WebRTC のソースは `VERSION` ファイルの `WEBRTC_COMMIT` に書かれた内容になり、その上でパッチを当てた状態でビルドされる。
ソースを手で書き換えた部分や追加したファイルも含め、全て元に戻るので注意すること。

なお既存のソースを全て破棄して取得し直す `--webrtc-fetch-force` コマンドも存在する。

### --webrtc-gen

同様に gn gen コマンドを実行し直したい場合は `--webrtc-gen` 引数を利用すれば良い。

```
python3 run.py build <target> --webrtc-gen
```

これで gn gen を実行し直した上でビルドされる。

なお既存のビルドディレクトリを全て破棄して生成し直す `--webrtc-gen-force` コマンドも存在する。

### iOS, Android のビルド

iOS の `WebRTC.xcframework`、Android の `webrtc.aar` は、他の場合と変わらず build コマンドで生成できる。
ただし `--webrtc-gen` コマンドは効かず、常に gn gen が実行される。

また、iOS や Android の `libwebrtc.a` が欲しいだけの状況で `WebRTC.xcframework` や `webrtc.aar` が生成されるのは無駄なので、
その場合は `--webrtc-nobuild-ios-framework` または `--webrtc-nobuild-android-aar` を利用すれば良い。

### ディレクトリ構成

- ソースは `_source` 以下に、ビルドで生成されたファイルは `_build` 以下にある。
- `_source/<target>/` や `_build/<target>/` のように、`_source` と `_build` のどちらも、ターゲットごとに別のディレクトリに分けられる。
- `_build/<target>/<configuration>` のように、`_build` はデバッグビルドかリリースビルドかで別のディレクトリに分けられる。

つまり以下のようになる。

```
webrtc-build/_source/ubuntu-20.04_x86_64/webrtc/...
webrtc-build/_source/android/webrtc/...
webrtc-build/_build/ubuntu-20.04_x86_64/debug/webrtc/...
webrtc-build/_build/ubuntu-20.04_x86_64/release/webrtc/...
webrtc-build/_build/android/debug/webrtc/...
webrtc-build/_build/android/release/webrtc/...
```

ソースディレクトリやビルドディレクトリを手で指定可能な仕組みは現在存在しないが、必要なら作るかもしれない。

### 制限

ローカルでのビルドは、以下の制限がある。

- Windows の場合は `windows` ターゲットのみビルド可能。
- macOS の場合は `macos_x86_64`, `macos_arm64`, `ios` ターゲットのみビルド可能。
- Ubuntu の x86_64 環境の場合、上記以外のターゲットのみビルド可能。
  - `android`, `raspberry-pi-os_armv*`, `ubuntu-*_armv8` あたりの ARM 環境は Ubuntu のバージョンに関係なくビルド可能
  - `ubuntu-18.04_x86_64` の場合は Ubuntu 18.04 が必要
  - `ubuntu-20.04_x86_64` の場合は Ubuntu 20.04 が必要
- Ubuntu の x86_64 でない環境ではビルド不可能。
- Ubuntu 以外の Linux 系 OS ではビルド不可能。