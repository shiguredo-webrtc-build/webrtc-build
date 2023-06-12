# パッチ開発支援ツールについて

本文書では、本リポジトリ用に用意したパッチ開発支援ツール `patchdev.py` について説明します。 `patchdev.py` は `scripts/patchdev.py` にあります。


## 目的

本ツールの主な目的は次の 2 つです。

- 開発中のパッチに関するソースコードを Git で管理できるようにする
- パッチファイルの作成など、パッチ開発で多用する操作を簡略にする


## 機能

本ツールは以下の機能を提供します。

- 開発中のソースコードを libwebrtc のリポジトリ外で編集・管理できるようにする
- 開発中のソースコードを libwebrtc に組み込んでビルドする
- パッチファイルを作成する
- JNI 用の C/C++ ヘッダーファイルを生成する


## 対応プラットフォーム

本ツールは以下の環境で動作します。

- macOS
- Windows
- Linux


## パッチ開発の流れ

パッチ開発の流れは次のようになります。

### プロジェクトを作成する

トップレベルで `patchdev.py init` を実行してプロジェクトを作成します。引数にプラットフォームとプロジェクト名を指定します。

例:

```
python3 scripts/patchdev.py init ios ios-simulcast
```

このコマンドは次の処理を行います:

1. プロジェクト用のディレクトリを作成する
2. パッチを適用せずにビルドを行う


#### プロジェクト用のディレクトリを作成する

 `patchdev` 以下にプロジェクト用のディレクトリ (`ios-simulcast`) が作成されます。このディレクトリには以下のファイルが含まれます。

```
Makefile
README.md
config.json
src/
```

`Makefile` は `patchdev.py` のサブコマンドを実行するターゲットを定義しており、 `patchdev.py` を直接使わずに `make` を使用して操作することができます。以降の説明は `make` を使用します。

`README.md` はプロジェクトの説明を記述するファイルです。

`config.json` はパッチに関する設定ファイルです。以降の節で説明します。

`src` は編集するソースコードを配置するディレクトリです。このディレクトリに必要なソースコードをコピーして編集します。トップレベルにある libwebrtc のソースコード (`_source` 以下) を直接編集する必要はありません。

この他に、他のコマンドにより `_build` が作成されます。 `_build` はリポジトリに含めないでください。


#### パッチを適用せずにビルドを行う

プロジェクト用のディレクトリの作成後、一度パッチを適用せずにビルドを行います。このビルドで libwebrtc のソースコードを取得し、フックの実行やビルドファイルの生成などを行い、パッチの開発に必要な環境を整えます。

ビルドが必要なければ `--nobuild` オプションを指定してください。


## 設定ファイルを編集する

`config.json` を編集し、編集するソースコードを指定します。以下に設定例を示します:

```
{
    "output": "ios_simulcast.patch",
    "platform": "ios",
    "build_flags": "--debug",
    "sources": [
        "sdk/BUILD.gn",
        "sdk/objc/base/RTCVideoCodecInfo.h",
        "sdk/objc/base/RTCVideoCodecInfo.m",
        "sdk/objc/api/peerconnection/RTCRtpEncodingParameters.h",
        "sdk/objc/api/peerconnection/RTCRtpEncodingParameters.mm",
        "sdk/objc/api/peerconnection/RTCVideoCodecInfo+Private.mm",
        "sdk/objc/api/video_codec/RTCVideoEncoderSimulcast.h",
        "sdk/objc/api/video_codec/RTCVideoEncoderSimulcast.mm",
        "sdk/objc/components/video_codec/RTCVideoEncoderFactorySimulcast.h",
        "sdk/objc/components/video_codec/RTCVideoEncoderFactorySimulcast.mm"
    ],

    # JNI 用の設定。必要ない場合は無視してください。
    "jni_classpaths": ["sdk/android/api"],
    "jni_classes": {
        "org.webrtc.Example": "sdk/android/src/jni/example.h"
    }
}
```

- `output`: パッチファイル名を指定します。このファイルは `make patch` で作成されます。
- `platform`: プラットフォームを指定します。この値は libwebrtc のソースコードのパス (`_source`) とビルド時のオプション (`run.py`) に使用されます。
- `build_flags`: `run.py` に渡すオプションを指定します。
- `sources`: 編集するソースコードのパスを指定します。
- `jni_classpaths`, `jni_classes`: JNI 用の設定です。後述します。


### パッチを適用せずにビルドする (オプション)

libwebrtc のソースコードには、ビルド時 (またはフェッチ時) に生成されるファイルがあります。編集するソースコードが自動的に生成されるファイルである場合、パッチを適用せずにビルドしておく必要があります。 libwebrtc のリポジトリをダウンロードし直した場合も同様です。

パッチを適用せずにビルドするには、 `make build-skip-patch` を実行します。このコマンドは `config.json` の設定にしたがって `run.py` を実行します。ただし、 `config.json` で指定したパッチは無視します。


### オリジナルのソースコードをコピーする

設定ファイルを編集したら `make sync` を実行します。 `make sync` は設定ファイルに指定したソースコードを `src` にコピーします。前記の `config.json` の例だと、 `make sync` 実行後のディレクトリは次のようになります。

```
└── src
    └── sdk
        ├── BUILD.gn
        └── objc
            ├── api
            │   ├── peerconnection
            │   │   ├── RTCRtpEncodingParameters.h
            │   │   ├── RTCRtpEncodingParameters.mm
            │   │   └── RTCVideoCodecInfo+Private.mm
            │   └── video_codec
            │       ├── RTCVideoEncoderSimulcast.h
            │       └── RTCVideoEncoderSimulcast.mm
            ├── base
            │   ├── RTCVideoCodecInfo.h
            │   └── RTCVideoCodecInfo.m
            └── components
                └── video_codec
                    ├── RTCVideoEncoderFactorySimulcast.h
                    └── RTCVideoEncoderFactorySimulcast.mm
```

