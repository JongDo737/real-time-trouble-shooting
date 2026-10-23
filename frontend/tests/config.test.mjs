import test from 'node:test';
import assert from 'node:assert/strict';
import { createSupportApi } from '../public/js/support-api.js';

let configVersion = 0;
async function loadConfig(raw, origin) {
    const previous = globalThis.window;
    globalThis.window = { RILSHU_CONFIG: raw, location: { origin, pathname: '/' } };
    try {
        return (await import(`../public/js/config.js?test=${++configVersion}`)).config;
    } finally {
        if (previous === undefined) delete globalThis.window;
        else globalThis.window = previous;
    }
}

for (const protocol of ['http', 'https']) {
    test(`Docker relative config sends login and signup requests over ${protocol}`, async () => {
        const origin = `${protocol}://support.example.invalid:8443`;
        const config = await loadConfig({
            API_BASE_URL: '/backend/api/', WS_BASE_URL: '/backend/ws/', STT_URL: '/voice/stt/',
        }, origin);
        assert.equal(config.WS_BASE_URL, `${protocol === 'https' ? 'wss' : 'ws'}://support.example.invalid:8443/backend/ws/`);
        assert.equal(config.STT_URL, `${origin}/voice/stt/`);
        const requests = [];
        const api = createSupportApi({
            baseAddress: config.API_BASE_URL,
            fetchImpl: async (url, options) => {
                requests.push({ url, ...options });
                return Response.json({});
            },
        });
        const credentials = { username: 'test_user', password: 'test-only-password' };
        const signup = { ...credentials, clientName: 'Test', companyName: 'Company', position: 'Engineer' };
        await api.login(credentials);
        await api.signup(signup);
        assert.deepEqual(requests.map(request => request.url), [
            `${origin}/backend/api/auth/login`, `${origin}/backend/api/auth/signup`,
        ]);
        for (const [index, body] of [credentials, signup].entries()) {
            assert.equal(requests[index].method, 'POST');
            assert.equal(requests[index].headers.Authorization, undefined);
            assert.deepEqual(JSON.parse(requests[index].body), body);
        }
    });
}

test('explicit external API and WebSocket addresses stay unchanged', async () => {
    const raw = {
        API_BASE_URL: 'https://api.example.invalid/api/',
        WS_BASE_URL: 'wss://socket.example.invalid/ws/',
    };
    const config = await loadConfig(raw, 'https://support.example.invalid');
    assert.equal(config.API_BASE_URL, raw.API_BASE_URL);
    assert.equal(config.WS_BASE_URL, raw.WS_BASE_URL);
});

test('missing service addresses remain unconfigured', async () => {
    const config = await loadConfig({}, 'https://support.example.invalid');
    assert.equal(config.API_BASE_URL, '');
    assert.equal(config.WS_BASE_URL, '');
});
