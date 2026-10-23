package com.realshoot.backend.rag;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;

/**
 * callId별 RAG 검색 상태 · 답변 (메모리). §11 스키마에 저장할 컬럼이 없어 메모리에 둔다.
 * 출처는 translation_manual_refs에 따로 저장하므로, 재시작 후에는 출처만 복원된다.
 */
@Component
public class RagResultStore {

    private final Map<String, SolutionResponse> results = new ConcurrentHashMap<>();

    public void markPending(String callId) {
        results.put(callId, SolutionResponse.pending());
    }

    public void put(String callId, SolutionResponse result) {
        results.put(callId, result);
    }

    public Optional<SolutionResponse> get(String callId) {
        return Optional.ofNullable(results.get(callId));
    }
}
