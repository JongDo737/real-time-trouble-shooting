package com.realshoot.backend.rag;

import java.util.List;
import java.util.UUID;

import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import com.realshoot.backend.call.Call;
import com.realshoot.backend.call.CallRepository;
import com.realshoot.backend.rag.RagDtos.RagQueryRequest;
import com.realshoot.backend.rag.RagDtos.RagQueryResponse;
import com.realshoot.backend.security.AuthUser;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/** C-4 받기 성공 시 /rag-query 비동기 호출 (backend-api.md §7.1) */
@Slf4j
@Service
@RequiredArgsConstructor
public class RagService {

    private final RagClient ragClient;
    private final RagResultStore resultStore;
    private final ManualRefRepository manualRefRepository;
    private final CallRepository callRepository;

    /** 비동기 실행 중 엔티티 지연 로딩을 피하려고 필요한 값만 넘긴다 */
    public record CallSnapshot(Long callPk, String callId, String equipmentName, String errorCode,
                               String symptom) {

        public static CallSnapshot from(Call call) {
            return new CallSnapshot(call.getId(), call.getCallId(), call.getEquipmentName(), call.getErrorCode(),
                    call.getSymptom());
        }
    }

    /** 호출 전에 resultStore.markPending(callId)가 되어 있어야 C-5가 바로 PENDING을 돌려준다 */
    @Async("ragExecutor")
    public void search(CallSnapshot call, AuthUser agent) {
        RagQueryRequest request = new RagQueryRequest(call.callId(), "q-" + UUID.randomUUID().toString().substring(0, 8),
                call.equipmentName(), call.errorCode(), call.symptom());
        try {
            RagQueryResponse response = ragClient.ragQuery(request, agent);
            saveSources(call.callPk(), response);
            resultStore.put(call.callId(), SolutionResponse.from(response));
        } catch (RuntimeException e) {
            log.warn("RAG 검색 실패 callId={} cause={}", call.callId(), RagClient.describe(e));
            resultStore.put(call.callId(), SolutionResponse.error());
        }
    }

    private void saveSources(Long callPk, RagQueryResponse response) {
        if (response.sources() == null || response.sources().isEmpty()) {
            return;
        }
        Call callRef = callRepository.getReferenceById(callPk);
        List<ManualRef> refs = response.sources().stream()
                .map(s -> ManualRef.of(callRef, s.doc(), s.page(), s.text(),
                        toFloat(s.score() != null ? s.score() : response.score()), s.riskLevel()))
                .toList();
        manualRefRepository.saveAll(refs);
    }

    private static Float toFloat(Double value) {
        return value == null ? null : value.floatValue();
    }
}
