import { createServiceUrls } from './service-urls.js';

export class ApiError extends Error {
    constructor(message, { status = 0, code = 'NETWORK_ERROR', requestId = null } = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.code = code;
        this.requestId = requestId;
    }
}

// 토큰 저장 방식과 화면 이동은 호출하는 쪽에서 결정합니다.
export function createApiClient({
    baseAddress,
    getAccessToken = () => null,
    onUnauthorized = () => {},
    fetchImpl = globalThis.fetch,
}) {
    const addresses = createServiceUrls({ API_BASE_URL: baseAddress });

    return async function request(path, {
        method = 'GET',
        body,
        query = {},
        authenticated = true,
        signal,
    } = {}) {
        const address = new URL(addresses.api(path));
        for (const [name, value] of Object.entries(query)) {
            if (value !== undefined && value !== null && value !== '') {
                address.searchParams.set(name, String(value));
            }
        }

        const headers = { Accept: 'application/json' };
        if (authenticated) {
            const token = getAccessToken();
            if (!token) {
                const error = new ApiError('로그인이 필요합니다.', { code: 'UNAUTHORIZED', status: 401 });
                onUnauthorized(error);
                throw error;
            }
            headers.Authorization = `Bearer ${token}`;
        }
        if (body !== undefined) headers['Content-Type'] = 'application/json';

        let response;
        try {
            response = await fetchImpl(address.href, {
                method,
                headers,
                body: body === undefined ? undefined : JSON.stringify(body),
                credentials: 'omit',
                signal,
            });
        } catch (error) {
            if (error.name === 'AbortError') throw error;
            throw new ApiError('서버에 연결하지 못했습니다.');
        }

        let result = null;
        if (response.status !== 204) {
            const text = await response.text();
            if (text) {
                try {
                    result = JSON.parse(text);
                } catch {
                    const error = new ApiError('서버 응답 형식을 확인해 주세요.', {
                        status: response.status,
                        code: 'INVALID_RESPONSE',
                    });
                    if (response.status === 401 && authenticated) onUnauthorized(error);
                    throw error;
                }
            }
        }

        if (!response.ok) {
            const details = result?.error;
            const error = new ApiError(details?.message || '요청을 처리하지 못했습니다.', {
                status: response.status,
                code: details?.code || 'UNKNOWN_ERROR',
                requestId: details?.request_id || null,
            });
            if (response.status === 401 && authenticated) onUnauthorized(error);
            throw error;
        }
        return result;
    };
}
