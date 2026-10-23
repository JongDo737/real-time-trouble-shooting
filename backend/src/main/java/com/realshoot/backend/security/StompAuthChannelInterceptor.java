package com.realshoot.backend.security;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.http.HttpHeaders;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageDeliveryException;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageHeaderAccessor;
import org.springframework.stereotype.Component;

import com.realshoot.backend.call.CallRepository;
import com.realshoot.backend.call.CallStatus;

import lombok.RequiredArgsConstructor;

/**
 * CONNECT: Authorization 헤더 JWT 검증 후 사용자 등록.
 * SUBSCRIBE: /topic/calls/{callId} 구독 권한 확인 (W-1).
 * 예외를 던지면 클라이언트에 ERROR 프레임이 가고 연결이 끊긴다.
 */
@Component
@RequiredArgsConstructor
public class StompAuthChannelInterceptor implements ChannelInterceptor {

    private static final Pattern CALL_TOPIC = Pattern.compile("^/topic/calls/([0-9a-fA-F-]{36})$");

    private final JwtProvider jwtProvider;
    private final CallRepository callRepository;

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor = MessageHeaderAccessor.getAccessor(message, StompHeaderAccessor.class);
        if (accessor == null || accessor.getCommand() == null) {
            return message;
        }
        StompCommand command = accessor.getCommand();
        if (command == StompCommand.CONNECT) {
            accessor.setUser(authenticate(accessor));
        } else if (command == StompCommand.SUBSCRIBE) {
            checkSubscribe(currentUser(accessor), accessor.getDestination());
        } else if (command == StompCommand.SEND) {
            currentUser(accessor);
        }
        return message;
    }

    private AuthUser authenticate(StompHeaderAccessor accessor) {
        try {
            return jwtProvider.parseBearer(accessor.getFirstNativeHeader(HttpHeaders.AUTHORIZATION));
        } catch (RuntimeException e) {
            throw new MessageDeliveryException("UNAUTHORIZED");
        }
    }

    private AuthUser currentUser(StompHeaderAccessor accessor) {
        if (accessor.getUser() instanceof AuthUser user) {
            return user;
        }
        throw new MessageDeliveryException("UNAUTHORIZED");
    }

    /** USER: 본인 통화 + PENDING/CALLING, ADMIN: 받은 상담원 + CALLING */
    private void checkSubscribe(AuthUser user, String destination) {
        Matcher matcher = destination == null ? null : CALL_TOPIC.matcher(destination);
        if (matcher == null || !matcher.matches()) {
            throw new MessageDeliveryException("FORBIDDEN");
        }
        boolean allowed = callRepository.findByCallId(matcher.group(1))
                .map(call -> user.isAdmin()
                        ? call.isAcceptedBy(user.id()) && call.getStatus() == CallStatus.CALLING
                        : call.isRequestedBy(user.id())
                          && (call.getStatus() == CallStatus.PENDING || call.getStatus() == CallStatus.CALLING))
                .orElse(false);
        if (!allowed) {
            throw new MessageDeliveryException("FORBIDDEN");
        }
    }
}
