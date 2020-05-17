#!/bin/bash

cd `dirname $0`
source VERSION
SCRIPT_DIR="`pwd`"

PACKAGE_NAME=android
SOURCE_DIR="`pwd`/_source/$PACKAGE_NAME"
BUILD_DIR="`pwd`/_build/$PACKAGE_NAME"
PACKAGE_DIR="`pwd`/_package/$PACKAGE_NAME"

set -ex

# ======= ここまでは全ての build.*.sh で共通（PACKAGE_NAME だけ変える）

_name=WebrtcBuildVersion
_branch="M`echo $WEBRTC_VERSION | cut -d'.' -f1`"
_commit="`echo $WEBRTC_VERSION | cut -d'.' -f3`"
_revision=$WEBRTC_COMMIT
_maint="`echo $WEBRTC_BUILD_VERSION | cut -d'.' -f4`"
./scripts/generate_version_android.sh "$_name" "$_branch" "$_commit" "$_revision" "$_maint" > android/$_name.java
cat android/$_name.java

IMAGE_NAME=webrtc/$PACKAGE_NAME:m${WEBRTC_VERSION}
DOCKER_BUILDKIT=1 docker build \
  -t $IMAGE_NAME \
  --build-arg WEBRTC_COMMIT=$WEBRTC_COMMIT \
  -f $PACKAGE_NAME/Dockerfile \
  .

rm android/WebrtcBuildVersion.java

mkdir -p $PACKAGE_DIR
CONTAINER_ID=`docker container create $IMAGE_NAME`
docker container cp $CONTAINER_ID:/webrtc.tar.gz $PACKAGE_DIR/webrtc.tar.gz
docker container rm $CONTAINER_ID
