const raw = window.RILSHU_CONFIG || {};
export const config = Object.freeze({
    API_BASE_URL: raw.API_BASE_URL || '',
    WS_BASE_URL: raw.WS_BASE_URL || '',
    MOCK_ROLE: raw.MOCK_ROLE === 'CUSTOMER' ? 'CUSTOMER' : 'AGENT',
    ENABLE_UI_PREVIEW: raw.ENABLE_UI_PREVIEW === true
});
export const isPreview = config.ENABLE_UI_PREVIEW && window.location.pathname.endsWith('/preview.html');
