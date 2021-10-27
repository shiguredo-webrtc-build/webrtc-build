#!/bin/bash

set -ex
cd `dirname $0`
python3 run.py build ios --webrtc-overlap-ios-build-dir
python3 run.py package ios --webrtc-overlap-ios-build-dir
