#ifndef MODULES_VIDEO_CAPTURE_WINDOWS_MRC_VIDEO_EFFECT_DEFINITION_H_
#define MODULES_VIDEO_CAPTURE_WINDOWS_MRC_VIDEO_EFFECT_DEFINITION_H_

#include <stddef.h>
#include <memory>

namespace webrtc {

class MrcVideoEffectDefinition {
 public:
  static std::shared_ptr<MrcVideoEffectDefinition> Create();

  virtual ~MrcVideoEffectDefinition() {}

  enum class MediaStreamType {
    VideoPreview = 0,
    VideoRecord = 1,
    Audio = 2,
    Photo = 3,
    Metadata = 4,
  };

  virtual MediaStreamType StreamType() = 0;
  virtual void StreamType(MediaStreamType newValue) = 0;

  virtual bool HologramCompositionEnabled() = 0;
  virtual void HologramCompositionEnabled(bool newValue) = 0;

  virtual bool RecordingIndicatorEnabled() = 0;
  virtual void RecordingIndicatorEnabled(bool newValue) = 0;

  virtual bool VideoStabilizationEnabled() = 0;
  virtual void VideoStabilizationEnabled(bool newValue) = 0;

  virtual uint32_t VideoStabilizationBufferLength() = 0;
  virtual void VideoStabilizationBufferLength(uint32_t newValue) = 0;

  virtual float GlobalOpacityCoefficient() = 0;
  virtual void GlobalOpacityCoefficient(float newValue) = 0;
};

}  // namespace webrtc

#endif