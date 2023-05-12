/*
 *  Copyright 2017 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#import <Foundation/Foundation.h>

#import "RTCMacros.h"

NS_ASSUME_NONNULL_BEGIN

typedef NS_ENUM(uint8_t, RTCScalabilityMode) {
  RTCScalabilityModeL1T1,
  RTCScalabilityModeL1T2,
  RTCScalabilityModeL1T3,
  RTCScalabilityModeL2T1,
  RTCScalabilityModeL2T1h,
  RTCScalabilityModeL2T1_KEY,
  RTCScalabilityModeL2T2,
  RTCScalabilityModeL2T2h,
  RTCScalabilityModeL2T2_KEY,
  RTCScalabilityModeL2T2_KEY_SHIFT,
  RTCScalabilityModeL2T3,
  RTCScalabilityModeL2T3h,
  RTCScalabilityModeL2T3_KEY,
  RTCScalabilityModeL3T1,
  RTCScalabilityModeL3T1h,
  RTCScalabilityModeL3T1_KEY,
  RTCScalabilityModeL3T2,
  RTCScalabilityModeL3T2h,
  RTCScalabilityModeL3T2_KEY,
  RTCScalabilityModeL3T3,
  RTCScalabilityModeL3T3h,
  RTCScalabilityModeL3T3_KEY,
  RTCScalabilityModeS2T1,
  RTCScalabilityModeS2T1h,
  RTCScalabilityModeS2T2,
  RTCScalabilityModeS2T2h,
  RTCScalabilityModeS2T3,
  RTCScalabilityModeS2T3h,
  RTCScalabilityModeS3T1,
  RTCScalabilityModeS3T1h,
  RTCScalabilityModeS3T2,
  RTCScalabilityModeS3T2h,
  RTCScalabilityModeS3T3,
  RTCScalabilityModeS3T3h,
};

/** Holds information to identify a codec. Corresponds to webrtc::SdpVideoFormat. */
RTC_OBJC_EXPORT
@interface RTC_OBJC_TYPE (RTCVideoCodecInfo) : NSObject <NSCoding>

- (instancetype)init NS_UNAVAILABLE;

- (instancetype)initWithName:(NSString *)name;

- (instancetype)initWithName:(NSString *)name
                  parameters:(nullable NSDictionary<NSString *, NSString *> *)parameters;
- (instancetype)initWithName:(NSString *)name
                  parameters:(nullable NSDictionary<NSString *, NSString *> *)parameters
            scalabilityModes:(nullable NSArray<NSNumber *> *)scalabilityModes
    NS_DESIGNATED_INITIALIZER;

- (BOOL)isEqualToCodecInfo:(RTC_OBJC_TYPE(RTCVideoCodecInfo) *)info;

@property(nonatomic, readonly) NSString *name;
@property(nonatomic, readonly) NSDictionary<NSString *, NSString *> *parameters;
@property(nonatomic, readonly) NSArray<NSNumber *> *scalabilityModes;

@end

NS_ASSUME_NONNULL_END
