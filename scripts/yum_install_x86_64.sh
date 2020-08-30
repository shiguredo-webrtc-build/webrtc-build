#!/bin/bash

yum -y update

yum -y install \
  git \
  patch \
  python3 \
  rsync \
  sudo \
  vim \
  wget

alternatives --set python /usr/bin/python3
