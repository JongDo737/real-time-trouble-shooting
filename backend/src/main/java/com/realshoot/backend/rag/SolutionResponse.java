package com.realshoot.backend.rag;

import java.util.List;

import com.realshoot.backend.rag.RagDtos.RagQueryResponse;

/**
 * C-5 응답. status: PENDING(검색 중) | found | not_found | error.
 * riskLevel: INFO | WARNING | CRITICAL (없으면 null), riskReason: 위험도 줄의 괄호 안 이유
 */
public record SolutionResponse(String status, String answer, List<Source> sources, boolean needsReview,
                               boolean handoff, String riskLevel, String riskReason) {

    public static final String PENDING = "PENDING";
    public static final String FOUND = "found";
    public static final String ERROR = "error";

    public record Source(String doc, Integer page, String section) {
    }

    public static SolutionResponse pending() {
        return new SolutionResponse(PENDING, null, List.of(), false, false, null, null);
    }

    public static SolutionResponse error() {
        return new SolutionResponse(ERROR, null, List.of(), false, false, null, null);
    }

    public static SolutionResponse from(RagQueryResponse response) {
        List<Source> sources = response.sources() == null ? List.of()
                : response.sources().stream().map(s -> new Source(s.doc(), s.page(), s.section())).toList();
        return new SolutionResponse(response.status(), response.answer(), sources, response.needsReview(),
                response.handoff(), response.riskLevel(), response.riskReason());
    }

    /** 서버 재시작으로 메모리 결과가 사라졌을 때 DB 출처만으로 복원 (위험도 이유는 저장하지 않아 등급만 복원) */
    public static SolutionResponse fromStoredRefs(List<ManualRef> refs) {
        if (refs.isEmpty()) {
            return error();
        }
        List<Source> sources = refs.stream().map(r -> new Source(r.getDocTitle(), r.getPageNo(), null)).toList();
        return new SolutionResponse(FOUND, null, sources, false, false, refs.get(0).getRiskLevel(), null);
    }
}
