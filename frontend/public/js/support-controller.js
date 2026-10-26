import { createSupportApi } from './support-api.js';
import { createState, profiles } from './model.js';
import { mapCall, mapMessage, getCallSummary } from './call-data.js';
import { createCallChannel, loadStompClient } from './call-channel.js';
import { normalizeSignupInput, validateCallInput, validateSignupInput, validateUtterance } from './validation.js';
import { utcNow } from './utc.js';
import { createSpeechInput } from './speech-input.js';
import { createRecordedSpeechInput, createTranscriber } from './recorded-speech.js';

const activeCallKey = 'rilshu.activeCall';

export function createSupportController({ config, isPreview, sessions, storage, onChange, loadClient = loadStompClient, apiFactory = createSupportApi,
    Recognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition,
    secureContext = globalThis.isSecureContext ?? true,
    Recorder = globalThis.MediaRecorder,
    getUserMedia = globalThis.navigator?.mediaDevices?.getUserMedia?.bind(globalThis.navigator.mediaDevices),
    sttFetch = globalThis.fetch,
    AudioContext = globalThis.AudioContext || globalThis.webkitAudioContext,
}) {
    const state = {
        data: createState(),
        role: config.MOCK_ROLE,
        language: config.MOCK_ROLE === 'CUSTOMER' ? 'en' : 'ko',
        view: isPreview ? 'dashboard' : 'login',
        filter: config.MOCK_ROLE === 'CUSTOMER' ? '' : 'PENDING',
        notes: '',
        draft: {},
        authDraft: {},
        signupDraft: {},
        errors: {},
        notice: '',
        busy: false,
    };
    let session = null;
    let channel = null;
    let activeCallId = null;
    let refreshTimer;
    let solutionTimer;
    let expirationTimer;
    let listRequest;
    let solutionRequest;
    let callRequest;
    let listVersion = 0;
    let sessionVersion = 0;
    let localMessageId = 0;
    let socketVersion = 0;
    let disposed = false;
    let actionRequest;
    let microphoneMuted = false;
    let microphoneSuspended = false;
    let microphoneTimer;
    const notify = () => { if (!disposed) onChange?.(); };
    const speechOptions = {
        Recognition, secureContext,
        onFinal: sendMessage,
        onChange: value => {
            state.speech = value; notify();
            if (value.status === 'idle') {
                clearTimeout(microphoneTimer);
                microphoneTimer = setTimeout(syncMicrophone, 100);
            }
        },
    };
    const speech = config.STT_URL ? createRecordedSpeechInput({
        ...speechOptions, Recorder, getUserMedia, AudioContext, continuous: true,
        transcribe: createTranscriber({ endpoint: config.STT_URL, getAccessToken: () => sessions.read()?.accessToken, fetchImpl: sttFetch }),
    }) : createSpeechInput(speechOptions);
    state.speech = speech.state;

    function syncMicrophone() {
        if (disposed || isPreview || microphoneMuted || microphoneSuspended || state.busy
            || state.view !== 'call' || state.data.connection !== 'connected'
            || !state.speech.supported || !state.speech.secureContext || state.speech.status !== 'idle') return;
        void speech.start(state.role === 'AGENT' ? 'ko-KR' : 'en-US');
    }

    function sendMessage(value) {
        const message = typeof value === 'string' ? value.trim() : value;
        if (disposed || isPreview || state.busy || state.view !== 'call' || state.data.connection !== 'connected' || !validateUtterance(message)) return false;
        try {
            channel.send(message);
            state.data.translations.push({ id: `local-${++localMessageId}`, local: true,
                speaker: text('나', 'Me'), roleLabel: state.role === 'AGENT' ? text('상담원', 'Support agent') : text('고객', 'Customer'),
                text: message, time: utcNow(), needsReview: false,
            });
            notify();
            return true;
        } catch (error) {
            errorNotice(error);
            return false;
        }
    }

    async function stopChannel(previous) {
        try {
            await previous?.stop();
        } catch {
            // 연결 정리에 실패해도 화면은 계속 동작합니다.
        }
    }
    const text = (ko, en) => state.language === 'ko' ? ko : en;
    const api = apiFactory({
        baseAddress: config.API_BASE_URL,
        getAccessToken: () => sessions.read()?.accessToken,
        onUnauthorized: () => expireSession(),
    });

    function errorNotice(error) {
        if (error.name === 'AbortError') return;
        if (error.code === 'INVALID_CREDENTIALS' && state.view === 'login') {
            state.errors.credentials = true;
            state.notice = '';
            notify();
            return;
        }
        if (state.view === 'signup' && error.code === 'DUPLICATE_USERNAME') {
            state.errors.username = text('이미 사용 중인 아이디입니다.', 'This username is already in use.');
            state.notice = '';
            notify();
            return;
        }
        if (error.code === 'VALIDATION_ERROR') {
            const fields = state.view === 'signup' ? ['username', 'password', 'clientName', 'companyName', 'position']
                : state.view === 'request' ? ['equipmentName', 'errorCode', 'symptom'] : [];
            for (const field of fields) {
                // 명세는 message 문자열만 보장합니다. 명시된 필드명만 입력란에 연결합니다.
                if (new RegExp(`\\b${field}\\s*:`).test(error.message)) {
                    state.errors[field] = text(error.message, 'Please check this field.');
                }
            }
        }
        const messages = {
            DUPLICATE_USERNAME: ['이미 사용 중인 아이디입니다.', 'This username is already in use.'],
            FORBIDDEN: ['권한이 없습니다.', 'You do not have permission.'],
            NOT_FOUND: ['요청을 찾을 수 없습니다.', 'The request could not be found.'],
            ALREADY_ACCEPTED: ['이미 다른 상담원이 받았습니다.', 'Another agent has already accepted this call.'],
            INVALID_STATUS_TRANSITION: ['통화 상태가 변경되었습니다. 목록을 확인해 주세요.', 'The call status has changed. Please check the list.'],
            VALIDATION_ERROR: ['입력 내용을 확인해 주세요.', 'Please check the entered details.'],
            STOMP_UNAVAILABLE: ['통화에 연결하지 못했습니다. 새로고침 후 다시 시도해 주세요.', 'Unable to connect. Refresh and try again.'],
            SOCKET_NOT_CONFIGURED: ['통화에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.', 'Unable to connect. Please try again.'],
        };
        state.notice = text(...(messages[error.code] || ['요청을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.', 'Unable to complete the request. Please try again.']));
        notify();
    }

    async function action(task) {
        if (disposed || state.busy || isPreview) return;
        const version = sessionVersion;
        actionRequest = new AbortController();
        const signal = actionRequest.signal;
        // 로그아웃 후 도착한 응답은 무시합니다.
        const wait = async promise => {
            const result = await promise;
            if (disposed || signal.aborted || version !== sessionVersion) {
                throw new DOMException('Request cancelled', 'AbortError');
            }
            return result;
        };
        state.busy = true;
        state.notice = '';
        state.errors = {};
        notify();
        try { return await task(wait, signal); }
        catch (error) {
            if (!disposed && version === sessionVersion) {
                errorNotice(error);
                if (['ALREADY_ACCEPTED', 'INVALID_STATUS_TRANSITION'].includes(error.code)) await refreshList();
                if (error.code === 'NOT_FOUND' && state.view !== 'signup') state.view = 'dashboard';
            }
        } finally {
            if (!disposed && version === sessionVersion) {
                state.busy = false;
                notify();
                syncMicrophone();
            }
        }
    }

    function clearCall() {
        clearTimeout(microphoneTimer);
        microphoneMuted = false;
        speech.cancel();
        socketVersion += 1;
        clearTimeout(solutionTimer);
        solutionRequest?.abort();
        callRequest?.abort();
        const oldChannel = channel;
        channel = null;
        stopChannel(oldChannel);
        activeCallId = null;
        storage.removeItem(activeCallKey);
        state.notes = '';
        state.data.translations = [];
        state.data.solution = null;
        state.data.connection = 'disconnected';
    }

    function clearSession() {
        sessionVersion += 1;
        listVersion += 1;
        actionRequest?.abort();
        clearTimeout(refreshTimer);
        clearTimeout(expirationTimer);
        listRequest?.abort();
        clearCall();
        sessions.clear();
        session = null;
        state.data = createState();
        state.view = 'login';
        state.busy = false;
        state.errors = {};
        state.authDraft = {};
        state.signupDraft = {};
        state.draft = {};
    }

    function expireSession() {
        clearSession();
        state.notice = text('로그인이 만료되었습니다. 다시 로그인해 주세요.', 'Your session has expired. Please sign in again.');
        notify();
    }

    function applySession(saved) {
        session = saved;
        state.role = saved.user.role === 'ADMIN' ? 'AGENT' : 'CUSTOMER';
        state.language = state.role === 'AGENT' ? 'ko' : 'en';
        state.filter = state.role === 'AGENT' ? 'PENDING' : '';
        state.view = 'dashboard';
        clearTimeout(expirationTimer);
        expirationTimer = setTimeout(expireSession, Math.max(0, saved.expiresAt - Date.now()));
    }

    async function refreshList() {
        if (disposed || isPreview || !session) return;
        const version = ++listVersion;
        listRequest?.abort();
        listRequest = new AbortController();
        try {
            const [result, summary] = await Promise.all([
                api.getCalls({ status: state.filter || undefined, page: state.data.page, size: state.data.size }, { signal: listRequest.signal }),
                state.role === 'AGENT' ? getCallSummary(api, listRequest.signal) : null,
            ]);
            if (version !== listVersion || !session) return;
            // 현재 페이지가 사라지면 마지막 페이지로 이동합니다.
            if (result.totalPages > 0 && state.data.page >= result.totalPages) {
                state.data.page = result.totalPages - 1;
                await refreshList();
                return;
            }
            if (!result.totalPages) state.data.page = 0;
            state.data.inquiries = result.items.map(call => mapCall(call));
            state.data.totalPages = result.totalPages;
            if (summary) state.data.summary = summary;
            if (state.view === 'dashboard') notify();
        } catch (error) { if (version === listVersion) errorNotice(error); }
    }

    function scheduleRefresh() {
        clearTimeout(refreshTimer);
        if (disposed || isPreview || !session || state.role !== 'AGENT') return;
        refreshTimer = setTimeout(async () => {
            if (state.view === 'dashboard') await refreshList();
            scheduleRefresh();
        }, 5000);
    }

    async function restoreActiveCall(wait, signal) {
        if (!session || disposed) return;
        // 상세 응답에는 고객·증상이 없으므로 목록에서 원본 정보를 먼저 확보합니다.
        let candidate;
        const savedId = storage.getItem(activeCallKey);
        let page = 0;
        let totalPages;
        do {
            const result = await wait(api.getCalls({
                status: state.role === 'AGENT' ? 'CALLING' : 'PENDING,CALLING', page, size: 100,
            }, { signal }));
            const mine = result.items.filter(call => ['PENDING', 'CALLING'].includes(call.status)
                && (state.role !== 'AGENT' || call.agent?.id === session.user.id));
            candidate = mine.find(call => call.callId === savedId) || mine[0];
            totalPages = result.totalPages;
            page += 1;
        } while (!candidate && page < totalPages);
        if (!candidate) {
            storage.removeItem(activeCallKey);
            return;
        }
        const detail = await wait(api.getCall(candidate.callId, { signal }));
        if (!['PENDING', 'CALLING'].includes(detail.status)) {
            storage.removeItem(activeCallKey);
            return;
        }
        const Client = await wait(ensureClient());
        state.data.selected = mapCall(detail, mapCall(candidate));
        state.view = detail.status === 'PENDING' ? 'waiting' : 'call';
        state.data.connection = 'connecting';
        await subscribeCall(candidate.callId, Client);
        if (state.role === 'AGENT') pollSolution(candidate.callId);
    }

    async function refreshActiveCall(callId, version) {
        callRequest?.abort();
        callRequest = new AbortController();
        const { signal } = callRequest;
        const result = await api.getCall(callId, { signal });
        if (signal.aborted || version !== socketVersion || activeCallId !== callId) return;
        state.data.selected = mapCall(result, state.data.selected || {});
        const history = (result.messages || []).map(message => mapMessage(message, session.user.role));
        const ids = new Set(history.map(message => message.id));
        state.data.translations = [...history, ...state.data.translations.filter(message => !message.local && !ids.has(message.id))];
        if (result.status === 'CALLING') {
            state.data.connection = channel?.connected ? 'connected' : 'reconnecting';
            state.view = 'call';
            state.notice = '';
        } else if (['MISSED', 'RESOLVED', 'UNRESOLVED'].includes(result.status)) {
            finishLocally(result.status);
        }
        notify();
        syncMicrophone();
    }

    async function ensureClient() {
        if (!config.WS_BASE_URL) throw Object.assign(new Error(), { code: 'SOCKET_NOT_CONFIGURED' });
        try { return await loadClient(); }
        catch { throw Object.assign(new Error(), { code: 'STOMP_UNAVAILABLE' }); }
    }

    async function subscribeCall(callId, Client) {
        speech.cancel();
        const version = ++socketVersion;
        const previous = channel;
        channel = null;
        await stopChannel(previous);
        if (disposed || version !== socketVersion || !session) return;
        activeCallId = callId;
        storage.setItem(activeCallKey, callId);
        channel = createCallChannel({
            Client, brokerURL: config.WS_BASE_URL, callId,
            getAccessToken: () => sessions.read()?.accessToken,
            myRole: session.user.role,
            onReady: async () => {
                try { await refreshActiveCall(callId, version); }
                catch (error) { if (version === socketVersion) errorNotice(error); }
            },
            onDisconnect: () => {
                if (version !== socketVersion) return;
                callRequest?.abort();
                speech.cancel();
                state.data.connection = 'reconnecting';
                state.notice = text('통화 채널 재연결 중입니다.', 'Reconnecting to the call.');
                notify();
            },
            onError: async error => {
                if (version !== socketVersion) return;
                speech.cancel();
                state.data.connection = 'reconnecting';
                notify();
                // 종료된 통화는 재구독이 금지됩니다. 놓친 종료 이벤트를 REST로 확인합니다.
                try { await refreshActiveCall(callId, version); }
                catch { /* 상세 확인에 실패하면 원래 소켓 오류를 표시합니다. */ }
                if (version === socketVersion && !channel?.connected) errorNotice(error);
            },
            onMessage: message => {
                if (version !== socketVersion) return;
                if (message.type === 'translation') {
                    if (state.data.translations.some(item => item.id === message.utteranceId)) return;
                    state.data.translations.push(mapMessage({ ...message,
                        text: message.translatedText ?? text('(번역 실패)', '(Translation failed)'),
                    }, session.user.role));
                } else if (message.type === 'accepted') {
                    state.data.connection = 'connected';
                    state.view = 'call';
                    state.notice = '';
                    state.data.selected.status = 'CALLING';
                    syncMicrophone();
                } else if (message.type === 'ended' || message.type === 'missed') {
                    finishLocally(message.status || 'MISSED');
                }
                notify();
            },
        });
        channel.start();
    }

    async function pollSolution(callId) {
        clearTimeout(solutionTimer);
        if (disposed || state.role !== 'AGENT' || activeCallId !== callId || !session) return;
        const version = socketVersion;
        solutionRequest?.abort();
        solutionRequest = new AbortController();
        try {
            const result = await api.getSolution(callId, { signal: solutionRequest.signal });
            if (disposed || version !== socketVersion || activeCallId !== callId) return;
            state.data.solution = result;
            notify();
            if (result.status === 'PENDING') solutionTimer = setTimeout(() => pollSolution(callId), 2000);
        } catch (error) {
            if (!disposed && version === socketVersion && error.name !== 'AbortError' && activeCallId === callId) {
                state.data.solution = { status: 'error', answer: null, sources: [] };
                notify();
            }
        }
    }

    function finishLocally(status) {
        if (state.data.selected) state.data.selected.status = status;
        clearCall();
        state.view = 'dashboard';
        state.notice = status === 'MISSED'
            ? text('상담원이 연결되지 않았습니다.', 'No support agent connected.')
            : text('통화가 종료되었습니다.', 'The call has ended.');
        refreshList();
    }

    return {
        state,
        get user() { return session?.user; },
        get profile() {
            const sample = profiles[state.role];
            return {
                ...sample,
                name: session ? (session.user.clientName || session.user.username || '') : sample.name,
                englishName: session ? (session.user.clientName || session.user.username || '') : sample.englishName,
                company: session ? (session.user.companyName || '') : sample.company,
                position: session?.user.position || '',
            };
        },
        async initialize() {
            if (isPreview) {
                notify();
                return;
            }
            const saved = sessions.read();
            if (!saved) {
                notify();
                return;
            }
            applySession(saved);
            notify();
            await refreshList();
            scheduleRefresh();
            await action((wait, signal) => restoreActiveCall(wait, signal));
        },
        login(credentials) {
            if (!credentials.username?.trim() || !credentials.password) {
                state.notice = text('아이디와 비밀번호를 입력해 주세요.', 'Enter your username and password.');
                notify();
                return;
            }
            state.authDraft = { username: credentials.username };
            return action(async (wait, signal) => {
                const result = await wait(api.login(credentials, { signal }));
                applySession(sessions.save(result));
                state.notice = '';
                state.authDraft = {};
                await refreshList();
                scheduleRefresh();
                await restoreActiveCall(wait, signal);
            });
        },
        signup(input) {
            input = normalizeSignupInput(input);
            state.signupDraft = { ...input, password: '' };
            state.errors = validateSignupInput(input);
            if (Object.keys(state.errors).length) {
                notify();
                return;
            }
            return action(async (wait, signal) => {
                await wait(api.signup(input, { signal }));
                state.signupDraft = {};
                state.view = 'login';
                state.notice = text('가입이 완료되었습니다. 로그인해 주세요.', 'Account created. Please sign in.');
            });
        },
        async logout() {
            if (isPreview) return;
            const logoutRequest = api.logout();
            clearSession();
            state.notice = '';
            notify();
            try { await logoutRequest; }
            catch { /* 서버 오류가 나도 로그인 정보는 삭제합니다. */ }
        },
        refreshList,
        async setFilter(filter) {
            state.filter = filter;
            state.data.page = 0;
            if (isPreview) notify();
            else await refreshList();
        },
        async setPage(page) {
            const total = state.data.totalPages;
            if (!Number.isInteger(page) || page < 0 || page >= total || state.busy) return;
            state.data.page = page;
            if (isPreview) notify();
            else await refreshList();
        },
        loadDetail(callId) {
            return action(async (wait, signal) => {
                const previous = state.data.inquiries?.find(item => item.callId === callId) || {};
                state.data.selected = null;
                state.data.selected = mapCall(await wait(api.getCall(callId, { signal })), previous);
            });
        },
        createCall(input) {
            const payload = { equipmentName: input.equipment, errorCode: input.errorCode, symptom: input.description || '' };
            state.errors = validateCallInput(payload);
            if (Object.keys(state.errors).length) {
                notify();
                return;
            }
            return action(async (wait, signal) => {
                const Client = await wait(ensureClient());
                const created = await wait(api.createCall(payload, { signal }));
                // 접수한 통화는 상세 조회가 실패해도 유지합니다.
                state.data.selected = mapCall({ ...payload, callId: created.callId, status: 'PENDING', customer: session.user });
                state.data.translations = [];
                state.draft = {};
                state.view = 'waiting';
                await subscribeCall(created.callId, Client);
            });
        },
        acceptCall() {
            if (state.role !== 'AGENT' || state.data.selected?.status !== 'PENDING') return;
            return action(async (wait, signal) => {
                const Client = await wait(ensureClient());
                const callId = state.data.selected.callId;
                const accepted = await wait(api.changeCallStatus(callId, 'CALLING', { signal }));
                state.data.selected = mapCall(accepted, state.data.selected);
                state.data.translations = [];
                state.data.connection = 'connecting';
                state.view = 'call';
                await subscribeCall(callId, Client);
                pollSolution(callId);
            });
        },
        endCall(status) {
            if (state.role !== 'AGENT' || !['RESOLVED', 'UNRESOLVED'].includes(status)) return;
            speech.cancel();
            return action(async (wait, signal) => {
                const callId = state.data.selected.callId;
                const updated = await wait(api.changeCallStatus(callId, status, { signal }));
                state.data.selected = mapCall(updated, state.data.selected);
                finishLocally(updated.status);
            });
        },
        toggleMicrophone() {
            if (['starting', 'listening'].includes(state.speech.status)) { microphoneMuted = true; speech.stop(); return; }
            if (disposed || isPreview || state.busy || state.view !== 'call' || state.data.connection !== 'connected') return;
            microphoneMuted = false;
            return speech.start(state.role === 'AGENT' ? 'ko-KR' : 'en-US');
        },
        stopMicrophone() {
            microphoneSuspended = true;
            speech.cancel();
        },
        resumeMicrophone() {
            microphoneSuspended = false;
            syncMicrophone();
        },
        dispose() {
            disposed = true;
            clearTimeout(microphoneTimer);
            speech.cancel();
            sessionVersion += 1;
            socketVersion += 1;
            listVersion += 1;
            actionRequest?.abort();
            clearTimeout(refreshTimer);
            clearTimeout(expirationTimer);
            clearTimeout(solutionTimer);
            listRequest?.abort();
            solutionRequest?.abort();
            callRequest?.abort();
            stopChannel(channel);
            channel = null;
        },
    };
}
