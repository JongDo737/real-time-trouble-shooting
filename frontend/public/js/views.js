import {
    profiles,
    inquiryFilterStatuses,
    summaryStatuses,
    statusLabels,
    escapeHTML,
} from './model.js';
import { toUtcIso, formatLocalTimestamp, formatTimeAgo } from './utc.js';
import { html } from './dom.js';
import { mapMessage } from './call-data.js';

// 화면을 만들고, 사용자 입력은 app.js에서 처리합니다.
export function createViews(context) {
    const {
        data,
        role,
        language,
        view,
        filter,
        notes,
        draft,
        notice,
        busy,
        canUseBackend,
        getPreviewScreen,
        config,
        isPreview,
        userProfile,
        errors = {},
        authDraft = {},
        signupDraft = {},
        speech = { supported: false, secureContext: true, status: 'idle', interim: '', lastTranscript: '', error: '' },
    } = context;
    const translate = (ko, en) => language === 'ko' ? ko : en;
    const formatValue = value => value === undefined || value === null || value === '' ? '—' : escapeHTML(value);
    const renderIcon = (file, size = 24) => `<img src="./assets/${file}.svg" width="${size}" height="${size}" alt="">`;
    const renderLogo = () => '<img class="logo" src="./assets/logo.png" width="150" height="62" alt="릴슈">';
    const disabledAttribute = name => canUseBackend(name) && !busy ? '' : 'disabled';
    const getStatusLabel = value => statusLabels[language][value] || formatValue(value);
    const getProfile = () => userProfile || profiles[role];
    const renderNotice = () => notice ? `<p class="notice" role="status">${escapeHTML(notice)}</p>` : '';
    function renderStatusOptions(choices, selectedStatus) {
        return choices.map(status => `<option value="${status}" ${selectedStatus === status ? 'selected' : ''}>${getStatusLabel(status)}</option>`).join('');
    }
    function previewBar() {
        if (!isPreview) return '';
        return html`<details class="preview-tools">
        <summary>화면 미리보기</summary>
        <nav class="preview-bar" aria-label="UI preview">
        <strong>화면 선택</strong>
    <label>화면 <select id="preview-screen">
    ${[
            ['agent', '상담원 대시보드'],
            ['customer', 'Customer dashboard'],
            ['request', 'New request'],
            ['detail', '상담원 상세'],
            ['customer-detail', 'Customer detail'],
            ['call', '상담원 통화'],
            ['customer-call', 'Customer call'],
            ['login', '로그인']
        ].map(([value, label]) => `<option value="${value}" ${getPreviewScreen() === value ? 'selected' : ''}>${label}</option>`).join('')}
    </select>
        </label>
        </nav>
        </details>`;
    }
    function fieldError(field) {
        if (!errors[field]) return '';
        const english = {
            clientName: 'Enter a name of up to 20 characters.',
            companyName: 'Enter a company name of up to 50 characters.',
            position: 'Enter a position of up to 30 characters.',
            '이미 사용 중인 아이디입니다.': 'This username is already in use.',
            'This username is already in use.': 'This username is already in use.',
            'Please check this field.': 'Please check this field.',
            username: 'Use 4–50 letters, numbers or underscores.',
            password: 'Use 8–64 characters.',
            equipmentName: 'Enter an equipment name of 1–100 characters.',
            errorCode: 'Enter an error code of 1–50 characters.',
            symptom: 'Use no more than 500 characters.',
        };
        return `<p class="field-error" id="${field}-error">${escapeHTML(language === 'ko' ? errors[field] : english[errors[field]] || english[field] || 'Please check this field.')}</p>`;
    }

    function login() {
        const signup = view === 'signup';
        const fields = signup ? signupDraft : authDraft;
        const loginFailed = !signup && errors.credentials === true;
        return html`
            <main id="main" class="login-page ${signup ? 'signup-page' : ''}">
                <div class="login-shell">
                    <section class="login-content">
                        <div class="login-brand">${renderLogo()}${languageControl()}</div>
                        <div class="login-form">
                            <h1>${signup ? translate('회원가입', 'Sign up') : translate('릴슈에 로그인', 'Log in to Rilshu')}</h1>
                            <p class="muted">${signup ? translate('고객사 계정을 등록해 주세요.', 'Create your customer account.') : translate('반도체 장비 지원을 한곳에서 시작하세요.', 'Connect with your equipment support team.')}</p>
                            ${renderNotice()}
                            <form id="${signup ? 'signup-form' : 'login-form'}" class="login-fields ${signup ? 'signup-fields' : ''}" ${signup ? 'novalidate' : ''}>
                                ${signup ? `
                                    <fieldset class="signup-profile">
                                        <legend class="sr-only">${translate('가입자 정보', 'Contact details')}</legend>
                                        <div class="auth-field full-width"><label>${translate('이름', 'Name')}<input name="clientName" maxlength="20" required autocomplete="name" value="${escapeHTML(fields.clientName || '')}" aria-describedby="clientName-error" aria-invalid="${Boolean(errors.clientName)}"></label>${fieldError('clientName')}</div>
                                        <div class="auth-field"><label>${translate('회사명', 'Company name')}<input name="companyName" maxlength="50" required autocomplete="organization" value="${escapeHTML(fields.companyName || '')}" aria-describedby="companyName-error" aria-invalid="${Boolean(errors.companyName)}"></label>${fieldError('companyName')}</div>
                                        <div class="auth-field"><label>${translate('직책', 'Position')}<input name="position" maxlength="30" required autocomplete="organization-title" value="${escapeHTML(fields.position || '')}" aria-describedby="position-error" aria-invalid="${Boolean(errors.position)}"></label>${fieldError('position')}</div>
                                    </fieldset>
                                ` : ''}
                                <div class="auth-field"><label>${translate('아이디', 'Username')}
                                    <input name="username" required maxlength="50" autocomplete="username" value="${escapeHTML(fields.username || '')}" ${signup ? 'minlength="4" pattern="[A-Za-z0-9_]{4,50}"' : ''} aria-describedby="${loginFailed ? 'login-error' : 'username-error'}" aria-invalid="${Boolean(errors.username || loginFailed)}">
                                </label>${fieldError('username')}</div>
                                <div class="auth-field"><label>${translate('비밀번호', 'Password')}
                                    <input name="password" type="password" required maxlength="64" ${signup ? 'minlength="8"' : ''} autocomplete="${signup ? 'new-password' : 'current-password'}" aria-describedby="${loginFailed ? 'login-error' : 'password-error'}" aria-invalid="${Boolean(errors.password || loginFailed)}">
                                </label>${fieldError('password')}
                                ${loginFailed ? `<p class="login-error" id="login-error" role="alert">${translate('아이디 또는 비밀번호가 올바르지 않습니다.', 'Incorrect username or password.')}</p>` : ''}</div>
                                <button class="button primary" type="submit" ${busy || isPreview || !config.API_BASE_URL ? 'disabled' : ''}>${signup ? translate('회원가입', 'Sign up') : translate('로그인', 'Log in')}</button>
                            </form>
                            <button class="button text-button ${signup ? 'back-to-login' : ''}" data-action="${signup ? 'login-screen' : 'signup-screen'}">${signup ? translate('로그인으로 돌아가기', 'Back to login') : translate('회원가입', 'Sign up')}</button>
                        </div>
                    </section>
                    <aside class="login-art">
                        <p class="eyebrow">릴슈 / GLOBAL EQUIPMENT SUPPORT</p>
                        <h2>${translate('언어가 달라도,<br>장비 지원은<br>이어지도록.', 'Different languages.<br>Connected support.')}</h2>
                        <p>${translate('글로벌 고객과 한국의 기술지원팀을 연결하는<br>실시간 장비 상담 서비스, 릴슈.', 'Real-time equipment support connecting<br>global customers and the Korean support team.')}</p>
                        <div class="circuit circuit-top" aria-hidden="true"></div>
                        <div class="circuit circuit-bottom" aria-hidden="true"></div>
                        <div class="circuit circuit-small" aria-hidden="true"></div>
                    </aside>
                </div>
            </main>`;
    }

    function languageControl() {
        if (!['login', 'signup'].includes(view)) return '';
        return `<button class="language-button" data-action="language">${language === 'ko' ? '<strong>한국어</strong> / English' : '한국어 / <strong>English</strong>'}</button>`;
    }

    function workspace() {
        const userProfile = getProfile();
        return html`<div class="workspace">
        <header class="call-header workspace-topbar">${renderLogo()}</header>
        <aside class="sidebar">
    <div class="profile">
        <img class="avatar" src="${userProfile.photo}" width="72" height="72" alt="${escapeHTML(userProfile.name)} ${translate('프로필', 'profile')}">
        <h2>${escapeHTML(language === 'en' ? userProfile.englishName : userProfile.name)}${role === 'AGENT' && language === 'ko' ? ' 상담원' : ''}</h2>
        <p>${escapeHTML(userProfile.company)}${userProfile.position ? `<br>${escapeHTML(userProfile.position)}` : ''}</p>
        </div>
    <button class="button logout" data-action="logout" ${disabledAttribute('logout')}>${translate('로그아웃', 'Log out')}</button>
    </aside>
        <div class="workspace-body">
        <h1 class="sr-only">${role === 'AGENT' ? translate('상담원 대시보드', 'Agent dashboard') : 'Customer dashboard'}</h1>
    <main id="main" class="dashboard ${role === 'CUSTOMER' ? 'customer' : ''}">${renderNotice()}${view === 'request' ? requestForm() : view === 'waiting' ? waitingScreen() : dashboard()}</main>
        </div>
        </div>`;
    }
    function renderInquiryRow(row) {
        return html`<tr>
        <td class="request-id">${formatValue(row.callId)}</td>
        <td class="company-cell">${formatValue(row.company)}</td>
        <td>${formatValue(row.equipment)}</td>
        <td>${formatValue(row.errorCode)}</td>
        <td>${getStatusLabel(row.status)}</td>
        <td>${receivedTime(row.createdAt)}</td>
        <td>
        <button class="button" data-detail="${escapeHTML(row.callId)}" aria-label="${escapeHTML(row.callId)} ${translate('문의 상세 보기', 'request details')}">${translate('상세 보기', 'View')}</button>
        </td>
        </tr>`;
    }

    function renderTranslationMessage(message) {
        return html`
            <article class="message">
                <header><div><strong>${formatValue(message.speaker)}</strong>${message.roleLabel !== message.speaker ? `<span>${formatValue(message.roleLabel)}</span>` : ''}</div>${translationTime(message.time)}</header>
                <p>${formatValue(message.text)}</p>
                ${message.needsReview ? `<span class="review-marker">${translate('번역 확인 필요', 'Translation needs review')}</span>` : ''}
            </article>`;
    }

    function dashboard() {
        const items = data.inquiries || [];
        return html`${role === 'AGENT' ? summary() : ''}<section class="inquiries" aria-labelledby="list-title">
        <div class="section-heading">
        <h2 id="list-title">${translate('문의 목록', 'Support requests')}</h2>
    ${role === 'AGENT' ? `<label class="filter-label">
        <span class="sr-only">${translate('처리 상태 필터', 'Filter by status')}</span>
        <select id="status-filter">
        <option value="">${translate('전체 상태', 'All statuses')}</option>${renderStatusOptions(inquiryFilterStatuses, filter)}</select>
        </label>` :`<button class="button primary icon-button add-button" data-action="request" aria-label="New support request" title="New support request">
        <span aria-hidden="true">+</span>
        </button>`}
    </div>
        <div class="table-wrap" tabindex="0" role="region" aria-label="${translate('문의 목록 표', 'Support requests table')}">
        <table>
        <caption class="sr-only">${translate('서버에서 제공하는 순서의 문의 목록', 'Support requests in server-provided order')}</caption>
        <thead>
        <tr>${[
            translate('문의 ID', 'Request ID'),
            translate('고객사', 'Company'),
            translate('장비 모델', 'Equipment'),
            translate('오류 코드', 'Error code'),
            translate('상태', 'Status'),
            translate('접수 시각', 'Received'),
            translate('상세', 'Details')
        ].map(x => `<th scope="col">${x}</th>`).join('')}</tr>
        </thead>
        <tbody>${items.length ? items.map(renderInquiryRow).join('') : ''}</tbody>
        </table>${items.length ? '' :`<div class="table-empty">
        <strong>${translate('표시할 문의가 없습니다.', 'No requests to display.')}</strong>
        ${data.inquiries !== null && role === 'AGENT' ? `<p>${translate('다른 상태를 선택해 보세요.', 'Try another status filter.')}</p>` : ''}
        </div>`}
        </div>
        ${pagination()}
        </section>`;
    }
    function pagination() {
        const total = Math.max(1, data.totalPages || 0);
        const page = Math.min(Math.max(0, data.page || 0), total - 1);
        const start = Math.max(0, Math.min(page - 2, total - 5));
        const pages = Array.from({ length: Math.min(5, total) }, (_, index) => start + index);
        const unavailable = busy || !data.totalPages;
        return `<nav class="pagination" aria-label="${translate('문의 페이지', 'Request pages')}">
            <button class="page-arrow" data-action="previous-page" aria-label="${translate('이전 페이지', 'Previous page')}" ${page === 0 || unavailable ? 'disabled' : ''}><span aria-hidden="true">‹</span></button>
            ${pages.map(number => `<button class="page-number" data-action="select-page" data-page="${number}" aria-label="${translate(`${number + 1}페이지`, `Page ${number + 1}`)}" ${number === page ? 'aria-current="page"' : ''} ${unavailable ? 'disabled' : ''}>${number + 1}</button>`).join('')}
            <button class="page-arrow" data-action="next-page" aria-label="${translate('다음 페이지', 'Next page')}" ${page === total - 1 || unavailable ? 'disabled' : ''}><span aria-hidden="true">›</span></button>
        </nav>`;
    }
    function summary() {
        return html`<section class="summary" aria-labelledby="summary-title">
        <div class="section-heading">
        <h2 id="summary-title">${translate('문의 현황', 'Request overview')}</h2>
        <p>${translate('전체 문의', 'Total requests')} <strong>${formatValue(data.summary?.total)}</strong>
        </p>
        </div>
        <dl class="summary-items">${summaryStatuses.map(s => `<div>
        <dt>${getStatusLabel(s)}</dt>
        <dd>${formatValue(data.summary?.counts?.[s])}${data.summary?.counts?.[s] != null ? translate('건', '') : ''}</dd>
        </div>`).join('')}</dl>
        </section>`;
    }
    function requestForm() {
        return html`
            <section aria-labelledby="request-title">
                <h2 id="request-title" class="page-title">New support request</h2>
                <form id="request-form" class="request-form panel">
                    <label>Company name<input readonly value="${escapeHTML(getProfile().company || '—')}"></label>
                    <div class="form-grid">
                        <div><label>Equipment name<input name="equipment" required maxlength="100" value="${escapeHTML(draft.equipment || '')}" aria-describedby="equipmentName-error" aria-invalid="${Boolean(errors.equipmentName)}"></label>${fieldError('equipmentName')}</div>
                        <div><label>Error code<input name="errorCode" required maxlength="50" value="${escapeHTML(draft.errorCode || '')}" aria-describedby="errorCode-error" aria-invalid="${Boolean(errors.errorCode)}"></label>${fieldError('errorCode')}</div>
                    </div>
                    <div><label class="issue-label">Issue details<textarea name="description" maxlength="500" aria-describedby="symptom-error" aria-invalid="${Boolean(errors.symptom)}">${escapeHTML(draft.description || '')}</textarea></label>${fieldError('symptom')}</div>
                    <div class="form-actions">
                        <p class="help">After submitting, please wait for a support agent to connect.</p>
                        <div><button type="button" class="button" data-action="cancel-request">Cancel</button><button class="button primary" type="submit" ${disabledAttribute('submitInquiry')}>Submit request</button></div>
                    </div>
                </form>
            </section>`;
    }

    function detailContent() {
        const row = data.selected || {};
        const previousMessages = row.messages || [];
        return html`
            <div class="modal-heading"><div><h2 id="detail-title">${translate('문의 상세', 'Request details')}</h2><p class="help request-id">ID ${formatValue(row.callId)}</p></div><button class="button modal-close" data-action="close-detail" aria-label="${translate('닫기', 'Close')}"><span aria-hidden="true">×</span></button></div>
            <div class="detail-grid"><div><span>${translate('고객 회사', 'Company')}</span><h3>${formatValue(row.company)}</h3></div><div><span>${row.requester ? translate('문의자', 'Contact person') : translate('문의 계정', 'Contact account')}</span><p class="detail-value">${formatValue(row.requester || row.requesterAccount)}</p><p class="help">${formatValue(row.position)}</p></div></div>
            <div class="detail-grid"><div><span>${translate('처리 상태', 'Status')}</span><p>${row.status ? getStatusLabel(row.status) : '—'}</p></div></div>
            <div class="detail-grid equipment-grid"><div><span>${translate('장비명', 'Equipment name')}</span><p class="detail-value">${formatValue(row.equipment)}</p></div><div><span>${translate('오류 코드', 'Error code')}</span><p class="detail-value">${formatValue(row.errorCode)}</p></div></div>
            <h3 class="issue-title">${translate('접수한 이슈', 'Submitted issue')}</h3><p class="issue-content">${formatValue(row.description)}</p>
            ${previousMessages.length ? `<details class="previous-conversation"><summary>${translate('지난 대화 보기', 'Conversation history')}</summary>${previousMessages.map(message => renderTranslationMessage(mapMessage(message, role === 'AGENT' ? 'ADMIN' : 'USER'))).join('')}</details>` : ''}
            <div class="modal-footer"><span class="help">${row.createdAt ? formatLocalTimestamp(row.createdAt) : ''}</span>${role === 'AGENT' && row.status === 'PENDING' ? `<button class="button primary icon-button" data-action="connect" ${disabledAttribute('connectCall')} aria-label="통화 연결">${renderIcon('phone')}</button>` : ''}</div>`;
    }

    function translationTime(timestamp) {
        const iso = toUtcIso(timestamp);
        return iso ? `<time datetime="${iso}">${formatLocalTimestamp(timestamp)}</time>` : '';
    }
    function callScreen() {
        const row = data.selected || {};
        const name = role === 'AGENT' ?[row.company, row.requester || row.requesterAccount].filter(Boolean).join(' · ') || translate('통화 상대 정보 대기', 'Waiting for participant information') : (row.agentAccount ? `Your support agent · ${row.agentAccount}` : 'Your support agent');
        const connected = data.connection === 'connected';
        return html`<header class="call-header">${renderLogo()}${role === 'AGENT' ? `<button class="button danger icon-button" data-action="end" ${disabledAttribute('endCall')} aria-label="통화 종료">${renderIcon('hangup')}</button>` : ''}
        </header>
        <main id="main" class="call-main ${role === 'CUSTOMER' ? 'customer-call' : ''}">${renderNotice()}<div class="call-heading">
        <div>
        <div class="participant">
        <h1>${escapeHTML(name)}</h1>
        <span class="connection">${connected ? translate('연결중', 'Connected') : data.connection === 'reconnecting' ? translate('재연결 중', 'Reconnecting') : data.connection === 'connecting' ? translate('연결 중', 'Connecting') : translate('미연결', 'Not connected')}${connected ? renderIcon('connected', 8) : '<span class="offline-dot" aria-hidden="true"></span>'}</span>
        </div>
        <p class="help request-id">${translate('문의 ID', 'Request ID')} ${formatValue(row.callId)} · ${formatValue(row.equipment)} · ${formatValue(row.errorCode)}</p>
        </div>
        <button class="button" data-action="notes">${translate('메모장', 'Notes')}</button>
        </div>
        <div class="call-panels">
        <section class="panel conversation" aria-labelledby="conversation-title">
        <div class="panel-heading">
        <h2 id="conversation-title">${translate('대화 기록', 'Conversation')}</h2>
        </div>
        <div class="transcript" role="log" aria-label="${translate('번역된 대화', 'Translated conversation')}" aria-live="polite">${data.translations.length ? data.translations.map(renderTranslationMessage).join('') :`<div class="conversation-empty">
        <strong>${translate('번역문을 기다리고 있습니다.', 'Waiting for translated messages.')}</strong>
        <p>${translate('수신된 번역문이 여기에 표시됩니다.', 'Translated messages will appear here when received.')}</p>
        </div>`}</div>
        <footer class="conversation-footer">
        ${microphoneControl(connected)}
        </footer>
        </section>${role === 'AGENT' ? `<aside class="panel rag-panel" aria-labelledby="rag-title">${solutionContent()}</aside>` : ''}</div>
        </main>`;
    }

    function microphoneControl(connected) {
        const active = ['starting', 'listening', 'stopping'].includes(speech.status);
        const unavailable = !speech.supported || !speech.secureContext;
        const disabled = isPreview || busy || !connected || unavailable || speech.status === 'stopping';
        const statuses = {
            idle: translate('마이크 꺼짐', 'Microphone off'),
            starting: translate('마이크 시작 중 · 권한 요청을 확인하세요', 'Starting microphone · check the permission prompt'),
            listening: translate('듣는 중', 'Listening'),
            stopping: translate('음성을 텍스트로 변환 중', 'Converting speech to text'),
            error: translate('음성 인식 중지됨', 'Speech recognition stopped'),
        };
        const errors = {
            'unsupported': translate('이 브라우저는 음성 인식을 지원하지 않습니다. 지원 브라우저에서 접속해 주세요.', 'Speech recognition is unavailable in this browser. Open a supported browser.'),
            'insecure-context': translate('마이크는 HTTPS 또는 localhost에서 사용해 주세요.', 'Use HTTPS or localhost for microphone access.'),
            'not-allowed': translate('마이크 권한이 차단되었습니다. 사이트 권한에서 허용한 뒤 다시 시작해 주세요.', 'Microphone permission was denied. Allow it in site permissions and try again.'),
            'service-not-allowed': translate('브라우저의 음성 인식 서비스 사용이 차단되었습니다. 사이트 권한을 확인해 주세요.', 'The browser speech service is blocked. Check site permissions.'),
            'audio-capture': translate('마이크를 찾지 못했습니다. 장치 연결과 마이크 사용 설정을 확인해 주세요.', 'No microphone is available. Check your device and microphone settings.'),
            'network': translate('음성 인식 서비스에 연결하지 못했습니다. 네트워크를 확인한 뒤 다시 시작해 주세요.', 'Unable to reach the speech service. Check your connection and try again.'),
            'no-speech': translate('음성이 감지되지 않았습니다. 마이크를 다시 시작해 주세요.', 'No speech was detected. Start the microphone again.'),
            'language-not-supported': translate('브라우저가 이 인식 언어를 지원하지 않습니다. 지원 브라우저에서 접속해 주세요.', 'This recognition language is unavailable. Open a supported browser.'),
            'too-long': translate('인식 문장이 2,000자를 넘어 전송하지 못했습니다. 짧게 나누어 말해 주세요.', 'The phrase exceeds 2,000 characters and was not sent. Use shorter phrases.'),
            'send-failed': translate('인식 문장을 전송하지 못해 마이크를 중지했습니다. 연결 상태를 확인해 주세요.', 'The recognized phrase was not sent. Microphone stopped. Check the call connection.'),
            'stt-unauthorized': translate('음성 서비스 인증이 만료되었습니다. 다시 로그인해 주세요.', 'Speech service authentication expired. Please log in again.'),
            'stt-failed': translate('음성 변환에 실패했습니다. 잠시 후 마이크를 재개해 주세요.', 'Transcription failed. Resume the microphone shortly.'),
            'stt-timeout': translate('음성 변환 시간이 초과되었습니다. 짧게 다시 녹음해 주세요.', 'Transcription timed out. Record a shorter phrase.'),
            'stt-backlog': translate('음성 변환이 지연되어 마이크를 중지했습니다. 잠시 후 재개해 주세요.', 'Transcription is delayed. Microphone paused. Resume shortly.'),
        };
        const error = speech.error || (!speech.supported ? 'unsupported' : !speech.secureContext ? 'insecure-context' : '');
        return `<div class="speech-input">
            <div class="speech-controls"><button id="microphone-toggle" class="button ${active ? 'microphone-active' : ''}" type="button" data-action="microphone" aria-pressed="${active}" aria-describedby="speech-status speech-hint" ${disabled ? 'disabled' : ''}>${active ? translate('음소거', 'Mute microphone') : translate('마이크 재개', 'Resume microphone')}</button>
            <p id="speech-status" role="status">${statuses[speech.status] || statuses.idle}${speech.processing ? translate(' · 음성 변환 중', ' · Transcribing') : ''} · ${role === 'AGENT' ? translate('한국어', 'Korean') : translate('영어', 'English')}</p></div>
            <p id="speech-hint" class="message-hint">${speech.provider === 'whisper'
                ? translate('통화 연결 시 자동으로 듣습니다. 말이 끝나면 텍스트로 변환해 전송합니다.', 'Listening starts automatically when connected. Finished phrases are transcribed and sent.')
                : translate('확정된 문장을 자동 전송합니다. 브라우저 음성 인식 서비스를 사용합니다.', 'Final phrases are sent automatically using the browser speech service.')}</p>
            ${speech.interim ? `<p class="speech-interim" aria-live="off">${translate('인식 중:', 'Recognizing:')} ${escapeHTML(speech.interim)}</p>` : ''}
            ${speech.lastTranscript ? `<p class="speech-interim">${translate('마지막 인식:', 'Last recognized:')} ${escapeHTML(speech.lastTranscript)}</p>` : ''}
            ${error ? `<p class="field-error" role="alert">${errors[error] || translate('음성 인식을 시작하지 못했습니다. 마이크 설정을 확인한 뒤 다시 시도해 주세요.', 'Speech recognition failed. Check microphone settings and try again.')}</p>` : ''}
        </div>`;
    }

    function receivedTime(timestamp) {
        const iso = toUtcIso(timestamp);
        return iso ? `<time datetime="${iso}" data-received-at="${iso}" title="${formatLocalTimestamp(iso)}" aria-label="${formatLocalTimestamp(iso)}">${formatTimeAgo(iso, language)}</time>` : '—';
    }

    function waitingScreen() {
        return `<section class="panel waiting-panel"><h2>Waiting for a support agent</h2><p>Your request has been submitted. Please keep this page open.</p><p class="help request-id">Request ID ${formatValue(data.selected?.callId)}</p></section>`;
    }

    function solutionContent() {
        const solution = data.solution;
        const status = solution?.status || 'PENDING';
        const fallback = status === 'found' ? '관련 매뉴얼을 찾았습니다. 아래 출처를 확인해 주세요.' : status === 'not_found' ? '관련 매뉴얼을 찾지 못했습니다.' : status === 'error' ? '매뉴얼을 불러오지 못했습니다.' : '관련 매뉴얼을 찾고 있습니다.';
        return `<h2 id="rag-title">관련 매뉴얼</h2><p class="help">접수한 장비 · 오류 코드 · 이슈를 바탕으로 조회</p>
            ${solution?.needsReview ? '<p class="review-marker">확인 필요</p>' : ''}
            <div class="rag-answer">${escapeHTML(solution?.answer || fallback)}</div>
            ${solution?.handoff ? '<p class="review-marker">해결방법을 찾지 못했습니다. 엔지니어 연결이 필요합니다.</p>' : ''}
            ${solution?.sources?.length ? `<ul class="manual-sources">${solution.sources.map(source => `<li>${formatValue(source.doc)}${source.page != null ? ` · p. ${formatValue(source.page)}` : ''}${source.section ? ` · ${formatValue(source.section)}` : ''}</li>`).join('')}</ul>` : ''}`;
    }

    function endCallContent() {
        return `<h2 id="end-title">통화 종료</h2><p class="help">처리 결과를 선택하면 통화가 종료됩니다.</p><form id="end-call-form"><label>처리 결과<select name="status"><option value="RESOLVED">해결 완료</option><option value="UNRESOLVED">미해결</option></select></label><div class="form-actions"><button type="button" class="button" data-action="close-end">취소</button><button class="button danger" type="submit" ${busy || isPreview ? 'disabled' : ''}>종료</button></div></form>`;
    }

    function notesContent() {
        return html`<div class="section-heading">
        <h2 id="notes-title">${translate('메모장', 'Notes')}</h2>
        <button class="button" data-action="close-notes">${translate('닫기', 'Close')}</button>
        </div>
        <p class="help">${translate('이 메모는 저장되지 않습니다.', 'These notes are temporary and are not saved.')}</p>
        <label class="sr-only" for="notes-text">${translate('개인 메모', 'Personal notes')}</label>
        <textarea id="notes-text" placeholder="${translate('필요한 내용을 자유롭게 메모하세요.', 'Write your notes here.')}">${escapeHTML(notes)}</textarea>`;
    }
    return { previewBar, login, workspace, detailContent, callScreen, notesContent, endCallContent };
}
