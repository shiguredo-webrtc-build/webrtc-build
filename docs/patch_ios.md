# iOS 向けのパッチについて

## 内容

- 接続時のマイクのパーミッション要求を抑制する。

- マイクの初期化を明示的に行う API を追加する。
  パッチ適用後はマイクは自動的に初期化されない。

- ``AVAudioSession`` の初期化時に設定されるカテゴリを ``AVAudioSessionCategoryPlayAndRecord`` から ``AVAudioSessionCategoryAmbient`` に変更する。


## パッチ適用後の使い方

- マイクを使う場合は ``RTCAudioSession.initializeInput(completionHandler:)`` を実行してマイクを初期化する。
  - このメソッドはマイクが使用されるまで非同期で待ち、必要になったら初期化する。マイクの使用許可がなければユーザーにパーミッションを要求する。
  - 接続ごとに実行すること。接続が終了するとマイクは初期化前の状態に戻る。

- マイクを使わない場合は ``Info.plist`` にマイクの用途を記述する必要はない。
