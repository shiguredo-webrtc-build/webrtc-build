#!/bin/bash

cd `dirname $0`
source VERSION
SCRIPT_DIR="`pwd`"

PACKAGE_NAME=ubuntu-18.04_armv8_jetson_nano
SOURCE_DIR="`pwd`/_source/$PACKAGE_NAME"
BUILD_DIR="`pwd`/_build/$PACKAGE_NAME"
PACKAGE_DIR="`pwd`/_package/$PACKAGE_NAME"

set -ex

# ======= ここまでは全ての build.*.sh で共通（PACKAGE_NAME だけ変える）

IMAGE_NAME=webrtc/$PACKAGE_NAME:m${WEBRTC_VERSION}
DOCKER_BUILDKIT=1 docker build \
  -t $IMAGE_NAME \
  --build-arg WEBRTC_COMMIT=$WEBRTC_COMMIT \
  -f $PACKAGE_NAME/Dockerfile \
  .

mkdir -p $PACKAGE_DIR
CONTAINER_ID=`docker container create $IMAGE_NAME`
docker container cp $CONTAINER_ID:/webrtc.tar.gz $PACKAGE_DIR/webrtc.tar.gz
docker container rm $CONTAINER_ID
