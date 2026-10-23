package com.realshoot.backend.call;

import java.time.Instant;
import java.util.UUID;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import com.realshoot.backend.auth.User;
import com.realshoot.backend.global.Times;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * calls — 고객 1명 ↔ 응대직원 1명.
 * 내부 PK는 {@code id}, API의 {@code callId}는 {@code calls_id}(UUID).
 * 상태 전환은 동시성 때문에 CallRepository의 조건부 UPDATE로만 한다.
 */
@Entity
@Table(name = "calls", indexes = {
        @Index(name = "idx_calls_user", columnList = "user_id, created_at"),
        @Index(name = "idx_calls_status", columnList = "status, created_at")
})
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Call {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(name = "calls_id", nullable = false, unique = true, updatable = false, length = 36)
    private String callId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User customer;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "admin_id")
    private User agent;

    @Column(name = "equipment_no", length = 100)
    private String equipmentName;

    @Column(name = "error_code", length = 50)
    private String errorCode;

    @Column(name = "issue_text", columnDefinition = "TEXT")
    private String symptom;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private CallStatus status;

    @Column(name = "created_at")
    private Instant createdAt;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "ended_at")
    private Instant endedAt;

    public static Call request(User customer, String equipmentName, String errorCode, String symptom) {
        Call call = new Call();
        call.customer = customer;
        call.equipmentName = equipmentName;
        call.errorCode = errorCode;
        call.symptom = symptom;
        call.status = CallStatus.PENDING;
        return call;
    }

    public boolean isRequestedBy(Long userId) {
        return customer.getId().equals(userId);
    }

    public boolean isAcceptedBy(Long userId) {
        return agent != null && agent.getId().equals(userId);
    }

    @PrePersist
    void prePersist() {
        if (callId == null) {
            callId = UUID.randomUUID().toString();
        }
        if (createdAt == null) {
            createdAt = Times.now();
        }
    }
}
