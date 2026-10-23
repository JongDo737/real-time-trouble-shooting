package com.realshoot.backend.global.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

/**
 * WebSocket 설정이 자체 TaskScheduler · Executor 빈을 만들기 때문에
 * 우리가 쓰는 스케줄러 · 실행기는 이름을 붙여 따로 둔다.
 */
@Configuration
@EnableScheduling
@EnableAsync
public class AsyncConfig {

    /** 부재중 타이머 + @Scheduled 작업 (이름이 taskScheduler면 @Scheduled가 이 빈을 씀) */
    @Bean(name = "taskScheduler")
    public ThreadPoolTaskScheduler taskScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(2);
        scheduler.setThreadNamePrefix("call-timer-");
        return scheduler;
    }

    /** RAG /rag-query 비동기 호출 */
    @Bean(name = "ragExecutor")
    public ThreadPoolTaskExecutor ragExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(4);
        executor.setMaxPoolSize(8);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("rag-");
        return executor;
    }
}
