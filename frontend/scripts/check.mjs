import { readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

async function findJavaScriptFiles(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    const nestedFiles = await Promise.all(entries.map(entry => {
        const path = join(directory, entry.name);
        return entry.isDirectory() ? findJavaScriptFiles(path) : [path];
    }));
    return nestedFiles.flat().filter(path => /\.(js|mjs)$/.test(path));
}
const files = ['server.mjs', ...await findJavaScriptFiles('public/js'), ...await findJavaScriptFiles('scripts')];
for (const file of files) {
    const result = spawnSync(process.execPath, ['--check', file], { stdio: 'inherit' });
    if (result.status !== 0) process.exit(result.status ?? 1);
}
console.log(`${files.length}개 JavaScript 파일 구문 검사 통과`);
