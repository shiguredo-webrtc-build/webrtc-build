#include "rtc_base/proxy_info_revive.h"

namespace rtc::revive {

const char* ProxyToString(ProxyType proxy) {
  const char* const PROXY_NAMES[] = {"none", "https", "socks5", "unknown"};
  return PROXY_NAMES[proxy];
}

ProxyInfo::ProxyInfo() : type(PROXY_NONE), autodetect(false) {}
ProxyInfo::~ProxyInfo() = default;

}
