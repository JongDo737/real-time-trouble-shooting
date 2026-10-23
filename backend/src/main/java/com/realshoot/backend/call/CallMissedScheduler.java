package com.realshoot.backend.call;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledFuture;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import com.realshoot.backend.chat.CallEventPublisher;
import com.realshoot.backend.global.Times;

import lombok.extern.slf4j.Slf4j;

/**
 * 부재중 처리 (backend-api.md §7.3).
 * 통화마다 타이머를 걸고, 재시작으로 타이머가 사라진 경우를 위해 1분마다 일괄 정리도 한다.
 * 둘 다 PENDING 조건부 UPDATE라서 그 사이 상담원이 받았으면 아무 일도 없다.
 */
@Slf4j
@Component
public class CallMissedScheduler {

    private final TaskScheduler taskScheduler;
    private final CallRepository callRepository;
    private final CallEventPublisher events;
    private final Duration timeout;
    private final Map<String, ScheduledFuture<?>> timers = new ConcurrentHashMap<>();

    public CallMissedScheduler(@Qualifier("taskScheduler") TaskScheduler taskScheduler,
                               CallRepository callRepository, CallEventPublisher events,
                               @Value("${call.missed-timeout}") long timeoutSeconds) {
        this.taskScheduler = taskScheduler;
        this.callRepository = callRepository;
        this.events = events;
        this.timeout = Duration.ofSeconds(timeoutSeconds);
    }

    public void schedule(String callId) {
        timers.put(callId, taskScheduler.schedule(() -> expire(callId), Instant.now().plus(timeout)));
    }

    public void cancel(String callId) {
        ScheduledFuture<?> timer = timers.remove(callId);
        if (timer != null) {
            timer.cancel(false);
        }
    }

    @Scheduled(fixedDelay = 60_000, initialDelay = 60_000)
    public void sweep() {
        callRepository.findCallIdsByStatusCreatedBefore(CallStatus.PENDING, Instant.now().minus(timeout))
                .forEach(this::expire);
    }

    void expire(String callId) {
        timers.remove(callId);
        int updated = callRepository.expire(callId, CallStatus.PENDING, CallStatus.MISSED, Times.now());
        if (updated == 1) {
            log.info("부재중 처리 callId={}", callId);
            events.missed(callId);
        }
    }
}
