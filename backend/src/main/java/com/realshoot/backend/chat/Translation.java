package com.realshoot.backend.chat;

import java.time.Instant;

import com.realshoot.backend.auth.User;
import com.realshoot.backend.call.Call;
import com.realshoot.backend.global.Times;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
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

/** translations — 통화 중 오간 문장 1건. 원문은 여기에만 저장하고 채널로 보내지 않는다 */
@Entity
@Table(name = "translations", indexes = @Index(name = "idx_translations_call", columnList = "call_id, id"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Translation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "call_id", nullable = false)
    private Call call;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "sender_id", nullable = false)
    private User sender;

    @Column(name = "original_text", nullable = false, columnDefinition = "TEXT")
    private String originalText;

    @Column(name = "original_lang", nullable = false, columnDefinition = "CHAR(2)")
    private String originalLang;

    @Column(name = "translated_text", columnDefinition = "TEXT")
    private String translatedText;

    @Column(name = "translated_lang", nullable = false, columnDefinition = "CHAR(2)")
    private String translatedLang;

    @Column(name = "latency_ms")
    private Integer latencyMs;

    @Column(name = "created_at", columnDefinition = "DATETIME(3)")
    private Instant createdAt;

    public static Translation of(Call call, User sender, String originalText, String originalLang,
                                 String translatedLang) {
        Translation t = new Translation();
        t.call = call;
        t.sender = sender;
        t.originalText = originalText;
        t.originalLang = originalLang;
        t.translatedLang = translatedLang;
        return t;
    }

    /** 번역 실패면 translatedText = null */
    public void applyTranslation(String translatedText, int latencyMs) {
        this.translatedText = translatedText;
        this.latencyMs = latencyMs;
    }

    @PrePersist
    void prePersist() {
        if (createdAt == null) {
            createdAt = Times.now();
        }
    }
}
