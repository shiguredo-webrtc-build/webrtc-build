#!/bin/bash

apt-get update
apt-get -y upgrade

# Ubuntu 18.04 では tzdata を noninteractive にしないと実行が止まってしまう
apt-get -y install tzdata
echo 'Asia/Tokyo' > /etc/timezone
dpkg-reconfigure -f noninteractive tzdata

apt-get -y install \
  git \
  libsdl2-dev \
  lsb-release \
  python \
  rsync \
  sudo \
  vim \
  wget
