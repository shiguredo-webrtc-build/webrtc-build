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
- `--webrtc-source-dir`: WebRTC のソースを配置するディレクトリ。`--source-dir` よりもこちらの設定を優先する。
  - デフォルトは `<source-dir>/webrtc` 
- `--build-dir`: ビルドディレクトリ
  - デフォルトは `<run.pyのあるディレクトリ>/_build/<target名>/<configuration>` 
- `--webrtc-build-dir`: WebRTC のビルド成果物を配置するディレクトリ。`--build-dir` よりもこちらの設定を優先する。
  - デフォルトは `<build-dir>/webrtc` 

これらのディレクトリは、カレントディレクトリからの相対パスで指定可能となっている。

### 制限

ローカルでのビルドは、以下の制限がある。

- Windows の場合は `windows` ターゲットのみビルド可能。
- macOS の場合は `macos_x86_64`, `macos_arm64`, `ios` ターゲットのみビルド可能。
- Ubuntu の x86_64 環境の場合、上記以外のターゲットのみビルド可能。
  - `android`, `raspberry-pi-os_armv*`, `ubuntu-*_armv8` あたりの ARM 環境は Ubuntu のバージョンに関係なくビルド可能
  - `ubuntu-20.04_x86_64` の場合は Ubuntu 20.04 が必要
  - `ubuntu-22.04_x86_64` の場合は Ubuntu 22.04 が必要
  - `ubuntu-24.04_x86_64` の場合は Ubuntu 24.04 が必要
- Ubuntu の x86_64 でない環境ではビルド不可能。
- Ubuntu 以外の Linux 系 OS ではビルド不可能。

## ソースの取得

WebRTC のソースをリポジトリから取得し直したい場合は `fetch` コマンドを利用すれば良い。

```
python3 run.py fetch <target>
```

これで WebRTC のソースは `VERSION` ファイルの `WEBRTC_COMMIT` に書かれた内容になり、その上でパッチを当てた状態になる。ビルドは行わない。

ソースを手で書き換えた部分や追加したファイルも含め、全て元に戻るので注意すること。

## 編集したソースを元に戻す

WebRTC のソースを元に戻したい場合や、パッチを当て直す場合は `revert` コマンドを利用すれば良い。

```
python3 run.py revert <target>
```

これは関連する全てのリポジトリに対して `git clean -df` と `git reset --hard` を実行する。

また、パッチを編集する際には `--patch` コマンドを使うと良い

```
python3 run.py revert <target> --patch <patch>
```

これによって、このパッチより前に当てるべきパッチを適用/コミットした後、このパッチを適用し、コミットしていない状態になる

`--patch` オプションで指定したパッチのコミットも行っておきたい場合、`--commit` オプションを指定する。

```
python3 run.py revert <target> --patch <patch> --commit
```

これによって、このパッチまでの全てのパッチが適用/コミットされる。

`--commit` オプションは、パッチの適用順序を変えたい場合に利用する。

## libwebrtc のソース差分を出力する

WebRTC のソースの差分を確認する場合、以下のコマンドを利用する

```
python3 run.py diff <target>
```

## パッチを作成する

新しいパッチを作成する場合、以下の手順で行う

1. `python3 run.py revert <target>` コマンドでソースを綺麗にする
2. libwebrtc のソースを編集する
3. `python3 run.py diff <target>` コマンドで差分を確認した後、問題なければ `python3 run.py diff <target> > <patch>` でパッチをファイルに出力する
4. run.py の PATCHES に追加したパッチを最後に付け加える
5. `python3 run.py revert <target>` でパッチが正しく適用されているか確認する

上記の方法は追加したパッチを最後に適用する場合の方法である。

パッチの途中に新しいパッチを適用したい場合は、`--patch` と `--commit` オプションを利用する。

1. `python3 run.py revert <target> --patch <patch> --commit` コマンドで、新しく作るパッチより前に適用しておきたいパッチを適用しておく
2. libwebrtc のソースを編集する
3. `python3 run.py diff <target>` コマンドで差分を確認した後、問題なければ `python3 run.py diff <target> > <patch>` でパッチをファイルに出力する
4. run.py の PATCHES に、追加したパッチを最初に追加したパッチの次の位置に付け加える
5. `python3 run.py revert <target>` でパッチが正しく適用されているか確認する
  - 適用順序が変わっているので、以降のパッチ適用でエラーが発生する可能性もある

## パッチを編集する

既存のパッチを編集する場合、以下の手順で行う

1. `python3 run.py revert <target> --patch <patch>` コマンドで、このパッチを適用してコミットしていない状態にする
2. libwebrtc のソースを編集して正しい状態にする
3. `python3 run.py diff <target>` コマンドで差分を確認した後、問題なければ `python3 run.py diff <target> > <patch>` でパッチを上書きする
4. `python3 run.py revert <target>` でパッチが正しく適用されているか確認する

## エラーになったパッチを修正する

基本的にはパッチを編集する場合と同じ。

```bash
# エラーになっているブランチをチェックアウト
git checkout feature/<libwebrtc-version>
# エラーになっているバージョンを取ってくる
python3 run.py fetch <target>
```

この `fetch` 時に、どれかのパッチ適用でエラーになっているのが前提となる。

1. エラーになったパッチファイルを確認して `python3 run.py revert <target> --patch <patch>` コマンドを実行する
  - この時にエラーが出るけれども、気にせず次に進む
2. libwebrtc のソースを編集して正しい状態にする
  - 元のパッチファイルの差分を見て、どうするべきかを考えて修正する
  - 場合によっては旧バージョンのソースファイルも確認する必要があるかもしれないが、ローカルにダウンロードするのは大変なので https://source.chromium.org/chromium あたりから探すのが良い
3. `python3 run.py diff <target>` コマンドで差分を確認した後、問題なければ `python3 run.py diff <target> > <patch>` でパッチを上書きする
4. `python3 run.py revert <target>` でパッチが正しく適用されているか確認する

## libwebrtc に新しいバージョンがあるか確認する

libwebrtc に新しいバージョンがあるか確認する場合、以下のコマンドを利用する

```
$ python3 run.py version_list
m126 6478 1 a18e38fed2307edd6382760213fa3ddf199fa181
m125 6422 2 8505a9838ea91c66c96c173d30cd66f9dbcc7548
m124 6367 3 a55ff9e83e4592010969d428bee656bace8cbc3b
m123 6312 3 41b1493ddb5d98e9125d5cb002fd57ce76ebd8a7
m122 6261 1 6b419a0536b1a0ccfff3682f997c6f19bcbd9bd8
```

## libwebrtc のバージョンを変更する

libwebrtc のバージョンを変更する場合、以下のコマンドを利用する

```
$ python3 run.py version_update m126
```

ただし、バージョンの更新は GitHub Actions によって自動で行われるため、基本的に手動で行う必要はない。
