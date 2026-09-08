#import <AudioToolbox/AudioToolbox.h>
#import <Foundation/Foundation.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <span>
#include <vector>

#include "api/audio/audio_device.h"
#include "api/environment/environment_factory.h"
#include "rtc_base/thread.h"
#include "sdk/objc/native/api/objc_audio_device_module.h"

namespace {

void Require(bool condition, const char *message) {
  if (!condition) {
    std::fprintf(stderr, "失敗: %s\n", message);
    std::exit(EXIT_FAILURE);
  }
}

// 録音した PCM を保存し、再生要求には保存した PCM を順に返すメモリー音声転送。
// ADM とその内部バッファは実物を使い、この境界で 10 ms ごとの入力を観測する。
class MemoryAudioTransport final : public webrtc::AudioTransport {
 public:
  explicit MemoryAudioTransport(size_t channels) : channels_(channels) {}

  int32_t RecordedDataIsAvailable(const void *audio_samples, size_t frames, size_t bytes_per_frame,
                                  size_t channels, uint32_t sample_rate, uint32_t, int32_t,
                                  uint32_t microphone_level, bool,
                                  uint32_t &new_microphone_level) override {
    Require(frames == 480, "ADM の通知は 48 kHz の 10 ms 単位であること");
    Require(channels == channels_, "録音チャンネル数が一致すること");
    Require(sample_rate == 48000, "録音サンプルレートが一致すること");
    Require(bytes_per_frame == channels * sizeof(int16_t),
            "フレームのバイト数が全チャンネルを含むこと");
    const auto *begin = static_cast<const int16_t *>(audio_samples);
    samples.insert(samples.end(), begin, begin + frames * channels);
    new_microphone_level = microphone_level;
    ++callbacks;
    return 0;
  }

  int32_t NeedMorePlayData(size_t frames, size_t bytes_per_frame, size_t channels,
                           uint32_t sample_rate, void *audio_samples, size_t &samples_out,
                           int64_t *elapsed_time_ms, int64_t *ntp_time_ms) override {
    Require(bytes_per_frame == channels * sizeof(int16_t), "再生フレームのバイト数が一致すること");
    PullRenderData(16, sample_rate, channels, frames, audio_samples, elapsed_time_ms, ntp_time_ms);
    // 出力個数には全チャンネルのサンプル数を返す。
    // AudioDeviceBuffer がチャンネル数で割ってフレーム数へ戻す。
    samples_out = frames * channels;
    return 0;
  }

  void PullRenderData(int bits_per_sample, int sample_rate, size_t channels, size_t frames,
                      void *audio_samples, int64_t *elapsed_time_ms,
                      int64_t *ntp_time_ms) override {
    Require(bits_per_sample == 16 && sample_rate == 48000 && channels == channels_,
            "メモリー再生の PCM 形式が一致すること");
    auto *output = static_cast<int16_t *>(audio_samples);
    const size_t count = frames * channels;
    const size_t available = std::min(count, samples.size() - played_samples_);
    std::copy_n(samples.data() + played_samples_, available, output);
    std::fill(output + available, output + count, 0);
    if (elapsed_time_ms) {
      *elapsed_time_ms = played_samples_ / channels / 48;
    }
    if (ntp_time_ms) {
      *ntp_time_ms = 0;
    }
    played_samples_ += available;
  }

  std::vector<int16_t> samples;
  size_t callbacks = 0;

 private:
  const size_t channels_;
  size_t played_samples_ = 0;
};

// 左右とフレーム位置を区別できる PCM。今回の入力長では値が周回しない。
std::vector<int16_t> MakeSamples(size_t frames, size_t channels) {
  std::vector<int16_t> samples(frames * channels);
  for (size_t frame = 0; frame < frames; ++frame) {
    samples[frame * channels] = static_cast<int16_t>(frame + 1);
    if (channels == 2) {
      samples[frame * channels + 1] = -static_cast<int16_t>(frame + 1);
    }
  }
  return samples;
}

}

