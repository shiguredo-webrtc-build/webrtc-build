#include <future>

// WebRTC
#include <absl/memory/memory.h>
#include <api/audio_codecs/builtin_audio_decoder_factory.h>
#include <api/audio_codecs/builtin_audio_encoder_factory.h>
#include <api/create_peerconnection_factory.h>
#include <api/enable_media.h>
#include <api/make_ref_counted.h>
#include <api/peer_connection_interface.h>
#include <api/rtc_event_log/rtc_event_log_factory.h>
#include <api/scoped_refptr.h>
#include <api/task_queue/default_task_queue_factory.h>
#include <api/video_codecs/builtin_video_decoder_factory.h>
#include <api/video_codecs/builtin_video_encoder_factory.h>
#include <media/engine/internal_decoder_factory.h>
#include <media/engine/internal_encoder_factory.h>
#include <media/engine/simulcast_encoder_adapter.h>
#include <media/engine/webrtc_media_engine.h>
#include <modules/audio_device/include/audio_device.h>
#include <modules/audio_device/include/audio_device_factory.h>
#include <modules/audio_processing/include/audio_processing.h>
#include <modules/video_capture/video_capture.h>
#include <modules/video_capture/video_capture_factory.h>
#include <p2p/client/basic_port_allocator.h>
#include <pc/peer_connection_factory_proxy.h>
#include <pc/session_description.h>
#include <pc/video_track_source_proxy.h>
#include <rtc_base/crypto_random.h>
#include <rtc_base/logging.h>
#include <rtc_base/ref_counted_object.h>
#include <rtc_base/ssl_adapter.h>

#include "fake_video_capturer.h"

class CreateSessionDescriptionThunk
    : public webrtc::CreateSessionDescriptionObserver {
 public:
  static rtc::scoped_refptr<CreateSessionDescriptionThunk> Create(
      std::function<void(webrtc::SessionDescriptionInterface*)> on_success,
      std::function<void(webrtc::RTCError)> on_failure) {
    return rtc::make_ref_counted<CreateSessionDescriptionThunk>(
        std::move(on_success), std::move(on_failure));
  }

 protected:
  CreateSessionDescriptionThunk(
      std::function<void(webrtc::SessionDescriptionInterface*)> on_success,
      std::function<void(webrtc::RTCError)> on_failure)
      : on_success_(std::move(on_success)),
        on_failure_(std::move(on_failure)) {}
  void OnSuccess(webrtc::SessionDescriptionInterface* desc) override {
    auto f = std::move(on_success_);
    if (f) {
      f(desc);
    }
  }
  void OnFailure(webrtc::RTCError error) override {
    RTC_LOG(LS_ERROR) << "Failed to create session description : "
                      << webrtc::ToString(error.type()) << ": "
                      << error.message();
    auto f = std::move(on_failure_);
    if (f) {
      f(error);
    }
  }

 private:
  std::function<void(webrtc::SessionDescriptionInterface*)> on_success_;
  std::function<void(webrtc::RTCError)> on_failure_;
};

class SetLocalDescriptionThunk
    : public webrtc::SetLocalDescriptionObserverInterface {
 public:
  static rtc::scoped_refptr<SetLocalDescriptionThunk> Create(
      std::function<void(webrtc::RTCError)> on_complete) {
    return rtc::make_ref_counted<SetLocalDescriptionThunk>(
        std::move(on_complete));
  }

 protected:
  SetLocalDescriptionThunk(std::function<void(webrtc::RTCError)> on_complete)
      : on_complete_(std::move(on_complete)) {}
  void OnSetLocalDescriptionComplete(webrtc::RTCError error) override {
    auto f = std::move(on_complete_);
    if (f) {
      f(error);
    }
  }

 private:
  std::function<void(webrtc::RTCError)> on_complete_;
};

