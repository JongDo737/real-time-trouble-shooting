// 보이스 AI 예제의 독립 녹음 파일을 문장 단위로 생성해 Whisper로 순서대로 전송합니다.
export function createSilenceDetector() {
    let voicedFrames = 0, lastVoice = 0;
    return {
        get hasSpeech() { return voicedFrames >= 3; },
        sample(rms, now) {
            if (rms >= 0.015) { voicedFrames++; lastVoice = now; }
            return voicedFrames >= 3 && now - lastVoice >= 1000;
        },
    };
}

export function createRecordedSpeechInput({ Recorder, getUserMedia, AudioContext, continuous = false,
    secureContext = true, transcribe, onFinal, onChange = () => {} }) {
    let state = { supported: typeof Recorder === 'function' && typeof getUserMedia === 'function', secureContext,
        provider: 'whisper', status: 'idle', processing: false, interim: '', lastTranscript: '', error: '' };
    let session = 0, recorder, stream, timer, monitor, request, audioContext, analyser;
    let language, recording = false, processing = false;
    const queue = [];
    const update = patch => { state = { ...state, ...patch }; onChange(state); };
    const release = () => {
        clearInterval(monitor);
        stream?.getTracks().forEach(track => { track.onended = null; track.stop(); }); stream = null;
        if (audioContext) { audioContext.close().catch(() => {}); audioContext = null; analyser = null; }
    };
    const cancel = (error = '') => {
        session++; recording = false; processing = false; queue.length = 0;
        clearTimeout(timer); clearInterval(monitor); request?.abort();
        if (recorder) {
            recorder.onstop = recorder.ondataavailable = recorder.onerror = null;
            try { if (recorder.state !== 'inactive') recorder.stop(); } catch { /* 이미 종료됨 */ }
            recorder = null;
        }
        release();
        if (state.status !== 'idle' || state.processing || error) update({ status: error ? 'error' : 'idle', processing: false, error });
    };
    async function processQueue(version) {
        if (processing || version !== session) return;
        processing = true; update({ processing: true });
        while (queue.length && version === session) {
            const blob = queue.shift(); request = new AbortController();
            const timeout = setTimeout(() => { if (version === session) cancel('stt-timeout'); }, 120000);
            try {
                const text = (await transcribe(blob, language, request.signal)).trim();
                if (version !== session) return;
                if (text) {
                    update({ lastTranscript: text });
                    if (text.length > 2000) { cancel('too-long'); return; }
                    let delivered = false;
                    try { delivered = onFinal(text) === true; } catch { /* 전송 실패는 음성 변환 실패와 구분 */ }
                    if (!delivered) { cancel('send-failed'); return; }
                } else if (!continuous) { cancel('no-speech'); return; }
            } catch (error) {
                if (version === session) cancel(error.code || 'stt-failed');
                return;
            } finally { clearTimeout(timeout); }
        }
        if (version === session) { processing = false; update({ processing: false, status: recording ? 'listening' : 'idle' }); }
    }
    function segment(version) {
        if (!recording || version !== session) return;
        const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find(type => Recorder.isTypeSupported?.(type));
        const current = new Recorder(stream, mimeType ? { mimeType } : undefined);
        recorder = current;
        const chunks = [], detector = createSilenceDetector();
        let measured = false;
        current.ondataavailable = event => { if (version === session && event.data?.size) chunks.push(event.data); };
        current.onerror = () => { if (version === session) cancel('audio-capture'); };
        current.onstop = () => {
            clearTimeout(timer); clearInterval(monitor);
            if (version !== session) return;
            recorder = null;
            const blob = new Blob(chunks, { type: current.mimeType || mimeType || 'audio/webm' });
            if (blob.size && (!measured || detector.hasSpeech)) {
                if (queue.length >= 3) { cancel('stt-backlog'); return; }
                queue.push(blob);
            }
            if (recording) {
                try { segment(version); } catch { cancel('audio-capture'); return; }
            } else release();
            if (queue.length) void processQueue(version);
            else if (!recording && !processing) update({ status: 'idle' });
        };
        current.start();
        timer = setTimeout(() => { if (version === session) { if (!continuous) recording = false; current.stop(); } }, 30000);
        if (analyser) {
            const samples = new Float32Array(analyser.fftSize);
            monitor = setInterval(() => {
                if (version !== session || current.state !== 'recording' || audioContext?.state !== 'running') return;
                measured = true; analyser.getFloatTimeDomainData(samples);
                const rms = Math.sqrt(samples.reduce((sum, n) => sum + n * n, 0) / samples.length);
                if (detector.sample(rms, Date.now())) current.stop();
            }, 100);
        }
    }
    return {
        get state() { return state; },
        async start(lang) {
            if (['starting', 'listening', 'stopping'].includes(state.status)) return false;
            if (!state.supported || !secureContext) {
                update({ status: 'error', error: !secureContext ? 'insecure-context' : 'unsupported' }); return false;
            }
            const version = ++session; language = lang; recording = true;
            update({ status: 'starting', lastTranscript: '', error: '' });
            try {
                const captured = await getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false });
                if (version !== session) { captured.getTracks().forEach(track => track.stop()); return false; }
                stream = captured;
                stream.getTracks().forEach(track => {
                    track.onended = () => { if (version === session) cancel('audio-capture'); };
                });
                if (continuous && AudioContext) {
                    audioContext = new AudioContext(); analyser = audioContext.createAnalyser(); analyser.fftSize = 1024;
                    audioContext.createMediaStreamSource(stream).connect(analyser);
                    void audioContext.resume().catch(() => {});
                }
                segment(version); update({ status: 'listening' }); return true;
            } catch (error) {
                if (version === session) cancel(['NotAllowedError', 'SecurityError'].includes(error.name) ? 'not-allowed' : 'audio-capture');
                return false;
            }
        },
        stop() {
            if (state.status === 'starting') { cancel(); return; }
            recording = false;
            if (!recorder) return;
            clearTimeout(timer); clearInterval(monitor); update({ status: 'stopping' });
            try { recorder.stop(); } catch { cancel('audio-capture'); }
        },
        cancel,
    };
}

export function createTranscriber({ endpoint, getAccessToken, fetchImpl = globalThis.fetch }) {
    return async (audio, language, signal) => {
        const token = getAccessToken();
        if (!token) throw Object.assign(new Error(), { code: 'stt-unauthorized' });
        const body = new FormData();
        body.append('audio', audio, audio.type.includes('mp4') ? 'recording.mp4' : 'recording.webm');
        body.append('language', language.startsWith('ko') ? 'ko' : 'en');
        const response = await fetchImpl(endpoint, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body, credentials: 'omit', signal });
        if (!response.ok) throw Object.assign(new Error(), { code: response.status === 401 ? 'stt-unauthorized' : 'stt-failed' });
        const result = await response.json();
        if (typeof result.text !== 'string' || result.error) throw Object.assign(new Error(), { code: 'stt-failed' });
        return result.text;
    };
}