// 音声ハードウェアを使わず、明示的に供給した PCM を実際の delegate へ送る。
// 各ライフサイクル操作は状態を更新し、ADM が指定した録音・再生状態を保持する。
@interface MemoryAudioDevice : NSObject <RTCAudioDevice>
@property(nonatomic, readonly) id<RTCAudioDeviceDelegate> delegate;
@property(nonatomic) NSInteger channelCount;
@end

@implementation MemoryAudioDevice {
  id<RTCAudioDeviceDelegate> _delegate;
  BOOL _isPlayoutInitialized;
  BOOL _isRecordingInitialized;
  BOOL _isPlaying;
  BOOL _isRecording;
}

- (id<RTCAudioDeviceDelegate>)delegate {
  return _delegate;
}
- (double)deviceInputSampleRate {
  return 48000;
}
- (double)deviceOutputSampleRate {
  return 48000;
}
- (NSTimeInterval)inputIOBufferDuration {
  return 0.020;
}
- (NSTimeInterval)outputIOBufferDuration {
  return 0.020;
}
- (NSInteger)inputNumberOfChannels {
  return self.channelCount;
}
- (NSInteger)outputNumberOfChannels {
  return self.channelCount;
}
- (NSTimeInterval)inputLatency {
  return 0;
}
- (NSTimeInterval)outputLatency {
  return 0;
}
- (BOOL)isInitialized {
  return _delegate != nil;
}
- (BOOL)isPlayoutInitialized {
  return _isPlayoutInitialized;
}
- (BOOL)isRecordingInitialized {
  return _isRecordingInitialized;
}
- (BOOL)isPlaying {
  return _isPlaying;
}
- (BOOL)isRecording {
  return _isRecording;
}

- (BOOL)initializeWithDelegate:(id<RTCAudioDeviceDelegate>)delegate {
  if (_delegate != nil || delegate == nil) {
    return NO;
  }
  _delegate = delegate;
  return YES;
}

- (BOOL)terminateDevice {
  _isPlaying = NO;
  _isRecording = NO;
  _isPlayoutInitialized = NO;
  _isRecordingInitialized = NO;
  _delegate = nil;
  return YES;
}

- (BOOL)initializePlayout {
  _isPlayoutInitialized = self.isInitialized;
  return _isPlayoutInitialized;
}

- (BOOL)initializeRecording {
  _isRecordingInitialized = self.isInitialized;
  return _isRecordingInitialized;
}

- (BOOL)startPlayout {
  _isPlaying = _isPlayoutInitialized;
  return _isPlaying;
}

- (BOOL)startRecording {
  _isRecording = _isRecordingInitialized;
  return _isRecording;
}

- (BOOL)stopPlayout {
  _isPlaying = NO;
  return YES;
}

- (BOOL)stopRecording {
  _isRecording = NO;
  return YES;
}

@end

namespace {

class RecordingSession {
 public:
  explicit RecordingSession(size_t channels) : transport(channels) {
    device = [[MemoryAudioDevice alloc] init];
    device.channelCount = channels;
    module = webrtc::CreateAudioDeviceModule(webrtc::CreateEnvironment(), device);
    Require(module->Init() == 0, "実際のカスタム ADM が初期化できること");
    Require(module->RegisterAudioCallback(&transport) == 0, "メモリー音声転送を登録できること");
    Require(module->InitRecording() == 0, "録音を初期化できること");
    Require(module->StartRecording() == 0, "録音を開始できること");
  }

  ~RecordingSession() {
    Require(module->StopRecording() == 0, "録音を停止できること");
    Require(module->RegisterAudioCallback(nullptr) == 0, "音声転送の登録を解除できること");
    Require(module->Terminate() == 0, "実際のカスタム ADM を終了できること");
  }

  OSStatus Deliver(UInt32 frames, const AudioBufferList *input_data,
                   RTCAudioDeviceRenderRecordedDataBlock render_block = nil) {
    AudioUnitRenderActionFlags flags = 0;
    AudioTimeStamp timestamp = {};
    return device.delegate.deliverRecordedData(&flags, &timestamp, 0, frames, input_data, nullptr,
                                               render_block);
  }

