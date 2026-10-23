package com.realshoot.backend.chat;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import com.realshoot.backend.auth.Role;
import com.realshoot.backend.auth.UserRepository;
import com.realshoot.backend.call.Call;
import com.realshoot.backend.call.CallRepository;
import com.realshoot.backend.call.CallStatus;
import com.realshoot.backend.chat.CallEventPublisher.TranslationMessage;
import com.realshoot.backend.rag.RagClient;
import com.realshoot.backend.rag.RagDtos.ContextItem;
import com.realshoot.backend.rag.RagDtos.TranslateRequest;
import com.realshoot.backend.rag.RagDtos.TranslateResponse;
import com.realshoot.backend.security.AuthUser;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/** W-2 말하기: 저장 → /translate 동기 호출 → 번역문만 채널로 (backend-api.md §5, §7.2) */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatService {

    static final int MAX_TEXT_LENGTH = 2000;
    private static final int CONTEXT_SIZE = 5;

    private final CallRepository callRepository;
    private final UserRepository userRepository;
    private final TranslationRepository translationRepository;
    private final RagClient ragClient;
    private final CallEventPublisher events;

    /** 보낸 사람이 참여자가 아니거나 통화가 CALLING이 아니거나 text가 잘못되면 무시 */
    public void handle(AuthUser sender, String callId, String text) {
        if (text == null || text.isBlank() || text.length() > MAX_TEXT_LENGTH) {
            return;
        }
        Call call = callRepository.findByCallId(callId).orElse(null);
        if (call == null || call.getStatus() != CallStatus.CALLING) {
            return;
        }
        boolean participant = sender.isAdmin() ? call.isAcceptedBy(sender.id()) : call.isRequestedBy(sender.id());
        if (!participant) {
            return;
        }

        Role role = sender.role();
        String targetLang = role.counterpart().lang();
        List<ContextItem> context = recentContext(call.getId());

        Translation utterance = translationRepository.save(
                Translation.of(call, userRepository.getReferenceById(sender.id()), text, role.lang(), targetLang));

        long startedAt = System.nanoTime();
        TranslateResponse result = translate(call, utterance, role, context, sender);
        int latencyMs = (int) ((System.nanoTime() - startedAt) / 1_000_000);
        String translatedText = result == null ? null : result.translatedText();
        translationRepository.applyTranslation(utterance.getId(), translatedText, latencyMs);

        events.translation(new TranslationMessage("translation", callId, String.valueOf(utterance.getId()), role,
                translatedText, targetLang, result != null && result.needsReview(), utterance.getCreatedAt()));
    }

    private TranslateResponse translate(Call call, Translation utterance, Role role, List<ContextItem> context,
                                        AuthUser sender) {
        TranslateRequest request = new TranslateRequest(call.getCallId(), "u-" + utterance.getId(),
                utterance.getOriginalText(), role.lang(), role.counterpart().lang(), role.name(),
                call.getEquipmentName(), call.getErrorCode(), context);
        try {
            return ragClient.translate(request, sender);
        } catch (RuntimeException e) {
            // 발화 내용은 남기지 않음
            log.warn("번역 실패 callId={} utteranceId={} cause={}", call.getCallId(), utterance.getId(),
                    RagClient.describe(e));
            return null;
        }
    }

    /** 같은 통화의 최근 5발화 (오래된 순, 원문) */
    private List<ContextItem> recentContext(Long callPk) {
        List<ContextItem> items = new ArrayList<>();
        translationRepository.findRecentWithSender(callPk, PageRequest.of(0, CONTEXT_SIZE))
                .forEach(t -> items.add(new ContextItem(t.getSender().getRole().name(), t.getOriginalText())));
        Collections.reverse(items);
        return items;
    }
}
