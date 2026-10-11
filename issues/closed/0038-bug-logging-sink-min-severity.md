# LoggingConfig で登録した sink の配信閾値が min_severity に従わない

- Created: 2026-10-11
- Completed: 2026-10-11
- Branch: feature/fix-logging-sink-min-severity
- Polished: {YYYY-MM-DD}

## 目的

`LoggingConfig::set_min_severity` で指定した閾値を、 `LoggingConfig::AddSink` で登録した sink への配信にも反映させる。

現状は sink の閾値が `LS_INFO` に固定されているため、 sink を登録した状態では次のようになる。

- `warning` / `error` / `none` を指定しても `LS_INFO` の行が sink へ届く
- `verbose` を指定しても `LS_VERBOSE` の行が sink へ届かない

webrtc-rs の `log::LoggingConfig::set_min_severity` は「この重大度より軽いメッセージは出力されない」と説明しており、 実態と一致していない。 下流では sink の handler 側で同じ条件を再実装して回避している。

## 現状

### sink の閾値が config から設定できない

`rtc_base/logging.cc` の `LogMessage::~LogMessage` は、 `config.sinks()` のループで `sink->min_severity_` と比較して配信を決めている。 `LogSink::min_severity_` は `rtc_base/logging.h` の `LogSink` の private メンバで、 friend は `LogMessage` のみである。 `LoggingConfig::AddSink` に閾値の引数は無く、 `LogSink` に setter も無いため、 値は宣言時の既定値 `LS_INFO` に固定される。

このメンバが `LS_INFO` で初期化されたのは未初期化アクセスを避けるための変更 (`975c47205a`) であり、 config sink の閾値の意味を定義したものではない。 `LoggingConfig` と `AddSink` を導入した `1dd7260d65` の時点では未初期化だった。

### 構築を抑止する閾値も同じ値で引き下げられる

`LogMessage::UpdateMinLogSeverity` は `config.min_severity()` に加えて `config.sinks()` の各 sink の `min_severity_` も `std::min` に混ぜている。 `std::min` はより軽い方を取るため、 config sink を登録すると `g_min_sev` が `LS_INFO` まで下がる。 この結果 `config.min_severity` を `LS_WARNING` 以上にしても `LS_INFO` の行が構築され続ける。 配信は `config.min_severity` で絞られるため出力は正しいが、 破棄される行の整形コストを払い続ける。

### legacy な経路でしか閾値を指定できない

閾値を登録時に指定できるのは legacy な `LogMessage::AddLogToStream(stream, min_sev)` だけであり、 これは `stream->min_severity_` を設定する。 しかし webrtc-rs の C API はこの API を公開しておらず、 libwebrtc は `Bug: webrtc:42234107` (Remove LogSink from rtc::LogMessage) でこの経路の削除を進めている。 legacy な経路の callback は `GetLoggingLock()` を保持したまま呼ばれるため、 callback 内でログを出すとデッドロックする。

### 上流の状況

2026-10-11 時点の上流 `main` の `rtc_base/logging.h` / `rtc_base/logging.cc` でも同じ実装であり、 `AddSink` に閾値の引数は追加されていない。

## 設計方針

- config sink の閾値は `LoggingConfig::min_severity()` のみとする。 sink ごとの閾値は現行 API に設定経路が無く、 導入すると `min_severity` との大小関係を定義する必要があるため、 本 issue では導入しない
- `rtc_base/logging.cc` の `LogMessage::~LogMessage` にある config sink ループの比較を `config.min_severity()` に変える
- `LogMessage::UpdateMinLogSeverity` の `config.sinks()` ループを削除する。 これにより `g_min_sev` は `min(debug_severity, min_severity)` になり、 配信されない行を構築しなくなる
- legacy な `streams_` を使う経路 (`entry->min_severity_` で比較するループ、 `AddLogToStream`、 `RemoveLogToStream`、 `GetLogToStream`) は変更しない。 `LogSink::min_severity_` は legacy 専用のメンバになる
- `patches/` に patch を追加し、 `run.py` の `PATCHES` の全ターゲットに登録する。 `patches/README.md` に解説と削除条件 (上流の移行完了) を書く
- 上流に還元する場合は `webrtc:42234107` の文脈で提案する

