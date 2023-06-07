/*
 *  Copyright 2017 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "sdk/android/src/jni/video_codec_info.h"

#include "sdk/android/generated_video_jni/VideoCodecInfo_jni.h"
#include "sdk/android/native_api/jni/java_types.h"
#include "sdk/android/src/jni/jni_helpers.h"

#include "absl/container/inlined_vector.h"

namespace webrtc {
namespace jni {

SdpVideoFormat VideoCodecInfoToSdpVideoFormat(JNIEnv* jni,
                                              const JavaRef<jobject>& j_info) {
  absl::InlinedVector<webrtc::ScalabilityMode, webrtc::kScalabilityModeCount> scalabilityModes;
  std::vector<int32_t> javaScalabilityModes = JavaToNativeIntArray(jni, Java_VideoCodecInfo_getScalabilityModes(jni, j_info));
  for (const auto& scalabilityMode : javaScalabilityModes) {
    scalabilityModes.push_back(static_cast<webrtc::ScalabilityMode>(scalabilityMode));
  }
  return SdpVideoFormat(
      JavaToNativeString(jni, Java_VideoCodecInfo_getName(jni, j_info)),
      JavaToNativeStringMap(jni, Java_VideoCodecInfo_getParams(jni, j_info)),
      scalabilityModes);
}

ScopedJavaLocalRef<jobject> SdpVideoFormatToVideoCodecInfo(
    JNIEnv* jni,
    const SdpVideoFormat& format) {
  ScopedJavaLocalRef<jobject> j_params =
      NativeToJavaStringMap(jni, format.parameters);

  ScopedJavaLocalRef<jobject> codec = Java_VideoCodecInfo_Constructor(
      jni, NativeToJavaString(jni, format.name), j_params);

  size_t size = format.scalability_modes.size();
  std::vector<int32_t> temp(size);
  for (size_t i = 0; i < size; i++) {
    temp[i] = static_cast<jint>(format.scalability_modes[i]);
  }
  Java_VideoCodecInfo_setScalabilityModes(jni, codec, NativeToJavaIntArray(jni, temp));

  return codec;
}

}  // namespace jni
}  // namespace webrtc
