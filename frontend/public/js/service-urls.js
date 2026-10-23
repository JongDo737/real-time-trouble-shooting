function joinServiceUrl(baseAddress, relativePath, protocols) {
    if (!baseAddress) throw new Error('서버 기본 주소가 설정되지 않았습니다.');
    const base = new URL(baseAddress);
    if (!protocols.includes(base.protocol) || base.username || base.password || base.search || base.hash) {
        throw new Error('서버 기본 주소의 형식을 확인해 주세요.');
    }
    if (typeof relativePath !== 'string' || !relativePath.trim() || relativePath !== relativePath.trim() || /^[\\/]/.test(relativePath) || /^[a-z][a-z\d+.-]*:/i.test(relativePath)) {
        throw new Error('기능 경로는 앞에 / 없는 상대 경로를 사용해 주세요.');
    }
    if (!base.pathname.endsWith('/')) base.pathname += '/';
    const result = new URL(relativePath, base);
    // 기본 주소의 경로가 사라지지 않도록 확인합니다.
    if (result.origin !== base.origin || !result.pathname.startsWith(base.pathname) || result.hash) {
        throw new Error('기능 경로가 서버 기본 주소를 벗어났습니다.');
    }
    return result.href;
}

export function createServiceUrls(settings) {
    return Object.freeze({
        api: relativePath => joinServiceUrl(settings.API_BASE_URL, relativePath,['http:', 'https:']),
        socket: relativePath => joinServiceUrl(settings.WS_BASE_URL, relativePath,['ws:', 'wss:'])
    });
}
