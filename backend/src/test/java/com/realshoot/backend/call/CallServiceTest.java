package com.realshoot.backend.call;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import com.realshoot.backend.auth.Role;
import com.realshoot.backend.auth.User;
import com.realshoot.backend.auth.UserRepository;
import com.realshoot.backend.chat.CallEventPublisher;
import com.realshoot.backend.chat.Translation;
import com.realshoot.backend.chat.TranslationRepository;
import com.realshoot.backend.global.error.ApiException;
import com.realshoot.backend.global.error.ErrorCode;
import com.realshoot.backend.rag.ManualRefRepository;
import com.realshoot.backend.rag.RagResultStore;
import com.realshoot.backend.rag.RagService;
import com.realshoot.backend.security.AuthUser;

class CallServiceTest {

    private static final String CALL_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7";
    private static final AuthUser CUSTOMER = new AuthUser(17L, Role.USER);
    private static final AuthUser OTHER_CUSTOMER = new AuthUser(18L, Role.USER);
    private static final AuthUser AGENT = new AuthUser(1L, Role.ADMIN);
    private static final AuthUser OTHER_AGENT = new AuthUser(2L, Role.ADMIN);

    private CallRepository callRepository;
    private CallEventPublisher events;
    private RagService ragService;
    private CallService callService;

    @BeforeEach
    void setUp() {
        callRepository = mock(CallRepository.class);
        events = mock(CallEventPublisher.class);
        ragService = mock(RagService.class);
        callService = new CallService(callRepository, mock(UserRepository.class), mock(TranslationRepository.class),
                mock(ManualRefRepository.class), mock(CallMissedScheduler.class), events, ragService,
                new RagResultStore());
    }

    @Test
    void 받기_성공하면_accepted를_보내고_RAG를_호출한다() {
        givenCalls(call(CallStatus.PENDING, null), call(CallStatus.CALLING, AGENT));
        given(callRepository.accept(eq(CALL_ID), eq(CallStatus.PENDING), eq(CallStatus.CALLING), any(), any()))
                .willReturn(1);

        var response = callService.changeStatus(AGENT, CALL_ID, CallStatus.CALLING);

        assertThat(response.status()).isEqualTo(CallStatus.CALLING);
        verify(events).accepted(CALL_ID);
        verify(ragService).search(any(), eq(AGENT));
        assertThat(callService.solution(AGENT, CALL_ID).status()).isEqualTo("PENDING");
    }

    @Test
    void 다른_상담원이_먼저_받았으면_409_ALREADY_ACCEPTED() {
        givenCalls(call(CallStatus.PENDING, null), call(CallStatus.CALLING, OTHER_AGENT));
        given(callRepository.accept(anyString(), any(), any(), any(), any())).willReturn(0);

        assertError(() -> callService.changeStatus(AGENT, CALL_ID, CallStatus.CALLING), ErrorCode.ALREADY_ACCEPTED);
        verifyNoInteractions(events, ragService);
    }

    @Test
    void 부재중_통화를_받으면_409_INVALID_STATUS_TRANSITION() {
        givenCalls(call(CallStatus.MISSED, null));
        given(callRepository.accept(anyString(), any(), any(), any(), any())).willReturn(0);

        assertError(() -> callService.changeStatus(AGENT, CALL_ID, CallStatus.CALLING),
                ErrorCode.INVALID_STATUS_TRANSITION);
    }

    @Test
    void 받지_않은_상담원의_종료는_403() {
        givenCalls(call(CallStatus.CALLING, AGENT));

        assertError(() -> callService.changeStatus(OTHER_AGENT, CALL_ID, CallStatus.RESOLVED), ErrorCode.FORBIDDEN);
        verify(callRepository, never()).end(anyString(), any(), any(), any(), any());
    }

    @Test
    void PENDING이나_MISSED로는_바꿀_수_없다_422() {
        assertError(() -> callService.changeStatus(AGENT, CALL_ID, CallStatus.MISSED), ErrorCode.VALIDATION_ERROR);
        assertError(() -> callService.changeStatus(AGENT, CALL_ID, CallStatus.PENDING), ErrorCode.VALIDATION_ERROR);
    }

    @Test
    void 고객이_남의_통화를_조회하면_404() {
        givenCalls(call(CallStatus.CALLING, AGENT));

        assertError(() -> callService.detail(OTHER_CUSTOMER, CALL_ID), ErrorCode.NOT_FOUND);
    }

    @Test
    void 받지_않은_상담원의_해결방법_조회는_403() {
        givenCalls(call(CallStatus.CALLING, AGENT));

        assertError(() -> callService.solution(OTHER_AGENT, CALL_ID), ErrorCode.FORBIDDEN);
    }

    @Test
    void 대화_내용은_조회자_언어로_고른다() {
        Translation fromCustomer = Translation.of(null, null, "The fan is not spinning.", "en", "ko");
        fromCustomer.applyTranslation("팬이 돌지 않습니다.", 100);

        assertThat(CallService.textFor(Role.USER.lang(), fromCustomer)).isEqualTo("The fan is not spinning.");
        assertThat(CallService.textFor(Role.ADMIN.lang(), fromCustomer)).isEqualTo("팬이 돌지 않습니다.");
    }

    @Test
    void 페이지_크기는_100까지() {
        assertError(() -> callService.list(CUSTOMER, null, null, null, 0, 101), ErrorCode.VALIDATION_ERROR);
        assertError(() -> callService.list(CUSTOMER, "PENDING,FOO", null, null, 0, 20), ErrorCode.VALIDATION_ERROR);
    }

    private void givenCalls(Call first, Call... rest) {
        given(callRepository.findByCallId(CALL_ID)).willReturn(Optional.of(first),
                java.util.Arrays.stream(rest).map(Optional::of).toArray(Optional[]::new));
    }

    private static Call call(CallStatus status, AuthUser agent) {
        Call call = Call.request(user(CUSTOMER), "CNC-500", "E-1042", null);
        ReflectionTestUtils.setField(call, "id", 1L);
        ReflectionTestUtils.setField(call, "callId", CALL_ID);
        ReflectionTestUtils.setField(call, "status", status);
        if (agent != null) {
            ReflectionTestUtils.setField(call, "agent", user(agent));
        }
        return call;
    }

    private static User user(AuthUser authUser) {
        User user = User.signup("user" + authUser.id(), "hash", "name", "company", "position");
        ReflectionTestUtils.setField(user, "id", authUser.id());
        ReflectionTestUtils.setField(user, "role", authUser.role());
        return user;
    }

    private static void assertError(Runnable action, ErrorCode expected) {
        assertThatThrownBy(action::run)
                .isInstanceOf(ApiException.class)
                .extracting(e -> ((ApiException) e).getErrorCode())
                .isEqualTo(expected);
    }
}
