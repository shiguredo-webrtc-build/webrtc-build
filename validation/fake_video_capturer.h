#ifndef FAKE_VIDEO_CAPTURER_H_
#define FAKE_VIDEO_CAPTURER_H_

// WebRTC
#include <media/base/adapted_video_track_source.h>
#include <media/base/video_adapter.h>
#include <rtc_base/timestamp_aligner.h>
#include <api/make_ref_counted.h>

struct FakeVideoCapturerConfig {
  int width;
  int height;
  int fps;
};

class FakeVideoCapturer : public rtc::AdaptedVideoTrackSource {
 public:
  FakeVideoCapturer(FakeVideoCapturerConfig config) : config_(config) {}
  ~FakeVideoCapturer() override {}

  bool is_screencast() const override { return false; }
  absl::optional<bool> needs_denoising() const override { return false; }
  webrtc::MediaSourceInterface::SourceState state() const override { return SourceState::kLive; }
  bool remote() const override { return false; }

 private:
  FakeVideoCapturerConfig config_;
};

rtc::scoped_refptr<FakeVideoCapturer> CreateFakeVideoCapturer(
    FakeVideoCapturerConfig config) { return rtc::make_ref_counted<FakeVideoCapturer>(config);}

#endif