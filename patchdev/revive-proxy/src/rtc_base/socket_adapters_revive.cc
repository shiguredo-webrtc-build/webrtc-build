#include "rtc_base/socket_adapters_revive.h"

#include <algorithm>

#include "absl/strings/match.h"
#include "absl/strings/string_view.h"
#include "rtc_base/buffer.h"
#include "rtc_base/byte_buffer.h"
#include "rtc_base/checks.h"
#include "rtc_base/http_common_revive.h"
#include "rtc_base/logging.h"
#include "rtc_base/strings/string_builder.h"
#include "rtc_base/zero_memory.h"

namespace rtc::revive {

AsyncHttpsProxySocket::AsyncHttpsProxySocket(Socket* socket,
                                             absl::string_view user_agent,
                                             const SocketAddress& proxy,
                                             absl::string_view username,
                                             const CryptString& password)
    : BufferedReadAdapter(socket, 1024),
      proxy_(proxy),
      agent_(user_agent),
      user_(username),
      pass_(password),
      force_connect_(false),
      state_(PS_ERROR),
      context_(0) {}

AsyncHttpsProxySocket::~AsyncHttpsProxySocket() {
  delete context_;
}

int AsyncHttpsProxySocket::Connect(const SocketAddress& addr) {
  int ret;
  RTC_LOG(LS_VERBOSE) << "AsyncHttpsProxySocket::Connect("
                      << proxy_.ToSensitiveString() << ")";
  dest_ = addr;
  state_ = PS_INIT;
  if (ShouldIssueConnect()) {
    BufferInput(true);
  }
  ret = BufferedReadAdapter::Connect(proxy_);
  // TODO: Set state_ appropriately if Connect fails.
  return ret;
}

SocketAddress AsyncHttpsProxySocket::GetRemoteAddress() const {
  return dest_;
}

int AsyncHttpsProxySocket::Close() {
  headers_.clear();
  state_ = PS_ERROR;
  dest_.Clear();
  delete context_;
  context_ = nullptr;
  return BufferedReadAdapter::Close();
}

Socket::ConnState AsyncHttpsProxySocket::GetState() const {
  if (state_ < PS_TUNNEL) {
    return CS_CONNECTING;
  } else if (state_ == PS_TUNNEL) {
    return CS_CONNECTED;
  } else {
    return CS_CLOSED;
  }
}

void AsyncHttpsProxySocket::OnConnectEvent(Socket* socket) {
  RTC_LOG(LS_VERBOSE) << "AsyncHttpsProxySocket::OnConnectEvent";
  if (!ShouldIssueConnect()) {
    state_ = PS_TUNNEL;
    BufferedReadAdapter::OnConnectEvent(socket);
    return;
  }
  SendRequest();
}

void AsyncHttpsProxySocket::OnCloseEvent(Socket* socket, int err) {
  RTC_LOG(LS_VERBOSE) << "AsyncHttpsProxySocket::OnCloseEvent(" << err << ")";
  if ((state_ == PS_WAIT_CLOSE) && (err == 0)) {
    state_ = PS_ERROR;
    Connect(dest_);
  } else {
    BufferedReadAdapter::OnCloseEvent(socket, err);
  }
}

void AsyncHttpsProxySocket::ProcessInput(char* data, size_t* len) {
  size_t start = 0;
  for (size_t pos = start; state_ < PS_TUNNEL && pos < *len;) {
    if (state_ == PS_SKIP_BODY) {
      size_t consume = std::min(*len - pos, content_length_);
      pos += consume;
      start = pos;
      content_length_ -= consume;
      if (content_length_ == 0) {
        EndResponse();
      }
      continue;
    }

    if (data[pos++] != '\n')
      continue;

    size_t length = pos - start - 1;
    if ((length > 0) && (data[start + length - 1] == '\r'))
      --length;

    data[start + length] = 0;
    ProcessLine(data + start, length);
    start = pos;
  }

  *len -= start;
  if (*len > 0) {
    memmove(data, data + start, *len);
  }

  if (state_ != PS_TUNNEL)
    return;

  bool remainder = (*len > 0);
  BufferInput(false);
  SignalConnectEvent(this);

  // FIX: if SignalConnect causes the socket to be destroyed, we are in trouble
  if (remainder)
    SignalReadEvent(this);  // TODO: signal this??
}

bool AsyncHttpsProxySocket::ShouldIssueConnect() const {
  // TODO: Think about whether a more sophisticated test
  // than dest port == 80 is needed.
  return force_connect_ || (dest_.port() != 80);
}

void AsyncHttpsProxySocket::SendRequest() {
  rtc::StringBuilder ss;
  ss << "CONNECT " << dest_.ToString() << " HTTP/1.0\r\n";
  ss << "User-Agent: " << agent_ << "\r\n";
  ss << "Host: " << dest_.HostAsURIString() << "\r\n";
  ss << "Content-Length: 0\r\n";
  ss << "Proxy-Connection: Keep-Alive\r\n";
  ss << headers_;
  ss << "\r\n";
  std::string str = ss.str();
  DirectSend(str.c_str(), str.size());
  state_ = PS_LEADER;
  expect_close_ = true;
  content_length_ = 0;
  headers_.clear();

  RTC_LOG(LS_VERBOSE) << "AsyncHttpsProxySocket >> " << str;
}

void AsyncHttpsProxySocket::ProcessLine(char* data, size_t len) {
  RTC_LOG(LS_VERBOSE) << "AsyncHttpsProxySocket << " << data;

  if (len == 0) {
    if (state_ == PS_TUNNEL_HEADERS) {
      state_ = PS_TUNNEL;
    } else if (state_ == PS_ERROR_HEADERS) {
      Error(defer_error_);
      return;
    } else if (state_ == PS_SKIP_HEADERS) {
      if (content_length_) {
        state_ = PS_SKIP_BODY;
      } else {
        EndResponse();
        return;
      }
    } else {
      if (!unknown_mechanisms_.empty()) {
        RTC_LOG(LS_ERROR) << "Unsupported authentication methods: "
                          << unknown_mechanisms_;
      }
      // Unexpected end of headers
      Error(0);
      return;
    }
  } else if (state_ == PS_LEADER) {
    unsigned int code;
    if (sscanf(data, "HTTP/%*u.%*u %u", &code) != 1) {
      Error(0);
      return;
    }
    switch (code) {
      case 200:
        // connection good!
        state_ = PS_TUNNEL_HEADERS;
        return;
#if defined(HTTP_STATUS_PROXY_AUTH_REQ) && (HTTP_STATUS_PROXY_AUTH_REQ != 407)
#error Wrong code for HTTP_STATUS_PROXY_AUTH_REQ
#endif
      case 407:  // HTTP_STATUS_PROXY_AUTH_REQ
        state_ = PS_AUTHENTICATE;
        return;
      default:
        defer_error_ = 0;
        state_ = PS_ERROR_HEADERS;
        return;
    }
  } else if ((state_ == PS_AUTHENTICATE) &&
             absl::StartsWithIgnoreCase(data, "Proxy-Authenticate:")) {
    std::string response, auth_method;
    switch (HttpAuthenticate(absl::string_view(data + 19, len - 19), proxy_,
                             "CONNECT", "/", user_, pass_, context_, response,
                             auth_method)) {
      case HAR_IGNORE:
        RTC_LOG(LS_VERBOSE) << "Ignoring Proxy-Authenticate: " << auth_method;
        if (!unknown_mechanisms_.empty())
          unknown_mechanisms_.append(", ");
        unknown_mechanisms_.append(auth_method);
        break;
      case HAR_RESPONSE:
        headers_ = "Proxy-Authorization: ";
        headers_.append(response);
        headers_.append("\r\n");
        state_ = PS_SKIP_HEADERS;
        unknown_mechanisms_.clear();
        break;
      case HAR_CREDENTIALS:
        defer_error_ = SOCKET_EACCES;
        state_ = PS_ERROR_HEADERS;
        unknown_mechanisms_.clear();
        break;
      case HAR_ERROR:
        defer_error_ = 0;
        state_ = PS_ERROR_HEADERS;
        unknown_mechanisms_.clear();
        break;
    }
  } else if (absl::StartsWithIgnoreCase(data, "Content-Length:")) {
    content_length_ = strtoul(data + 15, 0, 0);
  } else if (absl::StartsWithIgnoreCase(data, "Proxy-Connection: Keep-Alive")) {
    expect_close_ = false;
    /*
  } else if (absl::StartsWithIgnoreCase(data, "Connection: close") {
    expect_close_ = true;
    */
  }
}

void AsyncHttpsProxySocket::EndResponse() {
  if (!expect_close_) {
    SendRequest();
    return;
  }

  // No point in waiting for the server to close... let's close now
  // TODO: Refactor out PS_WAIT_CLOSE
  state_ = PS_WAIT_CLOSE;
  BufferedReadAdapter::Close();
  OnCloseEvent(this, 0);
}

void AsyncHttpsProxySocket::Error(int error) {
  BufferInput(false);
  Close();
  SetError(error);
  SignalCloseEvent(this, error);
}

}  // namespace rtc::revive
