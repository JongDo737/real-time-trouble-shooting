package com.realshoot.backend.rag;

import java.io.IOException;
import java.time.Duration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realshoot.backend.rag.RagDtos.RagQueryRequest;
import com.realshoot.backend.rag.RagDtos.RagQueryResponse;
import com.realshoot.backend.rag.RagDtos.TranslateRequest;
import com.realshoot.backend.rag.RagDtos.TranslateResponse;
import com.realshoot.backend.security.AuthUser;
import com.realshoot.backend.security.JwtProvider;

import lombok.extern.slf4j.Slf4j;

/**
 * RAG · 번역 서비스 호출 (blocking). 요청한 사용자 이름으로 짧은 JWT를 새로 발급해 보낸다
 * (같은 JWT_SECRET 공유). 오류 응답이 LLM_TIMEOUT이면 1회 재시도.
 */
@Slf4j
@Component
public class RagClient {

    private static final String LLM_TIMEOUT = "LLM_TIMEOUT";

    private final WebClient webClient;
    private final JwtProvider jwtProvider;
    private final ObjectMapper objectMapper;
    private final Duration translateTimeout;
    private final Duration queryTimeout;

    public RagClient(WebClient.Builder builder, JwtProvider jwtProvider, ObjectMapper objectMapper,
                     @Value("${rag.base-url}") String baseUrl,
                     @Value("${rag.translate-timeout}") Duration translateTimeout,
                     @Value("${rag.query-timeout}") Duration queryTimeout) {
        this.webClient = builder.baseUrl(baseUrl).build();
        this.jwtProvider = jwtProvider;
        this.objectMapper = objectMapper;
        this.translateTimeout = translateTimeout;
        this.queryTimeout = queryTimeout;
    }

    public TranslateResponse translate(TranslateRequest request, AuthUser caller) {
        return postWithRetry("/translate", request, TranslateResponse.class, caller, translateTimeout);
    }

    public RagQueryResponse ragQuery(RagQueryRequest request, AuthUser caller) {
        return postWithRetry("/rag-query", request, RagQueryResponse.class, caller, queryTimeout);
    }

    private <T> T postWithRetry(String path, Object body, Class<T> type, AuthUser caller, Duration timeout) {
        try {
            return post(path, body, type, caller, timeout);
        } catch (WebClientResponseException e) {
            if (!LLM_TIMEOUT.equals(errorCode(e))) {
                throw e;
            }
            log.info("RAG {} LLM_TIMEOUT, 1회 재시도", path);
            return post(path, body, type, caller, timeout);
        }
    }

    private <T> T post(String path, Object body, Class<T> type, AuthUser caller, Duration timeout) {
        return webClient.post()
                .uri(path)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.issue(caller.id(), caller.role()))
                .bodyValue(body)
                .retrieve()
                .bodyToMono(type)
                .timeout(timeout)
                .block();
    }

    /** RAG 오류 형식 { "error": { "code": ... } } 에서 code 추출 */
    private String errorCode(WebClientResponseException e) {
        try {
            return objectMapper.readTree(e.getResponseBodyAsByteArray()).path("error").path("code").asText(null);
        } catch (IOException ignored) {
            return null;
        }
    }

    /** 로그용 실패 요약 (응답 본문 · 요청 내용은 남기지 않음) */
    public static String describe(Throwable e) {
        if (e instanceof WebClientResponseException wcre) {
            return "HTTP " + wcre.getStatusCode().value();
        }
        return e.getClass().getSimpleName();
    }
}
