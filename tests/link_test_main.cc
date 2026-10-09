// テストの実行ファイルの main。テストの本体は link_test.cc の webrtc_link_test_main にある。

extern "C" int webrtc_link_test_main();

int main() {
  return webrtc_link_test_main();
}