class SetRemoteDescriptionThunk
    : public webrtc::SetRemoteDescriptionObserverInterface {
 public:
  static rtc::scoped_refptr<SetRemoteDescriptionThunk> Create(
      std::function<void(webrtc::RTCError)> on_complete) {
    return rtc::make_ref_counted<SetRemoteDescriptionThunk>(
        std::move(on_complete));
  }

 protected:
  SetRemoteDescriptionThunk(std::function<void(webrtc::RTCError)> on_complete)
      : on_complete_(std::move(on_complete)) {}
  void OnSetRemoteDescriptionComplete(webrtc::RTCError error) override {
    auto f = std::move(on_complete_);
    if (f) {
      f(error);
    }
  }

 private:
  std::function<void(webrtc::RTCError)> on_complete_;
};

class PeerConnectionObserverThunk : public webrtc::PeerConnectionObserver {
 public:
  std::function<void(webrtc::PeerConnectionInterface::SignalingState)>
      on_signaling_change;
  std::function<void(rtc::scoped_refptr<webrtc::MediaStreamInterface>)>
      on_add_stream;
  std::function<void(rtc::scoped_refptr<webrtc::MediaStreamInterface>)>
      on_remove_stream;
  std::function<void(rtc::scoped_refptr<webrtc::DataChannelInterface>)>
      on_data_channel;
  std::function<void()> on_renegotiation_needed;
  std::function<void(uint32_t)> on_negotiation_needed_event;
  std::function<void(webrtc::PeerConnectionInterface::IceConnectionState)>
      on_ice_connection_change;
  std::function<void(webrtc::PeerConnectionInterface::IceConnectionState)>
      on_standardized_ice_connection_change;
  std::function<void(webrtc::PeerConnectionInterface::PeerConnectionState)>
      on_connection_change;
  std::function<void(webrtc::PeerConnectionInterface::IceGatheringState)>
      on_ice_gathering_change;
  std::function<void(const webrtc::IceCandidateInterface*)> on_ice_candidate;
  std::function<void(const std::string&,
                     int,
                     const std::string&,
                     int,
                     const std::string&)>
      on_ice_candidate_error;
  std::function<void(const std::vector<cricket::Candidate>&)>
      on_ice_candidates_removed;
  std::function<void(bool)> on_ice_connection_receiving_change;
  std::function<void(const cricket::CandidatePairChangeEvent&)>
      on_ice_selected_candidate_pair_changed;
  std::function<void(
      rtc::scoped_refptr<webrtc::RtpReceiverInterface>,
      const std::vector<rtc::scoped_refptr<webrtc::MediaStreamInterface>>)>
      on_add_track;
  std::function<void(rtc::scoped_refptr<webrtc::RtpTransceiverInterface>)>
      on_track;
  std::function<void(rtc::scoped_refptr<webrtc::RtpReceiverInterface>)>
      on_remove_track;
  std::function<void(int)> on_interesting_usage;

