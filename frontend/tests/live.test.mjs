import test from 'node:test';
import assert from 'node:assert/strict';
import { createSessionStore } from '../public/js/session.js';
import { createCallChannel } from '../public/js/call-channel.js';
import { createSupportController } from '../public/js/support-controller.js';
import { mapCall, getCallSummary } from '../public/js/call-data.js';
import { formatTimeAgo } from '../public/js/utc.js';

const callId = '7c9e6679-7425-40de-944b-e07fc1f90ae7';
function memoryStorage() {
    const values = new Map();
    return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}
function loginResponse(role = 'USER') {
    return { accessToken: 'test-only-token', expiresIn: 3600, user: { id: 17, username: 'test-user', role, client_name: '실제 이름', companyName: 'Test company' } };
}

class FakeClient {
    static last;
    constructor(options) { this.options = options; this.connected = false; FakeClient.last = this; }
    activate() { this.options.beforeConnect?.(); this.connected = true; this.options.onConnect(); }
    subscribe(destination, listener) { this.destination = destination; this.listener = listener; return { unsubscribe: () => { this.unsubscribed = true; } }; }
    publish(message) { this.sent = message; }
    deactivate() { this.connected = false; this.deactivated = true; return Promise.resolve(); }
    receive(message) { this.listener({ body: JSON.stringify(message) }); }
}

test('session expires by expiresIn and never stores passwords', () => {
    const storage = memoryStorage(); let now = 1000;
    const sessions = createSessionStore(storage, () => now);
    sessions.save(loginResponse());
    assert.equal(sessions.read().user.role, 'USER');
    assert.equal(sessions.read().password, undefined);
    now += 3600001;
    assert.equal(sessions.read(), null);
});

test('queue number and UUID stay separate; username is never a real name', () => {
    const mapped = mapCall({ id: 52, callId, status: 'PENDING', customer: { username: 'login-id', client_name: '실제 이름', position: 'Engineer' } });
    assert.equal(mapped.id, 52); assert.equal(mapped.callId, callId);
    assert.equal(mapped.requester, '실제 이름');
    const missing = mapCall({ callId, customer: { username: 'login-id' } });
    assert.equal(missing.id, null); assert.equal(missing.requester, '');
});

test('summary reads database-backed totalElements rather than counting a page', async () => {
    const counts = { PENDING: 23, MISSED: 4, RESOLVED: 82, UNRESOLVED: 12 };
    const summary = await getCallSummary({ getCalls: async query => ({ totalElements: query.status ? counts[query.status] : 122 }) });
    assert.equal(summary.total, 122); assert.equal(summary.counts.PENDING, 23);
});

test('STOMP uses subscription destinations, deduplicates and ignores own echo', () => {
    const received = [];
    const channel = createCallChannel({ Client: FakeClient, brokerURL: 'ws://example.invalid/ws', callId,
        getAccessToken: () => 'test-only-token', myRole: 'USER', onMessage: message => received.push(message) });
    channel.start();
    const client = FakeClient.last;
    assert.equal(client.connectHeaders.Authorization, 'Bearer test-only-token');
    assert.equal(client.destination, `/topic/calls/${callId}`);
    const message = { type: 'translation', callId, senderRole: 'ADMIN', utteranceId: 'u1', translatedText: 'hello' };
    client.receive(message); client.receive(message); client.receive({ ...message, utteranceId: 'u2', senderRole: 'USER' });
    assert.equal(received.length, 1);
    channel.send('recognized text');
    assert.equal(client.sent.destination, `/app/calls/${callId}/message`);
    assert.deepEqual(JSON.parse(client.sent.body), { text: 'recognized text' });
    channel.stop(); assert.ok(client.deactivated); assert.ok(client.unsubscribed);
});

function makeController(role = 'USER', overrides = {}) {
    const storage = memoryStorage();
    const sessions = createSessionStore(storage);
    const api = {
        login: async () => loginResponse(role),
        getCalls: async () => ({ items: [], page: 0, size: 20, totalElements: 0, totalPages: 0 }),
        getCall: async () => ({ id: 52, callId, status: 'PENDING', messages: [] }),
        logout: async () => {},
        ...overrides,
    };
    const controller = createSupportController({
        config: { API_BASE_URL: 'https://example.invalid/api/', WS_BASE_URL: 'ws://example.invalid/ws', MOCK_ROLE: 'AGENT' },
        isPreview: false, sessions, storage, onChange: () => {}, loadClient: async () => FakeClient,
        apiFactory: () => api,
    });
    return { controller, sessions, api };
}

