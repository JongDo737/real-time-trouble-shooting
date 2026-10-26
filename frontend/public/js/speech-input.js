// 확정된 문장만 전달합니다. 인식기 이벤트는 시작한 세션 안에서만 유효합니다.
export function createSpeechInput({ Recognition, secureContext = true, onFinal, onChange = () => {} }) {
    let recognition = null;
    let state = { supported: typeof Recognition === 'function', secureContext, status: 'idle', interim: '', lastTranscript: '', error: '' };
    const update = patch => { state = { ...state, ...patch }; onChange(state); };

    function cancel(error = '') {
        const previous = recognition;
        recognition = null;
        if (previous) {
            previous.onstart = previous.onresult = previous.onerror = previous.onend = null;
            try { previous.abort(); } catch { /* 이미 종료된 인식기 */ }
        }
        if (previous || state.status !== 'idle') update({ status: error ? 'error' : 'idle', interim: '', error });
    }

    return {
        get state() { return state; },
        start(lang) {
            if (recognition) return false;
            if (!state.supported || !secureContext) {
                update({ status: 'error', error: state.supported ? 'insecure-context' : 'unsupported' });
                return false;
            }
            let current;
            try {
                current = new Recognition();
                recognition = current;
                current.lang = lang;
                current.continuous = true;
                current.interimResults = true;
                current.maxAlternatives = 1;
                const sent = new Set();
                current.onstart = () => {
                    if (recognition === current && state.status === 'starting') update({ status: 'listening' });
                };
                current.onresult = event => {
                    if (recognition !== current) return;
                    const interim = [];
                    for (let i = 0; i < event.results.length; i++) {
                        const result = event.results[i];
                        const text = result[0]?.transcript?.trim() || '';
                        if (!result.isFinal) { if (text) interim.push(text); continue; }
                        if (sent.has(i) || !text) continue;
                        sent.add(i);
                        update({ lastTranscript: text });
                        if (recognition !== current) return;
                        if (text.length > 2000) { cancel('too-long'); return; }
                        let delivered = false;
                        try { delivered = onFinal(text) === true; } catch { /* 전송 실패는 아래에서 안내 */ }
                        if (!delivered) { cancel('send-failed'); return; }
                    }
                    if (recognition === current) update({ interim: interim.join(' ') });
                };
                current.onerror = event => {
                    if (recognition === current) cancel(event.error || 'unknown');
                };
                current.onend = () => {
                    if (recognition !== current) return;
                    recognition = null;
                    update({ status: 'idle', interim: '' });
                };
                update({ status: 'starting', interim: '', lastTranscript: '', error: '' });
                current.start();
                return true;
            } catch (error) {
                if (!current) update({ status: 'error', error: 'start-failed' });
                else if (recognition === current) cancel(error.name === 'NotAllowedError' ? 'not-allowed' : 'start-failed');
                return false;
            }
        },
        stop() {
            if (!recognition || state.status === 'stopping') return;
            update({ status: 'stopping' });
            try { recognition.stop(); } catch { cancel(); }
        },
        cancel,
    };
}
