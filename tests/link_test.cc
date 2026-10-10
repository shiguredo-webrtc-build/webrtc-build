// webrtc-build が生成する libwebrtc.a (Windows は webrtc.lib) を、GN を経由せずに
// コンパイラで直接リンクできるかを確認するテスト。
//
// GN のリンクでは rlib や libc++ がリンカに直接渡されるため、配布するアーカイブに
// それらが入っていなくてもリンクできてしまう。このテストはアーカイブだけを
// リンカに渡すため、アーカイブが自己完結していなければ未定義シンボルになる。
// corruption detection は Rust の実装なので、Rust のオブジェクトが入っていないと
// リンクに失敗する。
// リンクできた場合は、アーカイブから引けるはずの API を実際に呼び出して動作も確認する。
// メディアやサイマルキャスト、フィールドトライアル、proxy、zlib や log_sinks、
// H.265 の VPS パーサなど、配布するアーカイブに入っている必要があるものを対象にする。
// プラットフォーム固有のもの (Windows の Core Audio の ADM、macOS の画面キャプチャ、
// Linux の v4l2 のデバイス情報) は、そのプラットフォームでだけ確認する。iOS の
// アーカイブには desktop_capture が入っていないので、画面キャプチャは iOS では確認しない。
// Apple の ObjC の実装は GN の完全な静的ライブラリに入らず、WebRTC.framework のリンクに
// だけ渡るため、ObjC++ のソース (link_test_objc.mm) で別に確認する。
// AdaptedVideoTrackSource は抽象クラスなので、テスト側で継承したクラスを作って確認する。

#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <vector>

#include "api/create_modular_peer_connection_factory.h"
#include "api/enable_media.h"
#include "api/enable_media_with_defaults.h"
#include "api/environment/environment_factory.h"
#include "api/field_trials.h"
#include "api/make_ref_counted.h"
#include "api/peer_connection_interface.h"
#include "api/task_queue/default_task_queue_factory.h"
#include "api/task_queue/task_queue_base.h"
#include "api/task_queue/task_queue_factory.h"
#include "api/transport/rtp/corruption_detection_message.h"
#include "api/video/adapted_video_track_source.h"
#include "api/video/i420_buffer.h"
#include "api/video/video_frame.h"
#include "api/video_codecs/sdp_video_format.h"
#include "api/video_codecs/video_encoder_factory_template.h"
#include "api/video_codecs/video_encoder_factory_template_libvpx_vp8_adapter.h"
#include "common_video/h265/h265_vps_parser.h"
#include "media/engine/simulcast_encoder_adapter.h"
#include "modules/audio_device/include/audio_device_factory.h"
#include "modules/desktop_capture/desktop_capture_options.h"
#include "modules/desktop_capture/desktop_capturer.h"
#include "modules/rtp_rtcp/source/corruption_detection_extension.h"
#include "modules/video_capture/video_capture.h"
#include "modules/video_capture/video_capture_factory.h"
#include "rtc_base/crypt_string_revive.h"
#include "rtc_base/log_sinks.h"
#include "rtc_base/logging.h"
#include "rtc_base/socket_adapters.h"
#include "rtc_base/ssl_identity.h"
#include "rtc_base/thread.h"
#include "third_party/zlib/zlib.h"

