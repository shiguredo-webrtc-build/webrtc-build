# パッチ解説

## 4k.patch


## add_dep_zlib.patch


## android_fixsegv.patch


## android_onremovetrack.patch


## android_simulcast.patch


## android_webrtc_version.patch


## ios_manual_audio_input.patch


## ios_simulcast.patch


## macos_av1.patch


## macos_h264_encoder.patch


## macos_screen_capture.patch


## macos_simulcast.patch


## macos_statistics.patch


## nacl_armv6_2.patch

## libjpeg_turbo_mangle_jpeg_names.patch

libwebrtc (chromium) には、利用している libjpeg がシステムの libjpeg と混ざることを防ぐ仕組みがあるが、それが M93 から壊れている。  
結果、 momo の一部の機能が正常に動作しなくなったため、パッチを当てて壊れる前の状態にしている。

libjpeg が混ざることを防ぐ仕組みの解説 https://source.chromium.org/chromium/chromium/src/+/master:third_party/libjpeg_turbo/README.chromium;l=30-34;drc=ff19e5b2e176c61d552f68768e0e051867745321  
問題の原因と思われる変更 https://chromium-review.googlesource.com/c/chromium/deps/libjpeg_turbo/+/2872069  
本家のイシューに報告済み https://bugs.chromium.org/p/webrtc/issues/detail?id=13101  

## ubuntu_nolibcxx.patch


## windows_add_deps.patch


