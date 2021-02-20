#!/bin/bash

set -ex

SYSDIR=/root/rootfs

ln -sf ../../../lib/aarch64-linux-gnu/libdl.so.2 $SYSDIR/usr/lib/aarch64-linux-gnu/libdl.so
ln -s libnvbuf_fdmap.so.1.0.0 $SYSDIR/usr/lib/aarch64-linux-gnu/tegra/libnvbuf_fdmap.so
