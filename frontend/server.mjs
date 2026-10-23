import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, extname, sep } from 'node:path';

const root = fileURLToPath(new URL('./public/', import.meta.url));
const port = Number(process.env.PORT || 8080);
const host = process.env.HOST || '0.0.0.0';
const mime = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
// 브라우저에 공개할 설정만 전달합니다.
const config = {
    API_BASE_URL: process.env.API_BASE_URL || '',
    WS_BASE_URL: process.env.WS_BASE_URL || '',
    MOCK_ROLE: process.env.MOCK_ROLE || 'AGENT',
    ENABLE_UI_PREVIEW: process.env.ENABLE_UI_PREVIEW === 'true'
};
http.createServer(async (req, res) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'same-origin');
    res.setHeader('Cache-Control', 'no-store');
    if (!['GET', 'HEAD'].includes(req.method)) {
        res.writeHead(405, { Allow: 'GET, HEAD' }); res.end(); return;
    }
    try {
        const pathname = decodeURIComponent(new URL(req.url, 'http://local.invalid').pathname);
        if (pathname === '/runtime-config.js') {
            res.writeHead(200, { 'Content-Type': 'text/javascript; charset=utf-8' });
            res.end(req.method === 'HEAD' ? undefined :`window.RILSHU_CONFIG = ${JSON.stringify(config).replaceAll('<', '\\u003c')};`);
            return;
        }
        if (pathname === '/preview.html' && !config.ENABLE_UI_PREVIEW) {
            res.writeHead(404); res.end(); return;
        }
        const path = resolve(root, `.${pathname === '/' ? '/index.html' : pathname}`);
        if (!path.startsWith(root.endsWith(sep) ? root : root + sep)) {
            res.writeHead(403); res.end(); return;
        }
        const body = await readFile(path);
        res.writeHead(200, { 'Content-Type':`${mime[extname(path)] || 'application/octet-stream'}; charset=utf-8` });
        res.end(req.method === 'HEAD' ? undefined : body);
    } catch {
        res.writeHead(404); res.end('Not found');
    }
}).listen(port, host, () => console.log(`릴슈 프론트 시작 · port ${port}`));