 private:
  void OnSignalingChange(
      webrtc::PeerConnectionInterface::SignalingState new_state) override {
    if (on_signaling_change) {
      on_signaling_change(new_state);
    }
  }
  void OnAddStream(
      rtc::scoped_refptr<webrtc::MediaStreamInterface> stream) override {
    if (on_add_stream) {
      on_add_stream(stream);
    }
  }
  void OnRemoveStream(
      rtc::scoped_refptr<webrtc::MediaStreamInterface> stream) override {
    if (on_remove_stream) {
      on_remove_stream(stream);
    }
  }
  void OnDataChannel(
      rtc::scoped_refptr<webrtc::DataChannelInterface> data_channel) override {
    if (on_data_channel) {
      on_data_channel(data_channel);
    }
  }
  void OnRenegotiationNeeded() override {
    if (on_renegotiation_needed) {
      on_renegotiation_needed();
    }
  }
  void OnNegotiationNeededEvent(uint32_t event_id) override {
    if (on_negotiation_needed_event) {
      on_negotiation_needed_event(event_id);
    }
  }
  void OnIceConnectionChange(
      webrtc::PeerConnectionInterface::IceConnectionState new_state) override {
    if (on_ice_connection_change) {
      on_ice_connection_change(new_state);
    }
  }
  void OnStandardizedIceConnectionChange(
      webrtc::PeerConnectionInterface::IceConnectionState new_state) override {
    if (on_standardized_ice_connection_change) {
      on_standardized_ice_connection_change(new_state);
    }
  }
  void OnConnectionChange(
      webrtc::PeerConnectionInterface::PeerConnectionState new_state) override {
    if (on_connection_change) {
      on_connection_change(new_state);
    }
  }
  void OnIceGatheringChange(
      webrtc::PeerConnectionInterface::IceGatheringState new_state) override {
    if (on_ice_gathering_change) {
      on_ice_gathering_change(new_state);
    }
  }
  void OnIceCandidate(const webrtc::IceCandidateInterface* candidate) override {
    if (on_ice_candidate) {
      on_ice_candidate(candidate);
    }
  }
  void OnIceCandidateError(const std::string& address,
                           int port,
                           const std::string& url,
                           int error_code,
                           const std::string& error_text) override {
    if (on_ice_candidate_error) {
      on_ice_candidate_error(address, port, url, error_code, error_text);
    }
  }
  void OnIceCandidatesRemoved(
      const std::vector<cricket::Candidate>& candidates) override {
    if (on_ice_candidates_removed) {
      on_ice_candidates_removed(candidates);
    }
  }
  void OnIceConnectionReceivingChange(bool receiving) override {
    if (on_ice_connection_receiving_change) {
      on_ice_connection_receiving_change(receiving);
    }
  }
  void OnIceSelectedCandidatePairChanged(
      const cricket::CandidatePairChangeEvent& event) override {
    if (on_ice_selected_candidate_pair_changed) {
      on_ice_selected_candidate_pair_changed(event);
    }
  }
  void OnAddTrack(
      rtc::scoped_refptr<webrtc::RtpReceiverInterface> receiver,
      const std::vector<rtc::scoped_refptr<webrtc::MediaStreamInterface>>&
          streams) override {
    if (on_add_track) {
      on_add_track(receiver, streams);
    }
  }
  void OnTrack(rtc::scoped_refptr<webrtc::RtpTransceiverInterface> transceiver)
      override {
    if (on_track) {
      on_track(transceiver);
    }
  }
  void OnRemoveTrack(
      rtc::scoped_refptr<webrtc::RtpReceiverInterface> receiver) override {
    if (on_remove_track) {
      on_remove_track(receiver);
    }
  }
  void OnInterestingUsage(int usage_pattern) override {
    if (on_interesting_usage) {
      on_interesting_usage(usage_pattern);
    }
  }
};

