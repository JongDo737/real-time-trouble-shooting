package com.realshoot.backend.chat;

import java.security.Principal;

import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageExceptionHandler;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Controller;

import com.realshoot.backend.security.AuthUser;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/** W-2. SEND /app/calls/{callId}/message { "text": "..." } */
@Slf4j
@Controller
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;

    @MessageMapping("/calls/{callId}/message")
    public void message(@DestinationVariable String callId, @Payload ChatMessageRequest request, Principal principal) {
        if (principal instanceof AuthUser user && request != null) {
            chatService.handle(user, callId, request.text());
        }
    }

    /** 기본 처리는 예외 메시지를 그대로 로그에 남기므로 타입만 기록 */
    @MessageExceptionHandler
    public void handleException(Exception e) {
        log.error("W-2 처리 실패: {}", e.getClass().getName());
    }

    public record ChatMessageRequest(String text) {

        @Override
        public String toString() {
            return "ChatMessageRequest[length=" + (text == null ? 0 : text.length()) + "]";
        }
    }
}
