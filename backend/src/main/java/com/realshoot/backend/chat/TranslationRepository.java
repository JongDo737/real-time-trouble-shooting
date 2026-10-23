package com.realshoot.backend.chat;

import java.util.List;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.transaction.annotation.Transactional;

public interface TranslationRepository extends JpaRepository<Translation, Long> {

    @Query("select t from Translation t join fetch t.sender where t.call.id = :callPk order by t.id")
    List<Translation> findAllWithSender(Long callPk);

    /** 최근 발화부터 (번역 context용) */
    @Query("select t from Translation t join fetch t.sender where t.call.id = :callPk order by t.id desc")
    List<Translation> findRecentWithSender(Long callPk, Pageable pageable);

    @Transactional
    @Modifying
    @Query("update Translation t set t.translatedText = :translatedText, t.latencyMs = :latencyMs where t.id = :id")
    int applyTranslation(Long id, String translatedText, int latencyMs);
}
