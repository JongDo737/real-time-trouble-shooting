import test from 'node:test';
import assert from 'node:assert/strict';
import { createSessionStore } from '../public/js/session.js';
import { createCallChannel } from '../public/js/call-channel.js';
import { createSupportController } from '../public/js/support-controller.js';
import { createSupportApi } from '../public/js/support-api.js';
import { mapCall, mapMessage, getCallSummary } from '../public/js/call-data.js';
import { formatTimeAgo } from '../public/js/utc.js';

const callId = '7c9e6679-7425-40de-944b-e07fc1f90ae7';
function memoryStorage() {
    const values = new Map();
    return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}
function loginResponse(role = 'USER') {
    return { accessToken: 'test-only-token', expiresIn: 3600, user: { id: 17, username: 'test-user', role, clientName: '실제 이름', companyName: 'Test company' } };
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

class FakeRecognition {
    static last;
    constructor() { FakeRecognition.last = this; this.results = []; }
    start() { this.onstart?.(); }
    stop() { this.onend?.(); }
    abort() {}
    speak(text) {
        this.results.push(Object.assign([{ transcript: text }], { isFinal: true }));
        this.onresult?.({ results: this.results });
    }
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
    const mapped = mapCall({ id: 52, callId, status: 'PENDING', customer: { username: 'login-id', clientName: '실제 이름', companyName: 'Test company', position: 'Engineer' } });
    assert.equal(mapped.id, 52); assert.equal(mapped.callId, callId);
    assert.equal(mapped.requester, '실제 이름');
    assert.equal(mapped.company, 'Test company');
    const detail = mapCall({ callId, status: 'PENDING' }, mapped);
    assert.equal(detail.requester, '실제 이름');
    assert.equal(detail.company, 'Test company');
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

function makeController(role = 'USER', overrides = {}, dependencies = {}) {
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
        Recognition: FakeRecognition,
        ...dependencies,
    });
    return { controller, sessions, api };
}

for (const role of ['USER', 'ADMIN']) {
    test(`${role} microphone starts automatically on connection and publishes text through the existing STOMP channel`, async () => {
        class SpeechRecognition {
            static last;
            constructor() { SpeechRecognition.last = this; }
            start() { this.onstart(); }
            stop() { this.stopped = true; }
            abort() { this.aborted = true; }
        }
        const { controller } = makeController(role, {
            createCall: async () => ({ callId }),
            getCall: async () => ({ callId, status: 'CALLING', messages: [] }),
            changeCallStatus: async () => ({ callId, status: 'CALLING' }),
            getSolution: async () => ({ status: 'found', answer: 'Test solution', sources: [] }),
        }, { Recognition: SpeechRecognition });
        try {
            await controller.login({ username: 'test', password: 'test-only' });
            assert.equal(controller.toggleMicrophone(), undefined);
            if (role === 'USER') await controller.createCall({ equipment: 'Tool', errorCode: 'E1' });
            else {
                controller.state.data.selected = { callId, status: 'PENDING' };
                await controller.acceptCall();
            }
            await new Promise(resolve => setImmediate(resolve));
            assert.equal(controller.state.speech.status, 'listening');
            const engine = SpeechRecognition.last;
            assert.equal(engine.lang, role === 'ADMIN' ? 'ko-KR' : 'en-US');
            const recognized = Object.assign([{ transcript: role === 'ADMIN' ? '팬을 확인하세요.' : 'The fan stopped.' }], { isFinal: true });
            engine.onresult({ results: [recognized] });
            assert.equal(FakeClient.last.sent.destination, `/app/calls/${callId}/message`);
            assert.deepEqual(JSON.parse(FakeClient.last.sent.body), { text: recognized[0].transcript });
            assert.equal(controller.state.data.translations.at(-1).text, recognized[0].transcript);
            const lateResult = engine.onresult;
            FakeClient.last.options.onWebSocketClose();
            assert.ok(engine.aborted);
            assert.equal(controller.state.speech.status, 'idle');
            lateResult({ results: [recognized, recognized] });
            assert.equal(controller.state.data.translations.length, 1);
        } finally { controller.dispose(); }
    });
}

