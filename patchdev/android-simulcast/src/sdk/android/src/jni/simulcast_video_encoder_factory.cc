#include <jni.h>

#include "sdk/android/src/jni/jni_helpers.h"
#include "sdk/android/src/jni/video_encoder_factory_wrapper.h"
#include "sdk/android/src/jni/video_codec_info.h"
#include "sdk/android/native_api/codecs/wrapper.h"
#include "sdk/android/native_api/jni/class_loader.h"
#include "modules/video_coding/codecs/av1/av1_svc_config.h"
#include "modules/video_coding/codecs/vp9/include/vp9.h"
#include "media/base/media_constants.h"
#include "media/engine/simulcast_encoder_adapter.h"
#include "absl/container/inlined_vector.h"
#include "api/video_codecs/video_codec.h"
#include "api/video_codecs/sdp_video_format.h"
#include "api/video_codecs/video_codec.h"

using namespace webrtc;
using namespace webrtc::jni;

#ifdef __cplusplus
extern "C" {
#endif

JNIEXPORT jobject JNICALL Java_org_webrtc_SimulcastVideoEncoderFactory_nativeVP9Codecs
  (JNIEnv *env, jclass klass) {
    std::vector<SdpVideoFormat> formats = SupportedVP9Codecs(true);
    return NativeToJavaList(env, formats, &SdpVideoFormatToVideoCodecInfo).Release();
}

JNIEXPORT jobject JNICALL Java_org_webrtc_SimulcastVideoEncoderFactory_nativeAV1Codec
  (JNIEnv *env, jclass klass) {
    SdpVideoFormat format = SdpVideoFormat(
        cricket::kAv1CodecName, SdpVideoFormat::Parameters(),
        LibaomAv1EncoderSupportedScalabilityModes());
    return SdpVideoFormatToVideoCodecInfo(env, format).Release();
}

#ifdef __cplusplus
}
#endif
