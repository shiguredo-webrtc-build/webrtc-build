# android_proxy.patch の ConnectionContext 破棄順による Android のプロセスクラッシュを修正する

- Created: 2026-09-28
- Completed: 2026-10-01
- Branch: feature/fix-android-proxy-context-destruction-order
- Polished: {YYYY-MM-DD}

## 目的

`android_proxy.patch` が `OwnedFactoryAndThreads` に追加した `ConnectionContext` の参照を、 worker / network / signaling thread より先に破棄するように修正する。
これにより `PeerConnectionFactory.dispose()` 時の use-after-free によるプロセスクラッシュを解消する。

## 現状

- `patches/android_proxy.patch` は `OwnedFactoryAndThreads` に `context_` ( `ConnectionContext` の参照 ) を追加している。
  現在の宣言順は `env_`, `context_`, `socket_factory_`, `signaling_thread_`, `worker_thread_`, `network_thread_`, `factory_` であり、 デストラクタは宣言の逆順で実行されるため `context_` は thread の破棄後に解放される。
- `pc/connection_context.cc` の `ConnectionContext::~ConnectionContext` は `worker_thread_->BlockingCall` と `worker_thread_->PostTask` を呼ぶ。
  そのため thread 破棄後に `~ConnectionContext` が実行されると、 破棄済みの `Thread` オブジェクトへ仮想呼び出しを行い use-after-free になる。