test('manual mute survives updates and microphone denial does not cause repeated permission requests', async () => {
    class Recognition {
        static starts = 0;
        static last;
        constructor() { Recognition.last = this; }
        start() { Recognition.starts++; this.onstart(); }
        stop() { this.onend?.(); }
        abort() {}
    }
    const { controller } = makeController('USER', {
        createCall: async () => ({ callId }),
        getCall: async () => ({ callId, status: 'CALLING', messages: [] }),
    }, { Recognition });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        await controller.createCall({ equipment: 'Tool', errorCode: 'E1' });
        assert.equal(Recognition.starts, 1);
        controller.toggleMicrophone();
        controller.resumeMicrophone();
        assert.equal(Recognition.starts, 1);
        controller.toggleMicrophone();
        assert.equal(Recognition.starts, 2);
        Recognition.last.onerror({ error: 'not-allowed' });
        controller.resumeMicrophone();
        assert.equal(Recognition.starts, 2);
        assert.equal(controller.state.speech.error, 'not-allowed');
    } finally { controller.dispose(); }
});

test('socket errors keep a CALLING REST response disconnected until STOMP reconnects', async () => {
    const { controller } = makeController('USER', {
        createCall: async () => ({ callId }),
        getCall: async () => ({ callId, status: 'CALLING', messages: [] }),
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        await controller.createCall({ equipment: 'Tool', errorCode: 'E1' });
        const client = FakeClient.last;
        assert.equal(controller.state.data.connection, 'connected');
        await client.options.onStompError();
        assert.equal(controller.state.data.connection, 'reconnecting');
        assert.equal(controller.state.speech.status, 'idle');
        assert.equal(client.sent, undefined);
        client.options.onConnect();
        await new Promise(resolve => setImmediate(resolve));
        assert.equal(controller.state.data.connection, 'connected');
        FakeRecognition.last.speak('Reconnected');
        assert.deepEqual(JSON.parse(client.sent.body), { text: 'Reconnected' });
    } finally { controller.dispose(); }
});

test('disconnect aborts pending call reconciliation and a late response cannot restore connection', async () => {
    let pending, requestSignal;
    const { controller } = makeController('USER', {
        createCall: async () => ({ callId }),
        getCall: (_, { signal }) => {
            requestSignal = signal;
            return new Promise(resolve => { pending = resolve; });
        },
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        await controller.createCall({ equipment: 'Tool', errorCode: 'E1' });
        FakeClient.last.options.onWebSocketClose();
        assert.equal(requestSignal.aborted, true);
        pending({ callId, status: 'CALLING', messages: [] });
        await new Promise(resolve => setImmediate(resolve));
        assert.equal(controller.state.data.connection, 'reconnecting');
        assert.equal(FakeClient.last.sent, undefined);
    } finally { controller.dispose(); }
});

test('local speaker role follows the account role independently of interface language', async () => {
    for (const role of ['USER', 'ADMIN']) {
        const { controller } = makeController(role, {
            createCall: async () => ({ callId }),
            changeCallStatus: async () => ({ callId, status: 'CALLING' }),
            getCall: async () => ({ callId, status: 'CALLING', messages: [] }),
            getSolution: async () => ({ status: 'found', sources: [] }),
        });
        try {
            await controller.login({ username: 'test', password: 'test-only' });
            if (role === 'USER') await controller.createCall({ equipment: 'Tool', errorCode: 'E1' });
            else {
                controller.state.data.selected = { callId, status: 'PENDING' };
                await controller.acceptCall();
            }
            for (const language of ['ko', 'en']) {
                controller.state.language = language;
                FakeRecognition.last.speak('Test');
                assert.equal(controller.state.data.translations.at(-1).roleLabel,
                    role === 'ADMIN' ? (language === 'ko' ? '상담원' : 'Support agent') : (language === 'ko' ? '고객' : 'Customer'));
            }
        } finally { controller.dispose(); }
    }
});

test('login uses real role and forces the role language', async () => {
    const { controller } = makeController();
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        assert.equal(controller.state.role, 'CUSTOMER'); assert.equal(controller.state.language, 'en');
        assert.equal(controller.profile.name, '실제 이름');
        assert.equal(controller.profile.englishName, '실제 이름');
        assert.equal(controller.profile.company, 'Test company');
    } finally { controller.dispose(); }
});

test('documented minimal login response displays account and company without sample identity', async () => {
    const { controller } = makeController('USER', { login: async () => ({
        accessToken: 'test-only-token', tokenType: 'Bearer', expiresIn: 3600,
        user: { id: 17, username: 'branch_kim', role: 'USER', companyName: 'ACME Semiconductor US' },
    }) });
    try {
        await controller.login({ username: 'branch_kim', password: 'test-only-password' });
        assert.equal(controller.profile.name, 'branch_kim');
        assert.equal(controller.profile.englishName, 'branch_kim');
        assert.equal(controller.profile.company, 'ACME Semiconductor US');
        assert.equal(controller.profile.position, '');
        assert.equal(controller.state.language, 'en');
    } finally { controller.dispose(); }
});

test('signup server validation highlights camelCase fields and keeps the signup screen', async () => {
    const { controller } = makeController('USER', { signup: async () => {
        throw Object.assign(new Error('companyName: 공백일 수 없습니다, clientName: 공백일 수 없습니다'), { status: 422, code: 'VALIDATION_ERROR' });
    } });
    try {
        controller.state.view = 'signup';
        await controller.signup({ clientName: 'Name', companyName: 'Company', position: 'Engineer', username: 'test_user', password: 'test-only-password' });
        assert.equal(controller.state.view, 'signup');
        assert.ok(controller.state.errors.clientName);
        assert.ok(controller.state.errors.companyName);
        assert.equal(controller.state.errors.company_name, undefined);
        assert.equal(controller.state.signupDraft.password, '');
    } finally { controller.dispose(); }
});

test('duplicate signup username is attached to the username field', async () => {
    const { controller } = makeController('USER', { signup: async () => {
        throw Object.assign(new Error(), { status: 409, code: 'DUPLICATE_USERNAME' });
    } });
    try {
        controller.state.view = 'signup';
        await controller.signup({ clientName: 'Name', companyName: 'Company', position: 'Engineer', username: 'test_user', password: 'test-only-password' });
        assert.equal(controller.state.view, 'signup');
        assert.ok(controller.state.errors.username);
    } finally { controller.dispose(); }
});

test('login restores a customer active call from backend list without a stored call ID', async () => {
    const { controller } = makeController('USER', {
        getCalls: async ({ status }) => ({
            items: status === 'PENDING,CALLING' ? [{ callId, status: 'PENDING', equipmentName: 'Tool', errorCode: 'E1', symptom: 'Issue', customer: { clientName: 'Contact', companyName: 'Company' } }] : [],
            totalPages: 1,
        }),
        getCall: async () => ({ callId, status: 'PENDING', equipmentName: 'Tool', errorCode: 'E1', messages: [] }),
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        assert.equal(controller.state.view, 'waiting');
        assert.equal(controller.state.data.selected.requester, 'Contact');
        assert.equal(controller.state.data.selected.company, 'Company');
        assert.equal(controller.state.data.selected.description, 'Issue');
        assert.equal(FakeClient.last.destination, `/topic/calls/${callId}`);
    } finally { controller.dispose(); }
});

test('session restoration finds only the accepted agent call across active-call pages', async () => {
    const pages = [];
    const { controller, sessions } = makeController('ADMIN', {
        getCalls: async ({ status, page }) => {
            if (status !== 'CALLING') return { items: [], totalPages: 0, totalElements: 0 };
            pages.push(page);
            return { items: [{ callId, status: 'CALLING', agent: { id: page === 0 ? 99 : 17 }, customer: { clientName: 'Contact' }, symptom: 'Issue' }], totalPages: 2 };
        },
        getCall: async () => ({ callId, status: 'CALLING', messages: [] }),
        getSolution: async () => ({ status: 'found', answer: 'Solution', sources: [], needsReview: false, handoff: false }),
    });
    try {
        sessions.save(loginResponse('ADMIN'));
        await controller.initialize();
        assert.deepEqual(pages, [0, 1]);
        assert.equal(controller.state.view, 'call');
        assert.equal(controller.state.data.selected.requester, 'Contact');
        assert.equal(controller.state.data.selected.description, 'Issue');
        assert.equal(FakeClient.last.destination, `/topic/calls/${callId}`);
    } finally { controller.dispose(); }
});

test('socket subscription error reconciles a missed end event through REST', async () => {
    let status = 'CALLING';
    const { controller } = makeController('USER', {
        getCalls: async ({ status: filter }) => ({ items: filter === 'PENDING,CALLING' ? [{ callId, status: 'CALLING' }] : [], totalPages: 1 }),
        getCall: async () => ({ callId, status, messages: [] }),
    });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        const client = FakeClient.last;
        status = 'RESOLVED';
        client.options.onStompError();
        await new Promise(resolve => setImmediate(resolve));
        assert.equal(controller.state.view, 'dashboard');
        assert.equal(controller.state.data.selected.status, 'RESOLVED');
        assert.ok(client.deactivated);
        assert.equal(controller.state.notice, 'The call has ended.');
    } finally { controller.dispose(); }
});

test('null history translations are visible failures needing review', () => {
    const mapped = mapMessage({ utteranceId: '1', senderRole: 'USER', text: null, timestamp: '2026-10-23T04:00:00Z' }, 'ADMIN');
    assert.equal(mapped.text, '(번역 실패)');
    assert.equal(mapped.needsReview, true);
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
        FakeRecognition.last.speak('Spoken message');
        assert.deepEqual(JSON.parse(FakeClient.last.sent.body), { text: 'Spoken message' });
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
        const input = { clientName: 'Test person', companyName: 'Test company', position: 'Engineer', username: 'test_user', password: 'test-only-password' };
        await controller.signup(input);
        assert.deepEqual(received, input);
        assert.equal(received.companyCode, undefined);
        assert.equal(controller.state.view, 'login');
    } finally { controller.dispose(); }
});

