import { createApiClient } from './api-client.js';

function callPath(callId) {
    if (typeof callId !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(callId)) {
        throw new Error('UUID 형식의 통화 ID가 필요합니다.');
    }
    return `calls/${encodeURIComponent(callId)}`;
}

// front-api v1.1에 정의된 REST 경로만 사용합니다.
export function createSupportApi(options) {
    const request = createApiClient(options);

    return Object.freeze({
        signup({ clientName, companyName, position, username, password }, { signal } = {}) {
            return request('auth/signup', {
                method: 'POST',
                authenticated: false,
                body: { clientName, companyName, position, username, password },
                signal,
            });
        },
        login({ username, password }, { signal } = {}) {
            return request('auth/login', {
                method: 'POST',
                authenticated: false,
                body: { username, password },
                signal,
            });
        },
        logout({ signal } = {}) {
            return request('auth/logout', { method: 'POST', signal });
        },
        createCall({ equipmentName, errorCode, symptom }, { signal } = {}) {
            return request('calls', {
                method: 'POST',
                body: { equipmentName, errorCode, symptom },
                signal,
            });
        },
        getCalls({ status, from, to, page, size } = {}, { signal } = {}) {
            return request('calls', {
                query: {
                    status: Array.isArray(status) ? status.join(',') : status,
                    from,
                    to,
                    page,
                    size,
                },
                signal,
            });
        },
        getCall(callId, { signal } = {}) {
            return request(callPath(callId), { signal });
        },
        changeCallStatus(callId, status, { signal } = {}) {
            if (!['CALLING', 'RESOLVED', 'UNRESOLVED'].includes(status)) {
                throw new Error('클라이언트에서 변경할 수 없는 통화 상태입니다.');
            }
            return request(`${callPath(callId)}/status`, {
                method: 'PATCH',
                body: { status },
                signal,
            });
        },
        getSolution(callId, { signal } = {}) {
            return request(`${callPath(callId)}/solution`, { signal });
        },
    });
}
