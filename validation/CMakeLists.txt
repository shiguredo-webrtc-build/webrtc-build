cmake_minimum_required(VERSION 3.16)

set(CMAKE_C_COMPILER ${WEBRTC_SOURCE_DIR}/third_party/llvm-build/Release+Asserts/bin/clang)
set(CMAKE_CXX_COMPILER ${WEBRTC_SOURCE_DIR}/third_party/llvm-build/Release+Asserts/bin/clang++)

project(validation C CXX)

find_package(Threads REQUIRED)

find_library(Blend2D_LIBRARY NAMES blend2d PATHS ${BLEND2D_ROOT_DIR}/lib)

add_executable(offer)
set_target_properties(offer PROPERTIES CXX_STANDARD 20 C_STANDARD 20)
target_include_directories(offer
  PRIVATE
    ${WEBRTC_SOURCE_DIR}
    ${WEBRTC_SOURCE_DIR}/third_party/abseil-cpp
    ${WEBRTC_SOURCE_DIR}/third_party/boringssl/src/include
    ${WEBRTC_SOURCE_DIR}/third_party/libyuv/include
    ${WEBRTC_SOURCE_DIR}/third_party/zlib
    ${WEBRTC_SOURCE_DIR}/buildtools/third_party/libc++
)
target_link_directories(offer PRIVATE ${WEBRTC_BUILD_DIR})
target_link_libraries(offer PRIVATE webrtc X11 dl rt Threads::Threads)
target_sources(offer
  PRIVATE
    offer.cpp
    internal_encoder_factory.cc
    internal_decoder_factory.cc
    fake_video_capturer.cpp
)
target_compile_definitions(offer PRIVATE BL_STATIC=1)
target_include_directories(offer PRIVATE ${BLEND2D_ROOT_DIR}/include)
target_link_libraries(offer PRIVATE ${Blend2D_LIBRARY})

target_compile_options(offer
  PRIVATE
    "$<$<COMPILE_LANGUAGE:CXX>:-nostdinc++>"
    "$<$<COMPILE_LANGUAGE:CXX>:-isystem${WEBRTC_LIBCXX_DIR}/include>"
)

target_compile_definitions(offer
  PRIVATE
    WEBRTC_POSIX
    WEBRTC_LINUX
    _LIBCPP_ABI_NAMESPACE=Cr
    _LIBCPP_ABI_VERSION=2
    _LIBCPP_DISABLE_AVAILABILITY
    _LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE
    RTC_ENABLE_H265
)
