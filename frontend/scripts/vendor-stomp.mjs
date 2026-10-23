import { mkdir, copyFile } from 'node:fs/promises';

const destination = new URL('../public/vendor/', import.meta.url);
await mkdir(destination, { recursive: true });
await copyFile(
    new URL('../node_modules/@stomp/stompjs/bundles/stomp.umd.min.js', import.meta.url),
    new URL('stomp.umd.min.js', destination),
);
await copyFile(
    new URL('../node_modules/@stomp/stompjs/LICENSE', import.meta.url),
    new URL('stomp.LICENSE', destination),
);
console.log('STOMP 브라우저 파일 준비 완료');
