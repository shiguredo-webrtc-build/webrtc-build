#ifndef FAKE_VIDEO_CAPTURER_H_
#define FAKE_VIDEO_CAPTURER_H_

// WebRTC
#include <media/base/adapted_video_track_source.h>

struct FakeVideoCapturerConfig {
  int width;
  int height;
  int fps;
};

class FakeVideoCapturer : public rtc::AdaptedVideoTrackSource {
 public:
  virtual void StartCapture() = 0;
  virtual void StopCapture() = 0;
};

rtc::scoped_refptr<FakeVideoCapturer> CreateFakeVideoCapturer(
    FakeVideoCapturerConfig config);

#endif
