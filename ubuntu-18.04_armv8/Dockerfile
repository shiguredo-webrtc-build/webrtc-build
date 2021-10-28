# syntax = docker/dockerfile:experimental
FROM ubuntu:20.04 AS builder

ARG PACKAGE_NAME=ubuntu-18.04_armv8

ENV PACKAGE_DIR "/root/_package/$PACKAGE_NAME"

COPY run.py /root/
COPY VERSION /root/
COPY patches/ /root/patches/
COPY scripts/ /root/scripts/
COPY $PACKAGE_NAME/ /root/$PACKAGE_NAME/
RUN /root/scripts/apt_install_arm.sh
ENV LC_ALL=C.UTF-8
RUN cd /root && python3 run.py build $PACKAGE_NAME
RUN cd /root && python3 run.py package $PACKAGE_NAME
RUN mv $PACKAGE_DIR/webrtc.tar.gz /

FROM ubuntu:20.04

COPY --from=builder /webrtc.tar.gz /