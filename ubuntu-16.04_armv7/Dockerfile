# syntax = docker/dockerfile:experimental
FROM ubuntu:16.04 AS builder

ARG PACKAGE_NAME=ubuntu-16.04_armv7

ENV SOURCE_DIR "/root/_source/$PACKAGE_NAME"
ENV BUILD_DIR "/root/_build/$PACKAGE_NAME"
ENV PACKAGE_DIR "/root/_package/$PACKAGE_NAME"

COPY scripts/apt_install_arm.sh /root/scripts/
RUN /root/scripts/apt_install_arm.sh

COPY scripts/init_rootfs_armhf.sh /root/scripts/
COPY $PACKAGE_NAME/armhf.conf /root/$PACKAGE_NAME/
RUN /root/scripts/init_rootfs_armhf.sh /root/rootfs /root/$PACKAGE_NAME/armhf.conf

COPY scripts/get_depot_tools.sh /root/scripts/
RUN /root/scripts/get_depot_tools.sh $SOURCE_DIR

ENV PATH "$SOURCE_DIR/depot_tools:$PATH"

ARG WEBRTC_COMMIT
COPY scripts/prepare_webrtc.sh /root/scripts/
RUN /root/scripts/prepare_webrtc.sh $SOURCE_DIR $WEBRTC_COMMIT

COPY scripts/install_webrtc_build_deps.sh /root/scripts/
RUN /root/scripts/install_webrtc_build_deps.sh $SOURCE_DIR arm

COPY patches/4k.patch /root/patches/
RUN cd $SOURCE_DIR/webrtc/src \
  && patch -p2 < /root/patches/4k.patch

RUN cd $SOURCE_DIR/webrtc/src \
  && gn gen $BUILD_DIR/webrtc --args=' \
    target_os="linux" \
    target_cpu="arm" \
    is_debug=false \
    target_sysroot="/root/rootfs" \
    rtc_use_h264=false \
    rtc_include_tests=false \
    use_rtti=true \
    is_component_build=false \
    is_desktop_linux=false \
  ' \
  && ninja -C $BUILD_DIR/webrtc

RUN cd $BUILD_DIR/webrtc/obj \
  && $SOURCE_DIR/webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar -rc $BUILD_DIR/webrtc/libwebrtc.a `find . -name '*.o'`

COPY patches/ubuntu-16.04_nolibcxx.patch /root/patches/
RUN cd $SOURCE_DIR/webrtc/src \
  && patch -p2 < /root/patches/ubuntu-16.04_nolibcxx.patch

RUN cd $SOURCE_DIR/webrtc/src \
  && gn gen $BUILD_DIR/webrtc_nolibcxx --args=' \
    target_os="linux" \
    target_cpu="arm" \
    is_debug=false \
    target_sysroot="/root/rootfs" \
    rtc_use_h264=false \
    rtc_include_tests=false \
    use_rtti=true \
    is_component_build=false \
    is_desktop_linux=false \
    use_custom_libcxx=false \
    use_custom_libcxx_for_host=false \
  ' \
  && ninja -C $BUILD_DIR/webrtc_nolibcxx

RUN cd $BUILD_DIR/webrtc_nolibcxx/obj \
  && $SOURCE_DIR/webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar -rc $BUILD_DIR/webrtc_nolibcxx/libwebrtc.a `find . -name '*.o'`

ENV STATIC_DIR "/root/static"

COPY scripts/package_webrtc.sh /root/scripts/
COPY static/NOTICE /root/static/
COPY VERSION /root/
RUN /root/scripts/package_webrtc.sh $STATIC_DIR $SOURCE_DIR $BUILD_DIR $PACKAGE_DIR /root/VERSION nolibcxx

RUN mv $PACKAGE_DIR/webrtc.tar.gz /

FROM ubuntu:16.04

COPY --from=builder /webrtc.tar.gz /