std::string CreateOffer(
    rtc::scoped_refptr<webrtc::PeerConnectionInterface> peer_connection,
    rtc::scoped_refptr<webrtc::VideoTrackInterface> video_track) {
  std::promise<std::string> promise;
  auto future = promise.get_future();

  webrtc::PeerConnectionInterface::RTCOfferAnswerOptions options;
  peer_connection->CreateOffer(
      CreateSessionDescriptionThunk::Create(
          [&promise, peer_connection,
           video_track](webrtc::SessionDescriptionInterface* desc) {
            // ビデオトラックを設定する
            auto sender = peer_connection->GetTransceivers()[0]->sender();
            sender->SetTrack(video_track.get());

            // 各 RtpEncodingParameters の利用するコーデックと payload_type を関連付ける
            std::map<std::string, int> rid_payload_type_map;
            auto send_encodings = sender->init_send_encodings();
            auto& content = desc->description()->contents()[0];
            auto media_desc = content.media_description();
            for (auto& send_encoding : send_encodings) {
              for (auto& codec : media_desc->codecs()) {
                if (send_encoding.codec &&
                    codec.MatchesRtpCodec(*send_encoding.codec)) {
                  RTC_LOG(LS_WARNING)
                      << "rid=" << send_encoding.rid << " codec=" << codec.name
                      << " payload_type=" << codec.id;
                  rid_payload_type_map[send_encoding.rid] = codec.id;
                }
              }
            }
            auto& track = media_desc->mutable_streams()[0];
            auto rids = track.rids();
            for (auto& rid : rids) {
              auto it = rid_payload_type_map.find(rid.rid);
              if (it == rid_payload_type_map.end()) {
                continue;
              }
              rid.payload_types.push_back(it->second);
            }
            track.set_rids(rids);

            auto parameters = sender->GetParameters();
            for (auto& encoding : parameters.encodings) {
              RTC_LOG(LS_WARNING)
                  << "Encoding Parameters: rid=" << encoding.rid << " codec="
                  << (encoding.codec ? encoding.codec->name : "none");
            }

            std::string sdp;
            desc->ToString(&sdp);
            RTC_LOG(LS_WARNING) << "Offer SDP: " << sdp;
            peer_connection->SetLocalDescription(
                std::unique_ptr<webrtc::SessionDescriptionInterface>(desc),
                SetLocalDescriptionThunk::Create(
                    [&promise, sdp](webrtc::RTCError error) {
                      if (!error.ok()) {
                        RTC_LOG(LS_WARNING) << "Failed to SetLocalDescription";
                        promise.set_value("");
                        return;
                      }
                      RTC_LOG(LS_WARNING) << "Succeeded to SetLocalDescription";
                      promise.set_value(sdp);
                    }));
          },
          [&promise](webrtc::RTCError error) { promise.set_value(""); })
          .get(),
      options);

  return future.get();
}

std::string SetRemoteDescriptionAndAnswer(
    rtc::scoped_refptr<webrtc::PeerConnectionInterface> peer_connection,
    std::unique_ptr<webrtc::SessionDescriptionInterface> description) {
  std::promise<std::string> promise;
  auto future = promise.get_future();

  peer_connection->SetRemoteDescription(
      std::move(description),
      SetRemoteDescriptionThunk::Create([&promise, peer_connection](
                                            webrtc::RTCError error) {
        if (!error.ok()) {
          RTC_LOG(LS_WARNING) << "Failed to SetRemoteDescription";
          promise.set_value("");
          return;
        }
        RTC_LOG(LS_WARNING)
            << "Receivers: " << peer_connection->GetReceivers().size();
        auto receiver = peer_connection->GetReceivers()[0];
        RTC_LOG(LS_WARNING) << "Streams: " << receiver->streams().size();
        for (auto stream : receiver->streams()) {
          RTC_LOG(LS_WARNING) << "id: " << stream->id();
        }

        webrtc::PeerConnectionInterface::RTCOfferAnswerOptions options;
        peer_connection->CreateAnswer(
            CreateSessionDescriptionThunk::Create(
                [&promise,
                 peer_connection](webrtc::SessionDescriptionInterface* desc) {
                  RTC_LOG(LS_WARNING)
                      << "Content: " << desc->description()->contents().size();
                  auto& content = desc->description()->contents()[0];
                  auto media_desc = content.media_description();
                  RTC_LOG(LS_WARNING)
                      << "MediaDescription: " << media_desc->streams().size();
                  std::vector<cricket::RidDescription> rids;
                  rids.push_back(cricket::RidDescription(
                      "r0", cricket::RidDirection::kReceive));
                  rids.push_back(cricket::RidDescription(
                      "r1", cricket::RidDirection::kReceive));
                  rids.push_back(cricket::RidDescription(
                      "r2", cricket::RidDirection::kReceive));
                  media_desc->set_receive_rids(rids);
                  cricket::SimulcastDescription simulcast;
                  simulcast.receive_layers().AddLayer(
                      cricket::SimulcastLayer("r0", false));
                  simulcast.receive_layers().AddLayer(
                      cricket::SimulcastLayer("r1", false));
                  simulcast.receive_layers().AddLayer(
                      cricket::SimulcastLayer("r2", false));
                  media_desc->set_simulcast_description(simulcast);
                  //auto& track = media_desc->mutable_streams()[0];
                  //RTC_LOG(LS_WARNING) << "Track: " << track.rids().size();

                  std::string sdp;
                  desc->ToString(&sdp);
                  RTC_LOG(LS_WARNING) << "Answer SDP: " << sdp;
                  peer_connection->SetLocalDescription(
                      std::unique_ptr<webrtc::SessionDescriptionInterface>(
                          desc),
                      SetLocalDescriptionThunk::Create(
                          [&promise, sdp](webrtc::RTCError error) {
                            if (!error.ok()) {
                              RTC_LOG(LS_WARNING)
                                  << "Failed to SetLocalDescription";
                              promise.set_value("");
                              return;
                            }
                            RTC_LOG(LS_WARNING)
                                << "Succeeded to SetLocalDescription";
                            promise.set_value(sdp);
                          }));
                },
                [&promise](webrtc::RTCError error) { promise.set_value(""); })
                .get(),
            options);
      }));

  return future.get();
}

