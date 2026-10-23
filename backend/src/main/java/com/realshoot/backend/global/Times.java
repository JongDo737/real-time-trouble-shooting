package com.realshoot.backend.global;

import java.time.Instant;
import java.time.temporal.ChronoUnit;

/** 저장 · 응답 시각은 UTC, 밀리초까지 (예: 2026-10-23T09:11:02.120Z) */
public final class Times {

    private Times() {
    }

    public static Instant now() {
        return Instant.now().truncatedTo(ChronoUnit.MILLIS);
    }
}
