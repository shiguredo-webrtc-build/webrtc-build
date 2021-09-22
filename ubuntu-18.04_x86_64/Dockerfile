# syntax = docker/dockerfile:experimental
FROM ubuntu:18.04 AS builder

ARG PACKAGE_NAME=ubuntu-18.04_x86_64

ENV SOURCE_DIR "/root/_source/$PACKAGE_NAME"
ENV BUILD_DIR "/root/_build/$PACKAGE_NAME"
ENV PACKAGE_DIR "/root/_package/$PACKAGE_NAME"

COPY scripts/apt_install_x86_64.sh /root/scripts/
RUN /root/scripts/apt_install_x86_64.sh

COPY scripts/get_depot_tools.sh /root/scripts/
RUN /root/scripts/get_depot_tools.sh $SOURCE_DIR

ENV PATH "$SOURCE_DIR/depot_tools:$PATH"

ARG WEBRTC_COMMIT
COPY scripts/prepare_webrtc.sh /root/scripts/
RUN /root/scripts/prepare_webrtc.sh $SOURCE_DIR $WEBRTC_COMMIT

COPY scripts/install_webrtc_build_deps.sh /root/scripts/
RUN /root/scripts/install_webrtc_build_deps.sh $SOURCE_DIR x86_64

COPY patches/4k.patch /root/patches/
COPY patches/libjpeg_turbo_mangle_jpeg_names.patch /root/patches/
RUN cd $SOURCE_DIR/webrtc/src \
  && patch -p2 < /root/patches/4k.patch \
  && cd $SOURCE_DIR/webrtc/src/third_party/libjpeg_turbo \
  && patch < /root/patches/libjpeg_turbo_mangle_jpeg_names.patch

RUN cd $SOURCE_DIR/webrtc/src \
  && gn gen $BUILD_DIR/webrtc --args=' \
    target_os="linux" \
    is_debug=false \
    rtc_include_tests=false \
    rtc_use_h264=false \
    rtc_use_pipewire=false \
    is_component_build=false \
    use_rtti=true \
  ' \
  && ninja -C $BUILD_DIR/webrtc

RUN cd $BUILD_DIR/webrtc/obj \
  && $SOURCE_DIR/webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar -rc $BUILD_DIR/webrtc/libwebrtc.a `find . -name '*.o'`

RUN cd $SOURCE_DIR/webrtc/src \
  && python2 tools_webrtc/libs/generate_licenses.py --target :webrtc $BUILD_DIR/webrtc/ $BUILD_DIR/webrtc/

ENV STATIC_DIR "/root/static"

COPY scripts/package_webrtc.sh /root/scripts/
COPY VERSION /root/
RUN /root/scripts/package_webrtc.sh $STATIC_DIR $SOURCE_DIR $BUILD_DIR $PACKAGE_DIR /root/VERSION

RUN mv $PACKAGE_DIR/webrtc.tar.gz /

FROM ubuntu:18.04

COPY --from=builder /webrtc.tar.gz /
