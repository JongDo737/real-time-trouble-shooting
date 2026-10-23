package com.realshoot.backend.rag;

import java.util.List;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

/**
 * RAG 서비스 요청 · 응답 (snake_case). RAG 담당 api.md(v0.3) 기준 — 필드가 바뀌면 이 파일만 고친다.
 * speaker는 USER / ADMIN (RAG 쪽이 맞추기로 협의). 응답의 쓰지 않는 필드는 무시한다.
 */
public final class RagDtos {

    private RagDtos() {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record TranslateRequest(String sessionId, String utteranceId, String text, String sourceLang,
                                   String targetLang, String speaker, String equipmentName, String errorCode,
                                   List<ContextItem> context) {

        @Override
        public String toString() {
            return "TranslateRequest[sessionId=" + sessionId + ", utteranceId=" + utteranceId + "]";
        }
    }

    /** 같은 통화의 이전 발화 (원문) */
    public record ContextItem(String speaker, String text) {

        @Override
        public String toString() {
            return "ContextItem[speaker=" + speaker + "]";
        }
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record TranslateResponse(String translatedText, boolean needsReview) {

        @Override
        public String toString() {
            return "TranslateResponse[needsReview=" + needsReview + "]";
        }
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record RagQueryRequest(String sessionId, String requestId, String equipmentName, String errorCode,
                                  String symptom) {
    }

    /** status: found | not_found (not_found도 HTTP 200 정상 응답) */
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record RagQueryResponse(String status, String answer, Double score, List<RagSource> sources,
                                   boolean needsReview, boolean handoff) {
    }

    /** text = 근거 청크 본문 (→ translation_manual_refs.text) */
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record RagSource(String doc, Integer page, String section, String text, Double score) {
    }
}
