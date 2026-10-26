import { resolveServiceAddress } from './service-urls.js';

const raw = window.RILSHU_CONFIG || {};
export const config = Object.freeze({
    API_BASE_URL: resolveServiceAddress(raw.API_BASE_URL, window.location.origin),
    WS_BASE_URL: resolveServiceAddress(raw.WS_BASE_URL, window.location.origin, { socket: true }),
    STT_URL: resolveServiceAddress(raw.STT_URL, window.location.origin),
    MOCK_ROLE: raw.MOCK_ROLE === 'CUSTOMER' ? 'CUSTOMER' : 'AGENT',
    ENABLE_UI_PREVIEW: raw.ENABLE_UI_PREVIEW === true
});
export const isPreview = config.ENABLE_UI_PREVIEW && window.location.pathname.endsWith('/preview.html');
