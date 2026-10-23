package com.realshoot.backend.rag;

import com.realshoot.backend.call.Call;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/** translation_manual_refs — 본사 화면에 표시된 매뉴얼 출처 (RAG 응답 sources[]) */
@Entity
@Table(name = "translation_manual_refs", indexes = @Index(name = "idx_manual_refs_call", columnList = "calls_id"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ManualRef {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 컬럼명은 calls_id지만 calls.id(BIGINT)를 가리킨다 (§11) */
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "calls_id", nullable = false)
    private Call call;

    @Column(name = "doc_title", length = 200)
    private String docTitle;

    @Column(name = "page_no")
    private Integer pageNo;

    /** 근거 청크 본문 (RAG sources[].text) */
    @Column(name = "text", columnDefinition = "TEXT")
    private String text;

    private Float score;

    public static ManualRef of(Call call, String docTitle, Integer pageNo, String text, Float score) {
        ManualRef ref = new ManualRef();
        ref.call = call;
        ref.docTitle = docTitle;
        ref.pageNo = pageNo;
        ref.text = text;
        ref.score = score;
        return ref;
    }
}
