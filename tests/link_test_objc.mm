// webrtc-build が生成する libwebrtc.a に ObjC の実装が入っているかを確認するテスト。
//
// GN の完全な静的ライブラリ (//:webrtc) は C++ の実装だけで、ObjC の実装は
// WebRTC.framework のリンクにだけ渡る。そのため配布するアーカイブに ObjC の実装が
// 入っていないと、webrtc-rs や Sora SDK のような利用者が ObjC の API を使ったときに
// 未定義シンボルでリンクに失敗する。このテストはアーカイブだけをリンクするため、
// ObjC の実装が抜けていればリンクの時点で失敗する。
//
// リンクできた場合は、既定のコーデックファクトリと ObjCToNative* の変換関数を実際に
// 呼び出して動作も確認する。変換関数は Rust の利用者が使う経路で、m156 の webrtc-rs の
// ビルドが未定義シンボルで失敗した原因である。その他のクラスは、シンボルが引けることを
// 確認する。iOS と macOS では入っているクラスが違うため、プラットフォーム固有のものは
// 分けて確認する。

#import <Foundation/Foundation.h>

#include <cstdio>
#include <memory>

#include "api/video_codecs/video_decoder_factory.h"
#include "api/video_codecs/video_encoder_factory.h"

#import "sdk/objc/api/logging/RTCCallbackLogger.h"
#import "sdk/objc/api/peerconnection/RTCAudioSource.h"
#import "sdk/objc/api/peerconnection/RTCAudioTrack.h"
#import "sdk/objc/api/peerconnection/RTCCertificate.h"
#import "sdk/objc/api/peerconnection/RTCConfiguration.h"
#import "sdk/objc/api/peerconnection/RTCCryptoOptions.h"
#import "sdk/objc/api/peerconnection/RTCDataChannel.h"
#import "sdk/objc/api/peerconnection/RTCDataChannelConfiguration.h"
#import "sdk/objc/api/peerconnection/RTCDtlsFingerprint.h"
#import "sdk/objc/api/peerconnection/RTCFileLogger.h"
#import "sdk/objc/api/peerconnection/RTCIceCandidate.h"
#import "sdk/objc/api/peerconnection/RTCIceCandidateErrorEvent.h"
#import "sdk/objc/api/peerconnection/RTCIceServer.h"
#import "sdk/objc/api/peerconnection/RTCLegacyStatsReport.h"
#import "sdk/objc/api/peerconnection/RTCMediaConstraints.h"
#import "sdk/objc/api/peerconnection/RTCMediaSource.h"
#import "sdk/objc/api/peerconnection/RTCMediaStream.h"
#import "sdk/objc/api/peerconnection/RTCMediaStreamTrack.h"
#import "sdk/objc/api/peerconnection/RTCMetricsSampleInfo.h"
#import "sdk/objc/api/peerconnection/RTCPeerConnection.h"
#import "sdk/objc/api/peerconnection/RTCPeerConnectionFactory.h"
#import "sdk/objc/api/peerconnection/RTCPeerConnectionFactoryOptions.h"
#import "sdk/objc/api/peerconnection/RTCRtcpParameters.h"
#import "sdk/objc/api/peerconnection/RTCRtpCapabilities.h"
#import "sdk/objc/api/peerconnection/RTCRtpCodecCapability.h"
#import "sdk/objc/api/peerconnection/RTCRtpCodecParameters.h"
#import "sdk/objc/api/peerconnection/RTCRtpEncodingParameters.h"
#import "sdk/objc/api/peerconnection/RTCRtpHeaderExtension.h"
#import "sdk/objc/api/peerconnection/RTCRtpHeaderExtensionCapability.h"
#import "sdk/objc/api/peerconnection/RTCRtpParameters.h"
#import "sdk/objc/api/peerconnection/RTCRtpReceiver.h"
#import "sdk/objc/api/peerconnection/RTCRtpSender.h"
#import "sdk/objc/api/peerconnection/RTCRtpSource.h"
#import "sdk/objc/api/peerconnection/RTCRtpTransceiver.h"
#import "sdk/objc/api/peerconnection/RTCSessionDescription.h"
#import "sdk/objc/api/peerconnection/RTCStatisticsReport.h"
#import "sdk/objc/api/peerconnection/RTCVideoSource.h"
#import "sdk/objc/api/peerconnection/RTCVideoTrack.h"
#import "sdk/objc/api/video_codec/RTCVideoDecoderAV1.h"
#import "sdk/objc/api/video_codec/RTCVideoDecoderVP8.h"
#import "sdk/objc/api/video_codec/RTCVideoDecoderVP9.h"
#import "sdk/objc/api/video_codec/RTCVideoEncoderAV1.h"
#import "sdk/objc/api/video_codec/RTCVideoEncoderSimulcast.h"
#import "sdk/objc/api/video_codec/RTCVideoEncoderVP8.h"
#import "sdk/objc/api/video_codec/RTCVideoEncoderVP9.h"
#import "sdk/objc/api/video_frame_buffer/RTCNativeI420Buffer.h"
#import "sdk/objc/api/video_frame_buffer/RTCNativeMutableI420Buffer.h"
#import "sdk/objc/base/RTCEncodedImage.h"
#import "sdk/objc/base/RTCVideoCapturer.h"
#import "sdk/objc/base/RTCVideoCodecInfo.h"
#import "sdk/objc/base/RTCVideoEncoderQpThresholds.h"
#import "sdk/objc/base/RTCVideoEncoderSettings.h"
#import "sdk/objc/base/RTCVideoFrame.h"
#import "sdk/objc/components/capturer/RTCCameraVideoCapturer.h"
#import "sdk/objc/components/renderer/metal/RTCMTLI420Renderer.h"
#import "sdk/objc/components/renderer/metal/RTCMTLNV12Renderer.h"
#import "sdk/objc/components/renderer/metal/RTCMTLRGBRenderer.h"
#import "sdk/objc/components/video_codec/RTCCodecSpecificInfoH264.h"
#import "sdk/objc/components/video_codec/RTCCodecSpecificInfoH265.h"
#import "sdk/objc/components/video_codec/RTCDefaultVideoDecoderFactory.h"
#import "sdk/objc/components/video_codec/RTCDefaultVideoEncoderFactory.h"
#import "sdk/objc/components/video_codec/RTCH264ProfileLevelId.h"
#import "sdk/objc/components/video_codec/RTCVideoDecoderFactoryH264.h"
#import "sdk/objc/components/video_codec/RTCVideoDecoderH264.h"
#import "sdk/objc/components/video_codec/RTCVideoDecoderH265.h"
#import "sdk/objc/components/video_codec/RTCVideoEncoderFactoryH264.h"
#import "sdk/objc/components/video_codec/RTCVideoEncoderFactorySimulcast.h"
#import "sdk/objc/components/video_codec/RTCVideoEncoderH264.h"
#import "sdk/objc/components/video_codec/RTCVideoEncoderH265.h"
#import "sdk/objc/components/video_frame_buffer/RTCCVPixelBuffer.h"
#import "sdk/objc/native/api/video_decoder_factory.h"
#import "sdk/objc/native/api/video_encoder_factory.h"