bool SetRemoteDescription(
    rtc::scoped_refptr<webrtc::PeerConnectionInterface> peer_connection,
    std::unique_ptr<webrtc::SessionDescriptionInterface> description) {
  std::promise<bool> promise;
  auto future = promise.get_future();

  auto sender = peer_connection->GetTransceivers()[0]->sender();
  auto parameters = sender->GetParameters();
  for (auto& encoding : parameters.encodings) {
    RTC_LOG(LS_WARNING) << "Encoding Parameters: rid=" << encoding.rid
                        << " codec="
                        << (encoding.codec ? encoding.codec->name : "none");
  }

  peer_connection->SetRemoteDescription(
      std::move(description),
      SetRemoteDescriptionThunk::Create([&promise, peer_connection](
                                            webrtc::RTCError error) {
        auto sender = peer_connection->GetTransceivers()[0]->sender();
        auto parameters = sender->GetParameters();
        for (auto& encoding : parameters.encodings) {
          RTC_LOG(LS_WARNING)
              << "Encoding Parameters: rid=" << encoding.rid
              << " codec=" << (encoding.codec ? encoding.codec->name : "none");
        }

        if (!error.ok()) {
          RTC_LOG(LS_WARNING) << "Failed to SetRemoteDescription";
          promise.set_value(false);
          return;
        }
        RTC_LOG(LS_WARNING) << "Succeeded to SetRemoteDescription";
        promise.set_value(true);
      }));

  return future.get();
}

class VideoEncoderFactory : public webrtc::VideoEncoderFactory {
  std::unique_ptr<webrtc::InternalEncoderFactory> factory_;

 public:
  VideoEncoderFactory()
      : factory_(std::make_unique<webrtc::InternalEncoderFactory>()) {}

  std::vector<webrtc::SdpVideoFormat> GetSupportedFormats() const override {
    return factory_->GetSupportedFormats();
  }

  std::unique_ptr<webrtc::VideoEncoder> Create(
      const webrtc::Environment& env,
      const webrtc::SdpVideoFormat& format) override {
    return std::make_unique<webrtc::SimulcastEncoderAdapter>(
        env, factory_.get(), nullptr, format);
  }
};

class Sink : public rtc::VideoSinkInterface<webrtc::VideoFrame> {
 public:
  void OnFrame(const webrtc::VideoFrame& frame) override {
    RTC_LOG(LS_WARNING) << "Received frame: width=" << frame.width()
                        << " height=" << frame.height();
  }
};

