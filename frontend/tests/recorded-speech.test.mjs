import test from 'node:test';
import assert from 'node:assert/strict';
import { createRecordedSpeechInput, createSilenceDetector, createTranscriber } from '../public/js/recorded-speech.js';

class Recorder {
    static last;
    static isTypeSupported(type) { return type === 'audio/webm'; }
    constructor(stream, options) { this.stream = stream; this.mimeType = options.mimeType; this.state = 'inactive'; Recorder.last = this; }
    start() { this.state = 'recording'; }
    stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['test-audio'], { type: this.mimeType }) }); this.onstop?.(); }
}
const flush = () => new Promise(resolve => setImmediate(resolve));
function setup(overrides = {}) {
    let released = false;
    const sent = [];
    const speech = createRecordedSpeechInput({
        Recorder, getUserMedia: async () => ({ getTracks: () => [{ stop: () => { released = true; } }] }),
        transcribe: async () => ' Recognized phrase ', onFinal: text => { sent.push(text); return true; }, ...overrides,
    });
    return { speech, sent, released: () => released };
}

test('recording stops, releases microphone, transcribes and sends text once', async () => {
    const { speech, sent, released } = setup();
    await speech.start('en-US');
    assert.equal(speech.state.provider, 'whisper');
    assert.equal(speech.state.status, 'listening');
    assert.deepEqual(sent, []);
    speech.stop();
    await flush();
    assert.equal(speech.state.status, 'idle');
    assert.ok(released());
    assert.deepEqual(sent, ['Recognized phrase']);
    speech.cancel();
});

test('logout during transcription aborts the request and ignores its late response', async () => {
    let resolve, signal;
    const { speech, sent } = setup({ transcribe: (_, __, requestSignal) => { signal = requestSignal; return new Promise(done => { resolve = done; }); } });
    await speech.start('ko-KR');
    speech.stop();
    speech.cancel();
    assert.equal(signal.aborted, true);
    resolve('Do not send');
    await flush();
    assert.deepEqual(sent, []);
    assert.equal(speech.state.status, 'idle');
});

test('cancel while permission is pending releases a late microphone stream without recording', async () => {
    let permission, released = false;
    const { speech } = setup({ getUserMedia: () => new Promise(resolve => { permission = resolve; }) });
    const pending = speech.start('en-US');
    speech.stop();
    permission({ getTracks: () => [{ stop: () => { released = true; } }] });
    assert.equal(await pending, false);
    assert.equal(speech.state.status, 'idle');
    assert.ok(released);
});

test('disconnected microphone stops recording and discards unfinished audio', async () => {
    let released = false;
    const track = { stop() { released = true; } };
    const { speech, sent } = setup({ getUserMedia: async () => ({ getTracks: () => [track] }) });
    await speech.start('ko-KR');
    const recorder = Recorder.last;
    track.onended();
    assert.equal(speech.state.status, 'error');
    assert.equal(speech.state.error, 'audio-capture');
    assert.equal(recorder.state, 'inactive');
    assert.equal(track.onended, null);
    assert.ok(released);
    assert.deepEqual(sent, []);
});

test('a thrown message delivery error is reported as send-failed instead of transcription failure', async () => {
    const { speech } = setup({ onFinal: () => { throw new Error('Socket disconnected'); } });
    await speech.start('ko-KR');
    speech.stop(); await flush();
    assert.equal(speech.state.error, 'send-failed');
    assert.equal(speech.state.lastTranscript, 'Recognized phrase');
});

test('silence and failed transcription keep the conversation free of invalid messages', async () => {
    for (const transcribe of [async () => '', async () => { throw Object.assign(new Error(), { code: 'stt-unauthorized' }); }]) {
        const { speech, sent } = setup({ transcribe });
        await speech.start('en-US'); speech.stop(); await flush();
        assert.equal(speech.state.status, 'error');
        assert.deepEqual(sent, []);
        speech.cancel();
    }
});

test('Whisper uploads the audio field and role language with the existing Bearer token', async () => {
    let request;
    const transcribe = createTranscriber({ endpoint: 'https://example.invalid/voice/stt/', getAccessToken: () => 'test-only-token',
        fetchImpl: async (url, options) => { request = { url, ...options }; return Response.json({ text: '인식한 문장' }); } });
    assert.equal(await transcribe(new Blob(['audio'], { type: 'audio/webm' }), 'ko-KR'), '인식한 문장');
    assert.equal(request.headers.Authorization, 'Bearer test-only-token');
    assert.equal(request.headers['Content-Type'], undefined);
    assert.equal(request.body.get('audio').name, 'recording.webm');
    assert.equal(request.body.get('language'), 'ko');
    assert.equal(request.credentials, 'omit');
});

test('silence ends a phrase only after speech, and no speech does not create uploads', () => {
    const silence = createSilenceDetector();
    assert.equal(silence.sample(0, 10000), false);
    assert.equal(silence.hasSpeech, false);
    silence.sample(0.05, 10100); silence.sample(0.05, 10200); silence.sample(0.05, 10300);
    assert.equal(silence.hasSpeech, true);
    assert.equal(silence.sample(0, 11200), false);
    assert.equal(silence.sample(0, 11300), true);
});

test('continuous recording starts the next segment before previous transcription completes', async () => {
    let resolve;
    const { speech, sent, released } = setup({ continuous: true, transcribe: () => new Promise(done => { resolve = done; }) });
    await speech.start('ko-KR');
    const first = Recorder.last;
    first.stop();
    assert.notEqual(Recorder.last, first);
    assert.equal(Recorder.last.state, 'recording');
    assert.equal(released(), false);
    assert.equal(speech.state.processing, true);
    resolve('첫 번째 문장'); await flush();
    assert.deepEqual(sent, ['첫 번째 문장']);
    assert.equal(speech.state.status, 'listening');
    speech.cancel();
    assert.ok(released());
});
