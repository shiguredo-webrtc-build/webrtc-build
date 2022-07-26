#ifndef MODULES_VIDEO_CAPTURE_WINDOWS_MRC_VIDEO_EFFECT_DEFINITION_IMPL_H_
#define MODULES_VIDEO_CAPTURE_WINDOWS_MRC_VIDEO_EFFECT_DEFINITION_IMPL_H_

#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Media.Effects.h>
#include <winrt/base.h>

#include "mrc_video_effect_definition.h"

// This class provides an IAudioEffectDefinition which can be used
// to configure and create a MixedRealityCaptureVideoEffect
// object. See https://developer.microsoft.com/en-us/windows/holographic/mixed_reality_capture_for_developers#creating_a_custom_mixed_reality_capture_.28mrc.29_recorder
// for more information about the effect definition properties.

#define RUNTIMECLASS_MIXEDREALITYCAPTURE_VIDEO_EFFECT \
  L"Windows.Media.MixedRealityCapture.MixedRealityCaptureVideoEffect"

//
// StreamType: Describe which capture stream this effect is used for.
// Type: Windows::Media::Capture::MediaStreamType as UINT32
// Default: VideoRecord
//
#define PROPERTY_STREAMTYPE L"StreamType"

//
// HologramCompositionEnabled: Flag to enable or disable holograms in video capture.
// Type: bool
// Default: True
//
#define PROPERTY_HOLOGRAMCOMPOSITIONENABLED L"HologramCompositionEnabled"

//
// RecordingIndicatorEnabled: Flag to enable or disable recording indicator on screen during hologram capturing.
// Type: bool
// Default: True
//
#define PROPERTY_RECORDINGINDICATORENABLED L"RecordingIndicatorEnabled"

//
// VideoStabilizationEnabled: Flag to enable or disable video stabilization powered by the HoloLens tracker.
// Type : bool
// Default: False
//
#define PROPERTY_VIDEOSTABILIZATIONENABLED L"VideoStabilizationEnabled"

//
// VideoStabilizationBufferLength: Set how many historical frames are used for video stabilization.
// Type : UINT32 (Max num is 30)
// Default: 0
//
#define PROPERTY_VIDEOSTABILIZATIONBUFFERLENGTH \
  L"VideoStabilizationBufferLength"

//
// GlobalOpacityCoefficient: Set global opacity coefficient of hologram.
// Type : float (0.0 to 1.0)
// Default: 0.9
//
#define PROPERTY_GLOBALOPACITYCOEFFICIENT L"GlobalOpacityCoefficient"

//
// Maximum value of VideoStabilizationBufferLength
// This number is defined and used in MixedRealityCaptureVideoEffect
//
#define PROPERTY_MAX_VSBUFFER 30U

namespace webrtc {
template <typename T, typename U>
U GetValueFromPropertySet(
    winrt::Windows::Foundation::Collections::IPropertySet const& propertySet,
    winrt::hstring const& key,
    U defaultValue) {
  try {
    return static_cast<U>(
        static_cast<T>(winrt::unbox_value<T>(propertySet.Lookup(key))));
  } catch (winrt::hresult_out_of_bounds const& /*e*/) {
    // The key is not present in the PropertySet. Return the default value.
    return defaultValue;
  }
}

class MrcVideoEffectDefinitionImpl
    : public MrcVideoEffectDefinition
    , public winrt::implements<
          MrcVideoEffectDefinitionImpl,
          winrt::Windows::Media::Effects::IVideoEffectDefinition> {
 public:
  MrcVideoEffectDefinitionImpl();

  //
  // IVideoEffectDefinition
  //
  winrt::hstring ActivatableClassId() { return m_activatableClassId; }

  winrt::Windows::Foundation::Collections::IPropertySet Properties() {
    return m_propertySet;
  }

  //
  // Mixed Reality Capture effect properties
  //
  MediaStreamType StreamType() override {
    return (MediaStreamType)GetValueFromPropertySet<uint32_t>(
              m_propertySet, PROPERTY_STREAMTYPE, DefaultStreamType);
  }

  void StreamType(MediaStreamType newValue) override {
    m_propertySet.Insert(PROPERTY_STREAMTYPE,
                         winrt::box_value(static_cast<uint32_t>(newValue)));
  }

  bool HologramCompositionEnabled() override {
    return GetValueFromPropertySet<bool>(m_propertySet,
                                         PROPERTY_HOLOGRAMCOMPOSITIONENABLED,
                                         DefaultHologramCompositionEnabled);
  }

  void HologramCompositionEnabled(bool newValue) override {
    m_propertySet.Insert(PROPERTY_HOLOGRAMCOMPOSITIONENABLED,
                         winrt::box_value(newValue));
  }

  bool RecordingIndicatorEnabled() override {
    return GetValueFromPropertySet<bool>(m_propertySet,
                                         PROPERTY_RECORDINGINDICATORENABLED,
                                         DefaultRecordingIndicatorEnabled);
  }

  void RecordingIndicatorEnabled(bool newValue) override {
    m_propertySet.Insert(PROPERTY_RECORDINGINDICATORENABLED,
                         winrt::box_value(newValue));
  }

  bool VideoStabilizationEnabled() override {
    return GetValueFromPropertySet<bool>(m_propertySet,
                                         PROPERTY_VIDEOSTABILIZATIONENABLED,
                                         DefaultVideoStabilizationEnabled);
  }

  void VideoStabilizationEnabled(bool newValue) override {
    m_propertySet.Insert(PROPERTY_VIDEOSTABILIZATIONENABLED,
                         winrt::box_value(newValue));
  }

  uint32_t VideoStabilizationBufferLength() override {
    return GetValueFromPropertySet<uint32_t>(
        m_propertySet, PROPERTY_VIDEOSTABILIZATIONBUFFERLENGTH,
        DefaultVideoStabilizationBufferLength);
  }

  void VideoStabilizationBufferLength(uint32_t newValue) override {
    m_propertySet.Insert(
        PROPERTY_VIDEOSTABILIZATIONBUFFERLENGTH,
        winrt::box_value((std::min)(newValue, PROPERTY_MAX_VSBUFFER)));
  }

  float GlobalOpacityCoefficient() override {
    return GetValueFromPropertySet<float>(m_propertySet,
                                          PROPERTY_GLOBALOPACITYCOEFFICIENT,
                                          DefaultGlobalOpacityCoefficient);
  }

  void GlobalOpacityCoefficient(float newValue) override {
    m_propertySet.Insert(PROPERTY_GLOBALOPACITYCOEFFICIENT,
                         winrt::box_value(newValue));
  }

  uint32_t VideoStabilizationMaximumBufferLength() {
    return PROPERTY_MAX_VSBUFFER;
  }

 private:
  static constexpr MediaStreamType DefaultStreamType = MediaStreamType::VideoRecord;
  static constexpr bool DefaultHologramCompositionEnabled = true;
  static constexpr bool DefaultRecordingIndicatorEnabled = true;
  static constexpr bool DefaultVideoStabilizationEnabled = false;
  static constexpr uint32_t DefaultVideoStabilizationBufferLength = 0U;
  static constexpr float DefaultGlobalOpacityCoefficient = 0.9f;

 private:
  winrt::hstring m_activatableClassId{
      RUNTIMECLASS_MIXEDREALITYCAPTURE_VIDEO_EFFECT};
  winrt::Windows::Foundation::Collections::PropertySet m_propertySet;
};

}  // namespace webrtc

#endif