/*
 *  Copyright 2004 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef RTC_BASE_SOCKET_ADAPTERS_REVIVE_H_
#define RTC_BASE_SOCKET_ADAPTERS_REVIVE_H_

#include <string>

#include "rtc_base/async_socket.h"
#include "rtc_base/crypt_string.h"
#include "rtc_base/socket_adapters.h"
#include "rtc_base/socket_address.h"

namespace rtc::revive {

struct HttpAuthContext;

// Implements a socket adapter that speaks the HTTP/S proxy protocol.
class AsyncHttpsProxySocket : public BufferedReadAdapter {
 public:
  AsyncHttpsProxySocket(Socket* socket,
                        absl::string_view user_agent,
                        const SocketAddress& proxy,
                        absl::string_view username,
                        const CryptString& password);
  ~AsyncHttpsProxySocket() override;

  AsyncHttpsProxySocket(const AsyncHttpsProxySocket&) = delete;
  AsyncHttpsProxySocket& operator=(const AsyncHttpsProxySocket&) = delete;

  // If connect is forced, the adapter will always issue an HTTP CONNECT to the
  // target address.  Otherwise, it will connect only if the destination port
  // is not port 80.
  void SetForceConnect(bool force) { force_connect_ = force; }

  int Connect(const SocketAddress& addr) override;
  SocketAddress GetRemoteAddress() const override;
  int Close() override;
  ConnState GetState() const override;

 protected:
  void OnConnectEvent(Socket* socket) override;
  void OnCloseEvent(Socket* socket, int err) override;
  void ProcessInput(char* data, size_t* len) override;

  bool ShouldIssueConnect() const;
  void SendRequest();
  void ProcessLine(char* data, size_t len);
  void EndResponse();
  void Error(int error);

 private:
  SocketAddress proxy_, dest_;
  std::string agent_, user_, headers_;
  CryptString pass_;
  bool force_connect_;
  size_t content_length_;
  int defer_error_;
  bool expect_close_;
  enum ProxyState {
    PS_INIT,
    PS_LEADER,
    PS_AUTHENTICATE,
    PS_SKIP_HEADERS,
    PS_ERROR_HEADERS,
    PS_TUNNEL_HEADERS,
    PS_SKIP_BODY,
    PS_TUNNEL,
    PS_WAIT_CLOSE,
    PS_ERROR
  } state_;
  HttpAuthContext* context_;
  std::string unknown_mechanisms_;
};

}  // namespace rtc::revive

#endif
