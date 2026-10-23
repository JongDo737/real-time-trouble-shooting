export const statuses = ['PENDING', 'CALLING', 'MISSED', 'RESOLVED', 'UNRESOLVED'];

// 목록 필터에서는 통화 중을 제외합니다.
export const inquiryFilterStatuses = statuses.filter(status => status !== 'CALLING');
export const summaryStatuses = [...inquiryFilterStatuses];

export const profiles = Object.freeze({
    AGENT: Object.freeze({
        name: '김민서',
        englishName: 'Minseo Kim',
        company: '릴슈 한국 본사',
        photo: './assets/agent.png',
    }),
    CUSTOMER: Object.freeze({
        name: 'Alex Harper',
        englishName: 'Alex Harper',
        company: 'Atlas Semiconductor',
        photo: './assets/customer.png',
    }),
});

export const statusLabels = {
    ko: {
        PENDING: '수신 대기',
        CALLING: '통화 중',
        MISSED: '부재중',
        RESOLVED: '해결 완료',
        UNRESOLVED: '미해결',
    },
    en: {
        PENDING: 'Pending',
        CALLING: 'Calling',
        MISSED: 'Missed',
        RESOLVED: 'Resolved',
        UNRESOLVED: 'Unresolved',
    },
};

const htmlEntities = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
};

export function escapeHTML(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => htmlEntities[character]);
}

export function createState() {
    return {
        inquiries: null,
        summary: null,
        selected: null,
        translations: [],
        connection: 'disconnected',
        page: 0,
        size: 20,
        totalPages: 0,
        solution: null,
    };
}
