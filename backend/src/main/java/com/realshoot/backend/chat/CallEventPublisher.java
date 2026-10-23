package com.realshoot.backend.chat;

import java.time.Instant;

import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.realshoot.backend.auth.Role;
import com.realshoot.backend.call.CallStatus;

import lombok.RequiredArgsConstructor;

/**
 * /topic/calls/{callId} 채널 전송 (W-1). 고객도 구독하는 채널이므로
 * 해결방법(RAG 결과)과 발화 원문은 절대 여기로 보내지 않는다.
 */
@Component
@RequiredArgsConstructor
public class CallEventPublisher {

    private final SimpMessagingTemplate messagingTemplate;

    public void accepted(String callId) {
        send(callId, new CallEvent("accepted", callId, null));
    }

    public void ended(String callId, CallStatus status) {
        send(callId, new CallEvent("ended", callId, status));
    }

    public void missed(String callId) {
        send(callId, new CallEvent("missed", callId, null));
    }

    public void translation(TranslationMessage message) {
        send(message.callId(), message);
    }

    private void send(String callId, Object payload) {
        messagingTemplate.convertAndSend("/topic/calls/" + callId, payload);
    }

    /** accepted / ended / missed — 문구 없이 상태값만 */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record CallEvent(String type, String callId, CallStatus status) {
    }

    /** 번역문만 담는다. translatedText는 실패 시 null로 그대로 보냄 */
    public record TranslationMessage(String type, String callId, String utteranceId, Role senderRole,
                                     String translatedText, String targetLang, boolean needsReview,
                                     Instant timestamp) {

        @Override
        public String toString() {
            return "TranslationMessage[callId=" + callId + ", utteranceId=" + utteranceId + "]";
        }
    }
}
