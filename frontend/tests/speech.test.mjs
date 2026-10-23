import test from 'node:test';
import assert from 'node:assert/strict';
import { createSpeechInput } from '../public/js/speech-input.js';

class Recognition {
    static last;
    constructor() { Recognition.last = this; }
    start() { this.onstart?.(); }
    stop() { this.stopped = true; }
    abort() { this.aborted = true; }
}
const result = (text, isFinal) => Object.assign([{ transcript: text }], { isFinal });

test('only final results are sent once per result index; repeated spoken phrases remain valid', () => {
    const sent = [];
    const speech = createSpeechInput({ Recognition, onFinal: text => { sent.push(text); return true; } });
    speech.start('ko-KR');
    const engine = Recognition.last;
    assert.equal(engine.lang, 'ko-KR');
    assert.equal(engine.continuous, true);
    engine.onresult({ results: [result('인식 중', false)] });
    assert.deepEqual(sent, []);
    assert.equal(speech.state.interim, '인식 중');
    const final = result('  확정 문장  ', true);
    engine.onresult({ results: [final] });
    engine.onresult({ results: [final] });
    engine.onresult({ results: [final, result('확정 문장', true)] });
    assert.deepEqual(sent, ['확정 문장', '확정 문장']);
    speech.cancel();
});

test('stop allows the final phrase; cancellation blocks late results and releases the microphone', () => {
    const sent = [];
    const speech = createSpeechInput({ Recognition, onFinal: text => { sent.push(text); return true; } });
    speech.start('en-US');
    const engine = Recognition.last;
    speech.stop();
    assert.equal(speech.state.status, 'stopping');
    assert.ok(engine.stopped);
    engine.onresult({ results: [result('Final phrase', true)] });
    engine.onend();
    assert.equal(speech.state.status, 'idle');
    speech.start('en-US');
    const next = Recognition.last;
    const lateResult = next.onresult;
    speech.cancel();
    assert.ok(next.aborted);
    lateResult({ results: [result('Do not send after logout', true)] });
    assert.deepEqual(sent, ['Final phrase']);
});

test('unsupported and insecure environments do not start audio capture', () => {
    const unsupported = createSpeechInput({ onFinal: () => true });
    assert.equal(unsupported.start('en-US'), false);
    assert.equal(unsupported.state.error, 'unsupported');
    const insecure = createSpeechInput({ Recognition, secureContext: false, onFinal: () => true });
    assert.equal(insecure.start('en-US'), false);
    assert.equal(insecure.state.error, 'insecure-context');
});

test('permission and network errors stop capture and preserve a useful error state', () => {
    for (const error of ['not-allowed', 'network', 'audio-capture', 'no-speech']) {
        const speech = createSpeechInput({ Recognition, onFinal: () => true });
        speech.start('en-US');
        const engine = Recognition.last;
        engine.onerror({ error });
        assert.equal(speech.state.status, 'error');
        assert.equal(speech.state.error, error);
        assert.ok(engine.aborted);
    }
});

test('failed transmission retains recognized text and stops instead of silently losing speech', () => {
    const speech = createSpeechInput({ Recognition, onFinal: () => false });
    speech.start('en-US');
    Recognition.last.onresult({ results: [result('Keep this phrase', true)] });
    assert.equal(speech.state.lastTranscript, 'Keep this phrase');
    assert.equal(speech.state.error, 'send-failed');
    assert.ok(Recognition.last.aborted);
});

test('oversized speech does not reach the backend and startup failures are recoverable', () => {
    let sent = 0;
    const speech = createSpeechInput({ Recognition, onFinal: () => { sent++; return true; } });
    speech.start('en-US');
    Recognition.last.onresult({ results: [result('a'.repeat(2001), true)] });
    assert.equal(sent, 0);
    assert.equal(speech.state.error, 'too-long');
    class BrokenRecognition { constructor() { throw new Error('unavailable'); } }
    const broken = createSpeechInput({ Recognition: BrokenRecognition, onFinal: () => true });
    assert.equal(broken.start('en-US'), false);
    assert.equal(broken.state.error, 'start-failed');
});
