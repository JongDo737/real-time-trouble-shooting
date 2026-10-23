import test from 'node:test';
import assert from 'node:assert/strict';
import { createState, escapeHTML, summaryStatuses, statuses } from '../public/js/model.js';

test('unconnected data is unknown, not zero or fabricated requests', () => {
    const state = createState();
    assert.equal(state.inquiries, null); assert.equal(state.summary, null);
    assert.deepEqual(state.translations, []);
    assert.equal(state.connection, 'disconnected');
    assert.equal(state.page, 0);
    assert.equal(state.size, 20);
    assert.equal(state.totalPages, 0);
    assert.equal(state.solution, null);
    state.translations.push({ id: 'test-only' });
    assert.deepEqual(createState().translations, []);
});
test('calling remains a valid state but is excluded from summary display', () => {
    assert.ok(statuses.includes('CALLING')); assert.ok(!summaryStatuses.includes('CALLING'));
});
test('remote issue descriptions and names cannot inject markup', () => {
    assert.equal(escapeHTML('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
});
