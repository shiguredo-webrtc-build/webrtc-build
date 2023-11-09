#include <jni.h>

#include "api/transport/field_trial_based_config.h"
#include "sdk/android/src/jni/jni_helpers.h"
#include "sdk/android/src/jni/video_encoder_factory_wrapper.h"
#include "sdk/android/src/jni/video_codec_info.h"
#include "sdk/android/native_api/codecs/wrapper.h"
#include "media/engine/simulcast_encoder_adapter.h"
#include "rtc_base/logging.h"

using namespace webrtc;
using namespace webrtc::jni;

#ifdef __cplusplus
extern "C" {
#endif

// primary, fallback のライフタイムを管理するためのラッパー
class SimulcastEncoderAdapterWrapper : public VideoEncoder {
public:
    SimulcastEncoderAdapterWrapper(JNIEnv *env,
                            std::unique_ptr<VideoEncoderFactory> primary,
                            std::unique_ptr<VideoEncoderFactory> fallback,
                            const SdpVideoFormat& format,
                            const FieldTrialsView& field_trials) : primary_(std::move(primary)), fallback_(std::move(fallback)) {
        adapter_ = std::make_unique<SimulcastEncoderAdapter>(primary_.get(), fallback_.get(), format, field_trials);
    }

    int Encode(
        const VideoFrame& input_image,
        const std::vector<VideoFrameType>* frame_types) override {
            return adapter_.get()->Encode(input_image, frame_types);
    }

    int RegisterEncodeCompleteCallback(
        EncodedImageCallback* callback) override {
            return adapter_.get()->RegisterEncodeCompleteCallback(callback);
    }

    int32_t Release() override {
        return adapter_.get()->Release();
    }

    void SetRates(const RateControlParameters& parameters) override {
        adapter_.get()->SetRates(parameters);
    }

    EncoderInfo GetEncoderInfo() const override {
        return adapter_.get()->GetEncoderInfo();
    }

private:
    std::unique_ptr<SimulcastEncoderAdapter> adapter_;
    std::unique_ptr<VideoEncoderFactory> primary_;
    std::unique_ptr<VideoEncoderFactory> fallback_;
};

// (VideoEncoderFactory primary, VideoEncoderFactory fallback, VideoCodecInfo info)
JNIEXPORT jlong JNICALL Java_org_webrtc_SimulcastVideoEncoder_nativeCreateEncoder(JNIEnv *env, jclass klass, jobject primary, jobject fallback, jobject info) {
    RTC_LOG(LS_INFO) << "Create simulcast video encoder";
    JavaParamRef<jobject> info_ref(info);
    SdpVideoFormat format = VideoCodecInfoToSdpVideoFormat(env, info_ref);
    auto field_trials = webrtc::FieldTrialBasedConfig();

    return NativeToJavaPointer(std::make_unique<SimulcastEncoderAdapterWrapper>(
                            env,
                            JavaToNativeVideoEncoderFactory(env, primary),
                            fallback != nullptr ? JavaToNativeVideoEncoderFactory(env, fallback) : nullptr,
                            format,
                            field_trials).release());
}


#ifdef __cplusplus
}
#endif
