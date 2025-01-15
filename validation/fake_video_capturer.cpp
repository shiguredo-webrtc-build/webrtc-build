#include "fake_video_capturer.h"

#include <memory>
#include <thread>

// WebRTC
#include <api/video/i420_buffer.h>
#include <rtc_base/ref_counted_object.h>
#include <rtc_base/timestamp_aligner.h>

// libyuv
#include <libyuv.h>

// Blend2D
#include <blend2d.h>

#include "kosugi_regular_ttf.bin"

class FakeVideoCapturerImpl : public FakeVideoCapturer {
 public:
  FakeVideoCapturerImpl(FakeVideoCapturerConfig config) : config_(config) {
    StartCapture();
  }
  ~FakeVideoCapturerImpl() { StopCapture(); }

  bool is_screencast() const override { return false; }
  std::optional<bool> needs_denoising() const override { return false; }
  webrtc::MediaSourceInterface::SourceState state() const override {
    return SourceState::kLive;
  }
  bool remote() const override { return false; }

  void StartCapture() override {
    StopCapture();
    stopped_ = false;
    started_at_ = std::chrono::high_resolution_clock::now();
    thread_.reset(new std::thread([this]() {
      image_.create(config_.width, config_.height, BL_FORMAT_PRGB32);
      frame_ = 0;
      {
        BLFontFace face;
        BLFontData data;
        data.createFromData(Kosugi_Regular_ttf, sizeof(Kosugi_Regular_ttf));
        BLResult err = face.createFromData(data, 0);

        // We must handle a possible error returned by the loader.
        if (err) {
          //printf("Failed to load a font-face (err=%u)\n", err);
          return;
        }

        base_font_.createFromFace(face, config_.height * 0.08);
        bipbop_font_.createFromFace(face, base_font_.size() * 2.5);
        stats_font_.createFromFace(face, base_font_.size() * 0.5);
      }

      while (!stopped_) {
        auto now = std::chrono::high_resolution_clock::now();
        rtc::scoped_refptr<webrtc::I420Buffer> buffer;

        UpdateImage(now);

        BLImageData data;
        BLResult result = image_.getData(&data);
        if (result != BL_SUCCESS) {
          std::this_thread::sleep_until(now + std::chrono::milliseconds(16));
          continue;
        }

        buffer = webrtc::I420Buffer::Create(config_.width, config_.height);

        libyuv::ABGRToI420((const uint8_t*)data.pixelData, data.stride,
                           buffer->MutableDataY(), buffer->StrideY(),
                           buffer->MutableDataU(), buffer->StrideU(),
                           buffer->MutableDataV(), buffer->StrideV(),
                           config_.width, config_.height);

        int64_t timestamp_us =
            std::chrono::duration_cast<std::chrono::microseconds>(now -
                                                                  started_at_)
                .count();

        bool captured =
            OnCapturedFrame(webrtc::VideoFrame::Builder()
                                .set_video_frame_buffer(buffer)
                                .set_rotation(webrtc::kVideoRotation_0)
                                .set_timestamp_us(timestamp_us)
                                .build());

        if (captured) {
          std::this_thread::sleep_until(
              now + std::chrono::milliseconds(1000 / config_.fps - 2));
          frame_ += 1;
        } else {
          std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
      }
    }));
  }
  void StopCapture() override {
    if (thread_) {
      stopped_ = true;
      thread_->join();
      thread_.reset();
    }
  }

 private:
  void UpdateImage(std::chrono::high_resolution_clock::time_point now) {
    BLContext ctx(image_);

    ctx.setCompOp(BL_COMP_OP_SRC_COPY);
    ctx.fillAll();

    ctx.save();
    DrawTexts(ctx, now);
    ctx.restore();

    ctx.save();
    DrawAnimations(ctx, now);
    ctx.restore();

    ctx.save();
    DrawBoxes(ctx, now);
    ctx.restore();

    ctx.end();
  }
  void DrawTexts(BLContext& ctx,
                 std::chrono::high_resolution_clock::time_point now) {
    auto ms =
        std::chrono::duration_cast<std::chrono::milliseconds>(now - started_at_)
            .count();

    ctx.setFillStyle(BLRgba32(0xFFFFFFFF));

    int width = config_.width;
    int height = config_.height;
    int fps = config_.fps;

    auto pad = [](char c, int d, int v) {
      std::string s;
      for (int i = 0; i < d || v != 0; i++) {
        if (i != 0 && v == 0) {
          s = c + s;
          continue;
        }

        s = (char)('0' + (v % 10)) + s;
        v /= 10;
      }
      return s;
    };

    {
      std::string text = pad('0', 2, ms / (60 * 60 * 1000)) + ':' +
                         pad('0', 2, ms / (60 * 1000) % 60) + ':' +
                         pad('0', 2, ms / 1000 % 60) + '.' +
                         pad('0', 3, ms % 1000);
      ctx.fillUtf8Text(BLPoint(width * 0.05, height * .15), base_font_,
                       text.c_str());
    }

    {
      std::string text = pad('0', 6, frame_);
      ctx.fillUtf8Text(BLPoint(width * 0.05, height * .15 + base_font_.size()),
                       base_font_, text.c_str());
    }

    {
      std::string text =
          "Requested frame rate: " + std::to_string(fps) + " fps";
      ctx.fillUtf8Text(BLPoint(width * 0.45, height * 0.75), stats_font_,
                       text.c_str());
    }
    {
      std::string text =
          "Size: " + std::to_string(width) + " x " + std::to_string(height);
      ctx.fillUtf8Text(
          BLPoint(width * 0.45, height * 0.75 + stats_font_.size()),
          stats_font_, text.c_str());
    }

    {
      int m = frame_ % 60;
      if (m < 15) {
        ctx.setFillStyle(BLRgba32(0, 255, 255));
        ctx.fillUtf8Text(BLPoint(width * 0.6, height * 0.6), bipbop_font_,
                         "Bip");
      } else if (m >= 30 && m < 45) {
        ctx.setFillStyle(BLRgba32(255, 255, 0));
        ctx.fillUtf8Text(BLPoint(width * 0.6, height * 0.6), bipbop_font_,
                         "Bop");
      }
    }
  }
  void DrawAnimations(BLContext& ctx,
                      std::chrono::high_resolution_clock::time_point now) {
    int width = config_.width;
    int height = config_.height;
    int fps = config_.fps;

    float pi = 3.14159;
    ctx.translate(width * 0.8, height * 0.3);
    ctx.rotate(-pi / 2);
    ctx.setFillStyle(BLRgba32(255, 255, 255));
    ctx.fillPie(0, 0, width * 0.09, 0, 2 * pi);

    ctx.setFillStyle(BLRgba32(160, 160, 160));
    ctx.fillPie(0, 0, width * 0.09, 0,
                (frame_ % fps) / (float)fps * 2 * 3.14159);
  }

  void DrawBoxes(BLContext& ctx,
                 std::chrono::high_resolution_clock::time_point now) {
    int width = config_.width;
    int height = config_.height;

    float size = width * 0.035;
    float top = height * 0.6;

    ctx.setFillStyle(BLRgba32(255, 255, 255));
    ctx.setStrokeStyle(BLRgba32(255, 255, 255));

    ctx.setStrokeWidth(2);
    BLArray<double> dash;
    // 本当はこれで点線になるはずだが、現在動かない
    // https://github.com/blend2d/blend2d/issues/48
    dash.resize(2, 6);
    ctx.setStrokeDashArray(dash);
    ctx.strokeRect(2, 2, width - 4, height - 4);

    ctx.setStrokeDashArray(BLArray<double>());
    ctx.strokeLine(0, top + size, width, top + size);

    ctx.setStrokeWidth(2);
    float left = size;
    for (int i = 0; i < size / 4; i++) {
      ctx.strokeLine(left + 4 * i, top, left + 4 * i, top + size);
    }
    left += size + 2;
    for (int i = 0; i < size / 4; i++) {
      ctx.strokeLine(left, top + 4 * i, left + size, top + 4 * i);
    }

    ctx.setStrokeWidth(3);
    left += size + 2;
    for (int i = 0; i < size / 8; i++) {
      ctx.strokeLine(left + 8 * i, top, left + 8 * i, top + size);
    }
    left += size + 2;
    for (int i = 0; i < size / 8; i++) {
      ctx.strokeLine(left, top + 8 * i, left + size, top + 8 * i);
    }

    const BLRgba32 colors[] = {
        BLRgba32(255, 255, 255), BLRgba32(255, 255, 0), BLRgba32(0, 255, 255),
        BLRgba32(0, 128, 0),     BLRgba32(255, 0, 255), BLRgba32(255, 0, 0),
        BLRgba32(0, 0, 255),
    };
    left = size;
    for (const auto& color : colors) {
      ctx.setFillStyle(color);
      ctx.fillRect(left, top + size + 2, size + 1, size + 1);
      left += size + 1;
    }
  }

  bool OnCapturedFrame(const webrtc::VideoFrame& video_frame) {
    webrtc::VideoFrame frame = video_frame;

    const int64_t timestamp_us = frame.timestamp_us();
    const int64_t translated_timestamp_us =
        timestamp_aligner_.TranslateTimestamp(timestamp_us, rtc::TimeMicros());

    // 回転が必要
    if (frame.rotation() != webrtc::kVideoRotation_0) {
      int width;
      int height;
      libyuv::RotationMode mode;
      switch (frame.rotation()) {
        case webrtc::kVideoRotation_180:
          width = frame.width();
          height = frame.height();
          mode = libyuv::kRotate180;
          break;
        case webrtc::kVideoRotation_90:
          width = frame.height();
          height = frame.width();
          mode = libyuv::kRotate90;
          break;
        case webrtc::kVideoRotation_270:
        default:
          width = frame.height();
          height = frame.width();
          mode = libyuv::kRotate270;
          break;
      }

      rtc::scoped_refptr<webrtc::I420Buffer> rotated =
          webrtc::I420Buffer::Create(width, height);
      rtc::scoped_refptr<webrtc::I420BufferInterface> src =
          frame.video_frame_buffer()->ToI420();
      libyuv::I420Rotate(src->DataY(), src->StrideY(), src->DataU(),
                         src->StrideU(), src->DataV(), src->StrideV(),
                         rotated->MutableDataY(), rotated->StrideY(),
                         rotated->MutableDataU(), rotated->StrideU(),
                         rotated->MutableDataV(), rotated->StrideV(),
                         frame.width(), frame.height(), mode);
      frame.set_video_frame_buffer(rotated);
      frame.set_rotation(webrtc::kVideoRotation_0);
    }

    int adapted_width;
    int adapted_height;
    int crop_width;
    int crop_height;
    int crop_x;
    int crop_y;
    if (!AdaptFrame(frame.width(), frame.height(), timestamp_us, &adapted_width,
                    &adapted_height, &crop_width, &crop_height, &crop_x,
                    &crop_y)) {
      return false;
    }

    if (frame.video_frame_buffer()->type() ==
        webrtc::VideoFrameBuffer::Type::kNative) {
      OnFrame(frame);
      return true;
    }

    rtc::scoped_refptr<webrtc::VideoFrameBuffer> buffer =
        frame.video_frame_buffer();

    if (adapted_width != frame.width() || adapted_height != frame.height()) {
      // Video adapter has requested a down-scale. Allocate a new buffer and
      // return scaled version.
      rtc::scoped_refptr<webrtc::I420Buffer> i420_buffer =
          webrtc::I420Buffer::Create(adapted_width, adapted_height);
      i420_buffer->ScaleFrom(*buffer->ToI420());
      buffer = i420_buffer;
    }

    OnFrame(webrtc::VideoFrame::Builder()
                .set_video_frame_buffer(buffer)
                .set_rotation(frame.rotation())
                .set_timestamp_us(translated_timestamp_us)
                .build());

    return true;
  }

 private:
  std::unique_ptr<std::thread> thread_;
  FakeVideoCapturerConfig config_;
  std::atomic_bool stopped_{false};
  std::chrono::high_resolution_clock::time_point started_at_;

  rtc::TimestampAligner timestamp_aligner_;

  BLImage image_;
  BLFont base_font_;
  BLFont bipbop_font_;
  BLFont stats_font_;
  uint32_t frame_;
};

rtc::scoped_refptr<FakeVideoCapturer> CreateFakeVideoCapturer(
    FakeVideoCapturerConfig config) {
  return rtc::make_ref_counted<FakeVideoCapturerImpl>(config);
}
