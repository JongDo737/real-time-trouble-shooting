const sessionKey = 'rilshu.session';

export function createSessionStore(storage, now = Date.now) {
    return {
        read() {
            try {
                const saved = JSON.parse(storage.getItem(sessionKey));
                if (!saved?.accessToken || !['USER', 'ADMIN'].includes(saved.user?.role) || !Number.isFinite(saved.expiresAt) || saved.expiresAt <= now()) {
                    this.clear();
                    return null;
                }
                return saved;
            } catch {
                this.clear();
                return null;
            }
        },
        save(response) {
            if (!response?.accessToken || !['USER', 'ADMIN'].includes(response.user?.role) || !Number.isFinite(response.expiresIn) || response.expiresIn <= 0) {
                throw new Error('로그인 응답을 확인해 주세요.');
            }
            const saved = {
                accessToken: response.accessToken,
                user: response.user,
                expiresAt: now() + response.expiresIn * 1000,
            };
            storage.setItem(sessionKey, JSON.stringify(saved));
            return saved;
        },
        clear() { storage.removeItem(sessionKey); },
    };
}