test('login uses real role and forces the role language', async () => {
    const { controller } = makeController();
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        assert.equal(controller.state.role, 'CUSTOMER'); assert.equal(controller.state.language, 'en');
        assert.equal(controller.profile.name, '실제 이름');
    } finally { controller.dispose(); }
});

test('logout clears the local session even when the server fails', async () => {
    const { controller, sessions } = makeController('ADMIN', { logout: async () => { throw new Error('offline'); } });
    try {
        await controller.login({ username: 'test', password: 'test-only' }); await controller.logout();
        assert.equal(sessions.read(), null); assert.equal(controller.state.view, 'login');
    } finally { controller.dispose(); }
});

test('request uses REST before subscribing, then shows waiting', async () => {
    const steps = [];
    const { controller } = makeController('USER', {
        createCall: async payload => { steps.push(payload); return { callId }; },
        getCall: async () => ({ id: 52, callId, status: 'PENDING', messages: [] }),
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        await controller.createCall({ equipment: 'TEST', errorCode: 'TEST', description: 'symptom' });
        assert.deepEqual(steps[0], { equipmentName: 'TEST', errorCode: 'TEST', symptom: 'symptom' });
        assert.equal(controller.state.view, 'waiting');
        FakeClient.last.receive({ type: 'accepted', callId });
        assert.equal(controller.state.view, 'call');
        assert.ok(controller.sendRecognizedText('already recognized text'));
        assert.deepEqual(JSON.parse(FakeClient.last.sent.body), { text: 'already recognized text' });
        await controller.endCall('RESOLVED'); // 고객은 통화를 종료할 수 없습니다.
        assert.equal(controller.state.view, 'call');
    } finally { controller.dispose(); }
});

test('elapsed time uses UTC instants and never stores a derived database value', () => {
    const now = Date.parse('2026-10-23T04:03:00Z');
    assert.equal(formatTimeAgo('2026-10-23T04:00:00Z', 'ko', now), '3분 전');
    assert.equal(formatTimeAgo('2026-10-23T13:00:00+09:00', 'en', now), '3 minutes ago');
    assert.equal(formatTimeAgo(null, 'ko', now), '—');
});

test('signup sends actual name, company and position without a company code', async () => {
    let received;
    const { controller } = makeController('USER', { signup: async input => { received = input; } });
    try {
        const input = { client_name: 'Test person', company_name: 'Test company', position: 'Engineer', username: 'test_user', password: 'test-only-password' };
        await controller.signup(input);
        assert.deepEqual(received, input);
        assert.equal(received.companyCode, undefined);
        assert.equal(controller.state.view, 'login');
    } finally { controller.dispose(); }
});

test('admin chooses an end result and the channel is deactivated', async () => {
    let ended;
    let currentStatus = 'PENDING';
    const { controller } = makeController('ADMIN', {
        changeCallStatus: async (id, status) => {
            currentStatus = status;
            if (status !== 'CALLING') ended = status;
            return { id: 52, callId: id, status };
        },
        getCall: async () => ({ id: 52, callId, status: currentStatus, messages: [] }),
        getSolution: async () => ({ status: 'found', answer: 'test-only answer', sources: [] }),
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        controller.state.data.selected = mapCall({ id: 52, callId, status: 'PENDING' });
        await controller.acceptCall();
        await controller.endCall('UNRESOLVED');
        assert.equal(ended, 'UNRESOLVED');
        assert.equal(controller.state.view, 'dashboard');
        assert.equal(controller.state.notes, '');
        assert.ok(FakeClient.last.deactivated);
    } finally { controller.dispose(); }
});

test('invalid session expiry is rejected instead of keeping a stale login', () => {
    const storage = memoryStorage();
    const sessions = createSessionStore(storage);
    storage.setItem('rilshu.session', JSON.stringify({ ...loginResponse(), expiresAt: 'invalid' }));
    assert.equal(sessions.read(), null);
    assert.throws(() => sessions.save({ ...loginResponse(), expiresIn: Infinity }));
});

test('a failed detail refresh does not lose a newly created call or its subscription', async () => {
    const { controller } = makeController('USER', {
        createCall: async () => ({ callId }),
        getCall: async () => { throw new Error('temporary failure'); },
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        await controller.createCall({ equipment: 'TEST', errorCode: 'E1' });
        assert.equal(controller.state.view, 'waiting');
        assert.equal(controller.state.data.selected.callId, callId);
        assert.equal(FakeClient.last.destination, `/topic/calls/${callId}`);
        FakeClient.last.receive({ type: 'accepted', callId });
        assert.equal(controller.state.view, 'call');
    } finally { controller.dispose(); }
});

test('late detail response cannot restore a logged out screen', async () => {
    let resolveDetail;
    const { controller, sessions } = makeController('USER', {
        getCall: () => new Promise(resolve => { resolveDetail = resolve; }),
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        const pending = controller.loadDetail(callId);
        await controller.logout();
        resolveDetail({ callId, status: 'PENDING' });
        await pending;
        assert.equal(sessions.read(), null);
        assert.equal(controller.state.view, 'login');
        assert.equal(controller.state.data.selected, null);
    } finally { controller.dispose(); }
});

test('disposed login response cannot create a new session', async () => {
    let resolveLogin;
    const { controller, sessions } = makeController('USER', {
        login: () => new Promise(resolve => { resolveLogin = resolve; }),
    });
    const pending = controller.login({ username: 'test', password: 'test-only' });
    controller.dispose();
    resolveLogin(loginResponse());
    await pending;
    assert.equal(sessions.read(), null);
});

test('closed channel ignores queued messages and null frames', () => {
    let count = 0;
    const channel = createCallChannel({ Client: FakeClient, brokerURL: 'ws://example.invalid/ws', callId,
        getAccessToken: () => 'test-only-token', myRole: 'USER', onMessage: () => count++ });
    channel.start();
    FakeClient.last.receive(null);
    channel.stop();
    FakeClient.last.receive({ type: 'accepted', callId });
    assert.equal(count, 0);
});

test('pagination follows added data and recovers when the current page disappears', async () => {
    let totalPages = 1;
    const { controller } = makeController('USER', {
        getCalls: async ({ page }) => ({ items: [], page, size: 20, totalElements: totalPages * 20, totalPages }),
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        assert.equal(controller.state.data.totalPages, 1);
        totalPages = 3;
        await controller.refreshList();
        await controller.setPage(2);
        assert.equal(controller.state.data.page, 2);
        totalPages = 1;
        await controller.refreshList();
        assert.equal(controller.state.data.page, 0);
        assert.equal(controller.state.data.totalPages, 1);
    } finally { controller.dispose(); }
});

test('invalid credentials appear as a field error and clear on a successful retry', async () => {
    let invalid = true;
    const { controller, sessions } = makeController('USER', {
        login: async () => {
            if (invalid) throw Object.assign(new Error('wrong credentials'), { code: 'INVALID_CREDENTIALS' });
            return loginResponse();
        },
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        assert.equal(controller.state.errors.credentials, true);
        assert.equal(controller.state.notice, '');
        assert.equal(sessions.read(), null);
        invalid = false;
        await controller.login({ username: 'test', password: 'correct-test-only' });
        assert.deepEqual(controller.state.errors, {});
        assert.equal(controller.state.view, 'dashboard');
    } finally { controller.dispose(); }
});

test('preview filter resets the page and renders once without a backend request', async () => {
    let renders = 0;
    const storage = memoryStorage();
    const controller = createSupportController({
        config: { MOCK_ROLE: 'AGENT' },
        isPreview: true,
        sessions: createSessionStore(storage),
        storage,
        onChange: () => { renders += 1; },
        apiFactory: () => ({ getCalls: () => { throw new Error('Preview must not request data'); } }),
    });
    try {
        controller.state.data.page = 3;
        await controller.setFilter('RESOLVED');
        assert.equal(controller.state.filter, 'RESOLVED');
        assert.equal(controller.state.data.page, 0);
        assert.equal(renders, 1);
    } finally {
        controller.dispose();
    }
});

test('socket shutdown failures do not interrupt logout or data cleanup', async () => {
    for (const shutdown of [
        () => { throw new Error('Socket already closed'); },
        () => Promise.reject(new Error('Socket already closed')),
    ]) {
        const { controller, sessions } = makeController('USER', {
            createCall: async () => ({ callId }),
        });
        try {
            await controller.login({ username: 'test', password: 'test-only' });
            await controller.createCall({ equipment: 'TEST', errorCode: 'TEST', description: '' });
            FakeClient.last.deactivate = shutdown;
            await controller.logout();
            assert.equal(sessions.read(), null);
            assert.equal(controller.state.view, 'login');
            assert.equal(controller.state.data.selected, null);
            assert.deepEqual(controller.state.data.translations, []);
            assert.equal(controller.state.data.connection, 'disconnected');
        } finally {
            controller.dispose();
        }
    }
});
