import test from 'node:test';
import assert from 'node:assert/strict';
import { createViews } from '../public/js/views.js';
import { createState } from '../public/js/model.js';
import { formatLocalTimestamp } from '../public/js/utc.js';

function screenContext(role = 'AGENT') {
    return {
        data: createState(),
        role,
        language: role === 'AGENT' ? 'ko' : 'en',
        view: 'dashboard',
        filter: '',
        notes: '',
        draft: {},
        notice: '',
        busy: false,
        canUseBackend: () => false,
        getPreviewScreen: () => 'agent',
        config: {},
        isPreview: true,
    };
}

test('signup uses application validation so trimming runs before username checks', () => {
    const context = { ...screenContext(), view: 'signup' };
    assert.match(createViews(context).login(), /<form[^>]*id="signup-form"[^>]*novalidate/);
    assert.doesNotMatch(createViews({ ...context, view: 'login' }).login(), /<form[^>]*novalidate/);
});

test('signup fields, drafts and accessible errors use camelCase consistently', () => {
    const screen = createViews({
        ...screenContext(), view: 'signup',
        signupDraft: { clientName: '실제 이름', companyName: 'Test Company' },
        errors: { clientName: '이름을 확인해 주세요.', companyName: '회사명을 확인해 주세요.' },
    }).login();
    for (const [field, value] of [['clientName', '실제 이름'], ['companyName', 'Test Company']]) {
        assert.ok(screen.includes(`name="${field}"`));
        assert.ok(screen.includes(`value="${value}"`));
        assert.ok(screen.includes(`aria-describedby="${field}-error" aria-invalid="true"`));
        assert.ok(screen.includes(`id="${field}-error"`));
    }
});

test('agent list permits all documented statuses while detail only exposes supported actions', () => {
    const screens = createViews(screenContext());
    const list = screens.workspace();
    assert.ok(list.includes('value="CALLING"'));
    assert.ok(list.includes('value="PENDING"'));
    assert.ok(!screens.detailContent().includes('detail-status'));
});

test('customer call does not render RAG or claim a connection', () => {
    const screen = createViews(screenContext('CUSTOMER')).callScreen();
    assert.ok(!screen.includes('rag-panel'));
    assert.ok(screen.includes('Not connected'));
    assert.ok(!screen.includes('connected.svg'));
});

test('minimal documented customer records display the account and UUID across screens', () => {
    const context = screenContext('CUSTOMER');
    const callId = '7c9e6679-7425-40de-944b-e07fc1f90ae7';
    context.data.selected = { callId, requesterAccount: 'branch_kim', company: 'ACME', messages: [] };
    const detail = createViews(context).detailContent();
    assert.ok(detail.includes('Contact account'));
    assert.ok(detail.includes('branch_kim'));
    const call = createViews(context).callScreen();
    assert.ok(call.includes(callId));
    assert.ok(call.includes('Your support agent'));
    assert.ok(!call.includes('Minseo Kim'));
    context.view = 'waiting';
    assert.ok(createViews(context).workspace().includes(`Request ID ${callId}`));
});

test('backend UUID and raw detail messages render with the viewer role', () => {
    const context = screenContext();
    context.data.selected = {
        callId: '7c9e6679-7425-40de-944b-e07fc1f90ae7', status: 'RESOLVED',
        messages: [{ utteranceId: '1', senderRole: 'USER', text: null, timestamp: '2026-10-23T04:00:00Z' }],
    };
    const detail = createViews(context).detailContent();
    assert.ok(detail.includes(context.data.selected.callId));
    assert.ok(detail.includes('(번역 실패)'));
    assert.ok(detail.includes('번역 확인 필요'));
    assert.ok(detail.includes('고객'));
    context.data.inquiries = [context.data.selected];
    const workspace = createViews(context).workspace();
    assert.ok(workspace.includes(`<td class="request-id">${context.data.selected.callId}</td>`));
});

test('stored RAG sources with no answer display a completed result', () => {
    const context = screenContext();
    context.data.solution = {
        status: 'found', answer: null, sources: [{ doc: 'Manual', page: 7, section: null }],
        needsReview: true, handoff: true, riskLevel: 'CRITICAL', riskReason: '<b>내파</b>',
    };
    const screen = createViews(context).callScreen();
    assert.ok(screen.includes('관련 매뉴얼을 찾았습니다.'));
    assert.ok(!screen.includes('관련 매뉴얼을 찾고 있습니다.'));
    assert.ok(screen.includes('Manual · p. 7'));
    assert.ok(screen.includes('해결방법을 찾지 못했습니다. 엔지니어 연결이 필요합니다.'));
    assert.ok(screen.includes('class="review-marker risk-critical"'));
    assert.ok(screen.includes('CRITICAL · &lt;b&gt;내파&lt;/b&gt;'));
    assert.ok(!screen.includes('<b>내파</b>'));
});

