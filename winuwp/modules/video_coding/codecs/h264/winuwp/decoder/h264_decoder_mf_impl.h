/*
 *  Copyright (c) 2015 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef MODULES_VIDEO_CODING_CODECS_H264_WIN_ENCODER_H264_DECODER_MF_IMPL_H_
#define MODULES_VIDEO_CODING_CODECS_H264_WIN_ENCODER_H264_DECODER_MF_IMPL_H_

#include <mfapi.h>
#include <mferror.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <wrl.h>
#include "../utils/sample_attribute_queue.h"
#include "api/video_codecs/video_decoder.h"
#include "common_video/include/video_frame_buffer_pool.h"
#include "modules/video_coding/codecs/h264/include/h264.h"
#include "rtc_base/synchronization/mutex.h"

namespace webrtc {

class H264DecoderMFImpl : public H264Decoder {
 public:
  H264DecoderMFImpl();

  virtual ~H264DecoderMFImpl();

  bool Configure(const Settings& settings) override;

  int Decode(const EncodedImage& input_image,
             bool missing_frames,
             int64_t /*render_time_ms*/) override;

  int RegisterDecodeCompleteCallback(DecodedImageCallback* callback) override;

  int Release() override;

  const char* ImplementationName() const override;

 private:
  HRESULT FlushFrames(uint32_t timestamp, uint64_t ntp_time_ms);
  HRESULT EnqueueFrame(const EncodedImage& input_image, bool missing_frames);

 private:
  Microsoft::WRL::ComPtr<IMFTransform> decoder_;
  VideoFrameBufferPool buffer_pool_;

  bool inited_ = false;
  bool require_keyframe_ = true;
  uint32_t first_frame_rtp_ = 0;
  std::optional<uint32_t> width_;
  std::optional<uint32_t> height_;
  webrtc::Mutex crit_;
  DecodedImageCallback* decode_complete_callback_;
};

}  // namespace webrtc

#endif  // MODULES_VIDEO_CODING_CODECS_H264_WIN_ENCODER_H264_DECODER_MF_IMPL_H_