namespace {

// 失敗した内容を出力して終了コードを返す
int Failed(const char* message) {
  std::fprintf(stderr, "link_test: %s\n", message);
  return 1;
}

// サンプル値を含むヘッダ拡張をパースして期待値と一致するか確認する
bool ParseAndCheck(const std::span<const uint8_t> raw,
                   webrtc::CorruptionDetectionMessage* message,
                   const char* context) {
  if (!webrtc::CorruptionDetectionExtension::Parse(raw, message)) {
    std::fprintf(stderr, "link_test: %s のパースに失敗しました\n", context);
    return false;
  }
  if (message->sequence_index() != 0b0100'0100) {
    std::fprintf(stderr, "link_test: %s の sequence_index が 68 ではありません\n", context);
    return false;
  }
  if (!message->interpret_sequence_index_as_most_significant_bits()) {
    std::fprintf(stderr,
                 "link_test: %s の sequence_index の解釈が最上位ビットになっていません\n",
                 context);
    return false;
  }
  if (std::abs(message->std_dev() - 220.0 * 40.0 / 255.0) > 1e-9) {
    std::fprintf(stderr, "link_test: %s の std_dev が期待値と一致しません\n", context);
    return false;
  }
  if (message->luma_error_threshold() != 14 || message->chroma_error_threshold() != 15) {
    std::fprintf(stderr, "link_test: %s の luma / chroma のしきい値が期待値と一致しません\n",
                 context);
    return false;
  }
  const std::span<const double> samples = message->sample_values();
  if (samples.size() != 3 || samples[0] != 1.0 || samples[1] != 2.0 || samples[2] != 3.0) {
    std::fprintf(stderr, "link_test: %s のサンプル値が期待値と一致しません\n", context);
    return false;
  }
  return true;
}

// Rust の実装が入っていることを確認する
int TestCorruptionDetection() {
  // 必須フィールドだけのヘッダ拡張をパースする (Rust の実装が呼ばれる)
  {
    const uint8_t raw[] = {0b1110'1111};
    webrtc::CorruptionDetectionMessage message;
    if (!webrtc::CorruptionDetectionExtension::Parse(raw, &message)) {
      return Failed("必須フィールドだけのヘッダ拡張のパースに失敗しました");
    }
    if (message.sequence_index() != 0b0110'1111) {
      return Failed("必須フィールドだけのヘッダ拡張の sequence_index が 111 ではありません");
    }
    if (!message.interpret_sequence_index_as_most_significant_bits()) {
      return Failed("必須フィールドだけのヘッダ拡張の sequence_index の解釈が最上位ビットになっていません");
    }
    if (!message.sample_values().empty()) {
      return Failed("必須フィールドだけのヘッダ拡張のサンプル値が空ではありません");
    }
  }

  // サンプル値を含むヘッダ拡張をパースする
  const uint8_t raw[] = {0b1100'0100, 220, 0b1110'1111, 1, 2, 3};
  webrtc::CorruptionDetectionMessage message;
  if (!ParseAndCheck(raw, &message, "サンプル値を含むヘッダ拡張")) {
    return 1;
  }

  // Write したものを Parse し直して値が往復することを確認する
  std::array<uint8_t, webrtc::CorruptionDetectionExtension::kMaxValueSizeBytes> written{};
  const size_t size = webrtc::CorruptionDetectionExtension::ValueSize(message);
  if (!webrtc::CorruptionDetectionExtension::Write(std::span(written).first(size), message)) {
    return Failed("ヘッダ拡張の書き込みに失敗しました");
  }
  webrtc::CorruptionDetectionMessage round_tripped;
  if (!ParseAndCheck(std::span(written).first(size), &round_tripped, "書き込んだヘッダ拡張")) {
    return 1;
  }
  std::printf("link_test: corruption detection の確認に成功しました\n");
  return 0;
}

// スレッドとタスクキューの実装が入っていることを確認する
int TestThreadAndTaskQueue() {
  std::unique_ptr<webrtc::Thread> network_thread = webrtc::Thread::CreateWithSocketServer();
  if (network_thread == nullptr) {
    return Failed("ネットワークスレッドを作成できませんでした");
  }
  std::unique_ptr<webrtc::Thread> worker_thread = webrtc::Thread::Create();
  if (worker_thread == nullptr) {
    return Failed("ワーカースレッドを作成できませんでした");
  }
  network_thread->Start();
  worker_thread->Start();

  std::unique_ptr<webrtc::TaskQueueFactory> task_queue_factory =
      webrtc::CreateDefaultTaskQueueFactory();
  if (task_queue_factory == nullptr) {
    return Failed("タスクキューファクトリを作成できませんでした");
  }
  auto task_queue =
      task_queue_factory->CreateTaskQueue("link_test", webrtc::TaskQueueFactory::Priority::NORMAL);
  if (task_queue == nullptr) {
    return Failed("タスクキューを作成できませんでした");
  }

  worker_thread->Stop();
  network_thread->Stop();
  std::printf("link_test: スレッドとタスクキューの確認に成功しました\n");
  return 0;
}

// PeerConnectionFactory の実装が入っていることを確認する
int TestPeerConnectionFactory() {
  std::unique_ptr<webrtc::Thread> network_thread = webrtc::Thread::CreateWithSocketServer();
  std::unique_ptr<webrtc::Thread> worker_thread = webrtc::Thread::Create();
  std::unique_ptr<webrtc::Thread> signaling_thread = webrtc::Thread::Create();
  if (network_thread == nullptr || worker_thread == nullptr || signaling_thread == nullptr) {
    return Failed("スレッドを作成できませんでした");
  }
  network_thread->Start();
  worker_thread->Start();
  signaling_thread->Start();

  webrtc::PeerConnectionFactoryDependencies dependencies;
  dependencies.network_thread = network_thread.get();
  dependencies.worker_thread = worker_thread.get();
  dependencies.signaling_thread = signaling_thread.get();
  webrtc::scoped_refptr<webrtc::PeerConnectionFactoryInterface> factory =
      webrtc::CreateModularPeerConnectionFactory(std::move(dependencies));
  if (factory == nullptr) {
    return Failed("PeerConnectionFactory を作成できませんでした");
  }

  signaling_thread->Stop();
  worker_thread->Stop();
  network_thread->Stop();
  std::printf("link_test: PeerConnectionFactory の確認に成功しました\n");
  return 0;
}

// 映像の実装が入っていることを確認する (libyuv なども含まれる)
int TestVideoFrame() {
  webrtc::scoped_refptr<webrtc::I420Buffer> buffer = webrtc::I420Buffer::Create(16, 16);
  if (buffer == nullptr) {
    return Failed("I420Buffer を作成できませんでした");
  }
  buffer->InitializeData();
  webrtc::VideoFrame frame = webrtc::VideoFrame::Builder()
                                 .set_video_frame_buffer(buffer)
                                 .set_rtp_timestamp(1234)
                                 .build();
  if (frame.width() != 16 || frame.height() != 16 || frame.rtp_timestamp() != 1234) {
    return Failed("VideoFrame の値が期待値と一致しません");
  }
  std::printf("link_test: 映像フレームの確認に成功しました\n");
  return 0;
}

// AdaptedVideoTrackSource が入っていることを確認する
// 抽象クラスなので、SDK の実装と同じように継承して使う
// (参照カウントは webrtc::make_ref_counted が埋めるので書かなくて良い)
class LinkTestVideoTrackSource : public webrtc::AdaptedVideoTrackSource {
 public:
  // 継承先からしか呼べない保護メンバを呼ぶための入り口
  void SendFrame(const webrtc::VideoFrame& frame) { OnFrame(frame); }
  bool WantsFrame(int width, int height, int64_t time_us) {
    int out_width = 0;
    int out_height = 0;
    int crop_width = 0;
    int crop_height = 0;
    int crop_x = 0;
    int crop_y = 0;
    return AdaptFrame(width, height, time_us, &out_width, &out_height, &crop_width, &crop_height,
                      &crop_x, &crop_y);
  }

  // SDK の実装と同じで、純粋仮想関数を埋めるためだけのもの
  webrtc::MediaSourceInterface::SourceState state() const override {
    return webrtc::MediaSourceInterface::kLive;
  }
  bool remote() const override { return false; }
  bool is_screencast() const override { return false; }
  std::optional<bool> needs_denoising() const override { return false; }
};

int TestAdaptedVideoTrackSource() {
  auto source = webrtc::make_ref_counted<LinkTestVideoTrackSource>();
  if (source->state() != webrtc::MediaSourceInterface::kLive) {
    return Failed("映像ソースの状態が kLive ではありません");
  }
  // シンクを繋いでいないので、フレームは要求されない
  if (source->WantsFrame(1280, 720, 0)) {
    return Failed("シンクが無いのにフレームが要求されました");
  }
  webrtc::scoped_refptr<webrtc::I420Buffer> buffer = webrtc::I420Buffer::Create(16, 16);
  webrtc::VideoFrame frame = webrtc::VideoFrame::Builder()
                                 .set_video_frame_buffer(buffer)
                                 .set_rtp_timestamp(1234)
                                 .build();
  // シンクが無いのでどこにも流れないが、SDK と同じ経路を呼んでおく
  source->SendFrame(frame);
  std::printf("link_test: AdaptedVideoTrackSource の確認に成功しました\n");
  return 0;
}

// proxy の実装 (rtc_base/crypt_string_revive.h の webrtc::revive) が
// 入っていることを確認する
int TestRevivedProxy() {
  webrtc::revive::CryptString crypt;
  if (crypt.GetLength() != 0) {
    return Failed("空の CryptString の長さが 0 ではありません");
  }
  if (!crypt.UrlEncode().empty()) {
    return Failed("空の CryptString の URL エンコードの結果が空ではありません");
  }
  // 中身を入れた状態から消して、空に戻ることまで確認する
  std::vector<unsigned char> raw = {1, 2, 3};
  crypt.CopyRawTo(&raw);
  if (!raw.empty()) {
    return Failed("空の CryptString のコピー結果が空ではありません");
  }
  crypt.Clear();
  if (crypt.GetLength() != 0) {
    return Failed("Clear した CryptString の長さが 0 ではありません");
  }
  std::printf("link_test: proxy の実装の確認に成功しました\n");
  return 0;
}

// EnableMedia でメディア関連の実装がリンクされることを確認する
// media_factory の仮想関数がボイスエンジンとビデオエンジンと Call を参照するため、
// この 1 回の呼び出しでメディア周りのシンボルが引けるかどうかが分かる
int TestEnableMedia() {
  webrtc::PeerConnectionFactoryDependencies dependencies;
  webrtc::EnableMedia(dependencies);
  if (dependencies.media_factory == nullptr) {
    return Failed("EnableMedia で media_factory が設定されませんでした");
  }
  std::printf("link_test: EnableMedia の確認に成功しました\n");
  return 0;
}

// サイマルキャストで使う SimulcastEncoderAdapter のコンストラクタとデストラクタが
// 引けることを確認する
int TestSimulcastEncoderAdapter() {
  const webrtc::Environment env = webrtc::CreateEnvironment();
  webrtc::VideoEncoderFactoryTemplate<webrtc::LibvpxVp8EncoderTemplateAdapter> factory;
  // エンコーダの生成は InitEncode で行われるので、ここでは生成と破棄だけを確認する
  webrtc::SimulcastEncoderAdapter adapter(env, &factory, nullptr, webrtc::SdpVideoFormat("VP8"));
  std::printf("link_test: SimulcastEncoderAdapter の確認に成功しました\n");
  return 0;
}

// zlib が入っていることを確認する
int TestZlib() {
  const char* version = zlibVersion();
  if (version == nullptr || version[0] < '0' || version[0] > '9') {
    return Failed("zlib のバージョンを取得できませんでした");
  }
  std::printf("link_test: zlib の確認に成功しました\n");
  return 0;
}

// socket adapters が入っていることを確認する
int TestSocketAdapters() {
  const std::span<const uint8_t> hello = webrtc::AsyncSSLSocket::SslClientHello();
  // SSLv2 形式の CLIENT_HELLO で、先頭がメッセージ長 (0x80 0x46)、3 バイト目が CLIENT_HELLO (0x01)
  if (hello.size() != 0x48 || hello[0] != 0x80 || hello[2] != 0x01) {
    return Failed("SSLv2 形式の ClientHello の中身が期待値と一致しません");
  }
  std::printf("link_test: socket adapters の確認に成功しました\n");
  return 0;
}

// フィールドトライアルが入っていることを確認する
// フィールドトライアル文字列を扱う webrtc::FieldTrials::Create を呼ぶ
int TestFieldTrials() {
  std::unique_ptr<webrtc::FieldTrials> trials =
      webrtc::FieldTrials::Create("WebRTC-LinkTest/Enabled/");
  if (trials == nullptr) {
    return Failed("有効なフィールドトライアル文字列の作成に失敗しました");
  }
  if (trials->Lookup("WebRTC-LinkTest") != "Enabled") {
    return Failed("フィールドトライアルの値が Enabled ではありません");
  }
  // 区切りの / が足りない文字列は不正になる
  if (webrtc::FieldTrials::Create("WebRTC-LinkTest/Enabled") != nullptr) {
    return Failed("不正なフィールドトライアル文字列が受け付けられました");
  }
  std::printf("link_test: フィールドトライアルの確認に成功しました\n");
  return 0;
}

// IceServer の tls_client_identity と、クライアント証明書を作る SSLIdentity の API が
// 入っていることを確認する
int TestTurnTlsClientCertificate() {
  webrtc::PeerConnectionInterface::IceServer server;
  // 不正な PEM なので nullptr になる
  server.tls_client_identity = webrtc::SSLIdentity::CreateFromPEMChainStrings("", "");
  if (server.tls_client_identity != nullptr) {
    return Failed("不正な PEM から SSLIdentity が作成されました");
  }
  std::printf("link_test: TURN-TLS のクライアント証明書の確認に成功しました\n");
  return 0;
}

// log sinks が入っていることを確認する
// ファイルパスは Init を呼ぶまで使われないので、ここでは生成と破棄だけを確認する
int TestLogSinks() {
  webrtc::FileRotatingLogSink sink("", "link_test", 1024 * 1024, 3);
  // ログ出力に繋ぐ AddLogToStream と RemoveLogToStream も呼ぶ
  webrtc::LogMessage::AddLogToStream(&sink, webrtc::LS_INFO);
  webrtc::LogMessage::RemoveLogToStream(&sink);
  std::printf("link_test: log sinks の確認に成功しました\n");
  return 0;
}

// enable_media_with_defaults が入っていることを確認する
// 既定のコーデックとメディアエンジンをまとめて参照するので、ここで引けなければアーカイブに入っていない
int TestEnableMediaWithDefaults() {
  webrtc::PeerConnectionFactoryDependencies dependencies;
  webrtc::EnableMediaWithDefaults(dependencies);
  if (dependencies.media_factory == nullptr || dependencies.audio_encoder_factory == nullptr ||
      dependencies.audio_decoder_factory == nullptr ||
      dependencies.video_encoder_factory == nullptr ||
      dependencies.video_decoder_factory == nullptr) {
    return Failed("EnableMediaWithDefaults で既定の実装が設定されませんでした");
  }
  std::printf("link_test: EnableMediaWithDefaults の確認に成功しました\n");
  return 0;
}

// H.265 の VPS パーサが入っていることを確認する
// 不正なデータなので空の結果になるが、パーサの実装が引けることを確認する
int TestH265VpsParser() {
  const std::optional<webrtc::H265VpsParser::VpsState> state =
      webrtc::H265VpsParser::ParseVps(std::span<const uint8_t>());
  if (state.has_value()) {
    return Failed("空のデータから VPS が取得できました");
  }
  std::printf("link_test: H.265 の VPS パーサの確認に成功しました\n");
  return 0;
}

// Linux の v4l2 のデバイス情報が入っていることを確認する
#if defined(WEBRTC_LINUX)
int TestLinuxVideoCapture() {
  webrtc::VideoCaptureModule::DeviceInfo* device_info =
      webrtc::VideoCaptureFactory::CreateDeviceInfo();
  if (device_info == nullptr) {
    return Failed("v4l2 のデバイス情報を作成できませんでした");
  }
  // カメラが繋がっていない環境では 0 台になるので、台数は見ない
  const uint32_t devices = device_info->NumberOfDevices();
  delete device_info;
  std::printf("link_test: v4l2 のデバイス情報の確認に成功しました (%u 台)\n", devices);
  return 0;
}
#endif

// Windows の Core Audio の ADM を作る関数と、その先の実装が入っていることを確認する
#if defined(WEBRTC_WIN)
int TestWindowsAudioDeviceModule() {
  const webrtc::Environment env = webrtc::CreateEnvironment();
  // COM を初期化していないので nullptr になることがある。
  // Core Audio の ADM を作る関数を呼んで、その先の実装まで引けることを確認する
  webrtc::scoped_refptr<webrtc::AudioDeviceModule> adm =
      webrtc::CreateWindowsCoreAudioAudioDeviceModule(env);
  (void)adm;
  std::printf("link_test: Windows の AudioDeviceModule の確認に成功しました\n");
  return 0;
}
#endif

// macOS の画面キャプチャの実装が入っていることを確認する
// iOS でも WEBRTC_MAC は定義されるが、iOS のアーカイブには desktop_capture が入っていない
#if defined(WEBRTC_MAC) && !defined(WEBRTC_IOS)
int TestMacScreenCapture() {
  const webrtc::DesktopCaptureOptions options =
      webrtc::DesktopCaptureOptions::CreateDefault();
  // 画面収録の権限が無いと nullptr になることがある。ここではリンクの確認だけをする
  std::unique_ptr<webrtc::DesktopCapturer> capturer =
      webrtc::DesktopCapturer::CreateScreenCapturer(options);
  (void)capturer;
  std::printf("link_test: macOS の画面キャプチャの確認に成功しました\n");
  return 0;
}
#endif

}  // namespace

// Apple の ObjC の実装がアーカイブに入っているかは ObjC++ のソースで確認する
#if defined(WEBRTC_MAC)
extern "C" int webrtc_link_test_objc();
#endif

// テストの本体。テストの実行ファイルの main と、C の関数を呼ぶ別のテストプログラムが
// 呼び出すため extern "C" で公開している
extern "C" int webrtc_link_test_main() {
  for (const auto& test : {TestCorruptionDetection, TestThreadAndTaskQueue,
                           TestPeerConnectionFactory, TestVideoFrame,
                           TestAdaptedVideoTrackSource, TestRevivedProxy, TestZlib,
                           TestSocketAdapters, TestFieldTrials, TestTurnTlsClientCertificate,
                           TestLogSinks, TestEnableMedia, TestEnableMediaWithDefaults,
                           TestSimulcastEncoderAdapter, TestH265VpsParser,
#if defined(WEBRTC_MAC)
                           webrtc_link_test_objc,
#endif
#if defined(WEBRTC_LINUX)
                           TestLinuxVideoCapture,
#endif
#if defined(WEBRTC_WIN)
                           TestWindowsAudioDeviceModule,
#endif
#if defined(WEBRTC_MAC) && !defined(WEBRTC_IOS)
                           TestMacScreenCapture,
#endif
                           }) {
    const int result = test();
    if (result != 0) {
      return result;
    }
  }

  std::printf("link_test: 成功しました\n");
  return 0;
}
