import test from 'node:test';
import assert from 'node:assert/strict';
import { createServiceUrls } from '../public/js/service-urls.js';
import { toUtcIso, formatUtcTimestamp, formatLocalTimestamp, utcNow } from '../public/js/utc.js';

const urls = createServiceUrls({ API_BASE_URL:'http://realshoot/backend/api/', WS_BASE_URL:'ws://realshoot/backend/ws/' });
test('keeps API and socket base paths when joining agreed relative paths', () => {
    assert.equal(urls.api('example?state=PENDING'), 'http://realshoot/backend/api/example?state=PENDING');
    assert.equal(urls.socket('example'), 'ws://realshoot/backend/ws/example');
    const secure = createServiceUrls({ API_BASE_URL:'https://host.invalid/backend/api', WS_BASE_URL:'wss://host.invalid/backend/ws' });
    assert.equal(secure.api('example'), 'https://host.invalid/backend/api/example');
    assert.equal(secure.socket('example'), 'wss://host.invalid/backend/ws/example');
});
test('does not guess missing URLs or allow base path replacement', () => {
    assert.throws(() => createServiceUrls({}).api('example'), /설정/);
    for (const path of[
        '/example',
        '//other.invalid/path',
        'https://other.invalid/path',
        '../example',
        '%2e%2e/example',
        '\\example',
        ' example'
    ]) assert.throws(() => urls.api(path));
    assert.throws(() => createServiceUrls({ API_BASE_URL:'ws://host.invalid/' }).api('example'));
});
test('normalizes explicit offsets to UTC, including date boundaries', () => {
    assert.equal(toUtcIso('2026-10-23T01:30:00Z'), '2026-10-23T01:30:00.000Z');
    assert.equal(toUtcIso('2026-10-23T01:30:00+09:00'), '2026-10-22T16:30:00.000Z');
    assert.equal(formatUtcTimestamp('2026-10-23T01:30:00+09:00'), '2026-10-22 16:30:00 UTC');
});

test('displays API UTC timestamps in the selected local zone including DST and date boundaries', () => {
    assert.equal(formatLocalTimestamp('2026-10-23T09:11:02.120Z', 'Asia/Seoul'), '2026-10-23 18:11:02 Asia/Seoul');
    assert.equal(formatLocalTimestamp('2026-10-23T02:00:00Z', 'America/Los_Angeles'), '2026-10-22 19:00:00 America/Los_Angeles');
    assert.equal(formatLocalTimestamp('2026-01-23T02:00:00Z', 'America/Los_Angeles'), '2026-01-22 18:00:00 America/Los_Angeles');
    assert.equal(formatLocalTimestamp('2026-10-23T09:11:02'), '—');
});
test('does not interpret ambiguous or invalid dates as local time', () => {
    for(const value of[
        null,
        undefined,
        '',
        '09:21:03',
        '2026-10-23T01:30:00',
        1792719000,
        '2026-02-30T00:00:00Z',
        '2026-13-01T00:00:00Z',
        '2026-10-23T24:00:00Z'
    ]) {
        assert.equal(toUtcIso(value), null);assert.equal(formatUtcTimestamp(value), '—');
    }
    assert.equal(toUtcIso('2028-02-29T00:00:00Z'), '2028-02-29T00:00:00.000Z');
    assert.match(utcNow(), /^\d{4}-\d{2}-\d{2}T.*Z$/);
});
