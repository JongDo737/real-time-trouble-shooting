import { summaryStatuses } from './model.js';

export function mapCall(call, previous = {}) {
    return {
        ...previous,
        callId: call.callId,
        id: call.id ?? previous.id ?? null,
        status: call.status,
        createdAt: call.createdAt ?? previous.createdAt ?? null,
        equipment: call.equipmentName,
        errorCode: call.errorCode,
        description: call.symptom ?? previous.description ?? '',
        company: call.customer?.companyName ?? previous.company ?? '',
        // 이름이 없으면 로그인 아이디로 대신 표시하지 않습니다.
        requester: call.customer?.clientName ?? previous.requester ?? '',
        requesterAccount: call.customer?.username ?? previous.requesterAccount ?? '',
        agentAccount: call.agent?.username ?? previous.agentAccount ?? '',
        position: call.customer?.position ?? previous.position ?? '',
        messages: call.messages ?? [],
    };
}

export async function getCallSummary(api, signal) {
    const [all, ...results] = await Promise.all([
        api.getCalls({ page: 0, size: 1 }, { signal }),
        ...summaryStatuses.map(status => api.getCalls({ status, page: 0, size: 1 }, { signal })),
    ]);
    return {
        total: all.totalElements,
        counts: Object.fromEntries(summaryStatuses.map((status, index) => [status, results[index].totalElements])),
    };
}

export function mapMessage(message, myRole) {
    const mine = message.senderRole === myRole;
    return {
        id: message.utteranceId,
        speaker: mine ? (myRole === 'ADMIN' ? '나' : 'Me') : (myRole === 'ADMIN' ? '고객' : 'Support agent'),
        roleLabel: myRole === 'ADMIN'
            ? (message.senderRole === 'ADMIN' ? '상담원' : '고객')
            : (message.senderRole === 'ADMIN' ? 'Support agent' : 'Customer'),
        text: message.text ?? (myRole === 'ADMIN' ? '(번역 실패)' : '(Translation failed)'),
        time: message.timestamp,
        needsReview: message.needsReview === true || message.text == null,
    };
}