test('external names and translations are escaped and timestamps use local time', () => {
    const context = screenContext();
    context.data.translations = [{
        speaker: '<script>unsafe</script>',
        text: '<img src=x onerror=alert(1)>',
        time: '2026-10-23T10:30:00+09:00',
    }];
    const screen = createViews(context).callScreen();
    assert.ok(!screen.includes('<script>unsafe</script>'));
    assert.ok(screen.includes('&lt;img'));
    assert.ok(screen.includes(formatLocalTimestamp('2026-10-23T10:30:00+09:00')));
});

test('request draft is preserved without enabling unconnected submission', () => {
    const context = screenContext('CUSTOMER');
    context.view = 'request';
    context.draft = { equipment: 'AE Cesar 1312', errorCode: 'ALARM-402', description: 'draft text' };
    const screen = createViews(context).workspace();
    assert.match(screen, /name="equipment" value="AE Cesar 1312" checked/);
    assert.match(screen, /name="errorCode" value="ALARM-402" checked/);
    assert.match(screen, /name="errorCode" value="ERR-MATCH-TUNE"/);
    assert.ok(!screen.includes('name="errorCode" value="TEMP-COMM-FAIL"'));
    assert.ok(screen.includes('draft text'));
    assert.match(screen, /type="submit"\s+disabled/);
});

test('pagination follows server page counts and marks the selected page', () => {
    const context = screenContext();
    context.isPreview = false;
    Object.assign(context.data, { page: 6, totalPages: 12, inquiries: [] });
    const screen = createViews(context).workspace();
    assert.match(screen, /data-page="6"[^>]*aria-current="page"/);
    assert.match(screen, /data-page="4"/);
    assert.match(screen, /data-page="8"/);
    assert.doesNotMatch(screen, /data-page="9"/);
    context.data.totalPages = 2;
    context.data.page = 0;
    const shorter = createViews(context).workspace();
    assert.match(shorter, /data-page="1"/);
    assert.doesNotMatch(shorter, /data-page="2"/);
});

test('login error is below the password, accessible, and localized', () => {
    const context = screenContext();
    context.view = 'login';
    context.errors = { credentials: true };
    for (const [language, message] of [['ko', '아이디 또는 비밀번호가 올바르지 않습니다.'], ['en', 'Incorrect username or password.']]) {
        context.language = language;
        const screen = createViews(context).login();
        assert.ok(screen.indexOf('name="password"') < screen.indexOf('id="login-error"'));
        assert.ok(screen.indexOf('id="login-error"') < screen.indexOf('type="submit"'));
        assert.match(screen, /aria-describedby="login-error" aria-invalid="true"/);
        assert.ok(screen.includes(message));
        assert.match(screen, /id="login-error" role="alert"/);
    }
});


test('both roles retain voice controls and conversation without a text composer', () => {
    for (const role of ['AGENT', 'CUSTOMER']) {
        const context = screenContext(role);
        context.data.connection = 'connected';
        const screen = createViews(context).callScreen();
        assert.doesNotMatch(screen, /message-form|message-text|send-message|<textarea/);
        assert.match(screen, /id="microphone-toggle"/);
        assert.match(screen, /role="log"/);
    }
});

test('microphone controls are localized, escaped and available only on a supported connected call', () => {
    for (const role of ['AGENT', 'CUSTOMER']) {
        const context = { ...screenContext(role), isPreview: false, canUseBackend: () => true,
            speech: { supported: true, secureContext: true, status: 'listening', interim: '<unsafe>', lastTranscript: 'Final phrase', error: '' } };
        context.data.connection = 'connected';
        let screen = createViews(context).callScreen();
        assert.match(screen, /id="microphone-toggle"[^>]*aria-pressed="true"[^>]* >|id="microphone-toggle"[^>]*aria-pressed="true"[^>]*>/);
        assert.ok(screen.includes(role === 'AGENT' ? '음소거' : 'Mute microphone'));
        assert.ok(screen.includes('&lt;unsafe&gt;'));
        assert.ok(!screen.includes('<unsafe>'));
        context.data.connection = 'reconnecting';
        assert.match(createViews(context).callScreen(), /id="microphone-toggle"[^>]*disabled/);
        context.data.connection = 'connected';
        context.speech = { ...context.speech, supported: false, status: 'idle', interim: '' };
        screen = createViews(context).callScreen();
        assert.match(screen, /id="microphone-toggle"[^>]*disabled/);
        assert.ok(screen.includes(role === 'AGENT' ? '지원 브라우저' : 'supported browser'));
    }
});
