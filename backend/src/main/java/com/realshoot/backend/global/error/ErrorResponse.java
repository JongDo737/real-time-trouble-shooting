package com.realshoot.backend.global.error;

import com.fasterxml.jackson.annotation.JsonProperty;

/** {@code { "error": { "code", "message", "request_id" } }} — RAG 명세와 같은 형식 */
public record ErrorResponse(Body error) {

    public record Body(String code, String message, @JsonProperty("request_id") String requestId) {
    }

    public static ErrorResponse of(ErrorCode code, String message) {
        return new ErrorResponse(new Body(code.name(), message, RequestIdFilter.currentRequestId()));
    }

    public static ErrorResponse of(ErrorCode code) {
        return of(code, code.getDefaultMessage());
    }
}
