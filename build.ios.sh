#!/bin/bash

set -ex
cd `dirname $0`
python3 run.py build ios
python3 run.py package ios
