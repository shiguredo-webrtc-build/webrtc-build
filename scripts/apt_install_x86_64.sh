#!/bin/bash

set -ex

apt-get update
apt-get -y upgrade

# tzdata を noninteractive にしないと実行が止まってしまう
apt-get -y install tzdata
echo 'Asia/Tokyo' > /etc/timezone
dpkg-reconfigure -f noninteractive tzdata

export DEBIAN_FRONTEND=noninteractive

apt-get -y install \
  binutils \
  git \
  locales \
  lsb-release \
  ninja-build \
  pkg-config \
  python3 \
  python3-setuptools \
  rsync \
  sudo \
  unzip \
  vim \
  wget \
  xz-utils
