package com.realshoot.backend.call;

import java.time.Instant;
import java.util.List;
import java.util.function.Function;

import org.springframework.data.domain.Page;

import com.realshoot.backend.auth.Role;
import com.realshoot.backend.auth.User;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public final class CallDtos {

    private CallDtos() {
    }

    /** C-1 */
    public record CreateCallRequest(
            @NotBlank @Size(max = 100) String equipmentName,
            @NotBlank @Size(max = 50) String errorCode,
            @Size(max = 500) String symptom) {
    }

    public record CreateCallResponse(String callId) {
    }

    /** C-4. CALLING(받기) · RESOLVED · UNRESOLVED(종료)만 허용 */
    public record UpdateStatusRequest(@NotNull CallStatus status) {
    }

    /** C-2 items[] · C-4 응답 */
    public record CallResponse(String callId, CallStatus status, String equipmentName, String errorCode,
                               String symptom, Customer customer, Agent agent, Instant createdAt,
                               Instant startedAt, Instant endedAt) {

        public static CallResponse from(Call call) {
            User agent = call.getAgent();
            return new CallResponse(call.getCallId(), call.getStatus(), call.getEquipmentName(), call.getErrorCode(),
                    call.getSymptom(), Customer.from(call.getCustomer()), agent == null ? null : Agent.from(agent),
                    call.getCreatedAt(), call.getStartedAt(), call.getEndedAt());
        }
    }

    public record Customer(Long id, String username, String clientName, String companyName) {

        static Customer from(User user) {
            return new Customer(user.getId(), user.getUsername(), user.getClientName(), user.getCompanyName());
        }
    }

    public record Agent(Long id, String username, String clientName) {

        static Agent from(User user) {
            return new Agent(user.getId(), user.getUsername(), user.getClientName());
        }
    }

    /** C-3 */
    public record CallDetailResponse(String callId, CallStatus status, String equipmentName, String errorCode,
                                     Instant createdAt, Instant startedAt, Instant endedAt,
                                     List<MessageResponse> messages) {
    }

    /** text는 조회자 언어 (같은 언어로 말했으면 원문, 아니면 번역문) */
    public record MessageResponse(String utteranceId, Role senderRole, String text, Instant timestamp) {

        @Override
        public String toString() {
            return "MessageResponse[utteranceId=" + utteranceId + "]";
        }
    }

    public record PageResponse<T>(List<T> items, int page, int size, long totalElements, int totalPages) {

        public static <E, T> PageResponse<T> of(Page<E> page, Function<E, T> mapper) {
            return new PageResponse<>(page.getContent().stream().map(mapper).toList(), page.getNumber(),
                    page.getSize(), page.getTotalElements(), page.getTotalPages());
        }
    }
}