## 完了条件

- sink を登録し `set_min_severity(LS_VERBOSE)` にすると `LS_VERBOSE` の行が sink へ届く
- sink を登録し `set_min_severity(LS_WARNING)` にすると `LS_INFO` の行が sink へ届かない
- sink を登録し `set_min_severity(LS_NONE)` にするとどの重大度の行も sink へ届かない
- sink を登録し `set_min_severity(LS_WARNING)` にすると `LS_INFO` の行が構築されない (`RTC_LOG` の `IsNoop` が真になる)
- legacy な `AddLogToStream` で指定した閾値と `GetLogToStream` の結果が変わらない
- `PATCHES` の全ターゲットでビルドが通る
- `patches/README.md` に解説と削除条件が書かれている
- `CHANGES.md` に FIX が追記されている
- 生成した libwebrtc を使う webrtc-rs の canary で上記の配信閾値の挙動を確認する

## 解決方法

`patches/logging_sink_min_severity.patch` を追加し、 `run.py` の `PATCHES` の全ターゲットに登録した。

- `LogMessage::~LogMessage` の config sink ループの比較を `sink->min_severity_` から `config.min_severity()` に変える
- `LogMessage::UpdateMinLogSeverity` から `config.sinks()` のループを削除し、 `g_min_sev` を debug 出力の閾値、 config の閾値、 legacy な `streams_` の閾値の最小値にする
- legacy な `streams_` を使う経路 (`entry->min_severity_` で比較するループ、 `AddLogToStream`、 `RemoveLogToStream`、 `GetLogToStream`) は変更しない

`patches/README.md` に解説と削除条件 (上流の `webrtc:42234107` の移行完了) を追記し、 `CHANGES.md` に FIX を追記した。

### 確認したこと

ubuntu-24.04_x86_64 をビルドし、 生成した `libwebrtc.a` をリンクした canary で次を確認した。 `InitializeLogging` は 1 プロセスにつき 1 回しか成功しないため、 ケースごとに別プロセスで実行した。

- sink を登録し `min_severity` を `LS_VERBOSE` にすると `LS_VERBOSE` の行が sink へ届く
- sink を登録し `min_severity` を `LS_WARNING` にすると `LS_INFO` の行は届かず、 `LS_WARNING` と `LS_ERROR` の行が届く
- sink を登録し `min_severity` を `LS_NONE` にするとどの重大度の行も sink へ届かない
- sink を登録し `min_severity` を `LS_WARNING` にすると `IsNoop(LS_INFO)` が真になる。 debug 出力が `LS_INFO` を要求しているときは debug 出力のために構築されるので、 `debug_severity` を `LS_NONE` にして確認した
- legacy な `AddLogToStream` で指定した閾値と `GetLogToStream` の結果が変わらない

`WEBRTC_BUILD_ROOT` にローカルの webrtc-build を指定した webrtc-rs の canary でも `verbose` / `warning` / `none` の 3 ケースを確認した。 `python3 run.py test-link ubuntu-24.04_x86_64` と `python3 run.py test-link-rust ubuntu-24.04_x86_64` も成功した。

### 残っている作業

- `rtc_base/logging.cc` はローカルに取得済みの 8 ターゲットで適用前の内容が同一 (blob が `00f49c9a52`) であり、 残りのターゲットも同じリビジョンの libwebrtc を使うため同じパッチが適用できる。 ビルドの確認は ubuntu-24.04_x86_64 のみで、 全ターゲットのビルドは CI で確認する
- リリースした libwebrtc を使う webrtc-rs の canary での確認は未実施
