package com.realshoot.backend.call;

import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.transaction.annotation.Transactional;

import com.realshoot.backend.auth.User;

public interface CallRepository extends JpaRepository<Call, Long>, JpaSpecificationExecutor<Call> {

    @EntityGraph(attributePaths = {"customer", "agent"})
    Optional<Call> findByCallId(String callId);

    @Override
    @EntityGraph(attributePaths = {"customer", "agent"})
    Page<Call> findAll(Specification<Call> spec, Pageable pageable);

    boolean existsByCustomer_IdAndStatusIn(Long customerId, Collection<CallStatus> statuses);

    @Query("select c.callId from Call c where c.status = :status and c.createdAt < :before")
    List<String> findCallIdsByStatusCreatedBefore(CallStatus status, Instant before);

    /** 받기: 먼저 누른 1명만 성공 (영향 행 0이면 실패) */
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("""
            update Call c set c.status = :to, c.agent = :agent, c.startedAt = :now
            where c.callId = :callId and c.status = :from
            """)
    int accept(String callId, CallStatus from, CallStatus to, User agent, Instant now);

    /** 종료: 받은 상담원 본인 + CALLING일 때만 */
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("""
            update Call c set c.status = :to, c.endedAt = :now
            where c.callId = :callId and c.status = :from and c.agent.id = :agentId
            """)
    int end(String callId, CallStatus from, CallStatus to, Long agentId, Instant now);

    /** 부재중: PENDING일 때만 */
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("""
            update Call c set c.status = :to, c.endedAt = :now
            where c.callId = :callId and c.status = :from
            """)
    int expire(String callId, CallStatus from, CallStatus to, Instant now);
}