編集するソースコードを追加する場合は、 `config.json` を編集してソースコードのパスを追加してから再度 `make sync` を実行してください。 `make sync` は `src` 以下に存在しないファイルのみコピーします。


#### JNI 用の C/C++ ヘッダーファイルを生成する (オプション)

JNI 用のパッチを開発する場合は、 `javah` で C/C++ のヘッダーファイルを生成する必要があります。 `config.json` を編集して JNI の設定を記述し、 `make jni` を実行します。 `make jni` は `javah` を実行して C/C++ のヘッダーファイルを生成し、 `src` 以下に出力します。

`javah` は事前にマシンにインストールしておいてください。 libwebrtc のソースコードにはビルドに使われるサードパーティーのツールが含まれていますが、 `javah` は含まれていません。

JNI 用の `config.json` の設定例を以下に示します:

```json
{
    "jni_classpaths": [
        "sdk/android/api"
    ],
    "jni_classes": {
        "org.webrtc.SimulcastVideoEncoder": "sdk/android/src/jni/simulcast_video_encoder.h"
    }
}
```

- `jni_classpaths`: クラスパス (`-classpath` オプション) のリストを指定します。指定したクラスパスは、 libwebrtc のソースコードのディレクトリに適用されます。上記の例だと、 `javah` に渡されるクラスパスは `../../_sources/sdk/android/api` (の絶対パス) になります。
- `jni_classes`: ヘッダーファイルを生成するクラスと出力ファイルパスをペアで指定します。

上記の設定例では、 `make jni` で以下のコマンドが実行されます:

```
javah -classpath TOP/_source/android/webrtc/src/sdk/android/api -o simulcast_video_encoder.h org.webrtc.SimulcastVideoEncoder
```


### パッチを実装する

パッチの開発は `src` 以下のソースコードを編集してください。

`make check` を実行すると、ファイル終端の改行の有無をチェックできます。ビルドやパッチ作成時は自動的にチェックしますが、手動でチェックする場合に使ってください。


### ビルドする

`make build` を実行すると、編集したソースコードを libwebrtc のソースコードのディレクトリにコピーしてから `run.py` でビルドします。以降の挙動は `run.py` と同じです。トップレベルの `_build` 以下にビルド結果が出力されます。


### パッチファイルを生成する

`make patch` を実行すると、編集したソースコードとオリジナルのソースコードとの差分をまとめてパッチファイルを生成します。パッチファイルは `config.json` の `output` で指定したファイル名で `_build` 以下に出力されます。たとえば `output` に `ios_simulcast.patch` を指定すると、 `_build/ios_simulcast.patch` が生成されます。

パッチの開発が終わったら、生成したパッチファイルをトップレベルの `patches` にコピーしてください。

なお、編集したソースコードのファイルの終端が改行でない場合はエラーになります。ファイル終端に改行を追加してから再度 `make patch` を実行してください。


### その他の操作

#### 差分を表示する

`make diff` を実行します。 `make diff` の挙動は、パッチファイルを生成する以外は `make patch` と同じです。


#### オリジナルのソースコードに加えた変更を元に戻す

`make clean` を実行します。 `make build` の実行時にオリジナルのソースコードに加えた変更を元に戻します。


## サブコマンド

以下は `patchdev.py` の各サブコマンドの詳細な説明です。 `init` 以外は、プロジェクトごとに生成される `Makefile` で実行できます。

### `init`

トップレベルの `patchdev` 以下に新しいプロジェクトを作成します。以下のファイルを生成します:

- `Makefile`: `patchdev.py` のサブコマンドを実行するターゲットを定義してあります。
- `config.json`: パッチに関する設定ファイルです。
- `src/`: このディレクトリにソースコードを配置します。設定ファイルでソースコードを指定して `make sync`を実行すると、オリジナルのファイルがこのディレクトリにコピーされます。


### `sync`

設定ファイルで指定したファイルを`src` にコピーします。ただし、既に `src` に存在するファイルはコピーされません。


### `build`

`src` のソースコードを libwebrtc のソースコードがあるディレクトリにコピーし、 `run.py` を使用してビルドします。設定ファイルで指定されたプラットフォームが対象になります。

`run.py` に渡すコマンドラインオプションを指定するには、渡したいオプションを設定ファイルで `build_flags` に指定します。

`--skip-patch` オプションを指定すると、パッチを適用せずにビルドします。


### `build-skip-patch` (`Makefile` のみ)

パッチを適用せずにビルドします。このコマンドは `Makefile` でのみ実行できます。 `patchdev.py build --skip-patch` と同じです。


### `check`

`src` のファイル終端の改行の有無をチェックします。改行が存在しなければエラーになります。


### `diff`

`src` のソースコードとオリジナルのソースコードとの差分を表示します。ファイル終端の改行の有無もチェックします。


### `patch`

パッチファイルを作成します。すべての差分を 1 つのファイルにまとめます。事前にファイル終端の改行の有無をチェックします。

パッチファイルは `_build` 以下に生成されます。ファイル名は設定ファイルの `output` で指定します。

パッチ開発が終わったら、パッチファイルをトップレベルの `patches` ディレクトリにコピーしてください。


### `clean`

`build` コマンドでオリジナルに加えたすべての変更を元に戻し、 `_build` を削除します。 `src` のファイルに影響はありません。