test('signup trims fields before validation and sends backend camelCase keys', async () => {
    const storage = memoryStorage();
    const requests = [];
    const controller = createSupportController({
        config: { API_BASE_URL: 'https://example.invalid/backend/api/', MOCK_ROLE: 'AGENT' },
        isPreview: false, storage, sessions: createSessionStore(storage),
        apiFactory: options => createSupportApi({ ...options, fetchImpl: async (url, options) => {
            requests.push({ url, ...options });
            return new Response(null, { status: 201 });
        } }),
    });
    try {
        await controller.signup({
            clientName: ` ${'가'.repeat(20)} `,
            companyName: '  Test Company  ', position: '  Senior Engineer  ',
            username: ' test_user ', password: ' test-only-password ',
        });
        assert.equal(requests.length, 1);
        assert.equal(requests[0].url, 'https://example.invalid/backend/api/auth/signup');
        assert.deepEqual(JSON.parse(requests[0].body), {
            clientName: '가'.repeat(20), companyName: 'Test Company', position: 'Senior Engineer',
            username: 'test_user', password: ' test-only-password ',
        });
        assert.equal(controller.state.view, 'login');
    } finally { controller.dispose(); }
});

test('signup rejects whitespace-only fields before making a request', async () => {
    let requests = 0;
    const { controller } = makeController('USER', { signup: async () => { requests++; } });
    try {
        const valid = { clientName: 'Name', companyName: 'Company', position: 'Engineer', username: 'test_user', password: 'test-only-password' };
        for (const field of ['clientName', 'companyName', 'position', 'username']) {
            await controller.signup({ ...valid, [field]: ' \t ' });
            assert.ok(controller.state.errors[field]);
            assert.equal(controller.state.signupDraft[field], '');
            assert.equal(controller.state.signupDraft.password, '');
        }
        assert.equal(requests, 0);
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

test('only recognized speech is sent and incoming translations remain visible', async () => {
    const { controller } = makeController('USER', { createCall: async () => ({ callId }) });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        await controller.createCall({ equipment: 'TEST', errorCode: 'TEST', description: '' });
        const client = FakeClient.last;
        assert.equal(controller.sendText, undefined);
        assert.equal('messageDraft' in controller.state, false);
        assert.equal(client.sent, undefined);
        client.receive({ type: 'accepted', callId });
        FakeRecognition.last.speak('  The fan stopped.  ');
        assert.deepEqual(JSON.parse(client.sent.body), { text: 'The fan stopped.' });
        assert.equal(controller.state.data.translations.at(-1).text, 'The fan stopped.');
        client.receive({ type: 'translation', callId, senderRole: 'ADMIN', utteranceId: 'reply', translatedText: 'Check the cooling fan.', timestamp: '2026-10-23T07:00:00Z' });
        assert.equal(controller.state.data.translations.at(-1).text, 'Check the cooling fan.');
    } finally { controller.dispose(); }
});

test('speech publication failure stops recognition and logout clears the conversation', async () => {
    const { controller } = makeController('USER', { createCall: async () => ({ callId }) });
    try {
        await controller.login({ username: 'test', password: 'test-only' });
        await controller.createCall({ equipment: 'TEST', errorCode: 'TEST' });
        const client = FakeClient.last;
        client.receive({ type: 'accepted', callId });
        client.publish = () => { throw new Error('disconnected'); };
        FakeRecognition.last.speak('The fan stopped.');
        assert.equal(controller.state.speech.error, 'send-failed');
        assert.deepEqual(controller.state.data.translations, []);
        await controller.logout();
        assert.equal(controller.state.view, 'login');
        assert.deepEqual(controller.state.data.translations, []);
    } finally { controller.dispose(); }
});
