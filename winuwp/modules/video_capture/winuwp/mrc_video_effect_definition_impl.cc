#include "mrc_video_effect_definition_impl.h"

namespace webrtc {

MrcVideoEffectDefinitionImpl::MrcVideoEffectDefinitionImpl() {
  StreamType(DefaultStreamType);
  HologramCompositionEnabled(DefaultHologramCompositionEnabled);
  RecordingIndicatorEnabled(DefaultRecordingIndicatorEnabled);
  VideoStabilizationEnabled(DefaultVideoStabilizationEnabled);
  VideoStabilizationBufferLength(DefaultVideoStabilizationBufferLength);
  //VideoStabilizationBufferLength(0);
  GlobalOpacityCoefficient(DefaultGlobalOpacityCoefficient);
}

std::shared_ptr<MrcVideoEffectDefinition> MrcVideoEffectDefinition::Create() {
  auto p = winrt::make_self<MrcVideoEffectDefinitionImpl>();
  return std::shared_ptr<MrcVideoEffectDefinition>(p.detach(), [](MrcVideoEffectDefinition* p) {
    winrt::com_ptr<MrcVideoEffectDefinitionImpl> cp;
    cp.attach(static_cast<MrcVideoEffectDefinitionImpl*>(p));
  });
}

}  // namespace webrtc