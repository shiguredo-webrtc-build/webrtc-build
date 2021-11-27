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

初回の build コマンド実行時には、自動的に WebRTC のソースやツールのダウンロードやパッチの適用をした上でビルドされる。

2回目の build コマンドの実行時には、ビルドのみ行われる。WebRTC ソースの更新や、gn gen の再実行は行われない。

もう少し細かく書くと、build コマンドをオプション引数無しで実行した場合、以下のことを行なっている。

- 必要な WebRTC のソースやツールが存在しない場合、ダウンロードしてから WebRTC ソースに時雨堂パッチを当てる
- まだ ninja ファイルが存在しない場合、gn gen コマンドで ninja ファイルを生成する
- ninja コマンドでビルドする

2回目の実行では WebRTC のソースやツールや、ninja ファイルが既に存在しているため取得・生成されず、単にビルドだけが行われる。

WebRTC のソースを手で書き換えた場合は、単にもう一度 build コマンドを実行するだけで良い。

### --webrtc-fetch

WebRTC のソースをリポジトリから取得し直したい場合は `--webrtc-fetch` 引数を利用すれば良い。

```
python3 run.py build <target> --webrtc-fetch
```

これで WebRTC のソースは `VERSION` ファイルの `WEBRTC_COMMIT` に書かれた内容になり、その上でパッチを当てた状態でビルドされる。

ソースを手で書き換えた部分や追加したファイルも含め、全て元に戻るので注意すること。

なお既存のソースを全て破棄して取得し直す `--webrtc-fetch-force` 引数も存在する。

### --webrtc-gen

同様に gn gen コマンドを実行し直したい場合は `--webrtc-gen` 引数を利用すれば良い。

```
python3 run.py build <target> --webrtc-gen
```

これで gn gen を実行し直した上でビルドされる。

なお既存のビルドディレクトリを全て破棄して生成し直す `--webrtc-gen-force` 引数も存在する。

### iOS, Android のビルド

iOS の `WebRTC.xcframework`、Android の `webrtc.aar` は、他の場合と変わらず build コマンドで生成できる。

ただし `--webrtc-gen` コマンドは効かず、常に gn gen が実行される。

また、iOS や Android の `libwebrtc.a` が欲しいだけの状況で `WebRTC.xcframework` や `webrtc.aar` が生成されるのは無駄なので、
その場合は `--webrtc-nobuild-ios-framework` または `--webrtc-nobuild-android-aar` を利用すれば良い。

### ディレクトリ構成

- ソースは `_source` 以下に、ビルド成果物は `_build` 以下に配置される。
- `_source/<target>/` や `_build/<target>/` のように、`_source` と `_build` のどちらも、ターゲットごとに別のディレクトリに分けられる。
- `_build/<target>/<configuration>` のように、`_build` はデバッグビルドかリリースビルドかで別のディレクトリに分けられる。

つまりデフォルトでは以下のような配置になる。

```
webrtc-build/
|-- _source/
|   |-- ubuntu-20.04_x86_64/
|   |   |-- depot_tools/...
|   |   `-- webrtc/...
|   `-- android/
|       |-- depot_tools/...
|       `-- webrtc/...
`-- _build/
    |-- ubuntu-20.04_x86_64/
    |   |-- debug/
    |   |   `-- webrtc/...
    |   `-- release/
    |       `-- webrtc/...
    `-- android/
        |-- debug/
        |   `-- webrtc/...
        `-- release/
            `-- webrtc/...
```

また、ソースディレクトリやビルドディレクトリは以下のオプションを指定することで任意の場所に変更できる。

- `--source-dir`: ソースディレクトリ
  - デフォルトは `<run.pyのあるディレクトリ>/_source/<target名>` 
  - ただし Windows の場合は `C:\webrtc` になる（パスが長いとビルドエラーになってしまうため）
- `--webrtc-source-dir`: WebRTC のソースを配置するディレクトリ。`--source-dir` よりもこちらの設定を優先する。
  - デフォルトは `<source-dir>/webrtc` 
- `--build-dir`: ビルドディレクトリ
  - デフォルトは `<run.pyのあるディレクトリ>/_build/<target名>/<configuration>` 
  - Windows の場合は `C:\webrtc-build\<configuration>`
- `--webrtc-build-dir`: WebRTC のビルド成果物を配置するディレクトリ。`--build-dir` よりもこちらの設定を優先する。
  - デフォルトは `<build-dir>/webrtc` 

これらのディレクトリは、カレントディレクトリからの相対パスで指定可能となっている。

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