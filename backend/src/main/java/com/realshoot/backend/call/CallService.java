package com.realshoot.backend.call;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;

import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.realshoot.backend.auth.UserRepository;
import com.realshoot.backend.call.CallDtos.CallDetailResponse;
import com.realshoot.backend.call.CallDtos.CallResponse;
import com.realshoot.backend.call.CallDtos.CreateCallRequest;
import com.realshoot.backend.call.CallDtos.CreateCallResponse;
import com.realshoot.backend.call.CallDtos.MessageResponse;
import com.realshoot.backend.call.CallDtos.PageResponse;
import com.realshoot.backend.chat.CallEventPublisher;
import com.realshoot.backend.chat.Translation;
import com.realshoot.backend.chat.TranslationRepository;
import com.realshoot.backend.global.Times;
import com.realshoot.backend.global.error.ApiException;
import com.realshoot.backend.global.error.ErrorCode;
import com.realshoot.backend.rag.ManualRefRepository;
import com.realshoot.backend.rag.RagResultStore;
import com.realshoot.backend.rag.RagService;
import com.realshoot.backend.rag.RagService.CallSnapshot;
import com.realshoot.backend.rag.SolutionResponse;
import com.realshoot.backend.security.AuthUser;

import jakarta.persistence.criteria.Predicate;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class CallService {

    private static final int MAX_PAGE_SIZE = 100;
    private static final Set<CallStatus> ACTIVE = EnumSet.of(CallStatus.PENDING, CallStatus.CALLING);

    private final CallRepository callRepository;
    private final UserRepository userRepository;
    private final TranslationRepository translationRepository;
    private final ManualRefRepository manualRefRepository;
    private final CallMissedScheduler missedScheduler;
    private final CallEventPublisher events;
    private final RagService ragService;
    private final RagResultStore ragResults;

    /** C-1 */
    @Transactional
    public CreateCallResponse create(AuthUser user, CreateCallRequest request) {
        if (callRepository.existsByCustomer_IdAndStatusIn(user.id(), ACTIVE)) {
            throw new ApiException(ErrorCode.INVALID_STATUS_TRANSITION, "이미 대기 중이거나 통화 중인 요청이 있습니다.");
        }
        Call call = Call.request(userRepository.getReferenceById(user.id()), request.equipmentName(),
                request.errorCode(), request.symptom());
        callRepository.save(call);
        missedScheduler.schedule(call.getCallId());
        return new CreateCallResponse(call.getCallId());
    }

    /** C-2. 조회 범위는 역할로 서버가 정한다 (USER = 본인 통화만) */
    @Transactional(readOnly = true)
    public PageResponse<CallResponse> list(AuthUser user, String status, LocalDate from, LocalDate to, int page,
                                           int size) {
        if (page < 0 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new ApiException(ErrorCode.VALIDATION_ERROR, "page는 0 이상, size는 1~100입니다.");
        }
        Set<CallStatus> statuses = parseStatuses(status);

        Specification<Call> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (!user.isAdmin()) {
                predicates.add(cb.equal(root.get("customer").get("id"), user.id()));
            }
            if (!statuses.isEmpty()) {
                predicates.add(root.get("status").in(statuses));
            }
            if (from != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("createdAt"), startOfDay(from)));
            }
            if (to != null) {
                predicates.add(cb.lessThan(root.get("createdAt"), startOfDay(to.plusDays(1))));
            }
            return cb.and(predicates.toArray(Predicate[]::new));
        };

        // 본사 대기 목록(PENDING만)은 오래 기다린 순
        boolean waitingList = user.isAdmin() && statuses.equals(EnumSet.of(CallStatus.PENDING));
        Sort.Direction direction = waitingList ? Sort.Direction.ASC : Sort.Direction.DESC;
        var pageable = PageRequest.of(page, size, Sort.by(direction, "createdAt", "id"));

        return PageResponse.of(callRepository.findAll(spec, pageable), CallResponse::from);
    }

    /** C-3. messages[].text는 조회자 언어로 */
    @Transactional(readOnly = true)
    public CallDetailResponse detail(AuthUser user, String callId) {
        Call call = findVisibleCall(user, callId);
        String viewerLang = user.role().lang();
        List<MessageResponse> messages = translationRepository.findAllWithSender(call.getId()).stream()
                .map(t -> new MessageResponse(String.valueOf(t.getId()), t.getSender().getRole(),
                        textFor(viewerLang, t), t.getCreatedAt()))
                .toList();
        return new CallDetailResponse(call.getCallId(), call.getStatus(), call.getEquipmentName(),
                call.getErrorCode(), call.getCreatedAt(), call.getStartedAt(), call.getEndedAt(), messages);
    }

    /** C-4. 상태 전환은 조건부 UPDATE (각 repository 메서드가 자체 트랜잭션) */
    public CallResponse changeStatus(AuthUser admin, String callId, CallStatus to) {
        switch (to) {
            case CALLING -> accept(admin, callId);
            case RESOLVED, UNRESOLVED -> end(admin, callId, to);
            default -> throw new ApiException(ErrorCode.VALIDATION_ERROR,
                    "status는 CALLING, RESOLVED, UNRESOLVED만 가능합니다.");
        }
        return CallResponse.from(findCall(callId));
    }

    /** C-5. 받은 상담원 본인만 */
    @Transactional(readOnly = true)
    public SolutionResponse solution(AuthUser admin, String callId) {
        Call call = findCall(callId);
        if (!call.isAcceptedBy(admin.id())) {
            throw new ApiException(ErrorCode.FORBIDDEN);
        }
        return ragResults.get(callId)
                .orElseGet(() -> SolutionResponse.fromStoredRefs(manualRefRepository.findByCall_IdOrderByIdAsc(call.getId())));
    }

    private void accept(AuthUser admin, String callId) {
        Call call = findCall(callId);
        int updated = callRepository.accept(callId, CallStatus.PENDING, CallStatus.CALLING,
                userRepository.getReferenceById(admin.id()), Times.now());
        if (updated == 0) {
            CallStatus current = findCall(callId).getStatus();
            throw new ApiException(current == CallStatus.CALLING
                    ? ErrorCode.ALREADY_ACCEPTED : ErrorCode.INVALID_STATUS_TRANSITION);
        }
        missedScheduler.cancel(callId);
        events.accepted(callId);
        ragResults.markPending(callId);
        ragService.search(CallSnapshot.from(call), admin);
    }

    private void end(AuthUser admin, String callId, CallStatus to) {
        Call call = findCall(callId);
        if (call.getStatus() != CallStatus.CALLING) {
            throw new ApiException(ErrorCode.INVALID_STATUS_TRANSITION, "CALLING 상태의 통화만 종료할 수 있습니다.");
        }
        if (!call.isAcceptedBy(admin.id())) {
            throw new ApiException(ErrorCode.FORBIDDEN, "통화를 받은 상담원만 종료할 수 있습니다.");
        }
        if (callRepository.end(callId, CallStatus.CALLING, to, admin.id(), Times.now()) == 0) {
            throw new ApiException(ErrorCode.INVALID_STATUS_TRANSITION);
        }
        events.ended(callId, to);
    }

    private Call findCall(String callId) {
        return callRepository.findByCallId(callId).orElseThrow(() -> new ApiException(ErrorCode.NOT_FOUND));
    }

    /** USER가 남의 통화를 보면 존재를 숨기려고 403 대신 404 */
    private Call findVisibleCall(AuthUser user, String callId) {
        Call call = findCall(callId);
        if (!user.isAdmin() && !call.isRequestedBy(user.id())) {
            throw new ApiException(ErrorCode.NOT_FOUND);
        }
        return call;
    }

    static String textFor(String viewerLang, Translation t) {
        return viewerLang.equals(t.getOriginalLang()) ? t.getOriginalText() : t.getTranslatedText();
    }

    private static Set<CallStatus> parseStatuses(String status) {
        if (status == null || status.isBlank()) {
            return EnumSet.noneOf(CallStatus.class);
        }
        try {
            Set<CallStatus> statuses = EnumSet.noneOf(CallStatus.class);
            Arrays.stream(status.split(",")).map(String::trim).filter(s -> !s.isEmpty())
                    .map(CallStatus::valueOf).forEach(statuses::add);
            return statuses;
        } catch (IllegalArgumentException e) {
            throw new ApiException(ErrorCode.VALIDATION_ERROR, "status 값이 올바르지 않습니다.");
        }
    }

    private static Instant startOfDay(LocalDate date) {
        return date.atStartOfDay(ZoneOffset.UTC).toInstant();
    }
}
