import { createSupportApi } from './support-api.js';
import { createState, profiles } from './model.js';
import { mapCall, mapMessage, getCallSummary } from './call-data.js';
import { createCallChannel, loadStompClient } from './call-channel.js';
import { validateCallInput, validateSignupInput, validateUtterance } from './validation.js';
import { utcNow } from './utc.js';

const activeCallKey = 'rilshu.activeCall';

export function createSupportController({ config, isPreview, sessions, storage, onChange, loadClient = loadStompClient, apiFactory = createSupportApi }) {
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
    const notify = () => { if (!disposed) onChange?.(); };

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
                if (error.code === 'NOT_FOUND') state.view = 'dashboard';
            }
        } finally {
            if (!disposed && version === sessionVersion) {
                state.busy = false;
                notify();
            }
        }
    }

    function clearCall() {
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

    async function refreshActiveCall(callId, version) {
        callRequest?.abort();
        callRequest = new AbortController();
        const result = await api.getCall(callId, { signal: callRequest.signal });
        if (version !== socketVersion || activeCallId !== callId) return;
        state.data.selected = mapCall(result, state.data.selected || {});
        const history = (result.messages || []).map(message => mapMessage(message, session.user.role));
        const ids = new Set(history.map(message => message.id));
        state.data.translations = [...history, ...state.data.translations.filter(message => !message.local && !ids.has(message.id))];
        if (result.status === 'CALLING') {
            state.data.connection = 'connected';
            state.view = 'call';
            state.notice = '';
        } else if (['MISSED', 'RESOLVED', 'UNRESOLVED'].includes(result.status)) {
            finishLocally(result.status);
        }
        notify();
    }

    async function ensureClient() {
        if (!config.WS_BASE_URL) throw Object.assign(new Error(), { code: 'SOCKET_NOT_CONFIGURED' });
        try { return await loadClient(); }
        catch { throw Object.assign(new Error(), { code: 'STOMP_UNAVAILABLE' }); }
    }

    async function subscribeCall(callId, Client) {
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
                state.data.connection = 'reconnecting';
                state.notice = text('통화 채널 재연결 중입니다.', 'Reconnecting to the call.');
                notify();
            },
            onError: error => { if (version === socketVersion) errorNotice(error); },
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
                name: session?.user.client_name || sample.name,
                englishName: session?.user.client_name || sample.englishName,
                company: session ? (session.user.company_name || session.user.companyName || '') : sample.company,
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
            const restoredCall = storage.getItem(activeCallKey);
            if (restoredCall) {
                await action(async (wait, signal) => {
                    const Client = await wait(ensureClient());
                    state.data.selected = mapCall(await wait(api.getCall(restoredCall, { signal })), state.data.inquiries?.find(item => item.callId === restoredCall));
                    if (['CALLING', 'PENDING'].includes(state.data.selected.status)) {
                        state.view = state.data.selected.status === 'PENDING' ? 'waiting' : 'call';
                        await subscribeCall(restoredCall, Client);
                        if (state.role === 'AGENT') pollSolution(restoredCall);
                    } else storage.removeItem(activeCallKey);
                });
            }
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
            });
        },
        signup(input) {
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
            return action(async (wait, signal) => {
                const callId = state.data.selected.callId;
                const updated = await wait(api.changeCallStatus(callId, status, { signal }));
                state.data.selected = mapCall(updated, state.data.selected);
                finishLocally(updated.status);
            });
        },
        sendRecognizedText(value) {
            if (isPreview || state.data.connection !== 'connected' || !validateUtterance(value)) return false;
            try {
                channel.send(value);
                state.data.translations.push({ id: `local-${++localMessageId}`, local: true,
                    speaker: text('나', 'Me'), roleLabel: text('상담원', 'Customer'),
                    text: value, time: utcNow(), needsReview: false,
                });
                notify();
                return true;
            } catch (error) {
                errorNotice(error);
                return false;
            }
        },
        dispose() {
            disposed = true;
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
