# syntax = docker/dockerfile:experimental
FROM ubuntu:18.04 AS builder

ARG PACKAGE_NAME=raspberry-pi-os_armv6

ENV SOURCE_DIR "/root/_source/$PACKAGE_NAME"
ENV BUILD_DIR "/root/_build/$PACKAGE_NAME"
ENV PACKAGE_DIR "/root/_package/$PACKAGE_NAME"

COPY scripts/apt_install_arm.sh /root/scripts/
RUN /root/scripts/apt_install_arm.sh

COPY scripts/init_rootfs_armhf.sh /root/scripts/
COPY $PACKAGE_NAME/rpi-raspbian.conf /root/$PACKAGE_NAME/
RUN /root/scripts/init_rootfs_armhf.sh /root/rootfs /root/$PACKAGE_NAME/rpi-raspbian.conf

COPY scripts/get_depot_tools.sh /root/scripts/
RUN /root/scripts/get_depot_tools.sh $SOURCE_DIR

ENV PATH "$SOURCE_DIR/depot_tools:$PATH"

ARG WEBRTC_COMMIT
COPY scripts/prepare_webrtc.sh /root/scripts/
RUN /root/scripts/prepare_webrtc.sh $SOURCE_DIR $WEBRTC_COMMIT

COPY scripts/install_webrtc_build_deps.sh /root/scripts/
RUN /root/scripts/install_webrtc_build_deps.sh $SOURCE_DIR arm

COPY patches/nacl_armv6_2.patch /root/patches/
COPY patches/add_dep_zlib.patch /root/patches/
COPY patches/4k.patch /root/patches/
COPY patches/ssl_verify_callback_with_native_handle.patch /root/patches/
COPY patches/libjpeg_turbo_mangle_jpeg_names.patch /root/patches/
RUN cd $SOURCE_DIR/webrtc/src \
  && patch -p1 < /root/patches/nacl_armv6_2.patch \
  && patch -p1 < /root/patches/add_dep_zlib.patch \
  && patch -p2 < /root/patches/4k.patch \
  && patch -p1 < /root/patches/ssl_verify_callback_with_native_handle.patch \
  && cd $SOURCE_DIR/webrtc/src/third_party/libjpeg_turbo \
  && patch < /root/patches/libjpeg_turbo_mangle_jpeg_names.patch

RUN cd $SOURCE_DIR/webrtc/src \
  && gn gen $BUILD_DIR/webrtc --args=' \
    target_os="linux" \
    target_cpu="arm" \
    is_debug=false \
    target_sysroot="/root/rootfs" \
    rtc_use_h264=false \
    rtc_include_tests=false \
    arm_version=6 \
    arm_arch="armv6" \
    arm_tune="arm1176jzf-s" \
    arm_fpu="vfpv2" \
    arm_float_abi="hard" \
    arm_use_neon=false \
    rtc_use_pipewire=false \
    rtc_build_json=true \
    use_rtti=true \
    enable_libaom=false \
    enable_libaom_decoder=false \
  ' \
  && ninja -C $BUILD_DIR/webrtc

RUN cd $BUILD_DIR/webrtc/obj \
  && $SOURCE_DIR/webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar -rc $BUILD_DIR/webrtc/libwebrtc.a `find . -name '*.o'`

# ライセンスを生成するんだけど、ビルドによっては enable_libaom=false あるいは enable_libaom_decoder=false で
# 警告が出てきて実行に失敗してしまうので、そうなった場合は GN で生成し直して再度実行する
RUN cd $SOURCE_DIR/webrtc/src \
  && python2 tools_webrtc/libs/generate_licenses.py --target :webrtc $BUILD_DIR/webrtc/ $BUILD_DIR/webrtc/ \
  || gn gen $BUILD_DIR/webrtc --args=' \
    target_os="linux" \
    target_cpu="arm" \
    is_debug=false \
    target_sysroot="/root/rootfs" \
    rtc_use_h264=false \
    rtc_include_tests=false \
    arm_version=6 \
    arm_arch="armv6" \
    arm_tune="arm1176jzf-s" \
    arm_fpu="vfpv2" \
    arm_float_abi="hard" \
    arm_use_neon=false \
    rtc_use_pipewire=false \
    rtc_build_json=true \
    use_rtti=true \
    enable_libaom_decoder=false \
  ' \
  && python2 tools_webrtc/libs/generate_licenses.py --target :webrtc $BUILD_DIR/webrtc/ $BUILD_DIR/webrtc/ \
  || gn gen $BUILD_DIR/webrtc --args=' \
    target_os="linux" \
    target_cpu="arm" \
    is_debug=false \
    target_sysroot="/root/rootfs" \
    rtc_use_h264=false \
    rtc_include_tests=false \
    arm_version=6 \
    arm_arch="armv6" \
    arm_tune="arm1176jzf-s" \
    arm_fpu="vfpv2" \
    arm_float_abi="hard" \
    arm_use_neon=false \
    rtc_use_pipewire=false \
    rtc_build_json=true \
    use_rtti=true \
    enable_libaom=false \
  ' \
  && python2 tools_webrtc/libs/generate_licenses.py --target :webrtc $BUILD_DIR/webrtc/ $BUILD_DIR/webrtc/ \
  || gn gen $BUILD_DIR/webrtc --args=' \
    target_os="linux" \
    target_cpu="arm" \
    is_debug=false \
    target_sysroot="/root/rootfs" \
    rtc_use_h264=false \
    rtc_include_tests=false \
    arm_version=6 \
    arm_arch="armv6" \
    arm_tune="arm1176jzf-s" \
    arm_fpu="vfpv2" \
    arm_float_abi="hard" \
    arm_use_neon=false \
    rtc_use_pipewire=false \
    rtc_build_json=true \
    use_rtti=true \
  ' \
  && python2 tools_webrtc/libs/generate_licenses.py --target :webrtc $BUILD_DIR/webrtc/ $BUILD_DIR/webrtc/

ENV STATIC_DIR "/root/static"

COPY scripts/package_webrtc.sh /root/scripts/
COPY VERSION /root/
RUN /root/scripts/package_webrtc.sh $STATIC_DIR $SOURCE_DIR $BUILD_DIR $PACKAGE_DIR /root/VERSION

RUN mv $PACKAGE_DIR/webrtc.tar.gz /

FROM ubuntu:18.04

COPY --from=builder /webrtc.tar.gz /
