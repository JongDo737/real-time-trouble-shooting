export const UTC_TIME_ZONE = 'UTC';

function parseTimestamp(value) {
    if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
    if (typeof value !== 'string') return null;
    // 시간대 없는 값이나 초/밀리초 숫자는 추측하지 않습니다.
    const parts = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/i);
    if (!parts) return null;
    const[, year, month, day, hour, minute, second] = parts;
    const daysInMonth = new Date(Date.UTC(Number(year), Number(month), 0)).getUTCDate();
    if (Number(month) < 1 || Number(month) > 12 || Number(day) < 1 || Number(day) > daysInMonth || Number(hour) > 23 || Number(minute) > 59 || Number(second) > 59) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
}

export function toUtcIso(value) {
    return parseTimestamp(value)?.toISOString() ?? null;
}

export function utcNow() {
    return new Date().toISOString();
}

export function formatUtcTimestamp(value) {
    const iso = toUtcIso(value);
    return iso ?`${iso.slice(0, 10)} ${iso.slice(11, 19)} UTC`: '—';
}

export function formatTimeAgo(value, language = 'ko', now = Date.now()) {
    const iso = toUtcIso(value);
    if (!iso) return '—';
    const elapsed = Math.floor((now - new Date(iso).getTime()) / 1000);
    if (elapsed < 0) return formatUtcTimestamp(value);
    if (elapsed < 60) return language === 'ko' ? '방금 전' : 'Just now';
    const [amount, korean, english] = elapsed < 3600
        ? [Math.floor(elapsed / 60), '분', 'minute']
        : elapsed < 86400
            ? [Math.floor(elapsed / 3600), '시간', 'hour']
            : [Math.floor(elapsed / 86400), '일', 'day'];
    return language === 'ko'
        ? `${amount}${korean} 전`
        : `${amount} ${english}${amount === 1 ? '' : 's'} ago`;
}
