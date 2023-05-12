/*
 *  Copyright 2017 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#import "RTCVideoCodecInfo+Private.h"

#import "helpers/NSString+StdString.h"

@implementation RTC_OBJC_TYPE (RTCVideoCodecInfo)
(Private)

- (instancetype)initWithNativeSdpVideoFormat : (webrtc::SdpVideoFormat)format {
  NSMutableDictionary *params = [NSMutableDictionary dictionary];
  for (auto it = format.parameters.begin(); it != format.parameters.end(); ++it) {
    [params setObject:[NSString stringForStdString:it->second]
               forKey:[NSString stringForStdString:it->first]];
  }

  NSMutableArray *scalabilityModes = [[NSMutableArray alloc] init];
  if (!format.scalability_modes.empty()) {
    for (const auto scalability_mode : format.scalability_modes) {
      uint8_t value = static_cast<uint8_t>(scalability_mode);
      [scalabilityModes addObject: [NSNumber numberWithUnsignedInt:value]];
    }
  }

  return [self initWithName:[NSString stringForStdString:format.name]
                 parameters:params
           scalabilityModes:scalabilityModes];
}

- (webrtc::SdpVideoFormat)nativeSdpVideoFormat {
  std::map<std::string, std::string> parameters;
  for (NSString *paramKey in self.parameters.allKeys) {
    std::string key = [NSString stdStringForString:paramKey];
    std::string value = [NSString stdStringForString:self.parameters[paramKey]];
    parameters[key] = value;
  }

  absl::InlinedVector<webrtc::ScalabilityMode, webrtc::kScalabilityModeCount> scalabilityModes;
  for (NSNumber *scalabilityMode in self.scalabilityModes) {
    unsigned int value = [scalabilityMode unsignedIntValue];
    scalabilityModes.push_back(static_cast<webrtc::ScalabilityMode>(value));
  }

  return webrtc::SdpVideoFormat([NSString stdStringForString:self.name], parameters, scalabilityModes);
}

@end
