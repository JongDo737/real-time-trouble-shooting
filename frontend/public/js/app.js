import { config, isPreview } from './config.js';
import { createSessionStore } from './session.js';
import { createSupportController } from './support-controller.js';
import { createViews } from './views.js';
import { openDialog } from './dom.js';
import { formatTimeAgo } from './utc.js';

// 클릭에는 강조선을 숨기고 Tab 이동에는 포커스를 표시합니다.
document.addEventListener('pointerdown', () => {
    document.documentElement.dataset.focusMethod = 'pointer';
}, { capture: true });
document.addEventListener('keydown', event => {
    if (event.key === 'Tab') document.documentElement.dataset.focusMethod = 'keyboard';
}, { capture: true });

const app = document.querySelector('#app');
const screen = document.createElement('div');
app.append(screen);
const dialogMarkup = new WeakMap();
const sessions = createSessionStore(window.sessionStorage);
const controller = createSupportController({
    config, isPreview, sessions, storage: window.sessionStorage, onChange: render,
});
const state = controller.state;
const translate = (ko, en) => state.language === 'ko' ? ko : en;

function canUseBackend(name) {
    if (isPreview || state.busy || !config.API_BASE_URL) return false;
    if (name === 'connectCall') return state.role === 'AGENT' && state.data.selected?.status === 'PENDING';
    if (name === 'endCall') return state.role === 'AGENT' && state.data.selected?.status === 'CALLING';
    return !!controller.user;
}

function previewScreen() {
    if (['login', 'signup', 'request'].includes(state.view)) return state.view === 'signup' ? 'login' : state.view;
    if (state.view === 'call') return state.role === 'AGENT' ? 'call' : 'customer-call';
    return state.role === 'AGENT' ? 'agent' : 'customer';
}

function screens() {
    return createViews({
        ...state, config, isPreview, canUseBackend,
        getPreviewScreen: previewScreen, userProfile: controller.profile,
    });
}

function render() {
    const focused = document.activeElement;
    const detailOpen = document.querySelector('#detail-dialog[open]');
    const dialogs = [...app.querySelectorAll('.notes-dialog[open], .end-dialog[open]')];
    const transcript = app.querySelector('.transcript');
    const scrollTop = transcript?.scrollTop ?? 0;
    const followLatest = !transcript || transcript.scrollHeight - scrollTop - transcript.clientHeight < 24;
    document.documentElement.lang = state.language;
    document.title = translate('릴슈 · 장비 지원', 'Rilshu · Equipment support');
    const view = screens();
    const content = ['login', 'signup'].includes(state.view)
        ? view.login() : state.view === 'call' ? view.callScreen() : view.workspace();
    // 모달은 화면 갱신과 분리해 입력과 키보드 포커스를 유지합니다.
    screen.innerHTML = view.previewBar() + content;
    document.querySelector('#announcement').textContent = state.notice;
    if (state.view !== 'call') dialogs.forEach(dialog => dialog.close());
    if (detailOpen) {
        if (state.view === 'dashboard' && state.data.selected) {
            const content = view.detailContent();
            if (dialogMarkup.get(detailOpen) !== content) {
                const historyOpen = detailOpen.querySelector('.previous-conversation')?.open;
                detailOpen.innerHTML = content;
                dialogMarkup.set(detailOpen, content);
                const history = detailOpen.querySelector('.previous-conversation');
                if (history) history.open = Boolean(historyOpen);
            }
        } else detailOpen.close();
    }
    if (focused?.isConnected) focused.focus({ preventScroll: true });
    else if (focused?.id) document.getElementById(focused.id)?.focus({ preventScroll: true });
    const updatedTranscript = app.querySelector('.transcript');
    if (updatedTranscript) updatedTranscript.scrollTop = followLatest ? updatedTranscript.scrollHeight : scrollTop;
}

function showDialog(className, titleId, content, id) {
    const dialog = document.createElement('dialog');
    dialog.className = className;
    if (id) dialog.id = id;
    dialog.setAttribute('aria-labelledby', titleId);
    dialog.innerHTML = content;
    dialogMarkup.set(dialog, content);
    openDialog(app, dialog);
    if (id === 'end-dialog') dialog.addEventListener('close', () => controller.resumeMicrophone(), { once: true });
    return dialog;
}

function openDetail() {
    const callId = state.data.selected?.callId;
    const dialog = showDialog('detail-dialog', 'detail-title', screens().detailContent(), 'detail-dialog');
    // 목록이 자동 갱신되어도 현재 DOM의 상세 버튼으로 포커스를 돌려줍니다.
    dialog.addEventListener('close', () => {
        app.querySelector(`[data-detail="${CSS.escape(callId || '')}"]`)?.focus();
    }, { once: true });
    return dialog;
}