int main() {
  rtc::LogMessage::LogToDebug(rtc::LS_INFO);
  //rtc::LogMessage::LogToDebug(rtc::LS_WARNING);
  rtc::LogMessage::LogTimestamps();
  rtc::LogMessage::LogThreads();

  rtc::InitializeSSL();

  auto network_thread = rtc::Thread::CreateWithSocketServer();
  network_thread->Start();
  auto worker_thread = rtc::Thread::Create();
  worker_thread->Start();
  auto signaling_thread = rtc::Thread::Create();
  signaling_thread->Start();

  // PC Factory を作る
  rtc::scoped_refptr<webrtc::PeerConnectionFactoryInterface>
      peer_connection_factory;
  {
    webrtc::PeerConnectionFactoryDependencies dependencies;
    dependencies.network_thread = network_thread.get();
    dependencies.worker_thread = worker_thread.get();
    dependencies.signaling_thread = signaling_thread.get();
    dependencies.task_queue_factory = webrtc::CreateDefaultTaskQueueFactory();

    dependencies.adm = worker_thread->BlockingCall([&] {
      auto audio_layer = webrtc::AudioDeviceModule::kDummyAudio;
      auto task_queue_factory = dependencies.task_queue_factory.get();
      return webrtc::AudioDeviceModule::Create(audio_layer, task_queue_factory);
    });

    dependencies.audio_encoder_factory =
        webrtc::CreateBuiltinAudioEncoderFactory();
    dependencies.audio_decoder_factory =
        webrtc::CreateBuiltinAudioDecoderFactory();

    dependencies.video_encoder_factory =
        std::make_unique<VideoEncoderFactory>();
    dependencies.video_decoder_factory =
        std::make_unique<webrtc::InternalDecoderFactory>();

    dependencies.audio_mixer = nullptr;
    dependencies.audio_processing = webrtc::AudioProcessingBuilder().Create();

    webrtc::EnableMedia(dependencies);

    peer_connection_factory =
        webrtc::CreateModularPeerConnectionFactory(std::move(dependencies));

    webrtc::PeerConnectionFactoryInterface::Options factory_options;
    factory_options.disable_encryption = false;
    factory_options.ssl_max_version = rtc::SSL_PROTOCOL_DTLS_12;
    factory_options.crypto_options.srtp.enable_gcm_crypto_suites = true;
    peer_connection_factory->SetOptions(factory_options);
  }

  // Fake キャプチャラを持つビデオトラックを作る
  rtc::scoped_refptr<webrtc::VideoTrackInterface> video_track;
  {
    FakeVideoCapturerConfig fake_config;
    fake_config.width = 1920;
    fake_config.height = 1080;
    fake_config.fps = 30;
    auto video_source = CreateFakeVideoCapturer(fake_config);
    std::string video_track_id = rtc::CreateRandomString(16);
    video_track =
        peer_connection_factory->CreateVideoTrack(video_source, video_track_id);
  }

  rtc::scoped_refptr<webrtc::PeerConnectionInterface> local_pc;
  rtc::scoped_refptr<webrtc::PeerConnectionInterface> remote_pc;
  PeerConnectionObserverThunk local_pc_observer;
  PeerConnectionObserverThunk remote_pc_observer;

  // Offer 側の PC を作る
  {
    webrtc::PeerConnectionInterface::RTCConfiguration rtc_config;
    rtc_config.sdp_semantics = webrtc::SdpSemantics::kUnifiedPlan;

    local_pc_observer.on_ice_candidate =
        [&remote_pc](const webrtc::IceCandidateInterface* candidate) {
          std::string sdp;
          if (!candidate->ToString(&sdp)) {
            RTC_LOG(LS_ERROR) << "Failed to serialize candidate";
            return;
          }
          RTC_LOG(LS_WARNING)
              << "OnIceCandidate: sdp=" << sdp
              << " mid=" << candidate->sdp_mid()
              << " mline_index=" << candidate->sdp_mline_index();
          remote_pc->AddIceCandidate(candidate);
        };

    webrtc::PeerConnectionDependencies pc_dependencies(&local_pc_observer);

    auto result = peer_connection_factory->CreatePeerConnectionOrError(
        rtc_config, std::move(pc_dependencies));
    if (!result.ok()) {
      RTC_LOG(LS_ERROR) << "Failed to create PeerConnection: "
                        << result.error().message();
      return -1;
    }
    local_pc = result.value();
  }

  webrtc::RtpTransceiverInit init;
  webrtc::RtpCodecCapability vp9_codec;
  webrtc::RtpCodecCapability av1_codec;
  vp9_codec.kind = cricket::MEDIA_TYPE_VIDEO;
  vp9_codec.name = "VP9";
  vp9_codec.parameters["profile-id"] = "0";
  vp9_codec.clock_rate = 90000;
  av1_codec.kind = cricket::MEDIA_TYPE_VIDEO;
  av1_codec.name = "AV1";
  av1_codec.clock_rate = 90000;
  av1_codec.parameters["level-idx"] = "5";
  av1_codec.parameters["profile"] = "0";
  av1_codec.parameters["tier"] = "0";
  init.direction = webrtc::RtpTransceiverDirection::kSendOnly;
  init.stream_ids = {"s0"};
  init.send_encodings.resize(3);
  init.send_encodings[0].rid = "r0";
  init.send_encodings[0].codec = vp9_codec;
  init.send_encodings[0].scale_resolution_down_by = 4.0;
  init.send_encodings[1].rid = "r1";
  init.send_encodings[1].codec = vp9_codec;
  init.send_encodings[1].scale_resolution_down_by = 2.0;
  init.send_encodings[2].rid = "r2";
  init.send_encodings[2].codec = vp9_codec;
  init.send_encodings[2].scale_resolution_down_by = 1.0;
  auto transceiver_result =
      local_pc->AddTransceiver(cricket::MEDIA_TYPE_VIDEO, init);
  if (!transceiver_result.ok()) {
    RTC_LOG(LS_ERROR) << "Failed to AddTransceiver: "
                      << transceiver_result.error().message();
    return -1;
  }

  std::string local_sdp = CreateOffer(local_pc, video_track);
  if (local_sdp.empty()) {
    RTC_LOG(LS_ERROR) << "Failed to create offer";
    return -1;
  }
  auto local_desc =
      webrtc::CreateSessionDescription(webrtc::SdpType::kOffer, local_sdp);

  // Answer 側の PC を作る
  {
    webrtc::PeerConnectionInterface::RTCConfiguration rtc_config;
    rtc_config.sdp_semantics = webrtc::SdpSemantics::kUnifiedPlan;

    remote_pc_observer.on_track =
        [](rtc::scoped_refptr<webrtc::RtpTransceiverInterface> transceiver) {
          RTC_LOG(LS_WARNING) << "OnTrack";
          rtc::scoped_refptr<webrtc::MediaStreamTrackInterface> track =
              transceiver->receiver()->track();
          if (track->kind() == webrtc::MediaStreamTrackInterface::kVideoKind) {
            webrtc::VideoTrackInterface* video_track =
                static_cast<webrtc::VideoTrackInterface*>(track.get());
            video_track->AddOrUpdateSink(new Sink(), rtc::VideoSinkWants());
          }
        };
    webrtc::PeerConnectionDependencies pc_dependencies(&remote_pc_observer);

    auto result = peer_connection_factory->CreatePeerConnectionOrError(
        rtc_config, std::move(pc_dependencies));
    if (!result.ok()) {
      RTC_LOG(LS_ERROR) << "Failed to create PeerConnection: "
                        << result.error().message();
      return -1;
    }
    remote_pc = result.value();
  }

  auto remote_sdp =
      SetRemoteDescriptionAndAnswer(remote_pc, std::move(local_desc));
  if (remote_sdp.empty()) {
    RTC_LOG(LS_ERROR) << "Failed to SetRemoteDescription";
    return -1;
  }
  auto remote_desc =
      webrtc::CreateSessionDescription(webrtc::SdpType::kAnswer, remote_sdp);

  {
    bool r = SetRemoteDescription(local_pc, std::move(remote_desc));
    if (!r) {
      return -1;
    }
  }

  std::this_thread::sleep_for(std::chrono::seconds(5));
}
