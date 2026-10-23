import test from 'node:test';
import assert from 'node:assert/strict';
import { createSupportApi } from '../public/js/support-api.js';
import { validateCallInput, validateSignupInput, validateUtterance } from '../public/js/validation.js';

const baseAddress = 'https://api.example.invalid/backend/api/';
const callId = '7c9e6679-7425-40de-944b-e07fc1f90ae7';

function setup(response = () => Response.json({})) {
    const requests = [];
    const api = createSupportApi({
        baseAddress,
        getAccessToken: () => 'test-only-token',
        fetchImpl: async (url, options) => {
            requests.push({ url, ...options });
            return response();
        },
    });
    return { api, requests };
}

test('uses the configured API prefix once and sends Bearer without cookies', async () => {
    const { api, requests } = setup();
    await api.getCalls({ status: ['RESOLVED', 'UNRESOLVED'], page: 0, size: 20 });
    const request = requests[0];
    assert.equal(new URL(request.url).pathname, '/backend/api/calls');
    assert.equal(new URL(request.url).searchParams.get('status'), 'RESOLVED,UNRESOLVED');
    assert.equal(request.headers.Authorization, 'Bearer test-only-token');
    assert.equal(request.credentials, 'omit');
});

test('login sends exactly the documented fields without a previous token', async () => {
    const { api, requests } = setup();
    await api.login({ username: 'test_user', password: 'test-only-password', companyCode: 'not-sent' });
    assert.equal(new URL(requests[0].url).pathname, '/backend/api/auth/login');
    assert.equal(requests[0].headers.Authorization, undefined);
    assert.deepEqual(JSON.parse(requests[0].body), { username: 'test_user', password: 'test-only-password' });
});

test('call creation preserves the agreed request field names', async () => {
    const { api, requests } = setup();
    const input = { equipmentName: 'TEST', errorCode: 'TEST', symptom: 'test-only description' };
    await api.createCall(input);
    assert.deepEqual(JSON.parse(requests[0].body), input);
});

test('accepting, ending and solution queries use the documented call paths', async () => {
    const { api, requests } = setup();
    await api.changeCallStatus(callId, 'CALLING');
    await api.changeCallStatus(callId, 'RESOLVED');
    await api.getSolution(callId);
    assert.equal(requests[0].method, 'PATCH');
    assert.equal(new URL(requests[0].url).pathname, `/backend/api/calls/${callId}/status`);
    assert.deepEqual(JSON.parse(requests[1].body), { status: 'RESOLVED' });
    assert.equal(new URL(requests[2].url).pathname, `/backend/api/calls/${callId}/solution`);
    assert.throws(() => api.changeCallStatus(callId, 'MISSED'));
    assert.throws(() => api.changeCallStatus(callId, 'PENDING'));
});

test('logout accepts an empty 204 response', async () => {
    const { api } = setup(() => new Response(null, { status: 204 }));
    assert.equal(await api.logout(), null);
});

test('API errors retain the status, code and request identifier', async () => {
    const { api } = setup(() => Response.json({
        error: { code: 'ALREADY_ACCEPTED', message: 'already accepted', request_id: 'test-request' },
    }, { status: 409 }));
    await assert.rejects(api.changeCallStatus(callId, 'CALLING'), error =>
        error.status === 409 && error.code === 'ALREADY_ACCEPTED' && error.requestId === 'test-request');
});

test('unauthorized callback runs for protected calls, not invalid login attempts', async () => {
    let count = 0;
    const api = createSupportApi({
        baseAddress,
        getAccessToken: () => 'test-only-token',
        onUnauthorized: () => { count += 1; },
        fetchImpl: async () => Response.json({ error: { code: 'UNAUTHORIZED' } }, { status: 401 }),
    });
    await assert.rejects(api.getCalls());
    assert.equal(count, 1);
    await assert.rejects(api.login({ username: 'test', password: 'test' }));
    assert.equal(count, 1);
});

test('validates only the limits specified in the API document', () => {
    assert.deepEqual(validateCallInput({ equipmentName: 'TEST', errorCode: 'TEST' }), {});
    assert.ok(validateCallInput({ equipmentName: '', errorCode: 'TEST' }).equipmentName);
    assert.ok(validateCallInput({ equipmentName: 'TEST', errorCode: 'TEST', symptom: 'x'.repeat(501) }).symptom);
    assert.deepEqual(validateSignupInput({ client_name: 'Test', company_name: 'Test company', position: 'Engineer', username: 'user_1', password: '12345678' }), {});
    assert.ok(!validateUtterance('  '));
    assert.ok(!validateUtterance('x'.repeat(2001)));
});

test('missing tokens and non-JSON 401 responses both invalidate authentication', async () => {
    for (const token of [null, 'test-only-token']) {
        let invalidated = 0;
        const api = createSupportApi({ baseAddress, getAccessToken: () => token,
            onUnauthorized: () => invalidated++,
            fetchImpl: async () => new Response('Unauthorized', { status: 401 }),
        });
        await assert.rejects(api.getCalls());
        assert.equal(invalidated, 1);
    }
});