- 2026-09-25 の Sora Android SDK の E2E ( [run 36105148765](https://github.com/shiguredo/sora-android-sdk/actions/runs/36105148765) ) で、 `SoraCloseTypeE2ETest` の `DataChannelシグナリングのみの切断経路がDataChannelであることを検証すること` の実行中に SIGSEGV が発生し、 E2E が途中終了した。
- tombstone のスタックは `org.webrtc.PeerConnectionFactory.freeFactory` から `OwnedFactoryAndThreads` のデストラクタ、 `ConnectionContext` のデストラクタ内の仮想呼び出しへと続いており、 上記の破棄順が原因であることを示している。
- この経路は `PeerConnectionFactory.dispose()` を呼ぶたびに通るため、 クラッシュは接続・切断のたびに発生し得る。
  Sora Android SDK では接続時に client offer SDP 生成用の一時 `PeerChannelImpl` を `SoraMediaChannel.requestClientOfferSdp` で作成して破棄する。
- Sora Android SDK の E2E では libwebrtc 151 に更新した後に不定期でプロセスクラッシュが発生している。
  同種のクラッシュは 151 の develop や 154 / 155 のブランチの run でも記録されている ( [run 36090210506](https://github.com/shiguredo/sora-android-sdk/actions/runs/36090210506) / [run 35954978680](https://github.com/shiguredo/sora-android-sdk/actions/runs/35954978680) / [run 35314967507](https://github.com/shiguredo/sora-android-sdk/actions/runs/35314967507) )。
  150 を使っていた期間は発生していない。
- 原因は upstream のコードではなく `android_proxy.patch` のメンバ宣言順にある。
  upstream の `OwnedFactoryAndThreads` は `env_` を先頭に置き、 デストラクタのコメントで `env_` を最後に破棄することを明示している。
  m150 の `android_proxy.patch` では `context_` が thread の後ろに宣言されており、 thread より先に破棄される安全な順序だった。
  m151 以降では `env_` の直後に `context_` を置いたため破棄順が変わった ( [5a90d0b](https://github.com/shiguredo-webrtc-build/webrtc-build/commit/5a90d0bb686fd68438b93b4ea28efe25d331a545) )。
- 同じ宣言順は `feature/m151.7922` / `feature/m152.7977` / `feature/m153.8010` / `feature/m154.8037` / `feature/m155.8059` のすべてに含まれている。

## 設計方針

- `OwnedFactoryAndThreads` の `context_` を `network_thread_` と `factory_` の間に宣言し、 `~ConnectionContext` が thread の生存中に実行されるようにする。
- 破棄順は `factory_` → `context_` → `network_thread_` / `worker_thread_` / `signaling_thread_` → `socket_factory_` → `env_` となる。
  `env_` を最後に破棄する既存の方針は維持する。
- デストラクタのコメントを実際の破棄順に合わせて修正し、 コンストラクタの初期化子リストも宣言順に合わせる。
- パッチの生成は DEVELOPMENT.md の「パッチを編集する」の手順で行い、 `run.py diff` の出力で `patches/android_proxy.patch` を更新する。
- m151 だけでなく、 同じ順序を持つ m152 / m153 / m154 / m155 の各ブランチにも同じ修正を適用する。

## 検証方法

- Sora Android SDK の E2E ( Gradle Managed Device の pixelApi35 ) を修正版の AAR で繰り返し実行し、 プロセスクラッシュが発生しないことを確認する。
- 検証には zztkm/webrtc-build のテスト用ブランチとテストリリース、 zztkm/shiguredo-webrtc-android のテストリリース、 JitPack の AAR を利用した。
- `E2E_REPEAT` による繰り返しでは Gradle の UP-TO-DATE 判定で 2 回目以降にテストが実行されないため、 検証時は `--rerun-tasks` を付けて実行した。

## 完了条件

- 修正した `android_proxy.patch` を含む Android SDK ビルドで、 Sora Android SDK の E2E が繰り返し成功し、 プロセスクラッシュが発生しないこと。
- 修正が m151 以降の各ブランチに適用され、 それぞれリリースされること。

## 検証結果

- 修正内容: zztkm/webrtc-build の `feature/test-fix-connection-context-destruction-order` ( [8678943](https://github.com/zztkm/webrtc-build/commit/8678943c9a432d5caf88a598825ef83289016502) )
- テストリリース: [m151.7922.0.1-test1](https://github.com/zztkm/webrtc-build/releases/tag/m151.7922.0.1-test1) ( android_sdk のみ )
- AAR テストリリース: [151.7922.0.1-test1](https://github.com/zztkm/shiguredo-webrtc-android/releases/tag/151.7922.0.1-test1)
  - JitPack: `com.github.zztkm:shiguredo-webrtc-android:151.7922.0.1-test1`
- Sora Android SDK の E2E 実行結果
  - push run: [36374089962](https://github.com/shiguredo/sora-android-sdk/actions/runs/36374089962) ( 8/8 成功 )
  - push run: [36375462086](https://github.com/shiguredo/sora-android-sdk/actions/runs/36375462086) ( 8/8 成功 )
  - repeat=10 run: [36375477207](https://github.com/shiguredo/sora-android-sdk/actions/runs/36375477207) ( 10 回 × 8 テスト = 80 テストすべて成功、 クラッシュ 0 件 )
  - logcat に `"libwebrtc":"Shiguredo-build M151 (151.7922.0.1-test1 f20ebb8)"` が記録されており、 検証は修正版 AAR で行われている
  - 上記を合わせて 13 スイート / 104 テスト実行でクラッシュは発生していない
- バイナリ検証: 修正版 AAR の `libjingle_peerconnection_so.so` ( BuildId `59c294f4e06514a6` ) の `OwnedFactoryAndThreads` デストラクタで、 `context_` が thread より先に解放されることを逆アセンブルで確認した

## 解決方法

- `patches/android_proxy.patch` の `OwnedFactoryAndThreads` の `context_` を `network_thread_` と `factory_` の間に宣言し、 worker / network / signaling thread より先に破棄されるようにする。
  - デストラクタのコメントとコンストラクタの初期化子リストも実際の破棄順に合わせる。
  - メンバの破棄順は次の制約を満たす必要がある。
    - `env_` を最後に破棄する(upstream の要件で、 core utilities を他オブジェクトより長生きさせるため)
    - `factory_` を `context_` より先に破棄する(`~PeerConnectionFactory` が `context_->worker_thread()` を使うため)
    - `context_` を worker / network / signaling thread より先に破棄する(`~ConnectionContext` が worker thread へ `BlockingCall` / `PostTask` を呼ぶため)
- パッチの生成は DEVELOPMENT.md の「パッチを編集する」の手順で行い、 依存関係まで同期した状態で `run.py revert android_sdk --patch android_proxy.patch` を実行し、 `run.py diff android_sdk` の出力がパッチと一致することと、 `run.py revert android_sdk` で全パッチが適用できることを確認する。
- 修正したパッチを含む AAR を作成し、 Sora Android SDK の E2E を繰り返し実行してプロセスクラッシュが発生しないことを確認する。 繰り返し実行では Gradle の UP-TO-DATE 判定で 2 回目以降にテストが実行されないため `--rerun-tasks` を付ける。
- 修正したパッチを m151 / m152 / m153 / m154 / m155 の各ブランチに適用し、 各ブランチで CHANGES.md を更新して修正を含むバージョンをリリースする。

### 実施結果

- m151 で `patches/android_proxy.patch` を修正し、 m152 / m153 / m154 / m155 の各ブランチと master にマージした。
- 修正を含むバージョンをリリースした。
  - `m151.7922.0.1`
  - `m152.7977.0.4`
  - `m153.8010.0.2`
  - `m154.8037.3.0`
  - `m155.8059.2.0`
- 検証は上記の「検証結果」のとおりで、 プロセスクラッシュは再発していない。
