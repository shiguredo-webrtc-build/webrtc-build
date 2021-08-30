# [iOS] サイマルキャスト対応パッチについて

## パッチファイル

`patches/ios_simulcast.patch`


## 目的

サイマルキャストの映像エンコードに対応する。


## 解決する問題

サイマルキャストの映像エンコーダーが ObjC API に存在しない。
C++ API にはあるので、本パッチでは ObjC ラッパーを追加する。


## 本家にパッチを投げるには

単純なラッパーであり、 API は他の映像エンコーダーに合わせているので、あとはコメントと説明を用意すればよいと思われる。


## パッチが不要になる条件

サイマルキャストの映像エンコーダーが追加されること。


## 内容

- 以下の ObjC API を追加する。

  - `RTCVideoEncoderFactorySimulcast` クラス
  - `RTCVideoEncoderSimulcast` クラス


## 使い方

映像エンコーダーファクトリに `RTCVideoEncoderFactorySimulcast` を使う。
`RTCVideoEncoderFactorySimulcast` オブジェクトを生成するには、プライマリとフォールバックの 2 つの映像エンコーダーファクトリを用意する。
これらのファクトリは映像のエンコードに使われる。
最初にプライマリのファクトリでエンコードを試み、コーデックが対応していなければフォールバックのファクトリを使用する。
プライマリとフォールバックの両方に同じオブジェクトを指定しても問題ない。

例 (Swift):

```swift
let primary = RTCDefaultVideoEncoderFactory()
let fallback = RTCDefaultVideoEncoderFactory()
let simulcast = RTCVideoEncoderFactorySimulcast(primary: primary, fallback: fallback)
```


## API

### RTCVideoEncoderFactorySimulcast クラス

サイマルキャスト映像エンコーダーを生成する。

#### 宣言

```objc
@interface RTC_OBJC_TYPE (RTCVideoEncoderFactorySimulcast) : NSObject <RTCVideoEncoderFactory>
```


#### primary

```objc
@property id<RTCVideoEncoderFactory> primary;
```

最初に使用される映像エンコーダーファクトリ。


#### fallback

```objc
@property id<RTCVideoEncoderFactory> fallback;
```

プライマリの映像エンコーダーファクトリで対応できない場合に使用される映像エンコーダーファクトリ。


#### - initWithPrimary:fallback:

```objc
- (instancetype)initWithPrimary:(id<RTCVideoEncoderFactory>)primary
                       fallback:(id<RTCVideoEncoderFactory>)fallback;
```

初期化する。


### RTCVideoEncoderSimulcast クラス

このクラスは `RTCVideoEncoderSimulcastFactory` から使われる。
通常は直接使う必要はない。

#### 宣言

```objc
@interface RTC_OBJC_TYPE (RTCVideoEncoderSimulcast) : NSObject
```

#### + simulcastEncoderWithPrimary:fallback:videoCodecInfo:

```objc
+ (id<RTCVideoEncoder>)simulcastEncoderWithPrimary:(id<RTCVideoEncoderFactory>)primary
                                          fallback:(id<RTCVideoEncoderFactory>)fallback
                                    videoCodecInfo:(RTCVideoCodecInfo *)videoCodecInfo
```

サイマルキャスト用の映像エンコーダーを生成する。