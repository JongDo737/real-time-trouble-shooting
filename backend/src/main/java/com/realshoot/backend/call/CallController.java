package com.realshoot.backend.call;

import java.time.LocalDate;

import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.realshoot.backend.call.CallDtos.CallDetailResponse;
import com.realshoot.backend.call.CallDtos.CallResponse;
import com.realshoot.backend.call.CallDtos.CreateCallRequest;
import com.realshoot.backend.call.CallDtos.CreateCallResponse;
import com.realshoot.backend.call.CallDtos.PageResponse;
import com.realshoot.backend.call.CallDtos.UpdateStatusRequest;
import com.realshoot.backend.rag.SolutionResponse;
import com.realshoot.backend.security.AuthUser;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;

/** 역할 검사는 SecurityConfig, 본인 통화 · 받은 상담원 검사는 CallService */
@Tag(name = "통화")
@RestController
@RequestMapping("/api/calls")
@RequiredArgsConstructor
public class CallController {

    private final CallService callService;

    @Operation(summary = "C-1 통화 요청 (USER)")
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CreateCallResponse create(@Parameter(hidden = true) @AuthenticationPrincipal AuthUser user,
                                     @Valid @RequestBody CreateCallRequest request) {
        return callService.create(user, request);
    }

    @Operation(summary = "C-2 통화 목록 (USER = 본인, ADMIN = 전체)")
    @GetMapping
    public PageResponse<CallResponse> list(@Parameter(hidden = true) @AuthenticationPrincipal AuthUser user,
                                           @RequestParam(required = false) String status,
                                           @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
                                           @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
                                           @RequestParam(defaultValue = "0") int page,
                                           @RequestParam(defaultValue = "20") int size) {
        return callService.list(user, status, from, to, page, size);
    }

    @Operation(summary = "C-3 통화 상세 (messages[].text는 조회자 언어)")
    @GetMapping("/{callId}")
    public CallDetailResponse detail(@Parameter(hidden = true) @AuthenticationPrincipal AuthUser user,
                                     @PathVariable String callId) {
        return callService.detail(user, callId);
    }

    @Operation(summary = "C-4 통화 상태 변경 — 받기(CALLING) · 종료(RESOLVED / UNRESOLVED) (ADMIN)")
    @PatchMapping("/{callId}/status")
    public CallResponse changeStatus(@Parameter(hidden = true) @AuthenticationPrincipal AuthUser user,
                                     @PathVariable String callId,
                                     @Valid @RequestBody UpdateStatusRequest request) {
        return callService.changeStatus(user, callId, request.status());
    }

    @Operation(summary = "C-5 해결방법 조회 (받은 상담원만)")
    @GetMapping("/{callId}/solution")
    public SolutionResponse solution(@Parameter(hidden = true) @AuthenticationPrincipal AuthUser user,
                                     @PathVariable String callId) {
        return callService.solution(user, callId);
    }
}