// iOS だけに入っているクラス
#if defined(WEBRTC_IOS)
#import "sdk/objc/components/audio/RTCAudioSession.h"
#import "sdk/objc/components/audio/RTCAudioSessionConfiguration.h"
#import "sdk/objc/components/capturer/RTCFileVideoCapturer.h"
#import "sdk/objc/components/renderer/metal/RTCMTLVideoView.h"
#import "sdk/objc/helpers/RTCCameraPreviewView.h"
#endif

// macOS だけに入っているクラス
#if defined(WEBRTC_MAC) && !defined(WEBRTC_IOS)
#import "sdk/objc/components/renderer/metal/RTCMTLNSVideoView.h"
#endif

namespace {

// 失敗した内容を出力して終了コードを返す
int Failed(const char* message) {
  std::fprintf(stderr, "link_test_objc: %s\n", message);
  return 1;
}

// 既定のコーデックファクトリの実装が入っていることを確認する
// VideoToolbox の初期化は initEncode で行われるため、ここではオブジェクトの生成までを
// 確認する。対応コーデックが 1 つも返らない場合は、コーデックの実装がアーカイブに
// 入っていない
int TestDefaultCodecFactories() {
  RTCDefaultVideoEncoderFactory* encoder_factory = [[RTCDefaultVideoEncoderFactory alloc] init];
  RTCDefaultVideoDecoderFactory* decoder_factory = [[RTCDefaultVideoDecoderFactory alloc] init];
  if (encoder_factory == nil || decoder_factory == nil) {
    return Failed("既定のコーデックファクトリを作成できませんでした");
  }
  NSArray<RTCVideoCodecInfo*>* formats = [encoder_factory supportedCodecs];
  if (formats.count == 0) {
    return Failed("既定のエンコーダファクトリが対応コーデックを返しませんでした");
  }
  if ([decoder_factory supportedCodecs].count == 0) {
    return Failed("既定のデコーダファクトリが対応コーデックを返しませんでした");
  }
  RTCVideoCodecInfo* info = formats[0];
  if ([encoder_factory createEncoder:info] == nil) {
    return Failed("既定のエンコーダファクトリがエンコーダを作成できませんでした");
  }
  if ([decoder_factory createDecoder:info] == nil) {
    return Failed("既定のデコーダファクトリがデコーダを作成できませんでした");
  }
  std::printf("link_test_objc: 既定のコーデックファクトリの確認に成功しました\n");
  return 0;
}

// ObjC のコーデックファクトリを C++ のファクトリに変換する関数が入っていることを確認する
// Rust の利用者はこの経路で ObjC のコーデックファクトリを渡すため、この関数が
// アーカイブに無いとリンクに失敗する
int TestObjCToNativeCodecFactories() {
  RTCDefaultVideoEncoderFactory* encoder_factory = [[RTCDefaultVideoEncoderFactory alloc] init];
  RTCDefaultVideoDecoderFactory* decoder_factory = [[RTCDefaultVideoDecoderFactory alloc] init];
  std::unique_ptr<webrtc::VideoEncoderFactory> native_encoder_factory =
      webrtc::ObjCToNativeVideoEncoderFactory(encoder_factory);
  std::unique_ptr<webrtc::VideoDecoderFactory> native_decoder_factory =
      webrtc::ObjCToNativeVideoDecoderFactory(decoder_factory);
  if (native_encoder_factory == nullptr || native_decoder_factory == nullptr) {
    return Failed("ObjC のコーデックファクトリを C++ のファクトリに変換できませんでした");
  }
  // 変換したファクトリは ObjC 側の supportedCodecs を呼ぶ。ブリッジの実装が
  // アーカイブに無ければここで未定義シンボルになる
  if (native_encoder_factory->GetSupportedFormats().empty()) {
    return Failed("変換したエンコーダファクトリが対応形式を返しませんでした");
  }
  if (native_decoder_factory->GetSupportedFormats().empty()) {
    return Failed("変換したデコーダファクトリが対応形式を返しませんでした");
  }
  std::printf("link_test_objc: ObjC のコーデックファクトリの変換の確認に成功しました\n");
  return 0;
}

// ロガーの実装が入っていることを確認する
// RTCFileLogger は start でファイルを作るため、一時ディレクトリに出す
int TestLoggers() {
  RTCCallbackLogger* callback_logger = [[RTCCallbackLogger alloc] init];
  [callback_logger start:^(NSString* message) {
    (void)message;
  }];
  [callback_logger stop];

  RTCFileLogger* file_logger =
      [[RTCFileLogger alloc] initWithDirPath:NSTemporaryDirectory() maxFileSize:1024 * 1024];
  [file_logger start];
  [file_logger stop];
  std::printf("link_test_objc: ロガーの確認に成功しました\n");
  return 0;
}

// カメラのキャプタの実装が入っていることを確認する
// カメラが繋がっていない環境では 0 台になるので、台数は見ない
int TestCameraCapturer() {
  NSArray<AVCaptureDevice*>* devices = [RTCCameraVideoCapturer captureDevices];
  if (devices == nil) {
    return Failed("カメラのデバイス一覧を取得できませんでした");
  }
  std::printf("link_test_objc: カメラのキャプタの確認に成功しました (%lu 台)\n",
              (unsigned long)devices.count);
  return 0;
}

// 配布するアーカイブに入っているべき ObjC のクラスを参照する
// ここに並べたクラスのシンボルが引けない場合はリンクに失敗する
int TestClasses() {
  NSArray<Class>* classes = @[
    [RTCAudioSource class],
    [RTCAudioTrack class],
    [RTCCVPixelBuffer class],
    [RTCCallbackLogger class],
    [RTCCameraVideoCapturer class],
    [RTCCertificate class],
    [RTCCodecSpecificInfoH264 class],
    [RTCCodecSpecificInfoH265 class],
    [RTCConfiguration class],
    [RTCCryptoOptions class],
    [RTCDataChannel class],
    [RTCDataChannelConfiguration class],
    [RTCDefaultVideoDecoderFactory class],
    [RTCDefaultVideoEncoderFactory class],
    [RTCDtlsFingerprint class],
    [RTCEncodedImage class],
    [RTCFileLogger class],
    [RTCH264ProfileLevelId class],
    [RTCI420Buffer class],
    [RTCIceCandidate class],
    [RTCIceCandidateErrorEvent class],
    [RTCIceServer class],
    [RTCLegacyStatsReport class],
    [RTCMTLI420Renderer class],
    [RTCMTLNV12Renderer class],
    [RTCMTLRGBRenderer class],
    [RTCMediaConstraints class],
    [RTCMediaSource class],
    [RTCMediaStream class],
    [RTCMediaStreamTrack class],
    [RTCMetricsSampleInfo class],
    [RTCMutableI420Buffer class],
    [RTCPeerConnection class],
    [RTCPeerConnectionFactory class],
    [RTCPeerConnectionFactoryOptions class],
    [RTCRtcpParameters class],
    [RTCRtpCapabilities class],
    [RTCRtpCodecCapability class],
    [RTCRtpCodecParameters class],
    [RTCRtpEncodingParameters class],
    [RTCRtpHeaderExtension class],
    [RTCRtpHeaderExtensionCapability class],
    [RTCRtpParameters class],
    [RTCRtpReceiver class],
    [RTCRtpSender class],
    [RTCRtpSource class],
    [RTCRtpTransceiver class],
    [RTCRtpTransceiverInit class],
    [RTCSessionDescription class],
    [RTCStatistics class],
    [RTCStatisticsReport class],
    [RTCVideoCapturer class],
    [RTCVideoCodecInfo class],
    [RTCVideoDecoderAV1 class],
    [RTCVideoDecoderFactoryH264 class],
    [RTCVideoDecoderH264 class],
    [RTCVideoDecoderH265 class],
    [RTCVideoDecoderVP8 class],
    [RTCVideoDecoderVP9 class],
    [RTCVideoEncoderAV1 class],
    [RTCVideoEncoderFactoryH264 class],
    [RTCVideoEncoderFactorySimulcast class],
    [RTCVideoEncoderH264 class],
    [RTCVideoEncoderH265 class],
    [RTCVideoEncoderQpThresholds class],
    [RTCVideoEncoderSettings class],
    [RTCVideoEncoderSimulcast class],
    [RTCVideoEncoderVP8 class],
    [RTCVideoEncoderVP9 class],
    [RTCVideoFrame class],
    [RTCVideoSource class],
    [RTCVideoTrack class],
#if defined(WEBRTC_IOS)
    [RTCAudioSession class],
    [RTCAudioSessionConfiguration class],
    [RTCCameraPreviewView class],
    [RTCFileVideoCapturer class],
    [RTCMTLVideoView class],
#endif
#if defined(WEBRTC_MAC) && !defined(WEBRTC_IOS)
    [RTCMTLNSVideoView class],
#endif
  ];
  for (Class cls in classes) {
    if (cls == Nil) {
      return Failed("ObjC のクラスを取得できませんでした");
    }
  }
  std::printf("link_test_objc: ObjC のクラスの確認に成功しました (%lu 個)\n",
              (unsigned long)classes.count);
  return 0;
}

}  // namespace

// テストの本体。リンクテストの main と Rust のテストプログラムが呼び出すため
// extern "C" で公開している
extern "C" int webrtc_link_test_objc() {
  for (const auto& test : {TestDefaultCodecFactories, TestObjCToNativeCodecFactories, TestLoggers,
                           TestCameraCapturer, TestClasses}) {
    const int result = test();
    if (result != 0) {
      return result;
    }
  }

  std::printf("link_test_objc: 成功しました\n");
  return 0;
}
