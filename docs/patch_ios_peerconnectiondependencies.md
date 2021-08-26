# [iOS] RTCPeerConnectionDependencies 追加パッチについて

## パッチファイル

`patches/ios_peerconnectiondependencies.patch`


## 目的

ユーザーが証明書を検証できるようにする。


## 解決する問題

ユーザーが証明書を検証するための API が ObjC にない。
C++ API はあるが、公開されていない。
Android に証明書検証 API があるので参考にした。


## 本家にパッチを投げるには

ソースコードのコメントとパッチの十分な説明が必要。
Android の証明書検証 API を参考にしたので、あるべき形から大きく外れてはいないと思われる。


## パッチが不要になる条件

ユーザーが証明書を検証するための ObjC API が追加されること。


## 内容

- 以下の ObjC API を追加する。いずれも C++ API のラッパー。

  - `RTCPeerConnectionDependencies` クラス
  - `RTCSSLCertificateVerifier` プロトコル


## 使い方

本パッチの ObjC API は Swift からでも特別な対応なく使える。

### 任意の証明書検証処理を実装する

1. `RTCSSLCertificateVerifier` プロトコルを実装し、証明書検証処理を実装する。
2. `RTCPeerConnectionDependencies` オブジェクトを生成し、 1. のオブジェクトを `sslCertificateVerifier` プロパティにセットする。
3. `RTCPeerConnection` を生成する。 `-[RTCPeerconnectionFactory peerConnectionWithConfiguration:constraints:dependencies:delegate:]` を使う。 2. を引数に渡す。

以上の手順で `RTCPeerConnection` を生成すると、接続試行時に証明書を任意の方法で検証できる。


### すべての証明書を検証せずに信頼する

1. `RTCPeerConnectionDependencies` オブジェクトを生成し、 `allowsInsecureCertificate` プロパティに `YES` をセットする。
2. 前節と同様にして `RTCPeerConnection` を生成する。

以上の手順で `RTCPeerConnection` を生成すると、すべての証明書が検証することなく信頼される。
`RTCSSLCertificateVerifier` プロトコルを実装する必要はない。


## API

### RTCPeerConnectionFactory 拡張

`RTCPeerConnectionDependencies` を引数に受け取るメソッドを追加する。


#### - peerConnectionWithConfiguration:constraints:dependencies:delegate:

```objc
- (RTCPeerConnection *)
    peerConnectionWithConfiguration:(RTCConfiguration *)configuration
                        constraints:(RTCMediaConstraints *)constraints
                       dependencies:(RTCPeerConnectionDependencies *)dependencies
                           delegate:(nullable id<RTCPeerConnectionDelegate>)delegate;
```

`RTCPeerconnection` オブジェクトを生成する。


### RTCPeerConnection 拡張

`RTCPeerConnectionDependencies` を引数に受け取るメソッドを追加する。
`RTCPeerConnection` は通常 `RTCPeerConnectionFactory` を使って生成するので、プライベート API でいいかもしれない。

#### - initWithFactory:configuration:constraints:dependencies:delegate:

```objc
- (nullable instancetype)initWithFactory:(RTCPeerConnectionFactory *)factory
                           configuration:(RTCConfiguration *)configuration
                             constraints:(RTCMediaConstraints *)constraints
                            dependencies:(RTCPeerConnectionDependencies *)dependencies
                                delegate:(nullable id<RTCPeerConnectionDelegate>)delegate;
```


### RTCPeerConnectionDependencies クラス

`PeerConnectionDependencies` のラッパー。
`RTCPeerConnection` の依存物を設定する。

#### 宣言

```objc
@interface RTCPeerConnectionDependencies : NSObject
```

#### - init

```objc
- (instancetype)init;
```

オブジェクトを初期化する。

#### sslCertificateVerifier

```objc
@property (readwrite, nonatomic, nullable) id<RTCSSLCertificateVerifier> sslCertificateVerifier;
```

SSL 証明書を検証するオブジェクト。

#### allowsInsecureCertificate

```objc
@property (readwrite, nonatomic) BOOL allowsInsecureCertificate;
```

安全でない証明書の可否。
このプロパティが `YES` の場合、すべての証明書を検証せずに信頼する。


### RTCSSLCertificateVerifier プロトコル

SSL 証明書を検証する API 。
任意の方法で証明書を検証するには、本プロトコルを実装したオブジェクトを `RTCPeerConnectionDependencies` の `sslCertificateVerifier` プロパティにセットする。

#### 宣言

```objc
@protocol RTCSSLCertificateVerifier <NSObject>
```

#### - verifyCertificate:

```objc
- (BOOL)verifyCertificate:(NSData *)certificate;
```

証明書を検証する。
問題がなければ `YES` を返す。