  OSStatus Deliver(std::span<const int16_t> samples, bool render) {
    const UInt32 frames = samples.size() / device.channelCount;
    if (render) {
      return Deliver(frames, nullptr,
                     ^OSStatus(AudioUnitRenderActionFlags *, const AudioTimeStamp *, NSInteger,
                               UInt32 count, AudioBufferList *buffers, void *) {
                       Require(count == frames && buffers->mNumberBuffers == 1,
                               "renderBlock のフレーム数とバッファ数が一致すること");
                       Require(buffers->mBuffers[0].mDataByteSize == samples.size_bytes(),
                               "renderBlock の保存領域が全チャンネル分あること");
                       std::memcpy(buffers->mBuffers[0].mData, samples.data(),
                                   samples.size_bytes());
                       return noErr;
                     });
    }
    AudioBufferList buffers = {
        1,
        {{static_cast<UInt32>(device.channelCount), static_cast<UInt32>(samples.size_bytes()),
          const_cast<int16_t *>(samples.data())}}};
    return Deliver(frames, &buffers);
  }

  MemoryAudioTransport transport;
  MemoryAudioDevice *device;
  webrtc::scoped_refptr<webrtc::AudioDeviceModule> module;
};

void TestCompleteInput(size_t channels, bool render) {
  RecordingSession session(channels);
  const auto expected = MakeSamples(960, channels);
  Require(session.Deliver(expected, render) == noErr, "20 ms の入力に成功すること");
  std::printf("確認: %zu ch / %s、通知 %zu 回、PCM %zu サンプル\n", channels,
              render ? "renderBlock" : "inputData", session.transport.callbacks,
              session.transport.samples.size());
  Require(session.transport.callbacks == 2, "20 ms の入力が 10 ms の通知 2 回になること");
  Require(session.transport.samples == expected, "入力の後半を含めて PCM が完全一致すること");

  // 保存した録音 PCM を実際の再生コールバックから取り出し、転送の往復も確認する。
  Require(session.module->InitPlayout() == 0, "メモリー再生を初期化できること");
  Require(session.module->StartPlayout() == 0, "メモリー再生を開始できること");
  std::vector<int16_t> played(expected.size());
  AudioBufferList output = {
      1,
      {{static_cast<UInt32>(channels), static_cast<UInt32>(played.size() * sizeof(int16_t)),
        played.data()}}};
  AudioUnitRenderActionFlags flags = 0;
  AudioTimeStamp timestamp = {};
  Require(session.device.delegate.getPlayoutData(&flags, &timestamp, 0, 960, &output) == noErr,
          "実際の再生コールバックに成功すること");
  Require(played == expected, "メモリー転送の再生 PCM が録音 PCM と一致すること");
  Require(session.module->StopPlayout() == 0, "メモリー再生を停止できること");
}

void TestCallbackBoundaries(size_t channels, bool render) {
  RecordingSession session(channels);
  const auto expected = MakeSamples(480 * 20, channels);
  size_t offset = 0;
  uint32_t random = 1234567;
  while (offset < expected.size()) {
    // 10 ms より短い入力と長い入力を混在させ、同じ分割列を再現可能にする。
    random = random * 1664525 + 1013904223;
    size_t count = (1 + random % 1100) * channels;
    count = std::min(count, expected.size() - offset);
    Require(session.Deliver(std::span(expected).subspan(offset, count), render) == noErr,
            "コールバックをまたぐ入力に成功すること");
    offset += count;
    const size_t delivered = (offset / (480 * channels)) * (480 * channels);
    Require(session.transport.samples.size() == delivered, "10 ms 未満の残りが保持されること");
    Require(std::equal(session.transport.samples.begin(), session.transport.samples.end(),
                       expected.begin()),
            "蓄積した PCM の順序が一致すること");
  }
  Require(session.transport.samples == expected, "分割入力の全 PCM が一致すること");
}

void TestInvalidInput(size_t channels) {
  RecordingSession session(channels);
  const auto expected = MakeSamples(480, channels);
  Require(session.Deliver(std::span(expected).first(240 * channels), false) == noErr,
          "エラー前に 5 ms を蓄積できること");
  AudioBufferList valid = {
      1,
      {{static_cast<UInt32>(channels), static_cast<UInt32>(expected.size() * sizeof(int16_t)),
        const_cast<int16_t *>(expected.data())}}};
  constexpr std::array invalid_names = {
      "バッファ数 0",   "バッファ数 2",         "入力チャンネル数 0", "チャンネル数不一致",
      "バッファ長不足", "データポインターなし", "フレーム数上限"};
  for (size_t invalid = 0; invalid < invalid_names.size(); ++invalid) {
    AudioBufferList buffers = valid;
    UInt32 frames = 480;
    switch (invalid) {
      case 0:
        buffers.mNumberBuffers = 0;
        break;
      case 1:
        buffers.mNumberBuffers = 2;
        break;
      case 2:
        buffers.mBuffers[0].mNumberChannels = 0;
        break;
      case 3:
        buffers.mBuffers[0].mNumberChannels = 3 - channels;
        break;
      case 4:
        --buffers.mBuffers[0].mDataByteSize;
        break;
      case 5:
        buffers.mBuffers[0].mData = nullptr;
        break;
      case 6:
        frames = std::numeric_limits<UInt32>::max();
        break;
    }
    const OSStatus result = session.Deliver(frames, &buffers);
    if (result != kAudio_ParamError || !session.transport.samples.empty()) {
      std::fprintf(stderr,
                   "失敗: %zu ch / %s、戻り値の期待値 %ld、実際 %ld、"
                   "通知 PCM の期待値 0、実際 %zu サンプル\n",
                   channels, invalid_names[invalid], static_cast<long>(kAudio_ParamError),
                   static_cast<long>(result), session.transport.samples.size());
      std::exit(EXIT_FAILURE);
    }
  }

  // 5 ms の端数がある状態で 0 フレームを挟み、蓄積が消えないことを確認する。
  AudioBufferList empty = valid;
  empty.mBuffers[0].mData = nullptr;
  empty.mBuffers[0].mDataByteSize = 0;
  Require(session.Deliver(0, &empty) == noErr, "0 フレームを安全に受け付けること");
  Require(session.transport.samples.empty(), "0 フレームで余分な通知がないこと");
  Require(session.Deliver(std::span(expected).subspan(240 * channels), false) == noErr,
          "エラー後の正常入力を受け付けること");
  Require(session.transport.samples == expected, "エラー前の蓄積が失われないこと");

  Require(session.module->StopRecording() == 0, "録音停止に成功すること");
  valid.mNumberBuffers = 0;
  Require(session.Deliver(480, &valid) == noErr, "録音停止中は入力を検査せず成功すること");
}

void TestOversizedBuffer(size_t channels) {
  RecordingSession session(channels);
  auto samples = MakeSamples(960, channels);
  AudioBufferList buffers = {
      1,
      {{static_cast<UInt32>(channels), static_cast<UInt32>(samples.size() * sizeof(int16_t)),
        samples.data()}}};
  Require(session.Deliver(480, &buffers) == noErr, "必要量より大きなバッファを受け付けること");
  samples.resize(480 * channels);
  Require(session.transport.samples == samples, "指定フレーム数を超えて取り込まないこと");
}

void TestUnsupportedRecordingChannels() {
  // リリースビルドでも、録音設定自体が 1 ch / 2 ch 以外なら入力を拒否する。
  RecordingSession session(3);
  const auto samples = MakeSamples(480, 3);
  Require(session.Deliver(samples, false) == kAudio_ParamError,
          "未対応の録音チャンネル数を拒否すること");
  Require(session.transport.samples.empty(), "未対応の録音設定では PCM を取り込まないこと");
}

}

int main() {
  @autoreleasepool {
    auto thread = webrtc::Thread::Create();
    Require(thread->Start(), "ADM の実行スレッドを開始できること");
    thread->BlockingCall([] {
      @autoreleasepool {
        for (size_t channels : {1, 2}) {
          for (bool render : {false, true}) {
            TestCompleteInput(channels, render);
            TestCallbackBoundaries(channels, render);
          }
        }
        for (size_t channels : {1, 2}) {
          TestInvalidInput(channels);
          TestOversizedBuffer(channels);
        }
        TestUnsupportedRecordingChannels();
      }
    });
    thread->Stop();
  }
  std::puts("成功: カスタム ADM の入力、分割、エラー後の蓄積を確認しました");
  return EXIT_SUCCESS;
}
