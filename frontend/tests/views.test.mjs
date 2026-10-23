import test from 'node:test';
import assert from 'node:assert/strict';
import { createViews } from '../public/js/views.js';
import { createState } from '../public/js/model.js';

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

test('agent list filter excludes calling and detail does not allow arbitrary status changes', () => {
    const screens = createViews(screenContext());
    const list = screens.workspace();
    assert.ok(!list.includes('value="CALLING"'));
    assert.ok(list.includes('value="PENDING"'));
    assert.ok(!screens.detailContent().includes('detail-status'));
});

test('customer call does not render RAG or claim a connection', () => {
    const screen = createViews(screenContext('CUSTOMER')).callScreen();
    assert.ok(!screen.includes('rag-panel'));
    assert.ok(screen.includes('Not connected'));
    assert.ok(!screen.includes('connected.svg'));
});

test('external names and translations are escaped and timestamps are UTC', () => {
    const context = screenContext();
    context.data.translations = [{
        speaker: '<script>unsafe</script>',
        text: '<img src=x onerror=alert(1)>',
        time: '2026-10-23T10:30:00+09:00',
    }];
    const screen = createViews(context).callScreen();
    assert.ok(!screen.includes('<script>unsafe</script>'));
    assert.ok(screen.includes('&lt;img'));
    assert.ok(screen.includes('2026-10-23 01:30:00 UTC'));
});

test('request draft is preserved without enabling unconnected submission', () => {
    const context = screenContext('CUSTOMER');
    context.view = 'request';
    context.draft = { equipment: 'TEST-ONLY', description: 'draft text' };
    const screen = createViews(context).workspace();
    assert.ok(screen.includes('value="TEST-ONLY"'));
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