function openNotes() {
    const dialog = showDialog('notes-dialog', 'notes-title', screens().notesContent());
    dialog.querySelector('textarea').focus();
}

function focusErrors() {
    const field = Object.keys(state.errors)[0];
    const first = field === 'credentials' ? 'password' : field;
    const inputName = first === 'equipmentName' ? 'equipment' : first === 'symptom' ? 'description' : first;
    if (inputName) document.querySelector(`[name="${inputName}"]`)?.focus();
}

app.addEventListener('input', event => {
    if (event.target.id === 'notes-text') {
        state.notes = event.target.value;
        return;
    }
    const form = event.target.closest('form');
    if (form?.id === 'request-form') state.draft = Object.fromEntries(new FormData(form));
    if (form?.id === 'signup-form') state.signupDraft = Object.fromEntries(new FormData(form));
    if (form?.id === 'login-form') state.authDraft = { username: form.elements.username.value };
});

app.addEventListener('change', async event => {
    if (event.target.id === 'preview-screen') {
        const key = event.target.value;
        state.role = key.startsWith('customer') || key === 'request' ? 'CUSTOMER' : 'AGENT';
        state.language = state.role === 'CUSTOMER' ? 'en' : 'ko';
        state.view = key === 'login' ? 'login' : key.includes('call') ? 'call' : key === 'request' ? 'request' : 'dashboard';
        state.notes = '';
        state.notice = '';
        state.errors = {};
        state.data.selected = null;
        state.data.connection = 'disconnected';
        render();
        if (key.includes('detail')) openDetail();
    }
    if (event.target.id === 'status-filter') {
        await controller.setFilter(event.target.value);
        document.querySelector('#status-filter')?.focus();
    }
});

app.addEventListener('click', async event => {
    const detail = event.target.closest('[data-detail]');
    if (detail && !state.busy) {
        await controller.loadDetail(detail.dataset.detail);
        if (state.data.selected) openDetail();
        return;
    }
    const button = event.target.closest('[data-action]');
    if (!button || button.disabled || state.busy) return;
    switch (button.dataset.action) {
        case 'language':
            state.language = state.language === 'ko' ? 'en' : 'ko';
            render();
            break;
        case 'signup-screen':
            state.view = 'signup';
            state.notice = '';
            state.errors = {};
            render();
            break;
        case 'login-screen':
            state.view = 'login';
            state.signupDraft = {};
            state.errors = {};
            state.notice = '';
            render();
            break;
        case 'request':
            state.view = 'request';
            state.draft = {};
            state.errors = {};
            render();
            document.querySelector('#request-title')?.setAttribute('tabindex', '-1');
            document.querySelector('#request-title')?.focus();
            break;
        case 'cancel-request':
            state.view = 'dashboard';
            state.draft = {};
            state.errors = {};
            render();
            break;
        case 'close-detail':
            document.querySelector('#detail-dialog')?.close();
            break;
        case 'notes':
            openNotes();
            break;
        case 'microphone':
            controller.toggleMicrophone();
            break;
        case 'close-notes':
            document.querySelector('.notes-dialog')?.close();
            break;
        case 'connect':
            document.querySelector('#detail-dialog')?.close();
            await controller.acceptCall();
            break;
        case 'end':
            controller.stopMicrophone();
            showDialog('end-dialog', 'end-title', screens().endCallContent(), 'end-dialog');
            break;
        case 'close-end':
            document.querySelector('#end-dialog')?.close();
            break;
        case 'select-page':
            await controller.setPage(Number(button.dataset.page));
            break;
        case 'previous-page':
            await controller.setPage(state.data.page - 1);
            break;
        case 'next-page':
            await controller.setPage(state.data.page + 1);
            break;
        case 'logout':
            await controller.logout();
            break;
    }
});

app.addEventListener('submit', async event => {
    event.preventDefault();
    if (isPreview || state.busy) return;
    const input = Object.fromEntries(new FormData(event.target));
    switch (event.target.id) {
        case 'login-form':
            await controller.login(input);
            break;
        case 'signup-form':
            await controller.signup(input);
            break;
        case 'request-form':
            await controller.createCall(input);
            break;
        case 'end-call-form':
            document.querySelector('#end-dialog')?.close();
            await controller.endCall(input.status);
            break;
    }
    focusErrors();
});

const timeRefresh = setInterval(() => {
    document.querySelectorAll('[data-received-at]').forEach(element => {
        element.textContent = formatTimeAgo(element.dataset.receivedAt, state.language);
    });
}, 60000);
window.addEventListener('pagehide', () => {
    clearInterval(timeRefresh);
    controller.dispose();
});
document.addEventListener('visibilitychange', () => {
    if (document.hidden) controller.stopMicrophone();
    else controller.resumeMicrophone();
});
await controller.initialize();
